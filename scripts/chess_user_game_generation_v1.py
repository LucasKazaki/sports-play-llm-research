#!/usr/bin/env python3
"""Freeze and retain one local typed-response probe for a completed chess game.

Capture requires a frozen run and explicit CLI pins. Coordinate use of the
shared local-model lane. A saved request spends its sole attempt, including after a timeout or
process interruption. Raw output is evidence, never an accepted explanation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import chess_counterfactual_evidence as cf
import chess_local_route_attestation as route_capture
import chess_no_forward_generation_runner as old_runner
import chess_no_forward_typed_transport_v2 as typed_transport
import chess_user_game_no_forward_v1 as user_packet


SCHEMA = 'chess-user-game-generation/v1'
RESULT_SCHEMA = 'chess-user-game-generation-result/v1'
PACKET_FILE = 'packet.json'
REQUEST_FILE = 'request.json'
RESULT_FILE = 'result.json'
RAW_FILE = 'raw-response.bin'
MANIFEST_FILE = 'manifest.json'
ROUTE_DIR = 'route'
ATTESTATION_FILES = (
    route_capture.RECEIPT_NAME,
    route_capture.OBSERVED_ROUTE_NAME,
    route_capture.ATTESTATION_NAME,
    route_capture.SNAPSHOT_NAME,
)
MANIFEST_FIELDS = (
    'schema', 'run_state', 'requested', 'model_calls', 'automatic_retries',
    'heldout_outcomes_scored', 'commentary_capability_gate_passed',
    'pgn_path', 'review_dir', 'packet_path', 'declared_route_path',
    'pgn_sha256', 'review_sha256', 'page_sha256', 'role', 'packet_sha256',
    'declared_route_sha256', 'route', 'route_evidence_sha256',
    'prompt_sha256', 'typed_transport_source_sha256',
    'packet_builder_source_sha256', 'runner_source_sha256',
    'helper_sources_sha256', 'request_sha256',
)
RESULT_FIELDS = (
    'schema', 'manifest_sha256', 'request_sha256', 'packet_sha256',
    'status', 'attempt_count', 'model_calls', 'automatic_retries',
    'input_dispatched', 'latency_ns', 'http_status', 'raw_path',
    'raw_sha256', 'raw_bytes', 'raw_classification', 'observed_model_id',
    'model_identity', 'error', 'heldout_outcomes_scored',
    'commentary_capability_gate_passed',
)
MAX_METADATA_BYTES = 512 * 1024
MAX_RAW_BYTES = old_runner.MAX_RAW_BYTES
HELPER_MODULES = {
    'chess_no_forward_generation_runner.py': old_runner,
    'chess_local_route_attestation.py': route_capture,
    'chess_counterfactual_evidence.py': cf,
    'chess_no_forward_packet.py': user_packet.no_forward,
    'chess_paired_review_v3.py': user_packet.paired,
    'chess_review_completed_game.py': user_packet.previous,
    'chess_real_evidence_interface.py': user_packet.paired.ui,
}


def _read(path: Path, maximum: int, message: str) -> bytes:
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(message)
    return raw


def _json(path: Path, maximum: int = MAX_METADATA_BYTES) -> dict:
    raw = _read(path, maximum, 'user_game_generation_metadata_too_large')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_user_game_generation_json') from error
    if not isinstance(value, dict):
        raise ValueError('user_game_generation_json_not_object')
    return value


def _write(path: Path, raw: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def _write_json(path: Path, value: dict) -> None:
    raw = cf.canonical(value) + b'\n'
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError('user_game_generation_metadata_too_large')
    _write(path, raw)


def _source_sha256(path: Path) -> str:
    """Hash source without relying on an imported helper being checked."""
    digest = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_hashes() -> dict:
    return {
        'prompt_sha256': sha256(typed_transport.PROMPT.encode('utf-8')).hexdigest(),
        'typed_transport_source_sha256': _source_sha256(Path(typed_transport.__file__)),
        'packet_builder_source_sha256': _source_sha256(Path(user_packet.__file__)),
        'runner_source_sha256': _source_sha256(Path(__file__)),
        'helper_sources_sha256': {name: _source_sha256(Path(module.__file__))
                                  for name, module in HELPER_MODULES.items()},
    }


def build_request(packet_bytes: bytes, route: dict) -> bytes:
    """Use the fixed typed prompt with exactly one source-bound user packet."""
    old_runner._validate_route(route)
    if type(packet_bytes) is not bytes or not 0 < len(packet_bytes) <= user_packet.MAX_PACKET_BYTES:
        raise ValueError('invalid_user_game_generation_packet_bytes')
    try:
        packet = json.loads(packet_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_user_game_generation_packet_json') from error
    user_packet._shape(packet)
    if packet_bytes != cf.canonical(packet):
        raise ValueError('user_game_generation_packet_not_canonical')
    request = {
        'model': route['model_id'],
        'messages': [
            {'role': 'system', 'content': typed_transport.PROMPT},
            {'role': 'user', 'content': packet_bytes.decode('utf-8')},
        ],
        'stream': False,
        'temperature': route['sampling']['temperature'],
        'top_p': route['sampling']['top_p'],
        'max_tokens': route['sampling']['max_output_tokens'],
        'seed': route['seed'],
        'reasoning_effort': route['reasoning']['effort'],
    }
    return cf.canonical(request)


def _source_packet(pgn_path: Path, review_dir: Path, pgn_sha256: str,
                   review_sha256: str, page_sha256: str, role: str,
                   packet_path: Path) -> bytes:
    raw = _read(packet_path, user_packet.MAX_PACKET_BYTES,
                'user_game_generation_packet_too_large')
    try:
        packet = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_user_game_generation_packet_json') from error
    canonical = user_packet.encode_packet(
        pgn_path, review_dir, pgn_sha256, review_sha256, page_sha256,
        role=role, packet=packet,
    )
    if raw != canonical:
        raise ValueError('user_game_generation_packet_file_not_canonical')
    return raw


def _declared_route(path: Path) -> tuple[bytes, dict]:
    raw = _read(path, MAX_METADATA_BYTES, 'user_game_generation_route_too_large')
    try:
        route = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_user_game_generation_route_json') from error
    old_runner._validate_route(route)
    return raw, route


def _route_files(directory: Path) -> dict[str, bytes]:
    return {name: _read(Path(directory) / name, MAX_METADATA_BYTES,
                        'user_game_generation_route_evidence_too_large')
            for name in ATTESTATION_FILES}


def _manifest_shape(manifest: dict) -> None:
    cf.exact_keys(manifest, MANIFEST_FIELDS, 'invalid_user_game_generation_manifest_shape')
    if (manifest['schema'] != SCHEMA or manifest['run_state'] != 'frozen' or
            type(manifest['requested']) is not int or manifest['requested'] != 1 or
            type(manifest['model_calls']) is not int or manifest['model_calls'] != 0 or
            type(manifest['automatic_retries']) is not int or
            manifest['automatic_retries'] != 0 or
            type(manifest['heldout_outcomes_scored']) is not int or
            manifest['heldout_outcomes_scored'] != 0 or
            manifest['commentary_capability_gate_passed'] is not False or
            manifest['role'] not in user_packet.ROLES):
        raise ValueError('invalid_user_game_generation_manifest_boundary')
    old_runner._validate_route(manifest['route'])
    cf.exact_keys(manifest['route_evidence_sha256'], ATTESTATION_FILES,
                  'invalid_user_game_generation_route_hashes')
    cf.exact_keys(manifest['helper_sources_sha256'], HELPER_MODULES,
                  'invalid_user_game_generation_helper_hashes')


def freeze_run(pgn_path: Path, review_dir: Path, pgn_sha256: str,
               review_sha256: str, page_sha256: str, role: str,
               packet_path: Path, declared_route_path: Path,
               attestation_dir: Path, run_dir: Path) -> dict:
    """Freeze all source, prompt, route and GET evidence before any POST exists."""
    pgn_path, review_dir = Path(pgn_path).resolve(), Path(review_dir).resolve()
    packet_path = Path(packet_path).resolve()
    declared_route_path = Path(declared_route_path).resolve()
    attestation_dir, run_dir = Path(attestation_dir).resolve(), Path(run_dir).resolve()
    if run_dir.exists():
        raise FileExistsError(run_dir)
    packet_raw = _source_packet(pgn_path, review_dir, pgn_sha256, review_sha256,
                                page_sha256, role, packet_path)
    route_raw, route = _declared_route(declared_route_path)
    attested = route_capture.verify_capture(declared_route_path, attestation_dir)
    if attested['verified'] is not True:
        raise ValueError('user_game_generation_route_not_attested')
    route_files = _route_files(attestation_dir)
    request_raw = build_request(packet_raw, route)
    manifest = {
        'schema': SCHEMA, 'run_state': 'frozen', 'requested': 1,
        'model_calls': 0, 'automatic_retries': 0,
        'heldout_outcomes_scored': 0,
        'commentary_capability_gate_passed': False,
        'pgn_path': str(pgn_path), 'review_dir': str(review_dir),
        'packet_path': str(packet_path),
        'declared_route_path': str(declared_route_path),
        'pgn_sha256': pgn_sha256, 'review_sha256': review_sha256,
        'page_sha256': page_sha256, 'role': role,
        'packet_sha256': cf.digest(packet_raw),
        'declared_route_sha256': cf.digest(route_raw), 'route': route,
        'route_evidence_sha256': {name: cf.digest(raw)
                                  for name, raw in route_files.items()},
        **_implementation_hashes(),
        'request_sha256': cf.digest(request_raw),
    }
    _manifest_shape(manifest)
    run_dir.mkdir(parents=True, exist_ok=False)
    _write(run_dir / PACKET_FILE, packet_raw)
    for name, raw in route_files.items():
        _write(run_dir / ROUTE_DIR / name, raw)
    _write_json(run_dir / MANIFEST_FILE, manifest)
    return manifest


def _preflight(run_dir: Path) -> tuple[dict, bytes, bytes]:
    run_dir = Path(run_dir).resolve()
    manifest = _json(run_dir / MANIFEST_FILE)
    if any(manifest.get(name) != value for name, value in _implementation_hashes().items()):
        raise ValueError('user_game_generation_implementation_changed_since_freeze')
    _manifest_shape(manifest)
    route_raw, route = _declared_route(Path(manifest['declared_route_path']))
    if (cf.digest(route_raw) != manifest['declared_route_sha256'] or
            cf.canonical(route) != cf.canonical(manifest['route'])):
        raise ValueError('user_game_generation_declared_route_changed')
    route_dir = run_dir / ROUTE_DIR
    files = _route_files(route_dir)
    if {name: cf.digest(raw) for name, raw in files.items()} != manifest['route_evidence_sha256']:
        raise ValueError('user_game_generation_route_evidence_changed')
    if route_capture.verify_capture(Path(manifest['declared_route_path']), route_dir)['verified'] is not True:
        raise ValueError('user_game_generation_route_attestation_changed')
    source = (Path(manifest['pgn_path']), Path(manifest['review_dir']),
              manifest['pgn_sha256'], manifest['review_sha256'],
              manifest['page_sha256'], manifest['role'])
    original = _source_packet(*source, Path(manifest['packet_path']))
    frozen = _read(run_dir / PACKET_FILE, user_packet.MAX_PACKET_BYTES,
                   'user_game_generation_frozen_packet_too_large')
    if original != frozen or cf.digest(frozen) != manifest['packet_sha256']:
        raise ValueError('user_game_generation_frozen_packet_changed')
    request = build_request(frozen, route)
    if cf.digest(request) != manifest['request_sha256']:
        raise ValueError('user_game_generation_request_changed_since_freeze')
    return manifest, frozen, request


def _error(error: Exception) -> dict:
    return {'type': type(error).__name__, 'message': str(error)[:512]}


def _observed_model(raw: bytes) -> str | None:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value.get('model') if isinstance(value, dict) and type(value.get('model')) is str else None


def capture_frozen_run(run_dir: Path, *, opener=None) -> dict:
    """Write request before one loopback POST; preserve failure without retry."""
    run_dir = Path(run_dir).resolve()
    if (run_dir / REQUEST_FILE).exists() or (run_dir / RESULT_FILE).exists():
        raise ValueError('user_game_generation_already_attempted')
    manifest, _, request_raw = _preflight(run_dir)
    if opener is None:
        opener = build_opener(ProxyHandler({}), old_runner._NoRedirect())
    if not callable(getattr(opener, 'open', None)):
        raise ValueError('user_game_generation_invalid_opener_before_post')
    request = Request(manifest['route']['endpoint'] + '/chat/completions',
                      data=request_raw, headers={'Content-Type': 'application/json'},
                      method='POST')
    _write(run_dir / REQUEST_FILE, request_raw)
    started = time.perf_counter_ns()
    status = 'transport_failure'
    http_status = None
    raw_path = raw_sha256 = observed_model_id = None
    raw_bytes = 0
    raw_classification = 'transport_failure'
    model_identity = 'unverified'
    error_record = None
    try:
        try:
            response = opener.open(request, timeout=manifest['route']['timeout_seconds'])
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_RAW_BYTES + 1)
            http_status = int(getattr(response, 'status', getattr(response, 'code', 0)) or 0)
        _write(run_dir / RAW_FILE, raw)
        raw_path, raw_sha256, raw_bytes = RAW_FILE, cf.digest(raw), len(raw)
        if len(raw) > MAX_RAW_BYTES:
            status = raw_classification = 'response_too_large'
            error_record = {'type': 'ResponseTooLarge',
                            'message': 'retained_first_max_raw_bytes_plus_one'}
        else:
            raw_classification = old_runner._classify_raw(raw)
            observed_model_id = _observed_model(raw)
            model_identity = ('matched' if observed_model_id == manifest['route']['model_id']
                              else 'mismatch' if observed_model_id is not None else 'unverified')
            if not 200 <= http_status < 300:
                status = 'http_error'
            elif model_identity == 'mismatch':
                status = 'identity_mismatch'
            elif model_identity == 'unverified':
                status = 'identity_unverified'
            else:
                status = 'captured'
    except Exception as error:
        error_record = _error(error)
    result = {
        'schema': RESULT_SCHEMA,
        'manifest_sha256': cf.file_digest(run_dir / MANIFEST_FILE),
        'request_sha256': cf.digest(request_raw),
        'packet_sha256': manifest['packet_sha256'],
        'status': status, 'attempt_count': 1, 'model_calls': 1,
        'automatic_retries': 0, 'input_dispatched': True,
        'latency_ns': time.perf_counter_ns() - started,
        'http_status': http_status, 'raw_path': raw_path,
        'raw_sha256': raw_sha256, 'raw_bytes': raw_bytes,
        'raw_classification': raw_classification,
        'observed_model_id': observed_model_id,
        'model_identity': model_identity,
        'error': error_record, 'heldout_outcomes_scored': 0,
        'commentary_capability_gate_passed': False,
    }
    _write_json(run_dir / RESULT_FILE, result)
    return result


def verify_run(run_dir: Path) -> dict:
    """Offline integrity check; a request without a result is spent/incomplete."""
    run_dir = Path(run_dir).resolve()
    manifest, _, expected_request = _preflight(run_dir)
    request_path, result_path = run_dir / REQUEST_FILE, run_dir / RESULT_FILE
    if not request_path.exists():
        if result_path.exists():
            raise ValueError('user_game_generation_result_without_request')
        if (run_dir / RAW_FILE).exists():
            raise ValueError('user_game_generation_raw_without_request')
        return {'schema': SCHEMA, 'integrity_passed': True, 'status': 'frozen',
                'requested': 1, 'attempts_consumed': 0, 'model_calls': 0,
                'commentary_capability_gate_passed': False}
    retained_request = _read(request_path, MAX_METADATA_BYTES,
                             'user_game_generation_request_too_large')
    if retained_request != expected_request:
        raise ValueError('user_game_generation_request_changed')
    if not result_path.exists():
        return {'schema': SCHEMA, 'integrity_passed': False, 'status': 'interrupted',
                'requested': 1, 'attempts_consumed': 1, 'model_calls_upper_bound': 1,
                'commentary_capability_gate_passed': False}
    result = _json(result_path)
    cf.exact_keys(result, RESULT_FIELDS, 'invalid_user_game_generation_result_shape')
    if (result['schema'] != RESULT_SCHEMA or
            result['manifest_sha256'] != cf.file_digest(run_dir / MANIFEST_FILE) or
            result['request_sha256'] != cf.digest(expected_request) or
            result['packet_sha256'] != manifest['packet_sha256'] or
            result['attempt_count'] != 1 or result['model_calls'] != 1 or
            result['automatic_retries'] != 0 or result['input_dispatched'] is not True or
            result['heldout_outcomes_scored'] != 0 or
            result['commentary_capability_gate_passed'] is not False or
            type(result['latency_ns']) is not int or result['latency_ns'] < 0):
        raise ValueError('user_game_generation_result_binding_changed')
    if result['status'] not in ('captured', 'http_error', 'identity_mismatch',
                                'identity_unverified', 'response_too_large',
                                'transport_failure'):
        raise ValueError('invalid_user_game_generation_result_status')
    if result['raw_path'] is None:
        if (result['raw_sha256'] is not None or result['raw_bytes'] != 0 or
                (run_dir / RAW_FILE).exists() or result['status'] != 'transport_failure' or
                result['error'] is None or result['raw_classification'] != 'transport_failure' or
                result['http_status'] is not None or
                result['observed_model_id'] is not None or
                result['model_identity'] != 'unverified'):
            raise ValueError('user_game_generation_missing_raw_inconsistent')
    else:
        if result['raw_path'] != RAW_FILE:
            raise ValueError('invalid_user_game_generation_raw_path')
        raw = _read(run_dir / RAW_FILE, MAX_RAW_BYTES + 1,
                    'user_game_generation_raw_too_large')
        if (result['raw_sha256'] != cf.digest(raw) or result['raw_bytes'] != len(raw) or
                result['raw_classification'] != ('response_too_large' if len(raw) > MAX_RAW_BYTES
                                                 else old_runner._classify_raw(raw))):
            raise ValueError('user_game_generation_raw_response_changed')
        if len(raw) > MAX_RAW_BYTES:
            if (result['status'] != 'response_too_large' or
                    result['observed_model_id'] is not None or
                    result['model_identity'] != 'unverified' or
                    result['error'] != {'type': 'ResponseTooLarge',
                                        'message': 'retained_first_max_raw_bytes_plus_one'} or
                    type(result['http_status']) is not int):
                raise ValueError('user_game_generation_large_response_metadata_changed')
        else:
            observed = _observed_model(raw)
            identity = ('matched' if observed == manifest['route']['model_id']
                        else 'mismatch' if observed is not None else 'unverified')
            expected_status = ('http_error' if type(result['http_status']) is int and
                               not 200 <= result['http_status'] < 300 else
                               'identity_mismatch' if identity == 'mismatch' else
                               'identity_unverified' if identity == 'unverified' else
                               'captured')
            if (result['observed_model_id'] != observed or
                    result['model_identity'] != identity or result['status'] != expected_status or
                    result['error'] is not None or type(result['http_status']) is not int):
                raise ValueError('user_game_generation_raw_metadata_changed')
    return {'schema': SCHEMA, 'integrity_passed': True,
            'status': result['status'], 'requested': 1,
            'attempts_consumed': 1, 'model_calls': 1,
            'raw_classification': result['raw_classification'],
            'commentary_capability_gate_passed': False}


def _check_capture_cli_pins(manifest: dict, args, manifest_sha256: str) -> None:
    """Make the one authorized role/source/model/request explicit in the command."""
    expected = {
        'role': manifest['role'],
        'pgn_sha256': manifest['pgn_sha256'],
        'review_sha256': manifest['review_sha256'],
        'page_sha256': manifest['page_sha256'],
        'packet_sha256': manifest['packet_sha256'],
        'model_id': manifest['route']['model_id'],
        'seed': manifest['route']['seed'],
        'request_sha256': manifest['request_sha256'],
        'manifest_sha256': manifest_sha256,
    }
    if any(getattr(args, name) != value for name, value in expected.items()):
        raise ValueError('user_game_generation_capture_cli_pins_changed')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    freeze = sub.add_parser('freeze')
    freeze.add_argument('--pgn', type=Path, required=True)
    freeze.add_argument('--review-dir', type=Path, required=True)
    freeze.add_argument('--pgn-sha256', required=True)
    freeze.add_argument('--review-sha256', required=True)
    freeze.add_argument('--page-sha256', required=True)
    freeze.add_argument('--role', choices=user_packet.ROLES, required=True)
    freeze.add_argument('--packet', type=Path, required=True)
    freeze.add_argument('--declared-route', type=Path, required=True)
    freeze.add_argument('--route-attestation', type=Path, required=True)
    freeze.add_argument('--run-dir', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--run-dir', type=Path, required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--run-dir', type=Path, required=True)
    capture.add_argument('--role', choices=user_packet.ROLES, required=True)
    capture.add_argument('--pgn-sha256', required=True)
    capture.add_argument('--review-sha256', required=True)
    capture.add_argument('--page-sha256', required=True)
    capture.add_argument('--packet-sha256', required=True)
    capture.add_argument('--model-id', required=True)
    capture.add_argument('--seed', type=int, required=True)
    capture.add_argument('--request-sha256', required=True)
    capture.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        manifest = freeze_run(args.pgn, args.review_dir, args.pgn_sha256,
                              args.review_sha256, args.page_sha256, args.role,
                              args.packet, args.declared_route,
                              args.route_attestation, args.run_dir)
        result = {'schema': SCHEMA, 'status': 'frozen', 'role': manifest['role'],
                  'model_id': manifest['route']['model_id'],
                  'packet_sha256': manifest['packet_sha256'],
                  'request_sha256': manifest['request_sha256'],
                  'model_calls': 0, 'heldout_outcomes_scored': 0,
                  'commentary_capability_gate_passed': False}
    elif args.command == 'capture':
        manifest_path = Path(args.run_dir) / MANIFEST_FILE
        current_manifest_sha256 = _source_sha256(manifest_path)
        if args.manifest_sha256 != current_manifest_sha256:
            raise ValueError('user_game_generation_capture_cli_manifest_changed')
        manifest = _json(manifest_path)
        _manifest_shape(manifest)
        _check_capture_cli_pins(manifest, args, current_manifest_sha256)
        result = capture_frozen_run(args.run_dir)
    else:
        result = verify_run(args.run_dir)
    print(cf.canonical(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
