"""Prospective direct-base plans require real closed CPU/software evidence."""
import argparse
import copy
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import cold_eval_v7 as cold
import direct_launch_contract as launch
import prepare_observer_protocols as preserved


bind = preserved.binding
def worker_grace(plan):
    """Preserve old CLI's30s wrapper grace without extending computation clocks."""
    phase = plan.get('maximum_seconds')
    if type(phase) is not int:
        phase = plan.get('phase_maximum_seconds')
        if isinstance(phase, dict):
            if phase != {'training': 3000, 'heldout': 4500}:
                raise ValueError('Scientific phase dictionary differs')
            phase = phase['training']
    if type(phase) is not int or phase not in (90, 450, 600, 3000, 4500):
        raise ValueError('Unknown unchanged computation phase budget')
    plan.update(worker_maximum_seconds=phase+30, worker_cleanup_maximum_seconds=30,
        external_maximum_seconds=phase+60, computation_budget_unchanged=True,
        wrapper_limit='Worker phase+30 preserves prior CLI effective wrapper grace. Cleanup separately bounded30; external worker+30. All computation clocks and22UTC cutoff remain unchanged.')
    return plan


def create(out, plan):
    return preserved.create(out, worker_grace(plan))


def environment_stage(protocol, result, worker, audit):
    return {name: bind(path) for name, path in [('protocol', protocol), ('result', result), ('worker', worker), ('audit', audit)]}


def launch_fields(stage):
    return {'launch_profile': launch.PROFILE, 'owned_worker_source': bind(HERE/'owned_worker_v2.py'),
        'cpu_environment_parity': stage}


def dependencies(previous=()):
    names = ['job_context_direct_v1.py', 'direct_launch_contract.py', 'cold_eval_v7.py',
        'probe_process_observer_v2.py', 'qualify_training_direct_v1.py', 'prepare_held_v4.py',
        'prepare_direct_protocols_v3.py', 'owned_worker_v2.py', 'test_job_context_direct_v1.py',
        'test_direct_launch_contract.py', 'test_qualify_training_direct_v1.py', 'test_direct_observer.py',
        'test_prepare_direct_protocols_v3.py', 'test_daytime_held_v4.py']
    paths = [item['path'] for item in previous]+[str(HERE/name) for name in names]
    return [bind(path) for path in dict.fromkeys(paths)]


