"""Typed transport checks: one no-forward packet, one retained request, no retry."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_typed_transport_v2 as typed


PACKET = ROOT / 'artifacts/chess-no-forward-input-v1/dev8-inputs/00.json'
ROUTE = ROOT / 'research/chess-local-route-131k-v1.json'


def test_request_carries_only_exact_no_forward_packet_and_fixed_format_instruction():
    packet = PACKET.read_bytes()
    route = json.loads(ROUTE.read_bytes())
    request = json.loads(typed.build_request(packet, route))
    assert request['model'] == route['model_id']
    assert request['messages'][0] == {'role': 'system', 'content': typed.PROMPT}
    assert request['messages'][1] == {'role': 'user', 'content': packet.decode('utf-8')}
    assert request['seed'] == route['seed']
    assert request['reasoning_effort'] == route['reasoning']['effort']
    assert len(request['messages']) == 2
    assert not any(key in json.loads(request['messages'][1]['content']) for key in
                   ('pv_uci', 'post_move_fen', 'future_moves', 'solution', 'themes',
                    'answer_label', 'annotations', 'evaluator'))


@pytest.mark.parametrize('field', ('pv_uci', 'post_move_fen', 'solution', 'annotations'))
def test_extra_evaluator_or_future_field_rejected_before_request(field):
    packet = json.loads(PACKET.read_bytes())
    packet[field] = 'leak'
    with pytest.raises(ValueError, match='no_forward_root_fields'):
        typed.build_request(cf.canonical(packet), json.loads(ROUTE.read_bytes()))


def test_noncanonical_or_changed_route_rejected_before_request():
    packet = PACKET.read_bytes()
    route = json.loads(ROUTE.read_bytes())
    with pytest.raises(ValueError, match='typed_transport_packet_not_canonical'):
        typed.build_request(packet + b'\n', route)
    foreign = copy.deepcopy(route)
    foreign['endpoint'] = 'https://example.com/v1'
    with pytest.raises(ValueError, match='route_is_not_pinned_loopback_endpoint'):
        typed.build_request(packet, foreign)


def test_transport_retains_exact_request_before_one_fake_open_and_never_retries(tmp_path, monkeypatch):
    packet = PACKET.read_bytes()
    route = json.loads(ROUTE.read_bytes())
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'manifest.json').write_bytes(b'{}')
    manifest = {'observed_route': route, 'requests': [{'input_sha256': cf.digest(packet)}]}
    monkeypatch.setattr(typed.runner, '_load_manifest', lambda _: manifest)
    protocol = typed._protocol(run_dir, route, cf.digest(packet))
    typed.runner.write_json(protocol, run_dir / typed.PROTOCOL_FILE)
    calls = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, maximum):
            return b'{"object":"chat.completion"}'

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            assert (run_dir / typed.REQUEST_FILE).read_bytes() == request.data
            return Response()

    transport = typed.build_transport(run_dir, opener=Opener())
    result = transport(packet)
    assert result['transport_status'] == 'completed'
    assert result['raw_output'] == b'{"object":"chat.completion"}'
    assert len(calls) == 1
    assert calls[0][0].full_url == route['endpoint'] + '/chat/completions'
    assert calls[0][1] == route['timeout_seconds']
    with pytest.raises(FileExistsError):
        transport(packet)
    assert len(calls) == 1


def test_protocol_hash_blocks_adapter_or_manifest_drift_before_open(tmp_path, monkeypatch):
    packet = PACKET.read_bytes()
    route = json.loads(ROUTE.read_bytes())
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'manifest.json').write_bytes(b'{}')
    manifest = {'observed_route': route, 'requests': [{'input_sha256': cf.digest(packet)}]}
    monkeypatch.setattr(typed.runner, '_load_manifest', lambda _: manifest)
    protocol = typed._protocol(run_dir, route, cf.digest(packet))
    protocol['prompt_sha256'] = '0' * 64
    typed.runner.write_json(protocol, run_dir / typed.PROTOCOL_FILE)
    with pytest.raises(ValueError, match='typed_transport_protocol_binding_changed'):
        typed.build_transport(run_dir, opener=object())
