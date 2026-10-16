"""Authored software fixtures only: no actual corpus, engine, model or probes."""
import copy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import chess

HERE=Path(__file__).resolve().parent
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value
d=load(HERE/'run_once.py','_fresh_operation_test')
b=load(HERE/'build_protocol.py','_fresh_builder_test')
n=load(d.ROOT/'scripts/chess_queen_adapter.py','_fresh_native_authored_test')
FEN=chess.STARTING_FEN
NOW=lambda:datetime(2026,10,16,20,tzinfo=timezone.utc)
MEM=lambda:{'physical_available_bytes':10*1024**3,'commit_headroom_bytes':12*1024**3}


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,ensure_ascii=False)+'\n').encode());return path


def binding(path,root):return {'root':'repo','path':path.relative_to(root).as_posix(),'sha256':d.sha(path.read_bytes())}
def locator(bound,parts):return {'binding':bound,'format':'json','line':None,'locator':parts}
def proof(bound,kind,path,value):return {'kind':kind,'evidence':locator(bound,path),'equals':value}
def key(board):return ' '.join(board.fen().split()[:4])


def atom(uci,pov=True):
    move=chess.Move.from_uci(uci);origin=move.from_square if pov else move.from_square^56
    target=move.to_square if pov else move.to_square^56
    piece='P' if uci in ('e2e4','e7e5','d2d4','d7d5') else 'R'
    side='M' if (uci[1]=='2')==pov else 'O'
    return f'<PIECE_{side}{piece}><SQUARE_{origin+1}><SQUARE_{target+1}>'


def exposure(tmp,disposition='retained_raw',text=None,root=None):
    root=root or tmp
    request=put(tmp/'request.json',{'fen':FEN})
    response=put(tmp/'raw.json',{'input':{'fen':FEN,'history':[]},'raw_text':text or 'CRITICAL_LINE: '+atom('e2e4')+' '+atom('e7e5')})
    meta={'state':disposition,'input_sha':d.sha(request.read_bytes()),'raw_sha':d.sha(response.read_bytes()),'calls':0,'case':'case0'}
    receipt=put(tmp/'receipt.json',meta);rb=binding(receipt,root)
    checks=[proof(rb,'disposition',['state'],disposition),proof(rb,'input_file_sha256',['input_sha'],meta['input_sha']),
        proof(rb,'raw_sha256',['raw_sha'],meta['raw_sha']),proof(rb,'model_calls',['calls'],0),proof(rb,'case_id',['case'],'case0')]
    return {'slot_id':'authored0','disposition':disposition,'attestations':checks,
        'context':{'kind':'anonymous_authored'},'input_evidence':locator(binding(request,root),[]),
        'raw':binding(response,root) if disposition=='retained_raw' else None}


@pytest.mark.parametrize('relative',['../escape','/absolute'])
def test_binding_traversal(tmp_path,relative):
    with pytest.raises(ValueError):d.path_for({'root':'repo','path':relative,'sha256':'0'*64},{'repo':tmp_path})


def test_hash_changed_and_duplicate_json(tmp_path):
    path=put(tmp_path/'a.json',{});item=binding(path,tmp_path);path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):d.read_bound(item,{'repo':tmp_path})
    with pytest.raises(ValueError,match='Duplicate'):d.decode(b'{"x":1,"x":2}')
    with pytest.raises(ValueError,match='Nonfinite'):d.decode(b'{"x":NaN}')


def test_read_size_and_exact_locator_types(tmp_path):
    p=put(tmp_path/'a.json',{'value':False,'rows':[7]});bound=binding(p,tmp_path)
    with pytest.raises(ValueError,match='too large'):d.read_bound(bound,{'repo':tmp_path},maximum=1)
    with pytest.raises(ValueError,match='differs'):d.attest([proof(bound,'zero',['value'],0)],{'repo':tmp_path},lambda:None)
    with pytest.raises(ValueError):d.pointer({'x':1},[False])
    assert d.pointer({'rows':[7]},['rows',0])==7


