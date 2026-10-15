"""Offline controls for a source-bound, replayable practice lesson."""
from __future__ import annotations

from html import unescape
from pathlib import Path
import sys

import chess
import chess.engine
import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_paired_teaching_v5 as teaching
import chess_review_completed_game as previous
from test_chess_paired_teaching_v4 import synthetic_v3  # synthetic source fixture


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'
PLAYED = ['c2c3', 'd7d4', 'c3d4', 'd8d4']
ALTERNATIVE = ['c2e4', 'e3d5']


def _v3_record():
    score = lambda value: {'type': 'cp', 'value': value, 'bound': 'exact',
                           'order': 'engine_score', 'perspective': 'side_to_move',
                           'side_to_move': 'white'}
    v3 = {
        'selection': {'fen_before': FEN, 'ply': 39, 'played_san': 'Qc3',
                      'side_to_move': 'white'},
        'source': {'headers': {'White': '<script>White</script>', 'Black': 'Black'}},
        'engine': {'name': 'Stockfish 19', 'sha256': '0' * 64,
                   'settings': {'requested_nodes_per_search': 10_000},
                   'paired_observations': [
                       {'san': 'Qc3', 'score': score(-471), 'pv_uci': PLAYED},
                       {'san': 'Qe4', 'score': score(-95), 'pv_uci': ALTERNATIVE}]},
        'comparison': {'status': 'alternative_higher', 'delta_cp': 376, 'reason': None},
    }
    return v3


def _record(v3=None):
    return teaching.build_record(b'synthetic-pgn', b'synthetic-v3',
                                 b'synthetic-page', _v3_record() if v3 is None else v3)


def test_same_queen_exchange_is_legally_replayed_from_both_moves():
    contrast = teaching.derive_shared_exchange(chess.Board(FEN), PLAYED, ALTERNATIVE)
    assert contrast['status'] == 'supported'
    assert contrast['same_final_board'] is True
    assert [step['san'] for step in contrast['played']['steps']] == [
        'Qc3', 'Qxd4', 'Qxd4', 'Rxd4']
    assert [step['san'] for step in contrast['alternative']['steps']] == [
        'Qe4', 'Qxd4', 'Qxd4', 'Rxd4']
    assert contrast['played']['final_fen'] == contrast['alternative']['final_fen']
    assert contrast['played']['steps'][1]['captured_piece'] == 'pawn'
    assert contrast['played']['steps'][2]['captured_piece'] == 'queen'
    assert contrast['played']['steps'][3]['captured_piece'] == 'queen'


def test_step_lines_use_legal_positions_and_explicit_focus_squares():
    record = _record()
    assert record['schema'] == teaching.SCHEMA
    assert record['shared_exchange']['status'] == 'supported'
    assert record['option_contrast'] == {
        'status': 'supported', 'reason': None, 'san_after_alternative': 'Qxb7+',
        'capture_piece': 'pawn', 'gives_check': True,
        'played_can_move_to_same_target': False}
    by_id = {line['id']: line for line in record['step_lines']}
    assert {'played_exchange', 'alternative_exchange', 'checking_option',
            'saved_block'} <= set(by_id)
    assert by_id['played_exchange']['focus_square'] == 'd4'
    assert by_id['alternative_exchange']['focus_square'] == 'd4'
    assert by_id['checking_option']['focus_square'] == 'b7'
    assert by_id['saved_block']['focus_square'] == 'd5'
    assert [step['san'] for step in by_id['checking_option']['steps']] == [
        'Qe4', 'Qxd4', 'Qxb7+']
    assert [step['san'] for step in by_id['saved_block']['steps']] == ['Qe4', 'Nd5']
    for line in record['step_lines']:
        board = chess.Board(FEN)
        for step in line['steps']:
            move = chess.Move.from_uci(step['uci'])
            assert move in board.legal_moves
            assert board.san(move) == step['san']
            board.push(move)
            assert board.fen() == step['fen_after']


def test_page_states_contrast_without_engine_causality_or_unsafe_markup():
    page = teaching.render(_record()).decode('utf-8')
    assert "White's 20th move (game ply 39)" in page
    assert 'Qe4 does not stop that same exchange' in page
    assert 'After 20.Qe4 Qxd4, White can choose 21.Qxb7+ instead of trading queens.' in page
    assert 'Qxb7+' in page
    assert 'do not prove Stockfish' in unescape(page)
    assert 'not a best-response claim' in page
    assert '<details' in page and '<summary' in page
    assert 'Legal counterfactual; not a saved engine line' in page
    assert 'Hypothetical legal illustration; not a saved engine line' in page
    assert 'Hypothetical reply after Qe4' in page
    assert 'Hypothetical legal reply, not a saved engine line' not in page
    assert 'data-focus="d4"' in page
    assert 'data-focus="b7"' in page
    assert 'data-focus="d5"' in page
    assert '<script>White</script>' not in page
    assert '&lt;script&gt;White&lt;/script&gt;' in page


