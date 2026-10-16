"""Freeze separately named TF5-compatible parity after its new kernel closes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--diagnostic-receipt', default='data/private/chess-queen-nf4-v1/kernel-2.json')
parser.add_argument('--worker-receipt', default='data/private/chess-queen-nf4-v1/kernel-worker-2.json')
args = parser.parse_args()


def item(path):
    return {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


prior = item('experiments/chess-queen-nf4-v1/parity-protocol-v2.json')
assert prior['sha256'] == '14a5b78f91cb7620034fafaef85646abdf519cc2e465b05b3ccd692785a5783b'
plan = json.loads((ROOT / prior['path']).read_text())
kernel_path = 'experiments/chess-queen-nf4-v1/kernel-protocol-v2.json'
kernel = json.loads((ROOT / kernel_path).read_text())
diagnostic = json.loads((ROOT / args.diagnostic_receipt).read_text())
worker = json.loads((ROOT / args.worker_receipt).read_text())
if diagnostic.get('status') != 'passed' or diagnostic.get('all_checks_passed') is not True or diagnostic.get('source_sha256') != kernel['implementation_sha256'] or diagnostic.get('protocol_sha256') != item(kernel_path)['sha256']:
    raise ValueError('New matching actual kernel diagnostic has not passed')
if worker.get('status') != 'completed' or worker.get('exit_code') != 0 or worker.get('child_exited_before_lease_release') is not True:
    raise ValueError('New diagnostic worker has not closed successfully')
plan.pop('previous_unexecuted_protocol', None)
plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),
    implementation_sha256=item('experiments/chess-queen-nf4-v1/parity_no_cache_v2.py')['sha256'],
    previous_executed_protocol=prior,
    amendment='Actual prior parity1 failed after loading/quantization but before any pretrained forward because optional Transformers5 hf_device_map was absent. Separately named v2 adapter/parity preserve the executed sources, verify actual CUDA0 tensors, report absent optional metadata honestly, and bind a fresh successful matching tiny kernel. The new parity also persists model_load_started before loading. Method, prefixes, thresholds and reserves are unchanged.',
    kernel_protocol=item(kernel_path), diagnostic_receipt=item(args.diagnostic_receipt),
    diagnostic_worker_receipt=item(args.worker_receipt))
plan['dependencies'] = [item(path) for path in ('scripts/chess_queen_nf4_adapter_v2.py',
    'tests/test_chess_queen_nf4_parity_v2.py', 'experiments/chess-queen-v1/gpu_worker.py')]
plan['preserved_failed_attempt'] = item('data/private/chess-queen-nf4-v1/parity-1.json')
with (HERE / 'parity-protocol-v3.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'source': plan['implementation_sha256'],
    'protocol': item('experiments/chess-queen-nf4-v1/parity-protocol-v3.json')['sha256'],
    'tests': plan['dependencies'][1]['sha256']}))
