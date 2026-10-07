"""Create-only v4 capture controls using a fake local transport."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_capture_v4 as capture  # noqa: E402
import chess_no_forward_teaching_v4 as teaching  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


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


def proposal():
    return {'schema': teaching.CLAIM_SCHEMA, 'kind': teaching.CLAIM_KIND,
            'selected_uci': 'c2c3', 'alternative_uci': 'c2e4',
            'hypothesis': teaching.HYPOTHESIS,
            'modality': 'candidate_only',
            'uncertainty': 'other_replies_and_engine_intent_unverified'}


def test_freeze_preserves_nine_field_input_and_rejects_reply_menu(frozen):
    run_dir, manifest, _ = frozen
    assert manifest['requested'] == 1
    assert manifest['model_calls'] == manifest['automatic_retries'] == 0
    assert manifest['heldout_outcomes_scored'] == 0
    safe = json.loads((run_dir / capture.GENERATOR_INPUT_FILE).read_bytes())
    assert set(safe) == set(capture.PROJECTION_FIELDS)
    assert safe['assertion_kinds'] == [teaching.CLAIM_KIND, 'abstention']
    assert 'c2e4' not in json.dumps(safe)
    assert 'd7d4' not in json.dumps(safe)
    assert capture.verify_run(run_dir)['attempts_consumed'] == 0
    for forbidden in ({'legal_reply_candidates': ['d7d4']},
                      {'post_move_fen': 'forbidden'},
                      {'alternative_score': -100}, {'review_label': 'mistake'}):
        changed = dict(safe, **forbidden)
        with pytest.raises(ValueError, match='invalid_teaching_projection_fields'):
            capture.build_request(cf.canonical(changed), manifest['route'])
    assert not (run_dir / capture.REQUEST_FILE).exists()


def test_one_fake_call_then_offline_witness_and_no_retry(frozen):
    run_dir, manifest, _ = frozen
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': cf.canonical(proposal()).decode()},
                                     'finish_reason': 'stop'}]})
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.data == capture.build_request(
                (run_dir / capture.GENERATOR_INPUT_FILE).read_bytes(),
                manifest['route'])
            assert (run_dir / capture.REQUEST_FILE).exists()
            return Response(raw)

    result = capture.capture_frozen_run(run_dir, opener=Opener())
    assert result['status'] == 'captured'
    assert result['attempt_count'] == result['model_calls'] == 1
    assert result['automatic_retries'] == 0
    assert len(calls) == 1
    check = capture.evaluate_frozen_run(run_dir)
    assert check['checker']['decision'] == 'verified_conditional_option'
    assert check['checker']['witness_search_counts']['exclusive_concrete_witness_count'] > 0
    assert check['quality_evaluated'] is False
    assert capture.verify_run(run_dir)['evaluation_retained'] is True
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_frozen_run(run_dir, opener=Opener())
    assert len(calls) == 1


def test_changed_source_blocks_before_post(frozen):
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


def test_interrupted_request_is_spent_without_hidden_retry(frozen):
    run_dir, manifest, _ = frozen
    safe = (run_dir / capture.GENERATOR_INPUT_FILE).read_bytes()
    (run_dir / capture.REQUEST_FILE).write_bytes(
        capture.build_request(safe, manifest['route']))
    status = capture.verify_run(run_dir)
    assert status['status'] == 'interrupted'
    assert status['attempts_consumed'] == 1
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_frozen_run(run_dir)


def test_empty_assistant_content_remains_a_rejected_attempt(frozen):
    run_dir, manifest, _ = frozen
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': '',
                                                 'tool_calls': []},
                                     'finish_reason': 'length'}]})

    class Opener:
        def open(self, request, timeout):
            return Response(raw)

    assert capture.capture_frozen_run(run_dir, opener=Opener())['status'] == 'captured'
    check = capture.evaluate_frozen_run(run_dir)
    assert check['checker']['decision'] == 'rejected'
    assert check['extraction_status'] == 'invalid_model_envelope'
    assert capture.verify_run(run_dir)['attempts_consumed'] == 1


def test_length_truncated_complete_json_still_rejects_and_retains_raw(frozen):
    run_dir, manifest, _ = frozen
    raw = cf.canonical({'model': manifest['route']['model_id'],
                        'choices': [{'message': {'role': 'assistant',
                                                 'content': cf.canonical(proposal()).decode(),
                                                 'tool_calls': []},
                                     'finish_reason': 'length'}]})

    class Opener:
        def open(self, request, timeout):
            return Response(raw)

    captured = capture.capture_frozen_run(run_dir, opener=Opener())
    assert captured['status'] == 'captured'
    assert captured['raw_sha256'] == cf.digest(raw)
    assert (run_dir / capture.RAW_FILE).read_bytes() == raw
    check = capture.evaluate_frozen_run(run_dir)
    assert check['extraction_status'] == 'incomplete_model_response'
    assert check['checker']['decision'] == 'rejected'
    assert check['checker']['reason'] == 'invalid_response_length'
    assert check['checker']['teaching_text'] is None
    assert capture.verify_run(run_dir)['attempts_consumed'] == 1
