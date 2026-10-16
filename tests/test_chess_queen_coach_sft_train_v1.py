"""Pure CPU pilot orchestration checks; all generator outputs are fixtures."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_train_v1 as pilot


def rows():
    fen='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    return [{'case_id':'g:'+mode,'group_id':'g','mode':mode,
        'input':{'fen':fen,**({'selected_uci':'e2e4'}if mode=='selected'else{})},'response':'fixture target'}
        for mode in('free','selected')]


def condition(step,legal=8,prefix=0,best=0,nll=1.):
    return {'step':step,'status':'completed','raw_planned':8,'raw_completed':8,'nll_completed':64,
        'response_token_nll':nll,'counts':{'accepted_best_legal':legal,'free_critical_3ply_agreement':prefix,'free_best_agreement':best}}


def test_selector_prioritizes_all_legal_then_free_threeply_best_nll_earliest():
    baseline=condition(0,8,0,0,2)
    assert pilot.select([baseline,condition(64,7,4,4,.1)])is baseline
    three=condition(64,8,2,0,3)
    assert pilot.select([baseline,three,condition(128,8,1,4,.1)])is three
    best=condition(128,8,2,3,4)
    assert pilot.select([three,best])is best
    nll=condition(256,8,2,3,.5)
    assert pilot.select([best,nll])is nll
    assert pilot.select([baseline,condition(64,8,0,0,2)])is baseline


def test_call_intent_journal_is_flushed_and_synced_before_return(tmp_path,monkeypatch):
    path=tmp_path/'calls.jsonl';seen=[]
    def synced(fd):
        assert isinstance(fd,int)
        seen.append(json.loads(path.read_text()))
    monkeypatch.setattr(pilot.os,'fsync',synced)
    pilot.append(path,{'case_id':'fixture','status':'call_started'})
    assert seen==[{'case_id':'fixture','status':'call_started'}]


def test_selector_fallback_legal_count_and_incomplete_panels_not_eligible():
    values=[condition(0,6,4,4,.1),condition(64,7,0,0,2)]
    assert pilot.select(values)['step']==64
    incomplete=condition(128,8,4,4,.01);incomplete['raw_completed']=7
    assert pilot.select(values+[incomplete])['step']==64
    with pytest.raises(ValueError):pilot.select([incomplete])


@pytest.mark.parametrize('defect',['duplicate','wrong_mode','future_input','unmatched','different_fen','unknown_fields'])
def test_corpus_rows_require_exact_paired_label_free_inputs(defect,tmp_path):
    values=rows()
    if defect=='duplicate':values[1]['case_id']=values[0]['case_id']
    if defect=='wrong_mode':values[0]['input']['selected_uci']='e2e4'
    if defect=='future_input':values[0]['input']['reference_pv_uci']=['e2e4']
    if defect=='unmatched':values.pop()
    if defect=='different_fen':values[1]['input']['fen']=values[1]['input']['fen'].replace('0 1','1 1')
    if defect=='unknown_fields':values[0]['teacher_score']=0
    path=tmp_path/'rows.jsonl';path.write_text('\n'.join(json.dumps(row)for row in values))
    with pytest.raises(ValueError):pilot.read_rows(path,True)


def test_raw_first_backend_failure_retains_full_denominator_and_stops_remaining(tmp_path):
    values=rows();path=tmp_path/'panel.json';calls=[]
    pilot.pending_panel(path,values,'fixture')
    class Runtime:
        def infer(self,row,identity):
            calls.append(row['case_id']);return {'status':'failed','error':'fixture backend','raw_text':'partial retained'}
    with pytest.raises(RuntimeError,match='First raw generator'):
        pilot.generate_panel(Runtime(),values,path,{'sha256':'fixture'},lambda:None)
    actual=json.loads(path.read_text())
    assert len(calls)==1 and actual['planned']==2 and actual['rows'][0]['status']=='failed'
    assert actual['rows'][1]['status']=='not_run'
    raw=json.loads(Path(actual['rows'][0]['response_path']).read_text())
    assert raw['raw_text']=='partial retained'


def test_raw_call_intent_is_durable_if_backend_raises_before_result(tmp_path):
    values=rows();path=tmp_path/'panel.json'
    pilot.pending_panel(path,values,'fixture')
    class Runtime:
        def infer(self,row,identity):raise RuntimeError('fixture interruption')
    with pytest.raises(RuntimeError,match='interruption'):
        pilot.generate_panel(Runtime(),values,path,{},lambda:None)
    actual=json.loads(path.read_text())
    assert actual['rows'][0]['status']=='call_started'and actual['rows'][1]['status']=='not_run'


def test_heldout_resource_setup_failure_keeps_both_full_pending_conditions_without_reference_read(tmp_path,monkeypatch):
    values=[]
    for group in range(16):
        for row in rows():
            row['group_id']=str(group);row['case_id']=f'{group}:{row["mode"]}';row.pop('response');values.append(row)
    data=tmp_path/'held.jsonl';data.write_text('\n'.join(json.dumps(row)for row in values))
    protocol=tmp_path/'protocol.json';protocol.write_text('{}')
    selection=tmp_path/'selection.json';selection.write_text(json.dumps({'status':'selected',
        'protocol_sha256':pilot.checked.nf4.base.digest(protocol),'baseline':{},'selected':{}}))
    monkeypatch.setattr(pilot,'verify_selection',lambda *args:None)
    def fail(*args):raise ValueError('fixture resource setup failure')
    monkeypatch.setattr(pilot,'guard_for',fail)
    monkeypatch.setattr(pilot,'references',lambda *args:pytest.fail('Held references must remain closed'))
    plan={'data':{'heldout_inputs':{'path':str(data),'sha256':pilot.checked.nf4.base.digest(data)}}}
    out=tmp_path/'attempt'
    with pytest.raises(ValueError,match='resource setup'):
        pilot.heldout(plan,protocol,selection,out)
    for name in('baseline','selected'):
        panel=json.loads((out/f'{name}.json').read_text())
        assert panel['planned']==32 and all(row['status']=='not_run'for row in panel['rows'])


def test_saved_selection_is_recomputed_and_actual_checkpoint_hashes_checked(tmp_path):
    protocol=tmp_path/'protocol.json';protocol.write_text('{}')
    base=tmp_path/'base.pt';base.write_bytes(b'baseline fixture')
    tuned=tmp_path/'tuned.pt';tuned.write_bytes(b'tuned fixture')
    baseline=condition(0);baseline['identity']={'path':str(base),'sha256':pilot.checked.nf4.base.digest(base)}
    selected=condition(64,prefix=1);selected['identity']={'path':str(tuned),'sha256':pilot.checked.nf4.base.digest(tuned)}
    value={'status':'selected','protocol_sha256':pilot.checked.nf4.base.digest(protocol),
        'conditions':[baseline,selected],'baseline':baseline['identity'],'selected':selected['identity']}
    pilot.verify_selection(value,protocol)
    wrong=copy.deepcopy(value);wrong['selected']=wrong['baseline']
    with pytest.raises(ValueError,match='disagrees'):pilot.verify_selection(wrong,protocol)
    tuned.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checkpoint bytes'):pilot.verify_selection(value,protocol)
