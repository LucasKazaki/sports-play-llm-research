"""Synthetic reducer checks; no Stockfish, model, or real r4 reduction runs."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import chess
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import chess_arbitrary_move_bound_reducer_v2 as reducer  # noqa: E402
import chess_arbitrary_move_contrast_v1 as contrast  # noqa: E402
import chess_arbitrary_move_practice_v1 as practice  # noqa: E402


SOURCE_SHA = 'a' * 64
ENGINE_SHA = 'b' * 64


def score(value: int, side: str, bound: str = 'exact', kind: str = 'cp') -> dict:
    return {'type': kind, 'value': value, 'perspective': 'side_to_move',
            'side_to_move': side, 'bound': bound, 'order': 'engine_score'}


def observation(rank: int, move: str, value: int, side: str,
                *, nodes: int, depth: int, bound: str = 'exact') -> dict:
    return {'rank': rank, 'move_uci': move,
            'score': score(value, side, bound),
            'nodes_observed': nodes, 'depth': depth,
            'score_info_sequence': rank, 'line_plies_checked': 1}


def attempt(board: chess.Board, phase: str, nodes: int,
            roots: list[str], observations: list[dict]) -> dict:
    request = {'phase': phase, 'fen_before': board.fen(), 'nodes': nodes,
               'multipv': 2, 'root_moves_uci': roots,
               'options': contrast.ENGINE_OPTIONS}
    return {'phase': phase, 'status': 'succeeded', 'reason': None,
            'request_sha256': contrast._digest(contrast._canonical(request)),
            'nodes_requested': nodes, 'roots_requested': roots,
            'observations': observations}


def fixture(board: chess.Board | None = None, selected: str = 'g1f3',
            alternative: str = 'e2e4', discovery_other: str = 'd2d4',
            low: tuple[int, int] = (200, 0),
            high: tuple[int, int] = (220, 10)) -> dict:
    board = board or chess.Board()
    side = 'white' if board.turn else 'black'
    settings = practice._expected_settings()
    pin = contrast.position_sha256(board, selected)
    discovery = attempt(board, 'discovery', 100_000, [], [
        observation(1, alternative, 40, side, nodes=100_000, depth=12),
        observation(2, discovery_other, 20, side, nodes=100_000, depth=12),
    ])
    paired = []
    for phase, budget, depth, values in (
            ('paired_low', 30_000, 12, low),
            ('paired_high', 100_000, 14, high)):
        paired.append(attempt(board, phase, budget, [selected, alternative], [
            observation(1, alternative, values[0], side, nodes=budget, depth=depth),
            observation(2, selected, values[1], side, nodes=budget,
                        depth=depth, bound='upper'),
        ]))
    evaluation = {'schema': contrast.SCHEMA, 'evaluator_only': True,
                  'selected_uci': selected, 'alternative_uci': alternative,
                  'fen_before': board.fen(), 'position_sha256': pin,
                  'source_receipt_sha256': SOURCE_SHA,
                  'engine_sha256': ENGINE_SHA,
                  'engine_name': contrast.ENGINE_NAME,
                  'settings': settings,
                  'settings_sha256': contrast._digest(contrast._canonical(settings)),
                  'attempts': [discovery, *paired],
                  'comparison': {
                      'status': 'unresolved', 'reason': 'mate_or_qualified_score',
                      'delta_cp_by_budget': None, 'observed_loss_cp': None}}
    return {'schema': practice.SCHEMA, 'status': 'unresolved',
            'reason': 'mate_or_qualified_score', 'engine_cleanup': 'closed',
            'failure_codes': [], 'engine_launch_attempted': True,
            'model_calls': 0, 'browser_calls': 0,
            'source_receipt_sha256': SOURCE_SHA, 'engine': {'sha256': ENGINE_SHA},
            'position_sha256': pin, 'selected_uci': selected,
            'evaluation': evaluation}


def test_one_sided_search_score_floor_uses_minimum_over_budgets():
    record = fixture(low=(200, -108), high=(220, -133))
    outcome = reducer.reduce_record(record)
    assert outcome['status'] == 'paired_search_floor_exceeds_threshold'
    assert outcome['search_observation_floor_cp_by_budget'] == [308, 353]
    assert outcome['conservative_search_observation_floor_cp'] == 308
    assert outcome['exact_loss_cp'] is None
    assert 'pv' not in str(outcome) and 'fen_after' not in str(outcome)


def test_black_side_to_move_uses_its_own_score_perspective():
    board = chess.Board()
    board.push_uci('e2e4')
    record = fixture(board, selected='e7e5', alternative='c7c5',
                     discovery_other='e7e6', low=(100, -110),
                     high=(120, -115))
    outcome = reducer.reduce_record(record)
    assert outcome['status'] == 'paired_search_floor_exceeds_threshold'
    assert outcome['search_observation_floor_cp_by_budget'] == [210, 235]
    assert outcome['conservative_search_observation_floor_cp'] == 210


@pytest.mark.parametrize('mutation', [
    lambda r: r['evaluation']['attempts'][1]['observations'][1].update(depth=13),
    lambda r: r['evaluation']['attempts'][1]['observations'][1].update(nodes_observed=1),
    lambda r: r['evaluation']['attempts'][1]['observations'][1].update(nodes_observed=29_999),
    lambda r: r['evaluation']['attempts'][1]['observations'][1].update(move_uci='d2d4'),
    lambda r: r['evaluation']['attempts'][1]['observations'][1]['score'].update(side_to_move='black'),
    lambda r: r['evaluation']['attempts'][2].update(status='failed'),
    lambda r: r['evaluation']['attempts'][2].update(request_sha256='0' * 64),
    lambda r: r['evaluation']['attempts'][1]['observations'][1].update(score_info_sequence=1),
    lambda r: r['evaluation'].update(settings_sha256='0' * 64),
    lambda r: r.update(position_sha256='0' * 64),
])
def test_tampered_or_incomparable_pair_cannot_emit_floor(mutation):
    record = fixture()
    mutation(record)
    with pytest.raises(ValueError):
        reducer.reduce_record(record)


def test_mate_score_does_not_become_a_centipawn_floor():
    record = fixture()
    record['evaluation']['attempts'][2]['observations'][1]['score'] = score(
        -3, 'white', 'upper', 'mate')
    outcome = reducer.reduce_record(record)
    assert outcome['status'] == 'unresolved'
    assert outcome['reason'] == 'mate_score_cannot_yield_cp_floor'
    assert outcome['conservative_search_observation_floor_cp'] is None


@pytest.mark.parametrize('move,bound', [('selected', 'lower'),
                                       ('alternative', 'upper')])
def test_wrong_one_sided_bound_pattern_is_unresolved(move, bound):
    record = fixture()
    index = 1 if move == 'selected' else 0
    record['evaluation']['attempts'][2]['observations'][index]['score']['bound'] = bound
    outcome = reducer.reduce_record(record)
    assert outcome['status'] == 'unresolved'
    assert outcome['reason'] == 'unsupported_one_sided_bound_pattern'


def test_threshold_and_floor_drift_stay_unresolved():
    below = reducer.reduce_record(fixture(low=(140, 0), high=(220, 0)))
    assert below['reason'] == 'threshold_not_supported_at_both_budgets'
    assert below['conservative_search_observation_floor_cp'] is None
    drifting = reducer.reduce_record(fixture(low=(200, 0), high=(350, 0)))
    assert drifting['reason'] == 'floor_drift_exceeds_predeclared_limit'
    assert drifting['search_observation_floor_cp_by_budget'] == [200, 350]
    assert drifting['conservative_search_observation_floor_cp'] is None


def test_pinned_r4_bytes_reject_tamper_before_local_verifier(tmp_path, monkeypatch):
    (tmp_path / 'source.json').write_bytes(b'not the frozen source')
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError('local verifier should not see changed bytes')
    monkeypatch.setattr(practice, 'verify', fail_if_called)
    with pytest.raises(ValueError, match='r4_pinned_evidence_hash_mismatch'):
        reducer.reduce_r4(tmp_path, tmp_path / 'missing-receipt.json')


def test_frozen_native_receipt_verifier_digest_is_required():
    receipt = {'schema': 'project-execution-receipt/v1',
               'jobId': reducer.R4_JOB_ID, 'taskId': reducer.R4_TASK_ID,
               'projectId': 'sports-play-llm', 'status': 'succeeded',
               'commands': [{
                   'exitCode': 0, 'timedOut': False, 'projectCommandStarted': True,
                   'sandboxEntry': {'status': 'entered'},
               } for _ in range(5)]}
    receipt['commands'][1]['args'] = [
        'scripts/chess_arbitrary_move_practice_v1.py', 'run',
        '--selected-uci', 'c2c3', '--output-dir', reducer.R4_RUN_DIRECTORY_ARGUMENT]
    receipt['commands'][2]['args'] = [
        'scripts/chess_arbitrary_move_practice_v1.py', 'verify',
        '--output-dir', reducer.R4_RUN_DIRECTORY_ARGUMENT]
    receipt['commands'][2]['stdoutTail'] = reducer._canonical({
        'status': 'verified_local_evidence', 'run_status': 'unresolved',
        'reason': 'mate_or_qualified_score',
        'result_sha256': '0' * 64,
        'source_receipt_sha256': reducer.R4_SHA256['source.json'],
        'engine_sha256': practice.PINS.engine_sha256,
        'pgn_sha256': practice.PINS.pgn_sha256,
        'engine_calls': 0, 'model_calls': 0,
    }).decode('utf-8')
    with pytest.raises(ValueError, match='r4_native_verification_mismatch'):
        reducer._check_native_receipt(receipt)
    fixed = copy.deepcopy(receipt)
    fixed['commands'][2]['stdoutTail'] = fixed['commands'][2]['stdoutTail'].replace(
        '0' * 64, reducer.R4_SHA256['result.json'])
    reducer._check_native_receipt(fixed)
