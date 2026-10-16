"""Freeze already approved method against the root's completed CPU Queen pool.

This metadata-only preparation makes no source intake, backend import or model
call. The final protocol is create-only and must receive independent review.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024**2), b''):
            result.update(block)
    return result.hexdigest()


def binding(path):
    actual = ROOT / path
    return {'path': str(path).replace('\\', '/'), 'sha256': digest(actual)}


queen_pool = binding('data/private/chess-queen-benchmark-v1/dataset.json')
if queen_pool['sha256'] != '2a7e6d660d1fc28c3b34e99c5dcd29dc8441fad30664e7d2690e6e812277c8cf':
    raise ValueError('Root-provided Queen pool differs')
source_manifest = json.loads((ROOT / 'experiments/chess-queen-v1/source-manifest.json').read_text())
source_root = Path(source_manifest['checkout'])
reuse = 'data/private/chess-check-balanced-v2/cohort/'
source_dependencies = ['scripts/chess_board_fact_core.py', 'scripts/chess_check_balanced_v2.py',
    'scripts/chess_fact_sft_common.py', 'scripts/chess_fact_sft_intake.py',
    'scripts/chess_board_fact_diagnostic.py', 'scripts/chess_native_resources.py',
    'scripts/chess_queen_adapter.py', 'tests/test_chess_encoder_check_v1.py']
encoder_source = binding(source_root / 'models/encoder.py')
planes_source = binding(source_root / 'utils/lc0_planes.py')
plan = {
    'schema': 'chess.encoder-check.v1',
    'frozen_at': datetime.now(timezone.utc).isoformat(),
    'implementation_sha256': digest(ROOT / 'scripts/chess_encoder_check_v1.py'),
    'hypothesis': 'A small trained selected-move head can learn check discrimination from frozen expert current-board LC0 features more reliably than majority-false or an untrained head.',
    'source': {**binding('data/private/chess-fact-sft-v1/source/lichess-hf-train-00000.parquet'),
        'license': 'CC0-1.0; retained pinned local source; no new data acquisition',
        'upstream': 'https://huggingface.co/datasets/Lichess/chess-puzzles/resolve/461725966ea46898ec6481372a6326de3281bfbd/data/train-00000-of-00003.parquet'},
    'known_registry': binding('experiments/chess-matched-check-v1/archive/v2/known-history-exclusions-v2.json'),
    'excluded_cohorts': [binding(path) for path in [
        'data/private/chess-matched-check-diagnostic-v1/cohort/dataset.json',
        reuse + 'dataset.json', 'data/private/chess-move-policy-v5/dataset.json',
        'data/private/chess-move-policy-v6/dataset.json']],
    'queen_benchmark': queen_pool,
    'queen_pool_protocol_sha256': '19d48f385a97583f5c577a4e918b36cdffc5fcba0f7a1daaec2281ff83147e8a',
    'reused_dataset': binding(reuse + 'dataset.json'),
    'reuse': {split + '_' + kind: binding(reuse + split + '-' + kind + '.json')
             for split in ('train', 'dev') for kind in ('inputs', 'labels')},
    'reused_pairs': {'train': 8192, 'dev': 128},
    'holdout_pairs': 256, 'seed': 4082071, 'source_row_cap': 500000,
    'intake': 'Exact balanced-v2 TRAIN/dev rows and labels only. New heldout256 original games in deterministic source order, one matched same-piece/capture-category checking/nonchecking pair per game. Consume source setup token only. Exclude all registered historical games/before/current and selected-successor boards, all V5 roots, all V6 new roots including every unused reservoir candidate, and all96 Queen pool games/before/current boards. No old heldout training reuse.',
    'encoder': {'model_id': 'princeton-nlp/queen_pawn-8',
        'model_revision': '5027687fac08b64b2403b13aca5b198e68294fe9',
        'source_revision': source_manifest['revision'],
        'directory': 'data/private/chess-queen-v1/pawn-8/lc0',
        'weights': binding('data/private/chess-queen-v1/pawn-8/lc0/model.safetensors'),
        'config': binding('data/private/chess-queen-v1/pawn-8/lc0/config.json'),
        'source': encoder_source, 'planes_source': planes_source,
        'precision': 'All floating buffers explicitly BF16, policy_index_map int64, target-only meta materialization; encoder eval/frozen. No language decoder or bridge instantiated.',
        'rights': 'Queen source Apache-2.0. Publisher asserts no blanket combined-weights license; LC0 component terms retained. Private local experimentation only; no redistribution claim.'},
    'features': 'Current six-field FEN + selected legal UCI only. No history/postboard/PV/answer fields. Empty history uses pinned upstream FEN-only synthesis. Deduplicate exact canonical current FEN for one encoder forward per board; retain every requested move identity. Cache FP32 current-state mean/source/target vectors3072 + native POV source/target/promotion indices; label-free manifest. No policy/value/engine outputs. Heldout extraction only after saved dev selection and training-feature hash check.',
    'head': 'Learned source64x32/target64x32/promotion5x8 embeddings. Concatenate to3072 frozen features,3144->512ReLU->128ReLU->1. Exactly1680169 trainable head parameters. Raw logit>=0 check prediction; no class mask or rule replacement.',
    'training': {'optimizer': 'AdamW', 'learning_rate': .001, 'weight_decay': .01,
        'batch_size': 256, 'epochs': 8, 'checkpoint_epochs': [0, 1, 2, 4, 8],
        'seed': 4082072, 'planned_optimizer_updates': 512, 'gradient_clip': 1.,
        'objective': 'FP32 binary_cross_entropy_with_logits on exactly16384 reused TRAIN moves per epoch. All encoder buffers remain frozen; only the1680169-parameter head learns.'},
    'selection': 'Highest development number correct, then most complete two-move pairs correct, then earliest epoch including0. Save selection and checkpoint hashes before any heldout pretrained call.',
    'evaluation': 'Full512 fresh heldout moves/256pairs remain denominators. Report TP/TN/FP/FN, checking/nonchecking recall, pair correctness, invalid/unknown/failed/notrun; same-panel majority-false, actual saved untrained head and selected head. Alias selected0 without replay. First backend failure stops further calls/conditions. Per-batch durable intent/results and full ledgers; recovery never makes model calls.',
    'maximum_seconds': 5400,
    'resources': 'Root-owned CUDA only. Start>=6GiB physical/8GiB commit/4GiB GPU available; running>=4GiB physical/6GiB commit/512MiB GPU. Read-only samples at most once per second, cooperative before each encoder call and per64optimizer updates; owned CANCEL/deadline checks. No settings changes.',
    'dependencies': [binding(path) for path in source_dependencies] + [encoder_source, planes_source,
        binding(source_root / 'LICENSE'), binding('data/private/chess-queen-v1/pawn-8/lc0/config.json')],
    'native_environment': {name: metadata.version(name) for name in
        ('torch', 'transformers', 'safetensors', 'accelerate', 'peft', 'bitsandbytes')},
    'limitations': ['Check discrimination only; not explanation quality, language understanding, move strength or Elo.',
        'Matched tactical same-piece pairs; promotions/castling/en passant not covered by this real cohort.',
        'Unknown overlap with original encoder pretraining. Reused development set is not fresh evidence.',
        'Synthetic software tests do not establish actual model learning.'],
    'primary_sources': ['https://huggingface.co/princeton-nlp/queen_pawn-8',
        'https://github.com/queen-project/queen/tree/c372da22ca75e95c3c79bee8a83c220fc54d0dcb',
        'https://database.lichess.org/']
}
target = Path(__file__).parent / 'protocol.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'protocol_sha256': digest(target), 'implementation_sha256': plan['implementation_sha256'],
                  'queen_pool_sha256': queen_pool['sha256']}))
