#!/usr/bin/env python3
"""One-attempt, create-only capture of four known postgame chess practice moves.

The request contains only v9's source-checked nine-field pre-move projection.
The PGN, review, alternative score, and evaluator witness stay outside the
generator. Frozen and failed cases remain in a denominator of four. This is
practice plumbing, not a chess commentary capability result.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import chess_counterfactual_evidence as cf
import chess_local_route_attestation as route_capture
import chess_no_forward_generation_runner as route_rules
import chess_no_forward_teaching_capture_v7 as capture_v7
import chess_no_forward_teaching_v3 as teaching_v3
import chess_no_forward_teaching_v4 as teaching_v4
import chess_no_forward_teaching_v5 as teaching_v5
import chess_no_forward_teaching_v6 as teaching_v6
import chess_no_forward_teaching_v7 as teaching_v7
import chess_no_forward_teaching_v8 as teaching_v8
import chess_no_forward_teaching_v9 as teaching
import chess_tactical_hypothesis_v2 as tactical
import chess_user_game_no_forward_v1 as user_packet


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess-no-forward-teaching-capture/v9'
RESULT_SCHEMA = 'chess-no-forward-teaching-capture-result/v9'
EVALUATION_SCHEMA = 'chess-no-forward-teaching-capture-evaluation/v9'
PLAN_FILE = 'plan.json'
MANIFEST_FILE = 'manifest.json'
PACKET_FILE = 'packet.json'
PROJECTION_FILE = 'generator-input.json'
FROZEN_REQUEST_FILE = 'frozen-request.json'
REQUEST_FILE = 'request.json'
RAW_FILE = 'raw-response.bin'
RESULT_FILE = 'result.json'
EVALUATION_FILE = 'evaluation.json'
ROUTE_DIR = 'route'
PGN = ROOT / 'artifacts/chess-user-reviews/chesscom-184866057876/source.pgn'
REVIEW_ROOT = ROOT / 'artifacts/chesscom-breadth-baseline-20261006'
DECLARED_ROUTE = ROOT / 'research/chess-local-route-131k-v2-teaching-1024.json'
PGN_SHA256 = '684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075'
ROUTE_SHA256 = 'bb0260811fc13970bea18dfc310786e4b927c56f59883921629544417cd74acb'
CASE_PINS = {
    33: ('68a93644e372d4df7058fdae2866c6bc1ceee56e27b9240801842c2ca1bb0fae',
         '7c70158228d817860ef5324720e4ab7463e4a39f9cb529af2b172111e3e12e49'),
    46: ('2d377b2e0223a9fb9c4d01ba060c15078dc788aef233eb68fe52a861a5f735aa',
         '0c97c3f4b518c11d70e24a74cd5d6ce7c138cfaf3ae6fee6997b7a8fe2769ef5'),
    57: ('76d906526abaed37760bea838cec7671b9a093e607895f057f61c35cad767597',
         'd40f62a8ef428f27920fd3a11d8e94b35b9da1ed1bfbc1fdcf7f5dfce2cd9628'),
    93: ('3219c8c925997a9b02d4446f9ff04dd62a88a8bf6f815b43a141f4669b4c24eb',
         'd043d1b5df046fe286227ca19549e4934c973d027760095084eda82296911b9d'),
}
ATTESTATION_FILES = (route_capture.RECEIPT_NAME,
                     route_capture.OBSERVED_ROUTE_NAME,
                     route_capture.ATTESTATION_NAME, route_capture.SNAPSHOT_NAME)
MAX_METADATA_BYTES = 512 * 1024
MAX_RAW_BYTES = route_rules.MAX_RAW_BYTES
FRESH_SECONDS = 10 * 60
SOURCE_MODULES = {
    'chess_no_forward_teaching_v9.py': teaching,
    'chess_no_forward_teaching_v8.py': teaching_v8,
    'chess_no_forward_teaching_v7.py': teaching_v7,
    'chess_no_forward_teaching_v6.py': teaching_v6,
    'chess_no_forward_teaching_v5.py': teaching_v5,
    'chess_no_forward_teaching_v4.py': teaching_v4,
    'chess_no_forward_teaching_v3.py': teaching_v3,
    'chess_no_forward_teaching_capture_v7.py': capture_v7,
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
PLAN_FIELDS = ('schema', 'status', 'plies', 'denominator', 'requested',
               'model_calls', 'automatic_retries', 'heldout_outcomes_scored',
               'commentary_capability_gate_passed', 'pgn_path', 'pgn_sha256',
               'review_root', 'declared_route_path', 'declared_route_sha256',
               'route', 'route_evidence_sha256', 'implementation_sha256',
               'cases')
MANIFEST_FIELDS = ('schema', 'state', 'ply', 'case_kind', 'selected_uci',
                   'requested', 'model_calls', 'automatic_retries',
                   'heldout_outcomes_scored', 'commentary_capability_gate_passed',
                   'source_binding', 'source_packet_sha256',
                   'projection_sha256', 'prompt_sha256', 'request_sha256',
                   'route_evidence_sha256', 'implementation_sha256',
                   'plan_sha256')
RESULT_FIELDS = ('schema', 'manifest_sha256', 'request_sha256',
                 'source_packet_sha256', 'projection_sha256', 'status',
                 'attempt_count', 'model_calls', 'automatic_retries',
                 'input_dispatched', 'latency_ns', 'http_status', 'raw_path',
                 'raw_sha256', 'raw_bytes', 'declared_model_id',
                 'observed_model_id', 'model_identity', 'error',
                 'heldout_outcomes_scored', 'commentary_capability_gate_passed')


def _read(path: Path, limit: int = MAX_METADATA_BYTES) -> bytes:
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('v9_capture_file_too_large')
    return raw


def _json(path: Path) -> dict:
    raw = _read(path)
    try:
        value = capture_v7._strict_response_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError('v9_capture_invalid_json') from error
    if type(value) is not dict or raw != cf.canonical(value) + b'\n':
        raise ValueError('v9_capture_metadata_not_canonical')
    return value


def _write(path: Path, raw: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def _write_json(path: Path, value: dict) -> None:
    raw = cf.canonical(value) + b'\n'
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError('v9_capture_metadata_too_large')
    _write(path, raw)


def _implementation_hashes() -> dict:
    return {'chess_no_forward_teaching_capture_v9.py': cf.file_digest(Path(__file__)),
            **{name: cf.file_digest(Path(module.__file__))
               for name, module in SOURCE_MODULES.items()}}


def _binding(pgn: Path, review_dir: Path, review_sha: str,
             page_sha: str) -> dict:
    return {'schema': tactical.BINDING_SCHEMA,
            'packet_schema': user_packet.SCHEMA,
            'pgn_path': str(pgn.resolve()),
            'review_dir': str(review_dir.resolve()),
            'pgn_sha256': PGN_SHA256, 'review_sha256': review_sha,
            'page_sha256': page_sha, 'role': 'played'}


def _route(path: Path) -> tuple[bytes, dict]:
    raw = _read(path)
    if cf.digest(raw) != ROUTE_SHA256:
        raise ValueError('v9_capture_declared_route_changed')
    try:
        route = capture_v7._strict_response_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError('v9_capture_invalid_route_json') from error
    route_rules._validate_route(route)
    if (route['endpoint'] != 'http://127.0.0.1:1234/v1' or
            route['model_id'] != 'loops-cpu-gpt-oss-20b' or
            route['context_window_tokens'] != 131072 or
            route['sampling'] != {'max_output_tokens': 1024,
                                  'temperature': 0, 'top_p': 1} or
            route['seed'] != 20260923 or
            route['reasoning'] != {'effort': 'low'} or
            route['timeout_seconds'] != 60 or
            route['automatic_retries'] != 0):
        raise ValueError('v9_capture_unexpected_route')
    return raw, route


def _attestation_files(directory: Path) -> dict[str, bytes]:
    return {name: _read(Path(directory) / name)
            for name in ATTESTATION_FILES}


def _verify_attestation(route_path: Path, directory: Path, *, fresh: bool) -> dict:
    verified = route_capture.verify_capture(route_path, directory)
    if verified.get('verified') is not True:
        raise ValueError('v9_capture_route_not_attested')
    files = _attestation_files(directory)
    attestation = _json(Path(directory) / route_capture.ATTESTATION_NAME)
    if fresh:
        try:
            captured = datetime.fromisoformat(attestation['captured_at'].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - captured).total_seconds()
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            raise ValueError('v9_capture_attestation_time_invalid') from error
        if captured.tzinfo is None or not -60 <= age <= FRESH_SECONDS:
            raise ValueError('v9_capture_attestation_not_fresh')
    return {name: cf.digest(raw) for name, raw in files.items()}


def _source_packet(pgn: Path, review_dir: Path, binding: dict,
                   ply: int) -> tuple[bytes, bytes]:
    packet = user_packet.build_packet(pgn, review_dir, PGN_SHA256,
                                      binding['review_sha256'],
                                      binding['page_sha256'], role='played')
    raw = user_packet.encode_packet(pgn, review_dir, PGN_SHA256,
                                    binding['review_sha256'],
                                    binding['page_sha256'], role='played',
                                    packet=packet)
    if (packet['source']['selected_ply'] != ply or
            cf.digest(raw) != CASE_PINS[ply][0]):
        raise ValueError('v9_capture_case_packet_mismatch')
    projected = teaching.build_generator_input(raw, cf.digest(raw),
                                                source_binding=binding)
    if cf.digest(projected) != CASE_PINS[ply][1]:
        raise ValueError('v9_capture_case_projection_mismatch')
    return raw, projected


def build_request(projection: bytes, route: dict) -> bytes:
    """Validate the complete v9 projection with v7's strict nested leaf gate."""
    if type(projection) is not bytes or not 0 < len(projection) <= 16384:
        raise ValueError('v9_capture_invalid_projection_bytes')
    try:
        value = capture_v7._strict_response_json(projection)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError('v9_capture_invalid_projection_json') from error
    if (type(value) is not dict or
            set(value) != set(capture_v7.PROJECTION_FIELDS) or
            projection != cf.canonical(value) or
            value.get('schema') != teaching.INPUT_SCHEMA or
            value.get('assertion_kinds') != list(teaching.KINDS)):
        raise ValueError('v9_capture_invalid_projection')
    # v7 validates every nested key and scalar leaf. Its two declarations are
    # temporarily substituted only for that validation, never sent to a model.
    v7_value = dict(value, schema=teaching_v7.INPUT_SCHEMA,
                    assertion_kinds=[teaching_v7.CLAIM_KIND, 'abstention'])
    capture_v7.build_request(cf.canonical(v7_value), route)
    request = {'model': route['model_id'],
               'messages': [{'role': 'system', 'content': teaching.PROMPT},
                            {'role': 'user', 'content': projection.decode('utf-8')}],
               'stream': False,
               'temperature': route['sampling']['temperature'],
               'top_p': route['sampling']['top_p'],
               'max_tokens': route['sampling']['max_output_tokens'],
               'seed': route['seed'],
               'reasoning_effort': route['reasoning']['effort']}
    return cf.canonical(request)


