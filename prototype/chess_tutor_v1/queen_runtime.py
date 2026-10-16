"""Metadata-only binding for the authored Queen NF4 runtime; no model imports."""
import importlib.metadata
import json
import math
from pathlib import Path
import sys

from coaching_jobs import Unavailable, read_record, sha

QUALIFICATION_SHA256 = '0a17fcaa72bef97eec28e4bec0e245c4c42a28219dcf5da6d8c06f807278188d'
EXPECTED_SETTINGS = {'max_new_tokens':1024,'maximum_seconds':240,'temperature':0.0,
    'seed':20260823,'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'}
RESOURCE_FLOORS = {'stop_physical_available_bytes':4*1024**3,
    'stop_commit_headroom_bytes':4*1024**3,'stop_gpu_free_bytes':1024**3}


def require(condition, message):
    if not condition: raise Unavailable(message)


def parity_passed(receipt, plan):
    if receipt.get('status')!='passed' or receipt.get('thresholds')!=plan.get('thresholds'):
        return False
    rows=receipt.get('comparisons',[])
    if [row.get('kind') for row in rows]!=['base_prompt','synthetic_vocabulary_suffix']:
        return False
    limits=plan['thresholds']
    for row in rows:
        for scope in ('all_logits','original_vocab_logits','added_vocab_logits'):
            value=row.get(scope,{})
            if value.get('finite') is not True or value.get('top1_equal') is not True:return False
            for key in ('max_absolute_error','mean_absolute_error','cosine_similarity'):
                if type(value.get(key)) not in (int,float) or not math.isfinite(value[key]):return False
            if value['max_absolute_error']>limits['max_absolute_error'] or value['mean_absolute_error']>limits['mean_absolute_error'] or value['cosine_similarity']<limits['minimum_cosine_similarity']:
                return False
    return True


