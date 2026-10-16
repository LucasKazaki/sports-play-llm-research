"""One authored standard-library venv topology probe; no model/backend import."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from chess_queen_process_lineage_v1 import Tracker


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    code="import json,os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid(),'torch_imported':'torch' in sys.modules}));time.sleep(1)"
    command=[sys.executable,'-c',code,str((out/'authored-child.json').resolve())]
    intent={'command':command,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'helper_sha256':hashlib.sha256((ROOT/'scripts/chess_queen_process_lineage_v1.py').read_bytes()).hexdigest(),
        'no_model_calls':True,'require_job':False,'note':'CPU probe is outside root GPU job; actual model outer requires job membership.'}
    (out/'intent.json').write_text(json.dumps(intent,indent=2))
    for source in(Path(__file__),ROOT/'scripts/chess_queen_process_lineage_v1.py'):
        shutil.copyfile(source,out/source.name)
    process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW);tracker=None;result={'status':'failed'}
    try:
        tracker=Tracker(process.pid,os.getpid(),require_job=False,launcher_handle=process._handle)
        deadline=time.monotonic()+5
        while True:
            tracker.observe()
            if process.poll()is not None:break
            if time.monotonic()>=deadline:raise RuntimeError('Authored CPU probe timeout')
            time.sleep(.02)
        while not all(tracker.os.exited(h)for h in tracker.handles.values()):
            if time.monotonic()>=deadline:raise RuntimeError('CPU auxiliary exit timeout')
            time.sleep(.02)
        receipt=json.loads((out/'authored-child.json').read_text());proof=tracker.proof(receipt)
        if process.returncode or receipt['torch_imported']or 'torch'in sys.modules:raise RuntimeError('CPU-only probe failed')
        result={'status':'passed','exit_code':process.returncode,'lineage':proof,'no_model_calls':True,'torch_imported':False}
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
