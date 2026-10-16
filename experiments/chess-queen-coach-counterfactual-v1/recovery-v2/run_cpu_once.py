"""One changed-context CPU recovery. No model, GPU query, retry or science edit.

Only root may dispatch after complete source review. The existing GPU mutex is
held as resource-context protection while unchanged intake/teacher/export run.
Imports and fake CPU tests do not import the scientific modules or start engines.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime,timezone
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SCHEMA='chess.counterfactual-cpu-recovery.v2'
GIB=1024**3
SCIENCE='f6dce48af4610b23d8c7a376e2f15221429c0b2d8b21b838842272aeca077a0a'
INTAKE='3f0e7ab1cfed89d1ebf5c09ed44c7eac850688d628f3af89241dc9f1b2e5f09c'
TEACHER='2cda3bc89ad0a5e2d7ef0a5dbce52f507cadad6ad83bad92d6fe271cc18db489'
ARGUMENTS='7332676ba8d11d61637c4e50176f7204dd08bbb2df1e9129f42ba1db0b7adad1'
PROPOSAL='e19aff29c1f1a78467c2b89a905e0ad9eee6d7055daba5c79e64ed68afec9ad1'
WORKER='f443d8fa2ac23a38477413528949f086d27432523fb25b1a81910574ebd5dd60'
CONTEXT='e7777a4a59004c8df9031d446e6d925527c0f86e3c4ddaacbb323a6758582526'
COUNTS={'train':512,'development':32,'reserve':512}
PHASES=('verify','lease','admission','intake','provenance','teachers','engine_exit','export')
POLICY={'sample_count':2,'sample_interval_seconds':1,'commit_headroom_bytes':8*GIB,
        'physical_available_bytes':4*GIB,'intake_seconds':1200,'teacher_seconds':3300,
        'engine_exit_seconds':15,'cutoff_utc':'2026-10-16T13:00:00+00:00'}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):value.update(chunk)
    return value.hexdigest()


def read(path):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    def constant(value):raise ValueError('Nonfinite JSON: '+value)
    with Path(path).open('rb') as stream:raw=stream.read(16*1024**2+1)
    require(len(raw)<=16*1024**2,'Metadata too large')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def append(path,value):
    with Path(path).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def utc():return datetime.now(timezone.utc).isoformat()


def binding(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}


def bound(item):
    require(type(item) is dict and set(item)=={'path','sha256'},'Malformed binding')
    path=Path(item['path']);require(path.is_absolute() and '..' not in path.parts,'Nonabsolute/traversal binding')
    require(str(path.absolute())==str(path.resolve()) and path.is_file(),'Missing file or symlink substitution')
    require(sha(path)==item['sha256'],'Bound bytes changed: '+str(path));return path


def paths_for(output):
    output=Path(output)
    return {name:output.with_name(output.name+'-operational-'+suffix) for name,suffix in (
        ('intent','intent.json'),('phases','phases.jsonl'),('samples','admission.jsonl'),
        ('pids','engine-pids.jsonl'),('closed','closed.json'))}


def verify(plan):
    require(plan.get('schema')==SCHEMA and plan.get('policy')==POLICY,'Operational policy changed')
    require(plan.get('driver_sha256')==sha(Path(__file__)),'Driver source changed')
    require(plan.get('scientific_protocol_sha256')==SCIENCE and plan.get('counts')==COUNTS
        and plan.get('teacher_requests')==3168,'Scientific contract changed')
    require(plan.get('filelock_version')==importlib.metadata.version('filelock')=='4.2.0','Filelock version changed')
    files=plan['bindings']
    require(set(files)=={'driver','builder','scientific_protocol','intake','teacher','proposal','closed_held_worker','root_changed_context'},'Incomplete source/context bindings')
    expected={'driver':plan['driver_sha256'],'scientific_protocol':SCIENCE,'intake':INTAKE,
        'teacher':TEACHER,'proposal':PROPOSAL,'closed_held_worker':WORKER,'root_changed_context':CONTEXT}
    for key,value in expected.items():require(files[key]['sha256']==value,'Fixed binding differs: '+key)
    paths={name:bound(item) for name,item in files.items()}
    require(paths['driver']==Path(__file__).resolve(),'Another driver source')
    require(paths['scientific_protocol']==ROOT/'experiments/chess-queen-coach-counterfactual-v1/intake-protocol.json'
        and paths['intake']==ROOT/'scripts/chess_queen_coach_counterfactual_intake_v1.py'
        and paths['teacher']==ROOT/'scripts/chess_queen_coach_counterfactual_teacher_v1.py','Scientific paths changed')
    proposal=read(paths['proposal'])
    require(plan.get('failed_attempt')==proposal['failed_attempt']['bindings'],'Failed-attempt bindings changed')
    for item in plan['failed_attempt']:bound({key:item[key] for key in ('path','sha256')})
    require(plan.get('output')==str(ROOT/'data/private/chess-queen-coach-counterfactual-recovery-v2')
        and plan.get('lock')==str(ROOT/'data/private/chess-gpu-owner.lock'),'Output/lease changed')
    old=read(paths['scientific_protocol'])
    require(old.get('counts')==COUNTS and old.get('implementation_sha256')==INTAKE
        and old['teacher_implementation']['sha256']==TEACHER,'Frozen science mismatch')
    for key,oldkey in (('intake_seconds','maximum_cpu_seconds'),('teacher_seconds',None),('cutoff_utc','cutoff_utc')):
        actual=old['teacher']['phase_maximum_seconds'] if oldkey is None else old[oldkey]
        require(actual==POLICY[key],'Scientific deadline mismatch')
    require(old['cpu_start_commit_bytes']==8*GIB and old['cpu_running_commit_bytes']==6*GIB
        and old['cpu_physical_bytes']==4*GIB,'Scientific reserve mismatch')
    worker=read(paths['closed_held_worker']);context=read(paths['root_changed_context'])
    require(worker.get('schema')=='chess.gpu-worker.v1' and worker.get('status')=='failed'
        and worker.get('exit_code')==1 and worker.get('child_pid')==53276
        and worker.get('arguments_sha256')==ARGUMENTS and worker.get('child_exited_before_lease_release') is True,
        'Current held worker is not the exact closed failure')
    require(worker.get('lock')==plan['lock'],'Closed owner used another lease')
    require(context.get('schema')=='chess.closed-owner-and-changed-context.v1'
        and context.get('worker_sha256')==WORKER and context.get('worker')==str(paths['closed_held_worker'])
        and context.get('child_pid')==53276 and context.get('child_pid_absent_OpenProcess_error')==87
        and context.get('lease_probe_free') is True,'Changed-context record differs')
    samples=context.get('CPU_samples',[])
    require(len(samples)==2 and all(type(row.get(key)) is int and row[key]>=POLICY[key] for row in samples
        for key in ('physical_available_bytes','commit_headroom_bytes')),'Root admission observations insufficient')
    require((datetime.fromisoformat(samples[1]['at'])-datetime.fromisoformat(samples[0]['at'])).total_seconds()>=1,
        'Root samples too close')
    return paths


def cpu_sample():
    """Windows read-only CPU counters; no nvidia-smi/model import."""
    class Info(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in (
            'CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache',
            'KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(name,wintypes.DWORD) for name in ('HandleCount','ProcessCount','ThreadCount')]
    fn=ctypes.WinDLL('psapi',use_last_error=True).GetPerformanceInfo
    fn.argtypes=(ctypes.POINTER(Info),wintypes.DWORD);fn.restype=wintypes.BOOL
    info=Info();info.cb=ctypes.sizeof(info)
    if not fn(ctypes.byref(info),info.cb):raise ctypes.WinError(ctypes.get_last_error())
    return {'at':utc(),'physical_available_bytes':int(info.PhysicalAvailable*info.PageSize),
        'commit_headroom_bytes':int((info.CommitLimit-info.CommitTotal)*info.PageSize)}


def alive(pid):
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);api.OpenProcess.restype=wintypes.HANDLE
    api.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD);api.WaitForSingleObject.restype=wintypes.DWORD
    api.CloseHandle.argtypes=(wintypes.HANDLE,);api.CloseHandle.restype=wintypes.BOOL
    handle=api.OpenProcess(0x100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        state=api.WaitForSingleObject(handle,0)
        require(state in (0,258),'Process observation failed');return state==258
    finally:api.CloseHandle(handle)


def owned_children(parent,image):
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
            ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
            ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes=(wintypes.DWORD,wintypes.DWORD);api.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    api.Process32FirstW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry));api.Process32FirstW.restype=wintypes.BOOL
    api.Process32NextW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry));api.Process32NextW.restype=wintypes.BOOL
    api.CloseHandle.argtypes=(wintypes.HANDLE,);api.CloseHandle.restype=wintypes.BOOL
    handle=api.CreateToolhelp32Snapshot(2,0)
    if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    found=[]
    try:
        entry=Entry();entry.dwSize=ctypes.sizeof(entry);ok=api.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            if entry.th32ParentProcessID==parent and entry.szExeFile.casefold()==image.casefold():
                found.append({'pid':int(entry.th32ProcessID),'parent_pid':parent,'image':entry.szExeFile,'observed_at':utc()})
            ok=api.Process32NextW(handle,ctypes.byref(entry))
    finally:api.CloseHandle(handle)
    return found


class EngineObserver:
    def __init__(self,journal,cancel,image):
        self.journal=journal;self.cancel=cancel;self.image=image;self.rows={};self.errors=[];self.stop=threading.Event()
    def sample(self):
        try:
            for row in owned_children(os.getpid(),self.image):
                if row['pid'] not in self.rows:self.rows[row['pid']]=row;append(self.journal,{'event':'owned_engine',**row})
        except Exception as error:
            self.errors.append(type(error).__name__+': '+str(error))
            try:append(self.journal,{'event':'observation_failure','error':self.errors[-1],'at':utc()})
            except Exception as journal_error:self.errors.append('PID error journal: '+type(journal_error).__name__+': '+str(journal_error))
            finally:
                try:
                    if not self.cancel.exists():save(self.cancel,{'reason':'Owned PID observation failed; stop this sequence'})
                except Exception as cancel_error:self.errors.append('Owned cancellation write: '+type(cancel_error).__name__+': '+str(cancel_error))
    def start(self):
        self.sample()
        def watch():
            while not self.stop.wait(.05):
                self.sample()
                if self.errors:return
        self.thread=threading.Thread(target=watch,daemon=True);self.thread.start()
    def finish(self):
        self.stop.set();self.thread.join(timeout=2);require(not self.thread.is_alive(),'PID observer did not stop')
        self.sample();return list(self.rows.values()),list(self.errors)


def load_science():
    sys.path.insert(0,str(ROOT/'scripts'))
    return (importlib.import_module('chess_queen_coach_counterfactual_intake_v1'),
        importlib.import_module('chess_queen_coach_counterfactual_teacher_v1'))


def lease(path):
    from filelock import FileLock
    return FileLock(str(path),timeout=0)


def snapshot(out,plan,protocol):
    directory=out/'operational-sources';directory.mkdir();records=[]
    items=[binding(protocol)]+list(plan['bindings'].values())+[
        {key:row[key] for key in ('path','sha256')} for row in plan['failed_attempt']]
    result={'status':'failed','files':records}
    try:
        for index,item in enumerate(items):
            source=bound(item);target=directory/f'{index:02d}-{source.name}'
            shutil.copyfile(source,target);require(sha(target)==item['sha256'],'Snapshot copy differs')
            records.append({'source':item,'copy':target.name,'sha256':sha(target)})
        result['status']='completed'
    except BaseException as error:result['error']=type(error).__name__+': '+str(error);raise
    finally:save(directory/'manifest.json',result)
    return binding(directory/'manifest.json')


def run(protocol,expected_sha,*,sampler=cpu_sample,is_alive=alive,acquire=lease,
        loader=load_science,observer_factory=EngineObserver,clock=time.monotonic,sleep=time.sleep,now=None):
    """Injection points are for authored CPU tests, never source monkeypatches."""
    protocol=Path(protocol);require(sha(protocol)==expected_sha,'Operational protocol hash differs')
    plan=read(protocol);out=Path(plan['output']);paths=paths_for(out)
    require(not out.exists() and not any(path.exists() for path in paths.values()),'One create-only recovery; no replay')
    require(out.parent.is_dir(),'Private parent directory must already exist')
    save(paths['intent'],{'schema':SCHEMA,'status':'started','at':utc(),'pid':os.getpid(),'argv':sys.argv,
        'scientific_protocol_sha256':SCIENCE,'operational_protocol_sha256':expected_sha,
        'operational_protocol':str(protocol),'output':str(out),'driver_sha256':sha(Path(__file__)),
        'authorization':'One root-dispatched changed-context CPU sequence only; no retry or learned calls'})
    state={name:'not_run' for name in PHASES};current=None;started=clock();monitor=None;owned=[];monitor_errors=[]
    source_paths=None;science=None;teacher=None;active_lease=None;lease_held=False;proof=None
    result={'schema':SCHEMA,'status':'failed','error':None,'owned_engine_exit_verified':False,
        'scientific_protocol_sha256':SCIENCE,'operational_protocol_sha256':expected_sha,
        'corpus_manifest_sha256':None,'closed_held_worker':plan.get('bindings',{}).get('closed_held_worker') if type(plan.get('bindings')) is dict else None,
        'teacher_outcomes':{'not_run':3168},'model_calls':0,'GPU_calls':0,'no_retry':True}
    def cutoff():
        actual=now() if now else datetime.now(timezone.utc)
        require(actual<datetime.fromisoformat(POLICY['cutoff_utc']),'Global13UTC cutoff reached')
        require(not (out/'CANCEL').exists(),'Owned CPU sequence cancelled')
    def phase(name,fn,maximum=None):
        nonlocal current
        current=name;state[name]='active_unknown';at=clock()
        append(paths['phases'],{'phase':name,'status':'intent','at':utc(),'elapsed_seconds':at-started})
        cutoff();value=fn()
        if maximum is not None:require(clock()-at<=maximum,'Phase deadline exceeded: '+name)
        cutoff();state[name]='completed'
        append(paths['phases'],{'phase':name,'status':'completed','at':utc(),'elapsed_seconds':clock()-started})
        return value
    def verify_exit():
        nonlocal owned,monitor_errors,monitor
        if monitor is not None:owned,monitor_errors=monitor.finish();monitor=None
        deadline=clock()+POLICY['engine_exit_seconds']
        while True:
            states={str(row['pid']):is_alive(row['pid']) for row in owned}
            append(paths['pids'],{'event':'owned_exit_observation','at':utc(),'alive':states,'errors':monitor_errors})
            if not any(states.values()):break
            require(clock()<deadline,'Owned engine still alive; no export');sleep(.2)
        require(owned and not monitor_errors,'Owned engine presence/exit not independently observed')
        result['owned_engine_exit_verified']=True
    try:
        source_paths=phase('verify',lambda:verify(plan))
        require(not is_alive(53276),'Previously held child still alive')
        def enter_lease():
            nonlocal active_lease,lease_held
            active_lease=acquire(Path(plan['lock']));active_lease.acquire(timeout=0);lease_held=True
        phase('lease',enter_lease)
        def admission():
            require(not is_alive(53276),'Previously held child still alive')
            previous=None
            for index in range(2):
                if previous is not None:sleep(max(0,1-(clock()-previous)))
                observed=clock();sample=sampler();append(paths['samples'],{'index':index,'monotonic':observed,**sample})
                if previous is not None:require(observed-previous>=1,'Admission samples less than1second apart')
                for key in ('commit_headroom_bytes','physical_available_bytes'):
                    require(type(sample.get(key)) is int and sample[key]>=POLICY[key],'CPU admission reserve: '+key)
                previous=observed
        phase('admission',admission)
        def intake_once():
            nonlocal science,teacher
            science,teacher=loader()
            receipt=science.intake(source_paths['scientific_protocol'],out)
            dataset=read(out/'dataset.json')
            require(receipt.get('status')=='ready_for_teachers' and dataset.get('status')=='ready_for_teachers'
                and dataset.get('shortages')=={key:0 for key in COUNTS}
                and {key:len(value) for key,value in dataset['groups'].items()}==COUNTS,'Incomplete intake; no teachers')
            return dataset
        dataset=phase('intake',intake_once,1200)
        proof=phase('provenance',lambda:snapshot(out,plan,protocol))
        tasks=teacher.tasks_for(dataset)
        require(len(tasks)==3168 and len({row['case_id'] for row in tasks})==3168,'Full unique3168 task plan required')
        save(out/'operational-teacher-planned.json',{'rows':[{**row,'status':'not_run'} for row in tasks]})
        image=Path(read(source_paths['scientific_protocol'])['teacher']['binary']['path']).name
        monitor=observer_factory(paths['pids'],out/'CANCEL',image);monitor.start()
        def teach_once():
            teacher.teachers(source_paths['scientific_protocol'],out)
            labels=read(out/'teachers.json');closed=read(out/'teacher-closed.json')
            recovered=teacher.recover(tasks,out/'teacher-journal.jsonl')
            require(labels.get('planned')==3168 and labels.get('all_planned_completed') is True
                and labels.get('statuses')=={'completed':3168} and labels.get('rows')==recovered
                and closed.get('teachers_sha256')==sha(out/'teachers.json'),'Incomplete/incoherent teacher outcomes; no export')
        phase('teachers',teach_once,3300)
        phase('engine_exit',verify_exit,15)
        def export_once():
            manifest=teacher.export(source_paths['scientific_protocol'],out)
            require(manifest.get('status')=='ready_for_training' and manifest.get('protocol_sha256')==SCIENCE,'Export not ready')
        phase('export',export_once)
        result['status']='completed'
    except BaseException as error:
        if current and state[current]=='active_unknown':state[current]='failed'
        result['error']=type(error).__name__+': '+str(error)
        append(paths['phases'],{'phase':current,'status':'failed','at':utc(),'error':result['error']})
    finally:
        # Failure retention must not dispatch any phase or replay a scientific call.
        def retain_error(label,error):
            result['status']='failed';result.setdefault('finalizer_errors',[]).append(label+': '+type(error).__name__+': '+str(error))
        if monitor is not None:
            try:verify_exit()
            except BaseException as error:retain_error('engine_exit',error)
        if science is not None:
            try:
                out.mkdir(exist_ok=True)
                if proof is None and not (out/'operational-sources').exists():
                    append(paths['phases'],{'phase':'finalizer_source_snapshot','status':'intent','at':utc()})
                    proof=snapshot(out,plan,protocol)
                    append(paths['phases'],{'phase':'finalizer_source_snapshot','status':'completed','at':utc()})
                if teacher is not None and (out/'operational-teacher-planned.json').exists():
                    tasks=read(out/'operational-teacher-planned.json')['rows']
                    tasks=[{key:value for key,value in row.items() if key!='status'} for row in tasks]
                    rows=teacher.recover(tasks,out/'teacher-journal.jsonl')
                    save(out/'operational-teacher-outcomes.json',{'planned':3168,'rows':rows})
                    result['teacher_outcomes']={status:sum(row['status']==status for row in rows) for status in sorted({row['status'] for row in rows})}
            except BaseException as error:retain_error('provenance_or_teacher_recovery',error)
        try:
            if (out/'manifest.json').exists():result['corpus_manifest_sha256']=sha(out/'manifest.json')
            result.update(phases=state,owned_engine_pids=owned,pid_observation_errors=monitor_errors,
                operational_source_snapshot=proof,elapsed_seconds=clock()-started,
                operational_phase_ledger_sha256=sha(paths['phases']),resource_context_lease_held_through_scientific_cleanup=lease_held)
            if lease_held:
                try:active_lease.release();lease_held=False;result['resource_context_lease_released']=True
                except BaseException as error:retain_error('lease_release',error)
            save(paths['closed'],result)
            if out.exists():save(out/'operational-provenance.json',result)
        finally:
            if lease_held:active_lease.release()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args();result=run(args.protocol,args.protocol_sha256)
    print(json.dumps({'status':result['status'],'error':result.get('error')}))
    raise SystemExit(0 if result['status']=='completed' else 2)


if __name__=='__main__':main()
