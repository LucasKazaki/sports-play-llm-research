"""Offline v9 capture state-machine tests; no model, engine or loopback POST."""
from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_teaching_capture_v9 as capture  # noqa: E402
import chess_no_forward_teaching_v9 as teaching  # noqa: E402


class FakeResponse:
    def __init__(self, raw: bytes, status=200):
        self.raw = raw
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.raw[:size]


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


def envelope(content: str, *, model='loops-cpu-gpt-oss-20b',
             finish='stop', message_extra=None, choices=None) -> bytes:
    message = {'role': 'assistant', 'content': content}
    message.update(message_extra or {})
    value = {'model': model, 'choices': choices if choices is not None else
             [{'index': 0, 'message': message, 'finish_reason': finish}]}
    return cf.canonical(value)


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    evidence_dir = tmp_path / 'attestation'
    evidence_dir.mkdir()
    current = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    for name in capture.ATTESTATION_FILES:
        raw = (cf.canonical({'captured_at': current}) + b'\n'
               if name == capture.route_capture.ATTESTATION_NAME else
               b'fake_fresh_route_test_evidence')
        (evidence_dir / name).write_bytes(raw)
    monkeypatch.setattr(capture.route_capture, 'verify_capture',
                        lambda *_: {'verified': True})
    run_dir = tmp_path / 'run'
    plan = capture.freeze_run(run_dir, evidence_dir)
    return run_dir, plan


def pins(frozen, ply):
    run_dir, plan = frozen
    case_dir = run_dir / f'ply{ply}'
    manifest = capture._json(case_dir / capture.MANIFEST_FILE)
    return capture._pins(manifest, plan['route'], case_dir)


def test_four_source_bound_cases_and_denominator_freeze_before_post(frozen):
    run_dir, plan = frozen
    assert plan['plies'] == [33, 46, 57, 93]
    assert plan['denominator'] == 4
    assert plan['model_calls'] == 0
    assert plan['heldout_outcomes_scored'] == 0
    assert plan['commentary_capability_gate_passed'] is False
    assert (run_dir / capture.PLAN_FILE).exists()
    for ply in capture.CASE_PINS:
        case_dir = run_dir / f'ply{ply}'
        manifest = capture._json(case_dir / capture.MANIFEST_FILE)
        assert manifest['source_packet_sha256'] == capture.CASE_PINS[ply][0]
        assert manifest['projection_sha256'] == capture.CASE_PINS[ply][1]
        assert not (case_dir / capture.REQUEST_FILE).exists()
        request = json.loads((case_dir / capture.FROZEN_REQUEST_FILE).read_bytes())
        assert request['model'] == plan['route']['model_id']
        assert request['messages'][0]['content'] == teaching.PROMPT
        assert cf.canonical(json.loads(request['messages'][1]['content'])) == (
            case_dir / capture.PROJECTION_FILE).read_bytes()
        assert set(json.loads(request['messages'][1]['content'])) == set(
            capture.capture_v7.PROJECTION_FIELDS)
        assert request['seed'] == 20260923
    assert capture.verify_run(run_dir)['counts']['not_run'] == 4


def test_existing_parent_and_second_capture_rejected(frozen):
    run_dir, _ = frozen
    with pytest.raises(FileExistsError):
        capture.freeze_run(run_dir, run_dir / capture.ROUTE_DIR)
    opener = FakeOpener(FakeResponse(envelope('{"schema":"x"}')))
    result = capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    assert result['status'] == 'captured'
    assert len(opener.calls) == 1
    assert opener.calls[0][0].get_method() == 'POST'
    assert opener.calls[0][1] == 60
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    assert len(opener.calls) == 1


@pytest.mark.parametrize('case_name,mutate', [
    ('packet', lambda run: (run / 'ply33' / capture.PACKET_FILE).write_bytes(b'{}')),
    ('route', lambda run: (run / capture.ROUTE_DIR /
                           capture.route_capture.ATTESTATION_NAME).write_bytes(b'{}')),
    ('request', lambda run: (run / 'ply33' /
                             capture.FROZEN_REQUEST_FILE).write_bytes(b'{}')),
    ('manifest', lambda run: (run / 'ply33' /
                              capture.MANIFEST_FILE).write_bytes(b'{}')),
])
def test_changed_frozen_artifacts_block_before_post(frozen, case_name, mutate):
    run_dir, _ = frozen
    mutate(run_dir)
    opener = FakeOpener()
    with pytest.raises((ValueError, KeyError)):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33) if case_name != 'manifest' else {},
                             opener=opener)
    assert opener.calls == []
    assert not (run_dir / 'ply33' / capture.REQUEST_FILE).exists()


