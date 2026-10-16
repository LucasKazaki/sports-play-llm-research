import json
from pathlib import Path
import sys
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO/'scripts'))
sys.path.insert(0, str(Path(__file__).parent))
import chess_queen_benchmark_nf4_v1 as run


def row():
    return {'id':'fixture', 'fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',
        'source_before_fen':'6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1',
        'status':'completed','teacher_move_uci':'g5d8','reference_pv':['g5d8'],
        'solution':'forbidden','score':{'mate':1},'theme':'never pass'}


def setup(tmp_path, monkeypatch):
    plan={'accepted_pool':{'labels':{'sha256':'labels'}},'panel_counts':{'development':1,'holdout':1},
          'generation':{},'resources':{},'phase_maximum_seconds':{'development':100,'holdout':100},
          'limitations':['fixture']}
    labels={'splits':{'development':[row()],'holdout':[row()]}}
    protocol=tmp_path/'protocol.json';protocol.write_text('{}',encoding='utf-8')
    monkeypatch.setattr(run,'verify',lambda _:plan)
    monkeypatch.setattr(run,'accepted_pool',lambda _ : ({},labels))
    monkeypatch.setattr(run,'collision_check',lambda *_ : {'collisions':0})
    monkeypatch.setattr(run,'snapshot',lambda *_:None)
    import chess_native_resources as resources
    monkeypatch.setattr(resources,'reasons',lambda *_:[])
    return protocol, tmp_path/'out',plan


def test_packet_has_only_current_fen_and_selected_legal_move():
    assert run.packet(row(),'free')=={'fen':row()['fen']}
    assert run.packet(row(),'selected')=={'fen':row()['fen'],'selected_uci':'g5d8'}
    with pytest.raises(ValueError):run.packet(row(),'unknown')


def test_exact_accepted_cohort_and_teacher_are_required(tmp_path, monkeypatch):
    data={'protocol_sha256':'old','splits':{'development':[{'id':'a','fen':'fen'}]}}
    labels={'protocol_sha256':'old','dataset_sha256':'data',
            'splits':{'development':[{'id':'a','fen':'fen','status':'completed'}]}}
    run.save(tmp_path/'dataset.json',data);run.save(tmp_path/'labels.json',labels)
    monkeypatch.setattr(run,'bound',lambda item:tmp_path/item['path'])
    plan={'accepted_pool':{'dataset':{'path':'dataset.json','sha256':'data'},
          'labels':{'path':'labels.json'},'intake_protocol':{'sha256':'old'},'available_counts':{'development':1}}}
    assert run.accepted_pool(plan)[0]==data
    labels['splits']['development'][0]['fen']='changed';run.save(tmp_path/'labels.json',labels)
    with pytest.raises(ValueError,match='Teacher does not match'):run.accepted_pool(plan)


def test_cohort_cannot_be_rebound_to_new_generation_plan(tmp_path,monkeypatch):
    run.save(tmp_path/'dataset',{'protocol_sha256':'changed'})
    run.save(tmp_path/'labels',{'protocol_sha256':'original','dataset_sha256':'data'})
    monkeypatch.setattr(run,'bound',lambda item:tmp_path/item['path'])
    plan={'accepted_pool':{'dataset':{'path':'dataset','sha256':'data'},'labels':{'path':'labels'},
                          'intake_protocol':{'sha256':'original'}}}
    with pytest.raises(ValueError,match='identity differs'):run.accepted_pool(plan)


def test_authored_collision_aborts_including_unused_cpu_pool(tmp_path,monkeypatch):
    run.save(tmp_path/'boards',{'board_fens':[row()['fen']]})
    monkeypatch.setattr(run,'bound',lambda _:tmp_path/'boards')
    with pytest.raises(ValueError,match='collides'):
        run.collision_check({'authored_boards':[{}]}, {'splits':{'unused':[row()]}})


def test_panel_selection_is_frozen_source_order():
    rows=[{'id':i} for i in range(5)]
    assert run.selected_rows({'panel_counts':{'development':2}}, {'splits':{'development':rows}},'development')==rows[:2]
    with pytest.raises(ValueError):run.selected_rows({'panel_counts':{'development':6}}, {'splits':{'development':rows}},'development')


def test_backend_failure_preserves_full_denominator_and_closes_holdout(tmp_path,monkeypatch):
    protocol,out,plan=setup(tmp_path,monkeypatch);calls=[]
    class Broken:
        def generate(self,value,**kw):calls.append(value);return {'status':'failed','error':'backend failure'}
    monkeypatch.setattr(run,'model_factory',lambda *_:Broken())
    result=run.run(protocol,out,'development')
    assert result['execution_status']=='failed_or_incomplete'
    assert result['planned_request_count']==2 and result['completed_request_count']==0
    assert result['metrics']['free']['statuses']=={'failed':1}
    assert result['metrics']['selected']['statuses']=={'not_run':1}
    with pytest.raises(ValueError,match='holdout remains unopened'):run.run(protocol,out,'holdout')
    assert len(calls)==1


def test_load_failure_has_no_disappearing_rows(tmp_path,monkeypatch):
    protocol,out,plan=setup(tmp_path,monkeypatch)
    def broken(*_):raise RuntimeError('load failed')
    monkeypatch.setattr(run,'model_factory',broken)
    result=run.run(protocol,out,'development')
    assert result['metrics']['free']['statuses']=={'not_run':1}
    assert result['metrics']['selected']['statuses']=={'not_run':1}
    assert result['error']=='RuntimeError: load failed'


def test_exception_after_call_start_remains_unknown(tmp_path,monkeypatch):
    protocol,out,plan=setup(tmp_path,monkeypatch)
    class Broken:
        def generate(self,*a,**kw):raise RuntimeError('process boundary fixture')
    monkeypatch.setattr(run,'model_factory',lambda *_:Broken())
    result=run.run(protocol,out,'development')
    assert result['metrics']['free']['statuses']=={'unknown_after_interruption':1}
    assert result['metrics']['selected']['statuses']=={'not_run':1}


def test_partial_is_kept_and_coaching_quality_unrated(tmp_path,monkeypatch):
    protocol,out,plan=setup(tmp_path,monkeypatch)
    class Fixture:
        def generate(self,*a,**kw):return {'status':'partial','finish_reason':'token_limit','raw_text':'kept'}
    monkeypatch.setattr(run,'model_factory',lambda *_:Fixture())
    result=run.run(protocol,out,'development')
    assert result['execution_status']=='complete_without_backend_failure'
    assert result['completed_request_count']==2
    assert result['metrics']['free']['raw_best_legal']==0
    assert run.read(out/'development'/'response-0000.json')['raw_text']=='kept'
    with pytest.raises(FileExistsError):run.run(protocol,out,'development')


def test_verification_failure_precedes_any_model_or_output(tmp_path,monkeypatch):
    protocol,out,plan=setup(tmp_path,monkeypatch)
    def broken(_):raise ValueError('pin changed')
    monkeypatch.setattr(run,'verify',broken)
    monkeypatch.setattr(run,'model_factory',lambda *_:pytest.fail('No model call'))
    with pytest.raises(ValueError,match='pin changed'):run.run(protocol,out,'development')
    assert not out.exists()
