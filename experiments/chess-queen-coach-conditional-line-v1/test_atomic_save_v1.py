"""Authored tiny files, injected clocks, and Windows deny-delete handles only."""
from pathlib import Path
import ast,ctypes,json,os,sys,threading,time
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import bounded_atomic_save_v1 as subject


def permission(code):
    error=PermissionError(13,'authored Windows sharing denial')
    error.winerror=code
    return error


class Clock:
    def __init__(self):self.now=0.;self.sleeps=[]
    def monotonic(self):return self.now
    def sleep(self,seconds):self.sleeps.append(seconds);self.now+=seconds


@pytest.mark.parametrize('code',[5,32,33])
def test_transient_permission_failure_replaces_only_after_closed_temp(code,tmp_path):
    destination=tmp_path/'run.json';destination.write_text('{"old":true}')
    temporary=tmp_path/'new.tmp';temporary.write_text('{"new":true}')
    clock=Clock();calls=[];first=permission(code)
    def replace(source,target):
        calls.append(1)
        with Path(source).open('r+')as stream:assert json.load(stream)=={'new':True}
        if len(calls)==1:raise first
        os.replace(source,target)
    subject.replace_closed(temporary,destination,replace=replace,monotonic=clock.monotonic,sleep=clock.sleep)
    assert len(calls)==2 and clock.sleeps==[.02]
    assert json.loads(destination.read_text())=={'new':True}and not temporary.exists()


@pytest.mark.parametrize('code',[5,32,33])
def test_persistent_permission_preserves_first_error_target_and_temp(code,tmp_path):
    destination=tmp_path/'run.json';destination.write_text('{"old":true}')
    temporary=tmp_path/'new.tmp';temporary.write_text('{"new":true}')
    clock=Clock();calls=[];first=permission(code)
    def replace(*args):
        calls.append(1)
        raise first if len(calls)==1 else permission(code)
    with pytest.raises(PermissionError)as caught:
        subject.replace_closed(temporary,destination,replace=replace,monotonic=clock.monotonic,sleep=clock.sleep)
    assert caught.value is first and 1<len(calls)<=26 and clock.now<=.5
    assert json.loads(destination.read_text())=={'old':True}
    assert json.loads(temporary.read_text())=={'new':True}


@pytest.mark.parametrize('error',[permission(2),PermissionError('without Windows code'),OSError('other failure')])
def test_nonretryable_errors_propagate_unchanged_immediately(error):
    clock=Clock();calls=[]
    def replace(*args):calls.append(1);raise error
    with pytest.raises(type(error))as caught:
        subject.replace_closed('temporary','destination',replace=replace,monotonic=clock.monotonic,sleep=clock.sleep)
    assert caught.value is error and calls==[1]and not clock.sleeps


def test_fixed_attempt_bound_survives_nonadvancing_clock():
    calls=[];first=permission(32)
    def replace(*args):calls.append(1);raise first
    with pytest.raises(PermissionError)as caught:
        subject.replace_closed('temporary','destination',replace=replace,monotonic=lambda:0.,sleep=lambda seconds:None)
    assert caught.value is first and len(calls)==26


def test_serialization_failure_never_replaces_destination_or_leaks_open_handle(tmp_path):
    destination=tmp_path/'run.json';destination.write_text('{"old":true}')
    with pytest.raises(ValueError):subject.save(destination,{'invalid':float('nan')})
    assert json.loads(destination.read_text())=={'old':True}
    leftovers=list(tmp_path.glob('.run.json.*.tmp'));assert len(leftovers)==1
    leftovers[0].unlink()  # Windows deletion succeeds only after our write handle closes.


def test_success_has_exact_prior_json_bytes_and_no_temporary_leftover(tmp_path):
    path=tmp_path/'run.json';prior=tmp_path/'prior.json';value={'status':'completed','nested':[1,True,None]}
    prior.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    subject.save(path,value)
    assert path.read_bytes()==prior.read_bytes()and not list(tmp_path.glob('.run.json.*.tmp'))


def deny_delete(path):
    from ctypes import wintypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,
        wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE)
    api.CreateFileW.restype=wintypes.HANDLE
    api.CloseHandle.argtypes=(wintypes.HANDLE,);api.CloseHandle.restype=wintypes.BOOL
    handle=api.CreateFileW(str(path),0x80000000,0x1|0x2,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    return api,handle


@pytest.mark.skipif(sys.platform!='win32',reason='Actual Windows file-sharing contract')
def test_actual_windows_transient_deny_delete_handle_released_within_bound(tmp_path):
    path=tmp_path/'run.json';path.write_text('{"old":true}')
    api,handle=deny_delete(path);closed=[]
    def release():closed.append(bool(api.CloseHandle(handle)))
    timer=threading.Timer(.08,release);timer.start();started=time.monotonic()
    try:subject.save(path,{'new':True})
    finally:
        timer.join(timeout=1)
        if not closed:release()
    assert closed==[True]and json.loads(path.read_text())=={'new':True}
    assert time.monotonic()-started<1.5 and not list(tmp_path.glob('.run.json.*.tmp'))


@pytest.mark.skipif(sys.platform!='win32',reason='Actual Windows file-sharing contract')
def test_actual_windows_persistent_deny_delete_fails_preserving_old_target(tmp_path):
    path=tmp_path/'run.json';path.write_text('{"old":true}')
    api,handle=deny_delete(path);started=time.monotonic()
    try:
        with pytest.raises(PermissionError)as caught:subject.save(path,{'new':True})
        assert caught.value.winerror in subject.RETRYABLE_WINERRORS
    finally:assert api.CloseHandle(handle)
    elapsed=time.monotonic()-started
    assert .4<=elapsed<1.5 and json.loads(path.read_text())=={'old':True}
    leftovers=list(tmp_path.glob('.run.json.*.tmp'));assert len(leftovers)==1
    assert json.loads(leftovers[0].read_text())=={'new':True}
    leftovers[0].unlink()


def test_train_v4_preserves_every_numerical_function_and_changes_only_save_alias():
    def functions(name):
        return {node.name:ast.dump(node)for node in ast.parse((HERE/name).read_text()).body if isinstance(node,ast.FunctionDef)}
    assert functions('train_v3.py')==functions('train_v4.py')
    text=(HERE/'train_v4.py').read_text()
    assert 'from bounded_atomic_save_v1 import save'in text and 'save=prior.save'not in text
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules
