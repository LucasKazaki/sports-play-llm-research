"""Pure CPU fixed-budget, plateau and inflight-denominator contracts."""
import copy
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('memory_qualification',ROOT/'experiments/chess-queen-coach-sft-training-v2/memory_qualification_v1.py')
qualification=importlib.util.module_from_spec(spec);spec.loader.exec_module(qualification)


def ready():
    live={'parameters':'hash-w','gradients':'hash-g','gradient_tensors':144}
    state={'updates_completed':32,'presentations_completed':256,
        'rows':[{'status':'backward_completed'}for _ in range(256)],
        'optimizer_rows':[{'status':'completed'}for _ in range(32)],
        'generation':{'status':'partial','generated_tokens':1024},'resource_failure':None,
        'frozen_storage':{'identical':True},'adapter_before':'old','adapter_after':'new',
        'preservation':[{'before':live.copy(),'after':live.copy()}for _ in range(2)]}
    boundaries=[{'process':{'available':True,'private_usage_bytes':10_000_000_000},
        'cuda_allocated_bytes':3_600_000_000,'cuda_reserved_bytes':3_700_000_000}for _ in range(32)]
    plan={'qualification':{'maximum_private_tail_span_bytes':512*1024**2,'maximum_cuda_tail_span_bytes':256*1024**2}}
    return state,boundaries,plan


def test_success_requires_full_budget_real_frozen_change_and_live_preservation():
    state,boundaries,plan=ready()
    assert all(qualification.qualification_checks(state,boundaries,plan).values())
    for field,bad in [('updates_completed',31),('presentations_completed',255),('adapter_after','old')]:
        changed=copy.deepcopy(state);changed[field]=bad
        assert not all(qualification.qualification_checks(changed,boundaries,plan).values())
    state['preservation'][1]['after']['gradients']='changed'
    assert not qualification.qualification_checks(state,boundaries,plan)['two_cleanups_preserve_live_tensors']


def test_private_or_allocator_growth_missing_counters_and_short_stress_fail():
    state,boundaries,plan=ready();boundaries[-1]['process']['private_usage_bytes']+=512*1024**2+1
    assert not qualification.qualification_checks(state,boundaries,plan)['process_tail_plateau']
    boundaries[-1]['cuda_reserved_bytes']+=256*1024**2+1
    assert not qualification.qualification_checks(state,boundaries,plan)['cuda_reserved_tail_plateau']
    boundaries[-1]['process']['available']=False
    assert not qualification.qualification_checks(state,boundaries,plan)['process_tail_plateau']
    state['generation']['generated_tokens']=1000
    assert not qualification.qualification_checks(state,boundaries,plan)['full_prefix_exercised']


def test_failed_inflight_model_and_optimizer_calls_remain_unknown_not_notrun():
    state,_,_=ready()
    state['rows'][20]['status']='call_started';state['rows'][21]['status']='not_run'
    state['optimizer_rows'][2]['status']='call_started';state['generation']['status']='call_started'
    qualification.mark_unknown(state)
    assert state['rows'][20]['status']=='active_unknown'and state['rows'][21]['status']=='not_run'
    assert state['optimizer_rows'][2]['status']=='active_unknown'and state['generation']['status']=='active_unknown'
    assert len(state['rows'])==256 and len(state['optimizer_rows'])==32
