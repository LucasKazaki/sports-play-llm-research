from pathlib import Path
import ast
import json
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chess_move_policy_v6_run2 as run2
import chess_move_policy_v6 as original
import chess_native_resources as resources


def test_scientific_objective_and_selector_are_unchanged():
    def tree(module,name):
        value=ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
        return ast.dump(next(n for n in value.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
    for name in ('objective','legal_action_indices','selection_key','choose_rollout'):
        assert tree(run2,name)==tree(original,name)


def test_six_gib_reserve_rejects_lower_sample(tmp_path,monkeypatch):
    gib=resources.GIB
    state=resources.Sample(32*gib,10*gib,48*gib,41*gib,16*gib,11*gib)
    monkeypatch.setattr(resources,'windows_sample',lambda:state)
    run2.resource_check(tmp_path,{'maximum_seconds':10000},run2.time.perf_counter())
    state=resources.Sample(32*gib,10*gib,48*gib,43*gib,16*gib,11*gib)
    with pytest.raises(RuntimeError,match='commit_headroom'):
        run2.resource_check(tmp_path,{'maximum_seconds':10000},run2.time.perf_counter())


def test_forward_guard_covers_all_phases_and_throttles(tmp_path,monkeypatch):
    import torch
    times=iter([1.,1.2,2.2]);seen=[]
    monkeypatch.setattr(run2.time,'perf_counter',lambda:next(times))
    monkeypatch.setattr(run2,'resource_check',lambda *a:seen.append(True))
    model=torch.nn.Linear(1,1)
    handle=run2.attach_forward_guard(model,tmp_path,{},0)
    for _ in range(3):model(torch.zeros(1,1))
    handle.remove()
    assert len(seen)==2


def test_failure_ledger_keeps_every_future_case(tmp_path):
    labels={'splits':{'development':[{'id':'d'}],'holdout':[{'id':'h'}],'rollout':[{'id':'r'}]}}
    run2.plan_outcomes(tmp_path,labels,{'training':{'checkpoints':[0,256]}})
    run2.save(tmp_path/'active-evaluation.json',{'name':'step-0-development'})
    run2.finalize_outcomes(tmp_path)
    ledger=run2.read(tmp_path/'outcome-ledger.json')['cohorts']
    assert ledger['step-0-development']['status']=='unknown_after_interruption'
    assert ledger['starting-holdout']['ids']==['h']
    assert ledger['selected-rollout-raw']['ids']==['r']
    assert ledger['step-256-development']['status']=='not_run'


def test_identical_starting_selection_retains_explicit_no_second_call(tmp_path):
    labels={'splits':{'development':[{'id':'d'}],'holdout':[{'id':'h'}],'rollout':[{'id':'r'}]}}
    run2.plan_outcomes(tmp_path,labels,{'training':{'checkpoints':[0]}})
    run2.save(tmp_path/'selection-before-holdout.json',{'selected_step':0})
    run2.save(tmp_path/'starting-holdout.json',{'records':[{'id':'h'}]})
    run2.finalize_outcomes(tmp_path)
    assert 'no second model call' in run2.read(tmp_path/'outcome-ledger.json')['cohorts']['selected-holdout']['status']
