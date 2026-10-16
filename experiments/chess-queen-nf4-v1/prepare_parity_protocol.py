"""Create-only freeze for same-quantized-decoder canonical software parity."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def item(path):
    return {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


plan = {
    'schema': 'chess.queen-nf4-no-cache-parity-protocol.v1',
    'frozen_at': datetime.now(timezone.utc).isoformat(),
    'implementation_sha256': item('experiments/chess-queen-nf4-v1/parity_no_cache.py')['sha256'],
    'kind': 'Authored numerical software preflight. No chess evaluation or model tuning.',
    'fixture': {'fen': '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'},
    'suffix': '<SQUARE_1><PIECE_MP><EMPTY>',
    'conditions': ['base_prompt', 'synthetic_vocabulary_suffix'],
    'comparison': 'Each complete token prefix is evaluated independently without a KV cache. Compare its final-position raw logits between the pinned official manual Flamingo walk and native bridge hooks, sharing the identical actual NF4 decoder and BF16 bridges. Both use the same once-encoded current FEN.',
    'logit_scopes': {'all_logits': [0, 128333], 'original_vocab_logits': [0, 128256], 'added_vocab_logits': [128256, 128333]},
    'thresholds': {'max_absolute_error': .01, 'mean_absolute_error': .001, 'minimum_cosine_similarity': .9999},
    'additional_requirements': ['Finite logits and equal argmax in every scope for both prefixes',
        'Three synthetic suffix tokens all belong to the added Queen vocabulary',
        'Verified actual252 NF4 decoder linears, BF16 encoder/bridges/full tied vocabulary, CUDA0 only',
        'No further forward after a backend exception or nonfinite output',
        'Create-only attempt, intent persisted before each forward, completed comparisons saved immediately'],
    'kernel_protocol': item('experiments/chess-queen-nf4-v1/kernel-protocol.json'),
    'diagnostic_receipt': item('data/private/chess-queen-nf4-v1/kernel-1.json'),
    'diagnostic_worker_receipt': item('data/private/chess-queen-nf4-v1/kernel-worker-1.json'),
    'root_only_execution': {'worker_deadline_seconds': 270,
        'worker_maximum_seconds_argument': 240,
        'worker': item('experiments/chess-queen-v1/gpu_worker.py'),
        'resources': 'Exactly the kernel-protocol reserves, including4GiB commit stop floor; cancellation and owned process lease preserved.'},
    'dependencies': [item(path) for path in ('scripts/chess_queen_nf4_adapter.py',
        'tests/test_chess_queen_nf4_parity.py', 'experiments/chess-queen-v1/gpu_worker.py')],
    'interpretation': 'Passing establishes two software-prefix implementations agree for the same locally quantized weights. It establishes neither BF16 equivalence, generation quality, chess understanding, coaching quality nor published Elo. Authored end-to-end generation is a separate next condition; no QLoRA training is implemented.'}
with (HERE / 'parity-protocol.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'parity_source': plan['implementation_sha256'],
    'protocol': item('experiments/chess-queen-nf4-v1/parity-protocol.json')['sha256'],
    'tests': plan['dependencies'][1]['sha256']}))