def test_jsonl_receipt_exact_line(tmp_path):
    p=tmp_path/'rows.jsonl';p.write_bytes(b'{"x":0}\n{"x":1}\n')
    loc={'binding':binding(p,tmp_path),'format':'jsonl','line':1,'locator':['x']}
    assert d.evidence_value(loc,{'repo':tmp_path},lambda:None)==1
    loc['line']=2
    with pytest.raises(ValueError):d.evidence_value(loc,{'repo':tmp_path},lambda:None)


def test_memory_sampler_throttled_and_running_floor(tmp_path):
    t=[0];calls=[]
    def sample():calls.append(1);return MEM()
    guard=d.Guard(tmp_path,0,sample,lambda:t[0],NOW);guard();guard();t[0]=.9;guard();assert len(calls)==1
    t[0]=1;guard();assert len(calls)==2
    assert [json.loads(line)['phase'] for line in (tmp_path/'memory.jsonl').read_text().splitlines()]==['startup','running']


@pytest.mark.parametrize('kind',['commit','physical','deadline','cutoff','cancel'])
def test_guard_stops_without_lowering_floors(tmp_path,kind):
    sample=MEM;clock=lambda:0;utc=NOW
    if kind=='commit':sample=lambda:{**MEM(),'commit_headroom_bytes':8*1024**3-1}
    if kind=='physical':sample=lambda:{**MEM(),'physical_available_bytes':4*1024**3-1}
    if kind=='deadline':clock=lambda:90
    if kind=='cutoff':utc=lambda:datetime.fromisoformat(d.CUTOFF)
    if kind=='cancel':(tmp_path/'CANCEL').write_text('owned')
    with pytest.raises(ValueError):d.Guard(tmp_path,0,sample,clock,utc)()


def test_project_legal_prefix_and_independent_best(tmp_path):
    slot=exposure(tmp_path,text='BEST_MOVE: '+atom('d2d4')+'\nCRITICAL_LINE: '+atom('e2e4')+' '+atom('e7e5'))
    keys,game,detail=d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)
    board=chess.Board();expected={key(board)}
    for move in ('e2e4','e7e5'):board.push_uci(move);expected.add(key(board))
    board=chess.Board();board.push_uci('d2d4');expected.add(key(board))
    assert keys==expected and game is None and detail['generated_paths_assessed']


def test_first_illegal_stops_no_forced_turn(tmp_path):
    slot=exposure(tmp_path,text='CRITICAL_LINE: '+atom('e2e4')+' '+atom('a1a8')+' '+atom('e7e5'))
    keys,_,_=d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)
    board=chess.Board();expected={key(board)};board.push_uci('e2e4');expected.add(key(board))
    assert keys==expected


@pytest.mark.parametrize('disposition',['unknown_no_raw','closed_raw_absent','root_only_forward'])
def test_unretained_path_retains_known_root_and_unknown(tmp_path,disposition):
    slot=exposure(tmp_path,disposition);keys,game,detail=d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)
    assert keys=={key(chess.Board())} and game is None and not detail['generated_paths_assessed']
    assert 'unknown' in detail['limit']


def test_not_run_requires_typed_zero_no_raw(tmp_path):
    slot=exposure(tmp_path,'not_run');assert d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)[0]==set()
    for check in slot['attestations']:
        if check['kind']=='model_calls':check['equals']=False
    with pytest.raises(ValueError):d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)


def test_raw_packet_and_file_identity_required(tmp_path):
    slot=exposure(tmp_path);p=tmp_path/'raw.json';raw=json.loads(p.read_bytes());raw['input']['selected_uci']='d2d4';put(p,raw)
    slot['raw']=binding(p,tmp_path)
    with pytest.raises(ValueError,match='closed receipt'):d.project_slot(slot,{},n,chess,{'repo':tmp_path},lambda:None)