def freeze_run(run_dir: Path, attestation_dir: Path, *,
               pgn: Path = PGN, review_root: Path = REVIEW_ROOT,
               declared_route: Path = DECLARED_ROUTE) -> dict:
    """Freeze all four cases and the denominator before any request sentinel."""
    run_dir, pgn, review_root, declared_route = (
        Path(item).resolve() for item in
        (run_dir, pgn, review_root, declared_route))
    if run_dir.exists():
        raise FileExistsError(run_dir)
    if pgn != PGN.resolve() or review_root != REVIEW_ROOT.resolve() or declared_route != DECLARED_ROUTE.resolve():
        raise ValueError('v9_capture_source_or_route_path_changed')
    if cf.file_digest(pgn) != PGN_SHA256:
        raise ValueError('v9_capture_pgn_changed')
    _, route = _route(declared_route)
    evidence_hashes = _verify_attestation(declared_route, attestation_dir,
                                           fresh=True)
    evidence = _attestation_files(attestation_dir)
    impl = _implementation_hashes()
    cases = {}
    frozen = {}
    for ply in CASE_PINS:
        review_dir = review_root / f'ply{ply}'
        binding = _binding(pgn, review_dir,
                           cf.file_digest(review_dir / 'review.json'),
                           cf.file_digest(review_dir / 'index.html'))
        packet, projection = _source_packet(pgn, review_dir, binding, ply)
        request = build_request(projection, route)
        case_kind, _, selected_uci = teaching_v8.CASES[ply]
        cases[str(ply)] = {'packet_sha256': cf.digest(packet),
                           'projection_sha256': cf.digest(projection),
                           'request_sha256': cf.digest(request),
                           'review_sha256': binding['review_sha256'],
                           'page_sha256': binding['page_sha256']}
        frozen[ply] = (binding, packet, projection, request,
                       case_kind, selected_uci)
    plan = {'schema': SCHEMA, 'status': 'frozen', 'plies': list(CASE_PINS),
            'denominator': 4, 'requested': 4, 'model_calls': 0,
            'automatic_retries': 0, 'heldout_outcomes_scored': 0,
            'commentary_capability_gate_passed': False,
            'pgn_path': str(pgn), 'pgn_sha256': PGN_SHA256,
            'review_root': str(review_root),
            'declared_route_path': str(declared_route),
            'declared_route_sha256': ROUTE_SHA256, 'route': route,
            'route_evidence_sha256': evidence_hashes,
            'implementation_sha256': impl, 'cases': cases}
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_json(run_dir / PLAN_FILE, plan)
    for name, raw in evidence.items():
        _write(run_dir / ROUTE_DIR / name, raw)
    plan_sha = cf.file_digest(run_dir / PLAN_FILE)
    for ply, (binding, packet, projection, request,
              case_kind, selected_uci) in frozen.items():
        case_dir = run_dir / f'ply{ply}'
        case_dir.mkdir(exist_ok=False)
        manifest = {'schema': SCHEMA, 'state': 'frozen', 'ply': ply,
                    'case_kind': case_kind, 'selected_uci': selected_uci,
                    'requested': 1, 'model_calls': 0,
                    'automatic_retries': 0, 'heldout_outcomes_scored': 0,
                    'commentary_capability_gate_passed': False,
                    'source_binding': binding,
                    'source_packet_sha256': cf.digest(packet),
                    'projection_sha256': cf.digest(projection),
                    'prompt_sha256': cf.digest(teaching.PROMPT.encode('utf-8')),
                    'request_sha256': cf.digest(request),
                    'route_evidence_sha256': evidence_hashes,
                    'implementation_sha256': impl, 'plan_sha256': plan_sha}
        _write(case_dir / PACKET_FILE, packet)
        _write(case_dir / PROJECTION_FILE, projection)
        _write(case_dir / FROZEN_REQUEST_FILE, request)
        _write_json(case_dir / MANIFEST_FILE, manifest)
    return plan


