"""Authored metadata checks; no models, real corpus or held reference parsing."""
from pathlib import Path
import importlib.util
import json
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('existing_compare_builder',ROOT/'experiments/chess-queen-existing-checkpoint-comparison-v1/prepare_protocol.py')
subject=importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def fixture(tmp_path,monkeypatch):
    def save(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value),encoding='utf-8');return p
    source='7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349'
    checkpoints={}
    for key,step,sha in [('baseline',256,'bd8a7b886f94c1199e2fc0a14481dc0603f72fe9503a562a82cf12ba0bf8059e'),
                         ('selected',64,'73e632f65d9146c789223ddcd7cbe106041b84aecab25ed9a775efc11bb28e3e')]:
        checkpoints[key]={'step':step,'sha256':sha,'path':str(tmp_path/(key+'.pt')),
            'candidate_id':'queen-pawn-8/nf4-coach-sft-v2','source_sha256':source}
    actual_digest=subject.outer.digest
    def digest(path):
        for identity in checkpoints.values():
            if Path(path)==Path(identity['path']):return identity['sha256']
        return actual_digest(path)
    monkeypatch.setattr(subject.outer,'digest',digest)
    metadata={key:subject.bind(save(key+'.json',value))for key,value in checkpoints.items()}
    inputs=tmp_path/'inputs.jsonl'
    rows=[{'case_id':str(i),'group_id':str(i//3),'mode':('free','selected_a','selected_b')[i%3],
        'input':{'fen':'authored fixture',**({'selected_uci':'e2e4'}if i%3 else{})}}for i in range(48)]
    inputs.write_text(''.join(json.dumps(row)+'\n'for row in rows),encoding='utf-8')
    refs=tmp_path/'references';refs.write_text('Deliberately not JSON: never parse evaluator truth.',encoding='utf-8')
    reserve=save('reserved.json',{'never_train':True})
    corpus=save('corpus-audit.json',{'status':'passed'})
    training=save('original-training-audit.json',{'verdict':'PASS: authored metadata'})
    design={'schema':'chess.existing-coach-checkpoint-fresh-comparison-design.v1',
        'planned':96,'records_per_condition':48,'source_game_groups':16,'reserved_source_games':512,
        'condition_order':['baseline','selected'],'no_new_training':True,
        'whole_phase_admission_latest_utc':'2026-10-16T11:30:00+00:00','cutoff_utc':'2026-10-16T13:00:00+00:00',
        'phase_maximum_seconds':4500,'effective_request_guard_seconds':120,'child_outer_maximum_seconds':210,
        'conditions':checkpoints,'checkpoint_metadata':metadata,'closed_corpus_audit':subject.bind(corpus),
        'closed_original_training_audit':subject.bind(training),'inputs':subject.bind(inputs),
        'references':subject.bind(refs),'reserved_exclusions':subject.bind(reserve),
        'generation':{'same':'frozen'},'condition_labels':{'baseline':'Trained terminal256','selected':'Trained dev-selected64'},
        'future_spent_policy':'All512 never train; these16 never evaluate again.',
        'claims':'Old-SFT only, no learning or reselection.','metrics':'Fixed strict scorer.'}
    proposal=save('design.json',design)
    qplan=save('qualification-plan.json',{'model_runtime':{'generation':design['generation']},
        'raw_provenance':{'candidate_id':'queen-pawn-8/nf4-coach-sft-v2','schema':'chess.queen-coach-sft-output.v2','adapter_sha256':source},
        'dependencies':[],'expected_worker_script':'scripts/outer.py','expected_worker_arguments':['scripts/outer.py','--protocol','fixed']})
    spent=save('spent.json',{'schema':'chess.once-only-fresh-cohort-reservation.v1',
        'design_sha256':subject.outer.digest(proposal),'input_sha256':design['inputs']['sha256'],
        'group_ids':sorted({r['group_id']for r in rows}),
        'all512_reserved_from_future_training':True,'these16_forbidden_for_future_evaluation':True})
    args=[proposal,qplan,save('qualified.json',{'status':'passed'}),save('worker.json',{'status':'completed'}),save('audit.json',{'status':'passed'}),spent,tmp_path/'protocol.json']
    calls=[]
    monkeypatch.setattr(subject.outer,'verify',lambda plan:calls.append(plan['mode']if'mode'in plan else'qualification'))
    read=subject.outer.read
    def embargo(path):
        if Path(path)==refs:raise AssertionError('Held reference semantics opened')
        return read(path)
    monkeypatch.setattr(subject.outer,'read',embargo)
    return args,design,calls


def test_freeze_fixed_trained256_then64_without_opening_references(tmp_path,monkeypatch):
    args,design,calls=fixture(tmp_path,monkeypatch)
    subject.prepare(*args)
    plan=json.loads(args[-1].read_text())
    assert list(plan['conditions'])==['baseline','selected']
    assert [x['step']for x in plan['conditions'].values()]==[256,64]
    assert plan['no_new_training'] and plan['planned']==96 and plan['phase_maximum_seconds']==4500
    assert plan['admission_latest_utc'].endswith('11:30:00+00:00')
    assert calls==['qualification','heldout']


@pytest.mark.parametrize('key,value',[('planned',95),('condition_order',['selected','baseline']),('no_new_training',False),
    ('whole_phase_admission_latest_utc','2026-10-16T11:31:00+00:00'),('effective_request_guard_seconds',180)])
def test_changed_quota_order_learning_or_budget_fails_before_output(tmp_path,monkeypatch,key,value):
    args,design,calls=fixture(tmp_path,monkeypatch);design[key]=value;args[0].write_text(json.dumps(design))
    with pytest.raises(ValueError,match='Exact prospective'):subject.prepare(*args)
    assert not args[-1].exists()and not calls


def test_missing_actual_qualification_blocks_final_freeze(tmp_path,monkeypatch):
    args,design,calls=fixture(tmp_path,monkeypatch)
    def verify(plan):
        if plan.get('mode')=='heldout':raise ValueError('Actual matching software qualification required')
    monkeypatch.setattr(subject.outer,'verify',verify)
    with pytest.raises(ValueError,match='Actual matching'):subject.prepare(*args)
    assert not args[-1].exists()


def test_missing_spent_cohort_group_blocks_freeze(tmp_path,monkeypatch):
    args,design,calls=fixture(tmp_path,monkeypatch)
    spent=json.loads(args[-2].read_text());spent['group_ids'].pop();args[-2].write_text(json.dumps(spent))
    with pytest.raises(ValueError,match='reservation'):subject.prepare(*args)
    assert not args[-1].exists()and not calls