def test_explicit_case_owner_and_black_current_only(tmp_path):
    slot=exposure(tmp_path,'unknown_no_raw');board=chess.Board();board.push_uci('e2e4')
    task={'group_id':'known','mode':'selected_a','fen':board.fen(),'selected_uci':'e7e5'}
    slot['context']={'kind':'corpus_case','case_id':'case0','group_id':'known'}
    keys,game,_=d.project_slot(slot,{'case0':task},n,chess,{'repo':tmp_path},lambda:None)
    assert game=='known' and keys=={key(board)}
    slot['context']['group_id']='invented'
    with pytest.raises(ValueError):d.project_slot(slot,{'case0':task},n,chess,{'repo':tmp_path},lambda:None)
    with pytest.raises(ValueError):d.normalized(n,{'fen':FEN,'history':[FEN]})


def manual_fixture(tmp):
    slot=exposure(tmp);raw=json.loads((tmp/'raw.json').read_bytes());text=raw['raw_text'];steps=[];board=chess.Board();keys=[key(board)]
    for i,uci in enumerate(('e2e4','e7e5'),1):
        token=atom(uci);start=text.index(token);board.push_uci(uci);keys.append(key(board))
        steps.append({'ply':i,'uci':uci,'fen_after':board.fen(),'source_atom_span':{'start':start,'end':start+len(token),
            'unit':'unicode_code_points_of_response.raw_text','sha256':d.sha(token.encode())}})
    def old(path):return {'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':d.sha(path.read_bytes())}
    analysis=put(tmp/'analysis.json',{'scope':'AI-authored fixture, not actual semantic evidence'})
    review=put(tmp/'review.json',{'status':'passed_private_semantic_correspondence_review','synthetic':True})
    value={'schema':'chess.manual-branch-exclusion-projection.v1','status':'projected_from_previously_independently_reviewed_annotation',
        'analysis':old(analysis),'semantic_review':old(review),'raw_response':old(tmp/'raw.json'),
        'root_input':raw['input'],'game_context':None,'later_operational_replay_required':True,
        'branches':[{'branch_id':'authored_branch','root_fen':FEN,'paragraph_span':{'start':0,'end':len(text),
            'unit':'unicode_code_points_of_response.raw_text','sha256':d.sha(text.encode())},'legal_prefix':steps,
            'board_keys_from_previously_reviewed_FENs':keys,'first_invalid_ply':3,'no_after_invalid_board':True}],
        'board_keys':sorted(keys),'key_count':len(keys)}
    projection=put(tmp/'projection.json',value)
    return slot,value,projection


def test_manual_native_atoms_exact_replay_only(tmp_path):
    slot,value,path=manual_fixture(tmp_path);bound=binding(path,tmp_path)
    result=d.manual_keys({'projection':bound,'raw_slot_id':'authored0'},{'authored0':slot},{'repo':tmp_path},n,chess,lambda:None,[bound])
    assert result==set(value['board_keys'])


@pytest.mark.parametrize('change',['root','span','uci','after','keys','after_illegal','approval'])
def test_manual_projection_rejects_replacement_or_unbound_context(tmp_path,change):
    slot,value,path=manual_fixture(tmp_path);branch=value['branches'][0]
    if change=='root':branch['root_fen']=chess.Board().mirror().fen()
    if change=='span':branch['legal_prefix'][0]['source_atom_span']['sha256']='0'*64
    if change=='uci':branch['legal_prefix'][0]['uci']='d2d4'
    if change=='after':branch['legal_prefix'][0]['fen_after']=FEN
    if change=='keys':branch['board_keys_from_previously_reviewed_FENs']=[]
    if change=='after_illegal':branch['first_invalid_ply']=2
    put(path,value);bound=binding(path,tmp_path)
    with pytest.raises(ValueError):d.manual_keys({'projection':bound,'raw_slot_id':'authored0'},{'authored0':slot},
        {'repo':tmp_path},n,chess,lambda:None,[] if change=='approval' else [bound])


