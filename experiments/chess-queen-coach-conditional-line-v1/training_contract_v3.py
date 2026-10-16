"""Conditional-target science/data/qualification gates; no model or OS imports."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'experiments/chess-queen-coach-daytime-v1'
sys.path.insert(0,str(OLD))
import daytime_contract as original
import direct_launch_contract as launch
UPDATE_CHECKS=original.UPDATE_CHECKS
CUTOFF='2026-10-16T22:00:00+00:00'
ADMISSION='2026-10-16T18:30:00+00:00'
SAME=('training','generation','development_raw_groups','warm_start','successful_memory_qualification',
    'kernel_protocol','kernel_receipt','expected_formatter','expected_tokenizer_bindings','resources',
    'qualified_parent_protocol','cpu_environment_parity','owned_worker_source','interpreters','launch_profile')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bound(item):
    path=Path(item['path']);path=path if path.is_absolute()else ROOT/path
    if digest(path)!=item['sha256']:raise ValueError('Frozen bytes differ: '+str(path))
    return path

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def science(plan,parent):
    for key in SAME:
        if plan[key]!=parent[key]:raise ValueError('Unchanged numerical/backend science differs: '+key)
    if plan['phase_maximum_seconds']!={'training':3000,'heldout':4500}:raise ValueError('Full phase caps changed')
    if(plan['cutoff_utc']!=CUTOFF or plan['admission_latest_utc']!=ADMISSION
        or plan['worker_maximum_seconds']!=plan['maximum_seconds']+30
        or plan['external_maximum_seconds']!=plan['worker_maximum_seconds']+30):raise ValueError('Operating bounds changed')
    if plan['selection_method']!='Fixed terminal192; all DEV results monitoring only; no candidate choice from DEV or held quality.':raise ValueError('Fixed terminal192 policy required')
    if(plan['fixed_treatment_step']!=192 or plan['comparison_control']['step']!=192
        or plan['comparison_control']['candidate_id']!='queen-pawn-8/nf4-coach-counterfactual-v1'):
        raise ValueError('Fixed existing192 control and future terminal192 required')
    if plan['training']['updates']!=192 or plan['training']['gradient_accumulation']!=8:raise ValueError('Full192/1536 required')

def target_readiness(plan):
    manifest=read(bound(plan['corpus_manifest']));closed=read(bound(plan['target_export_closed']))
    export=read(bound(plan['target_export_protocol']));tokens=read(bound(plan['cpu_preflight']))
    token_plan=read(bound(plan['cpu_preflight_protocol']));audit=read(bound(plan['target_data_audit']))
    if(manifest.get('schema')!='chess.conditional-targets.v1'or manifest.get('status')!='ready_for_training'
        or manifest.get('model_inputs_changed')is not False or manifest.get('stored_PVs_changed')is not False
        or manifest.get('new_held_or_reserve_content_read')is not False
        or manifest.get('model_or_engine_calls')!=0 or manifest['protocol_sha256']!=plan['target_export_protocol']['sha256']
        or closed.get('status')!='completed'or closed.get('completed')!=1632 or closed.get('active_unknown')!=0
        or closed.get('not_run')!=0 or closed.get('manifest_sha256')!=plan['corpus_manifest']['sha256']):
        raise ValueError('Complete target-only export required')
    for item in export['dependencies']:bound(item)
    if manifest['parent_manifest']!=plan['parent_corpus_manifest']:raise ValueError('Wrong original input/group/PV source')
    if(tokens.get('status')!='passed'or tokens.get('planned')!=1632 or tokens.get('completed')!=1632
        or tokens.get('active_unknown')!=0 or tokens.get('not_run')!=0
        or tokens.get('manifest_sha256')!=plan['corpus_manifest']['sha256']
        or tokens.get('model_weights_loaded')is not False or tokens.get('learned_forward_calls')!=0
        or tokens.get('maximum_total_tokens')!=512 or tokens.get('cuda_initialized')is not False
        or tokens.get('exact_prefix_mask_eos_untruncated')is not True
        or tokens.get('official_formatter_sha256')!=plan['expected_formatter']['sha256']
        or tokens.get('tokenizer_bindings')!=plan['expected_tokenizer_bindings']):raise ValueError('Actual complete512 CPU token gate required')
    if(len(tokens.get('outcomes',[]))!=1632 or any(row.get('status')!='completed'for row in tokens['outcomes'])
        or len({row['case_id']for row in tokens['outcomes']})!=1632
        or sum(row.get('split')=='train'for row in tokens['outcomes'])!=1536
        or sum(row.get('split')=='development'for row in tokens['outcomes'])!=96):raise ValueError('Full unique1632 tokenizer outcomes required')
    if(token_plan['target_manifest']!=plan['corpus_manifest']or token_plan['target_export_protocol']!=plan['target_export_protocol']
        or token_plan['implementation_sha256']!=plan['cpu_preflight_source']['sha256']):raise ValueError('Actual new token source/protocol differs')
    for item in token_plan['dependencies']:bound(item)
    if(audit.get('status')!='passed'or audit.get('manifest_sha256')!=plan['corpus_manifest']['sha256']
        or audit.get('tokenizer_receipt_sha256')!=plan['cpu_preflight']['sha256']
        or audit.get('export_protocol_sha256')!=plan['target_export_protocol']['sha256']
        or audit.get('tokenizer_protocol_sha256')!=plan['cpu_preflight_protocol']['sha256']):raise ValueError('Independent actual target/token closure audit required')
    expected={'train':('train.jsonl',1536),'development':('development.jsonl',96),'development_references':('development-references.jsonl',96)}
    if set(plan['data'])!=set(expected):raise ValueError('TRAIN/DEV-only source whitelist required')
    for key,(name,count)in expected.items():
        if manifest['files'][name]!={'sha256':plan['data'][key]['sha256'],'rows':count}:raise ValueError('New target data/count binding differs')
        bound(plan['data'][key])
    if(manifest['splits']['train']['source_games']!=512 or manifest['splits']['development']['source_games']!=32):raise ValueError('Full512/32 source-game denominator differs')
    return manifest

def qualification_gate(plan):
    stage=plan['conditional_update_gate']
    protocol=read(bound(stage['protocol']));result=read(bound(stage['result']));worker=read(bound(stage['worker']));audit=read(bound(stage['audit']))
    original.worker(worker,stage['script'],stage['arguments']);launch.owned_worker(worker,plan['owned_worker_source'],plan['interpreters'])
    if(stage['arguments']!=protocol['expected_worker_arguments']or stage['script']!=protocol['expected_worker_script']
        or result.get('status')!='passed'or result.get('protocol_sha256')!=stage['protocol']['sha256']
        or audit.get('status')!='passed'or audit.get('protocol_sha256')!=stage['protocol']['sha256']
        or audit.get('qualification_sha256')!=stage['result']['sha256']or audit.get('worker_sha256')!=stage['worker']['sha256']
        or protocol['corpus_manifest']!=plan['corpus_manifest']or protocol['warm_start']!=plan['warm_start']
        or protocol['counterfactual_runtime']!=plan['counterfactual_runtime']
        or result.get('updates_completed')!=1 or result.get('presentations_completed')!=8
        or result.get('disposable_not_candidate')is not True or set(result.get('checks',{}))!=UPDATE_CHECKS
        or not all(value is True for value in result['checks'].values())):raise ValueError('Actual long-target disposable8/reload software audit required')

def failed_attempt_gate(plan):
    stage=plan['preserved_failed_training']
    audit=read(bound(stage['audit']));run=read(bound(stage['run']));worker=read(bound(stage['worker']))
    bound(stage['protocol'])
    if(audit.get('status')!='passed'or audit.get('protocol_sha256')!=stage['protocol']['sha256']
        or audit.get('run_sha256')!=stage['run']['sha256']or audit.get('worker_sha256')!=stage['worker']['sha256']
        or audit.get('no_training_or_optimizer_attempt')is not True
        or run.get('status')!='failed'or run.get('updates_completed')!=0 or run.get('presentations_completed')!=0
        or run.get('partial_accumulation')!=0 or run.get('inflight_training')is not None
        or run.get('inflight_optimizer')is not None or run.get('active_unknown')is not None
        or worker.get('child_exited_before_lease_release')is not True
        or worker.get('owned_job_exit_verified')is not True):raise ValueError('Exact closed no-learning failed attempt audit required')
    return run


def verify(path,phase):
    plan=read(path)
    script='train_v3.py'if phase=='training'else'qualify_conditional_v2.py'
    if(plan['schema']!='chess.conditional-training-protocol.v1'or plan['phase']!=phase
        or plan['implementation_sha256']!=digest(Path(__file__).with_name(script))):raise ValueError('Exact new phase source required')
    for item in plan['dependencies']:bound(item)
    parent=read(bound(plan['preserved_training_protocol']));science(plan,parent)
    parent_audit=read(bound(plan['preserved_training_closed_audit']))
    if(parent_audit.get('status')!='passed'or parent_audit.get('protocol_sha256')!=plan['preserved_training_protocol']['sha256']
        or parent_audit.get('selection_sha256')!=plan['preserved_selection']['sha256']
        or read(bound(plan['preserved_selection']))['selected']!=plan['comparison_control']):raise ValueError('Actual completed original192 source/audit required')
    authority=read(bound(plan['daytime_authority']))
    if(authority.get('human_text')!='Continue today until 6:00 PM Eastern'or authority.get('cutoff_utc')!=CUTOFF):raise ValueError('Actual daytime authority required')
    launch.environment(plan,bound,read)
    target_readiness(plan)
    from conditional_runtime import validate_start
    validate_start(plan['warm_start'])
    if phase=='training':
        if plan['maximum_seconds']!=3000:raise ValueError('Full3000 computation cap required')
        qualification_gate(plan)
        failed_attempt_gate(plan)
    elif(plan['maximum_seconds']!=600 or plan['planned_updates']!=1 or plan['planned_presentations']!=8
        or plan['disposable_not_candidate']is not True):raise ValueError('Exact disposable8 software plan required')
    return plan

def admit(plan,now=None):
    now=datetime.now(timezone.utc)if now is None else now
    if now>=datetime.fromisoformat(plan['admission_latest_utc']):raise RuntimeError('Conditional cycle admission closed at18:30UTC')
