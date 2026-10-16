"""Unactivated metadata-only admission for one fixed tuned Queen profile.

No server route, launch default or UI is changed by adding this module. Ordinary
admission requires separately bound closed audits, an explicit local-demo decision
and actual entrypoint completion/cancellation evidence. None is shipped enabled.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

from coaching_jobs import Unavailable

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'
if str(SCRIPTS) not in sys.path:sys.path.insert(0,str(SCRIPTS))
import chess_queen_coach_tutor_v1 as child


class TunedQueenRunner:
    fixture=False
    label='Tuned Queen (unverified research draft)'
    maximum_seconds=210

    def __init__(self,repo,qualification=None,qualification_sha256=None):
        self.repo=Path(repo).resolve()
        self.qualification=Path(qualification) if qualification else Path(__file__).with_name('queen-tuned-runtime-v1.json')
        self.qualification_sha256=qualification_sha256
        self.verify()

    def verify(self):
        try:
            require=child.require
            q=child.read_json(self.qualification)
            require(q.get('availability') is True and q.get('status')=='admitted_optional_local_demo',
                'The tuned research model is unavailable pending quality review and entrypoint qualification.')
            require(type(self.qualification_sha256) is str and child.HEX.fullmatch(self.qualification_sha256)
                and child.digest(self.qualification)==self.qualification_sha256,'An exact approved qualification hash is required.')
            require(q.get('profile_id')==child.PROFILE and q.get('candidate_id')==child.CANDIDATE,'Unknown tuned profile.')
            require(q.get('runner_sha256')==child.digest(Path(__file__)),'Tuned UI runner source changed.')
            bindings=q.get('bindings',{})
            require(set(bindings)=={'protocol','training_audit','heldout_quality_audit','entrypoint_qualification_audit','eligibility','completed_input','completed_entrypoint','completed_worker','cancelled_input','cancelled_entrypoint','cancelled_worker'},'Incomplete admission evidence.')
            paths={name:child.bound(self.repo,item) for name,item in bindings.items()}
            plan,training,identity,_=child.verify_protocol(self.repo,paths['protocol'],bindings['protocol']['sha256'])
            # These local-agent wrappers bind original independent audit reports;
            # they are not invented substitutes for missing reports or expert gold.
            for name in ('training_audit','heldout_quality_audit'):
                audit=child.read_json(paths[name])
                require(audit.get('schema')=='chess.tuned-tutor-closed-audit-binding.v1' and audit.get('status')=='passed',
                    'A closed independent audit binding is missing.')
                require(audit.get('kind')==name and audit.get('selected_adapter_sha256')==child.FIXED['checkpoint']
                    and audit.get('selection_sha256')==child.FIXED['selection']
                    and audit.get('expert_human_semantic_validation') is False,'Audit scope or fixed identity differs.')
                report=child.bound(self.repo,audit['original_report'])
                require(report!=paths[name],'Audit binding cannot cite itself.')
                require(audit.get('planned_ledger_closed') is True,'Audit has not closed every planned outcome.')
            actual_audit=child.read_json(paths['entrypoint_qualification_audit'])
            require(actual_audit.get('schema')=='chess.tuned-tutor-entrypoint-qualification-audit-binding.v1'
                and actual_audit.get('status')=='passed'
                and actual_audit.get('review_kind')=='independent_local_agent_engineering'
                and actual_audit.get('expert_human_semantic_validation') is False,'Missing independent actual entrypoint audit.')
            require(actual_audit.get('entrypoint_sha256')==plan['implementation_sha256']
                and actual_audit.get('protocol_sha256')==bindings['protocol']['sha256']
                and actual_audit.get('evidence')=={key:bindings[key] for key in
                    ('completed_input','completed_entrypoint','completed_worker','cancelled_input','cancelled_entrypoint','cancelled_worker')},
                'Actual entrypoint audit binds different qualification evidence.')
            require(child.bound(self.repo,actual_audit['original_report'])!=paths['entrypoint_qualification_audit'],
                'Actual entrypoint audit cannot cite itself.')
            require(actual_audit.get('observed')=={'completed_eos_and_frozen_storage_verified':True,
                'cancelled_selected_adapter_load_completed':True,'cancelled_infer_started':True,
                'owned_cancellation_observed':True,'both_children_exited_before_lease_release':True},
                'Actual qualification phases or owned shutdown were not independently observed.')
            decision=child.read_json(paths['eligibility'])
            require(decision.get('schema')=='chess.tuned-tutor-eligibility.v1'
                and decision.get('status')=='eligible_for_optional_local_demo'
                and decision.get('scope')=='optional_local_demo_only'
                and decision.get('explicit_root_decision') is True,'No explicit optional-demo eligibility decision.')
            require(decision.get('selected_adapter_sha256')==child.FIXED['checkpoint']
                and decision.get('selection_sha256')==child.FIXED['selection']
                and decision.get('training_audit_sha256')==bindings['training_audit']['sha256']
                and decision.get('heldout_quality_audit_sha256')==bindings['heldout_quality_audit']['sha256']
                and decision.get('entrypoint_qualification_audit_sha256')==bindings['entrypoint_qualification_audit']['sha256']
                and decision.get('expert_human_semantic_validation') is False,'Eligibility evidence differs.')
            completed=child.read_json(paths['completed_entrypoint']);cancelled=child.read_json(paths['cancelled_entrypoint'])
            self.plan=plan;self.identity=identity
            self._check_envelope(completed,plan,identity,bindings['protocol']['sha256'])
            self._check_envelope(cancelled,plan,identity,bindings['protocol']['sha256'])
            require(completed.get('status')=='completed' and completed['raw_response'].get('finish_reason')=='eos',
                'No complete authored entrypoint response.')
            require(cancelled.get('schema')==child.ENVELOPE_SCHEMA and cancelled.get('status')=='failed'
                and 'owned cancellation' in str(cancelled.get('error','')).lower(),'No owned-cancellation entrypoint receipt.')
            for prefix,record in (('completed',completed),('cancelled',cancelled)):
                require(record['entrypoint'].get('source_sha256')==plan['implementation_sha256']
                    and record['entrypoint'].get('protocol_sha256')==bindings['protocol']['sha256'],'Actual qualification used another entrypoint/protocol.')
                require(record['entrypoint'].get('input_sha256')==bindings[prefix+'_input']['sha256'],
                    'Actual qualification input byte binding differs.')
            for name in ('completed_worker','cancelled_worker'):
                worker=child.read_json(paths[name])
                prefix=name.split('_')[0]
                arguments=[str(self.repo/'scripts/chess_queen_coach_tutor_v1.py'),'--protocol',str(paths['protocol']),
                    '--protocol-sha256',bindings['protocol']['sha256'],'--input',str(paths[prefix+'_input']),'--out',str(paths[prefix+'_entrypoint'])]
                require(worker.get('script','').replace('\\','/')=='scripts/chess_queen_coach_tutor_v1.py'
                    and worker.get('arguments_sha256')==hashlib.sha256(json.dumps(arguments).encode()).hexdigest(),
                    'Qualification worker did not run this exact request/entrypoint.')
                require(worker.get('status')=='completed' if name=='completed_worker' else worker.get('status')=='failed',
                    'Qualification worker status differs.')
                require(worker.get('child_exited_before_lease_release') is True,'Qualification child outlived the lease.')
                require(worker.get('exit_code')==0 if name=='completed_worker' else type(worker.get('exit_code')) is int and worker['exit_code']!=0,
                    'Qualification exit code differs.')
            current,_=child.packet(child.read_json(paths['completed_input'],maximum=32768))
            require(child.canonical(current)==child.canonical(completed['raw_response']['input']),'Qualification response/input differs.')
            child.packet(child.read_json(paths['cancelled_input'],maximum=32768))
            self.q=q;self.protocol=paths['protocol'];self.protocol_sha256=bindings['protocol']['sha256']
            self.worker=child.bound(self.repo,plan['bindings']['worker'])
            self.child=self.repo/'scripts/chess_queen_coach_tutor_v1.py'
        except (OSError,ValueError,KeyError,TypeError,AttributeError,child.metadata.PackageNotFoundError) as error:
            raise Unavailable('Tuned coaching is unavailable: '+str(error)) from error

    def _check_envelope(self,value,plan,identity,protocol_sha):
        child.require(value.get('schema')==child.ENVELOPE_SCHEMA,'Unknown trained envelope.')
        raw=value.get('raw_response');entry=value.get('entrypoint',{})
        child.require(type(entry) is dict,'Entrypoint provenance is not an object.')
        child.require(type(entry.get('input_sha256')) is str and child.HEX.fullmatch(entry['input_sha256']),
            'Entrypoint input byte hash is missing.')
        child.require(entry.get('profile_id')==child.PROFILE and entry.get('source_sha256')==plan['implementation_sha256']
            and entry.get('protocol_sha256')==protocol_sha
            and entry.get('selection_sha256')==child.FIXED['selection']
            and entry.get('fixed_checkpoint_sha256')==child.FIXED['checkpoint'],'Entrypoint provenance differs.')
        child.require(type(entry.get('outer_seconds')) is int and entry['outer_seconds']==210,'Entrypoint outer deadline differs.')
        if raw is None:
            child.require(value.get('status')=='failed' and type(value.get('error')) is str,'Missing raw response without a retained failure.')
            return
        current,_=child.packet(raw.get('input') if type(raw) is dict else None)
        child.validate_raw(raw,current,identity,plan)
        child.require(entry.get('raw_response_sha256')==child.raw_digest(raw),'Untouched raw response hash differs.')
        child.require(type(entry.get('resource_policy')) is dict,'Entrypoint resource policy is not an object.')
        child.require(child.canonical(entry.get('trained_identity'))==child.canonical(identity)
            and all(entry.get('resource_policy',{}).get(key)==value for key,value in child.RESOURCES.items()),'Entrypoint identity/resource policy differs.')
        if value.get('status') in {'completed','partial','terminal'}:
            child.require(value['status']==raw['status'] and value.get('error') is None
                and entry.get('frozen_storage',{}).get('identical') is True,'Entrypoint did not close frozen-storage verification.')

    def command(self,job):
        self.verify()
        return [sys.executable,str(self.worker),'--receipt',str(job['worker']),'--maximum-seconds','180',
            '--',str(self.child),'--protocol',str(self.protocol),'--protocol-sha256',self.protocol_sha256,
            '--input',str(job['input']),'--out',str(job['out'])]

    def decorate_result(self,job,result):
        """Keep the raw inference dictionary intact under raw_response."""
        value=copy.deepcopy(result)
        try:
            self._check_envelope(result,self.plan,self.identity,self.protocol_sha256)
            child.require(result['entrypoint']['input_sha256']==child.digest(job['input']),
                'Response input byte binding differs.')
            verified=result.get('raw_response') is not None
            if verified:
                current,_=child.packet(child.read_json(job['input'],maximum=32768))
                child.require(child.canonical(result['raw_response']['input'])==child.canonical(current),'Response belongs to another board.')
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            value.update(status='failed',ui_validation_error=str(error),error=str(error));verified=False
        value['ui_provenance']={'profile_id':child.PROFILE,'backend_label':self.label,
            'qualification_sha256':self.qualification_sha256,'response_binding_verified':verified,
            'scope':'Optional local research draft. Runtime checks do not verify prose or teaching quality.'}
        return value
