"""Actual NEW TRAIN/dev tokenizer validation; CUDA initialization forbidden."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_train_v1 as pilot
checked=pilot.checked


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists():raise ValueError('CPU preflight is create-only')
    manifest=checked.nf4.base.read_json(args.data/'manifest.json')
    if manifest['status']!='ready_for_training':raise ValueError('Complete fresh corpus required')
    for name,identity in manifest['files'].items():
        if checked.nf4.base.digest(args.data/name)!=identity['sha256']:raise ValueError('Export bytes differ')
    import torch
    if torch.cuda.is_initialized():raise RuntimeError('Must start without CUDA')
    def forbid(*args,**kwargs):raise RuntimeError('CUDA initialization forbidden during CPU tokenization')
    torch.cuda._lazy_init=forbid
    from transformers import AutoTokenizer
    assets=checked.nf4.base.read_json(checked.nf4.base.MANIFEST)
    tokenizer_files={name:value for name,value in assets['files'].items()if name.startswith('tokenizer')or name in('chat_template.jinja','special_tokens_map.json','added_tokens.json')}
    checked.nf4.base.verify_files(checked.nf4.base.DEFAULT_ASSETS,tokenizer_files)
    tokenizer=AutoTokenizer.from_pretrained(checked.nf4.base.DEFAULT_ASSETS,local_files_only=True,trust_remote_code=False)
    source=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-source/utils/instance_format.py')
    spec=importlib.util.spec_from_file_location('official_counterfactual_format_cpu',source)
    official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
    result={'status':'started','source_sha256':checked.nf4.base.digest(Path(__file__)),
        'manifest_sha256':checked.nf4.base.digest(args.data/'manifest.json'),
        'tokenizer_bindings':tokenizer_files,'official_formatter_sha256':checked.nf4.base.digest(source),
        'model_weights_loaded':False,'learned_forward_calls':0,'splits':{}}
    for split,name,expected in [('train','train.jsonl',1536),('development','development.jsonl',96)]:
        rows=pilot.read_rows(args.data/name,True)
        if len(rows)!=expected:raise ValueError('Exact new corpus counts required')
        total=[];supervised=[]
        for row in rows:
            packet,_=checked.nf4.base.input_packet(row['input'])
            ids,labels,prefix=checked.tokenize_training(tokenizer,checked.nf4.base.prompt_for(packet),row['response'],official.tokenize_instance,maximum=512)
            parsed=checked.nf4.base.parse_output(packet,row['response'])
            if parsed['accepted_move_uci']is None or parsed['critical_line']['failure']is not None:raise ValueError('Invalid native target')
            total.append(len(ids));supervised.append(sum(value!=-100 for value in labels))
        result['splits'][split]={'records':len(rows),'groups':len({row['group_id']for row in rows}),
            'minimum_total_tokens':min(total),'maximum_total_tokens':max(total),'total_supervised_tokens':sum(supervised),
            'exact_integer_prefix_mask_eos_no_truncation':True}
    result.update(status='passed',cuda_initialized=torch.cuda.is_initialized())
    if result['cuda_initialized']:raise RuntimeError('Unexpected CUDA initialization')
    with args.out.open('x',encoding='utf-8')as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
