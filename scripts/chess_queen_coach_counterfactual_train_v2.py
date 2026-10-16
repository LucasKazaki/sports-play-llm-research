"""Training-only operational v2; preserved v1 science and prospective admissions."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time
import chess_queen_coach_sft_train_v2 as prior
import chess_queen_coach_counterfactual_eval_v1 as scoring
from chess_queen_coach_counterfactual_runtime_v1 import Runtime,checked,validate_start
from chess_queen_coach_counterfactual_contract_v1 import verify_preflight
ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'experiments/chess-queen-coach-counterfactual-v1/training-protocol-v2.json'
STEPS=(0,48,96,192)
MODES=('free','selected_a','selected_b')
save=prior.save;append=prior.append;finalize_training_rows=prior.finalize_training_rows
pending_panel=prior.pending_panel;generate_panel=prior.generate_panel


def read_rows(path,targets):
    rows=[json.loads(line)for line in Path(path).read_text(encoding='utf-8-sig').splitlines()if line.strip()]
    seen=set();groups={}
    for row in rows:
        keys={'case_id','group_id','mode','input'}|({'response'}if targets else set())
        if set(row)!=keys:raise ValueError('Unexpected corpus row fields')
        if not isinstance(row['case_id'],str)or row['case_id']in seen:raise ValueError('Missing/duplicate case ID')
        seen.add(row['case_id'])
        if not isinstance(row['group_id'],str)or row['mode']not in MODES:raise ValueError('Invalid group/mode')
        allowed={'fen'}if row['mode']=='free'else{'fen','selected_uci'}
        if not isinstance(row['input'],dict)or set(row['input'])!=allowed:raise ValueError('Exact current-only input whitelist required')
        packet,_=checked.nf4.base.input_packet(row['input'])
        if ('selected_uci'in packet)!=(row['mode']!='free'):raise ValueError('Input/mode differs')
        if targets and(not isinstance(row['response'],str)or not row['response']):raise ValueError('Missing complete target')
        groups.setdefault(row['group_id'],[]).append(row)
    for pair in groups.values():
        if len(pair)!=3 or {row['mode']for row in pair}!=set(MODES)or len({row['input']['fen']for row in pair})!=1:
            raise ValueError('Every game requires oneFREE plus two opaque selected cases')
        selected=[row['input']['selected_uci']for row in pair if row['mode']!='free']
        if len(set(selected))!=2:raise ValueError('Supplied candidate moves must differ')
    return rows

def references(path,rows):
    values=[json.loads(line)for line in Path(path).read_text(encoding='utf-8-sig').splitlines()if line.strip()]
    result={value['case_id']:value for value in values}
    if len(result)!=len(values)or set(result)!={row['case_id']for row in rows}:raise ValueError('Reference IDs differ')
    for row in rows:
        reference=result[row['case_id']]
        if reference['group_id']!=row['group_id']:raise ValueError('Reference group differs')
        if row['mode']!='free'and reference['selected_uci']!=row['input']['selected_uci']:raise ValueError('Selected input/reference differs')
    return result

def selection_key(condition):
    counts=condition['counts'];nll=condition['response_token_nll']
    legal=counts['accepted_best_legal']
    return (legal==6,legal,counts['free_critical_3ply_agreement'],counts['free_best_agreement'],-nll,-condition['step'])

def select(conditions):
    eligible=[value for value in conditions if value.get('status')=='completed'
        and value.get('raw_planned')==6 and value.get('raw_completed')==6
        and value.get('nll_completed')==96 and math.isfinite(value['response_token_nll'])]
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
    if plan['implementation_sha256']!=checked.nf4.base.digest(Path(__file__)):raise ValueError('Frozen trainer differs')
    for item in plan['dependencies']:checked.nf4.binding(item)
    for item in plan['data'].values():checked.nf4.binding(item) # Bytes only; held truth is not semantically read.
    parent=prior.verify_protocol(checked.nf4.binding(plan['qualified_parent_protocol']))
    if plan['successful_memory_qualification']!=parent['successful_memory_qualification']:raise ValueError('Qualified runtime changed')
    if(plan['training']['updates']!=192 or plan['training']['gradient_accumulation']!=8
        or plan['training']['seed']!=4082086 or plan['training']['learning_rate']!=1e-4
        or plan['training']['warmup_updates']!=16 or plan['training']['max_total_tokens']!=512):raise ValueError('Frozen one-epoch schedule differs')
    if plan['generation']!=parent['generation']:raise ValueError('Fair generation limits changed')
    validate_start(plan['warm_start'])
    manifest=checked.nf4.base.read_json(checked.nf4.binding(plan['corpus_manifest']))
    verify_preflight(plan,checked.nf4.binding,checked.nf4.base.read_json)
    if(manifest['status']!='ready_for_training'or manifest['reserved_holdout_games']!=512
        or manifest['teacher_outcomes']!={'completed':3168}or len(manifest['held_root_game_ids'])!=16):
        raise ValueError('Exact closed corpus required')
    for key in('corpus_scientific_protocol','corpus_operational_protocol','corpus_operational_closed','corpus_closed_audit'):
        checked.nf4.binding(plan[key])
    provenance=checked.nf4.base.read_json(checked.nf4.binding(plan['corpus_operational_provenance']))
    if(provenance['status']!='completed'or provenance['owned_engine_exit_verified']is not True
        or provenance['scientific_protocol_sha256']!=plan['corpus_scientific_protocol']['sha256']
        or provenance['operational_protocol_sha256']!=plan['corpus_operational_protocol']['sha256']
        or provenance['corpus_manifest_sha256']!=plan['corpus_manifest']['sha256']
        or manifest['protocol_sha256']!=plan['corpus_scientific_protocol']['sha256']):
        raise ValueError('Actual changed-admission corpus provenance differs')
    if plan['development_raw_groups']!=manifest['development_raw_group_ids']or len(plan['development_raw_groups'])!=2:
        raise ValueError('Fixed pre-model raw development roots differ')
    for key,name in [('train','train.jsonl'),('development','development.jsonl'),
        ('development_references','development-references.jsonl'),('heldout_inputs','heldout-inputs.jsonl'),
        ('heldout_references','heldout-references.jsonl')]:
        if plan['data'][key]['sha256']!=manifest['files'][name]['sha256']:raise ValueError('Export binding differs')
    if(plan['admission_latest_utc']!='2026-10-16T11:00:00+00:00'
        or plan['held_admission_latest_utc']!='2026-10-16T11:30:00+00:00'
        or plan['cutoff_utc']!='2026-10-16T13:00:00+00:00'):raise ValueError('Fixed per-phase admission/cutoff differs')
    return plan


def snapshot(out,protocol,plan):
    directory=out/'executed-sources';directory.mkdir();copied={}
    sources=[Path(__file__),Path(protocol)]+[checked.nf4.binding(item)for item in plan['dependencies']]
    for index,path in enumerate(sources):
        target=directory/f'{index:02d}-{path.name}';shutil.copyfile(path,target)
        copied[target.name]={'source':str(path),'sha256':checked.nf4.base.digest(target)}
    save(directory/'manifest.json',copied)


def admit(plan,now=None):
    now=datetime.now(timezone.utc)if now is None else now
    if now>=datetime.fromisoformat(plan['admission_latest_utc']):raise RuntimeError('Latest11:00UTC training admission; separate cold held phase requires11:30UTC')


def guard_for(plan,out):
    admit(plan)
    return prior.guard_for(plan,out)


def score_panel(rows,panel,refs):
    if len(rows)!=len(panel['rows']):raise ValueError('Raw full denominator differs')
    responses=[]
    for row,receipt in zip(rows,panel['rows']):
        if row['case_id']!=receipt['case_id']:raise ValueError('Raw case order differs')
        if receipt['status']in('not_run','call_started'):
            raw={'status':receipt['status'],'raw_text':''}
        else:
            path=Path(receipt['response_path'])
            if checked.nf4.base.digest(path)!=receipt['response_sha256']:raise ValueError('Raw bytes changed')
            raw=checked.nf4.base.read_json(path)
        responses.append(raw)
    return scoring.panel(rows,responses,refs)


def checkpoint_development(runtime,plan,out,step,presentations,optimizer,dev,dev_tokens,raw_rows,refs,guard):
    identity=runtime.save_adapter(out/f'checkpoint-{step:04d}',step,presentations)
    runtime.torch.save(optimizer.state_dict(),out/f'checkpoint-{step:04d}'/'optimizer.pt')
    condition={'step':step,'status':'started','identity':identity,'raw_planned':6,'raw_completed':0,
        'nll_planned':96,'nll_completed':0,'nll_supervised_tokens':0,'nll_weighted_sum':0.,
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
    if len(train_rows)!=1536 or len(dev)!=96:raise ValueError('TRAIN/dev quotas differ')
    if {row['group_id']for row in train_rows}&{row['group_id']for row in dev}:raise ValueError('TRAIN/dev game overlap')
    refs=references(checked.nf4.binding(plan['data']['development_references']),dev)
    raw_rows=[row for row in dev if row['group_id']in plan['development_raw_groups']]
    if len(raw_rows)!=6 or len(set(plan['development_raw_groups']))!=2:raise ValueError('Fixed raw-development cohort differs')
    for step in STEPS:
        pending_panel(out/f'raw-development-{step:04d}.json',raw_rows,f'development-step{step}')
        save(out/f'development-{step:04d}.json',{'step':step,'status':'not_run','raw_planned':6,'raw_completed':0,
            'nll_planned':96,'nll_completed':0,'nll_rows':[{'case_id':row['case_id'],'status':'not_run'}for row in dev]})
    order=list(range(1536));random.Random(plan['training']['seed']).shuffle(order)
    planned=[{'step':index//8+1,'micro':index%8,'case_id':train_rows[source]['case_id']}
        for index,source in enumerate(order)]
    save(out/'training-plan.json',{'planned':1536,'rows':planned})
    state={'schema':'chess.queen-coach-counterfactual-training.v1','status':'attempt_started','updates_planned':192,
        'updates_completed':0,'presentations_planned':1536,'presentations_completed':0,'partial_accumulation':0,
        'protocol_sha256':checked.nf4.base.digest(protocol),'conditions':[],
        'active_unknown':None,'inflight_training':None,'inflight_optimizer':None,
        'restart':'Exact fixedselected64 warm start and fresh optimizer; no prior optimizer reuse. Additional one-epoch paired-data learning only.',
        'memory_qualification_sha256':plan['successful_memory_qualification']['sha256'],'warm_start':plan['warm_start']}
    save(out/'run.json',state);samples=[]
    try:
        guard,samples,_=guard_for(plan,out/'training.json')
        snapshot(out,protocol,plan)
        runtime=Runtime(plan,guard);runtime.memory_journal=out/'memory-lifetime.jsonl'
        runtime.load();torch=runtime.torch;runtime.release_inactive('after_model_load')
        train_tokens=[runtime.tokenize(row)for row in train_rows];dev_tokens=[runtime.tokenize(row)for row in dev]
        config=plan['training']
        optimizer=torch.optim.AdamW([value for _,value in runtime.parameters],lr=config['learning_rate'],
            betas=(.9,.999),eps=1e-8,weight_decay=.01,foreach=False)
        optimizer.zero_grad(set_to_none=True)
        state['conditions'].append(checkpoint_development(runtime,plan,out,0,0,optimizer,dev,dev_tokens,raw_rows,refs,guard))
        save(out/'run.json',state)
        order=list(range(1536));random.Random(config['seed']).shuffle(order)
        for step in range(1,193):
            guard();optimizer.zero_grad(set_to_none=True);state['partial_accumulation']=0;save(out/'run.json',state)
            warm=config['warmup_updates'];factor=step/warm if step<=warm else(.1+.9*.5*(1+math.cos(math.pi*(step-warm)/(192-warm))))
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
        selection={'schema':'chess.queen-coach-counterfactual-selection.v1','status':'selected',
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
        save(out/'training-denominator.json',{'planned':1536,
            **finalize_training_rows(planned,out/'training-calls.jsonl')})

def heldout(plan,protocol,selection_path,out):
    if out.exists():raise ValueError('Heldout attempt directory must be new')
    out.mkdir(parents=True)
    selection=checked.nf4.base.read_json(selection_path)
    verify_selection(selection,protocol)
    rows=read_rows(checked.nf4.binding(plan['data']['heldout_inputs']),False)
    if len(rows)!=48:raise ValueError('Heldout16games/48tripletinputs differ')
    # Both full conditions are durable before resource/model setup. Evaluator
    # reference content is opened only after every planned response is retained.
    for condition in('baseline','selected'):pending_panel(out/f'{condition}.json',rows,condition,selection[condition])
    samples=[]
    try:
        guard,samples,_=guard_for(plan,out/'heldout.json')
        snapshot(out,protocol,plan)
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
        save(out/'summary.json',{'status':'completed','planned_responses':96,
            'selection_sha256':checked.nf4.base.digest(selection_path),'protocol_sha256':checked.nf4.base.digest(protocol),
            'claim':'Fresh3ply-eligible matched roots; selected first move was supplied. Teacher agreement is not Elo or correctness; recognized facts do not establish whole-prose coaching quality.'})
    except Exception as error:
        save(out/'failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),'planned_responses':96})
        raise
    finally:save(out/'resources.json',samples)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['train'])
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
                'planned_updates':192 if args.mode=='train' else 0,
                'planned_presentations':1536 if args.mode=='train' else 0,
                'planned_raw_responses':24 if args.mode=='train' else 96})
        raise

if __name__=='__main__':main()
