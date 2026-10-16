"""Pure CPU provenance/failure contracts for the runtime wrapper."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_runtime_v1 as runtime


def test_actual_adapter_is_identified_and_decoder_eval_mode_restored_for_raw_generation(monkeypatch,tmp_path):
    modes=[]
    module=lambda label:NS(eval=lambda:modes.append(label))
    model=runtime.Runtime({'generation':{'max_new_tokens':1024,'maximum_seconds':180,'seed':1}},lambda:None)
    binding=tmp_path/'software-fixture.json';binding.write_text('{}')
    model.model=NS(model=module('decoder'),encoder=module('encoder'),bridges=module('bridges'),
        protocol=binding,diagnostic_receipt=binding,inventory={'linear4bit_count':252})
    seen=[]
    def fixture(*args,**kwargs):
        seen.append(kwargs);return {'status':'completed','adapter_sha256':'native-generator','raw_text':'fixture'}
    monkeypatch.setattr(runtime.checked.nf4.base.NativeQueen,'generate',fixture)
    identity={'step':64,'sha256':'actual-adapter-bytes'}
    output=model.infer({'input':{'fen':'fixture'}},identity)
    assert modes==['decoder','encoder','bridges']and len(seen)==1
    assert seen[0]['max_new_tokens']==1024 and seen[0]['maximum_seconds']==180
    assert output['trained_adapter']==identity and output['base_generator_source_sha256']=='native-generator'
    assert output['candidate_id']=='queen-pawn-8/nf4-coach-sft-v1'and output['base_candidate_id']==runtime.checked.nf4.CANDIDATE
    assert output['quantization']['base_decoder_inventory_before_lora']['linear4bit_count']==252
    assert output['quantization']['actual_lora_parameters']==1916928


def test_first_backend_failure_latches_before_any_second_raw_call(monkeypatch,tmp_path):
    module=NS(eval=lambda:None)
    model=runtime.Runtime({'generation':{'max_new_tokens':1024,'maximum_seconds':180,'seed':1}},lambda:None)
    binding=tmp_path/'software-fixture.json';binding.write_text('{}')
    model.model=NS(model=module,encoder=module,bridges=module,
        protocol=binding,diagnostic_receipt=binding,inventory={'linear4bit_count':252});calls=[]
    def fixture(*args,**kwargs):calls.append(True);return {'status':'failed','error':'fixture backend','raw_text':'partial'}
    monkeypatch.setattr(runtime.checked.nf4.base.NativeQueen,'generate',fixture)
    assert model.infer({'input':{}},{})['raw_text']=='partial'
    with pytest.raises(RuntimeError,match='first backend failure'):model.infer({'input':{}},{})
    assert len(calls)==1
