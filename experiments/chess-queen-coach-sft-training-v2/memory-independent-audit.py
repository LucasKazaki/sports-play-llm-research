"""Closed qualification audit: metadata/JSON only, no tensors or model calls."""
import importlib.util
import json
import hashlib
import math
from pathlib import Path
import random
import sys

REPO=Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
OUT=Path(__file__).parent
PRIVATE=REPO/'data/private/chess-queen-coach-sft-training-v2'
RUN=PRIVATE/'memory-qualification-1'
SOURCE=REPO/'experiments/chess-queen-coach-sft-training-v2/memory_qualification_v1.py'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def lines(path):return [json.loads(x)for x in path.read_text(encoding='utf-8-sig').splitlines()if x]
spec=importlib.util.spec_from_file_location('qualification',SOURCE)
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
plan,pilot=q.verify_plan(q.PROTOCOL)
seals={str(p):sha(p)for p in RUN.rglob('*')if p.is_file()}
worker_path=PRIVATE/'memory-qualification-1-worker.json';seals[str(worker_path)]=sha(worker_path)
state=read(RUN/'qualification.json');worker=read(worker_path)
assert state['status']=='passed'and state['protocol_sha256']==sha(q.PROTOCOL)
assert state['updates_completed']==state['planned_updates']==32
assert state['presentations_completed']==state['planned_presentations']==256 and state['partial_accumulation']==0
assert worker['status']=='completed'and worker['exit_code']==0 and worker['child_exited_before_lease_release']is True
assert worker['script'].replace('\\','/')=='experiments/chess-queen-coach-sft-training-v2/memory_qualification_v1.py'
assert worker['elapsed_seconds']<=plan['qualification']['maximum_seconds']+30
train=q.prior.read_rows(q.checked.nf4.binding(pilot['data']['train']),True)
dev=q.prior.read_rows(q.checked.nf4.binding(pilot['data']['development']),True)
order=list(range(2048));random.Random(pilot['training']['seed']).shuffle(order)
assert len(state['rows'])==256 and len(state['optimizer_rows'])==32
events=lines(RUN/'calls.jsonl');offset=0
for step in range(1,33):
    for micro in range(8):
        position=(step-1)*8+micro;expected=train[order[position]]['case_id']
        start,done=events[offset:offset+2];offset+=2
        row=state['rows'][position]
        assert row['step']==step and row['micro']==micro and row['case_id']==expected
        assert row['status']=='backward_completed'and math.isfinite(row['loss'])and row['loss']>0
        assert start['step']==step and start['micro']==micro and start['case_id']==expected and start['status']=='call_started'
        assert done==row
    start,done=events[offset:offset+2];offset+=2
    assert start=={'step':step,'status':'call_started'}
    assert done==state['optimizer_rows'][step-1]and done['status']=='completed'
assert offset==len(events)==576
raw=read(RUN/'spent-development-raw.json')
spent=[row for row in dev if row['case_id']==plan['qualification']['spent_development_case_id']]
assert len(spent)==1
packet,_=q.checked.nf4.base.input_packet(spent[0]['input'])
assert raw['input']==packet and set(packet)=={'fen','history'}and packet['history']==[]
assert raw['settings']['generation_mode']=='no_cache'and raw['settings']['precision_profile']=='math_sdpa_fp32_reduction'
assert raw['settings']['max_new_tokens']==len(raw['generated_tokens'])==1024
assert raw['settings']['maximum_seconds'] == 180 and raw['status'] == 'partial' and raw['finish_reason'] == 'token_limit'
assert state['generation']['status']==raw['status']and state['generation']['generated_tokens']==1024
assert state['generation']['receipt_sha256']==sha(RUN/'spent-development-raw.json')
assert raw['trained_adapter']['step']==0 and raw['trained_adapter']['parameter_sha256']==state['adapter_before']
for key in('adapter_before','adapter_after'):
    assert state[key]['tensor_count']==144 and state[key]['bytes_hashed']==7667712
