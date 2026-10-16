"""Authored fake metadata/calls only. No real corpus, model, GPU or engine."""
import builtins
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import types

import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experiments/chess-queen-coach-counterfactual-v1/recovery-v2/run_cpu_once.py'
spec=importlib.util.spec_from_file_location('tested_counterfactual_recovery',SOURCE)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)


@pytest.fixture
def case(tmp_path,monkeypatch):
    repo=tmp_path/'repo';private=repo/'data/private';private.mkdir(parents=True)
    monkeypatch.setattr(driver,'ROOT',repo)
    def file(name,value):
        path=repo/name;path.parent.mkdir(parents=True,exist_ok=True)
        driver.save(path,value);return path
    intake_source=file('scripts/chess_queen_coach_counterfactual_intake_v1.py',{'fake_source':'intake'})
    teacher_source=file('scripts/chess_queen_coach_counterfactual_teacher_v1.py',{'fake_source':'teacher'})
    monkeypatch.setattr(driver,'INTAKE',driver.sha(intake_source));monkeypatch.setattr(driver,'TEACHER',driver.sha(teacher_source))
    science=file('experiments/chess-queen-coach-counterfactual-v1/intake-protocol.json',{
        'counts':driver.COUNTS,'implementation_sha256':driver.INTAKE,'teacher_implementation':{'sha256':driver.TEACHER},
        'teacher':{'phase_maximum_seconds':3300,'binary':{'path':'tools/stockfish.exe'}},
        'maximum_cpu_seconds':1200,'cutoff_utc':driver.POLICY['cutoff_utc'],
        'cpu_start_commit_bytes':8*driver.GIB,'cpu_running_commit_bytes':6*driver.GIB,'cpu_physical_bytes':4*driver.GIB})
    monkeypatch.setattr(driver,'SCIENCE',driver.sha(science))
    failed=file('failed/failure.json',{'status':'failed','fixture_only':True})
    proposal=file('proposal.json',{'failed_attempt':{'bindings':[{**driver.binding(failed),'bytes':failed.stat().st_size}]}})
    monkeypatch.setattr(driver,'PROPOSAL',driver.sha(proposal))
    worker=file('held-worker.json',{'schema':'chess.gpu-worker.v1','status':'failed','exit_code':1,'child_pid':53276,
        'arguments_sha256':driver.ARGUMENTS,'child_exited_before_lease_release':True,'lock':str(private/'chess-gpu-owner.lock')})
    monkeypatch.setattr(driver,'WORKER',driver.sha(worker))
    context=file('context.json',{'schema':'chess.closed-owner-and-changed-context.v1','worker':str(worker),
        'worker_sha256':driver.WORKER,'child_pid':53276,'child_pid_absent_OpenProcess_error':87,'lease_probe_free':True,
        'CPU_samples':[{'at':f'2026-10-16T10:00:0{i}+00:00','commit_headroom_bytes':9*driver.GIB,
            'physical_available_bytes':5*driver.GIB} for i in range(2)]})
    monkeypatch.setattr(driver,'CONTEXT',driver.sha(context))
    files={'driver':SOURCE,'builder':SOURCE.with_name('build_protocol.py'),'scientific_protocol':science,
        'intake':intake_source,'teacher':teacher_source,'proposal':proposal,'closed_held_worker':worker,'root_changed_context':context}
    plan={'schema':driver.SCHEMA,'driver_sha256':driver.sha(SOURCE),'scientific_protocol_sha256':driver.SCIENCE,
        'bindings':{key:driver.binding(path) for key,path in files.items()},'policy':driver.POLICY,'counts':driver.COUNTS,
        'teacher_requests':3168,'filelock_version':'4.2.0','failed_attempt':driver.read(proposal)['failed_attempt']['bindings'],
        'output':str(private/'chess-queen-coach-counterfactual-recovery-v2'),'lock':str(private/'chess-gpu-owner.lock')}
    protocol=file('op.json',plan)
    value={'repo':repo,'protocol':protocol,'plan':plan,'out':Path(plan['output']),'calls':[],
        'time':0.0,'sample_index':0,'samples':[9*driver.GIB,9*driver.GIB]}
    def clock():return value['time']
    def sleep(seconds):value['time']+=seconds;value['calls'].append(('sleep',seconds))
    def sampler():
        i=value['sample_index'];value['sample_index']+=1
        return {'at':'2026-10-16T10:00:00+00:00','commit_headroom_bytes':value['samples'][i],
            'physical_available_bytes':value.get('physical',5*driver.GIB)}
    class Lease:
        def acquire(self,timeout):
            assert timeout==0;value['calls'].append('lease_acquire')
            if value.get('busy'):raise RuntimeError('Fake busy lease')
        def release(self):value['calls'].append('lease_release')
    class Intake:
        def intake(self,path,out):
            assert path==science and not out.exists();value['calls'].append('intake')
            if value.get('intake_failure')=='before':raise RuntimeError('Fake setup failure before output')
            out.mkdir()
            if value.get('intake_failure')=='after':raise KeyboardInterrupt('Fake interrupted setup')
            dataset={'groups':{name:[{'game_id':f'{name}:{i}'} for i in range(count)] for name,count in driver.COUNTS.items()},
                'shortages':{key:0 for key in driver.COUNTS},'status':'ready_for_teachers'}
            if value.get('shortage'):dataset['groups']['train'].pop();dataset['shortages']['train']=1;dataset['status']='insufficient_cohort'
            driver.save(out/'dataset.json',dataset)
            value['time']+=value.get('intake_elapsed',0)
            return {'status':dataset['status']}
    class Teacher:
        @staticmethod
        def tasks_for(dataset):
            return [{'case_id':f'{row["game_id"]}:{mode}','group_id':row['game_id'],'mode':mode}
                for rows in dataset['groups'].values() for row in rows for mode in ('free','selected_a','selected_b')]
        @staticmethod
        def recover(tasks,journal):
            rows={row['case_id']:{**row,'status':'not_run'} for row in tasks}
            if journal.exists():
                for text in journal.read_text().splitlines():
                    event=json.loads(text);row=rows[event['case_id']]
                    row['status']='active_unknown' if event['event']=='intent' else event['status']
            return list(rows.values())
        def teachers(self,path,out):
            value['calls'].append('teachers');tasks=self.tasks_for(driver.read(out/'dataset.json'))
            if value.get('teacher_setup_failure'):raise RuntimeError('Fake teacher setup failure')
            events=[]
            for task in tasks:
                events.append({'event':'intent','case_id':task['case_id']})
                if value.get('teacher_unknown'):break
                events.append({'event':'outcome','case_id':task['case_id'],'status':'completed'})
            (out/'teacher-journal.jsonl').write_text('\n'.join(json.dumps(row) for row in events)+'\n')
            records=self.recover(tasks,out/'teacher-journal.jsonl')
            driver.save(out/'teachers.json',{'planned':3168,'all_planned_completed':not value.get('teacher_unknown'),
                'statuses':{'completed':3168} if not value.get('teacher_unknown') else {'active_unknown':1,'not_run':3167},'rows':records})
            driver.save(out/'teacher-closed.json',{'teachers_sha256':driver.sha(out/'teachers.json') if not value.get('incoherent') else '0'*64})
            value['time']+=value.get('teacher_elapsed',0)
            if value.get('teacher_unknown'):raise KeyboardInterrupt('Fake active teacher interruption')
        def export(self,path,out):
            value['calls'].append('export')
            if value.get('export_failure'):raise RuntimeError('Fake export shortage')
            result={'status':'ready_for_training','protocol_sha256':driver.SCIENCE,'fixture_only':True}
            driver.save(out/'manifest.json',result);return result
    class Observer:
        def __init__(self,journal,cancel,image):self.journal=journal;assert image=='stockfish.exe'
        def start(self):value['calls'].append('observe_start')
        def finish(self):
            value['calls'].append('observe_finish')
            rows=[] if value.get('no_engine') else [{'pid':90001,'parent_pid':os.getpid(),'image':'stockfish.exe','fixture_only':True}]
            return rows,['Fake observation failure'] if value.get('observer_error') else []
    def loader():value['calls'].append('loader');return Intake(),Teacher()
    value['kwargs']={'sampler':sampler,'clock':clock,'sleep':sleep,'acquire':lambda path:Lease(),
        'is_alive':lambda pid:value.get('old_child_alive',False) if pid==53276 else value.get('engine_alive',False),
        'loader':loader,'observer_factory':Observer,'now':lambda:datetime(2026,10,16,10,tzinfo=timezone.utc)}
    return value