def _preflight(run_dir: Path, *, fresh: bool = False) -> tuple[dict, dict]:
    run_dir = Path(run_dir).resolve()
    plan = _json(run_dir / PLAN_FILE)
    cf.exact_keys(plan, PLAN_FIELDS, 'v9_capture_invalid_plan_shape')
    if (plan['schema'] != SCHEMA or plan['status'] != 'frozen' or
            plan['plies'] != list(CASE_PINS) or plan['denominator'] != 4 or
            plan['requested'] != 4 or plan['model_calls'] != 0 or
            plan['automatic_retries'] != 0 or
            plan['heldout_outcomes_scored'] != 0 or
            plan['commentary_capability_gate_passed'] is not False or
            plan['pgn_path'] != str(PGN.resolve()) or
            plan['pgn_sha256'] != PGN_SHA256 or
            plan['review_root'] != str(REVIEW_ROOT.resolve()) or
            plan['declared_route_path'] != str(DECLARED_ROUTE.resolve()) or
            plan['declared_route_sha256'] != ROUTE_SHA256 or
            plan['implementation_sha256'] != _implementation_hashes() or
            set(plan['cases']) != {str(ply) for ply in CASE_PINS}):
        raise ValueError('v9_capture_plan_binding_changed')
    if cf.file_digest(PGN) != PGN_SHA256:
        raise ValueError('v9_capture_pgn_changed')
    _, route = _route(DECLARED_ROUTE)
    if route != plan['route']:
        raise ValueError('v9_capture_route_changed')
    evidence = _attestation_files(run_dir / ROUTE_DIR)
    if ({name: cf.digest(raw) for name, raw in evidence.items()} !=
            plan['route_evidence_sha256'] or
            _verify_attestation(DECLARED_ROUTE, run_dir / ROUTE_DIR,
                                fresh=fresh) != plan['route_evidence_sha256']):
        raise ValueError('v9_capture_attestation_changed')
    cases = {}
    for ply in CASE_PINS:
        case_dir = run_dir / f'ply{ply}'
        manifest = _json(case_dir / MANIFEST_FILE)
        cf.exact_keys(manifest, MANIFEST_FIELDS, 'v9_capture_invalid_manifest_shape')
        source = manifest['source_binding']
        expected = plan['cases'][str(ply)]
        if (manifest['schema'] != SCHEMA or manifest['state'] != 'frozen' or
                manifest['ply'] != ply or
                manifest['case_kind'] != teaching_v8.CASES[ply][0] or
                manifest['selected_uci'] != teaching_v8.CASES[ply][2] or
                manifest['requested'] != 1 or manifest['model_calls'] != 0 or
                manifest['automatic_retries'] != 0 or
                manifest['heldout_outcomes_scored'] != 0 or
                manifest['commentary_capability_gate_passed'] is not False or
                manifest['implementation_sha256'] != plan['implementation_sha256'] or
                manifest['route_evidence_sha256'] != plan['route_evidence_sha256'] or
                manifest['plan_sha256'] != cf.file_digest(run_dir / PLAN_FILE) or
                manifest['prompt_sha256'] != cf.digest(teaching.PROMPT.encode('utf-8')) or
                source != _binding(PGN, REVIEW_ROOT / f'ply{ply}',
                                   expected['review_sha256'],
                                   expected['page_sha256'])):
            raise ValueError('v9_capture_manifest_binding_changed')
        packet, projection = _source_packet(PGN, REVIEW_ROOT / f'ply{ply}',
                                             source, ply)
        request = build_request(projection, route)
        hashes = (cf.digest(packet), cf.digest(projection), cf.digest(request))
        if (hashes != (expected['packet_sha256'],
                       expected['projection_sha256'], expected['request_sha256']) or
                hashes != (manifest['source_packet_sha256'],
                           manifest['projection_sha256'], manifest['request_sha256']) or
                _read(case_dir / PACKET_FILE, user_packet.MAX_PACKET_BYTES) != packet or
                _read(case_dir / PROJECTION_FILE, 16384) != projection or
                _read(case_dir / FROZEN_REQUEST_FILE) != request):
            raise ValueError('v9_capture_frozen_case_changed')
        cases[ply] = {'dir': case_dir, 'manifest': manifest,
                      'packet': packet, 'projection': projection,
                      'request': request}
    return plan, cases


