import importlib.util
from pathlib import Path
import sys
import json
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_benchmark_v1 as benchmark
import chess_queen_adapter as queen


def row():
    return {'id':'fixture','fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',
            'status':'completed','teacher_move_uci':'g5d8','reference_pv':['g5d8','g8h7','d8d3'],
            'forbidden_theme':'mate','solution':'never include'}


def test_request_packet_separates_teacher_reference():
    free=benchmark.request_packet(row(),'free')
    selected=benchmark.request_packet(row(),'selected')
    assert set(free)=={'fen','history'}
    assert set(selected)=={'fen','history','selected_uci'}
    assert selected['selected_uci']=='g5d8'
    with pytest.raises(ValueError):benchmark.request_packet(row(),'unknown')


def test_missing_teacher_preserves_selected_request():
    item=row();item['status']='failed'
    assert benchmark.request_packet(item,'selected') is None
    assert benchmark.request_packet(item,'free') is not None


def test_missing_and_failed_are_false_in_full_denominator():
    scored=[benchmark.score_response(row(),mode,{'status':'not_run'}) for mode in ('free','selected')]
    summary=benchmark.summarize(scored)
    for mode in ('free','selected'):
        assert summary[mode]['planned']==1
        assert summary[mode]['raw_best_legal']==0
        assert summary[mode]['critical_line_exact_prefix']=={'1':0,'2':0,'3':0}
        assert summary[mode]['statuses']=={'not_run':1}


def test_forecast_stops_at_first_illegal_choice():
    response={'status':'partial','parsed':{'raw_choice_uci':'g5d8','raw_choice_is_legal':True,
        'description_valid':True,'accepted_move_uci':'g5d8','critical_line':{'steps':[
        {'legal':True,'raw_uci':'g5d8'},{'legal':False,'raw_uci':'g8h7'},{'legal':True,'raw_uci':'d8d3'}]}}}
    scored=benchmark.score_response(row(),'free',response)
    assert scored['free_best_teacher_match']
    assert scored['critical_line_exact_prefix']=={'1':True,'2':False,'3':False}
    assert scored['critical_line_legal_through']=={'1':True,'2':False,'3':False}


def test_selected_move_is_not_counted_as_independent_teacher_prediction():
    response={'status':'completed','parsed':{'raw_choice_uci':'g5d8','raw_choice_is_legal':True,
        'description_valid':True,'accepted_move_uci':'g5d8'}}
    scored=benchmark.score_response(row(),'selected',response)
    assert scored['selected_move_followed'] and not scored['free_best_teacher_match']


def test_interrupted_attempt_keeps_unknown_and_notrun(tmp_path):
    (tmp_path/'attempts.jsonl').write_text('{"index":0,"status":"started"}\n{"torn":',encoding='utf-8')
    outcomes=benchmark.finalize_attempt(tmp_path,[(row(),'free'),(row(),'selected')])
    assert [r['status'] for r in outcomes]==['unknown_after_interruption','not_run']
    assert benchmark.summarize(outcomes)['free']['planned']==1


def test_teacher_support_stops_on_automatic_draw():
    item=row();item.update(fen='7k/8/8/8/8/8/R7/K7 w - - 149 76',reference_pv=['a2a8','h8h7','a8a7'])
    scored=benchmark.score_response(item,'free',{'status':'failed'})
    assert scored['teacher_support_plies']==1


def test_backend_failure_blocks_new_holdout_model_calls(tmp_path,monkeypatch):
    protocol=tmp_path/'protocol.json';protocol.write_text('{}',encoding='utf-8')
    out=tmp_path/'data';out.mkdir()
    benchmark.save(out/'dataset.json',{'protocol_sha256':benchmark.sha(protocol)})
    benchmark.save(out/'labels.json',{'protocol_sha256':benchmark.sha(protocol),'dataset_sha256':benchmark.sha(out/'dataset.json'),
        'splits':{'development':[row()],'holdout':[row()]}})
    monkeypatch.setattr(benchmark,'verify',lambda _: {'generation':{},'limitations':['fixture']})
    monkeypatch.setattr(benchmark,'snapshot',lambda *a:None)
    calls=[]
    class Broken:
        def __init__(self,**kwargs):calls.append('init')
        def generate(self,*args,**kwargs):calls.append('generate');return {'status':'failed','error':'fixture_failure'}
    monkeypatch.setattr(queen,'NativeQueen',Broken)
    result=benchmark.run(protocol,out,'development')
    assert result['execution_status']=='failed_or_incomplete'
    assert result['metrics']['selected']['statuses']=={'not_run':1}
    assert calls==['init','generate']
    with pytest.raises(ValueError,match='holdout remains unopened'):
        benchmark.run(protocol,out,'holdout')
    assert calls==['init','generate']


def test_intake_only_protocol_stops_before_data_or_model_setup(tmp_path,monkeypatch):
    monkeypatch.setattr(benchmark,'verify',lambda _: {'generation_allowed':False})
    monkeypatch.setattr(queen,'NativeQueen',lambda **kw:pytest.fail('No model setup allowed'))
    with pytest.raises(ValueError,match='CPU intake/teachers only'):
        benchmark.run(tmp_path/'plan',tmp_path/'no-data','development')
