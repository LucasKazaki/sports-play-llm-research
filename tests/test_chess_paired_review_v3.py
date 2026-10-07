"""Focused software and pinned-local-engine checks for paired post-game review."""
import copy
import json
from pathlib import Path
import sys

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_paired_review_v3 as paired
import chess_review_completed_game as previous


PGN = '''[Event "Software fixture"]
[Site "local"]
[White "<script>White</script>"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 1-0
'''


def _score(value, *, kind='cp', bound='exact', side='white'):
    return {'type': kind, 'value': value, 'bound': bound,
            'order': 'engine_score', 'perspective': 'side_to_move',
            'side_to_move': side}


def test_comparison_abstains_for_mate_bounds_and_perspective_mismatch():
    assert paired.compare_scores(_score(-50), _score(30)) == {
        'status': 'alternative_higher', 'reason': None, 'delta_cp': 80}
    assert paired.compare_scores(_score(50), _score(30)) == {
        'status': 'played_higher', 'reason': None, 'delta_cp': -20}
    assert paired.compare_scores(_score(30), _score(30))['status'] == 'equal'
    assert paired.compare_scores(_score(30), None)['status'] == 'unavailable'
    assert paired.compare_scores(_score(2, kind='mate'), _score(200)) == {
        'status': 'abstain', 'reason': 'mate_or_bounded_score', 'delta_cp': None}
    assert paired.compare_scores(_score(20, bound='lower'), _score(50))['status'] == 'abstain'
    with pytest.raises(ValueError, match='perspective_mismatch'):
        paired.compare_scores(_score(20), _score(30, side='black'))
    with pytest.raises(ValueError, match='invalid_comparison_score_shape'):
        paired.compare_scores({'value': 20}, _score(30))


def test_first_reply_is_legally_replayed_without_causal_claim():
    board = chess.Board()
    board.push_san('e4')
    board.push_san('d5')
    assert paired.first_reply_fact(board, {'pv_uci': ['e4d5', 'd8d5']}) == {
        'san': 'Qxd5', 'uci': 'd8d5', 'captured_piece': 'pawn',
        'gives_check': False, 'checkmate': False,
        'new_attack_on_moved_piece': None}
    with pytest.raises(ValueError, match='record_engine_line_not_legal'):
        paired.first_reply_fact(board, {'pv_uci': ['e4d5', 'a1a8']})
    threat_board = chess.Board('4k3/3q4/8/8/3P4/8/2Q5/4K3 w - - 0 1')
    reply = paired.first_reply_fact(threat_board, {'pv_uci': ['c2c3', 'd7d4']})
    assert reply['san'] == 'Qxd4'
    assert reply['captured_piece'] == 'pawn'
    assert reply['new_attack_on_moved_piece'] == {'piece': 'queen', 'square': 'c3'}


def test_one_discovery_then_one_paired_search_and_checked_roots(tmp_path, monkeypatch):
    pgn = tmp_path / 'game.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    game, raw, moves = previous.load_completed_game(pgn)
    calls = []

    class FakeEngine:
        id = {'name': 'Stockfish 19'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def configure(self, options):
            assert options == {'Threads': 1, 'Hash': 16}

        def analyse(self, board, limit, *, root_moves=None, multipv=None):
            calls.append((root_moves, multipv, limit.nodes))
            e4 = chess.Move.from_uci('e2e4')
            d4 = chess.Move.from_uci('d2d4')
            if root_moves is None:
                return [{'pv': [d4]}, {'pv': [e4]}]
            assert root_moves == [e4, d4]
            return [
                {'pv': [d4, chess.Move.from_uci('d7d5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE),
                 'nodes': 600, 'depth': 7},
                {'pv': [e4, chess.Move.from_uci('e7e5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
                 'nodes': 400, 'depth': 7},
            ]

    monkeypatch.setattr(previous, 'engine_ready', lambda: {'status': 'ready'})
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', lambda _: FakeEngine())
    record = paired.analyze(game, raw, moves, 1, 1000)
    assert calls == [(None, 2, 1000), ([chess.Move.from_uci('e2e4'),
                                         chess.Move.from_uci('d2d4')], 2, 1000)]
    assert record['engine']['alternative_uci'] == 'd2d4'
    assert [item['move_uci'] for item in record['engine']['paired_observations']] == [
        'e2e4', 'd2d4']
    assert record['comparison'] == {
        'status': 'alternative_higher', 'reason': None, 'delta_cp': 15}
    changed = copy.deepcopy(record)
    changed['engine']['paired_observations'][0]['pv_uci'][1] = 'a1a8'
    with pytest.raises(ValueError, match='record_engine_line_not_legal'):
        paired.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['comparison']['delta_cp'] = 900
    with pytest.raises(ValueError, match='record_comparison_changed'):
        paired.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['comparison']['delta_cp'] = True
    with pytest.raises(ValueError, match='invalid_comparison_delta'):
        paired.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['selection']['capture'] = 0
    with pytest.raises(ValueError, match='invalid_selection_types'):
        paired.validate_record(changed, game, raw, moves)
    changed = copy.deepcopy(record)
    changed['source']['headers']['White'] = 'invented'
    with pytest.raises(ValueError, match='record_source_binding_changed'):
        paired.validate_record(changed, game, raw, moves)


def test_pinned_engine_page_and_offline_verification(tmp_path):
    if not previous.ENGINE.is_file():
        pytest.skip('pinned Stockfish binary is a local integration asset')
    pgn = tmp_path / 'fixture.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    output = tmp_path / 'v3'
    assert paired.main(['doctor']) == 0
    assert paired.main(['review', '--pgn', str(pgn), '--ply', '7', '--nodes', '1000',
                        '--output-dir', str(output)]) == 0
    assert paired.main(['verify', '--pgn', str(pgn), '--output-dir', str(output)]) == 0
    record = json.loads((output / 'review.json').read_text(encoding='utf-8'))
    page = (output / 'index.html').read_text(encoding='utf-8')
    assert record['selection']['played_san'] == 'Ba4'
    assert record['engine']['settings']['searches'] == 2
    assert len(record['engine']['paired_observations']) == 2
    assert 'root-restricted MultiPV search' in page
    assert 'It is not model commentary' in page
    assert '<script>White</script>' not in page
    assert '&lt;script&gt;White&lt;/script&gt;' in page
    with pytest.raises(FileExistsError):
        paired.main(['review', '--pgn', str(pgn), '--ply', '7', '--nodes', '1000',
                     '--output-dir', str(output)])
    (output / 'index.html').write_text(page.replace('Paired search', 'Proven best move'),
                                        encoding='utf-8')
    with pytest.raises(ValueError, match='rendered_page_differs_from_receipt'):
        paired.main(['verify', '--pgn', str(pgn), '--output-dir', str(output)])


def test_bad_pgn_is_still_rejected_by_inherited_loader(tmp_path):
    pgn = tmp_path / 'unfinished.pgn'
    pgn.write_text(PGN.replace('[Result "1-0"]', '[Result "*"]').replace('1-0\n', '*\n'),
                   encoding='utf-8')
    with pytest.raises(ValueError, match='completed_game_result_required'):
        paired.main(['review', '--pgn', str(pgn), '--ply', '1', '--output-dir',
                     str(tmp_path / 'result')])
