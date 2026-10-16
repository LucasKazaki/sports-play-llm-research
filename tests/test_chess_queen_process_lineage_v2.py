"""Pure identity/closure fixtures; no process, model or Torch calls."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chess_queen_process_lineage_v2 as s


def identities():
    launcher={'pid':10,'parent_pid':1,'image':s.normalized('venv/python.exe'),'created':100,'in_job':True}
    delegate={'pid':11,'parent_pid':10,'image':s.normalized('base/python.exe'),'created':101,'in_job':True}
    return launcher,delegate


def test_direct_and_exact_one_hop():
    a,b=identities()
    assert s.validate(1,a,a,'venv/python.exe','base/python.exe')=='direct'
    assert s.validate(1,a,b,'venv/python.exe','base/python.exe')=='venv_redirector'


@pytest.mark.parametrize('target,key,value',[(0,'parent_pid',99),(0,'image','wrong'),(0,'in_job',False),
    (1,'parent_pid',12),(1,'image','wrong'),(1,'in_job',False),(1,'created',99)])
def test_wrong_parent_image_job_extra_hop_or_creation_is_rejected(target,key,value):
    values=list(identities());values[target][key]=value
    with pytest.raises(ValueError):s.validate(1,*values,'venv/python.exe','base/python.exe')


def test_direct_reused_identity_is_rejected():
    a,b=identities();b={**a,'created':102}
    with pytest.raises(ValueError,match='identity'):s.validate(1,a,b,'venv/python.exe','base/python.exe')


def tracker_fixture(exited=True):
    a,b=identities();t=object.__new__(s.Tracker)
    t.outer=1;t.launcher=a;t.delegate=b;t.venv='venv/python.exe';t.base='base/python.exe';t.require_job=True
    t.records={10:a,11:b};t.handles={10:'launcher-handle',11:'delegate-handle'}
    class OS:
        def exited(self,handle):return exited or handle=='launcher-handle'
    t.os=OS();t.query_pids=set();t.sampler=None;return t


def test_live_delegate_or_selfreported_unobserved_pid_cannot_close_request():
    t=tracker_fixture(False)
    with pytest.raises(ValueError,match='still live'):t.proof({'pid':11,'parent_pid':10})
    with pytest.raises(ValueError,match='live observed'):t.proof({'pid':99,'parent_pid':10})
    with pytest.raises(ValueError,match='live observed'):t.proof({'pid':11,'parent_pid':1})


def test_all_stable_handles_exit_before_closure():
    t=tracker_fixture();proof=t.proof({'pid':11,'parent_pid':10})
    assert proof['all_observed_handles_exited']and proof['topology']=='venv_redirector'
    assert proof['runtime_pid']==11 and proof['launcher_pid']==10


def test_extra_descendant_and_multiple_delegate_rejected():
    t=tracker_fixture()
    t.os.snapshot=lambda:{10:1,11:10,12:11}
    t.os.retain=lambda pid,parent:('foreign',{'pid':pid,'parent_pid':parent,'image':'unexpected.exe','created':102,'in_job':True})
    t.os.k=type('K',(),{'CloseHandle':lambda self,handle:True})()
    with pytest.raises(ValueError,match='Unknown descendant'):t.observe()


def test_termination_uses_only_retained_owned_handles():
    t=tracker_fixture(False);actions=[];closed={'launcher-handle':False,'delegate-handle':False}
    t.os.exited=lambda handle:closed[handle]
    class K:
        def TerminateProcess(self,handle,code):actions.append(handle);closed[handle]=True;return True
    t.os.k=K();t.terminate_owned()
    assert actions==['delegate-handle','launcher-handle']


@pytest.mark.parametrize('key,value',[('image','other/conhost.exe'),('parent_pid',11),('created',99),('in_job',False)])
def test_aux_console_exact_system_image_parent_creation_and_job(key,value):
    launcher,_=identities();console={'pid':12,'parent_pid':10,'image':s.normalized('system/conhost.exe'),'created':102,'in_job':True}
    s.validate_console(launcher,console,'system/conhost.exe',True)
    console[key]=value
    with pytest.raises(ValueError):s.validate_console(launcher,console,'system/conhost.exe',True)


def test_console_cannot_be_runtime_or_be_left_live_at_closure():
    t=tracker_fixture();console={'pid':12,'parent_pid':10,'image':s.normalized('system/conhost.exe'),'created':102,'in_job':True}
    t.auxiliary=console;t.records[12]=console;t.handles[12]='console-handle'
    with pytest.raises(ValueError,match='Auxiliary process'):t.proof({'pid':12,'parent_pid':10})
    t.os.exited=lambda handle:handle!='console-handle'
    with pytest.raises(ValueError,match='still live'):t.proof({'pid':11,'parent_pid':10})


@pytest.mark.parametrize('changed',['parent','image','created','job','hash'])
def test_only_hashed_known_direct_runtime_resource_query_is_admitted(tmp_path,changed):
    import hashlib
    _,runtime=identities();exe=tmp_path/'nvidia-smi.exe';exe.write_bytes(b'authored fixture executable bytes, never executed')
    sampler={'executable':{'path':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}}
    record={'pid':12,'parent_pid':11,'image':s.normalized(exe),'created':103,'in_job':True}
    s.validate_query(runtime,record,sampler,True)
    if changed=='parent':record['parent_pid']=10
    elif changed=='image':record['image']='other/nvidia-smi.exe'
    elif changed=='created':record['created']=100
    elif changed=='job':record['in_job']=False
    else:sampler['executable']['sha256']='wrong'
    with pytest.raises(ValueError):s.validate_query(runtime,record,sampler,True)


def test_query_cannot_be_runtime_and_must_exit(tmp_path):
    t=tracker_fixture();query={'pid':12,'parent_pid':11,'image':'nvidia-smi.exe','created':102,'in_job':True}
    t.records[12]=query;t.handles[12]='query-handle';t.query_pids={12}
    with pytest.raises(ValueError,match='Auxiliary'):t.proof({'pid':12,'parent_pid':11})
    t.os.exited=lambda handle:handle!='query-handle'
    with pytest.raises(ValueError,match='still live'):t.proof({'pid':11,'parent_pid':10})


def test_a_second_python_delegate_is_rejected():
    t=tracker_fixture();t.console=s.normalized('system/conhost.exe')
    t.os.snapshot=lambda:{10:1,11:10,12:10}
    t.os.retain=lambda pid,parent:('second-python',{'pid':pid,'parent_pid':parent,
        'image':s.normalized('base/python.exe'),'created':104,'in_job':True})
    t.os.k=type('K',(),{'CloseHandle':lambda self,handle:True})()
    with pytest.raises(ValueError,match='Multiple interpreter'):t.observe()
