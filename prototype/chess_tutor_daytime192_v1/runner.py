"""Metadata admission and display projection. No learned calls on import/verify."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
for folder in (ROOT/'scripts',ROOT/'prototype/chess_tutor_v1'):
    if str(folder) not in sys.path:sys.path.insert(0,str(folder))
from coaching_jobs import Unavailable
import chess_queen_daytime192_tutor_v1 as child

EVIDENCE=('completed_input','completed_entrypoint','completed_worker',
    'cancelled_input','cancelled_entrypoint','cancelled_worker')
ADMISSION=set(EVIDENCE)|{'protocol','training_audit','held_audit','entrypoint_audit','eligibility','root_decision'}
PROFILE='direct-base-owned-worker-v2'
ROOT_DECISION_SHA='650b57b5452713ae2593aa565db9d4ea991cea938176b57d5e1f39d68cbea134'


def worker_arguments(repo,protocol,protocol_sha,input_path,out):
    return [str(Path(repo)/'scripts/chess_queen_daytime192_tutor_v1.py'),'--protocol',str(protocol),
        '--protocol-sha256',protocol_sha,'--input',str(input_path),'--out',str(out)]


def check_worker(worker,arguments,*,completed):
    r=child.require
    r(type(worker) is dict and worker.get('schema')=='chess.owned-worker.v2'
        and worker.get('launch_profile')==PROFILE
        and worker.get('source_sha256')==child.FIXED['worker'],'Wrong owned worker/source.')
    r(worker.get('script','').replace('\\','/')=='scripts/chess_queen_daytime192_tutor_v1.py'
        and worker.get('arguments_sha256')==hashlib.sha256(json.dumps(arguments).encode()).hexdigest()
        and worker.get('maximum_seconds_after_GO')==240,'Worker request/deadline differs.')
    r(worker.get('owned_member_before_go') is True and worker.get('owned_job_exit_verified') is True
        and worker.get('child_exited_before_lease_release') is True,'Owned worker did not close.')
    r(worker.get('status')==('completed' if completed else 'failed')
        and type(worker.get('exit_code')) is int
        and (worker['exit_code']==0 if completed else worker['exit_code']!=0),'Worker outcome differs.')
    pid=worker.get('child_pid');own=worker.get('ownership',{});before=own.get('before_go',{})
    r(type(pid) is int and pid>0 and before.get('child_identity',{}).get('pid')==pid
        and before.get('popen_handle_pid_matches') is True
        and before.get('member_of_explicit_creator_job') is True
        and before.get('creator_member_of_explicit_child_job') is False
        and before.get('job_handle_passed_to_child') is False
        and before.get('complete_job_pids')==[pid],'Explicit before-GO ownership differs.')
    after=own.get('after_go_complete_job_pids')
    r(type(after) is list and all(type(p) is int and p>0 for p in after)
        and len(set(after))==len(after) and pid in after,'Incomplete after-GO owned PID list.')
    closure=own.get('closure',{})
    r(closure.get('complete_job_pids')==[] and closure.get('child_stable_handle_exited') is True
        and closure.get('actual_job_handle_closed') is True,'Owned closure evidence differs.')
    # actual_job_handle_closed is the reviewed wrapper's object-close observation,
    # not an independently observed Win32 CloseHandle result.


def native_current(raw):
    value=raw.get('input') if type(raw) is dict else None
    child.require(type(value) is dict and value.get('history',[])==[],'Unexpected model history.')
    child.require(set(value)<={'fen','selected_uci','history'},'Unexpected native input field.')
    return child.packet({k:v for k,v in value.items() if k!='history'})[0]


def check_envelope(value,plan,identity,protocol_sha):
    r=child.require
    r(type(value) is dict and value.get('schema')==child.ENVELOPE_SCHEMA,'Unknown preview envelope.')
    entry=value.get('entrypoint',{});raw=value.get('raw_response')
    r(type(entry) is dict and type(entry.get('input_sha256')) is str
        and child.safe.HEX.fullmatch(entry['input_sha256']),'Missing original input byte hash.')
    r(entry.get('profile_id')==child.PROFILE and entry.get('source_sha256')==plan['implementation_sha256']
        and entry.get('protocol_sha256')==protocol_sha and entry.get('outer_seconds')==210
        and entry.get('selection_sha256')==child.FIXED['selection']
        and entry.get('fixed_checkpoint_sha256')==child.FIXED['checkpoint'],'Preview provenance differs.')
    if raw is None:
        r(value.get('status')=='failed' and type(value.get('error')) is str,'Missing raw without failure.')
        return
    child.validate_raw(raw,native_current(raw),identity,plan)
    r(entry.get('raw_response_sha256')==child.safe.raw_digest(raw),'Native raw dictionary changed.')
    r(child.canonical(entry.get('trained_identity'))==child.canonical(identity)
        and type(entry.get('resource_policy')) is dict
        and all(entry['resource_policy'].get(k)==v for k,v in child.RESOURCES.items()),'Identity/resource policy differs.')
    if value.get('status') in {'completed','partial','terminal'}:
        r(value['status']==raw['status'] and value.get('error') is None
            and entry.get('frozen_storage',{}).get('identical') is True,'Storage or native completion not closed.')


def check_record_input(envelope,input_path):
    current,_=child.packet(child.read_json(input_path,32768))
    child.require(envelope['entrypoint']['input_sha256']==child.digest(input_path),'Original input file bytes differ.')
    raw=envelope.get('raw_response')
    if raw is not None:child.require(child.canonical(raw['input'])==child.canonical(current),'Native board/selected input differs.')
    return current


def check_retained_raw(envelope,out):
    raw=envelope.get('raw_response')
    if raw is not None:
        path=Path(out).with_name(Path(out).stem+'.raw.json')
        child.require(child.digest(path)==envelope['entrypoint']['raw_response_sha256']
            and path.read_bytes()==child.safe.serialized(raw).encode('utf-8'),'Retained native file differs.')


class PreviewRunner:
    fixture=False
    label='Queen 192 (unverified research preview)'
    maximum_seconds=270 # Frozen controller adds15; worker itself receives240.

    def __init__(self,repo=ROOT,qualification=None,qualification_sha256=None):
        self.repo=Path(repo).resolve()
        self.qualification_path=Path(qualification) if qualification else self.repo/'experiments/chess-tutor-daytime192-v1/unavailable.json'
        self.qualification_sha256=qualification_sha256
        self.verify()

    def verify(self):
        try:
            r=child.require;q=child.read_json(self.qualification_path)
            r(q.get('availability') is True and q.get('status')=='admitted_optional_research_preview',
                'The research preview is unavailable pending closed review and entrypoint qualification.')
            r(type(self.qualification_sha256) is str and child.safe.HEX.fullmatch(self.qualification_sha256)
                and child.digest(self.qualification_path)==self.qualification_sha256,'Exact admission hash required.')
            child.before_cutoff()
            r(q.get('schema')=='chess.daytime192-preview-admission.v1' and q.get('profile_id')==child.PROFILE
                and q.get('candidate_id')==child.CANDIDATE and q.get('runner_sha256')==child.digest(__file__),
                'Unknown preview/source.')
            bindings=q.get('bindings',{});r(set(bindings)==ADMISSION,'Incomplete admission bindings.')
            paths={name:child.inside(self.repo,item) for name,item in bindings.items()}
            plan,_,identity,_=child.verify_protocol(self.repo,paths['protocol'],bindings['protocol']['sha256'])
            root_decision=child.read_json(paths['root_decision'])
            r(bindings['root_decision']['sha256']==ROOT_DECISION_SHA
                and root_decision.get('schema')=='chess.daytime192.limited-private-preview-decision.v1'
                and root_decision.get('status')=='conditional_research_preview_permitted_after_actual_entrypoint_qualification'
                and root_decision.get('cutoff_utc')==child.CUTOFF
                and root_decision.get('profile_id')==child.PROFILE
                and root_decision.get('candidate_id')==child.CANDIDATE
                and root_decision.get('selected_step')==192
                and root_decision.get('checkpoint_sha256')==child.FIXED['checkpoint']
                and root_decision.get('selection_sha256')==child.FIXED['selection'],
                'Missing exact conditional root preview decision.')
            for name in ('training_audit','held_audit'):
                a=child.read_json(paths[name])
                r(a.get('schema')=='chess.daytime192-closed-audit-binding.v1' and a.get('status')=='passed'
                    and a.get('kind')==name and a.get('planned_ledger_closed') is True
                    and a.get('selected_adapter_sha256')==child.FIXED['checkpoint']
                    and a.get('selection_sha256')==child.FIXED['selection']
                    and a.get('expert_human_semantic_validation') is False,'Closed independent audit binding missing.')
                r(a.get('experiment_status') in {'completed','failed','partial'},'Audit must state actual experiment outcome.')
                counts=a.get('outcome_counts',{});planned=a.get('planned')
                r(type(planned) is int and planned>0 and type(counts) is dict and counts
                    and all(type(v) is int and v>=0 for v in counts.values()) and sum(counts.values())==planned,
                    'Audit planned denominator is not fully accounted.')
                r(child.inside(self.repo,a['original_report'])!=paths[name],'Audit cannot cite itself.')
                expected=root_decision['training_audit_sha256' if name=='training_audit' else 'held_failure_audit_sha256']
                r(a['original_report']['sha256']==expected,'Closed audit differs from the root decision.')
                if name=='held_audit':
                    child.inside(self.repo,a['scope_amendment'])
                    r(a['scope_amendment']['sha256']==root_decision['held_scope_amendment_sha256'],
                        'Held scope amendment differs from the root decision.')
                # A passed engineering audit can close a FAILED experiment. No
                # success score or96 successful responses is invented as a gate.
            audit=child.read_json(paths['entrypoint_audit'])
            r(audit.get('schema')=='chess.daytime192-entrypoint-audit-binding.v1'
                and audit.get('status')=='passed' and audit.get('review_kind')=='independent_local_agent_engineering'
                and audit.get('expert_human_semantic_validation') is False,'Missing independent actual qualification audit.')
            r(audit.get('entrypoint_sha256')==plan['implementation_sha256']
                and audit.get('protocol_sha256')==bindings['protocol']['sha256']
                and audit.get('evidence')=={key:bindings[key] for key in EVIDENCE},'Actual audit binds other executions.')
            r(child.inside(self.repo,audit['original_report'])!=paths['entrypoint_audit'],'Audit cannot cite itself.')
            r(audit.get('observed')=={'completed_eos_and_frozen_storage_verified':True,
                'cancelled_selected_adapter_load_completed':True,'cancelled_infer_started':True,
                'owned_cancellation_observed':True,'both_children_exited_before_lease_release':True},
                'Actual qualification phases/ownership were not reviewed.')
            decision=child.read_json(paths['eligibility'])
            r(decision.get('schema')=='chess.daytime192-preview-eligibility.v1'
                and decision.get('status')=='eligible_for_optional_research_preview'
                and decision.get('scope')=='local_research_tutor_feedback_only'
                and decision.get('explicit_root_decision') is True
                and decision.get('expert_human_semantic_validation') is False,'Missing explicit limited-preview decision.')
            r(decision.get('selected_adapter_sha256')==child.FIXED['checkpoint']
                and decision.get('selection_sha256')==child.FIXED['selection']
                and decision.get('root_decision_sha256')==bindings['root_decision']['sha256']
                and all(decision.get(name+'_sha256')==bindings[name]['sha256']
                    for name in ('training_audit','held_audit','entrypoint_audit')),'Eligibility binds other audits/weights.')
            for prefix in ('completed','cancelled'):
                record=child.read_json(paths[prefix+'_entrypoint'])
                check_envelope(record,plan,identity,bindings['protocol']['sha256'])
                check_record_input(record,paths[prefix+'_input']);check_retained_raw(record,paths[prefix+'_entrypoint'])
                if prefix=='completed':r(record.get('status')=='completed' and record['raw_response'].get('finish_reason')=='eos','No authored EOS.')
                else:r(record.get('status')=='failed' and 'owned cancellation' in str(record.get('error','')).lower(),'No owned cancellation.')
                args=worker_arguments(self.repo,paths['protocol'],bindings['protocol']['sha256'],
                    paths[prefix+'_input'],paths[prefix+'_entrypoint'])
                check_worker(child.read_json(paths[prefix+'_worker']),args,completed=prefix=='completed')
            self.plan=plan;self.identity=identity;self.protocol=paths['protocol']
            self.protocol_sha256=bindings['protocol']['sha256'];self.q=q
            self.worker=child.inside(self.repo,plan['bindings']['worker'])
        except (OSError,ValueError,KeyError,TypeError,AttributeError,child.metadata.PackageNotFoundError) as error:
            raise Unavailable('Research preview is unavailable: '+str(error)) from error

    def command(self,job):
        self.verify()
        args=worker_arguments(self.repo,self.protocol,self.protocol_sha256,job['input'],job['out'])
        return [sys.executable,str(self.worker),'--receipt',str(job['worker']),'--maximum-seconds','240','--',*args]

    def decorate_result(self,job,envelope):
        """Separate display projection; never mutate either native/outer record."""
        value={'status':'failed','entrypoint_envelope':copy.deepcopy(envelope)}
        verified=False
        try:
            check_envelope(envelope,self.plan,self.identity,self.protocol_sha256)
            current=check_record_input(envelope,job['input']);check_retained_raw(envelope,job['out'])
            child.require(job.get('input_sha256')==envelope['entrypoint']['input_sha256']
                and child.canonical(job.get('request_packet'))==child.canonical({k:v for k,v in current.items() if k!='history'}),
                'Controller input snapshot differs.')
            args=worker_arguments(self.repo,self.protocol,self.protocol_sha256,job['input'],job['out'])
            check_worker(child.read_json(job['worker']),args,completed=envelope.get('status') in {'completed','terminal'})
            raw=envelope.get('raw_response')
            if raw is not None:value=copy.deepcopy(raw)
            value.update(status=envelope['status'],error=envelope.get('error'),
                native_raw_response=copy.deepcopy(raw),entrypoint_envelope=copy.deepcopy(envelope))
            verified=raw is not None
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
            value.update(status='failed',error=str(error),ui_validation_error=str(error))
        value['ui_provenance']={'profile_id':child.PROFILE,'backend_label':self.label,
            'qualification_sha256':self.qualification_sha256,'response_binding_verified':verified,
            'scope':'Research preview for tutor feedback. Prose and teaching quality are unverified.'}
        return value
