"""Temporary metadata and injected worker outcomes; no real process/model calls."""
from pathlib import Path
from types import SimpleNamespace
import contextlib,copy,hashlib,importlib.util,json,sys
import pytest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('flat_cold_authored',HERE/'run_once.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def row(i=0,mode='free',group=None):
    packet={'fen':'AUTHORED-FEN-'+str(group if group is not None else i)}
    if mode!='free':packet['selected_uci']='e2e4' if mode=='selected_a' else 'd2d4'
    return {'case_id':str(i),'group_id':str(group if group is not None else i),'mode':mode,'input':packet}

def write_rows(path,rows):
    path.write_text(''.join(json.dumps(value)+'\n' for value in rows),encoding='utf-8')
    return c.bind(path)

def fixture(tmp_path,monkeypatch,mode='qualification'):
    monkeypatch.setattr(c,'TASK',tmp_path);monkeypatch.setattr(c,'ROOT',tmp_path/'repo')
    cp=tmp_path/'work/daytime/checkpoint.json';cp.parent.mkdir(parents=True);c.write(cp,{'active_gpu_job':None},create=True)
    rows=[row(0),row(1,'selected_a')] if mode=='qualification' else [row(g*3+j,m,g)
        for g in range(16) for j,m in enumerate(('free','selected_a','selected_b'))]
    inputs=write_rows(tmp_path/'inputs.jsonl',rows)
    identities={'baseline':{'sha256':'authored64'},'selected':{'sha256':'authored192'}}
    plan={'mode':mode,'input_rows':inputs,'conditions':identities,'phase_maximum_seconds':450 if mode=='qualification' else 4500,
        'actual_out':str(tmp_path/'out'),
        'assignments':[{'case_id':str(i),'condition':name} for i,name in enumerate(('baseline','selected'))],
        'cutoff_utc':'2099-01-01T00:00:00+00:00','dependencies':[],
        'child_script':{'path':'scripts/authored.py'},'owned_worker_source':{'path':str(tmp_path/'worker.py')}}
    (tmp_path/'worker.py').write_text('# authored pinned worker\n');plan['owned_worker_source']=c.bind(tmp_path/'worker.py')
    protocol=tmp_path/'protocol.json';c.write(protocol,plan,create=True)
    monkeypatch.setattr(c,'verify',lambda *args:None)
    monkeypatch.setattr(c,'FileLock',lambda *args,**kwargs:contextlib.nullcontext())
    monkeypatch.setattr(c,'check_case',lambda *args:{'raw_status':'completed','raw_finish_reason':'eos'})
    calls=[];active=[]
    def launcher(command,folder,cancel,deadline,cutoff):
        assert not active;active.append(1);calls.append(command);active.pop()
        return {'returncode':0,'elapsed_seconds':.01}
    sample=lambda:{'commit_total_bytes':100}
    return plan,protocol,tmp_path/'out',cp,rows,calls,launcher,sample

def execute(values,**kwargs):
    plan,protocol,out,cp,rows,calls,launcher,sampler=values
    return c.run(plan,protocol,out,{}, {},launcher=kwargs.get('launcher',launcher),sampler=sampler,
        floor_check=lambda *args:None,scorer=kwargs.get('scorer',lambda *args:None))

def test_two_explicit_adapters_no_overlap_and_no_labels(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch);result=execute(values)
    assert result['status']=='passed' and result['completed_children']==2 and len(values[5])==2
    assert [item['identity']['sha256'] for item in result['rows']]==['authored64','authored192']
    assert not result['labels_opened'] and not result['outer_torch_imported']
    assert c.read(values[3])['active_gpu_job']['out']==str(values[2])  # Root actual audit owns clearing.

@pytest.mark.parametrize('failure_at',[0,1])
def test_first_failure_stops_with_all_two_rows_and_no_fabricated_acceptance(tmp_path,monkeypatch,failure_at):
    values=fixture(tmp_path,monkeypatch);calls=[];normal=values[6]
    def fail(*args):
        index=len(calls);calls.append(index)
        if index==failure_at:raise OSError('authored worker failure')
        return normal(*args)
    result=execute(values,launcher=fail)
    assert result['status']=='failed' and len(calls)==failure_at+1 and len(result['rows'])==2
    assert result['rows'][failure_at]['status']=='active_unknown'
    assert all(item['status']=='not_run' for item in result['rows'][failure_at+1:])
    assert not result['labels_opened']

def test_held96_first_failure_never_opens_truth_or_shrinks_panel(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch,'heldout');scores=[]
    def fail(*args):raise RuntimeError('authored first launch failure')
    result=execute(values,launcher=fail,scorer=lambda *args:scores.append(1))
    assert result['status']=='failed' and result['planned']==len(result['rows'])==96
    assert result['rows'][0]['status']=='active_unknown' and sum(item['status']=='not_run' for item in result['rows'])==95
    assert not scores and not result['labels_opened']

def test_truth_gate_only_after_both_closed48_panels(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch,'heldout');scores=[]
    def score(plan,rows,out):
        closed=c.read(out/'closed.json')
        assert closed['completed_children']==96 and all(item['status']=='completed' for item in closed['rows'])
        assert len(rows)==48 and all(c.read(out/(name+'.json'))['status']=='completed' for name in ('baseline','selected'))
        scores.append(1)
    result=execute(values,scorer=score)
    assert result['status']=='passed' and len(values[5])==96 and scores==[1] and result['labels_opened']

def test_acceptance_write_failure_preserves_pending_raw_and_stops(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch);write=c.write
    def fail(path,value,create=False):
        if Path(path).name=='accepted.json':raise OSError('authored acceptance fsync')
        return write(path,value,create)
    monkeypatch.setattr(c,'write',fail);result=execute(values)
    assert result['status']=='failed' and len(values[5])==1 and result['completed_children']==0
    assert [item['status'] for item in result['rows']]==['active_unknown','not_run']

def test_setup_failure_retains_full96_without_model_or_score(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch,'heldout')
    monkeypatch.setattr(c,'verify',lambda *args:(_ for _ in ()).throw(ValueError('authored source mismatch')))
    result=execute(values)
    assert result['status']=='failed' and len(result['rows'])==96 and not values[5]
    assert all(item['status']=='not_run' for item in result['rows']) and c.read(values[3])['active_gpu_job'] is None

def test_different_output_cannot_replay_a_prospectively_bound_plan(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch);plan,protocol,out,*_=values
    with pytest.raises(ValueError,match='prospective output'):
        c.run(plan,protocol,tmp_path/'other',{}, {})
    assert not (tmp_path/'other').exists() and not out.exists() and not values[5]

def test_mode_group_input_denominators_reject_before_dispatch(tmp_path,monkeypatch):
    values=fixture(tmp_path,monkeypatch,'heldout');plan,_,_,_,rows,*_=values
    rows[1]['mode']='free';plan['input_rows']=write_rows(tmp_path/'changed.jsonl',rows)
    with pytest.raises(ValueError,match='Mode/input'):c.tasks(plan)
    rows[1]['mode']='selected_a';rows[1]['group_id']='another';plan['input_rows']=write_rows(tmp_path/'changed.jsonl',rows)
    with pytest.raises(ValueError,match='Sixteen'):c.tasks(plan)

def case_fixture(tmp_path):
    protocol=tmp_path/'protocol.json';c.write(protocol,{'authored':True},create=True)
    folder=tmp_path/'case';(folder/'child').mkdir(parents=True)
    r=row();identity={'sha256':'authored64'};args=['scripts/authored.py','--protocol',str(protocol)]
    raw={'status':'completed','input':{'history':[],**r['input']},'trained_adapter':identity,'candidate_id':'authored',
        'settings':{**c.GENERATION,'use_kv_cache':False},'no_forward_input_audit':{'passed':True,
            'engine_evaluation_or_pv_input':False,'selected_move_supplied':False,'allowed_fields':['fen','history']},
        'parsed':{'fallback_used':False,'engine_interventions':0,'rule_replacements':0}}
    c.write(folder/'child/raw.json',raw,create=True)
    child={'status':'passed','pid':30,'parent_pid':29,'source_sha256':c.CHILD_SHA,'protocol_sha256':c.digest(protocol),
        'case_id':r['case_id'],'identity':identity,'requested_input_sha256':c.packet_sha(r['input']),
        'generation_requests_started':1,'in_owned_ancestor_job':True,'frozen_storage':{'identical':True},
        'raw_saved_before_postprocessing':True,'raw_sha256':c.digest(folder/'child/raw.json')}
    worker={'schema':'chess.owned-worker.v2','source_sha256':c.WORKER_SHA,'launch_profile':'direct-base-owned-worker-v2',
        'status':'completed','exit_code':0,'child_exited_before_lease_release':True,'owned_member_before_go':True,
        'owned_job_exit_verified':True,'child_pid':30,'maximum_seconds_after_GO':240,'script':args[0],
        'arguments_sha256':hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        'ownership':{'before_go':{'creator_identity':{'pid':29,'created':100,'image':'base.exe'},
            'child_identity':{'pid':30,'created':200,'image':'base.exe'},'popen_handle_pid_matches':True,
            'member_of_explicit_creator_job':True,'creator_member_of_explicit_child_job':False,
            'job_handle_passed_to_child':False,'complete_job_pids':[30]},'after_go_complete_job_pids':[30],
            'closure':{'child_stable_handle_exited':True,'actual_job_handle_closed':True,'complete_job_pids':[]}}}
    plan={'owned_worker_source':{'sha256':c.WORKER_SHA},'interpreters':{'delegate':'base.exe'},'raw_provenance':{'candidate_id':'authored'}}
    c.write(folder/'child/closed.json',child,create=True);c.write(folder/'worker.json',worker,create=True)
    return plan,protocol,r,identity,folder,args,child,worker,raw

def test_exact_actual_job_child_raw_and_current_input_bindings(tmp_path):
    plan,protocol,r,identity,folder,args,*_=case_fixture(tmp_path)
    assert c.check_case(plan,protocol,r,identity,folder,args,{'returncode':0})['raw_status']=='completed'

@pytest.mark.parametrize('fault',['input','child_pid','parent','adapter','frozen','source','arguments','live_job','raw_bytes','future_input'])
def test_child_or_worker_mutations_never_become_accepted(tmp_path,fault):
    plan,protocol,r,identity,folder,args,child,worker,raw=case_fixture(tmp_path)
    if fault=='input':child['requested_input_sha256']='changed'
    elif fault=='child_pid':child['pid']=31
    elif fault=='parent':child['parent_pid']=28
    elif fault=='adapter':child['identity']={'sha256':'different'}
    elif fault=='frozen':child['frozen_storage']['identical']=False
    elif fault=='source':child['source_sha256']='changed'
    elif fault=='arguments':worker['arguments_sha256']='changed'
    elif fault=='live_job':worker['ownership']['closure']['complete_job_pids']=[31]
    elif fault=='raw_bytes':raw['unexpected']='mutated'
    else:
        raw['input']['pv']=['e2e4'];child['raw_sha256']=None
    c.write(folder/'child/raw.json',raw)
    if fault=='future_input':child['raw_sha256']=c.digest(folder/'child/raw.json')
    c.write(folder/'child/closed.json',child);c.write(folder/'worker.json',worker)
    with pytest.raises(ValueError):c.check_case(plan,protocol,r,identity,folder,args,{'returncode':0})

def test_supervision_no_handle_never_borrows_pid_and_only_retained_object_killed():
    assert c.supervise(None)=={'retained_wrapper_present':False,'unseen_tree_closure_inferred':False,
        'cleanup_errors':[],'known_wrapper_exit':False}
    class Process:
        pid=77;returncode=None;terminated=0
        def poll(self):return self.returncode
        def terminate(self):self.terminated+=1;self.returncode=2
        def wait(self,timeout):return self.returncode
    p=Process();receipt=c.supervise(p)
    assert p.terminated==1 and receipt['known_wrapper_exit'] and receipt['retained_wrapper_pid']==77
    assert not receipt['unseen_tree_closure_inferred']

def test_post_Popen_journal_failure_signals_child_cancel_before_retained_wrapper_cleanup(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    folder=tmp_path/'case';folder.mkdir();cancel=tmp_path/'CANCEL';write=c.write
    class Process:
        pid=77;returncode=None;terminated=0
        def poll(self):return self.returncode
        def terminate(self):
            assert cancel.exists();self.terminated+=1;self.returncode=2
        def wait(self,timeout):return self.returncode
    p=Process();monkeypatch.setattr(c.subprocess,'Popen',lambda *args,**kwargs:p)
    def fail(path,value,create=False):
        if Path(path).name=='launch-started.json':raise OSError('authored post-Popen fsync')
        return write(path,value,create)
    monkeypatch.setattr(c,'write',fail)
    with pytest.raises(OSError,match='post-Popen'):
        c.launch(['authored-only'],folder,cancel,float('inf'),datetime(2099,1,1,tzinfo=timezone.utc))
    actual=c.read(folder/'launch-closed.json')
    assert cancel.exists() and p.terminated==1 and actual['known_wrapper_exit']
    assert 'post-Popen' in actual['primary_error'] and not actual['unseen_tree_closure_inferred']

def test_source_raw_provenance_numerical_function_matches_prior_AST():
    import ast
    def function(path):
        return next(ast.dump(node) for node in ast.parse(path.read_text()).body
            if isinstance(node,ast.FunctionDef) and node.name=='raw_provenance')
    assert function(HERE/'run_once.py')==function(HERE.parent/'chess-queen-coach-daytime-v1/cold_eval_v10.py')
    assert 'torch' not in sys.modules

def test_builder_pins_same_two_spent_packets_and_explicit_64_192_assignment(tmp_path,monkeypatch):
    sys.path.insert(0,str(HERE))
    spec=importlib.util.spec_from_file_location('flat_builder_authored',HERE/'build_protocol.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    repo=tmp_path/'repo';repo.mkdir();monkeypatch.setattr(b,'ROOT',repo)
    inputs=write_rows(tmp_path/'spent.jsonl',[row(0),row(1,'selected_a')])
    monkeypatch.setattr(b.core,'read',lambda path:{'input_rows':inputs})
    monkeypatch.setattr(b,'base',lambda *args:{'conditions':{'baseline':{'sha':'64'},'selected':{'sha':'192'}}})
    out=tmp_path/'plan.json';actual=repo/'data/private/chess-queen-coach-flat-v1/qualification-1'
    b.prepare_qualification(out,actual)
    plan=json.loads(out.read_text())
    assert plan['input_rows']==inputs
    assert plan['assignments']==[{'case_id':'0','condition':'baseline'},{'case_id':'1','condition':'selected'}]
    assert not actual.exists()  # Metadata preparation neither launches nor precreates raw phase.
    with pytest.raises(ValueError,match='Create-only'):b.prepare_qualification(out,actual)

@pytest.mark.parametrize('fault',[None,'changed_runtime','changed_condition','larger_budget','missing_root_read'])
def test_prospective_gate_rejects_changed_science_or_missing_read(tmp_path,monkeypatch,fault):
    old={'model_runtime':{'generation':dict(c.GENERATION)},'raw_provenance':{},
        'conditions':{'baseline':{'sha':'64'},'selected':{'sha':'192'}}}
    old_path=tmp_path/'old.json';c.write(old_path,old,create=True)
    plan={**copy.deepcopy(old),'schema':'chess.flat-cold-phase.v1','implementation_sha256':c.digest(c.__file__),
        'child_implementation_sha256':c.CHILD_SHA,'child_script':{'path':str(c.ROOT/'scripts/chess_queen_coach_counterfactual_cold_child_v1.py')},
        'owned_worker_source':{'sha256':c.WORKER_SHA},'dependencies':[],'frozen_science_protocol':{'path':str(old_path)},
        'mode':'qualification','phase_maximum_seconds':450,'child_maximum_seconds':210,'worker_seconds':240,
        'per_request_external_seconds':270,'external_maximum_seconds':510,'cutoff_utc':'2026-10-16T22:00:00+00:00',
        'admission_latest_utc':'2099-01-01T00:00:00+00:00'}
    if fault=='changed_runtime':plan['model_runtime']['generation']['seed']=99
    elif fault=='changed_condition':plan['conditions']['selected']['sha']='reselected'
    elif fault=='larger_budget':plan['phase_maximum_seconds']=451
    protocol=tmp_path/'plan.json';c.write(protocol,plan,create=True)
    review={'status':'passed','model_dispatch_permitted':True,'protocol_sha256':c.digest(protocol)}
    root_read={'status':'complete_root_source_and_plan_read','protocol':{'sha256':c.digest(protocol)}}
    if fault=='missing_root_read':root_read={}
    monkeypatch.setattr(c,'bound',lambda item:Path(item['path']))
    monkeypatch.setattr(c.launch_contract,'environment',lambda *args:None)
    if fault:
        with pytest.raises(ValueError):c.verify(plan,protocol,review,root_read)
    else:c.verify(plan,protocol,review,root_read)
