"""CPU-only authored metadata/runtime fakes. No GPU, model, engine or HTTP."""
import builtins
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'prototype/chess_tutor_v1'))
import chess_queen_coach_tutor_v1 as child
import queen_tuned_runtime_v1 as ui


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);child.write_new(path,value);return path


@pytest.fixture
def case(tmp_path,monkeypatch):
    """All bytes in this repository are authored fakes, never real weights."""
    repo=tmp_path/'repo';repo.mkdir()
    bindings={}
    for role in child.ROLES:
        path=repo/'bindings'/(role+'.json');save(path,{'fixture':role,'dependencies':[]})
        bindings[role]={'path':str(path.relative_to(repo)),'sha256':child.digest(path)}
    sources=repo/bindings['sources']['path']
    sources.write_text(json.dumps({'checkout':str(repo/'upstream'),'files':{}}))
    bindings['sources']['sha256']=child.digest(sources)
    formatter=repo/bindings['formatter_manifest']['path']
    formatter.write_text(json.dumps({'schema':'chess.tuned-tutor-upstream-formatter-manifest.v1',
        'parent_source_manifest_sha256':bindings['sources']['sha256'],
        'diagnostic_protocol_sha256':bindings['diagnostic_protocol']['sha256'],
        'checkout':str(repo/'upstream'),'files':{'utils/instance_format.py':{'sha256':child.FORMATTER_SHA}}}))
    bindings['formatter_manifest']['sha256']=child.digest(formatter)
    training=repo/bindings['training_protocol']['path']
    training.write_text(json.dumps({'generation':child.SETTINGS,'training':{'seed':4082083}}))
    bindings['training_protocol']['sha256']=child.digest(training)
    fixed={role:bindings[role]['sha256'] for role in child.FIXED}
    identity={'path':str((repo/bindings['checkpoint']['path']).resolve()).replace('\\','/'),
        'sha256':fixed['checkpoint'],'step':64,'presentations':512,'parameter_count':1916928,
        'candidate_id':child.CANDIDATE,'source_sha256':fixed['runtime']}
    metadata=repo/bindings['checkpoint_metadata']['path'];metadata.write_text(json.dumps(identity))
    bindings['checkpoint_metadata']['sha256']=child.digest(metadata)
    selection=repo/bindings['selection']['path']
    selection.write_text(json.dumps({'status':'selected','protocol_sha256':fixed['training_protocol'],'selected':identity}))
    bindings['selection']['sha256']=child.digest(selection);fixed['selection']=child.digest(selection)
    monkeypatch.setattr(child,'FIXED',fixed)
    monkeypatch.setattr(child.metadata,'version',lambda name:child.VERSIONS[name])
    plan={'schema':child.PROTOCOL_SCHEMA,'profile_id':child.PROFILE,
        'implementation_sha256':child.digest(Path(child.__file__)),
        'scope':'root_dispatched_pre_activation_qualification_or_admitted_single_request',
        'generation':child.SETTINGS,'resources':child.RESOURCES,'outer_seconds':210,
        'python_version':'3.12.2','runtime_versions':child.VERSIONS,'bindings':bindings}
    protocol=save(repo/'protocol.json',plan)
    input_path=save(repo/'input.json',{'fen':chess.STARTING_FEN})
    result={'repo':repo,'plan':plan,'protocol':protocol,'sha':child.digest(protocol),'input':input_path,
        'identity':identity,'calls':[],'raw':None}
    def make_runtime(training,guard):
        class FixtureRuntime:
            def load(self):result['calls'].append('load')
            def load_adapter(self,identity):
                assert identity==result['identity'];result['calls'].append('load_adapter')
            def infer(self,row,identity):
                assert set(row)=={'input'} and 'response' not in row
                result['calls'].append('infer')
                if result.get('cancel_on_infer'):(repo/'cancelled.CANCEL').write_text('owned CPU fixture cancel')
                guard()
                raw=raw_for(row['input'],identity,plan)
                if result.get('raw_change'):result['raw_change'](raw)
                result['raw']=raw;result['before']=copy.deepcopy(raw)
                return raw
            def release_inactive(self,phase):
                assert list(repo.glob('*.raw.json')),'Raw must be retained before cleanup.'
                result['calls'].append('release_inactive')
            def verify_frozen(self):
                result['calls'].append('verify_frozen')
                return {'identical':not result.get('storage_bad',False),'before':'fixture','after':'fixture'}
        return FixtureRuntime()
    result['factory']=make_runtime
    result['guard']=lambda cancel:(lambda:None,[],dict(child.RESOURCES))
    return result


