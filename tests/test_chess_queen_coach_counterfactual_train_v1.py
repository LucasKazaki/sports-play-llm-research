"""CPU authored rows/callbacks; no native/learned forward or historical truth."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import chess
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_train_v1 as subject


def rows(groups,targets=True):
    values=[]
    for group in groups:
        for mode,move in[('free',None),('selected_a','e2e4'),('selected_b','d2d4')]:
            value={'case_id':f'{group}:{mode}','group_id':group,'mode':mode,
                'input':{'fen':chess.STARTING_FEN,**({'selected_uci':move}if move else{})}}
            if targets:value['response']='authored target, never sent to a model'
            values.append(value)
    return values


def write(path,values):path.write_text(''.join(json.dumps(row)+'\n'for row in values));return path


def condition(step=0,legal=6,three=2,best=2,nll=1.,**extra):
    return {'step':step,'status':'completed','raw_planned':6,'raw_completed':6,'nll_completed':96,
        'response_token_nll':nll,'counts':{'accepted_best_legal':legal,'free_critical_3ply_agreement':three,
            'free_best_agreement':best},**extra}


def test_complete_triplets_exact_input_whitelist_and_distinct_candidates(tmp_path):
    path=write(tmp_path/'rows.jsonl',rows(['a']))
    assert len(subject.read_rows(path,True))==3
    for alteration in('missing','leak','duplicate_move','badmode'):
        values=rows(['a'])
        if alteration=='missing':values.pop()
        elif alteration=='leak':values[1]['input']['gives_check']=True
        elif alteration=='duplicate_move':values[2]['input']['selected_uci']='e2e4'
        else:values[1]['mode']='selected_check'
        write(path,values)
        with pytest.raises(ValueError):subject.read_rows(path,True)


def test_selector_legality_then_free_three_best_nll_and_earliest_baseline():
    base=condition()
    for worse in[condition(48,legal=5,three=2,best=2,nll=.1),condition(48,three=1,nll=.1),
        condition(48,best=1,nll=.1),condition(48,nll=2),condition(48)]:
        assert subject.select([worse,base])is base
    improved=condition(48,nll=.5);assert subject.select([base,improved])is improved
    assert subject.select([condition(48,legal=4),condition(0,legal=5)])['step']==0
    with pytest.raises(ValueError):subject.select([condition(nll=float('nan')),condition(raw_completed=5)])


def test_each_phase_admission_closes_at1115_utc():
    plan={'admission_latest_utc':'2026-10-16T11:15:00+00:00'}
    subject.admit(plan,datetime(2026,10,16,11,14,59,tzinfo=timezone.utc))
    for minute in(15,16):
        with pytest.raises(RuntimeError,match='EACH'):
            subject.admit(plan,datetime(2026,10,16,11,minute,tzinfo=timezone.utc))


@pytest.mark.parametrize('stage',['guard','setup'])
def test_training_setup_failure_keeps1536_and_all_four_full_development_plans(tmp_path,monkeypatch,stage):
    train=write(tmp_path/'train.jsonl',rows([f'train{i}'for i in range(512)]))
    dev_rows=rows([f'dev{i}'for i in range(32)]);dev=write(tmp_path/'dev.jsonl',dev_rows)
    refs=write(tmp_path/'refs.jsonl',[{'case_id':row['case_id'],'group_id':row['group_id'],
        'selected_uci':row['input'].get('selected_uci','e2e4')}for row in dev_rows])
    plan={'data':{'train':train,'development':dev,'development_references':refs},
        'development_raw_groups':['dev0','dev1'],'training':{'seed':4082086},'warm_start':{'step':64},
        'successful_memory_qualification':{'sha256':'qualified'}}
    original_digest=subject.checked.nf4.base.digest
    monkeypatch.setattr(subject.checked.nf4,'binding',lambda item:item)
    monkeypatch.setattr(subject.checked.nf4.base,'digest',lambda path:'protocol'if str(path)=='protocol'else original_digest(path))
    def make_guard(*args):
        if stage=='guard':raise RuntimeError('authored guard setup failure')
        return lambda:None,[],{}
    monkeypatch.setattr(subject,'guard_for',make_guard)
    monkeypatch.setattr(subject,'snapshot',lambda *args:None)
    out=tmp_path/'attempt'
    class Failed:
        def __init__(self,*args):assert stage!='guard'
        def load(self):
            for step in subject.STEPS:
                raw=subject.checked.nf4.base.read_json(out/f'raw-development-{step:04d}.json')
                nll=subject.checked.nf4.base.read_json(out/f'development-{step:04d}.json')
                assert len(raw['rows'])==6 and len(nll['nll_rows'])==96
            raise RuntimeError('authored setup failure')
    monkeypatch.setattr(subject,'Runtime',Failed)
    with pytest.raises(RuntimeError,match='setup'):subject.train(plan,'protocol',out)
    denominator=subject.checked.nf4.base.read_json(out/'training-denominator.json')
    assert denominator['planned']==1536 and all(row['status']=='not_run'for row in denominator['rows'])
    assert subject.checked.nf4.base.read_json(out/'run.json')['updates_completed']==0
    assert subject.checked.nf4.base.read_json(out/'run.json')['status']=='failed'
    assert subject.checked.nf4.base.read_json(out/'resources.json')==[]
    for step in subject.STEPS:
        assert len(subject.checked.nf4.base.read_json(out/f'raw-development-{step:04d}.json')['rows'])==6
        assert len(subject.checked.nf4.base.read_json(out/f'development-{step:04d}.json')['nll_rows'])==96


@pytest.mark.parametrize('stage',['guard','backend'])
def test_first_held_backend_failure_retains_both48_ledgers_without_opening_truth(tmp_path,monkeypatch,stage):
    inputs=write(tmp_path/'inputs.jsonl',rows([f'held{i}'for i in range(16)],False))
    selection=tmp_path/'selection.json';subject.save(selection,{'baseline':{'id':'fixed64'},'selected':{'id':'new'}})
    plan={'data':{'heldout_inputs':inputs,'heldout_references':'FORBIDDEN_TRUTH'}}
    monkeypatch.setattr(subject.checked.nf4,'binding',lambda item:item)
    monkeypatch.setattr(subject,'verify_selection',lambda *args:None)
    def make_guard(*args):
        if stage=='guard':raise RuntimeError('authored guard setup failure')
        return lambda:None,[],{}
    monkeypatch.setattr(subject,'guard_for',make_guard)
    monkeypatch.setattr(subject,'snapshot',lambda *args:None)
    def forbidden(*args):raise AssertionError('held truth opened after failure')
    monkeypatch.setattr(subject,'references',forbidden)
    calls=[]
    class Failed:
        def __init__(self,*args):assert stage!='guard'
        def load(self):pass
        def release_inactive(self,*args):pass
        def load_adapter(self,identity):calls.append(('reload',identity))
        def infer(self,row,identity):calls.append(('infer',row['case_id']));return {'status':'failed','raw_text':'partial retained','error':'authored backend failure'}
    monkeypatch.setattr(subject,'Runtime',Failed);out=tmp_path/'held'
    with pytest.raises(RuntimeError,match='guard'if stage=='guard'else'First raw generator'):subject.heldout(plan,'protocol',selection,out)
    baseline=subject.checked.nf4.base.read_json(out/'baseline.json');selected=subject.checked.nf4.base.read_json(out/'selected.json')
    assert len(baseline['rows'])==len(selected['rows'])==48
    assert [row['status']for row in baseline['rows']]==(['not_run']*48 if stage=='guard'else['failed']+['not_run']*47)
    assert all(row['status']=='not_run'for row in selected['rows'])and len(calls)==(0 if stage=='guard'else 2)
    assert (out/'failure.json').exists()and subject.checked.nf4.base.read_json(out/'resources.json')==[]


def test_inherits_durable_finalizer_including_torn_suffix(tmp_path):
    path=tmp_path/'calls.jsonl';path.write_text('{"step":1,"micro":0,"case_id":"a","status":"call_started"}\n{"step":')
    result=subject.finalize_training_rows([{'step':1,'micro':0,'case_id':'a'},{'step':1,'micro':1,'case_id':'b'}],path)
    assert [row['status']for row in result['rows']]==['active_unknown','not_run']
    assert result['journal']['trailing_partial']['original_bytes_preserved']
