"""CPU raw-output checks; fixtures establish scoring behavior, never capability."""
from pathlib import Path
import sys

import chess

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_eval_v1 as scoring


def atom(board,uci,pov=None):
    pov=board.turn if pov is None else pov; move=chess.Move.from_uci(uci)
    piece=board.piece_at(move.from_square)
    square=lambda value:value+1 if pov else (value^56)+1
    side=lambda value:'M'if value==pov else'O'
    text=f'<PIECE_{side(piece.color)}{piece.symbol().upper()}><SQUARE_{square(move.from_square)}>'
    victim=chess.Piece(chess.PAWN,not board.turn)if board.is_en_passant(move)else board.piece_at(move.to_square)
    if victim:text+=f'<PIECE_{side(victim.color)}{victim.symbol().upper()}>'
    text+=f'<SQUARE_{square(move.to_square)}>'
    if move.promotion:text+=f'<PIECE_{side(piece.color)}{chess.piece_symbol(move.promotion).upper()}>'
    return text


def response(board,line,analysis=''):
    pov=board.turn;tokens=[];replay=board.copy()
    for uci in line:
        tokens.append(atom(replay,uci,pov));replay.push_uci(uci)
    return {'status':'completed','finish_reason':'eos','raw_text':
        'ANALYSIS:\n'+analysis+'\nBEST_MOVE: '+tokens[0]+'\nCRITICAL_LINE: '+' '.join(tokens)+
        '\nPROMISING_MOVES: '+tokens[0]+'\nEVALUATION: Not assessed.'}


def test_unrecognized_fluent_prose_is_unknown_not_false_or_accepted_as_true():
    board=chess.Board();out=response(board,['e2e4','e7e5','g1f3'],'A fluent paragraph with unverified plans.')
    result=scoring.score({'fen':board.fen()},out,{'reference_pv_uci':['e2e4','e7e5','g1f3']})
    assert result['accepted_best_legal']and result['critical_prefix_matches']=={'1':True,'2':True,'3':True}
    assert result['facts']['recognized_claims']==0 and result['facts']['false_claims']==0
    assert result['facts']['other_prose_audited']is False


def test_immediate_check_and_capture_claims_are_checked_on_actual_legal_move():
    board=chess.Board();move=atom(board,'e2e4')
    good=response(board,['e2e4'],f'The move {move} does not give check. It does not capture a piece.')
    correct=scoring.recognized_facts({'fen':board.fen()},good['raw_text'])
    assert correct['recognized_claims']==2 and correct['false_claims']==0 and correct['check_and_capture_complete']
    bad=good['raw_text'].replace('does not give check','gives checkmate').replace('It does not capture a piece.','It captures <PIECE_OQ>.')
    incorrect=scoring.recognized_facts({'fen':board.fen()},bad)
    assert incorrect['recognized_claims']==2 and incorrect['false_claims']==2


def test_capture_in_unrelated_later_variation_does_not_inherit_root_move_truth():
    board=chess.Board();move=atom(board,'e2e4')
    text=response(board,['e2e4'],f'The move {move} does not give check. Another variation follows. It captures <PIECE_OQ>.')['raw_text']
    result=scoring.recognized_facts({'fen':board.fen()},text)
    assert result['recognized_claims']==1 and result['false_claims']==0 and not result['check_and_capture_complete']


def test_black_pov_capture_and_checker_are_replayed_correctly():
    board=chess.Board('6k1/8/8/8/8/8/4r3/4R1K1 b - - 0 1');move=atom(board,'e2e1')
    after=board.copy();after.push_uci('e2e1');assert after.is_check()
    checker=f'<PIECE_MR><SQUARE_{(chess.E1^56)+1}>'
    text=response(board,['e2e1'],f'The move {move} gives check. It captures <PIECE_OR>. The checking piece is {checker}.')['raw_text']
    result=scoring.recognized_facts({'fen':board.fen()},text)
    assert result['recognized_claims']==3 and result['false_claims']==0


def test_en_passant_victim_is_not_read_from_empty_destination():
    board=chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1');move=atom(board,'e5d6')
    assert board.is_en_passant(chess.Move.from_uci('e5d6'))
    text=response(board,['e5d6'],f'The move {move} does not give check. It captures <PIECE_OP>.')['raw_text']
    result=scoring.recognized_facts({'fen':board.fen()},text)
    assert result['recognized_claims']==2 and result['false_claims']==0


def test_missing_and_partial_responses_keep_denominator_and_prefix_limits():
    board=chess.Board();packet={'fen':board.fen()};ref={'reference_pv_uci':['e2e4','e7e5','g1f3']}
    missing=scoring.score(packet,{'status':'not_run','raw_text':''},ref)
    one=response(board,['e2e4']);one.update(status='partial',finish_reason='token_limit')
    partial=scoring.score(packet,one,ref)
    total=scoring.summarize([missing,partial])
    assert total['planned']==2 and total['complete_eos']==0
    assert total['teacher_best_agreement']==1 and total['critical_prefix_matches']=={'1':1,'2':0,'3':0}
    assert not total['whole_prose_factuality_measured']


def test_selected_move_copy_consistency_is_separate_from_unprompted_move_prediction():
    board=chess.Board();result=scoring.score({'fen':board.fen(),'selected_uci':'e2e4'},response(board,['e2e4']),{'reference_pv_uci':['e2e4']})
    assert result['selected_given_consistency']is True
    assert result['reference_plies']==1 and result['critical_prefix_matches']['3']is False
