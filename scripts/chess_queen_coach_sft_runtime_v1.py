"""Queen coach pilot runtime; root-owned GPU calls only, no import side effects."""
from __future__ import annotations
import importlib
from pathlib import Path

import chess_queen_qlora_v2 as checked


def frozen_tensors(torch, model):
    decoder=model.model
    values=[('decoder.'+name,value)for name,value in decoder.named_parameters()]
    values += [('decoder_buffer.'+name,value)for name,value in decoder.named_buffers()]
    for name,module in decoder.named_modules():
        state=getattr(getattr(module,'weight',None),'quant_state',None)
        for level,current in (('state',state),('state2',getattr(state,'state2',None))):
            for field in ('absmax','code','offset'):
                value=getattr(current,field,None)
                if isinstance(value,torch.Tensor):values.append((f'quantization.{name}.{level}.{field}',value))
    for label,component in (('encoder',model.encoder),('bridge',model.bridges)):
        values += [(label+'.'+name,value)for name,value in component.named_parameters()]
        values += [(label+'_buffer.'+name,value)for name,value in component.named_buffers()]
    return values


class Runtime:
    def __init__(self, plan, guard):
        self.plan=plan;self.guard=guard;self.model=None;self.backend_failure=None

    def load(self):
        if self.model is not None:return
        nf4=checked.nf4
        model=nf4.NativeQueenNF4(nf4.binding(self.plan['kernel_protocol']),
            nf4.binding(self.plan['kernel_receipt']),guard=self.guard)
        model.load()
        import torch
        from accelerate import init_empty_weights
        from peft import LoraConfig,get_peft_model
        self.torch=torch;torch.manual_seed(self.plan['training']['seed'])
        torch.cuda.manual_seed_all(self.plan['training']['seed'])
        decoder=model.model;self.frozen=frozen_tensors(torch,model)
        self.frozen_before=checked.streamed_hash(torch,self.frozen,self.guard)
        self.wrapper=get_peft_model(decoder,LoraConfig(**checked.LORA),autocast_adapter_dtype=True,
            revision=nf4.base.MODEL_REVISION)
        if self.wrapper.get_base_model() is not decoder:raise ValueError('Actual base decoder identity changed')
        self.parameters=checked.trainable_inventory(decoder,torch.float32)
        if any(value.requires_grad for _,value in self.frozen):raise ValueError('An original frozen tensor became trainable')
        if any(bool(value.detach().count_nonzero())for name,value in self.parameters if '.lora_B.'in name):
            raise ValueError('Initial adapter must be zero-B no-op')
        if any(getattr(module,'gradient_checkpointing',False)for module in decoder.modules()):
            raise ValueError('Duplicate HF checkpointing is forbidden')
        if decoder.get_input_embeddings().weight.dtype != torch.bfloat16 or decoder.get_output_embeddings().weight.data_ptr()!=decoder.get_input_embeddings().weight.data_ptr():
            raise ValueError('Full original tied BF16 vocabulary must remain preserved')
        with init_empty_weights():
            manual=model.modules['models.flamingo'].FlamingoChessLM(decoder,
                model.modules['models.adapters.smollm'].SmolLM3Adapter(decoder),n_new_tokens=0,lora_rank=0)
        manual.x_attn_layers=model.bridges;manual.rl_activation_checkpointing=True;manual.logit_chunk_size=32
        decoder.config.use_cache=False
        self.manual=manual;self.model=model
        self.formatting=importlib.import_module('utils.instance_format')

    def tokenize(self,row):
        packet,_=checked.nf4.base.input_packet(row['input'])
        prompt=checked.nf4.base.prompt_for(packet)
        return checked.tokenize_training(self.model.tokenizer,prompt,row['response'],
            self.formatting.tokenize_instance,maximum=self.plan['training']['max_total_tokens'])

    def loss(self,row,tokenized,training):
        self.guard();torch=self.torch;model=self.model
        self.manual.train(training);model.bridges.eval();model.encoder.eval()
        packet,_=checked.nf4.base.input_packet(row['input'])
        ids,labels,_=tokenized
        ids=torch.tensor([ids],dtype=torch.long,device='cuda:0')
        labels=torch.tensor([labels],dtype=torch.long,device='cuda:0')
        with checked.nf4.base.precision_context(torch,'math_sdpa_fp32_reduction'):
            with torch.no_grad():
                planes=model.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']],[packet['history']]).to('cuda:0')
                encoded=model.modules['utils.utils'].encode_planes(model.encoder,planes,torch.bfloat16,pov=True)
                if tuple(encoded.shape)!=(1,16,64,1024)or not bool(torch.isfinite(encoded).all())or encoded.requires_grad:
                    raise ValueError('Current-only frozen encoder contract differs')
            with torch.set_grad_enabled(training):
                value=self.manual(input_ids=ids,encoder_hidden_states=encoded,attention_mask=torch.ones_like(ids),labels=labels)
                if value.ndim!=0 or not bool(torch.isfinite(value)):raise ValueError('Nonfinite/non-scalar full-vocabulary loss')
                if training:
                    (value/self.plan['training']['gradient_accumulation']).backward()
                    torch.cuda.synchronize()
        scalar=float(value.detach());self.guard();return scalar

    def verify_gradients(self):
        torch=self.torch;nonzero=False
        for name,value in self.parameters:
            if value.grad is None or not bool(torch.isfinite(value.grad).all()):
                raise ValueError('Missing/nonfinite adapter gradient: '+name)
            nonzero=nonzero or bool(value.grad.count_nonzero())
        if not nonzero:raise ValueError('Adapter gradient is zero in aggregate')
        if any(value.grad is not None for _,value in self.frozen):raise ValueError('Frozen tensor received gradient')

    def save_adapter(self,directory,step,presentations):
        torch=self.torch;directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
        path=directory/'adapter.pt'
        torch.save({name:value.detach().cpu()for name,value in self.parameters},path)
        identity={'path':str(path.resolve()).replace('\\','/'),'sha256':checked.nf4.base.digest(path),
            'step':step,'presentations':presentations,'parameter_count':1916928,
            'candidate_id':'queen-pawn-8/nf4-coach-sft-v1','source_sha256':checked.nf4.base.digest(Path(__file__))}
        checked.nf4.save(directory/'metadata.json',identity);return identity

    def load_adapter(self,identity):
        torch=self.torch;path=Path(identity['path'])
        if checked.nf4.base.digest(path)!=identity['sha256']:raise ValueError('Saved adapter bytes changed')
        weights=torch.load(path,map_location='cpu',weights_only=True)
        if set(weights)!={name for name,_ in self.parameters}:raise ValueError('Adapter keys differ')
        with torch.no_grad():
            for name,value in self.parameters:
                saved=weights[name]
                if saved.dtype!=torch.float32 or tuple(saved.shape)!=tuple(value.shape)or not bool(torch.isfinite(saved).all()):
                    raise ValueError('Adapter shape/dtype/values differ')
                value.copy_(saved.to(device='cuda:0'))
        self.guard()

    def infer(self,row,identity):
        if self.backend_failure is not None:raise RuntimeError('No model call after first backend failure')
        self.model.model.eval();self.model.encoder.eval();self.model.bridges.eval()
        generation=self.plan['generation']
        # Call the reviewed raw generator directly, then identify actual tuned
        # weights explicitly. Never return its native-baseline identity unchanged.
        value=checked.nf4.base.NativeQueen.generate(self.model,row['input'],
            max_new_tokens=generation['max_new_tokens'],maximum_seconds=generation['maximum_seconds'],
            temperature=0.,seed=generation['seed'],generation_mode='no_cache',precision_profile='math_sdpa_fp32_reduction')
        value.update(schema='chess.queen-coach-sft-output.v1',candidate_id='queen-pawn-8/nf4-coach-sft-v1',
            base_candidate_id=checked.nf4.CANDIDATE,trained_adapter=identity,
            base_generator_source_sha256=value.pop('adapter_sha256',None),
            adapter_sha256=checked.nf4.base.digest(Path(__file__)),
            base_nf4_source_sha256=checked.nf4.base.digest(Path(checked.nf4.__file__)),
            nf4_protocol_sha256=checked.nf4.base.digest(self.model.protocol),
            kernel_receipt_sha256=checked.nf4.base.digest(self.model.diagnostic_receipt),
            quantization={'requested':checked.nf4.QUANTIZATION,
                'base_decoder_inventory_before_lora':self.model.inventory,
                'origin':'Local NF4 decoder override plus separately identified trained LoRA; not publisher-provided quantized/adapted weights',
                'encoder_and_bridges':'Frozen BF16', 'actual_lora_dtype':'float32','actual_lora_parameters':1916928})
        if value['status']=='failed':self.backend_failure=value.get('error','backend failure')
        return value

    def verify_frozen(self):
        after=checked.streamed_hash(self.torch,self.frozen,self.guard)
        if after!=self.frozen_before:raise ValueError('Original effective base/encoder/bridge storage changed')
        return {'before':self.frozen_before,'after':after,'identical':True}
