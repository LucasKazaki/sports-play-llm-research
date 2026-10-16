"""Actual corpus/tokenizer preflight with CUDA initialization forbidden."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_train_v1 as pilot
checked=pilot.checked

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data',type=Path,default=ROOT/'data/private/chess-queen-coach-sft-v1')
parser.add_argument('--out',type=Path,default=ROOT/'data/private/chess-queen-coach-sft-v1/tokenizer-preflight.json')
args=parser.parse_args()
if args.out.exists():raise ValueError('CPU tokenizer preflight is create-only')
manifest=checked.nf4.base.read_json(args.data/'manifest.json')
if manifest['status']!='ready_for_training':raise ValueError('Actual corpus has not closed')
for name,identity in manifest['files'].items():
    if checked.nf4.base.digest(args.data/name)!=identity['sha256']:raise ValueError('Corpus file differs: '+name)
import torch
if torch.cuda.is_initialized():raise RuntimeError('CPU preflight must start withoutCUDA')
def forbid_cuda(*args,**kwargs):raise RuntimeError('CUDA initialization forbidden in corpus tokenizer preflight')
torch.cuda._lazy_init=forbid_cuda
from transformers import AutoTokenizer

assets=checked.nf4.base.read_json(checked.nf4.base.MANIFEST)
tokenizer_files={name:value for name,value in assets['files'].items()if name.startswith('tokenizer')or name in('chat_template.jinja','special_tokens_map.json','added_tokens.json')}
checked.nf4.base.verify_files(checked.nf4.base.DEFAULT_ASSETS,tokenizer_files)
tokenizer=AutoTokenizer.from_pretrained(checked.nf4.base.DEFAULT_ASSETS,local_files_only=True,trust_remote_code=False)
source=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-source/utils/instance_format.py')
spec=importlib.util.spec_from_file_location('official_coach_format_cpu',source)
official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
result={'schema':'chess.queen-coach-cpu-tokenizer.v1','status':'started','model_weights_loaded':False,
    'learned_forward_calls':0,'cuda_initialized':False,'source_sha256':checked.nf4.base.digest(Path(__file__)),
    'manifest_sha256':checked.nf4.base.digest(args.data/'manifest.json'),
    'tokenizer_bindings':tokenizer_files,'splits':{}}
for split,name,expected in(('train','train.jsonl',2048),('development','development.jsonl',64)):
    rows=pilot.read_rows(args.data/name,True)
    if len(rows)!=expected:raise ValueError('Unexpected corpus count')
    counts=[];supervised=[]
    for row in rows:
        packet,_=checked.nf4.base.input_packet(row['input'])
        ids,labels,prefix=checked.tokenize_training(tokenizer,checked.nf4.base.prompt_for(packet),row['response'],official.tokenize_instance)
        parsed=checked.nf4.base.parse_output(packet,row['response'])
        if parsed['accepted_move_uci']is None or parsed['critical_line']['failure']is not None:
            raise ValueError('Invalid native supervised target: '+row['case_id'])
        counts.append(len(ids));supervised.append(sum(value!=-100 for value in labels))
    result['splits'][split]={'records':len(rows),'groups':len({row['group_id']for row in rows}),
        'minimum_total_tokens':min(counts),'maximum_total_tokens':max(counts),
        'total_supervised_tokens':sum(supervised),'all_integer_exact_prefix_mask_eos':True}
result.update(status='passed',cuda_initialized=torch.cuda.is_initialized())
if result['cuda_initialized']:raise RuntimeError('UnexpectedCUDAinitialization')
with args.out.open('x',encoding='utf-8')as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps(result))