def run(case):return driver.run(case['protocol'],driver.sha(case['protocol']),**case['kwargs'])


def test_one_sequence_with_unchanged_functions_exact_ready_interface_and_no_replay(case):
    result=run(case)
    assert result['status']=='completed' and result['owned_engine_exit_verified'] is True
    assert result['teacher_outcomes']=={'completed':3168}
    assert all(state=='completed' for state in result['phases'].values())
    assert result['scientific_protocol_sha256']==driver.SCIENCE
    assert result['operational_protocol_sha256']==driver.sha(case['protocol'])
    assert result['corpus_manifest_sha256']==driver.sha(case['out']/'manifest.json')
    assert result['resource_context_lease_released'] is True
    assert case['calls'].index('lease_acquire')<case['calls'].index('loader')<case['calls'].index('intake')
    assert case['calls'].index('observe_finish')<case['calls'].index('export')<case['calls'].index('lease_release')
    assert driver.read(case['out']/'operational-provenance.json')==result
    assert driver.read(driver.paths_for(case['out'])['closed'])==result
    assert driver.read(case['out']/'operational-sources/manifest.json')['status']=='completed'
    with pytest.raises(ValueError,match='no replay'):run(case)
    assert case['calls'].count('intake')==case['calls'].count('teachers')==case['calls'].count('export')==1


