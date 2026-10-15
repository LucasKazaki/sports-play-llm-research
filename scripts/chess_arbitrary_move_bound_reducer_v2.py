#!/usr/bin/env python3
"""Reduce a verified v1 practice run to a one-sided, evaluator-only contrast.

An ``upperbound`` UCI score for the selected move and an unqualified score for
the alternative imply a lower floor on the *reported search-score difference*:
alternative score - selected score >= alternative score - selected upper bound.
This does not bound the true value of a chess position or explain an engine move.

The ``r4`` entrypoint pins the exact Chess.com Qc3 practice result and its native
execution receipt before calling the existing offline verifier. It writes a new
sidecar; it never changes the v1 files or starts an engine or language model.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import chess

import chess_arbitrary_move_contrast_v1 as contrast
import chess_arbitrary_move_practice_v1 as practice


SCHEMA = 'chess-arbitrary-move-bound-reducer/v2'
ROOT = Path(__file__).resolve().parents[1]
R4_DIRECTORY = ROOT / 'artifacts/chess-arbitrary-move-practice-v1/chesscom-184866057876-qc3-r4'
R4_NATIVE_RECEIPT = ROOT / '.agent-runtime/jobs/68195dc6-5454-4d7b-bbc6-36dcb1585c85/receipt.json'
R4_SHA256 = {
    'source.json': '76315de63a2d76e5028b72ea5bf56395f8b71029e1f079d8807054aac712a8db',
    'attempt.json': '0c7d9865ddda9dfd4a4d86291654e85337624c8c5e4cdd0bc0dd104585a7d57c',
    'result.json': '8ad7745ac26adc21a3f4ace1855d46b9ae41452b05b1a570011671701f632a64',
    'seal.json': 'ef87943af0e2c54fa18b7d15d9e63f8cea3c5820a61aa8eb1563397e9445a575',
    'native_receipt': '96077f3694b1716ad06f5637e69e01926326f8ba9e688fa37bb132d57c3e23f4',
}
R4_TASK_ID = '6a5694f9-9297-4bf4-940e-99f408b2a905'
R4_JOB_ID = '68195dc6-5454-4d7b-bbc6-36dcb1585c85'
R4_RUN_DIRECTORY_ARGUMENT = (
    'artifacts/chess-arbitrary-move-practice-v1/chesscom-184866057876-qc3-r4'
)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read_pinned(path: Path, expected_sha256: str, maximum: int) -> bytes:
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('missing_or_oversize_pinned_evidence')
    raw = path.read_bytes()
    if _digest(raw) != expected_sha256:
        raise ValueError('r4_pinned_evidence_hash_mismatch')
    return raw


def _score_pair(observations: list[dict], selected: str,
                alternative: str, side: str) -> tuple[dict, dict]:
    by_root = {item['move_uci']: item['score'] for item in observations}
    if set(by_root) != {selected, alternative}:
        raise ValueError('paired_roots_mismatch')
    chosen, other = by_root[selected], by_root[alternative]
    for score in (chosen, other):
        if (type(score) is not dict or score.get('perspective') != 'side_to_move' or
                score.get('side_to_move') != side or score.get('order') != 'engine_score' or
                score.get('type') not in {'cp', 'mate'} or
                score.get('bound') not in {'exact', 'upper', 'lower'} or
                type(score.get('value')) is not int):
            raise ValueError('incompatible_score_perspective_or_type')
    return chosen, other


def _unresolved(reason: str, floors: list[int] | None = None) -> dict:
    return {'schema': SCHEMA, 'status': 'unresolved', 'reason': reason,
            'search_observation_floor_cp_by_budget': floors,
            'conservative_search_observation_floor_cp': None,
            'exact_loss_cp': None,
            'scope': 'engine_reported_pairwise_search_score_only',
            'limitations': [
                'A UCI search-score bound is not a bound on the true chess value.',
                'An unqualified engine score is not an exact chess value.',
                'The result does not explain Stockfish intent or teaching quality.',
            ]}


def reduce_record(result: dict) -> dict:
    """Reduce a structurally valid v1 record; callers must verify provenance.

    The public ``r4`` route pins bytes, checks the native receipt, and invokes
    ``practice.verify`` before calling this function. Synthetic unit tests may
    call this pure function without opening an engine or model.
    """
    if (type(result) is not dict or result.get('schema') != practice.SCHEMA or
            result.get('status') != 'unresolved' or
            result.get('reason') != 'mate_or_qualified_score' or
            result.get('engine_cleanup') not in {'closed', 'evaluator_closed'} or
            result.get('failure_codes') != [] or
            result.get('engine_launch_attempted') is not True or
            result.get('model_calls') != 0 or result.get('browser_calls') != 0):
        raise ValueError('invalid_v1_practice_result')
    engine_pin = result.get('engine')
    if type(engine_pin) is not dict:
        raise ValueError('invalid_v1_engine_pin')
    evaluation = result.get('evaluation')
    if (type(evaluation) is not dict or evaluation.get('schema') != contrast.SCHEMA or
            evaluation.get('evaluator_only') is not True or
            evaluation.get('comparison') != {
                'status': 'unresolved', 'reason': 'mate_or_qualified_score',
                'delta_cp_by_budget': None, 'observed_loss_cp': None} or
            evaluation.get('selected_uci') != result.get('selected_uci') or
            evaluation.get('position_sha256') != result.get('position_sha256') or
            evaluation.get('source_receipt_sha256') != result.get('source_receipt_sha256') or
            evaluation.get('engine_sha256') != engine_pin.get('sha256') or
            evaluation.get('engine_name') != contrast.ENGINE_NAME or
            evaluation.get('settings') != practice._expected_settings() or
            evaluation.get('settings_sha256') !=
            contrast._digest(contrast._canonical(practice._expected_settings()))):
        raise ValueError('invalid_v1_evaluator_record')
    try:
        board = chess.Board(evaluation['fen_before'])
        selected = evaluation['selected_uci']
        alternative = evaluation['alternative_uci']
        selected_move = chess.Move.from_uci(selected)
        alternative_move = chess.Move.from_uci(alternative)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('invalid_paired_position') from error
    if (not board.is_valid() or board.chess960 or selected == alternative or
            selected_move not in board.legal_moves or
            alternative_move not in board.legal_moves or
            contrast.position_sha256(board, selected) != result['position_sha256']):
        raise ValueError('invalid_paired_position')
    attempts = evaluation.get('attempts')
    if (type(attempts) is not list or len(attempts) != 3 or
            [item.get('phase') if type(item) is dict else None for item in attempts]
            != list(contrast.PHASES) or
            any(item.get('status') != 'succeeded' for item in attempts)):
        raise ValueError('missing_successful_paired_searches')
    discovery = practice._check_success_attempt(
        attempts[0], board, nodes=contrast.NODE_BUDGETS[1], roots=[])
    discovery_roots = [item['move_uci'] for item in discovery]
    if next(root for root in discovery_roots if root != selected) != alternative:
        raise ValueError('discovery_alternative_mismatch')
    side = 'white' if board.turn else 'black'
    floors = []
    for index, budget in enumerate(contrast.NODE_BUDGETS, 1):
        observations = practice._check_success_attempt(
            attempts[index], board, nodes=budget, roots=[selected, alternative])
        if observations[0]['nodes_observed'] != observations[1]['nodes_observed']:
            raise ValueError('incomparable_rank_node_counts')
        chosen, other = _score_pair(observations, selected, alternative, side)
        if chosen['type'] != 'cp' or other['type'] != 'cp':
            return _unresolved('mate_score_cannot_yield_cp_floor')
        if chosen['bound'] != 'upper' or other['bound'] != 'exact':
            return _unresolved('unsupported_one_sided_bound_pattern')
        floors.append(other['value'] - chosen['value'])
    threshold = contrast.INFERIOR_THRESHOLD_CP
    if any(floor < threshold for floor in floors):
        return _unresolved('threshold_not_supported_at_both_budgets', floors)
    if abs(floors[1] - floors[0]) > contrast.MAX_BUDGET_DELTA_DRIFT_CP:
        return _unresolved('floor_drift_exceeds_predeclared_limit', floors)
    outcome = _unresolved('internal_unset', floors)
    outcome.update(status='paired_search_floor_exceeds_threshold', reason=None,
                   conservative_search_observation_floor_cp=min(floors))
    return outcome


def _check_native_receipt(receipt: dict) -> None:
    if (type(receipt) is not dict or receipt.get('schema') != 'project-execution-receipt/v1' or
            receipt.get('jobId') != R4_JOB_ID or receipt.get('taskId') != R4_TASK_ID or
            receipt.get('projectId') != 'sports-play-llm' or
            receipt.get('status') != 'succeeded'):
        raise ValueError('r4_native_receipt_identity_mismatch')
    commands = receipt.get('commands')
    if type(commands) is not list or len(commands) != 5:
        raise ValueError('r4_native_receipt_commands_mismatch')
    for command in commands:
        sandbox_entry = command.get('sandboxEntry') if type(command) is dict else None
        if (type(command) is not dict or command.get('exitCode') != 0 or
                command.get('timedOut') is not False or
                command.get('projectCommandStarted') is not True or
                type(sandbox_entry) is not dict or
                sandbox_entry.get('status') != 'entered'):
            raise ValueError('r4_native_command_failure')
    run, verify = commands[1:3]
    if (run.get('args') != [
            'scripts/chess_arbitrary_move_practice_v1.py', 'run',
            '--selected-uci', 'c2c3', '--output-dir', R4_RUN_DIRECTORY_ARGUMENT] or
            verify.get('args') != [
                'scripts/chess_arbitrary_move_practice_v1.py', 'verify',
                '--output-dir', R4_RUN_DIRECTORY_ARGUMENT]):
        raise ValueError('r4_native_command_route_mismatch')
    try:
        verification = json.loads(verify['stdoutTail'].strip())
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('r4_native_verification_missing') from error
    if (verification.get('status') != 'verified_local_evidence' or
            verification.get('run_status') != 'unresolved' or
            verification.get('reason') != 'mate_or_qualified_score' or
            verification.get('result_sha256') != R4_SHA256['result.json'] or
            verification.get('source_receipt_sha256') != R4_SHA256['source.json'] or
            verification.get('engine_sha256') != practice.PINS.engine_sha256 or
            verification.get('pgn_sha256') != practice.PINS.pgn_sha256 or
            verification.get('engine_calls') != 0 or
            verification.get('model_calls') != 0):
        raise ValueError('r4_native_verification_mismatch')


def reduce_r4(practice_dir: Path = R4_DIRECTORY,
              native_receipt: Path = R4_NATIVE_RECEIPT) -> dict:
    """Verify the exact real r4 bytes before making a separate v2 observation."""
    raws = {name: _read_pinned(practice_dir / name, digest, 2 * 1024 * 1024)
            for name, digest in R4_SHA256.items() if name.endswith('.json')}
    native_raw = _read_pinned(native_receipt, R4_SHA256['native_receipt'],
                              2 * 1024 * 1024)
    _check_native_receipt(json.loads(native_raw))
    verification = practice.verify(practice.DEFAULT_PGN, practice.DEFAULT_ENGINE,
                                   practice_dir)
    if (verification['status'] != 'verified_local_evidence' or
            verification['result_sha256'] != R4_SHA256['result.json'] or
            verification['source_receipt_sha256'] != R4_SHA256['source.json']):
        raise ValueError('r4_local_verification_mismatch')
    outcome = reduce_record(json.loads(raws['result.json']))
    if outcome['status'] != 'paired_search_floor_exceeds_threshold':
        raise ValueError('r4_bound_comparison_not_supported')
    outcome['provenance'] = {
        'game_id': practice.PINS.game_id,
        'pgn_sha256': practice.PINS.pgn_sha256,
        'engine_sha256': practice.PINS.engine_sha256,
        'selected_uci': 'c2c3', 'alternative_uci': 'c2e4',
        'source_v1_sha256': R4_SHA256['source.json'],
        'result_v1_sha256': R4_SHA256['result.json'],
        'seal_v1_sha256': R4_SHA256['seal.json'],
        'native_task_id': R4_TASK_ID, 'native_job_id': R4_JOB_ID,
        'native_receipt_sha256': R4_SHA256['native_receipt'],
        'verification': 'pinned_native_receipt_and_current_local_offline_verifier',
    }
    outcome['limitations'].append(
        'The native receipt here is an inspection copy; the runtime owns its original.')
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['r4'])
    parser.add_argument('--practice-dir', type=Path, default=R4_DIRECTORY)
    parser.add_argument('--native-receipt', type=Path, default=R4_NATIVE_RECEIPT)
    parser.add_argument('--output', type=Path,
                        default=R4_DIRECTORY / 'bound-comparison-v2.json')
    args = parser.parse_args(argv)
    outcome = reduce_r4(args.practice_dir, args.native_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(_canonical(outcome))
    print(json.dumps({'schema': SCHEMA, 'status': outcome['status'],
                      'conservative_search_observation_floor_cp':
                      outcome['conservative_search_observation_floor_cp'],
                      'output_sha256': _digest(_canonical(outcome)),
                      'output': str(args.output), 'engine_calls': 0,
                      'model_calls': 0}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
