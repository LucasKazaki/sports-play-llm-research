"""Explicit exclusive-device preflight. Do not run during another GPU job.

One authored board fixture; no engine or held-out data. The caller owns process
serialization and resource guard. This file is prepared before any forward.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_adapter as adapter

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Receipt path is create-only.')
    import torch
    from accelerate import init_empty_weights
    from chess_native_resources import windows_sample,reasons,Policy,GIB
    first=True;resources=[]
    policy=Policy(start_physical_available_bytes=6*GIB,start_commit_headroom_bytes=10*GIB,
        start_gpu_free_bytes=10*GIB,stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=6*GIB)
    def guard():
        nonlocal first
        from dataclasses import asdict
        sample=windows_sample();resources.append(asdict(sample))
        issues=reasons(sample,policy,'start' if first else 'running');first=False
        if issues:raise RuntimeError('resource reserve: '+','.join(issues))
    model=adapter.NativeQueen(device=args.device,guard=guard)
    started=time.monotonic();model.load()
    packet,board=adapter.input_packet({'fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'})
    ids=model.tokenizer.apply_chat_template([{'role':'user','content':adapter.prompt_for(packet)}],
        tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
    ids=torch.tensor([ids],dtype=torch.long,device=args.device)
    dtype=next(model.model.parameters()).dtype
    # Keep one shared pretrained decoder and bridge set, avoiding a second full
    # model allocation. Only the upstream manual execution path is reconstructed.
    with init_empty_weights():
        manual=model.modules['models.flamingo'].FlamingoChessLM(model.model,
            model.modules['models.adapters.smollm'].SmolLM3Adapter(model.model),n_new_tokens=0,lora_rank=-1)
    manual.x_attn_layers=model.bridges;manual.eval()
    with torch.inference_mode():
        planes=model.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']],[[]]).to(args.device)
        encoded=model.modules['utils.utils'].encode_planes(model.encoder,planes,dtype,pov=True)
        assert tuple(encoded.shape)==(1,16,64,1024) and torch.isfinite(encoded).all()
        guard()
        manual_hidden=manual._hidden_states(ids,encoded,attention_mask=torch.ones_like(ids))[:,-1:]
        expected=model.model.lm_head(manual_hidden)[0,-1].float()
        handles=adapter.board_conditioning_hooks(model.model,model.bridges,encoded)
        try:
            actual=model.model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,logits_to_keep=1).logits[0,-1].float()
            prefill=model.model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=True,logits_to_keep=1)
            next_id=prefill.logits[:,-1].argmax(-1,keepdim=True)
            full=torch.cat((ids,next_id),dim=1)
            cached=model.model(input_ids=next_id,attention_mask=torch.ones_like(full),past_key_values=prefill.past_key_values,use_cache=True,logits_to_keep=1).logits[0,-1].float()
            uncached=model.model(input_ids=full,attention_mask=torch.ones_like(full),use_cache=False,logits_to_keep=1).logits[0,-1].float()
        finally:
            for handle in handles:handle.remove()
    def compare(left,right):
        delta=(left-right).abs()
        return {'max_absolute_error':float(delta.max()),'mean_absolute_error':float(delta.mean()),
            'cosine_similarity':float(torch.nn.functional.cosine_similarity(left,right,dim=0)),
            'top1_equal':int(left.argmax())==int(right.argmax()),'finite':bool(torch.isfinite(left).all() and torch.isfinite(right).all())}
    hook,cache=compare(expected,actual),compare(cached,uncached)
    # Frozen software parity tolerances, not thresholds chosen after measurement.
    thresholds={'hook_max_absolute_error':.01,'cache_max_absolute_error':.25,
                'cache_mean_absolute_error':.01,'minimum_cosine_similarity':.9999,'same_top1_required':True}
    passed=(hook['finite'] and cache['finite'] and hook['top1_equal'] and cache['top1_equal']
        and hook['max_absolute_error']<=thresholds['hook_max_absolute_error']
        and cache['max_absolute_error']<=thresholds['cache_max_absolute_error']
        and cache['mean_absolute_error']<=thresholds['cache_mean_absolute_error']
        and min(hook['cosine_similarity'],cache['cosine_similarity'])>=thresholds['minimum_cosine_similarity'])
    guard()
    result={'schema':'chess.queen-native-pretrained-parity.v1','status':'passed' if passed else 'failed',
        'device':args.device,'input':packet,'kind':'Authored software fixture; not a held-out chess evaluation.',
        'hook_vs_upstream_manual':hook,'cache_vs_no_cache':cache,'frozen_tolerances':thresholds,
        'adapter_sha256':adapter.digest(ROOT/'scripts/chess_queen_adapter.py'),
        'parity_source_sha256':adapter.digest(Path(__file__)),
        'asset_manifest_sha256':adapter.digest(adapter.MANIFEST),'source_manifest_sha256':adapter.digest(adapter.SOURCE_MANIFEST),
        'encoder_shape':list(encoded.shape),'elapsed_seconds':time.monotonic()-started,'resource_samples':resources,
        'limitations':'Numerical port verification on one authored input; no chess strength, coaching quality, or paper Elo reproduction.'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result));raise SystemExit(0 if passed else 2)

if __name__=='__main__':main()