def raw_for(packet,identity,plan):
    value={'schema':'chess.queen-coach-sft-output.v2','status':'completed','finish_reason':'eos',
        'input':copy.deepcopy(packet),'raw_text':'An authored CPU fixture, not a learned explanation.',
        'candidate_id':child.CANDIDATE,'base_candidate_id':'queen-pawn-8/native-nf4-v2',
        'trained_adapter':copy.deepcopy(identity),'settings':{**child.SETTINGS,'temperature':0.0,'use_kv_cache':False},
        'parsed':{'engine_interventions':0,'rule_replacements':0,'fallback_used':False},
        'no_forward_input_audit':{'passed':True,'engine_evaluation_or_pv_input':False,
            'selected_move_supplied':'selected_uci' in packet},
        'quantization':{'base_decoder_inventory_before_lora':{'linear4bit_count':252},
            'actual_lora_dtype':'float32','actual_lora_parameters':1916928}}
    for field,role in (('adapter_sha256','runtime'),('base_generator_source_sha256','native'),
        ('base_nf4_source_sha256','nf4'),('nf4_protocol_sha256','kernel_protocol'),('kernel_receipt_sha256','kernel_receipt'),
        ('asset_manifest_sha256','assets'),('source_manifest_sha256','sources')):
        value[field]=plan['bindings'][role]['sha256']
    return value


def run(case,name='response'):
    return child.run_request(case['repo'],case['protocol'],case['sha'],case['input'],case['repo']/(name+'.json'),
        make_runtime=case['factory'],make_guard=case['guard'])


def test_one_fixed_adapter_is_loaded_before_infer_and_raw_is_untouched(case):
    result=run(case)
    assert result['status']=='completed' and result['raw_response'] is case['raw']
    assert result['raw_response']==case['before']
    assert result['entrypoint']['source_sha256']==child.digest(Path(child.__file__))
    assert result['entrypoint']['input_sha256']==child.digest(case['input'])
    assert child.read_json(case['repo']/'response.intent.json')['input_sha256']==result['entrypoint']['input_sha256']
    assert result['raw_response']['adapter_sha256']==child.FIXED['runtime']
    assert result['raw_response']['adapter_sha256']!=result['entrypoint']['source_sha256']
    assert case['calls']==['load','load_adapter','infer','release_inactive','verify_frozen']
    assert child.read_json(case['repo']/'response.raw.json')==case['before']
    with pytest.raises(ValueError,match='create-only'):run(case)
    assert len(case['calls'])==5


@pytest.mark.parametrize('selected',[False,True])
@pytest.mark.parametrize('black',[False,True])
def test_real_prior_history_black_white_selected_and_free_are_current_only(case,selected,black):
    board=chess.Board();history=[]
    if black:history.append(board.fen());board.push_uci('e2e4')
    packet={'fen':board.fen(),'history':history}
    if selected:packet['selected_uci']='e7e5' if black else 'e2e4'
    case['input'].write_text(json.dumps(packet))
    result=run(case)
    assert result['status']=='completed' and result['raw_response']['input']==packet
    assert result['raw_response']['no_forward_input_audit']['selected_move_supplied']==selected


