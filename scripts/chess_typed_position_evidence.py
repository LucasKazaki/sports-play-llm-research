"""Source-bound typed chess observations and conservative structured claim checks.

The caller pins a reviewed source receipt SHA256. This adapter preserves that
observation; it does not reproduce engine scores or establish explanation quality.
PositionEvidence v1 consumers must opt into this explicit typed v2 structure.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re

import chess
import chess_counterfactual_evidence as cf

SCHEMA = 'chess-typed-position-evidence/v1'
FACT_FIELDS = frozenset(('fen_before', 'fen_after', 'san', 'moving_piece', 'moving_color',
                        'from', 'to', 'capture', 'captured_piece', 'captured_square',
                        'en_passant', 'castling', 'promotion', 'gives_check', 'checkmate',
                        'material_delta'))
LIMITATIONS = [
    'Development inputs only; no new engine/model calls or heldout outcome scoring.',
    'Engine observations retain cp/mate types, perspective and bound qualification; exact is not ground truth.',
    'No human choices, generated explanations, strategic concepts or teaching-quality labels are inferred.',
    'Board facts are legally replayed. All comparative superiority and unsupported concept claims abstain.',
    'This versioned typed PositionEvidence v2 structure is not compatible with the scalar v1 score_cp contract.',
]


def _read_bounded(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(cf.MAX_RECEIPT_BYTES + 1)
    cf.require(len(raw) <= cf.MAX_RECEIPT_BYTES, 'receipt_exceeds_byte_budget')
    return raw


def _source(data_root, source_receipt_path, expected_source_sha256):
    cf.require(isinstance(expected_source_sha256, str) and
               re.fullmatch('[a-f0-9]{64}', expected_source_sha256), 'invalid_pinned_source_hash')
    raw = _read_bounded(source_receipt_path)
    cf.require(cf.digest(raw) == expected_source_sha256, 'pinned_source_receipt_changed')
    source = json.loads(raw)
    cf.require(isinstance(source, dict) and source.get('schema') == 'chess-counterfactual-evidence/v3',
               'typed_adapter_requires_v3')
    checked = cf.verify_receipt(Path(data_root), source)
    projection, _ = cf.load_development(Path(data_root))
    return source, checked, projection


def build_typed_position_evidence(data_root, source_receipt_path, expected_source_sha256):
    source, checked, projection = _source(data_root, source_receipt_path, expected_source_sha256)
    positions = []
    for case, row in zip(projection['items'], source['results']):
        item = {key: copy.deepcopy(row[key]) for key in
                ('position_id', 'game_id', 'source_url', 'split', 'status')}
        item.update(schema='position-evidence/v2', fen=case['fen'],
                    engine_evidence=copy.deepcopy(row['candidates']), commentary_evidence=[])
        if row['status'] == 'failed':
            item['error'] = copy.deepcopy(row['error'])
        positions.append(item)
    return {'schema': SCHEMA, 'source_receipt_sha256': expected_source_sha256,
            'source_manifest_sha256': source['source_manifest_sha256'],
            'source_projection_sha256': source['source_projection_sha256'],
            'source_implementation_sha256': copy.deepcopy(source['implementation_sha256']),
            'adapter_sha256': cf.file_digest(Path(__file__)), 'engine': copy.deepcopy(source['engine']),
            'requested_positions': checked['requested_positions'],
            'successful_positions': checked['successful_positions'], 'failed_positions': checked['failed_positions'],
            'legal_candidates': checked['legal_candidates'], 'positions': positions,
            'source_boundaries': copy.deepcopy(source['boundaries']), 'limitations': list(LIMITATIONS)}


def validate_typed_position_evidence(data_root, source_receipt_path, expected_source_sha256, packet):
    expected = build_typed_position_evidence(data_root, source_receipt_path, expected_source_sha256)
    # Canonical JSON equality distinguishes integers from booleans and floats.
    cf.require(cf.canonical(packet) == cf.canonical(expected), 'typed_evidence_differs_from_pinned_source')
    candidates = [candidate for row in expected['positions'] for candidate in row['engine_evidence']]
    return {'schema': 'chess-typed-position-check/v1', 'integrity_passed': True,
            'complete': expected['failed_positions'] == 0,
            **{key: expected[key] for key in ('requested_positions', 'successful_positions', 'failed_positions', 'legal_candidates')},
            'exact_candidates': sum(c['score']['bound'] == 'exact' for c in candidates),
            'qualified_candidates': sum(c['score']['bound'] != 'exact' for c in candidates),
            'model_calls': 0, 'engine_calls': 0, 'test_outcomes_scored': 0,
            'engine_scores_independently_reproduced': False,
            'packet_sha256': cf.digest(cf.canonical(packet))}


def validate_claim(data_root, source_receipt_path, expected_source_sha256, packet,
                   position_id, evidence_id, claim):
    """Validate trusted bindings before judging a structured claim; no NLP inference."""
    validate_typed_position_evidence(data_root, source_receipt_path, expected_source_sha256, packet)
    abstain = lambda reason: {'status': 'abstain', 'reason': reason}
    row = next((r for r in packet['positions'] if r['position_id'] == position_id), None)
    if row is None or row['status'] != 'succeeded':
        return abstain('unknown_or_failed_position')
    candidate = next((c for c in row['engine_evidence'] if c['evidence_id'] == evidence_id), None)
    if candidate is None:
        return abstain('unknown_position_bound_evidence')
    if not isinstance(claim, dict):
        return abstain('unsupported_claim_shape')
    if set(claim) == {'kind', 'field', 'value'} and claim['kind'] == 'board_fact':
        field = claim['field']
        if not isinstance(field, str) or field not in FACT_FIELDS:
            return abstain('unsupported_board_fact')
        projection, _ = cf.load_development(Path(data_root))
        case = next(c for c in projection['items'] if c['position_id'] == position_id)
        facts = cf.transition_evidence(cf.board_for(case), chess.Move.from_uci(candidate['move_uci']))
        if cf.canonical(claim['value']) != cf.canonical(facts[field]):
            return abstain('contradicted_by_replayed_board')
        return {'status': 'verified_board_fact', 'evidence_id': evidence_id, 'field': field}
    if set(claim) == {'kind', 'score'} and claim['kind'] == 'engine_observation':
        if cf.canonical(claim['score']) != cf.canonical(candidate['score']):
            return abstain('differs_from_retained_engine_observation')
        return {'status': 'verified_engine_observation', 'evidence_id': evidence_id,
                'independently_reproduced': False}
    return abstain('unsupported_claim_or_comparison')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build':
        packet = build_typed_position_evidence(args.data, args.source, args.source_sha256)
        cf.write_receipt(packet, args.output)
    else:
        packet = json.loads(_read_bounded(args.output))
    checked = validate_typed_position_evidence(args.data, args.source, args.source_sha256, packet)
    checked['receipt_sha256'] = cf.file_digest(args.output)
    print(json.dumps(checked, sort_keys=True))
    return 0 if checked['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

