"""One frozen native LoRA experiment. No heldout labels enter this process."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import hashlib
import math
from pathlib import Path
import random
import subprocess
import sys
import time
from chess_fact_sft_common import (read, save, sha, native_prompt, native_training_row,
    collate_training, decode_generated, seal_raw, select_checkpoint, finalize_run_ledger)


class Cancelled(RuntimeError):
    pass


def check_cancel(out):
    if (out / 'cancel.json').exists():
        raise Cancelled('resource supervisor latched stop')


def base_hash(model):
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            digest.update(name.encode())
            digest.update(parameter.detach().contiguous().cpu().view(__import__('torch').uint8).numpy().tobytes())
    return digest.hexdigest()


def score_external(repo, cohort, raw, split, expected_label_sha256):
    score = raw.parent / (raw.name + '-score.json')
    subprocess.run([sys.executable, str(repo / 'scripts/chess_fact_sft_evaluate.py'),
        '--raw', str(raw), '--labels', str(cohort / (split + '-labels.json')), '--out', str(score),
        '--expected-label-sha256', expected_label_sha256],
        check=True, timeout=60, capture_output=True, text=True)
    return read(score)


def generate_cohort(model, tokenizer, inputs, raw_dir, metadata, out, disabled, torch):
    from transformers import StoppingCriteria, StoppingCriteriaList
    class StopOwned(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            return (out / 'cancel.json').exists()
    model.eval()
    rows = []
    planned = [row['case_id'] for row in inputs]
    journal = raw_dir.with_suffix('.journal.jsonl')
    if journal.exists() or raw_dir.exists():
        raise ValueError('generation cannot be replayed')
    error = None
    with journal.open('x', encoding='utf-8', buffering=1) as log:
        import json
        for index, row in enumerate(inputs):
            result = {'case_id': row['case_id'], 'text': ''}
            try:
                check_cancel(out)
                prefix = native_prompt(tokenizer, row)
                result.update(prompt_ids=prefix, prompt_sha256=hashlib.sha256(bytes(str(prefix), 'utf-8')).hexdigest())
                save(out / 'progress.json', {'phase': metadata['phase'], 'checkpoint': metadata['step'],
                    'cohort': raw_dir.name, 'attempted_case': row['case_id'], 'completed_rows': len(rows)})
                ids = torch.tensor([prefix], device='cuda:0', dtype=torch.long)
                started = time.monotonic()
                context = model.disable_adapter() if disabled else nullcontext()
                with context, torch.inference_mode():
                    generated = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                        do_sample=False, max_new_tokens=128, eos_token_id=151645, pad_token_id=151643,
                        use_cache=True, logits_to_keep=1,
                        stopping_criteria=StoppingCriteriaList([StopOwned()]))
                torch.cuda.synchronize()
                new_ids = generated[0, len(prefix):].tolist()
                result.update(new_ids=new_ids, elapsed_seconds=time.monotonic() - started)
                result.update(decode_generated(tokenizer, new_ids))
                check_cancel(out)
            except Exception as caught:
                error = caught
                result.update(status='error', error=type(caught).__name__ + ':' + str(caught))
            rows.append(result)
            log.write(json.dumps(result, allow_nan=False) + '\n')
            if error is not None:
                rows.extend({'case_id': later['case_id'], 'status': 'not_run', 'text': '',
                    'reason': 'stopped_after_owned_failure'} for later in inputs[index + 1:])
                break
    seal_raw(raw_dir, rows, planned, metadata)
    if error is not None:
        raise error


def checkpoint(model, optimizer, torch, out, step, permutation, base_digest):
    check_cancel(out)
    directory = out / ('checkpoint-' + str(step))
    directory.mkdir()
    model.save_pretrained(directory / 'adapter', safe_serialization=True)
    torch.save({'step': step, 'optimizer': optimizer.state_dict(), 'torch_rng': torch.get_rng_state(),
        'cuda_rng': torch.cuda.get_rng_state_all(), 'python_rng': random.getstate(),
        'permutation': permutation, 'base_hash': base_digest}, directory / 'training-state.pt')
    files = {path.relative_to(directory).as_posix(): sha(path) for path in directory.rglob('*') if path.is_file()}
    save(directory / 'manifest.json', {'step': step, 'files_sha256': files, 'base_hash': base_digest})
    check_cancel(out)
    return sha(directory / 'manifest.json')


def run(repo, cohort, protocol, out):
    repo, cohort, protocol, out = (Path(item).resolve() for item in (repo, cohort, protocol, out))
    handshake_deadline = time.monotonic() + 5.
    while not (out / 'ownership.json').exists() and time.monotonic() < handshake_deadline:
        time.sleep(.01)
    if not (out / 'ownership.json').exists():
        raise ValueError('owned supervisor handshake timed out')
    import os
    ownership = read(out / 'ownership.json')
    if ownership['pid'] != os.getpid():
        raise ValueError('child ownership identity mismatch')
    for name, digest in ownership['source_sha256'].items():
        if sha(repo / name) != digest:
            raise ValueError('executed source changed after parent snapshot')
    plan = read(protocol)
    if sha(cohort / 'frozen-data.json') != ownership['cohort_frozen_sha256']:
        raise ValueError('frozen cohort manifest changed')
    frozen = read(cohort / 'frozen-data.json')
    for name, digest in frozen['files_sha256'].items():
        if name in ('dev-labels.json', 'holdout-labels.json'):
            continue  # Only the parent and separate evaluator may open these files.
        if sha(cohort / name) != digest:
            raise ValueError('frozen data identity changed: ' + name)
    if sha(protocol) != frozen['protocol_sha256']:
        raise ValueError('protocol/data binding mismatch')
    for filename, digest in plan['model']['files_sha256'].items():
        if sha(repo / plan['model']['local_path'] / filename) != digest:
            raise ValueError('model asset changed')
    for filename, digest in plan['evidence']['installed_source_sha256'].items():
        if sha(filename) != digest:
            raise ValueError('installed Qwen/loss source changed')
    import torch
    import transformers
    import peft
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model
    torch.set_num_threads(8)
    random.seed(4082031)
    torch.manual_seed(4082031)
    torch.cuda.manual_seed_all(4082031)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = 'cuda:0'
    tokenizer = AutoTokenizer.from_pretrained(repo / plan['model']['local_path'],
        local_files_only=True, trust_remote_code=False)
    tokenizer.padding_side = 'left'
    if tokenizer.pad_token_id != 151643 or tokenizer.eos_token_id != 151645:
        raise ValueError('native token identity changed')
    # Only train labels are loaded in the model worker; scoring runs separately.
    train_inputs = read(cohort / 'train-inputs.json')['rows']
    train_labels = read(cohort / 'train-labels.json')['rows']
    dev_inputs = read(cohort / 'dev-inputs.json')['rows']
    holdout_inputs = read(cohort / 'holdout-inputs.json')['rows']
    if (len(train_inputs), len(dev_inputs), len(holdout_inputs)) != (8192, 128, 256):
        raise ValueError('frozen planned counts differ')
    if [r['case_id'] for r in train_inputs] != [r['case_id'] for r in train_labels]:
        raise ValueError('training label identity mismatch')
    train = [native_training_row(tokenizer, row, label['expected'])
        for row, label in zip(train_inputs, train_labels, strict=True)]
    for row in dev_inputs + holdout_inputs:
        native_prompt(tokenizer, row)
    permutation = torch.randperm(8192, generator=torch.Generator(device='cpu').manual_seed(4082031)).tolist()
    save(out / 'permutation.json', permutation)
    save(out / 'token-boundaries.json', {'train_count': len(train),
        'prompt_min': min(r['prompt_count'] for r in train), 'prompt_max': max(r['prompt_count'] for r in train),
        'target_min': min(r['target_count'] for r in train), 'target_max': max(r['target_count'] for r in train),
        'sequence_max': max(len(r['input_ids']) for r in train), 'permutation_sha256': sha(out/'permutation.json')})
    check_cancel(out)
    model = optimizer = None
    completed = 0
    status = 'aborted'
    failure = None
    try:
        model = AutoModelForCausalLM.from_pretrained(repo / plan['model']['local_path'],
            local_files_only=True, trust_remote_code=False, use_safetensors=True,
            dtype=torch.bfloat16, attn_implementation='sdpa').to(device)
        model.tie_weights()
        if model.get_input_embeddings().weight is not model.get_output_embeddings().weight:
            raise ValueError('base input/output weights not tied')
        if sum(p.numel() for p in model.parameters()) != 596049920:
            raise ValueError('unexpected unique base parameter count')
        check_cancel(out)
        model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0., bias='none',
            task_type='CAUSAL_LM', target_modules=plan['training']['lora']['target_modules']))
        trainable = [p for p in model.parameters() if p.requires_grad]
        names = [name for name, p in model.named_parameters() if p.requires_grad]
        if sum(p.numel() for p in trainable) != 5046272 or len(names) != 392:
            raise ValueError('adapter parameter/target count mismatch')
        if any('lora_' not in name for name in names) or any(p.dtype != torch.float32 for p in trainable):
            raise ValueError('unexpected trainable base/dtype')
        if any(p.dtype != torch.bfloat16 for p in model.parameters() if not p.requires_grad):
            raise ValueError('frozen base must remain BF16')
        before = base_hash(model)
        save(out / 'runtime-identity.json', {'torch': torch.__version__, 'transformers': transformers.__version__,
            'peft': peft.__version__, 'unique_base_parameters': 596049920, 'adapter_parameters': 5046272,
            'trainable_names': names, 'base_tensor_sha256': before, 'protocol_sha256': sha(protocol),
            'frozen_data_sha256': sha(cohort/'frozen-data.json'), 'device': torch.cuda.get_device_name(0)})
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        optimizer = torch.optim.AdamW(trainable, lr=2e-4, betas=(.9, .999), eps=1e-8,
            weight_decay=0., foreach=False)
        scores = []
        checkpoint_bindings = {}
        def dev(step, binding):
            raw = out / ('dev-' + str(step))
            metadata = {'phase': 'dev', 'step': step, 'adapter_disabled': step == 0,
                'checkpoint_sha256': binding, 'inputs_sha256': sha(cohort/'dev-inputs.json'),
                'protocol_sha256': sha(protocol)}
            generate_cohort(model, tokenizer, dev_inputs, raw, metadata, out, step == 0, torch)
            value = score_external(repo, cohort, raw, 'dev', frozen['files_sha256']['dev-labels.json'])
            scores.append({'step': step, 'counts': value['counts'], 'score_sha256': sha(raw.parent/(raw.name+'-score.json')),
                'checkpoint_sha256': binding})
            save(out / 'dev-scores.json', scores)
        binding = checkpoint(model, optimizer, torch, out, 0, permutation, before)
        checkpoint_bindings[0] = binding
        dev(0, binding)
        with (out / 'training.jsonl').open('x', encoding='utf-8', buffering=1) as log:
            import json
            for update in range(1024):
                check_cancel(out)
                model.train()
                optimizer.zero_grad(set_to_none=True)
                rows = [train[i] for i in permutation[update*8:(update+1)*8]]
                batch, target_count = collate_training(rows, tokenizer.pad_token_id, torch, device)
                lr = 2e-4 * min(1., (update + 1) / 32)
                for group in optimizer.param_groups:
                    group['lr'] = lr
                started = time.monotonic()
                result = model(**batch, use_cache=False, logits_to_keep=128)
                if not torch.isfinite(result.loss):
                    raise FloatingPointError('nonfinite loss')
                result.loss.backward()
                if update == 0:
                    first = {name: bool(p.grad is not None and torch.isfinite(p.grad).all() and torch.count_nonzero(p.grad))
                        for name, p in model.named_parameters() if '.lora_B.' in name}
                    if len(first) != 196 or not all(first.values()):
                        raise FloatingPointError('initial adapter B gradients not finite/nonzero')
                    save(out / 'first-gradients.json', first)
                norm = torch.nn.utils.clip_grad_norm_(trainable, 1., error_if_nonfinite=True)
                check_cancel(out)
                optimizer.step()
                torch.cuda.synchronize()
                completed = update + 1
                log.write(json.dumps({'step': completed, 'loss': float(result.loss.detach()), 'target_tokens': target_count,
                    'lr': lr, 'gradient_norm_before_clip': float(norm), 'elapsed_seconds': time.monotonic()-started,
                    'cuda_allocated_peak': torch.cuda.max_memory_allocated(),
                    'cuda_reserved_peak': torch.cuda.max_memory_reserved()}) + '\n')
                del result, batch
                check_cancel(out)
                save(out / 'training-progress.json', {'completed_updates': completed})
                if completed in (128, 256, 512, 1024):
                    binding = checkpoint(model, optimizer, torch, out, completed, permutation, before)
                    checkpoint_bindings[completed] = binding
                    dev(completed, binding)
        selection = select_checkpoint(scores)
        selection['checkpoint_bindings'] = checkpoint_bindings
        selection['base_hash'] = before
        save(out / 'selection.json', selection)
        check_cancel(out)
        # A new bounded phase begins only after complete persisted dev selection.
        save(out / 'phase.json', {'phase': 'holdout', 'started_monotonic': time.monotonic(),
            'selection_sha256': sha(out/'selection.json')})
        selected = selection['selected_step']
        if selected:
            from peft import set_peft_model_state_dict
            from safetensors.torch import load_file
            adapter = load_file(out/('checkpoint-'+str(selected))/'adapter/adapter_model.safetensors')
            incompatible = set_peft_model_state_dict(model, adapter)
            if incompatible.unexpected_keys:
                raise ValueError('unexpected adapter keys on selected checkpoint load')
            from peft import get_peft_model_state_dict
            loaded = get_peft_model_state_dict(model)
            if set(loaded) != set(adapter) or any(not torch.equal(loaded[key].detach().cpu(), value)
                                                for key, value in adapter.items()):
                raise ValueError('selected adapter tensor reload mismatch')
            manifest_path = out/('checkpoint-'+str(selected))/'manifest.json'
            if sha(manifest_path) != checkpoint_bindings[selected]:
                raise ValueError('selected checkpoint manifest changed')
            for name, digest in read(manifest_path)['files_sha256'].items():
                if sha(manifest_path.parent/name) != digest:
                    raise ValueError('selected checkpoint file changed')
        for condition, disabled in [('base', True), ('selected', selected == 0)]:
            raw = out / ('holdout-' + condition)
            generate_cohort(model, tokenizer, holdout_inputs, raw,
                {'phase': 'holdout', 'step': 0 if disabled else selected, 'adapter_disabled': disabled,
                 'selection_sha256': sha(out/'selection.json'), 'inputs_sha256': sha(cohort/'holdout-inputs.json')},
                out, disabled, torch)
        # Both full conditions are sealed before this separate label-reading process.
        for condition in ('base', 'selected'):
            score_external(repo, cohort, out/('holdout-'+condition), 'holdout',
                frozen['files_sha256']['holdout-labels.json'])
        after = base_hash(model)
        if before != after:
            raise ValueError('frozen base weights changed')
        save(out / 'base-integrity.json', {'before': before, 'after': after, 'unchanged': True})
        status = 'completed_candidate_not_promoted'
    except Exception as error:
        failure = type(error).__name__ + ':' + str(error)
        raise
    finally:
        try:
            save(out / 'outcome.json', {'status': status, 'failure': failure, 'completed_updates': completed,
                'cuda_peak_allocated': torch.cuda.max_memory_allocated(),
                'cuda_peak_reserved': torch.cuda.max_memory_reserved()})
            finalize_run_ledger(out)
        finally:
            optimizer = model = None
            import gc
            gc.collect()
            torch.cuda.empty_cache()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for item in ('repo', 'cohort', 'protocol', 'out'):
        parser.add_argument('--' + item, required=True)
    run(**vars(parser.parse_args()))