@pytest.mark.parametrize('change', [
    {'fen_after':chess.STARTING_FEN}, {'reference_pv_uci':['e2e4']}, {'facts':{}},
    {'history':[chess.Board().fen()]}, {'history':['invalid']}, {'selected_uci':'e7e5'},
    {'selected_uci':'e2e2'}, {'history':'not a list'},
])
def test_future_or_invalid_packet_rejected_before_guard_or_model(case,change):
    packet={'fen':chess.STARTING_FEN,**change};case['input'].write_text(json.dumps(packet))
    result=run(case)
    assert result['status']=='failed' and result['raw_response'] is None and case['calls']==[]
    assert result['entrypoint']['failed_phase']=='validate'


def test_disjoint_or_future_history_is_rejected_before_model(case):
    board=chess.Board();board.push_uci('e2e4')
    case['input'].write_text(json.dumps({'fen':chess.STARTING_FEN,'history':[board.fen()]}))
    assert run(case)['status']=='failed' and not case['calls']


def test_protocol_or_checkpoint_tamper_has_durable_failed_attempt(case):
    checkpoint=case['repo']/case['plan']['bindings']['checkpoint']['path']
    checkpoint.write_text('different authored fixture bytes')
    result=run(case)
    assert result['status']=='failed' and 'Pinned file changed' in result['error']
    assert not case['calls']
    assert (case['repo']/'response.intent.json').is_file() and (case['repo']/'response.events.jsonl').is_file()
    assert child.read_json(case['repo']/'response.json')['raw_response'] is None


def test_wrong_protocol_hash_and_settings_fail_closed(case):
    with pytest.raises(ValueError):child.verify_protocol(case['repo'],case['protocol'],'0'*64)
    changed=copy.deepcopy(case['plan']);changed['generation']['maximum_seconds']=240
    altered=save(case['repo']/'altered.json',changed)
    with pytest.raises(ValueError,match='policy changed'):child.verify_protocol(case['repo'],altered,child.digest(altered))


def test_owned_cancellation_before_load_keeps_raw_absent(case):
    (case['repo']/'response.CANCEL').write_text('owned fixture cancel')
    result=run(case)
    assert result['status']=='failed' and 'owned cancellation' in result['error']
    assert result['raw_response'] is None and case['calls']==[]
    assert not (case['repo']/'response.raw.json').exists()


@pytest.mark.parametrize('change', [
    lambda raw:raw.update(adapter_sha256='0'*64),
    lambda raw:raw['settings'].update(maximum_seconds=240),
    lambda raw:raw['settings'].update(temperature=True),
    lambda raw:raw['trained_adapter'].update(step=256),
    lambda raw:raw['input'].update(selected_uci='e2e4'),
    lambda raw:raw.update(settings=None),
    lambda raw:raw.update(quantization=None),
    lambda raw:raw['parsed'].update(fallback_used=True),
])
def test_bad_raw_identity_mode_or_context_preserved_but_not_admitted(case,change):
    case['raw_change']=change
    result=run(case)
    assert result['status']=='failed' and result['raw_response']==case['before']
    assert (case['repo']/'response.raw.json').is_file()
    assert 'release_inactive' not in case['calls']


def test_backend_failure_and_frozen_storage_failure_never_retry(case):
    case['raw_change']=lambda raw:raw.update(status='failed',error='resource reserve: fixture')
    first=run(case)
    assert first['status']=='failed' and first['raw_response']==case['before']
    assert case['calls']==['load','load_adapter','infer']
    case.pop('raw_change');case['storage_bad']=True
    second=run(case,'second')
    assert second['status']=='failed' and 'Frozen storage changed' in second['error']


