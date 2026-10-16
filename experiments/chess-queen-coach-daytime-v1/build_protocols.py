"""Freeze prospective daytime software plans; final TRAIN requires actual gates."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import daytime_contract as contract
import chess_queen_coach_counterfactual_cold_eval_v5 as outer

DIRECTORY = Path(__file__).resolve().parent
AUTHORITY = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look/work/daytime/resume-authority.json')
OLD_TRAIN = ROOT / 'experiments/chess-queen-coach-counterfactual-v1/training-protocol-v2.json'
OLD_COLD = ROOT / 'experiments/chess-queen-coach-counterfactual-v1/cold-sft-qualification-protocol-v6.json'
DAY_OUT = 'data/private/chess-queen-coach-daytime-v1'


def bind(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT / path
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        'sha256': outer.digest(path)}


def write(path, plan):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(plan, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return bind(path)


def common():
    old = outer.read(OLD_TRAIN)
    plan = copy.deepcopy(old)
    plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),
        schema='chess.queen-coach-daytime-training-protocol.v1',
        daytime_authority=bind(AUTHORITY), preserved_overnight_protocol=bind(OLD_TRAIN),
        admission_latest_utc=contract.TRAIN_ADMISSION,
        held_admission_latest_utc=contract.HELD_ADMISSION, cutoff_utc=contract.CUTOFF,
        counterfactual_runtime=bind('scripts/chess_queen_coach_counterfactual_runtime_v1.py'),
        operating_amendment=bind(AUTHORITY),
        admission='New dated user window only:TRAIN19:00UTC/wholeHELD20:30UTC/global22UTC. Full original scientific phases and all floors remain unchanged.',
        authorized_entrypoints={
            'training': 'experiments/chess-queen-coach-daytime-v1/daytime_train.py train after both actual audited software gates',
            'heldout': 'ONLY unchanged cold_eval_v5 with a separately frozen exact daytime held plan after closed training/audit; embedded trainer.heldout remains unauthorized'},
        historical_limit='Old overnight UNRUN/failure records and closeout are unchanged; no expired protocol is replayed.',
        coverage_limit='Targeted check contrast only:4 FREE TRAIN king targets,0 selected/allDEV king targets; all544 TRAIN/DEV roots outsidecheck. No broad coaching gate.')
    names = [item['path'] for item in old['dependencies']]
    names += [str(DIRECTORY / name) for name in ('daytime_contract.py', 'daytime_train.py',
        'qualify_training.py', 'build_protocols.py', 'test_daytime.py')]
    names += [str(AUTHORITY), str(OLD_TRAIN)]
    plan['dependencies'] = [bind(name) for name in dict.fromkeys(names)]
    contract.windows(plan, outer.bound, outer.read)
    contract.science(plan, old)
    return plan


def initial():
    warm = common()
    warm.update(schema='chess.queen-coach-daytime-warm-qualification.v1',
        implementation_sha256=bind(DIRECTORY / 'qualify_training.py')['sha256'],
        maximum_seconds=600, planned_updates=1, planned_presentations=8,
        disposable_not_candidate=True,
        fixed_rows='First8 from the existing seeded1536 TRAIN permutation; no selection or generated-quality threshold.',
        acceptance='Exact original64 effective144FP32 values;8finite loss/8backwards, one first-schedule AdamW update, finite nonzero gradients, changed adapter,2268 frozen tensors unchanged, strict disposable save/reload equal. Disposable adapter never becomes candidate or scientific warmstart.',
        expected_worker_arguments=[
            'experiments/chess-queen-coach-daytime-v1/qualify_training.py', '--protocol',
            'experiments/chess-queen-coach-daytime-v1/warm-qualification-protocol-v3.json',
            '--out', DAY_OUT + '/warm-qualification-1'])
    warm['expected_worker_script'] = warm['expected_worker_arguments'][0]
    cold = outer.read(OLD_COLD)
    cold = copy.deepcopy(cold)
    cold.update(frozen_at=datetime.now(timezone.utc).isoformat(),
        schema='chess.queen-coach-daytime-cold-qualification.v1',
        daytime_authority=bind(AUTHORITY), preserved_overnight_cold_protocol=bind(OLD_COLD),
        profile='Counterfactual wrapper29 over unchanged qualified runtime7f; fixed original64 software only, no newly trained counterfactual weights.',
        cutoff_utc=contract.CUTOFF, admission_latest_utc=contract.HELD_ADMISSION,
        guard_limit='Policy120s remains metadata, not an enforced request timer. Actual unchanged generator180/child210/qualification450/global22UTC; same reserve floors.',
        exit_observation_rule='Same reviewed bounded1000ms EXIT-only observation; child/phase/new22UTC clocks keep running. No live unknown admission, identity or termination.',
        root_dispatch='One root-owned lease/job; sequential cold children only. This new protocol does not edit or replay any old result.',
        inherited_error_wording='Unchanged resource/child sources may say13UTC in error text; actual datetime is the bound22UTC field.',
        child_script=bind('scripts/chess_queen_coach_counterfactual_cold_child_v1.py'),
        expected_worker_arguments=[
            'scripts/chess_queen_coach_counterfactual_cold_eval_v5.py', '--protocol',
            'experiments/chess-queen-coach-daytime-v1/cold-qualification-protocol-v3.json',
            '--out', DAY_OUT + '/cold-qualification-1'])
    cold['child_implementation_sha256'] = cold['child_script']['sha256']
    cold['raw_provenance'].update(schema='chess.queen-coach-counterfactual-output.v1',
        candidate_id='queen-pawn-8/nf4-coach-counterfactual-v1',
        adapter_sha256=warm['counterfactual_runtime']['sha256'],
        qualified_runtime_source_sha256='7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349')
    cold['raw_provenance']['warm_start.sha256'] = warm['warm_start']['sha256']
    names = [item['path'] for item in cold['dependencies']]
    names += [str(AUTHORITY), str(OLD_COLD), cold['child_script']['path'],
        warm['counterfactual_runtime']['path'], str(Path(__file__)), str(DIRECTORY / 'test_daytime.py')]
    cold['dependencies'] = [bind(name) for name in dict.fromkeys(names)]
    outer.verify(cold)
    return warm, cold


def final_training(gates):
    plan = common()
    plan['implementation_sha256'] = bind(DIRECTORY / 'daytime_train.py')['sha256']
    plan['qualification_gates'] = gates
    for stage in gates.values():
        plan['dependencies'] += [stage[name] for name in ('protocol', 'result', 'worker', 'audit')]
    contract.qualifications(plan, outer.bound, outer.read)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['initial', 'training'])
    parser.add_argument('--gates', type=Path)
    args = parser.parse_args()
    if args.mode == 'initial':
        warm, cold = initial()
        print(json.dumps({'warm': write(DIRECTORY / 'warm-qualification-protocol-v3.json', warm),
            'cold': write(DIRECTORY / 'cold-qualification-protocol-v3.json', cold), 'model_calls': 0}))
    else:
        if args.gates is None:
            raise ValueError('Actual closed gate bindings required')
        print(json.dumps(write(DIRECTORY / 'training-protocol.json', final_training(outer.read(args.gates)))))
