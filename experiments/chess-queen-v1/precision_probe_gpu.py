"""Root-only tiny random BF16 cache diagnostic; no pretrained weights or chess task.

Run under gpu_worker.py only after exclusive GPU authorization. This numerical
software diagnostic does not establish real Queen cache parity or capability.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_adapter as adapter


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Receipt is create-only.')
    args.out.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    result={'schema':'chess.queen-tiny-bf16-cache-diagnostic.v1','status':'not_run',
        'started_at':datetime.now(timezone.utc).isoformat(),'pretrained_forwards':0,
        'kind':'Tiny random software probe; no chess capability measurement.',
        'source_sha256':adapter.digest(Path(__file__)),'adapter_sha256':adapter.digest(ROOT/'scripts/chess_queen_adapter.py'),
        'profiles':{},'resource_samples':[]}
    args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    try:
        import torch
        from transformers import SmolLM3Config,SmolLM3ForCausalLM
        from chess_native_resources import windows_sample,reasons,Policy,GIB
        policy=Policy(start_physical_available_bytes=6*GIB,start_commit_headroom_bytes=10*GIB,
            start_gpu_free_bytes=10*GIB,stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=4*GIB)
        def guard(first=False):
            sample=windows_sample();result['resource_samples'].append(asdict(sample))
            issues=reasons(sample,policy,'start' if first else 'running')
            if issues:raise RuntimeError('resource reserve: '+','.join(issues))
        guard(True);torch.manual_seed(20260823);torch.set_num_threads(2)
        source=adapter.read_json(adapter.SOURCE_MANIFEST);source_root=Path(source['checkout'])
        adapter.verify_files(source_root,source['files']);modules=adapter.import_audited_source(source_root)
        config=SmolLM3Config(vocab_size=97,hidden_size=64,intermediate_size=128,num_hidden_layers=36,
            num_attention_heads=4,num_key_value_heads=2,max_position_embeddings=128,
            layer_types=['full_attention']*36,attn_implementation='sdpa',pad_token_id=0,bos_token_id=1,eos_token_id=2)
        decoder=SmolLM3ForCausalLM(config).to(device='cuda',dtype=torch.bfloat16).eval()
        bridges=torch.nn.ModuleList([modules['models.flamingo'].DenseXAttn(8,64,n_heads=4,n_kv_heads=4) for _ in range(16)])
        with torch.no_grad():
            for bridge in bridges:bridge.W_O.weight.normal_(std=.03)
        bridges=bridges.to(device='cuda',dtype=torch.bfloat16).eval()
        encoded=torch.randn(1,16,64,8,device='cuda',dtype=torch.bfloat16)
        ids=torch.arange(1,18,device='cuda').reshape(1,-1)
        handles=adapter.board_conditioning_hooks(decoder,bridges,encoded)
        try:
            for profile in adapter.PRECISION_PROFILES:
                rows=[]
                with torch.inference_mode(),adapter.precision_context(torch,profile):
                    prefill=decoder(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=True,logits_to_keep=1)
                    past=prefill.past_key_values;next_id=prefill.logits[:,-1].argmax(-1,keepdim=True);full=ids
                    for step in range(1,4):
                        guard();full=torch.cat((full,next_id),dim=1)
                        cached=decoder(input_ids=next_id,attention_mask=torch.ones_like(full),past_key_values=past,use_cache=True,logits_to_keep=1)
                        plain=decoder(input_ids=full,attention_mask=torch.ones_like(full),use_cache=False,logits_to_keep=1)
                        left,right=cached.logits[0,-1].float(),plain.logits[0,-1].float();delta=(left-right).abs()
                        rows.append({'step':step,'max_absolute_error':float(delta.max()),'mean_absolute_error':float(delta.mean()),
                            'cosine_similarity':float(torch.nn.functional.cosine_similarity(left,right,dim=0)),
                            'same_top1':int(left.argmax())==int(right.argmax()),'finite':bool(torch.isfinite(left).all() and torch.isfinite(right).all())})
                        past=cached.past_key_values;next_id=cached.logits[:,-1].argmax(-1,keepdim=True)
                result['profiles'][profile]=rows
        finally:
            for handle in handles:handle.remove()
        result.update(status='completed',peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated())
    except Exception as error:result.update(status='failed',error=type(error).__name__+': '+str(error))
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    raise SystemExit(0 if result['status']=='completed' else 2)


if __name__=='__main__':main()
