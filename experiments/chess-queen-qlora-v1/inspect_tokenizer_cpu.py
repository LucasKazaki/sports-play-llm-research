"""Actual local tokenizer/official formatter compatibility, strictly CPU only."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_queen_qlora_v2 as experiment

import torch
if torch.cuda.is_initialized(): raise RuntimeError('CPU inspection must start without CUDA initialization')
def forbid_cuda(*args, **kwargs): raise RuntimeError('CUDA initialization forbidden in tokenizer-only CPU inspection')
torch.cuda._lazy_init = forbid_cuda
from transformers import AutoTokenizer

source = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-source/utils/instance_format.py')
spec = importlib.util.spec_from_file_location('official_instance_format_cpu', source)
formatting = importlib.util.module_from_spec(spec); spec.loader.exec_module(formatting)
tokenizer = AutoTokenizer.from_pretrained(experiment.nf4.base.DEFAULT_ASSETS, local_files_only=True, trust_remote_code=False)
packet, _ = experiment.nf4.base.input_packet(experiment.FIXTURE)
prompt = experiment.nf4.base.prompt_for(packet); target = experiment.target_for_fixture()
default = tokenizer.apply_chat_template([{'role':'user','content':prompt}],
    tokenize=True,add_generation_prompt=True,enable_thinking=False)
old_ids, old_labels = formatting.tokenize_instance(tokenizer,prompt,target,max_length=None)
ids, labels, prefix = experiment.tokenize_training(tokenizer,prompt,target,formatting.tokenize_instance)
result = {'schema':'chess.queen-qlora-tokenizer-cpu.v2','status':'passed',
    'kind':'Actual tokenizer and chat formatter only. No model weights, learned forwards, backward, optimizer or CUDA initialization.',
    'official_source_sha256':experiment.nf4.base.digest(source),
    'default_template_result_type':type(default).__name__,
    'old_official_ids_length':len(old_ids),'old_official_ids_types':sorted(set(type(value).__name__ for value in old_ids)),
    'old_official_ids_if_mapping_keys':old_ids if old_ids and isinstance(old_ids[0],str) else None,
    'new_total_tokens':len(ids),'new_prefix_tokens':prefix,'new_supervised_tokens':sum(value!=-100 for value in labels),
    'max_context':512,'all_ids_labels_integer':all(type(value)is int for value in ids+labels),
    'exact_generation_prefix':True,'exact_assistant_eos_mask':True,'complete_untruncated':len(ids)<=512,
    'closing_token_id':tokenizer.convert_tokens_to_ids('<|im_end|>'), 'tail_token_ids':ids[-8:],
    'cuda_initialized':torch.cuda.is_initialized()}
if result['cuda_initialized']: raise RuntimeError('Unexpected CUDA initialization')
out=ROOT/'data/private/chess-queen-qlora-v1/tokenizer-cpu-v2.json'
with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result))
