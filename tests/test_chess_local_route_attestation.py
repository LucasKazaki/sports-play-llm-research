"""Offline checks for the snapshot-bound local chess route attestation."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_local_route_attestation as capture
import chess_no_forward_generation_runner as runner


ROUTE = ROOT / 'research/chess-local-route-131k-v1.json'


def catalog():
    return {
        'models': [{
            'key': runner.LOCAL_MODEL_CATALOG_KEY,
            'max_context_length': 131072,
            'loaded_instances': [{
                'id': 'loops-cpu-gpt-oss-20b',
                'config': {'context_length': 131072, 'parallel': 1},
            }],
            'capabilities': {
                'reasoning': {
                    'allowed_options': ['low', 'medium', 'high'],
                    'default': 'low',
                },
            },
        }],
    }


class Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        assert limit == capture.MAX_SNAPSHOT_BYTES + 1
        return self._body


class Opener:
    def __init__(self, status=200, body=None):
        self.status = status
        if isinstance(body, bytes):
            self.body = body
        else:
            self.body = json.dumps(catalog() if body is None else body,
                                   sort_keys=True, separators=(',', ':')).encode('utf-8')
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), request.data, timeout))
        return Response(self.status, self.body)


def test_capture_binds_the_live_metadata_snapshot_without_a_model_call(tmp_path):
    opener = Opener()
    output = tmp_path / 'capture'
    receipt = capture.capture(ROUTE, output, opener=opener,
                              captured_at='2026-09-23T10:35:00Z')
    assert opener.calls == [(runner.LOCAL_MODELS_URL, 'GET', None,
                             capture.REQUEST_TIMEOUT_SECONDS)]
    assert receipt['status'] == 'attested'
    assert receipt['model_calls'] == receipt['engine_calls'] == 0
    assert receipt['snapshot_path'] == runner.RUNTIME_SNAPSHOT_NAME
    assert receipt['declared_route_path'] == 'research/chess-local-route-131k-v1.json'
    assert (output / runner.RUNTIME_SNAPSHOT_NAME).is_file()
    assert (output / 'observed-route.json').is_file()
    assert (output / 'route-attestation.json').is_file()
    attestation = json.loads((output / 'route-attestation.json').read_bytes())
    runtime = attestation['runtime']
    assert attestation['schema'] == runner.ATTESTATION_SCHEMA
    assert runtime['loaded_instance_id'] == 'loops-cpu-gpt-oss-20b'
    assert runtime['loaded_context_window_tokens'] == 131072
    assert runtime['loaded_parallel'] == 1
    assert runtime['reasoning_allowed_options'] == ['low', 'medium', 'high']
    assert runtime['declared_request_fields'] == list(runner.DECLARED_REQUEST_FIELDS)
    assert capture.verify_capture(ROUTE, output)['verified'] is True


@pytest.mark.parametrize('mutate', [
    lambda value: value['models'][0]['loaded_instances'][0]['config'].__setitem__('context_length', 32768),
    lambda value: value['models'][0]['loaded_instances'][0]['config'].__setitem__('parallel', 2),
    lambda value: value['models'][0]['loaded_instances'][0].__setitem__('id', 'foreign-model'),
    lambda value: value['models'][0]['capabilities'].__setitem__(
        'reasoning', {'allowed_options': ['medium'], 'default': 'medium'}),
    lambda value: value['models'][0]['loaded_instances'].append(copy.deepcopy(
        value['models'][0]['loaded_instances'][0])),
    lambda value: value['models'][0].__setitem__('key', 'foreign-catalog-key'),
])
def test_invalid_runtime_metadata_retains_a_failure_without_an_admissible_attestation(tmp_path, mutate):
    body = catalog()
    mutate(body)
    output = tmp_path / 'capture'
    receipt = capture.capture(ROUTE, output, opener=Opener(body=body),
                              captured_at='2026-09-23T10:35:00Z')
    assert receipt['status'] == 'unattested'
    assert receipt['model_calls'] == receipt['engine_calls'] == 0
    assert (output / runner.RUNTIME_SNAPSHOT_NAME).is_file()
    assert not (output / 'route-attestation.json').exists()
    assert not (output / 'observed-route.json').exists()


def test_malformed_or_failed_readiness_response_is_retained_but_cannot_attest(tmp_path):
    malformed = capture.capture(ROUTE, tmp_path / 'malformed',
                                opener=Opener(body=b'not-json'),
                                captured_at='2026-09-23T10:35:00Z')
    unavailable = capture.capture(ROUTE, tmp_path / 'unavailable',
                                  opener=Opener(status=503, body={'error': 'offline'}),
                                  captured_at='2026-09-23T10:35:00Z')
    assert malformed['status'] == unavailable['status'] == 'unattested'
    assert malformed['http_status'] == 200
    assert unavailable['http_status'] == 503
    assert malformed['model_calls'] == unavailable['engine_calls'] == 0
    assert not (tmp_path / 'malformed/route-attestation.json').exists()
    assert not (tmp_path / 'unavailable/route-attestation.json').exists()


def test_capture_is_create_only_and_verifier_rejects_a_tampered_snapshot(tmp_path):
    output = tmp_path / 'capture'
    capture.capture(ROUTE, output, opener=Opener(),
                    captured_at='2026-09-23T10:35:00Z')
    with pytest.raises(FileExistsError):
        capture.capture(ROUTE, output, opener=Opener(),
                        captured_at='2026-09-23T10:35:01Z')
    (output / runner.RUNTIME_SNAPSHOT_NAME).write_bytes(b'{"models":[]}')
    with pytest.raises(ValueError):
        capture.verify_capture(ROUTE, output)