class Lease:
    def __init__(self,busy=False):self.held=False;self.exits=0;self.busy=busy
    def __enter__(self):
        if self.busy:raise RuntimeError('authored lease busy')
        self.held=True;return self
    def __exit__(self,*args):self.held=False;self.exits+=1


def operation(tmp,monkeypatch,slots=None):
    """Deliberately fake tables/selector; tests operation wiring, never corpus truth."""
    base=tmp/'bindings';base.mkdir();scopes=[];slots=slots or []
    for i,scope_id in enumerate(sorted(d.REQUIRED)):
        meta=put(base/f'scope{i}.json',{'scope':scope_id,'calls':0});bound=binding(meta,tmp)
        scope_slots=slots if i==0 else []
        scopes.append({'scope_id':scope_id,'no_learning':not scope_slots,'slots':scope_slots,
            'attestations':[proof(bound,'scope_id',['scope'],scope_id),proof(bound,'model_calls',['calls'],0)]})
    inventory=put(base/'inventory.json',{'schema':'chess.fresh-held-exposure-inventory.v1','status':'sealed','scopes':scopes})
    seal=put(base/'seal.json',{'schema':'chess.latest-exposure-root-seal.v1','status':'closed_for_selection',
        'inventory_sha256':d.sha(inventory.read_bytes()),'scope_ids':[s['scope_id'] for s in scopes],
        'all_dispatches_closed_or_explicit_unrun':True,'no_overlapped_gpu':True,'approved_manual_projections':[]})
    reserve=[{'game_id':f'fake{i}','source_ordinal':i} for i in range(512)]
    dataset=put(base/'dataset.json',{'groups':{'reserve':reserve}});teachers=put(base/'teachers.json',{'rows':[]})
    initial=put(base/'initial.json',{'games':[],'board_keys':[]});reserved=put(base/'reserved.json',{'games':[],'board_keys':[]})
    manifest=put(base/'corpus.json',{'dataset_sha256':d.sha(dataset.read_bytes()),'teachers_sha256':d.sha(teachers.read_bytes()),
        'reserved_exclusions_sha256':d.sha(reserved.read_bytes()),'held_root_game_ids':[f'fake{i}' for i in range(16)]})
    provenance=put(base/'provenance.json',{'status':'completed','owned_engine_exit_verified':True,'corpus_manifest_sha256':d.sha(manifest.read_bytes()),
        'scientific_protocol_sha256':'f6dce48af4610b23d8c7a376e2f15221429c0b2d8b21b838842272aeca077a0a',
        'operational_protocol_sha256':'3f9785466c0f35e8a01d3b05361370ce5e65bc9ba36f4667c2502dc25d98a65b'})
    data=dict(zip(('dataset','teachers','initial','reserved','corpus_manifest','operational_provenance','inventory','latest_seal'),
        (dataset,teachers,initial,reserved,manifest,provenance,inventory,seal)))
    audited={name+'_sha256':d.sha(data[name].read_bytes()) for name in ('dataset','teachers','initial','reserved')}
    audited.update(roots=1056,teacher_tasks=3168);audit=put(base/'fakeaudit.json',audited);ab=binding(audit,tmp)
    sources={}
    for name in d.SOURCE:
        path=base/(name+'.py');path.write_bytes((HERE/'run_once.py').read_bytes() if name=='driver' else b'# fake source fixture\n')
        sources[name]=binding(path,tmp)
    plan={'schema':'chess.fresh-held-cpu-protocol.v1','scope':'one_root_owned_cpu_selection_only','maximum_seconds':90,
        'cutoff_utc':d.CUTOFF,'memory_gib':{'startup_commit':8,'startup_physical':4,'running_commit':6,'running_physical':4},
        'source_sha256':d.sha((HERE/'run_once.py').read_bytes()),'sources':sources,'data':{k:binding(v,tmp) for k,v in data.items()},
        'versions':{'python':'.'.join(map(str,sys.version_info[:3])),'chess':d.metadata.version('chess'),'filelock':d.metadata.version('filelock')},
        'admit_by_utc':'2026-10-16T21:00:00+00:00','inventory_summary':{'scope_ids':[s['scope_id'] for s in scopes],'planned_slots':len(slots)},
        'corpus_attestations':[proof(ab,k,[k],v) for k,v in audited.items()]}
    path=put(tmp/'protocol.json',plan)
    def choose(rows,by_case,owners,historical,spent,keys,full):
        selected=[root for root in rows if root['game_id'] not in spent|historical][:16]
        chosen={r['game_id'] for r in selected}
        return selected,{'status':'ready_for_export','rows':[{'group_id':r['game_id'],'selected':r['game_id'] in chosen} for r in rows]}
    def export(rows,cases):
        return ([{'case_id':f'fake{i}','input':{'fen':FEN}} for i in range(48)],
            [{'case_id':f'fake{i}','reference_pv':['e2e4','e7e5','g1f3']} for i in range(48)])
    selector=SimpleNamespace(ownership=lambda *args:({},{}),choose=choose,export_rows=export)
    return path,plan,selector,lambda *args:(selector,n,chess,lambda task:True),data


