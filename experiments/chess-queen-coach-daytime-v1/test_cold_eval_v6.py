"""Serial fake children prove new context gates without an OS/backend call."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import cold_eval_v6 as subject
spec = importlib.util.spec_from_file_location('old_cold_authored_fixtures', ROOT / 'tests/test_chess_queen_coach_counterfactual_cold_eval_v5.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)

POLICY = {'unretained_error': 87, 'fresh_complete_observations': 2, 'separation_ms': 10,
    'maximum_observation_ms': 1000, 'classification': 'ABSENT_not_EXIT', 'baseline_only_after_sampler': True}


class Context:
    def __init__(self, fail_stage=None): self.stages = []; self.fail_stage = fail_stage; self.closed = False
    def describe(self): return {'authored_fake_context': True}
    def assert_baseline_only(self, stage):
        self.stages.append(stage)
        if stage == self.fail_stage: raise ValueError('authored residual job member')
        return {'stage': stage, 'baseline_handles_live': True}
    def close(self): self.closed = True


def setup(tmp_path, monkeypatch, mode='qualification'):
    monkeypatch.setattr(prior, 'subject', subject)
    plan, protocol, rows = prior.setup(tmp_path, mode)
    plan.update(process_lineage_helper={'path': str(HERE / 'process_lineage_v5.py'), 'sha256': subject.digest(HERE / 'process_lineage_v5.py')},
        job_context_source={'path': str(HERE / 'job_context.py'), 'sha256': subject.digest(HERE / 'job_context.py')},
        job_context_policy=POLICY)
    probe_plan = tmp_path / 'cpu-probe-plan.json'
    probe_value = {key: plan[key] for key in ('process_lineage_helper', 'job_context_source', 'job_context_policy', 'resource_sampler_auxiliary')}
    probe_value.update(cold_outer_source={'sha256': plan['implementation_sha256']}, expected_worker_arguments=['authored-probe.py', '--out', 'fixed'])
    subject.save(probe_plan, probe_value)
    probe = tmp_path / 'cpu-probe.json'
    subject.save(probe, {'status': 'passed', 'planned': 4, 'completed': 4, 'exact_87_measurements': 1,
        'torch_imported': False, 'model_calls': 0, 'engine_calls': 0, 'CUDA_initializations': 0,
        'protocol_sha256': subject.digest(probe_plan), 'final_baseline_only': {'baseline_handles_live': True}})
    probe_worker = tmp_path / 'cpu-worker.json'
    subject.save(probe_worker, {'status': 'completed', 'exit_code': 0, 'child_exited_before_lease_release': True,
        'script': 'authored-probe.py', 'arguments_sha256': subject.hashlib.sha256(json.dumps(probe_value['expected_worker_arguments']).encode()).hexdigest()})
    probe_audit = tmp_path / 'cpu-audit.json'
    subject.save(probe_audit, {'status': 'passed', 'protocol_sha256': subject.digest(probe_plan),
        'probe_sha256': subject.digest(probe), 'worker_sha256': subject.digest(probe_worker)})
    for key, path in [('cpu_observer_probe', probe), ('cpu_observer_protocol', probe_plan),
        ('cpu_observer_worker', probe_worker), ('cpu_observer_audit', probe_audit)]:
        plan[key] = {'path': str(path), 'sha256': subject.digest(path)}
    if mode == 'heldout':
        qpath = Path(plan['qualification_protocol']['path']); qualified = subject.read(qpath)
        for key in ('process_lineage_helper', 'job_context_source', 'job_context_policy',
            'cpu_observer_probe', 'cpu_observer_protocol', 'cpu_observer_worker', 'cpu_observer_audit'): qualified[key] = plan[key]
        subject.save(qpath, qualified); plan['qualification_protocol']['sha256'] = subject.digest(qpath)
        rpath = Path(plan['successful_qualification']['path']); receipt = subject.read(rpath)
        receipt['protocol_sha256'] = subject.digest(qpath); subject.save(rpath, receipt)
        plan['successful_qualification']['sha256'] = subject.digest(rpath)
        apath = Path(plan['qualification_audit']['path']); audit = subject.read(apath)
        audit.update(protocol_sha256=subject.digest(qpath), qualification_sha256=subject.digest(rpath))
        subject.save(apath, audit); plan['qualification_audit']['sha256'] = subject.digest(apath)
    subject.save(protocol, plan)
    return plan, protocol, rows


def runner(plan, protocol, calls, fail=None):
    old = prior.fake_runner(plan, protocol, calls, fail)
    def fake(command, folder, maximum, cancel, cutoff, deadline, context):
        assert context.stages[-1] == 'before_next_request'
        return old(command, folder, maximum, cancel, cutoff, deadline)
    return fake


def test_two_requests_check_baseline_after_sampler_and_close_without_torch(tmp_path, monkeypatch):
    plan, protocol, _ = setup(tmp_path, monkeypatch); ctx = Context(); calls = []
    result = subject.run(plan, protocol, tmp_path / 'attempt', runner(plan, protocol, calls),
        lambda: {'commit_total_bytes': 1000}, lambda audit: ctx)
    assert result['status'] == 'passed' and calls == ['0', '1'] and ctx.closed
    assert ctx.stages == ['before_next_request', 'after_postexit_resource_sampler',
        'before_next_request', 'after_postexit_resource_sampler', 'whole_phase_finalization']
    assert not result['outer_torch_imported'] and not result['labels_opened']


@pytest.mark.parametrize('stage', ['construction', 'after_postexit_resource_sampler', 'whole_phase_finalization'])
def test_context_failure_preserves_full_panel_and_stops_further_dispatch(tmp_path, monkeypatch, stage):
    plan, protocol, _ = setup(tmp_path, monkeypatch); calls = []; ctx = Context(stage)
    def factory(audit):
        if stage == 'construction': raise ValueError('authored context setup failure')
        return ctx
    with pytest.raises((ValueError, RuntimeError)):
        subject.run(plan, protocol, tmp_path / 'attempt', runner(plan, protocol, calls),
            lambda: {'commit_total_bytes': 1000}, factory)
    panel = subject.read(tmp_path / 'attempt/software.json')
    assert len(panel['rows']) == 2 and len(calls) == {'construction': 0, 'after_postexit_resource_sampler': 1, 'whole_phase_finalization': 2}[stage]
    assert all(row['status'] == 'not_run' for row in panel['rows'][len(calls):])
    assert subject.read(tmp_path / 'attempt/closed.json')['status'] == 'failed'
    assert (tmp_path / 'attempt/resources.json').exists()


def test_unknown_first_child_preserves96_denominator_and_never_opens_truth(tmp_path, monkeypatch):
    plan, protocol, _ = setup(tmp_path, monkeypatch, 'heldout'); calls = []; ctx = Context()
    plan['heldout_references'] = {'path': 'FORBIDDEN', 'sha256': 'never'}; subject.save(protocol, plan)
    with pytest.raises(RuntimeError):
        subject.run(plan, protocol, tmp_path / 'attempt', runner(plan, protocol, calls, 'timeout'),
            lambda: {'commit_total_bytes': 1000}, lambda audit: ctx)
    baseline = subject.read(tmp_path / 'attempt/baseline.json')['rows']; selected = subject.read(tmp_path / 'attempt/selected.json')['rows']
    assert len(baseline) == len(selected) == 48 and calls == ['0']
    assert baseline[0]['status'] == 'active_unknown' and all(row['status'] == 'not_run' for row in baseline[1:] + selected)


def test_weakened_absence_policy_fails_before_context_or_child(tmp_path, monkeypatch):
    plan, protocol, _ = setup(tmp_path, monkeypatch); plan['job_context_policy'] = {**POLICY, 'fresh_complete_observations': 1}
    subject.save(protocol, plan)
    def forbidden(*args): raise AssertionError('context/child was constructed')
    with pytest.raises(ValueError, match='policy'):
        subject.run(plan, protocol, tmp_path / 'attempt', forbidden, context_factory=forbidden)
    assert all(row['status'] == 'not_run' for row in subject.read(tmp_path / 'attempt/software.json')['rows'])


@pytest.mark.parametrize('mutation', ['probe_failed', 'missing_87', 'worker_arguments', 'different_outer'])
def test_unmeasured_or_different_os_probe_never_admits_model_child(tmp_path, monkeypatch, mutation):
    plan, protocol, _ = setup(tmp_path, monkeypatch)
    key = 'cpu_observer_worker' if mutation == 'worker_arguments' else 'cpu_observer_protocol' if mutation == 'different_outer' else 'cpu_observer_probe'
    path = Path(plan[key]['path']); value = subject.read(path)
    if mutation == 'probe_failed': value['status'] = 'failed'
    elif mutation == 'missing_87': value['exact_87_measurements'] = 0
    elif mutation == 'worker_arguments': value['arguments_sha256'] = 'different'
    else: value['cold_outer_source']['sha256'] = 'other-source'
    subject.save(path, value); plan[key]['sha256'] = subject.digest(path); subject.save(protocol, plan)
    def forbidden(*args): raise AssertionError('No model child permitted')
    with pytest.raises(ValueError): subject.run(plan, protocol, tmp_path / 'attempt', forbidden)
    assert all(row['status'] == 'not_run' for row in subject.read(tmp_path / 'attempt/software.json')['rows'])
