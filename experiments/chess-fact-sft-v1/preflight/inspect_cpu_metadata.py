"""Pinned local config/tokenizer/meta inspection. No weight load or pretrained forward."""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq
import torch
from accelerate import init_empty_weights
from peft import LoraConfig,get_peft_model
from transformers import AutoConfig,AutoModelForCausalLM,AutoTokenizer
from transformers.models.qwen3.modeling_qwen3 import Qwen3ForCausalLM
from transformers.loss.loss_utils import ForCausalLMLoss

HERE=Path(__file__).resolve().parent
REPO=HERE.parent/'repos/sports-play-llm-research'
BASE=REPO/'data/private/chess-fact-sft-v1/models/base'
sys.path.insert(0,str(HERE.parent))
import board_fact_core as core

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):h.update(chunk)
    return h.hexdigest()
config=AutoConfig.from_pretrained(BASE,local_files_only=True,trust_remote_code=False)
tok=AutoTokenizer.from_pretrained(BASE,local_files_only=True,trust_remote_code=False)
with init_empty_weights():
    model=AutoModelForCausalLM.from_config(config,dtype=torch.bfloat16,attn_implementation='sdpa',trust_remote_code=False)
before_tie={'unique_meta_parameters':sum(p.numel() for p in model.parameters()),
            'input_output_tied_identity':model.get_input_embeddings().weight is model.get_output_embeddings().weight}
model.tie_weights()
after_tie={'unique_meta_parameters':sum(p.numel() for p in model.parameters()),
           'input_output_tied_identity':model.get_input_embeddings().weight is model.get_output_embeddings().weight}
targets=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']
modules={n:[m.in_features,m.out_features] for n,m in model.named_modules() if n.split('.')[-1] in targets}
model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.,bias='none',target_modules=targets,task_type='CAUSAL_LM'))
assert all(p.device.type=='meta' for p in model.parameters())
assert after_tie=={'unique_meta_parameters':596049920,'input_output_tied_identity':True}
def ids(messages,generation):
    result=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=generation,enable_thinking=False)
    return list(result['input_ids']) if hasattr(result,'keys') else list(result)
fixtures=[
 ('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','e2e4'),
 ('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1','e7e5'),
 ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1'),
 ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6'),
 ('4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1','e4d3'),
 ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1','a7a8q'),
 ('1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1','a7b8n'),
 ('4k3/8/8/8/8/8/p7/4K3 b - - 0 1','a2a1q'),
 ('4k3/8/8/8/8/8/4B3/4R1K1 w - - 0 1','e2f3'),
 ('4k3/8/3p4/8/4N3/8/8/4K3 w - - 0 1','e4d6')]
checks=[]
for fen,move in fixtures:
    row={'fen':fen,'selected_uci':move}
    facts=core.expected_facts(fen,move)
    assert facts==core.independent_facts(fen,move)
    target=json.dumps(facts,sort_keys=True,separators=(',',':'))
    prompt=core.build_prompt(row,'fen_uci_piece_map')
    messages=[{'role':'user','content':prompt}]
    prefix=ids(messages,True)
    joint=ids(messages+[{'role':'assistant','content':target}],False)
    assert joint[:len(prefix)]==prefix
    eos=next(i for i in range(len(prefix),len(joint)) if joint[i]==tok.eos_token_id)
    training=joint[:eos+1]
    target_ids=training[len(prefix):]
    assert target_ids[-1]==151645 and len(target_ids)+1<=128
    assert tok.decode(target_ids[:-1],skip_special_tokens=False)==target
    assert tok.decode(joint[eos+1:],skip_special_tokens=False)=='\n'
    checks.append({'fen':fen,'move':move,'prompt_tokens':len(prefix),'full_native_joint_tokens':len(joint),
        'training_joint_tokens_through_assistant_EOS':len(training),'supervised_JSON_plus_EOS_tokens':len(target_ids),
        'native_prefix_match':True,'post_EOS_newline_omitted':True})
source=REPO/'data/private/chess-fact-sft-v1/source/lichess-hf-train-00000.parquet'
metadata=pq.ParquetFile(source)
sources={}
for name,obj in [('qwen3-forward.py.txt',Qwen3ForCausalLM.forward),('causal-lm-loss.py.txt',ForCausalLMLoss)]:
    p=HERE/name;p.write_text(inspect.getsource(obj));sources[name]=sha(p)
report={'schema':'chess.fact-sft.cpu-metadata-inspection.v1','pretrained_weight_loads':0,'pretrained_forwards':0,'GPU_calls':0,
 'cohort_rows_selected':0,'versions':{p:importlib.metadata.version(p) for p in ('torch','transformers','peft','accelerate','pyarrow','tokenizers')},
 'model_card_stored_BF16_scalar_count':751632384,'meta_before_explicit_tie':before_tie,'meta_after_explicit_tie':after_tie,
 'runtime_caveat':'Meta inspection is not actual loaded-model verification. Training must verify tied identity and unique count after from_pretrained before any forward.',
 'target_linear_modules':len(modules),'target_modules_sha256':hashlib.sha256(json.dumps(modules,sort_keys=True).encode()).hexdigest(),
 'first_layer_shapes':{n:s for n,s in modules.items() if '.layers.0.' in n},
 'rank8_adapter_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
 'trainable_meta_dtypes':sorted({str(p.dtype) for p in model.parameters() if p.requires_grad}),
 'tokenizer':{'class':type(tok).__name__,'pad_token_id':tok.pad_token_id,'eos_token_id':tok.eos_token_id,'padding_side_for_proposal':'left'},
 'hand_fixture_native_token_checks':checks,'minimum_prompt_tokens':min(c['prompt_tokens'] for c in checks),
 'maximum_prompt_tokens':max(c['prompt_tokens'] for c in checks),
 'minimum_target_tokens':min(c['supervised_JSON_plus_EOS_tokens'] for c in checks),
 'maximum_target_tokens':max(c['supervised_JSON_plus_EOS_tokens'] for c in checks),
 'parquet_metadata_only':{'rows':metadata.metadata.num_rows,'row_groups':metadata.metadata.num_row_groups,'columns':metadata.schema.names,'selected_rows':0},
 'local_model_source_sha256':{p.name:sha(p) for p in BASE.iterdir() if p.is_file() and p.name!='model.safetensors'},
 'installed_source_sha256':{str(Path(inspect.getfile(obj))):sha(inspect.getfile(obj)) for obj in (Qwen3ForCausalLM,ForCausalLMLoss)},
 'reviewed_source_extract_sha256':sources,'inspection_source_sha256':sha(Path(__file__))}
(HERE/'cpu-metadata-inspection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('meta_after_explicit_tie','target_linear_modules','rank8_adapter_parameters',
 'minimum_prompt_tokens','maximum_prompt_tokens','minimum_target_tokens','maximum_target_tokens','parquet_metadata_only')},indent=2))