def _pins(manifest: dict, route: dict, case_dir: Path) -> dict:
    source = manifest['source_binding']
    return {'pgn_sha256': source['pgn_sha256'],
            'review_sha256': source['review_sha256'],
            'page_sha256': source['page_sha256'],
            'packet_sha256': manifest['source_packet_sha256'],
            'model_id': route['model_id'], 'endpoint': route['endpoint'],
            'seed': route['seed'],
            'request_sha256': manifest['request_sha256'],
            'manifest_sha256': cf.file_digest(case_dir / MANIFEST_FILE)}


def _observed_model(raw: bytes) -> str | None:
    try:
        envelope = capture_v7._strict_response_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return (envelope.get('model') if type(envelope) is dict and
            type(envelope.get('model')) is str else None)


def capture_case(run_dir: Path, ply: int, *, pins: dict, opener=None) -> dict:
    """Spend one case attempt; a request sentinel survives interruption."""
    if ply not in CASE_PINS or type(ply) is not int:
        raise ValueError('v9_capture_unknown_ply')
    case_dir = Path(run_dir).resolve() / f'ply{ply}'
    if (case_dir / REQUEST_FILE).exists() or (case_dir / RESULT_FILE).exists():
        raise ValueError('v9_capture_already_attempted')
    plan, cases = _preflight(run_dir, fresh=True)
    case = cases[ply]
    if pins != _pins(case['manifest'], plan['route'], case_dir):
        raise ValueError('v9_capture_cli_pins_changed')
    if opener is None:
        opener = build_opener(ProxyHandler({}), route_rules._NoRedirect())
    if not callable(getattr(opener, 'open', None)):
        raise ValueError('v9_capture_invalid_opener')
    request_raw = case['request']
    request = Request(plan['route']['endpoint'] + '/chat/completions',
                      data=request_raw,
                      headers={'Content-Type': 'application/json'},
                      method='POST')
    _write(case_dir / REQUEST_FILE, request_raw)
    started = time.perf_counter_ns()
    status, http_status, raw_path, raw_sha, raw_size = (
        'transport_failure', None, None, None, 0)
    observed, identity, error_record = None, 'unverified', None
    try:
        try:
            response = opener.open(request,
                                   timeout=plan['route']['timeout_seconds'])
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_RAW_BYTES + 1)
            http_status = int(getattr(response, 'status',
                                      getattr(response, 'code', 0)) or 0)
        _write(case_dir / RAW_FILE, raw)
        raw_path, raw_sha, raw_size = RAW_FILE, cf.digest(raw), len(raw)
        if raw_size > MAX_RAW_BYTES:
            status = 'response_too_large'
            error_record = {'type': 'ResponseTooLarge',
                            'message': 'retained_first_max_raw_bytes_plus_one'}
        else:
            observed = _observed_model(raw)
            identity = ('matched' if observed == plan['route']['model_id'] else
                        'mismatch' if observed is not None else 'unverified')
            status = ('http_error' if not 200 <= http_status < 300 else
                      'identity_mismatch' if identity == 'mismatch' else
                      'identity_unverified' if identity == 'unverified' else
                      'captured')
    except Exception as error:
        if (case_dir / RAW_FILE).exists():
            # A local failure after receiving bytes is ambiguous. Keep the
            # sentinel/raw file and do not falsely record a transport result.
            raise
        error_record = {'type': type(error).__name__,
                        'message': str(error)[:512]}
    result = {'schema': RESULT_SCHEMA,
              'manifest_sha256': cf.file_digest(case_dir / MANIFEST_FILE),
              'request_sha256': cf.digest(request_raw),
              'source_packet_sha256': case['manifest']['source_packet_sha256'],
              'projection_sha256': case['manifest']['projection_sha256'],
              'status': status, 'attempt_count': 1, 'model_calls': 1,
              'automatic_retries': 0, 'input_dispatched': True,
              'latency_ns': time.perf_counter_ns() - started,
              'http_status': http_status, 'raw_path': raw_path,
              'raw_sha256': raw_sha, 'raw_bytes': raw_size,
              'declared_model_id': plan['route']['model_id'],
              'observed_model_id': observed, 'model_identity': identity,
              'error': error_record, 'heldout_outcomes_scored': 0,
              'commentary_capability_gate_passed': False}
    _write_json(case_dir / RESULT_FILE, result)
    return result


