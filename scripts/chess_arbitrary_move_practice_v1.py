#!/usr/bin/env python3
"""One-game, evaluator-only practice driver for a pinned Chess.com PGN.

The CLI is deliberately tied to one already exported, completed game. ``run``
opens the local pinned Stockfish binary only after checking the exact PGN,
selected legal move, and binary bytes. ``verify`` never starts an engine. This
module has no generator or Chess.com review-label input, and its observations
are not an explanation of the engine's intent or a teaching-quality result.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

import chess
import chess.engine

import chess_arbitrary_move_contrast_v1 as contrast
import chess_review_completed_game as completed
import chess_score_bounds as score_bounds


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess-arbitrary-move-practice/v1'
SOURCE_SCHEMA = 'chess-arbitrary-move-practice-source/v1'
ATTEMPT_SCHEMA = 'chess-arbitrary-move-practice-attempt/v1'
SEAL_SCHEMA = 'chess-arbitrary-move-practice-local-seal/v1'
MAX_ENGINE_BYTES = 512 * 1024 * 1024
DEFAULT_PGN = ROOT / 'artifacts/chess-user-reviews/chesscom-184866057876/source.pgn'
DEFAULT_ENGINE = ROOT / 'vendor/stockfish-19/stockfish/stockfish-windows-x86-64-universal.exe'


@dataclass(frozen=True)
class PracticePins:
    game_id: str
    link: str
    pgn_sha256: str
    engine_sha256: str
    ply: int
    played_uci: str
    fen_before: str


PINS = PracticePins(
    game_id='chesscom:184866057876',
    link='https://www.chess.com/analysis/game/live/184866057876/review?move=38',
    pgn_sha256='684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075',
    engine_sha256='45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0',
    ply=39,
    played_uci='c2c3',
    fen_before='2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20',
)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _file_digest(path: Path, *, maximum: int) -> tuple[str, int]:
    if not path.is_file():
        raise ValueError('pinned_file_missing')
    digest = sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > maximum:
                raise ValueError('pinned_file_too_large')
            digest.update(chunk)
    if size == 0:
        raise ValueError('pinned_file_empty')
    return digest.hexdigest(), size


def _implementation_hashes() -> dict:
    return {
        'driver': _file_digest(Path(__file__), maximum=1024 * 1024)[0],
        'evaluator': _file_digest(Path(contrast.__file__), maximum=1024 * 1024)[0],
        'completed_game_loader': _file_digest(Path(completed.__file__), maximum=1024 * 1024)[0],
        'score_bounds': _file_digest(Path(score_bounds.__file__), maximum=1024 * 1024)[0],
    }


@dataclass
class Prepared:
    board: chess.Board
    source: dict
    source_bytes: bytes
    engine_pin: dict
    position_sha256: str


def prepare(pgn_path: Path, engine_path: Path, selected_uci: str,
            *, pins: PracticePins = PINS) -> Prepared:
    """Fail before launch unless the exact source and binary pins both hold."""
    game, raw, moves = completed.load_completed_game(pgn_path)
    if _digest(raw) != pins.pgn_sha256:
        raise ValueError('source_pgn_sha256_mismatch')
    if game.headers.get('Link') != pins.link:
        raise ValueError('source_game_link_mismatch')
    if type(pins.ply) is not int or not 1 <= pins.ply <= len(moves):
        raise ValueError('source_ply_missing')
    if moves[pins.ply - 1].uci() != pins.played_uci:
        raise ValueError('source_played_move_mismatch')
    board = completed.board_at_ply(game, moves, pins.ply)
    if board.fen() != pins.fen_before:
        raise ValueError('source_pre_move_board_mismatch')
    if type(selected_uci) is not str:
        raise ValueError('selected_move_invalid')
    try:
        selected = chess.Move.from_uci(selected_uci)
    except ValueError as error:
        raise ValueError('selected_move_invalid') from error
    if selected not in board.legal_moves:
        raise ValueError('selected_move_illegal')
    resolved_engine = engine_path.resolve(strict=True)
    engine_hash, engine_size = _file_digest(resolved_engine, maximum=MAX_ENGINE_BYTES)
    if engine_hash != pins.engine_sha256:
        raise ValueError('engine_binary_sha256_mismatch')
    source = {
        'schema': SOURCE_SCHEMA,
        'game_id': pins.game_id,
        'source_link': pins.link,
        'pgn_sha256': pins.pgn_sha256,
        'pgn_bytes': len(raw),
        'declared_completed_result': game.headers['Result'],
        'ply': pins.ply,
        'played_uci': pins.played_uci,
        'played_san': board.san(moves[pins.ply - 1]),
        'selected_uci': selected_uci,
        'selected_san': board.san(selected),
        'fen_before': board.fen(),
        'position_sha256': contrast.position_sha256(board, selected_uci),
        'history_plies': len(board.move_stack),
        'prior_uci_sha256': _digest(_canonical([move.uci() for move in moves[:pins.ply - 1]])),
        'implementation_sha256': _implementation_hashes(),
    }
    return Prepared(
        board=board,
        source=source,
        source_bytes=_canonical(source),
        engine_pin={'name': contrast.ENGINE_NAME, 'sha256': engine_hash,
                    'bytes': engine_size, 'path': str(resolved_engine)},
        position_sha256=source['position_sha256'],
    )


def _forbidden_output(value: object) -> bool:
    prohibited = {'pv', 'pv_uci', 'fen_after', 'post_move_fen', 'future_moves',
                  'solution', 'theme', 'annotation', 'human_annotation'}
    if isinstance(value, dict):
        return bool(prohibited.intersection(value)) or any(
            _forbidden_output(item) for item in value.values())
    if isinstance(value, list):
        return any(_forbidden_output(item) for item in value)
    return False


def _expected_settings() -> dict:
    return {'engine_options': contrast.ENGINE_OPTIONS,
            'node_budgets': list(contrast.NODE_BUDGETS),
            'inferior_threshold_cp': contrast.INFERIOR_THRESHOLD_CP,
            'max_budget_delta_drift_cp': contrast.MAX_BUDGET_DELTA_DRIFT_CP,
            'max_events': contrast.MAX_EVENTS, 'max_pv_plies': contrast.MAX_PV_PLIES,
            'search_timeout_seconds': contrast.SEARCH_TIMEOUT_SECONDS,
            'min_final_score_nodes_fraction': [contrast.MIN_FINAL_SCORE_NODES_NUMERATOR,
                                               contrast.MIN_FINAL_SCORE_NODES_DENOMINATOR],
            'discovery': 'unrestricted_two_roots_at_high_budget',
            'paired': 'same_two_roots_one_multipv_call_per_budget'}


def _check_score(score: object, side_to_move: str) -> None:
    base = {'type', 'value', 'perspective', 'side_to_move', 'bound', 'order'}
    if (type(score) is not dict or score.get('type') not in {'cp', 'mate'} or
            type(score.get('value')) is not int or
            score.get('perspective') != 'side_to_move' or
            score.get('side_to_move') != side_to_move or
            score.get('bound') not in {'exact', 'lower', 'upper'} or
            score.get('order') != 'engine_score'):
        raise ValueError('invalid_typed_observation_score')
    if score['type'] == 'mate' and score['value'] == 0:
        if set(score) != base | {'mate_zero'} or score.get('mate_zero') not in {'delivered', 'received'}:
            raise ValueError('invalid_typed_observation_score')
    elif set(score) != base:
        raise ValueError('invalid_typed_observation_score')


def _check_success_attempt(attempt: dict, board: chess.Board, *, nodes: int,
                           roots: list[str]) -> list[dict]:
    if attempt.get('reason') is not None or type(attempt.get('observations')) is not list or len(attempt['observations']) != 2:
        raise ValueError('incomplete_successful_search')
    expected_request = {'phase': attempt['phase'], 'fen_before': board.fen(),
                        'nodes': nodes, 'multipv': 2, 'root_moves_uci': roots,
                        'options': contrast.ENGINE_OPTIONS}
    if (attempt.get('nodes_requested') != nodes or attempt.get('roots_requested') != roots or
            attempt.get('request_sha256') != _digest(contrast._canonical(expected_request))):
        raise ValueError('search_request_mismatch')
    minimum_nodes = ((nodes * contrast.MIN_FINAL_SCORE_NODES_NUMERATOR +
                      contrast.MIN_FINAL_SCORE_NODES_DENOMINATOR - 1) //
                     contrast.MIN_FINAL_SCORE_NODES_DENOMINATOR)
    observations = attempt['observations']
    move_ucis = []
    depths = []
    for rank, item in enumerate(observations, 1):
        if (type(item) is not dict or set(item) !=
                {'rank', 'move_uci', 'score', 'nodes_observed', 'depth',
                 'score_info_sequence', 'line_plies_checked'} or
                type(item.get('rank')) is not int or item['rank'] != rank or
                type(item.get('move_uci')) is not str or
                type(item.get('nodes_observed')) is not int or item['nodes_observed'] < minimum_nodes or
                type(item.get('depth')) is not int or item['depth'] < 1 or
                type(item.get('score_info_sequence')) is not int or
                not 1 <= item['score_info_sequence'] <= contrast.MAX_EVENTS or
                type(item.get('line_plies_checked')) is not int or
                not 1 <= item['line_plies_checked'] <= contrast.MAX_PV_PLIES):
            raise ValueError('incomplete_successful_search')
        try:
            move = chess.Move.from_uci(item['move_uci'])
        except ValueError as error:
            raise ValueError('invalid_observed_root') from error
        if move not in board.legal_moves:
            raise ValueError('invalid_observed_root')
        _check_score(item['score'], 'white' if board.turn else 'black')
        move_ucis.append(item['move_uci'])
        depths.append(item['depth'])
    if len(set(move_ucis)) != 2 or depths[0] != depths[1]:
        raise ValueError('incomparable_observed_roots')
    if observations[0]['score_info_sequence'] == observations[1]['score_info_sequence']:
        raise ValueError('duplicate_observation_sequence')
    if roots and set(move_ucis) != set(roots):
        raise ValueError('paired_root_mismatch')
    return observations


def _check_failed_attempt(attempt: dict, board: chess.Board, *, nodes: int,
                          roots: list[str]) -> None:
    expected_request = {'phase': attempt['phase'], 'fen_before': board.fen(),
                        'nodes': nodes, 'multipv': 2, 'root_moves_uci': roots,
                        'options': contrast.ENGINE_OPTIONS}
    if (attempt.get('nodes_requested') != nodes or attempt.get('roots_requested') != roots or
            attempt.get('request_sha256') != _digest(contrast._canonical(expected_request))):
        raise ValueError('failed_search_request_mismatch')


def _check_evaluation(record: object, prepared: Prepared, source_sha256: str) -> None:
    if not isinstance(record, dict) or _forbidden_output(record):
        raise ValueError('invalid_evaluator_record')
    if set(record) != {'schema', 'evaluator_only', 'source_receipt_sha256',
                       'position_sha256', 'fen_before', 'selected_uci', 'engine_sha256',
                       'engine_name', 'settings', 'settings_sha256', 'engine_cleanup',
                       'alternative_uci', 'attempts', 'comparison', 'limitations'}:
        raise ValueError('invalid_evaluator_record')
    if record['evaluator_only'] is not True:
        raise ValueError('invalid_evaluator_only_flag')
    expected = {'schema': contrast.SCHEMA,
                'evaluator_only': True, 'engine_name': contrast.ENGINE_NAME,
                'source_receipt_sha256': source_sha256,
                'position_sha256': prepared.position_sha256,
                'fen_before': prepared.board.fen(),
                'selected_uci': prepared.source['selected_uci'],
                'engine_sha256': prepared.engine_pin['sha256']}
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError('evaluator_pin_mismatch')
    settings = _expected_settings()
    if (record.get('settings') != settings or
            record.get('settings_sha256') != _digest(contrast._canonical(settings))):
        raise ValueError('evaluator_settings_mismatch')
    attempts = record.get('attempts')
    comparison = record.get('comparison')
    if (not isinstance(attempts, list) or len(attempts) != 3 or
            [item.get('phase') if isinstance(item, dict) else None for item in attempts]
            != list(contrast.PHASES) or not isinstance(comparison, dict) or
            comparison.get('status') not in {'unresolved', 'observed_inferior_in_pair',
                                             'not_observed_inferior_in_pair'}):
        raise ValueError('invalid_evaluator_record')
    for attempt in attempts:
        if (type(attempt) is not dict or set(attempt) != {'phase', 'status', 'reason', 'request_sha256',
                            'nodes_requested', 'roots_requested', 'observations'} or
                attempt['status'] not in {'succeeded', 'failed', 'not_run'}):
            raise ValueError('invalid_evaluator_attempt')
        if attempt['status'] == 'not_run' and (attempt['request_sha256'] is not None or
                attempt['nodes_requested'] is not None or attempt['roots_requested'] != [] or
                attempt['observations'] != [] or type(attempt['reason']) is not str):
            raise ValueError('invalid_not_run_attempt')
        if attempt['status'] == 'failed' and (type(attempt['reason']) is not str or
                attempt['observations'] != []):
            raise ValueError('invalid_failed_attempt')
    selected = prepared.source['selected_uci']
    if prepared.board.legal_moves.count() == 1:
        expected_comparison = {'status': 'unresolved', 'reason': 'only_one_legal_move',
                               'delta_cp_by_budget': None, 'observed_loss_cp': None}
        if any(item['status'] != 'not_run' or item['reason'] != 'only_one_legal_move'
               for item in attempts) or record['alternative_uci'] is not None:
            raise ValueError('single_move_attempt_mismatch')
    else:
        discovery = attempts[0]
        if discovery['status'] == 'not_run':
            raise ValueError('missing_discovery_attempt')
        if discovery['status'] == 'failed':
            _check_failed_attempt(discovery, prepared.board,
                                  nodes=contrast.NODE_BUDGETS[1], roots=[])
            expected_comparison = {'status': 'unresolved', 'reason': discovery['reason'],
                                   'delta_cp_by_budget': None, 'observed_loss_cp': None}
            if record['alternative_uci'] is not None:
                raise ValueError('failed_discovery_has_alternative')
            if any(item['status'] != 'not_run' or item['reason'] != 'earlier_stage'
                   for item in attempts[1:]):
                raise ValueError('failed_discovery_followup_mismatch')
        else:
            found = _check_success_attempt(discovery, prepared.board,
                                           nodes=contrast.NODE_BUDGETS[1], roots=[])
            discovery_ucis = [item['move_uci'] for item in found]
            alternative = next(move for move in discovery_ucis if move != selected)
            if record['alternative_uci'] != alternative:
                raise ValueError('discovery_alternative_mismatch')
            if any(item['score']['type'] != 'cp' or item['score']['bound'] != 'exact'
                   for item in found):
                expected_comparison = {'status': 'unresolved',
                                       'reason': 'discovery_mate_or_qualified_score',
                                       'delta_cp_by_budget': None, 'observed_loss_cp': None}
                if any(item['status'] != 'not_run' or
                       item['reason'] != 'discovery_mate_or_qualified_score'
                       for item in attempts[1:]):
                    raise ValueError('qualified_discovery_followup_mismatch')
            else:
                paired = []
                for index, nodes in enumerate(contrast.NODE_BUDGETS, 1):
                    attempt = attempts[index]
                    if attempt['status'] == 'not_run':
                        if index != 2 or attempts[1]['status'] != 'failed' or attempt['reason'] != 'earlier_stage':
                            raise ValueError('missing_paired_attempt')
                        break
                    roots = [selected, alternative]
                    if attempt['status'] == 'failed':
                        _check_failed_attempt(attempt, prepared.board,
                                              nodes=nodes, roots=roots)
                        if index == 1 and (attempts[2]['status'] != 'not_run' or
                                           attempts[2]['reason'] != 'earlier_stage'):
                            raise ValueError('failed_low_followup_mismatch')
                        break
                    paired.append(_check_success_attempt(attempt, prepared.board,
                                                         nodes=nodes, roots=roots))
                if len(paired) == 2:
                    expected_comparison = contrast._comparison(paired[0], paired[1],
                                                                selected, alternative)
                else:
                    failed = attempts[1] if attempts[1]['status'] == 'failed' else attempts[2]
                    expected_comparison = {'status': 'unresolved', 'reason': failed['reason'],
                                           'delta_cp_by_budget': None, 'observed_loss_cp': None}
    if comparison != expected_comparison:
        raise ValueError('evaluator_comparison_mismatch')
    failed_phase = any(item['status'] == 'failed' for item in attempts)
    if failed_phase and record['engine_cleanup'] not in {'closed', 'unavailable', 'failed'}:
        raise ValueError('evaluator_cleanup_mismatch')
    if not failed_phase and record['engine_cleanup'] != 'caller_owned':
        raise ValueError('evaluator_cleanup_mismatch')


def _write_new(path: Path, content: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(content)


def _default_engine_factory(path: str) -> object:
    return chess.engine.SimpleEngine.popen_uci(path)


def _close_engine(engine: object) -> str:
    closer = getattr(engine, 'quit', None) or getattr(engine, 'close', None)
    if closer is None:
        return 'unavailable'
    try:
        closer()
    except Exception:
        return 'failed'
    return 'closed'


def run(pgn_path: Path, engine_path: Path, selected_uci: str, output_dir: Path,
        *, pins: PracticePins = PINS,
        engine_factory: Callable[[str], object] = _default_engine_factory,
        evaluator: Callable[..., dict] = contrast.evaluate) -> dict:
    """Reserve create-only evidence before one engine launch and evaluation."""
    prepared = prepare(pgn_path, engine_path, selected_uci, pins=pins)
    source_sha256 = _digest(prepared.source_bytes)
    attempt = {'schema': ATTEMPT_SCHEMA, 'source_receipt_sha256': source_sha256,
               'pgn_sha256': pins.pgn_sha256, 'engine_sha256': pins.engine_sha256,
               'implementation_sha256': prepared.source['implementation_sha256'],
               'position_sha256': prepared.position_sha256,
               'selected_uci': selected_uci, 'status': 'reserved_before_engine_launch',
               'maximum_engine_launches': 1}
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_new(output_dir / 'source.json', prepared.source_bytes)
    _write_new(output_dir / 'attempt.json', _canonical(attempt))
    result = {'schema': SCHEMA, 'status': 'unresolved', 'reason': 'not_run',
              'source_receipt_sha256': source_sha256,
              'pgn_sha256': pins.pgn_sha256,
              'implementation_sha256': prepared.source['implementation_sha256'],
              'engine': prepared.engine_pin,
              'position_sha256': prepared.position_sha256,
              'selected_uci': selected_uci,
              'engine_launch_attempted': False, 'engine_cleanup': 'not_applicable',
              'model_calls': 0, 'browser_calls': 0,
              'failure_codes': [],
              'evaluation': None,
              'limitations': [
                  'Evaluator-only post-game observation; no generator, model, or Chess.com label is used.',
                  'The PGN result is a supplied declaration of completion.',
                  'FEN alone omits repetition history; this source receipt also pins a hash of the replayed prior moves.',
                  'A bounded score contrast does not explain Stockfish intent or establish teaching quality.',
                  'Source and engine file checks precede launch; an externally changed path remains a caller risk.',
              ]}
    engine = None
    try:
        result['engine_launch_attempted'] = True
        engine = engine_factory(prepared.engine_pin['path'])
    except Exception:
        result['reason'] = 'engine_launch_failed'
        result['failure_codes'].append('engine_launch_failed')
    else:
        try:
            observation = evaluator(
                prepared.board, selected_uci,
                source_receipt_sha256=source_sha256,
                expected_position_sha256=prepared.position_sha256,
                engine_sha256=prepared.engine_pin['sha256'], engine=engine)
            _check_evaluation(observation, prepared, source_sha256)
            result['evaluation'] = observation
            result['status'] = ('unresolved' if observation['comparison']['status'] == 'unresolved'
                                else 'observed')
            result['reason'] = observation['comparison']['reason']
        except Exception:
            result['reason'] = 'evaluator_failed_or_rejected'
            result['failure_codes'].append('evaluator_failed_or_rejected')
        finally:
            if isinstance(result['evaluation'], dict) and result['evaluation'].get('engine_cleanup') == 'closed':
                result['engine_cleanup'] = 'evaluator_closed'
            else:
                result['engine_cleanup'] = _close_engine(engine)
            if result['engine_cleanup'] in {'failed', 'unavailable'}:
                result['status'] = 'unresolved'
                result['reason'] = 'engine_cleanup_failed'
                result['failure_codes'].append('engine_cleanup_failed')
    _write_new(output_dir / 'result.json', _canonical(result))
    seal = {'schema': SEAL_SCHEMA,
            'source_sha256': _digest(prepared.source_bytes),
            'attempt_sha256': _digest(_canonical(attempt)),
            'result_sha256': _digest(_canonical(result))}
    _write_new(output_dir / 'seal.json', _canonical(seal))
    return result


def verify(pgn_path: Path, engine_path: Path, output_dir: Path,
           *, pins: PracticePins = PINS) -> dict:
    """Check source/binary pins and canonical local evidence without an engine."""
    source_raw = (output_dir / 'source.json').read_bytes()
    attempt_raw = (output_dir / 'attempt.json').read_bytes()
    result_raw = (output_dir / 'result.json').read_bytes()
    seal_raw = (output_dir / 'seal.json').read_bytes()
    source = json.loads(source_raw)
    attempt = json.loads(attempt_raw)
    result = json.loads(result_raw)
    seal = json.loads(seal_raw)
    if any(_canonical(value) != raw for value, raw in
           ((source, source_raw), (attempt, attempt_raw),
            (result, result_raw), (seal, seal_raw))):
        raise ValueError('noncanonical_evidence_bytes')
    if seal != {'schema': SEAL_SCHEMA,
                'source_sha256': _digest(source_raw),
                'attempt_sha256': _digest(attempt_raw),
                'result_sha256': _digest(result_raw)}:
        raise ValueError('local_evidence_seal_mismatch')
    if not isinstance(result, dict) or result.get('schema') != SCHEMA:
        raise ValueError('invalid_result_schema')
    selected_uci = result.get('selected_uci')
    prepared = prepare(pgn_path, engine_path, selected_uci, pins=pins)
    if source_raw != prepared.source_bytes:
        raise ValueError('source_receipt_mismatch')
    source_sha256 = _digest(source_raw)
    expected_attempt = {
        'schema': ATTEMPT_SCHEMA, 'source_receipt_sha256': source_sha256,
        'pgn_sha256': pins.pgn_sha256, 'engine_sha256': pins.engine_sha256,
        'implementation_sha256': prepared.source['implementation_sha256'],
        'position_sha256': prepared.position_sha256,
        'selected_uci': selected_uci, 'status': 'reserved_before_engine_launch',
        'maximum_engine_launches': 1}
    if attempt != expected_attempt:
        raise ValueError('attempt_reservation_mismatch')
    expected_result_pins = {
        'source_receipt_sha256': source_sha256,
        'pgn_sha256': pins.pgn_sha256, 'engine': prepared.engine_pin,
        'implementation_sha256': prepared.source['implementation_sha256'],
        'position_sha256': prepared.position_sha256,
        'selected_uci': selected_uci}
    if any(result.get(key) != value for key, value in expected_result_pins.items()):
        raise ValueError('result_pin_mismatch')
    if result.get('status') not in {'observed', 'unresolved'} or type(result.get('engine_launch_attempted')) is not bool:
        raise ValueError('invalid_result_status')
    if result.get('model_calls') != 0 or result.get('browser_calls') != 0:
        raise ValueError('invalid_external_call_count')
    if result['engine_launch_attempted'] is not True:
        raise ValueError('missing_reserved_launch_attempt')
    cleanup = result.get('engine_cleanup')
    if cleanup not in {'not_applicable', 'closed', 'failed', 'unavailable', 'evaluator_closed'}:
        raise ValueError('invalid_engine_cleanup')
    evaluation = result.get('evaluation')
    expected_failures = []
    if evaluation is not None:
        _check_evaluation(evaluation, prepared, source_sha256)
        if cleanup == 'not_applicable':
            raise ValueError('evaluation_without_cleanup')
        if cleanup in {'failed', 'unavailable'}:
            expected_status, expected_reason = 'unresolved', 'engine_cleanup_failed'
            expected_failures.append('engine_cleanup_failed')
        else:
            expected_status = ('unresolved' if evaluation['comparison']['status'] == 'unresolved'
                               else 'observed')
            expected_reason = evaluation['comparison']['reason']
    else:
        expected_status = 'unresolved'
        if cleanup == 'not_applicable':
            expected_reason = 'engine_launch_failed'
            expected_failures.append('engine_launch_failed')
        elif cleanup in {'failed', 'unavailable'}:
            expected_reason = 'engine_cleanup_failed'
            expected_failures.extend(('evaluator_failed_or_rejected', 'engine_cleanup_failed'))
        else:
            expected_reason = 'evaluator_failed_or_rejected'
            expected_failures.append('evaluator_failed_or_rejected')
    if result['status'] != expected_status or result.get('reason') != expected_reason:
        raise ValueError('result_state_mismatch')
    if result.get('failure_codes') != expected_failures:
        raise ValueError('failure_accounting_mismatch')
    return {'schema': SCHEMA, 'status': 'verified_local_evidence',
            'run_status': result['status'], 'reason': result['reason'],
            'comparison_status': evaluation['comparison']['status'] if evaluation else 'unresolved',
            'pgn_sha256': pins.pgn_sha256,
            'source_receipt_sha256': source_sha256,
            'engine_sha256': pins.engine_sha256,
            'result_sha256': _digest(result_raw),
            'engine_calls': 0, 'model_calls': 0,
            'limits': 'Verifier checks pins and structure; engine observations are not regenerated.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'verify'):
        command = sub.add_parser(name)
        command.add_argument('--pgn', type=Path, default=DEFAULT_PGN)
        command.add_argument('--engine', type=Path, default=DEFAULT_ENGINE)
        command.add_argument('--output-dir', type=Path, required=True)
        if name == 'run':
            command.add_argument('--selected-uci', required=True)
    args = parser.parse_args(argv)
    if args.command == 'run':
        record = run(args.pgn, args.engine, args.selected_uci, args.output_dir)
        response = {'schema': SCHEMA, 'status': record['status'],
                    'reason': record['reason'], 'output_dir': str(args.output_dir),
                    'model_calls': 0}
    else:
        response = verify(args.pgn, args.engine, args.output_dir)
    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
