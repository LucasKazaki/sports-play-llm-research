"""Root-only authored one-step Queen QLoRA software diagnostic.

No corpus selection, full training or learned call occurs on import. This
separate condition never identifies its adapted weights as the native baseline.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import re
import sys
import time

import chess
import chess_queen_nf4_adapter_v2 as nf4

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'experiments/chess-queen-qlora-v1/diagnostic-protocol.json'
FIXTURE = {'fen': '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'}
LORA = {'r': 8, 'lora_alpha': 16, 'target_modules': ['q_proj', 'v_proj'],
        'lora_dropout': 0, 'bias': 'none', 'task_type': 'CAUSAL_LM'}
NATIVE_NAME = re.compile(r'^model\.layers\.(\d+)\.self_attn\.(q_proj|v_proj)\.lora_([AB])\.default\.weight$')
EXPECTED_CHECKS = {'finite_loss', 'finite_nonzero_lora_gradients', 'frozen_gradients_absent',
    'frozen_storage_exactly_unchanged', 'lora_storage_actually_changed',
    'full_expected_fp32_lora_inventory', 'base_decoder_identity_preserved', 'bf16_tied_vocabulary_preserved'}


def target_for_fixture():
    board = chess.Board(FIXTURE['fen']); move = chess.Move.from_uci('g5d8')
    if move not in board.legal_moves or board.is_capture(move):
        raise ValueError('Authored mate fixture changed')
    piece = board.piece_at(move.from_square)
    atom = f'<PIECE_M{piece.symbol().upper()}><SQUARE_{move.from_square+1}><SQUARE_{move.to_square+1}>'
    board.push(move)
    if not board.is_checkmate(): raise ValueError('Authored target must be verified mate')
    return ('ANALYSIS:\nThe move ' + atom + ' gives checkmate. It does not capture a piece.\n'
        'BEST_MOVE: ' + atom + '\nCRITICAL_LINE: ' + atom + '\nPROMISING_MOVES: ' + atom +
        '\nEVALUATION: Checkmate for player')


def tokenize_training(tokenizer, prompt, response, official_tokenize, maximum=512):
    """Use the official template and verify the complete untruncated boundary."""
    ids, labels = official_tokenize(tokenizer, prompt, response, max_length=None)
    prefix = list(tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}],
        tokenize=True, add_generation_prompt=True, enable_thinking=False))
    if not prefix or ids[:len(prefix)] != prefix or len(ids) != len(labels):
        raise ValueError('Training/generation prefix mismatch')
    if len(ids) > maximum or len(ids) <= len(prefix):
        raise ValueError('Complete target exceeds the frozen context or has no response')
    if labels != [-100] * len(prefix) + ids[len(prefix):]:
        raise ValueError('Only complete assistant response/EOS may be supervised')
    closing = tokenizer.convert_tokens_to_ids('<|im_end|>')
    if closing not in labels[len(prefix):] or closing not in ids[-8:]:
        raise ValueError('Complete supervised assistant closing token is required')
    return ids, labels, len(prefix)


def trainable_inventory(decoder, fp32):
    values = []
    for name, parameter in decoder.named_parameters():
        if not parameter.requires_grad: continue
        match = NATIVE_NAME.fullmatch(name)
        if match is None or int(match[1]) not in range(36):
            raise ValueError('Unexpected trainable parameter: ' + name)
        target, matrix = match[2], match[3]
        shape = (8, 2048) if matrix == 'A' else ((2048, 8) if target == 'q_proj' else (512, 8))
        if tuple(parameter.shape) != shape or parameter.dtype != fp32:
            raise ValueError('LoRA shape/dtype differs: ' + name)
        if parameter.device.type != 'cuda' or parameter.device.index != 0:
            raise ValueError('LoRA must be on cuda0')
        values.append((name, parameter))
    expected = {f'model.layers.{layer}.self_attn.{target}.lora_{matrix}.default.weight'
        for layer in range(36) for target in ('q_proj', 'v_proj') for matrix in ('A', 'B')}
    if {name for name, _ in values} != expected or len(values) != 144:
        raise ValueError('Expected exactly144q/v LoRA A/B tensors')
    count = sum(math.prod(parameter.shape) for _, parameter in values)
    if count != 1916928: raise ValueError('Unexpected LoRA parameter count')
    return values


def verify_protocol(path):
    plan = nf4.base.read_json(path)
    if plan['schema'] != 'chess.queen-qlora-authored-diagnostic-protocol.v1' or plan['implementation_sha256'] != nf4.base.digest(Path(__file__)):
        raise ValueError('Frozen QLoRA software source changed')
    if plan['fixture'] != FIXTURE or plan['target'] != target_for_fixture() or plan['lora'] != LORA:
        raise ValueError('Authored input/target or LoRA configuration differs')
    for item in plan['dependencies']: nf4.binding(item)
    for name, version in plan['runtime_versions'].items():
        if metadata.version(name) != version: raise ValueError('Runtime changed: ' + name)
    kernel_path = nf4.binding(plan['kernel_protocol'])
    kernel = nf4.verify_protocol(kernel_path)
    nf4.require_diagnostic(nf4.binding(plan['kernel_receipt']), kernel_path)
    prior = nf4.base.read_json(nf4.binding(plan['authored_runtime_receipt']))
    if prior.get('status') != 'completed' or prior.get('finish_reason') != 'eos' or prior.get('parsed', {}).get('accepted_move_uci') != 'g5d8':
        raise ValueError('Prior authored native response has not actually completed')
    if prior.get('adapter_sha256') != nf4.base.digest(Path(nf4.__file__)):
        raise ValueError('Prior authored runtime used a different adapter')
    return plan, kernel_path, kernel


def streamed_hash(torch, named, guard):
    """Hash exact existing device storage using bounded1MiB host transfers."""
    digest = hashlib.sha256(); total = 0
    for name, value in named:
        guard()
        if not value.is_contiguous(): raise ValueError('Storage hash requires contiguous tensor: ' + name)
        digest.update(json.dumps([name, str(value.dtype), list(value.shape)], separators=(',', ':')).encode())
        flat = value.detach().reshape(-1).view(torch.uint8)
        for offset in range(0, flat.numel(), 1024**2):
            guard(); block = flat[offset:offset+1024**2].cpu().numpy().tobytes()
            digest.update(block); total += len(block)
    return {'sha256': digest.hexdigest(), 'tensor_count': len(named), 'bytes_hashed': total}


def qualified(result):
    checks = result.get('checks', {})
    return (result.get('updates_completed') == 1 and result.get('loss') is not None
        and type(result['loss']) in (float, int) and math.isfinite(result['loss'])
        and set(checks) == EXPECTED_CHECKS and all(value is True for value in checks.values()))


def diagnostic(protocol, out):
    if out.exists(): raise ValueError('Authored QLoRA diagnostic is create-only')
    out.parent.mkdir(parents=True, exist_ok=True); started = time.monotonic()
    result = {'schema': 'chess.queen-qlora-authored-diagnostic.v1', 'status': 'attempt_started',
        'kind': 'Authored one-step software/gradient/memory test. No chess-understanding or source-game training claim.',
        'started_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': nf4.base.digest(Path(__file__)),
        'protocol_sha256': nf4.base.digest(protocol), 'candidate_id': 'queen-pawn-8/authored-qlora-diagnostic-v1',
        'base_candidate_id': nf4.CANDIDATE, 'fixture_input': FIXTURE, 'updates_planned': 1,
        'updates_completed': 0, 'phases': [], 'checks': {}, 'resource_samples': []}
    nf4.save(out, result); samples = []
    def phase(name, function):
        row = {'name': name, 'status': 'started', 'started_seconds': time.monotonic()-started}
        result['phases'].append(row); nf4.save(out, result)
        value = function()
        row.update(status='completed', elapsed_seconds=time.monotonic()-started-row['started_seconds'])
        nf4.save(out, result); return value
    try:
        plan, kernel_path, kernel = verify_protocol(protocol)
        guard_base, samples, policy = nf4.guard_for(kernel, out)
        def guard():
            if time.monotonic()-started > plan['maximum_seconds']:
                raise RuntimeError('Owned QLoRA diagnostic time budget')
            guard_base()
        model = nf4.NativeQueenNF4(kernel_path, nf4.binding(plan['kernel_receipt']), guard=guard)
        phase('base_model_load', model.load)
        import torch
        from accelerate import init_empty_weights
        from peft import LoraConfig, get_peft_model
        torch.manual_seed(plan['seed']); torch.cuda.manual_seed_all(plan['seed'])
        decoder = model.model  # Keep this actual base object; PEFT injects in place.
        frozen = [('decoder.'+name, value) for name, value in decoder.named_parameters()]
        frozen += [('decoder_buffer.'+name, value) for name, value in decoder.named_buffers()]
        # Params4bit quantization scales/codebooks are not registered buffers;
        # include their storage so unchanged bytes means unchanged effective weights.
        for name, module in decoder.named_modules():
            state = getattr(getattr(module, 'weight', None), 'quant_state', None)
            for level, current in (('state', state), ('state2', getattr(state, 'state2', None))):
                for field in ('absmax', 'code', 'offset'):
                    value = getattr(current, field, None)
                    if isinstance(value, torch.Tensor):
                        frozen.append((f'quantization.{name}.{level}.{field}', value))
        for label, component in (('encoder', model.encoder), ('bridge', model.bridges)):
            frozen += [(label+'.'+name, value) for name, value in component.named_parameters()]
            frozen += [(label+'_buffer.'+name, value) for name, value in component.named_buffers()]
        initial_frozen = phase('hash_frozen_before', lambda: streamed_hash(torch, frozen, guard))
        guard()
        wrapper = phase('inject_lora', lambda: get_peft_model(decoder, LoraConfig(**LORA),
            autocast_adapter_dtype=True, revision=nf4.base.MODEL_REVISION))
        if wrapper.get_base_model() is not decoder: raise ValueError('PEFT did not retain the actual base decoder')
        parameters = trainable_inventory(decoder, torch.float32)
        if any(value.requires_grad for _, value in frozen): raise ValueError('Original base/encoder/bridge became trainable')
        if decoder.get_input_embeddings().weight.dtype != torch.bfloat16 or decoder.get_output_embeddings().weight.data_ptr() != decoder.get_input_embeddings().weight.data_ptr():
            raise ValueError('Original BF16 tied embeddings were changed')
        if any(getattr(module, 'gradient_checkpointing', False) for module in decoder.modules()):
            raise ValueError('Duplicate HF layer checkpointing is forbidden')
        if any(bool(value.detach().count_nonzero()) for name, value in parameters if '.lora_B.' in name):
            raise ValueError('Initial LoRA B must be zero')
        result.update(trainable_names=[name for name, _ in parameters], trainable_parameters=1916928,
            lora=LORA, base_decoder_identity_preserved=True, original_frozen_storage_before=initial_frozen)
        initial_lora = phase('hash_lora_before', lambda: streamed_hash(torch, parameters, guard))
        with init_empty_weights():
            manual = model.modules['models.flamingo'].FlamingoChessLM(decoder,
                model.modules['models.adapters.smollm'].SmolLM3Adapter(decoder), n_new_tokens=0, lora_rank=0)
        manual.x_attn_layers = model.bridges
        manual.rl_activation_checkpointing = True; manual.logit_chunk_size = 32
        formatting = importlib.import_module('utils.instance_format')
        packet, _ = nf4.base.input_packet(FIXTURE); prompt = nf4.base.prompt_for(packet)
        ids, labels, prompt_length = tokenize_training(model.tokenizer, prompt, target_for_fixture(), formatting.tokenize_instance)
        result.update(token_count=len(ids), supervised_tokens=sum(label != -100 for label in labels), prompt_tokens=prompt_length)
        ids = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        labels = torch.tensor([labels], dtype=torch.long, device='cuda:0'); mask = torch.ones_like(ids)
        optimizer = torch.optim.AdamW([value for _, value in parameters], lr=plan['learning_rate'],
            betas=(.9,.999), eps=1e-8, weight_decay=.01, foreach=False)
        with nf4.base.precision_context(torch, 'math_sdpa_fp32_reduction'):
            def encode():
                guard()
                with torch.no_grad():
                    planes = model.modules['utils.lc0_planes'].encode_fen_batch([packet['fen']], [[]]).to('cuda:0')
                    value = model.modules['utils.utils'].encode_planes(model.encoder, planes, torch.bfloat16, pov=True)
                    if tuple(value.shape) != (1,16,64,1024) or not bool(torch.isfinite(value).all()) or value.requires_grad:
                        raise ValueError('Frozen current-only encoder contract differs')
                    return value
            encoded = phase('encoder_forward', encode)
            manual.train(); model.bridges.eval(); model.encoder.eval(); decoder.config.use_cache = False
            optimizer.zero_grad(set_to_none=True)
            def loss_forward():
                guard(); value = manual(input_ids=ids, encoder_hidden_states=encoded, attention_mask=mask, labels=labels)
                if value.ndim != 0 or not bool(torch.isfinite(value)):
                    result['loss'] = None; raise ValueError('Nonfinite/non-scalar diagnostic loss')
                result['loss'] = float(value.detach()); return value
            loss = phase('training_loss_forward', loss_forward)
            def backward():
                guard(); loss.backward(); torch.cuda.synchronize(); guard()
            phase('checkpointed_backward', backward)
            gradient_rows = []
            for name, value in parameters:
                if value.grad is None or not bool(torch.isfinite(value.grad).all()):
                    raise ValueError('Missing/nonfinite LoRA gradient: '+name)
                gradient_rows.append({'name': name, 'norm': float(value.grad.float().norm())})
            if not all(math.isfinite(row['norm']) for row in gradient_rows) or not any(row['norm'] > 0 for row in gradient_rows):
                raise ValueError('LoRA gradients must be finite and nonzero in aggregate')
            if any(value.grad is not None for _, value in frozen): raise ValueError('Frozen base/encoder/bridge received gradient')
            result['gradients'] = gradient_rows; nf4.save(out, result)
            torch.nn.utils.clip_grad_norm_([value for _, value in parameters], 1.)
            def update():
                guard(); optimizer.step(); torch.cuda.synchronize()
                result['updates_completed'] = 1
                nf4.save(out, result); guard()
            phase('optimizer_update', update)
        final_lora = phase('hash_lora_after', lambda: streamed_hash(torch, parameters, guard))
        final_frozen = phase('hash_frozen_after', lambda: streamed_hash(torch, frozen, guard))
        result.update(original_frozen_storage_after=final_frozen, lora_before=initial_lora, lora_after=final_lora,
            checks={'finite_loss': math.isfinite(result['loss']), 'finite_nonzero_lora_gradients': True,
                'frozen_gradients_absent': all(value.grad is None for _, value in frozen),
                'frozen_storage_exactly_unchanged': final_frozen == initial_frozen,
                'lora_storage_actually_changed': final_lora['sha256'] != initial_lora['sha256'],
                'full_expected_fp32_lora_inventory': len(parameters) == 144,
                'base_decoder_identity_preserved': wrapper.get_base_model() is decoder,
                'bf16_tied_vocabulary_preserved': decoder.get_input_embeddings().weight.dtype == torch.bfloat16 and decoder.get_output_embeddings().weight.data_ptr() == decoder.get_input_embeddings().weight.data_ptr()})
        guard_base(force=True)
        result.update(status='passed' if qualified(result) else 'failed',
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    except Exception as error:
        result.update(status='failed', error=type(error).__name__+': '+str(error))
    finally:
        result.update(resource_samples=samples, elapsed_seconds=time.monotonic()-started)
        nf4.save(out, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=PROTOCOL)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); value = diagnostic(args.protocol, args.out)
    print(json.dumps({'status': value['status'], 'out': str(args.out)}))
    raise SystemExit(0 if value['status'] == 'passed' else 2)


if __name__ == '__main__': main()
