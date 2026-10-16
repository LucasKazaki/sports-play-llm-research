"""Prospective admission-only amendment; authored source/time fixtures."""
import ast
from datetime import datetime,timezone
from pathlib import Path
import sys
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import training_contract_v2 as c
import prepare_training_v4 as builder

def functions(name):return {node.name:ast.dump(node)for node in ast.parse((HERE/name).read_text(encoding='utf-8-sig')).body if isinstance(node,ast.FunctionDef)}

def test_qualifier_and_training_all_functions_remain_AST_identical():
    assert functions('train_v2.py')==functions('train.py')
    assert functions('qualify_conditional_v2.py')==functions('qualify_conditional.py')
    old=functions('training_contract.py');new=functions('training_contract_v2.py')
    assert {key for key in old if old[key]!=new[key]}=={'verify','admit'}
    assert c.CUTOFF=='2026-10-16T22:00:00+00:00'

@pytest.mark.parametrize('phase',['qualification','training'])
def test_each_new_phase_admits_before_and_rejects_at18_15(phase):
    plan={'phase':phase,'admission_latest_utc':c.ADMISSION,'cutoff_utc':c.CUTOFF}
    c.admit(plan,datetime(2026,10,16,18,14,59,tzinfo=timezone.utc))
    with pytest.raises(RuntimeError,match='18:15'):c.admit(plan,datetime(2026,10,16,18,15,tzinfo=timezone.utc))
    with pytest.raises(RuntimeError):c.admit(plan,datetime(2026,10,16,22,tzinfo=timezone.utc))

def test_full_remaining_budget_is_within_unchanged22_cutoff():
    seconds=sum([660,3060,510,120,4560,285,600,1200,1200])
    assert seconds==12195 and 18*3600+15*60+seconds<22*3600
    assert builder.c is c
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules

def test_science_enforces_exact22_cutoff_without_changing_phase_caps():
    import copy
    parent={key:{'authored':key}for key in c.SAME};parent['training']={'updates':192,'gradient_accumulation':8}
    plan=copy.deepcopy(parent);plan.update(phase_maximum_seconds={'training':3000,'heldout':4500},
        cutoff_utc=c.CUTOFF,admission_latest_utc=c.ADMISSION,maximum_seconds=3000,worker_maximum_seconds=3030,external_maximum_seconds=3060,
        selection_method=builder.SELECTION,fixed_treatment_step=192,comparison_control={'step':192,'candidate_id':'queen-pawn-8/nf4-coach-counterfactual-v1'})
    c.science(plan,parent)
    plan['cutoff_utc']='2026-10-16T22:00:01+00:00'
    with pytest.raises(ValueError,match='Operating bounds'):c.science(plan,parent)
