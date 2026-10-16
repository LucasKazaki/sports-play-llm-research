"""Prospective metadata builders never manufacture actual proof or change science."""
from pathlib import Path
import sys
import pytest
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_direct_protocols_v3 as subject


def test_cpu_probe_plan_cannot_freeze_without_actual_passed_environment(tmp_path, monkeypatch):
    def fail(*args): raise ValueError('Actual parity required')
    monkeypatch.setattr(subject.launch, 'environment', fail)
    with pytest.raises(ValueError, match='parity'):
        subject.prepare_probe(tmp_path/'probe.json', tmp_path/'out', {'authored_missing': True})
    assert not (tmp_path/'probe.json').exists()


def test_cold_plan_preserves_exact_inputs_runtime_rawsettings_and_limits(tmp_path, monkeypatch):
    _, old = subject.preserved.old_cold()
    frozen = {'process_lineage_helper': {'path': 'authored', 'sha256': 'authored'},
        'job_context_policy': old.get('job_context_policy', subject.preserved.POLICY),
        'launch_profile': subject.launch.PROFILE, 'owned_worker_source': {'path': 'authored', 'sha256': 'authored'},
        'cpu_environment_parity': {'authored': True}}
    source = tmp_path/'probe.json'; subject.cold.save(source, frozen)
    dummy = tmp_path/'incomplete.json'; subject.cold.save(dummy, {'status': 'failed'})
    monkeypatch.setattr(subject.launch, 'environment', lambda *args: None)
    def reject(plan):
        for name in ['model_runtime', 'conditions', 'input_rows', 'raw_provenance', 'child_script',
            'child_maximum_seconds', 'phase_maximum_seconds', 'cutoff_utc', 'admission_latest_utc', 'resources']:
            assert plan[name] == old[name]
        raise ValueError('Actual closed4case observer required')
    monkeypatch.setattr(subject.cold, 'verify_observer_probe', reject)
    with pytest.raises(ValueError, match='closed4case'):
        subject.prepare_cold(tmp_path/'cold.json', tmp_path/'out', source, dummy, dummy, dummy)
    assert not (tmp_path/'cold.json').exists()


@pytest.mark.parametrize('phase', [90, 450, 600, 3000, 4500])
def test_wrapper_grace_preserves_computation_phase_and_absolute_cutoff(phase):
    plan = {'phase_maximum_seconds': phase, 'cutoff_utc': '2026-10-16T22:00:00+00:00'}
    subject.worker_grace(plan)
    assert plan['phase_maximum_seconds'] == phase
    assert plan['worker_maximum_seconds'] == phase+30
    assert plan['external_maximum_seconds'] == phase+60
    assert plan['worker_cleanup_maximum_seconds'] == 30
    assert plan['cutoff_utc'] == '2026-10-16T22:00:00+00:00'


def test_unknown_computation_budget_not_admitted():
    with pytest.raises(ValueError): subject.worker_grace({'phase_maximum_seconds': 451})


def test_actual_warm_plan_shape_uses_600_not_future_scientific_dictionary():
    plan = {'maximum_seconds': 600, 'phase_maximum_seconds': {'training': 3000, 'heldout': 4500}}
    subject.worker_grace(plan)
    assert plan['worker_maximum_seconds'] == 630
    assert plan['phase_maximum_seconds'] == {'training': 3000, 'heldout': 4500}


def test_actual_scientific_train_dictionary_admits_3030_wrapper_only():
    plan = {'phase_maximum_seconds': {'training': 3000, 'heldout': 4500}}
    subject.worker_grace(plan)
    assert plan['worker_maximum_seconds'] == 3030
    assert plan['external_maximum_seconds'] == 3060
    assert plan['phase_maximum_seconds'] == {'training': 3000, 'heldout': 4500}


def test_changed_scientific_dictionary_cannot_infer_wrapper_budget():
    with pytest.raises(ValueError):
        subject.worker_grace({'phase_maximum_seconds': {'training': 3001, 'heldout': 4500}})
