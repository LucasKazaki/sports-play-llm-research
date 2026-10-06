#!/usr/bin/env python3
"""Evaluator-only, bounded contrast for a source-pinned arbitrary legal move.

The caller must verify the source receipt and engine binary upstream. This module
checks the supplied position pin, never launches an engine, and has no generator
interface. Its injected engine receives one unrestricted discovery search and,
when discovery succeeds, the same two root moves at two fixed node budgets.
Scores and lines are observations, not Stockfish's rationale or chess teaching.
"""
from __future__ import annotations

import hashlib
import json
import time

import chess
import chess.engine

from chess_score_bounds import typed_score_bound


SCHEMA = 'chess-arbitrary-move-contrast-evaluator/v1'
ENGINE_NAME = 'Stockfish 19'
ENGINE_OPTIONS = {'Threads': 1, 'Hash': 16, 'Skill Level': 20,
                  'UCI_LimitStrength': False, 'UCI_Chess960': False}
NODE_BUDGETS = (30_000, 100_000)
INFERIOR_THRESHOLD_CP = 150
MAX_BUDGET_DELTA_DRIFT_CP = 100
MIN_FINAL_SCORE_NODES_NUMERATOR = 4
MIN_FINAL_SCORE_NODES_DENOMINATOR = 5
MAX_EVENTS = 4096
MAX_PV_PLIES = 128
SEARCH_TIMEOUT_SECONDS = 30
PHASES = ('discovery', 'paired_low', 'paired_high')


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def position_sha256(board: chess.Board, selected_uci: str) -> str:
    """Pin the pre-move position and selected move, including FEN clocks."""
    return _digest(_canonical({'fen_before': board.fen(),
                               'selected_uci': selected_uci}))


def _sha(value: object, field: str) -> str:
    if (type(value) is not str or len(value) != 64 or
            any(c not in '0123456789abcdef' for c in value)):
        raise ValueError(f'{field}_invalid_sha256')
    return value


class SearchFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _checked_observation(board: chess.Board, info: dict, sequence: int) -> dict:
    if not isinstance(info, dict):
        raise SearchFailure('invalid_score_event')
    rank = info.get('multipv')
    pv = info.get('pv')
    if (type(rank) is not int or rank not in (1, 2) or
            type(pv) is not list or not 1 <= len(pv) <= MAX_PV_PLIES or
            type(info.get('nodes')) is not int or info['nodes'] < 1 or
            type(info.get('depth')) is not int or info['depth'] < 1):
        raise SearchFailure('incomplete_score_event')
    replay = board.copy(stack=True)
    for move in pv:
        if not isinstance(move, chess.Move) or move not in replay.legal_moves:
            raise SearchFailure('illegal_engine_line')
        replay.push(move)
    try:
        score = typed_score_bound(info, board.turn)
    except (TypeError, ValueError) as error:
        raise SearchFailure('invalid_typed_score') from error
    return {'rank': rank, 'move_uci': pv[0].uci(), 'score': score,
            'nodes_observed': info['nodes'], 'depth': info['depth'],
            'score_info_sequence': sequence, 'line_plies_checked': len(pv)}


