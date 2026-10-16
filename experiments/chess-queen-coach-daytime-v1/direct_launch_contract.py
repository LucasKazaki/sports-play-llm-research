"""Pure metadata gates for the new direct-base worker; no OS/backend calls."""
from pathlib import Path
from job_context_direct_v1 import PROFILE
from job_context import normalized


def complete_ids(value):
    if not isinstance(value, list) or any(type(pid) is not int or pid <= 0 for pid in value) or len(set(value)) != len(value):
        raise ValueError('Complete unique positive explicit-job list required')
    return set(value)


def owned_worker(receipt, source, interpreters):
    """Any-job membership never substitutes for actual creator-held-job proof."""
    before = receipt.get('ownership', {}).get('before_go', {})
    closed = receipt.get('ownership', {}).get('closure', {})
    creator = before.get('creator_identity', {}); child = before.get('child_identity', {})
    if (receipt.get('schema') != 'chess.owned-worker.v2' or receipt.get('source_sha256') != source['sha256']
        or receipt.get('launch_profile') != PROFILE or receipt.get('status') != 'completed'
        or type(receipt.get('exit_code')) is not int or receipt['exit_code'] != 0
        or receipt.get('child_exited_before_lease_release') is not True
        or receipt.get('owned_member_before_go') is not True or receipt.get('owned_job_exit_verified') is not True
        or before.get('popen_handle_pid_matches') is not True or before.get('member_of_explicit_creator_job') is not True
        or before.get('creator_member_of_explicit_child_job') is not False
        or before.get('job_handle_passed_to_child') is not False
        or type(child.get('pid')) is not int or child['pid'] <= 0 or child['pid'] != receipt.get('child_pid')
        or type(creator.get('pid')) is not int or creator['pid'] <= 0 or creator['pid'] == child['pid']
        or normalized(child.get('image', '')) != normalized(interpreters['delegate'])
        or normalized(creator.get('image', '')) != normalized(interpreters['delegate'])
        or type(child.get('created')) is not int or type(creator.get('created')) is not int
        or child['created'] <= 0 or creator['created'] <= 0
        or child['created'] < creator['created']
        or closed.get('child_stable_handle_exited') is not True or closed.get('actual_job_handle_closed') is not True):
        raise ValueError('Exact direct-base creator-owned handle/identity/EXIT evidence required')
    if complete_ids(before.get('complete_job_pids')) != {child['pid']}:
        raise ValueError('Actual child must be sole explicit creator-job member beforeGO')
    complete_ids(receipt.get('ownership', {}).get('after_go_complete_job_pids'))
    if complete_ids(closed.get('complete_job_pids')):
        raise ValueError('Explicit creator job still has active members at closure')


def environment(plan, bound, read):
    source = plan['owned_worker_source']; path = bound(source)
    if path.resolve() != (Path(__file__).resolve().parent/'owned_worker_v2.py').resolve():
        raise ValueError('Wrong direct-base owned worker source')
    if plan['launch_profile'] != PROFILE: raise ValueError('Wrong prospective launch profile')
    stage = plan['cpu_environment_parity']
    frozen = read(bound(stage['protocol'])); result = read(bound(stage['result']))
    worker = read(bound(stage['worker'])); audit = read(bound(stage['audit']))
    owned_worker(worker, source, plan['interpreters'])
    if (result.get('status') != 'passed' or result.get('launch_profile') != PROFILE
        or result.get('worker_source_sha256') != source['sha256']
        or result.get('protocol_sha256') != stage['protocol']['sha256']
        or result.get('candidate_worker_sha256') != stage['worker']['sha256']
        or audit.get('status') != 'passed' or audit.get('protocol_sha256') != stage['protocol']['sha256']
        or audit.get('parity_sha256') != stage['result']['sha256']
        or audit.get('worker_sha256') != stage['worker']['sha256']):
        raise ValueError('Actual closed CPU environment parity and independent audit required')
    return frozen
