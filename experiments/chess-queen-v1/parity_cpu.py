"""Tiny random CPU model parity; no pretrained weights, engine or CUDA calls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_adapter as adapter

def main():
    import torch
    from transformers import SmolLM3Config,SmolLM3ForCausalLM
    torch.set_num_threads(2)
    source=adapter.read_json(adapter.SOURCE_MANIFEST)
    source_root=Path(source['checkout'])
    adapter.verify_files(source_root,source['files'])
    modules=adapter.import_audited_source(source_root)
    config=SmolLM3Config(vocab_size=97,hidden_size=32,intermediate_size=64,
        num_hidden_layers=36,num_attention_heads=4,num_key_value_heads=2,
        max_position_embeddings=128,layer_types=['full_attention']*36,attn_implementation='eager',
        pad_token_id=0,bos_token_id=1,eos_token_id=2)
    decoder=SmolLM3ForCausalLM(config).to('cpu').eval()
    class TinyFlamingo(modules['models.flamingo'].FlamingoChessLM):ENCODER_DIM=8
    manual_decoder=copy.deepcopy(decoder)
    manual=TinyFlamingo(manual_decoder,modules['models.adapters.smollm'].SmolLM3Adapter(manual_decoder),
        n_new_tokens=0,lora_rank=-1,x_attn_kwargs={'n_heads':4,'n_kv_heads':4}).to('cpu').eval()
    # DenseXAttn W_O starts at zero; make it nonzero to test conditioning itself.
    with torch.no_grad():
        for bridge in manual.x_attn_layers:bridge.W_O.weight.normal_(mean=0,std=.03)
    with tempfile.TemporaryDirectory(prefix='queen-cpu-meta-parity-') as folder:
        state_path=Path(folder)/'tiny-bridges.pt'
        torch.save(manual.x_attn_layers.state_dict(),state_path)
        bridges=adapter.materialize_pinned_module(torch,
            lambda:torch.nn.ModuleList([modules['models.flamingo'].DenseXAttn(8,32,n_heads=4,n_kv_heads=4) for _ in range(16)]),
            state_path,'cpu',torch.float32).eval()
    encoded=torch.randn(1,16,64,8,device='cpu')
    ids=torch.tensor([[1,4,9,3,7]],device='cpu')
    handles=adapter.board_conditioning_hooks(decoder,bridges,encoded)
    try:
        with torch.inference_mode():
            expected=manual(ids,encoded,attention_mask=torch.ones_like(ids))
            actual=decoder(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False).logits
            difference=float((expected-actual).abs().max())
            assert torch.allclose(expected,actual,atol=2e-5,rtol=2e-4),difference
            pref=decoder(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=True)
            next_id=pref.logits[:,-1].argmax(-1,keepdim=True)
            full=torch.cat((ids,next_id),dim=1)
            cached=decoder(input_ids=next_id,attention_mask=torch.ones_like(full),past_key_values=pref.past_key_values,use_cache=True).logits[:,-1]
            uncached=decoder(input_ids=full,attention_mask=torch.ones_like(full),use_cache=False).logits[:,-1]
            cache_difference=float((cached-uncached).abs().max())
            assert torch.allclose(cached,uncached,atol=2e-5,rtol=2e-4),cache_difference
    finally:
        for handle in handles:handle.remove()
    report={'schema':'chess.queen-native-cpu-parity.v1','status':'passed',
        'model':'Tiny random SmolLM3, not pretrained Queen','device':'cpu',
        'native_hook_vs_upstream_manual_max_absolute_error':difference,
        'cached_vs_uncached_next_logits_max_absolute_error':cache_difference,
        'tolerance':{'atol':2e-5,'rtol':2e-4},'pretrained_forwards':0,'cuda_calls':0,
        'adapter_sha256':adapter.digest(ROOT/'scripts/chess_queen_adapter.py'),
        'source_manifest_sha256':adapter.digest(adapter.SOURCE_MANIFEST),
        'limitation':'CPU random-weight parity is not pretrained GPU numerical parity, strength, or explanation quality.'}
    target=Path(__file__).with_name('cpu-parity-memory-v2.json')
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
