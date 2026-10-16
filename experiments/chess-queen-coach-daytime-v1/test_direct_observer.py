"""Operational-only AST changes and full pending rows before failed parity gates."""
import ast
from pathlib import Path
import sys
import pytest
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cold_eval_v7 as subject
import probe_process_observer_v2 as probe
import test_cold_eval_v6 as authored


def functions(path):
    return {node.name: ast.dump(node) for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef)}


def test_generation_raw_denominators_dispatch_and_scoring_functions_unchanged_AST():
    previous, current = functions(HERE/'cold_eval_v6.py'), functions(HERE/'cold_eval_v7.py')
    assert set(previous) == set(current)
    assert {name for name in current if previous[name] != current[name]} == {'verify', 'verify_observer_probe'}
    before, after = functions(HERE/'probe_process_observer.py'), functions(HERE/'probe_process_observer_v2.py')
    assert {name for name in after if before[name] != after[name]} == {'verify'}


def test_failed_environment_stops_before_outer_context_or_model_with2notrun(tmp_path, monkeypatch):
    plan, protocol, _ = authored.setup(tmp_path, monkeypatch)
    plan.update(implementation_sha256=subject.digest(Path(subject.__file__)),
        job_context_source={'path': str(HERE/'job_context_direct_v1.py'), 'sha256': subject.digest(HERE/'job_context_direct_v1.py')})
    subject.save(protocol, plan)
    def failed(*args): raise ValueError('authored parity/owned-worker failure')
    def forbidden(*args): raise AssertionError('No OS or model setup before parity')
    monkeypatch.setattr(subject.launch_contract, 'environment', failed)
    with pytest.raises(ValueError, match='parity'):
        subject.run(plan, protocol, tmp_path/'attempt', runner=forbidden, context_factory=forbidden)
    actual = subject.read(tmp_path/'attempt/software.json')
    assert len(actual['rows']) == 2 and all(row['status'] == 'not_run' for row in actual['rows'])
    assert subject.read(tmp_path/'attempt/closed.json')['status'] == 'failed'


def test_failed_environment_preserves4CPUprobe_cases_beforeOS(tmp_path, monkeypatch):
    protocol = tmp_path/'protocol.json'; probe.save(protocol, {'authored': True})
    plan = {'cutoff_utc': '2099-01-01T00:00:00+00:00'}
    def failed(*args): raise ValueError('authored parity not passed')
    monkeypatch.setattr(probe.launch_contract, 'environment', failed)
    with pytest.raises(ValueError, match='parity'): probe.run(plan, protocol, tmp_path/'attempt')
    value = probe.read(tmp_path/'attempt/closed.json')
    assert value['completed'] == 0 and value['planned'] == 4
    assert all(row['status'] == 'not_run' for row in value['rows'])