def test_no_learned_engine_trainer_evaluator_or_corpus_reads_in_cpu_route(case,monkeypatch):
    original_import=builtins.__import__;original_open=Path.open
    def imports(name,*args,**kwargs):
        if name.split('.')[0] in {'torch','transformers','bitsandbytes','peft','chess_queen_coach_sft_train_v2','chess_queen_coach_sft_eval_v1'} or name=='chess.engine':
            raise AssertionError('Forbidden runtime import in CPU test: '+name)
        return original_import(name,*args,**kwargs)
    def opens(path,*args,**kwargs):
        assert not any(name in str(path) for name in ('train.jsonl','references.jsonl','heldout-inputs','development.jsonl'))
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',imports);monkeypatch.setattr(Path,'open',opens)
    assert run(case)['status']=='completed'


def test_shipped_or_missing_admission_never_becomes_a_model_choice(tmp_path):
    path=save(tmp_path/'q.json',{'availability':False,'status':'not_admitted'})
    with pytest.raises(ui.Unavailable,match='unavailable pending quality'):
        ui.TunedQueenRunner(tmp_path,path)


def make_admission(case):
    repo=case['repo'];completed=run(case,'completed')
    cancel_input=save(repo/'cancel-input.json',{'fen':chess.STARTING_FEN})
    case['input']=cancel_input;case['cancel_on_infer']=True
    cancelled=run(case,'cancelled')
    bindings={'protocol':{'path':'protocol.json','sha256':case['sha']}}
    for prefix,input_name in (('completed','input.json'),('cancelled','cancel-input.json')):
        for role,path in (('input',repo/input_name),('entrypoint',repo/(prefix+'.json'))):
            bindings[prefix+'_'+role]={'path':str(path.relative_to(repo)),'sha256':child.digest(path)}
        args=[str(repo/'scripts/chess_queen_coach_tutor_v1.py'),'--protocol',str(case['protocol']),
            '--protocol-sha256',case['sha'],'--input',str(repo/input_name),'--out',str(repo/(prefix+'.json'))]
        worker=save(repo/(prefix+'-worker.json'),{'script':'scripts/chess_queen_coach_tutor_v1.py',
            'arguments_sha256':hashlib.sha256(json.dumps(args).encode()).hexdigest(),
            'status':'completed' if prefix=='completed' else 'failed','exit_code':0 if prefix=='completed' else 2,
            'child_exited_before_lease_release':True})
        bindings[prefix+'_worker']={'path':str(worker.relative_to(repo)),'sha256':child.digest(worker)}
    for kind in ('training_audit','heldout_quality_audit'):
        original=save(repo/(kind+'-original.json'),{'fixture_only':True,'status':'passed'})
        path=save(repo/(kind+'.json'),{'schema':'chess.tuned-tutor-closed-audit-binding.v1','kind':kind,
            'status':'passed','selected_adapter_sha256':child.FIXED['checkpoint'],'selection_sha256':child.FIXED['selection'],
            'expert_human_semantic_validation':False,'planned_ledger_closed':True,
            'original_report':{'path':str(original.relative_to(repo)),'sha256':child.digest(original)}})
        bindings[kind]={'path':str(path.relative_to(repo)),'sha256':child.digest(path)}
    actual_report=save(repo/'entrypoint-audit-original.json',{'fixture_only':True,'status':'passed',
        'scope':'Authored fake CPU evidence only; no actual model qualification or expert review.'})
    actual_audit=save(repo/'entrypoint-audit.json',{'schema':'chess.tuned-tutor-entrypoint-qualification-audit-binding.v1',
        'status':'passed','review_kind':'independent_local_agent_engineering','expert_human_semantic_validation':False,
        'entrypoint_sha256':case['plan']['implementation_sha256'],'protocol_sha256':case['sha'],
        'evidence':{key:bindings[key] for key in ('completed_input','completed_entrypoint','completed_worker',
            'cancelled_input','cancelled_entrypoint','cancelled_worker')},
        'observed':{'completed_eos_and_frozen_storage_verified':True,'cancelled_selected_adapter_load_completed':True,
            'cancelled_infer_started':True,'owned_cancellation_observed':True,'both_children_exited_before_lease_release':True},
        'original_report':{'path':str(actual_report.relative_to(repo)),'sha256':child.digest(actual_report)}})
    bindings['entrypoint_qualification_audit']={'path':str(actual_audit.relative_to(repo)),'sha256':child.digest(actual_audit)}
    decision=save(repo/'eligibility.json',{'schema':'chess.tuned-tutor-eligibility.v1','status':'eligible_for_optional_local_demo',
        'scope':'optional_local_demo_only','explicit_root_decision':True,'expert_human_semantic_validation':False,
        'selected_adapter_sha256':child.FIXED['checkpoint'],'selection_sha256':child.FIXED['selection'],
        'training_audit_sha256':bindings['training_audit']['sha256'],
        'heldout_quality_audit_sha256':bindings['heldout_quality_audit']['sha256'],
        'entrypoint_qualification_audit_sha256':bindings['entrypoint_qualification_audit']['sha256']})
    bindings['eligibility']={'path':'eligibility.json','sha256':child.digest(decision)}
    q=save(repo/'admission.json',{'availability':True,'status':'admitted_optional_local_demo',
        'profile_id':child.PROFILE,'candidate_id':child.CANDIDATE,
        'runner_sha256':child.digest(Path(ui.__file__)),'bindings':bindings})
    return q,completed,cancelled


