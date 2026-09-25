"""Frozen evaluator-only experiment for source-bound extended chess claims.

This module validates structured occupation and variation assertions over the
retained development packet. It never builds a generator input, runs a model or
engine, scores heldout data, or converts a retained principal variation into a
commentary claim.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import chess
import chess_counterfactual_evidence as cf
import chess_extended_claims as extended
import chess_typed_position_evidence as adapter


MAX_CLAIMS = 512
MAX_BYTES = 2 * 1024 * 1024
SCHEMA = 'chess-extended-claim-manifest/v1'
REPORT_SCHEMA = 'chess-extended-claim-experiment/v1'
LIMITATIONS = [
    'This is evaluator-only plumbing over eight retained development boards, not commentary generation or quality evidence.',
    'Retained engine PVs are used only to check an explicit evaluator assertion and must never enter a generator packet.',
    'Synthetic false claims are software controls, not human labels or chess teaching judgments.',
    'No engine or model is called, and no heldout data are scored.',
]


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    cf.require(len(raw) <= MAX_BYTES, 'byte_budget_exceeded')
    return json.loads(raw)


def write_json(value, path):
    encoded = cf.canonical(value) + b'\n'
    cf.require(len(encoded) <= MAX_BYTES, 'byte_budget_exceeded')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(encoded)


def load_packet(data, source, source_sha, packet_path, packet_sha):
    cf.require(cf.file_digest(Path(packet_path)) == packet_sha, 'pinned_typed_packet_changed')
    packet = read_json(packet_path)
    adapter.validate_typed_position_evidence(data, source, source_sha, packet)
    return packet


def _piece(board, square):
    observed = board.piece_at(chess.parse_square(square))
    return None if observed is None else {
        'type': chess.piece_name(observed.piece_type),
        'color': chess.COLOR_NAMES[observed.color],
    }


def _opposite_piece(piece):
    if piece is None:
        return {'type': 'pawn', 'color': 'white'}
    return None


def _add_claim(claims, category, row, candidate, claim, expected_status, derivation,
               *, position_id=None, evidence_id=None):
    core = {
        'category': category,
        'origin_position_id': row['position_id'],
        'origin_evidence_id': candidate['evidence_id'],
        'position_id': position_id or row['position_id'],
        'evidence_id': evidence_id or candidate['evidence_id'],
        'claim': copy.deepcopy(claim),
        'expected_status': expected_status,
        'derivation': derivation,
    }
    claims.append({'claim_id': cf.digest(cf.canonical(core)), **core})


def freeze(data, source, source_sha, packet_path, packet_sha):
    """Return a deterministic manifest before running any claim validations."""
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    projection, _ = cf.load_development(Path(data))
    cases = {case['position_id']: case for case in projection['items']}
    claims = []
    good_rows = [row for row in packet['positions'] if row['status'] == 'succeeded']
    for row_index, row in enumerate(good_rows):
        case = cases[row['position_id']]
        foreign_row = good_rows[(row_index + 1) % len(good_rows)]
        foreign_evidence = foreign_row['engine_evidence'][0]['evidence_id']
        for candidate_index, candidate in enumerate(row['engine_evidence']):
            board = cf.board_for(case)
            selected = chess.Move.from_uci(candidate['move_uci'])
            cf.require(selected in board.legal_moves, 'typed_packet_selected_move_not_legal')
            from_square = chess.square_name(selected.from_square)
            to_square = chess.square_name(selected.to_square)
            before_piece = _piece(board, from_square)
            after_board = board.copy(stack=True)
            after_board.push(selected)
            after_piece = _piece(after_board, to_square)
            before_claim = {'kind': 'square_occupation', 'board': 'before',
                            'square': from_square, 'piece': before_piece}
            after_claim = {'kind': 'square_occupation', 'board': 'after_selected_move',
                           'square': to_square, 'piece': after_piece}
            _add_claim(claims, 'valid_before_occupation', row, candidate, before_claim,
                       'verified_board_fact', 'Replayed source-square occupation before selected legal move.')
            _add_claim(claims, 'valid_after_occupation', row, candidate, after_claim,
                       'verified_board_fact', 'Replayed destination-square occupation after selected legal move.')
            _add_claim(claims, 'valid_retained_pv', row, candidate,
                       {'kind': 'variation_legality', 'origin': 'retained_engine_pv',
                        'moves_uci': copy.deepcopy(candidate['pv_uci'])},
                       'verified_legal_variation',
                       'Exact retained evaluator-only PV for this selected candidate.')
            _add_claim(claims, 'valid_asserted_selected_move', row, candidate,
                       {'kind': 'variation_legality', 'origin': 'asserted_variation',
                        'moves_uci': [candidate['move_uci']]},
                       'verified_legal_variation',
                       'Single selected legal move without engine-continuation attribution.')
            _add_claim(claims, 'wrong_piece', row, candidate,
                       {**before_claim, 'piece': _opposite_piece(before_piece)}, 'abstain',
                       'Synthetic contradictory source-square occupation control.')
            _add_claim(claims, 'wrong_stage', row, candidate,
                       {'kind': 'square_occupation', 'board': 'after_selected_move',
                        'square': from_square, 'piece': before_piece}, 'abstain',
                       'Synthetic before/after stage confusion for moved source piece.')
            _add_claim(claims, 'foreign_evidence', row, candidate, before_claim, 'abstain',
                       'Synthetic evidence identity from a different real development position.',
                       evidence_id=foreign_evidence)
            _add_claim(claims, 'unknown_position', row, candidate, before_claim, 'abstain',
                       'Synthetic unknown position identity with a real evidence reference.',
                       position_id='unknown-position-control')
            if len(candidate['pv_uci']) > 1:
                _add_claim(claims, 'truncated_retained_pv', row, candidate,
                           {'kind': 'variation_legality', 'origin': 'retained_engine_pv',
                            'moves_uci': [candidate['move_uci']]}, 'abstain',
                           'Synthetic retained-PV attribution shortened to its first move.')
            other = row['engine_evidence'][(candidate_index + 1) % len(row['engine_evidence'])]
            if other['evidence_id'] != candidate['evidence_id']:
                _add_claim(claims, 'misattributed_pv', row, candidate,
                           {'kind': 'variation_legality', 'origin': 'retained_engine_pv',
                            'moves_uci': copy.deepcopy(other['pv_uci'])}, 'abstain',
                           'Synthetic PV attribution from another candidate at this position.')
            _add_claim(claims, 'illegal_later_ply', row, candidate,
                       {'kind': 'variation_legality', 'origin': 'asserted_variation',
                        'moves_uci': [candidate['move_uci'], candidate['move_uci']]}, 'abstain',
                       'Synthetic repeated selected move after side-to-move changes.')
            _add_claim(claims, 'unsupported_claim', row, candidate,
                       {'kind': 'strategy', 'text': 'forced winning attack'}, 'abstain',
                       'Synthetic unsupported strategic-quality claim.')
    cf.require(len(claims) <= MAX_CLAIMS, 'claim_budget_exceeded')
    cf.require(len({claim['claim_id'] for claim in claims}) == len(claims), 'duplicate_claim')
    return {
        'schema': SCHEMA,
        'maximum_claims': MAX_CLAIMS,
        'source_receipt_sha256': source_sha,
        'typed_packet_sha256': packet_sha,
        'source_projection_sha256': packet['source_projection_sha256'],
        'implementation_sha256': cf.file_digest(Path(__file__)),
        'validator_sha256': cf.file_digest(Path(extended.__file__)),
        'adapter_sha256': cf.file_digest(Path(adapter.__file__)),
        'requested_positions': packet['requested_positions'],
        'successful_positions': packet['successful_positions'],
        'failed_positions': packet['failed_positions'],
        'legal_candidates': packet['legal_candidates'],
        'position_sources': [{key: copy.deepcopy(row[key]) for key in
                              ('position_id', 'game_id', 'source_url', 'split', 'status')}
                             for row in packet['positions']],
        'claims': claims,
        'model_calls': 0,
        'engine_calls': 0,
        'heldout_scored': 0,
        'evaluator_only': True,
        'limitations': list(LIMITATIONS),
    }


def validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest):
    expected = freeze(data, source, source_sha, packet_path, packet_sha)
    cf.require(cf.canonical(manifest) == cf.canonical(expected), 'manifest_changed')


def _accepted(row):
    return row['status'] == 'succeeded' and row['decision'].get('status') in (
        'verified_board_fact', 'verified_legal_variation')


def metrics(manifest, rows):
    claims = manifest['claims']
    paired = list(zip(claims, rows))
    valid = [(claim, row) for claim, row in paired if claim['expected_status'] != 'abstain']
    false = [(claim, row) for claim, row in paired if claim['expected_status'] == 'abstain']
    categories = {}
    for category in sorted({claim['category'] for claim in claims}):
        category_rows = [(claim, row) for claim, row in paired if claim['category'] == category]
        categories[category] = {
            'requested': len(category_rows),
            'accepted': sum(_accepted(row) for _, row in category_rows),
            'abstained': sum(row['status'] == 'succeeded' and row['decision'].get('status') == 'abstain'
                             for _, row in category_rows),
            'failed': sum(row['status'] == 'failed' for _, row in category_rows),
            'not_run': sum(row['status'] == 'not_run' for _, row in category_rows),
        }
    return {
        'requested': len(claims),
        'succeeded': sum(row['status'] == 'succeeded' for row in rows),
        'failed': sum(row['status'] == 'failed' for row in rows),
        'not_run': sum(row['status'] == 'not_run' for row in rows),
        'accepted': sum(_accepted(row) for row in rows),
        'abstained': sum(row['status'] == 'succeeded' and row['decision'].get('status') == 'abstain'
                         for row in rows),
        'valid_coverage': {
            'accepted': sum(_accepted(row) and row['decision'].get('status') == claim['expected_status']
                            for claim, row in valid),
            'requested': len(valid),
        },
        'false_acceptance': {
            'accepted': sum(_accepted(row) for _, row in false),
            'requested': len(false),
        },
        'categories': categories,
        'elapsed_ns_total': sum(row['elapsed_ns'] for row in rows),
    }


def run(data, source, source_sha, packet_path, packet_sha, manifest):
    validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest)
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    rows = []
    for frozen in manifest['claims']:
        start = time.perf_counter_ns()
        try:
            decision = extended.validate_extended_claim(
                data, source, source_sha, packet, frozen['position_id'],
                frozen['evidence_id'], frozen['claim'])
            row = {'claim_id': frozen['claim_id'], 'status': 'succeeded', 'decision': decision}
        except Exception as error:
            row = {'claim_id': frozen['claim_id'], 'status': 'failed',
                   'error': {'type': type(error).__name__, 'message': str(error)[:500]}}
        row['elapsed_ns'] = time.perf_counter_ns() - start
        rows.append(row)
    return {'schema': REPORT_SCHEMA, 'manifest_sha256': cf.digest(cf.canonical(manifest)),
            'results': rows, 'metrics': metrics(manifest, rows),
            'model_calls': 0, 'engine_calls': 0, 'heldout_scored': 0}


def verify(data, source, source_sha, packet_path, packet_sha, manifest, report):
    validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest)
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    cf.exact_keys(report, ('schema', 'manifest_sha256', 'results', 'metrics',
                           'model_calls', 'engine_calls', 'heldout_scored'), 'invalid_report_shape')
    cf.require(report['schema'] == REPORT_SCHEMA, 'invalid_report_schema')
    cf.require(report['manifest_sha256'] == cf.digest(cf.canonical(manifest)), 'report_manifest_changed')
    cf.require(report['model_calls'] == report['engine_calls'] == report['heldout_scored'] == 0,
               'unexpected_execution_calls')
    rows = report['results']
    cf.require(isinstance(rows, list) and len(rows) == len(manifest['claims']),
               'incomplete_claim_denominator')
    replayed = 0
    for frozen, row in zip(manifest['claims'], rows):
        cf.require(row.get('claim_id') == frozen['claim_id'], 'invalid_claim_identity')
        cf.require(type(row.get('elapsed_ns')) is int and row['elapsed_ns'] >= 0, 'invalid_elapsed_ns')
        status = row.get('status')
        cf.require(status in ('succeeded', 'failed', 'not_run'), 'invalid_result_status')
        if status == 'succeeded':
            cf.exact_keys(row, ('claim_id', 'status', 'decision', 'elapsed_ns'), 'invalid_success_shape')
            actual = extended.validate_extended_claim(data, source, source_sha, packet,
                                                       frozen['position_id'], frozen['evidence_id'],
                                                       frozen['claim'])
            cf.require(cf.canonical(row['decision']) == cf.canonical(actual),
                       'retained_decision_not_reproduced')
            replayed += 1
        elif status == 'failed':
            cf.exact_keys(row, ('claim_id', 'status', 'error', 'elapsed_ns'), 'invalid_failure_shape')
            cf.exact_keys(row['error'], ('type', 'message'), 'invalid_failure')
            cf.require(all(isinstance(value, str) for value in row['error'].values()), 'invalid_failure')
        else:
            cf.exact_keys(row, ('claim_id', 'status', 'reason', 'elapsed_ns'), 'invalid_not_run_shape')
            cf.require(isinstance(row['reason'], str) and row['reason'], 'invalid_not_run_reason')
    cf.require(cf.canonical(report['metrics']) == cf.canonical(metrics(manifest, rows)), 'metrics_changed')
    return {
        'schema': 'chess-extended-claim-check/v1',
        'integrity_passed': True,
        'replayed': replayed,
        'complete': replayed == len(rows) and report['metrics']['failed'] == 0
                    and report['metrics']['not_run'] == 0 and manifest['failed_positions'] == 0,
        'metrics': report['metrics'],
        'model_calls': 0,
        'engine_calls': 0,
        'heldout_scored': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'run', 'verify'))
    for name in ('data', 'source', 'packet', 'manifest'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    inputs = (args.data, args.source, args.source_sha256, args.packet, args.packet_sha256)
    if args.command == 'freeze':
        manifest = freeze(*inputs)
        write_json(manifest, args.manifest)
        result = {'manifest_file_sha256': cf.file_digest(args.manifest), 'claims': len(manifest['claims'])}
        complete = True
    else:
        cf.require(args.output is not None, 'missing_output')
        manifest = read_json(args.manifest)
        if args.command == 'run':
            report = run(*inputs, manifest)
            write_json(report, args.output)
            result = {'metrics': report['metrics'], 'receipt_sha256': cf.file_digest(args.output)}
            complete = report['metrics']['failed'] == report['metrics']['not_run'] == manifest['failed_positions'] == 0
        else:
            result = verify(*inputs, manifest, read_json(args.output))
            result['receipt_sha256'] = cf.file_digest(args.output)
            complete = result['complete']
    print(json.dumps(result, sort_keys=True))
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