assert state['adapter_before']['sha256']!=state['adapter_after']['sha256']
frozen=state['frozen_storage'];assert frozen['identical']is True and frozen['before']==frozen['after']
assert frozen['before']['tensor_count']==2268 and frozen['before']['bytes_hashed']==3393484936
assert [(x['step'],x['micro'])for x in state['preservation']]==[(1,7),(32,7)]
for item in state['preservation']:
    assert item['before']==item['after']and item['before']['gradient_tensors']==144
    for name in('parameters','gradients'):
        assert item['before'][name]['tensor_count']==144 and item['before'][name]['bytes_hashed']==7667712
boundaries=read(RUN/'update-memory.json');assert len(boundaries)==32
memory=lines(RUN/'memory-lifetime.jsonl');assert len(memory)==580
phases=['after_model_load','after_spent_full_prefix_generation']
for step in range(1,33):
    phases.extend(f'after_returned_backward_step{step}_micro{micro}'for micro in range(8))
    phases.append(f'after_optimizer_step{step}')
for index,phase in enumerate(phases):
    start,done=memory[2*index:2*index+2]
    assert start['phase']==done['phase']==phase
    assert start['status']=='cleanup_started'and done['status']=='cleanup_completed'
    assert start['before']==done['before']
    assert done['after']['process']['available']is True
    if phase.startswith('after_optimizer_step'):
        step=int(phase.removeprefix('after_optimizer_step'))
        assert done['after']==boundaries[step-1]
checks=q.qualification_checks(state,boundaries,plan)
assert checks == state['checks'] and len(checks) == 12 and all(checks.values())
tail=boundaries[-8:]
private_span=max(x['process']['private_usage_bytes']for x in tail)-min(x['process']['private_usage_bytes']for x in tail)
allocated_span=max(x['cuda_allocated_bytes']for x in tail)-min(x['cuda_allocated_bytes']for x in tail)
reserved_span=max(x['cuda_reserved_bytes']for x in tail)-min(x['cuda_reserved_bytes']for x in tail)
resources=read(RUN/'resources.json');assert resources==lines(RUN/'memory-qualification.resources.jsonl')
assert all(x['physical_available_bytes']>=4*1024**3 and x['gpu_free_bytes']>=1024**3 and x['commit_limit_bytes']-x['commit_total_bytes']>=4*1024**3 for x in resources)
assert not any(p.suffix=='.pt'for p in RUN.iterdir())and not (RUN/'selection.json').exists()
assert all(sha(Path(name))==value for name,value in seals.items())
assert not any(name in sys.modules for name in('torch','peft','bitsandbytes'))
result={'status':'passed_closed_file_audit','qualification_status':'passed','checks_recomputed':12,
    'updates':32,'confirmed_backward_presentations':256,'calls_journal_events':576,
    'stress_generated_tokens':1024,'stress_finish':'partial/token_limit','cleanup_pairs':290,
    'live_preservation_boundaries':2,'live_parameters_and_gradients_each':144,
    'frozen_tensors':2268,'frozen_bytes':3393484936,'frozen_hash_unchanged':True,'adapter_hash_changed':True,
    'process_private_tail_span_bytes':private_span,'cuda_allocated_tail_span_bytes':allocated_span,
    'cuda_reserved_tail_span_bytes':reserved_span,'resource_samples':len(resources),
    'minimum_commit_headroom_bytes':min(x['commit_limit_bytes']-x['commit_total_bytes']for x in resources),
    'worker_elapsed_seconds':worker['elapsed_seconds'],'stable_files':len(seals),
    'receipt_sha256':sha(RUN/'qualification.json'),'worker_sha256':sha(worker_path),
    'new_model_calls':0,'new_engine_calls':0,'held_references_opened':False,
    'limit':'Combined operational qualification, not causal proof of cache repair or a guarantee for256updates. Hashes are execution receipts; no saved qualification checkpoint was rehashed. Adapter discarded, no chess-quality result.'}
(OUT/'memory-qualification-completed-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
