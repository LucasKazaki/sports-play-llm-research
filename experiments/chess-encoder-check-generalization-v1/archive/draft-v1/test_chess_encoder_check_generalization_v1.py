"""CPU legal-replay fixtures only; no pretrained or engine calls."""
from collections import Counter
import copy
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_encoder_check_generalization_v1 as panel


def source(kind='king',game='abc12345',puzzle='puzzle1',ordinal=0):
    before={'king':'5k2/8/8/8/4K3/8/8/4R3 b - - 0 1',
        'knights':'5k2/8/8/8/4N3/8/8/KN2R3 b - - 0 1',
        'pawn':'8/8/8/3k4/8/8/5P2/K7 b - - 0 1'}[kind]
    return ({'source_ordinal':ordinal,'row_group':0,'row_in_group':ordinal},
        {'GameId':game,'PuzzleId':puzzle,'FEN':before,
            'Moves':('d5e5'if kind=='pawn'else'f8e8')+' INVALID_ANSWER_TAIL_MUST_NOT_BE_PARSED',
            'Themes':'ignored answer-like metadata'})


def current(kind):
    _,row=source(kind);board=chess.Board(row['FEN']);before=panel.board_key(board.fen())
    board.push_uci(row['Moves'].split()[0]);return board,before


def test_ordinary_king_discovered_check_and_strict_same_origin_negative():
    board,before=current('king')
    yes=panel.describe_move(board,chess.Move.from_uci('e4d4'))
    no=panel.describe_move(board,chess.Move.from_uci('e4e5'))
    assert yes['gives_check']and yes['king_mover']and yes['discovered_check']and yes['checkers']==['e1']
    assert not no['gives_check']and panel.allocation(yes)=='king_mover'
    result=panel.candidate_pair(board,'abc12345',1,set(),panel.QUOTAS,before)
    assert result[0]=='king_mover'and result[1]['source']==result[2]['source']


def test_direct_pawn_double_push_matches_single_push_noncheck_same_origin():
    board,before=current('pawn')
    yes=panel.describe_move(board,chess.Move.from_uci('f2f4'))
    no=panel.describe_move(board,chess.Move.from_uci('f2f3'))
    assert yes['pawn_mover']and yes['gives_check']and not yes['discovered_check']
    assert not no['gives_check']and panel.allocation(yes)=='pawn_mover'
    result=panel.candidate_pair(board,'abc12345',1,set(),panel.QUOTAS,before)
    assert result[0]=='pawn_mover'and result[1]['source']==result[2]['source']


def test_discovered_and_double_checker_has_no_same_origin_noncheck_but_other_instance_works():
    board,before=current('knights')
    assert board.is_valid()
    same=[move for move in board.legal_moves if move.from_square==chess.E4]
    assert same and all(board.gives_check(move)for move in same)
    double=panel.describe_move(board,chess.Move.from_uci('e4f6'))
    discovered=panel.describe_move(board,chess.Move.from_uci('e4c5'))
    negative=panel.describe_move(board,chess.Move.from_uci('b1a3'))
    assert double['checkers']==['e1','f6']and panel.allocation(double)=='double_check'
    assert discovered['checkers']==['e1']and panel.allocation(discovered)=='remaining_discovered_check'
    assert not negative['gives_check']and negative['piece']==double['piece']==chess.KNIGHT
    for target in('double_check','remaining_discovered_check'):
        remaining={name:int(name==target)for name in panel.STRATA}
        pair=panel.candidate_pair(board,'abc12345',4,set(),remaining,before)
        assert pair[0]==target and pair[1]['source']!=pair[2]['source']
        assert tuple(pair[1][key]for key in('piece','capture','victim'))==tuple(pair[2][key]for key in('piece','capture','victim'))


def test_overlap_allocation_priority_preserves_nonexclusive_truth_flags():
    truth={'gives_check':True,'king_mover':False,'pawn_mover':True,'double_check':True,'discovered_check':True}
    assert panel.allocation(truth)=='pawn_mover'
    truth['king_mover']=True
    assert panel.allocation(truth)=='king_mover'and truth['double_check']and truth['discovered_check']
    truth['gives_check']=False
    assert panel.allocation(truth)is None


