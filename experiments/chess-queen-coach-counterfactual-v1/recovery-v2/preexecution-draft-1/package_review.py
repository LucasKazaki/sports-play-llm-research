"""Package finite full source/test evidence; never dispatch the recovery."""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def info(path):return {'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size}
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(value,indent=2)+'\n')
tests=ROOT/'tests/test_chess_counterfactual_recovery_v2.py'
receipt={'schema':'chess.counterfactual-recovery-software-tests.v2','status':'passed',
    'command':'.venv-soccernet/Scripts/python.exe -m pytest tests/test_chess_counterfactual_recovery_v2.py -q',
    'execution_tool':'exec_command','chunk_id':'2d5450','exit_code':0,'tests':31,'elapsed_seconds':5.82,
    'stdout':'............................... [100%]\n31 passed in5.82s',
    'driver':info(HERE/'run_cpu_once.py'),'builder':info(HERE/'build_protocol.py'),'tests_source':info(tests),
    'operational_protocol':info(HERE/'protocol.json'),
    'metadata_only_protocol_build':{'chunk_id':'ea7e48','exit_code':0,'verified':'Exact reviewed old source/protocol, eight failed-attempt receipts, closed failed held worker and root context metadata.'},
    'scope':'Authored fake corpus/teacher/process/clock tests. Actual closed-worker/source metadata hashing only.',
    'actual_recovery_dispatches':0,'real_corpus_rows_constructed':0,'engine_calls':0,'model_GPU_calls':0,
    'current_held_response_reference_quality_reads':0,'old_scientific_source_edits':0}
save(HERE/'software-tests.json',receipt)
groups=[('driver',[HERE/'run_cpu_once.py']),('operational-metadata',[HERE/'build_protocol.py',HERE/'protocol.json',HERE/'README.md',Path(__file__)]),
    ('tests',[tests,HERE/'software-tests.json'])]
bundles=[]
for name,files in groups:
    path=HERE/(name+'-bundle.txt')
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        for file in files:stream.write('FILE '+str(file.relative_to(ROOT))+' SHA256 '+sha(file)+'\n'+file.read_text(encoding='utf-8')+'\n\n')
    assert path.stat().st_size<30000
    bundles.append(info(path))
save(HERE/'source-handoff.json',{'status':'awaiting_independent_source_review_not_execution_authorized',
    'sources':[info(HERE/'run_cpu_once.py'),info(HERE/'build_protocol.py')],'tests':info(tests),
    'protocol':info(HERE/'protocol.json'),'receipt':info(HERE/'software-tests.json'),'bundles':bundles,
    'actual_recovery_dispatches':0})
print(json.dumps(json.loads((HERE/'source-handoff.json').read_text()),indent=2))
