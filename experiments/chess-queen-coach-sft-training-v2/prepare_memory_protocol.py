"""Freeze one fixed diagnostic before any v2 model calls; metadata only."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent


def item(name):
    return {'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}


old='data/private/chess-queen-coach-sft-training-v1/train-1'
plan={'schema':'chess.queen-coach-memory-protocol.v1','frozen_at':datetime.now(timezone.utc).isoformat(),
    'implementation_sha256':item('experiments/chess-queen-coach-sft-training-v2/memory_qualification_v1.py')['sha256'],
    'pilot_protocol':item('experiments/chess-queen-coach-sft-training-v1/protocol.json'),
    'previous_failure':item(old+'/failure.json'),'previous_closed_worker':item(old+'-worker.json'),
    'previous_journal':item(old+'/training-calls.jsonl'),
    'previous_spent_generation':item(old+'/raw-development-0000/006.json'),
    'qualification':{'spent_development_case_id':'queen-coach-v1:FrE6YlJF:free',
        'generation':'Exactly one already-spent dev input, original1024tokens/180s/greedy/no-cache/math. Must actually reach1024tokens, otherwise stop as insufficient stress.',
        'updates':32,'presentations':256,'maximum_seconds':900,
        'order':'First256 of original seed4082083 permutation over2048TRAINrecords; original8accumulation/optimizer/LR schedule throughstep32. Reuse declared; no held content.',
        'maximum_private_tail_span_bytes':512*1024**2,'maximum_cuda_tail_span_bytes':256*1024**2,
        'plateau':'Over last8completed optimizer boundaries, max-minus-min ownProcessPrivateUsage<=512MiB and CUDAallocated/reserved<=256MiB. Allresourceguards retain original4GiBcommit/physical and1GiBGPU stop floors.',
        'live_preservation':'At step1/micro7 andstep32/micro7, hashall144trainable tensors andtheir144gradients immediatelybefore/aftercleanup, requireexactequality.',
        'cleanup':'Only after load and returned generation/loss-backward and optimizer+zero_grad: synchronize, journalactualbefore, gc.collect, cuda.empty_cache, synchronize, journalactualafter, originalguard. No cleanup duringforward/backward or zeroingofliveaccumulatedgradients.',
        'acceptance':'Allfixedgeneration/update/presentationcallscomplete, allfinitegradients, completefrozenstoragehashidentical, LoRAhashchanged, bothlivepreservationchecksandtailplateau pass. Anyfailurehaltsremainingcalls. Discardadapter; no qualitymeasurement, checkpointselection or heldcalls.',
        'global_cutoff_utc':'2026-10-16T13:00:00+00:00'},
    'prior_provenance':'Original attempt20confirmedupdates/160confirmedbackwardpresentations; step21/micro0 callstarted withoutcompletion isactive_unknown. Nooptimizercheckpointafterstep0. Preserveallbytes andneverresumethisstate.',
    'scope':'A software memory experiment, not chess competence. Windowsglobalcommit includesotherprocesses; ownPrivateUsage andCUDAallocator counters distinguishmeasuredscopes. NoOSsettings/dependency/device/offload/reservechanges.',
    'dependencies':[item(name)for name in[
        'scripts/chess_queen_coach_sft_runtime_v2.py','tests/test_chess_queen_coach_sft_runtime_v2.py',
        'tests/test_chess_queen_coach_memory_qualification_v1.py',
        'scripts/chess_queen_coach_sft_train_v1.py','scripts/chess_queen_coach_sft_runtime_v1.py',
        old+'/training.resources.jsonl',old+'/run.json',old+'-worker.log',
        'experiments/chess-queen-v1/gpu_worker.py']]}
with(HERE/'memory-protocol.json').open('x',encoding='utf-8')as stream:
    json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
print(json.dumps(item('experiments/chess-queen-coach-sft-training-v2/memory-protocol.json')))
