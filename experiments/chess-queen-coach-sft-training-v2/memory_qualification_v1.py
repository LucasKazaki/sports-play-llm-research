"""Root-only finite memory qualification; TRAIN/spent-dev, never heldout."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_train_v1 as prior
from chess_queen_coach_sft_runtime_v2 import Runtime,checked

PROTOCOL=Path(__file__).with_name('memory-protocol.json')


def qualification_checks(state,boundaries,plan):
    tail=boundaries[-8:]
    def span(key):return max(row[key]for row in tail)-min(row[key]for row in tail)
    available=len(tail)==8 and all(row['process'].get('available')for row in tail)
    private_span=(max(row['process']['private_usage_bytes']for row in tail)-
        min(row['process']['private_usage_bytes']for row in tail))if available else None
    return {'updates_complete':state['updates_completed']==32,
        'presentations_complete':state['presentations_completed']==256,
        'full_prefix_exercised':state['generation'].get('generated_tokens')==1024,
        'no_unknown_or_missing':all(row['status']=='backward_completed'for row in state['rows']),
        'all_optimizer_calls_complete':all(row['status']=='completed'for row in state['optimizer_rows']),
        'frozen_storage_identical':state.get('frozen_storage',{}).get('identical')is True,
        'adapter_changed':bool(state.get('adapter_before'))and bool(state.get('adapter_after'))and state['adapter_before']!=state['adapter_after'],
        'two_cleanups_preserve_live_tensors':len(state['preservation'])==2 and
            all(row['before']==row['after']and row['before']['gradient_tensors']==144 for row in state['preservation']),
        'all_guards_passed':state.get('resource_failure')is None,
        'process_tail_plateau':available and private_span<=plan['qualification']['maximum_private_tail_span_bytes'],
        'cuda_allocated_tail_plateau':len(tail)==8 and span('cuda_allocated_bytes')<=plan['qualification']['maximum_cuda_tail_span_bytes'],
        'cuda_reserved_tail_plateau':len(tail)==8 and span('cuda_reserved_bytes')<=plan['qualification']['maximum_cuda_tail_span_bytes']}


def mark_unknown(state):
    for row in state['rows']+state['optimizer_rows']:
        if row['status']=='call_started':row['status']='active_unknown'
    if state['generation']['status']=='call_started':state['generation']['status']='active_unknown'


def verify_plan(path):
    plan=checked.nf4.base.read_json(path)
    if plan['implementation_sha256']!=checked.nf4.base.digest(Path(__file__)):
        raise ValueError('Frozen qualification source differs')
    for binding in plan['dependencies']:checked.nf4.binding(binding)
    pilot=prior.verify_protocol(checked.nf4.binding(plan['pilot_protocol']))
    if plan['qualification']['updates']!=32 or plan['qualification']['presentations']!=256:
        raise ValueError('Fixed qualification budget differs')
    failed=checked.nf4.base.read_json(checked.nf4.binding(plan['previous_failure']))
    worker=checked.nf4.base.read_json(checked.nf4.binding(plan['previous_closed_worker']))
    journal=[json.loads(line)for line in checked.nf4.binding(plan['previous_journal']).read_text().splitlines()]
    starts=[(row['step'],row['micro'])for row in journal if row['status']=='call_started']
    completed=[(row['step'],row['micro'])for row in journal if row['status']=='backward_completed']
    if (failed['status']!='failed'or failed['updates_completed']!=20 or len(completed)!=160
        or set(starts)-set(completed)!={(21,0)}or not worker['child_exited_before_lease_release']):
        raise ValueError('Closed failed-attempt provenance differs')
    return plan,pilot


def run(plan,pilot,protocol,out):
    if out.exists():raise ValueError('Qualification directory is create-only')
    out.mkdir(parents=True)
    rows=prior.read_rows(checked.nf4.binding(pilot['data']['train']),True)
    dev=prior.read_rows(checked.nf4.binding(pilot['data']['development']),True)
    if len(rows)!=2048 or len(dev)!=64:raise ValueError('Frozen TRAIN/dev quota differs')
    selected=[row for row in dev if row['case_id']==plan['qualification']['spent_development_case_id']]
    if len(selected)!=1:raise ValueError('Fixed already-spent development case differs')
    spent=checked.nf4.base.read_json(checked.nf4.binding(plan['previous_spent_generation']))
    if spent['input']['fen']!=selected[0]['input']['fen']or len(spent['generated_tokens'])!=1024:
        raise ValueError('Bound previous full-prefix generation differs')
    order=list(range(2048));random.Random(pilot['training']['seed']).shuffle(order)
    state={'schema':'chess.queen-coach-memory-qualification.v1','status':'attempt_started',
        'protocol_sha256':checked.nf4.base.digest(protocol),'updates_completed':0,'presentations_completed':0,
        'partial_accumulation':0,'planned_updates':32,'planned_presentations':256,
        'generation':{'case_id':selected[0]['case_id'],'status':'not_run'},
        'rows':[{'step':index//8+1,'micro':index%8,'case_id':rows[source]['case_id'],'status':'not_run'}
            for index,source in enumerate(order[:256])],
        'optimizer_rows':[{'step':step,'status':'not_run'}for step in range(1,33)],
        'preservation':[],'resource_failure':None,
        'claim':'Software memory qualification only. Discard adapter, no selection or heldout calls.',
        'prior_attempt':'20 confirmed updates/160 confirmed backward presentations; step21/micro0 active_unknown.'}
    prior.save(out/'qualification.json',state)
    guarded=copy.deepcopy(pilot);guarded['phase_maximum_seconds']['memory-qualification']=plan['qualification']['maximum_seconds']
    guard,samples,_=prior.guard_for(guarded,out/'memory-qualification.json')
    boundaries=[]
    try:
        runtime=Runtime(pilot,guard);runtime.memory_journal=out/'memory-lifetime.jsonl'
        runtime.load();torch=runtime.torch
        runtime.release_inactive('after_model_load')
        state['adapter_before']=checked.streamed_hash(torch,runtime.parameters,guard)
        identity={'condition':'discarded-memory-qualification','step':0,'parameter_sha256':state['adapter_before']}
        state['generation']['status']='call_started';prior.save(out/'qualification.json',state)
        raw=runtime.infer(selected[0],identity);prior.save(out/'spent-development-raw.json',raw)
        state['generation'].update(status=raw['status'],generated_tokens=len(raw.get('generated_tokens',[])),
            receipt_sha256=checked.nf4.base.digest(out/'spent-development-raw.json'))
        prior.save(out/'qualification.json',state)
        if raw['status']=='failed':raise RuntimeError('First generator failure: '+raw.get('error','unknown'))
        if len(raw.get('generated_tokens',[]))!=1024:
            raise ValueError('Fixed spent-dev request did not exercise the complete1024-token prefix; stop qualification')
        runtime.release_inactive('after_spent_full_prefix_generation')
        tokens=[runtime.tokenize(row)for row in rows]
        optimizer=torch.optim.AdamW([value for _,value in runtime.parameters],lr=.0001,
            betas=(.9,.999),eps=1e-8,weight_decay=.01,foreach=False)
        config=pilot['training']
        for step in range(1,33):
            guard();optimizer.zero_grad(set_to_none=True);state['partial_accumulation']=0
            warm=config['warmup_updates'];factor=step/warm if step<=warm else(.1+.9*.5*(1+math.cos(math.pi*(step-warm)/(256-warm))))
            for group in optimizer.param_groups:group['lr']=config['learning_rate']*factor
            for micro in range(8):
                index=(step-1)*8+micro;source=order[index];row=state['rows'][index]
                row.update(status='call_started',started_at=datetime.now(timezone.utc).isoformat())
                prior.save(out/'qualification.json',state);prior.append(out/'calls.jsonl',row)
                loss=runtime.loss(rows[source],tokens[source],training=True)
                row.update(status='backward_completed',loss=loss,completed_at=datetime.now(timezone.utc).isoformat())
                state['presentations_completed']+=1;state['partial_accumulation']+=1
                prior.append(out/'calls.jsonl',row);prior.save(out/'qualification.json',state)
                check_live=(step,micro)in((1,7),(32,7))
                before=runtime.live_hashes()if check_live else None
                runtime.release_inactive(f'after_returned_backward_step{step}_micro{micro}')
                if check_live:
                    after=runtime.live_hashes();record={'step':step,'micro':micro,'before':before,'after':after}
                    state['preservation'].append(record);prior.save(out/'qualification.json',state)
                    if before!=after:raise ValueError('Inactive-cache cleanup changed a live tensor')
            runtime.verify_gradients();torch.nn.utils.clip_grad_norm_([value for _,value in runtime.parameters],1.)
            event=state['optimizer_rows'][step-1];event['status']='call_started'
            prior.save(out/'qualification.json',state);prior.append(out/'calls.jsonl',event)
            optimizer.step();torch.cuda.synchronize()
            event.update(status='completed',completed_at=datetime.now(timezone.utc).isoformat())
            state.update(updates_completed=step,partial_accumulation=0)
            prior.append(out/'calls.jsonl',event);prior.save(out/'qualification.json',state)
            optimizer.zero_grad(set_to_none=True)
            boundary=runtime.release_inactive(f'after_optimizer_step{step}')
            boundaries.append(boundary);prior.save(out/'update-memory.json',boundaries)
        state['frozen_storage']=runtime.verify_frozen()
        state['adapter_after']=checked.streamed_hash(torch,runtime.parameters,guard)
        state['checks']=qualification_checks(state,boundaries,plan)
        state['status']='passed'if all(state['checks'].values())else'failed'
        prior.save(out/'qualification.json',state)
        if state['status']!='passed':raise ValueError('Fixed memory qualification checks did not all pass')
    except Exception as error:
        mark_unknown(state);state.update(status='failed',error=type(error).__name__+': '+str(error))
        if 'reserve'in str(error).lower():state['resource_failure']=state['error']
        prior.save(out/'failure.json',state);prior.save(out/'qualification.json',state);raise
    finally:prior.save(out/'resources.json',samples)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=PROTOCOL);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Qualification output must be new')
    try:
        plan,pilot=verify_plan(args.protocol);run(plan,pilot,args.protocol,args.out)
    except Exception as error:
        args.out.mkdir(parents=True,exist_ok=True)
        if not(args.out/'failure.json').exists():prior.save(args.out/'failure.json',{
            'status':'failed','stage':'protocol_or_data_setup','error':type(error).__name__+': '+str(error),
            'planned_updates':32,'planned_presentations':256,'planned_raw_responses':1,'model_calls_started':False})
        raise


if __name__=='__main__':main()
