"""Fail-closed local-generation runner for the versioned chess no-forward path.

This module is deliberately narrower than a chess commentator.  It freezes at
most eight real development packets that have already passed
``chess_no_forward_packet.dispatch_no_forward``, binds a separately retained
local-route attestation, and retains every raw response or failure.  It never
scores explanation quality, opens Stockfish, reads Studio configuration, or
uses held-out outcomes.  A later independent evaluator is required before any
commentary capability claim.

The command line has intentionally safe commands only: ``freeze`` and
``verify``.  Live execution is library-only, requires an explicit injected
transport, and must be invoked by the project-native execution workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess-no-forward-generation-runner/v1'
RESULT_SCHEMA = 'chess-no-forward-generation-results/v1'
ATTESTATION_SCHEMA = 'chess-local-route-attestation/v2'
RUNTIME_OBSERVATION_SCHEMA = 'chess-local-route-runtime-observation/v1'
RUNTIME_SNAPSHOT_NAME = 'models-snapshot.json'
LOCAL_MODELS_URL = 'http://127.0.0.1:1234/api/v1/models'
LOCAL_MODEL_CATALOG_KEY = 'openai/gpt-oss-20b'
MAX_REQUESTS = 8
MAX_PACKET_BYTES = 16_384
MAX_METADATA_BYTES = 512 * 1024
MAX_RAW_BYTES = 1_048_576

ROUTE_FIELDS = (
    'route_id', 'endpoint', 'model_id', 'context_window_tokens', 'reasoning',
    'sampling', 'seed', 'request_schema', 'timeout_seconds', 'automatic_retries',
)
REASONING_FIELDS = ('effort',)
SAMPLING_FIELDS = ('temperature', 'top_p', 'max_output_tokens')
ATTESTATION_FIELDS = ('schema', 'captured_at', 'runtime', 'route')
RUNTIME_OBSERVATION_FIELDS = (
    'schema', 'models_url', 'http_status', 'snapshot_path', 'snapshot_sha256',
    'snapshot_bytes', 'catalog_model_key', 'loaded_instance_id',
    'loaded_context_window_tokens', 'loaded_parallel',
    'model_max_context_window_tokens', 'reasoning_allowed_options',
    'reasoning_default', 'declared_request_fields', 'limitations',
)
DECLARED_REQUEST_FIELDS = (
    'route_id', 'sampling', 'seed', 'request_schema', 'timeout_seconds',
    'automatic_retries',
)
RUNTIME_OBSERVATION_LIMITATIONS = [
    'The local readiness response attests only to loaded runtime state at capture time.',
    'Route ID, sampling, seed, request schema, timeout and retry policy are declared by the frozen runner; the readiness endpoint does not return them.',
    'This is not a model-weight hash, a future-response identity proof, or a commentary-quality result.',
]
INPUT_MANIFEST_FIELDS = (
    'schema', 'commentary_gate_passed', 'heldout_outcomes_scored',
    'implementation_sha256', 'model_calls', 'new_engine_calls', 'records',
    'requested', 'retained', 'selection', 'source_receipt_sha256',
    'source_split', 'typed_packet_sha256',
)
INPUT_RECORD_FIELDS = (
    'bytes', 'evidence_id', 'game_id', 'path', 'position_id', 'sha256',
)
REQUEST_FIELDS = (
    'ordinal', 'request_id', 'input_path', 'input_sha256', 'input_bytes',
    'position_id', 'evidence_id', 'game_id',
)
MANIFEST_FIELDS = (
    'schema', 'created_at_ns', 'run_state', 'commentary_capability_gate_passed',
    'commentary_quality_evaluated', 'independent_acceptance', 'model_calls',
    'new_engine_calls', 'heldout_outcomes_scored', 'data_root',
    'source_receipt_path', 'source_receipt_sha256', 'typed_packet_path',
    'typed_packet_file_sha256', 'typed_packet_canonical_sha256',
    'input_manifest_path', 'input_manifest_sha256', 'route_attestation_path',
    'route_attestation_sha256', 'route_attestation_snapshot_path',
    'route_attestation_snapshot_sha256', 'declared_route', 'declared_route_sha256',
    'observed_route', 'observed_route_sha256', 'implementation', 'requests',
)
IMPLEMENTATION_FIELDS = (
    'runner_sha256', 'no_forward_boundary_sha256', 'counterfactual_sha256',
)
OUTCOME_FIELDS = (
    'ordinal', 'request_id', 'input_path', 'input_sha256', 'input_bytes',
    'position_id', 'evidence_id', 'game_id', 'status', 'input_dispatched',
    'model_call_began', 'raw_path', 'raw_sha256', 'raw_bytes',
    'raw_classification', 'observed_route', 'observed_route_sha256', 'transport_status',
    'latency_ns', 'error',
)
RESULT_FIELDS = (
    'schema', 'manifest_sha256', 'commentary_capability_gate_passed',
    'commentary_quality_evaluated', 'independent_acceptance', 'requested',
    'accounted', 'model_calls', 'new_engine_calls', 'heldout_outcomes_scored',
    'status_counts', 'raw_classification_counts', 'outcomes', 'limitations',
)
LIMITATIONS = [
    'Raw local-generation transport capture only; no explanation quality or factuality result is computed here.',
    'The generator receives only the canonical no-forward packet; typed receipts, PVs, future moves and evaluator material remain outside the transport boundary.',
    'Development inputs are convenience inputs, not game-disjoint heldout commentary evidence.',
    'A retained route attestation binds the local route before calls but is not a model-weight identity proof.',
]


def _require_string(value, message, *, maximum=512):
    cf.require(type(value) is str and 0 < len(value) <= maximum, message)


def _require_digest(value, message):
    cf.require(type(value) is str and len(value) == 64 and
               all(character in '0123456789abcdef' for character in value), message)


def _require_nonnegative_int(value, message):
    cf.require(type(value) is int and 0 <= value <= 2**63 - 1, message)


def _read_bytes(path, maximum, message):
    path = Path(path)
    with path.open('rb') as stream:
        value = stream.read(maximum + 1)
    cf.require(len(value) <= maximum, message)
    return value


def _read_json(path, maximum=MAX_METADATA_BYTES):
    try:
        return json.loads(_read_bytes(path, maximum, 'artifact_exceeds_byte_budget'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_json_artifact') from error


def _write_bytes_create(path, value, maximum, message):
    cf.require(isinstance(value, bytes) and len(value) <= maximum, message)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value)


def write_json(value, path):
    """Write a bounded canonical receipt once; never rewrite a retained artifact."""
    encoded = cf.canonical(value) + b'\n'
    _write_bytes_create(path, encoded, MAX_METADATA_BYTES, 'metadata_exceeds_byte_budget')


def _root_relative(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError('path_outside_project_root') from error


def _from_root_relative(value):
    _require_string(value, 'invalid_project_relative_path', maximum=1024)
    candidate = Path(value)
    cf.require(not candidate.is_absolute() and '..' not in candidate.parts,
               'unsafe_project_relative_path')
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError('unsafe_project_relative_path') from error
    return resolved


def _from_run_relative(run_dir, value):
    _require_string(value, 'invalid_run_relative_path', maximum=256)
    candidate = Path(value)
    cf.require(not candidate.is_absolute() and '..' not in candidate.parts,
               'unsafe_run_relative_path')
    resolved = (Path(run_dir) / candidate).resolve()
    try:
        resolved.relative_to(Path(run_dir).resolve())
    except ValueError as error:
        raise ValueError('unsafe_run_relative_path') from error
    return resolved


def _implementation_hashes():
    return {
        'runner_sha256': cf.file_digest(Path(__file__)),
        'no_forward_boundary_sha256': cf.file_digest(Path(no_forward.__file__)),
        'counterfactual_sha256': cf.file_digest(Path(cf.__file__)),
    }


def _validate_route(route):
    """Admit only the declared local 131k route, with no retries or fallback."""
    cf.exact_keys(route, ROUTE_FIELDS, 'invalid_route_shape')
    _validate_route_claim_shape(route)
    _require_string(route['route_id'], 'invalid_route_id')
    _require_string(route['endpoint'], 'invalid_route_endpoint')
    endpoint = urlsplit(route['endpoint'])
    cf.require(endpoint.scheme == 'http' and endpoint.hostname == '127.0.0.1' and
               endpoint.port == 1234 and endpoint.path == '/v1' and
               not endpoint.query and not endpoint.fragment and
               endpoint.username is None and endpoint.password is None,
               'route_is_not_pinned_loopback_endpoint')
    cf.require(type(route['context_window_tokens']) is int and
               route['context_window_tokens'] == 131_072,
               'route_context_window_is_not_131072')
    cf.require(route['request_schema'] == 'openai-chat-completions/v1',
               'invalid_route_request_schema')
    cf.require(route['automatic_retries'] == 0, 'automatic_retries_not_permitted')


def _validate_route_claim_shape(route):
    """Validate a returned route record without mistaking drift for a valid route.

    A response claiming 32k context or a foreign model is deliberately retained
    as an identity mismatch.  It must still have a complete, bounded route shape
    so an arbitrary response object cannot masquerade as an attestation.
    """
    cf.exact_keys(route, ROUTE_FIELDS, 'invalid_route_shape')
    _require_string(route['route_id'], 'invalid_route_id')
    _require_string(route['endpoint'], 'invalid_route_endpoint')
    _require_string(route['model_id'], 'invalid_route_model_id')
    cf.require(type(route['context_window_tokens']) is int and
               1 <= route['context_window_tokens'] <= 2**20,
               'invalid_observed_route_context_window')
    cf.exact_keys(route['reasoning'], REASONING_FIELDS, 'invalid_reasoning_settings')
    cf.require(route['reasoning']['effort'] in ('low', 'medium', 'high'),
               'invalid_reasoning_effort')
    cf.exact_keys(route['sampling'], SAMPLING_FIELDS, 'invalid_sampling_settings')
    for field in ('temperature', 'top_p'):
        cf.require(type(route['sampling'][field]) in (int, float) and
                   not isinstance(route['sampling'][field], bool) and
                   0 <= route['sampling'][field] <= 1,
                   'invalid_sampling_' + field)
    cf.require(type(route['sampling']['max_output_tokens']) is int and
               64 <= route['sampling']['max_output_tokens'] <= 8192,
               'invalid_sampling_max_output_tokens')
    _require_nonnegative_int(route['seed'], 'invalid_route_seed')
    _require_string(route['request_schema'], 'invalid_route_request_schema')
    cf.require(type(route['timeout_seconds']) in (int, float) and
               not isinstance(route['timeout_seconds'], bool) and
               1 <= route['timeout_seconds'] <= 120,
               'invalid_route_timeout')
    _require_nonnegative_int(route['automatic_retries'], 'invalid_route_retries')


def runtime_observation_from_models_snapshot(raw, route):
    """Derive the admissible local-runtime facts from one retained GET body.

    The future request settings remain explicit declarations in ``route``.  The
    loaded instance, context, serialism and supported reasoning effort must be
    present in LM Studio's own local readiness response rather than copied from
    that declaration.
    """
    _validate_route(route)
    cf.require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_METADATA_BYTES,
               'invalid_route_runtime_snapshot_bytes')
    try:
        catalog = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_route_runtime_snapshot_json') from error
    cf.require(type(catalog) is dict and isinstance(catalog.get('models'), list),
               'invalid_route_runtime_catalog')
    matches = []
    for entry in catalog['models']:
        if type(entry) is not dict or entry.get('key') != LOCAL_MODEL_CATALOG_KEY:
            continue
        loaded = entry.get('loaded_instances')
        if not isinstance(loaded, list):
            continue
        for instance in loaded:
            if type(instance) is dict and instance.get('id') == route['model_id']:
                matches.append((entry, instance))
    cf.require(len(matches) == 1, 'route_runtime_does_not_have_one_matching_loaded_instance')
    entry, instance = matches[0]
    config = instance.get('config')
    cf.require(type(config) is dict, 'invalid_route_runtime_instance_config')
    context = config.get('context_length')
    parallel = config.get('parallel')
    maximum = entry.get('max_context_length')
    cf.require(type(context) is int and context == route['context_window_tokens'],
               'route_runtime_context_does_not_match_declared_131072')
    cf.require(type(parallel) is int and parallel == 1,
               'route_runtime_is_not_serial')
    cf.require(type(maximum) is int and maximum >= context,
               'invalid_route_runtime_max_context')
    reasoning = (entry.get('capabilities') or {}).get('reasoning')
    cf.require(type(reasoning) is dict and isinstance(reasoning.get('allowed_options'), list),
               'route_runtime_reasoning_capability_missing')
    allowed = reasoning['allowed_options']
    cf.require(all(type(value) is str for value in allowed) and len(set(allowed)) == len(allowed) and
               route['reasoning']['effort'] in allowed,
               'route_runtime_reasoning_effort_not_supported')
    default = reasoning.get('default')
    cf.require(type(default) is str and default in allowed,
               'invalid_route_runtime_reasoning_default')
    return {
        'schema': RUNTIME_OBSERVATION_SCHEMA,
        'models_url': LOCAL_MODELS_URL,
        'http_status': 200,
        'snapshot_path': RUNTIME_SNAPSHOT_NAME,
        'snapshot_sha256': cf.digest(raw),
        'snapshot_bytes': len(raw),
        'catalog_model_key': entry['key'],
        'loaded_instance_id': instance['id'],
        'loaded_context_window_tokens': context,
        'loaded_parallel': parallel,
        'model_max_context_window_tokens': maximum,
        'reasoning_allowed_options': allowed,
        'reasoning_default': default,
        'declared_request_fields': list(DECLARED_REQUEST_FIELDS),
        'limitations': list(RUNTIME_OBSERVATION_LIMITATIONS),
    }


def _validate_runtime_observation(runtime, raw, route):
    cf.exact_keys(runtime, RUNTIME_OBSERVATION_FIELDS,
                  'invalid_route_runtime_observation_shape')
    expected = runtime_observation_from_models_snapshot(raw, route)
    cf.require(cf.canonical(runtime) == cf.canonical(expected),
               'route_runtime_observation_does_not_match_snapshot')


def _load_route_attestation(path, observed_route):
    path = Path(path)
    raw = _read_bytes(path, MAX_METADATA_BYTES, 'route_attestation_exceeds_byte_budget')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_route_attestation_json') from error
    cf.exact_keys(value, ATTESTATION_FIELDS, 'invalid_route_attestation_shape')
    cf.require(value['schema'] == ATTESTATION_SCHEMA, 'invalid_route_attestation_schema')
    _require_string(value['captured_at'], 'invalid_route_attestation_time')
    _validate_route(value['route'])
    cf.require(cf.canonical(value['route']) == cf.canonical(observed_route),
               'route_attestation_does_not_match_observed_route')
    snapshot = _read_bytes(path.parent / RUNTIME_SNAPSHOT_NAME, MAX_METADATA_BYTES,
                           'route_attestation_snapshot_exceeds_byte_budget')
    _validate_runtime_observation(value['runtime'], snapshot, observed_route)
    return raw, value, snapshot


def _request_id(record):
    return 'request-' + cf.digest(cf.canonical({
        'position_id': record['position_id'], 'evidence_id': record['evidence_id'],
        'game_id': record['game_id'], 'sha256': record['sha256'],
    }))


def _load_input_records(data_root, source_path, source_sha256, typed_packet_path,
                        input_manifest_path):
    """Recompute each no-forward packet before it can be frozen or dispatched."""
    _require_digest(source_sha256, 'invalid_source_receipt_sha256')
    data_root, source_path = Path(data_root), Path(source_path)
    typed_packet_path, input_manifest_path = Path(typed_packet_path), Path(input_manifest_path)
    cf.require(data_root.is_dir() and source_path.is_file() and typed_packet_path.is_file() and
               input_manifest_path.is_file(), 'missing_frozen_input_dependency')
    cf.require(cf.file_digest(source_path) == source_sha256, 'source_receipt_sha256_changed')
    value = _read_json(input_manifest_path)
    cf.exact_keys(value, INPUT_MANIFEST_FIELDS, 'invalid_input_manifest_shape')
    cf.require(value['schema'] == 'chess-no-forward-development-input-manifest/v1' and
               value['commentary_gate_passed'] is False and
               value['heldout_outcomes_scored'] == value['model_calls'] ==
               value['new_engine_calls'] == 0 and value['source_split'] == 'dev',
               'input_manifest_is_not_development_only')
    _require_digest(value['implementation_sha256'], 'invalid_input_manifest_implementation_sha')
    _require_digest(value['source_receipt_sha256'], 'invalid_input_manifest_source_sha')
    _require_digest(value['typed_packet_sha256'], 'invalid_input_manifest_typed_sha')
    cf.require(value['source_receipt_sha256'] == source_sha256,
               'input_manifest_source_binding_changed')
    cf.require(type(value['requested']) is int and type(value['retained']) is int and
               value['requested'] == value['retained'] == len(value['records']) and
               1 <= len(value['records']) <= MAX_REQUESTS,
               'invalid_input_request_denominator')
    _require_string(value['selection'], 'invalid_input_selection')
    typed = _read_json(typed_packet_path, MAX_METADATA_BYTES)
    cf.require(cf.digest(cf.canonical(typed)) == value['typed_packet_sha256'],
               'typed_packet_binding_changed')
    records = []
    seen_position, seen_evidence, seen_game, seen_request = set(), set(), set(), set()
    for ordinal, record in enumerate(value['records']):
        cf.exact_keys(record, INPUT_RECORD_FIELDS, 'invalid_input_record_shape')
        _require_nonnegative_int(record['bytes'], 'invalid_input_record_bytes')
        _require_string(record['position_id'], 'invalid_input_position_id')
        _require_string(record['evidence_id'], 'invalid_input_evidence_id')
        _require_string(record['game_id'], 'invalid_input_game_id')
        _require_digest(record['sha256'], 'invalid_input_record_sha')
        packet_path = _from_root_relative(record['path'])
        raw = _read_bytes(packet_path, MAX_PACKET_BYTES, 'input_packet_exceeds_byte_budget')
        cf.require(len(raw) == record['bytes'] and cf.digest(raw) == record['sha256'],
                   'input_packet_file_binding_changed')
        try:
            packet = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('invalid_input_packet_json') from error
        canonical = no_forward.encode_no_forward_packet(
            data_root, source_path, source_sha256, typed, record['position_id'],
            record['evidence_id'], packet,
        )
        cf.require(raw == canonical, 'input_packet_is_not_canonical_no_forward_bytes')
        request = {
            'ordinal': ordinal,
            'request_id': _request_id(record),
            'input_path': 'inputs/{:02d}.packet.json'.format(ordinal),
            'input_sha256': record['sha256'],
            'input_bytes': record['bytes'],
            'position_id': record['position_id'],
            'evidence_id': record['evidence_id'],
            'game_id': record['game_id'],
        }
        for observed, bucket, message in (
            (record['position_id'], seen_position, 'duplicate_input_position'),
            (record['evidence_id'], seen_evidence, 'duplicate_input_evidence'),
            (record['game_id'], seen_game, 'duplicate_input_game'),
            (request['request_id'], seen_request, 'duplicate_input_request'),
        ):
            cf.require(observed not in bucket, message)
            bucket.add(observed)
        records.append((request, raw))
    return value, typed, records


def _validate_manifest_shape(value):
    cf.exact_keys(value, MANIFEST_FIELDS, 'invalid_generation_manifest_shape')
    cf.require(value['schema'] == SCHEMA and value['run_state'] == 'frozen' and
               type(value['created_at_ns']) is int and value['created_at_ns'] > 0,
               'invalid_generation_manifest_identity')
    cf.require(value['commentary_capability_gate_passed'] is False and
               value['commentary_quality_evaluated'] is False and
               value['independent_acceptance'] is False and
               value['model_calls'] == value['new_engine_calls'] ==
               value['heldout_outcomes_scored'] == 0,
               'invalid_generation_manifest_claim_boundary')
    for name in ('data_root', 'source_receipt_path', 'typed_packet_path',
                 'input_manifest_path', 'route_attestation_path',
                 'route_attestation_snapshot_path'):
        _require_string(value[name], 'invalid_manifest_' + name, maximum=1024)
    for name in ('source_receipt_sha256', 'typed_packet_file_sha256',
                 'typed_packet_canonical_sha256', 'input_manifest_sha256',
                 'route_attestation_sha256', 'route_attestation_snapshot_sha256',
                 'declared_route_sha256',
                 'observed_route_sha256'):
        _require_digest(value[name], 'invalid_manifest_' + name)
    _validate_route(value['declared_route'])
    _validate_route(value['observed_route'])
    cf.require(cf.canonical(value['declared_route']) == cf.canonical(value['observed_route']),
               'manifest_declared_observed_route_mismatch')
    cf.require(value['declared_route_sha256'] == cf.digest(cf.canonical(value['declared_route'])) and
               value['observed_route_sha256'] == cf.digest(cf.canonical(value['observed_route'])),
               'manifest_route_digest_mismatch')
    cf.exact_keys(value['implementation'], IMPLEMENTATION_FIELDS,
                  'invalid_generation_implementation_shape')
    for digest in value['implementation'].values():
        _require_digest(digest, 'invalid_generation_implementation_sha')
    cf.require(isinstance(value['requests'], list) and 1 <= len(value['requests']) <= MAX_REQUESTS,
               'invalid_generation_request_count')
    for ordinal, request in enumerate(value['requests']):
        cf.exact_keys(request, REQUEST_FIELDS, 'invalid_generation_request_shape')
        cf.require(request['ordinal'] == ordinal and request['input_path'] ==
                   'inputs/{:02d}.packet.json'.format(ordinal),
                   'invalid_generation_request_order')
        _require_string(request['request_id'], 'invalid_generation_request_id')
        _require_digest(request['input_sha256'], 'invalid_generation_request_sha')
        _require_nonnegative_int(request['input_bytes'], 'invalid_generation_request_bytes')
        for field in ('position_id', 'evidence_id', 'game_id'):
            _require_string(request[field], 'invalid_generation_request_' + field)


def freeze_run(data_root, source_path, source_sha256, typed_packet_path,
               input_manifest_path, declared_route, observed_route,
               route_attestation_path, output_dir):
    """Create immutable inputs and a pre-call local-route binding.

    ``observed_route`` may not be inferred from the declaration: it has to be
    present in the separately retained attestation.  Thus absent/stale 32k
    runtime details stop the run before any transport exists.
    """
    _validate_route(declared_route)
    _validate_route(observed_route)
    cf.require(cf.canonical(declared_route) == cf.canonical(observed_route),
               'declared_observed_route_mismatch')
    attestation_raw, _, snapshot_raw = _load_route_attestation(
        route_attestation_path, observed_route,
    )
    input_manifest, typed, records = _load_input_records(
        data_root, source_path, source_sha256, typed_packet_path, input_manifest_path,
    )
    run_dir = Path(output_dir)
    cf.require(not run_dir.exists(), 'generation_run_directory_already_exists')
    manifest = {
        'schema': SCHEMA,
        'created_at_ns': time.time_ns(),
        'run_state': 'frozen',
        'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False,
        'independent_acceptance': False,
        'model_calls': 0,
        'new_engine_calls': 0,
        'heldout_outcomes_scored': 0,
        'data_root': _root_relative(data_root),
        'source_receipt_path': _root_relative(source_path),
        'source_receipt_sha256': source_sha256,
        'typed_packet_path': _root_relative(typed_packet_path),
        'typed_packet_file_sha256': cf.file_digest(Path(typed_packet_path)),
        'typed_packet_canonical_sha256': cf.digest(cf.canonical(typed)),
        'input_manifest_path': _root_relative(input_manifest_path),
        'input_manifest_sha256': cf.file_digest(Path(input_manifest_path)),
        'route_attestation_path': 'route-attestation.json',
        'route_attestation_sha256': cf.digest(attestation_raw),
        'route_attestation_snapshot_path': RUNTIME_SNAPSHOT_NAME,
        'route_attestation_snapshot_sha256': cf.digest(snapshot_raw),
        'declared_route': declared_route,
        'declared_route_sha256': cf.digest(cf.canonical(declared_route)),
        'observed_route': observed_route,
        'observed_route_sha256': cf.digest(cf.canonical(observed_route)),
        'implementation': _implementation_hashes(),
        'requests': [request for request, _ in records],
    }
    _validate_manifest_shape(manifest)
    # All checks are complete before creating a directory that could later look runnable.
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_create(run_dir / manifest['route_attestation_path'], attestation_raw,
                        MAX_METADATA_BYTES, 'route_attestation_exceeds_byte_budget')
    _write_bytes_create(run_dir / manifest['route_attestation_snapshot_path'], snapshot_raw,
                        MAX_METADATA_BYTES, 'route_attestation_snapshot_exceeds_byte_budget')
    for request, raw in records:
        _write_bytes_create(_from_run_relative(run_dir, request['input_path']), raw,
                            MAX_PACKET_BYTES, 'input_packet_exceeds_byte_budget')
    write_json(manifest, run_dir / 'manifest.json')
    return manifest


def _load_manifest(run_dir):
    run_dir = Path(run_dir)
    cf.require(run_dir.is_dir(), 'generation_run_directory_missing')
    value = _read_json(run_dir / 'manifest.json')
    _validate_manifest_shape(value)
    return value


def _verify_frozen_run(data_root, source_path, source_sha256, typed_packet_path, run_dir):
    """Revalidate immutable source, packets and route before inspection or a call."""
    manifest = _load_manifest(run_dir)
    cf.require(manifest['implementation'] == _implementation_hashes(),
               'generation_implementation_changed_since_freeze')
    cf.require(_root_relative(data_root) == manifest['data_root'] and
               _root_relative(source_path) == manifest['source_receipt_path'] and
               _root_relative(typed_packet_path) == manifest['typed_packet_path'],
               'generation_source_path_changed_since_freeze')
    cf.require(source_sha256 == manifest['source_receipt_sha256'] and
               cf.file_digest(Path(source_path)) == source_sha256,
               'generation_source_receipt_changed_since_freeze')
    cf.require(cf.file_digest(Path(typed_packet_path)) == manifest['typed_packet_file_sha256'],
               'generation_typed_packet_file_changed_since_freeze')
    input_manifest_path = _from_root_relative(manifest['input_manifest_path'])
    cf.require(cf.file_digest(input_manifest_path) == manifest['input_manifest_sha256'],
               'generation_input_manifest_changed_since_freeze')
    attestation_path = _from_run_relative(run_dir, manifest['route_attestation_path'])
    attestation_raw, _, snapshot_raw = _load_route_attestation(
        attestation_path, manifest['observed_route'],
    )
    cf.require(cf.digest(attestation_raw) == manifest['route_attestation_sha256'],
               'generation_route_attestation_changed_since_freeze')
    snapshot_path = _from_run_relative(run_dir, manifest['route_attestation_snapshot_path'])
    cf.require(snapshot_path == attestation_path.parent / RUNTIME_SNAPSHOT_NAME and
               cf.digest(snapshot_raw) == manifest['route_attestation_snapshot_sha256'],
               'generation_route_attestation_snapshot_changed_since_freeze')
    input_manifest, typed, current_records = _load_input_records(
        data_root, source_path, source_sha256, typed_packet_path, input_manifest_path,
    )
    del input_manifest
    cf.require(cf.digest(cf.canonical(typed)) == manifest['typed_packet_canonical_sha256'],
               'generation_typed_packet_canonical_changed_since_freeze')
    cf.require(len(current_records) == len(manifest['requests']),
               'generation_request_denominator_changed_since_freeze')
    for frozen, (current, raw) in zip(manifest['requests'], current_records):
        cf.require(cf.canonical(frozen) == cf.canonical(current),
                   'generation_request_binding_changed_since_freeze')
        frozen_path = _from_run_relative(run_dir, frozen['input_path'])
        copied = _read_bytes(frozen_path, MAX_PACKET_BYTES, 'frozen_input_packet_exceeds_byte_budget')
        cf.require(copied == raw and len(copied) == frozen['input_bytes'] and
                   cf.digest(copied) == frozen['input_sha256'],
                   'frozen_input_packet_changed_since_freeze')
        try:
            packet = json.loads(copied)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('frozen_input_packet_invalid_json') from error
        canonical = no_forward.encode_no_forward_packet(
            Path(data_root), Path(source_path), source_sha256, typed,
            frozen['position_id'], frozen['evidence_id'], packet,
        )
        cf.require(canonical == copied, 'frozen_input_packet_not_no_forward')
    return manifest, typed


def _attempt_path(run_dir, ordinal):
    return Path(run_dir) / 'attempts' / '{:02d}.json'.format(ordinal)


def _raw_path(run_dir, ordinal):
    return Path(run_dir) / 'raw' / '{:02d}.bin'.format(ordinal)


def _error_value(error):
    return {
        'type': type(error).__name__,
        'message': str(error)[:500] or type(error).__name__,
    }


def _base_outcome(request, *, status, input_dispatched, model_call_began,
                  raw_path=None, raw_sha256=None, raw_bytes=0,
                  raw_classification='not_run', observed_route=None,
                  observed_route_sha256=None,
                  transport_status='not_run', latency_ns=0, error=None):
    outcome = {
        'ordinal': request['ordinal'],
        'request_id': request['request_id'],
        'input_path': request['input_path'],
        'input_sha256': request['input_sha256'],
        'input_bytes': request['input_bytes'],
        'position_id': request['position_id'],
        'evidence_id': request['evidence_id'],
        'game_id': request['game_id'],
        'status': status,
        'input_dispatched': input_dispatched,
        'model_call_began': model_call_began,
        'raw_path': raw_path,
        'raw_sha256': raw_sha256,
        'raw_bytes': raw_bytes,
        'raw_classification': raw_classification,
        'observed_route': observed_route,
        'observed_route_sha256': observed_route_sha256,
        'transport_status': transport_status,
        'latency_ns': latency_ns,
        'error': error,
    }
    cf.exact_keys(outcome, OUTCOME_FIELDS, 'invalid_generated_outcome_shape')
    return outcome


def _classify_raw(raw):
    if raw == b'':
        return 'empty'
    try:
        decoded = raw.decode('utf-8')
    except UnicodeDecodeError:
        return 'raw_text'
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return 'malformed_json'
    if isinstance(parsed, dict) and set(parsed) == {'status', 'reason'} and \
            parsed['status'] == 'abstain' and type(parsed['reason']) is str:
        return 'declared_abstention'
    return 'raw_text'


def _coerce_raw(value):
    if value is None:
        return b''
    if isinstance(value, bytes):
        return value
    if type(value) is str:
        return value.encode('utf-8')
    raise ValueError('transport_raw_output_must_be_bytes_string_or_null')


def _write_raw(run_dir, ordinal, raw):
    cf.require(len(raw) <= MAX_RAW_BYTES, 'transport_raw_output_exceeds_byte_budget')
    path = _raw_path(run_dir, ordinal)
    _write_bytes_create(path, raw, MAX_RAW_BYTES, 'transport_raw_output_exceeds_byte_budget')
    return 'raw/{:02d}.bin'.format(ordinal), cf.digest(raw), len(raw)


def _validate_transport_response(value):
    cf.exact_keys(value, ('raw_output', 'observed_route', 'transport_status'),
                  'invalid_transport_response_shape')
    _validate_route_claim_shape(value['observed_route'])
    cf.require(value['transport_status'] in ('completed', 'http_error', 'response_error'),
               'invalid_transport_status')


def _run_one(data_root, source_path, source_sha256, typed, run_dir, request, transport):
    """Dispatch one canonical packet exactly once and retain its unjudged output."""
    started = time.perf_counter_ns()
    try:
        raw = _read_bytes(_from_run_relative(run_dir, request['input_path']), MAX_PACKET_BYTES,
                          'frozen_input_packet_exceeds_byte_budget')
        cf.require(len(raw) == request['input_bytes'] and cf.digest(raw) == request['input_sha256'],
                   'frozen_input_packet_changed_after_preflight')
        packet = json.loads(raw)
    except (OSError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return _base_outcome(
            request, status='not_run', input_dispatched=False, model_call_began=False,
            raw_classification='not_run', transport_status='not_run',
            latency_ns=time.perf_counter_ns() - started, error=_error_value(error),
        )
    model_call_began = False

    def generator(canonical_packet):
        nonlocal model_call_began
        cf.require(type(canonical_packet) is bytes and canonical_packet == raw,
                   'generator_did_not_receive_exact_frozen_packet')
        model_call_began = True
        return transport(canonical_packet)

    try:
        response = no_forward.dispatch_no_forward(
            Path(data_root), Path(source_path), source_sha256, typed,
            request['position_id'], request['evidence_id'], packet, generator,
        )
    except Exception as error:  # A transport or boundary error is durable evidence, never a retry.
        return _base_outcome(
            request,
            status='transport_failure' if model_call_began else 'not_run',
            input_dispatched=model_call_began,
            model_call_began=model_call_began,
            raw_classification='transport_failure' if model_call_began else 'not_run',
            transport_status='exception',
            latency_ns=time.perf_counter_ns() - started,
            error=_error_value(error),
        )
    raw_path = raw_sha256 = observed_sha = None
    raw_bytes = 0
    classification = 'transport_failure'
    observed_route = None
    transport_status = 'invalid_response'
    try:
        # Preserve raw output first whenever the callback supplied a coercible value.
        # Route/status defects are metadata failures, not permission to discard text.
        if isinstance(response, dict) and 'raw_output' in response:
            raw_output = _coerce_raw(response['raw_output'])
            raw_path, raw_sha256, raw_bytes = _write_raw(run_dir, request['ordinal'], raw_output)
            classification = _classify_raw(raw_output)
        _validate_transport_response(response)
        observed_route = response['observed_route']
        observed_sha = cf.digest(cf.canonical(observed_route))
        transport_status = response['transport_status']
        if cf.canonical(observed_route) != cf.canonical(_load_manifest(run_dir)['observed_route']):
            return _base_outcome(
                request, status='identity_mismatch', input_dispatched=True,
                model_call_began=True, raw_path=raw_path, raw_sha256=raw_sha256,
                raw_bytes=raw_bytes, raw_classification=classification,
                observed_route=observed_route, observed_route_sha256=observed_sha,
                transport_status=transport_status,
                latency_ns=time.perf_counter_ns() - started,
                error={'type': 'RouteIdentityMismatch',
                       'message': 'transport observed route differs from frozen route'},
            )
        if transport_status != 'completed':
            return _base_outcome(
                request, status='transport_failure', input_dispatched=True,
                model_call_began=True, raw_path=raw_path, raw_sha256=raw_sha256,
                raw_bytes=raw_bytes, raw_classification=classification,
                observed_route=observed_route, observed_route_sha256=observed_sha,
                transport_status=transport_status,
                latency_ns=time.perf_counter_ns() - started,
                error={'type': 'TransportStatus',
                       'message': 'transport returned ' + transport_status},
            )
        return _base_outcome(
            request, status='captured', input_dispatched=True, model_call_began=True,
            raw_path=raw_path, raw_sha256=raw_sha256, raw_bytes=raw_bytes,
            raw_classification=classification, observed_route=observed_route,
            observed_route_sha256=observed_sha,
            transport_status='completed', latency_ns=time.perf_counter_ns() - started,
        )
    except Exception as error:
        # If a raw write succeeded before malformed route/status metadata was noticed,
        # it remains in raw/ even though this request cannot be accepted as captured.
        return _base_outcome(
            request, status='transport_failure', input_dispatched=True,
            model_call_began=True, raw_path=raw_path, raw_sha256=raw_sha256,
            raw_bytes=raw_bytes, raw_classification=classification,
            transport_status=transport_status, latency_ns=time.perf_counter_ns() - started,
            error=_error_value(error),
        )


def _load_attempts(run_dir, manifest):
    values = {}
    for request in manifest['requests']:
        path = _attempt_path(run_dir, request['ordinal'])
        if path.exists():
            values[request['ordinal']] = _read_json(path)
    return values


def _validate_outcome(outcome, request, run_dir, expected_route):
    cf.exact_keys(outcome, OUTCOME_FIELDS, 'invalid_outcome_shape')
    for field in REQUEST_FIELDS:
        cf.require(outcome[field] == request[field], 'outcome_request_binding_changed')
    cf.require(outcome['status'] in ('captured', 'transport_failure', 'identity_mismatch', 'not_run'),
               'invalid_outcome_status')
    cf.require(type(outcome['input_dispatched']) is bool and
               type(outcome['model_call_began']) is bool,
               'invalid_outcome_call_flags')
    _require_nonnegative_int(outcome['raw_bytes'], 'invalid_outcome_raw_bytes')
    _require_nonnegative_int(outcome['latency_ns'], 'invalid_outcome_latency')
    cf.require(outcome['raw_classification'] in (
        'raw_text', 'malformed_json', 'declared_abstention', 'empty',
        'transport_failure', 'not_run',
    ), 'invalid_outcome_raw_classification')
    _require_string(outcome['transport_status'], 'invalid_outcome_transport_status')
    if outcome['raw_path'] is None:
        cf.require(outcome['raw_sha256'] is None and outcome['raw_bytes'] == 0,
                   'missing_raw_artifact_binding')
    else:
        cf.require(outcome['raw_path'] == 'raw/{:02d}.bin'.format(request['ordinal']),
                   'invalid_outcome_raw_path')
        _require_digest(outcome['raw_sha256'], 'invalid_outcome_raw_sha')
        raw = _read_bytes(_from_run_relative(run_dir, outcome['raw_path']), MAX_RAW_BYTES,
                          'outcome_raw_artifact_exceeds_byte_budget')
        cf.require(len(raw) == outcome['raw_bytes'] and cf.digest(raw) == outcome['raw_sha256'],
                   'outcome_raw_artifact_binding_changed')
    if outcome['observed_route'] is None:
        cf.require(outcome['observed_route_sha256'] is None,
                   'missing_observed_route_binding')
    else:
        _validate_route_claim_shape(outcome['observed_route'])
        expected_observed_sha = cf.digest(cf.canonical(outcome['observed_route']))
        cf.require(outcome['observed_route_sha256'] == expected_observed_sha,
                   'outcome_observed_route_digest_changed')
    if outcome['observed_route_sha256'] is not None:
        _require_digest(outcome['observed_route_sha256'], 'invalid_outcome_observed_route_sha')
    if outcome['error'] is None:
        cf.require(outcome['status'] == 'captured', 'missing_failure_error')
    else:
        cf.exact_keys(outcome['error'], ('type', 'message'), 'invalid_outcome_error_shape')
        _require_string(outcome['error']['type'], 'invalid_outcome_error_type')
        _require_string(outcome['error']['message'], 'invalid_outcome_error_message', maximum=500)
        cf.require(outcome['status'] != 'captured', 'captured_outcome_has_error')
    if outcome['status'] == 'not_run':
        cf.require(not outcome['model_call_began'] and not outcome['input_dispatched'],
                   'not_run_outcome_attempted_a_call')
    else:
        cf.require(outcome['model_call_began'] and outcome['input_dispatched'],
                   'attempted_outcome_missing_call_flag')
    if outcome['status'] == 'captured':
        cf.require(outcome['observed_route'] is not None and
                   cf.canonical(outcome['observed_route']) == cf.canonical(expected_route),
                   'captured_outcome_route_is_not_frozen_route')
    if outcome['status'] == 'identity_mismatch':
        cf.require(outcome['observed_route'] is not None and
                   cf.canonical(outcome['observed_route']) != cf.canonical(expected_route),
                   'identity_mismatch_outcome_does_not_retain_foreign_route')


def _write_missing_not_run(run_dir, manifest, reason, error_type='PreflightValidationError'):
    existing = _load_attempts(run_dir, manifest)
    for request in manifest['requests']:
        if request['ordinal'] not in existing:
            outcome = _base_outcome(
                request, status='not_run', input_dispatched=False, model_call_began=False,
                raw_classification='not_run', transport_status='not_run',
                error={'type': error_type, 'message': reason[:500] or error_type},
            )
            write_json(outcome, _attempt_path(run_dir, request['ordinal']))


def _finalize(run_dir, manifest):
    result_path = Path(run_dir) / 'results.json'
    cf.require(not result_path.exists(), 'generation_results_already_exist')
    attempts = _load_attempts(run_dir, manifest)
    cf.require(set(attempts) == set(range(len(manifest['requests']))),
               'generation_results_have_unaccounted_requests')
    outcomes = []
    for request in manifest['requests']:
        outcome = attempts[request['ordinal']]
        _validate_outcome(outcome, request, run_dir, manifest['observed_route'])
        outcomes.append(outcome)
    status_counts = dict(sorted(Counter(outcome['status'] for outcome in outcomes).items()))
    raw_counts = dict(sorted(Counter(outcome['raw_classification'] for outcome in outcomes).items()))
    result = {
        'schema': RESULT_SCHEMA,
        'manifest_sha256': cf.file_digest(Path(run_dir) / 'manifest.json'),
        'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False,
        'independent_acceptance': False,
        'requested': len(outcomes),
        'accounted': len(outcomes),
        'model_calls': sum(outcome['model_call_began'] for outcome in outcomes),
        'new_engine_calls': 0,
        'heldout_outcomes_scored': 0,
        'status_counts': status_counts,
        'raw_classification_counts': raw_counts,
        'outcomes': outcomes,
        'limitations': list(LIMITATIONS),
    }
    write_json(result, result_path)
    return result


def seal_interrupted_run(run_dir, reason='interrupted_or_identity_mismatch'):
    """Account for untouched frozen requests without ever resuming transport calls."""
    manifest = _load_manifest(run_dir)
    cf.require(not (Path(run_dir) / 'results.json').exists(), 'generation_results_already_exist')
    _write_missing_not_run(run_dir, manifest, reason, error_type='RunSealed')
    return _finalize(run_dir, manifest)


def execute_frozen_run(data_root, source_path, source_sha256, typed_packet_path,
                       run_dir, transport):
    """Execute a pre-frozen run through an injected transport exactly once per input.

    The method refuses any existing attempt/raw/result artifact.  A changed packet,
    source, attestation or route creates durable ``not_run`` outcomes and invokes
    the transport zero times.  A route identity mismatch is retained and seals the
    remaining denominator without a fallback route.
    """
    manifest = _load_manifest(run_dir)
    run_dir = Path(run_dir)
    cf.require(not (run_dir / 'results.json').exists() and not any(
        any((run_dir / name).glob('*')) for name in ('attempts', 'raw')
    ), 'generation_run_already_started')
    try:
        manifest, typed = _verify_frozen_run(
            data_root, source_path, source_sha256, typed_packet_path, run_dir,
        )
    except (OSError, ValueError, TypeError) as error:
        _write_missing_not_run(run_dir, manifest, str(error))
        return _finalize(run_dir, manifest)
    for request in manifest['requests']:
        outcome = _run_one(
            data_root, source_path, source_sha256, typed, run_dir, request, transport,
        )
        write_json(outcome, _attempt_path(run_dir, request['ordinal']))
        if outcome['status'] in ('identity_mismatch', 'not_run'):
            return seal_interrupted_run(run_dir, outcome['error']['message'])
    return _finalize(run_dir, manifest)


def verify_results(data_root, source_path, source_sha256, typed_packet_path, run_dir):
    """Mechanically verify a completed capture; this is not commentary evaluation."""
    manifest, _ = _verify_frozen_run(data_root, source_path, source_sha256,
                                     typed_packet_path, run_dir)
    result = _read_json(Path(run_dir) / 'results.json')
    cf.exact_keys(result, RESULT_FIELDS, 'invalid_generation_results_shape')
    cf.require(result['schema'] == RESULT_SCHEMA and
               result['manifest_sha256'] == cf.file_digest(Path(run_dir) / 'manifest.json') and
               result['commentary_capability_gate_passed'] is False and
               result['commentary_quality_evaluated'] is False and
               result['independent_acceptance'] is False and
               result['new_engine_calls'] == result['heldout_outcomes_scored'] == 0,
               'invalid_generation_results_boundary')
    cf.require(result['requested'] == result['accounted'] == len(manifest['requests']) and
               isinstance(result['outcomes'], list) and len(result['outcomes']) == len(manifest['requests']),
               'generation_results_denominator_changed')
    for request, outcome in zip(manifest['requests'], result['outcomes']):
        _validate_outcome(outcome, request, run_dir, manifest['observed_route'])
        retained = _read_json(_attempt_path(run_dir, request['ordinal']))
        cf.require(cf.canonical(retained) == cf.canonical(outcome),
                   'generation_result_outcome_differs_from_retained_attempt')
    statuses = dict(sorted(Counter(row['status'] for row in result['outcomes']).items()))
    classifications = dict(sorted(Counter(row['raw_classification'] for row in result['outcomes']).items()))
    cf.require(result['status_counts'] == statuses and
               result['raw_classification_counts'] == classifications and
               result['model_calls'] == sum(row['model_call_began'] for row in result['outcomes']) and
               result['limitations'] == LIMITATIONS,
               'generation_result_summary_changed')
    return {
        'schema': RESULT_SCHEMA,
        'integrity_passed': True,
        'requested': result['requested'],
        'model_calls': result['model_calls'],
        'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def build_loopback_transport(frozen_route, *, opener=None):
    """Return the production-style local transport; it makes no call until invoked.

    The caller must supply the separately frozen observed route as well.  No
    credentials, redirects, proxies, endpoint switching or retry behavior is
    available here.
    """
    _validate_route(frozen_route)
    if opener is None:
        opener = build_opener(ProxyHandler({}), _NoRedirect())
    endpoint = frozen_route['endpoint'] + '/chat/completions'

    def transport(canonical_packet):
        cf.require(type(canonical_packet) is bytes and len(canonical_packet) <= MAX_PACKET_BYTES,
                   'invalid_loopback_transport_input')
        content = canonical_packet.decode('utf-8')
        payload = {
            'model': frozen_route['model_id'],
            'messages': [{'role': 'user', 'content': content}],
            'stream': False,
            'temperature': frozen_route['sampling']['temperature'],
            'top_p': frozen_route['sampling']['top_p'],
            'max_tokens': frozen_route['sampling']['max_output_tokens'],
            'seed': frozen_route['seed'],
            'reasoning_effort': frozen_route['reasoning']['effort'],
        }
        request = Request(endpoint, data=cf.canonical(payload),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            response = opener.open(request, timeout=frozen_route['timeout_seconds'])
        except HTTPError as error:
            response = error
        with response:
            body = response.read(MAX_RAW_BYTES + 1)
            status = getattr(response, 'status', 200)
        cf.require(len(body) <= MAX_RAW_BYTES, 'loopback_response_exceeds_byte_budget')
        return {
            'raw_output': body,
            'observed_route': frozen_route,
            'transport_status': 'completed' if 200 <= status < 300 else 'http_error',
        }

    return transport


def _route_file(path):
    value = _read_json(path)
    _validate_route(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'verify'))
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--typed-packet', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--input-manifest', type=Path)
    parser.add_argument('--declared-route', type=Path)
    parser.add_argument('--observed-route', type=Path)
    parser.add_argument('--route-attestation', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'freeze':
        cf.require(args.input_manifest is not None and args.declared_route is not None and
                   args.observed_route is not None and args.route_attestation is not None,
                   'freeze_requires_inputs_routes_and_attestation')
        manifest = freeze_run(
            args.data, args.source, args.source_sha256, args.typed_packet,
            args.input_manifest, _route_file(args.declared_route),
            _route_file(args.observed_route), args.route_attestation, args.run_dir,
        )
        result = {
            'schema': SCHEMA,
            'frozen': True,
            'requested': len(manifest['requests']),
            'model_calls': 0,
            'new_engine_calls': 0,
            'commentary_capability_gate_passed': False,
        }
    else:
        result = verify_results(args.data, args.source, args.source_sha256,
                                args.typed_packet, args.run_dir)
    print(cf.canonical(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
