"""Real strict6-case scorer with96refs; authored chess only, no models/data."""
import ast,json,copy
from datetime import datetime,timezone
from pathlib import Path
import sys
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import train_v3 as subject
import training_contract_v3 as c
import targets_v2 as target
import chess

def fixture(tmp_path):
    fen=chess.STARTING_FEN;pv=['e2e4','e7e5','g1f3'];rows=[];references={};receipts=[]
    for index in range(96):
        group='g'+str(index//3);mode=['free','selected_a','selected_b'][index%3];case='case'+str(index)
        packet={'fen':fen}
        if mode!='free':packet['selected_uci']=pv[0]
        raw,old,facts=target.target(fen,pv,selected=mode!='free')
        references[case]={'case_id':case,'group_id':group,'selected_uci':None if mode=='free'else pv[0],
            'reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts}
        if index<6:
            rows.append({'case_id':case,'group_id':group,'mode':mode,'input':packet})
            path=tmp_path/(case+'.json');path.write_text(json.dumps({'status':'completed','finish_reason':'eos','raw_text':raw}))
            receipts.append({'case_id':case,'status':'completed','response_path':str(path),'response_sha256':subject.checked.nf4.base.digest(path)})
    return rows,{'rows':receipts},references

def test_exact_six_monitoring_projection_accepts_original96_reference_pool(tmp_path):
    rows,panel,refs=fixture(tmp_path);before=copy.deepcopy(refs)
    scored=subject.score_panel(rows,panel,refs)
    assert len(scored['rows'])==6 and scored['counts']['presentations']==6
    assert scored['counts']['conditional_joint_correct']==6
    assert refs==before and len(refs)==96
    # The evaluator itself remains strict; only the caller selects its requested cases.
    with pytest.raises(ValueError,match='Full panel'):subject.scoring.panel(rows,[{}]*6,refs)


def test_missing_monitor_reference_is_failure_not_omitted_row(tmp_path):
    rows,panel,refs=fixture(tmp_path);refs.pop(rows[0]['case_id'])
    with pytest.raises(KeyError):subject.score_panel(rows,panel,refs)


def test_training_numerical_functions_remain_exact_AST():
    def functions(name):return {n.name:ast.dump(n)for n in ast.parse((HERE/name).read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef)}
    old=functions('train_v2.py');new=functions('train_v3.py')
    assert {name for name in old if old[name]!=new[name]}=={'score_panel'}
    assert old['train']==new['train']and old['checkpoint_development']==new['checkpoint_development']
    old=functions('training_contract_v2.py');new=functions('training_contract_v3.py')
    assert {name for name in old if old[name]!=new[name]}=={'verify','admit'}


def test_new_prospective_admission_and_unchanged_full_window_budget():
    plan={'admission_latest_utc':c.ADMISSION}
    c.admit(plan,datetime(2026,10,16,18,29,59,tzinfo=timezone.utc))
    with pytest.raises(RuntimeError,match='18:30'):c.admit(plan,datetime(2026,10,16,18,30,tzinfo=timezone.utc))
    assert c.CUTOFF=='2026-10-16T22:00:00+00:00'
    assert sum([660,3060,510,120,4560,285,600,1200,1200])==12195
    assert 18*3600+30*60+12195==21*3600+53*60+15
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules

def test_closed_failure_gate_requires_zero_training_and_independent_no_attempt_proof(tmp_path):
    def file(name,value):
        path=tmp_path/name;path.write_text(json.dumps(value));return {'path':str(path),'sha256':c.digest(path)}
    protocol=file('failed-plan.json',{})
    run_value={'status':'failed','updates_completed':0,'presentations_completed':0,'partial_accumulation':0,
        'inflight_training':None,'inflight_optimizer':None,'active_unknown':None}
    run=file('run.json',run_value)
    worker=file('worker.json',{'child_exited_before_lease_release':True,'owned_job_exit_verified':True})
    audit_value={'status':'passed','protocol_sha256':protocol['sha256'],'run_sha256':run['sha256'],
        'worker_sha256':worker['sha256'],'no_training_or_optimizer_attempt':True}
    audit=file('audit.json',audit_value)
    plan={'preserved_failed_training':{'protocol':protocol,'run':run,'worker':worker,'audit':audit}}
    assert c.failed_attempt_gate(plan)['updates_completed']==0
    audit_value['no_training_or_optimizer_attempt']=False;plan['preserved_failed_training']['audit']=file('audit2.json',audit_value)
    with pytest.raises(ValueError,match='no-learning'):c.failed_attempt_gate(plan)
