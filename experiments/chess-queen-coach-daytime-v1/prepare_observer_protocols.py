"""Versioned metadata-only builders; actual OS/GPU dispatch belongs to root."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import cold_eval_v6 as cold

CHAT = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')
POLICY = {'unretained_error': 87, 'fresh_complete_observations': 2, 'separation_ms': 10,
    'maximum_observation_ms': 1000, 'classification': 'ABSENT_not_EXIT', 'baseline_only_after_sampler': True}
OLD_COLD_SHA = 'c7a74ccff15e7994178316fc2eb627a66a347e2446d54532add15b7a9330fd60'


def old_cold():
    path = HERE/'cold-qualification-protocol-v3.json'
    if cold.digest(path) != OLD_COLD_SHA: raise ValueError('Historical frozen daytime protocol changed')
    return path, cold.read(path)


def binding(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT/path
    return {'path': str(path), 'sha256': cold.digest(path)}


def create(path, value):
    path = Path(path)
    if path.exists(): raise ValueError('Prospective protocol is create-only')
    path.parent.mkdir(parents=True, exist_ok=True); cold.save(path, value)
    return binding(path)


def prepare_probe(out, actual_out):
    old_path, old = old_cold()
    names = ['job_context.py', 'process_lineage_v5.py', 'cold_eval_v6.py',
        'probe_process_observer.py', 'probe_observer_child.py', 'prepare_observer_protocols.py',
        'test_job_context.py', 'test_process_lineage_v5.py', 'test_cold_eval_v6.py', 'test_observer_probe.py']
    dependencies = [binding(HERE/name) for name in names]
    dependencies += [binding(ROOT/path) for path in ['scripts/chess_queen_process_lineage_v4.py',
        'scripts/chess_native_resources.py', 'experiments/chess-queen-v1/gpu_worker.py']]
    script = str((HERE/'probe_process_observer.py').relative_to(ROOT)).replace('\\', '/')
    arguments = [script, '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan = {'schema': 'chess.daytime.process-observer-CPU-probe.v1', 'mode': 'software_only',
        'implementation_sha256': cold.digest(HERE/'probe_process_observer.py'),
        'cold_outer_source': binding(HERE/'cold_eval_v6.py'), 'process_lineage_helper': binding(HERE/'process_lineage_v5.py'),
        'job_context_source': binding(HERE/'job_context.py'), 'job_context_policy': POLICY,
        'probe_child': binding(HERE/'probe_observer_child.py'), 'dependencies': dependencies,
        'resource_sampler_auxiliary': old['resource_sampler_auxiliary'], 'interpreters': old['interpreters'],
        'cutoff_utc': old['cutoff_utc'], 'maximum_seconds': 90, 'sampler_child_seconds': 30,
        'planned': 4, 'sampler_calls': 12, 'stale_attempts': 3,
        'daytime_authority': old['daytime_authority'], 'expected_worker_arguments': arguments,
        'source_design': binding(CHAT/'work/daytime/process-observer-recovery-proposal.json'),
        'prior_closed_failure_audit': binding(CHAT/'work/queen-review/daytime-cold-qualification-1-failure-closed-review.json'),
        'acceptance': 'All4 authored cases close,12 actual unchanged sampler calls, exact venv/direct topology and stable EXIT, no framework/model/engine/CUDA initialization, unchanged floors; at least1 actually measured OpenProcess87 with two complete fresh ABSENT observations. All3 predeclared stale attempts retained. No adaptive retry if zero87 or any failure. Query-only exact baseline must be the entire active immediate job before next/at closure.',
        'scope': 'Standard-library CPU/OS software only, root exclusive owned-job/lease. nvidia-smi is read-only counter transport, no model/GPU compute. New helper does not repair or explain the historical unknown PID. ABSENT is not EXIT/identity/termination authority.',
        'resources': old['resources'], 'no_new_dataset_or_reference_access': True}
    return create(out, plan)


def prepare_cold(out, actual_out, probe_protocol, probe, probe_worker, probe_audit):
    old_path, old = old_cold(); plan = copy.deepcopy(old)
    frozen = cold.read(probe_protocol)
    plan.update(implementation_sha256=cold.digest(HERE/'cold_eval_v6.py'),
        process_lineage_helper=binding(HERE/'process_lineage_v5.py'), job_context_source=binding(HERE/'job_context.py'),
        job_context_policy=POLICY, cpu_observer_protocol=binding(probe_protocol), cpu_observer_probe=binding(probe),
        cpu_observer_worker=binding(probe_worker), cpu_observer_audit=binding(probe_audit),
        preserved_failed_daytime_protocol=binding(old_path),
        prior_daytime_failure_audit=binding(CHAT/'work/queen-review/daytime-cold-qualification-1-failure-closed-review.json'))
    script = str((HERE/'cold_eval_v6.py').relative_to(ROOT)).replace('\\', '/')
    plan['expected_worker_script'] = script
    plan['expected_worker_arguments'] = [script, '--protocol', str(Path(out).resolve()), '--out', str(Path(actual_out).resolve())]
    plan['dependencies'] += frozen['dependencies'] + [binding(probe_protocol), binding(probe), binding(probe_worker), binding(probe_audit)]
    plan['lineage_contract'] = ('All prior exact direct/one-hop, hashed sampler and retained EXIT checks remain. '
        'Only OpenProcess87 under an already retained live actual runtime may become unretained ABSENT after two complete fresh system/job observations. '
        'No identity/EXIT/ancestry/termination authority for that PID; later PID/reuse/parent role fails phase-wide. '
        'Complete immediate job must equal unchanged query-handle-bound actual outer baseline after child exit and postexit sampler before every next request.')
    plan['transient_process_rule'] = ('Retained image-query Win5 EXIT-only bounded1000ms rule unchanged. '
        'New separate unretained OpenProcess87 rule is exactly job_context_policy, no live unknown admission. '
        'Original failing PID/cause remain unknown; software qualification is prospective, not a historical diagnosis.')
    # Same scientific inputs, runtime, settings, thresholds, dates and two-request software-only objective.
    cold.verify_observer_probe(plan)
    return create(out, plan)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['probe', 'cold'])
    parser.add_argument('--out', type=Path, required=True); parser.add_argument('--actual-out', type=Path, required=True)
    for name in ['probe-protocol', 'probe', 'probe-worker', 'probe-audit']: parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    if args.phase == 'probe': result = prepare_probe(args.out, args.actual_out)
    else:
        if not all([args.probe_protocol, args.probe, args.probe_worker, args.probe_audit]): parser.error('Actual closed probe/worker/audit required')
        result = prepare_cold(args.out, args.actual_out, args.probe_protocol, args.probe, args.probe_worker, args.probe_audit)
    print(json.dumps(result))