def test_all_admission_evidence_is_required_and_exact_worker_command_binds_inputs(case):
    q,completed,cancelled=make_admission(case)
    runner=ui.TunedQueenRunner(case['repo'],q,child.digest(q))
    assert runner.maximum_seconds==210 and 'unverified' in runner.label
    command=runner.command({'worker':Path('fixture-worker'),'input':Path('fixture-input'),'out':Path('fixture-out')})
    assert command[command.index('--maximum-seconds')+1]=='180'
    assert 'chess_queen_coach_tutor_v1.py' in command[command.index('--')+1]
    saved=copy.deepcopy(completed)
    decorated=runner.decorate_result({'input':case['repo']/'input.json'},completed)
    assert decorated['ui_provenance']['response_binding_verified'] is True
    assert decorated['raw_response']==saved['raw_response'] and completed==saved
    cancelled_view=runner.decorate_result({'input':case['input']},cancelled)
    assert cancelled_view['status']=='failed' and 'ui_validation_error' not in cancelled_view
    assert cancelled_view['ui_provenance']['response_binding_verified'] is False
    with pytest.raises(ui.Unavailable,match='qualification hash'):ui.TunedQueenRunner(case['repo'],q)


@pytest.mark.parametrize('role',['heldout_quality_audit','entrypoint_qualification_audit','eligibility','completed_worker','cancelled_worker'])
def test_missing_quality_decision_or_closed_worker_blocks_admission(case,role):
    q,_,_=make_admission(case);value=child.read_json(q);del value['bindings'][role]
    q.write_text(json.dumps(value))
    with pytest.raises(ui.Unavailable):ui.TunedQueenRunner(case['repo'],q,child.digest(q))


