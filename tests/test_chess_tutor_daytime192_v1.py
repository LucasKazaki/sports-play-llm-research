"""Authored CPU engineering fixtures only. No actual audit/model is invented."""
import copy
from datetime import datetime,timezone
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('daytime192_test_runner',ROOT/'prototype/chess_tutor_daytime192_v1/runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
child=runner.child
spec=importlib.util.spec_from_file_location('daytime192_test_server',ROOT/'prototype/chess_tutor_daytime192_v1/server.py')
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(child.safe.serialized(value),encoding='utf-8',newline='\n')
    return {'path':str(path),'sha256':child.digest(path)}


def data():
    current,_=child.packet({'fen':chess.STARTING_FEN})
    identity={'sha256':child.FIXED['checkpoint'],'step':192,'presentations':1536,
        'parent_presentations':512,'parameter_count':1916928,'candidate_id':child.CANDIDATE,
        'source_sha256':child.FIXED['runtime'],'warm_start':{'sha256':child.safe.FIXED['checkpoint']}}
    plan={'implementation_sha256':child.digest(child.__file__),
        'bindings':{role:{'sha256':value} for role,value in child.FIXED.items()}}
    plan['bindings'].update({name:{'sha256':name*2} for name in ('assets','sources')})
    raw={'status':'completed','finish_reason':'eos','input':current,'candidate_id':child.CANDIDATE,
        'base_candidate_id':'queen-pawn-8/native-nf4-v2','trained_adapter':identity,
        'warm_start':identity['warm_start'],'raw_text':'ANALYSIS: authored fixture only',
        'decoded_text':'Authored display fixture, not model output.','settings':{**child.SETTINGS,'use_kv_cache':False},
        'no_forward_input_audit':{'passed':True,'engine_evaluation_or_pv_input':False,'selected_move_supplied':False},
        'parsed':{'engine_interventions':0,'rule_replacements':0,'fallback_used':False},
        'quantization':{'actual_lora_dtype':'float32','actual_lora_parameters':1916928,
            'base_decoder_inventory_before_lora':{'linear4bit_count':252}}}
    for field,role in (('adapter_sha256','runtime'),('qualified_runtime_source_sha256','qualified_runtime'),
        ('base_generator_source_sha256','native'),('base_nf4_source_sha256','nf4'),
        ('nf4_protocol_sha256','kernel_protocol'),('kernel_receipt_sha256','kernel_receipt'),
        ('asset_manifest_sha256','assets'),('source_manifest_sha256','sources')):
        raw[field]=plan['bindings'][role]['sha256']
    envelope={'schema':child.ENVELOPE_SCHEMA,'status':'completed','error':None,'raw_response':raw,
        'entrypoint':{'profile_id':child.PROFILE,'source_sha256':plan['implementation_sha256'],
            'input_sha256':'0'*64,'protocol_sha256':'1'*64,'outer_seconds':210,
            'selection_sha256':child.FIXED['selection'],'fixed_checkpoint_sha256':child.FIXED['checkpoint'],
            'trained_identity':identity,'resource_policy':dict(child.RESOURCES),'frozen_storage':{'identical':True},
            'raw_response_sha256':child.safe.raw_digest(raw)}}
    return current,identity,plan,raw,envelope


def worker(arguments,completed=True):
    return {'schema':'chess.owned-worker.v2','launch_profile':runner.PROFILE,
        'source_sha256':child.FIXED['worker'],'script':'scripts/chess_queen_daytime192_tutor_v1.py',
        'arguments_sha256':hashlib.sha256(json.dumps(arguments).encode()).hexdigest(),
        'maximum_seconds_after_GO':240,'owned_member_before_go':True,'owned_job_exit_verified':True,
        'child_exited_before_lease_release':True,'status':'completed' if completed else 'failed',
        'exit_code':0 if completed else 2,'child_pid':17,'ownership':{
            'before_go':{'child_identity':{'pid':17},'popen_handle_pid_matches':True,
                'member_of_explicit_creator_job':True,'creator_member_of_explicit_child_job':False,
                'job_handle_passed_to_child':False,'complete_job_pids':[17]},
            'after_go_complete_job_pids':[17],
            'closure':{'complete_job_pids':[],'child_stable_handle_exited':True,'actual_job_handle_closed':True}}}


@pytest.mark.parametrize('fen,move',[(chess.STARTING_FEN,'e2e4'),
    ('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1','e7e5')])
def test_free_selected_and_black_packet(fen,move):
    current,board=child.packet({'fen':fen});assert board.fen()==current['fen'] and current['history']==[]
    current,_=child.packet({'fen':fen,'selected_uci':move});assert current['selected_uci']==move


@pytest.mark.parametrize('extra', [{'history':[]},{'score':12},{'pv':['e2e4']},{'response':'teacher'},
    {'next_fen':chess.STARTING_FEN},{'facts':{'check':True}},{'mode':'selected'}])
def test_forbidden_input(extra):
    with pytest.raises(ValueError):child.packet({'fen':chess.STARTING_FEN,**extra})


def test_illegal_move_and_current_only_projection():
    with pytest.raises(ValueError):child.packet({'fen':chess.STARTING_FEN,'selected_uci':'e2e5'})
    packet,context,_=server.preview_packet({'position':{'fen':chess.STARTING_FEN,'moves':['e2e4']},
        'selected_uci':'e7e5','selected_move_origin':'stockfish_selection'})
    assert set(packet)=={'fen','selected_uci'} and context['position']['moves']==['e2e4']
    assert context['selected_move_origin']=='stockfish_selection'
    assert 'stockfish' not in child.canonical(packet)


@pytest.mark.parametrize('field,value',[('adapter_sha256','wrong'),('qualified_runtime_source_sha256','wrong'),
    ('candidate_id','baseline'),('warm_start',{}),('settings',{}),('quantization',{}),('input',{})])
def test_native_source_semantics(field,value):
    current,identity,plan,raw,_=data();child.validate_raw(raw,current,identity,plan)
    raw[field]=value
    with pytest.raises(ValueError):child.validate_raw(raw,current,identity,plan)


@pytest.mark.parametrize('key',['engine_interventions','rule_replacements','fallback_used'])
def test_no_move_repair(key):
    current,identity,plan,raw,_=data();raw['parsed'][key]=1
    with pytest.raises(ValueError):child.validate_raw(raw,current,identity,plan)


def test_exact_input_bytes_distinct_from_canonical_and_raw_null_cancel(tmp_path):
    current,identity,plan,raw,envelope=data();path=tmp_path/'input.json'
    minimal={'fen':chess.STARTING_FEN};save(path,minimal)
    envelope['entrypoint']['input_sha256']=child.digest(path)
    runner.check_record_input(envelope,path)
    assert child.digest(path)!=hashlib.sha256(child.canonical(current).encode()).hexdigest()
    envelope.update(status='failed',error='RuntimeError: owned cancellation',raw_response=None)
    runner.check_envelope(envelope,plan,identity,'1'*64);runner.check_record_input(envelope,path)
    path.write_text(json.dumps(minimal,separators=(',',':')),encoding='utf-8')
    with pytest.raises(ValueError,match='bytes'):runner.check_record_input(envelope,path)


@pytest.mark.parametrize('key,value',[('owned_member_before_go',False),('owned_job_exit_verified',False),
    ('child_exited_before_lease_release',False),('source_sha256','wrong'),('arguments_sha256','wrong'),
    ('maximum_seconds_after_GO',180)])
def test_worker_ownership_and_vector(key,value):
    w=worker(['authored']);runner.check_worker(w,['authored'],completed=True);w[key]=value
    with pytest.raises(ValueError):runner.check_worker(w,['authored'],completed=True)


def test_complete_job_lists_are_required():
    w=worker(['authored']);w['ownership']['before_go']['complete_job_pids']=[17,19]
    with pytest.raises(ValueError):runner.check_worker(w,['authored'],completed=True)
    w=worker(['authored']);w['ownership']['after_go_complete_job_pids']=[17,17]
    with pytest.raises(ValueError):runner.check_worker(w,['authored'],completed=True)
    w=worker(['authored']);w['ownership']['closure']['complete_job_pids']=[19]
    with pytest.raises(ValueError):runner.check_worker(w,['authored'],completed=True)


def fake_admission(tmp_path,monkeypatch):
    """Explicit synthetic documents, never usable as actual qualification."""
    current,identity,plan,raw,envelope=data();bindings={};protocol=tmp_path/'protocol.json'
    bindings['protocol']=save(protocol,{'synthetic_not_execution_evidence':True})
    protocol_sha=bindings['protocol']['sha256'];plan['bindings']['worker']=save(tmp_path/'fake-worker.py',{'not_real':True})
    for prefix in ('completed','cancelled'):
        input_path=tmp_path/(prefix+'-input.json');out=tmp_path/(prefix+'.json')
        bindings[prefix+'_input']=save(input_path,{'fen':chess.STARTING_FEN})
        record=copy.deepcopy(envelope);record['entrypoint']['protocol_sha256']=protocol_sha
        record['entrypoint']['input_sha256']=child.digest(input_path)
        if prefix=='cancelled':record.update(status='failed',error='RuntimeError: owned cancellation',raw_response=None)
        else:save(out.with_name(out.stem+'.raw.json'),raw)
        bindings[prefix+'_entrypoint']=save(out,record)
        args=runner.worker_arguments(tmp_path,protocol,protocol_sha,input_path,out)
        bindings[prefix+'_worker']=save(tmp_path/(prefix+'-worker.json'),worker(args,prefix=='completed'))
    original=save(tmp_path/'synthetic-original-review.json',{'synthetic':True,'status':'not_an_actual_audit'})
    scope=save(tmp_path/'synthetic-scope-amendment.json',{'synthetic':True,'not_an_actual_audit':True})
    bindings['root_decision']=save(tmp_path/'synthetic-root-decision.json',{
        'schema':'chess.daytime192.limited-private-preview-decision.v1',
        'status':'conditional_research_preview_permitted_after_actual_entrypoint_qualification',
        'cutoff_utc':child.CUTOFF,'profile_id':child.PROFILE,'candidate_id':child.CANDIDATE,'selected_step':192,
        'checkpoint_sha256':child.FIXED['checkpoint'],'selection_sha256':child.FIXED['selection'],
        'training_audit_sha256':original['sha256'],'held_failure_audit_sha256':original['sha256'],
        'held_scope_amendment_sha256':scope['sha256']})
    monkeypatch.setattr(runner,'ROOT_DECISION_SHA',bindings['root_decision']['sha256'])
    for name in ('training_audit','held_audit'):
        bindings[name]=save(tmp_path/(name+'.json'),{'schema':'chess.daytime192-closed-audit-binding.v1',
            'status':'passed','kind':name,'planned_ledger_closed':True,'expert_human_semantic_validation':False,
            'selected_adapter_sha256':child.FIXED['checkpoint'],'selection_sha256':child.FIXED['selection'],
            'experiment_status':'failed','planned':96,'outcome_counts':{'completed':9,'failed':1,'not_run':86},
            'original_report':original,'scope_amendment':scope})
    bindings['entrypoint_audit']=save(tmp_path/'entrypoint-audit.json',{
        'schema':'chess.daytime192-entrypoint-audit-binding.v1','status':'passed',
        'review_kind':'independent_local_agent_engineering','expert_human_semantic_validation':False,
        'entrypoint_sha256':plan['implementation_sha256'],'protocol_sha256':protocol_sha,
        'evidence':{key:bindings[key] for key in runner.EVIDENCE},'original_report':original,
        'observed':{'completed_eos_and_frozen_storage_verified':True,
            'cancelled_selected_adapter_load_completed':True,'cancelled_infer_started':True,
            'owned_cancellation_observed':True,'both_children_exited_before_lease_release':True}})
    bindings['eligibility']=save(tmp_path/'eligibility.json',{'schema':'chess.daytime192-preview-eligibility.v1',
        'status':'eligible_for_optional_research_preview','scope':'local_research_tutor_feedback_only',
        'explicit_root_decision':True,'expert_human_semantic_validation':False,
        'selected_adapter_sha256':child.FIXED['checkpoint'],'selection_sha256':child.FIXED['selection'],
        'root_decision_sha256':bindings['root_decision']['sha256'],
        **{name+'_sha256':bindings[name]['sha256'] for name in ('training_audit','held_audit','entrypoint_audit')}})
    q={'schema':'chess.daytime192-preview-admission.v1','availability':True,
        'status':'admitted_optional_research_preview','profile_id':child.PROFILE,'candidate_id':child.CANDIDATE,
        'runner_sha256':child.digest(runner.__file__),'bindings':bindings}
    path=tmp_path/'admission.json';save(path,q)
    monkeypatch.setattr(child,'verify_protocol',lambda *a,**k:(plan,{},identity,{}))
    monkeypatch.setattr(child,'before_cutoff',lambda *a,**k:None)
    return path,q,plan,identity


def test_closed_failed_held_audit_can_support_explicit_limited_decision(tmp_path,monkeypatch):
    path,q,_,_=fake_admission(tmp_path,monkeypatch)
    value=runner.PreviewRunner(tmp_path,path,child.digest(path));assert value.identity['step']==192


@pytest.mark.parametrize('missing',['training_audit','held_audit','entrypoint_audit','eligibility','cancelled_input'])
def test_missing_gate_fails_closed(tmp_path,monkeypatch,missing):
    path,q,_,_=fake_admission(tmp_path,monkeypatch);q['bindings'].pop(missing);save(path,q)
    with pytest.raises(runner.Unavailable):runner.PreviewRunner(tmp_path,path,child.digest(path))


def test_cancel_same_path_rebinding_rejected(tmp_path,monkeypatch):
    path,q,_,_=fake_admission(tmp_path,monkeypatch)
    binding=q['bindings']['cancelled_input'];p=Path(binding['path'])
    p.write_text('{"fen":'+json.dumps(chess.STARTING_FEN)+'}',encoding='utf-8')
    binding['sha256']=child.digest(p)
    audit_path=Path(q['bindings']['entrypoint_audit']['path']);audit=child.read_json(audit_path)
    audit['evidence']['cancelled_input']=binding
    q['bindings']['entrypoint_audit']=save(audit_path,audit)
    eligibility_path=Path(q['bindings']['eligibility']['path']);elig=child.read_json(eligibility_path)
    elig['entrypoint_audit_sha256']=q['bindings']['entrypoint_audit']['sha256']
    q['bindings']['eligibility']=save(eligibility_path,elig);save(path,q)
    with pytest.raises(runner.Unavailable,match='bytes'):runner.PreviewRunner(tmp_path,path,child.digest(path))


def test_no_actual_config_is_enabled():
    with pytest.raises(runner.Unavailable,match='unavailable'):runner.PreviewRunner(ROOT)


def test_display_projection_keeps_native_and_envelope_untouched(tmp_path,monkeypatch):
    path,q,_,_=fake_admission(tmp_path,monkeypatch);r=runner.PreviewRunner(tmp_path,path,child.digest(path))
    b=q['bindings'];out=Path(b['completed_entrypoint']['path']);envelope=child.read_json(out)
    before=copy.deepcopy(envelope);before_bytes=out.read_bytes()
    job={'input':Path(b['completed_input']['path']),'out':out,'worker':Path(b['completed_worker']['path']),
        'input_sha256':b['completed_input']['sha256'],'request_packet':{'fen':chess.STARTING_FEN}}
    display=r.decorate_result(job,envelope)
    assert display['ui_provenance']['response_binding_verified'] is True
    assert display['native_raw_response']==before['raw_response'] and display['entrypoint_envelope']==before
    assert display['raw_text']==before['raw_response']['raw_text']
    assert envelope==before and out.read_bytes()==before_bytes
    job['request_packet']['selected_uci']='e2e4'
    assert r.decorate_result(job,envelope)['ui_validation_error']


def test_new_profile_does_not_gain_original_rule_qualification():
    base=server.base_module();current,identity,plan,raw,envelope=data()
    import draft_checks_v1
    assert not draft_checks_v1.original_profile(raw,worker([]),False,'not-original-qualification.json')


def test_async_busy_owned_cancel_without_a_process(tmp_path,monkeypatch):
    base=server.base_module()
    monkeypatch.setattr(base.threading.Thread,'start',lambda self:None)
    class Fake:
        fixture=True;label='Authored CPU fixture'
        def verify(self):pass
    jobs=base.CoachingJobs(tmp_path,server.preview_packet,Fake())
    payload={'position':{'fen':chess.STARTING_FEN,'moves':[]}}
    first=jobs.start(payload)
    with pytest.raises(base.JobBusy):jobs.start(payload)
    jobs.cancel(first['request_id']);job=jobs.jobs[first['request_id']]
    assert job['cancel'].is_file() and job['status']=='stopping'
    assert child.digest(job['input'])==job['input_sha256']


def test_cutoff_and_path_membership(tmp_path):
    child.before_cutoff(datetime(2026,10,16,21,59,tzinfo=timezone.utc))
    with pytest.raises(ValueError):child.before_cutoff(datetime(2026,10,16,22,0,tzinfo=timezone.utc))
    p=tmp_path/'f';p.write_text('source',encoding='utf-8')
    assert child.inside(tmp_path,{'path':'f','sha256':child.digest(p)})==p.resolve()
    with pytest.raises(ValueError):child.inside(tmp_path,{'path':'../f','sha256':child.digest(p)})
    with pytest.raises(ValueError):child.inside(tmp_path,{'path':'f','sha256':'0'*64})


def test_page_has_no_generic_file_route_and_preserves_controls():
    assert server.page_asset('/../../scripts/a.py') is None
    assert server.page_asset('/preview.css')[1]=='text/css; charset=utf-8'
    class Tags(HTMLParser):
        def __init__(self):super().__init__();self.ids=[];self.check=None
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if 'id' in a:self.ids.append(a['id'])
            if a.get('id')=='use-model':self.check=a
    page=server.page_asset('/')[0].decode('utf-8');p=Tags();p.feed(page)
    assert len(p.ids)==len(set(p.ids)) and {'ask-coach','coach-return','export','preview-heading'}<=set(p.ids)
    assert 'disabled' in p.check and 'checked' not in p.check
    assert 'Explanations may be wrong.' in page and '192 training updates' in page


def test_imports_have_no_learning_framework():
    assert not {'torch','transformers','peft','bitsandbytes','accelerate'}&set(sys.modules)


def fake_entry(tmp_path,monkeypatch,mode='completed'):
    current,identity,plan,raw,_=data();input_path=tmp_path/'input.json'
    save(input_path,{'fen':chess.STARTING_FEN});out=tmp_path/'response.json';calls=[]
    monkeypatch.setattr(child,'before_cutoff',lambda *a,**k:None)
    runtime_plan={'no_corpus_paths':True}
    monkeypatch.setattr(child,'verify_protocol',lambda *a,**k:(plan,runtime_plan,identity,{}))
    class Runtime:
        def load(self):calls.append('load')
        def load_adapter(self,value):assert value==identity;calls.append('selected192')
        def infer(self,row,value):
            calls.append('infer');assert row=={'input':current} and value==identity
            if mode=='cancel':out.with_suffix('.CANCEL').write_text('owned fixture',encoding='utf-8');self.guard()
            return raw
        def release_inactive(self,phase):
            calls.append('cleanup')
            if mode=='cleanup_failure':raise RuntimeError('authored cleanup failure')
        def verify_frozen(self):calls.append('storage');return {'identical':True}
    def factory(p,guard):assert p==runtime_plan;r=Runtime();r.guard=guard;return r
    result=child.run_request(tmp_path,tmp_path/'unused-protocol','1'*64,input_path,out,
        make_runtime=factory,make_guard=lambda cancel:(lambda:None,[],dict(child.RESOURCES)))
    return result,out,input_path,calls,raw


def test_authored_entry_completion_retains_native_dictionary_before_cleanup(tmp_path,monkeypatch):
    result,out,input_path,calls,raw=fake_entry(tmp_path,monkeypatch)
    assert result['status']=='completed' and result['raw_response'] is raw
    assert calls==['load','selected192','infer','cleanup','storage']
    assert out.with_name('response.raw.json').read_bytes()==child.safe.serialized(raw).encode()
    assert result['entrypoint']['input_sha256']==child.digest(input_path)
    events=[json.loads(line) for line in out.with_name('response.events.jsonl').read_text().splitlines()]
    assert {'phase':'load_selected_adapter','status':'completed'} in [{k:v for k,v in e.items() if k!='at'} for e in events]


def test_authored_entry_owned_cancellation_after_selected_load(tmp_path,monkeypatch):
    result,out,input_path,calls,_=fake_entry(tmp_path,monkeypatch,'cancel')
    assert result['status']=='failed' and result['raw_response'] is None
    assert calls==['load','selected192','infer'] and 'owned cancellation' in result['error']
    assert result['entrypoint']['failed_phase']=='infer' and result['entrypoint']['input_sha256']==child.digest(input_path)
    assert out.is_file() and not out.with_name('response.raw.json').exists()


def test_cleanup_failure_keeps_raw_and_prevents_success(tmp_path,monkeypatch):
    result,out,_,calls,raw=fake_entry(tmp_path,monkeypatch,'cleanup_failure')
    assert result['status']=='failed' and result['raw_response']==raw
    assert out.with_name('response.raw.json').is_file() and 'storage' not in calls


def test_entry_protocol_failure_is_closed_and_create_only(tmp_path,monkeypatch):
    p=tmp_path/'input.json';save(p,{'fen':chess.STARTING_FEN});out=tmp_path/'response.json'
    monkeypatch.setattr(child,'before_cutoff',lambda *a,**k:None)
    def fail(*a,**k):raise ValueError('authored bad protocol')
    monkeypatch.setattr(child,'verify_protocol',fail)
    result=child.run_request(tmp_path,tmp_path/'absent','0'*64,p,out)
    assert result['status']=='failed' and result['entrypoint']['failed_phase']=='validate'
    assert out.with_name('response.intent.json').is_file() and out.with_name('response.events.jsonl').is_file()
    with pytest.raises(ValueError,match='create-only'):child.run_request(tmp_path,tmp_path/'absent','0'*64,p,out)


def synthetic_protocol(tmp_path,monkeypatch):
    """A complete tiny fake dependency closure, without any real tensor read."""
    def b(role,value):return save(tmp_path/(role+'.json'),value)
    bindings={name:b(name,{'synthetic_source':name}) for name in child.ROLES}
    bindings['sources']=b('sources',{'checkout':str(tmp_path/'upstream'),'files':{}})
    bindings['kernel_protocol']=b('kernel_protocol',{'dependencies':[]})
    bindings['diagnostic_protocol']=b('diagnostic_protocol',{'dependencies':[]})
    bindings['formatter_manifest']=b('formatter_manifest',{
        'schema':'chess.tuned-tutor-upstream-formatter-manifest.v1',
        'parent_source_manifest_sha256':bindings['sources']['sha256'],
        'diagnostic_protocol_sha256':bindings['diagnostic_protocol']['sha256'],
        'checkout':str(tmp_path/'upstream'),'files':{'utils/instance_format.py':{'sha256':child.safe.FORMATTER_SHA}}})
    warm={'sha256':child.safe.FIXED['checkpoint']}
    bindings['training_protocol']=b('training_protocol',{'generation':child.SETTINGS,'training':{'seed':41},
        'warm_start':warm,'data':{'MUST_NOT_FOLLOW':'absent-private-held-reference'}})
    identity={'step':192,'presentations':1536,'parent_presentations':512,'parameter_count':1916928,
        'sha256':bindings['checkpoint']['sha256'],'candidate_id':child.CANDIDATE,
        'source_sha256':bindings['runtime']['sha256'],'path':Path(bindings['checkpoint']['path']).as_posix(),
        'warm_start':warm}
    bindings['checkpoint_metadata']=b('checkpoint_metadata',identity)
    bindings['selection']=b('selection',{'status':'selected','protocol_sha256':bindings['training_protocol']['sha256'],'selected':identity})
    monkeypatch.setattr(child,'FIXED',{name:bindings[name]['sha256'] for name in child.FIXED})
    monkeypatch.setattr(child,'PREVIEW_FILES',());monkeypatch.setattr(child,'UI_FILES',())
    selected={name:item for name,item in bindings.items() if name not in
        {'selection','checkpoint','checkpoint_metadata','training_protocol','kernel_receipt','preview_manifest'}}
    bindings['preview_manifest']=b('preview_manifest',{'schema':'chess.daytime192-preview-sources.v1','files':list(selected.values())})
    plan={'schema':child.PROTOCOL_SCHEMA,'profile_id':child.PROFILE,'implementation_sha256':child.digest(child.__file__),
        'scope':'root_qualification_or_explicitly_admitted_research_preview','cutoff_utc':child.CUTOFF,
        'outer_seconds':210,'worker_seconds_after_go':240,'runner_seconds':270,'generation':dict(child.SETTINGS),
        'resources':dict(child.RESOURCES),'runtime_versions':child.safe.VERSIONS,'python_version':'3.12.2','bindings':bindings}
    path=tmp_path/'protocol.json';save(path,plan);return path,plan


def test_protocol_builds_minimal_inference_plan_without_following_data(tmp_path,monkeypatch):
    path,plan=synthetic_protocol(tmp_path,monkeypatch)
    _,runtime,identity,_=child.verify_protocol(tmp_path,path,child.digest(path),check_environment=False)
    assert set(runtime)=={'generation','training','warm_start','kernel_protocol','kernel_receipt'}
    assert runtime['training']=={'seed':41} and identity['step']==192


@pytest.mark.parametrize('field,value',[('outer_seconds',211),('worker_seconds_after_go',180),
    ('runner_seconds',210),('cutoff_utc','2026-10-17T22:00:00+00:00'),('generation',{}),('resources',{})])
def test_protocol_policy_tamper(tmp_path,monkeypatch,field,value):
    path,plan=synthetic_protocol(tmp_path,monkeypatch);plan[field]=value;save(path,plan)
    with pytest.raises(ValueError):child.verify_protocol(tmp_path,path,child.digest(path),check_environment=False)


def test_protocol_rejects_missing_transitive_source(tmp_path,monkeypatch):
    path,plan=synthetic_protocol(tmp_path,monkeypatch)
    p=Path(plan['bindings']['preview_manifest']['path']);manifest=child.read_json(p)
    manifest['files'].pop();plan['bindings']['preview_manifest']=save(p,manifest);save(path,plan)
    with pytest.raises(ValueError,match='closure'):child.verify_protocol(tmp_path,path,child.digest(path),check_environment=False)
