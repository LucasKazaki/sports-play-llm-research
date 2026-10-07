"""A real local-engine smoke check and fail-closed PGN/receipt controls."""
import copy
import json
from pathlib import Path
import sys

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_review_completed_game as review

PGN = '''[Event "Example"]
[Site "local"]
[Round "9"]
[White "<script>Example</script>"]
[Black "Black player"]
[Result "1-0"]
[ECO "C60"]
[Zeta "last optional header"]
[Alpha "first optional header"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 1-0
'''
FOOLS_MATE_PGN = '''[Event "Software checkmate fixture"]
[Site "local"]
[White "White"]
[Black "Black"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
'''


def test_local_postgame_review_and_offline_reverification(tmp_path):
    if not review.ENGINE.is_file():
        pytest.skip('pinned Stockfish binary is a local integration asset')
    pgn = tmp_path / 'one-game.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    output = tmp_path / 'review'
    assert review.main(['doctor']) == 0
    assert review.main(['review', '--pgn', str(pgn), '--ply', '7',
                        '--nodes', '1000', '--output-dir', str(output)]) == 0
    assert review.main(['verify', '--pgn', str(pgn), '--output-dir', str(output)]) == 0
    record = json.loads((output / 'review.json').read_text(encoding='utf-8'))
    page_bytes = (output / 'index.html').read_bytes()
    page = page_bytes.decode('utf-8')
    assert record['selection']['actual_move_san'] == 'Ba4'
    assert record['selection']['ply'] == 7
    assert record['engine']['actual_move']['move_uci'] == 'b5a4'
    assert record['engine']['settings']['requested_nodes_per_search'] == 1000
    assert page.count('<svg ') in (2, 3)
    assert 'Move list' in page
    assert 'Download annotated PGN' in page
    exported = (output / 'review.pgn').read_text(encoding='utf-8')
    assert 'Local Stockfish observation, root restricted' in exported
    assert '<script>Example</script>' in exported
    assert '[Round "9"]' in exported and '[ECO "C60"]' in exported
    assert exported.index('[Zeta "last optional header"]') < exported.index(
        '[Alpha "first optional header"]')
    assert 'No model claim or teaching-quality review is available' in page
    assert 'Stockfish binary SHA-256' in page
    assert '<script>Example</script>' not in page
    assert '&lt;script&gt;Example&lt;/script&gt;' in page
    with pytest.raises(FileExistsError):
        review.main(['review', '--pgn', str(pgn), '--ply', '7',
                     '--nodes', '1000', '--output-dir', str(output)])
    (output / 'index.html').write_text(page.replace('Withheld', 'Proven'), encoding='utf-8')
    with pytest.raises(ValueError, match='rendered_page_differs'):
        review.main(['verify', '--pgn', str(pgn), '--output-dir', str(output)])
    (output / 'index.html').write_bytes(page_bytes)
    (output / 'review.pgn').write_text('tampered', encoding='utf-8')
    with pytest.raises(ValueError, match='annotated_pgn_differs'):
        review.main(['verify', '--pgn', str(pgn), '--output-dir', str(output)])


def test_malformed_or_unfinished_pgn_is_rejected(tmp_path):
    pgn = tmp_path / 'bad.pgn'
    pgn.write_text(PGN.replace('[Result "1-0"]', '[Result "*"]').replace('1-0\n', '*\n'),
                   encoding='utf-8')
    with pytest.raises(ValueError, match='completed_game_result_required'):
        review.load_completed_game(pgn)
    pgn.write_text(PGN + '\n' + PGN, encoding='utf-8')
    with pytest.raises(ValueError, match='expected_exactly_one_game'):
        review.load_completed_game(pgn)
    pgn.write_text(PGN.replace('Ba4', 'Ba9'), encoding='utf-8')
    with pytest.raises(ValueError, match='pgn_parse_or_replay_error'):
        review.load_completed_game(pgn)


def test_record_rejects_wrong_board_and_illegal_engine_line(tmp_path):
    if not review.ENGINE.is_file():
        pytest.skip('pinned Stockfish binary is a local integration asset')
    pgn = tmp_path / 'one-game.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    game, raw, moves = review.load_completed_game(pgn)
    record = review.analyze(game, raw, moves, 7, 1000)
    changed = copy.deepcopy(record)
    changed['selection']['fen_after'] = changed['selection']['fen_before']
    with pytest.raises(ValueError, match='record_board_replay_changed'):
        review.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['engine']['actual_move']['pv_uci'][0] = 'e2e4'
    with pytest.raises(ValueError, match='record_engine_line_not_legal|record_engine_move_changed'):
        review.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['selection']['side_to_move'] = 'black'
    with pytest.raises(ValueError, match='record_board_replay_changed'):
        review.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['source']['headers']['White'] = 'invented player'
    with pytest.raises(ValueError, match='record_board_replay_changed'):
        review.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['limitations'] = []
    with pytest.raises(ValueError, match='record_limitations_changed'):
        review.validate_record(changed, game, raw, moves)


def test_typed_engine_scores_keep_perspective_and_bounds():
    info = {'score': chess.engine.PovScore(chess.engine.Cp(-73), chess.WHITE),
            'lowerbound': True}
    score = review.score_record(info, chess.BLACK)
    assert score == {'type': 'cp', 'value': 73, 'bound': 'lower',
                     'order': 'engine_score', 'perspective': 'side_to_move',
                     'side_to_move': 'black'}
    mate = review.score_record(
        {'score': chess.engine.PovScore(chess.engine.Mate(-2), chess.BLACK),
         'upperbound': True}, chess.BLACK)
    assert mate['type'] == 'mate' and mate['value'] == -2 and mate['bound'] == 'upper'
    assert review.display_score(mate) == (
        'Engine mate score -2, Black perspective · upper bound')


def test_software_fixture_is_a_finished_legal_game(tmp_path):
    pgn = tmp_path / 'fools-mate.pgn'
    pgn.write_text(FOOLS_MATE_PGN, encoding='utf-8')
    game, _, moves = review.load_completed_game(pgn)
    assert len(moves) == 4
    assert game.end().board().is_checkmate()
    assert game.headers['Result'] == '0-1'


def test_saved_demo_is_a_finished_legal_game():
    path = ROOT / 'demo/chess-review-fools-mate-fixture.pgn'
    if not path.is_file():
        pytest.skip('saved demo PGN is a local integration asset')
    game, _, moves = review.load_completed_game(
        path)
    assert len(moves) == 4
    assert game.end().board().is_checkmate()
    assert game.headers['Result'] == '0-1'
