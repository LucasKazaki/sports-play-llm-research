"""Exactly twelve read-only resource queries; no model, engine or framework."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'scripts'))
from cold_eval_v6 import append, bound, digest, read, save
from chess_native_resources import windows_sample, reasons, Policy, GIB


def execute(protocol, request, out, parent_cancel):
    plan = read(protocol)
    if plan['probe_child']['sha256'] != digest(Path(__file__)): raise ValueError('Probe child source differs')
    for item in plan['dependencies']: bound(item)
    if out.exists(): raise ValueError('Probe child is create-only')
    out.mkdir(parents=True); started = time.monotonic()
    result = {'status': 'started', 'pid': os.getpid(), 'parent_pid': os.getppid(),
        'planned_sampler_calls': 12, 'completed_sampler_calls': 0,
        'source_sha256': digest(Path(__file__)), 'protocol_sha256': digest(protocol)}
    save(out / 'closed.json', result)
    policy = Policy(start_physical_available_bytes=6*GIB, start_commit_headroom_bytes=10*GIB,
        start_gpu_free_bytes=10*GIB, stop_physical_available_bytes=4*GIB,
        stop_commit_headroom_bytes=4*GIB, stop_gpu_free_bytes=GIB)
    try:
        # Give the parent observer time to retain the delegate before queries start.
        time.sleep(.3)
        for index in range(12):
            if (parent_cancel.exists() or time.monotonic()-started >= 30
                or datetime.now(timezone.utc) >= datetime.fromisoformat(plan['cutoff_utc'])):
                raise RuntimeError('Owned CPU probe clock/cancel')
            append(out / 'sampler-calls.jsonl', {'index': index, 'status': 'call_started'})
            sample = windows_sample()
            append(out / 'sampler-calls.jsonl', {'index': index, 'status': 'completed', 'sample': sample.__dict__})
            result['completed_sampler_calls'] += 1
            if reasons(sample, policy, 'start' if index == 0 else 'running'):
                raise RuntimeError('Frozen resource floors reject CPU probe')
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error=type(error).__name__ + ': ' + str(error)); raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-started, torch_imported='torch' in sys.modules,
            model_calls=0, engine_calls=0, CUDA_initializations=0)
        save(out / 'closed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('protocol', 'request', 'out', 'parent-cancel'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); execute(args.protocol, args.request, args.out, args.parent_cancel)
