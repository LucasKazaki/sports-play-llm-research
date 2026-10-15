"""One create-only native CUDA child, sampled reserves and exact-handle stop."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from chess_fact_sft_common import read, save, sha, declare_run, finalize_run_ledger
from chess_native_resources import windows_sample, Policy, reasons


def termination_due(cancelled_at, now):
    return cancelled_at is not None and now - cancelled_at >= 30.


def phase_deadline(start, phase, now):
    if phase.get('phase') == 'holdout':
        began = phase.get('started_monotonic')
        if not isinstance(began, (int, float)) or not start <= began <= now:
            return ['invalid_holdout_clock']
        if began - start > 3600 or now - began >= 1800 or now - start >= 5400:
            return ['owned_phase_deadline']
    elif now - start >= 3600:
        return ['owned_training_dev_deadline']
    return []


def run(repo, cohort, protocol, out):
    repo, cohort, protocol, out = (Path(item).resolve() for item in (repo, cohort, protocol, out))
    if out.exists():
        raise ValueError('create-only job; no replay')
    # The fixed experiment assets/model are confined to this checkout's private area.
    cohort.relative_to(repo / 'data/private/chess-fact-sft-v1')
    out.relative_to(repo / 'data/private/chess-fact-sft-v1')
    if read(protocol)['status'] != 'FROZEN_BEFORE_COHORT_SELECTION_IMPLEMENTATION_AND_PRETRAINED_FORWARD':
        raise ValueError('frozen protocol required')
    out.mkdir(parents=True)
    declare_run(out, [r['case_id'] for r in read(cohort/'dev-inputs.json')['rows']],
        [r['case_id'] for r in read(cohort/'holdout-inputs.json')['rows']])
    finalize_run_ledger(out)  # Durable all-not-run denominator before any preflight failure.
    records = []
    policy = Policy(maximum_owned_request_seconds=5400.)
    frozen_digest = sha(cohort / 'frozen-data.json')
    for name, digest in read(cohort / 'frozen-data.json')['files_sha256'].items():
        target = (cohort / name).resolve()
        target.relative_to(cohort)
        if sha(target) != digest:
            raise ValueError('frozen cohort artifact changed: ' + name)
    # No model loading here; this monitor does not import torch/transformers.
    with urlopen('http://127.0.0.1:11434/api/ps', timeout=5) as response:
        import json
        if json.load(response).get('models') != []:
            raise ValueError('Ollama must have no resident model')
    foreign = subprocess.run(['powershell', '-NoProfile', '-Command',
        "@(Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue).Count"],
        check=True, capture_output=True, text=True, timeout=10)
    if foreign.stdout.strip() != '0':
        raise ValueError('foreign llama-server present')
    for _ in range(10):
        sample = windows_sample()
        records.append(asdict(sample))
        issues = reasons(sample, policy, 'start')
        if issues:
            save(out / 'preflight.json', {'status': 'rejected', 'issues': issues, 'samples': records})
            raise RuntimeError('resource preflight failed: ' + repr(issues))
        time.sleep(1.)
    save(out / 'preflight.json', {'status': 'passed', 'samples': records})
    command = [sys.executable, str(repo / 'scripts/chess_fact_sft_train.py'), '--repo', str(repo),
        '--cohort', str(cohort), '--protocol', str(protocol), '--out', str(out)]
    sources = {}
    snapshots = out / 'executed-sources'
    snapshots.mkdir()
    import shutil
    for path in [*repo.glob('scripts/chess_fact_sft_*.py'), repo/'scripts/chess_native_resources.py',
                 repo/'scripts/chess_board_fact_core.py', protocol]:
        target = snapshots / path.name
        shutil.copyfile(path, target)
        sources[path.relative_to(repo).as_posix()] = sha(path)
    start = last_sample = time.monotonic()
    cancelled_at, issues, samples = None, [], 0
    finalization_error = None
    with (out / 'worker.stdout.txt').open('wb') as stdout, (out / 'worker.stderr.txt').open('wb') as stderr, \
         (out / 'resources.jsonl').open('w', encoding='utf-8', buffering=1) as log:
        child = subprocess.Popen(command, cwd=repo, stdout=stdout, stderr=stderr)
        forced = False
        try:
            save(out / 'ownership.json', {'pid': child.pid, 'command': command, 'source_sha256': sources,
                'started_monotonic': start, 'policy': asdict(policy), 'cohort_frozen_sha256': frozen_digest})
            while child.poll() is None:
                now = time.monotonic()
                current_issues = []
                try:
                    sample = windows_sample()
                    sample.validate()
                    import json
                    log.write(json.dumps({'monotonic': now, **asdict(sample)}) + '\n')
                    samples += 1
                    current_issues.extend(reasons(sample, policy, 'running'))
                    if now - last_sample > 3.:
                        current_issues.append('monitor_sample_gap')
                    last_sample = now
                except Exception as error:
                    current_issues.append('sample_failure:' + type(error).__name__)
                phase = read(out / 'phase.json') if (out / 'phase.json').exists() else {}
                current_issues.extend(phase_deadline(start, phase, now))
                if current_issues and cancelled_at is None:
                    issues = current_issues
                    cancelled_at = now
                    save(out / 'cancel.json', {'issues': issues, 'monotonic': now})
                if termination_due(cancelled_at, now):
                    child.terminate()  # Exact Popen-owned Windows process handle only.
                    forced = True
                    child.wait(timeout=10)
                    break
                time.sleep(1.)
        except BaseException:
            if child.poll() is None:
                try:
                    save(out / 'cancel.json', {'issues': ['supervisor_exception'], 'monotonic': time.monotonic()})
                except Exception:
                    pass  # Owned-process cleanup must never depend on a writable disk.
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    forced = True
                    child.wait(timeout=10)
            raise
        finally:
            try:
                finalize_run_ledger(out)
                save(out / 'supervision.json', {'pid': child.pid, 'exit_code': child.poll(),
                    'forced_owned_termination': forced, 'cancel_issues': issues, 'sample_count': samples,
                    'elapsed_seconds': time.monotonic() - start, 'sources_sha256': sources})
            except Exception as error:
                finalization_error = type(error).__name__ + ':' + str(error)
                print('Final local artifact unavailable: '+type(error).__name__, file=sys.stderr)
    if finalization_error:
        raise RuntimeError('owned child ended but final artifacts unavailable: '+finalization_error)
    if child.returncode or issues:
        raise RuntimeError('owned experiment failed; retain artifacts and do not replay')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for item in ('repo', 'cohort', 'protocol', 'out'):
        parser.add_argument('--' + item, required=True)
    run(**vars(parser.parse_args()))