def test_mirrored_black_pair_names_the_actual_pawn_sides():
    v3 = _v3_record()
    board = chess.Board(FEN).mirror()

    def mirror_uci(uci):
        move = chess.Move.from_uci(uci)
        return chess.Move(chess.square_mirror(move.from_square),
                          chess.square_mirror(move.to_square)).uci()

    played = [mirror_uci(uci) for uci in PLAYED]
    alternative = [mirror_uci(uci) for uci in ALTERNATIVE]
    v3['selection'].update(fen_before=board.fen(), ply=40,
                           played_san=board.san(chess.Move.from_uci(played[0])),
                           side_to_move='black')
    observations = v3['engine']['paired_observations']
    for observation, pv in zip(observations, (played, alternative)):
        observation['san'] = board.san(chess.Move.from_uci(pv[0]))
        observation['pv_uci'] = pv
        observation['score']['side_to_move'] = 'black'
    record = _record(v3)
    assert record['shared_exchange']['status'] == 'supported'
    page = unescape(teaching.render(record).decode('utf-8'))
    assert "Black's 20th move (game ply 40)" in page
    assert f"White takes Black's pawn on {record['shared_exchange']['focus_square']}" in page
    assert "Black takes White's pawn" not in page


def test_nonqueen_pair_and_no_alternative_use_accurate_intro_and_board_caption():
    v3 = _v3_record()
    board = chess.Board()
    v3['selection'].update(fen_before=board.fen(), ply=1,
                           played_san='e4', side_to_move='white')
    observations = v3['engine']['paired_observations']
    observations[0].update(san='e4', pv_uci=['e2e4'])
    observations[1].update(san='d4', pv_uci=['d2d4'])
    paired_page = teaching.render(_record(v3)).decode('utf-8')
    assert "White's 1st move (game ply 1):" in paired_page
    assert 'e4 compared with d4' in paired_page
    assert 'Before either candidate move' in paired_page
    assert 'Before either queen move' not in paired_page

    v3['engine']['paired_observations'] = observations[:1]
    single_page = teaching.render(_record(v3)).decode('utf-8')
    assert "White's 1st move (game ply 1):" in single_page
    assert 'Before the played move' in single_page
    assert 'No alternative was recorded' in single_page
    assert 'Start with the position' in single_page
    assert 'What does the saved line show?' in single_page
    assert 'paired search' not in single_page
    assert 'scoring the moves differently' not in single_page
    assert 'compared with None' not in single_page
    assert 'after the alternative' not in single_page


def test_checking_option_title_does_not_imply_shared_reply_captures():
    v3 = _v3_record()
    v3['engine']['paired_observations'][0]['pv_uci'] = ['c2c3', 'a7a6']
    record = _record(v3)
    assert record['shared_exchange']['status'] == 'abstain'
    assert record['option_contrast']['status'] == 'supported'
    assert record['threat_contrast']['shared_reply']['reply_san'] == 'a6'
    line = next(line for line in record['step_lines'] if line['id'] == 'checking_option')
    assert [step['san'] for step in line['steps'][:2]] == ['Qe4', 'a6']
    assert line['steps'][1]['captured_piece'] is None
    page = teaching.render(record).decode('utf-8')
    assert 'Another option after the shared reply' in page
    assert 'Another option after the pawn capture' not in page
    assert 'White has a legal option:' in page
    assert 'extra legal option' not in page


def _args(pgn_path, v3_dir, output, *, receipt_sha=None, page_sha=None):
    return ['--pgn', str(pgn_path), '--v3-dir', str(v3_dir),
            '--v3-receipt-sha256', receipt_sha or previous.digest(
                (v3_dir / 'review.json').read_bytes()),
            '--v3-page-sha256', page_sha or previous.digest(
                (v3_dir / 'index.html').read_bytes()),
            '--output-dir', str(output)]


def test_create_only_verify_bytes_and_pin_failures(synthetic_v3, tmp_path, monkeypatch):
    pgn_path, v3_dir, *_ = synthetic_v3
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci',
                        lambda *_: (_ for _ in ()).throw(AssertionError('engine call')))
    output = tmp_path / 'v5'
    args = _args(pgn_path, v3_dir, output)
    assert teaching.main(['review', *args]) == 0
    before = {name: (output / name).read_bytes() for name in ('review.json', 'index.html')}
    assert teaching.main(['verify', *args]) == 0
    assert {name: (output / name).read_bytes() for name in before} == before
    with pytest.raises(FileExistsError):
        teaching.main(['review', *args])
    output.joinpath('index.html').write_bytes(before['index.html'] + b'changed')
    with pytest.raises(ValueError, match='v5_page_differs_from_receipt'):
        teaching.main(['verify', *args])
    with pytest.raises(ValueError, match='v3_receipt_sha256_changed'):
        teaching.main(['verify', *_args(pgn_path, v3_dir, output,
                                        receipt_sha='0' * 64)])


def test_illegal_saved_line_and_unavailable_shared_exchange_abstain():
    board = chess.Board(FEN)
    with pytest.raises(ValueError, match='illegal_saved_line'):
        teaching.derive_shared_exchange(board, PLAYED + ['a1a8'], ALTERNATIVE)
    no_exchange = teaching.derive_shared_exchange(chess.Board(),
                                                   ['e2e4', 'e7e5'],
                                                   ['d2d4', 'e7e5'])
    assert no_exchange['status'] == 'abstain'
    assert no_exchange['same_final_board'] is None
