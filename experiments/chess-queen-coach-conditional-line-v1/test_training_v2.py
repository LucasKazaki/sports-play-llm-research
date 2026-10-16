"""Authored metadata/accounting mocks and actual AST comparisons; no backend/data."""
import ast,copy,json,math
from pathlib import Path
import sys
import pytest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'chess-queen-coach-daytime-v1'))
import train as subject
import qualify_conditional as warm
import conditional_runtime as runtime
import prepare_training_v2 as builder
import training_contract as contract
from chess_queen_coach_counterfactual_runtime_v1 import Runtime as OriginalRuntime

def functions(path):return {node.name:ast.dump(node)for node in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(node,ast.FunctionDef)}

def test_training_and_development_numerical_bodies_are_exact_preserved_AST():
    old=functions(HERE.parent/'chess-queen-coach-daytime-v1/daytime_train.py');new=functions(HERE/'train.py')
    for name in ['train','checkpoint_development','score_panel','read_rows','references','guard_for','snapshot']:
        assert new[name]==old[name],name
    old=functions(HERE.parent/'chess-queen-coach-daytime-v1/qualify_training_direct_v1.py');new=functions(HERE/'qualify_conditional.py')
    for name in ['first_eight','micros','snapshot']:assert new[name]==old[name],name

def test_runtime_only_overrides_saved_provenance_and_preserves_shared_inference():
    assert {key for key in runtime.Runtime.__dict__ if not key.startswith('__')}=={'save_adapter'}
    for name in ['load','loss','tokenize','infer','load_adapter','verify_frozen','release_inactive']:
        assert getattr(runtime.Runtime,name)is getattr(OriginalRuntime,name)
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules

def conditions():
    return [dict(step=step,status='completed',raw_planned=6,raw_completed=6,nll_completed=96,response_token_nll=1+step,
        counts={'arbitrary_monitoring_score':1000-step},identity={'step':step})for step in [0,48,96,192]]

def test_terminal192_fixed_despite_better_earlier_development_scores():
    rows=conditions();assert subject.select(rows)['step']==192
    rows[-1]['response_token_nll']=1000000;assert subject.select(rows)['step']==192

@pytest.mark.parametrize('fault',['missing','partial','nonfinite'])
def test_incomplete_monitoring_is_failure_not_new_selection(fault):
    rows=conditions()
    if fault=='missing':rows.pop()
    elif fault=='partial':rows[-1]['raw_completed']=5
    else:rows[-1]['response_token_nll']=math.nan
    with pytest.raises(ValueError):subject.select(rows)

def test_guard_failure_preserves1536_training_and_all_dev_pending(tmp_path,monkeypatch):
    training=[{'case_id':f't{i}','group_id':'t'}for i in range(1536)]
    dev=[{'case_id':f'd{i}','group_id':f'g{i//3}','mode':['free','selected_a','selected_b'][i%3],'input':{'fen':'authored'}}for i in range(96)]
    monkeypatch.setattr(subject,'read_rows',lambda path,targets:training if str(path)=='train'else dev)
    monkeypatch.setattr(subject,'references',lambda path,rows:{})
    monkeypatch.setattr(subject.checked.nf4,'binding',lambda item:Path(item['path']))
    def failure(*args):raise RuntimeError('authored setup guard failure')
    monkeypatch.setattr(subject,'guard_for',failure)
    plan={'data':{'train':{'path':'train'},'development':{'path':'dev'},'development_references':{'path':'refs'}},
        'development_raw_groups':['g0','g1'],'training':{'seed':4082086},'successful_memory_qualification':{'sha256':'historical'},'warm_start':{'path':'original64'}}
    protocol=tmp_path/'protocol.json';protocol.write_text('{}');out=tmp_path/'attempt'
    with pytest.raises(RuntimeError,match='setup guard'):subject.train(plan,protocol,out)
    assert json.loads((out/'run.json').read_text())['status']=='failed'
    final=json.loads((out/'training-denominator.json').read_text())
    assert final['planned']==1536 and len(final['rows'])==1536 and all(row['status']=='not_run'for row in final['rows'])
    for step in [0,48,96,192]:
        assert len(json.loads((out/f'development-{step:04d}.json').read_text())['nll_rows'])==96
        assert len(json.loads((out/f'raw-development-{step:04d}.json').read_text())['rows'])==6
    assert json.loads((out/'resources.json').read_text())==[]

def test_disposable_setup_failure_preserves8pending_no_model(tmp_path,monkeypatch):
    protocol=tmp_path/'protocol.json';protocol.write_text('{}');plan={'training':{'seed':4082086},'data':{'train':{'path':'authored'}}}
    monkeypatch.setattr(warm,'verify',lambda path:plan)
    monkeypatch.setattr(warm.preserved,'read_rows',lambda *args:[{'case_id':f'case{i}'}for i in range(1536)])
    monkeypatch.setattr(warm.checked.nf4,'binding',lambda item:Path(item['path']))
    monkeypatch.setattr(warm,'snapshot',lambda *args:None)
    def fail():raise RuntimeError('authored guard construction failure')
    def model(*args):raise AssertionError('no model setup')
    with pytest.raises(RuntimeError,match='guard construction'):warm.run(plan,protocol,tmp_path/'attempt',runtime_factory=model,guard_factory=fail)
    value=json.loads((tmp_path/'attempt/qualification.json').read_text())
    assert value['status']=='failed'and len(value['rows'])==8 and all(row['status']=='not_run'for row in value['rows'])
    assert value['updates_completed']==value['presentations_completed']==0