def execute(path,tmp,loader,lease=None,**kwargs):
    return d.run(path,d.sha(path.read_bytes()),tmp/'out',roots={'repo':tmp},sample=MEM,clock=lambda:0,utc=NOW,
        lease=lease or Lease(),loader=loader,**kwargs)


def test_mock_closed_ready_manifest_exact48_and_full512(tmp_path,monkeypatch):
    path,plan,selector,loader,data=operation(tmp_path,monkeypatch);lease=Lease();value=execute(path,tmp_path,loader,lease)
    assert value['status']=='ready_for_model_protocol_review' and value['root_counts']=={'not_selected':496,'selected':16}
    assert len(value['selected_slots'])==16 and len(value['pair_slots'])==48 and value['closure_written_while_lease_held']
    manifest=json.loads((tmp_path/'out/manifest.json').read_bytes())
    assert manifest['status']=='ready' and manifest['selected_games']==16 and manifest['input_count']==48
    assert manifest['input_rows']['sha256']==d.sha(Path(manifest['input_rows']['path']).read_bytes())
    assert not lease.held and lease.exits==1 and manifest['requires_independent_closed_audit']
    with pytest.raises(ValueError,match='Create-only'):execute(path,tmp_path,loader)


@pytest.mark.parametrize('failure',['malformed','busy','startup','seal','scope','changed_source','projection','selection','export','final_data_change'])
def test_mock_every_failure_closes_denominators_no_ready(tmp_path,monkeypatch,failure):
    slot=exposure(tmp_path/'exposure',root=tmp_path) if failure=='projection' else None
    path,plan,selector,loader,data=operation(tmp_path,monkeypatch,[slot] if slot else [])
    lease=Lease(busy=failure=='busy');sample=MEM
    if failure=='malformed':put(path,{'schema':'bad'})
    if failure=='startup':sample=lambda:{**MEM(),'commit_headroom_bytes':0}
    if failure=='seal':put(data['latest_seal'],{'status':'pending'})
    if failure=='scope':plan['inventory_summary']['scope_ids']=[];put(path,plan)
    if failure=='changed_source':(tmp_path/plan['sources']['tests']['path']).write_text('changed')
    if failure=='projection':(tmp_path/'exposure/raw.json').write_text('changed')
    if failure=='selection':selector.choose=lambda *a:(_ for _ in ()).throw(ValueError('authored selection failure'))
    if failure=='export':selector.export_rows=lambda *a:(_ for _ in ()).throw(ValueError('authored export failure'))
    if failure=='final_data_change':
        old=selector.export_rows
        def changed(*args):data['initial'].write_text('changed');return old(*args)
        selector.export_rows=changed
    value=d.run(path,d.sha(path.read_bytes()),tmp_path/'out',roots={'repo':tmp_path},sample=sample,clock=lambda:0,utc=NOW,lease=lease,loader=loader)
    assert value['status']=='failed' and sum(value['root_counts'].values())==512 and len(value['pair_slots'])==48
    assert not (tmp_path/'out/manifest.json').exists() and (tmp_path/'out/closed.json').exists() and not lease.held
    if failure=='projection':assert value['exposure_counts']=={'active_unknown':1}
    if failure=='selection':assert value['root_counts']=={'active_unknown':512}
    if failure=='export':assert value['root_counts']['selected']==16 and all(r['status']=='active_unknown' for r in value['pair_slots'])


