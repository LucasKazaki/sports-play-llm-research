"""Authored actual-ownerfalse and incomplete-closure counterexamples."""
import copy
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import direct_launch_contract as subject


def receipt():
    return {'schema': 'chess.owned-worker.v2', 'source_sha256': 'new-source', 'launch_profile': subject.PROFILE,
        'status': 'completed', 'exit_code': 0, 'child_pid': 19, 'child_exited_before_lease_release': True,
        'owned_member_before_go': True, 'owned_job_exit_verified': True,
        'ownership': {'before_go': {'creator_identity': {'pid': 18, 'image': 'base.exe', 'created': 100},
            'child_identity': {'pid': 19, 'image': 'base.exe', 'created': 101},
            'popen_handle_pid_matches': True, 'member_of_explicit_creator_job': True,
            'creator_member_of_explicit_child_job': False, 'job_handle_passed_to_child': False, 'complete_job_pids': [19]},
            'after_go_complete_job_pids': [19], 'closure': {'complete_job_pids': [],
                'child_stable_handle_exited': True, 'actual_job_handle_closed': True}}}


def check(value): subject.owned_worker(value, {'sha256': 'new-source'}, {'delegate': 'base.exe'})


def test_actual_explicit_creator_owned_direct_identity_and_empty_job_close(): check(receipt())


@pytest.mark.parametrize('change', ['any_job_only', 'wrong_source', 'wrong_profile', 'wrong_pid', 'wrong_image',
    'popen_mismatch', 'creator_in_child_job', 'missing_list_pid', 'duplicate_list', 'residual_child', 'not_exited', 'job_not_closed', 'child_held_job_handle'])
def test_any_job_or_incomplete_creator_evidence_cannot_pass(change):
    value = receipt(); before = value['ownership']['before_go']; closure = value['ownership']['closure']
    if change == 'any_job_only': before['member_of_explicit_creator_job'] = False; before['in_any_job'] = True
    elif change == 'wrong_source': value['source_sha256'] = 'old-source'
    elif change == 'wrong_profile': value['launch_profile'] = 'old-venv-launcher'
    elif change == 'wrong_pid': before['child_identity']['pid'] = 20
    elif change == 'wrong_image': before['child_identity']['image'] = 'venv.exe'
    elif change == 'popen_mismatch': before['popen_handle_pid_matches'] = False
    elif change == 'creator_in_child_job': before['creator_member_of_explicit_child_job'] = True
    elif change == 'missing_list_pid': before['complete_job_pids'] = []
    elif change == 'duplicate_list': before['complete_job_pids'] = [19, 19]
    elif change == 'residual_child': closure['complete_job_pids'] = [20]
    elif change == 'not_exited': closure['child_stable_handle_exited'] = False
    elif change == 'job_not_closed': closure['actual_job_handle_closed'] = False
    else: before['job_handle_passed_to_child'] = True
    with pytest.raises(ValueError): check(value)
