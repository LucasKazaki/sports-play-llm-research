"""Closed failed train1 only. No tensor, model, engine or held-reference imports."""
import hashlib
import json
import math
from pathlib import Path
import random
import sys

REPO=Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
OUT=Path(__file__).parent
PRIVATE=REPO/'data/private/chess-queen-coach-sft-training-v1'
RUN=PRIVATE/'train-1'
sys.path.insert(0,str(REPO/'scripts'))
import chess_queen_coach_sft_train_v1 as trainer

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def lines(path):return [json.loads(line)for line in path.read_text(encoding='utf-8-sig').splitlines()if line]
plan_path=REPO/'experiments/chess-queen-coach-sft-training-v1/protocol.json'
plan=trainer.verify_protocol(plan_path)
state=read(RUN/'run.json');failure=read(RUN/'failure.json');worker=read(PRIVATE/'train-1-worker.json')
seals={str(p):sha(p)for p in RUN.rglob('*')if p.is_file()}
seals[str(PRIVATE/'train-1-worker.json')]=sha(PRIVATE/'train-1-worker.json')
assert state==failure and state['status']=='failed'
assert state['protocol_sha256']==sha(plan_path)
assert state['updates_planned']==256 and state['presentations_planned']==2048
assert state['updates_completed']==20 and state['presentations_completed']==160 and state['partial_accumulation']==0
assert worker['status']=='failed'and worker['exit_code']==1 and worker['child_exited_before_lease_release']is True
assert worker['script'].replace('\\','/')=='scripts/chess_queen_coach_sft_train_v1.py'
assert 'commit_headroom_bytes_below_reserve'in state['error']

train=trainer.read_rows(trainer.checked.nf4.binding(plan['data']['train']),True)
dev=trainer.read_rows(trainer.checked.nf4.binding(plan['data']['development']),True)
refs=trainer.references(trainer.checked.nf4.binding(plan['data']['development_references']),dev)
order=list(range(2048));random.Random(plan['training']['seed']).shuffle(order)
events=lines(RUN/'training-calls.jsonl');offset=0;losses=[]
for step in range(1,21):
    current=[]
    for micro in range(8):
        identity=train[order[(step-1)*8+micro]]['case_id']
        intent,done=events[offset:offset+2];offset+=2
        assert intent=={'step':step,'micro':micro,'case_id':identity,'status':'call_started'}
        assert done=={**intent,'status':'backward_completed','loss':done['loss']}
        assert math.isfinite(done['loss'])and done['loss']>0
        current.append(done['loss']);losses.append(done['loss'])
    intent,done=events[offset:offset+2];offset+=2
    assert intent=={'step':step,'status':'optimizer_started'}
    assert done=={'step':step,'status':'optimizer_completed','mean_loss':sum(current)/8}
remaining=events[offset:]
unknown={'step':21,'micro':0,'case_id':train[order[160]]['case_id'],'status':'call_started'}
assert remaining==[unknown]
assert len(losses)==160

nll_events=lines(RUN/'development-calls.jsonl')
condition=read(RUN/'development-0000.json')
assert state['conditions']==[condition]and condition['status']=='completed'
assert len(nll_events)==128 and condition['nll_completed']==64
weighted=0.;supervised=0
for index,row in enumerate(dev):
    intent,done=nll_events[2*index:2*index+2]
    assert intent=={'step':0,'case_id':row['case_id'],'status':'call_started'}
    recorded=condition['nll_rows'][index]
    assert recorded['case_id']==row['case_id']and recorded['status']=='completed'
    assert done=={'step':0,'case_id':row['case_id'],'status':'completed',
        'loss':recorded['loss'],'supervised_tokens':recorded['supervised_tokens']}
    assert math.isfinite(done['loss'])and done['supervised_tokens']>0
    weighted+=done['loss']*done['supervised_tokens'];supervised+=done['supervised_tokens']
assert supervised==4180==condition['nll_supervised_tokens']
assert weighted==condition['nll_weighted_sum']
assert weighted/supervised==condition['response_token_nll']

