"""Strict, evaluator-only acceptance for a frozen extended-claim experiment.

This is deliberately separate from the experiment runner.  It preserves the
versioned v1 experiment source and receipt while requiring the result metrics to
demonstrate both complete valid-claim coverage and zero false acceptance.  It
does not create a generator input, invoke a model or engine, or evaluate heldout
positions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import chess_counterfactual_evidence as cf
import chess_extended_claim_factuality_experiment as experiment


SCHEMA = 'chess-extended-claim-strict-acceptance/v1'
LIMITATIONS = [
    'This is a deterministic acceptance check for an evaluator-only development experiment, not commentary generation.',
    'It does not establish a no-forward generator, explanation quality, professional commentary, or board-game competence.',
    'The retained engine variation material remains evaluator-only and must never enter a generator packet.',
]


def implementation_hashes():
    """Bind this receipt to the exact evaluator-only implementation chain."""
    return {
        'acceptance_checker_sha256': cf.file_digest(Path(__file__)),
        'experiment_sha256': cf.file_digest(Path(experiment.__file__)),
        'validator_sha256': cf.file_digest(Path(experiment.extended.__file__)),
        'adapter_sha256': cf.file_digest(Path(experiment.adapter.__file__)),
    }


def _nonnegative_int(value, message):
    cf.require(type(value) is int and value >= 0, message)


def strict_metrics(metrics):
    """Require the outcome properties that a raw runner exit code does not prove."""
    cf.exact_keys(metrics, (
        'requested', 'succeeded', 'failed', 'not_run', 'accepted', 'abstained',
        'valid_coverage', 'false_acceptance', 'categories', 'elapsed_ns_total',
    ), 'invalid_metrics_shape')
    for name in ('requested', 'succeeded', 'failed', 'not_run', 'accepted', 'abstained',
                 'elapsed_ns_total'):
        _nonnegative_int(metrics[name], 'invalid_metric_' + name)
    cf.exact_keys(metrics['valid_coverage'], ('accepted', 'requested'),
                  'invalid_valid_coverage')
    cf.exact_keys(metrics['false_acceptance'], ('accepted', 'requested'),
                  'invalid_false_acceptance')
    for group, name in ((metrics['valid_coverage'], 'valid_coverage'),
                        (metrics['false_acceptance'], 'false_acceptance')):
        for field in ('accepted', 'requested'):
            _nonnegative_int(group[field], 'invalid_' + name + '_' + field)
        cf.require(group['accepted'] <= group['requested'],
                   'invalid_' + name + '_denominator')

    valid = metrics['valid_coverage']
    false = metrics['false_acceptance']
    cf.require(metrics['requested'] > 0, 'empty_claim_denominator')
    cf.require(valid['requested'] > 0, 'empty_valid_denominator')
    cf.require(false['requested'] > 0, 'empty_false_control_denominator')
    cf.require(valid['requested'] + false['requested'] == metrics['requested'],
               'claim_denominators_do_not_partition')
    cf.require(metrics['requested'] == metrics['succeeded'], 'incomplete_execution')
    cf.require(metrics['failed'] == metrics['not_run'] == 0, 'execution_has_failures')
    cf.require(valid['accepted'] == valid['requested'], 'incomplete_valid_coverage')
    cf.require(false['accepted'] == 0, 'false_acceptance_detected')
    cf.require(metrics['accepted'] == valid['accepted'], 'unexpected_accepted_claim')
    cf.require(metrics['abstained'] == false['requested'], 'incomplete_false_control_abstention')
    cf.require(metrics['succeeded'] == metrics['accepted'] + metrics['abstained'],
               'unclassified_successful_claim')
    return {
        'requested': metrics['requested'],
        'valid_coverage': dict(valid),
        'false_acceptance': dict(false),
        'accepted': metrics['accepted'],
        'abstained': metrics['abstained'],
    }


def accept(data, source, source_sha, packet_path, packet_sha, manifest, report):
    """Replay v1, then apply the stricter acceptance predicates."""
    checked = experiment.verify(data, source, source_sha, packet_path, packet_sha,
                                manifest, report)
    cf.require(checked['integrity_passed'] is True, 'replay_integrity_failed')
    cf.require(checked['replayed'] == len(report['results']), 'incomplete_replay')
    cf.require(manifest['evaluator_only'] is True, 'not_evaluator_only')
    cf.require(manifest['model_calls'] == manifest['engine_calls'] == manifest['heldout_scored'] == 0,
               'unexpected_manifest_calls')
    cf.require(report['model_calls'] == report['engine_calls'] == report['heldout_scored'] == 0,
               'unexpected_report_calls')
    summary = strict_metrics(report['metrics'])
    return {
        'schema': SCHEMA,
        'accepted': True,
        'acceptance_scope': 'deterministic_evaluator_only_development_check',
        'commentary_capability_gate_passed': False,
        'independent_acceptance': False,
        'manifest_canonical_sha256': cf.digest(cf.canonical(manifest)),
        'report_manifest_sha256': report['manifest_sha256'],
        'input_bindings': {
            'source_sha256': source_sha,
            'packet_sha256': packet_sha,
            'claim_denominator': len(report['results']),
        },
        'implementation_sha256': implementation_hashes(),
        'replayed': checked['replayed'],
        'metrics': summary,
        'model_calls': 0,
        'engine_calls': 0,
        'heldout_scored': 0,
        'limitations': list(LIMITATIONS),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = experiment.read_json(args.manifest)
    report = experiment.read_json(args.report)
    receipt = accept(args.data, args.source, args.source_sha256, args.packet,
                     args.packet_sha256, manifest, report)
    receipt['manifest_file_sha256'] = cf.file_digest(args.manifest)
    receipt['report_file_sha256'] = cf.file_digest(args.report)
    experiment.write_json(receipt, args.output)
    print(cf.canonical({
        'accepted': receipt['accepted'],
        'receipt_sha256': cf.file_digest(args.output),
        'replayed': receipt['replayed'],
        'valid_coverage': receipt['metrics']['valid_coverage'],
        'false_acceptance': receipt['metrics']['false_acceptance'],
    }).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
