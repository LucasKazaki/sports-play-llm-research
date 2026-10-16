"""Create-only interruption-safe finite-output repair; no model calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def item(path):
    return {'path': path, 'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


prior = item('experiments/chess-queen-nf4-v1/parity-protocol.json')
assert prior['sha256'] == 'a8f9154305482dd8b5d07d0d55dda53574a0702efbaa14341c5696ee7efbb882'
plan = json.loads((ROOT / prior['path']).read_text())
plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),
    implementation_sha256=item('experiments/chess-queen-nf4-v1/parity_no_cache.py')['sha256'],
    previous_unexecuted_protocol=prior,
    amendment='Before any pretrained call, independent review found that nonfinite logits could yield NaN metrics and prevent terminal JSON serialization. Each manual/native output now receives an immediate finite check before another forward; derived metrics must also serialize before appending. Failure flags stay JSON-safe. Exact numerical procedure, two prefixes, thresholds, model and resource reserves are unchanged.')
plan['dependencies'] = [item(binding['path']) for binding in plan['dependencies']]
with (HERE / 'parity-protocol-v2.json').open('x', encoding='utf-8') as stream:
    json.dump(plan, stream, indent=2, allow_nan=False); stream.write('\n')
print(json.dumps({'parity_source': plan['implementation_sha256'],
    'protocol': item('experiments/chess-queen-nf4-v1/parity-protocol-v2.json')['sha256'],
    'tests': plan['dependencies'][1]['sha256']}))
