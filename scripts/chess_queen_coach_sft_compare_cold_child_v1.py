"""Exactly one root-owned cold Queen request; no lease, selection or scoring."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import time

from chess_queen_coach_sft_runtime_v2 import Runtime,checked


def in_job():
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.GetCurrentProcess.restype=wintypes.HANDLE
    api.IsProcessInJob.argtypes=(wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL))
    api.IsProcessInJob.restype=wintypes.BOOL;found=wintypes.BOOL()
    if not api.IsProcessInJob(api.GetCurrentProcess(),None,ctypes.byref(found)):raise ctypes.WinError(ctypes.get_last_error())
    return bool(found.value)


def execute(plan,request,out,parent_cancel,runtime_factory=Runtime,guard_factory=None,job_check=in_job):
    """Callbacks make failure/closure ordering CPU testable without models."""
    if out.exists():raise ValueError('One create-only cold child')
    out.mkdir(parents=True);started=time.monotonic();samples=[];runtime=None
    result={'status':'started','phase':'before_setup','pid':os.getpid(),'parent_pid':os.getppid(),
        'case_id':request['row']['case_id'],'identity':request['identity'],'raw_saved_before_postprocessing':False,
        'maximum_seconds':210,'generation_requests_started':0,'protocol_sha256':request['protocol_sha256'],
        'source_sha256':checked.nf4.base.digest(Path(__file__)),
        'requested_input_sha256':hashlib.sha256(json.dumps(request['row']['input'],sort_keys=True).encode()).hexdigest()}
    save=lambda name,value:checked.nf4.save(out/name,value)
    save('closed.json',result)
    try:
        if not job_check():raise RuntimeError('Cold child must inherit the root-owned Windows job')
        result['in_owned_ancestor_job']=True
        packet,_=checked.nf4.base.input_packet(request['row']['input'])
        if set(request['row']['input'])not in({'fen'},{'fen','selected_uci'}):raise ValueError('Current-only input whitelist')
        if guard_factory is None:
            kernel=checked.nf4.verify_protocol(checked.nf4.binding(plan['model_runtime']['kernel_protocol']))
            base,samples,policy=checked.nf4.guard_for(kernel,out/'request.json')
            result['resource_policy']=policy.__dict__
        else:base,samples=guard_factory()
        def guard():
            if parent_cancel.exists():raise RuntimeError('Owned outer cancellation')
            if time.monotonic()-started>=210:raise RuntimeError('Cold child210s deadline')
            if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['cutoff_utc']):raise RuntimeError('Frozen13UTC cutoff')
            base()
        guard();result.update(phase='model_load_started');save('closed.json',result)
        runtime=runtime_factory(plan['model_runtime'],guard);runtime.memory_journal=out/'memory-lifetime.jsonl'
        load_start=time.monotonic();runtime.load();runtime.load_adapter(request['identity'])
        result['load_seconds']=time.monotonic()-load_start
        runtime.release_inactive('cold_after_exact_adapter_load')
        result.update(phase='generation_started',generation_requests_started=1);save('closed.json',result)
        generation_start=time.monotonic();raw=runtime.infer(request['row'],request['identity'])
        save('raw.json',raw) # Raw must survive a later cleanup/hash/resource failure.
        result.update(raw_sha256=checked.nf4.base.digest(out/'raw.json'),raw_status=raw['status'],
            raw_finish_reason=raw.get('finish_reason'),generation_seconds=time.monotonic()-generation_start,
            raw_saved_before_postprocessing=True,phase='raw_saved_before_postprocessing');save('closed.json',result)
        if raw['status']=='failed':raise RuntimeError('First raw backend failure: '+raw.get('error','unknown'))
        runtime.release_inactive('cold_after_returned_raw_generation')
        result['frozen_storage']=runtime.verify_frozen()
        result.update(status='passed',phase='closed')
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        save('resources.json',samples);save('closed.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('protocol','request','out','parent-cancel'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();plan=checked.nf4.base.read_json(args.protocol)
    if plan['child_implementation_sha256']!=checked.nf4.base.digest(Path(__file__)):raise ValueError('Cold child source changed')
    for item in plan['dependencies']:checked.nf4.binding(item)
    request=checked.nf4.base.read_json(args.request)
    if request['protocol_sha256']!=checked.nf4.base.digest(args.protocol):raise ValueError('Parent request protocol differs')
    if checked.nf4.base.digest(Path(request['identity']['path']))!=request['identity']['sha256']:raise ValueError('Actual condition adapter bytes differ')
    execute(plan,request,args.out,args.parent_cancel)


if __name__=='__main__':main()
