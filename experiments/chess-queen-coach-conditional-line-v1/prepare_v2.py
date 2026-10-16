"""Prospective target-only TRAIN/DEV export and lazy CPU full-token readiness."""
import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime, timezone
import targets

HERE=Path(__file__).resolve().parent
FILES={'train.jsonl':1536,'development.jsonl':96,'train-references.jsonl':1536,'development-references.jsonl':96}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bound(value):
    path=Path(value['path'])
    if digest(path)!=value['sha256']:raise ValueError('Frozen bytes changed: '+str(path))
    return path


def pairs(values):
    out={}
    for key,value in values:
        if key in out:raise ValueError('Duplicate JSON key')
        out[key]=value
    return out


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
def rows(path):return [json.loads(line,object_pairs_hook=pairs)for line in Path(path).read_text().splitlines()if line.strip()]


def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8')as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def append(path,value):
    with Path(path).open('a',encoding='utf-8')as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def verify_helpers(path):
    def functions(source):
        return {node.name:ast.dump(node)for node in ast.parse(Path(source).read_text()).body if isinstance(node,ast.FunctionDef)}
    original=functions(path);current=functions(Path(targets.__file__))
    if any(original[name]!=current[name]for name in ['piece_atom','move_atom','move_facts']):raise ValueError('Copied rule helper AST differs')


def aligned(data,refs,count,groups):
    if(len(data)!=count or len(refs)!=count or len({row['case_id']for row in data})!=count
        or len({row['case_id']for row in refs})!=count):raise ValueError('Full unique presentation denominator required')
    by_case={row['case_id']:row for row in refs}
    if set(by_case)!={row['case_id']for row in data}:raise ValueError('Reference IDs differ')
    by_group={}
    for row in data:by_group.setdefault(row['group_id'],[]).append(row)
    if len(by_group)!=groups:raise ValueError('Exact source-game denominator required')
    for values in by_group.values():
        if len(values)!=3 or {row['mode']for row in values}!={'free','selected_a','selected_b'}:raise ValueError('Three exact presentations per source game required')
        if len({row['input']['fen']for row in values})!=1:raise ValueError('Matched group boards differ')
    return by_case


