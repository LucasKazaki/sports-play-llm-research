"""Offline software controls for the one-request user-game local runner."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_local_route_attestation as attestation
import chess_no_forward_generation_runner as old_runner
import chess_no_forward_typed_transport_v2 as typed_prompt
import chess_paired_review_v3 as paired
import chess_review_completed_game as previous
import chess_user_game_no_forward_v1 as user_packet
import chess_user_game_generation_v1 as generation


PGN = '''[Event "Private software fixture"]
[Site "local"]
[White "PrivateName"]
[Black "OtherName"]
[Result "1-0"]

1. e4 $2 {future annotation} e5 2. Nf3 Nc6 1-0
'''
ROUTE = {
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


class Response:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, maximum):
        assert maximum >= len(self.body)
        return self.body


class ReadinessOpener:
    def __init__(self):
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        catalog = {'models': [{'key': old_runner.LOCAL_MODEL_CATALOG_KEY,
                               'max_context_length': 131072,
                               'loaded_instances': [{'id': ROUTE['model_id'],
                                                     'config': {'context_length': 131072,
                                                                'parallel': 1}}],
                               'capabilities': {'reasoning': {
                                   'allowed_options': ['low', 'medium', 'high'],
                                   'default': 'low'}}}]}
        return Response(cf.canonical(catalog))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(attestation, 'ROOT', tmp_path)
    pgn = tmp_path / 'game.pgn'
    pgn.write_text(PGN, encoding='utf-8')
    game, raw, moves = previous.load_completed_game(pgn)

    class FakeEngine:
        id = {'name': 'Stockfish 19'}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def configure(self, options):
            assert options == {'Threads': 1, 'Hash': 16}

        def analyse(self, board, limit, *, root_moves=None, multipv=None):
            e4 = chess.Move.from_uci('e2e4')
            d4 = chess.Move.from_uci('d2d4')
            if root_moves is None:
                return [{'pv': [d4]}, {'pv': [e4]}]
            assert root_moves == [e4, d4]
            return [
                {'pv': [d4, chess.Move.from_uci('d7d5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE),
                 'nodes': 600, 'depth': 7},
                {'pv': [e4, chess.Move.from_uci('e7e5')],
                 'score': chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
                 'nodes': 400, 'depth': 7},
            ]

    monkeypatch.setattr(previous, 'engine_ready', lambda: {'status': 'software-fixture'})
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', lambda _: FakeEngine())
    record = paired.analyze(game, raw, moves, 1, 1000)
    review = tmp_path / 'review'
    review.mkdir()
    (review / 'review.json').write_bytes(previous.canonical(record) + b'\n')
    (review / 'index.html').write_bytes(paired.render(record))
    pgn_sha = previous.digest(raw)
    review_sha = previous.digest((review / 'review.json').read_bytes())
    page_sha = previous.digest((review / 'index.html').read_bytes())
    packet = tmp_path / 'played.json'
    content = user_packet.build_packet(pgn, review, pgn_sha, review_sha, page_sha,
                                       role='played')
    packet.write_bytes(user_packet.encode_packet(pgn, review, pgn_sha, review_sha,
                                                 page_sha, role='played', packet=content))
    route = tmp_path / 'declared-route.json'
    route.write_bytes(cf.canonical(ROUTE) + b'\n')
    readiness = ReadinessOpener()
    att_dir = tmp_path / 'route-attestation'
    result = attestation.capture(route, att_dir, opener=readiness,
                                 captured_at='2026-10-06T05:00:00Z')
    assert result['status'] == 'attested'
    assert readiness.calls == [(old_runner.LOCAL_MODELS_URL, 'GET',
                                attestation.REQUEST_TIMEOUT_SECONDS)]
    run_dir = tmp_path / 'run'
    return (pgn, review, pgn_sha, review_sha, page_sha, 'played', packet,
            route, att_dir, run_dir)


def frozen(bundle):
    generation.freeze_run(*bundle)
    return bundle[-1]


def test_freeze_binds_one_packet_prompt_route_and_no_call(bundle):
    run_dir = frozen(bundle)
    status = generation.verify_run(run_dir)
    manifest = json.loads((run_dir / 'manifest.json').read_bytes())
    assert status['status'] == 'frozen' and status['model_calls'] == 0
    assert manifest['role'] == 'played'
    assert manifest['route']['model_id'] == ROUTE['model_id']
    assert manifest['route']['context_window_tokens'] == 131072
    assert manifest['route']['seed'] == ROUTE['seed']
    assert manifest['prompt_sha256'] == cf.digest(typed_prompt.PROMPT.encode('utf-8'))
    assert manifest['request_sha256'] == cf.digest(generation.build_request(
        (run_dir / 'packet.json').read_bytes(), ROUTE))
    assert not (run_dir / 'request.json').exists()
    assert not (run_dir / 'result.json').exists()
    with pytest.raises(FileExistsError):
        generation.freeze_run(*bundle)


def test_alternative_role_freezes_separately_without_played_move_or_score(bundle):
    pgn, review, pgn_sha, review_sha, page_sha, _, _, route, att_dir, run_dir = bundle
    alternative_packet = pgn.parent / 'alternative.json'
    alternative = user_packet.build_packet(pgn, review, pgn_sha, review_sha,
                                           page_sha, role='alternative')
    alternative_packet.write_bytes(user_packet.encode_packet(
        pgn, review, pgn_sha, review_sha, page_sha,
        role='alternative', packet=alternative))
    generation.freeze_run(pgn, review, pgn_sha, review_sha, page_sha,
                          'alternative', alternative_packet, route, att_dir, run_dir)
    assert generation.verify_run(run_dir)['status'] == 'frozen'
    request = json.loads(generation.build_request(
        (run_dir / 'packet.json').read_bytes(), ROUTE))
    user_content = request['messages'][1]['content']
    selected = json.loads(user_content)
    assert selected['source']['move_role'] == 'alternative'
    assert selected['selected_move'] == {'uci': 'd2d4', 'san': 'd4'}
    assert selected['engine_observation']['score']['value'] == 25
    assert 'e2e4' not in user_content
    assert 'pv_uci' not in user_content


def test_fake_post_sees_retained_exact_request_and_malformed_raw_is_kept(bundle):
    run_dir = frozen(bundle)
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            assert (run_dir / 'request.json').read_bytes() == request.data
            assert request.full_url == ROUTE['endpoint'] + '/chat/completions'
            assert request.get_method() == 'POST'
            assert timeout == ROUTE['timeout_seconds']
            payload = json.loads(request.data)
            assert payload['messages'][0] == {'role': 'system', 'content': typed_prompt.PROMPT}
            assert payload['messages'][1]['content'] == (run_dir / 'packet.json').read_text()
            assert 'pv_uci' not in payload['messages'][1]['content']
            return Response(b'not-json')

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1
    assert result['status'] == 'identity_unverified'
    assert result['raw_classification'] == 'malformed_json'
    assert (run_dir / 'raw-response.bin').read_bytes() == b'not-json'
    assert result['model_calls'] == result['attempt_count'] == 1
    assert result['latency_ns'] >= 0
    assert generation.verify_run(run_dir)['status'] == 'identity_unverified'
    with pytest.raises(ValueError, match='already_attempted'):
        generation.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_http_error_body_is_retained(bundle):
    run_dir = frozen(bundle)

    class Opener:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 503, 'unavailable', {}, BytesIO(b'{"error":"busy"}'))

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'http_error'
    assert result['http_status'] == 503
    assert (run_dir / 'raw-response.bin').read_bytes() == b'{"error":"busy"}'
    assert generation.verify_run(run_dir)['model_calls'] == 1


def test_timeout_spends_attempt_and_never_retries(bundle):
    run_dir = frozen(bundle)
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise TimeoutError('one failed POST')

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'transport_failure'
    assert result['model_calls'] == 1
    assert result['raw_sha256'] is None
    assert len(calls) == 1
    assert generation.verify_run(run_dir)['status'] == 'transport_failure'
    with pytest.raises(ValueError, match='already_attempted'):
        generation.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_foreign_response_model_is_retained_as_identity_mismatch(bundle):
    run_dir = frozen(bundle)

    class Opener:
        def open(self, request, timeout):
            return Response(b'{"object":"chat.completion","model":"foreign-model"}')

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'identity_mismatch'
    assert result['observed_model_id'] == 'foreign-model'
    assert (run_dir / 'raw-response.bin').read_bytes().endswith(b'"foreign-model"}')
    assert generation.verify_run(run_dir)['status'] == 'identity_mismatch'


def test_json_without_model_identity_is_not_a_captured_explanation(bundle):
    run_dir = frozen(bundle)

    class Opener:
        def open(self, request, timeout):
            return Response(b'{"object":"chat.completion","choices":[]}')

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'identity_unverified'
    assert result['model_identity'] == 'unverified'
    assert generation.verify_run(run_dir)['status'] == 'identity_unverified'


def test_oversized_response_retains_bounded_prefix_and_spends_attempt(bundle):
    run_dir = frozen(bundle)
    prefix = b'X' * (generation.MAX_RAW_BYTES + 1)
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response(prefix)

    result = generation.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1
    assert result['status'] == 'response_too_large'
    assert result['raw_classification'] == 'response_too_large'
    assert result['raw_bytes'] == generation.MAX_RAW_BYTES + 1
    assert (run_dir / 'raw-response.bin').read_bytes() == prefix
    assert generation.verify_run(run_dir)['status'] == 'response_too_large'
    with pytest.raises(ValueError, match='already_attempted'):
        generation.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_invalid_opener_is_pre_post_failure_with_zero_calls(bundle):
    run_dir = frozen(bundle)
    with pytest.raises(ValueError, match='invalid_opener_before_post'):
        generation.capture_frozen_run(run_dir, opener=object())
    assert generation.verify_run(run_dir)['status'] == 'frozen'
    assert not (run_dir / 'request.json').exists()


def test_request_without_result_is_spent_and_reported_interrupted(bundle):
    run_dir = frozen(bundle)
    request = generation.build_request((run_dir / 'packet.json').read_bytes(), ROUTE)
    (run_dir / 'request.json').write_bytes(request)
    checked = generation.verify_run(run_dir)
    assert checked['status'] == 'interrupted'
    assert checked['attempts_consumed'] == 1
    assert checked['model_calls_upper_bound'] == 1
    with pytest.raises(ValueError, match='already_attempted'):
        generation.capture_frozen_run(run_dir, opener=object())


def test_prohibited_packet_field_rejected_before_freeze_or_post(bundle):
    pgn, review, pgn_sha, review_sha, page_sha, role, packet, route, att_dir, run_dir = bundle
    changed = json.loads(packet.read_bytes())
    changed['pv_uci'] = ['future']
    packet.write_bytes(cf.canonical(changed))
    with pytest.raises(ValueError, match='user_game_no_forward_root_fields'):
        generation.freeze_run(*bundle)
    assert not run_dir.exists()


@pytest.mark.parametrize('drift', ('pgn', 'route', 'prompt', 'frozen_packet',
                                  'route_evidence'))
def test_source_route_prompt_or_frozen_packet_drift_blocks_before_post(bundle, monkeypatch, drift):
    run_dir = frozen(bundle)
    pgn, _, _, _, _, _, _, route, _, _ = bundle
    if drift == 'pgn':
        pgn.write_bytes(pgn.read_bytes() + b'\n')
    elif drift == 'route':
        route.write_bytes(route.read_bytes().replace(b'127.0.0.1', b'example.com'))
    elif drift == 'prompt':
        monkeypatch.setattr(typed_prompt, 'PROMPT', typed_prompt.PROMPT + '\nchanged')
    elif drift == 'route_evidence':
        snapshot = run_dir / 'route' / old_runner.RUNTIME_SNAPSHOT_NAME
        snapshot.write_bytes(snapshot.read_bytes() + b'\n')
    else:
        packet = run_dir / 'packet.json'
        packet.write_bytes(packet.read_bytes() + b'\n')
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise AssertionError('preflight must block POST')

    with pytest.raises(ValueError):
        generation.capture_frozen_run(run_dir, opener=Opener())
    assert not calls
    assert not (run_dir / 'request.json').exists()
    assert not (run_dir / 'result.json').exists()


@pytest.mark.parametrize('name', tuple(generation.HELPER_MODULES))
def test_helper_source_drift_blocks_before_post(bundle, monkeypatch, name):
    helper = generation.HELPER_MODULES[name]
    copied_source = bundle[0].parent / name
    copied_source.write_bytes(Path(helper.__file__).read_bytes())
    monkeypatch.setattr(helper, '__file__', str(copied_source))
    run_dir = frozen(bundle)
    manifest = json.loads((run_dir / 'manifest.json').read_bytes())
    assert manifest['helper_sources_sha256'][name] == cf.file_digest(copied_source)
    copied_source.write_bytes(copied_source.read_bytes() + b'\n# changed after freeze\n')
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise AssertionError('helper drift must block POST')

    with pytest.raises(ValueError, match='implementation_changed_since_freeze'):
        generation.capture_frozen_run(run_dir, opener=Opener())
    assert calls == []
    assert not (run_dir / 'request.json').exists()
    assert not (run_dir / 'result.json').exists()


def test_raw_tamper_detected_offline(bundle):
    run_dir = frozen(bundle)

    class Opener:
        def open(self, request, timeout):
            return Response(b'{"object":"chat.completion","model":"software-fixture-model"}')

    generation.capture_frozen_run(run_dir, opener=Opener())
    (run_dir / 'raw-response.bin').write_bytes(b'changed')
    with pytest.raises(ValueError, match='raw_response_changed'):
        generation.verify_run(run_dir)


def test_capture_cli_requires_exact_pins_before_library_call(bundle, monkeypatch):
    run_dir = frozen(bundle)
    manifest = json.loads((run_dir / 'manifest.json').read_bytes())
    args = [
        '--run-dir', str(run_dir), '--role', manifest['role'],
        '--pgn-sha256', manifest['pgn_sha256'],
        '--review-sha256', manifest['review_sha256'],
        '--page-sha256', manifest['page_sha256'],
        '--packet-sha256', manifest['packet_sha256'],
        '--model-id', manifest['route']['model_id'],
        '--seed', str(manifest['route']['seed']),
        '--request-sha256', manifest['request_sha256'],
        '--manifest-sha256', cf.file_digest(run_dir / 'manifest.json'),
    ]
    calls = []

    def fake_capture(path):
        calls.append(path)
        return {'status': 'stubbed', 'model_calls': 0}

    monkeypatch.setattr(generation, 'capture_frozen_run', fake_capture)
    bad = args.copy()
    bad[bad.index('--packet-sha256') + 1] = '0' * 64
    with pytest.raises(ValueError, match='capture_cli_pins_changed'):
        generation.main(['capture', *bad])
    stale_manifest = args.copy()
    stale_manifest[stale_manifest.index('--manifest-sha256') + 1] = '0' * 64
    with pytest.raises(ValueError, match='capture_cli_manifest_changed'):
        generation.main(['capture', *stale_manifest])
    assert calls == []
    assert not (run_dir / 'request.json').exists()
    assert generation.main(['capture', *args]) == 0
    assert calls == [run_dir]
    assert not (run_dir / 'request.json').exists()