def _model_content(raw: bytes) -> bytes:
    """Take one completed plain assistant message, rejecting tool output."""
    try:
        envelope = capture_v7._strict_response_json(raw)
        if type(envelope) is not dict or type(envelope.get('choices')) is not list or len(envelope['choices']) != 1:
            raise ValueError('invalid_choice_count')
        choice = envelope['choices'][0]
        if type(choice) is not dict or choice.get('finish_reason') != 'stop':
            raise ValueError('incomplete_model_response')
        message = choice.get('message')
        if (type(message) is not dict or
                set(message) != {'role', 'content'} or
                message['role'] != 'assistant' or
                type(message['content']) is not str or
                not message['content'].strip()):
            raise ValueError('invalid_plain_assistant_message')
        return message['content'].encode('utf-8')
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError,
            IndexError, AttributeError, ValueError) as error:
        raise ValueError(str(error) if type(error) is ValueError else
                         'invalid_model_envelope') from error


def _evaluation(case: dict, result: dict) -> dict:
    case_dir = case['dir']
    raw = _read(case_dir / RAW_FILE, MAX_RAW_BYTES + 1)
    try:
        content = _model_content(raw)
        extraction_status = 'one_plain_assistant_message'
    except ValueError as error:
        content = b''
        extraction_status = str(error)[:128]
    checker = teaching.evaluate(case['packet'],
                                case['manifest']['source_packet_sha256'],
                                content,
                                source_binding=case['manifest']['source_binding'])
    return {'schema': EVALUATION_SCHEMA,
            'manifest_sha256': cf.file_digest(case_dir / MANIFEST_FILE),
            'result_sha256': cf.file_digest(case_dir / RESULT_FILE),
            'raw_sha256': result['raw_sha256'],
            'extraction_status': extraction_status,
            'content_sha256': cf.digest(content), 'checker': checker,
            'model_calls_in_evaluator': 0, 'engine_calls_in_evaluator': 0,
            'quality_evaluated': False,
            'commentary_capability_gate_passed': False}


