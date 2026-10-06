"""Typed transport checks: one no-forward packet, one retained request, no retry."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward
import chess_no_forward_typed_transport_v2 as typed


PACKET = ROOT / 'artifacts/chess-no-forward-input-v1/dev8-inputs/00.json'
ROUTE = ROOT / 'research/chess-local-route-131k-v1.json'
SOFTWARE_ROUTE = {
    'route_id': 'software-fixture-local-route',
    'endpoint': 'http://127.0.0.1:1234/v1',
    'model_id': 'software-fixture-model',
    'context_window_tokens': 131072,
    'reasoning': {'effort': 'low'},
    'sampling': {'temperature': 0, 'top_p': 1, 'max_output_tokens': 512},
    'seed': 1,
    'request_schema': 'openai-chat-completions/v1',
    'timeout_seconds': 30,
    'automatic_retries': 0,
}


@pytest.fixture
def packet_bytes():
    """Schema-valid software input; it makes no source-bound evidence claim."""
    board = chess.Board()
    move = chess.Move.from_uci('e2e4')
    facts = cf.transition_evidence(board, move)
    packet = {
        'schema': no_forward.SCHEMA,
        'source': {'position_id': 'fixture-position', 'game_id': 'fixture-game',
                   'url': 'https://example.invalid/fixture', 'split': 'dev',
                   'manifest_sha256': '0' * 64, 'projection_sha256': '0' * 64,
                   'receipt_sha256': '0' * 64, 'typed_packet_sha256': '0' * 64},
        'fen': board.fen(), 'side_to_move': 'white',
        'selected_move': {'uci': move.uci(), 'san': board.san(move)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'evidence_id': 'fixture-observation',
                               'engine_sha256': '0' * 64,
                               'score': {'type': 'cp', 'value': 20,
                                         'perspective': 'side_to_move',
                                         'side_to_move': 'white', 'bound': 'exact',
                                         'order': 'engine_score'},
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    no_forward._shape(packet)
    return cf.canonical(packet)


@pytest.fixture
def route():
    return copy.deepcopy(SOFTWARE_ROUTE)


def test_request_carries_only_exact_no_forward_packet_and_fixed_format_instruction(packet_bytes, route):
    request = json.loads(typed.build_request(packet_bytes, route))
    assert request['model'] == route['model_id']
    assert request['messages'][0] == {'role': 'system', 'content': typed.PROMPT}
    assert request['messages'][1] == {'role': 'user', 'content': packet_bytes.decode('utf-8')}
    assert request['seed'] == route['seed']
    assert request['reasoning_effort'] == route['reasoning']['effort']
    assert len(request['messages']) == 2
    assert not any(key in json.loads(request['messages'][1]['content']) for key in
                   ('pv_uci', 'post_move_fen', 'future_moves', 'solution', 'themes',
                    'answer_label', 'annotations', 'evaluator'))


@pytest.mark.parametrize('field', ('pv_uci', 'post_move_fen', 'solution', 'annotations'))
def test_extra_evaluator_or_future_field_rejected_before_request(field, packet_bytes, route):
    packet = json.loads(packet_bytes)
    packet[field] = 'leak'
    with pytest.raises(ValueError, match='no_forward_root_fields'):
        typed.build_request(cf.canonical(packet), route)


def test_noncanonical_or_changed_route_rejected_before_request(packet_bytes, route):
    with pytest.raises(ValueError, match='typed_transport_packet_not_canonical'):
        typed.build_request(packet_bytes + b'\n', route)
    foreign = copy.deepcopy(route)
    foreign['endpoint'] = 'https://example.com/v1'
    with pytest.raises(ValueError, match='route_is_not_pinned_loopback_endpoint'):
        typed.build_request(packet_bytes, foreign)


def test_retained_real_packet_when_local_evidence_is_available(route):
    if not PACKET.is_file():
        pytest.skip('retained real no-forward packet is a local evidence asset')
    packet = PACKET.read_bytes()
    request = json.loads(typed.build_request(packet, route))
    assert request['messages'][1] == {'role': 'user', 'content': packet.decode('utf-8')}


def test_declared_route_when_local_config_is_available(packet_bytes):
    if not ROUTE.is_file():
        pytest.skip('declared local route file is absent from this checkout')
    route = json.loads(ROUTE.read_bytes())
    request = json.loads(typed.build_request(packet_bytes, route))
    assert request['model'] == route['model_id']


def test_transport_retains_exact_request_before_one_fake_open_and_never_retries(
        tmp_path, monkeypatch, packet_bytes, route):
    packet = packet_bytes
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


def test_protocol_hash_blocks_adapter_or_manifest_drift_before_open(
        tmp_path, monkeypatch, packet_bytes, route):
    packet = packet_bytes
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
