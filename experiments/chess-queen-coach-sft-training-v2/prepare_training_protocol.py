"""Freeze fresh full pilot only after the actual closed memory qualification."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_train_v2 as pilot


def item(name):
    return {'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}


def prepare(receipt,worker,destination):
    prior_path='experiments/chess-queen-coach-sft-training-v1/protocol.json'
    plan=json.loads((ROOT/prior_path).read_text())
    actual=json.loads((ROOT/receipt).read_text());closed=json.loads((ROOT/worker).read_text())
    if actual.get('status')!='passed'or not actual.get('checks')or not all(actual['checks'].values()):
        raise ValueError('Actual fixed memory qualification did not pass')
    if closed.get('status')!='completed'or closed.get('exit_code')!=0 or not closed.get('child_exited_before_lease_release'):
        raise ValueError('Actual qualification worker is not closed successfully')
    plan.update(schema='chess.queen-coach-sft-training-protocol.v2',frozen_at=datetime.now(timezone.utc).isoformat(),
        implementation_sha256=item('scripts/chess_queen_coach_sft_train_v2.py')['sha256'],
        prior_protocol=item(prior_path),successful_memory_qualification=item(receipt),closed_memory_worker=item(worker),
        memory_protocol=item('experiments/chess-queen-coach-sft-training-v2/memory-protocol.json'),
        memory_implementation=item('experiments/chess-queen-coach-sft-training-v2/memory_qualification_v1.py'),
        restart='Fresh publisher/NF4 base and exactoriginalseededzero-BLoRA/freshAdamW; no resume of failed20confirmedupdates/160confirmedpresentations+oneunknownmicro or discarded32qualificationupdates.',
        memory_lifetime='After each returned generation/NLL/loss-backward call has been retained, synchronize/gc.collect/empty_cache/synchronize withactualprocessPrivateUsage/CUDAallocated-reserved journal; after optimizer+zero_grad likewise. No objective/weight/gradient/mask/numerical-kernel change. Loss AST identical tooriginal.',
        operational_condition='Root retired only the owned idle model worker and restarted UI server with no model loaded before this condition; preserve original global memory failure. No unrelated process/OS/resourcefloor change.',
        repeated_train_development='Explicitly reuse sameTRAIN/dev after failed attempt and software qualification. Original8rawdev outcomes and qualification1spentdev outcome remain visible; samefixedselector, no held calls or references opened.',
        monitoring='Full256 stability is not established by32update software qualification; retain unchangedcooperativefloors andstopfirstfailure throughout. No automatic UIpromotion.')
    replaced={'scripts/chess_queen_coach_sft_runtime_v1.py':'scripts/chess_queen_coach_sft_runtime_v2.py',
        'tests/test_chess_queen_coach_sft_runtime_v1.py':'tests/test_chess_queen_coach_sft_runtime_v2.py',
        'tests/test_chess_queen_coach_sft_train_v1.py':'tests/test_chess_queen_coach_sft_train_v2.py'}
    plan['dependencies']=[item(replaced.get(binding['path'],binding['path']))for binding in plan['dependencies']]
    plan['dependencies'] += [item(name)for name in[
        'scripts/chess_queen_coach_sft_train_v1.py','scripts/chess_queen_coach_sft_runtime_v1.py',
        'data/private/chess-queen-coach-sft-training-v1/train-1/failure.json',
        'data/private/chess-queen-coach-sft-training-v1/train-1/training-calls.jsonl',
        'data/private/chess-queen-coach-sft-training-v1/train-1-worker.json']]
    target=ROOT/destination
    with target.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    pilot.verify_protocol(target)
    return item(destination)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',required=True);parser.add_argument('--worker',required=True)
    parser.add_argument('--out',default='experiments/chess-queen-coach-sft-training-v2/protocol.json')
    args=parser.parse_args();print(json.dumps(prepare(args.receipt,args.worker,args.out)))