def test_final_report_write_failure_still_closes_owned_lease(tmp_path,monkeypatch):
    path,plan,selector,loader,data=operation(tmp_path,monkeypatch);original=d.write_new;lease=Lease()
    def fail(path,value):
        if Path(path).name=='root-outcomes.json':raise OSError('authored report write failure')
        return original(path,value)
    monkeypatch.setattr(d,'write_new',fail);value=execute(path,tmp_path,loader,lease)
    assert value['status']=='failed' and 'finalization_error' in value and (tmp_path/'out/closed.json').exists() and lease.exits==1


def test_journal_known_prefix_survives_torn_tail_and_corruption(tmp_path):
    p=tmp_path/'events.jsonl';d.append(p,{'kind':'selection_intent'});d.append(p,{'kind':'root_outcome','slot':0,'status':'selected','group_id':'known'})
    with p.open('ab') as stream:stream.write(b'{torn')
    roots,slots,error=d.recover(p,512,2);assert roots[0]['group_id']=='known' and roots[1]['status']=='active_unknown' and error is None
    with p.open('ab') as stream:stream.write(b'\n{}\n')
    roots,slots,error=d.recover(p,512,2);assert roots[0]['group_id']=='known' and error is not None


def test_partial_root_outcome_io_recovers_known_selected_prefix(tmp_path,monkeypatch):
    path,plan,selector,loader,data=operation(tmp_path,monkeypatch);original=d.append
    def fail(path,value):
        if value.get('kind')=='root_outcome' and value['slot']==18:raise OSError('authored interrupted ledger')
        return original(path,value)
    monkeypatch.setattr(d,'append',fail);value=execute(path,tmp_path,loader)
    assert value['root_counts']=={'not_selected':16,'selected':2,'active_unknown':494}
    assert value['selected_slots'][0]['group_id']=='fake16' and not (tmp_path/'out/manifest.json').exists()


def test_builder_only_source_reads_pending_spec_rejected(tmp_path,monkeypatch):
    path,plan,selector,loader,data=operation(tmp_path,monkeypatch)
    spec={k:plan[k] for k in ('data','inventory_summary','corpus_attestations','admit_by_utc')}
    monkeypatch.setattr(d,'ROOTS',{'repo':tmp_path})
    # Invalid JSON proves builder does not interpret these bound data bytes.
    data['dataset'].write_bytes(b'not JSON, not read by builder')
    value=b.build(spec,module=d);assert value['maximum_seconds']==90 and value['data']==spec['data']
    with pytest.raises(ValueError):b.build({**spec,'pending_latest':True},module=d)


def test_original_full_three_is_frozen_ast_function_only():
    import ast
    raw=(d.ROOT/'scripts/chess_queen_coach_counterfactual_teacher_v1.py').read_bytes();assert d.sha(raw)==d.TEACHER
    functions=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='full_three']
    ns={'chess':chess};exec(compile(ast.Module(body=functions,type_ignores=[]),'authored_pinned_function','exec'),ns)
    task={'fen':FEN,'status':'completed','reference_pv':['e2e4','e7e5','g1f3']}
    assert ns['full_three'](task)
    task['reference_pv'][1]='e2e4';assert not ns['full_three'](task)
