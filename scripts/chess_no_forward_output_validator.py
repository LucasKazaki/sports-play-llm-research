"""Offline structural validation for retained no-forward local chess responses.

This module never calls a model or engine.  It first re-verifies the frozen
generation capture, then treats raw model output as untrusted.  Only a narrow,
versioned JSON assertion envelope can become an admissible structural claim;
ordinary prose is retained as an abstention with a reason.  This is not a
commentary-quality, factuality, heldout, or independent-acceptance result.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import chess_counterfactual_evidence as cf
import chess_no_forward_generation_runner as runner


SCHEMA = 'chess-no-forward-output-validator/v1'
OUTPUT_SCHEMA = 'chess-no-forward-commentary-output/v1'
REPORT_SCHEMA = 'chess-no-forward-output-validation/v1'
MAX_CONTENT_BYTES = 16_384
MAX_ASSERTIONS = 16

# These are exactly values already present in the no-forward generator packet.
# In particular, no post-move FEN, PV, reply sequence, puzzle label, or
# evaluator-only field can be admitted through the output schema.
BOARD_FACT_FIELDS = (
    'side_to_move', 'selected_move.uci', 'selected_move.san',
    'moving_piece', 'moving_color', 'from', 'to', 'capture', 'captured_piece',
    'captured_square', 'en_passant', 'castling', 'promotion', 'gives_check',
)
ASSERTION_KINDS = (
    'legal_board_fact', 'retained_engine_observation',
    'bounded_strategic_hypothesis', 'abstention',
)
OUTCOME_FIELDS = (
    'ordinal', 'request_id', 'input_sha256', 'raw_sha256', 'raw_bytes',
    'capture_status', 'response_envelope', 'content_sha256', 'decision',
    'reason', 'assertion_kinds',
)
REPORT_FIELDS = (
    'schema', 'validator_sha256', 'generation_manifest_sha256',
    'generation_results_sha256', 'source_receipt_sha256', 'requested',
    'accounted', 'captured_model_calls', 'model_calls', 'new_engine_calls',
    'heldout_outcomes_scored', 'commentary_capability_gate_passed',
    'commentary_quality_evaluated', 'independent_acceptance', 'decision_counts',
    'envelope_counts', 'outcomes', 'limitations',
)
LIMITATIONS = (
    'Offline structural validation only; no new model or engine calls occur.',
    'Admissible structure does not establish factuality, teaching quality, or professional commentary.',
    'Development outputs are not game-disjoint heldout commentary evidence.',
    'Untyped prose is retained but rejected as an admissible assertion.',
)


def _require_string(value, message, maximum=MAX_CONTENT_BYTES):
    cf.require(type(value) is str and 0 < len(value.encode('utf-8')) <= maximum, message)


def _read_raw(run_dir, outcome):
    cf.require(outcome['raw_path'] is not None, 'captured_output_missing_raw_path')
    path = Path(run_dir) / outcome['raw_path']
    raw = runner._read_bytes(path, runner.MAX_RAW_BYTES, 'output_raw_exceeds_byte_budget')
    cf.require(len(raw) == outcome['raw_bytes'] and cf.digest(raw) == outcome['raw_sha256'],
               'output_raw_binding_changed')
    return raw


def _packet_value(packet, field):
    if field == 'side_to_move':
        return packet['side_to_move']
    if field.startswith('selected_move.'):
        return packet['selected_move'][field.split('.', 1)[1]]
    return packet['transition'][field]


def _validate_primitive(packet, assertion):
    """Return a structural claim kind, or raise without attempting repair."""
    cf.require(isinstance(assertion, dict), 'assertion_not_object')
    kind = assertion.get('kind')
    if kind == 'legal_board_fact':
        cf.exact_keys(assertion, ('kind', 'field', 'value'), 'invalid_board_fact_shape')
        cf.require(assertion['field'] in BOARD_FACT_FIELDS, 'unsupported_board_fact_field')
        cf.require(cf.canonical(assertion['value']) ==
                   cf.canonical(_packet_value(packet, assertion['field'])),
                   'board_fact_not_checkable_from_no_forward_packet')
        return kind
    if kind == 'retained_engine_observation':
        cf.exact_keys(assertion, ('kind', 'score'), 'invalid_engine_observation_shape')
        cf.require(cf.canonical(assertion['score']) ==
                   cf.canonical(packet['engine_observation']['score']),
                   'engine_observation_not_exact_retained_score')
        return kind
    raise ValueError('unsupported_primitive_assertion_kind')


def _validate_assertion(packet, assertion):
    cf.require(isinstance(assertion, dict) and assertion.get('kind') in ASSERTION_KINDS,
               'unsupported_assertion_kind')
    kind = assertion['kind']
    if kind in ('legal_board_fact', 'retained_engine_observation'):
        return _validate_primitive(packet, assertion)
    if kind == 'bounded_strategic_hypothesis':
        cf.exact_keys(assertion, ('kind', 'concept', 'evidence', 'uncertainty'),
                      'invalid_strategic_hypothesis_shape')
        cf.require(assertion['concept'] in packet['concept_vocabulary'],
                   'unsupported_strategic_concept')
        _require_string(assertion['uncertainty'], 'missing_strategic_uncertainty', 512)
        evidence = assertion['evidence']
        cf.require(isinstance(evidence, list) and 1 <= len(evidence) <= 4,
                   'invalid_strategic_evidence_count')
        for item in evidence:
            _validate_primitive(packet, item)
        return kind
    cf.exact_keys(assertion, ('kind', 'reason'), 'invalid_abstention_shape')
    _require_string(assertion['reason'], 'invalid_abstention_reason', 512)
    return kind


def validate_typed_content(packet, content):
    """Validate strict response content without inferring prose or chess strategy."""
    _require_string(content, 'response_content_missing_or_too_large')
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return {'decision': 'abstain', 'reason': 'untyped_response_content',
                'assertion_kinds': []}
    try:
        cf.exact_keys(value, ('schema', 'assertions'), 'invalid_typed_output_root')
        cf.require(value['schema'] == OUTPUT_SCHEMA, 'invalid_typed_output_schema')
        assertions = value['assertions']
        cf.require(isinstance(assertions, list) and 1 <= len(assertions) <= MAX_ASSERTIONS,
                   'invalid_typed_assertion_count')
        kinds = [_validate_assertion(packet, assertion) for assertion in assertions]
        cf.require('abstention' not in kinds or len(kinds) == 1,
                   'abstention_must_not_mix_with_assertions')
    except (TypeError, ValueError):
        return {'decision': 'abstain', 'reason': 'unsupported_or_uncheckable_typed_assertion',
                'assertion_kinds': []}
    return {
        'decision': 'admissible_abstention' if kinds == ['abstention']
        else 'admissible_typed_assertions',
        'reason': None,
        'assertion_kinds': kinds,
    }


def _envelope_content(raw, expected_model):
    """Return a response-envelope classification and untrusted assistant content."""
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 'unrecognized', None, 'raw_response_not_json'
    if isinstance(value, dict) and set(value) == {'status', 'reason'} and \
            value.get('status') == 'abstain' and type(value.get('reason')) is str:
        return 'declared_abstention', value['reason'], None
    if not isinstance(value, dict) or value.get('object') != 'chat.completion' or \
            value.get('model') != expected_model:
        return 'unrecognized', None, 'unrecognized_local_response_envelope'
    choices = value.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        return 'unrecognized', None, 'unrecognized_local_response_envelope'
    choice = choices[0]
    message = choice.get('message')
    if choice.get('index') != 0 or not isinstance(message, dict) or \
            message.get('role') != 'assistant' or \
            (message.get('tool_calls') not in (None, [])) or type(message.get('content')) is not str:
        return 'unrecognized', None, 'unrecognized_local_response_envelope'
    content = message['content']
    if not content or len(content.encode('utf-8')) > MAX_CONTENT_BYTES:
        return 'openai_chat_completion', None, 'response_content_missing_or_too_large'
    return 'openai_chat_completion', content, None


def validate_raw_response(packet, raw, expected_model):
    """Classify one retained response as structural claims or a fail-safe abstention."""
    envelope, content, envelope_error = _envelope_content(raw, expected_model)
    if envelope_error:
        return {'response_envelope': envelope, 'content_sha256': None,
                'decision': 'abstain', 'reason': envelope_error, 'assertion_kinds': []}
    content_sha256 = cf.digest(content.encode('utf-8'))
    if envelope == 'declared_abstention':
        try:
            _require_string(content, 'invalid_abstention_reason', 512)
        except ValueError:
            return {'response_envelope': envelope, 'content_sha256': content_sha256,
                    'decision': 'abstain', 'reason': 'invalid_abstention_reason',
                    'assertion_kinds': []}
        return {'response_envelope': envelope, 'content_sha256': content_sha256,
                'decision': 'admissible_abstention', 'reason': None,
                'assertion_kinds': ['abstention']}
    decision = validate_typed_content(packet, content)
    return {'response_envelope': envelope, 'content_sha256': content_sha256, **decision}


def validate_run(data_root, source_path, source_sha256, typed_packet_path, run_dir):
    """Build a hash-bound structural report from a completed frozen capture."""
    run_dir = Path(run_dir)
    integrity = runner.verify_results(data_root, source_path, source_sha256, typed_packet_path, run_dir)
    manifest = runner._read_json(run_dir / 'manifest.json')
    results = runner._read_json(run_dir / 'results.json')
    cf.require(integrity['integrity_passed'] is True, 'generation_integrity_not_passed')
    outcomes = []
    expected_model = manifest['observed_route']['model_id']
    for request, captured in zip(manifest['requests'], results['outcomes']):
        base = {
            'ordinal': request['ordinal'], 'request_id': request['request_id'],
            'input_sha256': request['input_sha256'], 'raw_sha256': captured['raw_sha256'],
            'raw_bytes': captured['raw_bytes'], 'capture_status': captured['status'],
        }
        if captured['status'] != 'captured':
            decision = {'response_envelope': 'none', 'content_sha256': None,
                        'decision': 'abstain', 'reason': 'transport_' + captured['status'],
                        'assertion_kinds': []}
        else:
            raw = _read_raw(run_dir, captured)
            packet = json.loads(runner._read_bytes(run_dir / request['input_path'],
                                                   runner.MAX_PACKET_BYTES,
                                                   'frozen_input_packet_exceeds_byte_budget'))
            decision = validate_raw_response(packet, raw, expected_model)
        row = {**base, **decision}
        cf.exact_keys(row, OUTCOME_FIELDS, 'invalid_output_validation_outcome')
        outcomes.append(row)
    cf.require(len(outcomes) == len(manifest['requests']) == results['requested'],
               'output_validation_denominator_changed')
    decision_counts = dict(sorted(Counter(row['decision'] for row in outcomes).items()))
    envelope_counts = dict(sorted(Counter(row['response_envelope'] for row in outcomes).items()))
    report = {
        'schema': REPORT_SCHEMA,
        'validator_sha256': cf.file_digest(Path(__file__)),
        'generation_manifest_sha256': cf.file_digest(run_dir / 'manifest.json'),
        'generation_results_sha256': cf.file_digest(run_dir / 'results.json'),
        'source_receipt_sha256': source_sha256,
        'requested': len(outcomes), 'accounted': len(outcomes),
        'captured_model_calls': integrity['model_calls'],
        'model_calls': 0, 'new_engine_calls': 0, 'heldout_outcomes_scored': 0,
        'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False, 'independent_acceptance': False,
        'decision_counts': decision_counts, 'envelope_counts': envelope_counts,
        'outcomes': outcomes, 'limitations': list(LIMITATIONS),
    }
    cf.exact_keys(report, REPORT_FIELDS, 'invalid_output_validation_report')
    return report


def write_report(report, output):
    """Publish a create-only report; retained capture data is never overwritten."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = cf.canonical(report) + b'\n'
    cf.require(len(encoded) <= cf.MAX_RECEIPT_BYTES, 'output_validation_report_exceeds_byte_budget')
    with output.open('xb') as stream:
        stream.write(encoded)


def verify_report(data_root, source_path, source_sha256, typed_packet_path, run_dir, output):
    expected = validate_run(data_root, source_path, source_sha256, typed_packet_path, run_dir)
    retained = runner._read_json(output)
    cf.require(cf.canonical(retained) == cf.canonical(expected),
               'output_validation_report_differs_from_current_bindings')
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'verify'))
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--typed-packet', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'validate':
        report = validate_run(args.data, args.source, args.source_sha256,
                              args.typed_packet, args.run_dir)
        write_report(report, args.output)
    else:
        report = verify_report(args.data, args.source, args.source_sha256,
                               args.typed_packet, args.run_dir, args.output)
    print(json.dumps({
        'schema': SCHEMA, 'requested': report['requested'],
        'admissible': sum(value for key, value in report['decision_counts'].items()
                          if key.startswith('admissible_')),
        'model_calls': 0, 'engine_calls': 0,
        'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False,
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
