"""Injected serial workers and truth gates; no actual process/backend calls."""
from pathlib import Path
import ast,contextlib,json,sys
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import run_conditional as c


def fixture(tmp_path,monkeypatch,held=False):
    monkeypatch.setattr(c,'TASK',tmp_path);monkeypatch.setattr(c,'ROOT',tmp_path/'repo')
    checkpoint=tmp_path/'work/daytime/checkpoint.json';checkpoint.parent.mkdir(parents=True)
    c.write(checkpoint,{'active_gpu_job':None},create=True)
    rows=[]
    for group in range(16 if held else 1):
        for mode in (('free','selected_a','selected_b')if held else('free','selected')):
            packet={'fen':'AUTHORED-FEN-'+str(group)}
            if mode!='free':packet['selected_uci']='e2e4'if mode!='selected_b'else'd2d4'
            rows.append({'case_id':str(len(rows)),'group_id':str(group),'mode':mode,'input':packet})
    inputs=tmp_path/'inputs.jsonl';inputs.write_text(''.join(json.dumps(row)+'\n'for row in rows))
    worker=tmp_path/'worker.py';worker.write_text('# authored worker only\n')
    plan={'mode':'heldout'if held else'qualification','input_rows':c.bind(inputs),
        'conditions':{'baseline':{'sha256':'current192'},'selected':{'sha256':'conditional192'}},
        'assignments':[{'case_id':str(i),'condition':name}for i,name in enumerate(('baseline','selected'))],
        'phase_maximum_seconds':4500 if held else 450,'actual_out':str(tmp_path/'out'),
        'cutoff_utc':'2099-01-01T00:00:00+00:00','dependencies':[],
        'child_script':{'path':'scripts/authored.py'},'owned_worker_source':c.bind(worker)}
    protocol=tmp_path/'protocol.json';c.write(protocol,plan,create=True)
    monkeypatch.setattr(c,'verify',lambda *args:None)
    monkeypatch.setattr(c,'FileLock',lambda *args,**kwargs:contextlib.nullcontext())
    monkeypatch.setattr(c,'check_case',lambda *args:{'raw_status':'completed','raw_finish_reason':'eos'})
    calls=[]
    def launch(*args):calls.append(args);return {'returncode':0}
    def execute(launcher=launch,scorer=lambda *args:None):
        return c.run(plan,protocol,tmp_path/'out',{}, {},launcher=launcher,
            sampler=lambda:{'commit_total_bytes':100},floor_check=lambda *args:None,scorer=scorer)
    return plan,tmp_path/'out',rows,calls,execute


def test_fixed192_qualification_serial_and_truth_unopened(tmp_path,monkeypatch):
    plan,out,rows,calls,execute=fixture(tmp_path,monkeypatch)
    result=execute()
    assert result['status']=='passed'and result['completed_children']==2 and len(calls)==2
    assert [row['identity']['sha256']for row in result['rows']]==['current192','conditional192']
    assert not result['labels_opened']and not result['outer_torch_imported']


def test_first_failure_keeps_all96_and_never_opens_truth(tmp_path,monkeypatch):
    plan,out,rows,calls,execute=fixture(tmp_path,monkeypatch,True);scores=[]
    def fail(*args):calls.append(args);raise OSError('authored launch failure')
    result=execute(launcher=fail,scorer=lambda *args:scores.append(1))
    assert len(calls)==1 and result['planned']==96 and result['rows'][0]['status']=='active_unknown'
    assert sum(row['status']=='not_run'for row in result['rows'])==95
    assert not scores and not result['labels_opened']


def test_both_closed48_panels_precede_truth_and_keep_fixed_order(tmp_path,monkeypatch):
    plan,out,rows,calls,execute=fixture(tmp_path,monkeypatch,True)
    def score(plan,rows,out):
        assert c.read(out/'closed.json')['completed_children']==96
        assert len(rows)==48
        for name in ('baseline','selected'):
            saved=c.read(out/(name+'.json'))
            assert saved['status']=='completed'and saved['planned']==len(saved['rows'])==48
    result=execute(scorer=score)
    assert result['status']=='passed'and result['labels_opened']and len(calls)==96
    assert [row['condition']for row in result['rows']]==['baseline']*48+['selected']*48


def test_source_and_frozen_launch_numerical_functions_are_exact_prior_AST():
    def functions(path):
        return {node.name:ast.dump(node)for node in ast.parse(path.read_text()).body
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    prior=functions(HERE.parent/'chess-queen-coach-flat-v1/run_once_v2.py')
    current=functions(HERE/'run_conditional.py')
    assert set(current)==set(prior)
    assert all(current[name]==value for name,value in prior.items()if name not in('verify','score'))
    assert 'torch'not in sys.modules


def test_postclosure_scorer_failure_does_not_claim_truth_unopened(tmp_path,monkeypatch):
    plan,out,rows,calls,execute=fixture(tmp_path,monkeypatch,True)
    def score(*args):
        c.write(out/'truth-access.json',{'status':'references_opened'},create=True)
        raise OSError('authored scoring storage failure')
    result=execute(scorer=score)
    assert result['status']=='failed'and result['completed_children']==96
    assert result['labels_opened']and result['truth_access_state']=='references_opened_scoring_failed'
