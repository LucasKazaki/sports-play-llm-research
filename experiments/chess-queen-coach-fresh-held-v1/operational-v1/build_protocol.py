"""Create a prospective protocol from a root-sealed metadata spec; never run it.

No corpus, references, raw answers or inventory payload is opened by this builder.
The actual operation and its independent closed audit require separate admission.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PATHS={'driver':HERE/'run_once.py','builder':Path(__file__),'tests':HERE/'test_operational.py',
    'selector':HERE.parent/'selection_v2.py','rules':HERE.parent/'reference_rules_v1.py',
    'teacher':REPO/'scripts/chess_queen_coach_counterfactual_teacher_v1.py',
    'native':REPO/'scripts/chess_queen_adapter.py'}


def driver():
    spec=importlib.util.spec_from_file_location('_fresh_protocol_source',HERE/'run_once.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def build(spec,*,module=None):
    d=module or driver()
    d.require(type(spec) is dict and set(spec)=={'data','inventory_summary','corpus_attestations','admit_by_utc'},
        'Complete latest root metadata spec required; pending placeholders are not a protocol')
    d.require(set(spec['data'])==d.DATA,'All exact data/receipt roles required')
    # Validate syntax and resolved path membership, but do not read data payloads.
    for item in spec['data'].values():d.path_for(item,d.ROOTS)
    sources={}
    for name,path in PATHS.items():
        path=path.resolve();raw=path.read_bytes()
        sources[name]={'root':'repo','path':path.relative_to(REPO).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()}
    d.require(all(sources[name]['sha256']==value for name,value in
        [('selector',d.CORE),('rules',d.RULES),('teacher',d.TEACHER),('native',d.NATIVE)]),'Pinned scientific source changed')
    value={'schema':'chess.fresh-held-cpu-protocol.v1','scope':'one_root_owned_cpu_selection_only',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'maximum_seconds':90,'cutoff_utc':d.CUTOFF,
        'memory_gib':{'startup_commit':8,'startup_physical':4,'running_commit':6,'running_physical':4},
        'source_sha256':sources['driver']['sha256'],'sources':sources,
        'versions':{'python':'.'.join(map(str,sys.version_info[:3])),
            'chess':metadata.version('chess'),'filelock':metadata.version('filelock')},**spec}
    d.validate_protocol(value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=driver()
    d.require(a.spec.stat().st_size<=1024**2,'Metadata spec too large')
    value=build(d.decode(a.spec.read_bytes()),module=d);d.write_new(a.out,value)
    print(json.dumps({'status':'prospective_protocol_created_not_dispatched','sha256':hashlib.sha256(a.out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