def test_unrelated_worker_and_stale_result_rejected_without_rewriting_raw(case):
    q,completed,_=make_admission(case)
    value=child.read_json(q);worker=case['repo']/value['bindings']['completed_worker']['path']
    w=child.read_json(worker);w['arguments_sha256']='0'*64;worker.write_text(json.dumps(w))
    value['bindings']['completed_worker']['sha256']=child.digest(worker)
    audit_path=case['repo']/value['bindings']['entrypoint_qualification_audit']['path']
    audit=child.read_json(audit_path);audit['evidence']['completed_worker']=value['bindings']['completed_worker']
    audit_path.write_text(json.dumps(audit));value['bindings']['entrypoint_qualification_audit']['sha256']=child.digest(audit_path)
    decision_path=case['repo']/value['bindings']['eligibility']['path'];decision=child.read_json(decision_path)
    decision['entrypoint_qualification_audit_sha256']=child.digest(audit_path)
    decision_path.write_text(json.dumps(decision));value['bindings']['eligibility']['sha256']=child.digest(decision_path)
    q.write_text(json.dumps(value))
    with pytest.raises(ui.Unavailable,match='exact request'):ui.TunedQueenRunner(case['repo'],q,child.digest(q))
    runner=ui.TunedQueenRunner.__new__(ui.TunedQueenRunner)
    runner.plan=case['plan'];runner.identity=case['identity'];runner.protocol_sha256=case['sha'];runner.qualification_sha256='fixture'
    board=chess.Board();board.push_uci('e2e4');path=save(case['repo']/'different-input.json',{'fen':board.fen()})
    before=copy.deepcopy(completed)
    rejected=runner.decorate_result({'input':path},completed)
    assert rejected['status']=='failed' and rejected['raw_response']==before['raw_response']
    assert completed==before


def test_strict_json_duplicate_nonfinite_and_bounded_bytes(tmp_path):
    for index,raw in enumerate((b'{"a":1,"a":2}',b'{"a":NaN}',b'[]',b' '*(32768+1))):
        path=tmp_path/str(index);path.write_bytes(raw)
        with pytest.raises(ValueError):child.read_json(path,maximum=32768)


def test_input_snapshot_is_reused_for_intent_parsing_and_envelope(case,monkeypatch):
    original_bytes=case['input'].read_bytes();original_verify=child.verify_protocol
    def change_file_after_intent(*args):
        board=chess.Board();board.push_uci('e2e4')
        case['input'].write_text(json.dumps({'fen':board.fen()}))
        return original_verify(*args)
    monkeypatch.setattr(child,'verify_protocol',change_file_after_intent)
    result=run(case)
    assert result['status']=='completed' and result['raw_response']['input']['fen']==chess.STARTING_FEN
    expected=hashlib.sha256(original_bytes).hexdigest()
    assert result['entrypoint']['input_sha256']==expected
    assert child.read_json(case['repo']/'response.intent.json')['input_sha256']==expected
    assert child.digest(case['input'])!=expected


@pytest.mark.parametrize('prefix',['completed','cancelled'])
def test_rebinding_changed_input_at_same_path_cannot_qualify(case,prefix):
    q,_,_=make_admission(case);value=child.read_json(q)
    path=case['repo']/value['bindings'][prefix+'_input']['path']
    path.write_bytes(path.read_bytes()+b'\n') # Same normalized board, different request bytes.
    value['bindings'][prefix+'_input']['sha256']=child.digest(path)
    audit_path=case['repo']/value['bindings']['entrypoint_qualification_audit']['path']
    audit=child.read_json(audit_path);audit['evidence'][prefix+'_input']=value['bindings'][prefix+'_input']
    audit_path.write_text(json.dumps(audit));value['bindings']['entrypoint_qualification_audit']['sha256']=child.digest(audit_path)
    decision_path=case['repo']/value['bindings']['eligibility']['path'];decision=child.read_json(decision_path)
    decision['entrypoint_qualification_audit_sha256']=child.digest(audit_path)
    decision_path.write_text(json.dumps(decision));value['bindings']['eligibility']['sha256']=child.digest(decision_path)
    q.write_text(json.dumps(value))
    with pytest.raises(ui.Unavailable,match='input byte binding'):ui.TunedQueenRunner(case['repo'],q,child.digest(q))


