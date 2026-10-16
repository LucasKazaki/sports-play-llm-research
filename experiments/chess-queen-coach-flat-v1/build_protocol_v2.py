"""Create-only metadata plans. No model, reference scoring, or input acquisition."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));import run_once_v2 as core
DAY=ROOT/'experiments/chess-queen-coach-daytime-v1'
TASK=core.TASK

def binding(path):return core.bind(Path(path).resolve())

def base(mode,out,actual_out):
    frozen=DAY/'held-direct-protocol-v2.json';old=core.read(frozen)
    keep=['model_runtime','raw_provenance','child_script','child_implementation_sha256','conditions',
        'owned_worker_source','interpreters','launch_profile','cpu_environment_parity','dependencies']
    plan={key:copy.deepcopy(old[key]) for key in keep}
    plan.update(schema='chess.flat-cold-phase.v1',mode=mode,implementation_sha256=core.digest(HERE/'run_once_v2.py'),
        frozen_science_protocol=binding(frozen),frozen_at=datetime.now(timezone.utc).isoformat(),
        cutoff_utc='2026-10-16T22:00:00+00:00',admission_latest_utc=
            '2026-10-16T21:40:00+00:00' if mode=='qualification' else '2026-10-16T20:30:00+00:00',
        phase_maximum_seconds=450 if mode=='qualification' else 4500,child_maximum_seconds=210,
        worker_seconds=240,per_request_external_seconds=270,external_maximum_seconds=510 if mode=='qualification' else 4560,
        actual_out=str(Path(actual_out).resolve()),scope='Flat serial owned jobs; unchanged inference/science; no nested GPU lease.',
        descendant_scope='Creator-held job containment and empty closure, not individual descendant image/command proof.',
        prior_failed_CPU_audit=binding(TASK/'work/queen-review/daytime-observer-cpu-identity-3-failure-review.json'),
        design=binding(TASK/'work/queen-review/flat-cold-backbone-design-review-v2.json'))
    paths=[item['path'] for item in plan['dependencies']]+[str(HERE/name) for name in
        ['run_once_v2.py','build_protocol_v2.py','test_operational_v2.py']]+[str(frozen),plan['prior_failed_CPU_audit']['path'],plan['design']['path']]
    plan['dependencies']=[binding(path if Path(path).is_absolute() else ROOT/path) for path in dict.fromkeys(paths)]
    return plan

def prepare_qualification(out,actual_out):
    old=core.read(DAY/'cold-direct-qualification-protocol-v1.json')
    plan=base('qualification',out,actual_out);plan['input_rows']=old['input_rows']
    rows=[json.loads(line) for line in core.bound(plan['input_rows']).read_text().splitlines() if line.strip()]
    core.require(len(rows)==2,'Exactly two spent DEV packets required')
    plan['assignments']=[{'case_id':row['case_id'],'condition':name} for row,name in zip(rows,['baseline','selected'])]
    plan['purpose']='Two already-spent DEV software requests: original64 then actual saved192; no quality selection, no new held cohort.'
    return create(out,actual_out,plan)

def prepare_held(out,actual_out,qualification_protocol,qualification,qualification_audit,cohort_manifest,cohort_audit):
    plan=base('heldout',out,actual_out)
    ready=core.read(cohort_manifest);audit=core.read(cohort_audit)
    core.require(ready.get('status')=='ready' and ready.get('selected_games')==16 and ready.get('input_count')==48
        and audit.get('status')=='passed' and audit.get('manifest_sha256')==core.digest(cohort_manifest),
        'Exact independently audited fresh16 corpus required')
    plan.update(successful_qualification=binding(qualification),qualification_protocol=binding(qualification_protocol),
        qualification_audit=binding(qualification_audit),fresh_cohort=binding(cohort_manifest),fresh_cohort_audit=binding(cohort_audit),
        input_rows=ready['input_rows'],heldout_references=ready['grader_references'],
        purpose='Fixed original64 versus saved192 on freshly reserved16 games/48 inputs; full96 raw responses before truth opens.')
    plan['dependencies'] += [binding(path) for path in [qualification_protocol,qualification,qualification_audit,cohort_manifest,cohort_audit]]
    return create(out,actual_out,plan)

def create(out,actual_out,plan):
    out=Path(out).resolve();actual_out=Path(actual_out).resolve()
    core.require(not out.exists() and not actual_out.exists(),'Create-only plan/output; no retry')
    core.require(actual_out.is_relative_to(ROOT/'data/private/chess-queen-coach-flat-v1'),'Private flat output required')
    core.write(out,plan,create=True);return binding(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['qualification','heldout'])
    for name in ['out','actual-out','qualification-protocol','qualification','qualification-audit','cohort-manifest','cohort-audit']:
        parser.add_argument('--'+name,type=Path)
    args=parser.parse_args();core.require(args.out and args.actual_out,'Output paths required')
    if args.phase=='qualification':result=prepare_qualification(args.out,args.actual_out)
    else:
        values=[args.qualification_protocol,args.qualification,args.qualification_audit,args.cohort_manifest,args.cohort_audit]
        core.require(all(values),'Exact actual qualification and fresh cohort bindings required')
        result=prepare_held(args.out,args.actual_out,*values)
    print(json.dumps(result))
