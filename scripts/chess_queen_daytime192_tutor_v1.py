"""Inference-only fixed192 preview child. Importing this module loads no model.

Preactivation calls require an independently reviewed exact protocol. Ordinary
UI admission is a separate metadata decision. Native Runtime.infer dictionaries
are retained unchanged; no trainer, evaluator, corpus or reference is opened.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata as metadata
import math
from pathlib import Path
import sys
import time

import chess_queen_coach_tutor_v1 as safe

ROOT=Path(__file__).resolve().parents[1]
PROFILE='queen-daytime192-research-preview.v1'
CANDIDATE='queen-pawn-8/nf4-coach-counterfactual-v1'
PROTOCOL_SCHEMA='chess.daytime192-preview-protocol.v1'
ENVELOPE_SCHEMA='chess.daytime192-preview-envelope.v1'
CUTOFF='2026-10-16T22:00:00+00:00'
MAXIMUM_SECONDS=210
SETTINGS=dict(safe.SETTINGS)
RESOURCES=dict(safe.RESOURCES)
FIXED={**safe.FIXED,
    'runtime':'29f148855279fe0243bb4fbedac12057ab9d43cd6fe1c12a904606d4ca8f460b',
    'qualified_runtime':'7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349',
    'selection':'27baa5c33229dae385b98cbbc131890b0baef883f395b4a6149c064ddbc4276a',
    'checkpoint':'27d6b171c98a96257e2a267a340bdb981cebc1c5114cd54d87d7973f80ac714b',
    'training_protocol':'d9b025cb372fcc6e78a797c717998a385d5273c0f127bf468d8503e3d2ff72af',
    'worker':'fe4ce0abb0f6be934f2b78681115ec0aa0c9c85e2ef54a6955dc2e6778103ae8',
    'helpers':'90f35841b875853f5572ed9a7a5439565277a81ba0b08d493423992569bcc697',
    'original_worker':'1164d8fd1dbc59221a7d51ce410bb5e9a3109998fd3b6f9d00db071d237948c0'}
ROLES=set(FIXED)|{'checkpoint_metadata','qlora','materialize','resource','assets',
    'sources','diagnostic_protocol','formatter_manifest','preview_manifest'}
PREVIEW_FILES=('scripts/chess_queen_daytime192_tutor_v1.py',
    'prototype/chess_tutor_daytime192_v1/runner.py','prototype/chess_tutor_daytime192_v1/server.py',
    'prototype/chess_tutor_daytime192_v1/static/index.html','prototype/chess_tutor_daytime192_v1/static/preview.css',
    'tests/test_chess_tutor_daytime192_v1.py','experiments/chess-tutor-daytime192-v1/prepare_protocol.py')
UI_FILES=tuple('prototype/chess_tutor_v1/'+name for name in ('server.py','coaching_jobs.py',
    'draft_checks_v1.py','static/app.js','static/coaching.js','static/style.css','static/coaching.css'))
require=safe.require
digest=safe.digest
canonical=safe.canonical
read_json=safe.read_json
write_new=safe.write_new


def inside(repo,item):
    path=safe.bound(repo,item)
    declared=(Path(repo)/item['path']).absolute()
    require(declared==path,'Symlink substitution is not allowed.')
    return path


def before_cutoff(now=None):
    now=now or datetime.now(timezone.utc)
    require(now.tzinfo is not None and now<datetime.fromisoformat(CUTOFF),
        'The reviewed daytime authority has ended.')


def packet(value):
    require(type(value) is dict and set(value)<={'fen','selected_uci'} and 'fen' in value,
        'Preview accepts current FEN and an optional legal selected move only.')
    current,board=safe.packet(value)
    # Native normalization includes an empty prior-history field. No prior
    # board, teacher field or study path is added to the model packet.
    return current,board


def verify_protocol(repo,path,expected_sha256,*,check_environment=True):
    require(type(expected_sha256) is str and safe.HEX.fullmatch(expected_sha256)
        and digest(path)==expected_sha256,'Preview protocol bytes changed.')
    plan=read_json(path)
    require(plan.get('schema')==PROTOCOL_SCHEMA and plan.get('profile_id')==PROFILE,
        'Unknown preview protocol/profile.')
    require(plan.get('implementation_sha256')==digest(__file__), 'Preview child source changed.')
    require(plan.get('scope')=='root_qualification_or_explicitly_admitted_research_preview', 'Wrong execution scope.')
    require(plan.get('cutoff_utc')==CUTOFF and plan.get('outer_seconds')==210
        and plan.get('worker_seconds_after_go')==240 and plan.get('runner_seconds')==270,
        'Preview time bounds changed.')
    require(canonical(plan.get('generation'))==canonical(SETTINGS)
        and canonical(plan.get('resources'))==canonical(RESOURCES),'Frozen settings changed.')
    require(plan.get('runtime_versions')==safe.VERSIONS and plan.get('python_version')=='3.12.2',
        'Version contract changed.')
    if check_environment:
        require('.'.join(map(str,sys.version_info[:3]))=='3.12.2','Python version changed.')
        for name,version in safe.VERSIONS.items():require(metadata.version(name)==version,'Package changed: '+name)
    bindings=plan.get('bindings')
    require(type(bindings) is dict and set(bindings)==ROLES,'Incomplete or extra binding roles.')
    for role,expected in FIXED.items():require(bindings[role].get('sha256')==expected,'Fixed identity changed: '+role)
    paths={role:inside(repo,item) for role,item in bindings.items()}
    sources=read_json(paths['sources']);formatter=read_json(paths['formatter_manifest'])
    require(formatter.get('schema')=='chess.tuned-tutor-upstream-formatter-manifest.v1'
        and formatter.get('parent_source_manifest_sha256')==bindings['sources']['sha256']
        and formatter.get('diagnostic_protocol_sha256')==bindings['diagnostic_protocol']['sha256']
        and formatter.get('checkout')==sources.get('checkout')
        and formatter.get('files')=={'utils/instance_format.py':{'sha256':safe.FORMATTER_SHA}},'Formatter binding differs.')
    sources={**sources,'files':{**sources.get('files',{}),**formatter['files']}}
    for role in ('kernel_protocol','diagnostic_protocol'):
        for item in read_json(paths[role]).get('dependencies',[]):safe.dependency(repo,item,sources)
    manifest=read_json(paths['preview_manifest'])
    require(manifest.get('schema')=='chess.daytime192-preview-sources.v1'
        and type(manifest.get('files')) is list and manifest['files'],'Missing preview source closure.')
    expected=set(PREVIEW_FILES+UI_FILES)|{item['path'] for name,item in bindings.items()
        if name not in {'selection','checkpoint','checkpoint_metadata','training_protocol','kernel_receipt','preview_manifest'}}
    names=[item.get('path') for item in manifest['files']]
    require(len(names)==len(set(names)) and set(names)==expected,'Preview source closure is incomplete or duplicated.')
    for item in manifest['files']:inside(repo,item)
    training=read_json(paths['training_protocol']);selection=read_json(paths['selection'])
    identity=read_json(paths['checkpoint_metadata'])
    require(training.get('generation')==SETTINGS,'Training generation differs.')
    require(selection.get('status')=='selected' and selection.get('protocol_sha256')==FIXED['training_protocol']
        and canonical(selection.get('selected'))==canonical(identity),'Selection is not closed and fixed.')
    require(identity.get('step')==192 and identity.get('presentations')==1536
        and identity.get('parent_presentations')==512 and identity.get('parameter_count')==1916928
        and identity.get('sha256')==FIXED['checkpoint'] and identity.get('candidate_id')==CANDIDATE
        and identity.get('source_sha256')==FIXED['runtime']
        and identity.get('path')==paths['checkpoint'].as_posix(),'Wrong selected192 identity.')
    require(training.get('warm_start')==identity.get('warm_start')
        and identity['warm_start'].get('sha256')==safe.FIXED['checkpoint'],'Wrong fixed64 warm start.')
    # The runtime needs no dataset/ref path. Construct its minimal inference plan
    # instead of passing the full scientific training protocol into the worker.
    runtime_plan={'generation':dict(SETTINGS),'training':{'seed':training['training']['seed']},
        'warm_start':training['warm_start'],'kernel_protocol':bindings['kernel_protocol'],
        'kernel_receipt':bindings['kernel_receipt']}
    return plan,runtime_plan,identity,paths


def validate_raw(raw,current,identity,plan):
    require(type(raw) is dict and raw.get('status') in {'completed','partial','terminal','failed'},'Missing typed native response.')
    require(canonical(raw.get('input'))==canonical(current),'Native input differs.')
    require(raw.get('candidate_id')==CANDIDATE and raw.get('base_candidate_id')=='queen-pawn-8/native-nf4-v2'
        and canonical(raw.get('trained_adapter'))==canonical(identity),'Native trained identity differs.')
    for field,role in (('adapter_sha256','runtime'),('qualified_runtime_source_sha256','qualified_runtime'),
        ('base_generator_source_sha256','native'),('base_nf4_source_sha256','nf4'),
        ('nf4_protocol_sha256','kernel_protocol'),('kernel_receipt_sha256','kernel_receipt'),
        ('asset_manifest_sha256','assets'),('source_manifest_sha256','sources')):
        require(raw.get(field)==plan['bindings'][role]['sha256'],'Native source differs: '+field)
    require(raw.get('warm_start')==identity.get('warm_start'),'Native warm start differs.')
    settings=raw.get('settings',{})
    require(type(settings) is dict and settings.get('use_kv_cache') is False,'Native cache mode differs.')
    for key,value in SETTINGS.items():
        actual=settings.get(key)
        require((type(actual) in (int,float) and math.isfinite(actual) and actual==value)
            if type(value) in (int,float) else actual==value,'Native generation differs: '+key)
    audit=raw.get('no_forward_input_audit',{})
    require(type(audit) is dict and audit.get('passed') is True
        and audit.get('engine_evaluation_or_pv_input') is False
        and audit.get('selected_move_supplied')==('selected_uci' in current),'Native input audit differs.')
    quant=raw.get('quantization',{})
    require(type(quant) is dict and quant.get('actual_lora_dtype')=='float32'
        and quant.get('actual_lora_parameters')==1916928
        and type(quant.get('base_decoder_inventory_before_lora')) is dict
        and quant['base_decoder_inventory_before_lora'].get('linear4bit_count')==252,'Native quantization differs.')
    if raw['status'] in {'completed','partial'}:
        p=raw.get('parsed',{})
        require(type(p) is dict and p.get('engine_interventions')==0 and p.get('rule_replacements')==0
            and p.get('fallback_used') is False,'Native intervention metadata differs.')


def runtime_factory(plan,guard):
    from chess_queen_coach_counterfactual_runtime_v1 import Runtime
    return Runtime(plan,guard)


def run_request(repo,protocol,protocol_sha,input_path,out,*,make_runtime=None,make_guard=None):
    """Injection hooks are for authored CPU tests, never exposed by CLI/HTTP."""
    started=time.monotonic() # Before any native/model import or cold load.
    out=Path(out);raw_path=out.with_name(out.stem+'.raw.json')
    intent=out.with_name(out.stem+'.intent.json');events=out.with_name(out.stem+'.events.jsonl')
    memory=out.with_name(out.stem+'.memory.jsonl');cancel=out.with_suffix('.CANCEL')
    require(out.parent.is_dir() and not any(p.exists() for p in (out,raw_path,intent,events,memory)),
        'Owned attempt must be create-only in an existing directory.')
    input_bytes,input_sha=safe.input_snapshot(input_path)
    write_new(intent,{'schema':'chess.daytime192-preview-intent.v1','input_sha256':input_sha,
        'protocol_sha256':protocol_sha,'profile_id':PROFILE,'at':datetime.now(timezone.utc).isoformat()})
    phase='validate';raw=None;policy=None;samples=[];storage=None;identity=None
    envelope={'schema':ENVELOPE_SCHEMA,'status':'failed','error':None,'raw_response':None}
    def event(status):safe.append(events,{'phase':phase,'status':status,'at':datetime.now(timezone.utc).isoformat()})
    try:
        event('started');before_cutoff();plan,runtime_plan,identity,paths=verify_protocol(repo,protocol,protocol_sha)
        current,board=packet(safe.decode_json(input_bytes,32768))
        require(not board.is_game_over(claim_draw=False),'Current board is already game over.');event('completed')
        phase='resource_start';event('started')
        base_guard,samples,policy=(make_guard or safe.guard_factory)(cancel)
        def guard():
            before_cutoff();require(time.monotonic()-started<210,'Owned entrypoint deadline reached.')
            if cancel.exists():raise RuntimeError('owned cancellation')
            base_guard()
        guard();event('completed');phase='load';event('started')
        runtime=(make_runtime or runtime_factory)(runtime_plan,guard);runtime.memory_journal=memory
        runtime.load();guard();event('completed');phase='load_selected_adapter';event('started')
        runtime.load_adapter(identity);guard();event('completed');phase='infer';event('started')
        raw=runtime.infer({'input':current},identity)
        write_new(raw_path,raw);event('returned_and_raw_retained')
        validate_raw(raw,current,identity,plan)
        if raw['status']=='failed':raise RuntimeError(raw.get('error') or 'Native generator failed.')
        phase='release_inactive';event('started');runtime.release_inactive('after_retained_preview_generation');event('completed')
        phase='verify_frozen';event('started');storage=runtime.verify_frozen()
        require(storage.get('identical') is True,'Frozen storage changed.');event('completed');envelope['status']=raw['status']
    except Exception as error:
        envelope['error']=type(error).__name__+': '+str(error);event('failed')
    envelope['raw_response']=raw
    envelope['entrypoint']={'profile_id':PROFILE,'source_sha256':digest(__file__),'input_sha256':input_sha,
        'protocol_sha256':protocol_sha,'selection_sha256':FIXED['selection'],'fixed_checkpoint_sha256':FIXED['checkpoint'],
        'trained_identity':identity,'resource_policy':policy,'resource_samples':samples,'frozen_storage':storage,
        'raw_response_sha256':digest(raw_path) if raw_path.exists() else None,'outer_seconds':210,
        'elapsed_seconds':time.monotonic()-started,'failed_phase':phase if envelope['error'] else None,
        'scope':'Local research engineering evidence; prose and teaching quality are unverified.'}
    write_new(out,envelope);return envelope


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','input','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--protocol-sha256',required=True);args=parser.parse_args()
    value=run_request(ROOT,args.protocol,args.protocol_sha256,args.input,args.out)
    raise SystemExit(0 if value['status'] in {'completed','terminal'} else 2)


if __name__=='__main__':main()
