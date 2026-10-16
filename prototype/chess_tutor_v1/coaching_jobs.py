"""Owned asynchronous coaching requests. No model or engine imports.

Production runner configuration is operator-owned and hash-bound. HTTP inputs
cannot set executable paths or generation settings. Fixtures are CPU-only and
identified as interface fixtures in every public result.
"""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


ACTIVE={'starting','running','stopping'}


class JobBusy(RuntimeError):pass
class Unavailable(RuntimeError):pass


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject_nonfinite(token):raise ValueError('Non-finite worker JSON is not a valid UI response.')


def read_record(path):
    try:
        if path.stat().st_size>1_048_576:raise ValueError('Worker response exceeds the UI limit.')
        value=json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=reject_nonfinite)
        if type(value) is not dict:raise ValueError('Worker response must be an object.')
        return value
    except (FileNotFoundError,json.JSONDecodeError):return None


class CoachingJobs:
    def __init__(self,folder,packet_builder,runner=None):
        self.folder=Path(folder);self.packet_builder=packet_builder;self.runner=runner
        self.lock=threading.RLock();self.jobs=OrderedDict();self.blocked=None;self.closing=False

    def health(self):
        with self.lock:
            active=next((job for job in self.jobs.values() if job['status'] in ACTIVE),None)
            return {'configured':self.runner is not None,'fixture':bool(self.runner and self.runner.fixture),
                'status':'blocked' if self.blocked else 'busy' if active else 'ready' if self.runner else 'disabled',
                'reason':self.blocked,'label':self.runner.label if self.runner else 'Local coaching'}

    def start(self,payload):
        packet,context,terminal=self.packet_builder(payload) # Validate before any process or folder allocation.
        with self.lock:
            if self.closing or self.runner is None or self.blocked:raise Unavailable(self.blocked or 'Local coaching is not configured.')
            if any(job['status'] in ACTIVE for job in self.jobs.values()):raise JobBusy('A coaching request is already running.')
            self.runner.verify()
            identifier=uuid.uuid4().hex;folder=self.folder/identifier
            job={'request_id':identifier,'status':'terminal' if terminal else 'starting','context':context,
                'fixture':self.runner.fixture,'backend_label':self.runner.label,'created':time.monotonic(),
                'input':folder/'input.json','out':folder/'response.json','worker':folder/'worker.json',
                # The frozen NF4 child checks out.with_suffix('.CANCEL').
                'cancel':folder/'response.CANCEL','log':folder/'controller.log','process':None,'result':None,'error':None,
                'request_packet':json.loads(json.dumps(packet)),'input_sha256':None,'verification':None}
            self.jobs[identifier]=job
            while len(self.jobs)>32:
                oldest=next(iter(self.jobs))
                if self.jobs[oldest]['status'] in ACTIVE:break
                self.jobs.pop(oldest)
            if terminal:
                job['result']={'status':'terminal','finish_reason':'game_over','input':packet,'raw_text':'','decoded_text':''}
            else:
                folder.mkdir(parents=True,exist_ok=False)
                job['input'].write_text(json.dumps(packet,indent=2),encoding='utf-8')
                job['input_sha256']=sha(job['input'])
                threading.Thread(target=self._watch,args=(job,),daemon=True).start()
            return self._public(job)

    def _public(self,job):
        return {'schema':'chess.tutor-coach-candidate.v1','request_id':job['request_id'],'status':job['status'],
            'fixture':job['fixture'],'backend_label':job['backend_label'],'context':job['context'],
            'elapsed_seconds':round(time.monotonic()-job['created'],1),'result':job['result'],'error':job['error'],
            'verification':job['verification'],
            'poll_url':'/api/coach/'+job['request_id']}

    def _draft_checks(self,job,result,worker,base_result):
        """Separate CPU evidence after worker closure; never alter the raw result."""
        from draft_checks_v1 import audit_bytes, original_profile, unavailable
        try:
            qualified=(job['status']=='completed' and original_profile(result,worker or {},
                job['fixture'],Path(getattr(self.runner,'qualification_path','')).name))
            def bounded(path):
                with path.open('rb') as handle:return handle.read(1_048_577)
            value=audit_bytes(bounded(job['out']),bounded(job['input']),job['input_sha256'],
                job['request_packet'],job['context'],base_result,qualified=qualified)
        except Exception as error:
            value=unavailable('The draft or request could not be bound for rule checks.')
            value['error_type']=type(error).__name__
        value['request_id']=job['request_id']
        try:
            with job['out'].with_name('draft-checks-v1.json').open('x',encoding='utf-8',newline='\n') as handle:
                handle.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
        except OSError:
            value=unavailable('Rule checks could not be retained. The original draft is still available.')
            value['request_id']=job['request_id']
        return value

    def get(self,identifier):
        with self.lock:
            if identifier not in self.jobs:raise KeyError(identifier)
            job=self.jobs[identifier]
            if job['status']=='starting':
                receipt=read_record(job['worker'])
                if receipt and receipt.get('status')=='running':job['status']='running'
            return self._public(job)

    def cancel(self,identifier):
        with self.lock:
            if identifier not in self.jobs:raise KeyError(identifier)
            job=self.jobs[identifier]
            if job['status'] in ACTIVE:
                job['cancel'].parent.mkdir(parents=True,exist_ok=True)
                job['cancel'].write_text('{"owned_ui_cancellation":true}',encoding='utf-8')
                job['status']='stopping'
            return self._public(job)

    def _watch(self,job):
        try:
            with self.lock:
                if job['status']=='stopping':job['status']='cancelled';return
                command=self.runner.command(job)
                output=job['log'].open('xb')
                try:
                    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=output,
                        stderr=subprocess.STDOUT,cwd=getattr(self.runner,'repo',Path(__file__).parent))
                except Exception:output.close();raise
                job['process']=process
            deadline=time.monotonic()+self.runner.maximum_seconds+15
            while process.poll() is None:
                if time.monotonic()>deadline:
                    job['cancel'].write_text('{"owned_ui_deadline":true}',encoding='utf-8')
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
                    job['error']='The coaching request reached its time limit.'
                    break
                time.sleep(.05)
            output.close()
            result=read_record(job['out']);worker=read_record(job['worker']);base_result=result
            if result and hasattr(self.runner,'decorate_result'):
                result=self.runner.decorate_result(job,result)
            with self.lock:
                job['result']=result
                if worker and worker.get('status')=='busy':job['status']='busy'
                elif job['status']=='stopping':job['status']='cancelled'
                elif process.returncode == 0 and result and result.get('status') in {'completed','terminal'}:job['status']=result['status']
                elif result and result.get('status')=='partial':job['status']='partial'
                else:
                    job['status']='failed';job['error']=job['error'] or (result or {}).get('error') or 'The local model could not finish this request.'
                if result:
                    job['verification']=self._draft_checks(job,result,worker,base_result)
                error=(str((result or {}).get('error',''))+' '+str(job['error'] or '')).lower()
                if any(marker in error for marker in ('resource reserve','out of memory','cuda error')):
                    self.blocked='Local coaching is unavailable until this runtime resource failure is reviewed.'
                elif result and result.get('ui_validation_error'):
                    self.blocked='Local coaching is unavailable until its runtime binding is reviewed.'
        except Exception as error:
            with self.lock:job.update(status='failed',error=type(error).__name__+': '+str(error))
        finally:
            process=job.get('process')
            if process is not None and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()

    def close(self):
        with self.lock:
            self.closing=True
            active=[job for job in self.jobs.values() if job['status'] in ACTIVE]
            for job in active:self.cancel(job['request_id'])
        for job in active:
            process=job.get('process')
            if process is not None and process.poll() is None:
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
