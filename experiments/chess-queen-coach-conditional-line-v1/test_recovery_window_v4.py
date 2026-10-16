"""Prospective metadata/AST fixtures only; no data, model, resource or process."""
import ast,copy,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import training_contract_v4 as c


def put(tmp_path,name,value):
    path=tmp_path/name;path.write_text(json.dumps(value));return {'path':str(path),'sha256':c.digest(path)}


def test_admission_just_before_and_at1910_and_full_remaining_budget():
    plan={'admission_latest_utc':c.ADMISSION}
    c.admit(plan,datetime(2026,10,16,19,9,59,tzinfo=timezone.utc))
    with pytest.raises(RuntimeError,match='19:10'):c.admit(plan,datetime(2026,10,16,19,10,tzinfo=timezone.utc))
    assert c.CUTOFF=='2026-10-16T22:00:00+00:00'
    assert sum([3060,510,120,4560,900,870])==10020
    assert 19*3600+10*60+10020==21*3600+57*60


def test_all14_numerical_functions_and_all_source_save_fixtures_remain_exact_AST():
    def functions(name):return {node.name:ast.dump(node)for node in ast.parse((HERE/name).read_text()).body if isinstance(node,ast.FunctionDef)}
    assert len(functions('train_v3.py'))==14
    assert functions('train_v3.py')==functions('train_v4.py')==functions('train_v5.py')
    before=ast.parse((HERE/'train_v4.py').read_text());after=ast.parse((HERE/'train_v5.py').read_text())
    def normalized(tree):
        for node in tree.body:
            if isinstance(node,ast.Import):
                for item in node.names:
                    if item.name=='training_contract_v4':item.name='training_contract_v3'
            if isinstance(node,ast.Assign)and any(isinstance(target,ast.Name)and target.id=='PROTOCOL'for target in node.targets):
                node.value=ast.Constant('operational default path only')
        return ast.dump(tree)
    assert normalized(before)==normalized(after)
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules


def failure_fixture(tmp_path):
    old={key:{'authored':key}for key in (*c.SAME,'data','corpus_manifest','counterfactual_runtime','target_export_protocol','conditional_update_gate')}
    old.update(expected_worker_script='authored/train_v3.py',expected_worker_arguments=['AUTHORED-ABS/train_v3.py','train'])
    old['owned_worker_source']={'sha256':'worker-source'}
    protocol=put(tmp_path,'protocol.json',old)
    primary=put(tmp_path,'failure.json',{'status':'failed','updates_completed':167,'presentations_completed':1336,
        'partial_accumulation':0,'active_unknown':None})
    stale_value={'status':'attempt_started','updates_completed':166,'presentations_completed':1336,
        'partial_accumulation':8,'inflight_optimizer':{'step':167,'status':'call_started'}}
    stale=put(tmp_path,'run.json',stale_value)
    worker=put(tmp_path,'worker.json',{'source_sha256':'worker-source','status':'failed','exit_code':1,
        'child_exited_before_lease_release':True,'owned_job_exit_verified':True,
        'script':old['expected_worker_script'],'arguments_sha256':hashlib.sha256(json.dumps(old['expected_worker_arguments']).encode()).hexdigest(),
        'ownership':{'closure':{'child_stable_handle_exited':True,'actual_job_handle_closed':True,'complete_job_pids':[]}}})
    audit_value={'status':'passed','experiment_status':'failed','protocol_sha256':protocol['sha256'],
        'failure_sha256':primary['sha256'],'primary_result_sha256':primary['sha256'],
        'stale_run_sha256':stale['sha256'],'worker_sha256':worker['sha256'],
        'counts':{'TRAIN_updates_completed':167,'TRAIN_backwards_completed':1336,'TRAIN_not_run':200,
            'TRAIN_active_unknown':0,'partial_accumulation':0,'optimizer_completed':167},
        'no_terminal_candidate':{key:False for key in ['checkpoint167_saved','checkpoint192_saved','selection_saved','final_frozen_storage_receipt_present']},
        'stale_vs_failure':{'run_json':stale_value}}
    audit=put(tmp_path,'audit.json',audit_value)
    plan={**copy.deepcopy(old),'preserved_write_failure':{'protocol':protocol,'failure':primary,'stale_run':stale,'worker':worker,'audit':audit}}
    return plan,audit_value


def test_audited_primary167_is_distinct_from_stale_run_and_not_resumed(tmp_path):
    plan,audit=failure_fixture(tmp_path)
    assert c.write_failure_gate(plan)['updates_completed']==167
    plan['preserved_write_failure']['failure']=plan['preserved_write_failure']['stale_run']
    with pytest.raises(ValueError,match='primary/stale'):c.write_failure_gate(plan)


@pytest.mark.parametrize('fault',['wrong_failure','wrong_stale','saved_terminal','live_job','changed_training'])
def test_failed_partial_attempt_never_becomes_candidate_or_changes_restart_science(tmp_path,fault):
    plan,audit=failure_fixture(tmp_path)
    if fault=='wrong_failure':audit['failure_sha256']='other'
    elif fault=='wrong_stale':audit['stale_run_sha256']='other'
    elif fault=='saved_terminal':audit['no_terminal_candidate']['selection_saved']=True
    elif fault=='changed_training':plan['training']={'updates':25,'resume':167}
    else:
        worker=c.read(c.bound(plan['preserved_write_failure']['worker']))
        worker['ownership']['closure']['complete_job_pids']=[123]
        plan['preserved_write_failure']['worker']=put(tmp_path,'worker2.json',worker)
        audit['worker_sha256']=plan['preserved_write_failure']['worker']['sha256']
    plan['preserved_write_failure']['audit']=put(tmp_path,'audit2.json',audit)
    with pytest.raises(ValueError):c.write_failure_gate(plan)


def test_source_reuse_requires_actual_test_receipt_and_exact_all14_functions(tmp_path):
    binding=lambda path:{'path':str(path),'sha256':c.digest(path)}
    tested=[binding(HERE/name)for name in ['bounded_atomic_save_v1.py','test_atomic_save_v1.py','train_v4.py']]
    result=put(tmp_path,'tests.json',{'status':'completed','exit_code':0,'source_unchanged':True,'source_bindings':tested})
    audit=put(tmp_path,'tests-audit.json',{'status':'passed','source_software_readiness_passed':True,
        'actual_test_receipt':result,'retained_output':{'passed':15}})
    plan={'implementation_sha256':c.digest(HERE/'train_v5.py'),'prior_update_qualification_reuse':{
        'previous_training_source':binding(HERE/'train_v3.py'),'current_training_source':binding(HERE/'train_v5.py'),
        'tested_entrypoint':binding(HERE/'train_v4.py'),'atomic_helper':tested[0],'atomic_test_source':tested[1],
        'atomic_test_result':result,'atomic_test_audit':audit}}
    assert c.reuse_gate(plan)
    changed=tmp_path/'changed.py';changed.write_text((HERE/'train_v5.py').read_text().replace('for step in range(1,193):','for step in range(1,26):'))
    plan['prior_update_qualification_reuse']['current_training_source']=binding(changed)
    plan['implementation_sha256']=c.digest(changed)
    with pytest.raises(ValueError,match='All14'):c.reuse_gate(plan)
