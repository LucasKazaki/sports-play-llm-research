"""Freeze separate source after actual TF5 tokenizer failure; no model calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def item(path):
    return {'path':path,'sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}


prior=item('experiments/chess-queen-qlora-v1/diagnostic-protocol.json')
assert prior['sha256']=='86a8bd20666e8e0344c334b24bbe057db5bed09848a99105fc57f2907a6ffcf2'
plan=json.loads((ROOT/prior['path']).read_text())
plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),
    implementation_sha256=item('scripts/chess_queen_qlora_v2.py')['sha256'],
    previous_executed_protocol=prior,
    previous_failed_receipt=item('data/private/chess-queen-qlora-v1/diagnostic-1.json'),
    previous_closed_worker=item('data/private/chess-queen-qlora-v1/diagnostic-worker-1.json'),
    previous_executed_source=item('scripts/chess_queen_qlora_v1.py'),
    tokenizer_cpu_receipt=item('data/private/chess-queen-qlora-v1/tokenizer-cpu-v2.json'),
    amendment='Actual diagnostic1 completed base load/storage hash/LoRA injection, then stopped before any encoder/decoder forward, backward or update. TF5 apply_chat_template defaultBatchEncoding made unchanged official formatter return two string mapping keys. CPU-only actualtokenizer inspection confirmed this and verified the compatibility proxy forces return_dict=False without editing official formatter:141tokens/81prompt/60assistant+closing, correctEOS128012 and noCUDAinit. Ownprefix alsoexplicitFalse and alltokens must be integers. Additionally rawstorage hashing explicitly aliases as plainTensor before CPU chunks so Params4bit.cpu/to cannot move sharedquant_state. No input/target/loss/checkpoint/optimizer/quantization/resource method changed.')
plan['dependencies']=[item('tests/test_chess_queen_qlora_v2.py') if value['path']=='tests/test_chess_queen_qlora_v1.py' else value for value in plan['dependencies']]
plan['dependencies'].append(item('experiments/chess-queen-qlora-v1/inspect_tokenizer_cpu.py'))
plan['forward']['tokenizer_compatibility']='Official formatter receives an attribute-delegating proxy whose apply_chat_template forces return_dictFalse; actual inference-prefix call is explicitlyFalse. Integer-list/mask/EOS/context contracts checked against actualCPUtokenizer beforeCUDA.'
plan['storage_verification']+=' Plain torch.Tensor alias is created before anyCPUcopy; no Params4bit.cpu/to dispatch.'
with(HERE/'diagnostic-protocol-v2.json').open('x',encoding='utf-8')as stream:
    json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps({'source':plan['implementation_sha256'],
    'protocol':item('experiments/chess-queen-qlora-v1/diagnostic-protocol-v2.json')['sha256'],
    'tests':item('tests/test_chess_queen_qlora_v2.py')['sha256'],
    'actual_cpu_tokenizer':plan['tokenizer_cpu_receipt']['sha256']}))
