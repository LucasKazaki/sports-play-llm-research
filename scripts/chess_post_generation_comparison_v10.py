#!/usr/bin/env python3
"""Private, post-generation paired Stockfish comparison for four practice plies.

The v9 generator never imports this sidecar. Its output is evaluator evidence,
not a claim about why Stockfish chose a move or about teaching quality.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import chess
import chess.engine

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_capture_v9 as capture
import chess_no_forward_teaching_v8 as teaching_v8
import chess_review_completed_game as previous
import chess_user_game_no_forward_v1 as user_packet

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SCHEMA = 'chess-post-generation-comparison-protocol/v10'
INPUT_SCHEMA = 'chess-post-generation-comparison-input/v10'
RECEIPT_SCHEMA = 'chess-post-generation-comparison-receipt/v10'
ENGINE_NAME = 'Stockfish 19'
NODES = 100_000
THREADS = 1
HASH_MB = 16
ELIGIBLE = frozenset({'queen_escape', 'rook_coordination'})
UPSTREAM = {'plan': capture.PLAN_FILE, 'manifest': capture.MANIFEST_FILE,
            'request': capture.REQUEST_FILE, 'raw_response': capture.RAW_FILE,
            'result': capture.RESULT_FILE,
            'evaluation': capture.EVALUATION_FILE}
PROTOCOL_FIELDS = ('schema', 'engine_name', 'engine_binary_sha256', 'threads',
                   'hash_mb', 'requested_nodes', 'searches', 'multipv',
                   'root_policy', 'automatic_retries', 'evaluator_source_sha256',
                   'dependency_closure_sha256')
INPUT_FIELDS = ('schema', 'v9_run_dir', 'ply', 'protocol_sha256',
                'upstream_sha256')
OBSERVATION_FIELDS = ('move_uci', 'san', 'score', 'depth', 'nodes_observed',
                      'pv_uci')
SCORE_FIELDS = ('type', 'value', 'bound', 'order', 'perspective', 'side_to_move')


class PairValidationError(ValueError):
    """One search returned evidence that cannot support a ranking."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _canonical_line(value: dict) -> bytes:
    return cf.canonical(value) + b'\n'


def _artifact_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    artifacts = (ROOT / 'artifacts').resolve()
    if resolved == artifacts or not resolved.is_relative_to(artifacts):
        raise ValueError('v10_cli_path_outside_project_artifacts')
    return resolved


def _read_metadata(path: Path) -> bytes:
    with _artifact_path(path).open('rb') as stream:
        raw = stream.read(capture.MAX_METADATA_BYTES + 1)
    if len(raw) > capture.MAX_METADATA_BYTES:
        raise ValueError('v10_cli_metadata_too_large')
    return raw