def test_changed_source_prompt_implementation_and_cli_pins_block(frozen, monkeypatch):
    run_dir, _ = frozen
    original_source_packet = capture._source_packet
    opener = FakeOpener()
    monkeypatch.setattr(capture, '_source_packet',
                        lambda *args: (b'changed_source', b'changed_projection'))
    with pytest.raises(ValueError):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    monkeypatch.setattr(capture, '_source_packet', original_source_packet)
    original_prompt = teaching.PROMPT
    monkeypatch.setattr(teaching, 'PROMPT', original_prompt + '\nchanged')
    with pytest.raises(ValueError):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    monkeypatch.setattr(teaching, 'PROMPT', original_prompt)
    original_hashes = capture._implementation_hashes
    monkeypatch.setattr(capture, '_implementation_hashes', lambda: {'changed': 'source'})
    with pytest.raises(ValueError):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    monkeypatch.setattr(capture, '_implementation_hashes', original_hashes)
    changed_pins = dict(pins(frozen, 33), seed=99)
    with pytest.raises(ValueError, match='cli_pins'):
        capture.capture_case(run_dir, 33, pins=changed_pins, opener=opener)
    assert opener.calls == []


@pytest.mark.parametrize('field,value', [
    ('pv_uci', ['c3d1']), ('post_move_fen', 'future'),
    ('alternative_score', 42), ('review_label', 'mistake'),
    ('future_moves', ['c3d1']),
])
def test_hidden_nested_fields_never_build_request(frozen, field, value):
    run_dir, plan = frozen
    projection = json.loads((run_dir / 'ply33' / capture.PROJECTION_FILE).read_bytes())
    projection['engine_observation'][field] = value
    with pytest.raises(ValueError):
        capture.build_request(cf.canonical(projection), plan['route'])


def test_invalid_outer_fields_types_and_canonical_bytes_rejected(frozen):
    run_dir, plan = frozen
    projection = json.loads((run_dir / 'ply33' / capture.PROJECTION_FILE).read_bytes())
    for changed in (dict(projection, engine_pv=['c3d1']),
                    dict(projection, fen={'hidden': 'future'}),
                    dict(projection, assertion_kinds=['made_up'])):
        with pytest.raises(ValueError):
            capture.build_request(cf.canonical(changed), plan['route'])
    raw = cf.canonical(projection)
    with pytest.raises(ValueError):
        capture.build_request(b' ' + raw, plan['route'])


def test_interrupted_sentinel_spends_one_attempt(frozen):
    run_dir, _ = frozen
    case_dir = run_dir / 'ply33'
    (case_dir / capture.REQUEST_FILE).write_bytes(
        (case_dir / capture.FROZEN_REQUEST_FILE).read_bytes())
    report = capture.verify_run(run_dir)
    assert report['rows'][0]['status'] == 'interrupted'
    assert report['rows'][0]['attempts_consumed'] == 1
    assert report['counts']['interrupted'] == 1
    opener = FakeOpener()
    with pytest.raises(ValueError, match='already_attempted'):
        capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    assert opener.calls == []


def test_fake_success_retains_raw_and_checker_rejection(frozen):
    run_dir, _ = frozen
    raw = envelope('{"schema":"chess-no-forward-teaching-output/v9","kind":"abstention"}')
    opener = FakeOpener(FakeResponse(raw))
    result = capture.capture_case(run_dir, 46, pins=pins(frozen, 46), opener=opener)
    assert result['status'] == 'captured'
    assert result['model_identity'] == 'matched'
    assert result['raw_sha256'] == cf.digest(raw)
    assert (run_dir / 'ply46' / capture.RAW_FILE).read_bytes() == raw
    evaluated = capture.evaluate_case(run_dir, 46)
    assert evaluated['checker']['decision'] == 'model_abstention'
    assert evaluated['model_calls_in_evaluator'] == 0
    assert evaluated['engine_calls_in_evaluator'] == 0
    report = capture.verify_run(run_dir)
    assert report['counts']['abstention'] == 1
    assert report['counts']['not_run'] == 3
    assert report['denominator'] == 4
    assert report['quality_evaluated'] is False


@pytest.mark.parametrize('raw,status', [
    (b'', 'identity_unverified'),
    (b'not-json', 'identity_unverified'),
    (envelope('{}', model='wrong-model'), 'identity_mismatch'),
    (b'{"model":"loops-cpu-gpt-oss-20b","model":"wrong",' +
     b'"choices":[]}', 'identity_unverified'),
    (b'{"model":"loops-cpu-gpt-oss-20b","choices":[],"x":NaN}',
     'identity_unverified'),
])
def test_empty_malformed_wrong_model_and_duplicate_envelope_retained(frozen, raw, status):
    run_dir, _ = frozen
    result = capture.capture_case(run_dir, 33, pins=pins(frozen, 33),
                                  opener=FakeOpener(FakeResponse(raw)))
    assert result['status'] == status
    assert (run_dir / 'ply33' / capture.RAW_FILE).read_bytes() == raw
    assert capture.verify_run(run_dir)['rows'][0]['status'] == status
    with pytest.raises(ValueError, match='not_eligible'):
        capture.evaluate_case(run_dir, 33)