def prepare_probe(out, actual_out, stage):
    old_path = HERE/'observer-cpu-protocol-v1.json'; plan = copy.deepcopy(cold.read(old_path))
    plan.update(implementation_sha256=cold.digest(HERE/'probe_process_observer_v2.py'),
        cold_outer_source=bind(HERE/'cold_eval_v7.py'), job_context_source=bind(HERE/'job_context_direct_v1.py'),
        **launch_fields(stage))
    launch.environment(plan, cold.bound, cold.read)
    plan['preserved_failed_CPU_protocol'] = bind(old_path)
    script = str((HERE/'probe_process_observer_v2.py').relative_to(ROOT)).replace('\\', '/')
    plan['expected_worker_arguments'] = [script, '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan['dependencies'] = dependencies(plan['dependencies'])+list(stage.values())
    plan['scope'] = ('Same4 authored CPU cases/12unchanged counter queries/3controlled stale attempts; no model/framework/engine/held access. '
        'New measured exact direct-base/venv-getpath environment and parent-only actual creator-job ownership; oldfailedcontext/cause remains historical. '
        'A missing87 branch stays insufficient; no extension/replacement. Root uses owned_worker_v2, not a nested worker.')
    return create(out, plan)


def prepare_cold(out, actual_out, probe_protocol, probe, worker, audit):
    _, old = preserved.old_cold(); plan = copy.deepcopy(old)
    frozen = cold.read(probe_protocol)
    plan.update(implementation_sha256=cold.digest(HERE/'cold_eval_v7.py'),
        job_context_source=bind(HERE/'job_context_direct_v1.py'),
        process_lineage_helper=frozen['process_lineage_helper'], job_context_policy=frozen['job_context_policy'],
        cpu_observer_protocol=bind(probe_protocol), cpu_observer_probe=bind(probe),
        cpu_observer_worker=bind(worker), cpu_observer_audit=bind(audit),
        **{key: frozen[key] for key in ['launch_profile', 'owned_worker_source', 'cpu_environment_parity']})
    launch.environment(plan, cold.bound, cold.read)
    cold.verify_observer_probe(plan)
    script = str((HERE/'cold_eval_v7.py').relative_to(ROOT)).replace('\\', '/')
    plan['expected_worker_script'] = script
    plan['expected_worker_arguments'] = [script, '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan['dependencies'] = dependencies(plan['dependencies'])+frozen['dependencies']+[bind(path) for path in [probe_protocol, probe, worker, audit]]
    plan['lineage_contract'] = ('Direct actual base outer with exactly measured venv getpath, retained base creator outside its child current job, '
        'parent-held explicit creator-job proof beforeGO/empty-job EXIT closure from pinned worker. No child-held job handle. '
        'Existing exact cold launcher/delegate/query and retained EXIT checks remain; phase-wide unretained87ABSENT is never identity/EXIT/kill authority.')
    plan['transient_process_rule'] = ('Existing retained image-query Win5/at-most1000ms EXIT-only observation remains. '
        'Separate positive-PID OpenProcess87 under an already retained live runtime may become ABSENT only after two complete fresh system/current-job observations. '
        'No identity/EXIT/ancestry/termination authority for unretained entries; any later PID/reuse/parent role fails phase-wide. Live or ambiguous unknowns fail.')
    plan['guard_limit'] = 'Policy120s is metadata only; actual unchanged generator180/child210/qualification450/global22UTC and same reserve floors.'
    plan['prospective_operational_change'] = 'New actual-qualified direct-base process topology only. Same2spentDEV/current-only inputs/fixedoriginal64/raw unmasked generation and all scientific limits. No training or quality criterion in this condition.'
    return create(out, plan)


def prepare_warm(out, actual_out, cold_protocol):
    plan = copy.deepcopy(cold.read(HERE/'warm-qualification-protocol-v3.json'))
    gate = cold.read(cold_protocol)
    launch.environment(gate, cold.bound, cold.read); cold.verify_observer_probe(gate)
    plan.update(implementation_sha256=cold.digest(HERE/'qualify_training_direct_v1.py'),
        cpu_observer_gate_protocol=bind(cold_protocol),
        **{key: gate[key] for key in ['launch_profile', 'owned_worker_source', 'cpu_environment_parity', 'interpreters']})
    script = str((HERE/'qualify_training_direct_v1.py').relative_to(ROOT)).replace('\\', '/')
    plan['expected_worker_script'] = script
    plan['expected_worker_arguments'] = [script, '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan['dependencies'] = dependencies(plan['dependencies'])+gate['dependencies']+[bind(cold_protocol)]
    plan['prospective_operational_change'] = 'Same fixedoriginal64/seeded8TRAINmicros/one disposable planned optimizer update/save/reload; newactual-qualified direct-base worker only. All training/numeric functions ASTidentical; no candidate weights reused.'
    return create(out, plan)


def freeze_training(gates, out, actual_out):
    import build_protocols as old_builder
    import daytime_train as trainer
    plan = old_builder.final_training(gates)
    qplan = cold.read(cold.bound(gates['cold']['protocol']))
    launch.environment(qplan, cold.bound, cold.read)
    for gate in gates.values():
        launch.owned_worker(cold.read(cold.bound(gate['worker'])), qplan['owned_worker_source'], qplan['interpreters'])
    plan.update(**{key: qplan[key] for key in ['launch_profile', 'owned_worker_source', 'cpu_environment_parity', 'interpreters']})
    script = 'experiments/chess-queen-coach-daytime-v1/daytime_train.py'
    plan['expected_worker_script'] = script
    plan['expected_worker_arguments'] = [script, 'train', '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan['dependencies'] = dependencies(plan['dependencies'])+qplan['dependencies']
    receipt = create(out, plan)
    trainer.verify_protocol(out)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['probe', 'cold', 'warm', 'training'])
    parser.add_argument('--out', type=Path, required=True); parser.add_argument('--actual-out', type=Path, required=True)
    for name in ['parity-protocol', 'parity-result', 'parity-worker', 'parity-audit', 'probe-protocol', 'probe',
        'probe-worker', 'probe-audit', 'cold-protocol', 'gates']: parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    if args.phase == 'probe':
        values = [args.parity_protocol, args.parity_result, args.parity_worker, args.parity_audit]
        if not all(values): parser.error('Actual closed CPU environment parity/worker/audit required')
        result = prepare_probe(args.out, args.actual_out, environment_stage(*values))
    elif args.phase == 'cold':
        values = [args.probe_protocol, args.probe, args.probe_worker, args.probe_audit]
        if not all(values): parser.error('Actual closed four-case CPU probe/worker/audit required')
        result = prepare_cold(args.out, args.actual_out, *values)
    elif args.phase == 'warm':
        if not args.cold_protocol: parser.error('Actual CPU observer-bound cold protocol required')
        result = prepare_warm(args.out, args.actual_out, args.cold_protocol)
    else:
        if not args.gates: parser.error('Actual closed warm/cold software audits required')
        result = freeze_training(cold.read(args.gates), args.out, args.actual_out)
    print(json.dumps(result))
