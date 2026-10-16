"""Serial cold requests, each in its own explicit creator-owned Windows job.

The coordinator never owns a GPU lease or imports a model runtime. All actual
model work belongs to the pinned direct-base worker and unchanged cold child.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
import argparse, hashlib, json, os, subprocess, sys, time

ROOT=Path(__file__).resolve().parents[2]
TASK=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')
DAY=ROOT/'experiments/chess-queen-coach-daytime-v1'
sys.path.insert(0,str(DAY));sys.path.insert(0,str(ROOT/'scripts'))
import direct_launch_contract as launch_contract
from filelock import FileLock
GENERATION={'max_new_tokens':1024,'maximum_seconds':180,'temperature':0,'seed':20260823,
    'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'}
WORKER_SHA='fe4ce0abb0f6be934f2b78681115ec0aa0c9c85e2ef54a6955dc2e6778103ae8'
CHILD_SHA='e901e78c468754e952c4b1c7f9d3dbf2a165c66d29f86cb46ea53b235a15544b'

def require(value,message):
    if not value:raise ValueError(message)

def no_torch():require('torch' not in sys.modules,'Coordinator must never import Torch')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path):
    path=Path(path);return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)}
def bound(item):
    path=Path(item['path']);path=path if path.is_absolute() else ROOT/path
    require(digest(path)==item['sha256'],'Pinned file changed: '+str(path));return path

def write(path,value,create=False):
    path=Path(path);temporary=path if create else path.with_suffix(path.suffix+'.tmp')
    with temporary.open('x' if create else 'w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    if not create:os.replace(temporary,path)

def packet_sha(packet):return hashlib.sha256(json.dumps(packet,sort_keys=True).encode()).hexdigest()

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

def verify(plan,protocol,review,root_read):
    no_torch();require(plan['schema']=='chess.flat-cold-phase.v1','Wrong flat schema')
    require(review.get('status')=='passed' and review.get('model_dispatch_permitted') is True
        and review.get('protocol_sha256')==digest(protocol),'Exact independent source/plan GO required')
    require(root_read.get('status')=='complete_root_source_and_plan_read'
        and root_read.get('protocol',{}).get('sha256')==digest(protocol),'Exact root complete read required')
    require(plan['implementation_sha256']==digest(__file__),'Coordinator source differs')
    require(plan['child_implementation_sha256']==CHILD_SHA and bound(plan['child_script']).resolve()==
        (ROOT/'scripts/chess_queen_coach_counterfactual_cold_child_v1.py').resolve(),'Unchanged cold child required')
    require(plan['owned_worker_source']['sha256']==WORKER_SHA,'Unchanged worker required')
    launch_contract.environment(plan,bound,read)
    for item in plan['dependencies']:bound(item)
    old=read(bound(plan['frozen_science_protocol']))
    require(plan['model_runtime']==old['model_runtime'] and plan['raw_provenance']==old['raw_provenance']
        and plan['conditions']==old['conditions'],
        'Runtime/numerics/provenance must equal the frozen prior science')
    require(plan['model_runtime']['generation']==GENERATION,'Generation changed')
    require(plan['mode'] in ('qualification','heldout'),'Wrong mode')
    expected=450 if plan['mode']=='qualification' else 4500
    require((plan['phase_maximum_seconds'],plan['child_maximum_seconds'],plan['worker_seconds'],
        plan['per_request_external_seconds'],plan['external_maximum_seconds'])==(expected,210,240,270,expected+60),
        'Frozen budgets changed')
    require(plan['cutoff_utc']=='2026-10-16T22:00:00+00:00','Global cutoff changed')
    require(datetime.now(timezone.utc)<datetime.fromisoformat(plan['admission_latest_utc']),'Admission closed')
    if plan['mode']=='heldout':
        q=read(bound(plan['successful_qualification']));a=read(bound(plan['qualification_audit']))
        qp=read(bound(plan['qualification_protocol']))
        require(q.get('status')=='passed' and q.get('planned')==q.get('completed_children')==2
            and q.get('mode')=='qualification' and q.get('all_children_closed') is True
            and q.get('outer_torch_imported') is False and q.get('labels_opened') is False
            and q.get('protocol_sha256')==plan['qualification_protocol']['sha256']
            and a.get('status')=='passed' and a.get('qualification_sha256')==plan['successful_qualification']['sha256']
            and a.get('protocol_sha256')==plan['qualification_protocol']['sha256'],'Actual flat two-call audit required')
        for key in ('implementation_sha256','child_implementation_sha256','model_runtime','raw_provenance',
            'owned_worker_source','interpreters','cpu_environment_parity'):
            require(qp[key]==plan[key],'Qualification source/runtime identity differs')
        require([row['identity'] for row in q['rows']]==[plan['conditions']['baseline'],plan['conditions']['selected']],
            'Both actual condition identities must be cold qualified')
    no_torch()

def tasks(plan):
    rows=[json.loads(line) for line in bound(plan['input_rows']).read_text(encoding='utf-8').splitlines() if line.strip()]
    count=2 if plan['mode']=='qualification' else 48
    require(len(rows)==len({row['case_id'] for row in rows})==count,'Exact input denominator required')
    for row in rows:
        require(set(row)=={'case_id','group_id','mode','input'} and set(row['input']) in
            ({'fen'},{'fen','selected_uci'}),'Only current FEN/optional selected move')
        require(row['mode'] in (('free','selected') if plan['mode']=='qualification' else ('free','selected_a','selected_b'))
            and set(row['input'])==({'fen'} if row['mode']=='free' else {'fen','selected_uci'}),'Mode/input differs')
    if plan['mode']=='qualification':
        require(len(plan['assignments'])==2 and [row['mode'] for row in rows]==['free','selected'],'Exactly two legacy spent modes/free then selected required')
        require([item['case_id'] for item in plan['assignments']]==[row['case_id'] for row in rows],'Assignment order differs')
        return [(item['condition'],row,plan['conditions'][item['condition']]) for row,item in zip(rows,plan['assignments'])]
    require(list(plan['conditions'])==['baseline','selected'],'Fixed ordered baseline/selected required')
    require(len({row['group_id'] for row in rows})==16,'Sixteen distinct game groups required')
    require(len({(row['group_id'],row['mode']) for row in rows})==48
        and all({row['mode'] for row in rows if row['group_id']==group}=={'free','selected_a','selected_b'}
            for group in {row['group_id'] for row in rows}),'Exactly three modes per game required')
    for group in {row['group_id'] for row in rows}:
        triplet=[row for row in rows if row['group_id']==group]
        require(len({row['input']['fen'] for row in triplet})==1
            and len({row['input']['selected_uci'] for row in triplet if row['mode']!='free'})==2,
            'Group current position or selected roles differ')
    return [(name,row,identity) for name,identity in plan['conditions'].items() for row in rows]

def supervise(process):
    value={'retained_wrapper_present':process is not None,'unseen_tree_closure_inferred':False,'cleanup_errors':[]}
    if process is None:return {**value,'known_wrapper_exit':False}
    value['retained_wrapper_pid']=process.pid
    try:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        value['known_wrapper_exit']=process.poll() is not None
    except BaseException as error:
        value['known_wrapper_exit']=False;value['cleanup_errors'].append(type(error).__name__+': '+str(error))
    return value

def launch(command,folder,cancel,phase_deadline,cutoff):
    process=None;primary=None;started=time.monotonic();timed_out=False;closed=None;cancel_write_error=None
    write(folder/'launch-intent.json',{'command':command,'command_sha256':hashlib.sha256(json.dumps(command).encode()).hexdigest(),
        'at_utc':datetime.now(timezone.utc).isoformat()},create=True)
    try:
        with (folder/'process.log').open('xb') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            write(folder/'launch-started.json',{'retained_wrapper_pid':process.pid},create=True)
            deadline=min(started+270,phase_deadline)
            while True:
                if cancel.exists() or time.monotonic()>=deadline or datetime.now(timezone.utc)>=cutoff:
                    timed_out=True
                    if not cancel.exists():write(cancel,{'reason':'phase/request/global deadline'},create=True)
                    # Let the pinned cooperative child observe cancellation before wrapper cleanup.
                    try:process.wait(timeout=max(.001,min(30.,(cutoff-datetime.now(timezone.utc)).total_seconds())))
                    except subprocess.TimeoutExpired:pass
                    raise RuntimeError('Owned flat phase/request cancellation or deadline')
                if process.poll() is not None:break
                time.sleep(.05)
        require(process.returncode==0,'Cold owned worker returned nonzero')
        return {'returncode':process.returncode,'elapsed_seconds':time.monotonic()-started}
    except BaseException as error:
        primary=type(error).__name__+': '+str(error)
        try:
            if not cancel.exists():write(cancel,{'reason':'first owned launch/postprocessing failure'},create=True)
        except BaseException as nested:cancel_write_error=type(nested).__name__+': '+str(nested)
        raise
    finally:
        closed=supervise(process)
        closed.update(primary_error=primary,timed_out=timed_out,cancellation_write_error=cancel_write_error,
            elapsed_seconds=time.monotonic()-started)
        try:write(folder/'launch-closed.json',closed,create=True)
        except BaseException:
            if primary is None:raise
        if closed['cleanup_errors'] and primary is None:raise RuntimeError('Owned wrapper cleanup unresolved')

def check_case(plan,protocol,row,identity,folder,args,process):
    worker=read(folder/'worker.json');child=read(folder/'child/closed.json');raw_path=folder/'child/raw.json'
    launch_contract.owned_worker(worker,plan['owned_worker_source'],plan['interpreters'])
    require(worker['arguments_sha256']==hashlib.sha256(json.dumps(args).encode()).hexdigest()
        and worker['maximum_seconds_after_GO']==240
        and str(worker['script']).replace('\\','/')==args[0].replace('\\','/'),'Exact cold worker vector required')
    before=worker['ownership']['before_go']
    require(process['returncode']==0 and child.get('status')=='passed'
        and child.get('pid')==worker['child_pid'] and child.get('parent_pid')==before['creator_identity']['pid']
        and child.get('source_sha256')==CHILD_SHA and child.get('protocol_sha256')==digest(protocol)
        and child.get('case_id')==row['case_id'] and child.get('identity')==identity
        and child.get('requested_input_sha256')==packet_sha(row['input'])
        and child.get('generation_requests_started')==1 and child.get('in_owned_ancestor_job') is True
        and child.get('frozen_storage',{}).get('identical') is True
        and child.get('raw_saved_before_postprocessing') is True
        and raw_path.exists() and child.get('raw_sha256')==digest(raw_path),'Closed exact raw child binding required')
    raw=read(raw_path)
    require(raw_provenance(raw,row,identity,plan)
        and all(raw.get('settings',{}).get(key)==value for key,value in GENERATION.items()),'Raw input/adapter/generation differs')
    return {'response_path':str(raw_path),'response_sha256':digest(raw_path),'child_receipt':bind(folder/'child/closed.json'),
        'worker':bind(folder/'worker.json'),'raw_status':raw['status'],'raw_finish_reason':raw.get('finish_reason')}

def sample_resources():
    from chess_native_resources import windows_sample
    return asdict(windows_sample())

def floors(sample,stage):
    from chess_native_resources import Sample,Policy,reasons,GIB
    policy=Policy(start_physical_available_bytes=6*GIB,start_commit_headroom_bytes=10*GIB,start_gpu_free_bytes=10*GIB,
        stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=4*GIB,stop_gpu_free_bytes=GIB)
    require(not reasons(Sample(**sample),policy,stage),'Unchanged resource floor rejected '+stage)

def score(plan,rows,out):
    import chess_queen_coach_counterfactual_train_v1 as scoring
    write(out/'truth-access.json',{'status':'opening_reference_parse','reference':plan['heldout_references']},create=True)
    references=scoring.references(bound(plan['heldout_references']),rows)
    write(out/'truth-access.json',{'status':'references_opened','reference':plan['heldout_references']})
    for name in ('baseline','selected'):
        panel=read(out/(name+'.json'));write(out/(name+'-score.json'),scoring.score_panel(rows,panel,references),create=True)
    no_torch()

def run(plan,protocol,out,review,root_read,launcher=launch,sampler=sample_resources,floor_check=floors,scorer=score):
    require(Path(out).resolve()==Path(plan['actual_out']).resolve(),'Exact prospective output path required')
    require(not out.exists(),'Create-only flat phase; no retry');queue=tasks(plan)
    out.mkdir(parents=True);started=time.monotonic();deadline=started+plan['phase_maximum_seconds']
    ledger=[{'condition':name,'case_id':row['case_id'],'group_id':row['group_id'],'mode':row['mode'],
        'input_sha256':packet_sha(row['input']),'identity':identity,'status':'not_run'} for name,row,identity in queue]
    result={'schema':'chess.flat-cold-result.v1','status':'started','mode':plan['mode'],'protocol_sha256':digest(protocol),
        'planned':len(queue),'completed_children':0,'rows':ledger,'labels_opened':False,'outer_torch_imported':False}
    write(out/'closed.json',result,create=True);process=None;cp_path=TASK/'work/daytime/checkpoint.json';marked=False
    primary=None;storage_errors=[];samples=[]
    try:
        verify(plan,protocol,review,root_read)
        cp=read(cp_path);require(cp['active_gpu_job'] is None,'Another root phase active')
        cp.update(active_gpu_job={'stage':'flat_'+plan['mode'],'out':str(out),'protocol':bind(protocol)})
        write(cp_path,cp);marked=True;cutoff=datetime.fromisoformat(plan['cutoff_utc'])
        sources=out/'executed-sources';sources.mkdir();copies=[]
        for index,path in enumerate([Path(__file__),Path(protocol),*[bound(item) for item in plan['dependencies']]]):
            data=path.read_bytes();target=sources/f'{index:03d}-{path.name}'
            with target.open('xb') as stream:stream.write(data)
            copies.append({'source':str(path),'copy':bind(target)})
        write(sources/'manifest.json',copies,create=True)
        baseline=sampler();samples.append({'stage':'before_any_child',**baseline});floor_check(baseline,'start')
        for index,((name,row,identity),slot) in enumerate(zip(queue,ledger)):
            no_torch();require(time.monotonic()<deadline and datetime.now(timezone.utc)<cutoff
                and not (out/'CANCEL').exists(),'Whole/global phase ended')
            with FileLock(str(ROOT/'data/private/chess-gpu-owner.lock'),timeout=0):pass
            before=sampler();samples.append({'stage':'before_child','index':index,**before});floor_check(before,'start')
            folder=out/f'{index:03d}-{name}';folder.mkdir()
            request={'protocol_sha256':digest(protocol),'row':row,'identity':identity}
            write(folder/'request.json',request,create=True)
            args=[str(Path(plan['child_script']['path'])).replace('\\','/'),'--protocol',str(Path(protocol).resolve()),
                '--request',str((folder/'request.json').resolve()),'--out',str((folder/'child').resolve()),
                '--parent-cancel',str((out/'CANCEL').resolve())]
            command=[str(ROOT/'.venv-soccernet/Scripts/python.exe'),str(bound(plan['owned_worker_source'])),
                '--receipt',str(folder/'worker.json'),'--maximum-seconds','240','--',*args]
            slot.update(status='active_unknown',request=bind(folder/'request.json'),worker_arguments=args)
            write(out/'closed.json',result)
            process=launcher(command,folder,out/'CANCEL',deadline,cutoff)
            if (folder/'child/raw.json').exists():slot.update(response_path=str(folder/'child/raw.json'),response_sha256=digest(folder/'child/raw.json'))
            accepted={**slot,**check_case(plan,protocol,row,identity,folder,args,process),'status':'completed'}
            write(folder/'accepted.json',accepted,create=True);slot.clear();slot.update(accepted)
            result['completed_children']+=1;write(out/'closed.json',result)
            after=sampler();samples.append({'stage':'after_closed_child','index':index,**after});floor_check(after,'running')
            if plan['mode']=='qualification':
                require(after['commit_total_bytes']-baseline['commit_total_bytes']<=1024**3,'Qualification global commit growth >1GiB')
        # Do not expose truth until every actual request and its worker/job closes.
        require(result['completed_children']==len(queue) and all(row['status']=='completed' for row in ledger),'Complete raw panels required')
        if plan['mode']=='heldout':
            rows=[row for name,row,identity in queue if name=='baseline']
            for name in ('baseline','selected'):
                panel={'status':'completed','planned':48,'condition':name,'model_identity':plan['conditions'][name],
                    'protocol_sha256':digest(protocol),'rows':[dict(row,status=row['raw_status']) for row in ledger if row['condition']==name]}
                write(out/(name+'.json'),panel,create=True)
            result.update(labels_opened=None,truth_access_state='entered_scoring_truth_access_unknown')
            write(out/'closed.json',result)
            scorer(plan,rows,out);result.update(labels_opened=True,truth_access_state='references_opened_scoring_completed')
        result.update(status='passed',all_children_closed=True)
    except BaseException as error:
        primary=type(error).__name__+': '+str(error);result.update(status='failed',error=primary)
    finally:
        if result.get('truth_access_state')=='entered_scoring_truth_access_unknown':
            try:
                truth=out/'truth-access.json'
                if truth.exists() and read(truth).get('status')=='references_opened':
                    result.update(labels_opened=True,truth_access_state='references_opened_scoring_failed')
            except BaseException as error:
                storage_errors.append('truth_access: '+type(error).__name__+': '+str(error));result['status']='failed'
        result.update(elapsed_seconds=time.monotonic()-started,outer_torch_imported='torch' in sys.modules,
            storage_errors=storage_errors,replay_permitted=False,individual_descendant_identity_claim=False)
        for path,value in ((out/'resources.json',samples),(out/'closed.json',result)):
            try:write(path,value)
            except BaseException as error:storage_errors.append(str(path)+': '+type(error).__name__+': '+str(error));result['status']='failed'
        if marked:
            try:
                cp=read(cp_path);require(cp.get('active_gpu_job',{}).get('out')==str(out),'Root checkpoint owner changed')
                # Actual root closure/audit owns clearing this even on success.
                cp['phase']='flat phase closed; root explicit-job/lease audit next';write(cp_path,cp)
            except BaseException as error:storage_errors.append('checkpoint: '+type(error).__name__+': '+str(error));result['status']='failed'
        if storage_errors:
            try:write(out/'closed.json',result)
            except BaseException:pass
    return result

def main():
    parser=argparse.ArgumentParser()
    for name in ('protocol','out','review','source-read'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=run(read(args.protocol),args.protocol,args.out,read(args.review),read(args.source_read))
    print(json.dumps({'status':result['status'],'planned':result['planned'],'completed_children':result['completed_children'],
        'labels_opened':result['labels_opened'],'elapsed_seconds':result['elapsed_seconds'],'closed':bind(args.out/'closed.json')}))
    raise SystemExit(0 if result['status']=='passed' else 2)

if __name__=='__main__':main()