@pytest.mark.parametrize('index',[0,1])
@pytest.mark.parametrize('bad',[7*driver.GIB,True,-1])
def test_either_admission_sample_fails_before_source_import(case,index,bad):
    case['samples'][index]=bad;result=run(case)
    assert result['status']=='failed' and result['phases']['admission']=='failed'
    assert 'loader' not in case['calls'] and 'intake' not in case['calls']
    assert result['teacher_outcomes']=={'not_run':3168}
    assert case['calls'][-1]=='lease_release' and not case['out'].exists()
    assert driver.paths_for(case['out'])['intent'].exists()


@pytest.mark.parametrize('flag',['busy','old_child_alive'])
def test_closed_owner_and_free_lease_fail_closed_without_scientific_call(case,flag):
    case[flag]=True;result=run(case)
    assert result['status']=='failed' and 'loader' not in case['calls']
    assert result['phases']['intake']=='not_run'


def test_two_samples_are_at_least_one_second_apart_and_exact_threshold_is_accepted(case):
    case['samples']=[8*driver.GIB]*2;case['physical']=4*driver.GIB
    assert run(case)['status']=='completed'
    rows=[json.loads(text) for text in driver.paths_for(case['out'])['samples'].read_text().splitlines()]
    assert len(rows)==2 and rows[1]['monotonic']-rows[0]['monotonic']>=1


@pytest.mark.parametrize('failure',['before','after'])
def test_intake_setup_and_interrupt_keep_final_provenance_and_stop_future_phases(case,failure):
    case['intake_failure']=failure;result=run(case)
    assert result['status']=='failed' and result['phases']['intake']=='failed'
    assert 'teachers' not in case['calls'] and 'export' not in case['calls']
    assert (case['out']/'operational-provenance.json').exists()
    assert (case['out']/'operational-sources/manifest.json').exists()
    assert result['teacher_outcomes']=={'not_run':3168}


def test_short_cohort_does_not_dispatch_teachers(case):
    case['shortage']=True;result=run(case)
    assert result['status']=='failed' and 'Incomplete intake' in result['error']
    assert 'teachers' not in case['calls'] and 'export' not in case['calls']


@pytest.mark.parametrize('flag,expected',[('teacher_setup_failure',{'not_run':3168}),('teacher_unknown',{'active_unknown':1,'not_run':3167})])
def test_teacher_failure_retains_all_planned_notrun_and_unknown_without_export(case,flag,expected):
    case[flag]=True;result=run(case)
    assert result['status']=='failed' and result['teacher_outcomes']==expected
    outcomes=driver.read(case['out']/'operational-teacher-outcomes.json')
    assert outcomes['planned']==len(outcomes['rows'])==3168
    assert 'export' not in case['calls'] and result['owned_engine_exit_verified'] is True


@pytest.mark.parametrize('flag',['incoherent','engine_alive','no_engine','observer_error','export_failure'])
def test_incoherence_unobserved_or_live_owned_engine_and_export_shortage_never_ready(case,flag):
    case[flag]=True;result=run(case)
    assert result['status']=='failed'
    if flag!='export_failure':assert 'export' not in case['calls']
    assert result['resource_context_lease_released'] is True
    if flag in ('engine_alive','no_engine','observer_error'):assert result['owned_engine_exit_verified'] is False


@pytest.mark.parametrize('phase,elapsed',[('intake',1201),('teacher',3301)])
def test_elapsed_deadline_stops_later_phases_without_changing_science(case,phase,elapsed):
    case[phase+'_elapsed']=elapsed;result=run(case)
    assert result['status']=='failed' and 'deadline exceeded' in result['error']
    assert 'export' not in case['calls']
    if phase=='intake':assert 'teachers' not in case['calls']