def _capture(engine: object, board: chess.Board, *, phase: str,
             nodes: int, roots: tuple[chess.Move, ...] | None,
             position_pin: str) -> tuple[dict, list[dict]]:
    """Use original score events; merged MultiPV views can retain stale bounds."""
    request = {'phase': phase, 'fen_before': board.fen(), 'nodes': nodes,
               'multipv': 2, 'root_moves_uci': [move.uci() for move in roots] if roots else [],
               'options': ENGINE_OPTIONS}
    attempt = {'phase': phase, 'status': 'not_run', 'reason': None,
               'request_sha256': _digest(_canonical(request)),
               'nodes_requested': nodes, 'roots_requested': request['root_moves_uci'],
               'observations': []}
    latest: dict[int, dict] = {}
    try:
        with engine.analysis(board.copy(stack=True), chess.engine.Limit(nodes=nodes),
                             multipv=2, root_moves=list(roots) if roots else None,
                             options=dict(ENGINE_OPTIONS),
                             game=f'{position_pin}:{phase}') as stream:
            deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
            sequence = 0
            while True:
                if time.monotonic() >= deadline:
                    raise SearchFailure('search_timeout')
                if stream.would_block():
                    time.sleep(0.01)
                    continue
                info = stream.next()
                if info is None:
                    break
                sequence += 1
                if sequence > MAX_EVENTS:
                    raise SearchFailure('score_event_budget_exceeded')
                if not isinstance(info, dict):
                    raise SearchFailure('invalid_score_event')
                if 'score' in info:
                    observation = _checked_observation(board, info, sequence)
                    latest[observation['rank']] = observation
        if set(latest) != {1, 2}:
            raise SearchFailure('missing_score_rank')
        observations = [latest[rank] for rank in (1, 2)]
        if observations[0]['depth'] != observations[1]['depth']:
            raise SearchFailure('incomparable_rank_depth')
        minimum_nodes = ((nodes * MIN_FINAL_SCORE_NODES_NUMERATOR +
                          MIN_FINAL_SCORE_NODES_DENOMINATOR - 1) //
                         MIN_FINAL_SCORE_NODES_DENOMINATOR)
        if any(item['nodes_observed'] < minimum_nodes for item in observations):
            raise SearchFailure('insufficient_score_event_nodes')
        found = [item['move_uci'] for item in observations]
        if len(set(found)) != 2:
            raise SearchFailure('duplicate_engine_root')
        if roots is not None and set(found) != {move.uci() for move in roots}:
            raise SearchFailure('paired_root_mismatch')
        attempt['status'] = 'succeeded'
        attempt['observations'] = observations
        return attempt, observations
    except SearchFailure as error:
        attempt['status'], attempt['reason'] = 'failed', error.code
        return attempt, []
    except Exception:
        attempt['status'], attempt['reason'] = 'failed', 'engine_exception'
        return attempt, []


def _comparison(low: list[dict], high: list[dict], selected: str,
                alternative: str) -> dict:
    by_budget = []
    for observations in (low, high):
        by_root = {item['move_uci']: item['score'] for item in observations}
        selected_score, alternative_score = by_root[selected], by_root[alternative]
        if any(score['type'] != 'cp' or score['bound'] != 'exact'
               for score in (selected_score, alternative_score)):
            return {'status': 'unresolved', 'reason': 'mate_or_qualified_score',
                    'delta_cp_by_budget': None, 'observed_loss_cp': None}
        by_budget.append(alternative_score['value'] - selected_score['value'])
    low_delta, high_delta = by_budget
    # A changed ordering or threshold category is unstable at these budgets.
    if ((low_delta > 0) != (high_delta > 0) or
            (low_delta >= INFERIOR_THRESHOLD_CP) !=
            (high_delta >= INFERIOR_THRESHOLD_CP) or
            abs(high_delta - low_delta) > MAX_BUDGET_DELTA_DRIFT_CP):
        return {'status': 'unresolved', 'reason': 'unstable_contrast',
                'delta_cp_by_budget': None, 'observed_loss_cp': None}
    if high_delta >= INFERIOR_THRESHOLD_CP:
        return {'status': 'observed_inferior_in_pair', 'reason': None,
                'delta_cp_by_budget': by_budget, 'observed_loss_cp': high_delta}
    return {'status': 'not_observed_inferior_in_pair', 'reason': None,
            'delta_cp_by_budget': by_budget, 'observed_loss_cp': None}


def _close_failed_engine(engine: object, record: dict) -> None:
    if not hasattr(engine, 'close'):
        record['engine_cleanup'] = 'unavailable'
        return
    try:
        engine.close()
    except Exception:
        record['engine_cleanup'] = 'failed'
    else:
        record['engine_cleanup'] = 'closed'