def evaluate_case(run_dir: Path, ply: int) -> dict:
    """Check one captured response offline, retaining extraction failures."""
    statuses = verify_run(run_dir)
    row = next(item for item in statuses['rows'] if item['ply'] == ply)
    if row['status'] != 'captured' or row['evaluation'] is not None:
        raise ValueError('v9_capture_not_eligible_for_evaluation')
    _, cases = _preflight(run_dir)
    case = cases[ply]
    result = _json(case['dir'] / RESULT_FILE)
    receipt = _evaluation(case, result)
    _write_json(case['dir'] / EVALUATION_FILE, receipt)
    return receipt


def _verify_case(case: dict, plan: dict) -> dict:
    case_dir, manifest, request = (case['dir'], case['manifest'], case['request'])
    request_file, result_file = case_dir / REQUEST_FILE, case_dir / RESULT_FILE
    if not request_file.exists():
        if any((case_dir / name).exists() for name in
               (RESULT_FILE, RAW_FILE, EVALUATION_FILE)):
            raise ValueError('v9_capture_result_without_request')
        return {'status': 'not_run', 'attempts_consumed': 0,
                'evaluation': None, 'model_identity': None}
    if _read(request_file) != request:
        raise ValueError('v9_capture_request_changed')
    if not result_file.exists():
        return {'status': 'interrupted', 'attempts_consumed': 1,
                'evaluation': None, 'model_identity': None}
    result = _json(result_file)
    cf.exact_keys(result, RESULT_FIELDS, 'v9_capture_invalid_result_shape')
    if (result['schema'] != RESULT_SCHEMA or
            result['manifest_sha256'] != cf.file_digest(case_dir / MANIFEST_FILE) or
            result['request_sha256'] != cf.digest(request) or
            result['source_packet_sha256'] != manifest['source_packet_sha256'] or
            result['projection_sha256'] != manifest['projection_sha256'] or
            result['attempt_count'] != 1 or result['model_calls'] != 1 or
            result['automatic_retries'] != 0 or
            result['input_dispatched'] is not True or
            result['declared_model_id'] != plan['route']['model_id'] or
            result['heldout_outcomes_scored'] != 0 or
            result['commentary_capability_gate_passed'] is not False or
            type(result['latency_ns']) is not int or result['latency_ns'] < 0):
        raise ValueError('v9_capture_result_binding_changed')
    if result['raw_path'] is None:
        if (result['status'] != 'transport_failure' or
                result['error'] is None or result['raw_sha256'] is not None or
                result['raw_bytes'] != 0 or result['http_status'] is not None or
                result['observed_model_id'] is not None or
                result['model_identity'] != 'unverified' or
                (case_dir / RAW_FILE).exists()):
            raise ValueError('v9_capture_missing_raw_inconsistent')
    else:
        if result['raw_path'] != RAW_FILE:
            raise ValueError('v9_capture_invalid_raw_path')
        raw = _read(case_dir / RAW_FILE, MAX_RAW_BYTES + 1)
        if result['raw_sha256'] != cf.digest(raw) or result['raw_bytes'] != len(raw) or type(result['http_status']) is not int:
            raise ValueError('v9_capture_raw_changed')
        if len(raw) > MAX_RAW_BYTES:
            if (result['status'] != 'response_too_large' or
                    result['model_identity'] != 'unverified' or
                    result['observed_model_id'] is not None or
                    result['error'] != {'type': 'ResponseTooLarge',
                                        'message': 'retained_first_max_raw_bytes_plus_one'}):
                raise ValueError('v9_capture_large_raw_metadata_changed')
        else:
            observed = _observed_model(raw)
            identity = ('matched' if observed == plan['route']['model_id'] else
                        'mismatch' if observed is not None else 'unverified')
            status = ('http_error' if not 200 <= result['http_status'] < 300 else
                      'identity_mismatch' if identity == 'mismatch' else
                      'identity_unverified' if identity == 'unverified' else
                      'captured')
            if (result['observed_model_id'] != observed or
                    result['model_identity'] != identity or
                    result['status'] != status or result['error'] is not None):
                raise ValueError('v9_capture_raw_metadata_changed')
    evaluation = None
    if (case_dir / EVALUATION_FILE).exists():
        if result['status'] != 'captured':
            raise ValueError('v9_capture_evaluation_on_failed_result')
        evaluation = _json(case_dir / EVALUATION_FILE)
        if evaluation != _evaluation(case, result):
            raise ValueError('v9_capture_evaluation_changed')
    return {'status': result['status'], 'attempts_consumed': 1,
            'evaluation': evaluation, 'model_identity': result['model_identity']}


