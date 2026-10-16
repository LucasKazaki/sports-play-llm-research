"""Create-only fresh original64 restart after audited closed atomic-write failure."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
import training_contract_v4 as c
HERE=Path(__file__).resolve().parent


def binding(path):return {'path':str(Path(path).resolve()),'sha256':c.digest(path)}


def prepare_training(failed_protocol,failed_failure,failed_stale_run,failed_worker,failed_audit,
    budget,ui_closed,atomic_tests,atomic_review,out,output_dir):
    if out.exists()or output_dir.exists()or output_dir.name!='conditional-train-3':raise ValueError('Distinct create-only conditional-train-3 required')
    plan=deepcopy(c.read(failed_protocol));script=HERE/'train_v5.py'
    args=[str(script.resolve()),'train','--protocol',str(out.resolve()),'--out',str(output_dir.resolve())]
    plan.update(frozen_at=datetime.now(timezone.utc).isoformat(),phase='training',implementation_sha256=c.digest(script),
        admission_latest_utc=c.ADMISSION,maximum_seconds=3000,worker_maximum_seconds=3030,external_maximum_seconds=3060,
        expected_worker_script=script.relative_to(c.ROOT).as_posix(),expected_worker_arguments=args,
        expected_worker_arguments_sha256=hashlib.sha256(json.dumps(args).encode()).hexdigest(),
        preserved_write_failure={'protocol':binding(failed_protocol),'failure':binding(failed_failure),
            'stale_run':binding(failed_stale_run),'worker':binding(failed_worker),'audit':binding(failed_audit)},
        prior_update_qualification_reuse={'previous_training_source':binding(HERE/'train_v3.py'),
            'current_training_source':binding(script),'tested_entrypoint':binding(HERE/'train_v4.py'),
            'atomic_helper':binding(HERE/'bounded_atomic_save_v1.py'),'atomic_test_source':binding(HERE/'test_atomic_save_v1.py'),
            'atomic_test_result':binding(atomic_tests),'atomic_test_audit':binding(atomic_review)},
        prospective_recovery_budget={'budget':binding(budget),'completed_ui_closed':binding(ui_closed)},
        prospective_repair='Caller-local closed unique-temp JSON replacement with <=.5s sharing-denial retry; numerical functions/input/data/runtime unchanged. Prior failed167/1336 remains historical, no terminal candidate.',
        freshness='Fresh original64/freshAdamW/full192/1536/384NLL/24raw/fixedterminal192. No resume from unsaved167, saved96, failed optimizer or disposable qualifier. Root19:10 is a prospective internal admission inside unchanged human22 authority.',
        live_observation='Read append-only completed training journal records only. Never reopen atomically replaced run.json while active. Sharing-denial cause remains unknown; retry is not a universal filesystem repair.')
    paths=[failed_protocol,failed_failure,failed_stale_run,failed_worker,failed_audit,budget,ui_closed,atomic_tests,atomic_review]
    paths += [HERE/name for name in ['train_v3.py','train_v4.py','train_v5.py','bounded_atomic_save_v1.py',
        'test_atomic_save_v1.py','training_contract_v4.py','prepare_training_v7.py','test_recovery_window_v4.py']]
    plan['dependencies'] += [binding(path)for path in paths]
    unique={str((Path(item['path'])if Path(item['path']).is_absolute()else c.ROOT/item['path']).resolve()):item for item in plan['dependencies']}
    plan['dependencies']=list(unique.values())
    parent=c.read(c.bound(plan['preserved_training_protocol']));c.science(plan,parent)
    c.qualification_gate(plan);c.target_readiness(plan);c.failed_attempt_gate(plan)
    c.write_failure_gate(plan);c.reuse_gate(plan);c.budget_gate(plan)
    with out.open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return binding(out)
