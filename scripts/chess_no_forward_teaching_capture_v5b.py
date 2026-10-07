#!/usr/bin/env python3
"""Freeze, capture once, and check one v5 Chess.com alternative proposal.

The model sees only the v5 checker's nine-field pre-move projection. The
source-bound packet and review remain evaluator-side. Capture is one local POST
with a create-only request sentinel; an interruption spends that attempt.
Neither a successful transport nor a legal conditional claim establishes move
quality, Stockfish intent, or human teaching quality.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import chess_counterfactual_evidence as cf
import chess_local_route_attestation as route_capture
import chess_no_forward_packet as no_forward
import chess_no_forward_generation_runner as route_rules
import chess_no_forward_teaching_v3 as earlier_teaching
import chess_no_forward_teaching_v4 as previous_teaching
import chess_no_forward_teaching_v5 as teaching
import chess_tactical_hypothesis_v2 as tactical
import chess_user_game_no_forward_v1 as user_packet


SCHEMA = 'chess-no-forward-teaching-capture/v5b'
RESULT_SCHEMA = 'chess-no-forward-teaching-capture-result/v5b'
EVALUATION_SCHEMA = 'chess-no-forward-teaching-capture-evaluation/v5b'
MANIFEST_FILE = 'manifest.json'
PACKET_FILE = 'packet.json'
GENERATOR_INPUT_FILE = 'generator-input.json'
REQUEST_FILE = 'request.json'
RAW_FILE = 'raw-response.bin'
RESULT_FILE = 'result.json'
EVALUATION_FILE = 'evaluation.json'
ROUTE_DIR = 'route'
ATTESTATION_FILES = (route_capture.RECEIPT_NAME, route_capture.OBSERVED_ROUTE_NAME,
                     route_capture.ATTESTATION_NAME, route_capture.SNAPSHOT_NAME)
MAX_METADATA_BYTES = 512 * 1024
MAX_RAW_BYTES = route_rules.MAX_RAW_BYTES
SOURCE_MODULES = {
    'chess_no_forward_teaching_v5.py': teaching,
    'chess_no_forward_teaching_v4.py': previous_teaching,
    'chess_no_forward_teaching_v3.py': earlier_teaching,
    'chess_tactical_hypothesis_v2.py': tactical,
    'chess_user_game_no_forward_v1.py': user_packet,
    'chess_no_forward_packet.py': user_packet.no_forward,
    'chess_counterfactual_evidence.py': cf,
    'chess_local_route_attestation.py': route_capture,
    'chess_no_forward_generation_runner.py': route_rules,
    'chess_paired_review_v3.py': user_packet.paired,
    'chess_review_completed_game.py': user_packet.previous,
    'chess_real_evidence_interface.py': user_packet.paired.ui,
}
MANIFEST_FIELDS = ('schema', 'run_state', 'requested', 'model_calls',
                   'automatic_retries', 'heldout_outcomes_scored',
                   'commentary_capability_gate_passed', 'source_binding',
                   'source_packet_path', 'source_packet_sha256', 'selected_uci',
                   'projection_sha256', 'declared_route_path',
                   'declared_route_sha256', 'route', 'route_evidence_sha256',
                   'prompt_sha256', 'request_sha256', 'implementation_sha256')
RESULT_FIELDS = ('schema', 'manifest_sha256', 'request_sha256',
                 'source_packet_sha256', 'projection_sha256', 'status',
                 'attempt_count', 'model_calls', 'automatic_retries',
                 'input_dispatched', 'latency_ns', 'http_status', 'raw_path',
                 'raw_sha256', 'raw_bytes', 'observed_model_id',
                 'model_identity', 'error', 'heldout_outcomes_scored',
                 'commentary_capability_gate_passed')
PROJECTION_FIELDS = ('schema', 'source_packet_sha256', 'source', 'fen',
                     'side_to_move', 'selected_move', 'transition',
                     'engine_observation', 'assertion_kinds')


def _read(path: Path, maximum: int, code: str) -> bytes:
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(code)
    return raw


def _json_file(path: Path, maximum: int = MAX_METADATA_BYTES) -> dict:
    raw = _read(path, maximum, 'teaching_capture_metadata_too_large')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_teaching_capture_json') from error
    if type(value) is not dict or raw != cf.canonical(value) + b'\n':
        raise ValueError('teaching_capture_metadata_not_canonical')
    return value


def _write(path: Path, raw: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def _write_json(path: Path, value: dict) -> None:
    raw = cf.canonical(value) + b'\n'
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError('teaching_capture_metadata_too_large')
    _write(path, raw)


def _implementation_hashes() -> dict:
    return {
        'chess_no_forward_teaching_capture_v5b.py': cf.file_digest(Path(__file__)),
        **{name: cf.file_digest(Path(module.__file__))
           for name, module in SOURCE_MODULES.items()},
    }


def _source_binding(pgn: Path, review_dir: Path, pgn_sha: str,
                    review_sha: str, page_sha: str) -> dict:
    return {
        'schema': tactical.BINDING_SCHEMA,
        'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(Path(pgn).resolve()),
        'review_dir': str(Path(review_dir).resolve()),
        'pgn_sha256': pgn_sha, 'review_sha256': review_sha,
        'page_sha256': page_sha, 'role': 'played',
    }


def _verified_packet(path: Path, expected_sha: str, binding: dict) -> bytes:
    raw = _read(path, user_packet.MAX_PACKET_BYTES, 'teaching_capture_packet_too_large')
    # The checker invokes the owning packet encoder and replays the legal move.
    teaching.build_generator_input(raw, expected_sha, source_binding=binding)
    packet = json.loads(raw)
    if (packet['source']['move_role'] != 'played' or
            packet['source']['selected_ply'] != 39 or
            packet['selected_move']['uci'] != 'c2c3'):
        raise ValueError('teaching_capture_requires_played_ply39_qc3')
    return raw


def _route(path: Path) -> tuple[bytes, dict]:
    raw = _read(path, MAX_METADATA_BYTES, 'teaching_capture_route_too_large')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_teaching_capture_route_json') from error
    route_rules._validate_route(value)
    if value['automatic_retries'] != 0:
        raise ValueError('teaching_capture_retries_forbidden')
    return raw, value


def _attestation_files(directory: Path) -> dict[str, bytes]:
    return {name: _read(Path(directory) / name, MAX_METADATA_BYTES,
                        'teaching_capture_route_evidence_too_large')
            for name in ATTESTATION_FILES}


def build_request(generator_input: bytes, route: dict) -> bytes:
    """Encode the sole model request, accepting only a v5 nine-key projection."""
    route_rules._validate_route(route)
    if type(generator_input) is not bytes or not 0 < len(generator_input) <= 16_384:
        raise ValueError('invalid_teaching_generator_input_bytes')
    try:
        value = json.loads(generator_input)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_teaching_generator_input_json') from error
    cf.exact_keys(value, PROJECTION_FIELDS, 'invalid_teaching_projection_fields')
    cf.exact_keys(value['source'], user_packet.SOURCE_FIELDS,
                  'invalid_teaching_source_fields')
    cf.exact_keys(value['selected_move'], ('uci', 'san'),
                  'invalid_teaching_move_fields')
    cf.exact_keys(value['transition'], no_forward.TRANSITION_FIELDS,
                  'invalid_teaching_transition_fields')
    cf.exact_keys(value['engine_observation'], user_packet.ENGINE_FIELDS,
                  'invalid_teaching_engine_fields')
    cf.exact_keys(value['engine_observation']['score'], user_packet.SCORE_FIELDS,
                  'invalid_teaching_score_fields')
    # Exact keys alone do not stop a future line hidden as a value of an
    # otherwise allowed field. Every leaf in this projection is scalar, apart
    # from the separately checked assertion declaration.
    expected_leaves = (
        (value, {'source_packet_sha256': (str,), 'fen': (str,),
                 'side_to_move': (str,)}),
        (value['source'], {
            **{name: (str,) for name in user_packet.SOURCE_FIELDS
               if name != 'selected_ply'}, 'selected_ply': (int,)}),
        (value['selected_move'], {'uci': (str,), 'san': (str,)}),
        (value['transition'], {
            'moving_piece': (str,), 'moving_color': (str,),
            'from': (str,), 'to': (str,), 'capture': (bool,),
            'captured_piece': (str, type(None)),
            'captured_square': (str, type(None)),
            'en_passant': (bool,), 'castling': (bool,),
            'promotion': (str, type(None)), 'gives_check': (bool,)}),
        (value['engine_observation'], {
            'name': (str,), 'sha256': (str,),
            'observation_only': (bool,), 'independently_reproduced': (bool,)}),
        (value['engine_observation']['score'], {
            'type': (str,), 'value': (int,), 'bound': (str,),
            'order': (str,), 'perspective': (str,),
            'side_to_move': (str,)}),
    )
    if any(type(fields[name]) not in permitted
           for fields, rules in expected_leaves
           for name, permitted in rules.items()):
        raise ValueError('invalid_teaching_projection_leaf_type')
    if (generator_input != cf.canonical(value) or
            value['schema'] != teaching.INPUT_SCHEMA or
            value['assertion_kinds'] != [teaching.CLAIM_KIND, 'abstention']):
        raise ValueError('invalid_teaching_projection')
    request = {
        'model': route['model_id'],
        'messages': [{'role': 'system', 'content': teaching.PROMPT},
                     {'role': 'user', 'content': generator_input.decode('utf-8')}],
        'stream': False,
        'temperature': route['sampling']['temperature'],
        'top_p': route['sampling']['top_p'],
        'max_tokens': route['sampling']['max_output_tokens'],
        'seed': route['seed'],
        'reasoning_effort': route['reasoning']['effort'],
    }
    return cf.canonical(request)


def _manifest_shape(manifest: dict) -> None:
    cf.exact_keys(manifest, MANIFEST_FIELDS, 'invalid_teaching_capture_manifest_shape')
    if (manifest['schema'] != SCHEMA or manifest['run_state'] != 'frozen' or
            manifest['requested'] != 1 or manifest['model_calls'] != 0 or
            manifest['automatic_retries'] != 0 or
            manifest['heldout_outcomes_scored'] != 0 or
            manifest['commentary_capability_gate_passed'] is not False or
            manifest['selected_uci'] != 'c2c3' or
            manifest['source_binding'].get('role') != 'played'):
        raise ValueError('invalid_teaching_capture_manifest_boundary')
    cf.exact_keys(manifest['route_evidence_sha256'], ATTESTATION_FILES,
                  'invalid_teaching_capture_route_evidence_shape')
    cf.exact_keys(manifest['implementation_sha256'],
                  ('chess_no_forward_teaching_capture_v5b.py', *SOURCE_MODULES),
                  'invalid_teaching_capture_implementation_shape')
    route_rules._validate_route(manifest['route'])


def freeze_run(pgn_path: Path, review_dir: Path, pgn_sha256: str,
               review_sha256: str, page_sha256: str, packet_path: Path,
               declared_route_path: Path, attestation_dir: Path, run_dir: Path,
               *, expected_packet_sha256: str) -> dict:
    """Freeze the exact source, safe input, request, route and implementation."""
    run_dir = Path(run_dir).resolve()
    if run_dir.exists():
        raise FileExistsError(run_dir)
    packet_path = Path(packet_path).resolve()
    declared_route_path = Path(declared_route_path).resolve()
    binding = _source_binding(pgn_path, review_dir, pgn_sha256,
                              review_sha256, page_sha256)
    packet_raw = _verified_packet(packet_path, expected_packet_sha256, binding)
    projection = teaching.build_generator_input(packet_raw, expected_packet_sha256,
                                                source_binding=binding)
    route_raw, route = _route(declared_route_path)
    if route_capture.verify_capture(declared_route_path, attestation_dir)['verified'] is not True:
        raise ValueError('teaching_capture_route_not_attested')
    route_files = _attestation_files(attestation_dir)
    request_raw = build_request(projection, route)
    manifest = {
        'schema': SCHEMA, 'run_state': 'frozen', 'requested': 1,
        'model_calls': 0, 'automatic_retries': 0,
        'heldout_outcomes_scored': 0, 'commentary_capability_gate_passed': False,
        'source_binding': binding, 'source_packet_path': str(packet_path),
        'source_packet_sha256': expected_packet_sha256, 'selected_uci': 'c2c3',
        'projection_sha256': cf.digest(projection),
        'declared_route_path': str(declared_route_path),
        'declared_route_sha256': cf.digest(route_raw), 'route': route,
        'route_evidence_sha256': {name: cf.digest(raw)
                                  for name, raw in route_files.items()},
        'prompt_sha256': cf.digest(teaching.PROMPT.encode('utf-8')),
        'request_sha256': cf.digest(request_raw),
        'implementation_sha256': _implementation_hashes(),
    }
    _manifest_shape(manifest)
    run_dir.mkdir(parents=True, exist_ok=False)
    _write(run_dir / PACKET_FILE, packet_raw)
    _write(run_dir / GENERATOR_INPUT_FILE, projection)
    for name, raw in route_files.items():
        _write(run_dir / ROUTE_DIR / name, raw)
    _write_json(run_dir / MANIFEST_FILE, manifest)
    return manifest


def _preflight(run_dir: Path) -> tuple[dict, bytes, bytes]:
    run_dir = Path(run_dir).resolve()
    manifest = _json_file(run_dir / MANIFEST_FILE)
    _manifest_shape(manifest)
    if manifest['implementation_sha256'] != _implementation_hashes():
        raise ValueError('teaching_capture_implementation_changed_since_freeze')
    if manifest['prompt_sha256'] != cf.digest(teaching.PROMPT.encode('utf-8')):
        raise ValueError('teaching_capture_prompt_changed')
    route_raw, route = _route(Path(manifest['declared_route_path']))
    if (cf.digest(route_raw) != manifest['declared_route_sha256'] or
            cf.canonical(route) != cf.canonical(manifest['route'])):
        raise ValueError('teaching_capture_route_changed')
    route_dir = run_dir / ROUTE_DIR
    files = _attestation_files(route_dir)
    if {name: cf.digest(raw) for name, raw in files.items()} != manifest['route_evidence_sha256']:
        raise ValueError('teaching_capture_route_evidence_changed')
    if route_capture.verify_capture(Path(manifest['declared_route_path']),
                                    route_dir)['verified'] is not True:
        raise ValueError('teaching_capture_route_attestation_changed')
    packet = _verified_packet(Path(manifest['source_packet_path']),
                              manifest['source_packet_sha256'], manifest['source_binding'])
    if packet != _read(run_dir / PACKET_FILE, user_packet.MAX_PACKET_BYTES,
                       'teaching_capture_frozen_packet_too_large'):
        raise ValueError('teaching_capture_frozen_packet_changed')
    projection = teaching.build_generator_input(packet, manifest['source_packet_sha256'],
                                                source_binding=manifest['source_binding'])
    if (projection != _read(run_dir / GENERATOR_INPUT_FILE, 16_384,
                            'teaching_capture_projection_too_large') or
            cf.digest(projection) != manifest['projection_sha256']):
        raise ValueError('teaching_capture_projection_changed')
    request = build_request(projection, route)
    if cf.digest(request) != manifest['request_sha256']:
        raise ValueError('teaching_capture_request_changed')
    return manifest, packet, request


def _observed_model(raw: bytes) -> str | None:
    try:
        value = _strict_response_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return value.get('model') if type(value) is dict and type(value.get('model')) is str else None


def _strict_response_json(raw: bytes):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_response_key')
            value[key] = item
        return value

    def reject_constant(_value):
        raise ValueError('non_finite_response_number')

    def finite_float(value):
        try:
            number = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError('invalid_response_number') from error
        if not math.isfinite(number):
            raise ValueError('non_finite_response_number')
        return number

    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                          parse_constant=reject_constant,
                          parse_float=finite_float)
    except RecursionError as error:
        raise ValueError('response_json_too_deep') from error


class IncompleteModelResponse(ValueError):
    """A parseable answer cannot be admitted when generation hit its limit."""


def capture_frozen_run(run_dir: Path, *, opener=None) -> dict:
    """Spend exactly one attempt; preserve raw bytes or the transport failure."""
    run_dir = Path(run_dir).resolve()
    if (run_dir / REQUEST_FILE).exists() or (run_dir / RESULT_FILE).exists():
        raise ValueError('teaching_capture_already_attempted')
    manifest, _, request_raw = _preflight(run_dir)
    if opener is None:
        opener = build_opener(ProxyHandler({}), route_rules._NoRedirect())
    if not callable(getattr(opener, 'open', None)):
        raise ValueError('invalid_teaching_capture_opener_before_post')
    request = Request(manifest['route']['endpoint'] + '/chat/completions',
                      data=request_raw, headers={'Content-Type': 'application/json'},
                      method='POST')
    _write(run_dir / REQUEST_FILE, request_raw)
    started = time.perf_counter_ns()
    status, http_status, raw_path, raw_sha256 = 'transport_failure', None, None, None
    raw_bytes, observed, identity, error_record = 0, None, 'unverified', None
    try:
        try:
            response = opener.open(request, timeout=manifest['route']['timeout_seconds'])
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_RAW_BYTES + 1)
            http_status = int(getattr(response, 'status',
                                      getattr(response, 'code', 0)) or 0)
        _write(run_dir / RAW_FILE, raw)
        raw_path, raw_sha256, raw_bytes = RAW_FILE, cf.digest(raw), len(raw)
        if len(raw) > MAX_RAW_BYTES:
            status = 'response_too_large'
            error_record = {'type': 'ResponseTooLarge',
                            'message': 'retained_first_max_raw_bytes_plus_one'}
        else:
            observed = _observed_model(raw)
            identity = ('matched' if observed == manifest['route']['model_id'] else
                        'mismatch' if observed is not None else 'unverified')
            status = ('http_error' if not 200 <= http_status < 300 else
                      'identity_mismatch' if identity == 'mismatch' else
                      'identity_unverified' if identity == 'unverified' else 'captured')
    except Exception as error:
        error_record = {'type': type(error).__name__, 'message': str(error)[:512]}
    result = {
        'schema': RESULT_SCHEMA, 'manifest_sha256': cf.file_digest(run_dir / MANIFEST_FILE),
        'request_sha256': cf.digest(request_raw),
        'source_packet_sha256': manifest['source_packet_sha256'],
        'projection_sha256': manifest['projection_sha256'],
        'status': status, 'attempt_count': 1, 'model_calls': 1,
        'automatic_retries': 0, 'input_dispatched': True,
        'latency_ns': time.perf_counter_ns() - started,
        'http_status': http_status, 'raw_path': raw_path,
        'raw_sha256': raw_sha256, 'raw_bytes': raw_bytes,
        'observed_model_id': observed, 'model_identity': identity,
        'error': error_record, 'heldout_outcomes_scored': 0,
        'commentary_capability_gate_passed': False,
    }
    _write_json(run_dir / RESULT_FILE, result)
    return result


def _model_content(raw: bytes) -> bytes:
    """Extract one plain assistant message; never expose reasoning or tool calls."""
    try:
        envelope = _strict_response_json(raw)
        choices = envelope['choices']
        if type(choices) is not list or len(choices) != 1:
            raise ValueError('invalid_choice_count')
        message = choices[0]['message']
        if (type(message) is not dict or message.get('role') != 'assistant' or
                type(message.get('content')) is not str or
                not message['content'].strip() or
                message.get('tool_calls') not in (None, []) or
                message.get('function_call') is not None):
            raise ValueError('invalid_assistant_message')
        if choices[0].get('finish_reason') != 'stop':
            raise IncompleteModelResponse('incomplete_model_response')
        return message['content'].encode('utf-8')
    except IncompleteModelResponse:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError,
            IndexError, AttributeError, ValueError) as error:
        raise ValueError('invalid_teaching_model_envelope') from error


def _evaluation(run_dir: Path, manifest: dict, result: dict, packet: bytes) -> dict:
    raw = _read(run_dir / RAW_FILE, MAX_RAW_BYTES + 1,
                'teaching_capture_raw_too_large')
    try:
        content = _model_content(raw)
        extraction_status = 'one_plain_assistant_message'
    except IncompleteModelResponse:
        content = b''
        extraction_status = 'incomplete_model_response'
    except ValueError:
        # Still invoke the offline checker, which rejects the empty claim. The
        # raw envelope remains the authoritative evidence for diagnosis.
        content = b''
        extraction_status = 'invalid_model_envelope'
    checked = teaching.evaluate(packet, manifest['source_packet_sha256'], content,
                                source_binding=manifest['source_binding'])
    return {
        'schema': EVALUATION_SCHEMA,
        'manifest_sha256': cf.file_digest(run_dir / MANIFEST_FILE),
        'result_sha256': cf.file_digest(run_dir / RESULT_FILE),
        'raw_sha256': result['raw_sha256'],
        'extraction_status': extraction_status,
        'content_sha256': cf.digest(content),
        'checker': checked,
        'model_calls_in_evaluator': 0, 'engine_calls_in_evaluator': 0,
        'quality_evaluated': False,
        'commentary_capability_gate_passed': False,
    }


def evaluate_frozen_run(run_dir: Path) -> dict:
    """Offline check of a matched HTTP capture; no call or additional attempt."""
    run_dir = Path(run_dir).resolve()
    integrity = verify_run(run_dir)
    if integrity['status'] != 'captured':
        raise ValueError('teaching_capture_not_eligible_for_evaluation')
    manifest, packet, _ = _preflight(run_dir)
    result = _json_file(run_dir / RESULT_FILE)
    receipt = _evaluation(run_dir, manifest, result, packet)
    _write_json(run_dir / EVALUATION_FILE, receipt)
    return receipt


def verify_run(run_dir: Path) -> dict:
    """Readback source, route, request, raw bytes, result and optional check."""
    run_dir = Path(run_dir).resolve()
    manifest, packet, request = _preflight(run_dir)
    request_path, result_path = run_dir / REQUEST_FILE, run_dir / RESULT_FILE
    if not request_path.exists():
        if (result_path.exists() or (run_dir / RAW_FILE).exists() or
                (run_dir / EVALUATION_FILE).exists()):
            raise ValueError('teaching_capture_result_without_request')
        return {'schema': SCHEMA, 'integrity_passed': True, 'status': 'frozen',
                'attempts_consumed': 0, 'model_calls': 0,
                'commentary_capability_gate_passed': False}
    if _read(request_path, MAX_METADATA_BYTES,
             'teaching_capture_request_too_large') != request:
        raise ValueError('teaching_capture_request_changed')
    if not result_path.exists():
        return {'schema': SCHEMA, 'integrity_passed': False, 'status': 'interrupted',
                'attempts_consumed': 1, 'model_calls_upper_bound': 1,
                'commentary_capability_gate_passed': False}
    result = _json_file(result_path)
    cf.exact_keys(result, RESULT_FIELDS, 'invalid_teaching_capture_result_shape')
    if (result['schema'] != RESULT_SCHEMA or
            result['manifest_sha256'] != cf.file_digest(run_dir / MANIFEST_FILE) or
            result['request_sha256'] != cf.digest(request) or
            result['source_packet_sha256'] != manifest['source_packet_sha256'] or
            result['projection_sha256'] != manifest['projection_sha256'] or
            result['attempt_count'] != 1 or result['model_calls'] != 1 or
            result['automatic_retries'] != 0 or result['input_dispatched'] is not True or
            result['heldout_outcomes_scored'] != 0 or
            result['commentary_capability_gate_passed'] is not False or
            type(result['latency_ns']) is not int or result['latency_ns'] < 0):
        raise ValueError('teaching_capture_result_binding_changed')
    if result['raw_path'] is None:
        if (result['status'] != 'transport_failure' or result['error'] is None or
                result['raw_sha256'] is not None or result['raw_bytes'] != 0 or
                result['http_status'] is not None or (run_dir / RAW_FILE).exists() or
                result['observed_model_id'] is not None or
                result['model_identity'] != 'unverified'):
            raise ValueError('teaching_capture_missing_raw_inconsistent')
    else:
        if result['raw_path'] != RAW_FILE:
            raise ValueError('invalid_teaching_capture_raw_path')
        raw = _read(run_dir / RAW_FILE, MAX_RAW_BYTES + 1,
                    'teaching_capture_raw_too_large')
        if result['raw_sha256'] != cf.digest(raw) or result['raw_bytes'] != len(raw):
            raise ValueError('teaching_capture_raw_changed')
        if type(result['http_status']) is not int:
            raise ValueError('teaching_capture_http_status_invalid')
        if len(raw) > MAX_RAW_BYTES:
            if (result['status'] != 'response_too_large' or
                    result['observed_model_id'] is not None or
                    result['model_identity'] != 'unverified' or
                    result['error'] != {'type': 'ResponseTooLarge',
                                        'message': 'retained_first_max_raw_bytes_plus_one'}):
                raise ValueError('teaching_capture_large_response_metadata_changed')
        else:
            observed = _observed_model(raw)
            identity = ('matched' if observed == manifest['route']['model_id'] else
                        'mismatch' if observed is not None else 'unverified')
            status = ('http_error' if not 200 <= result['http_status'] < 300 else
                      'identity_mismatch' if identity == 'mismatch' else
                      'identity_unverified' if identity == 'unverified' else 'captured')
            if (result['observed_model_id'] != observed or
                    result['model_identity'] != identity or
                    result['status'] != status or result['error'] is not None):
                raise ValueError('teaching_capture_raw_metadata_changed')
    evaluation_path = run_dir / EVALUATION_FILE
    if evaluation_path.exists():
        if result['status'] != 'captured':
            raise ValueError('teaching_capture_invalid_evaluation_status')
        if _json_file(evaluation_path) != _evaluation(run_dir, manifest, result, packet):
            raise ValueError('teaching_capture_evaluation_changed')
    return {'schema': SCHEMA, 'integrity_passed': True,
            'status': result['status'], 'attempts_consumed': 1,
            'model_calls': 1, 'evaluation_retained': evaluation_path.exists(),
            'commentary_capability_gate_passed': False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    for name in ('pgn', 'review-dir', 'packet', 'declared-route',
                 'route-attestation', 'run-dir'):
        freeze.add_argument('--' + name, type=Path, required=True)
    for name in ('pgn-sha256', 'review-sha256', 'page-sha256',
                 'packet-sha256'):
        freeze.add_argument('--' + name, required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--run-dir', type=Path, required=True)
    for name in ('pgn-sha256', 'review-sha256', 'page-sha256',
                 'packet-sha256', 'model-id', 'endpoint', 'request-sha256',
                 'manifest-sha256'):
        capture.add_argument('--' + name, required=True)
    capture.add_argument('--seed', type=int, required=True)
    for name in ('evaluate', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        manifest = freeze_run(args.pgn, args.review_dir, args.pgn_sha256,
                              args.review_sha256, args.page_sha256, args.packet,
                              args.declared_route, args.route_attestation,
                              args.run_dir, expected_packet_sha256=args.packet_sha256)
        result = {'schema': SCHEMA, 'status': 'frozen',
                  'source_packet_sha256': manifest['source_packet_sha256'],
                  'projection_sha256': manifest['projection_sha256'],
                  'request_sha256': manifest['request_sha256'],
                  'model_calls': 0, 'commentary_capability_gate_passed': False}
    elif args.command == 'capture':
        path = Path(args.run_dir).resolve() / MANIFEST_FILE
        manifest = _json_file(path)
        _manifest_shape(manifest)
        expected = {
            'pgn_sha256': manifest['source_binding']['pgn_sha256'],
            'review_sha256': manifest['source_binding']['review_sha256'],
            'page_sha256': manifest['source_binding']['page_sha256'],
            'packet_sha256': manifest['source_packet_sha256'],
            'model_id': manifest['route']['model_id'],
            'endpoint': manifest['route']['endpoint'],
            'seed': manifest['route']['seed'],
            'request_sha256': manifest['request_sha256'],
            'manifest_sha256': cf.file_digest(path),
        }
        if any(getattr(args, name) != value for name, value in expected.items()):
            raise ValueError('teaching_capture_cli_pins_changed')
        result = capture_frozen_run(args.run_dir)
    elif args.command == 'evaluate':
        result = evaluate_frozen_run(args.run_dir)
    else:
        result = verify_run(args.run_dir)
    print(cf.canonical(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
