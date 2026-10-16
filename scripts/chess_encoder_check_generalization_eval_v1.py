"""Root-only inference for the fixed saved heads; no training or selection."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import shutil

import chess_encoder_check_generalization_v1 as intake

head=intake.head;ROOT=intake.ROOT
PROTOCOL=ROOT/'experiments/chess-encoder-check-generalization-v1/inference-protocol.json'
CONDITIONS=('untrained_head','selected_head')


def append(path,value):
    with Path(path).open('a',encoding='utf-8')as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def verify(path):
    plan=head.read(path)
    if plan['implementation_sha256']!=head.sha(Path(__file__)):raise ValueError('Frozen inference source changed')
    original=intake.verify(head.bound(plan['intake_protocol']))
    for item in plan['dependencies']:head.bound(item)
    head.bound(plan['actual_cohort_audit']) # Independent receipt bytes, not evaluator labels.
    for item in plan['cohort'].values():head.bound(item) # Byte hashes only, no label/reference content.
    closed=head.read(head.bound(plan['cohort']['closed']))
    if closed['status']!='cpu_panel_closed'or closed['model_calls']or closed['engine_calls']:
        raise ValueError('Actual closed CPU cohort required')
    for key in('inputs','labels','dataset'):
        if closed['files'][key+'.json']!=plan['cohort'][key]['sha256']:raise ValueError('Actual cohort file identity differs')
    if original['selected']!=plan['selected']or original['original_untrained']!=plan['original_untrained']:
        raise ValueError('Fixed original checkpoint identities differ')
    old=head.verify(head.bound(original['old_head_protocol']))
    if old['encoder']!=plan['encoder']:raise ValueError('Exact original encoder pipeline differs')
    for name in('selected','original_untrained'):head.bound(plan[name])
    return plan,closed


def read_inputs(path):
    rows=head.read(path)['rows'];head.requests(rows)
    if len(rows)!=len({row['case_id']for row in rows}):raise ValueError('Repeated actual input ID')
    return rows


def prepare_ledgers(out,rows,closed,plan,protocol_sha256=None):
    """All actual model requests and requested shortage slots precede backends."""
    if out.exists():raise ValueError('Inference attempt directory is create-only')
    out.mkdir(parents=True)
    slots=[]
    for name in intake.STRATA:
        constructed=16-closed['shortages'][name]
        for index in range(1,17):slots.append({'allocation':name,'slot':index,'requested_moves':2,
            'status':'constructed'if index<=constructed else'source_shortage'})
    head.save(out/'requested-source-slots.json',{'requested_pairs':64,'requested_move_slots':128,
        'actual_moves':len(rows),'slots':slots,'scope':'Source availability, not model errors; no labels/case-to-stratum mapping.'})
    for condition,key in zip(CONDITIONS,('original_untrained','selected')):
        head.save(out/(condition+'.json'),{'condition':condition,'status':'not_run','checkpoint':plan[key],
            'protocol_sha256':protocol_sha256,
            'planned':len(rows),'raw':[{'case_id':row['case_id'],'status':'not_run'}for row in rows]})
    grouped=head.requests(rows)
    head.save(out/'features.json',{'status':'not_run','planned':len(rows),'unique_current_fens':len(grouped),
        'protocol_sha256':protocol_sha256,'encoder_weights_sha256':plan['encoder']['weights']['sha256'],
        'encoder_source_sha256':plan['encoder']['source']['sha256'],
        'planes_source_sha256':plan['encoder']['planes_source']['sha256'],
        'feature_pipeline_source_sha256':head.sha(Path(head.__file__)),
        'input_sha256':plan['cohort']['inputs']['sha256'],
        'records':[{'case_id':row['case_id'],'input_sha256':row['input_sha256'],'status':'not_run'}
            for _,values in grouped for row in values]})


def feature_records(rows,path,journal,encode,emit):
    """Callback-driven durable current-board extraction, first-failure stop."""
    manifest=head.read(path);records={row['case_id']:row for row in manifest['records']}
    grouped=head.requests(rows)
    for index,(fen,values)in enumerate(grouped):
        ids=[row['case_id']for row in values]
        append(journal,{'index':index,'status':'started','ids':ids})
        for case in ids:records[case]['status']='unknown_after_interruption'
        manifest['status']='started';head.save(path,manifest)
        try:
            state=encode(fen);receipts=emit(index,values,state)
            if len(receipts)!=len(values):raise ValueError('Missing requested feature record')
            if any(set(receipt)!={'shard','row','shard_sha256'}for receipt in receipts):
                raise ValueError('Feature receipts must be label-free identities only')
            done=[{**records[case],**receipt,'status':'completed'}for case,receipt in zip(ids,receipts)]
            append(journal,{'index':index,'status':'completed','records':done})
            for row in done:records[row['case_id']].update(row)
            head.save(path,manifest)
        except Exception as error:
            message=type(error).__name__+': '+str(error)
            failed=[{**records[case],'status':'failed','error':message}for case in ids]
            append(journal,{'index':index,'status':'failed','records':failed})
            for row in failed:records[row['case_id']].update(row)
            manifest.update(status='failed',error=message);head.save(path,manifest)
            raise RuntimeError('First feature failure; no subsequent backend calls: '+message)from error
    manifest['status']='completed';head.save(path,manifest);return manifest


def extract(plan,rows,out,guard):
    import torch
    torch.set_num_threads(4)
    config=plan['encoder']
    for key in('weights','config'):head.bound(config[key])
    module=head.audited_module('generalization_lc0',config['source'])
    planes=head.audited_module('generalization_planes',config['planes_source'])
    model_config=module.Lc0Bt4HFConfig.from_pretrained(ROOT/config['directory'],local_files_only=True)
    encoder=head.materialize_pinned_module(torch,lambda:module.Lc0Bt4HFModel(model_config),
        head.bound(config['weights']),'cuda',torch.bfloat16)
    if(any(value.dtype!=torch.bfloat16 for value in encoder.buffers()if value.is_floating_point())
        or encoder.policy_index_map.dtype!=torch.int64):raise ValueError('Original encoder dtype contract differs')
    encoder.eval().requires_grad_(False);guard()
    shards=out/'features';shards.mkdir()
    def encode(fen):
        guard()
        with torch.inference_mode():
            value=encoder(input_planes=planes.encode_fen_batch([fen],[[]]).to('cuda'),return_dict=True).last_hidden_state
            if tuple(value.shape)!=(1,64,1024)or not torch.isfinite(value).all():raise ValueError('Current encoder state differs')
            return value[0].float().cpu().clone()
    def emit(index,values,state):
        packets=[row['input']for row in values]
        features=head.compact_features(state.unsqueeze(0).expand(len(values),-1,-1),packets)
        path=shards/f'features-{index:04d}.pt'
        torch.save({'features':features,'indices':torch.tensor([head.move_indices(packet)for packet in packets],dtype=torch.long)},path)
        return [{'shard':str(path.relative_to(out)),'row':index,'shard_sha256':head.sha(path)}for index in range(len(values))]
    try:return feature_records(rows,out/'features.json',out/'feature-attempts.jsonl',encode,emit)
    finally:
        del encoder;torch.cuda.empty_cache()


def cached(rows,out,plan,protocol):
    import torch
    manifest=head.read(out/'features.json')
    if manifest['status']!='completed':raise ValueError('All current-state features must complete')
    expected={'protocol_sha256':head.sha(protocol),'encoder_weights_sha256':plan['encoder']['weights']['sha256'],
        'encoder_source_sha256':plan['encoder']['source']['sha256'],'planes_source_sha256':plan['encoder']['planes_source']['sha256'],
        'feature_pipeline_source_sha256':head.sha(Path(head.__file__)),'input_sha256':plan['cohort']['inputs']['sha256']}
    if any(manifest[key]!=value for key,value in expected.items()):raise ValueError('Feature cache provenance differs')
    records={row['case_id']:row for row in manifest['records']};loaded={};xs=[];indices=[]
    for row in rows:
        record=records[row['case_id']];packet=head.packet({key:row[key]for key in('fen','selected_uci')})
        if record['status']!='completed'or record['input_sha256']!=head.json_hash(packet):raise ValueError('Requested feature identity differs')
        path=out/record['shard']
        if path not in loaded:
            if head.sha(path)!=record['shard_sha256']:raise ValueError('Feature shard bytes changed')
            loaded[path]=torch.load(path,map_location='cpu',weights_only=True)
        value=loaded[path]
        if set(value)!={'features','indices'}:raise ValueError('Feature cache must be label-free')
        vector=value['features'][record['row']];move=value['indices'][record['row']]
        if(vector.dtype!=torch.float32 or move.dtype!=torch.int64 or tuple(vector.shape)!=(3072,)
            or not torch.isfinite(vector).all()or move.tolist()!=list(head.move_indices(packet))):
            raise ValueError('Exact original feature/index contract differs')
        xs.append(vector);indices.append(move)
    return torch.stack(xs),torch.stack(indices)


def raw_condition(rows,path,predict,batch_size):
    """No labels are accepted; persist every actual raw logit before scoring."""
    value=head.read(path);journal=path.with_suffix('.attempts.jsonl')
    for start in range(0,len(rows),batch_size):
        batch=rows[start:start+batch_size];ids=[row['case_id']for row in batch]
        append(journal,{'status':'started','ids':ids})
        value['raw']=head.recover_predictions(rows,journal);value['status']='started';head.save(path,value)
        try:
            logits=predict(start,start+len(batch))
            if len(logits)!=len(batch)or any(type(logit)not in(float,int)or not math.isfinite(logit)for logit in logits):
                raise ValueError('Malformed/nonfinite raw head logits')
            done=[{'case_id':case,'status':'completed','logit':float(logit),'prediction':logit>=0}
                for case,logit in zip(ids,logits)]
            append(journal,{'status':'completed','records':done})
        except Exception as error:
            message=type(error).__name__+': '+str(error)
            append(journal,{'status':'failed','records':[{'case_id':case,'status':'failed','error':message}for case in ids]})
            value.update(status='failed',error=message,raw=head.recover_predictions(rows,journal));head.save(path,value)
            raise RuntimeError('First raw head failure; no later condition: '+message)from error
        value['raw']=head.recover_predictions(rows,journal);head.save(path,value)
    value['status']='completed';head.save(path,value);return value


def load_labels_after_raw(plan,rows,out):
    for condition in CONDITIONS:
        value=head.read(out/(condition+'.json'))
        if(value['status']!='completed'or [row['case_id']for row in value['raw']]!=[row['case_id']for row in rows]
            or any(row['status']!='completed'for row in value['raw'])):
            raise ValueError('Both complete raw conditions required before labels open')
    labels=head.read(head.bound(plan['cohort']['labels']))['rows'];head.validate_labels(rows,labels)
    return labels


def grouped_scores(rows,labels,raw,dataset):
    def score_ids(ids):
        selected=[index for index,row in enumerate(rows)if row['case_id']in ids]
        if not selected:return {'planned':0,'pairs_planned':0,'correct':0,'pairs_correct':0,
            'checking_recall':None,'nonchecking_recall':None,'statuses':{},'confusion':{}}
        return head.score([rows[i]for i in selected],[labels[i]for i in selected],[raw[i]for i in selected])
    records=dataset['groups']['diagnostic']
    allocated={name:score_ids({case for row in records if row['allocation']==name for case in row['case_ids']})for name in intake.STRATA}
    overlap={flag:score_ids({case for row in records if row['positive'][flag]for case in row['case_ids']})
        for flag in('king_mover','pawn_mover','double_check','discovered_check')}
    return {'overall':head.score(rows,labels,raw),'by_allocation':allocated,'by_overlapping_positive_flags':overlap}


def run(plan,closed,protocol,out):
    rows=read_inputs(head.bound(plan['cohort']['inputs']))
    if len(rows)!=closed['constructed_moves']:raise ValueError('Actual input denominator differs')
    prepare_ledgers(out,rows,closed,plan,head.sha(protocol))
    try:
        guard_base=head.guard_for(out,plan['maximum_seconds'])
        def guard():
            if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Frozen13UTC cutoff')
            guard_base()
        guard()
        sources=out/'sources';sources.mkdir()
        copied={}
        for index,path in enumerate([Path(__file__),Path(protocol)]+[head.bound(item)for item in plan['dependencies']]):
            target=sources/f'{index:02d}-{path.name}';shutil.copyfile(path,target);copied[target.name]={'source':str(path),'sha256':head.sha(target)}
        head.save(sources/'manifest.json',copied)
        if not rows:raise ValueError('No actual constructed inputs; no backend calls')
        extract(plan,rows,out,guard);x,indices=cached(rows,out,plan,protocol)
        import torch
        for condition,key in zip(CONDITIONS,('original_untrained','selected')):
            guard();model=head.make_head()
            model.load_state_dict(torch.load(head.bound(plan[key]),map_location='cpu',weights_only=True),strict=True)
            if sum(value.numel()for value in model.parameters())!=1680169 or any(value.dtype!=torch.float32 or not torch.isfinite(value).all()for value in model.parameters()):
                raise ValueError('Actual saved head dtype/count/finite contract differs')
            model.to('cuda').eval().requires_grad_(False)
            def predict(start,end):
                guard()
                with torch.no_grad():return model(x[start:end].to('cuda'),indices[start:end].to('cuda')).float().cpu().tolist()
            raw_condition(rows,out/(condition+'.json'),predict,plan['batch_size'])
            del model;torch.cuda.empty_cache()
        labels=load_labels_after_raw(plan,rows,out)
        dataset=head.read(head.bound(plan['cohort']['dataset']))
        scores={condition:grouped_scores(rows,labels,head.read(out/(condition+'.json'))['raw'],dataset)for condition in CONDITIONS}
        majority=[{'case_id':row['case_id'],'status':'completed','prediction':False}for row in rows]
        scores['majority_false']=grouped_scores(rows,labels,majority,dataset)
        head.save(out/'scores.json',scores)
        head.save(out/'closed.json',{'status':'completed','planned_actual_moves_per_condition':len(rows),
            'source_requested_move_slots':128,'source_shortages':closed['shortages'],'protocol_sha256':head.sha(protocol),
            'labels_opened_after_both_raw_conditions':True,'training_updates':0,'checkpoint_selection':False,
            'claim':'Targeted check-classification generalization only; differing source-origin contrasts disclosed. No coaching/Elo claim.'})
    except Exception as error:
        head.save(out/'failure.json',{'status':'failed','error':type(error).__name__+': '+str(error),
            'planned_actual_moves_per_condition':len(rows),'source_requested_move_slots':128,'no_retry':True});raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,default=PROTOCOL)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise ValueError('Inference attempt directory must be new')
    try:
        plan,closed=verify(args.protocol);run(plan,closed,args.protocol,args.out)
    except Exception as error:
        args.out.mkdir(parents=True,exist_ok=True)
        if not(args.out/'failure.json').exists():head.save(args.out/'failure.json',{'status':'failed',
            'stage':'protocol_or_input_setup','error':type(error).__name__+': '+str(error),'model_calls_started':False})
        raise


if __name__=='__main__':main()
