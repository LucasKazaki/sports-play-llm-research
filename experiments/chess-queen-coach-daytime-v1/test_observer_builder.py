"""Prospective builder admission/immutability tests, authored metadata only."""
import copy
from pathlib import Path
import sys
import pytest
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_observer_protocols as subject


def test_unclosed_cpu_probe_cannot_create_a_model_qualification_plan(tmp_path, monkeypatch):
    _, old = subject.old_cold()
    probe_protocol = tmp_path/'cpu-plan.json'
    subject.cold.save(probe_protocol, {'dependencies': [], 'authored': True})
    failed = tmp_path/'failed.json'; subject.cold.save(failed, {'status': 'failed'})
    def gate(plan):
        assert plan['model_runtime'] == old['model_runtime']
        assert plan['conditions'] == old['conditions'] and plan['input_rows'] == old['input_rows']
        assert plan['child_maximum_seconds'] == 210 and plan['phase_maximum_seconds'] == 450
        assert plan['cutoff_utc'] == old['cutoff_utc'] and plan['raw_provenance'] == old['raw_provenance']
        assert plan['expected_worker_arguments'][0] == 'experiments/chess-queen-coach-daytime-v1/cold_eval_v6.py'
        raise ValueError('Actual closed probe/audit required')
    monkeypatch.setattr(subject.cold, 'verify_observer_probe', gate)
    out = tmp_path/'model-plan.json'
    with pytest.raises(ValueError, match='closed probe'):
        subject.prepare_cold(out, tmp_path/'model-attempt', probe_protocol, failed, failed, failed)
    assert not out.exists()


def test_protocol_creation_is_create_only(tmp_path):
    path = tmp_path/'protocol.json'; subject.create(path, {'version': 1})
    with pytest.raises(ValueError): subject.create(path, {'version': 2})
    assert subject.cold.read(path) == {'version': 1}


def test_no_model_backend_imported_by_builders():
    assert not {'torch', 'transformers', 'bitsandbytes', 'peft'} & set(sys.modules)
