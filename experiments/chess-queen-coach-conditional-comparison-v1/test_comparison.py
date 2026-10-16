"""Authored metadata/chess fixtures only; no private rows or runtime backend."""
from pathlib import Path
from types import SimpleNamespace
import copy,sys
import pytest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import comparison_contract as contract
import build_protocol as builder
import grade_conditional as grade


def science_fixture(monkeypatch):
    shared={key:{'authored':key}for key in contract.FIELDS}
    shared['raw_provenance']={'candidate_id':contract.ORIGINAL}
    def bound(value):return Path(value['path'])
    def binding(name):return {'path':name,'sha256':'sha-'+name}
    control={'path':'current.pt','sha256':'current192','step':192,'presentations':1536,
        'parameter_count':1916928,'candidate_id':contract.ORIGINAL}
    treatment={'path':'conditional.pt','sha256':'conditional192','step':192,'presentations':1536,
        'parameter_count':1916928,'candidate_id':contract.TREATMENT,'source_sha256':'runtime',
        'warm_start':binding('original64'),'target_manifest':binding('targets'),
        'target_protocol':binding('export')}
    train={'selection_method':contract.METHOD,'fixed_treatment_step':192,
        'training':{'updates':192,'presentations':1536},'comparison_control':control,
        'counterfactual_runtime':{'sha256':'runtime'},'warm_start':binding('original64'),
        'corpus_manifest':binding('targets'),'target_export_protocol':binding('export'),
        'expected_worker_script':'authored.py','expected_worker_arguments':['authored.py']}
    monitors=[{'step':step,'status':'completed','raw_planned':6,'raw_completed':6,
        'nll_completed':96,'response_token_nll':1.25,'identity':copy.deepcopy(treatment)}
        for step in (0,48,96,192)]
    selected={'status':'selected','selection_method':contract.METHOD,'heldout_opened':False,
        'protocol_sha256':'sha-train','selected':treatment,'conditions':monitors}
    run={'status':'completed','updates_completed':192,'presentations_completed':1536,
        'partial_accumulation':0,'active_unknown':None,'frozen_storage':{'identical':True},
        'protocol_sha256':'sha-train'}
    audit={'status':'passed','protocol_sha256':'sha-train','run_sha256':'sha-run','selection_sha256':'sha-selection',
        'worker_sha256':'sha-worker'}
    files={'shared':shared,'train':train,'run':run,'selection':selected,'audit':audit,'worker':{}}
    plan={**copy.deepcopy(shared),'schema':'chess.conditional-comparison-science.v1',
        'preserved_shared_science':binding('shared'),'conditional_training_protocol':binding('train'),
        'conditional_training_run':binding('run'),'conditional_selection':binding('selection'),
        'conditional_training_audit':binding('audit'),'conditional_training_worker':binding('worker'),
        'conditions':{'baseline':control,'selected':treatment},'disposable_qualification_sha256':'discarded'}
    monkeypatch.setitem(sys.modules,'daytime_contract',SimpleNamespace(worker=lambda *args:None))
    monkeypatch.setitem(sys.modules,'direct_launch_contract',SimpleNamespace(owned_worker=lambda *args:None))
    return plan,files,bound,lambda path:files[str(path)]


def test_fixed_terminal192_and_same_inference_accept_exact_actual_metadata(monkeypatch):
    plan,files,bound,read=science_fixture(monkeypatch)
    assert contract.verify_science(plan,bound,read) is files['train']


@pytest.mark.parametrize('fault',['audit','wrong_run_audit','partial','missing_monitor','dev_selected','runtime',
    'original64','disposable','changed_control','wrong_saved_provenance','changed_envelope'])
def test_science_rejects_unclosed_unmatched_or_substituted_candidate(monkeypatch,fault):
    plan,files,bound,read=science_fixture(monkeypatch)
    if fault=='audit':files['audit']['status']='pending'
    elif fault=='wrong_run_audit':files['audit']['run_sha256']='unaudited-other-run'
    elif fault=='partial':files['run']['active_unknown']={'step':192}
    elif fault=='missing_monitor':files['selection']['conditions'][1]['raw_completed']=5
    elif fault=='dev_selected':files['selection']['selection_method']='lowest DEV loss'
    elif fault=='runtime':plan['model_runtime']['authored']='different'
    elif fault=='original64':plan['conditions']['baseline']['step']=64
    elif fault=='disposable':plan['disposable_qualification_sha256']='conditional192'
    elif fault=='changed_control':files['train']['comparison_control']=dict(plan['conditions']['baseline'],sha256='other')
    elif fault=='wrong_saved_provenance':plan['conditions']['selected']['target_manifest']={'sha256':'other'}
    else:
        plan['raw_provenance']['candidate_id']=contract.TREATMENT
        files['shared']['raw_provenance']['candidate_id']=contract.TREATMENT
    with pytest.raises(ValueError):contract.verify_science(plan,bound,read)


