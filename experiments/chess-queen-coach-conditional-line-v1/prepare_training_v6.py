"""TRAIN-only prospective scoring repair; preserve failed source and actual8-micro gate."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
import training_contract_v3 as c
HERE=Path(__file__).resolve().parent

def binding(path):return {'path':str(Path(path).resolve()),'sha256':c.digest(path)}
def create(path,value):
    with Path(path).open('x',encoding='utf-8')as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    return binding(path)

def prepare_training(qualification_protocol,qualification_result,qualification_worker,qualification_audit,
    failed_protocol,failed_run,failed_worker,failed_audit,out,output_dir):
    base=c.read(qualification_protocol);plan=deepcopy(base)
    script=HERE/'train_v3.py';args=[str(script.resolve()),'train','--protocol',str(out.resolve()),'--out',str(output_dir.resolve())]
    for key in ['planned_updates','planned_presentations','disposable_not_candidate','software_acceptance']:plan.pop(key,None)
    plan.update(phase='training',frozen_at=datetime.now(timezone.utc).isoformat(),implementation_sha256=c.digest(script),
        admission_latest_utc=c.ADMISSION,maximum_seconds=3000,worker_maximum_seconds=3030,external_maximum_seconds=3060,
        expected_worker_script=script.relative_to(c.ROOT).as_posix(),expected_worker_arguments=args,
        expected_worker_arguments_sha256=hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        conditional_update_gate={'protocol':binding(qualification_protocol),'result':binding(qualification_result),
            'worker':binding(qualification_worker),'audit':binding(qualification_audit),
            'script':base['expected_worker_script'],'arguments':base['expected_worker_arguments']},
        preserved_failed_training={'protocol':binding(failed_protocol),'run':binding(failed_run),
            'worker':binding(failed_worker),'audit':binding(failed_audit)},
        prospective_repair='Only six-case monitoring reference projection and unused18:30 operating admission change; strict evaluator/numerics/fullcounts unchanged. Priorfailedstep0 had no TRAIN/optimizer attempt, source/receipts remainhistorical.',
        freshness='Fresh original64/freshAdamW after closed no-learning scorer failure; no checkpoint/optimizer/disposable reuse.192full updates/1536presentations,384DEVNLL+24rawDEV,fixedterminal192.')
    plan['dependencies'] += [binding(path)for path in [qualification_protocol,qualification_result,qualification_worker,qualification_audit,
        failed_protocol,failed_run,failed_worker,failed_audit]]+[binding(HERE/name)for name in
        ['train_v3.py','training_contract_v3.py','prepare_training_v6.py','test_monitor_projection_v3.py']]
    c.qualification_gate(plan);c.target_readiness(plan);c.failed_attempt_gate(plan)
    return create(out,plan)