def test_http_error_and_timeout_retained_without_retry(frozen):
    run_dir, _ = frozen
    body = b'upstream error'
    error = HTTPError('http://127.0.0.1:1234/v1/chat/completions', 503,
                      'unavailable', {}, io.BytesIO(body))
    opener = FakeOpener(error=error)
    result = capture.capture_case(run_dir, 33, pins=pins(frozen, 33), opener=opener)
    assert result['status'] == 'http_error'
    assert result['http_status'] == 503
    assert (run_dir / 'ply33' / capture.RAW_FILE).read_bytes() == body
    assert len(opener.calls) == 1
    timeout = FakeOpener(error=TimeoutError('synthetic timeout'))
    result = capture.capture_case(run_dir, 46, pins=pins(frozen, 46), opener=timeout)
    assert result['status'] == 'transport_failure'
    assert result['error']['type'] == 'TimeoutError'
    assert not (run_dir / 'ply46' / capture.RAW_FILE).exists()
    assert len(timeout.calls) == 1
    report = capture.verify_run(run_dir)
    assert report['counts']['transport_failure'] == 1
    assert report['rows'][0]['status'] == 'http_error'


def test_oversized_raw_prefix_is_retained(frozen, monkeypatch):
    run_dir, _ = frozen
    monkeypatch.setattr(capture, 'MAX_RAW_BYTES', 32)
    raw = b'a' * 200
    result = capture.capture_case(run_dir, 33, pins=pins(frozen, 33),
                                  opener=FakeOpener(FakeResponse(raw)))
    assert result['status'] == 'response_too_large'
    assert result['raw_bytes'] == 33
    assert (run_dir / 'ply33' / capture.RAW_FILE).read_bytes() == b'a' * 33
    assert capture.verify_run(run_dir)['rows'][0]['status'] == 'response_too_large'


@pytest.mark.parametrize('raw,expected', [
    (envelope('{}', finish='length'), 'incomplete_model_response'),
    (envelope('{}', message_extra={'tool_calls': []}),
     'invalid_plain_assistant_message'),
    (envelope('{}', message_extra={'function_call': {'name': 'tool'}}),
     'invalid_plain_assistant_message'),
    (envelope(''), 'invalid_plain_assistant_message'),
    (envelope('{}', choices=[]), 'invalid_choice_count'),
    (b'{"model":"loops-cpu-gpt-oss-20b","choices":['
     b'{"message":{"role":"assistant","content":"{}"},'
     b'"finish_reason":"stop","finish_reason":"length"}]}'
     , 'duplicate_response_key'),
])
def test_invalid_assistant_envelope_retains_checker_receipt(frozen, raw, expected):
    run_dir, _ = frozen
    result = capture.capture_case(run_dir, 33, pins=pins(frozen, 33),
                                  opener=FakeOpener(FakeResponse(raw)))
    if expected == 'duplicate_response_key':
        assert result['status'] == 'identity_unverified'
        return
    assert result['status'] == 'captured'
    checked = capture.evaluate_case(run_dir, 33)
    assert checked['extraction_status'] == expected
    assert checked['checker']['decision'] == 'rejected'
    assert checked['content_sha256'] == cf.digest(b'')
    assert capture.verify_run(run_dir)['counts']['format_rejection'] == 1


def test_raw_or_evaluation_tamper_fails_verify(frozen):
    run_dir, _ = frozen
    raw = envelope('{"schema":"chess-no-forward-teaching-output/v9","kind":"abstention"}')
    capture.capture_case(run_dir, 33, pins=pins(frozen, 33),
                         opener=FakeOpener(FakeResponse(raw)))
    capture.evaluate_case(run_dir, 33)
    case_dir = run_dir / 'ply33'
    evaluation_path = case_dir / capture.EVALUATION_FILE
    original = evaluation_path.read_bytes()
    evaluation_path.write_bytes(b'{}\n')
    with pytest.raises(ValueError):
        capture.verify_run(run_dir)
    evaluation_path.write_bytes(original)
    (case_dir / capture.RAW_FILE).write_bytes(b'tampered')
    with pytest.raises(ValueError):
        capture.verify_run(run_dir)
