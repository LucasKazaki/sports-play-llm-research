"""Prepare the unchanged full96 daytime comparison after actual training closes."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import daytime_contract as contract
import daytime_train as trainer
import cold_eval_v7 as outer
import direct_launch_contract as launch_contract


def bind(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT / path
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        'sha256': outer.digest(path)}


def check_training(completed, audit, worker, scientific, selection_sha, protocol_sha, worker_sha):
    if (completed.get('status') != 'completed' or completed.get('updates_completed') != 192
        or completed.get('presentations_completed') != 1536
        or completed.get('partial_accumulation') != 0 or completed.get('active_unknown') is not None
        or completed.get('inflight_training') is not None or completed.get('inflight_optimizer') is not None
        or completed.get('protocol_sha256') != protocol_sha
        or not completed.get('frozen_storage', {}).get('identical')):
        raise ValueError('Closed complete unchanged-base scientific training required')
    if (audit.get('status') != 'passed' or audit.get('protocol_sha256') != protocol_sha
        or audit.get('selection_sha256') != selection_sha or audit.get('worker_sha256') != worker_sha):
        raise ValueError('Independent actual training/selection/worker audit required')
    script = 'experiments/chess-queen-coach-daytime-v1/daytime_train.py'
    arguments = scientific['expected_worker_arguments']
    if arguments[0] != script or arguments[1] != 'train':
        raise ValueError('Wrong scientific training dispatch vector')
    contract.worker(worker, script, arguments)
    launch_contract.owned_worker(worker, scientific['owned_worker_source'], scientific['interpreters'])


def check_reservation(reservation, inputs, authority):
    if (reservation.get('schema') != 'chess.daytime.fresh-held-admission.v1'
        or reservation.get('status') != 'reserved_unspent'
        or reservation.get('model_requests_before_admission') != 0
        or reservation.get('reference_semantics_opened_for_quality') is not False
        or reservation.get('input_sha256') != inputs['sha256']
        or reservation.get('daytime_authority_sha256') != authority['sha256']
        or reservation.get('roots') != 16 or reservation.get('planned_raw_responses') != 96
        or reservation.get('all512_reserved_from_training') is not True):
        raise ValueError('Root-owned fresh daytime reservation attestation required')


def held_contract(plan, protocol_path):
    """Replace software-only advertised fields; preserve qualifying-worker proof."""
    path = Path(protocol_path).resolve()
    protocol_arg = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    script = 'experiments/chess-queen-coach-daytime-v1/cold_eval_v7.py'
    plan.update(expected_worker_script=script,
        expected_worker_arguments=[script, '--protocol', protocol_arg, '--out',
            'data/private/chess-queen-coach-daytime-v1/held-1'],
        profile='Actual counterfactual route:original64 warm baseline versus saved dev-selected192-update-run checkpoint;96 fresh planned responses.',
        selection='Saved development-only selection before any fresh response. Fixed16roots x3modes x2conditions=96responses; no response-based cohort or checkpoint choice.',
        acceptance='All96 planned raw responses retained with exact sources/inputs/adapters/settings, frozen storage, owned lineage and child EXIT. Both48 ledgers close before references open. Operational completion is not a coaching-quality threshold.',
        root_dispatch='One root-owned WHOLE96response lease/job with serial cold children; generator180/child210/phase4500/global22UTC and20:30UTC admission. No nested lease or new admission per child.',
        guard_limit='Policy120s remains metadata, not an enforced request timer. Actual generator180/child210/held4500/global22UTC; unchanged reserve floors.',
        failure_limit='One-update and two-request software qualifiers do not establish96-request stability. First operational failure halts all later calls, retaining96 full planned unknown/notrun outcomes; no retry or quota reduction.')
    return plan


def prepare(training_protocol, selection_path, training_worker, training_audit,
            fresh_admission, out):
    scientific = trainer.verify_protocol(training_protocol)
    selected = outer.read(selection_path)
    trainer.verify_selection(selected, training_protocol)
    run_path = Path(selection_path).parent / 'run.json'
    completed = outer.read(run_path)
    worker = outer.read(training_worker)
    audit = outer.read(training_audit)
    check_training(completed, audit, worker, scientific,
        outer.digest(selection_path), outer.digest(training_protocol), outer.digest(training_worker))
    reservation = outer.read(fresh_admission)
    check_reservation(reservation, scientific['data']['heldout_inputs'], scientific['daytime_authority'])
    stage = scientific['qualification_gates']['cold']
    qualification_plan = outer.read(outer.bound(stage['protocol']))
    outer.verify(qualification_plan)
    if any(qualification_plan['model_runtime'][key] != scientific[key]
           for key in ('kernel_protocol', 'kernel_receipt', 'generation', 'warm_start')):
        raise ValueError('Actual qualified runtime and scientific model differ')
    plan = dict(qualification_plan)
    names = [item['path'] for item in qualification_plan['dependencies'] + scientific['dependencies']]
    names += [str(Path(__file__)), str(Path(__file__).with_name('test_daytime_held_v4.py')),
        str(selection_path), str(run_path), str(training_protocol), str(training_worker),
        str(training_audit), str(fresh_admission)]
    plan.update(schema='chess.queen-coach-daytime-cold-held.v1', mode='heldout',
        frozen_at=datetime.now(timezone.utc).isoformat(),
        input_rows=scientific['data']['heldout_inputs'],
        heldout_references=scientific['data']['heldout_references'],
        conditions={key: selected[key] for key in ('baseline', 'selected')},
        planned=96, source_game_groups=16, reserved_source_games=512,
        phase_maximum_seconds=4500, worker_maximum_seconds=4530, external_maximum_seconds=4560,
        worker_cleanup_maximum_seconds=30, computation_budget_unchanged=True, admission_latest_utc=contract.HELD_ADMISSION,
        cutoff_utc=contract.CUTOFF,
        qualification_protocol=stage['protocol'], successful_qualification=stage['result'],
        closed_qualification_worker=stage['worker'], qualification_audit=stage['audit'],
        qualification_worker_script=stage['script'], qualification_worker_arguments=stage['arguments'],
        selected_training_protocol=bind(training_protocol), closed_training_worker=bind(training_worker),
        closed_training_audit=bind(training_audit), selected_before_held=bind(selection_path),
        daytime_fresh_admission=bind(fresh_admission),
        purpose='Fresh16source roots x FREE/two opaque suppliedmoves x warm64/selected =96 planned calls. No oldfailed-held retry or held-based selection.',
        admission='WHOLE96response outer phase before20:30UTC; all children continue underONElease/job. Generator180/child210/phase4500/global22 and unchanged floors apply. No reduced panel or late admission.',
        scope='Supplied first move is not prediction. Exact recognized immediate facts and conditional continuations only; no general coaching/Elo claim.',
        dependencies=[bind(path) for path in dict.fromkeys(names)])
    held_contract(plan, out)
    outer.verify(plan)
    if datetime.now(timezone.utc) >= datetime.fromisoformat(contract.HELD_ADMISSION):
        raise RuntimeError('Daytime whole-held admission closed')
    with Path(out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(plan, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return bind(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('training-protocol', 'selection', 'training-worker', 'training-audit', 'fresh-admission', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.training_protocol, args.selection, args.training_worker,
        args.training_audit, args.fresh_admission, args.out)))
