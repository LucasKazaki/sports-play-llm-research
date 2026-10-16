import json
from pathlib import Path
import sys
import pytest
import chess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chess_check_balanced_v2 as target


def test_prompt_has_only_current_board_and_move():
    fen='7k/8/8/8/8/8/R7/K7 w - - 0 1'
    text=target.prompt(fen,'a2a8')
    packet=json.loads(text.split('\n',1)[1])
    assert set(packet)=={'fen','move','pieces'}
    assert packet['fen']==fen and packet['move']=='a2a8'
    assert '+' not in text and 'true' not in packet.values()
    assert 'a2:R' in packet['pieces'] and 'h8:k' in packet['pieces']


@pytest.mark.parametrize('uci',['a2a1','a2h8','h8h7'])
def test_illegal_candidate_is_rejected(uci):
    with pytest.raises(ValueError):target.prompt('7k/8/8/8/8/8/R7/K7 w - - 0 1',uci)


def test_pair_is_balanced_same_piece_and_capture_status():
    board=chess.Board('7k/8/8/8/8/8/R7/K7 w - - 0 1')
    yes,no=target.pair_for(board,'abcd1234',12,set())
    first,second=chess.Move.from_uci(yes),chess.Move.from_uci(no)
    assert board.gives_check(first) and not board.gives_check(second)
    assert first.from_square==second.from_square
    assert board.is_capture(first)==board.is_capture(second)
    assert target.pair_for(board,'abcd1234',12,set())==(yes,no)


def test_spent_successors_are_excluded():
    board=chess.Board('7k/8/8/8/8/8/R7/K7 w - - 0 1')
    forbidden=set()
    for move in board.legal_moves:
        after=board.copy();after.push(move);forbidden.add(target.board_key(after.fen()))
    assert target.pair_for(board,'abcd1234',12,forbidden) is None


def write_score_fixture(tmp_path, predictions):
    raw=tmp_path/'raw.json';labels=tmp_path/'labels.json';out=tmp_path/'score.json'
    target.save(raw,{'rows':[{'case_id':str(i),'prediction':p,'status':'completed'} for i,p in enumerate(predictions)]})
    target.save(raw.with_suffix('.seal.json'),{'sha256':target.sha(raw)})
    target.save(labels,{'rows':[{'case_id':str(i),'gives_check':bool(i%2==0)} for i in range(len(predictions))]})
    return raw,labels,out


def test_constant_negative_collapse_keeps_positive_failure(tmp_path):
    raw,labels,out=write_score_fixture(tmp_path,[False]*4)
    result=target.score(raw,labels,out,target.sha(labels))
    assert result['correct']==2 and result['balanced_accuracy']==.5
    assert result['confusion']['fn']==2 and result['pairs_correct']==0


def test_invalid_and_integer_predictions_never_count_as_correct(tmp_path):
    raw,labels,out=write_score_fixture(tmp_path,[None,None,1,0])
    result=target.score(raw,labels,out,target.sha(labels))
    assert result['correct']==0 and result['balanced_accuracy']==0
    assert result['confusion']['invalid_positive']==2
    assert result['confusion']['invalid_negative']==2


def test_seal_and_label_hash_reject_tampering(tmp_path):
    raw,labels,out=write_score_fixture(tmp_path,[True,False])
    with pytest.raises(ValueError,match='label identity'):
        target.score(raw,labels,out,'0'*64)
    raw.write_text('{}')
    with pytest.raises(ValueError,match='seal'):
        target.score(raw,labels,out,target.sha(labels))


def test_denominator_identity_is_checked(tmp_path):
    raw,labels,out=write_score_fixture(tmp_path,[True,False])
    value=target.read(labels);value['rows'].reverse();target.save(labels,value)
    with pytest.raises(ValueError,match='denominator'):
        target.score(raw,labels,out,target.sha(labels))


def test_interrupted_batch_and_future_cases_keep_full_denominator(tmp_path):
    target.save(tmp_path/'planned-outcomes.json',{'cohorts':{'dev-0':['a','b','c','d']}})
    target.save(tmp_path/'active-batch.json',{'cohort':'dev-0','case_ids':['a','b']})
    (tmp_path/'dev-0.journal.jsonl').write_text(json.dumps({'case_id':'a','status':'completed','prediction':True})+'\n{partial')
    target.finalize_ledger(tmp_path)
    value=target.read(tmp_path/'outcome-ledger.json')
    assert value['planned']==4
    assert [r['status'] for r in value['cohorts']['dev-0']]==[
        'completed','unknown_after_interruption','not_run','not_run']


def test_unchanged_warm_adapter_remains_selector_candidate():
    rows=[{'step':0,'correct':128,'pairs_correct':0},
          {'step':-1,'correct':137,'pairs_correct':21},
          {'step':256,'correct':136,'pairs_correct':20}]
    assert max(rows,key=target.selection_key)['step']==-1
    rows[2].update(correct=137,pairs_correct=21)
    assert max(rows,key=target.selection_key)['step']==-1
    rows[0].update(correct=137,pairs_correct=21)
    assert max(rows,key=target.selection_key)['step']==0