def evaluate(board: chess.Board, selected_uci: str, *,
             source_receipt_sha256: str, expected_position_sha256: str,
             engine_sha256: str, engine: object) -> dict:
    """Return one complete evaluator-side record; never generate commentary.

    The source receipt and binary digests are caller pins, not independently
    reverified here. The caller must perform those checks before this evaluator.
    """
    _sha(source_receipt_sha256, 'source_receipt')
    _sha(engine_sha256, 'engine')
    _sha(expected_position_sha256, 'position')
    if type(board) is not chess.Board or board.chess960 or not board.is_valid():
        raise ValueError('invalid_pre_move_board')
    if type(selected_uci) is not str:
        raise ValueError('invalid_selected_move')
    try:
        selected = chess.Move.from_uci(selected_uci)
    except ValueError as error:
        raise ValueError('invalid_selected_move') from error
    if selected not in board.legal_moves:
        raise ValueError('illegal_selected_move')
    pin = position_sha256(board, selected_uci)
    if pin != expected_position_sha256:
        raise ValueError('source_position_pin_mismatch')
    engine_id = getattr(engine, 'id', None)
    if not isinstance(engine_id, dict) or engine_id.get('name') != ENGINE_NAME:
        raise ValueError('engine_identity_unverified')
    settings = {'engine_options': ENGINE_OPTIONS, 'node_budgets': list(NODE_BUDGETS),
                'inferior_threshold_cp': INFERIOR_THRESHOLD_CP,
                'max_budget_delta_drift_cp': MAX_BUDGET_DELTA_DRIFT_CP,
                'max_events': MAX_EVENTS, 'max_pv_plies': MAX_PV_PLIES,
                'search_timeout_seconds': SEARCH_TIMEOUT_SECONDS,
                'min_final_score_nodes_fraction': [MIN_FINAL_SCORE_NODES_NUMERATOR,
                                                   MIN_FINAL_SCORE_NODES_DENOMINATOR],
                'discovery': 'unrestricted_two_roots_at_high_budget',
                'paired': 'same_two_roots_one_multipv_call_per_budget'}
    attempts = [{'phase': phase, 'status': 'not_run', 'reason': 'earlier_stage',
                 'request_sha256': None, 'nodes_requested': None,
                 'roots_requested': [], 'observations': []} for phase in PHASES]
    record = {'schema': SCHEMA, 'evaluator_only': True,
              'source_receipt_sha256': source_receipt_sha256,
              'position_sha256': pin, 'fen_before': board.fen(),
              'selected_uci': selected_uci, 'engine_sha256': engine_sha256,
              'engine_name': ENGINE_NAME, 'settings': settings,
              'settings_sha256': _digest(_canonical(settings)),
              'engine_cleanup': 'caller_owned',
              'alternative_uci': None, 'attempts': attempts,
              'comparison': {'status': 'unresolved', 'reason': 'not_run',
                             'delta_cp_by_budget': None, 'observed_loss_cp': None},
              'limitations': ['Source receipt and engine binary require upstream verification.',
                              'FEN alone may omit earlier repetition history; retain a caller board stack.',
                              'One legal PV is not a forced line or an explanation of engine intent.',
                              'Paired scores are bounded observations, not objective move labels.',
                              'No generator, model, source acquisition or engine launch is performed.']}
    if board.legal_moves.count() == 1:
        for attempt in attempts:
            attempt['reason'] = 'only_one_legal_move'
        record['comparison']['reason'] = 'only_one_legal_move'
        return record

    searches = (('discovery', NODE_BUDGETS[1], None),)
    for index, (phase, nodes, roots) in enumerate(searches):
        attempt, observations = _capture(engine, board, phase=phase, nodes=nodes,
                                         roots=roots, position_pin=pin)
        attempts[index] = attempt
        if attempt['status'] != 'succeeded':
            record['comparison']['reason'] = attempt['reason']
            _close_failed_engine(engine, record)
            return record
    discovery_roots = [item['move_uci'] for item in observations]
    alternative_uci = next(root for root in discovery_roots if root != selected_uci)
    alternative = chess.Move.from_uci(alternative_uci)
    record['alternative_uci'] = alternative_uci
    if any(item['score']['type'] != 'cp' or item['score']['bound'] != 'exact'
           for item in observations):
        record['comparison']['reason'] = 'discovery_mate_or_qualified_score'
        for attempt in attempts[1:]:
            attempt['reason'] = 'discovery_mate_or_qualified_score'
        return record
    roots = (selected, alternative)
    paired = []
    for index, (phase, nodes) in enumerate(zip(PHASES[1:], NODE_BUDGETS), start=1):
        attempt, found = _capture(engine, board, phase=phase, nodes=nodes,
                                  roots=roots, position_pin=pin)
        attempts[index] = attempt
        if attempt['status'] != 'succeeded':
            record['comparison']['reason'] = attempt['reason']
            _close_failed_engine(engine, record)
            return record
        paired.append(found)
    record['comparison'] = _comparison(paired[0], paired[1], selected_uci,
                                       alternative_uci)
    return record
