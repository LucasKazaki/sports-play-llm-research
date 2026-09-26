"""Create-only, inference-free capture of the local chess route readiness state.

This utility is intentionally narrower than the no-forward generator.  It
performs one GET against LM Studio's fixed loopback readiness endpoint, never
posts a prompt, never starts Stockfish, and never reads Studio configuration or
operator APIs.  The resulting v2 attestation binds the runner to retained
runtime metadata before any future chess packet can be frozen.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_generation_runner as runner


SCHEMA = 'chess-local-route-attestation-capture/v1'
RECEIPT_NAME = 'capture-receipt.json'
OBSERVED_ROUTE_NAME = 'observed-route.json'
ATTESTATION_NAME = 'route-attestation.json'
SNAPSHOT_NAME = runner.RUNTIME_SNAPSHOT_NAME
ARTIFACT_ROOT = ROOT / 'artifacts/chess-local-route-attestation-v1'
MAX_SNAPSHOT_BYTES = 512 * 1024
REQUEST_TIMEOUT_SECONDS = 15
LIMITATIONS = [
    'This capture performs one local GET only; it sends no prompt and makes zero model or engine calls.',
    'The retained readiness snapshot attests loaded instance identity, context, serialism and supported reasoning options at capture time.',
    'Sampling, seed, request schema, timeout, retry policy and route ID are explicitly declared by the frozen runner because LM Studio readiness metadata does not expose them.',
    'This is not a model-weight hash, future-response identity proof, or commentary-quality result.',
]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _write_create(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value)


def _write_json_create(path, value):
    _write_create(path, cf.canonical(value) + b'\n')


def _inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError('path_outside_allowed_root') from error
    return path


def _root_relative(path):
    return _inside(ROOT, path).relative_to(ROOT).as_posix()


def _load_declared_route(path):
    path = _inside(ROOT, path)
    raw = path.read_bytes()
    cf.require(0 < len(raw) <= MAX_SNAPSHOT_BYTES,
               'declared_route_exceeds_byte_budget')
    try:
        route = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_declared_route_json') from error
    runner._validate_route(route)
    return path, raw, route


def _new_output_dir(path, *, require_artifact_root):
    path = Path(path).resolve()
    if require_artifact_root:
        _inside(ARTIFACT_ROOT, path)
        cf.require(path != ARTIFACT_ROOT.resolve(), 'route_attestation_output_needs_unique_child')
    path.mkdir(parents=True, exist_ok=False)
    return path


def _default_opener():
    return build_opener(ProxyHandler({}), _NoRedirect())


def _read_models_snapshot(opener, *, timeout_seconds=REQUEST_TIMEOUT_SECONDS):
    request = Request(runner.LOCAL_MODELS_URL, headers={'Accept': 'application/json'}, method='GET')
    try:
        response = opener.open(request, timeout=timeout_seconds)
    except HTTPError as error:
        response = error
    with response:
        status = int(getattr(response, 'status', getattr(response, 'code', 0)) or 0)
        body = response.read(MAX_SNAPSHOT_BYTES + 1)
    return status, body


def _error_record(error):
    return {'type': type(error).__name__, 'message': str(error)[:512]}


def _failure_receipt(captured_at, declared_path, declared_raw, *, status=None,
                     snapshot=None, error=None):
    return {
        'schema': SCHEMA,
        'status': 'unattested',
        'captured_at': captured_at,
        'models_url': runner.LOCAL_MODELS_URL,
        'request_method': 'GET',
        'http_status': status,
        'snapshot_path': SNAPSHOT_NAME if snapshot is not None else None,
        'snapshot_sha256': cf.digest(snapshot) if snapshot is not None else None,
        'snapshot_bytes': len(snapshot) if snapshot is not None else 0,
        'declared_route_path': _root_relative(declared_path),
        'declared_route_sha256': cf.digest(declared_raw),
        'error': error or {'type': 'ValueError', 'message': 'route_attestation_not_created'},
        'model_calls': 0,
        'engine_calls': 0,
        'limitations': list(LIMITATIONS),
    }


def _success_receipt(captured_at, declared_path, declared_raw, output_dir,
                     status, snapshot, attestation):
    observed = output_dir / OBSERVED_ROUTE_NAME
    attestation_path = output_dir / ATTESTATION_NAME
    return {
        'schema': SCHEMA,
        'status': 'attested',
        'captured_at': captured_at,
        'models_url': runner.LOCAL_MODELS_URL,
        'request_method': 'GET',
        'http_status': status,
        'snapshot_path': SNAPSHOT_NAME,
        'snapshot_sha256': cf.digest(snapshot),
        'snapshot_bytes': len(snapshot),
        'declared_route_path': _root_relative(declared_path),
        'declared_route_sha256': cf.digest(declared_raw),
        'observed_route_path': OBSERVED_ROUTE_NAME,
        'observed_route_sha256': cf.file_digest(observed),
        'attestation_path': ATTESTATION_NAME,
        'attestation_sha256': cf.file_digest(attestation_path),
        'runtime_observation_sha256': cf.digest(cf.canonical(attestation['runtime'])),
        'model_calls': 0,
        'engine_calls': 0,
        'limitations': list(LIMITATIONS),
    }


def capture(declared_route_path, output_dir, *, opener=None, captured_at=None,
            require_artifact_root=False):
    """Capture one safe readiness snapshot, retaining a failure receipt on drift."""
    declared_path, declared_raw, route = _load_declared_route(declared_route_path)
    output_dir = _new_output_dir(output_dir, require_artifact_root=require_artifact_root)
    captured_at = captured_at or _now()
    opener = _default_opener() if opener is None else opener
    status, raw = None, None
    try:
        status, raw = _read_models_snapshot(opener)
        cf.require(len(raw) <= MAX_SNAPSHOT_BYTES, 'route_runtime_snapshot_exceeds_byte_budget')
        _write_create(output_dir / SNAPSHOT_NAME, raw)
        cf.require(status == 200, 'route_runtime_readiness_http_status_not_200')
        runtime = runner.runtime_observation_from_models_snapshot(raw, route)
        attestation = {
            'schema': runner.ATTESTATION_SCHEMA,
            'captured_at': captured_at,
            'runtime': runtime,
            'route': route,
        }
        _write_json_create(output_dir / OBSERVED_ROUTE_NAME, route)
        _write_json_create(output_dir / ATTESTATION_NAME, attestation)
        receipt = _success_receipt(captured_at, declared_path, declared_raw, output_dir,
                                   status, raw, attestation)
    except (HTTPError, URLError, OSError, TypeError, ValueError) as error:
        if raw is not None and not (output_dir / SNAPSHOT_NAME).exists():
            _write_create(output_dir / SNAPSHOT_NAME, raw[:MAX_SNAPSHOT_BYTES])
            raw = raw[:MAX_SNAPSHOT_BYTES]
        receipt = _failure_receipt(captured_at, declared_path, declared_raw,
                                   status=status, snapshot=raw,
                                   error=_error_record(error))
    _write_json_create(output_dir / RECEIPT_NAME, receipt)
    return receipt


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid_capture_json') from error


def verify_capture(declared_route_path, output_dir):
    """Verify a retained successful capture without contacting any endpoint."""
    declared_path, declared_raw, route = _load_declared_route(declared_route_path)
    output_dir = Path(output_dir)
    receipt = _read_json(output_dir / RECEIPT_NAME)
    cf.require(receipt.get('schema') == SCHEMA and receipt.get('status') == 'attested' and
               receipt.get('model_calls') == receipt.get('engine_calls') == 0,
               'route_capture_receipt_not_successful')
    cf.require(receipt.get('declared_route_path') == _root_relative(declared_path) and
               receipt.get('declared_route_sha256') == cf.digest(declared_raw),
               'route_capture_declared_route_changed')
    snapshot = (output_dir / SNAPSHOT_NAME).read_bytes()
    cf.require(receipt.get('snapshot_path') == SNAPSHOT_NAME and
               receipt.get('snapshot_bytes') == len(snapshot) and
               receipt.get('snapshot_sha256') == cf.digest(snapshot),
               'route_capture_snapshot_changed')
    observed = _read_json(output_dir / OBSERVED_ROUTE_NAME)
    runner._validate_route(observed)
    cf.require(cf.canonical(observed) == cf.canonical(route) and
               receipt.get('observed_route_sha256') == cf.file_digest(output_dir / OBSERVED_ROUTE_NAME),
               'route_capture_observed_route_changed')
    attestation_path = output_dir / ATTESTATION_NAME
    raw, attestation, retained_snapshot = runner._load_route_attestation(attestation_path, observed)
    cf.require(retained_snapshot == snapshot and
               receipt.get('attestation_sha256') == cf.digest(raw) and
               cf.canonical(attestation['route']) == cf.canonical(route),
               'route_capture_attestation_changed')
    return {
        'schema': SCHEMA,
        'verified': True,
        'model_calls': 0,
        'engine_calls': 0,
        'attestation_sha256': cf.digest(raw),
        'snapshot_sha256': cf.digest(snapshot),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('capture', 'verify'))
    parser.add_argument('--declared-route', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'capture':
            result = capture(args.declared_route, args.output_dir,
                             require_artifact_root=True)
            exit_code = 0 if result['status'] == 'attested' else 1
        else:
            result = verify_capture(args.declared_route, args.output_dir)
            exit_code = 0
    except (HTTPError, URLError, OSError, TypeError, ValueError) as error:
        result = {
            'schema': SCHEMA,
            'status': 'verification_failed',
            'error': _error_record(error),
            'model_calls': 0,
            'engine_calls': 0,
        }
        exit_code = 1
    print(cf.canonical(result).decode('utf-8'))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
