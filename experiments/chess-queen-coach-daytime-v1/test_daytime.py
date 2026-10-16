"""Authored CPU contracts only; never read a real corpus or initialize a backend."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
from unittest.mock import patch
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'scripts'))
import daytime_contract as contract
import daytime_train as daytime
import qualify_training as qualification


def functions(path):
    return {node.name: ast.dump(node) for node in ast.parse(path.read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_scientific_functions_identical_to_frozen_overnight():
    old = ROOT / 'scripts/chess_queen_coach_counterfactual_train_v2.py'
    assert hashlib.sha256(old.read_bytes()).hexdigest() == '98623ce21801896b3139395355dc41d4580e3ec2707cbaf0a43e6741be170714'
    previous, current = functions(old), functions(HERE / 'daytime_train.py')
    assert set(current) == set(previous)
    assert {name for name in current if current[name] != previous[name]} == {'verify_protocol', 'admit'}
    assert daytime.STEPS == (0, 48, 96, 192)
    assert daytime.Runtime is qualification.Runtime


def test_frameworks_absent():
    assert not {'torch', 'transformers', 'bitsandbytes', 'peft'} & set(sys.modules)


def authority():
    return {'schema': 'chess.daytime.resume-authority.v1',
        'human_text': 'Continue today until 6:00 PM Eastern', 'timezone': 'America/New_York',
        'date': '2026-10-16', 'cutoff_utc': contract.CUTOFF}


def window_plan():
    return {'daytime_authority': {}, 'cutoff_utc': contract.CUTOFF,
        'admission_latest_utc': contract.TRAIN_ADMISSION,
        'held_admission_latest_utc': contract.HELD_ADMISSION}


def test_dated_authority_and_admissions():
    plan = window_plan()
    contract.windows(plan, lambda _: None, lambda _: authority())
    contract.admit(plan, datetime(2026, 10, 16, 18, 59, 59, tzinfo=timezone.utc))
    with pytest.raises(RuntimeError):
        contract.admit(plan, datetime(2026, 10, 16, 19, tzinfo=timezone.utc))
    for key in ('cutoff_utc', 'admission_latest_utc', 'held_admission_latest_utc'):
        broken = {**plan, key: '2026-10-16T13:00:00+00:00'}
        with pytest.raises(ValueError):
            contract.windows(broken, lambda _: None, lambda _: authority())


def test_wrong_authority_not_accepted():
    with pytest.raises(ValueError):
        contract.windows(window_plan(), lambda _: None,
            lambda _: {**authority(), 'human_text': 'Maybe later'})


def test_science_and_phase_caps_are_value_bound():
    plan = {key: {'authored': key} for key in contract.SCIENCE_FIELDS}
    plan['phase_maximum_seconds'] = {'training': 3000, 'heldout': 4500}
    contract.science(plan, copy.deepcopy(plan))
    for key in contract.SCIENCE_FIELDS:
        broken = {**plan, key: {'changed': True}}
        with pytest.raises(ValueError, match='Frozen science changed'):
            contract.science(broken, plan)
    with pytest.raises(ValueError):
        contract.science({**plan, 'phase_maximum_seconds': {'training': 30, 'heldout': 4500}}, plan)


def test_exact_tokenizer_formatter_receipt():
    plan = {'expected_formatter': {'sha256': 'formatter'}, 'expected_tokenizer_bindings': {'asset': {'sha256': 'tokenizer'}}}
    actual = {'official_formatter_sha256': 'formatter', 'tokenizer_bindings': plan['expected_tokenizer_bindings']}
    contract.tokenizer(plan, actual)
    for key in actual:
        with pytest.raises(ValueError):
            contract.tokenizer(plan, {**actual, key: None})


def gate_fixture():
    store = {}
    plan = {'warm_start': {'sha256': 'original64'}, 'counterfactual_runtime': {'sha256': 'wrapper'}, 'qualification_gates': {}}
    for name in ('update', 'cold'):
        arguments = [name + '.py', '--protocol', name + '.json', '--out', name + '-1']
        protocol = {'expected_worker_arguments': arguments, 'expected_worker_script': arguments[0],
            'warm_start': plan['warm_start'], 'counterfactual_runtime': plan['counterfactual_runtime'],
            'maximum_seconds': 600, 'model_runtime': {'warm_start': plan['warm_start']},
            'raw_provenance': {'candidate_id': 'queen-pawn-8/nf4-coach-counterfactual-v1',
                'qualified_runtime_source_sha256': '7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349'}}
        result = {'status': 'passed', 'protocol_sha256': name + '-protocol',
            'updates_completed': 1, 'presentations_completed': 8, 'disposable_not_candidate': True,
            'checks': {key: True for key in contract.UPDATE_CHECKS}, 'planned': 2,
            'completed_children': 2, 'all_children_closed': True, 'outer_torch_imported': False}
        worker = {'status': 'completed', 'exit_code': 0, 'script': arguments[0],
            'arguments_sha256': hashlib.sha256(json.dumps(arguments).encode()).hexdigest(),
            'child_exited_before_lease_release': True}
        audit = {'status': 'passed', 'protocol_sha256': name + '-protocol',
            'qualification_sha256': name + '-result', 'worker_sha256': name + '-worker'}
        stage = {'script': arguments[0], 'arguments': arguments}
        for label, value in [('protocol', protocol), ('result', result), ('worker', worker), ('audit', audit)]:
            key = name + '-' + label
            store[key] = value
            stage[label] = {'path': key, 'sha256': key}
        plan['qualification_gates'][name] = stage
    return plan, store


def test_both_actual_closed_qualifications_required():
    plan, store = gate_fixture()
    contract.qualifications(plan, lambda item: item['path'], store.__getitem__)
    store['update-result']['checks']['adapter_changed'] = False
    with pytest.raises(ValueError):
        contract.qualifications(plan, lambda item: item['path'], store.__getitem__)


@pytest.mark.parametrize('case', ['old_sft', 'worker_arguments', 'worker_script', 'not_closed', 'audit_hash', 'wrong_original', 'wrong_wrapper'])
def test_wrong_route_or_dispatch_receipts_fail(case):
    plan, store = gate_fixture()
    if case == 'old_sft':
        store['cold-protocol']['raw_provenance']['candidate_id'] = 'queen-pawn-8/nf4-coach-sft-v2'
    elif case == 'worker_arguments':
        store['cold-worker']['arguments_sha256'] = hashlib.sha256(json.dumps(plan['qualification_gates']['cold']['arguments'][1:]).encode()).hexdigest()
    elif case == 'worker_script':
        plan['qualification_gates']['update']['script'] = 'other.py'
    elif case == 'not_closed':
        store['update-worker']['child_exited_before_lease_release'] = False
    elif case == 'audit_hash':
        store['cold-audit']['qualification_sha256'] = 'unrelated'
    elif case == 'wrong_original':
        store['update-protocol']['warm_start'] = {'sha256': 'disposable'}
    else:
        store['update-protocol']['counterfactual_runtime'] = {'sha256': 'other'}
    with pytest.raises(ValueError):
        contract.qualifications(plan, lambda item: item['path'], store.__getitem__)


def test_first_eight_are_same_seeded_training_prefix():
    rows = [{'case_id': str(index)} for index in range(1536)]
    order = list(range(1536))
    random.Random(4082086).shuffle(order)
    assert qualification.first_eight(rows, 4082086) == [rows[index] for index in order[:8]]
    with pytest.raises(ValueError):
        qualification.first_eight(rows[:-1], 4082086)


class FakeRuntime:
    def __init__(self, fail=None): self.calls = []; self.fail = fail
    def loss(self, row, tokens, training):
        assert training is True
        index = int(row['case_id'])
        self.calls.append(('loss', index))
        if self.fail == index: raise RuntimeError('authored backend failure')
        return 2.0
    def release_inactive(self, phase): self.calls.append(('cleanup', phase))
    def verify_gradients(self): self.calls.append(('verify_gradients',))
    def live_hashes(self): return {'gradient_tensors': 144, 'gradients': {'authored': True}}


def micro_fixture(out):
    rows = [{'case_id': str(index)} for index in range(8)]
    state = {'rows': [{'status': 'not_run'} for _ in rows], 'presentations_completed': 0,
        'updates_completed': 0, 'optimizer_status': 'not_run', 'inflight': None}
    return rows, state


def test_eight_micros_complete_before_one_optimizer(tmp_path):
    runtime = FakeRuntime(); rows, state = micro_fixture(tmp_path); events = []
    optimizer = type('Optimizer', (), {'step': lambda self: events.append('step'),
        'zero_grad': lambda self, **kw: events.append(('zero', kw))})()
    qualification.micros(runtime, rows, [None] * 8, optimizer, lambda: (events.append('clip') or 2.0),
        lambda: events.append('sync'), tmp_path, state, lambda: None)
    assert [call for call in runtime.calls if call[0] == 'loss'] == [('loss', index) for index in range(8)]
    assert events == ['clip', 'step', 'sync', ('zero', {'set_to_none': True})]
    assert state['presentations_completed'] == 8 and state['updates_completed'] == 1
    assert all(row['status'] == 'completed' for row in state['rows'])


def test_failed_micro_keeps_unknown_and_later_notrun(tmp_path):
    runtime = FakeRuntime(fail=3); rows, state = micro_fixture(tmp_path)
    with pytest.raises(RuntimeError):
        qualification.micros(runtime, rows, [None] * 8, None, None, None, tmp_path, state, lambda: None)
    assert state['presentations_completed'] == 3 and state['updates_completed'] == 0
    assert [row['status'] for row in state['rows']] == ['completed'] * 3 + ['active_unknown'] + ['not_run'] * 4
    assert len([call for call in runtime.calls if call[0] == 'loss']) == 4
    assert state['optimizer_status'] == 'not_run'


def test_failed_optimizer_retains_eight_completed_and_unknown_update(tmp_path):
    rows, state = micro_fixture(tmp_path)
    optimizer = type('Optimizer', (), {'step': lambda self: (_ for _ in ()).throw(RuntimeError('update'))})()
    with pytest.raises(RuntimeError):
        qualification.micros(FakeRuntime(), rows, [None] * 8, optimizer, lambda: 2.0,
            lambda: None, tmp_path, state, lambda: None)
    assert state['presentations_completed'] == 8 and state['updates_completed'] == 0
    assert state['optimizer_status'] == 'active_unknown'


def test_nonfinite_clip_stops_before_optimizer(tmp_path):
    rows, state = micro_fixture(tmp_path)
    with pytest.raises(ValueError, match='gradient norm'):
        qualification.micros(FakeRuntime(), rows, [None] * 8, None, lambda: float('inf'),
            None, tmp_path, state, lambda: None)
    assert state['presentations_completed'] == 8
    assert state['optimizer_status'] == 'not_run' and state['updates_completed'] == 0
    assert state['gradient_clip_norm_finite_positive'] is False
    assert 'gradient_clip_norm' not in state
    json.dumps(state, allow_nan=False)


def test_short_micro_list_rejected_before_calls(tmp_path):
    rows, state = micro_fixture(tmp_path); runtime = FakeRuntime()
    with pytest.raises(ValueError):
        qualification.micros(runtime, rows, [None] * 7, None, None, None, tmp_path, state, lambda: None)
    assert runtime.calls == []


def test_guard_setup_failure_retains_full_eight_pending_without_model(tmp_path):
    protocol = tmp_path / 'protocol.json'; protocol.write_text('{}')
    plan = {'data': {'train': {}}, 'training': {'seed': 4082086}}
    all_rows = [{'case_id': str(index)} for index in range(1536)]
    def broken(): raise RuntimeError('authored setup guard failure')
    def no_model(*args): raise AssertionError('backend must never be constructed')
    out = tmp_path / 'attempt'
    with patch.object(qualification, 'verify', return_value=plan), \
        patch.object(qualification.checked.nf4, 'binding', return_value=protocol), \
        patch.object(qualification.preserved, 'read_rows', return_value=all_rows), \
        patch.object(qualification, 'snapshot', return_value=None):
        with pytest.raises(RuntimeError):
            qualification.run(plan, protocol, out, no_model, broken)
    result = json.loads((out / 'qualification.json').read_text())
    assert result['status'] == 'failed' and result['presentations_completed'] == 0
    assert len(result['rows']) == 8 and all(row['status'] == 'not_run' for row in result['rows'])
    assert result['optimizer_status'] == 'not_run' and (out / 'resources.json').read_text().strip() == '[]'


def test_disposable_adapter_not_scientific_warm_start():
    source = (HERE / 'qualify_training.py').read_text()
    assert "out / 'disposable-not-a-candidate'" in source
    assert 'identity[\'warm_start\'] != plan[\'warm_start\']' in source
    tree = ast.parse((HERE / 'daytime_train.py').read_text())
    assert "Runtime(plan,guard)" in (HERE / 'daytime_train.py').read_text()
    assert 'disposable_adapter' not in ast.dump(tree)
