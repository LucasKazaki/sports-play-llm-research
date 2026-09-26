"""Acceptance tests for the strict evaluator-only extended-claim checker."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_extended_claim_factuality_acceptance as acceptance
import chess_extended_claim_factuality_experiment as experiment


DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
SOURCE_SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'
PACKET = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
PACKET_SHA = '7743b9fac58695a99cee8f5918e0ca6225909c1750658fc60e34c57f42a9bd0c'
FROZEN = ROOT / 'artifacts/chess-extended-claim-factuality-v1/dev8-20260923'
FROZEN_MANIFEST = FROZEN / 'manifest.json'
FROZEN_REPORT = FROZEN / 'report.json'
FROZEN_MANIFEST_SHA = '3ab006af3c663e146a18875617bbe62327509728d9eb97c0e4f7457d29fb94d9'
FROZEN_REPORT_SHA = '463f2d0f2d80cc8e0f1b3f8b519d53da3cdf7693bc55fc0eceda03060f1da224'
V1_EXPERIMENT_SHA = 'b0e2cc3415c07a54afd8cc0e921f77538f59cfcb60413dc2e0598d86c6f4baed'


@pytest.fixture(scope='module')
def manifest():
    return experiment.freeze(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA)


@pytest.fixture(scope='module')
def report(manifest):
    return experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)


def test_accepts_replayed_real_development_result(manifest, report):
    receipt = acceptance.accept(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, report)
    assert receipt['schema'] == acceptance.SCHEMA and receipt['accepted'] is True
    assert receipt['replayed'] == len(report['results']) == 191
    assert receipt['metrics']['valid_coverage'] == {'accepted': 64, 'requested': 64}
    assert receipt['metrics']['false_acceptance'] == {'accepted': 0, 'requested': 127}
    assert receipt['model_calls'] == receipt['engine_calls'] == receipt['heldout_scored'] == 0
    assert receipt['commentary_capability_gate_passed'] is False
    assert receipt['independent_acceptance'] is False
    assert receipt['input_bindings']['claim_denominator'] == 191


def test_accepts_exact_frozen_development_artifacts():
    assert cf.file_digest(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA
    assert cf.file_digest(FROZEN_REPORT) == FROZEN_REPORT_SHA
    manifest = experiment.read_json(FROZEN_MANIFEST)
    report = experiment.read_json(FROZEN_REPORT)
    receipt = acceptance.accept(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, report)
    assert receipt['accepted'] is True
    assert receipt['manifest_canonical_sha256'] == report['manifest_sha256']
    assert receipt['implementation_sha256']['experiment_sha256'] == V1_EXPERIMENT_SHA


def test_strict_metrics_rejects_missing_valid_coverage(report):
    metrics = copy.deepcopy(report['metrics'])
    metrics['valid_coverage']['accepted'] -= 1
    with pytest.raises(ValueError, match='incomplete_valid_coverage'):
        acceptance.strict_metrics(metrics)


def test_strict_metrics_rejects_a_false_acceptance(report):
    metrics = copy.deepcopy(report['metrics'])
    metrics['false_acceptance']['accepted'] = 1
    with pytest.raises(ValueError, match='false_acceptance_detected'):
        acceptance.strict_metrics(metrics)


def test_strict_metrics_rejects_unclassified_success(report):
    metrics = copy.deepcopy(report['metrics'])
    metrics['abstained'] -= 1
    with pytest.raises(ValueError, match='incomplete_false_control_abstention'):
        acceptance.strict_metrics(metrics)


def test_replay_tampering_is_rejected_before_strict_acceptance(manifest, report):
    changed = copy.deepcopy(report)
    changed['results'].pop()
    with pytest.raises(ValueError, match='incomplete_claim_denominator'):
        acceptance.accept(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, changed)


def test_strict_acceptance_rejects_a_faithfully_replayed_wrong_validator(monkeypatch, manifest):
    monkeypatch.setattr(
        experiment.extended,
        'validate_extended_claim',
        lambda *_args, **_kwargs: {'status': 'verified_board_fact'},
    )
    bad = experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)
    legacy = experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, bad)
    assert legacy['complete'] is True
    assert bad['metrics']['valid_coverage'] == {'accepted': 32, 'requested': 64}
    assert bad['metrics']['false_acceptance'] == {'accepted': 127, 'requested': 127}
    with pytest.raises(ValueError, match='incomplete_valid_coverage'):
        acceptance.accept(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, bad)


def test_acceptance_receipt_is_create_only_and_canonical(tmp_path, manifest, report):
    receipt = acceptance.accept(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, report)
    output = tmp_path / 'new' / 'acceptance.json'
    experiment.write_json(receipt, output)
    assert json.loads(output.read_bytes()) == receipt
    with pytest.raises(FileExistsError):
        experiment.write_json(receipt, output)
