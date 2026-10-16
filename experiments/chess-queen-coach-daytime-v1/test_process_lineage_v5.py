"""Error-stage, buffer-completeness and separate-absence contract regressions."""
import ctypes
from ctypes import wintypes as W
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import process_lineage_v5 as subject
from test_job_context import Fake, context, record


def test_openprocess_failure_durably_identifies_exact_stage_pid_and_no_handle():
    class Kernel:
        def OpenProcess(self, rights, inherit, pid):
            assert rights == 0x1000 | 0x100000 | 1 and pid == 30
            ctypes.set_last_error(87); return 0
    api = subject.Windows.__new__(subject.Windows); api.k = Kernel()
    with pytest.raises(subject.ObservationError) as caught: api.retain(30, 21)
    assert caught.value.observation == {'stage': 'OpenProcess', 'pid': 30, 'parent_pid': 21,
        'open_process_winerror': 87, 'stable_handle_retained': False}


@pytest.mark.parametrize('fault', [None, 'short', 'duplicate', 'zero', 'unrelated_error', 'oversize'])
def test_immediate_job_buffer_contract_never_treats_partial_list_as_complete(fault):
    class Kernel:
        calls = 0
        def QueryInformationJobObject(self, job, kind, buffer, size, returned):
            self.calls += 1; assert job is None and kind == 3
            assigned = 3 if self.calls == 1 or fault == 'oversize' else 2
            ctypes.c_uint32.from_buffer(buffer, 0).value = assigned
            ctypes.c_uint32.from_buffer(buffer, 4).value = 2
            values = (ctypes.c_size_t * 2).from_buffer(buffer, 8)
            values[:] = [9, 9 if fault == 'duplicate' else 0 if fault == 'zero' else 10]
            returned._obj.value = 8 if fault == 'short' else 8 + 2 * ctypes.sizeof(ctypes.c_size_t)
            if fault == 'unrelated_error': ctypes.set_last_error(5); return False
            return True
    api = subject.Windows.__new__(subject.Windows); api.k = Kernel()
    if fault is None:
        assert api.current_job_pids() == [9, 10] and api.k.calls == 2
    else:
        with pytest.raises((ValueError, OSError)): api.current_job_pids()


@pytest.mark.parametrize('end_code', [18, 5])
def test_toolhelp_pid_zero_is_preserved_but_abnormal_traversal_end_fails(end_code):
    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', W.DWORD), ('th32ProcessID', W.DWORD), ('th32ParentProcessID', W.DWORD)]
    class Kernel:
        def CreateToolhelp32Snapshot(self, flags, pid): return 50
        def Process32FirstW(self, handle, entry):
            entry._obj.th32ProcessID = 0; entry._obj.th32ParentProcessID = 0; return True
        def Process32NextW(self, handle, entry): ctypes.set_last_error(end_code); return False
        def CloseHandle(self, handle): assert handle == 50
    api = subject.Windows.__new__(subject.Windows); api.k = Kernel(); api.Entry = Entry
    if end_code == 18: assert api.snapshot() == {0: 0}
    else:
        with pytest.raises(OSError): api.snapshot()


def tracker_fixture():
    fake = Fake(); ctx = context(fake)
    fake.records.update({20: record(20, 10, 'venv.exe', 200), 21: record(21, 20, 'base.exe', 201)})
    fake.parents.update({20: 10, 21: 20}); fake.active.extend([20, 21])
    tracker = subject.Tracker(20, 10, venv_image='venv.exe', base_image='base.exe', job_context=ctx)
    tracker.observe(); assert tracker.delegate['pid'] == 21
    return fake, ctx, tracker


def test_snapshot87_absence_stays_out_of_known_handles_runtime_and_termination():
    fake, ctx, tracker = tracker_fixture(); fake.parents[30] = 21; fake.active.append(30)
    original = fake.retain
    def retain(pid, parent, **kwargs):
        if pid != 30: return original(pid, parent, **kwargs)
        fake.parents.pop(30); fake.active.remove(30)
        raise subject.ObservationError('authored OpenProcess87', {'stage': 'OpenProcess',
            'pid': pid, 'parent_pid': parent, 'open_process_winerror': 87})
    fake.retain = retain; tracker.observe()
    assert set(tracker.absences) == {30} and 30 not in tracker.records and 30 not in tracker.handles
    with pytest.raises(ValueError, match='never be runtime'): tracker.proof({'pid': 30})
    killed = []
    def terminate(handle, code): killed.append(handle); fake.dead.add(handle); return True
    fake.TerminateProcess = terminate
    tracker.terminate_owned(); assert set(killed) == {20, 21} and 30 not in killed
    fake.active = [9, 10]; fake.parents.pop(20); fake.parents.pop(21)
    proof = tracker.proof({'pid': 21, 'parent_pid': 20})
    assert proof['all_observed_handles_exited'] and len(proof['unretained_absent_entries']) == 1


@pytest.mark.parametrize('reappearance', ['pid', 'parent', 'job'])
def test_later_reused_pid_ancestry_or_job_appearance_fails(reappearance):
    fake, ctx, tracker = tracker_fixture(); tracker.absences[30] = {'exit_proved': False}
    if reappearance == 'pid': fake.parents[30] = 21
    elif reappearance == 'parent': fake.parents[31] = 30
    else: fake.active.append(30)
    with pytest.raises(ValueError, match='reappeared'): tracker.observe()


def test_openprocess87_without_already_retained_actual_runtime_is_not_recovered():
    fake, ctx, tracker = tracker_fixture(); fake.parents[31] = 20
    def retain(*args, **kwargs):
        raise subject.ObservationError('not runtime parent', {'stage': 'OpenProcess', 'pid': 31,
            'parent_pid': 20, 'open_process_winerror': 87})
    fake.retain = retain
    with pytest.raises(subject.ObservationError): tracker.observe()
    assert not tracker.absences
