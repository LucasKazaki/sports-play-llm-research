"""Authored state observations only; no process, framework or GPU calls."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_context import JobContext, normalized


def record(pid, parent, image, created):
    return dict(pid=pid, parent_pid=parent, image=normalized(image), created=created, in_job=True)


class Fake:
    def __init__(self, direct=False, console=False):
        self.records = {10: record(10, 9, 'base.exe', 100)}
        if not direct: self.records[9] = record(9, 1, 'venv.exe', 90)
        if console: self.records[11] = record(11, 9, 'conhost.exe', 91)
        self.parents = {0: 0, **{pid: row['parent_pid'] for pid, row in self.records.items()}}
        self.active = list(self.records)
        self.dead = set(); self.closed = []; self.requests = []
        self.k = self
    def snapshot(self): return dict(self.parents)
    def current_job_pids(self): return list(self.active)
    def retain(self, pid, parent, **kwargs):
        self.requests.append((pid, kwargs)); return pid, dict(self.records[pid])
    def exited(self, handle): return handle in self.dead
    def CloseHandle(self, handle): self.closed.append(handle)
    def console_image(self): return normalized('conhost.exe')


def context(fake=None, **kwargs):
    fake = fake or Fake()
    return JobContext(fake, outer_pid=10, venv_image='venv.exe', base_image='base.exe', **kwargs)


def add_runtime(fake):
    parent = record(20, 10, 'base.exe', 200)
    fake.parents[20] = 10; fake.active.append(20)
    return parent


def observation(**updates):
    return {'pid': 30, 'parent_pid': 20, 'stage': 'OpenProcess', 'open_process_winerror': 87, **updates}


def test_exact_context_includes_actual_outer_stub_and_optional_console_query_only():
    fake = Fake(console=True); ctx = context(fake)
    assert ctx.baseline == {9, 10, 11}
    assert all(request == {'termination_rights': False} for _, request in fake.requests)
    assert not ctx.describe()['baseline_handles_have_termination_rights']
    ctx.close(); assert set(fake.closed) == {9, 10, 11}


def test_direct_outer_and_normal_pid_zero_snapshot_are_valid():
    fake = Fake(direct=True)
    ctx = JobContext(fake, outer_pid=10, venv_image='base.exe', base_image='base.exe')
    assert ctx.baseline == {10} and 0 in fake.snapshot()


@pytest.mark.parametrize('change', ['image', 'parent', 'creation', 'job', 'extra', 'console_image'])
def test_baseline_never_accepts_other_image_ancestry_job_or_member(change):
    fake = Fake(console=change == 'console_image')
    if change == 'image': fake.records[9]['image'] = normalized('other.exe')
    elif change == 'parent': fake.records[10]['parent_pid'] = 50
    elif change == 'creation': fake.records[9]['created'] = 101
    elif change == 'job': fake.records[9]['in_job'] = False
    elif change == 'extra': fake.active.extend([12, 13])
    else: fake.records[11]['image'] = normalized('other-conhost.exe')
    with pytest.raises(ValueError): context(fake)
    assert fake.closed  # Any retained query handles close on failed construction.


def test_two_fresh_absences_are_not_exit_identity_or_kill_authority():
    events = []; fake = Fake(); ctx = context(fake, audit=events.append)
    parent = add_runtime(fake)
    value = ctx.certify_absence(observation(), parent, 20, lambda: 1000)
    assert value['identity_status'] == 'unretained_snapshot_entry_absent'
    assert len(value['observations']) == 2
    assert not any(value[key] for key in ('exit_proved', 'identity_verified', 'termination_permitted', 'stable_handle_retained'))
    assert [event['kind'] for event in events][-1] == 'snapshot_entry_classified_absent'
    assert len([event for event in events if event['kind'] == 'fresh_absence_observation']) == 2


@pytest.mark.parametrize('updates', [{'pid': 0}, {'pid': -1}, {'open_process_winerror': 5},
    {'stage': 'GetProcessTimes'}, {'parent_pid': 21}])
def test_other_error_stage_pid_or_parent_is_ineligible(updates):
    fake = Fake(); ctx = context(fake); parent = add_runtime(fake)
    with pytest.raises(ValueError): ctx.certify_absence(observation(**updates), parent, 20, lambda: 1000)


@pytest.mark.parametrize('change', ['system_present', 'job_present', 'parent_role', 'dead_parent',
    'missing_parent', 'second_present', 'bad_job_list', 'snapshot_failure'])
def test_live_reused_parent_role_incomplete_or_unavailable_observations_fail(change):
    fake = Fake(); ctx = context(fake); parent = add_runtime(fake)
    if change == 'system_present': fake.parents[30] = 20
    elif change == 'job_present': fake.active.append(30)
    elif change == 'parent_role': fake.parents[31] = 30
    elif change == 'dead_parent': fake.dead.add(20)
    elif change == 'missing_parent': fake.active.remove(20)
    elif change == 'bad_job_list': fake.active.append(20)
    elif change == 'snapshot_failure':
        fake.snapshot = lambda: (_ for _ in ()).throw(ValueError('incomplete snapshot'))
    else:
        original = fake.snapshot; calls = []
        def snapshot():
            calls.append(1); return {**original(), **({30: 20} if len(calls) == 2 else {})}
        fake.snapshot = snapshot
    with pytest.raises(ValueError): ctx.certify_absence(observation(), parent, 20, lambda: 1000)


def test_budget_and_cancellation_are_checked_during_second_observation():
    fake = Fake(); ctx = context(fake); parent = add_runtime(fake)
    budget = iter([1000, 1000, 0])
    with pytest.raises(RuntimeError): ctx.certify_absence(observation(), parent, 20, lambda: next(budget))


def test_baseline_closure_rejects_residual_member_or_exited_ancestor():
    fake = Fake(); ctx = context(fake); fake.active.append(30)
    with pytest.raises(ValueError, match='outside'): ctx.assert_baseline_only('before_next')
    fake.active.remove(30); fake.dead.add(9)
    with pytest.raises(ValueError, match='exited'): ctx.assert_baseline_only('final')


def test_absent_ids_remain_reserved_across_child_tracker_lifetimes():
    fake = Fake(); ctx = context(fake); parent = add_runtime(fake)
    ctx.certify_absence(observation(), parent, 20, lambda: 1000)
    fake.active.remove(20); fake.parents.pop(20)
    ctx.assert_baseline_only('after_first_child')
    fake.parents[30] = 1
    with pytest.raises(ValueError, match='reappeared'): ctx.assert_baseline_only('before_next_child')