def verify_run(run_dir: Path) -> dict:
    """Read all four immutable cases and report the complete practice denominator."""
    plan, cases = _preflight(run_dir)
    rows = []
    counts = {'legal_typed_claim': 0, 'abstention': 0,
              'format_rejection': 0, 'transport_failure': 0,
              'not_run': 0, 'interrupted': 0, 'other_failure': 0}
    for ply in CASE_PINS:
        observed = _verify_case(cases[ply], plan)
        evaluation = observed['evaluation']
        decision = evaluation['checker']['decision'] if evaluation else None
        if observed['status'] == 'not_run':
            category = 'not_run'
        elif observed['status'] == 'interrupted':
            category = 'interrupted'
        elif observed['status'] == 'transport_failure':
            category = 'transport_failure'
        elif evaluation is not None:
            category = ('legal_typed_claim' if decision == 'verified_typed_board_claim' else
                        'abstention' if decision == 'model_abstention' else
                        'format_rejection' if decision == 'rejected' else
                        'other_failure')
        else:
            category = 'other_failure'
        counts[category] += 1
        rows.append({'ply': ply, 'case_kind': cases[ply]['manifest']['case_kind'],
                     'status': observed['status'], 'category': category,
                     'attempts_consumed': observed['attempts_consumed'],
                     'model_identity': observed['model_identity'],
                     'evaluation': evaluation})
    return {'schema': SCHEMA, 'denominator': 4, 'rows': rows,
            'counts': counts,
            'attempts_consumed': sum(row['attempts_consumed'] for row in rows),
            'automatic_retries': 0, 'heldout_outcomes_scored': 0,
            'quality_evaluated': False,
            'commentary_capability_gate_passed': False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--run-dir', type=Path, required=True)
    freeze.add_argument('--route-attestation', type=Path, required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--run-dir', type=Path, required=True)
    capture.add_argument('--ply', type=int, choices=CASE_PINS, required=True)
    for name in ('pgn-sha256', 'review-sha256', 'page-sha256',
                 'packet-sha256', 'model-id', 'endpoint', 'seed',
                 'request-sha256', 'manifest-sha256'):
        capture.add_argument('--' + name, required=True,
                             type=int if name == 'seed' else str)
    evaluate = commands.add_parser('evaluate')
    evaluate.add_argument('--run-dir', type=Path, required=True)
    evaluate.add_argument('--ply', type=int, choices=CASE_PINS, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        plan = freeze_run(args.run_dir, args.route_attestation)
        result = {'schema': SCHEMA, 'status': 'frozen',
                  'denominator': plan['denominator'], 'model_calls': 0,
                  'commentary_capability_gate_passed': False}
    elif args.command == 'capture':
        pins = {name.replace('-', '_'): getattr(args, name.replace('-', '_'))
                for name in ('pgn-sha256', 'review-sha256', 'page-sha256',
                             'packet-sha256', 'model-id', 'endpoint', 'seed',
                             'request-sha256', 'manifest-sha256')}
        result = capture_case(args.run_dir, args.ply, pins=pins)
    elif args.command == 'evaluate':
        result = evaluate_case(args.run_dir, args.ply)
    else:
        result = verify_run(args.run_dir)
    print(cf.canonical(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
