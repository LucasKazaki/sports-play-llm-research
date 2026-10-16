"""Freeze four old authored packets for NF4 after actual canonical parity."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('same_nf4_parity', HERE / 'parity_no_cache_v2.py')
parity = importlib.util.module_from_spec(spec); spec.loader.exec_module(parity)


def item(path):
    return {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


parity_path = 'data/private/chess-queen-nf4-v1/parity-2.json'
worker_path = 'data/private/chess-queen-nf4-v1/parity-worker-2.json'
parity_plan, _, kernel = parity.verify_plan(HERE / 'parity-protocol-v3.json',
    ROOT / 'data/private/chess-queen-nf4-v1/kernel-2.json')
actual = json.loads((ROOT / parity_path).read_text()); worker = json.loads((ROOT / worker_path).read_text())
if actual.get('status') != 'passed' or actual.get('source_sha256') != parity_plan['implementation_sha256'] or actual.get('protocol_sha256') != item('experiments/chess-queen-nf4-v1/parity-protocol-v3.json')['sha256'] or not parity.verdict(actual['comparisons'], parity_plan['thresholds']):
    raise ValueError('Actual source-bound same-NF4 canonical preflight has not passed')
if worker.get('status') != 'completed' or worker.get('exit_code') != 0 or worker.get('child_exited_before_lease_release') is not True:
    raise ValueError('Canonical worker is not successfully closed')
prior = json.loads((ROOT / 'experiments/chess-queen-v1/authored-nocache-protocol-v2.json').read_text())
packets = []
for old in prior['packets']:
    bound = item(old['path'])
    if bound['sha256'] != old['sha256']: raise ValueError('Old authored packet changed')
    packet = json.loads((ROOT / bound['path']).read_text()); parity.nf4.base.input_packet(packet)
    packets.append({**bound, 'input_keys': sorted(packet), 'initial_status': 'not_run',
        'kind': 'Authored software fixture; no source-game capability claim'})
plan = {
    'schema': 'chess.queen-nf4-authored-generation-protocol.v1',
    'frozen_at': datetime.now(timezone.utc).isoformat(),
    'frozen_before_this_condition_generation': True,
    'candidate_id': 'queen-pawn-8/native-nf4-v2',
    'adapter': item('scripts/chess_queen_nf4_adapter_v2.py'),
    'kernel_protocol': item('experiments/chess-queen-nf4-v1/kernel-protocol-v2.json'),
    'kernel_receipt': item('data/private/chess-queen-nf4-v1/kernel-2.json'),
    'kernel_worker': item('data/private/chess-queen-nf4-v1/kernel-worker-2.json'),
    'canonical_protocol': item('experiments/chess-queen-nf4-v1/parity-protocol-v3.json'),
    'canonical_source': item('experiments/chess-queen-nf4-v1/parity_no_cache_v2.py'),
    'canonical_receipt': item(parity_path), 'canonical_worker': item(worker_path),
    'packets': packets, 'planned_denominator': 4,
    'generation': {'max_new_tokens': 1024, 'maximum_seconds': 240, 'temperature': 0,
        'seed': 20260823, 'generation_mode': 'no_cache', 'precision_profile': 'math_sdpa_fp32_reduction'},
    'quantization': kernel['quantization'], 'resources': kernel['resources'],
    'execution': {'owner': 'root only', 'parallel_workers': 1,
        'fresh_short_lived_worker_each_packet': True, 'worker_maximum_seconds_argument': 240,
        'actual_worker_deadline_seconds': 270, 'worker': item('experiments/chess-queen-v1/gpu_worker.py'),
        'arguments': ['scripts/chess_queen_nf4_adapter_v2.py', '--diagnostic-receipt', 'data/private/chess-queen-nf4-v1/kernel-2.json', '--input', '{packet.path}', '--out', '{new_create_only_receipt}']},
    'durability': 'Root writes all4 pending rows before worker dispatch, then persists each intent before its owned call and links actual worker/output hashes after closure. Retain partial raw text/token IDs, finish reason, truncation, resources and errors. Unknown interrupted calls stay unknown; undispatched calls stay not_run.',
    'failure_policy': 'First backend/resource/worker failure halts all remaining packets. Semantic missing/illegal/truncated output remains failed as software output quality, with full4 denominator; never replace a raw move or repair a continuation. No repeated attempts under this condition.',
    'completion_checks': ['Actual worker terminal and child exited before lease release',
        'Raw complete response ends by EOS instead of token/time limit; no backend/resource error',
        'Report structured BEST_MOVE parse, raw legality and CRITICAL_LINE legal prefix with missing/invalid results visible',
        'Inspect exact raw explanation against each authored board; arbitrary plans remain unverified'],
    'preserved_bf16_protocol': item('experiments/chess-queen-v1/authored-nocache-protocol-v2.json'),
    'preserved_bf16_outcomes': item('data/private/chess-queen-v1/authored-nocache-outcomes-v2.json'),
    'capability_claims_allowed': False,
    'interpretation': 'Runtime/output inspection on four old authored boards only. Passing is a prerequisite for later measured chess-specific tuning/evaluation, not evidence of unseen-game strength, coaching correctness or Elo.'}
with (HERE / 'authored-protocol.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'protocol': item('experiments/chess-queen-nf4-v1/authored-protocol.json')['sha256'],
    'canonical_receipt': item(parity_path), 'canonical_worker': item(worker_path), 'planned': len(packets)}))