@pytest.mark.parametrize('mutation',['missing_report','wrong_evidence','missing_phase','unbound_decision','human_claim'])
def test_independent_actual_qualification_audit_fails_closed(case,mutation):
    q,_,_=make_admission(case);value=child.read_json(q)
    path=case['repo']/value['bindings']['entrypoint_qualification_audit']['path'];audit=child.read_json(path)
    if mutation=='missing_report':(case['repo']/audit['original_report']['path']).unlink()
    if mutation=='wrong_evidence':audit['evidence']['cancelled_input']['sha256']='0'*64
    if mutation=='missing_phase':audit['observed']['cancelled_infer_started']=False
    if mutation=='human_claim':audit['expert_human_semantic_validation']=True
    path.write_text(json.dumps(audit));value['bindings']['entrypoint_qualification_audit']['sha256']=child.digest(path)
    if mutation!='unbound_decision':
        decision_path=case['repo']/value['bindings']['eligibility']['path'];decision=child.read_json(decision_path)
        decision['entrypoint_qualification_audit_sha256']=child.digest(path)
        decision_path.write_text(json.dumps(decision));value['bindings']['eligibility']['sha256']=child.digest(decision_path)
    q.write_text(json.dumps(value))
    with pytest.raises(ui.Unavailable):ui.TunedQueenRunner(case['repo'],q,child.digest(q))


def test_only_exact_manifest_declared_upstream_source_may_be_outside_repo(case,tmp_path):
    checkout=tmp_path/'pinned-source';checkout.mkdir()
    path=checkout/'source.py';path.write_text('# authored source fixture')
    item={'path':str(path),'sha256':child.digest(path)}
    manifest={'checkout':str(checkout),'files':{'source.py':{'sha256':item['sha256']}}}
    assert child.dependency(case['repo'],item,manifest)==path
    with pytest.raises(ValueError):child.bound(case['repo'],item)
    with pytest.raises(ValueError):child.dependency(case['repo'],item,{'checkout':str(checkout),'files':{}})
    other=tmp_path/'unrelated.py';other.write_text('# not inside checkout')
    with pytest.raises(ValueError):child.dependency(case['repo'],{'path':str(other),'sha256':child.digest(other)},manifest)


def test_formatter_needs_explicit_manifest_entry_and_unchanged_bytes(case,tmp_path):
    checkout=tmp_path/'formatter-checkout';(checkout/'utils').mkdir(parents=True)
    path=checkout/'utils/instance_format.py';path.write_text('# authored diagnostic formatter')
    item={'path':str(path),'sha256':child.digest(path)}
    manifest={'checkout':str(checkout),'files':{}}
    with pytest.raises(ValueError):child.dependency(case['repo'],item,manifest)
    manifest['files']['utils/instance_format.py']={'sha256':item['sha256']}
    assert child.dependency(case['repo'],item,manifest)==path
    path.write_text('# different bytes')
    with pytest.raises(ValueError):child.dependency(case['repo'],item,manifest)


def test_traversal_and_symlink_substitution_are_rejected_even_for_identical_bytes(case,tmp_path):
    checkout=tmp_path/'source-links';checkout.mkdir()
    target=checkout/'target.py';target.write_text('# identical fixture')
    item={'path':str(checkout/'sub'/'..'/'target.py'),'sha256':child.digest(target)}
    manifest={'checkout':str(checkout),'files':{'target.py':{'sha256':item['sha256']},'alias.py':{'sha256':item['sha256']}}}
    with pytest.raises(ValueError,match='Traversal'):child.dependency(case['repo'],item,manifest)
    alias=checkout/'alias.py'
    try:alias.symlink_to(target)
    except OSError:pytest.skip('Creating a source symlink is unavailable on this host.')
    with pytest.raises(ValueError,match='symlink'):child.dependency(case['repo'],{'path':str(alias),'sha256':item['sha256']},manifest)
    internal=case['repo']/'internal.py';internal.write_text(target.read_text())
    external_alias=checkout/'into-repo.py';external_alias.symlink_to(internal)
    manifest['files']['into-repo.py']={'sha256':item['sha256']}
    with pytest.raises(ValueError):child.dependency(case['repo'],{'path':str(external_alias),'sha256':item['sha256']},manifest)
    with pytest.raises(ValueError):child.bound(case['repo'],{'path':str(external_alias),'sha256':item['sha256']})
