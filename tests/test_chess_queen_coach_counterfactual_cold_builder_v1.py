"""Authored metadata only; no actual corpus, weights, engine or learned call."""
import importlib.util
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('cold_held_builder_cpu',ROOT/'experiments/chess-queen-coach-counterfactual-v1/prepare_cold_held_protocol.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def setup(tmp_path,monkeypatch):
    outer=builder.outer
    def file(name,value):
        path=tmp_path/name;outer.save(path,value);return path
    values={'kernel_protocol':{'sha256':'kernel'},'kernel_receipt':{'sha256':'receipt'},
        'generation':{'same':'frozen'},'warm_start':{'sha256':'fixed64'}}
    inputs=file('inputs.json',{'authored':'label-free'});refs=file('references.json',{'must_not_open':True})
    science={**values,'dependencies':[],'data':{'heldout_inputs':builder.bind(inputs),'heldout_references':builder.bind(refs)}}
    parent=file('training.json',{})
    selection=file('selection.json',{'baseline':{'sha256':'checkpoint0'},'selected':{'sha256':'checkpoint48'}})
    run=file('run.json',{'status':'completed','updates_completed':192,'presentations_completed':1536,
        'partial_accumulation':0,'frozen_storage':{'identical':True}})
    qplan=file('qualification-plan.json',{'model_runtime':values,'dependencies':[],
        'expected_worker_script':'scripts/outer.py','expected_worker_arguments':['scripts/outer.py','--protocol','frozen']})
    qualification=file('qualification.json',{'status':'passed'});worker=file('worker.json',{'closed':True})
    audit=file('audit.json',{'status':'passed'});training_audit=file('training-audit.json',{'status':'passed'})
    monkeypatch.setattr(builder.trainer,'verify_protocol',lambda path:science)
    monkeypatch.setattr(builder.trainer,'verify_selection',lambda value,path:None)
    seen=[];monkeypatch.setattr(outer,'verify',lambda plan:seen.append(plan))
    arguments=[parent,selection,qplan,qualification,worker,audit,training_audit,tmp_path/'new-held-plan.json']
    return arguments,run,seen,refs


def test_complete_metadata_freezes_exact96_and_original_saved_conditions_without_truth(tmp_path,monkeypatch):
    args,run,seen,refs=setup(tmp_path,monkeypatch)
    original=builder.outer.read
    def read(path):
        if Path(path)==refs:raise AssertionError('held reference content opened')
        return original(path)
    monkeypatch.setattr(builder.outer,'read',read)
    result=builder.prepare(*args);plan=original(args[-1])
    assert result['sha256']==builder.outer.digest(args[-1])and plan['planned']==96 and plan['phase_maximum_seconds']==4500
    assert plan['conditions']=={'baseline':{'sha256':'checkpoint0'},'selected':{'sha256':'checkpoint48'}}
    assert plan['qualification_worker_arguments']==['scripts/outer.py','--protocol','frozen']
    assert len(seen)==2 and plan['heldout_references']['sha256']==builder.outer.digest(refs)


@pytest.mark.parametrize('key,value',[('status','failed'),('updates_completed',191),('presentations_completed',1535),
    ('partial_accumulation',1),('frozen_storage',{'identical':False})])
def test_partial_or_failed_learning_cannot_freeze_a_fresh_held_plan(tmp_path,monkeypatch,key,value):
    args,run,seen,refs=setup(tmp_path,monkeypatch);actual=builder.outer.read(run);actual[key]=value;builder.outer.save(run,actual)
    with pytest.raises(ValueError,match='Complete'):builder.prepare(*args)
    assert not args[-1].exists()and not seen
