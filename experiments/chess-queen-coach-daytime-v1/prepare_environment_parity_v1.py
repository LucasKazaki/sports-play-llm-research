"""Create-only metadata plan builder. Does not launch a child or import a model."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
CHAT = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')


def bound(path):
    path = Path(path).resolve(); return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def build(output, cutoff):
    sources = [HERE/name for name in ('owned_worker_v2.py', 'environment_parity_child_v1.py',
        'environment_parity_v1.py', 'prepare_environment_parity_v1.py', 'test_owned_worker_v2.py')]
    fixed = [ROOT/'experiments/chess-queen-v1/gpu_worker.py', ROOT/'.venv-soccernet/Scripts/python.exe',
        Path('C:/Users/lucas/AppData/Local/Programs/Python/Python312/python.exe'), ROOT/'.venv-soccernet/pyvenv.cfg',
        CHAT/'work/daytime/direct-base-launch-proposal.json',
        CHAT/'work/queen-review/daytime-owned-job-diagnostic-1-closed-review.json']
    requests = {}
    for condition in ('original', 'candidate'):
        arguments = [str((HERE/'environment_parity_child_v1.py').relative_to(ROOT)), '--out',
            str((Path(output)/condition/'child.json').resolve())]
        requests[condition] = {'arguments': arguments,
            'arguments_sha256': hashlib.sha256(json.dumps(arguments).encode()).hexdigest()}
    return {'schema': 'chess.environment-parity-plan.v1', 'launch_profile': 'direct-base-owned-worker-v2',
        'driver_sha256': bound(HERE/'environment_parity_v1.py')['sha256'],
        'worker_source_sha256': bound(HERE/'owned_worker_v2.py')['sha256'],
        'child_source': bound(HERE/'environment_parity_child_v1.py'),
        'dependencies': [bound(path) for path in sources+fixed], 'output': str(Path(output).resolve()),
        'cutoff_utc': cutoff, 'maximum_seconds': 90, 'worker_maximum_seconds': 15,
        'requests': requests,
        'planned': ['original', 'candidate'], 'model_calls': 0, 'engine_calls': 0,
        'dispatch': 'Root only after complete source/protocol independent review; one attempt, no replay.',
        'scientific_sources_changed': False, 'resources_changed': False,
        'pass_requires': ['exact environment equality, including ordered sys.path/flags/package version and locations',
            'actual direct base handle matches Popen PID/image/creation before unchanged GO',
            'explicit creator-held owned-job membership and complete sole-member list beforeGO',
            'candidate child NULL-job sole interpreter and exact parent identity',
            'complete owned job empty and stable child EXIT before lease release'],
        'later_gate': 'CPU parity alone cannot admit model calls. New reviewed warm/cold qualification remains mandatory.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--private-out', type=Path, required=True); parser.add_argument('--cutoff-utc', required=True)
    args = parser.parse_args(); plan = build(args.private_out, args.cutoff_utc)
    with args.out.open('x', encoding='utf-8') as handle: json.dump(plan, handle, indent=2)