def _strict(raw: bytes, fields: tuple[str, ...], schema: str) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= capture.MAX_METADATA_BYTES:
        raise ValueError('v10_invalid_metadata_bytes')
    try:
        value = capture.capture_v7._strict_response_json(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError('v10_invalid_metadata_json') from error
    cf.exact_keys(value, fields, 'v10_invalid_metadata_shape')
    if value['schema'] != schema or raw != _canonical_line(value):
        raise ValueError('v10_noncanonical_or_wrong_schema')
    return value


def _sha(value: object) -> bool:
    return (type(value) is str and len(value) == 64 and
            all(char in '0123456789abcdef' for char in value))


def implementation_hashes() -> dict:
    """Pin v10 and the 23-module v9 source closure before any search."""
    return {'chess_post_generation_comparison_v10.py': cf.file_digest(Path(__file__)),
            **capture._implementation_hashes()}


def freeze_protocol() -> bytes:
    closure = capture._implementation_hashes()
    protocol = {
        'schema': PROTOCOL_SCHEMA, 'engine_name': ENGINE_NAME,
        'engine_binary_sha256': previous.ENGINE_SHA256,
        'threads': THREADS, 'hash_mb': HASH_MB, 'requested_nodes': NODES,
        'searches': 1, 'multipv': 2,
        'root_policy': 'played_plus_verified_model_alternative',
        'automatic_retries': 0,
        'evaluator_source_sha256': cf.file_digest(Path(__file__)),
        'dependency_closure_sha256': cf.digest(cf.canonical(closure)),
    }
    return _canonical_line(protocol)


def _protocol(raw: bytes) -> dict:
    value = _strict(raw, PROTOCOL_FIELDS, PROTOCOL_SCHEMA)
    if raw != freeze_protocol():
        raise ValueError('v10_protocol_or_implementation_changed')
    return value


def _input(raw: bytes, protocol_raw: bytes) -> tuple[dict, Path]:
    value = _strict(raw, INPUT_FIELDS, INPUT_SCHEMA)
    cf.exact_keys(value['upstream_sha256'], UPSTREAM,
                  'v10_invalid_upstream_hash_shape')
    if (type(value['ply']) is not int or value['ply'] not in capture.CASE_PINS or
            not _sha(value['protocol_sha256']) or
            value['protocol_sha256'] != cf.digest(protocol_raw) or
            any(not _sha(item) for item in value['upstream_sha256'].values()) or
            type(value['v9_run_dir']) is not str or not value['v9_run_dir']):
        raise ValueError('v10_invalid_input_binding')
    if not Path(value['v9_run_dir']).is_absolute():
        raise ValueError('v10_run_dir_must_be_absolute')
    run_dir = Path(value['v9_run_dir']).resolve()
    artifacts = (ROOT / 'artifacts').resolve()
    if not run_dir.is_relative_to(artifacts) or run_dir == artifacts:
        raise ValueError('v10_run_outside_project_artifacts')
    return value, run_dir


def _upstream(input_value: dict, run_dir: Path) -> tuple[dict, dict, dict]:
    ply = input_value['ply']
    case_dir = run_dir / f'ply{ply}'
    artifacts = (ROOT / 'artifacts').resolve()
    for name, filename in UPSTREAM.items():
        path = (run_dir if name == 'plan' else case_dir) / filename
        if not path.resolve().is_relative_to(artifacts):
            raise ValueError('v10_upstream_outside_project_artifacts')
        if cf.file_digest(path) != input_value['upstream_sha256'][name]:
            raise ValueError(f'v10_{name}_sha256_changed')
    # This rechecks the whole four-case denominator, source PGN/review, route,
    # every frozen request, raw response and v9 checker evaluation.
    verified = capture.verify_run(run_dir)
    plan, cases = capture._preflight(run_dir)
    row = next(item for item in verified['rows'] if item['ply'] == ply)
    if (row['status'] != 'captured' or row['model_identity'] != 'matched' or
            row['evaluation'] is None):
        raise ValueError('v10_v9_result_not_verified_and_evaluated')
    case = cases[ply]
    packet_raw = case['packet']
    packet = capture.capture_v7._strict_response_json(packet_raw)
    user_packet._shape(packet)
    if (packet_raw != cf.canonical(packet) or
            cf.digest(packet_raw) != case['manifest']['source_packet_sha256'] or
            packet['source']['selected_ply'] != ply or
            packet['fen'] != teaching_v8.CASES[ply][1] or
            packet['selected_move']['uci'] != teaching_v8.CASES[ply][2] or
            row['case_kind'] != teaching_v8.CASES[ply][0]):
        raise ValueError('v10_source_packet_binding_changed')
    checker = row['evaluation']['checker']
    if (checker['packet_sha256'] != cf.digest(packet_raw) or
            checker['source_binding_sha256'] !=
            cf.digest(cf.canonical(case['manifest']['source_binding'])) or
            checker['case_kind'] != row['case_kind'] or
            checker['decision'] not in
            ('verified_typed_board_claim', 'model_abstention', 'rejected')):
        raise ValueError('v10_checker_binding_changed')
    return plan, row, packet


def freeze_input(run_dir: Path, ply: int, protocol_raw: bytes) -> bytes:
    """After a sealed v9 evaluation, form exact input pins without a search."""
    _protocol(protocol_raw)
    if type(ply) is not int or ply not in capture.CASE_PINS:
        raise ValueError('v10_invalid_ply')
    run_dir = _artifact_path(run_dir)
    case_dir = run_dir / f'ply{ply}'
    artifacts = (ROOT / 'artifacts').resolve()
    hashes = {}
    for name, filename in UPSTREAM.items():
        path = (run_dir if name == 'plan' else case_dir) / filename
        if not path.resolve().is_relative_to(artifacts):
            raise ValueError('v10_upstream_outside_project_artifacts')
        hashes[name] = cf.file_digest(path)
    value = {'schema': INPUT_SCHEMA, 'v9_run_dir': str(run_dir), 'ply': ply,
             'protocol_sha256': cf.digest(protocol_raw),
             'upstream_sha256': hashes}
    raw = _canonical_line(value)
    _upstream(value, run_dir)
    return raw


def _search_pair(board: chess.Board, roots: tuple[chess.Move, chess.Move],
                 protocol: dict) -> list[dict]:
    """Exactly one root-restricted search; no discovery or adaptive retry."""
    previous.engine_ready()
    engine = chess.engine.SimpleEngine.popen_uci(previous.ENGINE)
    try:
        if engine.id.get('name') != protocol['engine_name']:
            raise ValueError('v10_engine_name_mismatch')
        engine.configure({'Threads': protocol['threads'],
                          'Hash': protocol['hash_mb']})
        infos = engine.analyse(
            board, chess.engine.Limit(nodes=protocol['requested_nodes']),
            root_moves=list(roots), multipv=protocol['multipv'])
        if type(infos) is not list:
            raise PairValidationError('missing_or_duplicate_root')
        try:
            return [previous.observation(board, info) for info in infos]
        except ValueError as error:
            reason = ('invalid_pv' if 'pv' in str(error) or 'root' in str(error)
                      else 'invalid_search_observation')
            raise PairValidationError(reason) from error
    finally:
        engine.quit()


def _validate_pair(board: chess.Board, roots: tuple[chess.Move, chess.Move],
                   observations: object) -> tuple[list[dict], dict]:
    root_uci = [move.uci() for move in roots]
    if (type(observations) is not list or len(observations) != 2 or
            any(type(item) is not dict for item in observations)):
        raise PairValidationError('missing_or_duplicate_root')
    names = [item.get('move_uci') for item in observations]
    if any(type(name) is not str for name in names) or sorted(names) != sorted(root_uci):
        raise PairValidationError('missing_or_duplicate_root')
    by_root = {}
    for item in observations:
        try:
            cf.exact_keys(item, OBSERVATION_FIELDS, 'v10_invalid_observation_shape')
            score = item['score']
            cf.exact_keys(score, SCORE_FIELDS, 'v10_invalid_score_shape')
        except (ValueError, TypeError) as error:
            raise PairValidationError('invalid_search_observation') from error
        try:
            move = chess.Move.from_uci(item['move_uci'])
        except ValueError as error:
            raise PairValidationError('invalid_search_observation') from error
        if (item['san'] != board.san(move) or type(item['depth']) is not int or
                item['depth'] <= 0 or type(item['nodes_observed']) is not int or
                item['nodes_observed'] <= 0):
            raise PairValidationError('invalid_search_observation')
        pv = item['pv_uci']
        if type(pv) is not list or not 1 <= len(pv) <= 128 or pv[0] != move.uci():
            raise PairValidationError('invalid_pv')
        replay = board.copy(stack=False)
        try:
            for uci in pv:
                reply = chess.Move.from_uci(uci)
                if reply not in replay.legal_moves:
                    raise ValueError('illegal_pv_move')
                replay.push(reply)
        except (TypeError, ValueError) as error:
            raise PairValidationError('invalid_pv') from error
        if (score['type'] not in ('cp', 'mate') or
                type(score['value']) is not int or
                score['bound'] not in ('exact', 'lower', 'upper') or
                score['order'] != 'engine_score' or
                score['perspective'] != 'side_to_move'):
            raise PairValidationError('invalid_search_observation')
        if score['side_to_move'] != chess.COLOR_NAMES[board.turn]:
            raise PairValidationError('perspective_mismatch')
        by_root[item['move_uci']] = item
    return observations, by_root


def _abstain(reason: str) -> dict:
    return {'status': 'abstain', 'reason': reason, 'relation': None,
            'delta_cp': None, 'display_sentence': None}


def evaluate(input_raw: bytes, protocol_raw: bytes, *, pair_search=None) -> dict:
    """Verify sealed v9 evidence, then optionally compare one witnessed pair."""
    protocol = _protocol(protocol_raw)
    input_value, run_dir = _input(input_raw, protocol_raw)
    plan, row, packet = _upstream(input_value, run_dir)
    ply = input_value['ply']
    checker = row['evaluation']['checker']
    decision = checker['decision']
    witness = checker['witness']
    source = {
        'pgn_sha256': packet['source']['pgn_sha256'],
        'source_packet_sha256': checker['packet_sha256'],
        'source_binding_sha256': checker['source_binding_sha256'],
        'ply': ply, 'fen_before': packet['fen'],
        'side_to_move': packet['side_to_move'],
        'selected_uci': packet['selected_move']['uci'],
        'alternative_uci': None,
    }
    receipt = {
        'schema': RECEIPT_SCHEMA, 'input_sha256': cf.digest(input_raw),
        'protocol_sha256': cf.digest(protocol_raw),
        'implementation_sha256': implementation_hashes(),
        'source': source,
        'upstream': {
            **{f'{name}_sha256': digest
               for name, digest in input_value['upstream_sha256'].items()},
            'witness_sha256': (cf.digest(cf.canonical(witness))
                               if witness is not None else None),
            'model_id': plan['route']['model_id'],
            'checker_decision': decision,
        },
        'engine': None, 'engine_error': None,
        'comparison': _abstain('no_model_named_alternative'),
        'counts': {'model_calls_v10': 0, 'engine_calls_v10': 0,
                   'automatic_retries': 0},
        'development_case': True, 'quality_evaluated': False,
        'commentary_capability_gate_passed': False,
    }
    if decision != 'verified_typed_board_claim':
        receipt['comparison'] = _abstain(
            'model_abstained' if decision == 'model_abstention' else 'claim_rejected')
        return receipt
    if row['case_kind'] not in ELIGIBLE:
        return receipt
    if type(witness) is not dict or type(witness.get('alternative_uci')) is not str:
        raise ValueError('v10_accepted_witness_missing_alternative')
    board = chess.Board(packet['fen'])
    selected = chess.Move.from_uci(source['selected_uci'])
    try:
        alternative = chess.Move.from_uci(witness['alternative_uci'])
    except ValueError as error:
        raise ValueError('v10_accepted_alternative_invalid_uci') from error
    if (not board.is_valid() or selected not in board.legal_moves or
            alternative not in board.legal_moves or selected == alternative or
            board.san(selected) != packet['selected_move']['san'] or
            packet['side_to_move'] != chess.COLOR_NAMES[board.turn]):
        raise ValueError('v10_accepted_alternative_not_legal_or_distinct')
    source['alternative_uci'] = alternative.uci()
    roots = (selected, alternative)
    receipt['counts']['engine_calls_v10'] = 1
    try:
        observations = (pair_search or _search_pair)(board, roots, protocol)
        observations, by_root = _validate_pair(board, roots, observations)
    except PairValidationError as error:
        receipt['engine_error'] = {
            'stage': 'validate', 'type': type(error).__name__,
            'message': str(error)[:160]}
        receipt['comparison'] = _abstain(error.reason)
        return receipt
    except Exception as error:
        receipt['engine_error'] = {
            'stage': 'search', 'type': type(error).__name__,
            'message': str(error)[:160]}
        receipt['comparison'] = _abstain('engine_failure')
        return receipt
    receipt['engine'] = {
        'name': ENGINE_NAME, 'binary_sha256': protocol['engine_binary_sha256'],
        'settings': {
            'threads': THREADS, 'hash_mb': HASH_MB, 'requested_nodes': NODES,
            'searches': 1, 'multipv': 2,
            'root_moves_uci': [selected.uci(), alternative.uci()],
        },
        'paired_observations': observations,
    }
    played = by_root[selected.uci()]['score']
    other = by_root[alternative.uci()]['score']
    if (played['type'] != 'cp' or other['type'] != 'cp' or
            played['bound'] != 'exact' or other['bound'] != 'exact'):
        receipt['comparison'] = _abstain('mate_or_bounded_score')
        return receipt
    delta = other['value'] - played['value']
    relation = ('alternative_higher' if delta > 0 else
                'played_higher' if delta < 0 else 'equal')
    subject = {'alternative_higher': 'the named alternative scored higher',
               'played_higher': 'the played move scored higher',
               'equal': 'the moves had equal scores'}[relation]
    sentence = (f'In this bounded {NODES:,}-node Stockfish search, '
                f'{subject} by {abs(delta)} centipawns.' if delta else
                f'In this bounded {NODES:,}-node Stockfish search, '
                'the two moves had equal centipawn scores.')
    receipt['comparison'] = {
        'status': 'ranked', 'reason': None, 'relation': relation,
        'delta_cp': delta, 'display_sentence': sentence,
    }
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze-protocol')
    freeze.add_argument('--output', type=Path, required=True)
    frozen_input = commands.add_parser('freeze-input')
    frozen_input.add_argument('--run-dir', type=Path, required=True)
    frozen_input.add_argument('--ply', type=int, required=True)
    frozen_input.add_argument('--protocol', type=Path, required=True)
    frozen_input.add_argument('--output', type=Path, required=True)
    compare = commands.add_parser('compare')
    compare.add_argument('--protocol', type=Path, required=True)
    compare.add_argument('--input', type=Path, required=True)
    compare.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = _artifact_path(args.output)
    if args.command == 'freeze-protocol':
        raw = freeze_protocol()
    elif args.command == 'freeze-input':
        raw = freeze_input(args.run_dir, args.ply,
                           _read_metadata(args.protocol))
    else:
        raw = _canonical_line(evaluate(_read_metadata(args.input),
                                       _read_metadata(args.protocol)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    print(cf.digest(raw))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
