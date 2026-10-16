"""Versioned observer: retained EXIT and unretained measured absence stay distinct."""
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from chess_queen_process_lineage_v4 import (normalized, validate, validate_console,
    validate_query, ObservationError, Windows as PreviousWindows, Tracker as PreviousTracker)


class Windows(PreviousWindows):
    def __init__(self):
        super().__init__()
        self.k.QueryInformationJobObject.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p,
            W.DWORD, ctypes.POINTER(W.DWORD)]
        self.k.QueryInformationJobObject.restype = W.BOOL

    def snapshot(self):
        handle = self.k.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        result = {}; entry = self.Entry(); entry.dwSize = ctypes.sizeof(entry)
        try:
            ctypes.set_last_error(0)
            more = self.k.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                pid = int(entry.th32ProcessID)
                if pid in result:
                    raise ValueError('Duplicate process in complete system snapshot')
                result[pid] = int(entry.th32ParentProcessID)  # PID0 is a normal system entry.
                ctypes.set_last_error(0)
                more = self.k.Process32NextW(handle, ctypes.byref(entry))
            code = ctypes.get_last_error()
            if code != 18:  # ERROR_NO_MORE_FILES is the only complete traversal end.
                raise ctypes.WinError(code)
        finally:
            self.k.CloseHandle(handle)
        return result

    def current_job_pids(self):
        capacity = 64
        while capacity <= 4096:
            buffer = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            returned = W.DWORD()
            ctypes.set_last_error(0)
            ok = self.k.QueryInformationJobObject(None, 3, buffer, len(buffer), ctypes.byref(returned))
            code = ctypes.get_last_error()
            assigned = ctypes.c_uint32.from_buffer(buffer, 0).value
            count = ctypes.c_uint32.from_buffer(buffer, 4).value
            if not ok and code != 234:
                raise ctypes.WinError(code)
            if not ok or count < assigned:
                capacity *= 2
                continue
            if count != assigned or count > capacity or returned.value < 8 + count * ctypes.sizeof(ctypes.c_size_t):
                raise ValueError('Ambiguous/truncated immediate-job PID list')
            values = list((ctypes.c_size_t * count).from_buffer(buffer, 8))
            if len(set(values)) != count or any(pid <= 0 for pid in values):
                raise ValueError('Unique positive immediate-job IDs required')
            return values
        raise ValueError('Immediate-job PID list exceeds frozen4096 bound')

    def retain(self, pid, parent, allow_exited_transient=False, exit_wait_ms=0,
               minimum_created=0, require_job=True, termination_rights=True):
        rights = 0x1000 | 0x100000 | (1 if termination_rights else 0)
        handle = self.k.OpenProcess(rights, False, pid)
        if not handle:
            raise ObservationError('OpenProcess failed before retaining any handle',
                {'stage': 'OpenProcess', 'pid': pid, 'parent_pid': parent,
                 'open_process_winerror': ctypes.get_last_error(), 'stable_handle_retained': False})
        record = {'pid': pid, 'parent_pid': parent}
        try:
            times = [W.FILETIME() for _ in range(4)]
            if not self.k.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
                raise ctypes.WinError(ctypes.get_last_error())
            job = W.BOOL()
            if not self.k.IsProcessInJob(handle, None, ctypes.byref(job)):
                raise ctypes.WinError(ctypes.get_last_error())
            record.update(created=(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                in_job=bool(job.value))
            buffer = ctypes.create_unicode_buffer(32768); size = W.DWORD(len(buffer))
            if not self.k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                code = ctypes.get_last_error(); exited = self.exited(handle)
                record.update(image=None, image_query_winerror=code,
                    initial_stable_handle_exited=exited, stable_handle_exited=exited,
                    exit_wait_ms=0, exit_wait_elapsed_seconds=0., exit_wait_result=0 if exited else 258)
                eligible = (allow_exited_transient and code == 5 and record['created'] >= minimum_created
                    and (record['in_job'] or not require_job))
                if eligible and not exited:
                    if type(exit_wait_ms) is not int or not 0 <= exit_wait_ms <= 1000:
                        raise ValueError('At most1000ms bounded retained-handle observation')
                    before = time.monotonic(); waited = self.k.WaitForSingleObject(handle, exit_wait_ms)
                    record.update(exit_wait_ms=exit_wait_ms, exit_wait_result=int(waited),
                        exit_wait_elapsed_seconds=time.monotonic() - before)
                    if waited not in (0, 258):
                        raise ctypes.WinError(ctypes.get_last_error())
                    exited = waited == 0; record['stable_handle_exited'] = exited
                if eligible and exited:
                    record['identity_status'] = 'unverified_exited_transient'
                    return handle, record
                raise ObservationError('Image query failed; unknown process not admitted', record)
            record['image'] = normalized(buffer.value)
            return handle, record
        except BaseException:
            self.k.CloseHandle(handle)
            raise


class Tracker(PreviousTracker):
    def __init__(self, pid, outer_pid, require_job=True, venv_image=None, base_image=None,
                 launcher_handle=None, sampler=None, wait_budget=None, job_context=None, audit=None):
        if job_context is None or job_context.outer != outer_pid:
            raise ValueError('Exact retained outer immediate-job context required')
        self.os = job_context.os; self.job_context = job_context
        self.audit = audit or (lambda value: None)
        self.outer = outer_pid; self.require_job = require_job
        self.venv = venv_image or sys.executable; self.base = base_image or sys._base_executable
        self.handles = {}; self.records = {}; self.delegate = None; self.auxiliary = None
        self.console = self.os.console_image(); self.sampler = sampler
        self.query_pids = set(); self.transients = {}; self.transient_handles = {}; self.absences = {}
        self.wait_budget = wait_budget or (lambda: 1000)
        if sampler and hashlib.sha256(Path(sampler['executable']['path']).read_bytes()).hexdigest() != sampler['executable']['sha256']:
            raise ValueError('Pinned resource-query executable changed')
        parents = self.os.snapshot()
        if parents.get(pid) != outer_pid or pid not in self.job_context.members():
            raise ValueError('Live launcher ancestry/immediate-job membership not observed')
        self.audit({'kind': 'retain_attempt', 'pid': pid, 'parent_pid': outer_pid, 'role': 'launcher'})
        handle, record = self.os.retain(pid, outer_pid)
        self.handles[pid] = handle; self.records[pid] = record; self.launcher = record
        try:
            validate(outer_pid, record, record, self.venv, self.base, require_job)
            if launcher_handle is not None:
                times = [W.FILETIME() for _ in range(4)]
                if not self.os.k.GetProcessTimes(int(launcher_handle), *[ctypes.byref(value) for value in times]):
                    raise ctypes.WinError(ctypes.get_last_error())
                created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
                if created != record['created']:
                    raise ValueError('Popen stable handle creation identity differs')
        except BaseException:
            self.close()
            raise

    def check_absent_reappearance(self, parents=None):
        parents = self.os.snapshot() if parents is None else parents
        self.job_context.reject_absent_reappearance(parents, self.job_context.members())
        if set(self.absences) & (set(parents) | set(parents.values()) | self.job_context.members()):
            raise ValueError('Previously absent PID reappeared/reused or became ancestry parent')

    def observe(self):
        parents = self.os.snapshot()
        self.check_absent_reappearance(parents)
        if any(parent in self.transients for parent in parents.values()):
            raise ValueError('Unverified retained transient cannot be ancestry parent')
        ordered = sorted(parents, key=lambda pid: 0 if parents[pid] == self.launcher['pid'] else 1)
        for pid in ordered:
            parent = parents[pid]
            if parent not in self.records or pid in self.records or pid in self.transients or pid in self.absences:
                continue
            runtime = self.delegate or (self.launcher if normalized(self.venv) == normalized(self.base) else None)
            eligible = runtime is not None and parent == runtime['pid']
            self.audit({'kind': 'retain_attempt', 'pid': pid, 'parent_pid': parent,
                'known_runtime_parent': eligible,
                'snapshot_sha256': hashlib.sha256(json.dumps(sorted(parents.items())).encode()).hexdigest()})
            try:
                handle, record = self.os.retain(pid, parent, allow_exited_transient=eligible,
                    exit_wait_ms=self.wait_budget() if eligible else 0,
                    minimum_created=runtime['created'] if runtime else 0, require_job=self.require_job)
            except ObservationError as error:
                self.audit({'kind': 'retain_failed', 'observation': error.observation})
                if (not eligible or error.observation.get('stage') != 'OpenProcess'
                    or error.observation.get('open_process_winerror') != 87):
                    raise
                self.absences[pid] = self.job_context.certify_absence(error.observation, runtime,
                    self.handles[runtime['pid']], self.wait_budget)
                continue
            try:
                if record.get('identity_status') == 'unverified_exited_transient':
                    if (not eligible or (not record['in_job'] and self.require_job)
                        or record['created'] < runtime['created'] or not self.os.exited(handle)):
                        raise ValueError('Retained transient lacks parent/creation/job/EXIT proof')
                    self.transient_handles[pid] = handle; self.transients[pid] = record
                    continue
                if not self.os.exited(handle) and pid not in self.job_context.members():
                    raise ValueError('Live descendant outside immediate owned context')
                if parent == self.launcher['pid'] and record['image'] == self.console:
                    validate_console(self.launcher, record, self.console, self.require_job)
                    if self.auxiliary is not None:
                        raise ValueError('Multiple console hosts')
                    self.auxiliary = record
                elif parent == self.launcher['pid'] and record['image'] == normalized(self.base):
                    validate(self.outer, self.launcher, record, self.venv, self.base, self.require_job)
                    if self.delegate is not None:
                        raise ValueError('Multiple interpreter delegates')
                    self.delegate = record
                else:
                    runtime = self.delegate or self.launcher
                    if not self.sampler or parent != runtime['pid']:
                        raise ValueError('Unknown descendant or extra interpreter hop')
                    validate_query(runtime, record, self.sampler, self.require_job)
                    self.query_pids.add(pid)
            except BaseException:
                self.os.k.CloseHandle(handle)
                raise
            self.handles[pid] = handle; self.records[pid] = record

    def all_exited(self):
        if not super().all_exited():
            return False
        self.check_absent_reappearance()
        self.job_context.assert_baseline_only('all_retained_child_handles_exited')
        return True

    def proof(self, receipt):
        if receipt.get('pid') in self.absences:
            raise ValueError('Unretained absent entry can never be runtime')
        value = super().proof(receipt)
        value.update(unretained_absent_entries=list(self.absences.values()),
            absent_entries_have_exit_or_identity_proof=False,
            current_job_baseline=self.job_context.describe())
        return value