def test_relative_absolute_reference_descriptors_do_not_open_reference_body(tmp_path,monkeypatch):
    monkeypatch.setattr(contract,'ROOT',tmp_path)
    unavailable=lambda value:(_ for _ in ()).throw(AssertionError('Truth body must stay closed'))
    assert contract.same_file({'path':'grade.jsonl','sha256':'same'},
        {'path':str(tmp_path/'grade.jsonl'),'sha256':'same'},unavailable)
    assert not contract.same_file({'path':'grade.jsonl','sha256':'same'},
        {'path':str(tmp_path/'grade.jsonl'),'sha256':'changed'},unavailable)


def authored_panel():
    import chess
    from targets_v2 import target
    rows=[];responses=[];refs={}
    for group in range(16):
        for mode in ('free','selected_a','selected_b'):
            pv=['d2d4','d7d5','c1f4']if mode=='selected_b'else['e2e4','e7e5','g1f3']
            case=f'authored-{group}-{mode}';packet={'fen':chess.STARTING_FEN}
            if mode!='free':packet['selected_uci']=pv[0]
            raw,_,facts=target(chess.STARTING_FEN,pv,selected=mode!='free')
            rows.append({'case_id':case,'group_id':str(group),'mode':mode,'input':packet})
            responses.append({'status':'completed','finish_reason':'eos','raw_text':raw})
            refs[case]={'case_id':case,'group_id':str(group),'selected_uci':pv[0],
                'reference_pv_uci':pv,'facts':facts[0],'per_ply_facts':facts}
    return rows,responses,refs


def test_complete_matched_panel_distinguishes_claims_presentations_and_games():
    rows,responses,refs=authored_panel();value=grade.panel(rows,responses,refs)
    assert value['requested_presentations']==48 and value['requested_source_games']==16
    assert value['conditional_claims']['true']==192 and value['conditional_claims']['false']==0
    assert value['conditional_claims']['requested_target_branch_claims']==192
    assert value['conditional']['all_three_presentations_joint_correct_games']==16
    assert value['conditional']['counts']['conditional_joint_correct']==48


@pytest.mark.parametrize('fault',['missing_response','extra_reference','duplicate_case','wrong_triplet'])
def test_grader_requires_full48_exact_references_and_triplets(fault):
    rows,responses,refs=authored_panel()
    if fault=='missing_response':responses.pop()
    elif fault=='extra_reference':refs['extra']=next(iter(refs.values()))
    elif fault=='duplicate_case':rows[-1]['case_id']=rows[0]['case_id']
    else:rows[-1]['mode']='free'
    with pytest.raises(ValueError):grade.panel(rows,responses,refs)


def test_unrecognized_partial_and_false_conditional_claims_are_separate():
    rows,responses,refs=authored_panel()
    responses[0]['raw_text']='ANALYSIS: An unsupported explanation.'
    responses[1]['status']='partial';responses[1]['finish_reason']='maximum_tokens'
    needle='that reply captures no piece and does not give check.'
    responses[2]['raw_text']=responses[2]['raw_text'].replace(needle,'that reply captures no piece and gives check.')
    value=grade.panel(rows,responses,refs)
    assert value['conditional']['counts']['conditional_joint_correct']==45
    assert value['conditional_claims']['false']==1
    assert value['conditional_claims']['true']==187
    assert value['conditional_claims']['recognized']==188  # Unrecognized prose creates no fabricated false claim.
    assert value['immediate']['counts']['partial_or_non_EOS_rows']==1


def test_paired_source_game_wins_not_independent_presentation_count():
    rows,responses,refs=authored_panel();full=grade.panel(rows,responses,refs)
    responses[0]['raw_text']='ANALYSIS: No recognized facts.'
    less=grade.panel(rows,responses,refs)
    value=grade.paired(less,full)
    assert value['conditional_joint']['source_games']==16
    assert value['conditional_joint']['conditional_higher']==1
    assert value['conditional_joint']['ties']==15


def test_builder_retains_two_exact_spent_inputs_and_never_reads_packet_bodies(tmp_path,monkeypatch):
    monkeypatch.setattr(builder,'ROOT',tmp_path)
    old={'input_rows':{'path':'intentionally-unavailable-spent.jsonl','sha256':'inputs'},
        'assignments':[{'case_id':'one','condition':'baseline'},{'case_id':'two','condition':'selected'}]}
    monkeypatch.setattr(builder.core,'read',lambda path:old)
    monkeypatch.setattr(builder,'base',lambda *args:{'authored':True})
    out=tmp_path/'plan.json';actual=tmp_path/'data/private/chess-queen-coach-conditional-comparison-v1/qualification-1'
    builder.prepare_qualification(tmp_path/'science.json',out,actual)
    import json
    plan=json.loads(out.read_text())
    assert plan['input_rows']==old['input_rows']and plan['assignments']==old['assignments']
    assert not actual.exists()
    with pytest.raises(ValueError,match='Create-only'):builder.prepare_qualification(tmp_path/'science.json',out,actual)
