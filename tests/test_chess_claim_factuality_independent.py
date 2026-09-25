"""Independent software-control tests; stage only, native owner installs/runs.

These mutations are fabricated adversarial reports, not new real chess outcomes.
"""
import copy
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
INPUTS = (DATA, SOURCE, SOURCE_SHA, PACKET, PACKET_SHA)


@pytest.fixture(scope='module')
def frozen():
    manifest = experiment.freeze(*INPUTS)
    return manifest, experiment.run(*INPUTS, manifest)


@pytest.mark.parametrize('expected', ['verified_board_fact', 'abstain'])
def test_self_consistent_forged_decision_is_rejected_by_actual_replay(frozen, expected):
    manifest, report = frozen
    changed = copy.deepcopy(report)
    index = next(i for i, claim in enumerate(manifest['claims']) if claim['expected'] == expected)
    claim = manifest['claims'][index]
    changed['results'][index]['decision'] = (
        {'status': 'abstain', 'reason': 'synthetic forged abstention'}
        if expected != 'abstain' else
        {'status': 'verified_board_fact', 'evidence_id': claim['evidence_id'], 'field': claim['claim']['field']}
    )
    # Make accounting self-consistent so only decision reproduction catches it.
    changed['metrics'] = experiment.metrics(manifest, changed['results'])
    with pytest.raises(ValueError, match='retained_decision_not_reproduced'):
        experiment.verify(*INPUTS, manifest, changed)


def test_not_run_rows_preserve_denominators_and_cannot_be_complete(frozen):
    manifest, report = frozen
    changed = copy.deepcopy(report)
    for row in changed['results']:
        row.pop('decision')
        row.update(status='not_run', elapsed_ns=0,
                   error={'type': 'SyntheticInterruptedControl', 'message': 'not executed'})
    changed['metrics'] = experiment.metrics(manifest, changed['results'])
    checked = experiment.verify(*INPUTS, manifest, changed)
    assert checked['integrity_passed'] and not checked['complete'] and checked['replayed'] == 0
    assert checked['metrics']['requested'] == checked['metrics']['not_run'] == 496
    assert checked['metrics']['valid_coverage'] == {'accepted': 0, 'requested': 272}
    assert checked['metrics']['false_acceptance'] == {'accepted': 0, 'requested': 224}


def test_wrong_pinned_packet_hash_is_rejected_before_claim_generation():
    with pytest.raises(ValueError, match='pinned_adapter_receipt_changed'):
        experiment.freeze(DATA, SOURCE, SOURCE_SHA, PACKET, '0' * 64)


@pytest.mark.parametrize('command', ['run', 'verify'])
def test_cli_incomplete_execution_cannot_look_like_success(command, tmp_path, monkeypatch):
    """Injected incomplete API outputs exercise the public process status boundary."""
    manifest_path = tmp_path / 'manifest.json'
    output_path = tmp_path / 'report.json'
    experiment.write_json({'failed_positions': 0}, manifest_path)
    if command == 'verify':
        experiment.write_json({'synthetic_incomplete_report': True}, output_path)
        monkeypatch.setattr(experiment, 'verify', lambda *_args: {'complete': False})
    else:
        monkeypatch.setattr(experiment, 'run', lambda *_args: {
            'metrics': {'failed': 1, 'not_run': 0}, 'results': []})
    monkeypatch.setattr(sys, 'argv', ['experiment', command, '--data', str(DATA),
                        '--source', str(SOURCE), '--source-sha256', SOURCE_SHA,
                        '--packet', str(PACKET), '--packet-sha256', PACKET_SHA,
                        '--manifest', str(manifest_path), '--output', str(output_path)])
    assert experiment.main() == 1
    assert output_path.exists()  # Failure evidence is retained, not erased.
