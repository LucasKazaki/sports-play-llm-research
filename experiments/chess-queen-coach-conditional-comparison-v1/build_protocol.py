"""Create-only fixed192/current192 science and flat-phase plans; metadata only."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import run_conditional as core
import comparison_contract as science
PRESERVED=ROOT/'experiments/chess-queen-coach-flat-v1/qualification-protocol-v2.json'


def binding(path):return core.bind(Path(path).resolve())

def create(out,actual_out,plan):
    out=Path(out).resolve();actual_out=Path(actual_out).resolve()
    core.require(not out.exists()and not actual_out.exists(),'Create-only plan/output; no replay')
    core.require(actual_out.is_relative_to(ROOT/'data/private/chess-queen-coach-conditional-comparison-v1'),'New private comparison output root required')
    core.write(out,plan,create=True);return binding(out)


def prepare_science(training_protocol,training_run,selection,worker,audit,out):
    """After actual complete TRAIN/audit only. No input/reference bodies are opened."""
    core.require(not out.exists(),'Science is create-only')
    shared=core.read(PRESERVED);train=core.read(training_protocol);saved=core.read(selection)
    plan={key:copy.deepcopy(shared[key])for key in science.FIELDS}
    q=core.read(core.bound(train['conditional_update_gate']['result']))
    plan.update(schema='chess.conditional-comparison-science.v1',frozen_at=datetime.now(timezone.utc).isoformat(),
        preserved_shared_science=binding(PRESERVED),conditional_training_protocol=binding(training_protocol),
        conditional_training_run=binding(training_run),conditional_selection=binding(selection),
        conditional_training_worker=binding(worker),conditional_training_audit=binding(audit),
        disposable_qualification_sha256=q['disposable_adapter']['sha256'],
        conditions={'baseline':train['comparison_control'],'selected':saved['selected']},
        condition_names={'baseline':'fixed_current192','selected':'fixed_conditional_terminal192'},
        candidate_identity_note='Both conditions trained. Top-level raw envelope identifies unchanged inference wrapper; trained_adapter carries the actual fixed checkpoint. No untrained/publisher or held-selected claim.',
        metric_note='Recognized conditional grammar coverage/truth and raw chess behavior separately. More target tokens/template fit is not broader tutoring quality or why-best truth.')
    paths=[item['path']for item in shared['dependencies']]+[str(PRESERVED),str(training_protocol),str(training_run),str(selection),str(worker),str(audit)]
    paths += [str(HERE/name)for name in ['comparison_contract.py','run_conditional.py','build_protocol.py','grade_conditional.py','test_comparison.py','test_operations.py']]
    paths += [str(ROOT/'experiments/chess-queen-coach-conditional-line-v1'/name)for name in ['targets.py','targets_v2.py','evaluate_v2.py','conditional_runtime.py']]
    unique={str((Path(path)if Path(path).is_absolute()else ROOT/path).resolve()):path for path in paths}
    plan['dependencies']=[binding(path)for path in unique]
    science.verify_science(plan,core.bound,core.read)
    core.write(out,plan,create=True);return binding(out)


def base(mode,science_protocol,out,actual_out):
    frozen=core.read(science_protocol);science.verify_science(frozen,core.bound,core.read)
    keep=[*science.FIELDS,'conditions','condition_names','dependencies']
    plan={key:copy.deepcopy(frozen[key])for key in keep}
    plan.update(schema='chess.flat-cold-phase.v1',mode=mode,implementation_sha256=core.digest(HERE/'run_conditional.py'),
        frozen_science_protocol=binding(science_protocol),frozen_at=datetime.now(timezone.utc).isoformat(),
        cutoff_utc='2026-10-16T22:00:00+00:00',admission_latest_utc='2026-10-16T21:40:00+00:00'if mode=='qualification'else'2026-10-16T20:30:00+00:00',
        phase_maximum_seconds=450 if mode=='qualification'else 4500,child_maximum_seconds=210,worker_seconds=240,
        per_request_external_seconds=270,external_maximum_seconds=510 if mode=='qualification'else 4560,
        actual_out=str(actual_out.resolve()),comparison_metric_version='conditional-facts.v2+unchanged-immediate.v1',
        scope='Same-child/same-inference fixed current192 versus conditional terminal192, serial explicit owned jobs.',
        descendant_scope='Creator-held job containment/empty closure; no individual descendant image/command proof.',
        paired_order='All48fixed current192 first, then48conditional192, preserving qualified flat order. Time-order/resource drift and16puzzle-biased groups limit inference.',
        labels_only_after_all_raw_jobs_closed=True)
    plan['dependencies'].append(binding(science_protocol));return plan


def prepare_qualification(science_protocol,out,actual_out):
    old=core.read(PRESERVED);plan=base('qualification',science_protocol,out,actual_out)
    plan.update(input_rows=old['input_rows'],assignments=copy.deepcopy(old['assignments']),
        purpose='Exactly two already-spent legacy DEV inputs: fixed current192 FREE then conditional terminal192 supplied. Coldload/input/source/storage/ownership only; no quality selection or fresh held data.')
    # Input and assignment metadata copied exactly; actual input packets are parsed only by the root-dispatched phase.
    core.require(len(plan['assignments'])==2 and [row['condition']for row in plan['assignments']]==['baseline','selected'],'Two fixed spentDEV assignments required')
    return create(out,actual_out,plan)


def prepare_held(science_protocol,out,actual_out,qualification_protocol,qualification,qualification_audit,cohort_manifest,cohort_audit):
    plan=base('heldout',science_protocol,out,actual_out)
    ready=core.read(cohort_manifest);audit=core.read(cohort_audit)
    core.require(ready.get('status')=='ready'and ready.get('selected_games')==16 and ready.get('input_count')==48
        and audit.get('status')=='passed'and audit.get('manifest_sha256')==core.digest(cohort_manifest),'Actual latest-unused16/48 audit required')
    plan.update(successful_qualification=binding(qualification),qualification_protocol=binding(qualification_protocol),
        qualification_audit=binding(qualification_audit),fresh_cohort=binding(cohort_manifest),fresh_cohort_audit=binding(cohort_audit),
        input_rows=ready['input_rows'],heldout_references=ready['grader_references'],
        purpose='Fixed trained current192 versus fixed terminal conditional192 on16newgames/48triplets/full96requests before grader truth opens. No count reduction/replacement/held selection.')
    plan['dependencies'] += [binding(path)for path in [qualification_protocol,qualification,qualification_audit,cohort_manifest,cohort_audit]]
    # Verify the actual new two-identity qualification now; no held reference body or generation is accessed.
    q=core.read(qualification);qp=core.read(qualification_protocol);qa=core.read(qualification_audit)
    core.require(q.get('status')=='passed'and q.get('planned')==q.get('completed_children')==2
        and q.get('all_children_closed')is True and q.get('labels_opened')is False
        and q.get('outer_torch_imported')is False and q.get('protocol_sha256')==core.digest(qualification_protocol)
        and qa.get('status')=='passed'and qa.get('qualification_sha256')==core.digest(qualification)
        and qa.get('protocol_sha256')==core.digest(qualification_protocol),'Actual new identity coldqualification/audit required')
    for key in ['implementation_sha256',*science.FIELDS,'conditions']:
        core.require(qp[key]==plan[key],'Actual qualified source/conditions differ: '+key)
    core.require([row['identity']for row in q['rows']]==[plan['conditions']['baseline'],plan['conditions']['selected']],
        'Both actual fixed192 identities must be qualified; no disposable or original64 substitution')
    return create(out,actual_out,plan)
