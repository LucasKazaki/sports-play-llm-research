"""Authored direct-outer versus venv getpath identity and closure regressions."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import job_context_direct_v1 as subject
from test_job_context import Fake, record, observation


def fixture():
    fake = Fake(direct=True)
    fake.records[9] = record(9, 1, 'base.exe', 90); fake.parents[9] = 1
    return fake


def context(fake, **kwargs):
    return subject.JobContext(fake, outer_pid=10, venv_image='venv.exe', base_image='base.exe', **kwargs)


def test_actual_base_outer_does_not_expect_shadow_venv_launcher_as_parent_member():
    fake = fixture(); ctx = context(fake)
    assert ctx.baseline == {10} and set(ctx.records) == {10} and ctx.creator['pid'] == 9
    assert 9 not in ctx.members() and ctx.describe()['launch_profile'] == subject.PROFILE
    assert all(request == {'termination_rights': False} for _, request in fake.requests)
    ctx.close(); assert set(fake.closed) == {9, 10}


def test_base_environment_without_expected_venv_getpath_is_not_qualified_profile():
    with pytest.raises(ValueError, match='getpath'):
        subject.JobContext(fixture(), outer_pid=10, venv_image='base.exe', base_image='base.exe')


@pytest.mark.parametrize('change', ['outer_image', 'creator_image', 'creator_in_job', 'creator_newer',
    'outer_parent_record', 'creator_missing', 'extra_members'])
def test_wrong_direct_identity_parent_or_membership_is_not_whitelisted(change):
    fake = fixture()
    if change == 'outer_image': fake.records[10]['image'] = subject.normalized('venv.exe')
    elif change == 'creator_image': fake.records[9]['image'] = subject.normalized('other.exe')
    elif change == 'creator_in_job': fake.active.append(9)
    elif change == 'creator_newer': fake.records[9]['created'] = 101
    elif change == 'outer_parent_record': fake.records[10]['parent_pid'] = 8
    elif change == 'creator_missing': fake.parents.pop(9)
    else: fake.active.extend([12, 13])
    with pytest.raises(ValueError): context(fake)
    assert 10 in fake.closed


def test_initial_identity_and_membership_evidence_precedes_constructor_failure():
    fake = fixture(); fake.active.append(9); events = []
    with pytest.raises(ValueError): context(fake, audit=events.append)
    assert events[0]['kind'] == 'direct_context_started_before_observation'
    assert any(event['kind'] == 'direct_context_system_snapshot' for event in events)
    assert [event['pids'] for event in events if event['kind'] == 'direct_context_NULL_job_list'] == [[9, 10]]


def test_closure_requires_retained_creator_alive_outside_and_same_parent():
    fake = fixture(); ctx = context(fake); fake.dead.add(9)
    with pytest.raises(ValueError, match='creator'): ctx.assert_baseline_only('before_next')
    fake.dead.clear(); fake.parents[10] = 8
    with pytest.raises(ValueError, match='ancestry'): ctx.assert_baseline_only('final')


def test_unchanged_absence_rule_remains_phase_wide_and_never_identity_or_exit():
    fake = fixture(); ctx = context(fake); parent = record(20, 10, 'base.exe', 200)
    fake.parents[20] = 10; fake.active.append(20)
    value = ctx.certify_absence(observation(), parent, 20, lambda: 1000)
    assert not value['exit_proved'] and not value['identity_verified'] and not value['termination_permitted']
    fake.active.remove(20); fake.parents.pop(20); ctx.assert_baseline_only('after_child')
    fake.parents[30] = 1
    with pytest.raises(ValueError, match='reappeared'): ctx.assert_baseline_only('before_second_child')
