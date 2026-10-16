"""Bounded CPU-only owned-job probe; actual OS observations are never invented."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'scripts'))
from cold_eval_v6 import append, bound, digest, launch, no_torch, read, save
from job_context import JobContext
from process_lineage_v5 import Windows, ObservationError, normalized


def verify(plan):
    no_torch()
    if plan['implementation_sha256'] != digest(Path(__file__)): raise ValueError('CPU probe source differs')
    if plan['planned'] != 4 or plan['stale_attempts'] != 3 or plan['sampler_calls'] != 12:
        raise ValueError('Fixed software-probe denominators differ')
    if plan['maximum_seconds'] != 90 or plan['sampler_child_seconds'] != 30:
        raise ValueError('Frozen CPU-only probe budgets differ')
    for item in plan['dependencies']: bound(item)
    bound(plan['probe_child'])
    if normalized(shutil.which('nvidia-smi')) != normalized(bound(plan['resource_sampler_auxiliary']['executable'])):
        raise ValueError('Frozen resource-query executable differs')
    if plan['interpreters'] != {'launcher': normalized(sys.executable), 'delegate': normalized(sys._base_executable)}:
        raise ValueError('Actual venv/base interpreter differs')


def wait_owned(process, deadline, cancel, cutoff):
    while process.poll() is None:
        if cancel.exists() or time.monotonic() >= deadline or datetime.now(timezone.utc) >= cutoff:
            # Only the exact Popen child created here is a termination target.
            process.terminate(); process.wait(timeout=5)
            raise RuntimeError('Authored CPU child exceeded existing probe clock/cancel')
        time.sleep(.005)


def stale_case(context, folder, deadline, cancel, cutoff):
    """Capture a known authored child's snapshot before releasing its Popen handle."""
    if cancel.exists() or time.monotonic() >= deadline or datetime.now(timezone.utc) >= cutoff:
        raise RuntimeError('No authored child after probe clock/cancel')
    folder.mkdir(); ready = folder / 'ready'; release = folder / 'release'
    code = ('import sys,time;from pathlib import Path;'
        'Path(sys.argv[1]).write_text("ready");'
        '\nwhile not Path(sys.argv[2]).exists(): time.sleep(.005)')
    command = [sys.executable, '-c', code, str(ready), str(release)]
    process = subprocess.Popen(command, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    save(folder / 'intent.json', {'command': command, 'launcher_pid': process.pid, 'parent_pid': os.getpid(),
        'known_authored_creator': True, 'no_model_or_framework': True})
    record = {'status': 'started', 'pid': process.pid, 'parent_pid': os.getpid()}
    try:
        while not ready.exists():
            if process.poll() is not None: raise RuntimeError('Authored child exited before readiness')
            if time.monotonic() >= deadline or cancel.exists() or datetime.now(timezone.utc) >= cutoff:
                raise RuntimeError('Stale-case readiness exceeded owned clock/cancel')
            time.sleep(.005)
        parents = context.os.snapshot()
        if parents.get(process.pid) != os.getpid(): raise ValueError('Authored source snapshot lacks exact parent')
        record['captured_snapshot_parent_pid'] = parents[process.pid]
        release.touch(); wait_owned(process, deadline, cancel, cutoff)
        record['creator_popen_exit_code'] = process.returncode
        # Closing the creator handle is material: a retained process object can keep its PID openable.
        process._handle.Close()
        try:
            handle, observed = context.os.retain(process.pid, os.getpid())
        except ObservationError as error:
            record['open_observation'] = error.observation
            if error.observation.get('stage') == 'OpenProcess' and error.observation.get('open_process_winerror') == 87:
                record['absence'] = context.certify_absence(error.observation, context.records[context.outer],
                    context.handles[context.outer], lambda: max(0, min(1000, int((deadline-time.monotonic())*1000),
                        int((cutoff-datetime.now(timezone.utc)).total_seconds()*1000))) if not cancel.exists() else 0)
                record['exact_87_branch_measured'] = True
            else:
                raise
        else:
            try:
                if not context.os.exited(handle):
                    raise ValueError('Authored target still live or PID reused after creator closure')
                record.update(open_observation=observed, retained_handle_exited=context.os.exited(handle),
                    exact_87_branch_measured=False)
            finally: context.os.k.CloseHandle(handle)
        context.assert_baseline_only('after_authored_stale_case')
        record['status'] = 'completed'
    except BaseException as error:
        record.update(status='failed', error=type(error).__name__+': '+str(error)); raise
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)
        record['elapsed_deadline_remaining_seconds'] = deadline-time.monotonic()
        save(folder / 'closed.json', record)
    return record


