"""Pure fake OS-probe lifecycle tests; actual OS probe remains undispatched."""
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_process_observer as subject


def test_controlled_stale_probe_closes_creator_handle_before_measuring87(tmp_path, monkeypatch):
    handle = SimpleNamespace(closed=False)
    handle.Close = lambda: setattr(handle, 'closed', True)
    class Process:
        pid = 77; returncode = 0; _handle = handle
        def __init__(self, command, **kwargs): Path(command[3]).write_text('ready')
        def poll(self): return self.returncode
    monkeypatch.setattr(subject.subprocess, 'Popen', Process)
    def retain(pid, parent):
        assert handle.closed
        raise subject.ObservationError('authored87', {'pid': pid, 'parent_pid': parent,
            'stage': 'OpenProcess', 'open_process_winerror': 87})
    called = []
    context = SimpleNamespace(outer=os.getpid(), records={os.getpid(): {'pid': os.getpid()}},
        handles={os.getpid(): 90}, os=SimpleNamespace(snapshot=lambda: {77: os.getpid()}, retain=retain),
        certify_absence=lambda *args: called.append(args) or {'exit_proved': False},
        assert_baseline_only=lambda stage: {'stage': stage})
    value = subject.stale_case(context, tmp_path / 'case', subject.time.monotonic()+10,
        tmp_path / 'CANCEL', datetime.now(timezone.utc)+timedelta(hours=1))
    assert value['exact_87_branch_measured'] and value['status'] == 'completed' and len(called) == 1
    assert value['absence']['exit_proved'] is False


@pytest.mark.parametrize('error_code', [5, 6])
def test_other_real_error_is_not_rewritten_as_absence(tmp_path, monkeypatch, error_code):
    handle = SimpleNamespace(Close=lambda: None)
    class Process:
        pid = 77; returncode = 0; _handle = handle
        def __init__(self, command, **kwargs): Path(command[3]).write_text('ready')
        def poll(self): return 0
    monkeypatch.setattr(subject.subprocess, 'Popen', Process)
    def retain(pid, parent):
        raise subject.ObservationError('authored other failure', {'pid': pid, 'parent_pid': parent,
            'stage': 'OpenProcess', 'open_process_winerror': error_code})
    context = SimpleNamespace(os=SimpleNamespace(snapshot=lambda: {77: os.getpid()}, retain=retain))
    with pytest.raises(subject.ObservationError):
        subject.stale_case(context, tmp_path / 'case', subject.time.monotonic()+10,
            tmp_path / 'CANCEL', datetime.now(timezone.utc)+timedelta(hours=1))
    assert subject.read(tmp_path / 'case/closed.json')['status'] == 'failed'


def test_probe_failure_precreates_four_unknown_notrun_denominators(tmp_path, monkeypatch):
    protocol = tmp_path / 'protocol.json'; subject.save(protocol, {'authored': True})
    plan = {'cutoff_utc': '2099-01-01T00:00:00+00:00'}
    def fail(plan): raise ValueError('authored metadata-only setup error')
    monkeypatch.setattr(subject, 'verify', fail)
    with pytest.raises(ValueError): subject.run(plan, protocol, tmp_path / 'attempt')
    value = subject.read(tmp_path / 'attempt/closed.json')
    assert value['planned'] == 4 and value['completed'] == 0 and len(value['rows']) == 4
    assert all(row['status'] == 'not_run' for row in value['rows'])
    assert value['model_calls'] == value['engine_calls'] == value['CUDA_initializations'] == 0
