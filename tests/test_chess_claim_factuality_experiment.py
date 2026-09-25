"""Real development inputs; mutations and injected failures are software controls."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_claim_factuality_experiment as experiment

DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
SOURCE_SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'
PACKET = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
PACKET_SHA = '7743b9fac58695a99cee8f5918e0ca6225909c1750658fc60e34c57f42a9bd0c'


@pytest.fixture(scope='module')
def manifest():
    return experiment.freeze(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA)


@pytest.fixture(scope='module')
def report(manifest):
    return experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)


def test_frozen_claim_denominator_is_complete_unique_and_bound_to_real_development(manifest):
    assert manifest['requested_positions'] == 8 and manifest['failed_positions'] == 0
    assert len(manifest['claims']) == 496 and len({c['claim_id'] for c in manifest['claims']}) == 496
    assert manifest['model_calls'] == manifest['engine_calls'] == manifest['heldout_scored'] == 0
    assert len(manifest['position_sources']) == 8
    assert all(p['split'] == 'dev' and p['source_url'].startswith('https://lichess.org/') for p in manifest['position_sources'])
    assert sum(c['expected'] == 'verified_board_fact' for c in manifest['claims']) == 256
    assert sum(c['expected'] == 'verified_engine_observation' for c in manifest['claims']) == 16
    assert sum(c['expected'] == 'abstain' for c in manifest['claims']) == 224
    assert all(c['derivation'] for c in manifest['claims'])


def test_real_run_has_full_denominators_and_measures_reference_only_control(report):
    metrics = report['metrics']
    assert metrics['requested'] == metrics['succeeded'] == 496
    assert metrics['failed'] == metrics['not_run'] == 0
    assert metrics['valid_coverage'] == {'accepted': 272, 'requested': 272}
    assert metrics['false_acceptance'] == {'accepted': 0, 'requested': 224}
    assert metrics['reference_only_baseline_false_acceptance'] == {'accepted': 192, 'requested': 224}
    assert all(type(row['elapsed_ns']) is int and row['elapsed_ns'] >= 0 for row in report['results'])


@pytest.mark.parametrize('mutation', ['drop', 'reorder', 'expected', 'reference', 'source', 'code', 'budget', 'extra'])
def test_frozen_manifest_cannot_be_tampered_with(manifest, mutation):
    changed = copy.deepcopy(manifest)
    if mutation == 'drop': changed['claims'].pop()
    elif mutation == 'reorder': changed['claims'].reverse()
    elif mutation == 'expected': changed['claims'][0]['expected'] = 'abstain'
    elif mutation == 'reference': changed['claims'][0]['evidence_id'] = 'invented'
    elif mutation == 'source': changed['source_receipt_sha256'] = '0' * 64
    elif mutation == 'code': changed['implementation_sha256'] = '0' * 64
    elif mutation == 'budget': changed['maximum_claims'] = 999
    else: changed['approval'] = True
    with pytest.raises(ValueError, match='manifest_changed'):
        experiment.validate_manifest(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, changed)


def test_replay_checks_actual_decisions_and_artifact_integrity(manifest, report):
    checked = experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, report)
    assert checked['integrity_passed'] and checked['complete'] and checked['replayed'] == 496


@pytest.mark.parametrize('mutation', ['drop', 'metrics', 'wrong_claim', 'nan_latency', 'boolean_latency', 'manifest', 'extra'])
def test_result_tampering_is_rejected_before_replay(manifest, report, mutation):
    changed = copy.deepcopy(report)
    if mutation == 'drop': changed['results'].pop()
    elif mutation == 'metrics': changed['metrics']['false_acceptance']['accepted'] = 1
    elif mutation == 'wrong_claim': changed['results'][0]['claim_id'] = 'unknown'
    elif mutation == 'nan_latency': changed['results'][0]['elapsed_ns'] = float('nan')
    elif mutation == 'boolean_latency': changed['results'][0]['elapsed_ns'] = True
    elif mutation == 'manifest': changed['manifest_sha256'] = 'f' * 64
    else: changed['approved'] = True
    with pytest.raises(ValueError):
        experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, changed)


def test_failures_stay_in_original_denominator_and_never_become_correct(manifest, monkeypatch):
    def fail(*_args):
        raise RuntimeError('synthetic injected validator failure')
    monkeypatch.setattr(experiment.adapter, 'validate_claim', fail)
    failed = experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)
    assert failed['metrics']['requested'] == failed['metrics']['failed'] == 496
    assert failed['metrics']['valid_coverage'] == {'accepted': 0, 'requested': 272}
    assert all(row['error']['type'] == 'RuntimeError' for row in failed['results'])
    checked = experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, failed)
    assert not checked['complete'] and checked['replayed'] == 0


def test_receipts_are_create_only_and_have_a_size_limit(tmp_path, manifest):
    output = tmp_path / 'frozen.json'
    experiment.write_json(manifest, output)
    assert json.loads(output.read_bytes()) == manifest
    with pytest.raises(FileExistsError): experiment.write_json(manifest, output)
    with pytest.raises(ValueError, match='byte_budget'):
        experiment.write_json({'too_big': 'x' * experiment.MAX_BYTES}, tmp_path / 'oversized.json')