def run(plan, protocol, out):
    if out.exists(): raise ValueError('CPU OS probe is create-only')
    out.mkdir(parents=True); started = time.monotonic(); deadline = started+90; context = None
    result = {'status': 'started', 'planned': 4, 'completed': 0, 'protocol_sha256': digest(protocol),
        'rows': [{'case_id': value, 'status': 'not_run'} for value in ['sampler12', 'stale0', 'stale1', 'stale2']]}
    save(out / 'closed.json', result); cancel = out / 'CANCEL'; cutoff = datetime.fromisoformat(plan['cutoff_utc'])
    try:
        verify(plan)
        if datetime.now(timezone.utc) >= cutoff: raise RuntimeError('CPU probe global cutoff')
        sources = out / 'executed-sources'; sources.mkdir(); manifest = []
        for index, path in enumerate([Path(protocol), Path(__file__), *[bound(item) for item in plan['dependencies']]]):
            target = sources / f'{index:02d}-{path.name}'; shutil.copyfile(path, target)
            manifest.append({'source': str(path), 'sha256': digest(target), 'copy': target.name})
        save(sources / 'manifest.json', manifest)
        context = JobContext(Windows(), audit=lambda value: append(out / 'job-events.jsonl', value))
        from chess_native_resources import windows_sample, reasons, Policy, GIB
        policy = Policy(start_physical_available_bytes=6*GIB, start_commit_headroom_bytes=10*GIB,
            start_gpu_free_bytes=10*GIB, stop_physical_available_bytes=4*GIB,
            stop_commit_headroom_bytes=4*GIB, stop_gpu_free_bytes=GIB)
        sample = windows_sample(); append(out / 'resources.jsonl', {'stage': 'start', **sample.__dict__})
        if reasons(sample, policy, 'start'): raise RuntimeError('Unchanged startup resource floors reject CPU probe')
        context.assert_baseline_only('after_startup_sampler')
        folder = out / 'sampler12'; folder.mkdir(); request = folder / 'request.json'; save(request, {'authored': True})
        result['rows'][0]['status'] = 'active_unknown'; save(out / 'closed.json', result)
        command = [sys.executable, str(bound(plan['probe_child'])), '--protocol', str(protocol.resolve()),
            '--request', str(request.resolve()), '--out', str((folder / 'child').resolve()), '--parent-cancel', str(cancel.resolve())]
        process = launch(command, folder, 30, cancel, cutoff, deadline, context)
        child = read(folder / 'child/closed.json')
        if (process['exit_code'] or child['status'] != 'passed' or child['completed_sampler_calls'] != 12
            or child['torch_imported'] or not process['child_exited_before_next_request']):
            raise ValueError('Exact sampler12 child did not close correctly')
        result['rows'][0].update(status='completed', process=process, child_sha256=digest(folder / 'child/closed.json'))
        result['completed'] += 1; save(out / 'closed.json', result)
        post = windows_sample(); append(out / 'resources.jsonl', {'stage': 'after_sampler12_exit', **post.__dict__})
        if reasons(post, policy, 'running'): raise RuntimeError('Unchanged running resource floors reject CPU probe')
        context.assert_baseline_only('after_postexit_sampler')
        for index in range(3):
            result['rows'][index+1]['status'] = 'active_unknown'; save(out / 'closed.json', result)
            value = stale_case(context, out / f'stale{index}', deadline, cancel, cutoff)
            result['rows'][index+1].update(status='completed', exact_87_branch_measured=value['exact_87_branch_measured'],
                result_sha256=digest(out / f'stale{index}/closed.json'))
            result['completed'] += 1; save(out / 'closed.json', result)
        result['exact_87_measurements'] = sum(row.get('exact_87_branch_measured', False) for row in result['rows'])
        result['status'] = 'passed' if result['exact_87_measurements'] else 'insufficient_exact_87_probe'
        result['no_repair_or_model_claim'] = True
    except BaseException as error:
        result.update(status='failed', error=type(error).__name__+': '+str(error)); raise
    finally:
        if context:
            try:
                result['final_baseline_only'] = context.assert_baseline_only('CPU_probe_finalization')
                result['job_context'] = context.describe()
            except BaseException as error:
                result.update(status='failed', closure_error=type(error).__name__+': '+str(error))
            finally: context.close()
        result.update(elapsed_seconds=time.monotonic()-started, torch_imported='torch' in sys.modules,
            model_calls=0, engine_calls=0, CUDA_initializations=0)
        save(out / 'closed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    result = run(read(args.protocol), args.protocol, args.out)
    raise SystemExit(0 if result['status'] == 'passed' else 2)
