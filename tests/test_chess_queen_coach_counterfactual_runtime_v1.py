"""Warm-start/identity contracts without pretrained imports or GPU calls."""
import ast
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_runtime_v1 as subject


def test_inherits_exact_qualified_loss_cleanup_and_strict_adapter_loader():
    assert subject.Runtime.loss is subject.QualifiedRuntime.loss
    assert subject.Runtime.release_inactive is subject.QualifiedRuntime.release_inactive
    assert subject.Runtime.load_adapter is subject.QualifiedRuntime.load_adapter
    assert subject.Runtime.verify_frozen is subject.QualifiedRuntime.verify_frozen


def test_warm_start_rejects_other_step_model_parameter_or_bytes(monkeypatch):
    identity={'step':64,'parameter_count':1916928,'sha256':'73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e',
        'candidate_id':'queen-pawn-8/nf4-coach-sft-v2','path':'authored.pt'}
    monkeypatch.setattr(subject.checked.nf4.base,'digest',lambda path:identity['sha256'])
    subject.validate_start(identity)
    for key,value in[('step',0),('parameter_count',1),('candidate_id','publisher-base')]:
        with pytest.raises(ValueError,match='selected64'):subject.validate_start({**identity,key:value})
    monkeypatch.setattr(subject.checked.nf4.base,'digest',lambda path:'changed')
    with pytest.raises(ValueError,match='bytes'):subject.validate_start(identity)


def test_actual_warm_load_follows_qualified_setup_and_is_idempotent(monkeypatch):
    calls=[];runtime=subject.Runtime({'warm_start':{'fixture':True}},lambda:None)
    monkeypatch.setattr(subject,'validate_start',lambda identity:calls.append('validate'))
    def load(self):calls.append('qualified_setup');self.model=object();self.torch=object();self.parameters=[]
    monkeypatch.setattr(subject.QualifiedRuntime,'load',load)
    monkeypatch.setattr(subject.QualifiedRuntime,'load_adapter',lambda self,identity:calls.append(('strict_reload',identity)))
    monkeypatch.setattr(subject.checked,'streamed_hash',lambda *args:'effective-trained-weights')
    runtime.load();runtime.load()
    assert calls==['validate','qualified_setup',('strict_reload',{'fixture':True})]
    assert runtime.warm_start_effective_hash=='effective-trained-weights'


def test_new_candidate_never_returns_parent_runtime_identity(monkeypatch):
    runtime=subject.Runtime({'warm_start':{'step':64}},lambda:None)
    monkeypatch.setattr(subject.QualifiedRuntime,'infer',lambda *args:{'adapter_sha256':'qualified-parent','candidate_id':'parent'})
    monkeypatch.setattr(subject.checked.nf4.base,'digest',lambda path:'new-source')
    raw=runtime.infer({'fixture':True},{'sha256':'adapted'})
    assert raw['candidate_id']==subject.CANDIDATE and raw['qualified_runtime_source_sha256']=='qualified-parent'
    assert raw['adapter_sha256']=='new-source'and raw['warm_start']=={'step':64}