def test_first_backward_failure_stops_full_eight_denominator(tmp_path):
    class Runtime:
        def __init__(self):self.calls=0
        def loss(self,*args,**kwargs):
            self.calls+=1
            if self.calls==4:raise RuntimeError('authored backward failure')
            return .5
        def release_inactive(self,*args):pass
    class Optimizer:
        def step(self):raise AssertionError('no optimizer after failed micro')
    result={'rows':[{'status':'not_run'}for _ in range(8)],'presentations_completed':0,'updates_completed':0}
    r=Runtime()
    with pytest.raises(RuntimeError,match='backward failure'):
        warm.micros(r,[{'case_id':str(i)}for i in range(8)],[None]*8,Optimizer(),lambda:1.,lambda:None,tmp_path,result,lambda:None)
    assert r.calls==4 and result['presentations_completed']==3
    assert [row['status']for row in result['rows']]==['completed']*3+['active_unknown']+['not_run']*4

def test_science_drift_and_deadline_are_rejected():
    parent={key:{'authored':key}for key in contract.SAME}
    parent['training']={'updates':192,'gradient_accumulation':8}
    plan=copy.deepcopy(parent);plan.update(phase_maximum_seconds={'training':3000,'heldout':4500},
        cutoff_utc=contract.CUTOFF,admission_latest_utc=contract.ADMISSION,maximum_seconds=3000,worker_maximum_seconds=3030,external_maximum_seconds=3060,
        selection_method=builder.SELECTION,fixed_treatment_step=192,comparison_control={'step':192,'candidate_id':'queen-pawn-8/nf4-coach-counterfactual-v1'})
    contract.science(plan,parent)
    plan['training']['updates']=191
    with pytest.raises(ValueError,match='science differs'):contract.science(plan,parent)
    plan['training']=parent['training'];plan['admission_latest_utc']='2026-10-16T19:00:00+00:00'
    with pytest.raises(ValueError,match='Operating bounds'):contract.science(plan,parent)


def test_prospective_qualifier_builder_copies_complete_science_and_actual_dispatch_vector(tmp_path):
    def file(name,value):
        path=tmp_path/name;path.write_text(json.dumps(value));return path
    parent={key:{'authored':key}for key in contract.SAME}
    parent.update(training={'updates':192,'gradient_accumulation':8},daytime_authority={'path':'authored-authority','sha256':'authored'},
        corpus_manifest={'path':'authored-parent-manifest','sha256':'parent'},dependencies=[])
    p=file('parent.json',parent);a=file('audit.json',{'status':'authored-not-actual'});s=file('selection.json',
        {'status':'selected','selected':{'step':192,'candidate_id':'queen-pawn-8/nf4-coach-counterfactual-v1'}})
    data=tmp_path/'data';data.mkdir();(data/'manifest.json').write_text(json.dumps({'files':{name:{'sha256':'authored'}for name in ['train.jsonl','development.jsonl','development-references.jsonl']}}))
    metadata=[file(name,{})for name in ['export.json','export-closed.json','token-plan.json','token-result.json','data-audit.json']]
    out=tmp_path/'qualifier-plan.json';output=tmp_path/'qualification-attempt'
    builder.prepare_qualification(p,a,s,data,*metadata,out,output)
    plan=json.loads(out.read_text())
    for key in contract.SAME:assert plan[key]==parent[key]
    assert plan['counterfactual_runtime']['path'].endswith('conditional_runtime.py')
    assert plan['conditional_evaluator']['path'].endswith('evaluate_v2.py')
    assert plan['maximum_seconds']==600 and plan['worker_maximum_seconds']==630 and plan['external_maximum_seconds']==660
    assert plan['selection_method']==builder.SELECTION and plan['fixed_treatment_step']==192
    assert plan['expected_worker_arguments'][0]==str((HERE/'qualify_conditional.py').resolve())
    assert plan['expected_worker_arguments'][2]==str(out.resolve())
    assert plan['expected_worker_script']=='experiments/chess-queen-coach-conditional-line-v1/qualify_conditional.py'
    contract.original.worker({'status':'completed','exit_code':0,'child_exited_before_lease_release':True,
        'script':plan['expected_worker_script'].replace('/','\\'),
        'arguments_sha256':plan['expected_worker_arguments_sha256']},plan['expected_worker_script'],plan['expected_worker_arguments'])
    assert not output.exists()  # Builder prepares metadata only; no data/model execution.

def test_final_training_freezer_refuses_unclosed_qualification_before_output(tmp_path,monkeypatch):
    q=tmp_path/'q.json';q.write_text(json.dumps({'dependencies':[],'expected_worker_script':'authored','expected_worker_arguments':['authored']}))
    records=[]
    for name in ['result','worker','audit']:
        path=tmp_path/(name+'.json');path.write_text('{}');records.append(path)
    def reject(plan):raise ValueError('authored unclosed actual qualification')
    monkeypatch.setattr(contract,'qualification_gate',reject)
    out=tmp_path/'training.json'
    with pytest.raises(ValueError,match='unclosed actual'):builder.prepare_training(q,*records,out,tmp_path/'train-attempt')
    assert not out.exists()


def test_actual_worker_relative_script_contract_keeps_full_absolute_arguments():
    import hashlib
    script=HERE/'qualify_conditional.py'
    arguments=[str(script.resolve()),'--protocol','authored-plan','--out','authored-output']
    expected=script.relative_to(contract.ROOT).as_posix()
    worker={'status':'completed','exit_code':0,'child_exited_before_lease_release':True,
        'script':expected.replace('/','\\'),'arguments_sha256':hashlib.sha256(json.dumps(arguments).encode()).hexdigest()}
    contract.original.worker(worker,expected,arguments)
    assert Path(arguments[0]).is_absolute()and not Path(expected).is_absolute()
