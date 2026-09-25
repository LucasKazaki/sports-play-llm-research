"""Focused offline checks for retained no-forward response validation."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_output_validator as validator


DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
TYPED = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
RUN = ROOT / 'artifacts/chess-no-forward-generation-v1/dev8-20260923T105300Z'
SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'


def packet():
    return json.loads((RUN / 'inputs/02.packet.json').read_bytes())


def response(content, *, model='loops-cpu-gpt-oss-20b'):
    return json.dumps({
        'object': 'chat.completion', 'model': model,
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content,
                                              'tool_calls': []}}],
    }, sort_keys=True).encode('utf-8')


def typed(assertions):
    return json.dumps({'schema': validator.OUTPUT_SCHEMA, 'assertions': assertions},
                      sort_keys=True)


def test_actual_retained_capture_is_hash_bound_and_prose_abstains_without_model_or_engine():
    import chess.engine
    original = chess.engine.SimpleEngine.popen_uci
    chess.engine.SimpleEngine.popen_uci = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError('validator must not start an engine'))
    try:
        report = validator.validate_run(DATA, SOURCE, SHA, TYPED, RUN)
    finally:
        chess.engine.SimpleEngine.popen_uci = original
    assert report['requested'] == report['accounted'] == 8
    assert report['captured_model_calls'] == 8
    assert report['model_calls'] == report['new_engine_calls'] == report['heldout_outcomes_scored'] == 0
    assert report['decision_counts'] == {'abstain': 8}
    assert report['envelope_counts'] == {'none': 2, 'openai_chat_completion': 6}
    assert all(row['reason'] in ('transport_transport_failure', 'untyped_response_content')
               for row in report['outcomes'])
    assert report['commentary_capability_gate_passed'] is False
    assert report['commentary_quality_evaluated'] is False
    assert report['independent_acceptance'] is False


def test_strict_typed_packet_claims_and_bounded_hypothesis_are_admissible_only_when_checkable():
    value = packet()
    content = typed([
        {'kind': 'legal_board_fact', 'field': 'capture', 'value': value['transition']['capture']},
        {'kind': 'retained_engine_observation', 'score': value['engine_observation']['score']},
        {'kind': 'bounded_strategic_hypothesis', 'concept': 'material',
         'evidence': [{'kind': 'legal_board_fact', 'field': 'captured_piece',
                       'value': value['transition']['captured_piece']}],
         'uncertainty': 'This is a bounded hypothesis, not a forced continuation.'},
    ])
    checked = validator.validate_raw_response(value, response(content), 'loops-cpu-gpt-oss-20b')
    assert checked['response_envelope'] == 'openai_chat_completion'
    assert checked['decision'] == 'admissible_typed_assertions'
    assert checked['assertion_kinds'] == [
        'legal_board_fact', 'retained_engine_observation', 'bounded_strategic_hypothesis',
    ]


@pytest.mark.parametrize('assertion', [
    {'kind': 'legal_board_fact', 'field': 'fen_after', 'value': 'forbidden'},
    {'kind': 'legal_board_fact', 'field': 'capture', 'value': False},
    {'kind': 'retained_engine_observation', 'score': {'type': 'cp', 'value': 999}},
    {'kind': 'bounded_strategic_hypothesis', 'concept': 'material', 'evidence': [],
     'uncertainty': 'missing evidence'},
])
def test_unsupported_or_uncheckable_typed_claims_fail_safe_to_abstention(assertion):
    checked = validator.validate_raw_response(packet(), response(typed([assertion])),
                                              'loops-cpu-gpt-oss-20b')
    assert checked['decision'] == 'abstain'
    assert checked['reason'] == 'unsupported_or_uncheckable_typed_assertion'
    assert checked['assertion_kinds'] == []


def test_declared_abstention_is_admissible_but_mixed_or_unrecognized_output_is_not():
    direct = b'{"status":"abstain","reason":"insufficient source-bound evidence"}'
    checked = validator.validate_raw_response(packet(), direct, 'loops-cpu-gpt-oss-20b')
    assert checked['decision'] == 'admissible_abstention'
    mixed = typed([
        {'kind': 'abstention', 'reason': 'uncertain'},
        {'kind': 'legal_board_fact', 'field': 'capture', 'value': packet()['transition']['capture']},
    ])
    assert validator.validate_raw_response(packet(), response(mixed), 'loops-cpu-gpt-oss-20b')['decision'] == 'abstain'
    assert validator.validate_raw_response(packet(), response('{}', model='foreign-model'),
                                            'loops-cpu-gpt-oss-20b')['reason'] == \
        'unrecognized_local_response_envelope'


def test_create_only_report_verifies_bindings_and_rejects_tampering(tmp_path):
    output = tmp_path / 'report.json'
    report = validator.validate_run(DATA, SOURCE, SHA, TYPED, RUN)
    validator.write_report(report, output)
    assert validator.verify_report(DATA, SOURCE, SHA, TYPED, RUN, output)['requested'] == 8
    with pytest.raises(FileExistsError):
        validator.write_report(report, output)
    altered = json.loads(output.read_bytes())
    altered['decision_counts'] = {'admissible_typed_assertions': 8}
    output.write_bytes(cf.canonical(altered) + b'\n')
    with pytest.raises(ValueError, match='differs'):
        validator.verify_report(DATA, SOURCE, SHA, TYPED, RUN, output)


def test_tampered_raw_capture_is_rejected_before_any_output_decision(tmp_path):
    copied = tmp_path / 'run'
    shutil.copytree(RUN, copied)
    (copied / 'raw/02.bin').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='binding'):
        validator.validate_run(DATA, SOURCE, SHA, TYPED, copied)
