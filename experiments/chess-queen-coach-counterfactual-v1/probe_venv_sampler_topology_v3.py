"""One authored standard-library venv topology probe; no model/backend import."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import shutil
from datetime import datetime,timezone
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from chess_queen_process_lineage_v3 import Tracker


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    code="import json,os,sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[2]);from chess_native_resources import windows_sample;[windows_sample() for _ in range(6)];Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid(),'torch_imported':'torch' in sys.modules,'actual_windows_sample_calls':6}));time.sleep(.2)"
    command=[sys.executable,'-c',code,str((out/'authored-child.json').resolve()),str(ROOT/'scripts')]
    executable=Path(shutil.which('nvidia-smi')).resolve()
    sampler={'executable':{'path':str(executable),'sha256':hashlib.sha256(executable.read_bytes()).hexdigest()},
        'arguments':['nvidia-smi','--query-gpu=memory.total,memory.free','--format=csv,noheader,nounits'],
        'source':{'path':str(ROOT/'scripts/chess_native_resources.py'),'sha256':hashlib.sha256((ROOT/'scripts/chess_native_resources.py').read_bytes()).hexdigest()}}
    intent={'command':command,'resource_sampler_auxiliary':sampler,'started_at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'helper_sha256':hashlib.sha256((ROOT/'scripts/chess_queen_process_lineage_v3.py').read_bytes()).hexdigest(),
        'no_model_calls':True,'no_CUDA_initialization':True,'require_job':False,'note':'CPU probe is outside root GPU job; actual model outer requires job membership.'}
    (out/'intent.json').write_text(json.dumps(intent,indent=2))
    for source in(Path(__file__),ROOT/'scripts/chess_queen_process_lineage_v3.py'):
        shutil.copyfile(source,out/source.name)
    process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW);tracker=None;result={'status':'failed'}
    try:
        tracker=Tracker(process.pid,os.getpid(),require_job=False,launcher_handle=process._handle,sampler=sampler)
        deadline=time.monotonic()+15
        while True:
            tracker.observe()
            if process.poll()is not None:break
            if time.monotonic()>=deadline:raise RuntimeError('Authored CPU probe timeout')
            time.sleep(.005)
        while not all(tracker.os.exited(h)for h in tracker.handles.values()):
            if time.monotonic()>=deadline:raise RuntimeError('CPU auxiliary exit timeout')
            time.sleep(.005)
        receipt=json.loads((out/'authored-child.json').read_text());proof=tracker.proof(receipt)
        if not proof['resource_query_pids']or process.returncode or receipt['actual_windows_sample_calls']!=6 or receipt['torch_imported']or 'torch'in sys.modules:raise RuntimeError('CPU-only probe failed')
        result={'status':'passed','exit_code':process.returncode,'lineage':proof,'no_model_calls':True,'no_CUDA_initialization':True,'actual_windows_sample_calls':6,'torch_imported':False}
    except BaseException as error:
        result.update(error=type(error).__name__+': '+str(error),observed_processes=list(tracker.records.values())if tracker else[])
        raise
    finally:
        if tracker:
            if any(not tracker.os.exited(h)for h in tracker.handles.values()):tracker.terminate_owned()
            tracker.close()
        if process.poll()is None:process.terminate();process.wait(timeout=10)
        (out/'closed.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);main(parser.parse_args().out)
