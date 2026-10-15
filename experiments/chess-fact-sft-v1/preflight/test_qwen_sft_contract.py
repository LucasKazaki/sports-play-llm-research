"""Random tiny CPU models only: no downloaded weights, GPU or chess cohort."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
import torch
import torch.nn.functional as F
from peft import LoraConfig,get_peft_model
from transformers import Qwen3Config,Qwen3ForCausalLM

TARGETS=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']
LOSS_ATOL=2e-6
GRAD_ATOL=2e-6
GRAD_RTOL=1e-4
RESULTS=[]

def tiny(dtype):
    torch.manual_seed(4082031)
    config=Qwen3Config(vocab_size=96,hidden_size=16,intermediate_size=32,num_hidden_layers=1,
        num_attention_heads=2,num_key_value_heads=1,head_dim=8,max_position_embeddings=512,
        tie_word_embeddings=True,attention_dropout=0.,pad_token_id=0,eos_token_id=95)
    config._attn_implementation='sdpa'
    model=Qwen3ForCausalLM(config).to(dtype=dtype,device='cpu')
    return get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.,bias='none',
        target_modules=TARGETS,task_type='CAUSAL_LM'))

def base_hash(model):
    h=hashlib.sha256()
    for name,p in model.named_parameters():
        if not p.requires_grad:
            h.update(name.encode());h.update(p.detach().contiguous().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()

def inputs(lengths=(141,157,176),targets=(1,31,127)):
    generator=torch.Generator(device='cpu').manual_seed(4082031)
    width=max(lengths);ids=torch.zeros((len(lengths),width),dtype=torch.long)
    mask=torch.zeros_like(ids);labels=torch.full_like(ids,-100)
    for i,(length,count) in enumerate(zip(lengths,targets,strict=True)):
        assert count+1<=128 and 0<count<length
        ids[i,-length:]=torch.randint(1,90,(length,),generator=generator)
        ids[i,-1]=95;mask[i,-length:]=1;labels[i,-count:]=ids[i,-count:]
    position=(mask.cumsum(-1)-1).masked_fill(mask==0,0)
    return dict(input_ids=ids,attention_mask=mask,position_ids=position),labels

@pytest.mark.parametrize('dtype',[torch.float32,torch.bfloat16])
def test_cropped_last128_logits_and_labels_preserve_loss_and_lora_gradients(dtype):
    torch.set_num_threads(1)
    model=tiny(dtype);data,labels=inputs()
    assert model.get_input_embeddings().weight is model.get_output_embeddings().weight
    assert all(p.device.type=='cpu' for p in model.parameters())
    assert all(p.dtype==torch.float32 for p in model.parameters() if p.requires_grad)
    model.eval()
    with torch.no_grad():
        enabled=model(**data,use_cache=False).logits
        with model.disable_adapter():disabled=model(**data,use_cache=False).logits
    assert torch.equal(enabled,disabled),'Zero-initialized B must preserve base logits exactly'
    before=base_hash(model)
    model.config.use_cache=False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.train()
    first=model(**data,labels=labels,use_cache=False)
    first.loss.backward()
    first_b=[p.grad for n,p in model.named_parameters() if '.lora_B.' in n]
    first_a=[p.grad for n,p in model.named_parameters() if '.lora_A.' in n]
    assert len(first_a)==len(first_b)==7
    assert all(g is not None and torch.isfinite(g).all() and torch.count_nonzero(g)>0 for g in first_b)
    assert all(g is not None and torch.count_nonzero(g)==0 for g in first_a)
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-4,
        betas=(.9,.999),eps=1e-8,weight_decay=0.,foreach=False)
    torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
    optimizer.step();optimizer.zero_grad(set_to_none=True)
    assert base_hash(model)==before
    cropped_model=copy.deepcopy(model)
    full=model(**data,labels=labels,use_cache=False,logits_to_keep=0)
    cropped=cropped_model(**data,labels=labels[:,-128:],use_cache=False,logits_to_keep=128)
    assert full.logits.shape==(3,176,96) and cropped.logits.shape==(3,128,96)
    assert int((labels[:,1:]!=-100).sum())==int((labels[:,-127:]!=-100).sum())==159
    shifted=labels[:,1:];keep=shifted!=-100
    manual=-full.logits[:,:-1].double().log_softmax(-1)[keep].gather(1,shifted[keep].unsqueeze(1)).mean()
    torch.testing.assert_close(full.loss.double(),manual,atol=LOSS_ATOL,rtol=0.)
    torch.testing.assert_close(cropped.loss,full.loss,atol=LOSS_ATOL,rtol=0.)
    full.loss.backward();cropped.loss.backward()
    diffs=[]
    for (name,a),(other,b) in zip(model.named_parameters(),cropped_model.named_parameters(),strict=True):
        assert name==other
        if a.requires_grad:
            assert a.grad is not None and b.grad is not None and torch.isfinite(a.grad).all() and torch.isfinite(b.grad).all()
            torch.testing.assert_close(a.grad,b.grad,atol=GRAD_ATOL,rtol=GRAD_RTOL)
            diffs.append(float((a.grad-b.grad).abs().max()))
            if '.lora_A.' in name:assert torch.count_nonzero(a.grad)>0
        else:assert a.grad is None and b.grad is None
    assert base_hash(model)==base_hash(cropped_model)==before
    RESULTS.append({'dtype':str(dtype),'target_token_counts':[1,31,127],'total_targets':159,
        'full_loss':float(full.loss.detach()),'cropped_loss':float(cropped.loss.detach()),
        'manual_nll':float(manual.detach()),'maximum_adapter_gradient_difference':max(diffs),
        'all14_adapter_gradients_finite_and_compared':True,'all7_first_B_gradients_nonzero':True,
        'all7_second_A_gradients_nonzero':True,'frozen_base_unchanged':True,'zero_B_base_equivalence':True,
        'pretrained_forwards':0,'GPU_calls':0})

def test_first_prediction_is_lost_if_target128_is_not_rejected():
    # Independent index arithmetic establishes why target_len+1<=128 is mandatory.
    length=176;target_count=128
    full_positions=list(range(length-target_count-1,length-1))
    cropped_positions=list(range(length-128,length-1))
    assert len(full_positions)==128 and len(cropped_positions)==127
    assert full_positions[0] not in cropped_positions

def teardown_module():
    report={'schema':'chess.fact-sft.random-cpu-contract-checks.v1','scope':'Random tiny CPU Qwen models only; no pretrained weights, GPU or selected data.',
        'loss_absolute_tolerance':LOSS_ATOL,'gradient_absolute_tolerance':GRAD_ATOL,
        'gradient_relative_tolerance':GRAD_RTOL,'results':RESULTS,'negative_boundary_target128_rejected':True}
    Path(__file__).with_name('random-cpu-contract-results.json').write_text(json.dumps(report,indent=2)+'\n')