def test_source_uses_only_first_setup_and_full_shortage_slots_stay_visible():
    values=[source()]
    result=panel.select_rows(values,set(),set(),panel.QUOTAS,4082084,500000)
    assert len(result['inputs'])==2 and sum(row['gives_check']for row in result['labels'])==1
    assert result['constructed_pairs']['king_mover']==1 and result['shortages']['king_mover']==15
    assert len(result['slots'])==64 and sum(row['planned_moves']for row in result['slots'])==128
    assert sum(row['status']=='source_shortage'for row in result['slots'])==63
    assert all(set(row)=={'case_id','fen','selected_uci'}for row in result['inputs'])
    assert result['metadata'][0]['matching_contract']=='same_origin'
    assert result['scanned_rows']==1 and result['last_source_ordinal']==0


def test_historical_game_before_current_and_every_successor_board_are_excluded():
    board,before=current('king');root=source()
    assert not panel.select_rows([root],{'abc12345'},set(),panel.QUOTAS,1,500000)['inputs']
    for key in(before,panel.board_key(board.fen())):
        assert not panel.select_rows([root],set(),{key},panel.QUOTAS,1,500000)['inputs']
    every_after=set()
    for move in board.legal_moves:
        after=board.copy();after.push(move);every_after.add(panel.board_key(after.fen()))
    assert not panel.select_rows([root],set(),every_after,panel.QUOTAS,1,500000)['inputs']


def test_new_game_and_path_reuse_cannot_enter_another_pair():
    cases=[source(),source(game='different'[:8],puzzle='puzzle2',ordinal=1),source(puzzle='puzzle3',ordinal=2)]
    result=panel.select_rows(cases,set(),set(),panel.QUOTAS,1,500000)
    assert len(result['metadata'])==1
    assert result['rejections']['excluded_before_board']==1 and result['rejections']['excluded_game']==1
    assert result['scanned_rows']==sum(result['rejections'].values())+len(result['metadata'])


def test_pair_choice_deterministic_and_forbidden_path_changes_candidates_without_reuse():
    board,before=current('knights');left=panel.candidate_pair(board,'abc12345',41,set(),panel.QUOTAS,before)
    assert left==panel.candidate_pair(board,'abc12345',41,set(),panel.QUOTAS,before)
    blocked={left[1]['successor_key'],left[2]['successor_key']}
    right=panel.candidate_pair(board,'abc12345',41,blocked,panel.QUOTAS,before)
    if right:assert not blocked&{right[1]['successor_key'],right[2]['successor_key']}


def test_registry_superset_never_assumes_missing_metadata_is_empty():
    registry={'games':['g'],'board_keys':['b']}
    assert panel.registry_superset(registry,{'g'},{'b'},'fixture')=={'games':1,'board_keys':1}
    for games,boards in[({'missing'},{'b'}),({'g'},{'missing'})]:
        with pytest.raises(ValueError,match='Reservation misses'):panel.registry_superset(registry,games,boards,'fixture')


def test_changed_quotas_or_nonconsecutive_source_prefix_rejected_and_check_before_selection():
    bad=dict(panel.QUOTAS);bad['king_mover']=1
    with pytest.raises(ValueError,match='quotas'):panel.select_rows([],set(),set(),bad,1,500000)
    with pytest.raises(ValueError,match='consecutive'):panel.select_rows([source(ordinal=1)],set(),set(),panel.QUOTAS,1,500000)
    def stopped(ordinal):raise RuntimeError('fixture owned CPU reserve')
    with pytest.raises(RuntimeError,match='CPU reserve'):
        panel.select_rows([source()],set(),set(),panel.QUOTAS,1,500000,check=stopped)


@pytest.mark.parametrize('fen,uci',[
    ('7k/P7/8/8/8/8/8/K7 w - - 0 1','a7a8q'),
    ('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1','e5d6'),
    ('4k3/8/8/8/8/8/8/4K2R w K - 0 1','e1g1')])
def test_special_moves_not_silently_added_to_generalization_scope(fen,uci):
    board=chess.Board(fen);move=chess.Move.from_uci(uci)
    assert move in board.legal_moves
    with pytest.raises(ValueError,match='Special'):panel.describe_move(board,move)
