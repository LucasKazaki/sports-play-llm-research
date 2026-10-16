"""Authored metadata-only future evaluation admission tests."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_held_v4 as builder
from test_direct_launch_contract import receipt as direct_receipt


def fixtures():
    args = ['experiments/chess-queen-coach-daytime-v1/daytime_train.py', 'train', '--protocol', 'plan.json', '--out', 'train-1']
    plan = {'expected_worker_arguments': args, 'owned_worker_source': {'sha256': 'new-source'},
        'interpreters': {'delegate': 'base.exe'}}
    completed = {'status': 'completed', 'updates_completed': 192, 'presentations_completed': 1536,
        'partial_accumulation': 0, 'active_unknown': None, 'inflight_training': None,
        'inflight_optimizer': None, 'protocol_sha256': 'protocol', 'frozen_storage': {'identical': True}}
    audit = {'status': 'passed', 'protocol_sha256': 'protocol', 'selection_sha256': 'selection', 'worker_sha256': 'worker'}
    worker = {**direct_receipt(), 'status': 'completed', 'exit_code': 0, 'script': args[0],
        'arguments_sha256': hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        'child_exited_before_lease_release': True}
    return completed, audit, worker, plan


def test_complete_actual_training_gate():
    builder.check_training(*fixtures(), 'selection', 'protocol', 'worker')


@pytest.mark.parametrize('field,value', [('updates_completed', 191), ('presentations_completed', 1535),
    ('partial_accumulation', 1), ('active_unknown', {'micro': 0}),
    ('inflight_training', {'micro': 0}), ('inflight_optimizer', {'step': 1}),
    ('status', 'failed'), ('protocol_sha256', 'other'), ('frozen_storage', {'identical': False})])
def test_incomplete_training_never_admits_evaluation(field, value):
    completed, audit, worker, plan = fixtures()
    completed[field] = value
    with pytest.raises(ValueError):
        builder.check_training(completed, audit, worker, plan, 'selection', 'protocol', 'worker')


def test_audit_and_actual_worker_are_both_bound():
    completed, audit, worker, plan = fixtures()
    with pytest.raises(ValueError):
        builder.check_training(completed, {**audit, 'selection_sha256': 'other'}, worker,
            plan, 'selection', 'protocol', 'worker')
    with pytest.raises(ValueError):
        builder.check_training(completed, audit, {**worker, 'child_exited_before_lease_release': False},
            plan, 'selection', 'protocol', 'worker')


def reservation():
    return {'schema': 'chess.daytime.fresh-held-admission.v1', 'status': 'reserved_unspent',
        'model_requests_before_admission': 0, 'reference_semantics_opened_for_quality': False,
        'input_sha256': 'inputs', 'daytime_authority_sha256': 'authority', 'roots': 16,
        'planned_raw_responses': 96, 'all512_reserved_from_training': True}


def test_fresh_reserved_cohort_admission():
    builder.check_reservation(reservation(), {'sha256': 'inputs'}, {'sha256': 'authority'})


@pytest.mark.parametrize('key,value', [('model_requests_before_admission', 1),
    ('reference_semantics_opened_for_quality', True), ('planned_raw_responses', 48),
    ('roots', 15), ('input_sha256', 'other'), ('all512_reserved_from_training', False),
    ('daytime_authority_sha256', 'expired')])
def test_spent_changed_or_shortened_panel_is_rejected(key, value):
    changed = {**reservation(), key: value}
    with pytest.raises(ValueError):
        builder.check_reservation(changed, {'sha256': 'inputs'}, {'sha256': 'authority'})


def test_no_backend_import_or_real_held_content_access():
    assert not {'torch', 'transformers', 'bitsandbytes', 'peft'} & set(sys.modules)


def test_held_dispatch_contract_replaces_qualifier_inheritance():
    proof_args = ['old-qualifying-outer.py', '--protocol', 'actual-spent-qualifier.json', '--out', 'qualifier-1']
    plan = {'expected_worker_script': proof_args[0], 'expected_worker_arguments': proof_args,
        'qualification_worker_script': proof_args[0], 'qualification_worker_arguments': proof_args.copy(),
        'profile': 'software only', 'selection': 'two spent DEV', 'acceptance': 'two children',
        'root_dispatch': '450s qualification', 'guard_limit': 'qualification450',
        'failure_limit': 'future96notyetqualified'}
    protocol = builder.ROOT / 'experiments/chess-queen-coach-daytime-v1/held-protocol.json'
    builder.held_contract(plan, protocol)
    expected = ['experiments/chess-queen-coach-daytime-v1/cold_eval_v7.py', '--protocol',
        str(protocol.relative_to(builder.ROOT)), '--out', 'data/private/chess-queen-coach-daytime-v1/held-1']
    assert plan['expected_worker_arguments'] == expected
    assert plan['expected_worker_script'] == expected[0]
    assert plan['qualification_worker_arguments'] == proof_args
    assert plan['qualification_worker_script'] == proof_args[0]
    for key in ('profile', 'selection', 'acceptance', 'root_dispatch', 'guard_limit', 'failure_limit'):
        assert '96' in plan[key] or '4500' in plan[key]
    assert '20:30UTC' in plan['root_dispatch'] and 'global22UTC' in plan['root_dispatch']


@pytest.mark.parametrize('change', ['legacy_worker', 'wrong_source', 'owner_false', 'job_residual'])
def test_closed_training_requires_actual_direct_owned_worker(change):
    completed, audit, worker, plan = fixtures()
    if change == 'legacy_worker':
        for key in ['schema', 'source_sha256', 'launch_profile', 'ownership', 'owned_job_exit_verified']:
            worker.pop(key, None)
    elif change == 'wrong_source': worker['source_sha256'] = 'legacy-source'
    elif change == 'owner_false': worker['ownership']['before_go']['member_of_explicit_creator_job'] = False
    else: worker['ownership']['closure']['complete_job_pids'] = [20]
    with pytest.raises(ValueError):
        builder.check_training(completed, audit, worker, plan, 'selection', 'protocol', 'worker')
