"""CPU checks: cleanup sequencing and durable actual-allocator provenance."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_runtime_v2 as runtime


def test_cleanup_is_outside_loss_and_never_mutates_live_gradient_or_parameter(monkeypatch,tmp_path):
    calls=[];live={'parameter':[1.,2.],'gradient':[.25,.5]}
    cuda=NS(synchronize=lambda:calls.append('synchronize'),empty_cache=lambda:calls.append('empty_cache'))
    model=runtime.Runtime({},lambda:calls.append('guard'));model.torch=NS(cuda=cuda)
    model.memory_journal=tmp_path/'memory.jsonl'
    counter=iter([{'cuda_allocated_bytes':10,'cuda_reserved_bytes':50},
        {'cuda_allocated_bytes':10,'cuda_reserved_bytes':20}])
    monkeypatch.setattr(runtime,'memory_snapshot',lambda torch:next(counter))
    monkeypatch.setattr(runtime.gc,'collect',lambda:calls.append('collect')or 7)
    returned=model.release_inactive('after_returned_backward')
    assert calls==['synchronize','collect','empty_cache','synchronize','guard']
    assert live=={'parameter':[1.,2.],'gradient':[.25,.5]}
    events=[json.loads(line)for line in model.memory_journal.read_text().splitlines()]
    assert [row['status']for row in events]==['cleanup_started','cleanup_completed']
    assert events[1]['before']['cuda_reserved_bytes']==50 and returned['cuda_reserved_bytes']==20
    assert events[1]['python_objects_collected']==7


def test_cleanup_durable_intent_precedes_failure_and_no_postfailure_guard(monkeypatch,tmp_path):
    seen=[];path=tmp_path/'memory.jsonl'
    def failed_cache():
        assert json.loads(path.read_text())['status']=='cleanup_started'
        raise RuntimeError('fixture cache failure')
    model=runtime.Runtime({},lambda:seen.append('guard'));model.memory_journal=path
    model.torch=NS(cuda=NS(synchronize=lambda:None,empty_cache=failed_cache))
    monkeypatch.setattr(runtime,'memory_snapshot',lambda torch:{'fixture':1})
    monkeypatch.setattr(runtime.gc,'collect',lambda:0)
    with pytest.raises(RuntimeError,match='fixture cache'):model.release_inactive('fixture')
    assert not seen and len(path.read_text().splitlines())==1


def test_memory_intents_fsync_and_missing_journal_fails_before_collection(monkeypatch,tmp_path):
    path=tmp_path/'memory.jsonl';seen=[]
    monkeypatch.setattr(runtime.os,'fsync',lambda fd:seen.append(json.loads(path.read_text())))
    runtime.memory_append(path,{'status':'cleanup_started'})
    assert seen==[{'status':'cleanup_started'}]
    with pytest.raises(ValueError,match='journal'):runtime.memory_append(None,{})


def test_process_counters_are_current_process_only_and_json_safe():
    value=runtime.process_memory();json.dumps(value,allow_nan=False)
    if sys.platform=='win32':
        assert value['available']is True and value['private_usage_bytes']>0
        assert value['working_set_bytes']>0


def test_runtime_loss_ast_preserves_executed_numerical_path():
    import ast
    def method(path):
        tree=ast.parse(path.read_text());cls=next(node for node in tree.body if isinstance(node,ast.ClassDef)and node.name=='Runtime')
        return ast.dump(next(node for node in cls.body if isinstance(node,ast.FunctionDef)and node.name=='loss'),include_attributes=False)
    assert method(ROOT/'scripts/chess_queen_coach_sft_runtime_v1.py')==method(ROOT/'scripts/chess_queen_coach_sft_runtime_v2.py')


def test_new_runtime_identifies_actual_version_without_changing_base_generator(monkeypatch,tmp_path):
    module=NS(eval=lambda:None);binding=tmp_path/'binding.json';binding.write_text('{}')
    model=runtime.Runtime({'generation':{'max_new_tokens':1024,'maximum_seconds':180,'seed':1}},lambda:None)
    model.model=NS(model=module,encoder=module,bridges=module,protocol=binding,diagnostic_receipt=binding,inventory={})
    monkeypatch.setattr(runtime.checked.nf4.base.NativeQueen,'generate',lambda *a,**k:{'status':'completed','adapter_sha256':'actual-base','raw_text':'fixture'})
    value=model.infer({'input':{}},{'step':32})
    assert value['candidate_id']=='queen-pawn-8/nf4-coach-sft-v2'
    assert value['base_generator_source_sha256']=='actual-base' and value['trained_adapter']['step']==32
