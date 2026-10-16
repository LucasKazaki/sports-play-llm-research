"""Create-only authored one-step diagnostic freeze; no backend/model imports."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_queen_qlora_v1 as experiment
QUEEN = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/queen-source')


def item(path):
    path = Path(path)
    return {'path': str(path).replace('\\', '/'), 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


kernel_path = 'experiments/chess-queen-nf4-v1/kernel-protocol-v2.json'
kernel = json.loads((ROOT / kernel_path).read_text())
plan = {
    'schema': 'chess.queen-qlora-authored-diagnostic-protocol.v1',
    'frozen_at': datetime.now(timezone.utc).isoformat(),
    'implementation_sha256': item('scripts/chess_queen_qlora_v1.py')['sha256'],
    'kind': 'One authored forward/backward/AdamW update; numerical/gradient/resource feasibility only. No source game selected and no chess-understanding or coaching quality claim.',
    'fixture': experiment.FIXTURE, 'target': experiment.target_for_fixture(),
    'input_contract': 'Current FEN only. Native no-forward packet validator and exact current-only encoder. Authored verified mate appears in assistant TARGET only. Original model hallucinated prose is not used as supervision.',
    'lora': experiment.LORA, 'seed': 4082082, 'learning_rate': .0001,
    'optimizer': {'name': 'AdamW', 'betas': [.9,.999], 'eps': 1e-8, 'weight_decay': .01,
        'foreach': False, 'gradient_clip_norm': 1., 'updates': 1},
    'trainable': {'tensor_count': 144, 'parameter_count': 1916928,
        'dtype': 'float32', 'device': 'cuda0', 'initialization': 'PEFT zero-B no-op',
        'scope': 'Onlyq/v LoRA A/B in all36decoder layers; no trained bridge/embedding/encoder/baseweight'},
    'forward': {'implementation': 'Exact pinned official Flamingo manual walk, actual base decoder object retained after PEFT injects in place; n_new_tokens0/lora_rank0 constructor avoids duplicate/refrozen LoRA.',
        'conditioning': 'Encoder current FEN under no_grad;16frozen BF16 bridges inside ordinary autograd/manual checkpoint closures.',
        'checkpointing': 'rl_activation_checkpointingTrue -> use_reentrantFalse/preserve_rng_stateFalse perofficialsource; HF layer checkpointing muststayoff to avoiddoublecheckpoint.',
        'loss': 'Official full128333-vocabulary shifted CE, assistant/closing tokens only; logit_chunk_size32, no truncation, context≤512.',
        'precision': 'Same reviewed math_sdpa_fp32_reduction; quantbaseBF16compute and frozen BF16 full tied embedding/head retained. No generic prepare_model_for_kbit_training bulkFP32 upcast.',
        'cache': False},
    'storage_verification': 'Stream exact raw storage hashes before/after for all original registered decoder/encoder/bridge params/buffers plus unregistered nestedNF4 scale/codebook tensors using≤1MiB host chunks. Require unchanged complete frozen hash and no frozen gradients; allLoRA gradients finite/nonzeroinaggregate, LoRA storage hashchanged. No adapted weights are promoted or reused for TRAIN.',
    'required_checks': sorted(experiment.EXPECTED_CHECKS),
    'maximum_seconds': 240, 'worker_deadline_seconds': 270,
    'worker_maximum_seconds_argument': 240,
    'resources': kernel['resources'],
    'durability': 'Create-only attempt before setup; one full planned update retained. Save intent and completion/timing per load/hash/encoder/loss/backward/update stage. Count/persist actual completed update before poststep resource guard. First exception/resource/cancel ends all further work; preserve started/unknown phases and failures, no repeat under same receipt.',
    'interpretation': 'A finite nonzero gradient and changed LoRA prove software learning machinery works on this authored target only. It cannot establish chess understanding, generalization or coaching. Fresh optimizer/seed and separately frozen source corpus/training/evaluation are needed later.',
    'kernel_protocol': item(kernel_path),
    'kernel_receipt': item('data/private/chess-queen-nf4-v1/kernel-2.json'),
    'authored_runtime_receipt': item('data/private/chess-queen-nf4-v1/authored-0.json'),
    'runtime_versions': {name: metadata.version(name) for name in ('torch','transformers','bitsandbytes','peft','accelerate','safetensors','numpy')},
    'dependencies': [item(path) for path in (
        'scripts/chess_queen_nf4_adapter_v2.py', 'scripts/chess_queen_adapter.py',
        'scripts/chess_queen_materialize.py', 'scripts/chess_native_resources.py',
        'tests/test_chess_queen_qlora_v1.py', 'experiments/chess-queen-v1/gpu_worker.py',
        'experiments/chess-queen-nf4-v1/parity-protocol-v3.json',
        'data/private/chess-queen-nf4-v1/parity-2.json', 'data/private/chess-queen-nf4-v1/parity-worker-2.json',
        'data/private/chess-queen-nf4-v1/authored-0-worker.json')]
        + [item(QUEEN / path) for path in ('utils/instance_format.py', 'models/base.py', 'models/flamingo.py', 'models/adapters/smollm.py')]
        + [item('.venv-soccernet/Lib/site-packages/' + path) for path in ('peft/mapping_func.py', 'peft/peft_model.py',
            'peft/utils/other.py', 'peft/tuners/lora/bnb.py', 'transformers/modeling_layers.py')],
    'full_training_scope': 'NOT FROZEN: throughput-informed pilot proposed1024freshTRAINgames/2048pairedexamples,32devNLLgames/raw4fixedgamesx2modes/checkpoint,16new3plyheldgames baseline+selectedx2modes. All generation1024tokens180s equally. No corpus selected or heldout called by this diagnostic.'}
with (HERE / 'diagnostic-protocol.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'source': plan['implementation_sha256'],
    'protocol': item('experiments/chess-queen-qlora-v1/diagnostic-protocol.json')['sha256'],
    'test': item('tests/test_chess_queen_qlora_v1.py')['sha256']}))
