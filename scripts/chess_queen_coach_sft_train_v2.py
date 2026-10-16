"""Durable root-only Queen coach pilot training and closed-heldout execution."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time

import chess_queen_coach_sft_eval_v1 as scoring
from chess_queen_coach_sft_runtime_v2 import Runtime,checked

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'experiments/chess-queen-coach-sft-training-v2/protocol.json'
STEPS=(0,64,128,256)


def read_rows(path,targets):
    rows=[json.loads(line)for line in Path(path).read_text(encoding='utf-8-sig').splitlines()if line.strip()]
    seen=set();groups={}
    for row in rows:
        keys={'case_id','group_id','mode','input'}|({'response'}if targets else set())
        if set(row)!=keys:raise ValueError('Unexpected corpus row fields')
        if not isinstance(row['case_id'],str)or row['case_id']in seen:raise ValueError('Missing/duplicate case ID')
        seen.add(row['case_id'])
        if not isinstance(row['group_id'],str)or row['mode']not in('free','selected'):raise ValueError('Invalid group/mode')
        packet,_=checked.nf4.base.input_packet(row['input'])
        if ('selected_uci'in packet)!=(row['mode']=='selected'):raise ValueError('Input/mode differs')
        if targets and(not isinstance(row['response'],str)or not row['response']):raise ValueError('Missing complete target')
        groups.setdefault(row['group_id'],[]).append(row)
    for pair in groups.values():
        if len(pair)!=2 or {row['mode']for row in pair}!={'free','selected'}or len({row['input']['fen']for row in pair})!=1:
            raise ValueError('Every game requires one matched free/selected pair')
    return rows


def references(path,rows):
    values=[json.loads(line)for line in Path(path).read_text(encoding='utf-8-sig').splitlines()if line.strip()]
    result={value['case_id']:value for value in values}
    if len(result)!=len(values)or set(result)!={row['case_id']for row in rows}:raise ValueError('Reference IDs differ')
    for row in rows:
        reference=result[row['case_id']]
        if reference['group_id']!=row['group_id']:raise ValueError('Reference group differs')
        if row['mode']=='selected'and reference['selected_uci']!=row['input']['selected_uci']:raise ValueError('Selected input/reference differs')
    return result


def selection_key(condition):
    counts=condition['counts'];nll=condition['response_token_nll']
    legal=counts['accepted_best_legal']
    return (legal==8,legal,counts['free_critical_3ply_agreement'],counts['free_best_agreement'],-nll,-condition['step'])


def select(conditions):
    eligible=[value for value in conditions if value.get('status')=='completed'
        and value.get('raw_planned')==8 and value.get('raw_completed')==8
        and value.get('nll_completed')==64 and math.isfinite(value['response_token_nll'])]
    if not eligible:raise ValueError('No complete development condition available for selection')
    return max(eligible,key=selection_key)


def verify_selection(value,protocol):
    if value.get('status')!='selected'or value['protocol_sha256']!=checked.nf4.base.digest(protocol):
        raise ValueError('Saved source-bound dev selection is required')
    chosen=select(value['conditions'])
    baseline=[row for row in value['conditions']if row['step']==0]
    if len(baseline)!=1 or value['selected']!=chosen['identity']or value['baseline']!=baseline[0]['identity']:
        raise ValueError('Saved selection disagrees with frozen development selector')
    for label in('baseline','selected'):
        identity=value[label]
        if checked.nf4.base.digest(Path(identity['path']))!=identity['sha256']:
            raise ValueError('Selected adapter checkpoint bytes differ')


def verify_protocol(path):
    plan=checked.nf4.base.read_json(path)
    if plan['implementation_sha256']!=checked.nf4.base.digest(Path(__file__)):raise ValueError('Frozen trainer source changed')
    for item in plan['dependencies']:checked.nf4.binding(item)
    for item in plan['data'].values():checked.nf4.binding(item)
    if plan['training']['updates']!=256 or plan['training']['gradient_accumulation']!=8:
        raise ValueError('Pilot update budget differs')
    if plan['generation']['max_new_tokens']!=1024 or plan['generation']['maximum_seconds']!=180:
        raise ValueError('Fair raw generation limit differs')
    prior=checked.nf4.base.read_json(checked.nf4.binding(plan['successful_diagnostic']))
    if prior.get('status')!='passed'or not checked.qualified(prior):raise ValueError('Actual authored backward diagnostic has not passed')
    if prior['source_sha256']!=checked.nf4.base.digest(Path(checked.__file__)):raise ValueError('Successful diagnostic source differs')
    checked.verify_protocol(checked.nf4.binding(plan['diagnostic_protocol']))
    qualification=checked.nf4.base.read_json(checked.nf4.binding(plan['successful_memory_qualification']))
    memory_plan=checked.nf4.base.read_json(checked.nf4.binding(plan['memory_protocol']))
    if (qualification.get('status')!='passed' or qualification.get('updates_completed')!=32
        or qualification.get('presentations_completed')!=256 or not qualification.get('checks')
        or not all(qualification['checks'].values())
        or qualification['protocol_sha256']!=checked.nf4.base.digest(checked.nf4.binding(plan['memory_protocol']))):
        raise ValueError('Actual bounded memory qualification has not passed')
    for item in memory_plan['dependencies']:checked.nf4.binding(item)
    if checked.nf4.base.digest(checked.nf4.binding(plan['memory_implementation']))!=memory_plan['implementation_sha256']:
        raise ValueError('Qualified diagnostic implementation differs')
    runtime_path=ROOT/'scripts/chess_queen_coach_sft_runtime_v2.py'
    matches=[item for item in memory_plan['dependencies']if item['path']=='scripts/chess_queen_coach_sft_runtime_v2.py']
    if len(matches)!=1 or matches[0]['sha256']!=checked.nf4.base.digest(runtime_path):
        raise ValueError('Runtime differs from actual qualified runtime')
    worker=checked.nf4.base.read_json(checked.nf4.binding(plan['closed_memory_worker']))
    if worker.get('status')!='completed' or worker.get('exit_code')!=0 or not worker.get('child_exited_before_lease_release'):
        raise ValueError('Qualification worker has not closed successfully')
    return plan


def save(path,value):checked.nf4.save(path,value)


def append(path,value):
    with Path(path).open('a',encoding='utf-8')as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def finalize_training_rows(planned,journal):
    """Overlay durable actual calls on all fixed planned IDs, preserving unknowns."""
    rows=[dict(row,status='not_run')for row in planned]
    by_key={(row['step'],row['micro']):row for row in rows}
    metadata={'valid_events':0,'trailing_partial':None}
    if Path(journal).exists():
        lines=Path(journal).read_bytes().splitlines(keepends=True)
        nonempty=[index for index,line in enumerate(lines)if line.strip()]
        for index in nonempty:
            line=lines[index]
            try:value=json.loads(line.decode('utf-8'))
            except(UnicodeDecodeError,json.JSONDecodeError):
                if index!=nonempty[-1]:raise ValueError('Training journal corruption before later events')
                metadata['trailing_partial']={'bytes':len(line),'sha256':hashlib.sha256(line).hexdigest(),
                    'journal_path':str(Path(journal).resolve()),'original_bytes_preserved':True}
                break
            if not isinstance(value,dict):raise ValueError('Training journal event is not an object')
            metadata['valid_events']+=1
            if 'micro'not in value:continue
            target=by_key[(value['step'],value['micro'])]
            if target['case_id']!=value['case_id']:raise ValueError('Actual training journal ID differs')
            target.update(status='active_unknown'if value['status']=='call_started'else value['status'])
            if 'loss'in value:target['loss']=value['loss']
    return {'rows':rows,'journal':metadata}


def guard_for(plan,out):
    kernel=checked.nf4.verify_protocol(checked.nf4.binding(plan['kernel_protocol']))
    base,samples,policy=checked.nf4.guard_for(kernel,out)
    cutoff=datetime.fromisoformat(plan['cutoff_utc']);started=time.monotonic()
    maximum=plan['phase_maximum_seconds'][out.stem]
    def guard():
        if datetime.now(timezone.utc)>=cutoff:raise RuntimeError('Frozen13:00UTC cutoff reached')
        if time.monotonic()-started>=maximum:raise RuntimeError('Frozen phase time budget reached: '+out.stem)
        base()
    return guard,samples,policy


def pending_panel(path,rows,condition,identity=None):
    if path.exists():raise ValueError('Raw panel is create-only')
    value={'schema':'chess.queen-coach-raw-panel.v1','condition':condition,'status':'not_run',
        'model_identity':identity,'planned':len(rows),'rows':[{'case_id':row['case_id'],'group_id':row['group_id'],
            'mode':row['mode'],'status':'not_run','input_sha256':hashlib.sha256(json.dumps(row['input'],sort_keys=True).encode()).hexdigest()}
            for row in rows]}
    save(path,value);return value


def generate_panel(runtime,rows,path,identity,guard):
    value=checked.nf4.base.read_json(path);value.update(status='started',model_identity=identity);save(path,value)
    directory=path.with_suffix('');directory.mkdir(exist_ok=False)
    for index,row in enumerate(rows):
        guard();receipt=directory/f'{index:03d}.json'
        value['rows'][index].update(status='call_started',response_path=str(receipt.resolve()))
        save(path,value) # Persist intent before the decoder sees this input.
        raw=runtime.infer(row,identity);save(receipt,raw)
        value['rows'][index].update(status=raw['status'],response_sha256=checked.nf4.base.digest(receipt))
        save(path,value)
        if raw['status']=='failed':
            value.update(status='failed',error=raw.get('error','backend failure'));save(path,value)
            raise RuntimeError('First raw generator backend/resource failure: '+value['error'])
        runtime.release_inactive('after_returned_raw_generation_'+row['case_id'])
    value['status']='completed';save(path,value);return value


def score_panel(rows,panel,refs):
    scored=[]
    for row,receipt in zip(rows,panel['rows']):
        if row['case_id']!=receipt['case_id']:raise ValueError('Raw panel case order differs')
        if receipt['status']in('not_run','call_started'):
            raw={'status':receipt['status'],'raw_text':''}
        else:
            path=Path(receipt['response_path'])
            if checked.nf4.base.digest(path)!=receipt['response_sha256']:raise ValueError('Raw response bytes changed')
            raw=checked.nf4.base.read_json(path)
        scored.append({'case_id':row['case_id'],'group_id':row['group_id'],'mode':row['mode'],
            **scoring.score(row['input'],raw,refs[row['case_id']])})
    free=[row for row in scored if row['mode']=='free']
    return {'rows':scored,'counts':{**scoring.summarize(scored),
        'free_critical_3ply_agreement':sum(row['critical_prefix_matches']['3']for row in free),
        'free_best_agreement':sum(row['accepted_teacher_best_agreement']for row in free)},
        'by_mode':{mode:scoring.summarize([row for row in scored if row['mode']==mode])for mode in('free','selected')}}


def checkpoint_development(runtime,plan,out,step,presentations,optimizer,dev,dev_tokens,raw_rows,refs,guard):
    identity=runtime.save_adapter(out/f'checkpoint-{step:04d}',step,presentations)
    runtime.torch.save(optimizer.state_dict(),out/f'checkpoint-{step:04d}'/'optimizer.pt')
    condition={'step':step,'status':'started','identity':identity,'raw_planned':8,'raw_completed':0,
        'nll_planned':64,'nll_completed':0,'nll_supervised_tokens':0,'nll_weighted_sum':0.,
        'nll_rows':[{'case_id':row['case_id'],'status':'not_run'}for row in dev]}
    path=out/f'development-{step:04d}.json';save(path,condition)
    for index,(row,tokens)in enumerate(zip(dev,dev_tokens)):
        condition['nll_rows'][index]['status']='call_started';save(path,condition)
        guard();append(out/'development-calls.jsonl',{'step':step,'case_id':row['case_id'],'status':'call_started'})
        with runtime.torch.no_grad():loss=runtime.loss(row,tokens,training=False)
        count=sum(value!=-100 for value in tokens[1])
        append(out/'development-calls.jsonl',{'step':step,'case_id':row['case_id'],'status':'completed','loss':loss,'supervised_tokens':count})
        condition['nll_completed']+=1;condition['nll_supervised_tokens']+=count;condition['nll_weighted_sum']+=loss*count
        condition['nll_rows'][index].update(status='completed',loss=loss,supervised_tokens=count)
        save(path,condition)
        runtime.release_inactive('after_returned_development_nll_step'+str(step)+'_'+row['case_id'])
    condition['response_token_nll']=condition['nll_weighted_sum']/condition['nll_supervised_tokens'];save(path,condition)
    panel=generate_panel(runtime,raw_rows,out/f'raw-development-{step:04d}.json',identity,guard)
    quality=score_panel(raw_rows,panel,refs);save(out/f'development-score-{step:04d}.json',quality)
    condition.update(status='completed',raw_completed=len(panel['rows']),counts=quality['counts'])
    save(path,condition);return condition


def train(plan,protocol,out):
    if out.exists():raise ValueError('Training attempt directory must be new')
    out.mkdir(parents=True)
    train_rows=read_rows(checked.nf4.binding(plan['data']['train']),True)
    dev=read_rows(checked.nf4.binding(plan['data']['development']),True)
    if len(train_rows)!=2048 or len(dev)!=64:raise ValueError('TRAIN/dev quotas differ')
    if {row['group_id']for row in train_rows}&{row['group_id']for row in dev}:raise ValueError('TRAIN/dev game overlap')
    refs=references(checked.nf4.binding(plan['data']['development_references']),dev)
    raw_rows=[row for row in dev if row['group_id']in plan['development_raw_groups']]
    if len(raw_rows)!=8 or len(set(plan['development_raw_groups']))!=4:raise ValueError('Fixed raw-development cohort differs')
    for step in STEPS:
        pending_panel(out/f'raw-development-{step:04d}.json',raw_rows,f'development-step{step}')
        save(out/f'development-{step:04d}.json',{'step':step,'status':'not_run','raw_planned':8,'raw_completed':0,
            'nll_planned':64,'nll_completed':0,'nll_rows':[{'case_id':row['case_id'],'status':'not_run'}for row in dev]})
    order=list(range(2048));random.Random(plan['training']['seed']).shuffle(order)
    planned=[{'step':index//8+1,'micro':index%8,'case_id':train_rows[source]['case_id']}
        for index,source in enumerate(order)]
    save(out/'training-plan.json',{'planned':2048,'rows':planned})
    state={'schema':'chess.queen-coach-training.v2','status':'attempt_started','updates_planned':256,
        'updates_completed':0,'presentations_planned':2048,'presentations_completed':0,'partial_accumulation':0,
        'protocol_sha256':checked.nf4.base.digest(protocol),'conditions':[],
        'active_unknown':None,'inflight_training':None,'inflight_optimizer':None,
        'restart':'Fresh publisher/NF4 base, seeded zero-B adapter and fresh optimizer; discard prior failed/qualification learning.',
        'memory_qualification_sha256':plan['successful_memory_qualification']['sha256']}
    save(out/'run.json',state);guard,samples,_=guard_for(plan,out/'training.json')
    try:
        runtime=Runtime(plan,guard);runtime.memory_journal=out/'memory-lifetime.jsonl'
        runtime.load();torch=runtime.torch;runtime.release_inactive('after_model_load')
        train_tokens=[runtime.tokenize(row)for row in train_rows];dev_tokens=[runtime.tokenize(row)for row in dev]
        config=plan['training']
        optimizer=torch.optim.AdamW([value for _,value in runtime.parameters],lr=config['learning_rate'],
            betas=(.9,.999),eps=1e-8,weight_decay=.01,foreach=False)
        optimizer.zero_grad(set_to_none=True)
        state['conditions'].append(checkpoint_development(runtime,plan,out,0,0,optimizer,dev,dev_tokens,raw_rows,refs,guard))
        save(out/'run.json',state)
        order=list(range(2048));random.Random(config['seed']).shuffle(order)
        for step in range(1,257):
            guard();optimizer.zero_grad(set_to_none=True);state['partial_accumulation']=0;save(out/'run.json',state)
            warm=config['warmup_updates'];factor=step/warm if step<=warm else(.1+.9*.5*(1+math.cos(math.pi*(step-warm)/(256-warm))))
            for group in optimizer.param_groups:group['lr']=config['learning_rate']*factor
            losses=[]
            for micro in range(8):
                guard();index=order[(step-1)*8+micro];row=train_rows[index]
                intent={'step':step,'micro':micro,'case_id':row['case_id'],'status':'call_started'}
                state['inflight_training']=intent.copy();save(out/'run.json',state)
                append(out/'training-calls.jsonl',intent)
                loss=runtime.loss(row,train_tokens[index],training=True)
                append(out/'training-calls.jsonl',{**intent,'status':'backward_completed','loss':loss})
                state['presentations_completed']+=1;state['partial_accumulation']+=1;losses.append(loss)
                state['inflight_training']=None;save(out/'run.json',state)
                runtime.release_inactive(f'after_returned_backward_step{step}_micro{micro}')
            runtime.verify_gradients();torch.nn.utils.clip_grad_norm_([value for _,value in runtime.parameters],1.)
            state['inflight_optimizer']={'step':step,'status':'call_started'};save(out/'run.json',state)
            append(out/'training-calls.jsonl',{'step':step,'status':'optimizer_started'})
            optimizer.step();torch.cuda.synchronize()
            state.update(updates_completed=step,partial_accumulation=0,inflight_optimizer=None)
            append(out/'training-calls.jsonl',{'step':step,'status':'optimizer_completed','mean_loss':sum(losses)/8})
            save(out/'run.json',state);optimizer.zero_grad(set_to_none=True)
            runtime.release_inactive(f'after_optimizer_step{step}');guard()
            if step in STEPS:
                optimizer.zero_grad(set_to_none=True)
                state['conditions'].append(checkpoint_development(runtime,plan,out,step,state['presentations_completed'],optimizer,
                    dev,dev_tokens,raw_rows,refs,guard));save(out/'run.json',state)
        state['frozen_storage']=runtime.verify_frozen()
        chosen=select(state['conditions'])
        selection={'schema':'chess.queen-coach-dev-selection.v2','status':'selected',
            'selected':chosen['identity'],'baseline':state['conditions'][0]['identity'],
            'protocol_sha256':state['protocol_sha256'],'selection_key':list(selection_key(chosen)),
            'heldout_opened':False,'selection_method':plan['selection_method'],'conditions':state['conditions']}
        save(out/'selection.json',selection)
        state.update(status='completed',peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved());save(out/'run.json',state)
    except Exception as error:
        state['active_unknown']=state['inflight_training']or state['inflight_optimizer']
        if state['active_unknown']is not None:state['active_unknown']={**state['active_unknown'],'status':'active_unknown'}
        state.update(status='failed',error=type(error).__name__+': '+str(error));save(out/'failure.json',state);save(out/'run.json',state)
        raise
    finally:
        save(out/'resources.json',samples)
        save(out/'training-denominator.json',{'planned':2048,
            **finalize_training_rows(planned,out/'training-calls.jsonl')})


def heldout(plan,protocol,selection_path,out):
    if out.exists():raise ValueError('Heldout attempt directory must be new')
    out.mkdir(parents=True)
    selection=checked.nf4.base.read_json(selection_path)
    verify_selection(selection,protocol)
    rows=read_rows(checked.nf4.binding(plan['data']['heldout_inputs']),False)
    if len(rows)!=32:raise ValueError('Heldout16games/32pairedinputs differ')
    # Both full conditions are durable before resource/model setup. Evaluator
    # reference content is opened only after every planned response is retained.
    for condition in('baseline','selected'):pending_panel(out/f'{condition}.json',rows,condition,selection[condition])
    guard,samples,_=guard_for(plan,out/'heldout.json')
    try:
        runtime=Runtime(plan,guard);runtime.memory_journal=out/'memory-lifetime.jsonl'
        runtime.load();runtime.release_inactive('after_model_load')
        for condition in('baseline','selected'):
            runtime.load_adapter(selection[condition]);runtime.release_inactive('after_loaded_'+condition+'_adapter')
            generate_panel(runtime,rows,out/f'{condition}.json',selection[condition],guard)
        refs=references(checked.nf4.binding(plan['data']['heldout_references']),rows)
        for condition in('baseline','selected'):
            panel=checked.nf4.base.read_json(out/f'{condition}.json')
            save(out/f'{condition}-score.json',score_panel(rows,panel,refs))
        save(out/'frozen-storage.json',runtime.verify_frozen())
        save(out/'summary.json',{'status':'completed','planned_responses':64,
            'selection_sha256':checked.nf4.base.digest(selection_path),'protocol_sha256':checked.nf4.base.digest(protocol),
            'claim':'Fresh3ply-eligible tactical roots; teacher agreement is not chess correctness/Elo. Whole-prose coaching correctness remains unmeasured.'})
    except Exception as error:
        save(out/'failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),'planned_responses':64})
        raise
    finally:save(out/'resources.json',samples)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['train','heldout'])
    parser.add_argument('--protocol',type=Path,default=PROTOCOL)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Attempt output directory must be new')
    try:
        plan=verify_protocol(args.protocol)
        if args.mode=='train':train(plan,args.protocol,args.out)
        else:
            if args.selection is None:raise ValueError('Heldout requires saved --selection')
            heldout(plan,args.protocol,args.selection,args.out)
    except Exception as error:
        args.out.mkdir(parents=True,exist_ok=True)
        failure=args.out/'failure.json'
        if not failure.exists():
            save(failure,{'status':'failed','stage':'protocol_or_data_setup',
                'error':type(error).__name__+': '+str(error),'model_calls_started':False,
                'planned_updates':256 if args.mode=='train' else 0,
                'planned_presentations':2048 if args.mode=='train' else 0,
                'planned_raw_responses':32 if args.mode=='train' else 64})
        raise


if __name__=='__main__':main()
