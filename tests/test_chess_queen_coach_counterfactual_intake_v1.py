"""Authored legal-board fixtures only; no source intake, engine or model."""
from pathlib import Path
import sys
import chess
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_intake_v1 as subject


def source(game='abc12345',ordinal=0,kind='king'):
    fen='5k2/8/8/8/4K3/8/8/4R3 b - - 0 1'if kind=='king'else'5k2/8/8/8/4N3/8/8/KN2R3 b - - 0 1'
    return ({'source_ordinal':ordinal,'row_group':0,'row_in_group':ordinal},
        {'GameId':game,'PuzzleId':'fixture'+str(ordinal),'FEN':fen,'Moves':'f8e8 INVALID_ANSWER_TAIL'})


def select(values,games=set(),boards=set()):
    return subject.select_rows(values,games,boards,4082085,500000,{'train':2,'development':2,'reserve':2})


def test_pair_balanced_same_piece_capture_victim_and_origin_preference():
    _,row=source();before=chess.Board(row['FEN']);board=before.copy();board.push_uci('f8e8')
    pair=subject.matched_pair(board,'abc12345',4082085,set(),subject.board_key(before.fen()))
    assert sum(value['gives_check']for value in pair)==1
    assert len({tuple(value[key]for key in('piece','capture','victim'))for value in pair})==1
    assert pair[0]['source']==pair[1]['source']
    assert pair==subject.matched_pair(board,'abc12345',4082085,set(),subject.board_key(before.fen()))


def test_other_same_type_instance_fallback_for_ordinary_discovery():
    _,row=source(kind='knights');before=chess.Board(row['FEN']);board=before.copy();board.push_uci('f8e8')
    pair=subject.matched_pair(board,'abc12345',4082085,set(),subject.board_key(before.fen()))
    assert pair and sum(value['gives_check']for value in pair)==1
    assert pair[0]['source']!=pair[1]['source']and pair[0]['piece']==pair[1]['piece']==chess.KNIGHT


def test_first_setup_only_opaque_cases_all_requested_shortages_and_no_replacement():
    result=select([source()]);records=[row for roots in result['groups'].values()for row in roots]
    assert len(records)==1 and result['status']=='insufficient_cohort'
    assert sum(result['shortages'].values())==5 and len(result['slots'])==6
    assert all(case.endswith(subject.MODES[index])for index,case in enumerate(records[0]['case_ids']))
    assert not any('check'in case for case in records[0]['case_ids'])
    assert result['scanned_rows']==1


def test_games_before_current_and_selected_successor_novelty():
    assert sum(map(len,select([source()],{'abc12345'})['groups'].values()))==0
    _,row=source();before=chess.Board(row['FEN']);board=before.copy();board.push_uci('f8e8')
    for key in(subject.board_key(before.fen()),subject.board_key(board.fen())):
        assert not any(select([source()],boards={key})['groups'].values())
    after=set()
    for move in board.legal_moves:
        replay=board.copy();replay.push(move);after.add(subject.board_key(replay.fen()))
    assert not any(select([source()],boards=after)['groups'].values())
    repeated=select([source(),source('other123',1)])
    assert sum(map(len,repeated['groups'].values()))==1


@pytest.mark.parametrize('fen,moves',[
    ('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1','h8h7'),
    ('7k/8/8/8/8/8/R7/K7 w - - 150 76','a2a8'),
    ('7k/8/8/8/8/8/R7/K7 w - - 149 76','a2a8'),
    ('8/8/8/8/8/8/8/4K3 w - - 0 1','e1e2')])
def test_invalid_automatic_terminal_before_or_setup_successor_rejected(fen,moves):
    location,row=source();row.update(FEN=fen,Moves=moves)
    assert not any(select([(location,row)])['groups'].values())


def test_guard_failure_precedes_even_source_iteration():
    class Forbidden:
        def __iter__(self):raise AssertionError('source opened before guard')
    def fail(index):assert index==-1;raise RuntimeError('authored reserve failure')
    with pytest.raises(RuntimeError,match='reserve'):
        subject.select_rows(Forbidden(),set(),set(),4082085,500000,subject.COUNTS,guard=fail)


def test_journal_io_failure_is_not_silently_relabelled_source_rejection():
    def fail(row):raise OSError('authored disk failure')
    with pytest.raises(OSError,match='disk'):
        subject.select_rows([source()],set(),set(),4082085,500000,subject.COUNTS,record=fail)
