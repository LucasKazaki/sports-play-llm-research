"""Real development inputs; false claim rows are deterministic software controls."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_extended_claim_factuality_experiment as experiment

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


def test_manifest_is_real_development_only_and_has_every_required_control(manifest):
    assert manifest['schema'] == experiment.SCHEMA
    assert manifest['requested_positions'] == manifest['successful_positions'] == 8
    assert manifest['failed_positions'] == 0 and manifest['legal_candidates'] == 16
    assert manifest['model_calls'] == manifest['engine_calls'] == manifest['heldout_scored'] == 0
    assert manifest['evaluator_only'] is True
    assert len({claim['claim_id'] for claim in manifest['claims']}) == len(manifest['claims'])
    assert all(row['split'] == 'dev' and row['source_url'].startswith('https://lichess.org/')
               for row in manifest['position_sources'])
    categories = {claim['category'] for claim in manifest['claims']}
    assert {'valid_before_occupation', 'valid_after_occupation', 'valid_retained_pv',
            'valid_asserted_selected_move', 'wrong_piece', 'wrong_stage', 'foreign_evidence',
            'unknown_position', 'truncated_retained_pv', 'misattributed_pv',
            'illegal_later_ply', 'unsupported_claim'} <= categories


def test_real_run_retains_complete_denominators_and_expected_decisions(manifest, report):
    metrics = report['metrics']
    assert metrics['requested'] == metrics['succeeded'] == len(manifest['claims'])
    assert metrics['failed'] == metrics['not_run'] == 0
    assert metrics['valid_coverage']['accepted'] == metrics['valid_coverage']['requested'] > 0
    assert metrics['false_acceptance']['accepted'] == 0
    assert metrics['abstained'] == metrics['false_acceptance']['requested'] > 0
    for frozen, row in zip(manifest['claims'], report['results']):
        assert row['status'] == 'succeeded'
        if frozen['expected_status'] == 'abstain':
            assert row['decision']['status'] == 'abstain'
        else:
            assert row['decision']['status'] == frozen['expected_status']


def test_verify_replays_every_successful_public_extended_validator_decision(manifest, report):
    checked = experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, report)
    assert checked['integrity_passed'] and checked['complete']
    assert checked['replayed'] == len(manifest['claims'])


@pytest.mark.parametrize('mutation', ['drop', 'reorder', 'source', 'packet', 'code', 'reference', 'extra'])
def test_manifest_tampering_is_rejected(manifest, mutation):
    changed = copy.deepcopy(manifest)
    if mutation == 'drop': changed['claims'].pop()
    elif mutation == 'reorder': changed['claims'].reverse()
    elif mutation == 'source': changed['source_receipt_sha256'] = '0' * 64
    elif mutation == 'packet': changed['typed_packet_sha256'] = '0' * 64
    elif mutation == 'code': changed['validator_sha256'] = '0' * 64
    elif mutation == 'reference': changed['claims'][0]['evidence_id'] = 'unknown'
    else: changed['approval'] = True
    with pytest.raises(ValueError, match='manifest_changed'):
        experiment.validate_manifest(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, changed)


@pytest.mark.parametrize('mutation', ['drop', 'metrics', 'claim', 'latency', 'extra', 'manifest'])
def test_report_tampering_is_rejected_before_acceptance(manifest, report, mutation):
    changed = copy.deepcopy(report)
    if mutation == 'drop': changed['results'].pop()
    elif mutation == 'metrics': changed['metrics']['false_acceptance']['accepted'] = 1
    elif mutation == 'claim': changed['results'][0]['claim_id'] = 'unknown'
    elif mutation == 'latency': changed['results'][0]['elapsed_ns'] = True
    elif mutation == 'extra': changed['approved'] = True
    else: changed['manifest_sha256'] = 'f' * 64
    with pytest.raises(ValueError):
        experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, changed)


def test_validator_failure_stays_in_the_original_denominator(manifest, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError('injected extended-validator failure')
    monkeypatch.setattr(experiment.extended, 'validate_extended_claim', fail)
    failed = experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)
    assert failed['metrics']['requested'] == failed['metrics']['failed'] == len(manifest['claims'])
    assert failed['metrics']['succeeded'] == failed['metrics']['not_run'] == 0
    assert all(row['error']['type'] == 'RuntimeError' for row in failed['results'])
    checked = experiment.verify(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest, failed)
    assert not checked['complete'] and checked['replayed'] == 0


def test_run_uses_the_public_seven_argument_extended_validator(manifest, monkeypatch):
    original = experiment.extended.validate_extended_claim
    calls = []
    def observed(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(experiment.extended, 'validate_extended_claim', observed)
    report = experiment.run(DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA, manifest)
    assert len(calls) == len(manifest['claims'])
    assert all(len(args) == 7 and args[0] == DATA and args[1] == SOURCE and args[2] == SOURCE_SHA
               for args in calls)
    assert report['metrics']['failed'] == 0


def test_receipts_are_create_only_and_bounded(tmp_path, manifest):
    target = tmp_path / 'new' / 'manifest.json'
    experiment.write_json(manifest, target)
    assert json.loads(target.read_bytes()) == manifest
    with pytest.raises(FileExistsError):
        experiment.write_json(manifest, target)
    with pytest.raises(ValueError, match='byte_budget'):
        experiment.write_json({'too_big': 'x' * experiment.MAX_BYTES}, tmp_path / 'too-big.json')


def test_source_receipt_binding_is_checked_before_claim_generation(tmp_path):
    changed_source = tmp_path / 'source.json'
    changed_source.write_bytes(SOURCE.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='pinned_source_receipt_changed'):
        experiment.freeze(DATA, changed_source, SOURCE_SHA, PACKET, PACKET_SHA)