def test_snapshot_setup_failure_is_durable_without_teacher_dispatch(case,monkeypatch):
    def fail(*args):raise OSError('Fake snapshot setup failure')
    monkeypatch.setattr(driver.shutil,'copyfile',fail)
    result=run(case)
    assert result['status']=='failed' and 'teachers' not in case['calls']
    snapshot=driver.read(case['out']/'operational-sources/manifest.json')
    assert snapshot['status']=='failed' and 'snapshot' in snapshot['error']
    assert driver.read(case['out']/'operational-provenance.json')['status']=='failed'


@pytest.mark.parametrize('field',['driver_sha256','scientific_protocol_sha256','policy','teacher_requests'])
def test_tampered_operational_contract_is_retained_then_rejected_before_import(case,field):
    plan=driver.read(case['protocol']);plan[field]='tampered';case['protocol'].write_text(json.dumps(plan))
    result=run(case)
    assert result['status']=='failed' and result['phases']['verify']=='failed'
    assert 'loader' not in case['calls'] and driver.paths_for(case['out'])['closed'].exists()


def test_changed_failed_receipt_or_bound_source_rejected_before_import(case):
    Path(case['plan']['failed_attempt'][0]['path']).write_text('changed')
    assert run(case)['status']=='failed' and 'loader' not in case['calls']


def test_global_cutoff_and_bad_protocol_hash_do_not_call_science(case):
    with pytest.raises(ValueError,match='protocol hash'):driver.run(case['protocol'],'0'*64,**case['kwargs'])
    assert not driver.paths_for(case['out'])['intent'].exists()
    case['kwargs']['now']=lambda:datetime(2026,10,16,13,tzinfo=timezone.utc)
    result=run(case)
    assert result['status']=='failed' and result['phases']['verify']=='failed' and not case['calls']


def test_readonly_observer_failure_cancels_only_owned_attempt(tmp_path,monkeypatch):
    marker=tmp_path/'CANCEL';journal=tmp_path/'pids.jsonl'
    def observe(parent,image):raise OSError('Fake process observation failure')
    monkeypatch.setattr(driver,'owned_children',observe)
    monitor=driver.EngineObserver(journal,marker,'stockfish.exe');monitor.sample()
    assert monitor.errors and marker.exists()
    assert driver.read(marker)['reason'].startswith('Owned PID observation failed')


@pytest.mark.parametrize('change',['missing_closed_binding','null_bindings','list_bindings'])
def test_malformed_binding_after_intent_always_has_closed_failed_phase_record(case,change):
    plan=driver.read(case['protocol'])
    if change=='missing_closed_binding':del plan['bindings']['closed_held_worker']
    else:plan['bindings']=None if change=='null_bindings' else []
    case['protocol'].write_text(json.dumps(plan))
    result=run(case)
    assert result['status']=='failed' and result['phases']['verify']=='failed'
    assert result['closed_held_worker'] is None and 'loader' not in case['calls']
    paths=driver.paths_for(case['out'])
    assert paths['intent'].exists() and paths['phases'].exists() and paths['closed'].exists()
    assert driver.read(paths['closed'])==result


def test_observation_and_error_logging_failure_still_cancels_owned_attempt_before_teachers(case,monkeypatch):
    original=driver.append;pids=driver.paths_for(case['out'])['pids']
    def append(path,row):
        if path==pids:raise OSError('Fake PID journal write failure')
        return original(path,row)
    monkeypatch.setattr(driver,'append',append)
    monkeypatch.setattr(driver,'owned_children',lambda parent,image:[{'pid':90001,'parent_pid':parent,'image':image}])
    case['kwargs']['observer_factory']=driver.EngineObserver
    result=run(case)
    assert result['status']=='failed' and 'teachers' not in case['calls'] and 'export' not in case['calls']
    assert result['teacher_outcomes']=={'not_run':3168}
    assert any('journal write failure' in error for error in result['pid_observation_errors'])
    assert driver.read(case['out']/'CANCEL')['reason'].startswith('Owned PID observation failed')


def test_cpu_route_has_no_scientific_model_engine_or_process_imports(case,monkeypatch):
    original=builtins.__import__
    def imports(name,*args,**kwargs):
        if name.split('.')[0] in {'torch','transformers','bitsandbytes','peft','subprocess'} or name.startswith('chess_queen_coach_counterfactual_'):
            raise AssertionError('Forbidden real import during fake CPU tests: '+name)
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',imports)
    assert run(case)['status']=='completed'
