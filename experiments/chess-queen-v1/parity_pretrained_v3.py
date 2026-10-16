"""One exclusive-device numerical preflight with vocabulary and cache coverage.

Authored software fixture only. Synthetic chess-token suffix exercises the
merged vocabulary; it is not a chess task response or capability measurement.
No engine or held-out data is used. Every attempted run retains a receipt.
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

THRESHOLDS={'hook_max_absolute_error':.01,'cache_max_absolute_error':.25,
    'cache_mean_absolute_error':.01,'minimum_cosine_similarity':.9999,
    'same_top1_required':True,'cached_steps':3}
FIXTURE={'fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'}
SUFFIX='<SQUARE_1><PIECE_MP><EMPTY>'
GIB=1024**3
RESOURCE_POLICY={'start_physical_available_bytes':6*GIB,'start_commit_headroom_bytes':10*GIB,
    'start_gpu_free_bytes':10*GIB,'stop_physical_available_bytes':4*GIB,
    'stop_commit_headroom_bytes':5*GIB,'stop_gpu_free_bytes':GIB}
PRIOR_ATTEMPTS=[
    {'path':'data/private/chess-queen-v1/parity-authored-v2-1.json',
     'sha256':'49c59e9b7652ceb71ceb2e9337f0da30d7dee0fc65027be516852650aa9f26be'},
    {'path':'data/private/chess-queen-v1/parity-authored-v2-2.json',
     'sha256':'a9d0ba7acceace068efa7039e92c3fbaf76a3d41ddfce0e1025ea5257e50b3db'}]
AMENDMENT_REASON=('Both prior attempts stopped at the commit reserve before any model forward, without GPU OOM. '
    'After the meta loading repair, decoder, bridges and encoder loaded with 6,440,951,808 bytes commit headroom, '
    '1,499,136 bytes below the former 6GiB reserve; physical free was 11,960,287,232 bytes and GPU free 7,047,479,296 bytes. '
    'The authorized inference-only running commit reserve is now 5GiB; numerical tolerances, start reserves, '
    '4GiB running physical and 1GiB running GPU reserves remain unchanged. Actual activation pressure remains to be measured.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Receipt path is create-only.')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    result={'schema':'chess.queen-native-pretrained-parity.v3','status':'not_run',
        'started_at':datetime.now(timezone.utc).isoformat(),'device':args.device,'input':FIXTURE,
        'kind':'Authored numerical software fixture; not a chess evaluation.',
        'synthetic_vocabulary_suffix':SUFFIX,'frozen_tolerances':THRESHOLDS,
        'resource_policy':RESOURCE_POLICY,'resource_policy_reason':AMENDMENT_REASON,'prior_attempts':PRIOR_ATTEMPTS,
        'adapter_sha256':adapter.digest(ROOT/'scripts/chess_queen_adapter.py'),
        'parity_source_sha256':adapter.digest(Path(__file__)),
        'asset_manifest_sha256':adapter.digest(adapter.MANIFEST),
        'source_manifest_sha256':adapter.digest(adapter.SOURCE_MANIFEST),'resource_samples':[],
        'limitations':['Synthetic vocabulary tokens are appended solely for numerical port verification; this is not a no-forward capability candidate.',
                       'One authored input cannot establish chess strength, coaching quality, or published Elo parity.']}
    # Persist the intent before model construction, then preserve failures too.
    args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    try:
        for prior in PRIOR_ATTEMPTS:
            if adapter.digest(ROOT/prior['path'])!=prior['sha256']:
                raise ValueError('Prior failed attempt receipt binding differs.')
        import torch
        from accelerate import init_empty_weights
        from chess_native_resources import windows_sample,reasons,Policy
        first=True
        policy=Policy(**RESOURCE_POLICY)
        def guard():
            nonlocal first
            sample=windows_sample();result['resource_samples'].append(asdict(sample))
            issues=reasons(sample,policy,'start' if first else 'running');first=False
            if issues:raise RuntimeError('resource reserve: '+','.join(issues))
        native=adapter.NativeQueen(device=args.device,guard=guard)
        native.load()
        packet,_=adapter.input_packet(FIXTURE)
        ids=native.tokenizer.apply_chat_template([{'role':'user','content':adapter.prompt_for(packet)}],
            tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
        suffix_ids=native.tokenizer.encode(SUFFIX,add_special_tokens=False)
        if len(suffix_ids)!=3 or any(token<adapter.FROZEN_VOCAB for token in suffix_ids):
            raise ValueError('The numerical probe did not reach the Queen vocabulary suffix.')
        result['synthetic_suffix_token_ids']=suffix_ids
        ids=torch.tensor([ids+suffix_ids],dtype=torch.long,device=args.device)
        dtype=next(native.model.parameters()).dtype
        # Reuse the exact decoder and bridge weights. Meta allocation avoids a
        # second full cross-attention or decoder copy during the manual path.
        with init_empty_weights():
            manual=native.modules['models.flamingo'].FlamingoChessLM(native.model,
                native.modules['models.adapters.smollm'].SmolLM3Adapter(native.model),n_new_tokens=0,lora_rank=-1)
        manual.x_attn_layers=native.bridges;manual.eval()
        def compare(left,right):
            delta=(left-right).abs()
            return {'max_absolute_error':float(delta.max()),'mean_absolute_error':float(delta.mean()),
                'cosine_similarity':float(torch.nn.functional.cosine_similarity(left,right,dim=0)),
                'top1_equal':int(left.argmax())==int(right.argmax()),
                'left_top1':int(left.argmax()),'right_top1':int(right.argmax()),
                'finite':bool(torch.isfinite(left).all() and torch.isfinite(right).all())}
        with torch.inference_mode():
            planes=native.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']],[[]]).to(args.device)
            encoded=native.modules['utils.utils'].encode_planes(native.encoder,planes,dtype,pov=True)
            if tuple(encoded.shape)!=(1,16,64,1024) or not torch.isfinite(encoded).all():
                raise ValueError('Encoder conditioning shape/finite check failed.')
            result['encoder_shape']=list(encoded.shape);guard()
            manual_hidden=manual._hidden_states(ids,encoded,attention_mask=torch.ones_like(ids))[:,-1:]
            expected=native.model.lm_head(manual_hidden)[0,-1].float()
            handles=adapter.board_conditioning_hooks(native.model,native.bridges,encoded)
            try:
                actual=native.model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,logits_to_keep=1).logits[0,-1].float()
                result['hook_vs_upstream_manual']=compare(expected,actual)
                prefill=native.model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=True,logits_to_keep=1)
                next_id=prefill.logits[:,-1].argmax(-1,keepdim=True);past=prefill.past_key_values;full=ids
                cache_rows=[]
                for step in range(1,THRESHOLDS['cached_steps']+1):
                    guard();full=torch.cat((full,next_id),dim=1)
                    cached=native.model(input_ids=next_id,attention_mask=torch.ones_like(full),past_key_values=past,use_cache=True,logits_to_keep=1)
                    uncached=native.model(input_ids=full,attention_mask=torch.ones_like(full),use_cache=False,logits_to_keep=1).logits[0,-1].float()
                    cache_rows.append({'cached_step':step,**compare(cached.logits[0,-1].float(),uncached)})
                    result['cache_vs_no_cache']=cache_rows
                    past=cached.past_key_values;next_id=cached.logits[:,-1].argmax(-1,keepdim=True)
            finally:
                for handle in handles:handle.remove()
        hook=result['hook_vs_upstream_manual']
        def common(row):return row['finite'] and row['top1_equal'] and row['cosine_similarity']>=THRESHOLDS['minimum_cosine_similarity']
        passed=(common(hook) and hook['max_absolute_error']<=THRESHOLDS['hook_max_absolute_error']
            and len(cache_rows)==3 and all(common(row) and row['max_absolute_error']<=THRESHOLDS['cache_max_absolute_error']
                and row['mean_absolute_error']<=THRESHOLDS['cache_mean_absolute_error'] for row in cache_rows))
        guard();result['status']='passed' if passed else 'failed'
        result['peak_cuda_allocated_bytes']=torch.cuda.max_memory_allocated() if args.device=='cuda' else None
    except Exception as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error))
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    raise SystemExit(0 if result['status']=='passed' else 2)


if __name__=='__main__':main()
