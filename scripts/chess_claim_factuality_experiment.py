"""Frozen structured claim experiment on retained real development boards.

Deliberately false claims are labelled software probes, never human annotations.
The reference-only baseline is a fixed deliberately weak control, not a model.
No engine, model, network, training or heldout scoring is performed.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import chess_typed_position_evidence as adapter
import chess_counterfactual_evidence as cf

MAX_CLAIMS = 512
MAX_BYTES = 2 * 1024 * 1024
MUTATED_FIELDS = ('capture', 'gives_check', 'moving_color', 'from', 'to', 'en_passant', 'castling', 'checkmate')
LIMITATIONS = [
    'Eight convenience-sample development boards; not general chess or sports performance.',
    'False/foreign-reference claims are synthetic software controls on real boards, not human labels.',
    'Engine observations retain typed bounds; matching a retained score does not independently reproduce it.',
    'Unsupported strategic and teaching claims must abstain; usefulness and model quality are not measured.',
    'Reference-only baseline checks identity only and intentionally ignores factual content.',
    'Latency includes complete source validation on each claim; no throughput or GPU benchmark claim.',
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
    cf.require(cf.file_digest(Path(packet_path)) == packet_sha, 'pinned_adapter_receipt_changed')
    packet = read_json(packet_path)
    adapter.validate_typed_position_evidence(data, source, source_sha, packet)
    return packet


def freeze(data, source, source_sha, packet_path, packet_sha):
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    claims = []
    good_rows = [row for row in packet['positions'] if row['status'] == 'succeeded']
    for row in good_rows:
        foreign = next((r['engine_evidence'][0]['evidence_id'] for r in good_rows
                        if r['position_id'] != row['position_id']), 'unknown-evidence-control')
        for candidate in row['engine_evidence']:
            def add(category, claim, expected, derivation, position_id=None, evidence_id=None):
                core = {'category': category, 'origin_position_id': row['position_id'],
                        'origin_evidence_id': candidate['evidence_id'], 'position_id': position_id or row['position_id'],
                        'evidence_id': evidence_id or candidate['evidence_id'],
                        'claim': copy.deepcopy(claim), 'expected': expected, 'derivation': derivation}
                claims.append({'claim_id': cf.digest(cf.canonical(core)), **core})
            facts = candidate['transition']
            for field in sorted(adapter.FACT_FIELDS):
                add('valid_board_fact', {'kind': 'board_fact', 'field': field, 'value': facts[field]},
                    'verified_board_fact', 'Unchanged legally replayed transition field: ' + field)
            for field in MUTATED_FIELDS:
                value = facts[field]
                altered = not value if type(value) is bool else 'deliberately-false:' + str(value)
                add('false_board_fact', {'kind': 'board_fact', 'field': field, 'value': altered},
                    'abstain', 'Synthetic mutation of transition field: ' + field)
            add('false_board_type', {'kind': 'board_fact', 'field': 'capture', 'value': int(facts['capture'])},
                'abstain', 'Synthetic boolean-to-integer confusion control')
            true_claim = {'kind': 'board_fact', 'field': 'capture', 'value': facts['capture']}
            add('foreign_reference', true_claim, 'abstain', 'Synthetic evidence ID from another position', evidence_id=foreign)
            add('unknown_position', true_claim, 'abstain', 'Synthetic unknown position identity', position_id='unknown-position-control')
            add('unsupported_strategy', {'kind': 'concept', 'name': 'winning_attack'}, 'abstain', 'Synthetic unsupported strategic concept')
            add('unsupported_teaching', {'kind': 'board_fact', 'field': 'teaching_quality', 'value': 'excellent'},
                'abstain', 'Synthetic unsupported human usefulness claim')
            add('valid_engine_observation', {'kind': 'engine_observation', 'score': candidate['score']},
                'verified_engine_observation', 'Unchanged retained typed engine observation, not new ground truth')
            score = copy.deepcopy(candidate['score'])
            score['value'] += 1
            add('false_engine_observation', {'kind': 'engine_observation', 'score': score},
                'abstain', 'Synthetic changed retained score value with type/bound otherwise unchanged')
    cf.require(len(claims) <= MAX_CLAIMS, 'claim_budget_exceeded')
    cf.require(len({row['claim_id'] for row in claims}) == len(claims), 'duplicate_claim')
    return {'schema': 'chess-claim-manifest/v1', 'maximum_claims': MAX_CLAIMS,
            'source_receipt_sha256': source_sha, 'typed_packet_sha256': packet_sha,
            'source_projection_sha256': packet['source_projection_sha256'],
            'implementation_sha256': cf.file_digest(Path(__file__)), 'adapter_sha256': packet['adapter_sha256'],
            'requested_positions': packet['requested_positions'], 'failed_positions': packet['failed_positions'],
            'position_sources': [{key: copy.deepcopy(row[key]) for key in ('position_id', 'game_id', 'source_url', 'split', 'status')}
                                 for row in packet['positions']],
            'claims': claims, 'model_calls': 0, 'engine_calls': 0, 'heldout_scored': 0,
            'baseline': 'reference-only/v1', 'limitations': list(LIMITATIONS)}


def validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest):
    expected = freeze(data, source, source_sha, packet_path, packet_sha)
    cf.require(cf.canonical(manifest) == cf.canonical(expected), 'manifest_changed')


def baseline_accepts(packet, claim):
    return any(row['position_id'] == claim['position_id'] and
               any(c['evidence_id'] == claim['evidence_id'] for c in row['engine_evidence'])
               for row in packet['positions'] if row['status'] == 'succeeded')


def metrics(manifest, rows):
    claims = manifest['claims']
    accepted = lambda r: r['status'] == 'succeeded' and r['decision'].get('status') in ('verified_board_fact', 'verified_engine_observation')
    valid = [(c, r) for c, r in zip(claims, rows) if c['expected'] != 'abstain']
    false = [(c, r) for c, r in zip(claims, rows) if c['expected'] == 'abstain']
    return {'requested': len(claims), 'succeeded': sum(r['status'] == 'succeeded' for r in rows),
            'failed': sum(r['status'] == 'failed' for r in rows), 'not_run': sum(r['status'] == 'not_run' for r in rows),
            'valid_coverage': {'accepted': sum(accepted(r) and r['decision']['status'] == c['expected'] for c, r in valid), 'requested': len(valid)},
            'false_acceptance': {'accepted': sum(accepted(r) for _, r in false), 'requested': len(false)},
            'reference_only_baseline_false_acceptance': {'accepted': sum(r['baseline_accepted'] for _, r in false), 'requested': len(false)},
            'categories': {category: {'requested': sum(c['category'] == category for c in claims),
                                    'accepted': sum(accepted(r) for c, r in zip(claims, rows) if c['category'] == category),
                                    'failed': sum(r['status'] != 'succeeded' for c, r in zip(claims, rows) if c['category'] == category)}
                           for category in sorted({c['category'] for c in claims})},
            'elapsed_ns_total': sum(r['elapsed_ns'] for r in rows)}


def run(data, source, source_sha, packet_path, packet_sha, manifest):
    validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest)
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    rows = []
    for claim in manifest['claims']:
        start = time.perf_counter_ns()
        result = {'claim_id': claim['claim_id'], 'baseline_accepted': baseline_accepts(packet, claim)}
        try:
            result.update(status='succeeded', decision=adapter.validate_claim(data, source, source_sha, packet,
                          claim['position_id'], claim['evidence_id'], claim['claim']))
        except Exception as error:
            result.update(status='failed', error={'type': type(error).__name__, 'message': str(error)[:500]})
        result['elapsed_ns'] = time.perf_counter_ns() - start
        rows.append(result)
    return {'schema': 'chess-claim-experiment/v1', 'manifest_sha256': cf.digest(cf.canonical(manifest)),
            'results': rows, 'metrics': metrics(manifest, rows)}


def verify(data, source, source_sha, packet_path, packet_sha, manifest, report):
    validate_manifest(data, source, source_sha, packet_path, packet_sha, manifest)
    packet = load_packet(data, source, source_sha, packet_path, packet_sha)
    cf.exact_keys(report, ('schema', 'manifest_sha256', 'results', 'metrics'), 'invalid_report_shape')
    cf.require(report['schema'] == 'chess-claim-experiment/v1' and report['manifest_sha256'] == cf.digest(cf.canonical(manifest)), 'report_manifest_changed')
    rows = report['results']
    cf.require(isinstance(rows, list) and len(rows) == len(manifest['claims']), 'incomplete_claim_denominator')
    for claim, row in zip(manifest['claims'], rows):
        cf.require(row.get('status') in ('succeeded', 'failed', 'not_run'), 'invalid_result_status')
        extra = ('decision',) if row['status'] == 'succeeded' else ('error',)
        cf.exact_keys(row, ('claim_id', 'baseline_accepted', 'status', 'elapsed_ns') + extra, 'invalid_result_shape')
        cf.require(row['claim_id'] == claim['claim_id'] and type(row['elapsed_ns']) is int and row['elapsed_ns'] >= 0, 'invalid_claim_or_latency')
        cf.require(type(row['baseline_accepted']) is bool and row['baseline_accepted'] == baseline_accepts(packet, claim), 'invalid_baseline')
        if row['status'] != 'succeeded':
            cf.exact_keys(row['error'], ('type', 'message'), 'missing_failure')
            cf.require(all(isinstance(v, str) for v in row['error'].values()), 'invalid_failure')
    cf.require(cf.canonical(report['metrics']) == cf.canonical(metrics(manifest, rows)), 'metrics_changed')
    replayed = 0
    for claim, row in zip(manifest['claims'], rows):
        if row['status'] != 'succeeded':
            continue
        actual = adapter.validate_claim(data, source, source_sha, packet, claim['position_id'], claim['evidence_id'], claim['claim'])
        cf.require(cf.canonical(row['decision']) == cf.canonical(actual), 'retained_decision_not_reproduced')
        replayed += 1
    return {'schema': 'chess-claim-check/v1', 'integrity_passed': True, 'replayed': replayed,
            'complete': replayed == len(rows) and manifest['failed_positions'] == 0,
            'metrics': report['metrics'], 'model_calls': 0, 'engine_calls': 0, 'heldout_scored': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'run', 'verify'))
    for name in ('data', 'source', 'packet', 'manifest'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    complete = True
    inputs = (args.data, args.source, args.source_sha256, args.packet, args.packet_sha256)
    if args.command == 'freeze':
        manifest = freeze(*inputs)
        write_json(manifest, args.manifest)
        result = {'manifest_file_sha256': cf.file_digest(args.manifest), 'claims': len(manifest['claims'])}
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
