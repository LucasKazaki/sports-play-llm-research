"""Synthetic contract checks; these tests never start Stockfish or a model."""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import chess.engine
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from chess_arbitrary_move_contrast_v1 import (  # noqa: E402
    ENGINE_OPTIONS,
    NODE_BUDGETS,
    evaluate,
    position_sha256,
)


SHA_SOURCE = 'a' * 64
SHA_ENGINE = 'b' * 64


def event(board, rank, move, cp, *, nodes=100_000, depth=17,
          perspective=None, lower=False, upper=False, mate=False,
          tail=()):
    score = chess.engine.Mate(cp) if mate else chess.engine.Cp(cp)
    info = {'multipv': rank,
            'pv': [chess.Move.from_uci(move), *[chess.Move.from_uci(x) for x in tail]],
            'score': chess.engine.PovScore(score, board.turn if perspective is None else perspective),
            'nodes': nodes, 'depth': depth}
    if lower:
        info['lowerbound'] = True
    if upper:
        info['upperbound'] = True
    return info


class FakeStream:
    def __init__(self, events):
        self.events = iter(events)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def would_block(self):
        return False

    def next(self):
        return next(self.events, None)


class FakeEngine:
    id = {'name': 'Stockfish 19'}

    def __init__(self, *scripts):
        self.scripts = iter(scripts)
        self.calls = []
        self.closed = False

    def analysis(self, board, limit, *, multipv, root_moves, options, game):
        self.calls.append({'fen': board.fen(), 'stack': list(board.move_stack),
                           'nodes': limit.nodes, 'multipv': multipv,
                           'roots': None if root_moves is None else [x.uci() for x in root_moves],
                           'options': options, 'game': game})
        script = next(self.scripts)
        if isinstance(script, Exception):
            raise script
        return FakeStream(script)

    def close(self):
        self.closed = True


def run(board, selected, engine):
    return evaluate(board, selected, source_receipt_sha256=SHA_SOURCE,
                    expected_position_sha256=position_sha256(board, selected),
                    engine_sha256=SHA_ENGINE, engine=engine)


