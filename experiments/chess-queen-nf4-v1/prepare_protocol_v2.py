"""Freeze TF5 device-map metadata compatibility repair; no backend calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def item(path):
    return {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


prior = item('experiments/chess-queen-nf4-v1/kernel-protocol.json')
assert prior['sha256'] == 'f2e41e4e10889f791b11c149b636a5dcc18e724d37e5b2981eb7117a0249df6c'
plan = json.loads((ROOT / prior['path']).read_text())
plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),
    implementation_sha256=item('scripts/chess_queen_nf4_adapter_v2.py')['sha256'],
    previous_protocol=prior,
    amendment='Actual full-model NF4 parity1 quantized the decoder but stopped before any forward: Transformers5 SmolLM3ForCausalLM did not retain optional hf_device_map. The v2 separately named source accepts absent/None metadata only after actual registered tensor CUDA0 verification, records metadata absence explicitly and still rejects malformed/CPU/disk maps. Quantization, tensors, all other numeric/rights/resource contracts remain unchanged. Fresh matching tiny diagnostic required.')
plan['model_candidate']['id'] = 'queen-pawn-8/native-nf4-v2'
plan['model_candidate']['placement_metadata'] = 'Explicit cuda0 requested; every registered parameter/buffer is independently checked. Optional hf_device_map absent/None is reported as absent, not invented; any present map must be dict containing only cuda0 destinations.'
plan['dependencies'] = [item('tests/test_chess_queen_nf4_adapter_v2.py') if binding['path'] == 'tests/test_chess_queen_nf4_adapter.py' else binding for binding in plan['dependencies']]
plan['preserved_actual_attempts'] = [item(path) for path in (
    'scripts/chess_queen_nf4_adapter.py', 'experiments/chess-queen-nf4-v1/parity_no_cache.py',
    'experiments/chess-queen-nf4-v1/parity-protocol-v2.json',
    'data/private/chess-queen-nf4-v1/kernel-1.json', 'data/private/chess-queen-nf4-v1/kernel-worker-1.json',
    'data/private/chess-queen-nf4-v1/parity-1.json', 'data/private/chess-queen-nf4-v1/parity-worker-1.json')]
with (HERE / 'kernel-protocol-v2.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'source': plan['implementation_sha256'],
    'protocol': item('experiments/chess-queen-nf4-v1/kernel-protocol-v2.json')['sha256'],
    'tests': item('tests/test_chess_queen_nf4_adapter_v2.py')['sha256']}))
