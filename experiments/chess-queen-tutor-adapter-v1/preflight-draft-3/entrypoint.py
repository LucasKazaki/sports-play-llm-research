"""Single-request, inference-only tuned Queen entrypoint. Disabled in the UI.

Only root dispatches a reviewed preactivation protocol through the shared GPU
worker. Import and CPU contract checks never load Torch or a model. No trainer,
evaluator, corpus, references, output repair, or checkpoint discovery is used.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import importlib.metadata as metadata
import math
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'coach-v2-step64'
CANDIDATE = 'queen-pawn-8/nf4-coach-sft-v2'
PROTOCOL_SCHEMA = 'chess.queen-tutor-entrypoint-protocol.v1'
ENVELOPE_SCHEMA = 'chess.queen-tutor-trained-envelope.v1'
FIXED = {
    'runtime': '7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349',
    'selection': '79abaea0cba0a292ef17e2686dbb69c72e568bdefb61848d64a38cc6ee15e714',
    'checkpoint': '73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e',
    'training_protocol': '5364c4c9a4b744770c5f0c9c617d6edc09730a0aa0dee2e3c0f55e6a80df6168',
    'native': 'e8f1c2d9d9fb1270e49288d9e39732cf5c2f521fe2e07962015fc776e8bb7ea0',
    'nf4': '0305b7af2661bc9554171774f49f1b14e5fc20767bbf01416e2e2497313367a8',
    'kernel_protocol': '515cf1d0ecabc5e058fbe6d8ac6ef04375cf9e9e5b8bd292dfcc80acf70fe83c',
    'kernel_receipt': '85cfb012f98c627b5d1c8a4b317ed554d683bb530de395b5f7f0df09e20ba7a9',
}
SETTINGS = {'max_new_tokens':1024,'maximum_seconds':180,'temperature':0,
    'seed':20260823,'generation_mode':'no_cache','precision_profile':'math_sdpa_fp32_reduction'}
RESOURCES = {'start_physical_available_bytes':6*1024**3,'start_commit_headroom_bytes':10*1024**3,
    'start_gpu_free_bytes':10*1024**3,'stop_physical_available_bytes':4*1024**3,
    'stop_commit_headroom_bytes':4*1024**3,'stop_gpu_free_bytes':1024**3}
VERSIONS = {'torch':'2.8.0+cu128','transformers':'5.19.0','bitsandbytes':'0.50.2',
    'peft':'0.21.2','accelerate':'1.15.0','safetensors':'0.8.0','numpy':'2.5.4'}
MAXIMUM_SECONDS = 210
ROLES = set(FIXED) | {'checkpoint_metadata','qlora','materialize','resource','worker','assets','sources','diagnostic_protocol'}
HEX = re.compile(r'[0-9a-f]{64}')
FORMATTER_SHA='daf763cc712a95442d65416a913cf37fa20f85d27345b2d96a98e1d826de83cc'


def require(value, message):
    if not value:raise ValueError(message)


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):value.update(chunk)
    return value.hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))


def read_json(path, maximum=1024**2):
    with Path(path).open('rb') as stream:raw=stream.read(maximum+1)
    require(0<len(raw)<=maximum,'JSON exceeds bounded input size.')
    def pairs(values):
        result={}
        for key,value in values:
            require(key not in result,'Duplicate JSON key.');result[key]=value
        return result
    def constant(value):raise ValueError('Nonfinite JSON value: '+value)
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    require(type(value) is dict,'Expected a JSON object.')
    return value


def bound(repo,item):
    require(type(item) is dict and set(item)=={'path','sha256'},'Malformed file binding.')
    require(type(item['path']) is str and type(item['sha256']) is str and HEX.fullmatch(item['sha256']),'Invalid file binding.')
    path=(Path(repo)/item['path']).resolve()
    require(path.is_relative_to(Path(repo).resolve()) and path.is_file(),'Binding is outside the repository or missing.')
    require(digest(path)==item['sha256'],'Pinned file changed: '+item['path'])
    return path


def dependency(repo,item,source_manifest):
    """Only pinned upstream source may live outside this repository."""
    require(type(item) is dict and set(item)=={'path','sha256'} and type(item['path']) is str
        and type(item['sha256']) is str and HEX.fullmatch(item['sha256']),'Malformed dependency binding.')
    path=(Path(repo)/item['path']).resolve()
    if path.is_relative_to(Path(repo).resolve()):return bound(repo,item)
    checkout=Path(source_manifest.get('checkout','')).resolve()
    require(path.is_relative_to(checkout),'Dependency is outside the pinned source checkout.')
    relative=path.relative_to(checkout).as_posix()
    record=source_manifest.get('files',{}).get(relative,{})
    # The frozen QLoRA diagnostic additionally pins this official formatter;
    # the earlier inference-only source manifest predates its use.
    expected=FORMATTER_SHA if relative=='utils/instance_format.py' else record.get('sha256')
    require(expected==item['sha256'] and path.is_file() and digest(path)==item['sha256'],
        'External dependency is not an exact pinned source/formatter file.')
    return path


def verify_protocol(repo,path,expected_sha256):
    require(type(expected_sha256) is str and HEX.fullmatch(expected_sha256) and digest(path)==expected_sha256,'Entrypoint protocol bytes changed.')
    plan=read_json(path)
    require(plan.get('schema')==PROTOCOL_SCHEMA and plan.get('profile_id')==PROFILE,'Unknown entrypoint protocol/profile.')
    require(plan.get('implementation_sha256')==digest(Path(__file__)),'Entrypoint source changed.')
    require(plan.get('scope')=='root_dispatched_pre_activation_qualification_or_admitted_single_request','Wrong execution scope.')
    require(canonical(plan.get('generation'))==canonical(SETTINGS) and canonical(plan.get('resources'))==canonical(RESOURCES),'Frozen generation/resource policy changed.')
    require(type(plan.get('outer_seconds')) is int and plan['outer_seconds']==MAXIMUM_SECONDS,'Outer deadline changed.')
    require(plan.get('python_version')=='3.12.2' and '.'.join(map(str,sys.version_info[:3]))==plan['python_version'],'Python version changed.')
    require(plan.get('runtime_versions')==VERSIONS,'Version contract changed.')
    for name,version in VERSIONS.items():require(metadata.version(name)==version,'Runtime package changed: '+name)
    bindings=plan.get('bindings')
    require(type(bindings) is dict and set(bindings)==ROLES,'Incomplete or extra dependency roles.')
    for role,expected in FIXED.items():require(bindings[role].get('sha256')==expected,'Fixed candidate changed: '+role)
    paths={role:bound(repo,item) for role,item in bindings.items()}
    # Verify source/package dependency bytes only. Never follow training data or
    # heldout reference bindings merely because a protocol mentions their paths.
    for role in ('kernel_protocol','diagnostic_protocol'):
        for item in read_json(paths[role]).get('dependencies',[]):dependency(repo,item,read_json(paths['sources']))
    training=read_json(paths['training_protocol'])
    require(canonical(training['generation'])==canonical(SETTINGS),'Trained generation settings differ.')
    selection=read_json(paths['selection']);identity=read_json(paths['checkpoint_metadata'])
    require(selection.get('status')=='selected' and selection.get('protocol_sha256')==FIXED['training_protocol'],'Selection is not closed/source-bound.')
    require(canonical(selection.get('selected'))==canonical(identity),'Selection/checkpoint metadata mismatch.')
    require(identity.get('sha256')==FIXED['checkpoint'] and identity.get('step')==64
        and identity.get('presentations')==512 and identity.get('parameter_count')==1916928
        and identity.get('candidate_id')==CANDIDATE and identity.get('source_sha256')==FIXED['runtime'],'Wrong selected adapter identity.')
    require(identity.get('path')==str(paths['checkpoint']).replace('\\','/'),'Selected adapter path differs.')
    return plan,training,identity,paths


def packet(value):
    # This audited module has no model/engine imports or load on import.
    from chess_queen_adapter import input_packet
    return input_packet(value)


def validate_raw(raw,current,identity,plan):
    require(type(raw) is dict and raw.get('status') in {'completed','partial','terminal','failed'},'No typed raw inference response.')
    require(canonical(raw.get('input'))==canonical(current),'Raw response belongs to a different input.')
    require(raw.get('candidate_id')==CANDIDATE and raw.get('base_candidate_id')=='queen-pawn-8/native-nf4-v2','Raw candidate identity differs.')
    require(canonical(raw.get('trained_adapter'))==canonical(identity),'Raw trained adapter differs.')
    for field,role in (('adapter_sha256','runtime'),('base_generator_source_sha256','native'),
                       ('base_nf4_source_sha256','nf4'),('nf4_protocol_sha256','kernel_protocol'),('kernel_receipt_sha256','kernel_receipt')):
        require(raw.get(field)==plan['bindings'][role]['sha256'],'Raw source binding differs: '+field)
    for field,role in (('asset_manifest_sha256','assets'),('source_manifest_sha256','sources')):
        require(raw.get(field)==plan['bindings'][role]['sha256'],'Raw publisher binding differs.')
    settings=raw.get('settings',{})
    require(type(settings) is dict,'Raw settings are not an object.')
    require(all((type(settings.get(key)) in (int,float) and math.isfinite(settings[key]) and settings[key]==value)
        if type(value) in (int,float) else settings.get(key)==value for key,value in SETTINGS.items())
        and settings.get('use_kv_cache') is False,'Raw generation settings differ.')
    audit=raw.get('no_forward_input_audit',{})
    require(type(audit) is dict,'Raw input audit is not an object.')
    require(audit.get('passed') is True and audit.get('engine_evaluation_or_pv_input') is False
        and audit.get('selected_move_supplied')==('selected_uci' in current),'Raw input audit differs.')
    quant=raw.get('quantization',{})
    require(type(quant) is dict and type(quant.get('base_decoder_inventory_before_lora')) is dict,'Raw quantization is not an object.')
    require(quant.get('base_decoder_inventory_before_lora',{}).get('linear4bit_count')==252
        and quant.get('actual_lora_dtype')=='float32' and quant.get('actual_lora_parameters')==1916928,'Raw quantized/LoRA inventory differs.')
    if raw['status'] in {'completed','partial'}:
        parsed=raw.get('parsed')
        require(type(parsed) is dict and parsed.get('engine_interventions')==0
            and parsed.get('rule_replacements')==0 and parsed.get('fallback_used') is False,'Raw fallback/intervention metadata differs.')


def serialized(value):return json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n'


def raw_digest(value):return hashlib.sha256(serialized(value).encode('utf-8')).hexdigest()


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(serialized(value));stream.flush();os.fsync(stream.fileno())


def append(path,value):
    with Path(path).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def runtime_factory(training,guard):
    from chess_queen_coach_sft_runtime_v2 import Runtime
    return Runtime(training,guard)


def guard_factory(cancel):
    # Import only after source/version/input checks; do not modify the worker.
    path=ROOT/'experiments/chess-queen-v1/gpu_worker.py'
    spec=importlib.util.spec_from_file_location('tuned_tutor_owned_guard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from chess_native_resources import Policy,windows_sample,reasons
    policy=Policy(**RESOURCES,maximum_owned_request_seconds=MAXIMUM_SECONDS)
    guard=module.CooperativeGuard(windows_sample,reasons,policy,cancel)
    return guard,guard.samples,asdict(policy)


def run_request(repo,protocol,protocol_sha,input_path,out,*,make_runtime=None,make_guard=None):
    """One process/one request. Injection hooks exist only for CPU source tests."""
    out=Path(out);raw_path=out.with_name(out.stem+'.raw.json')
    intent=out.with_name(out.stem+'.intent.json');events=out.with_name(out.stem+'.events.jsonl')
    memory=out.with_name(out.stem+'.memory.jsonl');cancel=out.with_suffix('.CANCEL')
    require(out.parent.is_dir(),'The owned attempt directory must already exist.')
    require(not any(path.exists() for path in (out,raw_path,intent,events,memory)),'Attempt is create-only; no replay.')
    write_new(intent,{'schema':'chess.queen-tutor-intent.v1','profile_id':PROFILE,
        'input_sha256':digest(input_path),'protocol_sha256':protocol_sha,'at':datetime.now(timezone.utc).isoformat()})
    started=time.monotonic();phase='validate';raw=None;policy=None;samples=[];storage=None;identity=None;plan=None
    envelope={'schema':ENVELOPE_SCHEMA,'status':'failed','error':None,'raw_response':None,'entrypoint':{}}
    def event(status):append(events,{'phase':phase,'status':status,'at':datetime.now(timezone.utc).isoformat()})
    try:
        event('started');plan,training,identity,paths=verify_protocol(repo,protocol,protocol_sha)
        current,board=packet(read_json(input_path,maximum=32768))
        require(not board.is_game_over(claim_draw=False),'Current board is already game over.')
        event('completed');phase='resource_start';event('started')
        base_guard,samples,policy=(make_guard or guard_factory)(cancel)
        def guard():
            require(time.monotonic()-started<MAXIMUM_SECONDS,'Owned entrypoint deadline reached.')
            if cancel.exists():raise RuntimeError('owned cancellation')
            base_guard()
        guard();event('completed');phase='load';event('started')
        runtime=(make_runtime or runtime_factory)(training,guard);runtime.memory_journal=memory
        runtime.load();guard();event('completed');phase='load_selected_adapter';event('started')
        runtime.load_adapter(identity);guard();event('completed');phase='infer';event('started')
        raw=runtime.infer({'input':current},identity)
        # Save the returned dictionary before cleanup or validation can fail.
        write_new(raw_path,raw);event('returned_and_raw_retained')
        validate_raw(raw,current,identity,plan)
        if raw['status']=='failed':raise RuntimeError(raw.get('error') or 'Raw generator failed.')
        phase='release_inactive';event('started');runtime.release_inactive('after_retained_tutor_generation');event('completed')
        phase='verify_frozen';event('started');storage=runtime.verify_frozen()
        require(storage.get('identical') is True,'Frozen storage changed.');event('completed')
        envelope['status']=raw['status']
    except Exception as error:
        envelope['error']=type(error).__name__+': '+str(error)
        event('failed')
    envelope['raw_response']=raw
    envelope['entrypoint']={'profile_id':PROFILE,'source_sha256':digest(Path(__file__)),
        'protocol_sha256':protocol_sha,'selection_sha256':FIXED['selection'],'fixed_checkpoint_sha256':FIXED['checkpoint'],
        'trained_identity':identity,'resource_policy':policy,'resource_samples':samples,'frozen_storage':storage,
        'raw_response_sha256':digest(raw_path) if raw_path.exists() else None,
        'elapsed_seconds':time.monotonic()-started,'outer_seconds':MAXIMUM_SECONDS,'failed_phase':phase if envelope['error'] else None,
        'scope':'Entry-point software provenance only; no whole-prose factuality, strength, expert or tutor acceptance.'}
    write_new(out,envelope)
    return envelope


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','input','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args()
    result=run_request(ROOT,args.protocol,args.protocol_sha256,args.input,args.out)
    print(json.dumps({'status':result['status'],'profile_id':PROFILE,'out':str(args.out)}))
    raise SystemExit(0 if result['status'] in ('completed','terminal') else 2)


if __name__=='__main__':main()
