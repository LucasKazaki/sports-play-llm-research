"""Native9m continuation with a full-vocabulary legal-mass training objective.

No inference masking. CPU teachers reuse the audited v5 event/journal path.
Only the root coordinator executes the CUDA phase.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil
import time

import chess
from chess_fact_sft_common import read, save, sha
from chess_fact_sft_intake import board_key, parquet_rows
from chess_classifier_adapter import encode_fen, load_native_contract, verify_model_mapping
import chess_move_policy_v5 as v5

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'chess.move-policy.v6'


def verify_protocol(protocol):
    plan = read(protocol)
    if plan['schema'] != SCHEMA or sha(Path(__file__)) != plan['implementation_sha256']:
        raise ValueError('frozen v6 source identity changed')
    for binding in plan['dependencies']:
        v5.bound_file(binding)
    return plan


def snapshot(protocol, out, name):
    destination = out/name
    destination.mkdir()
    bindings = {}
    for path in [Path(__file__),protocol]+[ROOT/b['path'] for b in read(protocol)['dependencies']]:
        shutil.copyfile(path,destination/path.name)
        bindings[path.name]=sha(destination/path.name)
    save(destination/'manifest.json',bindings)


def intake(protocol,out):
    plan=verify_protocol(protocol)
    source=v5.bound_file(plan['source'])
    games,boards=v5.exclusions(plan)
    old=read(v5.bound_file(plan['reused_dataset']))
    labels=read(v5.bound_file(plan['reused_labels']))
    reuse=labels['splits']['train']
    if (len(reuse)!=32768 or [r['id'] for r in reuse]!=[r['id'] for r in old['splits']['train']]
            or any(r['status']!='completed' for r in reuse)):
        raise ValueError('exact v5 training-only reuse is not established')
    if out.exists():
        raise ValueError('v6 intake is create-only')
    out.mkdir(parents=True)
    snapshot(protocol,out,'intake-executed-sources')
    fresh,selection=v5.select_rows(parquet_rows(source),plan['new_counts'],plan['seed'],
                                  games,boards,plan['source_row_cap'])
    save(out/'dataset.json',{'schema':SCHEMA,'protocol_sha256':sha(protocol),
        'new_splits':fresh,'reused_training':old['splits']['train'],
        'reuse_labels_sha256':plan['reused_labels']['sha256'],
        'exclusions':{'games':len(games),'board_keys':len(boards)},'selection':selection})
    save(out/'intake-receipt.json',{'dataset_sha256':sha(out/'dataset.json'),
        'new_counts':{s:len(v) for s,v in fresh.items()},'reused_training':len(reuse),
        'model_calls':0,'engine_calls':0})
    return {'new_counts':{s:len(v) for s,v in fresh.items()},'reused':len(reuse)}


def choose_rollout(candidates,count):
    selected,outcomes=[],[]
    for row in sorted(candidates,key=lambda r:r['source_ordinal']):
        reason='teacher_failed' if row['status']!='completed' else 'short_reference' if len(row['reference_pv'])<3 else 'eligible'
        if reason=='eligible':
            board=chess.Board(row['fen'])
            try:
                for uci in row['reference_pv'][:3]:
                    if board.is_game_over(claim_draw=False):
                        reason='terminal_reference'
                        break
                    move=chess.Move.from_uci(uci)
                    if move not in board.legal_moves: raise ValueError('illegal reference')
                    board.push(move)
            except ValueError:
                reason='invalid_reference'
        if reason=='eligible':
            if len(selected)<count:
                selected.append(row)
                reason='selected'
            else:
                reason='eligible_reservoir_remainder'
        outcomes.append({'id':row['id'],'game_id':row['game_id'],
                         'source_ordinal':row['source_ordinal'],'reason':reason,
                         'reference_plies':len(row['reference_pv'])})
    return selected,{'planned_candidates':len(candidates),'selected':len(selected),
                     'outcomes':outcomes,'reasons':dict(Counter(r['reason'] for r in outcomes))}


def cpu_workers(plan,out):
    from chess_native_resources import windows_sample,GIB
    sample=windows_sample()
    if sample.physical_available_bytes<6*GIB or sample.commit_headroom_bytes<6*GIB:
        raise RuntimeError('CPU teacher reserve below6GiB physical/commit; no calls started')
    workers=6 if min(sample.physical_available_bytes,sample.commit_headroom_bytes)>=10*GIB else 3
    save(out/'teacher-resource-start.json',{'sample':asdict(sample),'workers':workers,
                                          'rule':plan['teacher']['resource_rule']})
    return workers


def label(protocol,out):
    plan=verify_protocol(protocol)
    data=read(out/'dataset.json')
    if data['protocol_sha256']!=sha(protocol) or (out/'label-attempt.json').exists():
        raise ValueError('wrong dataset or retained teacher attempt; no replay')
    workers=cpu_workers(plan,out)
    engine=v5.bound_file(plan['teacher']['binary'])
    with (out/'label-attempt.json').open('x',encoding='utf-8') as stream:
        json.dump({'protocol_sha256':sha(protocol),'utc':datetime.now(timezone.utc).isoformat()},stream)
    snapshot(protocol,out,'label-executed-sources')
    (out/'teacher-chunks').mkdir()
    tasks=[(s,r) for s,rows in data['new_splits'].items() for r in rows]
    records={s:{} for s in data['new_splits']}
    started,done=time.perf_counter(),0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={}
        for index in range(0,len(tasks),128):
            rows=tasks[index:index+128]
            journal=out/'teacher-chunks'/f'chunk-{index//128:04d}.jsonl'
            future=pool.submit(v5.teacher_chunk,str(engine),plan['teacher'],rows,str(journal),str(out/'CANCEL'))
            futures[future]=(rows,journal)
        for future in as_completed(futures):
            try: values=future.result()
            except Exception as error: values=v5.recovered_chunk(*futures[future],error)
            for split,row in values:
                records[split][row['id']]=row
                done+=1
            save(out/'label-progress.json',{'done':done,'total':len(tasks),'seconds':time.perf_counter()-started})
            print(json.dumps({'phase':'v6_teacher','done':done,'total':len(tasks)}),flush=True)
    fresh={s:[records[s][r['id']] for r in rows] for s,rows in data['new_splits'].items()}
    # Persist every requested teacher record before eligibility filtering.
    save(out/'all-new-teacher-records.json',{'splits':fresh,'requested':len(tasks),
        'failure_count':sum(r['status']!='completed' for rows in fresh.values() for r in rows)})
    selected,eligibility=choose_rollout(fresh['rollout'],plan['rollout_count'])
    save(out/'rollout-selection.json',eligibility)
    if len(selected)!=plan['rollout_count']:
        raise RuntimeError('insufficient frozen three-ply cohort; all candidate outcomes retained')
    reused=read(v5.bound_file(plan['reused_labels']))['splits']['train']
    splits={'train':reused+fresh['train'],'development':fresh['development'],
            'holdout':fresh['holdout'],'rollout':selected}
    value={'schema':SCHEMA,'protocol_sha256':sha(protocol),'dataset_sha256':sha(out/'dataset.json'),
        'all_new_teacher_records_sha256':sha(out/'all-new-teacher-records.json'),
        'rollout_selection_sha256':sha(out/'rollout-selection.json'),
        'reused_labels_sha256':plan['reused_labels']['sha256'],'splits':splits,
        'failure_count':sum(r['status']!='completed' for rows in splits.values() for r in rows),
        'teacher_attempts':len(tasks),'teacher_seconds':time.perf_counter()-started,'workers':workers}
    save(out/'labels.json',value)
    save(out/'label-completed.json',{'labels_sha256':sha(out/'labels.json'),
        'counts':{s:len(v) for s,v in splits.items()},'failures':value['failure_count'],
        'teacher_attempts':len(tasks),'rollout_selection_sha256':sha(out/'rollout-selection.json')})
    return {'counts':{s:len(v) for s,v in splits.items()},'failures':value['failure_count']}


def legal_action_indices(fen,contract):
    board=chess.Board(fen)
    actions=[contract['label2id'][m.uci()] for m in board.legal_moves]
    if not board.is_valid() or board.is_game_over() or not actions:
        raise ValueError('valid nonterminal training position required')
    return actions


def objective(logits,targets,legal_mask):
    """CE over all1968classes + negative log total probability of legal moves."""
    import torch
    if (logits.ndim!=2 or logits.shape[1]!=1968 or legal_mask.shape!=logits.shape
            or legal_mask.dtype!=torch.bool or targets.shape!=(logits.shape[0],)):
        raise ValueError('wrong native objective shape/dtype')
    if not bool(torch.isfinite(logits).all()) or not bool(legal_mask.any(dim=1).all()):
        raise ValueError('nonfinite logits or empty legal support')
    if not bool(legal_mask.gather(1,targets[:,None]).all()):
        raise ValueError('teacher target is not legal')
    ce=torch.nn.functional.cross_entropy(logits,targets)
    mass=(torch.logsumexp(logits,dim=1)-torch.logsumexp(logits.masked_fill(~legal_mask,float('-inf')),dim=1)).mean()
    return ce+mass,ce,mass


def selection_key(step,result,threshold_milli=995):
    eligible=1000*result['raw_legal_count']>=threshold_milli*result['count']
    return int(eligible),result['raw_top1_match_count'],result['raw_legal_count'],-step


def train(protocol,out):
    import platform
    import torch
    import transformers
    from transformers import LlamaForSequenceClassification
    plan=verify_protocol(protocol)
    labels=read(out/'labels.json')
    completed=read(out/'label-completed.json')
    if (labels['protocol_sha256']!=sha(protocol) or labels['dataset_sha256']!=sha(out/'dataset.json')
            or completed['labels_sha256']!=sha(out/'labels.json') or labels['failure_count']):
        raise ValueError('complete frozen labels required; no failed rows dropped')
    if (out/'train-attempt.json').exists(): raise ValueError('retained training attempt; no replay')
    if not torch.cuda.is_available(): raise ValueError('root-only CUDA phase requires CUDA')
    with (out/'train-attempt.json').open('x',encoding='utf-8') as stream:
        json.dump({'protocol_sha256':sha(protocol),'utc':datetime.now(timezone.utc).isoformat()},stream)
    snapshot(protocol,out,'train-executed-sources')
    start=ROOT/plan['starting_model']['path']
    v5.bound_file(plan['starting_model']['weights'])
    contract=load_native_contract(ROOT/plan['tokenizer_contract'])
    verify_model_mapping(read(start/'config.json'))
    encoded,failures=v5.previous.encode_rows(labels['splits']['train'],contract)
    if len(encoded)!=65536 or failures: raise ValueError('all65536training rows must encode')
    train_ids=torch.tensor([r[1] for r in encoded],dtype=torch.long)
    targets=torch.tensor([r[2] for r in encoded],dtype=torch.long)
    legal_mask=torch.zeros((len(encoded),1968),dtype=torch.bool)
    for index,row in enumerate(labels['splits']['train']):
        legal_mask[index,legal_action_indices(row['fen'],contract)]=True
    if not bool(legal_mask.gather(1,targets[:,None]).all()): raise ValueError('illegal training target')
    settings=plan['training']
    torch.set_num_threads(4)
    torch.manual_seed(settings['seed'])
    started=time.perf_counter()
    v5.resource_check(out,plan,started)
    model=LlamaForSequenceClassification.from_pretrained(start,local_files_only=True,
        attn_implementation='sdpa').float().to('cuda')
    torch.cuda.reset_peak_memory_stats()
    (out/'checkpoints').mkdir()
    model.save_pretrained(out/'checkpoints/step-0',safe_serialization=True)
    evaluations={0:v5.checked_evaluate(model,labels['splits']['development'],contract,'cuda','step-0-development',out,128)}
    optimizer=torch.optim.AdamW(model.parameters(),lr=settings['learning_rate'],weight_decay=settings['weight_decay'])
    rng,order,history=random.Random(settings['seed']),[],[]
    model.train()
    for step in range(1,settings['steps']+1):
        if len(order)<settings['batch_size']:
            fresh=list(range(len(encoded)))
            rng.shuffle(fresh)
            order.extend(fresh)
        chosen,order=order[:settings['batch_size']],order[settings['batch_size']:]
        indices=torch.tensor(chosen,dtype=torch.long)
        ids=train_ids.index_select(0,indices).to('cuda')
        target=targets.index_select(0,indices).to('cuda')
        mask=legal_mask.index_select(0,indices).to('cuda')
        optimizer.zero_grad(set_to_none=True)
        logits=model(input_ids=ids,attention_mask=torch.ones_like(ids)).logits.float()
        loss,ce,mass=objective(logits,target,mask)
        if not bool(torch.isfinite(loss)): raise ValueError('nonfinite legality objective')
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True)
        optimizer.step()
        history.append({'step':step,'loss':float(loss.detach()),'cross_entropy':float(ce.detach()),
                        'legal_mass_loss':float(mass.detach()),'gradient_norm':float(norm)})
        if step%64==0:
            save(out/'training-log.json',history)
            v5.resource_check(out,plan,started)
            print(json.dumps({'phase':'v6_train',**history[-1],'seconds':time.perf_counter()-started}),flush=True)
        if step in settings['checkpoints']:
            model.save_pretrained(out/f'checkpoints/step-{step}',safe_serialization=True)
            evaluations[step]=v5.checked_evaluate(model,labels['splits']['development'],contract,
                'cuda',f'step-{step}-development',out,128)
            model.train()
    selected=max(evaluations,key=lambda s:selection_key(s,evaluations[s],plan['selection_threshold_milli']))
    eligible=[s for s,r in evaluations.items() if selection_key(s,r,plan['selection_threshold_milli'])[0]]
    save(out/'selection-before-holdout.json',{'selected_step':selected,'eligible_steps':eligible,
        'fallback_used':not bool(eligible),'rule':plan['selection'],'holdout_opened':False,
        'selected_weights_sha256':sha(out/f'checkpoints/step-{selected}/model.safetensors'),
        'development':{str(k):{x:v for x,v in r.items() if x!='records'} for k,r in evaluations.items()}})
    del optimizer,model
    torch.cuda.empty_cache()
    results={}
    for condition,step in [('starting',0),('selected',selected)]:
        if condition=='selected' and selected==0:
            results[condition]={**results['starting'],'reuses_starting_identical_checkpoint':True}
            continue
        model=LlamaForSequenceClassification.from_pretrained(out/f'checkpoints/step-{step}',
            local_files_only=True,attn_implementation='sdpa').float().to('cuda')
        results[condition]={'holdout':v5.checked_evaluate(model,labels['splits']['holdout'],contract,
            'cuda',condition+'-holdout',out,128),
            'rollout':v5.rollout(model,labels['splits']['rollout'],contract,'cuda',condition,out)}
        del model
        torch.cuda.empty_cache()
    value={'schema':SCHEMA,'protocol_sha256':sha(protocol),'labels_sha256':sha(out/'labels.json'),
        'selection_sha256':sha(out/'selection-before-holdout.json'),'selected_step':selected,
        'training':{**settings,'presentations':settings['steps']*settings['batch_size'],
                    'seconds_including_evaluation':time.perf_counter()-started},'results':results,
        'starting_weights_sha256':plan['starting_model']['weights']['sha256'],
        'selected_weights_sha256':sha(out/f'checkpoints/step-{selected}/model.safetensors'),
        'tokenizer_contract_sha256':contract['source_sha256'],
        'runtime':{'python':platform.python_version(),'torch':torch.__version__,'transformers':transformers.__version__,
                   'gpu':torch.cuda.get_device_name(),'peak_cuda_allocated':torch.cuda.max_memory_allocated()},
        'limitations':plan['limitations'],'finished_at':datetime.now(timezone.utc).isoformat()}
    save(out/'receipt.json',value)
    return {'selected_step':selected}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('intake','label','train'))
    parser.add_argument('--protocol',type=Path,default=ROOT/'experiments/chess-move-policy-v6/protocol-v2.json')
    parser.add_argument('--out',type=Path,default=ROOT/'data/private/chess-move-policy-v6')
    args=parser.parse_args()
    try: result={'intake':intake,'label':label,'train':train}[args.phase](args.protocol,args.out)
    except Exception as error:
        args.out.mkdir(parents=True,exist_ok=True)
        save(args.out/'failure.json',{'phase':args.phase,'status':'failed','error':type(error).__name__+':'+str(error),
             'replay_allowed':False,'utc':datetime.now(timezone.utc).isoformat()})
        raise
    print(json.dumps({'phase':args.phase,'status':'completed',**result}))


if __name__=='__main__': main()
