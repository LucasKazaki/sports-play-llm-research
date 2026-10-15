"""Fake one-attempt captures for offline user-game output accounting only."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
from urllib.error import HTTPError

import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_user_game_generation_v1 as generation
import chess_user_game_output_validation_v1 as validation
from test_chess_user_game_generation_v1 import ROUTE, Response, bundle  # synthetic fixture


def _content(packet: dict, assertions: list[dict]) -> str:
    return json.dumps({'schema': 'chess-no-forward-commentary-output/v1',
                       'assertions': assertions})


def _response(content: str, model: str | None = ROUTE['model_id']) -> bytes:
    envelope = {'object': 'chat.completion',
                'choices': [{'index': 0, 'message': {'role': 'assistant',
                                                     'content': content}}]}
    if model is not None:
        envelope['model'] = model
    return cf.canonical(envelope)


def _facts_and_score(packet: dict) -> str:
    return _content(packet, [
        {'kind': 'legal_board_fact', 'field': 'selected_move.san',
         'value': packet['selected_move']['san']},
        {'kind': 'retained_engine_observation',
         'score': packet['engine_observation']['score']},
    ])


def _pins(run_dir: Path) -> dict:
    def file_hash(name):
        path = run_dir / name
        return cf.file_digest(path) if path.exists() else None
    return {'manifest_sha256': file_hash(generation.MANIFEST_FILE),
            'packet_sha256': file_hash(generation.PACKET_FILE),
            'request_sha256': file_hash(generation.REQUEST_FILE),
            'result_sha256': file_hash(generation.RESULT_FILE)}


def _captured(bundle, body: bytes, *, http_status: int = 200) -> Path:
    run_dir = bundle[-1]
    generation.freeze_run(*bundle)

    class Opener:
        def open(self, request, timeout):
            assert request.get_method() == 'POST'
            assert (run_dir / generation.REQUEST_FILE).read_bytes() == request.data
            return Response(body, http_status)

    generation.capture_frozen_run(run_dir, opener=Opener())
    return run_dir


def _forbid_new_calls(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('offline validator must not call an engine or model')
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', forbidden)
    monkeypatch.setattr(generation, 'capture_frozen_run', forbidden)


def test_exact_typed_fact_and_score_admitted_only_after_full_verification(
        bundle, monkeypatch, tmp_path):
    packet = json.loads(bundle[6].read_bytes())
    run_dir = _captured(bundle, _response(_facts_and_score(packet)))
    _forbid_new_calls(monkeypatch)
    report = validation.validate_run(run_dir, **_pins(run_dir))
    row = report['outcomes'][0]
    assert report['requested'] == report['accounted'] == report['attempts_consumed'] == 1
    assert report['captured_model_calls'] == 1
    assert report['new_model_calls'] == report['new_engine_calls'] == 0
    assert report['source']['use_role'] == 'postgame_practice_only'
    assert report['commentary_capability_gate_passed'] is False
    assert row['capture_status'] == 'captured' and row['model_identity'] == 'matched'
    assert row['decision'] == 'admissible_typed_assertions'
    assert row['assertion_kinds'] == ['legal_board_fact', 'retained_engine_observation']
    assert row['raw_sha256'] == cf.file_digest(run_dir / generation.RAW_FILE)
    output = tmp_path / 'validation.json'
    validation.write_report(report, output)
    assert validation.verify_report(run_dir, output, **_pins(run_dir)) == report
    with pytest.raises(FileExistsError):
        validation.write_report(report, output)
    output.write_bytes(output.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='report_changed'):
        validation.verify_report(run_dir, output, **_pins(run_dir))


def test_unsupported_strategy_is_not_admitted(bundle, monkeypatch):
    packet = json.loads(bundle[6].read_bytes())
    content = _content(packet, [
        {'kind': 'bounded_strategic_hypothesis', 'concept': 'magic_win',
         'evidence': [{'kind': 'legal_board_fact', 'field': 'selected_move.san',
                       'value': packet['selected_move']['san']}],
         'uncertainty': 'Only a guess.'},
    ])
    run_dir = _captured(bundle, _response(content))
    _forbid_new_calls(monkeypatch)
    row = validation.validate_run(run_dir, **_pins(run_dir))['outcomes'][0]
    assert row['decision'] == 'abstain'
    assert row['reason'] == 'unsupported_or_uncheckable_typed_assertion'
    assert row['assertion_kinds'] == []


@pytest.mark.parametrize(('content', 'reason'), [
    ('A confident but untyped chess lesson.', 'untyped_response_content'),
    ('{"schema":"chess-no-forward-commentary-output/v1","assertions":[]}',
     'unsupported_or_uncheckable_typed_assertion'),
    ('{"schema":"chess-no-forward-commentary-output/v1",'
     '"schema":"chess-no-forward-commentary-output/v1","assertions":[]}',
     'duplicate_response_key'),
])
def test_malformed_or_ambiguous_content_remains_abstention(
        bundle, monkeypatch, content, reason):
    run_dir = _captured(bundle, _response(content))
    _forbid_new_calls(monkeypatch)
    row = validation.validate_run(run_dir, **_pins(run_dir))['outcomes'][0]
    assert row['decision'] == 'abstain' and row['reason'] == reason
    assert row['capture_status'] == 'captured' and row['model_identity'] == 'matched'


@pytest.mark.parametrize(('model', 'expected_status'), [
    ('foreign-model', 'identity_mismatch'),
    (None, 'identity_unverified'),
])
def test_identity_mismatch_or_unverified_never_admits_typed_content(
        bundle, monkeypatch, model, expected_status):
    packet = json.loads(bundle[6].read_bytes())
    run_dir = _captured(bundle, _response(_facts_and_score(packet), model=model))
    _forbid_new_calls(monkeypatch)
    row = validation.validate_run(run_dir, **_pins(run_dir))['outcomes'][0]
    assert row['capture_status'] == expected_status
    assert row['decision'] == 'abstain'
    assert row['reason'] in ('capture_not_admitted', 'model_identity_not_matched')
    assert row['assertion_kinds'] == []


def test_transport_and_http_failures_remain_in_one_attempt_denominator(bundle, monkeypatch):
    run_dir = bundle[-1]
    generation.freeze_run(*bundle)

    class TimeoutOpener:
        def open(self, *_args, **_kwargs):
            raise TimeoutError('synthetic timeout')

    generation.capture_frozen_run(run_dir, opener=TimeoutOpener())
    _forbid_new_calls(monkeypatch)
    report = validation.validate_run(run_dir, **_pins(run_dir))
    assert report['requested'] == report['accounted'] == 1
    assert report['outcomes'][0]['capture_status'] == 'transport_failure'
    assert report['outcomes'][0]['decision'] == 'abstain'
    assert report['outcomes'][0]['raw_sha256'] is None


def test_http_failure_raw_body_cannot_be_admitted(bundle, monkeypatch):
    run_dir = bundle[-1]
    generation.freeze_run(*bundle)

    class ErrorOpener:
        def open(self, request, timeout):
            body = _response(_facts_and_score(json.loads(bundle[6].read_bytes())))
            raise HTTPError(request.full_url, 503, 'synthetic failure', {}, BytesIO(body))

    generation.capture_frozen_run(run_dir, opener=ErrorOpener())
    _forbid_new_calls(monkeypatch)
    row = validation.validate_run(run_dir, **_pins(run_dir))['outcomes'][0]
    assert row['capture_status'] == 'http_error'
    assert row['model_identity'] == 'matched'
    assert row['decision'] == 'abstain' and row['reason'] == 'capture_not_admitted'


def test_oversized_response_prefix_is_accounted_without_content_admission(
        bundle, monkeypatch):
    prefix = b'X' * (generation.MAX_RAW_BYTES + 1)
    run_dir = _captured(bundle, prefix)
    _forbid_new_calls(monkeypatch)
    row = validation.validate_run(run_dir, **_pins(run_dir))['outcomes'][0]
    assert row['capture_status'] == 'response_too_large'
    assert row['raw_bytes'] == generation.MAX_RAW_BYTES + 1
    assert row['raw_sha256'] == cf.file_digest(run_dir / generation.RAW_FILE)
    assert row['decision'] == 'abstain' and row['reason'] == 'capture_not_admitted'


@pytest.mark.parametrize('changed', ['raw', 'packet', 'request', 'result', 'pin'])
def test_tampered_capture_or_wrong_result_pin_cannot_be_reported(bundle, changed):
    packet = json.loads(bundle[6].read_bytes())
    run_dir = _captured(bundle, _response(_facts_and_score(packet)))
    pins = _pins(run_dir)
    if changed == 'pin':
        pins['result_sha256'] = '0' * 64
    else:
        names = {'raw': generation.RAW_FILE, 'packet': generation.PACKET_FILE,
                 'request': generation.REQUEST_FILE, 'result': generation.RESULT_FILE}
        path = run_dir / names[changed]
        if changed == 'result':
            value = json.loads(path.read_bytes())
            value['latency_ns'] += 1  # Runner permits it; the external pin must catch it.
            path.write_bytes(cf.canonical(value) + b'\n')
        else:
            path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError):
        validation.validate_run(run_dir, **pins)


@pytest.mark.parametrize('raw_present', [False, True])
def test_interrupted_request_is_accounted_without_a_result(
        bundle, monkeypatch, raw_present):
    run_dir = bundle[-1]
    generation.freeze_run(*bundle)
    (run_dir / generation.REQUEST_FILE).write_bytes(generation.build_request(
        (run_dir / generation.PACKET_FILE).read_bytes(), ROUTE))
    if raw_present:
        (run_dir / generation.RAW_FILE).write_bytes(b'unbound partial response')
    _forbid_new_calls(monkeypatch)
    report = validation.validate_run(run_dir, **_pins(run_dir))
    assert report['requested'] == report['accounted'] == 1
    assert report['result_sha256'] is None
    assert report['captured_model_calls_upper_bound'] == 1
    assert report['outcomes'][0]['capture_status'] == 'interrupted'
    assert report['outcomes'][0]['decision'] == 'abstain'
    assert report['outcomes'][0]['raw_classification'] == (
        'unverified_without_result' if raw_present else None)
    assert report['outcomes'][0]['raw_bytes'] == (24 if raw_present else 0)


def test_unknown_future_status_fails_closed_without_parsing_raw(bundle):
    packet = json.loads(bundle[6].read_bytes())
    fake = {'status': 'future_status', 'model_identity': 'matched',
            'observed_model_id': ROUTE['model_id'], 'http_status': 200,
            'error': None}
    assert validation._classify(packet, fake, _response(_facts_and_score(packet)),
                                ROUTE['model_id']) == validation._no_claim(
                                    'capture_not_admitted')
