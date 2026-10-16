"""Authored CPU callbacks; no actual model, feature tensor or engine calls."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_encoder_check_generalization_eval_v2 as evaluation


def rows(prefix='king'):
    return [{'case_id':prefix+str(index),'fen':'4k3/8/8/8/4K3/8/8/4R3 w - - 0 1',
        'selected_uci':uci}for index,uci in enumerate(('e4d4','e4e5'))]


def setup(tmp_path,values=None):
    values=rows()if values is None else values;out=tmp_path/'attempt'
    closed={'shortages':{name:16-int(name=='king_mover')for name in evaluation.intake.STRATA}}
    plan={'cohort':{'inputs':{'sha256':'fixture-input'}},'original_untrained':{'epoch':0},'selected':{'epoch':4}}
    plan['encoder']={name:{'sha256':'fixture-'+name}for name in('weights','source','planes_source')}
    evaluation.prepare_ledgers(out,values,closed,plan);return out


def test_both_model_ledgers_all_requested_source_slots_and_features_precede_backends(tmp_path):
    out=setup(tmp_path)
    for condition in evaluation.CONDITIONS:
        value=evaluation.head.read(out/(condition+'.json'))
        assert value['planned']==2 and all(row['status']=='not_run'for row in value['raw'])
        assert not any('prediction'in row or'logit'in row for row in value['raw'])
    coverage=evaluation.head.read(out/'requested-source-slots.json')
    assert len(coverage['slots'])==64 and coverage['requested_move_slots']==128 and coverage['actual_moves']==2
    assert sum(row['status']=='source_shortage'for row in coverage['slots'])==63
    manifest=evaluation.head.read(out/'features.json')
    assert manifest['planned']==2 and manifest['unique_current_fens']==1
    assert all(set(row)=={'case_id','input_sha256','status'}for row in manifest['records'])


def test_feature_dedup_one_current_fen_and_durable_intent_then_label_free_move_identities(tmp_path):
    values=rows();out=setup(tmp_path);calls=[]
    def encode(fen):
        saved=evaluation.head.read(out/'features.json')
        assert all(row['status']=='unknown_after_interruption'for row in saved['records'])
        assert json.loads((out/'feature-attempts.jsonl').read_text())['status']=='started'
        calls.append(fen);return object()
    def emit(index,group,state):
        return [{'shard':'fixture.pt','row':i,'shard_sha256':'fixture-sha'}for i in range(len(group))]
    result=evaluation.feature_records(values,out/'features.json',out/'feature-attempts.jsonl',encode,emit)
    assert len(calls)==1 and result['status']=='completed'
    assert [row['case_id']for row in result['records']]==[row['case_id']for row in values]
    assert all(set(row)=={'case_id','input_sha256','status','shard','row','shard_sha256'}for row in result['records'])


def test_feature_first_failure_retains_all_remaining_requests_and_never_calls_second_board(tmp_path):
    values=rows();values+=[{'case_id':'pawn'+str(i),'fen':'8/8/8/4k3/8/8/5P2/K7 w - - 0 1',
        'selected_uci':uci}for i,uci in enumerate(('f2f4','f2f3'))]
    out=setup(tmp_path,values);calls=[]
    def failed(fen):calls.append(fen);raise RuntimeError('fixture encoder failure')
    with pytest.raises(RuntimeError,match='First feature'):
        evaluation.feature_records(values,out/'features.json',out/'feature-attempts.jsonl',failed,lambda *args:[])
    result=evaluation.head.read(out/'features.json')
    assert len(calls)==1 and [row['status']for row in result['records']]==['failed','failed','not_run','not_run']
    assert all(row['status']=='not_run'for row in evaluation.head.read(out/'selected_head.json')['raw'])


def test_feature_receipt_cannot_add_labels_or_successor_fields(tmp_path):
    out=setup(tmp_path)
    with pytest.raises(RuntimeError,match='label-free'):
        evaluation.feature_records(rows(),out/'features.json',out/'feature-attempts.jsonl',lambda fen:object(),
            lambda *args:[{'shard':'x','row':i,'shard_sha256':'h','gives_check':True}for i in range(2)])


def test_raw_zero_threshold_and_durable_unknown_before_prediction(tmp_path):
    out=setup(tmp_path);path=out/'untrained_head.json';calls=[]
    def predict(start,end):
        saved=evaluation.head.read(path)
        assert all(row['status']=='unknown_after_interruption'for row in saved['raw'])
        calls.append((start,end));return [-1.,0.]
    result=evaluation.raw_condition(rows(),path,predict,128)
    assert calls==[(0,2)]and result['status']=='completed'
    assert [row['prediction']for row in result['raw']]==[False,True]
    assert [row['logit']for row in result['raw']]==[-1.,0.]


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,None])
def test_nonfinite_or_nonlogit_output_fails_without_nonjson_metrics_and_stops_remaining(tmp_path,bad):
    values=rows()+[dict(row,case_id='next'+row['case_id'])for row in rows()]
    out=setup(tmp_path,values);path=out/'untrained_head.json';calls=[]
    def predict(start,end):calls.append((start,end));return [bad,bad]
    with pytest.raises(RuntimeError,match='First raw head'):evaluation.raw_condition(values,path,predict,2)
    saved=evaluation.head.read(path);json.dumps(saved,allow_nan=False)
    assert len(calls)==1 and [row['status']for row in saved['raw']]==['failed','failed','not_run','not_run']
    assert not any('logit'in row for row in saved['raw'])


def test_hard_interruption_preserves_started_request_unknown(tmp_path):
    out=setup(tmp_path);path=out/'untrained_head.json'
    def interrupted(*args):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):evaluation.raw_condition(rows(),path,interrupted,128)
    saved=evaluation.head.read(path)
    assert all(row['status']=='unknown_after_interruption'for row in saved['raw'])
    assert all(row['status']=='not_run'for row in evaluation.head.read(out/'selected_head.json')['raw'])


def test_labels_cannot_open_until_both_raw_ledgers_close(tmp_path,monkeypatch):
    values=rows();out=setup(tmp_path);labels_path=tmp_path/'labels.json'
    labels={'rows':[{'case_id':row['case_id'],'gives_check':index==0}for index,row in enumerate(values)]}
    evaluation.head.save(labels_path,labels)
    plan={'cohort':{'labels':{'path':str(labels_path),'sha256':evaluation.head.sha(labels_path)}}}
    original=evaluation.head.read;seen=[]
    def tracked(path):
        if Path(path)==labels_path:seen.append('labels')
        return original(path)
    monkeypatch.setattr(evaluation.head,'read',tracked)
    with pytest.raises(ValueError,match='Both complete'):evaluation.load_labels_after_raw(plan,values,out)
    assert not seen
    evaluation.raw_condition(values,out/'untrained_head.json',lambda *args:[1.,-1.],128)
    with pytest.raises(ValueError,match='Both complete'):evaluation.load_labels_after_raw(plan,values,out)
    assert not seen
    evaluation.raw_condition(values,out/'selected_head.json',lambda *args:[1.,-1.],128)
    assert evaluation.load_labels_after_raw(plan,values,out)==labels['rows']and seen==['labels']


def test_grouped_scores_distinguish_allocation_overlap_and_unavailable_source_support():
    values=rows();labels=[{'case_id':row['case_id'],'gives_check':index==0}for index,row in enumerate(values)]
    raw=[{'case_id':row['case_id'],'status':'completed','prediction':index==0}for index,row in enumerate(values)]
    dataset={'groups':{'diagnostic':[{'allocation':'king_mover','case_ids':[row['case_id']for row in values],
        'positive':{'king_mover':True,'pawn_mover':False,'double_check':False,'discovered_check':True}}]}}
    score=evaluation.grouped_scores(values,labels,raw,dataset)
    assert score['overall']['correct']==2 and score['by_allocation']['king_mover']['pairs_correct']==1
    assert score['by_overlapping_positive_flags']['discovered_check']['pairs_correct']==1
    assert score['by_allocation']['double_check']['planned']==0
    assert score['by_allocation']['double_check']['checking_recall']is None


from chess_native_resources import Sample,GIB

def sample(physical=6,commit=8,gpu=4):
    return Sample(64*GIB,int(physical*GIB),64*GIB,int((64-commit)*GIB),16*GIB,int(gpu*GIB))

def controlled_guard(tmp_path,values,maximum=900):
    now=[0.];calls=[]
    def read():calls.append(now[0]);return values.pop(0)
    return evaluation.guard_for(tmp_path,maximum,read,lambda:now[0]),now,calls

@pytest.mark.parametrize('mib',[750,768,1023])
def test_running_gpu_reserve_rejects_less_than_one_gib(tmp_path,mib):
    guard,now,calls=controlled_guard(tmp_path,[sample(),sample(4,6,mib/1024)])
    guard();now[0]=1
    with pytest.raises(RuntimeError,match='gpu_free_bytes_below_reserve'):guard()
    assert calls==[0.,1.]and len((tmp_path/'resources.jsonl').read_text().splitlines())==2

def test_exact_start_and_running_reserves_accepted(tmp_path):
    guard,now,calls=controlled_guard(tmp_path,[sample(),sample(4,6,1)])
    guard();now[0]=1;guard();assert calls==[0.,1.]

@pytest.mark.parametrize('value,stage,reason',[
    (sample(5.99,8,4),'start','physical'),(sample(6,7.99,4),'start','commit'),
    (sample(6,8,3.99),'start','gpu'),(sample(3.99,6,1),'running','physical'),
    (sample(4,5.99,1),'running','commit')])
def test_other_frozen_reserves_remain_enforced(tmp_path,value,stage,reason):
    values=[value]if stage=='start'else[sample(),value]
    guard,now,calls=controlled_guard(tmp_path,values)
    if stage=='running':guard();now[0]=1
    with pytest.raises(RuntimeError,match=reason):guard()

def test_throttle_does_not_suppress_owned_cancel_or_deadline(tmp_path):
    guard,now,calls=controlled_guard(tmp_path,[sample(),sample(4,6,1)],maximum=2)
    guard();now[0]=.5;guard();assert calls==[0.]
    now[0]=1;guard();assert calls==[0.,1.]
    (tmp_path/'CANCEL').write_text('owned')
    now[0]=1.1
    with pytest.raises(InterruptedError,match='cancellation'):guard()
    (tmp_path/'CANCEL').unlink();now[0]=2
    with pytest.raises(InterruptedError,match='deadline'):guard()
    assert calls==[0.,1.]
