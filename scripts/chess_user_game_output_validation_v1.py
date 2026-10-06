#!/usr/bin/env python3
"""Offline structural check of one frozen, source-bound user-game model attempt.

This is a software and transport receipt, not a chess explanation evaluation.
It makes no model or engine call. The generator must never receive this report,
the saved review's continuations, or other evaluator-side material.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import chess_counterfactual_evidence as cf
import chess_no_forward_output_validator as typed_output
import chess_user_game_generation_v1 as generation
import chess_user_game_no_forward_v1 as user_packet


SCHEMA = 'chess-user-game-output-validation/v1'
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
LIMITATIONS = [
    'Offline structural validation only; this step makes zero new model or engine calls.',
    'The saved user game is a practice case, not a blind game-disjoint holdout.',
    'Typed structure does not establish a sound strategic lesson or why Stockfish scored a move.',
    'The retained engine observation was not independently reproduced for this model output.',
    'A failed or identity-unverified attempt remains in the one-request denominator.',
]


def _pin(actual: str | None, expected: str | None, name: str) -> None:
    if (type(expected) is not str or SHA256.fullmatch(expected) is None or
            actual != expected):
        raise ValueError(f'{name}_sha256_changed_or_unpinned')


def _result_pins(run_dir: Path, *, manifest_sha256: str, packet_sha256: str,
                 request_sha256: str, result_sha256: str | None) -> dict:
    """Bind the exact retained files; a spent request may lack a result."""
    paths = {
        'manifest': run_dir / generation.MANIFEST_FILE,
        'packet': run_dir / generation.PACKET_FILE,
        'request': run_dir / generation.REQUEST_FILE,
        'result': run_dir / generation.RESULT_FILE,
    }
    actual = {name: cf.file_digest(path) if path.is_file() else None
              for name, path in paths.items()}
    _pin(actual['manifest'], manifest_sha256, 'manifest')
    _pin(actual['packet'], packet_sha256, 'packet')
    _pin(actual['request'], request_sha256, 'request')
    if actual['result'] is None:
        if result_sha256 is not None:
            raise ValueError('missing_result_with_supplied_pin')
    else:
        _pin(actual['result'], result_sha256, 'result')
    return actual


def _no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate_response_key')
        value[key] = item
    return value


def _duplicate_key_error(raw: bytes) -> bool:
    """Reject ambiguous JSON envelopes or typed content before v1 reuse."""
    try:
        envelope = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
        if isinstance(envelope, dict) and isinstance(envelope.get('choices'), list):
            choices = envelope['choices']
            if len(choices) == 1 and isinstance(choices[0], dict):
                message = choices[0].get('message')
                if isinstance(message, dict) and type(message.get('content')) is str:
                    try:
                        json.loads(message['content'], object_pairs_hook=_no_duplicate_keys)
                    except json.JSONDecodeError:
                        pass  # The existing validator records untyped prose.
    except ValueError as error:
        return str(error) == 'duplicate_response_key'
    except (UnicodeError, RecursionError):
        return False  # The existing validator will reject malformed raw data.
    return False


def _no_claim(reason: str) -> dict:
    return {'response_envelope': 'none', 'content_sha256': None,
            'decision': 'abstain', 'reason': reason, 'assertion_kinds': []}


def _classify(packet: dict, result: dict, raw: bytes | None, expected_model: str) -> dict:
    """Only a captured, matched, successful response reaches typed validation."""
    if result['status'] != 'captured':
        return _no_claim('capture_not_admitted')
    if (result['model_identity'] != 'matched' or
            result['observed_model_id'] != expected_model):
        return _no_claim('model_identity_not_matched')
    if (type(result['http_status']) is not int or
            not 200 <= result['http_status'] < 300 or
            result['error'] is not None or raw is None):
        return _no_claim('captured_response_inconsistent')
    if _duplicate_key_error(raw):
        return _no_claim('duplicate_response_key')
    try:
        return typed_output.validate_raw_response(packet, raw, expected_model)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return _no_claim('uncheckable_response_content')


def validate_run(run_dir: Path, *, manifest_sha256: str, packet_sha256: str,
                 request_sha256: str, result_sha256: str | None) -> dict:
    """Verify the runner first, then account for its sole attempted request."""
    run_dir = Path(run_dir).resolve()
    integrity = generation.verify_run(run_dir)
    if integrity['status'] == 'frozen':
        raise ValueError('user_game_generation_not_attempted')
    if integrity['status'] == 'interrupted':
        if integrity['attempts_consumed'] != 1 or integrity['integrity_passed'] is not False:
            raise ValueError('invalid_interrupted_attempt_accounting')
    elif (integrity['integrity_passed'] is not True or
          integrity['attempts_consumed'] != 1):
        raise ValueError('user_game_generation_integrity_not_passed')
    pins = _result_pins(run_dir, manifest_sha256=manifest_sha256,
                        packet_sha256=packet_sha256, request_sha256=request_sha256,
                        result_sha256=result_sha256)
    manifest = generation._json(run_dir / generation.MANIFEST_FILE)
    packet_raw = generation._read(run_dir / generation.PACKET_FILE,
                                  user_packet.MAX_PACKET_BYTES,
                                  'user_game_validation_packet_too_large')
    packet = json.loads(packet_raw)
    user_packet._shape(packet)
    if (packet_raw != cf.canonical(packet) or
            packet['source']['move_role'] != manifest['role'] or
            manifest['packet_sha256'] != pins['packet'] or
            manifest['request_sha256'] != pins['request']):
        raise ValueError('user_game_validation_packet_or_request_changed')
    expected_model = manifest['route']['model_id']
    result = None if pins['result'] is None else generation._json(
        run_dir / generation.RESULT_FILE)
    unverified_raw = None
    if result is None:
        if integrity['status'] != 'interrupted':
            raise ValueError('completed_attempt_missing_result')
        raw_path = run_dir / generation.RAW_FILE
        if raw_path.exists():
            unverified_raw = generation._read(raw_path, generation.MAX_RAW_BYTES + 1,
                                               'interrupted_raw_too_large')
        decision = _no_claim('interrupted_without_result')
        capture_status = 'interrupted'
        raw = None
    else:
        if result['status'] != integrity['status']:
            raise ValueError('generation_status_changed_after_verification')
        capture_status = result['status']
        raw = (generation._read(run_dir / generation.RAW_FILE, generation.MAX_RAW_BYTES + 1,
                                'user_game_validation_raw_too_large')
               if result['raw_path'] is not None else None)
        if raw is not None and (cf.digest(raw) != result['raw_sha256'] or
                                len(raw) != result['raw_bytes']):
            raise ValueError('user_game_validation_raw_changed')
        decision = _classify(packet, result, raw, expected_model)
    outcome = {
        'attempt': 1, 'capture_status': capture_status,
        'model_identity': result['model_identity'] if result else 'unverified',
        'observed_model_id': result['observed_model_id'] if result else None,
        'http_status': result['http_status'] if result else None,
        'raw_classification': result['raw_classification'] if result else
        'unverified_without_result' if unverified_raw is not None else None,
        'raw_sha256': result['raw_sha256'] if result else
        cf.digest(unverified_raw) if unverified_raw is not None else None,
        'raw_bytes': result['raw_bytes'] if result else
        len(unverified_raw) if unverified_raw is not None else 0,
        'latency_ns': result['latency_ns'] if result else None,
        'capture_error': result['error'] if result else None,
        **decision,
    }
    return {
        'schema': SCHEMA, 'validator_sha256': cf.file_digest(Path(__file__)),
        'manifest_sha256': pins['manifest'], 'packet_sha256': pins['packet'],
        'request_sha256': pins['request'], 'result_sha256': pins['result'],
        'source': dict(packet['source']), 'expected_model_id': expected_model,
        'requested': 1, 'accounted': 1, 'attempts_consumed': 1,
        'captured_model_calls': result['model_calls'] if result else None,
        'captured_model_calls_upper_bound': 1 if result is None else None,
        'new_model_calls': 0, 'new_engine_calls': 0,
        'heldout_outcomes_scored': 0, 'commentary_capability_gate_passed': False,
        'commentary_quality_evaluated': False, 'independent_acceptance': False,
        'outcomes': [outcome], 'limitations': list(LIMITATIONS),
    }


def write_report(report: dict, output: Path) -> None:
    raw = cf.canonical(report) + b'\n'
    if len(raw) > cf.MAX_RECEIPT_BYTES:
        raise ValueError('user_game_validation_report_too_large')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)


def verify_report(run_dir: Path, output: Path, **pins) -> dict:
    expected = validate_run(run_dir, **pins)
    raw = generation._read(output, cf.MAX_RECEIPT_BYTES,
                           'user_game_validation_report_too_large')
    if raw != cf.canonical(expected) + b'\n':
        raise ValueError('user_game_validation_report_changed')
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'verify'))
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--result-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    pins = {'manifest_sha256': args.manifest_sha256,
            'packet_sha256': args.packet_sha256,
            'request_sha256': args.request_sha256,
            'result_sha256': args.result_sha256}
    if args.command == 'validate':
        report = validate_run(args.run_dir, **pins)
        write_report(report, args.output)
    else:
        report = verify_report(args.run_dir, args.output, **pins)
    outcome = report['outcomes'][0]
    print(json.dumps({'schema': SCHEMA, 'requested': 1, 'accounted': 1,
                      'capture_status': outcome['capture_status'],
                      'decision': outcome['decision'],
                      'reason': outcome['reason'],
                      'new_model_calls': 0, 'new_engine_calls': 0,
                      'commentary_capability_gate_passed': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
