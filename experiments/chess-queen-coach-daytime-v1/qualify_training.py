"""Root-only disposable eight-micro warm-training-route software qualifier."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import daytime_contract as contract
import chess_queen_coach_counterfactual_train_v2 as preserved
from chess_queen_coach_counterfactual_runtime_v1 import Runtime, checked, validate_start

save = preserved.save
append = preserved.append


def verify(path):
    plan = checked.nf4.base.read_json(path)
    if (plan['implementation_sha256'] != checked.nf4.base.digest(Path(__file__))
        or plan['schema'] != 'chess.queen-coach-daytime-warm-qualification.v1'
        or plan['maximum_seconds'] != 600 or plan['planned_updates'] != 1
        or plan['planned_presentations'] != 8 or plan['disposable_not_candidate'] is not True):
        raise ValueError('Exact disposable eight-micro software plan required')
    for item in plan['dependencies']:
        checked.nf4.binding(item)
    contract.windows(plan, checked.nf4.binding, checked.nf4.base.read_json)
    old = checked.nf4.base.read_json(checked.nf4.binding(plan['preserved_overnight_protocol']))
    contract.science(plan, old)
    actual = preserved.verify_preflight(plan, checked.nf4.binding, checked.nf4.base.read_json)
    contract.tokenizer(plan, actual)
    validate_start(plan['warm_start'])
    return plan


def first_eight(rows, seed):
    if len(rows) != 1536:
        raise ValueError('Exact frozen TRAIN denominator required')
    order = list(range(1536))
    random.Random(seed).shuffle(order)
    return [rows[index] for index in order[:8]]


def micros(runtime, rows, tokens, optimizer, clip, synchronize, out, result, guard):
    """Actual loss includes /8 backward; call order and failure accounting are testable."""
    if len(rows) != 8 or len(tokens) != 8:
        raise ValueError('Exactly eight complete software micros required')
    for index, (row, tokenized) in enumerate(zip(rows, tokens)):
        guard()
        intent = {'micro': index, 'case_id': row['case_id'], 'status': 'call_started'}
        result['rows'][index]['status'] = 'active_unknown'
        result['inflight'] = intent
        save(out / 'qualification.json', result)
        append(out / 'calls.jsonl', intent)
        loss = runtime.loss(row, tokenized, training=True)
        if not math.isfinite(loss):
            raise ValueError('Nonfinite software loss')
        append(out / 'calls.jsonl', {**intent, 'status': 'backward_completed', 'loss': loss})
        result['rows'][index].update(status='completed', loss=loss)
        result['presentations_completed'] += 1
        result['inflight'] = None
        save(out / 'qualification.json', result)
        runtime.release_inactive('qualification_after_returned_backward_' + str(index))
    runtime.verify_gradients()
    result['gradient_evidence'] = runtime.live_hashes()
    norm = float(clip())
    if not math.isfinite(norm) or norm <= 0:
        result['gradient_clip_norm_finite_positive'] = False
        raise ValueError('Nonfinite/zero aggregate gradient norm before optimizer')
    result['gradient_clip_norm'] = norm
    result['gradient_clip_norm_finite_positive'] = True
    runtime.verify_gradients()
    result['optimizer_status'] = 'active_unknown'
    result['inflight'] = {'status': 'optimizer_started'}
    save(out / 'qualification.json', result)
    append(out / 'calls.jsonl', result['inflight'])
    optimizer.step()
    synchronize()
    append(out / 'calls.jsonl', {'status': 'optimizer_completed'})
    result.update(updates_completed=1, optimizer_status='completed', inflight=None)
    save(out / 'qualification.json', result)
    optimizer.zero_grad(set_to_none=True)
    runtime.release_inactive('qualification_after_complete_optimizer')


def snapshot(plan, protocol, out):
    folder = out / 'executed-sources'
    folder.mkdir()
    manifest = {}
    paths = [Path(__file__), Path(protocol)] + [checked.nf4.binding(item) for item in plan['dependencies']]
    for index, path in enumerate(paths):
        target = folder / (f'{index:02d}-' + path.name)
        shutil.copyfile(path, target)
        manifest[target.name] = {'path': str(path), 'sha256': checked.nf4.base.digest(target)}
    save(folder / 'manifest.json', manifest)


def run(plan, protocol, out, runtime_factory=Runtime, guard_factory=None):
    if out.exists():
        raise ValueError('Software attempt is create-only; no replay')
    out.mkdir(parents=True)
    started = time.monotonic()
    result = {'schema': 'chess.queen-coach-daytime-warm-qualification-result.v1',
        'status': 'started', 'protocol_sha256': checked.nf4.base.digest(protocol),
        'source_sha256': checked.nf4.base.digest(Path(__file__)),
        'planned_updates': 1, 'updates_completed': 0, 'planned_presentations': 8,
        'presentations_completed': 0, 'optimizer_status': 'not_run', 'inflight': None,
        'rows': [{'micro': index, 'status': 'not_run'} for index in range(8)],
        'checks': {}, 'disposable_not_candidate': True,
        'claim': 'Software route/gradient/storage qualification only; no model-quality acceptance or candidate learning.'}
    save(out / 'qualification.json', result)
    samples = []
    try:
        if plan != verify(protocol):
            raise ValueError('In-memory qualification plan differs from frozen file')
        rows = first_eight(preserved.read_rows(checked.nf4.binding(plan['data']['train']), True),
            plan['training']['seed'])
        for index, row in enumerate(rows):
            result['rows'][index]['case_id'] = row['case_id']
        save(out / 'qualification.json', result)
        snapshot(plan, protocol, out)
        if guard_factory is None:
            guard_plan = {**plan, 'phase_maximum_seconds': {'qualification': 600}}
            base_guard, samples, policy = preserved.prior.guard_for(guard_plan, out / 'qualification.json')
            result['resource_policy'] = policy.__dict__
        else:
            base_guard, samples = guard_factory()
        def guard():
            if (out / 'CANCEL').exists() or (out / 'qualification.CANCEL').exists():
                raise RuntimeError('Owned qualification cancellation')
            if time.monotonic() - started >= 600:
                raise RuntimeError('Frozen600s software phase cap')
            if datetime.now(timezone.utc) >= datetime.fromisoformat(plan['cutoff_utc']):
                raise RuntimeError('Frozen22UTC cutoff')
            base_guard()
        guard()
        result['phase'] = 'model_load_started'
        save(out / 'qualification.json', result)
        runtime = runtime_factory(plan, guard)
        runtime.memory_journal = out / 'memory-lifetime.jsonl'
        runtime.load()
        torch = runtime.torch
        runtime.release_inactive('qualification_after_warm_load')
        expected = torch.load(checked.nf4.binding(plan['warm_start']), map_location='cpu', weights_only=True)
        if set(expected) != {name for name, _ in runtime.parameters}:
            raise ValueError('Original warm checkpoint keys differ')
        for name, value in runtime.parameters:
            if (expected[name].dtype != torch.float32 or value.dtype != torch.float32
                or tuple(expected[name].shape) != tuple(value.shape)
                or not bool(torch.isfinite(expected[name]).all())):
                raise ValueError('Original warm checkpoint values/shape/dtype differ')
        expected_hash = checked.streamed_hash(torch,
            [(name, expected[name]) for name, _ in runtime.parameters], guard)
        before = checked.streamed_hash(torch, runtime.parameters, guard)
        if before != expected_hash or before != runtime.warm_start_effective_hash:
            raise ValueError('Actual wrapper did not load exact original64 tensors')
        result['warm_start'] = plan['warm_start']
        result['warm_expected_hash'] = expected_hash
        result['adapter_before'] = before
        del expected
        tokens = [runtime.tokenize(row) for row in rows]
        optimizer = torch.optim.AdamW([value for _, value in runtime.parameters],
            lr=plan['training']['learning_rate'] / plan['training']['warmup_updates'],
            betas=(.9, .999), eps=1e-8, weight_decay=.01, foreach=False)
        optimizer.zero_grad(set_to_none=True)
        micros(runtime, rows, tokens, optimizer,
            lambda: torch.nn.utils.clip_grad_norm_([value for _, value in runtime.parameters], 1.),
            torch.cuda.synchronize, out, result, guard)
        after = checked.streamed_hash(torch, runtime.parameters, guard)
        if after == before:
            raise ValueError('Disposable software adapter did not change')
        result['adapter_after'] = after
        result['frozen_storage'] = runtime.verify_frozen()
        identity = runtime.save_adapter(out / 'disposable-not-a-candidate', 1, 8)
        result['disposable_adapter'] = identity
        if (identity['candidate_id'] != 'queen-pawn-8/nf4-coach-counterfactual-v1'
            or identity['source_sha256'] != plan['counterfactual_runtime']['sha256']
            or identity['warm_start'] != plan['warm_start']):
            raise ValueError('Disposable wrapper save provenance differs')
        runtime.load_adapter(identity)
        reloaded = checked.streamed_hash(torch, runtime.parameters, guard)
        if reloaded != after:
            raise ValueError('Strict disposable save/reload changed values')
        result['reloaded_adapter_hash'] = reloaded
        result['frozen_storage_after_reload'] = runtime.verify_frozen()
        checks = {'effective_original64_equal': before == expected_hash,
            'complete_eight_micros': result['presentations_completed'] == 8,
            'finite_losses': all(math.isfinite(row['loss']) for row in result['rows']),
            'finite_nonzero_gradients': result['gradient_evidence']['gradient_tensors'] == 144
                and math.isfinite(result['gradient_clip_norm']) and result['gradient_clip_norm'] > 0,
            'exact_fp32_adapter_inventory': len(runtime.parameters) == 144 and sum(value.numel() for _, value in runtime.parameters) == 1916928,
            'adapter_changed': after != before,
            'frozen_storage_unchanged': result['frozen_storage']['identical'] and result['frozen_storage_after_reload']['identical']
                and result['frozen_storage']['before']['tensor_count'] == 2268
                and result['frozen_storage_after_reload']['before']['tensor_count'] == 2268,
            'strict_save_reload_equal': reloaded == after, 'disposable_not_candidate': True}
        if set(checks) != contract.UPDATE_CHECKS or not all(checks.values()):
            raise ValueError('Software acceptance checks failed')
        result.update(status='passed', phase='closed', checks=checks)
    except BaseException as error:
        result.update(status='failed', error=type(error).__name__ + ': ' + str(error))
        save(out / 'failure.json', result)
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        save(out / 'resources.json', samples)
        save(out / 'qualification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(checked.nf4.base.read_json(args.protocol), args.protocol, args.out)
