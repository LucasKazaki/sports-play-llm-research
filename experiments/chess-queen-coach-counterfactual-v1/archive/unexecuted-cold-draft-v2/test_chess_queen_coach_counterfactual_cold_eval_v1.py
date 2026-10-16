"""Fake serial children and host samples; no OS process, model, engine or Torch."""
import json
import os
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_cold_eval_v1 as subject

GENERATION={'max_new_tokens':1024,'maximum_seconds':180,'temperature':0,'seed':20260823,
    'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'}


def setup(tmp_path,mode='qualification'):
    rows=[]
    for index in range(2 if mode=='qualification'else 48):
        rows.append({'case_id':str(index),'group_id':str(index//3),'mode':'free'if index%3==0 else'selected_a'if index%3==1 else'selected_b',
            'input':{'fen':'authored six field FEN for fake child',**({'selected_uci':'e2e4'}if index%3 else{})}})
    inputs=tmp_path/'inputs.jsonl';inputs.write_text(''.join(json.dumps(row)+'\n'for row in rows))
    child=tmp_path/'authored-child.py';child.write_text('# not executable by fixture\n')
    identity={'path':'authored.pt','sha256':'fixed64'}
    conditions={'software':identity}if mode=='qualification'else{'baseline':identity,'selected':{'path':'new.pt','sha256':'new'}}
    plan={'mode':mode,'implementation_sha256':subject.digest(Path(subject.__file__)),'dependencies':[],
        'child_script':{'path':str(child),'sha256':subject.digest(child)},'child_implementation_sha256':subject.digest(child),
        'input_rows':{'path':str(inputs),'sha256':subject.digest(inputs)},'conditions':conditions,
        'model_runtime':{'generation':GENERATION,'warm_start':identity},'child_maximum_seconds':210,'phase_maximum_seconds':450 if mode=='qualification'else 4500,
        'cutoff_utc':'2099-01-01T00:00:00+00:00','admission_latest_utc':'2099-01-01T00:00:00+00:00',
        'raw_provenance':{'model_revision':'pinned-publisher','adapter_sha256':'runtime-source','base_nf4_source_sha256':'nf4-source'}}
    if mode=='heldout':
        plan['expected_worker_arguments']=['--protocol','frozen-qualification.json','--out','fixed-output']
        qplan=tmp_path/'qualification-protocol.json';subject.save(qplan,plan)
        receipt=tmp_path/'qualification.json';subject.save(receipt,{'status':'passed','planned':2,'completed_children':2,
            'outer_torch_imported':False,'all_children_closed':True,'protocol_sha256':subject.digest(qplan)})
        plan['qualification_worker_arguments']=plan['expected_worker_arguments']
        plan['qualification_worker_script']='scripts/outer.py'
        worker=tmp_path/'qualification-worker.json';subject.save(worker,{'status':'completed','exit_code':0,'child_exited_before_lease_release':True,
            'script':'scripts/outer.py','arguments_sha256':__import__('hashlib').sha256(json.dumps(plan['qualification_worker_arguments']).encode()).hexdigest()})
        for key,path in [('qualification_protocol',qplan),('successful_qualification',receipt),('closed_qualification_worker',worker)]:
            plan[key]={'path':str(path),'sha256':subject.digest(path)}
        audit=tmp_path/'qualification-audit.json';subject.save(audit,{'status':'passed','protocol_sha256':subject.digest(qplan),
            'qualification_sha256':subject.digest(receipt),'worker_sha256':subject.digest(worker)})
        plan['qualification_audit']={'path':str(audit),'sha256':subject.digest(audit)}
    protocol=tmp_path/'protocol.json';subject.save(protocol,plan)
    return plan,protocol,rows


def fake_runner(plan,protocol,calls,fail=None):
    def runner(command,folder,maximum,parent_cancel,cutoff,deadline):
        assert maximum==210 and 'gpu_worker'not in ' '.join(command)
        parent=folder.parent
        for condition in plan['conditions']:
            assert len(subject.read(parent/(condition+'.json'))['rows'])==(2 if plan['mode']=='qualification'else 48)
        request=subject.read(folder/'request.json');calls.append(request['row']['case_id']);(folder/'child').mkdir()
        if fail=='timeout':raise RuntimeError('authored child timeout')
        raw={'status':'completed','finish_reason':'eos','raw_text':'authored retained bytes','input':{'history':[],**request['row']['input']},
            'trained_adapter':request['identity'],'settings':{**GENERATION,'use_kv_cache':False},
            'model_revision':'pinned-publisher','adapter_sha256':'runtime-source','base_nf4_source_sha256':'nf4-source',
            'no_forward_input_audit':{'passed':True,'engine_evaluation_or_pv_input':False,
                'selected_move_supplied':'selected_uci'in request['row']['input'],'allowed_fields':sorted({'history',*request['row']['input']})},
            'parsed':{'fallback_used':False,'engine_interventions':0,'rule_replacements':0}}
        if fail=='wronginput':raw['input']['fen']='different'
        subject.save(folder/'child/raw.json',raw)
        receipt={'status':'failed'if fail=='cleanup'else'passed','case_id':request['row']['case_id'],'identity':request['identity'],
            'pid':1234,'parent_pid':os.getpid(),'protocol_sha256':subject.digest(protocol),
            'source_sha256':plan['child_implementation_sha256'],
            'requested_input_sha256':__import__('hashlib').sha256(json.dumps(request['row']['input'],sort_keys=True).encode()).hexdigest(),
            'raw_sha256':subject.digest(folder/'child/raw.json'),'frozen_storage':{'identical':True},'in_owned_ancestor_job':True}
        subject.save(folder/'child/closed.json',receipt)
        return {'pid':1234,'exit_code':0 if fail!='cleanup'else 1,'child_exited_before_next_request':True,'elapsed_seconds':1.}
    return runner


def test_two_software_children_serial_exit_rawbindings_fullpending_and_no_torch(tmp_path):
    plan,protocol,rows=setup(tmp_path);calls=[]
    result=subject.run(plan,protocol,tmp_path/'attempt',fake_runner(plan,protocol,calls),lambda:{'commit_total_bytes':1000})
    assert result['status']=='passed'and result['completed_children']==2 and calls==['0','1']
    assert not result['outer_torch_imported']and not result['labels_opened']
    assert len((tmp_path/'attempt/calls.jsonl').read_text().splitlines())==4


@pytest.mark.parametrize('failure',['cleanup','timeout','wronginput'])
def test_first_child_or_provenance_failure_retains96_denominator_and_never_opens_truth(tmp_path,failure):
    plan,protocol,rows=setup(tmp_path,'heldout');calls=[];plan['heldout_references']={'path':'FORBIDDEN','sha256':'never'}
    subject.save(protocol,plan)
    with pytest.raises(RuntimeError):subject.run(plan,protocol,tmp_path/'attempt',fake_runner(plan,protocol,calls,failure),lambda:{'commit_total_bytes':1000})
    baseline=subject.read(tmp_path/'attempt/baseline.json');selected=subject.read(tmp_path/'attempt/selected.json')
    assert len(baseline['rows'])==len(selected['rows'])==48 and calls==['0']
    assert baseline['rows'][0]['status']==('active_unknown'if failure=='timeout'else'failed')
    assert all(row['status']=='not_run'for row in baseline['rows'][1:]+selected['rows'])
    assert subject.read(tmp_path/'attempt/closed.json')['status']=='failed'


def test_software_globalcommit_threshold_stops_before_second_call(tmp_path):
    plan,protocol,rows=setup(tmp_path);calls=[];samples=iter([{'commit_total_bytes':0},{'commit_total_bytes':1024**3+1}])
    with pytest.raises(RuntimeError,match='growth'):subject.run(plan,protocol,tmp_path/'attempt',fake_runner(plan,protocol,calls),lambda:next(samples))
    assert calls==['0']and subject.read(tmp_path/'attempt/software.json')['rows'][1]['status']=='not_run'


def test_changed_generation_or_request_budget_stops_after_pending_before_anychild(tmp_path):
    plan,protocol,rows=setup(tmp_path);plan['model_runtime']['generation']={**GENERATION,'max_new_tokens':384};subject.save(protocol,plan)
    def forbidden(*args):raise AssertionError('child started')
    with pytest.raises(ValueError,match='generation'):subject.run(plan,protocol,tmp_path/'attempt',forbidden)
    assert all(row['status']=='not_run'for row in subject.read(tmp_path/'attempt/software.json')['rows'])
    assert subject.read(tmp_path/'attempt/closed.json')['status']=='failed'


def test_failed_qualification_cannot_open_fresh_held_panel(tmp_path):
    plan,protocol,rows=setup(tmp_path,'heldout');qpath=Path(plan['successful_qualification']['path'])
    value=subject.read(qpath);value['status']='failed';subject.save(qpath,value)
    plan['successful_qualification']['sha256']=subject.digest(qpath);subject.save(protocol,plan)
    calls=[]
    with pytest.raises(ValueError,match='qualification'):
        subject.run(plan,protocol,tmp_path/'attempt',fake_runner(plan,protocol,calls),lambda:{'commit_total_bytes':1000})
    assert not calls and all(row['status']=='not_run'for row in subject.read(tmp_path/'attempt/selected.json')['rows'])


def test_timeout_targets_only_spawned_child_and_records_exit_before_next(tmp_path,monkeypatch):
    folder=tmp_path/'request';folder.mkdir();times=iter([0.,211.,212.,213.]);actions=[]
    monkeypatch.setattr(subject.time,'monotonic',lambda:next(times))
    class Child:
        pid=4321;returncode=None
        def poll(self):return self.returncode
        def terminate(self):actions.append(('terminate',self.pid));self.returncode=1
        def wait(self,timeout):actions.append(('wait',self.pid));return self.returncode
    def popen(command,**kwargs):
        assert command==['authored-child']and kwargs['creationflags']==getattr(subject.subprocess,'CREATE_NO_WINDOW',0)
        actions.append(('spawn',4321));return Child()
    monkeypatch.setattr(subject.subprocess,'Popen',popen)
    with pytest.raises(RuntimeError,match='timeout'):
        subject.launch(['authored-child'],folder,210,tmp_path/'CANCEL',subject.datetime(2099,1,1,tzinfo=subject.timezone.utc),9999)
    assert actions==[('spawn',4321),('terminate',4321),('wait',4321)]
    assert subject.read(folder/'process-closed.json')['child_exited_before_next_request']
    assert(folder/'child/request.CANCEL').exists()


@pytest.mark.parametrize('field',['model_revision','adapter_sha256','base_nf4_source_sha256','cache','pv','selected','fallback','engine','rules'])
def test_false_audit_pass_cannot_mask_raw_provenance_or_intervention_mismatch(tmp_path,field):
    plan,protocol,rows=setup(tmp_path);row=rows[0];identity=plan['conditions']['software']
    raw={'status':'completed','input':{'history':[],**row['input']},'trained_adapter':identity,
        'model_revision':'pinned-publisher','adapter_sha256':'runtime-source','base_nf4_source_sha256':'nf4-source',
        'settings':{'use_kv_cache':False},'no_forward_input_audit':{'passed':True,'engine_evaluation_or_pv_input':False,
            'selected_move_supplied':False,'allowed_fields':['fen','history']},
        'parsed':{'fallback_used':False,'engine_interventions':0,'rule_replacements':0}}
    assert subject.raw_provenance(raw,row,identity,plan)
    if field in plan['raw_provenance']:raw[field]='changed'
    elif field=='cache':raw['settings']['use_kv_cache']=True
    elif field=='pv':raw['no_forward_input_audit']['engine_evaluation_or_pv_input']=True
    elif field=='selected':raw['no_forward_input_audit']['selected_move_supplied']=True
    else:raw['parsed'][{'fallback':'fallback_used','engine':'engine_interventions','rules':'rule_replacements'}[field]]=True if field=='fallback'else 1
    assert not subject.raw_provenance(raw,row,identity,plan)


@pytest.mark.parametrize('key,value',[('script','other.py'),('arguments_sha256','wrong-arguments')])
def test_arbitrary_completed_worker_cannot_qualify_a_different_phase(tmp_path,key,value):
    plan,protocol,rows=setup(tmp_path,'heldout');worker=Path(plan['closed_qualification_worker']['path'])
    actual=subject.read(worker);actual[key]=value;subject.save(worker,actual)
    plan['closed_qualification_worker']['sha256']=subject.digest(worker)
    audit=Path(plan['qualification_audit']['path']);metadata=subject.read(audit);metadata['worker_sha256']=subject.digest(worker)
    subject.save(audit,metadata);plan['qualification_audit']['sha256']=subject.digest(audit);subject.save(protocol,plan)
    with pytest.raises(ValueError,match='qualification'):subject.verify(plan)
