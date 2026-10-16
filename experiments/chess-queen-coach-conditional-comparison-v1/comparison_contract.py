"""Pure fixed-condition/actual-training metadata gates; no model or OS calls."""
from pathlib import Path
import hashlib,json,math
FIELDS=('model_runtime','raw_provenance','child_script','child_implementation_sha256',
    'owned_worker_source','interpreters','launch_profile','cpu_environment_parity')
ORIGINAL='queen-pawn-8/nf4-coach-counterfactual-v1'
TREATMENT='queen-pawn-8/nf4-coach-conditional-line-v1'
METHOD='Fixed terminal192; all DEV results monitoring only; no candidate choice from DEV or held quality.'

def require(value,message):
    if not value:raise ValueError(message)

ROOT=Path(__file__).resolve().parents[2]

def same_file(left,right,bound):
    # Descriptor identity only here: grader reference contents stay closed until all96 raw return.
    def resolved(value):
        path=Path(value['path']);return(path if path.is_absolute()else ROOT/path).resolve()
    return left['sha256']==right['sha256']and resolved(left)==resolved(right)

def verify_science(science,bound,read):
    require(science.get('schema')=='chess.conditional-comparison-science.v1','Wrong fixed comparison science')
    parent=read(bound(science['preserved_shared_science']))
    for key in FIELDS:require(science[key]==parent[key],'Shared inference source/numerics changed: '+key)
    train=read(bound(science['conditional_training_protocol']));run=read(bound(science['conditional_training_run']))
    selection=read(bound(science['conditional_selection']));audit=read(bound(science['conditional_training_audit']))
    worker=read(bound(science['conditional_training_worker']))
    require(audit.get('status')=='passed'and audit.get('protocol_sha256')==science['conditional_training_protocol']['sha256']
        and audit.get('run_sha256')==science['conditional_training_run']['sha256']
        and audit.get('selection_sha256')==science['conditional_selection']['sha256']
        and audit.get('worker_sha256')==science['conditional_training_worker']['sha256'],'Actual closed conditional TRAIN audit required')
    require(run.get('status')=='completed'and run.get('updates_completed')==192 and run.get('presentations_completed')==1536
        and run.get('partial_accumulation')==0 and run.get('active_unknown')is None
        and run.get('frozen_storage',{}).get('identical')is True
        and run.get('protocol_sha256')==science['conditional_training_protocol']['sha256'],'Full unchanged TRAIN/storage completion required')
    require(train.get('selection_method')==METHOD and train.get('fixed_treatment_step')==192
        and train['training']['updates']==192 and train['training']['presentations']==1536
        and selection.get('status')=='selected'and selection.get('selection_method')==METHOD
        and selection.get('heldout_opened')is False
        and selection.get('protocol_sha256')==science['conditional_training_protocol']['sha256'],'Fixed terminal, no held/DEV selection required')
    monitors=selection['conditions']
    require([item['step']for item in monitors]==[0,48,96,192]and all(item.get('status')=='completed'
        and item.get('raw_planned')==item.get('raw_completed')==6 and item.get('nll_completed')==96
        and math.isfinite(item['response_token_nll'])for item in monitors),'All384NLL/24raw monitoring calls required')
    terminal=next(item['identity']for item in monitors if item['step']==192)
    conditions=science['conditions']
    require(list(conditions)==['baseline','selected']and conditions['baseline']==train['comparison_control']
        and conditions['selected']==selection['selected']==terminal,'Exact fixed current192 versus conditional192 required')
    baseline=conditions['baseline'];treatment=conditions['selected']
    for value in conditions.values():
        require(value.get('step')==192 and value.get('presentations')==1536
            and value.get('parameter_count')==1916928,'Both conditions must be actual trained192 identities')
        bound(value)
    require(baseline['candidate_id']==ORIGINAL and treatment['candidate_id']==TREATMENT
        and baseline['sha256']!=treatment['sha256']
        and treatment.get('source_sha256')==train['counterfactual_runtime']['sha256']
        and treatment.get('warm_start')==train['warm_start']
        and treatment.get('target_manifest')==train['corpus_manifest']
        and treatment.get('target_protocol')==train['target_export_protocol'],'Conditional saved provenance or control identity differs')
    # The shared Runtime output envelope stays ORIGINAL; only trained_adapter varies.
    require(science['raw_provenance'].get('candidate_id')==ORIGINAL,'Do not relabel the shared inference wrapper')
    for identity in conditions.values():
        require(identity['sha256']!=science.get('disposable_qualification_sha256'),'Disposable software weights cannot be a condition')
    import daytime_contract
    import direct_launch_contract
    daytime_contract.worker(worker,train['expected_worker_script'],train['expected_worker_arguments'])
    direct_launch_contract.owned_worker(worker,science['owned_worker_source'],science['interpreters'])
    return train

def verify_phase(plan,bound,read):
    science=read(bound(plan['frozen_science_protocol']));verify_science(science,bound,read)
    for key in (*FIELDS,'conditions'):require(plan[key]==science[key],'Actual phase fixed-science mismatch: '+key)
    require(plan.get('comparison_metric_version')=='conditional-facts.v2+unchanged-immediate.v1'
        and plan.get('condition_names')=={'baseline':'fixed_current192','selected':'fixed_conditional_terminal192'},'Truthful matched-condition labels/metrics required')
    if plan['mode']=='heldout':
        ready=read(bound(plan['fresh_cohort']));audit=read(bound(plan['fresh_cohort_audit']))
        require(ready.get('status')=='ready'and ready.get('selected_games')==16 and ready.get('input_count')==48
            and audit.get('status')=='passed'and audit.get('manifest_sha256')==plan['fresh_cohort']['sha256'],
            'Actual latest-unused fresh16 cohort audit required')
        require(same_file(plan['input_rows'],ready['input_rows'],bound)
            and same_file(plan['heldout_references'],ready['grader_references'],bound),'Fresh input/grade bindings differ')
    return science
