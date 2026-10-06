"""Synthetic software checks for the offline, evaluator-side teaching layer.

These positions test legal replay and receipt binding. They are not evidence of
human teaching quality or a fresh game-disjoint commentary evaluation.
"""
from __future__ import annotations

import json
from html import unescape
from pathlib import Path
import sys

import chess
import chess.engine
import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_paired_review_v3 as paired
import chess_paired_teaching_v4 as teaching
import chess_review_completed_game as previous


# The PGN is deliberately synthetic. A declared result is all the inherited
# completed-game loader can establish; it does not prove that the game ended.
THREAT_FEN = '3qk3/5pp1/8/4p3/2BPP3/8/8/3Q2K1 w - - 0 1'
PGN = f'''[Event "Synthetic teaching fixture"]
[Site "local"]
[White "<script>White</script>"]
[Black "Black"]
[Result "0-1"]
[SetUp "1"]
[FEN "{THREAT_FEN}"]

1. Qg4 Qxd4+ 0-1
'''


def _is_mate_after(board: chess.Board, move: chess.Move) -> bool:
    replay = board.copy(stack=False)
    replay.push(move)
    return replay.is_checkmate()


@pytest.fixture
def synthetic_v3(tmp_path, monkeypatch):
    """Make a valid v3 receipt and exact page with a fake bounded search."""
    pgn_path = tmp_path / 'game.pgn'
    pgn_path.write_text(PGN, encoding='utf-8')
    game, pgn_raw, moves = previous.load_completed_game(pgn_path)
    played = chess.Move.from_uci('d1g4')
    alternative = chess.Move.from_uci('d1h5')
    reply = chess.Move.from_uci('d8d4')

    class FakeEngine:
        id = {'name': 'Stockfish 19'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def configure(self, options):
            assert options == {'Threads': 1, 'Hash': 16}

        def analyse(self, board, limit, *, root_moves=None, multipv=None):
            assert board.fen() == THREAT_FEN
            assert limit.nodes == 1_000
            assert multipv == 2
            if root_moves is None:
                return [{'pv': [alternative]}, {'pv': [played]}]
            assert root_moves == [played, alternative]
            # Reversed order makes the v3 adapter bind each line by its root.
            return [
                {'pv': [alternative, reply],
                 'score': chess.engine.PovScore(chess.engine.Cp(80), chess.WHITE),
                 'nodes': 510, 'depth': 7},
                {'pv': [played, reply],
                 'score': chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
                 'nodes': 490, 'depth': 7},
            ]

    monkeypatch.setattr(previous, 'engine_ready', lambda: {'status': 'fake-ready'})
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', lambda _: FakeEngine())
    record = paired.analyze(game, pgn_raw, moves, ply=1, nodes=1_000)
    assert record['engine']['settings']['searches'] == 2
    v3_dir = tmp_path / 'v3'
    v3_dir.mkdir()
    v3_raw = previous.canonical(record) + b'\n'
    v3_page_raw = paired.render(record)
    (v3_dir / 'review.json').write_bytes(v3_raw)
    (v3_dir / 'index.html').write_bytes(v3_page_raw)
    return pgn_path, v3_dir, pgn_raw, v3_raw, v3_page_raw, record


def test_short_line_replays_captures_material_and_final_position():
    board = chess.Board()
    board.push_san('e4')
    board.push_san('d5')
    pv = ['e4d5', 'd8d5', 'b1c3']
    original_fen = board.fen()
    line = teaching.derive_line(board, pv)
    assert board.fen() == original_fen
    assert [item['san'] for item in line['moves']] == ['exd5', 'Qxd5', 'Nc3']
    assert [item['mover'] for item in line['moves']] == ['white', 'black', 'white']
    assert line['captures'] == [
        {'san': 'exd5', 'mover': 'white', 'captured_side': 'black',
         'captured_piece': 'pawn', 'square': 'd5'},
        {'san': 'Qxd5', 'mover': 'black', 'captured_side': 'white',
         'captured_piece': 'pawn', 'square': 'd5'},
    ]
    assert line['truncated'] is False
    replay = board.copy(stack=False)
    for uci in pv:
        replay.push_uci(uci)
    assert line['final_fen'] == replay.fen()
    assert len(replay.pieces(chess.PAWN, chess.WHITE)) == 7
    assert len(replay.pieces(chess.PAWN, chess.BLACK)) == 7
    assert line['san_line'].endswith('Nc3')


def test_en_passant_capture_uses_the_taken_pawns_square():
    board = chess.Board()
    for san in ('e4', 'a6', 'e5', 'd5'):
        board.push_san(san)
    line = teaching.derive_line(board, ['e5d6'])
    assert line['moves'][0]['capture_square'] == 'd5'
    assert line['captures'][0] == {
        'san': 'exd6', 'mover': 'white', 'captured_side': 'black',
        'captured_piece': 'pawn', 'square': 'd5'}


def test_full_saved_line_is_checked_even_beyond_display_limit():
    board = chess.Board()
    pv = ['e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1c4']
    line = teaching.derive_line(board, pv, max_plies=4)
    assert line['truncated'] is True
    assert len(line['moves']) == 4
    prefix = board.copy(stack=False)
    for uci in pv[:4]:
        prefix.push_uci(uci)
    assert line['final_fen'] == prefix.fen()
    with pytest.raises(ValueError, match='illegal_saved_line'):
        teaching.derive_line(board, pv + ['a1a8'], max_plies=4)
    for invalid in ([], ['e7e5'], ['e2e4', 'a1a8']):
        with pytest.raises(ValueError, match='illegal_saved_line'):
            teaching.derive_line(board, invalid)
    with pytest.raises(ValueError, match='line_limit_out_of_bounds'):
        teaching.derive_line(board, pv, max_plies=0)


def test_unique_mate_threat_and_checking_capture_reply_are_legally_replayed():
    board = chess.Board(THREAT_FEN)
    contrast = teaching.derive_threat_contrast(
        board, ['d1g4', 'd8d4'], ['d1h5', 'd8d4'])
    assert contrast['status'] == 'supported'
    assert contrast['reason'] is None
    assert contrast['threat']['candidate_san'] == 'Qh5'
    assert contrast['threat']['uci'] == 'h5f7'
    assert contrast['threat']['san_after_pass'] == 'Qxf7#'
    assert contrast['threat']['captured_piece_after_pass'] == 'pawn'
    assert contrast['threat']['capture_square_after_pass'] == 'f7'
    example = contrast['legal_reply_example']
    assert example is not None
    after_candidate = board.copy(stack=False)
    after_candidate.push_uci('d1h5')
    reply = chess.Move.from_uci(example['reply_uci'])
    assert reply in after_candidate.legal_moves
    assert not after_candidate.is_capture(reply)
    assert not after_candidate.gives_check(reply)
    after_candidate.push(reply)
    threat = chess.Move.from_uci(example['threat_uci'])
    assert threat in after_candidate.legal_moves
    after_candidate.push(threat)
    assert after_candidate.is_checkmate()
    for key in ('saved_reply', 'shared_reply'):
        reply = contrast[key]
        assert reply['reply_san'] == 'Qxd4+'
        assert reply['reply_capture'] == 'pawn'
        assert reply['reply_capture_square'] == 'd4'
        assert reply['reply_gives_check'] is True
        assert reply['threat_available'] is False
        assert reply['threat_does_not_answer_check'] is True
        assert reply['threat_san'] is None
    assert contrast['shared_reply']['status'] == 'legal'


def test_no_or_ambiguous_mate_threat_abstains():
    quiet_after_pass = chess.Board()
    quiet_after_pass.push_uci('d2d4')
    quiet_after_pass.push(chess.Move.null())
    assert not any(_is_mate_after(quiet_after_pass, move)
                   for move in quiet_after_pass.legal_moves)
    no_threat = teaching.derive_threat_contrast(
        chess.Board(), ['e2e4', 'e7e5'], ['d2d4', 'e7e5'])
    assert no_threat == {
        'status': 'abstain', 'reason': 'no_unique_mate_in_one_threat',
        'threat': None, 'saved_reply': None, 'shared_reply': None,
        'legal_reply_example': None}
    multiple = chess.Board('7k/6pp/8/8/8/8/R7/K2Q4 w - - 0 1')
    multiple_after_pass = multiple.copy(stack=False)
    multiple_after_pass.push_uci('a2a4')
    multiple_after_pass.push(chess.Move.null())
    assert {multiple_after_pass.san(move) for move in multiple_after_pass.legal_moves
            if _is_mate_after(multiple_after_pass, move)} == {'Ra8#', 'Qd8#'}
    ambiguous = teaching.derive_threat_contrast(
        multiple, ['a2a3', 'h7h6'], ['a2a4', 'h7h6'])
    assert ambiguous == no_threat


def test_threat_contrast_rejects_bad_or_same_saved_lines():
    board = chess.Board(THREAT_FEN)
    with pytest.raises(ValueError, match='illegal_saved_line'):
        teaching.derive_threat_contrast(board, ['d1g4', 'd8d2'], ['d1h5'])
    with pytest.raises(ValueError, match='illegal_saved_line'):
        teaching.derive_threat_contrast(board, ['d1g4'], [])
    with pytest.raises(ValueError, match='same_candidate_move'):
        teaching.derive_threat_contrast(board, ['d1g4'], ['d1g4', 'd8d4'])


def test_record_uses_exact_three_source_hashes_and_safe_page(synthetic_v3):
    pgn_path, v3_dir, pgn_raw, v3_raw, v3_page_raw, v3_record = synthetic_v3
    assert pgn_path.exists() and v3_dir.exists()
    record = teaching.build_record(pgn_raw, v3_raw, v3_page_raw, v3_record)
    assert record['schema'] == teaching.SCHEMA
    assert record['source'] == {
        'pgn_sha256': previous.digest(pgn_raw),
        'v3_receipt_sha256': previous.digest(v3_raw),
        'v3_page_sha256': previous.digest(v3_page_raw),
    }
    assert record['selection']['played_san'] == 'Qg4'
    assert record['selection']['alternative_san'] == 'Qh5'
    assert record['threat_contrast']['status'] == 'supported'
    assert record['played_line']['captures'][0]['san'] == 'Qxd4+'
    page = teaching.render(record).decode('utf-8')
    assert 'Qxf7#' in page and 'Qxd4+' in page
    assert "White's perspective" in unescape(page)
    assert "Side_To_Move's perspective" not in unescape(page)
    assert 'hypothetical pass' in page
    assert 'not a forced' in page
    assert '<script>White</script>' not in page
    assert '&lt;script&gt;White&lt;/script&gt;' in page


@pytest.mark.parametrize('changed', ['pgn', 'v3_receipt', 'v3_page'])
def test_v3_source_and_page_tampering_fail_before_creating_v4(
        synthetic_v3, tmp_path, changed):
    pgn_path, v3_dir, *_ = synthetic_v3
    if changed == 'pgn':
        pgn_path.write_text(PGN.replace('Synthetic teaching fixture',
                                        'Different synthetic fixture'), encoding='utf-8')
    elif changed == 'v3_receipt':
        receipt_path = v3_dir / 'review.json'
        record = json.loads(receipt_path.read_bytes())
        record['source']['pgn_sha256'] = '0' * 64
        receipt_path.write_bytes(previous.canonical(record) + b'\n')
    else:
        (v3_dir / 'index.html').write_bytes(
            (v3_dir / 'index.html').read_bytes() + b'changed')
    output = tmp_path / 'v4'
    with pytest.raises(ValueError):
        teaching.main(['review', '--pgn', str(pgn_path), '--v3-dir', str(v3_dir),
                       '--output-dir', str(output)])
    assert not output.exists()


def test_review_is_create_only_verify_is_byte_identical_and_offline(
        synthetic_v3, tmp_path, monkeypatch, capsys):
    pgn_path, v3_dir, *_ = synthetic_v3

    def forbidden_engine(*_args, **_kwargs):
        raise AssertionError('v4 must never launch an engine')

    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', forbidden_engine)
    output = tmp_path / 'v4'
    args = ['--pgn', str(pgn_path), '--v3-dir', str(v3_dir),
            '--output-dir', str(output)]
    assert teaching.main(['review', *args]) == 0
    review_status = json.loads(capsys.readouterr().out)
    assert review_status['engine_calls'] == review_status['model_calls'] == 0
    before = {name: (output / name).read_bytes() for name in ('review.json', 'index.html')}
    assert teaching.main(['verify', *args]) == 0
    verify_status = json.loads(capsys.readouterr().out)
    assert verify_status['engine_calls'] == verify_status['model_calls'] == 0
    assert verify_status['page_sha256'] == previous.digest(before['index.html'])
    assert {name: (output / name).read_bytes() for name in before} == before
    with pytest.raises(FileExistsError):
        teaching.main(['review', *args])
    assert {name: (output / name).read_bytes() for name in before} == before


@pytest.mark.parametrize('changed', ['v4_receipt', 'v4_page'])
def test_verify_rejects_changed_v4_output(synthetic_v3, tmp_path, changed):
    pgn_path, v3_dir, *_ = synthetic_v3
    output = tmp_path / 'v4'
    args = ['--pgn', str(pgn_path), '--v3-dir', str(v3_dir),
            '--output-dir', str(output)]
    assert teaching.main(['review', *args]) == 0
    if changed == 'v4_receipt':
        path = output / 'review.json'
        record = json.loads(path.read_bytes())
        record['source']['pgn_sha256'] = '0' * 64
        path.write_bytes(previous.canonical(record) + b'\n')
    else:
        path = output / 'index.html'
        path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match=(
            'v4_record_differs_from_inputs' if changed == 'v4_receipt'
            else 'v4_page_differs_from_receipt')):
        teaching.main(['verify', *args])
