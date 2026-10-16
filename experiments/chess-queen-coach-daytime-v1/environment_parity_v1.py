"""One original and one direct-base CPU metadata launch; root dispatch only."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import owned_worker_v2 as candidate


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())
def save(path, value): Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')


def verify(plan, protocol):
    if plan['schema'] != 'chess.environment-parity-plan.v1' or plan['launch_profile'] != candidate.PROFILE:
        raise ValueError('Wrong CPU parity profile')
    if (plan['planned'] != ['original', 'candidate'] or plan['worker_maximum_seconds'] != 15
        or plan['model_calls'] != 0 or plan['engine_calls'] != 0): raise ValueError('Parity scope/budget differs')
    if not 1 <= plan['maximum_seconds'] <= 90: raise ValueError('Parity outer budget differs')
    for item in plan['dependencies']:
        if digest(item['path']) != item['sha256']: raise ValueError('Bound dependency changed: '+item['path'])
    if digest(__file__) != plan['driver_sha256'] or digest(candidate.__file__) != plan['worker_source_sha256']:
        raise ValueError('Parity implementation differs')
    if any(name.split('.')[0] in {'torch', 'transformers', 'bitsandbytes', 'peft', 'chess'} for name in sys.modules):
        raise RuntimeError('Parity driver must remain framework-free')


def compare(original, changed):
    for row in (original, changed):
        if (row['status'] != 'completed' or row['model_calls'] != 0 or row['engine_calls'] != 0
            or row['forbidden_framework_modules_imported'] != []): raise ValueError('Unsafe/incomplete metadata payload')
    if original['source_sha256'] != changed['source_sha256']: raise ValueError('Payload source differs')
    if original['environment'] != changed['environment']: raise ValueError('Exact Python environment parity failed')
    return {'exact_environment_equal': True, 'compared_fields': sorted(original['environment']),
        'allowed_differences': ['topology', 'sys_orig_argv executable', 'output argument path']}


def candidate_gate(worker, child):
    proof = worker['ownership']['before_go']; closure = worker['ownership']['closure']
    if (worker['status'] != 'completed' or worker['exit_code'] != 0
        or worker['schema'] != 'chess.owned-worker.v2' or worker['launch_profile'] != candidate.PROFILE
        or worker['source_sha256'] != digest(candidate.__file__)
        or not worker['owned_member_before_go'] or not worker['owned_job_exit_verified']
        or not worker['child_exited_before_lease_release']
        or not proof['popen_handle_pid_matches'] or not proof['member_of_explicit_creator_job']
        or proof['creator_member_of_explicit_child_job'] or proof['job_handle_passed_to_child']
        or proof['complete_job_pids'] != [worker['child_pid']]
        or proof['child_identity'] != child['topology']['actual_process']
        or child['topology']['parent_pid'] != proof['creator_identity']['pid']
        or child['topology']['immediate_current_job_pids'] != [worker['child_pid']]
        or closure['complete_job_pids'] != [] or not closure['child_stable_handle_exited']
        or not closure['actual_job_handle_closed']): raise ValueError('Direct interpreter ownership/exit proof differs')


def run(plan, protocol, out):
    out = Path(out)
    if out.resolve() != Path(plan['output']).resolve(): raise ValueError('Output differs from frozen plan')
    out.mkdir(parents=True, exist_ok=False); started = time.monotonic()
    result = {'schema': 'chess.environment-parity.v1', 'status': 'started', 'launch_profile': candidate.PROFILE,
        'worker_source_sha256': digest(candidate.__file__), 'protocol_sha256': digest(protocol),
        'planned': 2, 'completed': 0, 'model_calls': 0, 'engine_calls': 0,
        'rows': [{'condition': name, 'status': 'not_run'} for name in ('original', 'candidate')]}
    save(out/'closed.json', result)
    try:
        verify(plan, protocol); original = candidate.pinned_original()
        payload = Path(plan['child_source']['path'])
        if digest(payload) != plan['child_source']['sha256']: raise ValueError('Payload source differs')
        for row, implementation in zip(result['rows'], (original, candidate)):
            if (datetime.now(timezone.utc) >= datetime.fromisoformat(plan['cutoff_utc'])
                or time.monotonic()-started >= plan['maximum_seconds']): raise RuntimeError('CPU parity admission cutoff')
            folder = out/row['condition']; folder.mkdir()
            arguments = [str(payload.relative_to(ROOT)), '--out', str(folder/'child.json')]
            expected = plan['requests'][row['condition']]
            if arguments != expected['arguments'] or hashlib.sha256(json.dumps(arguments).encode()).hexdigest() != expected['arguments_sha256']:
                raise ValueError('Frozen full worker argument vector differs')
            save(folder/'intent.json', {'arguments': arguments,
                'arguments_sha256': hashlib.sha256(json.dumps(arguments).encode()).hexdigest(),
                'model_calls': 0, 'engine_calls': 0})
            row['status'] = 'active_unknown'; save(out/'closed.json', result)
            receipt = implementation.run_worker(arguments, folder/'worker.json', 15)
            if receipt['status'] != 'completed' or receipt['exit_code'] != 0 or not receipt['child_exited_before_lease_release']:
                raise RuntimeError('CPU metadata worker failed')
            child = read(folder/'child.json')
            if child['source_sha256'] != plan['child_source']['sha256']: raise ValueError('Actual child source differs')
            expected_orig = [str(candidate.ORIGINAL), '--bootstrap-script', str(payload), '--', *arguments[1:]]
            if child['topology']['sys_orig_argv'][1:] != expected_orig:
                raise ValueError('Actual bootstrap argument suffix differs')
            if row['condition'] == 'candidate': candidate_gate(receipt, child)
            row.update(status='completed', worker_sha256=digest(folder/'worker.json'), child_sha256=digest(folder/'child.json'))
            result['completed'] += 1; save(out/'closed.json', result)
        result['comparison'] = compare(read(out/'original/child.json'), read(out/'candidate/child.json'))
        result.update(status='passed', worker_sha256=digest(out/'candidate/worker.json'),
            candidate_worker_sha256=digest(out/'candidate/worker.json'),
            original_worker_sha256=digest(out/'original/worker.json'))
    except BaseException as error:
        result.update(status='failed', error=type(error).__name__+': '+str(error)); raise
    finally:
        for row in result['rows']:
            worker_path = out/row['condition']/'worker.json'
            if worker_path.exists():
                row['worker_sha256'] = digest(worker_path)
                receipt = read(worker_path); row['worker_status'] = receipt.get('status')
                row['child_exited_before_lease_release'] = receipt.get('child_exited_before_lease_release')
                if row['status'] == 'active_unknown' and receipt.get('status') in ('failed', 'deadline', 'busy', 'completed'):
                    row['status'] = 'failed'  # The parity request failed even if a child exited zero.
        result['elapsed_seconds'] = time.monotonic()-started
        result['limit'] = 'Authored CPU environment/ownership observation only; no model or scientific qualification.'
        save(out/'closed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args(); run(read(args.protocol), args.protocol, args.out)
