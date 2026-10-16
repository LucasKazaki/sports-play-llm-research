"""One prospective CPU-only fresh-reserve export, version2.

Actual IO requires a separately frozen latest inventory and root scope seal.
The driver never calls a model/engine, scans source data or changes the corpus.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[3]
TASK=Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')
ROOTS={'repo':ROOT,'task':TASK}
CUTOFF='2026-10-16T22:00:00+00:00'
CORE='cbd3f1c1a08fbb610826e5038a4c1f9867e7cfc1cbce0222a70df10a75a4d552'
RULES='0b7f81450e558be1dd94267ebceac7fe373e62f7ddeddaa8c03948b76b02b376'
TEACHER='2cda3bc89ad0a5e2d7ef0a5dbce52f507cadad6ad83bad92d6fe271cc18db489'
NATIVE='e8f1c2d9d9fb1270e49288d9e39732cf5c2f521fe2e07962015fc776e8bb7ea0'
REQUIRED={'old_cold_1','old_cold_2','old_cold_3','old_cold_4','daytime_cold_failed_1',
    'daytime_direct_cold_1','daytime_train_dev','daytime_held_failed','manual9431',
    'repaired_cold','preview192_qualification','preview192_optional_ui','observer_cpu_3','warm_scope'}
DISPOSITIONS={'retained_raw','unknown_no_raw','closed_raw_absent','not_run','root_only_forward'}
DATA={'dataset','teachers','initial','reserved','corpus_manifest','operational_provenance','inventory','latest_seal'}
SOURCE={'driver','builder','tests','selector','rules','teacher','native'}
MAX_JSON=32*1024**2


def require(value,message):
    if not value:raise ValueError(message)


def canon(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(raw):return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(values):
        value={}
        for key,item in values:
            require(key not in value,'Duplicate JSON key');value[key]=item
        return value
    def constant(value):raise ValueError('Nonfinite JSON')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)


def path_for(item,roots):
    require(type(item) is dict and set(item)=={'root','path','sha256'}
        and item['root'] in roots and type(item['path']) is str and item['path']
        and type(item['sha256']) is str and len(item['sha256'])==64
        and all(c in '0123456789abcdef' for c in item['sha256']),'Malformed exact binding')
    relative=Path(item['path']);require(not relative.is_absolute() and '..' not in relative.parts,'Binding traversal')
    base=Path(roots[item['root']]).resolve();declared=base/relative;actual=declared.resolve()
    require(declared==actual and actual.is_relative_to(base) and actual.is_file(),'Missing/outside/symlink binding')
    return actual


def read_bound(item,roots,guard=lambda:None,maximum=MAX_JSON):
    path=path_for(item,roots);chunks=[];size=0
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):
            size+=len(chunk);require(size<=maximum,'Bounded file too large');chunks.append(chunk);guard()
    raw=b''.join(chunks);require(sha(raw)==item['sha256'],'Bound file changed');return raw


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def write_lines(path,values,guard):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        for value in values:guard();stream.write(json.dumps(value,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())


def append(path,value):
    with Path(path).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def pointer(value,location):
    require(type(location) is list and len(location)<=20,'Receipt locator required')
    for part in location:
        if type(part) is int:
            require(type(value) is list and 0<=part<len(value),'Receipt index differs');value=value[part]
        else:
            require(type(part) is str and type(value) is dict and part in value,'Receipt field differs');value=value[part]
    return value


def evidence_value(item,roots,guard):
    require(type(item) is dict and set(item)=={'binding','format','locator','line'},'Exact evidence locator required')
    raw=read_bound(item['binding'],roots,guard)
    if item['format']=='json':require(item['line'] is None,'JSON line must be null');value=decode(raw)
    else:
        require(item['format']=='jsonl' and type(item['line']) is int and item['line']>=0,'JSONL line required')
        lines=raw.splitlines();require(item['line']<len(lines),'Missing receipt line');value=decode(lines[item['line']])
    return pointer(value,item['locator'])


def attest(items,roots,guard):
    require(type(items) is list and items,'Closed receipt attestations required')
    result=defaultdict(list)
    for item in items:
        require(type(item) is dict and set(item)=={'kind','evidence','equals'} and type(item['kind']) is str,'Malformed attestation')
        value=evidence_value(item['evidence'],roots,guard)
        require(canon(value)==canon(item['equals']),'Closed receipt attestation differs')
        result[item['kind']].append(value)
    return result


def cpu_sample():
    """Only memory counters; no nvidia-smi, process creation or Torch."""
    import ctypes
    from ctypes import wintypes as W
    require(os.name=='nt','Actual memory guard requires Windows')
    class Memory(ctypes.Structure):
        _fields_=[('length',W.DWORD),('load',W.DWORD)]+[(name,ctypes.c_ulonglong) for name in
            ('total','available','pagefile','available_pagefile','virtual','available_virtual','extended')]
    class Performance(ctypes.Structure):
        _fields_=[('size',W.DWORD)]+[(name,ctypes.c_size_t) for name in
            ('commit_total','commit_limit','commit_peak','physical_total','physical_available',
             'cache','kernel_total','kernel_paged','kernel_nonpaged','page_size')]+[
            ('handles',W.DWORD),('processes',W.DWORD),('threads',W.DWORD)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    m=Memory();m.length=ctypes.sizeof(m);p=Performance();p.size=ctypes.sizeof(p)
    kernel.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(Memory)];kernel.GlobalMemoryStatusEx.restype=W.BOOL
    psapi.GetPerformanceInfo.argtypes=[ctypes.POINTER(Performance),W.DWORD];psapi.GetPerformanceInfo.restype=W.BOOL
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(m)) or not psapi.GetPerformanceInfo(ctypes.byref(p),p.size):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'physical_available_bytes':int(m.available),
        'commit_headroom_bytes':int((p.commit_limit-p.commit_total)*p.page_size)}


class Guard:
    def __init__(self,out,started,sample=cpu_sample,clock=time.monotonic,utc=lambda:datetime.now(timezone.utc)):
        self.out=Path(out);self.started=started;self.sample=sample;self.clock=clock;self.utc=utc;self.last=None;self.calls=0
    def __call__(self):
        now=self.clock();require(now-self.started<90,'Owned90-second CPU phase deadline')
        require(self.utc()<datetime.fromisoformat(CUTOFF),'Global authority cutoff')
        require(not (self.out/'CANCEL').exists(),'Owned CPU cancellation')
        if self.last is None or now-self.last>=1:
            value=self.sample();self.last=now
            append(self.out/'memory.jsonl',{'phase':'startup' if self.calls==0 else 'running','sample':value})
            require(value['physical_available_bytes']>=4*1024**3
                and value['commit_headroom_bytes']>=(8 if self.calls==0 else 6)*1024**3,'CPU memory reserve')
            self.calls+=1


def checked_module(raw,path,name):
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__);return module


def components(source_bytes,source_paths):
    require(sha(source_bytes['selector'])==CORE and sha(source_bytes['rules'])==RULES
        and sha(source_bytes['teacher'])==TEACHER and sha(source_bytes['native'])==NATIVE,'Frozen component source differs')
    import chess
    sys.path.insert(0,str(ROOT/'scripts'))
    selector=checked_module(source_bytes['selector'],source_paths['selector'],'_fresh_owned_selector_v2')
    native=checked_module(source_bytes['native'],source_paths['native'],'_fresh_owned_native_parser')
    tree=ast.parse(source_bytes['teacher']);functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='full_three']
    require(len(functions)==1,'Original full_three source is missing')
    namespace={'chess':chess};exec(compile(ast.Module(body=functions,type_ignores=[]),'pinned_original_full_three','exec'),namespace)
    return selector,native,chess,namespace['full_three']


def validate_protocol(plan):
    require(type(plan) is dict and plan.get('schema')=='chess.fresh-held-cpu-protocol.v2'
        and plan.get('scope')=='one_root_owned_cpu_selection_only','Wrong operational protocol')
    require(plan.get('maximum_seconds')==90 and plan.get('cutoff_utc')==CUTOFF
        and plan.get('memory_gib')=={'startup_commit':8,'startup_physical':4,'running_commit':6,'running_physical':4},'Frozen CPU policy differs')
    require(set(plan.get('data',{}))==DATA and set(plan.get('sources',{}))==SOURCE,'Incomplete operational roles')
    require(plan.get('source_sha256')==sha(Path(__file__).read_bytes()),'Driver source differs')
    require(set(plan.get('versions',{}))=={'python','chess','filelock'},'Version identities required')
    require(plan['versions']['python']=='.'.join(map(str,sys.version_info[:3]))
        and all(metadata.version(name)==plan['versions'][name] for name in ('chess','filelock')),'CPU environment differs')
    admit=datetime.fromisoformat(plan['admit_by_utc'])
    require(admit.tzinfo is not None and admit<=datetime.fromisoformat(CUTOFF)
        and type(plan.get('corpus_attestations')) is list,'Prospective admission/closed corpus proof required')
    summary=plan.get('inventory_summary',{})
    require(type(summary.get('planned_slots')) is int and 0<=summary['planned_slots']<=1000
        and type(summary.get('scope_ids')) is list and len(summary['scope_ids'])==len(set(summary['scope_ids']))
        and REQUIRED<=set(summary['scope_ids']),'Incomplete declared latest scope')


def normalized(native,value):
    require(type(value) is dict and set(value)<={'fen','selected_uci','history'} and 'fen' in value
        and value.get('history',[])==[],'Exposure packet is not current-only')
    return native.input_packet(value)[0]


def packet_for_slot(slot,by_case,native,roots,guard):
    context=slot['context'];require(type(context) is dict,'Typed exposure context required')
    if context.get('kind')=='corpus_case':
        require(set(context)=={'kind','case_id','group_id'} and context['case_id'] in by_case,'Unknown exposure case')
        task=by_case[context['case_id']];require(task['group_id']==context['group_id'],'Exposure game differs')
        packet={'fen':task['fen']}
        if task['mode']!='free':packet['selected_uci']=task['selected_uci']
        return normalized(native,packet),context['group_id']
    require(context=={'kind':'anonymous_authored'},'Unknown context is not game ownership')
    value=evidence_value(slot['input_evidence'],roots,guard)
    return normalized(native,value),None


def foreign_packet(slot,proof,native,roots,guard,source_scope):
    """Closed legacy identity, never current-table ownership or an invented FEN."""
    context=slot['context']
    require(type(context) is dict and set(context)=={'kind','source_case_id','group_id','source_scope'}
        and context['kind']=='foreign_source_case'
        and all(type(context[name]) is str and 0<len(context[name])<=256 for name in
            ('source_case_id','group_id','source_scope')),'Exact foreign source identity required')
    require(type(source_scope) is str and context['source_scope']==source_scope,'Foreign outer source scope differs')
    evidence=slot['input_evidence']
    require(type(evidence) is dict and type(evidence.get('locator')) is list
        and evidence['locator'] and evidence['locator'][-1]=='input','Original request input evidence required')
    # Case and group must be siblings of this input in the SAME bound request
    # record/JSONL line. Independent matching strings are insufficient.
    for kind,field,expected in (('source_case_id','case_id',context['source_case_id']),
            ('group_id','group_id',context['group_id'])):
        require(expected in proof.get(kind,[]),'Foreign case/group attestation missing')
        matches=[item for item in slot['attestations'] if item['kind']==kind and item['equals']==expected]
        require(any(item['evidence']['binding']==evidence['binding']
            and item['evidence']['format']==evidence['format'] and item['evidence']['line']==evidence['line']
            and item['evidence']['locator']==evidence['locator'][:-1]+[field] for item in matches),
            'Foreign case/group/input are not one original request record')
    scope_proofs=[item for item in slot['attestations'] if item['kind']=='source_scope'
        and item['equals']==source_scope]
    require(scope_proofs and source_scope in proof.get('source_scope',[]),'Foreign closed source scope missing')
    # The same closed-scope receipt must explicitly bind this exact request SHA
    # and a terminal closure disposition. The root latest seal still owns the
    # semantic review of that typed projection; there is no OS authentication.
    linked=False
    for item in scope_proofs:
        receipt=item['evidence']['binding']
        request=any(p['kind']=='closed_request_sha256' and p['equals']==evidence['binding']['sha256']
            and p['evidence']['binding']==receipt for p in slot['attestations'])
        closed=any(p['kind']=='closed_status' and p['equals'] in {'passed','failed','completed','partial','cancelled'}
            and p['evidence']['binding']==receipt for p in slot['attestations'])
        linked=linked or (request and closed)
    require(linked,'Foreign scope does not bind this request and closed status')
    value=evidence_value(evidence,roots,guard)
    return normalized(native,value),context['group_id']


def project_slot(slot,by_case,native,chess,roots,guard,*,source_scope=None):
    require(type(slot) is dict and slot.get('disposition') in DISPOSITIONS,'Unresolved exposure disposition')
    proof=attest(slot['attestations'],roots,guard)
    require(slot['disposition'] in proof.get('disposition',[]),'Missing disposition proof')
    foreign=slot.get('context',{}).get('kind')=='foreign_source_case'
    packet=game=None
    if foreign:packet,game=foreign_packet(slot,proof,native,roots,guard,source_scope)
    if slot['disposition']=='not_run':
        require(slot.get('raw') is None and any(type(v) is int and v==0 for v in proof.get('model_calls',[])),
            'Never-run needs an explicit zero-call receipt')
        return set(),None,{'disposition':'not_run','generated_paths_assessed':False}
    if not foreign:
        packet,game=packet_for_slot(slot,by_case,native,roots,guard)
        if game is not None:require(slot['context']['case_id'] in proof.get('case_id',[]),'Missing original case membership proof')
        else:require(slot['input_evidence']['binding']['sha256'] in proof.get('input_file_sha256',[]),'Missing original input-file proof')
    board=chess.Board(packet['fen']);key=lambda b:' '.join(b.fen().split()[:4]);keys={key(board)}
    if slot['disposition']!='retained_raw':
        require(slot.get('raw') is None,'Raw-null disposition has a raw binding')
        return keys,game,{'disposition':slot['disposition'],'generated_paths_assessed':False,'foreign_source_case':foreign,
            'limit':'Known root/group excluded; unretained successor paths remain unknown.'}
    raw_bytes=read_bound(slot['raw'],roots,guard,1024**2)
    require(slot['raw']['sha256'] in proof.get('raw_sha256',[]),'Raw is not bound by its closed receipt')
    raw=decode(raw_bytes)
    require(type(raw) is dict and type(raw.get('raw_text')) is str
        and canon(normalized(native,raw.get('input')))==canon(packet),'Raw/request identity differs')
    parsed=native.parse_output(packet,raw['raw_text']);steps=parsed.get('critical_line',{}).get('steps')
    require(type(steps) is list and len(steps)<=32,'Bounded canonical steps required')
    for step in steps:
        guard()
        if not step.get('legal') or board.is_game_over(claim_draw=False):break
        move=chess.Move.from_uci(step['raw_uci']);require(move in board.legal_moves,'Parser/rule prefix differs')
        board.push(move);require(board.fen()==step.get('fen_after'),'Canonical successor differs');keys.add(key(board))
    for value in (parsed.get('accepted_move_uci'),packet.get('selected_uci')):
        if value:
            initial=chess.Board(packet['fen']);move=chess.Move.from_uci(value)
            if not initial.is_game_over(claim_draw=False) and move in initial.legal_moves:initial.push(move);keys.add(key(initial))
    return keys,game,{'disposition':'retained_raw','generated_paths_assessed':True,'foreign_source_case':foreign,'raw_sha256':sha(raw_bytes),
        'scope':'Canonical legal prefix and independently legal root BEST/given successors only; no whole-prose coverage.'}


def legacy_binding(value,roots):
    require(type(value) is dict and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int,'Malformed original projection binding')
    declared=Path(value['path']).absolute()
    for role,base in roots.items():
        base=Path(base).resolve()
        if declared.is_relative_to(base):
            return {'root':role,'path':declared.relative_to(base).as_posix(),'sha256':value['sha256']}
    raise ValueError('Original projection dependency outside allowed roots')


def read_legacy(value,roots,guard):
    raw=read_bound(legacy_binding(value,roots),roots,guard)
    require(len(raw)==value['bytes'],'Original projection byte count differs');return raw


def manual_keys(item,slots,roots,native,chess,guard,approved):
    require(item['projection'] in approved,'Manual projection is not in root latest seal')
    value=decode(read_bound(item['projection'],roots,guard))
    require(value.get('schema')=='chess.manual-branch-exclusion-projection.v1'
        and value.get('status')=='projected_from_previously_independently_reviewed_annotation'
        and value.get('game_context') is None and value.get('later_operational_replay_required') is True,'Manual mapping scope differs')
    for name in ('analysis','semantic_review'):read_legacy(value[name],roots,guard)
    review=decode(read_legacy(value['semantic_review'],roots,guard))
    require(review.get('status')=='passed_private_semantic_correspondence_review','Independent manual semantic mapping is not passed')
    slot=slots[item['raw_slot_id']]
    require(slot['raw']==legacy_binding(value['raw_response'],roots)
        and slot['disposition']=='retained_raw' and slot['context']=={'kind':'anonymous_authored'},'Manual raw/anonymous role differs')
    raw=decode(read_legacy(value['raw_response'],roots,guard));packet=normalized(native,raw['input']);text=raw['raw_text']
    require(canon(normalized(native,value['root_input']))==canon(packet),'Manual original root differs')
    require(type(value.get('branches')) is list and 0<len(value['branches'])<=16,'Bounded root branches required')
    require(len({branch['branch_id'] for branch in value['branches']})==len(value['branches']),'Duplicate manual branch identity')
    keys=set();unit='unicode_code_points_of_response.raw_text'
    def span_text(span):
        require(set(span)=={'start','end','unit','sha256'} and span['unit']==unit
            and type(span['start']) is int and type(span['end']) is int
            and 0<=span['start']<span['end']<=len(text),'Invalid Unicode-codepoint span')
        atom=text[span['start']:span['end']];require(sha(atom.encode())==span['sha256'],'Manual exact span differs');return atom
    for branch in value['branches']:
        require(branch['root_fen']==packet['fen'] and branch.get('no_after_invalid_board') is True
            and type(branch.get('legal_prefix')) is list and 0<len(branch['legal_prefix'])<=16,'No replacement FEN or invented branch context')
        paragraph=branch['paragraph_span'];span_text(paragraph);prefix=branch['legal_prefix']
        require(branch['first_invalid_ply'] is None or branch['first_invalid_ply']==len(prefix)+1,'Later-after-illegal branch context')
        atoms=[];end=0
        for step in prefix:
            span=step['source_atom_span'];atom=span_text(span)
            require(end<=span['start'] and paragraph['start']<=span['start']<span['end']<=paragraph['end']
                and native.MOVE.fullmatch(atom),'Manual native atom differs');end=span['end'];atoms.append(atom)
        parsed=native.parse_output(packet,'CRITICAL_LINE: '+' '.join(atoms));board=chess.Board(packet['fen'])
        reached=[' '.join(board.fen().split()[:4])];steps=parsed['critical_line']['steps']
        require(len(steps)==len(prefix),'Included manual prefix is not fully replayable')
        for i,(step,expected) in enumerate(zip(steps,prefix),1):
            require(step.get('legal') and not board.is_game_over(claim_draw=False) and expected['ply']==i
                and step['raw_uci']==expected['uci'],'Included manual UCI/turn differs')
            move=chess.Move.from_uci(step['raw_uci']);require(move in board.legal_moves,'Manual prefix legality differs')
            board.push(move);require(board.fen()==step['fen_after']==expected['fen_after'],'Manual successor differs');reached.append(' '.join(board.fen().split()[:4]))
        require(reached==branch['board_keys_from_previously_reviewed_FENs'],'Manual reviewed branch keys differ');keys.update(reached)
    require(sorted(keys)==value['board_keys'] and len(keys)==value['key_count'],'Manual projected key union differs')
    return keys


def recover(journal,root_count,slot_count):
    roots=[{'slot':i,'status':'not_run'} for i in range(root_count)]
    exposures=[{'slot':i,'status':'not_run'} for i in range(slot_count)];root_started=False
    error=None
    if journal.exists():
        lines=journal.read_bytes().splitlines()
        for i,line in enumerate(lines):
            try:
                try:event=decode(line)
                except (ValueError,UnicodeError):
                    if i==len(lines)-1:break
                    raise ValueError('Journal corruption before later event')
                kind=event.get('kind')
                if kind=='selection_intent':
                    require(not root_started,'Repeated selection intent');root_started=True
                    roots=[{'slot':n,'status':'active_unknown'} for n in range(root_count)]
                elif kind=='root_outcome':
                    n=event['slot'];require(type(n) is int and root_started and 0<=n<root_count
                        and roots[n]['status']=='active_unknown' and event['status'] in {'selected','not_selected'},'Repeated/outside root outcome');roots[n]=event
                elif kind in {'exposure_intent','exposure_outcome'}:
                    n=event['slot'];require(type(n) is int and 0<=n<slot_count,'Outside exposure slot')
                    previous=exposures[n]['status']
                    require(previous==('not_run' if kind=='exposure_intent' else 'active_unknown'),'Repeated exposure intent/outcome')
                    exposures[n]={'slot':n,'status':'active_unknown'} if kind=='exposure_intent' else event
            except (ValueError,TypeError,KeyError) as problem:
                error=str(problem)
                roots=[{**row,'status':'active_unknown'} if row['status']=='not_run' else row for row in roots]
                exposures=[{**row,'status':'active_unknown'} if row['status']=='not_run' else row for row in exposures]
                break
    return roots,exposures,error


def run(protocol,protocol_sha,out,*,roots=None,sample=cpu_sample,clock=time.monotonic,
        utc=lambda:datetime.now(timezone.utc),lease=None,loader=components):
    roots=roots or ROOTS;out=Path(out);require(not out.exists(),'Create-only attempt; no retries')
    out.mkdir(parents=True);started=clock();journal=out/'events.jsonl';planned=0;phase='protocol';selected=[];acquired=False
    result={'status':'failed','planned_reserve':512,'planned_selected':16,'planned_inputs':48,'model_calls':0,'engine_calls':0,
        'exposure_plan_state':'unconstructed_until_protocol_verified'}
    write_new(out/'intent.json',{'protocol_sha256':protocol_sha,'scope':'one_cpu_operation'})
    def emit(kind,**value):append(journal,{'kind':kind,**value})
    try:
        if lease is None:
            from filelock import FileLock
            # Exact shared path used by the reviewed owned GPU worker.
            lease=FileLock(str(ROOT/'data/private/chess-gpu-owner.lock'),timeout=0)
        lease.__enter__();acquired=True
        if acquired:
            guard=Guard(out,started,sample,clock,utc);guard()
            require(Path(protocol).stat().st_size<=1024**2,'Operational protocol too large')
            raw=Path(protocol).read_bytes();require(sha(raw)==protocol_sha,'Protocol changed');plan=decode(raw);validate_protocol(plan)
            require(utc()<=datetime.fromisoformat(plan['admit_by_utc']),'Prospective CPU admission deadline passed')
            planned=plan['inventory_summary']['planned_slots'];result.update(exposure_plan_state='bound',planned_exposure_slots=planned)
            (out/'sources').mkdir()
            source_bytes={name:read_bound(item,roots,guard) for name,item in plan['sources'].items()}
            require(sha(source_bytes['driver'])==plan['source_sha256'],'Bound driver source differs')
            with (out/'protocol.json').open('xb') as stream:stream.write(raw)
            for name,value in source_bytes.items():
                with (out/'sources'/f'{name}.py').open('xb') as stream:stream.write(value)
            source_paths={name:path_for(item,roots) for name,item in plan['sources'].items()}
            selector,native,chess,full_three=loader(source_bytes,source_paths)
            phase='inventory';inventory=decode(read_bound(plan['data']['inventory'],roots,guard))
            seal=decode(read_bound(plan['data']['latest_seal'],roots,guard))
            require(inventory.get('schema')=='chess.fresh-held-exposure-inventory.v1' and inventory.get('status')=='sealed',
                'Draft or unresolved exposure inventory')
            scope_ids=[scope['scope_id'] for scope in inventory['scopes']]
            require(scope_ids==plan['inventory_summary']['scope_ids'] and len(scope_ids)==len(set(scope_ids)),'Scope list differs')
            require(seal.get('schema')=='chess.latest-exposure-root-seal.v1' and seal.get('status')=='closed_for_selection'
                and seal.get('inventory_sha256')==plan['data']['inventory']['sha256']
                and seal.get('scope_ids')==scope_ids and seal.get('all_dispatches_closed_or_explicit_unrun') is True
                and seal.get('no_overlapped_gpu') is True,'Missing latest root dispatch freeze')
            slots=[];slot_scopes={}
            for scope in inventory['scopes']:
                proof=attest(scope['attestations'],roots,guard)
                require(scope['scope_id'] in proof.get('scope_id',[]),'Scope membership is not closed-receipted')
                require(type(scope.get('slots')) is list,'Scope slot denominator required')
                if scope.get('no_learning'):
                    require(any(type(v) is int and v==0 for v in proof.get('model_calls',[])) and not scope['slots'],'No-learning scope needs explicit zero-call proof')
                slots.extend(scope['slots'])
                for slot in scope['slots']:slot_scopes[slot['slot_id']]=scope['scope_id']
            require(len(slots)==planned and len({slot['slot_id'] for slot in slots})==planned,'Full unique exposure denominator differs')
            phase='ownership'
            data={name:decode(read_bound(plan['data'][name],roots,guard)) for name in ('dataset','teachers','initial','reserved','corpus_manifest','operational_provenance')}
            provenance=data['operational_provenance'];manifest=data['corpus_manifest']
            require(provenance.get('status')=='completed' and provenance.get('owned_engine_exit_verified') is True
                and provenance.get('corpus_manifest_sha256')==plan['data']['corpus_manifest']['sha256']
                and provenance.get('scientific_protocol_sha256')=='f6dce48af4610b23d8c7a376e2f15221429c0b2d8b21b838842272aeca077a0a'
                and provenance.get('operational_protocol_sha256')=='3f9785466c0f35e8a01d3b05361370ce5e65bc9ba36f4667c2502dc25d98a65b',
                'Original closed CPU corpus provenance differs')
            for field,name in (('dataset_sha256','dataset'),('teachers_sha256','teachers'),('reserved_exclusions_sha256','reserved')):
                require(manifest.get(field)==plan['data'][name]['sha256'],'Corpus manifest identity differs')
            corpus_proof=attest(plan['corpus_attestations'],roots,guard)
            for name in ('dataset','teachers','initial','reserved'):
                require(plan['data'][name]['sha256'] in corpus_proof.get(name+'_sha256',[]),'Independent corpus byte proof missing')
            require(any(type(v) is int and v==1056 for v in corpus_proof.get('roots',[]))
                and any(type(v) is int and v==3168 for v in corpus_proof.get('teacher_tasks',[])),'Independent corpus denominator proof missing')
            owners,by_case=selector.ownership(data['dataset'],data['teachers'],data['initial'],data['reserved'])
            spent=set(data['corpus_manifest']['held_root_game_ids']);require(len(spent)==16,'Exact old16 spent scope required')
            phase='projection';keys=set();games=set();overlay=[];slot_map={slot['slot_id']:slot for slot in slots}
            for i,slot in enumerate(slots):
                guard();emit('exposure_intent',slot=i,slot_id=slot['slot_id'],source_scope=slot_scopes[slot['slot_id']])
                observed,game,detail=project_slot(slot,by_case,native,chess,roots,guard,source_scope=slot_scopes[slot['slot_id']])
                keys.update(observed)
                if game:games.add(game)
                overlay.append({'slot_id':slot['slot_id'],'keys':sorted(observed),'group_id':game,'detail':detail,
                    'source_scope':slot_scopes[slot['slot_id']], 'context_kind':slot.get('context',{}).get('kind'),
                    'source_case_id':slot.get('context',{}).get('source_case_id'),
                    'owner_role':'foreign_exposure_never_current_reserve_owner'})
                emit('exposure_outcome',slot=i,status='projected',disposition=slot['disposition'],key_count=len(observed))
            for item in inventory.get('manual_projections',[]):
                observed=manual_keys(item,slot_map,roots,native,chess,guard,seal.get('approved_manual_projections',[]))
                keys.update(observed);overlay.append({'manual_projection':item['projection'],'raw_slot_id':item['raw_slot_id'],
                    'keys':sorted(observed),'group_id':None,'role':'anonymous_foreign_reviewed_prose_legal_prefix_only'})
            write_new(out/'private-exposure-roles.json',overlay)
            phase='selection';guard();emit('selection_intent')
            selected,ledger=selector.choose(data['dataset']['groups']['reserve'],by_case,owners,
                set(data['initial']['games'])|games,spent,keys,full_three)
            for i,row in enumerate(ledger['rows']):
                guard();emit('root_outcome',slot=i,status='selected' if row['selected'] else 'not_selected',**row)
            require(ledger['status']=='ready_for_export' and len(selected)==16,'Insufficient fresh cohort; no shrink or retry')
            phase='export';guard();emit('export_intent');values,refs=selector.export_rows(selected,by_case)
            require(len(values)==len(refs)==48,'Full48 input/reference pairs required')
            write_lines(out/'heldout-inputs.jsonl',values,guard);write_lines(out/'heldout-references.jsonl',refs,guard)
            write_new(out/'private-new16-reservation.json',{'games':[root['game_id'] for root in selected],
                'preserve_all512_for_training_exclusion':True,'held_scope':'reserved_even_if_later_model_calls_do_not_run'})
            for name,item in plan['data'].items():read_bound(item,roots,guard) # Final immutable readback, no new interpretation.
            outputs={name:sha((out/name).read_bytes()) for name in ('heldout-inputs.jsonl','heldout-references.jsonl','private-new16-reservation.json')}
            emit('export_outcome',status='written',input_records=48,reference_records=48)
            result.update(status='ready_for_model_protocol_review',selected=16,input_records=48,reference_records=48,outputs=outputs,
                exposure_artifacts=planned,exposed_keys=len(keys),no_quality_claim=True)
    except Exception as error:
        result.update(error=type(error).__name__+': '+str(error),failed_phase=phase)
    finally:
        try:
            root_rows,exposures,recovery_error=recover(journal,512,planned)
            if recovery_error:result.update(status='failed',recovery_error=recovery_error)
            result.update(root_counts=dict(Counter(row['status'] for row in root_rows)),
                exposure_counts=dict(Counter(row['status'] for row in exposures)),elapsed_seconds=clock()-started,
                closure_written_while_lease_held=acquired)
            selection_rows=[row for row in root_rows if row['status']=='selected']
            result['selected_slots']=[{'slot':i,'status':'selected','group_id':row['group_id']} for i,row in enumerate(selection_rows)]
            result['selected_slots'] += [{'slot':i,'status':'not_run' if not selection_rows else 'unfilled'} for i in range(len(selection_rows),16)]
            result['pair_slots']=[{'slot':i,'status':'written' if result['status']=='ready_for_model_protocol_review'
                else 'active_unknown' if phase=='export' else 'not_run'} for i in range(48)]
            try:
                write_new(out/'root-outcomes.json',root_rows);write_new(out/'exposure-outcomes.json',exposures)
                if result['status']=='ready_for_model_protocol_review':
                    require(len(selection_rows)==16 and len(root_rows)==512 and all(row['status']!='active_unknown' for row in root_rows),
                        'Incomplete final selection accounting')
                    write_new(out/'manifest.json',{'schema':'chess.fresh-held-ready-manifest.v1','status':'ready',
                        'selected_games':16,'input_count':48,
                        'input_rows':{'path':str((out/'heldout-inputs.jsonl').resolve()),'sha256':result['outputs']['heldout-inputs.jsonl']},
                        'grader_references':{'path':str((out/'heldout-references.jsonl').resolve()),'sha256':result['outputs']['heldout-references.jsonl']},
                        'operational_protocol_sha256':protocol_sha,'source_sha256':sha(Path(__file__).read_bytes()),
                        'requires_independent_closed_audit':True,'quality_claim':False,
                        'limit':'Ready data requires the bound successful closed ledger and independent audit; file presence is not admission.'})
            except Exception as error:
                result.update(status='failed',finalization_error=type(error).__name__+': '+str(error))
            write_new(out/'closed.json',result)
        finally:
            if acquired:lease.__exit__(None,None,None)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    value=run(args.protocol,args.protocol_sha256,args.out)
    print(json.dumps({key:value.get(key) for key in ('status','root_counts','exposure_counts','failed_phase','elapsed_seconds')}))
    raise SystemExit(0 if value['status']=='ready_for_model_protocol_review' else 2)


if __name__=='__main__':main()
