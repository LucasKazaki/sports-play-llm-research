"""One short-lived project Python worker under the shared GPU process lease.

The parent retains the OS lock until its child exits. On Windows an owned job
object kills the child tree if this wrapper dies, preventing an orphaned model
from outliving the lease. This is a mutex and lifecycle wrapper, not a scheduler.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from filelock import FileLock,Timeout

ROOT=Path(__file__).resolve().parents[2]
LOCK=ROOT/'data/private/chess-gpu-owner.lock'


class OwnedWindowsJob:
    """Only the child created by this wrapper may be assigned or terminated."""
    def __init__(self,child):
        self.handle=None
        if sys.platform!='win32':return
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_uint64) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class Basic(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),
                ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
                ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
                ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
        class Extended(ctypes.Structure):
            _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),
                ('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        self.kernel=kernel;self.handle=kernel.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        limits=Extended();limits.BasicLimitInformation.LimitFlags=0x2000 # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close();raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(self.handle,wintypes.HANDLE(int(child._handle))):
            self.close();raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


def run_worker(arguments,receipt,maximum_seconds=300,lock_path=LOCK):
    """Run one repo-local Python script. A busy lease never starts a child."""
    receipt=Path(receipt)
    if receipt.exists():raise ValueError('Worker receipt is create-only.')
    if not arguments:raise ValueError('A project Python script is required.')
    script=(ROOT/arguments[0]).resolve()
    if not script.is_relative_to(ROOT) or not script.is_file() or script.suffix!='.py':
        raise ValueError('Worker must be an existing Python script inside this repository.')
    if not 1<=maximum_seconds<=14_400:raise ValueError('Worker deadline must be1..14400seconds.')
    receipt.parent.mkdir(parents=True,exist_ok=True);Path(lock_path).parent.mkdir(parents=True,exist_ok=True)
    log=receipt.with_suffix('.log');started=time.monotonic()
    record={'schema':'chess.gpu-worker.v1','started_at':datetime.now(timezone.utc).isoformat(),
        'script':str(script.relative_to(ROOT)),'arguments_sha256':hashlib.sha256(json.dumps(arguments).encode()).hexdigest(),
        'lock':str(Path(lock_path).resolve()),'status':'not_started','child_pid':None,'exit_code':None,'log':str(log)}
    def save():receipt.write_text(json.dumps(record,indent=2),encoding='utf-8')
    child=None;job=None
    try:
        with FileLock(str(lock_path),timeout=0):
            record['status']='lease_acquired';save()
            try:
                with log.open('xb') as output:
                    # The bootstrap cannot import/run the target until GO. If
                    # this parent dies before assignment, its sole write end
                    # closes and the unassigned child sees EOF and exits.
                    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),
                        '--bootstrap-script',str(script),'--',*arguments[1:]],cwd=ROOT,
                        stdin=subprocess.PIPE,stdout=output,stderr=subprocess.STDOUT)
                    record.update(status='awaiting_job_assignment',child_pid=child.pid);save()
                    job=OwnedWindowsJob(child)
                    child.stdin.write(b'GO\n');child.stdin.flush();child.stdin.close()
                    record.update(status='running',child_pid=child.pid);save()
                    try:
                        code=child.wait(timeout=maximum_seconds)
                        record.update(status='completed' if code==0 else 'failed',exit_code=code)
                    except subprocess.TimeoutExpired:
                        record['status']='deadline'
                        child.terminate()
                        try:child.wait(timeout=10)
                        except subprocess.TimeoutExpired:child.kill();child.wait()
                        record['exit_code']=child.returncode
            except Exception as error:
                record.update(status='failed',error=type(error).__name__+': '+str(error))
                raise
            finally:
                # Also handles Ctrl+C and exceptions after process creation.
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
                if job is not None:job.close()
                record['child_exited_before_lease_release']=child is None or child.poll() is not None
                record['elapsed_seconds']=time.monotonic()-started;save()
    except Timeout:
        record.update(status='busy',elapsed_seconds=time.monotonic()-started);save()
    return record


def bootstrap_script(script,arguments):
    """No target imports before the job-protected parent releases this gate."""
    script=Path(script).resolve()
    if not script.is_relative_to(ROOT) or not script.is_file() or script.suffix!='.py':
        raise ValueError('Bootstrap target must be a project Python script.')
    received=[];ready=threading.Event()
    def read_signal():
        try:received.append(sys.stdin.buffer.readline(64))
        finally:ready.set()
    threading.Thread(target=read_signal,daemon=True).start()
    if not ready.wait(timeout=15) or received!=[b'GO\n']:
        raise SystemExit(76)
    # Keep one process: this process is already assigned to the owned Windows
    # job, so parent death closes the job and kills it and any descendants.
    import runpy
    sys.argv=[str(script),*arguments]
    sys.path[0]=str(script.parent)
    runpy.run_path(str(script),run_name='__main__')


class CooperativeGuard:
    """Check cancellation each call; sample global counters at most once/second."""
    def __init__(self,sampler,reasoner,policy,cancel=None,monotonic=time.monotonic):
        self.sampler=sampler;self.reasoner=reasoner;self.policy=policy;self.cancel=cancel
        self.monotonic=monotonic;self.last=None;self.samples=[]
    def __call__(self):
        if self.cancel and Path(self.cancel).exists():raise RuntimeError('owned cancellation')
        now=self.monotonic()
        if self.last is None or now-self.last>=1:
            sample=self.sampler();stage='start' if self.last is None else 'running'
            issues=self.reasoner(sample,self.policy,stage)
            self.samples.append(asdict(sample));self.last=now
            if issues:raise RuntimeError('resource reserve: '+','.join(issues))


def queen_child(args):
    """Called only as the short-lived leased child, never by the UI process."""
    sys.path.insert(0,str(ROOT/'scripts'))
    from chess_queen_adapter import NativeQueen,read_json
    from chess_native_resources import windows_sample,reasons,Policy,GIB
    if args.out.exists():raise ValueError('Inference receipt is create-only.')
    policy=Policy(start_physical_available_bytes=6*GIB,start_commit_headroom_bytes=10*GIB,
        start_gpu_free_bytes=10*GIB,stop_physical_available_bytes=4*GIB,stop_commit_headroom_bytes=4*GIB)
    guard=CooperativeGuard(windows_sample,reasons,policy,args.cancel)
    result=NativeQueen(device='cuda',guard=guard).generate(read_json(args.input),
        max_new_tokens=args.max_tokens,maximum_seconds=args.maximum_seconds,temperature=0,seed=20260823,
        generation_mode=args.generation_mode,precision_profile=args.precision_profile)
    result['resource_samples']=guard.samples
    result['resource_policy']=asdict(policy)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':result['status'],'finish_reason':result.get('finish_reason'),'out':str(args.out)}))
    return 0 if result['status'] in ('completed','terminal') else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-script',type=Path)
    parser.add_argument('--child-queen',action='store_true')
    parser.add_argument('--input',type=Path);parser.add_argument('--out',type=Path)
    parser.add_argument('--max-tokens',type=int,default=1024)
    parser.add_argument('--generation-mode',choices=['no_cache','cached'],default='no_cache')
    parser.add_argument('--precision-profile',choices=['default_sdpa','math_sdpa_fp32_reduction'],default='math_sdpa_fp32_reduction')
    parser.add_argument('--maximum-seconds',type=float,default=240)
    parser.add_argument('--cancel',type=Path)
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if args.bootstrap_script:
        bootstrap_script(args.bootstrap_script,command)
        return
    if args.child_queen:
        if not args.input or not args.out:parser.error('The child needs --input and --out.')
        raise SystemExit(queen_child(args))
    if not command:
        if not args.input or not args.out:parser.error('Supply one project script, or --input and --out for Queen.')
        command=[str(Path(__file__).relative_to(ROOT)),'--child-queen','--input',str(args.input.resolve()),
            '--out',str(args.out.resolve()),'--max-tokens',str(args.max_tokens),'--maximum-seconds',str(args.maximum_seconds),
            '--generation-mode',args.generation_mode,'--precision-profile',args.precision_profile]
        if args.cancel:command.extend(['--cancel',str(args.cancel.resolve())])
    receipt=args.receipt or ROOT/'data/private/chess-queen-v1/workers'/f'{uuid.uuid4()}.json'
    result=run_worker(command,receipt,args.maximum_seconds+30)
    print(json.dumps(result))
    raise SystemExit(0 if result['status']=='completed' else 75 if result['status']=='busy' else 2)


if __name__=='__main__':main()
