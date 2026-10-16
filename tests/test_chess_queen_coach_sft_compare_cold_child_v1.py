"""Authored callbacks only; no Torch, learned weights or actual child/model."""
from pathlib import Path
import sys
import chess
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import chess_queen_coach_sft_compare_cold_child_v1 as subject


def request():return {'protocol_sha256':'frozen','identity':{'sha256':'fixture'},
    'row':{'case_id':'fixture','input':{'fen':chess.STARTING_FEN}}}


@pytest.mark.parametrize('failure',[None,'load','postcleanup','storage','raw'])
def test_one_raw_request_immediately_saved_before_postprocessing_and_firstfailure_stops(tmp_path,failure):
    calls=[];out=tmp_path/'child'
    class Fake:
        def __init__(self,*args):pass
        def load(self):
            calls.append('load')
            if failure=='load':raise RuntimeError('authored load')
        def load_adapter(self,identity):calls.append(('reload',identity))
        def release_inactive(self,phase):
            calls.append(phase)
            if 'returned'in phase:
                assert(out/'raw.json').exists()
                if failure=='postcleanup':raise RuntimeError('authored cleanup')
        def infer(self,row,identity):calls.append('infer');return {'status':'failed'if failure=='raw'else'completed','raw_text':'kept','finish_reason':'eos'}
        def verify_frozen(self):
            assert(out/'raw.json').exists();calls.append('storage')
            if failure=='storage':raise RuntimeError('authored storage')
            return {'identical':True}
    plan={'model_runtime':{},'cutoff_utc':'2099-01-01T00:00:00+00:00'}
    call=lambda:subject.execute(plan,request(),out,tmp_path/'CANCEL',Fake,lambda:(lambda:None,[]),lambda:True)
    if failure:
        with pytest.raises(RuntimeError):call()
    else:assert call()['status']=='passed'
    receipt=subject.checked.nf4.base.read_json(out/'closed.json')
    assert receipt['status']==('failed'if failure else'passed')and(out/'resources.json').exists()
    assert calls.count('infer')==(0 if failure=='load'else 1)
    if failure!='load':
        assert receipt['raw_saved_before_postprocessing']and subject.checked.nf4.base.read_json(out/'raw.json')['raw_text']=='kept'


@pytest.mark.parametrize('problem',['job','cancel','leak'])
def test_job_cancel_or_forbidden_input_stops_before_model_setup(tmp_path,problem):
    row=request()
    if problem=='leak':row['row']['input']['reference_pv']=['e2e4']
    if problem=='cancel':(tmp_path/'CANCEL').touch()
    def forbidden(*args):raise AssertionError('model setup attempted')
    with pytest.raises((RuntimeError,ValueError)):
        subject.execute({'model_runtime':{},'cutoff_utc':'2099-01-01T00:00:00+00:00'},row,tmp_path/'child',
            tmp_path/'CANCEL',forbidden,lambda:(lambda:None,[]),lambda:problem!='job')
    assert subject.checked.nf4.base.read_json(tmp_path/'child/closed.json')['generation_requests_started']==0
