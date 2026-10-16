"""CPU-only UCI-event, durable recovery and independent legal replay fixtures."""
from pathlib import Path
import json
import sys
import chess
import chess.engine
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_counterfactual_teacher_v1 as subject


def fixture():
    board=chess.Board();pv=[chess.Move.from_uci(text)for text in('e2e4','e7e5','g1f3')]
    event={'score':chess.engine.PovScore(chess.engine.Cp(30),chess.WHITE),'pv':pv,'nodes':50000,'depth':12}
    return board,pv,event


def test_forced_root_final_and_same_score_event_pv_must_cohere():
    board,pv,event=fixture();result=subject.observation(board,event,pv[0],'e2e4')
    assert result['reference_pv']==['e2e4','e7e5','g1f3']and not result['score']['lowerbound']
    for bad_event,best,forced in[({**event,'pv':pv[1:]},pv[0],'e2e4'),(event,pv[0],'d2d4'),({'pv':pv},pv[0],None)]:
        with pytest.raises(ValueError):subject.observation(board,bad_event,best,forced)
    bounded=subject.observation(board,{**event,'lowerbound':True},pv[0])
    assert bounded['score']['lowerbound']and not bounded['score']['upperbound']
    assert not subject.observation(board,event,pv[0])['score']['lowerbound']


def test_reference_stops_before_automatic_terminal_and_cannot_claim_three_support():
    board=chess.Board('7k/8/8/8/8/8/R7/K7 w - - 149 76')
    pv=[chess.Move.from_uci(text)for text in('a2a8','h8h7','a8a7')]
    event={'pv':pv,'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE)}
    result=subject.observation(board,event,pv[0]);assert len(result['reference_pv'])==1
    assert not subject.full_three({'status':'completed','fen':board.fen(),'reference_pv':[move.uci()for move in pv]})


def test_durable_recovery_full_denominator_unknown_notrun_and_torn_suffix(tmp_path):
    tasks=[{'case_id':str(index)}for index in range(4)];journal=tmp_path/'journal.jsonl'
    events=[{'event':'intent','case_id':'0'},{'event':'outcome','case_id':'0','status':'completed'},
        {'event':'intent','case_id':'1'}]
    original='\n'.join(json.dumps(event)for event in events)+'\n{"event":"outcome",'
    journal.write_text(original)
    assert [row['status']for row in subject.recover(tasks,journal)]==['completed','active_unknown','not_run','not_run']
    assert journal.read_text()==original
    journal.write_text(original+'\n'+json.dumps({'event':'intent','case_id':'2'}))
    with pytest.raises(ValueError,match='corruption'):subject.recover(tasks,journal)


def test_train_development_and_reserve_teacher_path_collision_all_fail():
    def root(game,case,path):return {'game_id':game,'case_ids':[case],'path_keys':[path]}
    for second in('development','reserve'):
        dataset={'groups':{'train':[root('a','a','roota')],second:[root('b','b','rootb')]}}
        records=[{'case_id':case,'teacher_path_keys':['shared']}for case in('a','b')]
        with pytest.raises(ValueError,match='Cross-split'):subject.audit_paths(dataset,records)


def test_selected_targets_empty_promising_and_label_free_inputs_with_distinct_given_moves():
    board,pv,event=fixture();root={'game_id':'fixture','source_ordinal':0,
        'case_ids':['case:free','case:selected_a','case:selected_b']}
    records={}
    for case,mode,first in zip(root['case_ids'],subject.intake.MODES,('e2e4','e2e4','d2d4')):
        records[case]={'case_id':case,'mode':mode,'fen':board.fen(),'selected_uci':None if mode=='free'else first,
            'reference_pv':[first]}
    inputs,refs=subject.cases(root,records,True)
    assert set(inputs[0]['input'])=={'fen'}
    for row in inputs[1:]:
        assert set(row['input'])=={'fen','selected_uci'}and 'PROMISING_MOVES:\n'in row['response']
        assert 'check_role'not in row and 'facts'not in row
    assert refs[1]['selected_uci']=='e2e4'and refs[2]['selected_uci']=='d2d4'
    held,_=subject.cases(root,records,False);assert all('response'not in row for row in held)


def test_reserve_selection_does_not_replace_failed_or_short_roots_and_reports_every_attempt():
    board,pv,event=fixture();roots=[];records={}
    for index in range(3):
        case=str(index);roots.append({'game_id':case,'case_ids':[case],'path_keys':['root'+case],'source_ordinal':index})
        result=subject.observation(board,event,pv[0]);records[case]={**result,'fen':board.fen()}
    records['0']['reference_pv']=['e2e4'];records['1']['teacher_path_keys']=['historical']
    selected,rows=subject.held_roots(roots,records,{'historical'},set())
    assert [row['game_id']for row in selected]==['2']and len(rows)==3
    assert rows[0]['reason']=='short_or_invalid_reference'and rows[1]['reason']=='historical_or_training_path_overlap'


def test_all3168_pending_requests_survive_backend_setup_failure(tmp_path,monkeypatch):
    dataset={'status':'ready_for_teachers','protocol_sha256':'plan','groups':{name:[]for name in subject.intake.COUNTS}}
    for index in range(1056):
        split='train'if index<512 else'development'if index<544 else'reserve'
        dataset['groups'][split].append({'game_id':str(index),'fen':chess.STARTING_FEN,
            'case_ids':[f'{index}:{mode}'for mode in subject.intake.MODES],
            'pair':[{'uci':'e2e4'},{'uci':'d2d4'}]})
    subject.head.save(tmp_path/'dataset.json',dataset)
    subject.head.save(tmp_path/'intake-closed.json',{'status':'ready_for_teachers',
        'dataset_sha256':subject.head.sha(tmp_path/'dataset.json')})
    original_sha=subject.head.sha
    monkeypatch.setattr(subject.head,'sha',lambda path:'plan'if str(path)=='protocol'else original_sha(path))
    monkeypatch.setattr(subject.intake,'verify',lambda path:{'teacher':{'binary':{}},'cutoff_utc':'2099-01-01T00:00:00+00:00'})
    monkeypatch.setattr(subject.intake,'snapshot',lambda *args:None)
    monkeypatch.setattr(subject.intake.prior,'cpu_guard',lambda *args:lambda index:None)
    monkeypatch.setattr(subject.head,'bound',lambda item:'authored-engine')
    calls=[]
    def fail(*args,**kwargs):
        saved=subject.head.read(tmp_path/'teacher-planned.json')
        assert len(saved['rows'])==3168 and all(row['status']=='not_run'for row in saved['rows'])
        calls.append('setup');raise RuntimeError('authored unavailable engine')
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen',fail)
    with pytest.raises(RuntimeError,match='unavailable'):subject.teachers('protocol',tmp_path)
    assert calls==['setup']
    result=subject.head.read(tmp_path/'teachers.json')
    assert result['statuses']=={'not_run':3168}and not result['all_planned_completed']
    assert (tmp_path/'teacher-failure.json').exists()


def test_legal_unbalanced_selected_pair_cannot_be_exported():
    root={'case_ids':['free','a','b']}
    records={case:{'fen':chess.STARTING_FEN,'selected_uci':move}for case,move in[('a','e2e4'),('b','d2d4')]}
    with pytest.raises(ValueError,match='balanced'):subject.validate_selected_pair(root,records)
