"""One-attempt capture and offline teaching checks with a fake local transport."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward
import chess_no_forward_teaching_capture_v3 as capture
import chess_no_forward_teaching_v3 as teaching
import chess_user_game_no_forward_v1 as user_packet


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, maximum):
        return self.body[:maximum]


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    board = chess.Board(FEN)
    move = chess.Move.from_uci('c2c3')
    facts = cf.transition_evidence(board, move)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {'pgn_sha256': '1' * 64, 'review_receipt_sha256': '2' * 64,
                   'review_page_sha256': '3' * 64, 'selected_ply': 39,
                   'move_role': 'played', 'use_role': user_packet.USE_ROLE},
        'fen': board.fen(), 'side_to_move': 'white',
        'selected_move': {'uci': 'c2c3', 'san': board.san(move)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'name': 'synthetic', 'sha256': '4' * 64,
                               'score': {'type': 'cp', 'value': -471, 'bound': 'exact',
                                         'order': 'engine_score', 'perspective': 'side_to_move',
                                         'side_to_move': 'white'},
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    packet_path = tmp_path / 'packet.json'
    packet_path.write_bytes(cf.canonical(packet))
    pgn = tmp_path / 'source.pgn'
    pgn.write_text('fixture')
    review = tmp_path / 'review'
    review.mkdir()
    route_path = tmp_path / 'route.json'
    route_path.write_bytes((Path(__file__).resolve().parents[1] /
                            'research/chess-local-route-131k-v1.json').read_bytes())
    attestation = tmp_path / 'attestation'
    attestation.mkdir()
    for name in capture.ATTESTATION_FILES:
        (attestation / name).write_bytes(b'fixture')
    monkeypatch.setattr(user_packet, 'encode_packet',
                        lambda *args, **kwargs: cf.canonical(kwargs['packet']))
    monkeypatch.setattr(capture.route_capture, 'verify_capture',
                        lambda *_: {'verified': True})
    run_dir = tmp_path / 'new-run'
    manifest = capture.freeze_run(pgn, review, '1' * 64, '2' * 64, '3' * 64,
                                  packet_path, route_path, attestation, run_dir,
                                  expected_packet_sha256=cf.digest(cf.canonical(packet)))
    return run_dir, manifest, packet_path


def test_frozen_request_is_nine_key_projection_and_source_bound(frozen):
    run_dir, manifest, _ = frozen
    assert manifest['model_calls'] == manifest['automatic_retries'] == 0
    assert manifest['selected_uci'] == 'c2c3'
    assert not (run_dir / capture.REQUEST_FILE).exists()
    safe = json.loads((run_dir / capture.GENERATOR_INPUT_FILE).read_bytes())
    assert set(safe) == {'schema', 'source_packet_sha256', 'source', 'fen',
                         'side_to_move', 'selected_move', 'transition',
                         'engine_observation', 'assertion_kinds'}
    assert safe['assertion_kinds'] == [teaching.CLAIM_KIND, 'abstention']
    assert safe['selected_move']['uci'] == 'c2c3'
    assert 'c2e4' not in json.dumps(safe)
    assert 'pv_uci' not in json.dumps(safe)
    assert capture.verify_run(run_dir)['status'] == 'frozen'


def test_one_fake_call_then_offline_evaluation_and_no_retry(frozen):
    run_dir, manifest, _ = frozen
    claim = {'schema': teaching.CLAIM_SCHEMA, 'kind': teaching.CLAIM_KIND,
             'selected_uci': 'c2c3', 'alternative_uci': 'c2e4',
             'common_reply_uci': 'd7d4',
             'option': {'piece': 'queen', 'to': 'b7', 'promotion': None,
                        'property': 'capture_with_check'},
             'relation': 'legal_only_after_alternative',
             'modality': 'possible_if_common_reply',
             'uncertainty': 'other_replies_and_engine_intent_unverified'}
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': cf.canonical(claim).decode()}}]})
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.data == capture.build_request(
                (run_dir / capture.GENERATOR_INPUT_FILE).read_bytes(), manifest['route'])
            assert (run_dir / capture.REQUEST_FILE).exists()
            return Response(raw)

    result = capture.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'captured' and result['model_calls'] == 1
    assert len(calls) == 1
    receipt = capture.evaluate_frozen_run(run_dir)
    assert receipt['checker']['decision'] == 'verified_conditional_option'
    assert 'Qxb7+' in receipt['checker']['teaching_text']
    assert capture.verify_run(run_dir)['status'] == 'captured'
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_source_or_projection_tamper_blocks_before_post(frozen):
    run_dir, _, packet_path = frozen
    packet_path.write_bytes(packet_path.read_bytes() + b' ')
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response(b'{}')

    with pytest.raises(ValueError):
        capture.capture_frozen_run(run_dir, opener=Opener())
    assert calls == []
    assert not (run_dir / capture.REQUEST_FILE).exists()


def test_capture_cli_requires_frozen_model_endpoint_and_request_pins(frozen, monkeypatch):
    run_dir, manifest, _ = frozen
    args = [
        'capture', '--run-dir', str(run_dir),
        '--pgn-sha256', manifest['source_binding']['pgn_sha256'],
        '--review-sha256', manifest['source_binding']['review_sha256'],
        '--page-sha256', manifest['source_binding']['page_sha256'],
        '--packet-sha256', manifest['source_packet_sha256'],
        '--model-id', manifest['route']['model_id'],
        '--endpoint', manifest['route']['endpoint'],
        '--seed', str(manifest['route']['seed']),
        '--request-sha256', manifest['request_sha256'],
        '--manifest-sha256', cf.file_digest(run_dir / capture.MANIFEST_FILE),
    ]
    calls = []

    def fake_capture(path):
        calls.append(path)
        return {'status': 'stubbed', 'model_calls': 0}

    monkeypatch.setattr(capture, 'capture_frozen_run', fake_capture)
    changed = args.copy()
    changed[changed.index('--endpoint') + 1] = 'http://127.0.0.1:9999/v1'
    with pytest.raises(ValueError, match='cli_pins_changed'):
        capture.main(changed)
    assert calls == []
    assert capture.main(args) == 0
    assert calls == [run_dir]
    assert not (run_dir / capture.REQUEST_FILE).exists()


def test_failed_call_spends_attempt_and_retains_failure(frozen):
    run_dir, _, _ = frozen
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise TimeoutError('fixture timeout')

    result = capture.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'transport_failure'
    assert result['attempt_count'] == 1 and result['automatic_retries'] == 0
    assert capture.verify_run(run_dir)['attempts_consumed'] == 1
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_interrupted_request_is_spent(frozen):
    run_dir, manifest, _ = frozen
    safe = (run_dir / capture.GENERATOR_INPUT_FILE).read_bytes()
    (run_dir / capture.REQUEST_FILE).write_bytes(capture.build_request(safe, manifest['route']))
    assert capture.verify_run(run_dir)['status'] == 'interrupted'
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_frozen_run(run_dir)


def test_bad_envelope_is_retained_as_rejected_attempt(frozen):
    run_dir, manifest, _ = frozen
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': None, 'tool_calls': []}}]})

    class Opener:
        def open(self, request, timeout):
            return Response(raw)

    assert capture.capture_frozen_run(run_dir, opener=Opener())['status'] == 'captured'
    receipt = capture.evaluate_frozen_run(run_dir)
    assert receipt['extraction_status'] == 'invalid_model_envelope'
    assert receipt['checker']['decision'] == 'rejected'
    assert receipt['checker']['reason'] == 'invalid_response_length'
    assert capture.verify_run(run_dir)['evaluation_retained'] is True


def test_duplicate_model_key_cannot_attest_identity(frozen):
    run_dir, manifest, _ = frozen
    model = manifest['route']['model_id']
    raw = ('{"model":"wrong","model":"' + model + '","choices":[]}').encode()

    class Opener:
        def open(self, request, timeout):
            return Response(raw)

    result = capture.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'identity_unverified'
    assert result['observed_model_id'] is None
    assert capture.verify_run(run_dir)['status'] == 'identity_unverified'
    with pytest.raises(ValueError, match='not_eligible'):
        capture.evaluate_frozen_run(run_dir)


def test_raw_and_evaluation_tampering_are_rejected(frozen):
    run_dir, manifest, _ = frozen
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': '{"schema":"chess-no-forward-teaching-output/v3","kind":"abstention","reason":"insufficient_evidence"}'}}]})

    class Opener:
        def open(self, request, timeout):
            return Response(raw)

    capture.capture_frozen_run(run_dir, opener=Opener())
    capture.evaluate_frozen_run(run_dir)
    evaluation_path = run_dir / capture.EVALUATION_FILE
    original = evaluation_path.read_bytes()
    evaluation_path.write_bytes(original.replace(b'admissible_abstention', b'rejected'))
    with pytest.raises(ValueError, match='evaluation_changed'):
        capture.verify_run(run_dir)
    evaluation_path.write_bytes(original)
    (run_dir / capture.RAW_FILE).write_bytes(b'changed')
    with pytest.raises(ValueError, match='raw_changed'):
        capture.verify_run(run_dir)


def test_actual_qc3_source_freezes_without_model_when_assets_exist(tmp_path):
    root = Path(__file__).resolve().parents[1]
    review = root / 'artifacts/chess-user-reviews/chesscom-184866057876'
    pgn = review / 'source.pgn'
    reviewed = review / 'review-v3-paired-explanation-20261006'
    packet = root / 'artifacts/chess-user-game-no-forward-v1/chesscom-184866057876/ply39-played.json'
    route_path = root / 'research/chess-local-route-131k-v1.json'
    attestation = (root / 'artifacts/chess-user-game-generation-v1/'
                   'chesscom-184866057876/played-frozen-v2-20261006/route')
    if not all(path.exists() for path in (pgn, reviewed / 'review.json',
                                          reviewed / 'index.html', packet,
                                          route_path, attestation)):
        pytest.skip('ignored local practice assets are absent')
    manifest = capture.freeze_run(
        pgn, reviewed,
        '684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075',
        'b76e4746eadf4b85775468df0ee7324272dcb677673efe58dd8d4a8b40a3b730',
        'ed6ddf506897c76fce2856fb4e82e3c2a2a9ae6a8f48bfd93efb3c31b4b27a5b',
        packet, route_path, attestation, tmp_path / 'real-frozen',
        expected_packet_sha256='02c5f3955bf1649534e62b505659e6915ef98800b76938b9a6c00d44d82c7eec')
    assert manifest['source_packet_sha256'] == cf.file_digest(packet)
    assert capture.verify_run(tmp_path / 'real-frozen')['status'] == 'frozen'