raw_rows=[row for row in dev if row['group_id']in plan['development_raw_groups']]
panel=read(RUN/'raw-development-0000.json')
assert panel['status']=='completed'and panel['planned']==len(panel['rows'])==8
identity=condition['identity']
assert panel['model_identity']==identity and identity['step']==identity['presentations']==0
assert sha(Path(identity['path']))==identity['sha256']
statuses={}
for row,item in zip(raw_rows,panel['rows']):
    assert row['case_id']==item['case_id']and item['status']in('completed','partial')
    response=Path(item['response_path']);assert sha(response)==item['response_sha256']
    raw=read(response);normalized,_=trainer.checked.nf4.base.input_packet(row['input'])
    assert raw['input']==normalized and raw['trained_adapter']==identity
    assert raw['candidate_id']=='queen-pawn-8/nf4-coach-sft-v1'
    assert raw['adapter_sha256']==trainer.checked.nf4.base.digest(REPO/'scripts/chess_queen_coach_sft_runtime_v1.py')
    assert raw['no_forward_input_audit']['passed']is True
    assert raw['no_forward_input_audit']['engine_evaluation_or_pv_input']is False
    for name in ('max_new_tokens','maximum_seconds','seed','generation_mode','precision_profile'):
        assert raw['settings'][name]==plan['generation'][name]
    assert raw['settings']['temperature'] == 0 and raw['settings']['use_kv_cache'] is False
    statuses[raw['status']]=statuses.get(raw['status'],0)+1
quality=trainer.score_panel(raw_rows,panel,refs)
assert quality==read(RUN/'development-score-0000.json')and quality['counts']==condition['counts']

future_raw=future_nll=0
for step in(64,128,256):
    pending=read(RUN/f'raw-development-{step:04d}.json')
    assert pending['planned']==len(pending['rows'])==8 and all(r['status']=='not_run'for r in pending['rows'])
    assert [r['case_id']for r in pending['rows']]==[r['case_id']for r in raw_rows]
    nll=read(RUN/f'development-{step:04d}.json')
    assert nll['status']=='not_run'and nll['nll_completed']==0 and len(nll['nll_rows'])==64
    assert all(r['status']=='not_run'for r in nll['nll_rows'])
    future_raw+=8;future_nll+=64
assert not (RUN/'selection.json').exists()
assert 'frozen_storage'not in state
assert {p.name for p in RUN.glob('checkpoint-*')}=={'checkpoint-0000'}
assert not list(PRIVATE.glob('heldout*'))
samples=read(RUN/'resources.json');journal=lines(RUN/'training.resources.jsonl')
assert samples==journal and samples
last=samples[-1]
headroom=last['commit_limit_bytes']-last['commit_total_bytes']
assert headroom==4013944832<4*1024**3
assert last['physical_available_bytes']>4*1024**3 and last['gpu_free_bytes']>1024**3
frozen=PRIVATE/'frozen-execution';snapshot=read(frozen/'manifest.json')
assert snapshot['training_protocol_sha256']==sha(plan_path)
for item in snapshot['files']:
    saved=frozen/item['snapshot'];original=Path(item['original'])
    assert sha(saved)==sha(original)==item['sha256']
    assert saved.stat().st_size==original.stat().st_size==item['bytes']
assert all(sha(Path(name))==value for name,value in seals.items())
assert not any(name in sys.modules for name in('torch','bitsandbytes','peft'))
result={'status':'passed_closed_failure_audit','actual_run_status':'failed','completed_optimizer_updates':20,
    'confirmed_backward_completions':160,'training_micro_attempts':161,'unknown_micro_attempt':unknown,
    'never_run_remaining_micros':2048-161,'last_saved_partial_accumulation':0,
    'baseline_development_nll_completed':64,'baseline_response_token_nll':weighted/supervised,
    'baseline_raw_requests':8,'baseline_raw_statuses':statuses,'baseline_counts':quality['counts'],
    'future_raw_not_run':future_raw,'future_nll_not_run':future_nll,
    'held_calls':0,'selection_exists':False,'final_frozen_storage_accepted':False,
    'saved_post_training_weights':False,'last_commit_headroom_bytes':headroom,
    'resource_samples':len(samples),'frozen_source_snapshots':len(snapshot['files']),
    'stable_files':len(seals),'run_sha256':sha(RUN/'run.json'),'worker_sha256':sha(PRIVATE/'train-1-worker.json'),
    'limits':'No evidence of model gain; no final frozen-storage verification, no selected checkpoint, no saved20-step weights. Unknown21st micro may have reached backward before its post-loss guard.',
    'new_model_calls':0,'new_engine_calls':0,'held_references_opened':False}
(OUT/'coaching-train1-failed-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
