"""Prospective create-only conditional qualifier/TRAIN plans; never executes a backend."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import training_contract_v2 as c
HERE=Path(__file__).resolve().parent
SELECTION='Fixed terminal192; all DEV results monitoring only; no candidate choice from DEV or held quality.'

def binding(path):return {'path':str(Path(path).resolve()),'sha256':c.digest(path)}
def create(path,plan):
    with Path(path).open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return binding(path)

def common(parent_protocol,parent_audit,parent_selection,data,export_protocol,export_closed,token_protocol,token_receipt,data_audit):
    """Read only actual protocol/manifests/audits/selection metadata; no row semantics."""
    parent=c.read(parent_protocol);manifest=c.read(data/'manifest.json');selection=c.read(parent_selection)
    if(selection.get('status')!='selected'or selection['selected']['step']!=192):raise ValueError('Existing completed192 control required')
    result={key:deepcopy(parent[key])for key in c.SAME}
    result.update(schema='chess.conditional-training-protocol.v1',frozen_at=datetime.now(timezone.utc).isoformat(),
        daytime_authority=parent['daytime_authority'],preserved_training_protocol=binding(parent_protocol),
        preserved_training_closed_audit=binding(parent_audit),preserved_selection=binding(parent_selection),
        comparison_control=selection['selected'],parent_corpus_manifest=binding(c.bound(parent['corpus_manifest'])),
        corpus_manifest=binding(data/'manifest.json'),target_export_protocol=binding(export_protocol),
        target_export_closed=binding(export_closed),cpu_preflight_protocol=binding(token_protocol),
        cpu_preflight=binding(token_receipt),cpu_preflight_source=binding(HERE/'prepare_v3.py'),
        target_data_audit=binding(data_audit),phase_maximum_seconds={'training':3000,'heldout':4500},
        cutoff_utc=c.CUTOFF,admission_latest_utc=c.ADMISSION,fixed_treatment_step=192,selection_method=SELECTION,
        counterfactual_runtime=binding(HERE/'conditional_runtime.py'),conditional_evaluator=binding(HERE/'evaluate_v2.py'),
        data={key:{'path':str((data/name).resolve()),'sha256':manifest['files'][name]['sha256']}
            for key,name in [('train','train.jsonl'),('development','development.jsonl'),('development_references','development-references.jsonl')]},
        target_intervention='Only conditional line target prose changes; same source games, order, current-only inputs and stored PVs.',
        development_usage='All384 response-token NLL and24 raw DEV calls are monitoring only; fixed final192 irrespective of observed scores.',
        heldout_authority='Embedded heldout unauthorized. Separate latest-unused16/fresh96 plan must use SAME unchanged cold child/inference runtime for existing192 and conditional192, differing trained_adapter identities only.',
        future_held_maximum_seconds=4500,other_held_floors_or_counts_changed=False,
        disposable_qualification_adapter_may_warm_start_training=False)
    source_names=['conditional_runtime.py','training_contract_v2.py','train_v2.py','qualify_conditional_v2.py','prepare_training_v5.py',
        'targets.py','targets_v2.py','evaluate_v2.py','prepare_v3.py','test_operating_window_v2.py','test_training_binding_v5.py']
    dependencies=list(parent['dependencies'])+[binding(HERE/name)for name in source_names]
    dependencies += [binding(path)for path in [parent_protocol,parent_audit,parent_selection,export_protocol,export_closed,token_protocol,token_receipt,data_audit]]
    unique={str(Path(item['path']).resolve()):item for item in dependencies}
    result['dependencies']=list(unique.values())
    return result

def prepare_qualification(parent_protocol,parent_audit,parent_selection,data,export_protocol,export_closed,token_protocol,token_receipt,data_audit,out,output_dir):
    plan=common(parent_protocol,parent_audit,parent_selection,data,export_protocol,export_closed,token_protocol,token_receipt,data_audit)
    script=HERE/'qualify_conditional_v2.py';args=[str(script.resolve()),'--protocol',str(out.resolve()),'--out',str(output_dir.resolve())]
    plan.update(phase='qualification',implementation_sha256=c.digest(script),maximum_seconds=600,
        worker_maximum_seconds=630,external_maximum_seconds=660,planned_updates=1,planned_presentations=8,
        disposable_not_candidate=True,expected_worker_script=script.relative_to(c.ROOT).as_posix(),expected_worker_arguments=args,
        expected_worker_arguments_sha256=hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        software_acceptance='Exact original64 effective values;8complete finitebackwards+1update;144FP32/1916928, changedLoRA,2268frozen unchanged;save/reload equal. Disposable weights never candidate or warmstart. No accuracy criterion.')
    return create(out,plan)

def prepare_training(qualification_protocol,qualification_result,qualification_worker,qualification_audit,out,output_dir):
    base=c.read(qualification_protocol);plan=deepcopy(base)
    script=HERE/'train_v2.py';args=[str(script.resolve()),'train','--protocol',str(out.resolve()),'--out',str(output_dir.resolve())]
    for key in ['planned_updates','planned_presentations','disposable_not_candidate','software_acceptance']:plan.pop(key,None)
    plan.update(phase='training',frozen_at=datetime.now(timezone.utc).isoformat(),implementation_sha256=c.digest(script),
        maximum_seconds=3000,worker_maximum_seconds=3030,external_maximum_seconds=3060,
        expected_worker_script=script.relative_to(c.ROOT).as_posix(),expected_worker_arguments=args,
        expected_worker_arguments_sha256=hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        conditional_update_gate={'protocol':binding(qualification_protocol),'result':binding(qualification_result),
            'worker':binding(qualification_worker),'audit':binding(qualification_audit),
            'script':base['expected_worker_script'],'arguments':base['expected_worker_arguments']},
        freshness='Fresh original64/fresh AdamW; no disposable qualifier/checkpoint/optimizer reuse.192full updates/1536presentations,384DEVNLL+24rawDEV, fixed final192.')
    plan['dependencies'] += [binding(path)for path in [qualification_protocol,qualification_result,qualification_worker,qualification_audit]]
    # Actual closed software gate and target/source closure are mandatory before freezing a runnable TRAIN plan.
    c.qualification_gate(plan)
    c.target_readiness(plan)
    return create(out,plan)
