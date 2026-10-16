"""Create finite complete-source review artifacts; metadata only, no launch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE/'owned-worker-v2-evidence'


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(path, data):
    with path.open('xb') as handle: handle.write(data)


def run():
    OUT.mkdir(exist_ok=False)
    sources = [HERE/name for name in ('owned_worker_v2.py', 'environment_parity_child_v1.py',
        'environment_parity_v1.py', 'prepare_environment_parity_v1.py', 'test_owned_worker_v2.py',
        'direct-base-worker-v2-README.md', 'environment-parity-protocol-v1.json', 'build_worker_v2_review_v1.py')]
    result = {'scope': 'Authored CPU fake-process tests, metadata lookup and byte hashes only.',
        'actual_original_candidate_dispatch': False, 'actual_OS_job_calls': False, 'model_calls': 0,
        'engine_calls': 0, 'framework_imports': 0,
        'runs': [{'tool_chunk_id': 'dc0cde', 'passed': 23, 'seconds': .17},
            {'tool_chunk_id': '138bfd', 'passed': 28, 'seconds': .21},
            {'tool_chunk_id': '3a3133', 'passed': 32, 'seconds': .22}],
        'final_command': '.venv-soccernet/Scripts/python.exe -m pytest experiments/chess-queen-coach-daytime-v1/test_owned_worker_v2.py -q',
        'final_exact_output': '................................                                         [100%]\n32 passed in 0.22s\n',
        'final_sources': [binding(path) for path in sources],
        'limit': 'No actual CPU parity or ownership qualification; root dispatch and independent actual review remain required.'}
    write(OUT/'authored-test-result.json', json.dumps(result, indent=2).encode())
    groups = [('01-worker-and-payload.txt', sources[:2]),
        ('02-driver-builder-and-design.txt', sources[2:4]+[sources[5]]),
        ('03-tests-and-retained-result.txt', [sources[4], OUT/'authored-test-result.json']),
        ('04-protocol-and-review-builder.txt', sources[6:])]
    bundles = []
    for name, paths in groups:
        data = b''
        for path in paths:
            raw = path.read_bytes(); header = json.dumps(binding(path), sort_keys=True).encode()
            data += b'\n===== COMPLETE FILE '+header+b' =====\n'+raw+b'\n===== END COMPLETE FILE =====\n'
        if len(data) >= 30000: raise ValueError('Review bundle exceeds finite bound')
        write(OUT/name, data); bundles.append(binding(OUT/name))
    manifest = {'source_files': [binding(path) for path in sources], 'result': binding(OUT/'authored-test-result.json'),
        'bundles': bundles, 'status': 'source_review_candidate_only'}
    write(OUT/'manifest.json', json.dumps(manifest, indent=2).encode())
    print(json.dumps({'manifest': binding(OUT/'manifest.json'), 'bundles': bundles}))


if __name__ == '__main__': run()