def export(protocol,out):
    if out.exists():raise ValueError('Target export is create-only')
    started=time.monotonic();plan=read(protocol);out.mkdir(parents=True)
    result={'status':'started','planned':1632,'completed':0,'active_unknown':0,'not_run':1632,'protocol_sha256':digest(protocol)}
    save(out/'closed.json',result)
    try:
        if(plan['schema']!='chess.conditional-target-export.v1' or plan['implementation_sha256']!=digest(__file__)
            or plan['maximum_seconds']!=900 or plan['cutoff_utc']!='2026-10-16T22:00:00+00:00'):raise ValueError('Wrong source/plan/clock')
        for item in plan['dependencies']:bound(item)
        verify_helpers(bound(plan['original_rule_helper']))
        parent=read(bound(plan['parent_manifest']));source=Path(plan['source_dir'])
        if read(bound(plan['parent_closed_audit']))['status']!='passed':raise ValueError('Closed parent audit required')
        if parent['status']!='ready_for_training' or set(plan['source_files'])!=set(FILES):raise ValueError('Only four TRAIN/DEV files allowed')
        snapshots=out/'executed-sources';snapshots.mkdir();snapshot_files=[]
        for index,path in enumerate([Path(protocol),Path(__file__)]+[bound(item)for item in plan['dependencies']]):
            target=snapshots/f'{index:02d}-{path.name}';shutil.copyfile(path,target)
            snapshot_files.append({'source':str(path),'copy':target.name,'sha256':digest(target)})
        save(snapshots/'manifest.json',snapshot_files)
        source_paths={}
        for name,count in FILES.items():
            item=plan['source_files'][name]
            if Path(item['path']).resolve()!=(source/name).resolve()or item['sha256']!=parent['files'][name]['sha256']or parent['files'][name]['rows']!=count:raise ValueError('Exact audited source binding/count differs')
            source_paths[name]=bound(item)
        splits={};group_sets=[]
        for split,count,groups in [('train',1536,512),('development',96,32)]:
            data=rows(source_paths[split+'.jsonl']);refs=rows(source_paths[split+'-references.jsonl'])
            by_case=aligned(data,refs,count,groups);group_sets.append({row['group_id']for row in data})
            lengths=Counter();inputs=[]
            with(out/(split+'.jsonl')).open('x',encoding='utf-8')as stream:
                for row in data:
                    if time.monotonic()-started>=900 or (out/'CANCEL').exists() or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Owned export phase/cancel/global limit')
                    append(out/'transform.jsonl',{'status':'started','case_id':row['case_id'],'split':split})
                    result.update(active_unknown=1,active_case_id=row['case_id']);result['not_run']-=1
                    changed=targets.transform_case(row,by_case[row['case_id']])
                    stream.write(json.dumps(changed,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
                    lengths[len(by_case[row['case_id']]['reference_pv_uci'])]+=1;inputs.append(targets.input_hash(row['input']))
                    result['completed']+=1;result['active_unknown']=0;result.pop('active_case_id',None)
                    append(out/'transform.jsonl',{'status':'completed','case_id':row['case_id'],'input_sha256':inputs[-1]})
            shutil.copyfile(source_paths[split+'-references.jsonl'],out/(split+'-references.jsonl'))
            splits[split]={'presentations':count,'source_games':groups,'reference_length_counts':dict(lengths),
                'ordered_model_input_hash':hashlib.sha256(json.dumps(inputs).encode()).hexdigest()}
        if group_sets[0]&group_sets[1]:raise ValueError('TRAIN/development group overlap')
        files={name:{'sha256':digest(out/name),'rows':count}for name,count in FILES.items()}
        save(out/'manifest.json',{'schema':'chess.conditional-targets.v1','status':'ready_for_training',
            'tokenizer_readiness':'pending_separate_full512_CPU_gate','files':files,'splits':splits,
            'parent_manifest':plan['parent_manifest'],'source_files':plan['source_files'],
            'protocol_sha256':digest(protocol),'model_inputs_changed':False,'stored_PVs_changed':False,
            'new_held_or_reserve_content_read':False,'model_or_engine_calls':0})
        result.update(status='completed',manifest_sha256=digest(out/'manifest.json'))
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:save(out/'closed.json',result)
    return result


def verify_tokenizer_sources(plan):
    """Check both immediate tokenizer and every frozen export-source pin before imports."""
    for item in plan['dependencies']:bound(item)
    parent=read(bound(plan['target_export_protocol']))
    if parent.get('schema')!='chess.conditional-target-export.v1':raise ValueError('Wrong parent export protocol')
    for item in parent['dependencies']:bound(item)
    native=Path(targets.native.__file__).resolve()
    if not any(Path(item['path']).resolve()==native and item['sha256']==digest(native)for item in plan['dependencies']):
        raise ValueError('Direct actual native adapter binding required')
    return parent


def tokenizer_gate(protocol,data,out):
    if out.exists():raise ValueError('CPU tokenizer gate is create-only')
    started=time.monotonic();plan=read(protocol);manifest=read(bound(plan['target_manifest']));planned=[]
    if(Path(plan['target_manifest']['path']).resolve()!=(data/'manifest.json').resolve()
        or manifest['schema']!='chess.conditional-targets.v1'):raise ValueError('Exact new target manifest required')
    for split in ['train','development']:
        path=data/(split+'.jsonl')
        if digest(path)!=manifest['files'][path.name]['sha256']:raise ValueError('New targets changed')
        data_rows=rows(path)
        aligned(data_rows,data_rows,FILES[path.name],512 if split=='train' else 32)
        planned.extend({'split':split,'case':row,'status':'not_run'}for row in data_rows)
    if len(planned)!=1632:raise ValueError('Full1632 CPU tokenizer denominator required')
    result={'status':'started','planned':1632,'completed':0,'active_unknown':0,'not_run':1632,'manifest_sha256':digest(data/'manifest.json'),
        'model_weights_loaded':False,'learned_forward_calls':0,'maximum_total_tokens':512}
    save(out,result)
    try:
        if(plan['schema']!='chess.conditional-tokenizer.v1' or plan['implementation_sha256']!=digest(__file__)
            or plan['maximum_seconds']!=600 or plan['total_token_limit']!=512
            or plan['cutoff_utc']!='2026-10-16T22:00:00+00:00'):raise ValueError('Wrong CPU token source/protocol/clock')
        for item in plan['dependencies']:bound(item)
        verify_tokenizer_sources(plan)
        source=bound(plan['official_formatter']);assets=read(bound(plan['tokenizer_asset_manifest']))
        tokenizer_files={name:value for name,value in assets['files'].items()if name.startswith('tokenizer')or name in('chat_template.jinja','special_tokens_map.json','added_tokens.json')}
        for name,value in tokenizer_files.items():
            if digest(Path(plan['tokenizer_assets'])/name)!=value['sha256']:raise ValueError('Tokenizer asset differs')
        import torch
        if torch.cuda.is_initialized():raise RuntimeError('CPU gate requires no CUDA')
        def forbid(*args,**kwargs):raise RuntimeError('CUDA initialization forbidden in tokenizer gate')
        torch.cuda._lazy_init=forbid
        from transformers import AutoTokenizer
        import chess_queen_qlora_v2 as checked
        tokenizer=AutoTokenizer.from_pretrained(plan['tokenizer_assets'],local_files_only=True,trust_remote_code=False)
        spec=importlib.util.spec_from_file_location('conditional_official_format_cpu',source)
        official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
        result.update(tokenizer_bindings=tokenizer_files,official_formatter_sha256=digest(source));lengths={}
        for item in planned:
            if time.monotonic()-started>=600 or out.with_suffix('.CANCEL').exists()or datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Owned tokenizer phase/cancel/global limit')
            row=item['case'];item['status']='active_unknown'
            result['not_run']-=1;result['active_unknown']=1
            append(out.with_suffix('.journal.jsonl'),{'status':'started','case_id':row['case_id']})
            packet,_=targets.native.input_packet(row['input'])
            ids,labels,prefix=checked.tokenize_training(tokenizer,targets.native.prompt_for(packet),row['response'],official.tokenize_instance,maximum=512)
            if len(ids)>512 or not ids or not any(value!=-100 for value in labels):raise ValueError('Whole-example512 gate failed')
            item['status']='completed';result['completed']+=1;result['active_unknown']=0;lengths.setdefault(item['split'],[]).append(len(ids))
            append(out.with_suffix('.journal.jsonl'),{'status':'completed','case_id':row['case_id'],'total_tokens':len(ids),'supervised_tokens':sum(value!=-100 for value in labels)})
        result.update(status='passed',cuda_initialized=torch.cuda.is_initialized(),exact_prefix_mask_eos_untruncated=True,
            splits={split:{'records':len(values),'min':min(values),'max':max(values),'median':sorted(values)[len(values)//2]}for split,values in lengths.items()})
        if result['cuda_initialized']:raise RuntimeError('Unexpected CUDA initialization')
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        result['outcomes']=[{'case_id':item['case']['case_id'],'split':item['split'],'status':item['status']}for item in planned]
        save(out,result)
    return result


def freeze_export(source_dir,parent_manifest,parent_audit,out):
    """Prospective metadata-only plan creation; no source row or reference body opened."""
    if out.exists():raise ValueError('Protocol is create-only')
    parent=read(parent_manifest)
    if parent['status']!='ready_for_training':raise ValueError('Audited complete parent required')
    binding=lambda path:{'path':str(Path(path).resolve()),'sha256':digest(path)}
    sources=[HERE/name for name in ['targets.py','evaluate_v2.py','prepare_v2.py','test_targets_evaluate.py','test_evaluate_v2.py','test_prepare_v2.py']]
    sources += [targets.ROOT/'scripts'/name for name in ['chess_queen_adapter.py','chess_queen_coach_counterfactual_eval_v1.py','chess_queen_coach_sft_eval_v1.py','chess_queen_coach_sft_intake_v1.py']]
    source_files={name:{'path':str((source_dir/name).resolve()),'sha256':parent['files'][name]['sha256']}for name in FILES}
    if any(parent['files'][name]['rows']!=count for name,count in FILES.items()):raise ValueError('Exact1536/96 counts required')
    plan={'schema':'chess.conditional-target-export.v1','implementation_sha256':digest(__file__),
        'source_dir':str(source_dir.resolve()),'source_files':source_files,'parent_manifest':binding(parent_manifest),
        'parent_closed_audit':binding(parent_audit),'original_rule_helper':binding(sources[-1]),
        'dependencies':[binding(path)for path in sources]+[binding(parent_manifest),binding(parent_audit)],
        'cutoff_utc':'2026-10-16T22:00:00+00:00','maximum_seconds':900,
        'single_change':'conditional target prose only; same input/group/PV/order/1536+96',
        'no_held_reserve_combined_teacher_access':True,'model_or_engine_calls_permitted':False}
    with out.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return binding(out)


def freeze_tokenizer(data,parent_export_protocol,out,official_formatter):
    if out.exists():raise ValueError('Protocol is create-only')
    binding=lambda path:{'path':str(Path(path).resolve()),'sha256':digest(path)}
    plan={'schema':'chess.conditional-tokenizer.v1','implementation_sha256':digest(__file__),
        'target_manifest':binding(data/'manifest.json'),'target_export_protocol':binding(parent_export_protocol),
        'official_formatter':binding(official_formatter),'tokenizer_asset_manifest':binding(targets.native.MANIFEST),
        'tokenizer_assets':str(targets.native.DEFAULT_ASSETS),'maximum_seconds':600,'total_token_limit':512,
        'cutoff_utc':'2026-10-16T22:00:00+00:00','no_truncation_or_row_replacement':True,
        'dependencies':[binding(HERE/name)for name in ['prepare_v2.py','targets.py']]+[
            binding(targets.ROOT/'scripts/chess_queen_qlora_v2.py'),binding(Path(targets.native.__file__)),
            binding(targets.native.MANIFEST),binding(official_formatter),
            binding(parent_export_protocol),binding(data/'manifest.json')]}
    with out.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return binding(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['export','tokenizer'])
    for name in ['protocol','out']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--data',type=Path);args=parser.parse_args()
    if args.phase=='export':export(args.protocol,args.out)
    else:
        if not args.data:parser.error('--data required for tokenizer')
        tokenizer_gate(args.protocol,args.data,args.out)
