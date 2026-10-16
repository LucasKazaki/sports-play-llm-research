import copy
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from chess_queen_coach_counterfactual_contract_v1 import verify_preflight


def fixture():
    return {'status':'passed','cuda_initialized':False,'model_weights_loaded':False,'learned_forward_calls':0,
        'source_sha256':'source','manifest_sha256':'newmanifest','splits':{name:{'records':records,'groups':groups,
            'minimum_total_tokens':100,'maximum_total_tokens':150,'total_supervised_tokens':1000,
            'exact_integer_prefix_mask_eos_no_truncation':True}for name,records,groups in[('train',1536,512),('development',96,32)]}}


def test_new_actual_preflight_binding_complete_quotas_context_and_cpu_proof():
    plan={'cpu_preflight_source':{'sha256':'source'},'cpu_preflight':{'receipt':True},'corpus_manifest':{'sha256':'newmanifest'}}
    seen=[]
    def bound(value):seen.append(value);return value
    assert verify_preflight(plan,bound,lambda path:fixture())['status']=='passed'and len(seen)==2
    for key,value in[('cuda_initialized',True),('model_weights_loaded',True),('learned_forward_calls',1),
        ('manifest_sha256','oldmanifest'),('source_sha256','oldsource')]:
        actual=fixture();actual[key]=value
        with pytest.raises(ValueError,match='fresh'):verify_preflight(plan,bound,lambda path:actual)
    for key,value in[('records',1535),('groups',511),('maximum_total_tokens',513),
        ('exact_integer_prefix_mask_eos_no_truncation',False)]:
        actual=fixture();actual['splits']['train'][key]=value
        with pytest.raises(ValueError,match='quotas'):verify_preflight(plan,bound,lambda path:actual)
