"""Freeze one bounded authored integration request; never dispatch a model."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

CHAT = Path(__file__).resolve().parents[1]
REPO = Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
sys.path.insert(0, str(REPO/'scripts'))
from chess_native_resources import windows_sample
from filelock import FileLock

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
review = CHAT/'work/queen-review/tutor-draft-checks-v1-source-review.json'
assert sha(review) == '85e0dff0eaf0bb8586bb8d86760abe802783991437da6344fa9f02d50d679790'
verdict = json.loads(review.read_bytes())
for row in verdict['exact_current_sources'] + verdict['verified_unchanged_boundary_files']:
    path = Path(row['path'])
    assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
with FileLock(str(REPO/'data/private/chess-gpu-owner.lock'), timeout=0): pass
host = windows_sample().__dict__
assert host['physical_available_bytes'] >= 6*1024**3
assert host['commit_limit_bytes']-host['commit_total_bytes'] >= 10*1024**3
smi = shutil.which('nvidia-smi')
assert smi
query = subprocess.run([smi, '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                       check=True, capture_output=True, text=True, timeout=15)
free_mib = int(query.stdout.strip())
assert free_mib*1024**2 >= 10*1024**3
now = datetime.now(timezone.utc)
assert now < datetime.fromisoformat('2026-10-16T12:20:00+00:00')
record = {
    'schema':'chess.tutor-draft-checks-authored-integration-plan.v1',
    'status':'root_authorized_one_authored_request_not_yet_dispatched',
    'frozen_at_utc':now.isoformat(),
    'source_review_sha256':sha(review),
    'source_manifest_sha256':sha(CHAT/'work/tutor-draft-checks-design-v1/source-review/manifest.json'),
    'planned_requests':1,
    'position_fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',
    'mode':'This position; no selected move, engine score or continuation supplied',
    'profile':'Original qualified manual Queen NF4 no_cache; trained profile disabled',
    'reason':'Actual new-controller input-byte retention and post-worker checker integration remain unverified; strict older-receipt compatibility failed before checker call and is retained unchanged.',
    'admission_latest_utc':'2026-10-16T12:20:00+00:00',
    'global_cutoff_utc':'2026-10-16T13:00:00+00:00',
    'worker_maximum_seconds':240,
    'controller_limit_seconds':285,
    'stop_floors_bytes':{'physical_available':4*1024**3,'commit_headroom':4*1024**3,'gpu_free':1024**3},
    'starting_host_sample':host,'starting_gpu_free_MiB':free_mib,
    'lease_free_probe':True,'root_sole_GPU_dispatcher':True,
    'no_concurrent_heavy_CPU':True,'no_retry_or_output_repair':True,
    'save':'Original input/response/worker bytes, separate create-only draft-checks-v1.json, current and stale exports, browser screenshot and closed integration receipt.',
    'acceptance':'Software integration only. Exact saved input/response hashes and qualified worker closure must bind separate verification; ordinary prose may match zero statements. No quality, learned improvement, new data, cache repair or tuned UI admission.',
    'already_spent_authored_position':True,'fresh_held_data':False,
}
destination=CHAT/'work/overnight/draft-checks-authored-ui-smoke-plan-v1.json'
with destination.open('x',encoding='utf-8') as stream: json.dump(record,stream,indent=2)
print(json.dumps(record,indent=2))