class QueenRunner:
    fixture=False
    label='Queen (unverified draft)'
    maximum_seconds=270  # Frozen child has240seconds; shared wrapper adds30for owned exit.

    def __init__(self,repo):
        self.repo=Path(repo).resolve()
        self.qualification_path=Path(__file__).with_name('queen-runtime.json')
        self.verify()

    def verify(self):
        """No imports from the candidate, Torch, transformers or bitsandbytes."""
        try:
            require(sha(self.qualification_path)==QUALIFICATION_SHA256,'The local coaching qualification changed.')
            plan=read_record(self.qualification_path)
            require(plan and plan.get('status')=='approved_for_authored_ui','The local coaching runtime is not qualified for this interface.')
            self.plan=plan
            records={}
            for role,item in plan['bindings'].items():
                path=(self.repo/item['path']).resolve()
                require(path.is_relative_to(self.repo) and sha(path)==item['sha256'],'A qualified runtime file changed: '+role)
                if path.suffix=='.json':records[role]=read_record(path)
            kernel=records['kernel_protocol'];diagnostic=records['kernel_receipt']
            parity_plan=records['parity_protocol'];parity=records['parity_receipt'];authored=records['authored_receipt']
            bindings=plan['bindings']
            require(kernel['implementation_sha256']==bindings['adapter']['sha256'],'NF4 source does not match its protocol.')
            require(diagnostic.get('status')=='passed' and diagnostic.get('all_checks_passed') is True and diagnostic.get('source_sha256')==bindings['adapter']['sha256'] and diagnostic.get('protocol_sha256')==bindings['kernel_protocol']['sha256'],'NF4 kernel qualification does not match.')
            require(parity_plan['implementation_sha256']==bindings['parity_source']['sha256'] and parity.get('source_sha256')==bindings['parity_source']['sha256'] and parity.get('protocol_sha256')==bindings['parity_protocol']['sha256'],'Canonical numerical preflight does not match.')
            require(parity_plan['kernel_protocol']==bindings['kernel_protocol'] and parity_plan['diagnostic_receipt']==bindings['kernel_receipt'],'Canonical preflight is bound to a different NF4 candidate.')
            require(parity.get('kernel_protocol_sha256')==bindings['kernel_protocol']['sha256'] and parity.get('diagnostic_receipt_sha256')==bindings['kernel_receipt']['sha256'] and parity_passed(parity,parity_plan),'The no-cache canonical comparison did not pass.')
            for role in ('kernel_worker','parity_worker','authored_worker','authored_1_worker','authored_2_worker','authored_3_worker'):
                worker=records[role]
                require(worker.get('status')=='completed' and worker.get('exit_code')==0 and worker.get('child_exited_before_lease_release') is True,'A qualification worker did not close cleanly.')
            require(authored.get('status')=='completed' and authored.get('finish_reason')=='eos' and bool(authored.get('generated_tokens')),'No complete authored runtime response is retained.')
            self._check_response(authored, authored['input'])
            ledger=records['authored_ledger']
            require(ledger.get('status')=='completed' and ledger.get('completed_count')==4 and len(ledger.get('rows',[]))==4,'The four authored runtime attempts did not close.')
            for index,row in enumerate(ledger['rows']):
                role='authored' if index==0 else f'authored_{index}'
                receipt=records[role+'_receipt'];binding=bindings[role+'_receipt']
                require(row.get('index')==index and row.get('status')=='completed' and row.get('output')==binding['path'] and row.get('response_sha256')==binding['sha256'],'The authored runtime ledger binding differs.')
                require(row.get('worker')==bindings[role+'_worker']['path'] and row.get('worker_sha256')==bindings[role+'_worker']['sha256'],'The authored worker ledger binding differs.')
                require(receipt.get('status')=='completed' and receipt.get('finish_reason')=='eos' and bool(receipt.get('generated_tokens')),'An authored response was incomplete.')
                self._check_response(receipt,receipt['input'])
            require(all(kernel['resources'].get(key)==value for key,value in RESOURCE_FLOORS.items()),'The qualified memory reserves changed.')
            require('.'.join(str(x) for x in sys.version_info[:3])==kernel['python_version'],'The qualified Python runtime changed.')
            for name,version in kernel['runtime_versions'].items():
                require(importlib.metadata.version(name)==version,'The qualified runtime version changed: '+name)
            # Verify all closed dependency bindings without executing their source.
            for dependency in [*kernel['dependencies'],*parity_plan['dependencies']]:
                require(sha(self.repo/dependency['path'])==dependency['sha256'],'A frozen runtime dependency changed.')
            self.worker=self.repo/bindings['worker']['path'];self.child=self.repo/bindings['adapter']['path']
            self.diagnostic=self.repo/bindings['kernel_receipt']['path']
        except (OSError,ValueError,KeyError,TypeError,importlib.metadata.PackageNotFoundError) as error:
            raise Unavailable('Local coaching qualification is unavailable: '+str(error)) from error

    def _check_response(self,result,packet):
        bindings=self.plan['bindings']
        require(result.get('input')==packet,'The model response belongs to a different position.')
        require(result.get('candidate_id')==self.plan['candidate_id'] and result.get('adapter_sha256')==bindings['adapter']['sha256'],'The response candidate does not match the qualified source.')
        require(result.get('nf4_protocol_sha256')==bindings['kernel_protocol']['sha256'] and result.get('diagnostic_receipt_sha256')==bindings['kernel_receipt']['sha256'],'The response NF4 provenance does not match.')
        require(result.get('base_adapter_sha256')==bindings['base_adapter']['sha256'] and result.get('asset_manifest_sha256')==bindings['asset_manifest']['sha256'] and result.get('source_manifest_sha256')==bindings['source_manifest']['sha256'],'The response publisher/source bindings do not match.')
        settings=result.get('settings',{})
        require(all(settings.get(key)==value for key,value in EXPECTED_SETTINGS.items()) and settings.get('use_kv_cache') is False,'The response used an unqualified generation mode.')
        audit=result.get('no_forward_input_audit',{})
        require(audit.get('passed') is True and audit.get('engine_evaluation_or_pv_input') is False and audit.get('selected_move_supplied')==('selected_uci' in packet),'The response input audit does not match.')
        quantization=result.get('quantization',{})
        require(quantization.get('status')=='loaded_and_verified' and quantization.get('actual_decoder_inventory',{}).get('linear4bit_count')==252,'The response has no verified NF4 decoder inventory.')
        require(all(result.get('resource_policy',{}).get(key)==value for key,value in RESOURCE_FLOORS.items()),'The response resource policy differs from the qualified floor.')

    def command(self,job):
        self.verify()
        return [sys.executable,str(self.worker),'--receipt',str(job['worker']),'--maximum-seconds','240',
            '--',str(self.child),'--diagnostic-receipt',str(self.diagnostic),'--input',str(job['input']),'--out',str(job['out'])]

    def decorate_result(self,job,result):
        """Preserve raw receipt bytes; append only separately labelled UI provenance."""
        value=dict(result)
        bindings=self.plan['bindings'];verified=False
        if result.get('status') in {'completed','partial','terminal'}:
            try:
                self._check_response(result,read_record(job['input']))
                verified=True
            except Unavailable as error:
                value.update(status='failed',ui_validation_error=str(error),error=str(error))
        settings=result.get('settings',{})
        value['execution']={'candidate_id':result.get('candidate_id'),'backend':settings.get('backend'),
            'quantization':result.get('quantization'),'protocol_sha256':result.get('nf4_protocol_sha256'),
            'generation_mode':settings.get('generation_mode'),'precision_profile':settings.get('precision_profile'),
            'canonical_provenance':{'response_binding_verified':verified,
                'parity_protocol_sha256':bindings['parity_protocol']['sha256'],
                'parity_receipt_sha256':bindings['parity_receipt']['sha256'],
                'scope':'Same NF4 weights, two authored no-cache prefixes; no BF16 equivalence or coaching-quality claim.'},
            'qualification_sha256':QUALIFICATION_SHA256}
        return value
