"""Standard-library outer process; one leased phase with serial cold children."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from process_lineage_v8 import Tracker,normalized,Windows
from job_context_direct_v3 import JobContext, IDENTITY_POLICY
import direct_launch_contract as launch_contract


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8')as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def append(path,value):
    with Path(path).open('a',encoding='utf-8')as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def bound(item):
    path=Path(item['path']);path=path if path.is_absolute()else ROOT/path
    if digest(path)!=item['sha256']:raise ValueError('Frozen bytes changed: '+str(path))
    return path


def no_torch():
    if 'torch'in sys.modules:raise RuntimeError('Outer process must never import Torch')


def verify_observer_probe(plan):
    """Actual same-source CPU OS observations must precede any model child."""
    proof=read(bound(plan['cpu_observer_probe']))
    frozen=read(bound(plan['cpu_observer_protocol']))
    worker=read(bound(plan['cpu_observer_worker']))
    audit=read(bound(plan['cpu_observer_audit']))
    launch_contract.owned_worker(worker,plan['owned_worker_source'],plan['interpreters'])
    if(proof.get('status')!='passed'or proof.get('planned')!=4 or proof.get('completed')!=4
        or proof.get('exact_87_measurements',0)<1 or proof.get('torch_imported')is not False
        or any(proof.get(key)!=0 for key in ('model_calls','engine_calls','CUDA_initializations'))
        or proof.get('protocol_sha256')!=plan['cpu_observer_protocol']['sha256']
        or not proof.get('final_baseline_only',{}).get('baseline_handles_live')
        or frozen.get('cold_outer_source',{}).get('sha256')!=plan['implementation_sha256']
        or frozen.get('process_lineage_helper')!=plan['process_lineage_helper']
        or frozen.get('job_context_source')!=plan['job_context_source']
        or frozen.get('owned_worker_source')!=plan['owned_worker_source']
        or frozen.get('cpu_environment_parity')!=plan['cpu_environment_parity']
        or proof.get('job_context',{}).get('launch_profile')!=plan['launch_profile']
        or proof.get('job_context',{}).get('identity_policy')!=IDENTITY_POLICY
        or len(proof.get('job_context',{}).get('retained_identity_history',[]))<2
        or any(not value.get('handle_closed')or not value.get('exit_proved')
            for value in proof.get('job_context',{}).get('retained_identity_history',[]))
        or frozen.get('job_context_policy')!=plan['job_context_policy']
        or frozen.get('process_identity_policy')!=plan['process_identity_policy']
        or frozen.get('resource_sampler_auxiliary')!=plan['resource_sampler_auxiliary']
        or worker.get('status')!='completed'or worker.get('exit_code')!=0
        or not worker.get('child_exited_before_lease_release')
        or str(worker.get('script')).replace('\\','/')!=frozen['expected_worker_arguments'][0].replace('\\','/')
        or worker.get('arguments_sha256')!=hashlib.sha256(json.dumps(frozen['expected_worker_arguments']).encode()).hexdigest()
        or audit.get('status')!='passed'or audit.get('protocol_sha256')!=plan['cpu_observer_protocol']['sha256']
        or audit.get('probe_sha256')!=plan['cpu_observer_probe']['sha256']
        or audit.get('worker_sha256')!=plan['cpu_observer_worker']['sha256']):
        raise ValueError('Closed same-source CPU observer probe and independent audit required')


def verify(plan):
    no_torch()
    if plan['implementation_sha256']!=digest(Path(__file__)):raise ValueError('Outer source differs')
    helper=bound(plan['process_lineage_helper'])
    if helper.resolve()!=(ROOT/'experiments/chess-queen-coach-daytime-v1/process_lineage_v8.py').resolve():raise ValueError('Wrong lineage helper')
    context_source=bound(plan['job_context_source'])
    if context_source.resolve()!=(ROOT/'experiments/chess-queen-coach-daytime-v1/job_context_direct_v3.py').resolve():raise ValueError('Wrong current-job context source')
    if plan['job_context_policy']!={'unretained_error':87,'fresh_complete_observations':2,'separation_ms':10,'maximum_observation_ms':1000,'classification':'ABSENT_not_EXIT','baseline_only_after_sampler':True}:raise ValueError('Frozen absence/job-context policy differs')
    if plan['process_identity_policy']!=IDENTITY_POLICY:raise ValueError('Identity policy differs')
    launch_contract.environment(plan,bound,read)
    verify_observer_probe(plan)
    sampler=plan['resource_sampler_auxiliary']
    if digest(bound(sampler['source']))!=sampler['source']['sha256'] or sampler['arguments']!=['nvidia-smi','--query-gpu=memory.total,memory.free','--format=csv,noheader,nounits']:
        raise ValueError('Resource sampler source/arguments differ')
    if normalized(shutil.which('nvidia-smi'))!=normalized(bound(sampler['executable'])):raise ValueError('PATH sampler identity differs')
    if plan['interpreters']!={'launcher':normalized(sys.executable),'delegate':normalized(sys._base_executable)}:
        raise ValueError('Pinned launcher/base interpreter differs')
    for item in plan['dependencies']:bound(item)
    bound(plan['input_rows'])
    if plan['mode']not in('qualification','heldout'):raise ValueError('Unknown frozen phase')
    expected_conditions={'software'}if plan['mode']=='qualification'else{'baseline','selected'}
    if set(plan['conditions'])!=expected_conditions:raise ValueError('Exact frozen conditions required')
    if plan['mode']=='qualification':
        if plan['conditions']['software']!=plan['model_runtime']['warm_start']:raise ValueError('Software uses fixed64 only')
    else:
        qualification=read(bound(plan['successful_qualification']))
        qualified_plan=read(bound(plan['qualification_protocol']))
        worker=read(bound(plan['closed_qualification_worker']))
        audit=read(bound(plan['qualification_audit']))
        launch_contract.owned_worker(worker,plan['owned_worker_source'],plan['interpreters'])
        expected_arguments=json.dumps(plan['qualification_worker_arguments']).encode()
        if(qualification.get('status')!='passed'or qualification.get('planned')!=2
            or qualification.get('completed_children')!=2 or qualification.get('outer_torch_imported')
            or not qualification.get('all_children_closed')
            or qualification['protocol_sha256']!=plan['qualification_protocol']['sha256']
            or qualified_plan['model_runtime']!=plan['model_runtime']
            or qualified_plan['implementation_sha256']!=plan['implementation_sha256']
            or qualified_plan['child_implementation_sha256']!=plan['child_implementation_sha256']
            or qualified_plan['raw_provenance']!=plan['raw_provenance']
            or qualified_plan['process_lineage_helper']!=plan['process_lineage_helper']
            or qualified_plan['job_context_source']!=plan['job_context_source']
            or qualified_plan['job_context_policy']!=plan['job_context_policy']
            or qualified_plan['process_identity_policy']!=plan['process_identity_policy']
            or any(qualified_plan[key]!=plan[key]for key in('cpu_observer_probe','cpu_observer_protocol','cpu_observer_worker','cpu_observer_audit'))
            or qualified_plan['interpreters']!=plan['interpreters']
            or qualified_plan['owned_worker_source']!=plan['owned_worker_source']
            or qualified_plan['cpu_environment_parity']!=plan['cpu_environment_parity']
            or qualified_plan['resource_sampler_auxiliary']!=plan['resource_sampler_auxiliary']
            or plan['qualification_worker_arguments']!=qualified_plan['expected_worker_arguments']
            or worker.get('status')!='completed'or worker.get('exit_code')!=0
            or str(worker.get('script')).replace('\\','/')!=plan['qualification_worker_script'].replace('\\','/')
            or worker.get('arguments_sha256')!=hashlib.sha256(expected_arguments).hexdigest()
            or audit.get('status')!='passed'or audit.get('protocol_sha256')!=plan['qualification_protocol']['sha256']
            or audit.get('qualification_sha256')!=plan['successful_qualification']['sha256']
            or audit.get('worker_sha256')!=plan['closed_qualification_worker']['sha256']
            or not worker.get('child_exited_before_lease_release')):
            raise ValueError('Actual closed same-source2request software qualification required')
    if(plan['child_maximum_seconds']!=210
        or plan['phase_maximum_seconds']!=(450 if plan['mode']=='qualification'else 4500)):
        raise ValueError('Frozen cold budgets differ')
    if plan['model_runtime']['generation']!={'max_new_tokens':1024,'maximum_seconds':180,'temperature':0,
        'seed':20260823,'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'}:
        raise ValueError('Fair raw generation limits differ')


def pending(out,rows,conditions,protocol_sha256):
    if out.exists():raise ValueError('Cold phase is create-only; never replay')
    out.mkdir(parents=True)
    for name,identity in conditions.items():
        save(out/(name+'.json'),{'status':'not_run','condition':name,'model_identity':identity,
            'protocol_sha256':protocol_sha256,'planned':len(rows),
            'rows':[{'case_id':row['case_id'],'group_id':row['group_id'],'mode':row['mode'],'status':'not_run',
                'input_sha256':hashlib.sha256(json.dumps(row['input'],sort_keys=True).encode()).hexdigest()}for row in rows]})


def raw_provenance(raw,row,identity,plan):
    if raw.get('input')!={'history':[],**row['input']}or raw.get('trained_adapter')!=identity:return False
    for path,expected in plan['raw_provenance'].items():
        value=raw
        for key in path.split('.'):
            value=value.get(key)if isinstance(value,dict)else None
        if type(value)is not type(expected)or value!=expected:return False
    audit=raw.get('no_forward_input_audit',{});parsed=raw.get('parsed',{})
    return(raw.get('status')in('completed','partial')and raw.get('settings',{}).get('use_kv_cache')is False
        and audit.get('passed')is True and audit.get('engine_evaluation_or_pv_input')is False
        and audit.get('selected_move_supplied')is('selected_uci'in row['input'])
        and audit.get('allowed_fields')==sorted({'history',*row['input']})
        and parsed.get('fallback_used')is False
        and type(parsed.get('engine_interventions'))is int and parsed['engine_interventions']==0
        and type(parsed.get('rule_replacements'))is int and parsed['rule_replacements']==0)


def observation_wait_budget(started,maximum,parent_cancel,cutoff,deadline):
    if parent_cancel.exists():return 0
    seconds=min(1.,started+maximum-time.monotonic(),deadline-time.monotonic(),
        (cutoff-datetime.now(timezone.utc)).total_seconds())
    return max(0,int(seconds*1000))


def launch(command,folder,maximum,parent_cancel,cutoff,deadline,job_context):
    """Retain direct/one-hop owned identities; both handles must exit before next."""
    no_torch();started=time.monotonic();child=None;tracker=None;cancelled=False;proof=None;primary_error=None
    with(folder/'process.log').open('w',encoding='utf-8')as log:
        child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        save(folder/'process.json',{'status':'started','pid':child.pid,'parent_pid':os.getpid(),'command':command,
            'creation_flags':getattr(subprocess,'CREATE_NO_WINDOW',0),'breakaway':False})
        try:
            tracker=Tracker(child.pid,os.getpid(),launcher_handle=child._handle,
                sampler=read(command[command.index('--protocol')+1])['resource_sampler_auxiliary'],
                wait_budget=lambda:observation_wait_budget(started,maximum,parent_cancel,cutoff,deadline),
                job_context=job_context,audit=lambda value:append(folder/'process-events.jsonl',value))
            retained=0
            while True:
                tracker.observe()
                if len(tracker.records)+len(tracker.transients)+len(tracker.absences)!=retained:
                    save(folder/'process-lineage.json',{'observed_processes':list(tracker.records.values()),
                        'unverified_exited_transients':list(tracker.transients.values()),
                        'unretained_absent_entries':list(tracker.absences.values()),
                        'launcher_pid':child.pid,'outer_pid':os.getpid(),'root_job_inheritance':'No BREAKAWAY; live ancestry and every retained handle job membership required'})
                    retained=len(tracker.records)+len(tracker.transients)+len(tracker.absences)
                if child.poll()is not None:break
                timeout=time.monotonic()-started>=maximum
                stopping=parent_cancel.exists()or datetime.now(timezone.utc)>=cutoff or time.monotonic()>=deadline
                if timeout or stopping:
                    (folder/'child').mkdir(exist_ok=True);(folder/'child/request.CANCEL').touch(exist_ok=True)
                    cancelled=True;tracker.terminate_owned();child.wait(timeout=10)
                    raise RuntimeError('Owned child timeout or phase cancellation')
                time.sleep(.05)
            # A venv launcher exit alone cannot establish interpreter exit.
            while not tracker.all_exited():
                if time.monotonic()-started>=maximum or time.monotonic()>=deadline or parent_cancel.exists()or datetime.now(timezone.utc)>=cutoff:
                    cancelled=True;tracker.terminate_owned();raise RuntimeError('Owned auxiliary exit timeout/cancellation')
                time.sleep(.02)
            receipt=read(folder/'child/closed.json')
            proof=tracker.proof(receipt)
            return {'pid':proof['runtime_pid'],'parent_pid':proof['runtime_parent_pid'],'exit_code':child.returncode,
                'child_exited_before_next_request':True,'elapsed_seconds':time.monotonic()-started,'lineage':proof}
        except BaseException as error:
            primary_error=type(error).__name__+': '+str(error)
            save(folder/'process-observation-error.json',{'error':type(error).__name__+': '+str(error),
                'observation':getattr(error,'observation',None)})
            raise
        finally:
            exit_verified=False;cleanup_errors=[]
            try:
                if tracker:
                    if any(not tracker.os.exited(h)for h in tracker.handles.values()):tracker.terminate_owned()
                    exit_verified=tracker.all_exited()
                if child.poll()is None:child.terminate();child.wait(timeout=10)
            except BaseException as error:cleanup_errors.append(type(error).__name__+': '+str(error))
            try:
                save(folder/'process-final-context.json',job_context.describe())
            except BaseException as error:cleanup_errors.append(type(error).__name__+': '+str(error))
            if tracker:
                try:tracker.close()
                except BaseException as error:cleanup_errors.append(type(error).__name__+': '+str(error))
            save(folder/'process-closed.json',{'launcher_pid':child.pid,'exit_code':child.poll(),
                'child_exited_before_next_request':exit_verified and child.poll()is not None and not cleanup_errors,
                'lineage':proof,'elapsed_seconds':time.monotonic()-started,'cancelled':cancelled,
                'primary_error':primary_error,'cleanup_errors':cleanup_errors})
            if cleanup_errors and primary_error is None:raise RuntimeError('Owned closure failed: '+repr(cleanup_errors))


def make_context(audit):return JobContext(Windows(),audit=audit)


def run(plan,protocol,out,runner=launch,sampler=None,context_factory=make_context):
    no_torch()
    rows=[json.loads(line)for line in bound(plan['input_rows']).read_text().splitlines()if line.strip()]
    expected=2 if plan['mode']=='qualification'else 48
    if(len(rows)!=expected or len({row['case_id']for row in rows})!=expected
        or any(set(row)!={'case_id','group_id','mode','input'}or set(row['input'])not in({'fen'},{'fen','selected_uci'})for row in rows)):
        raise ValueError('Exact label-free frozen input denominator required')
    conditions=plan['conditions'];pending(out,rows,conditions,digest(protocol))
    result={'status':'started','mode':plan['mode'],'planned':len(rows)*len(conditions),'completed_children':0,
        'outer_torch_imported':False,'protocol_sha256':digest(protocol),'child_results':[]}
    samples=[];context=None;closure_error=None;started=time.monotonic();deadline=started+plan['phase_maximum_seconds'];save(out/'closed.json',result)
    try:
        verify(plan)
        context=context_factory(lambda value:append(out/'job-events.jsonl',value))
        result['job_context']=context.describe()
        if plan['mode']=='heldout'and datetime.now(timezone.utc)>=datetime.fromisoformat(plan['admission_latest_utc']):
            raise RuntimeError('Whole-held-phase admission closed')
        if sampler is None:
            from chess_native_resources import windows_sample
            sampler=lambda:windows_sample().__dict__
        baseline=sampler();samples.append({'stage':'outer_before_any_child',**baseline})
        sources=out/'executed-sources';sources.mkdir();copied={}
        for index,path in enumerate([Path(__file__),Path(protocol)]+[bound(item)for item in plan['dependencies']]):
            target=sources/f'{index:02d}-{path.name}';shutil.copyfile(path,target);copied[target.name]={'path':str(path),'sha256':digest(target)}
        save(sources/'manifest.json',copied)
        for condition,identity in conditions.items():
            panel_path=out/(condition+'.json');panel=read(panel_path);panel['status']='started';save(panel_path,panel)
            for index,row in enumerate(rows):
                no_torch()
                if(out/'CANCEL').exists()or time.monotonic()>=deadline or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):
                    raise RuntimeError('Owned outer phase/global deadline or cancellation')
                context.assert_baseline_only('before_next_request')
                folder=out/f'{condition}-{index:03d}';folder.mkdir()
                request={'protocol_sha256':digest(protocol),'row':row,'identity':identity}
                save(folder/'request.json',request)
                record=panel['rows'][index];record.update(status='active_unknown',request_sha256=digest(folder/'request.json'))
                append(out/'calls.jsonl',{'status':'call_started','condition':condition,'case_id':row['case_id'],
                    'request_sha256':record['request_sha256']});save(panel_path,panel)
                command=[sys.executable,str(bound(plan['child_script'])),'--protocol',str(Path(protocol).resolve()),
                    '--request',str((folder/'request.json').resolve()),'--out',str((folder/'child').resolve()),
                    '--parent-cancel',str((out/'CANCEL').resolve())]
                process=runner(command,folder,210,out/'CANCEL',datetime.fromisoformat(plan['cutoff_utc']),deadline,context)
                record.update(child_process=process)
                child_file=folder/'child/closed.json';raw_file=folder/'child/raw.json'
                child=read(child_file)if child_file.exists()else None
                if raw_file.exists():record.update(response_path=str(raw_file.resolve()),response_sha256=digest(raw_file))
                if(process['exit_code']!=0 or not process['child_exited_before_next_request']or not child
                    or child['status']!='passed'or not child.get('frozen_storage',{}).get('identical')
                    or not child.get('in_owned_ancestor_job')or not raw_file.exists()
                    or child.get('case_id')!=row['case_id']or child.get('identity')!=identity
                    or child.get('pid')!=process['pid']or child.get('parent_pid')!=process['parent_pid']
                    or child.get('protocol_sha256')!=digest(protocol)
                    or child.get('requested_input_sha256')!=record['input_sha256']
                    or child.get('source_sha256')!=plan['child_implementation_sha256']
                    or child.get('raw_sha256')!=digest(raw_file)):
                    record.update(status='failed',error='Cold child/process/postprocessing failed');save(panel_path,panel)
                    append(out/'calls.jsonl',{'status':'failed','condition':condition,'case_id':row['case_id'],'record':record})
                    raise RuntimeError(record['error'])
                raw=read(raw_file)
                settings=raw.get('settings',{});expected_generation=plan['model_runtime']['generation']
                if(not raw_provenance(raw,row,identity,plan)
                    or any(settings.get(key)!=value for key,value in expected_generation.items())
                    or not raw.get('no_forward_input_audit',{}).get('passed')):
                    record.update(status='failed',error='Actual raw input/checkpoint/generation provenance differs');save(panel_path,panel)
                    append(out/'calls.jsonl',{'status':'failed','condition':condition,'case_id':row['case_id'],'record':record})
                    raise RuntimeError(record['error'])
                record.update(status=raw['status'],child_receipt_sha256=digest(child_file))
                append(out/'calls.jsonl',{'status':'completed','condition':condition,'case_id':row['case_id'],'record':record})
                save(panel_path,panel);result['completed_children']+=1
                post=sampler();samples.append({'stage':'after_child_exit','condition':condition,'case_id':row['case_id'],**post})
                context.assert_baseline_only('after_postexit_resource_sampler')
                result['child_results'].append({'case_id':row['case_id'],'condition':condition,
                    'elapsed_seconds':process['elapsed_seconds'],'child_receipt_sha256':digest(child_file)})
                if plan['mode']=='qualification'and post['commit_total_bytes']-baseline['commit_total_bytes']>1024**3:
                    raise RuntimeError('Postexit globalcommit growth exceeds frozen1GiB qualification threshold')
                save(out/'closed.json',result)
            panel['status']='completed';save(panel_path,panel)
        if plan['mode']=='heldout':
            # Both48rawconditions are now closed. Only now import CPU evaluator/open truth.
            import chess_queen_coach_counterfactual_train_v1 as scoring
            references=scoring.references(bound(plan['heldout_references']),rows)
            for condition in conditions:save(out/(condition+'-score.json'),scoring.score_panel(rows,read(out/(condition+'.json')),references))
            no_torch()
        result.update(status='passed',outer_torch_imported='torch'in sys.modules,all_children_closed=True,
            labels_opened=plan['mode']=='heldout',claim='Software qualification only'if plan['mode']=='qualification'else'Recognized immediate facts and bounded teacher agreement only; not whole-prose coaching/Elo.')
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        if context is not None:
            try:result['final_job_baseline_only']=context.assert_baseline_only('whole_phase_finalization')
            except BaseException as error:
                closure_error=type(error).__name__+': '+str(error)
                result.update(status='failed',all_children_closed=False,job_context_closure_error=closure_error)
            finally:
                try:result['final_job_context']=context.describe()
                except BaseException as error:result['final_context_error']=type(error).__name__+': '+str(error)
                context.close()
        result['elapsed_seconds']=time.monotonic()-started
        result['outer_torch_imported']='torch'in sys.modules
        save(out/'resources.json',samples);save(out/'closed.json',result)
    if closure_error is not None:raise RuntimeError('Immediate-job closure failed: '+closure_error)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();run(read(args.protocol),args.protocol,args.out)
