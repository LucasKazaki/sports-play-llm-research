"""Authored final-plan metadata, exact direct ownership and unchanged science tests."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_direct_training_v1 as subject
from test_direct_launch_contract import receipt


def setup(monkeypatch):
    original = {'training': {'steps': 192, 'accumulation': 8}, 'data': {'TRAIN': 1536, 'DEV': 96},
        'selection_method': ['unchanged'], 'generation': {'max_new_tokens': 1024, 'timeout_seconds': 180},
        'phase_maximum_seconds': {'training': 3000, 'heldout': 4500},
        'cutoff_utc': '2026-10-16T22:00:00+00:00', 'dependencies': [],
        'authorized_entrypoints': {'heldout': 'old_eval_v5'}, 'frozen_at': 'stale'}
    gates = {'update': {'worker': {'id': 'warm'}}, 'cold': {'protocol': {'id': 'coldplan'}, 'worker': {'id': 'cold'}}}
    qualified = {'owned_worker_source': {'sha256': 'new-source'}, 'interpreters': {'delegate': 'base.exe'},
        'launch_profile': subject.source.launch.PROFILE, 'cpu_environment_parity': {'actual': 'passed'}, 'dependencies': []}
    workers = {'warm': receipt(), 'cold': receipt()}
    monkeypatch.setattr(subject.preserved, 'final_training', lambda value: copy.deepcopy(original))
    monkeypatch.setattr(subject.source.cold, 'bound', lambda value: value['id'])
    monkeypatch.setattr(subject.source.cold, 'read', lambda key: qualified if key == 'coldplan' else workers[key])
    monkeypatch.setattr(subject.source.launch, 'environment', lambda *args: None)
    monkeypatch.setattr(subject.source, 'dependencies', lambda value: [])
    monkeypatch.setattr(subject.source, 'bind', lambda value: {'path': str(value), 'sha256': 'authored'})
    monkeypatch.setattr(subject.trainer, 'verify_protocol', lambda value: None)
    return original, gates, workers


def test_current_truthful_dispatch_and_freeze_metadata_with_identical_science(tmp_path, monkeypatch):
    original, gates, workers = setup(monkeypatch)
    out = tmp_path/'final.json'; subject.prepare(gates, out, tmp_path/'train')
    result = json.loads(out.read_text())
    for key in ['training', 'data', 'selection_method', 'generation', 'phase_maximum_seconds', 'cutoff_utc']:
        assert result[key] == original[key]
    assert result['worker_maximum_seconds'] == 3030 and result['external_maximum_seconds'] == 3060
    assert result['expected_worker_arguments'][1] == 'train'
    assert result['expected_worker_arguments'][3] == str(out.resolve())
    assert 'cold_eval_v7.py' in result['authorized_entrypoints']['heldout']
    assert 'embedded trainer.heldout remains unauthorized' in result['authorized_entrypoints']['heldout']
    assert datetime.fromisoformat(result['frozen_at']).date() == datetime.now(timezone.utc).date()
    assert original['frozen_at'] == 'stale' and original['authorized_entrypoints']['heldout'] == 'old_eval_v5'


@pytest.mark.parametrize('stage', ['warm', 'cold'])
def test_each_actual_qualifier_requires_direct_owned_worker_before_freeze(tmp_path, monkeypatch, stage):
    original, gates, workers = setup(monkeypatch)
    workers[stage]['ownership']['before_go']['member_of_explicit_creator_job'] = False
    with pytest.raises(ValueError): subject.prepare(gates, tmp_path/'out.json', tmp_path/'train')
    assert not (tmp_path/'out.json').exists()


def test_failed_cpu_environment_evidence_never_freezes(tmp_path, monkeypatch):
    original, gates, workers = setup(monkeypatch)
    def fail(*args): raise ValueError('Actual closed parity required')
    monkeypatch.setattr(subject.source.launch, 'environment', fail)
    with pytest.raises(ValueError): subject.prepare(gates, tmp_path/'out.json', tmp_path/'train')
    assert not (tmp_path/'out.json').exists()