def nested_keys(value):
    if isinstance(value, dict):
        return set(value).union(*(nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(nested_keys(item) for item in value))
    return set()


def normal_scripts(board, selected='g1f3', alternative='e2e4',
                   low=(0, 200), high=(10, 220)):
    return (
        [event(board, 1, alternative, 40), event(board, 2, 'd2d4', 20)],
        [event(board, 1, alternative, low[1], nodes=NODE_BUDGETS[0]),
         event(board, 2, selected, low[0], nodes=NODE_BUDGETS[0])],
        [event(board, 1, alternative, high[1]), event(board, 2, selected, high[0])],
    )


def test_unrestricted_discovery_same_position_options_and_two_budget_contrast():
    board = chess.Board()
    scripts = list(normal_scripts(board))
    scripts[2][0] = event(board, 1, 'e2e4', 220, tail=('e7e5',))
    scripts[2][1] = event(board, 2, 'g1f3', 10, tail=('d7d5',))
    engine = FakeEngine(*scripts)
    result = run(board, 'g1f3', engine)
    assert result['comparison'] == {
        'status': 'observed_inferior_in_pair', 'reason': None,
        'delta_cp_by_budget': [200, 210], 'observed_loss_cp': 210}
    assert result['alternative_uci'] == 'e2e4'
    assert [item['status'] for item in result['attempts']] == ['succeeded'] * 3
    assert [call['nodes'] for call in engine.calls] == [100_000, 30_000, 100_000]
    assert engine.calls[0]['roots'] is None
    assert [call['roots'] for call in engine.calls[1:]] == [['g1f3', 'e2e4']] * 2
    assert [call['fen'] for call in engine.calls] == [board.fen()] * 3
    assert [call['options'] for call in engine.calls] == [ENGINE_OPTIONS] * 3
    assert [call['multipv'] for call in engine.calls] == [2] * 3
    assert result['source_receipt_sha256'] == SHA_SOURCE
    assert result['engine_sha256'] == SHA_ENGINE
    assert len(result['settings_sha256']) == 64
    assert all(len(attempt['request_sha256']) == 64 for attempt in result['attempts'])
    assert {'pv', 'post_move_fen', 'fen_after'}.isdisjoint(nested_keys(result))
    assert result['attempts'][2]['observations'][0]['line_plies_checked'] == 2
    assert 'e7e5' not in str(result) and 'd7d5' not in str(result)


def test_black_mover_scores_convert_from_white_perspective():
    board = chess.Board()
    board.push_uci('e2e4')
    selected = 'e7e5'
    alternative = 'c7c5'
    white = chess.WHITE
    engine = FakeEngine(
        [event(board, 1, alternative, -20, perspective=white),
         event(board, 2, 'e7e6', -5, perspective=white)],
        [event(board, 1, alternative, -200, nodes=30_000, perspective=white),
         event(board, 2, selected, 0, nodes=30_000, perspective=white)],
        [event(board, 1, alternative, -220, perspective=white),
         event(board, 2, selected, -10, perspective=white)],
    )
    result = run(board, selected, engine)
    assert result['comparison']['observed_loss_cp'] == 210
    assert result['attempts'][2]['observations'][0]['score'] == {
        'type': 'cp', 'value': 220, 'perspective': 'side_to_move',
        'side_to_move': 'black', 'bound': 'exact', 'order': 'engine_score'}
    assert [call['stack'] for call in engine.calls] == [board.move_stack] * 3


@pytest.mark.parametrize('qualified', ['lower', 'upper', 'mate'])
def test_qualified_or_mate_score_is_unresolved_without_numeric_loss(qualified):
    board = chess.Board()
    scripts = list(normal_scripts(board))
    kwargs = {qualified: True} if qualified != 'mate' else {'mate': True}
    scripts[2][1] = event(board, 2, 'g1f3', 3 if qualified == 'mate' else 10, **kwargs)
    result = run(board, 'g1f3', FakeEngine(*scripts))
    assert result['comparison'] == {
        'status': 'unresolved', 'reason': 'mate_or_qualified_score',
        'delta_cp_by_budget': None, 'observed_loss_cp': None}


def test_threshold_change_is_unresolved_without_numeric_loss():
    board = chess.Board()
    engine = FakeEngine(*normal_scripts(board, low=(0, 170), high=(0, 130)))
    result = run(board, 'g1f3', engine)
    assert result['comparison'] == {
        'status': 'unresolved', 'reason': 'unstable_contrast',
        'delta_cp_by_budget': None, 'observed_loss_cp': None}


def test_large_score_drift_is_unresolved_even_above_threshold():
    board = chess.Board()
    result = run(board, 'g1f3', FakeEngine(*normal_scripts(
        board, low=(0, 170), high=(0, 500))))
    assert result['comparison']['status'] == 'unresolved'
    assert result['comparison']['reason'] == 'unstable_contrast'
    assert result['comparison']['observed_loss_cp'] is None


def test_selected_move_not_observed_inferior_keeps_loss_empty():
    board = chess.Board()
    result = run(board, 'g1f3', FakeEngine(*normal_scripts(
        board, low=(40, 30), high=(50, 20))))
    assert result['comparison']['status'] == 'not_observed_inferior_in_pair'
    assert result['comparison']['delta_cp_by_budget'] == [-10, -30]
    assert result['comparison']['observed_loss_cp'] is None


def test_qualified_discovery_stops_before_paired_search():
    board = chess.Board()
    scripts = list(normal_scripts(board))
    scripts[0][0] = event(board, 1, 'e2e4', 40, upper=True)
    engine = FakeEngine(*scripts)
    result = run(board, 'g1f3', engine)
    assert [item['status'] for item in result['attempts']] == [
        'succeeded', 'not_run', 'not_run']
    assert result['comparison']['reason'] == 'discovery_mate_or_qualified_score'
    assert result['comparison']['observed_loss_cp'] is None
    assert len(engine.calls) == 1


def test_latest_raw_score_event_does_not_inherit_stale_bound():
    board = chess.Board()
    scripts = list(normal_scripts(board))
    scripts[2] = [event(board, 1, 'e2e4', 200, lower=True, depth=10),
                  event(board, 2, 'g1f3', 10, depth=18),
                  event(board, 1, 'e2e4', 220, depth=18),
                  {'multipv': 1, 'nodes': 100_000, 'depth': 19}]
    result = run(board, 'g1f3', FakeEngine(*scripts))
    assert result['comparison']['status'] == 'observed_inferior_in_pair'
    latest = result['attempts'][2]['observations'][0]
    assert latest['score']['bound'] == 'exact'
    assert latest['score_info_sequence'] == 3
    assert latest['depth'] == 18


@pytest.mark.parametrize('phase_index', [0, 1, 2])
def test_different_final_rank_depths_reject_phase_without_numeric_loss(phase_index):
    board = chess.Board()
    scripts = list(normal_scripts(board))
    scripts[phase_index][1]['depth'] += 1
    result = run(board, 'g1f3', FakeEngine(*scripts))
    assert result['attempts'][phase_index]['status'] == 'failed'
    assert result['attempts'][phase_index]['reason'] == 'incomparable_rank_depth'
    assert result['comparison']['status'] == 'unresolved'
    assert result['comparison']['observed_loss_cp'] is None
    assert all(item['status'] == 'not_run' for item in result['attempts'][phase_index + 1:])


@pytest.mark.parametrize('phase_index', [0, 1, 2])
def test_tiny_observed_progress_rejects_phase_without_numeric_loss(phase_index):
    board = chess.Board()
    scripts = list(normal_scripts(board))
    for info in scripts[phase_index]:
        info['nodes'] = 1
        info['depth'] = 1
    result = run(board, 'g1f3', FakeEngine(*scripts))
    assert result['attempts'][phase_index]['status'] == 'failed'
    assert result['attempts'][phase_index]['reason'] == 'insufficient_score_event_nodes'
    assert result['comparison']['status'] == 'unresolved'
    assert result['comparison']['observed_loss_cp'] is None
    assert all(item['status'] == 'not_run' for item in result['attempts'][phase_index + 1:])


def test_illegal_move_and_mismatched_position_pin_never_call_engine():
    board = chess.Board()
    engine = FakeEngine()
    with pytest.raises(ValueError, match='illegal_selected_move'):
        run(board, 'e2e5', engine)
    with pytest.raises(ValueError, match='source_position_pin_mismatch'):
        evaluate(board, 'g1f3', source_receipt_sha256=SHA_SOURCE,
                 expected_position_sha256='0' * 64,
                 engine_sha256=SHA_ENGINE, engine=engine)
    assert engine.calls == []


def test_unverified_engine_identity_never_calls_analysis():
    board = chess.Board()
    engine = FakeEngine()
    engine.id = {'name': 'other'}
    with pytest.raises(ValueError, match='engine_identity_unverified'):
        run(board, 'g1f3', engine)
    assert engine.calls == []


def test_nonstandard_board_mode_rejects_before_engine_call():
    board = chess.Board(chess960=True)
    engine = FakeEngine()
    with pytest.raises(ValueError, match='invalid_pre_move_board'):
        run(board, 'g1f3', engine)
    assert engine.calls == []


@pytest.mark.parametrize('bad_high,reason', [
    ('invalid_score', 'invalid_typed_score'),
    ('wrong_root', 'paired_root_mismatch'),
    ('illegal_line', 'illegal_engine_line'),
    ('missing_rank', 'missing_score_rank'),
])
def test_failed_paired_attempt_is_accounted_and_cannot_yield_loss(bad_high, reason):
    board = chess.Board()
    scripts = list(normal_scripts(board))
    if bad_high == 'wrong_root':
        scripts[2] = [event(board, 1, 'd2d4', 220), event(board, 2, 'g1f3', 10)]
    elif bad_high == 'illegal_line':
        scripts[2] = [event(board, 1, 'e2e4', 220, tail=('e7e5', 'e2e4')),
                      event(board, 2, 'g1f3', 10)]
    elif bad_high == 'missing_rank':
        scripts[2] = [event(board, 1, 'e2e4', 220)]
    elif bad_high == 'invalid_score':
        scripts[2] = [dict(event(board, 1, 'e2e4', 220), score=None)]
    else:
        scripts[2] = bad_high
    engine = FakeEngine(*scripts)
    result = run(board, 'g1f3', engine)
    assert [item['status'] for item in result['attempts']] == [
        'succeeded', 'succeeded', 'failed']
    assert result['attempts'][2]['reason'] == reason
    assert result['comparison']['status'] == 'unresolved'
    assert result['comparison']['observed_loss_cp'] is None
    assert engine.closed


def test_engine_failure_has_complete_attempt_accounting_without_retry():
    board = chess.Board()
    engine = FakeEngine(RuntimeError('synthetic engine failure'))
    result = run(board, 'g1f3', engine)
    assert [item['status'] for item in result['attempts']] == [
        'failed', 'not_run', 'not_run']
    assert result['attempts'][0]['reason'] == 'engine_exception'
    assert result['comparison']['status'] == 'unresolved'
    assert len(engine.calls) == 1
    assert engine.closed


def test_low_budget_failure_skips_high_budget_and_keeps_cleanup_status():
    board = chess.Board()
    discovery = normal_scripts(board)[0]
    engine = FakeEngine(discovery, RuntimeError('synthetic low-budget failure'))
    result = run(board, 'g1f3', engine)
    assert [item['status'] for item in result['attempts']] == [
        'succeeded', 'failed', 'not_run']
    assert result['comparison']['reason'] == 'engine_exception'
    assert result['engine_cleanup'] == 'closed'
    assert len(engine.calls) == 2


def test_cleanup_error_does_not_erase_attempt_accounting():
    board = chess.Board()

    class FailingCloseEngine(FakeEngine):
        def close(self):
            raise RuntimeError('synthetic cleanup failure')

    engine = FailingCloseEngine(RuntimeError('synthetic search failure'))
    result = run(board, 'g1f3', engine)
    assert result['attempts'][0]['status'] == 'failed'
    assert result['engine_cleanup'] == 'failed'
    assert result['comparison']['status'] == 'unresolved'
