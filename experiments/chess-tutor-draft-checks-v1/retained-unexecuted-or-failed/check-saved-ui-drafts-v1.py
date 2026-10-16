"""Derived CPU checks of three already-spent authored UI receipts; no new calls."""
import builtins
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

CHAT = Path(__file__).resolve().parents[1]
REPO = Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
DEST = CHAT/'work/tutor-draft-checks-saved-receipts-v1'
QA = CHAT/'outputs/chess-tutor-queen-browser-qa.json'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def bound(item):
    raw = Path(item['path']).read_bytes()
    assert len(raw) == item['bytes'] and sha(raw) == item['sha256']
    return raw

old_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'transformers', 'bitsandbytes'} or name == 'chess.engine':
        raise AssertionError('Unexpected heavy/backend import: '+name)
    return old_import(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, str(REPO/'prototype/chess_tutor_v1'))
from draft_checks_v1 import audit_bytes, original_profile
from queen_runtime import QueenRunner

qa = load(QA)
runner = QueenRunner(REPO)  # Metadata/hash verification only; never command().
DEST.mkdir(exist_ok=False)
rows = []
for item in qa['requests']:
    response_bytes = bound(item['response'])
    worker_bytes = bound(item['closed_worker'])
    response, worker = json.loads(response_bytes), json.loads(worker_bytes)
    input_path = Path(item['response']['path']).with_name('input.json')
    input_bytes = input_path.read_bytes()
    # Expected hash is in the ORIGINAL response, already bound by the closed QA
    # ledger. Never use a newly serialized response.input as substitute bytes.
    expected_input = response['input_sha256']
    assert sha(input_bytes) == expected_input
    packet = json.loads(input_bytes)
    assert packet == response['input']
    context = {'fen': packet['fen'], 'selected_uci': packet.get('selected_uci')}
    view = runner.decorate_result({'input': input_path}, response)
    qualified = original_profile(view, worker, False, runner.qualification_path.name)
    checked = audit_bytes(response_bytes, input_bytes, expected_input, packet,
                          context, response, qualified=qualified)
    checked['request_id'] = item['request_id']
    destination = DEST/(item['request_id']+'.json')
    destination.write_text(json.dumps(checked, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    assert input_path.read_bytes() == input_bytes
    assert Path(item['response']['path']).read_bytes() == response_bytes
    assert Path(item['closed_worker']['path']).read_bytes() == worker_bytes
    rows.append({'request_id': item['request_id'], 'original_response_sha256': sha(response_bytes),
                 'original_input_sha256': expected_input, 'original_worker_sha256': sha(worker_bytes),
                 'original_profile_qualified': qualified, 'status': checked['status'],
                 'claims_matched': len(checked['claims']),
                 'whole_prose_assessed': checked['whole_prose_assessed'],
                 'derived_receipt_sha256': sha(destination.read_bytes())})
assert len(rows) == 3 and sum(r['original_profile_qualified'] for r in rows) == 2
assert all(r['claims_matched'] == 0 and r['whole_prose_assessed'] is False for r in rows)
assert all(name not in sys.modules for name in ('torch', 'transformers', 'bitsandbytes', 'chess.engine'))
result = {'schema': 'chess.tutor-draft-saved-compatibility.v1', 'status': 'passed',
          'executed_at_utc': datetime.now(timezone.utc).isoformat(),
          'source_sha256': sha(Path(__file__).read_bytes()), 'original_qa_sha256': sha(QA.read_bytes()),
          'new_model_calls': 0, 'new_engine_calls': 0, 'new_gpu_calls': 0,
          'original_files_unchanged': True, 'rows': rows,
          'limit': 'Processing/schema compatibility on already-spent authored UI responses only. '
                   'Two completed drafts match zero canonical prose statements; other prose remains unassessed. '
                   'The cancelled response remains unassessed. No accuracy, coaching-quality or tuned-profile qualification.'}
(DEST/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, indent=2))
