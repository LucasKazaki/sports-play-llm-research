"""Retained process identities and historical unretained numbers have different lifetimes."""
import ctypes
from ctypes import wintypes as W
import time
from process_lineage_v5 import (Windows as PreviousWindows, Tracker as PreviousTracker,
    ObservationError, normalized, validate, validate_console, validate_query)
from chess_queen_process_lineage_v4 import Tracker as IdentityTracker


def same_identity(expected, observed):
    return all(type(expected.get(key)) is int and expected[key] > 0
        and type(observed.get(key)) is int and observed[key] == expected[key] for key in ('pid', 'created'))


class Windows(PreviousWindows):
    def __init__(self):
        super().__init__()
        self.k.GetProcessId.argtypes = [W.HANDLE]; self.k.GetProcessId.restype = W.DWORD

    def identity(self, handle):
        pid = int(self.k.GetProcessId(handle))
        if not pid: raise ObservationError('GetProcessId failed on retained handle',
            {'stage': 'GetProcessId', 'winerror': ctypes.get_last_error(), 'stable_handle_retained': True})
        times = [W.FILETIME() for _ in range(4)]
        if not self.k.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
            raise ObservationError('GetProcessTimes failed on retained handle',
                {'stage': 'GetProcessTimes', 'pid': pid, 'winerror': ctypes.get_last_error(), 'stable_handle_retained': True})
        return {'pid': pid, 'created': (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime}

    def retain(self, pid, parent, allow_exited_transient=False, exit_wait_ms=0,
               minimum_created=0, require_job=True, termination_rights=False):
        handle = self.k.OpenProcess(0x1000 | 0x100000 | (1 if termination_rights else 0), False, pid)
        if not handle:
            raise ObservationError('OpenProcess failed before retaining any handle',
                {'stage': 'OpenProcess', 'pid': pid, 'parent_pid': parent,
                 'open_process_winerror': ctypes.get_last_error(), 'stable_handle_retained': False})
        record = {'pid': pid, 'parent_pid': parent, 'handle_has_termination_rights': bool(termination_rights)}
        stage = 'handle_identity'
        try:
            actual = self.identity(handle)
            if actual['pid'] != pid: raise ObservationError('Actual handle PID differs', actual)
            record['created'] = actual['created']; job = W.BOOL(); stage = 'IsProcessInJob'
            if not self.k.IsProcessInJob(handle, None, ctypes.byref(job)):
                raise ctypes.WinError(ctypes.get_last_error())
            record['in_job'] = bool(job.value); stage = 'QueryFullProcessImageNameW'
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
                        raise ValueError('At most1000ms retained-handle observation')
                    before = time.monotonic(); stage = 'WaitForSingleObject'
                    waited = self.k.WaitForSingleObject(handle, exit_wait_ms)
                    record.update(exit_wait_ms=exit_wait_ms, exit_wait_result=int(waited),
                        exit_wait_elapsed_seconds=time.monotonic() - before)
                    if waited not in (0, 258): raise ctypes.WinError(ctypes.get_last_error())
                    exited = waited == 0; record['stable_handle_exited'] = exited
                if not eligible or not exited: raise ObservationError('Unknown image not admitted', record)
                record['identity_status'] = 'unverified_exited_transient'
            else: record['image'] = normalized(buffer.value)
            return handle, record
        except BaseException as error:
            witness = {**record, 'stage': stage, 'stable_handle_retained': True,
                'error': type(error).__name__ + ': ' + str(error),
                'nested_observation': getattr(error, 'observation', None)}
            witness['handle_closed_after_failure'] = bool(self.k.CloseHandle(handle))
            raise ObservationError('Retained query API failed', witness) from error


class Tracker(PreviousTracker):
    def __init__(self, *args, **kwargs):
        self.episodes = {}; self.roles = {}; self.closed_history = []; self.foreign_diagnostics = set()
        super().__init__(*args, **kwargs)
        try:
            self.check_parent(self.launcher, self.job_context.records[self.outer],
                self.job_context.handles[self.outer])
            self.register(self.launcher, 'launcher')
        except BaseException:
            self.close(); raise

    def register(self, record, role):
        self.roles[record['pid']] = role
        episode = len(self.job_context.identity_history)
        self.episodes[record['pid']] = episode
        actual = self.job_context.identity_opened(record, role)
        if actual != episode: raise RuntimeError('Identity episode order changed')

    def fail(self, message, parents, members, **details):
        witness = self.job_context.witness('observer_rejected', parents, members,
            message=message, **details)
        self.audit(witness)
        raise ObservationError(message, witness)

    def check_identity(self, record, handle):
        actual = self.os.identity(handle)
        if not same_identity(record, actual):
            raise ObservationError('Retained handle identity changed; reuse while open is invalid',
                {'expected': record, 'actual': actual, 'stable_handle_retained': True})

    def check_parent(self, child, parent, handle):
        self.check_identity(parent, handle)
        if (self.os.exited(handle) or child['parent_pid'] != parent['pid']
            or child['created'] < parent['created']):
            raise ObservationError('New child lacks live creation-bound retained parent',
                {'child': child, 'parent': parent, 'parent_handle_exited': self.os.exited(handle)})

    def check_absent_reappearance(self, parents=None):
        parents = self.os.snapshot() if parents is None else parents
        self.job_context.reject_absent_reappearance(parents, self.job_context.members())

    def observe(self):
        # Three complete refreshes are a fixed bound, not an atomic system snapshot claim.
        for attempt in range(3):
            if self.wait_budget() <= 0: raise RuntimeError('Observer clock/cancel exhausted')
            unknown, parents, members = self.observe_once()
            if not unknown: return
            self.job_context.witness('owned_members_need_refresh', parents, members,
                attempt=attempt, unknown_pids=sorted(unknown))
        self.fail('Unresolved complete owned-job members after3refreshes', parents, members,
            unknown_pids=sorted(unknown), snapshot_parents={pid: parents.get(pid) for pid in unknown})

    def observe_once(self):
        parents = self.os.snapshot(); members = self.job_context.members()
        self.check_absent_reappearance(parents)
        for pid, record in self.records.items():
            self.check_identity(record, self.handles[pid])
            if pid in parents and parents[pid] != record['parent_pid']:
                self.fail('Retained PID has contradictory snapshot parent', parents, members,
                    pid=pid, retained_identity=record, observed_parent=parents[pid])
        for pid, parent in parents.items():
            if parent in self.transients:
                self.fail('Unverified retained transient cannot supply ancestry', parents, members,
                    pid=pid, snapshot_parent_pid=parent)
        ordered = sorted(parents, key=lambda pid: 0 if parents[pid] == self.launcher['pid'] else 1)
        for pid in ordered:
            parent = parents[pid]
            # Retained handles prohibit reuse for this request. ABSENT entries do not.
            if parent not in self.records or pid in self.records or pid in self.transients:
                continue
            parent_record = self.records[parent]; parent_handle = self.handles[parent]
            if self.os.exited(parent_handle):
                if pid in members:
                    self.fail('Unresolved owned child first observed under exited parent', parents, members,
                        pid=pid, snapshot_parent_pid=parent, parent_identity=parent_record)
                continue  # Outside-job numeric parent alone grants neither ownership nor a kill right.
            runtime = self.delegate or (self.launcher if normalized(self.venv) == normalized(self.base) else None)
            eligible = runtime is not None and parent == runtime['pid']
            witness = self.job_context.witness('before_candidate_query', parents, members,
                pid=pid, snapshot_parent_pid=parent, parent_identity=parent_record,
                historical_absence_count=sum(value['pid'] == pid for value in self.job_context.absence_history),
                query_only=True, known_runtime_parent=eligible)
            self.audit(witness)
            self.check_identity(parent_record, parent_handle)
            try:
                handle, record = self.os.retain(pid, parent, allow_exited_transient=eligible,
                    exit_wait_ms=self.wait_budget() if eligible else 0,
                    minimum_created=runtime['created'] if runtime else 0,
                    require_job=self.require_job, termination_rights=False)
            except ObservationError as error:
                self.audit({'kind': 'candidate_query_failed', 'pid': pid,
                    'observation': error.observation, 'before_query': witness})
                if (not eligible or error.observation.get('stage') != 'OpenProcess'
                    or error.observation.get('open_process_winerror') != 87): raise
                self.absences[pid] = self.job_context.certify_absence(error.observation, runtime,
                    self.handles[runtime['pid']], self.wait_budget)
                continue
            except BaseException as error:
                self.fail('Candidate query API failed', parents, members, pid=pid,
                    snapshot_parent_pid=parent, api_error=type(error).__name__ + ': ' + str(error))
            transferred = False; local_close_attempted = False; local_close_succeeded = None
            try:
                self.check_identity(record, handle)
                fresh = self.os.snapshot(); active = self.job_context.members()
                # A global ParentProcessId may name an unrelated later reused parent number.
                # This branch disproves the relation; it admits no role/ancestry/kill rights.
                if record['created'] < parent_record['created'] and pid not in active and pid not in members:
                    self.check_identity(parent_record, parent_handle); self.check_identity(record, handle)
                    if (self.os.exited(parent_handle) or parent not in active or parent not in fresh
                        or fresh.get(pid, parent) != parent):
                        self.fail('Foreign older relation lacks current parent/job/identity observations',
                            fresh, active, pid=pid, retained_identity=record, parent_identity=parent_record)
                    key = (pid, record['created'], parent, parent_record['created'])
                    if key not in self.foreign_diagnostics and len(self.foreign_diagnostics) < 256:
                        self.foreign_diagnostics.add(key)
                        self.job_context.witness('creation_disproved_numeric_parent_relation', fresh, active,
                            pid=pid, actual_query_identity=record, current_parent_identity=parent_record,
                            any_job_flag_is_not_explicit_membership=True, exact_current_job_member=False,
                            parent_handle_live=True, ownership_admitted=False, ancestry_admitted=False,
                            termination_permitted=False, actual_PID_reuse_claim=False)
                    local_close_attempted = True
                    local_close_succeeded = bool(self.os.k.CloseHandle(handle))
                    if not local_close_succeeded: raise RuntimeError('Foreign query handle close failed')
                    continue
                if (pid not in members and pid not in active
                    and record.get('identity_status') != 'unverified_exited_transient'):
                    self.fail('Candidate lacks exact owned-job membership observation', fresh, active,
                        pid=pid, retained_identity=record, parent_identity=parent_record)
                self.check_parent(record, parent_record, parent_handle)
                if ((pid not in fresh and not self.os.exited(handle))
                    or fresh.get(pid, parent) != parent):
                    self.fail('Candidate snapshot parent changed during query', fresh, active,
                        pid=pid, retained_identity=record)
                if not self.os.exited(handle) and pid not in active:
                    self.fail('Live candidate outside exact current job', fresh, active, pid=pid,
                        retained_identity=record)
                if record.get('identity_status') == 'unverified_exited_transient':
                    if (not eligible or (not record['in_job'] and self.require_job)
                        or record['created'] < runtime['created'] or not self.os.exited(handle)):
                        self.fail('Unverified transient lacks job/creation/EXIT', fresh, active, pid=pid,
                            retained_identity=record)
                    self.roles[pid] = 'unverified_exited_transient'
                    self.transient_handles[pid] = handle; self.transients[pid] = record
                    transferred = True
                    self.register(record, 'unverified_exited_transient'); continue
                if parent == self.launcher['pid'] and record['image'] == self.console:
                    validate_console(self.launcher, record, self.console, self.require_job)
                    if self.auxiliary is not None: raise ValueError('Multiple console hosts')
                    self.auxiliary = record; role = 'console'
                elif parent == self.launcher['pid'] and record['image'] == normalized(self.base):
                    validate(self.outer, self.launcher, record, self.venv, self.base, self.require_job)
                    if self.delegate is not None: raise ValueError('Multiple interpreter delegates')
                    self.delegate = record; role = 'delegate'
                else:
                    runtime = self.delegate or self.launcher
                    if not self.sampler or parent != runtime['pid']:
                        raise ValueError('Unknown descendant or extra interpreter hop')
                    validate_query(runtime, record, self.sampler, self.require_job)
                    self.query_pids.add(pid); role = 'resource_query'
                self.roles[pid] = role
                self.handles[pid] = handle; self.records[pid] = record
                transferred = True
                self.register(record, role)
                self.audit({'kind': 'candidate_identity_admitted', 'role': role, 'identity': record,
                    'historical_number_has_no_identity_authority': True})
            except BaseException as error:
                if not transferred and not local_close_attempted:
                    local_close_attempted = True
                    local_close_succeeded = bool(self.os.k.CloseHandle(handle))
                self.fail('Candidate role/identity rejected', parents, members, pid=pid,
                    handle_transferred_to_owner=transferred, local_handle_close_attempted=local_close_attempted,
                    local_handle_close_succeeded=local_close_succeeded,
                    retained_identity=record, error=type(error).__name__ + ': ' + str(error),
                    nested_observation=getattr(error, 'observation', None))
        fresh = self.os.snapshot(); active = self.job_context.members()
        known = self.job_context.baseline | set(self.records) | set(self.transients)
        unknown = active - known
        return unknown, fresh, active

    def all_exited(self):
        if not IdentityTracker.all_exited(self): return False
        self.check_absent_reappearance()
        self.job_context.assert_baseline_only('all_retained_child_handles_exited')
        return True

    def proof(self, receipt):
        value = IdentityTracker.proof(self, receipt)
        value.update(unretained_absent_entries=list(self.absences.values()),
            absent_entries_have_exit_or_identity_proof=False,
            current_job_baseline=self.job_context.describe(), identity_policy_version=2)
        return value

    def terminate_owned(self):
        if not all(self.os.exited(handle) for handle in self.transient_handles.values()):
            raise RuntimeError('Unverified retained process is never a termination target')
        for pid in reversed(list(self.handles)):
            query_handle = self.handles[pid]; record = self.records[pid]
            self.check_identity(record, query_handle)
            if self.os.exited(query_handle): continue
            handle = None
            self.audit({'kind': 'termination_handle_requested', 'identity': record,
                'already_retained_query_handle': True, 'validated_role': self.roles[pid]})
            try:
                handle, actual = self.os.retain(pid, record['parent_pid'], termination_rights=True)
                if (not same_identity(record, actual) or actual['image'] != record['image']
                    or actual['in_job'] != record['in_job']):
                    raise ObservationError('Termination handle identity mismatch',
                        {'expected': record, 'actual': actual, 'termination_permitted': False})
                self.check_identity(record, query_handle)
                if not self.os.exited(handle) and not self.os.k.TerminateProcess(handle, 2):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                if handle is not None: self.os.k.CloseHandle(handle)
        deadline = time.monotonic() + 10
        while not all(self.os.exited(handle) for handle in self.handles.values()):
            if time.monotonic() >= deadline: raise RuntimeError('Owned stable handles not EXIT within10s')
            time.sleep(.02)

    def close(self):
        for mapping in (getattr(self, 'handles', {}), getattr(self, 'transient_handles', {})):
            for pid, handle in list(mapping.items()):
                exited = self.os.exited(handle)
                if not self.os.k.CloseHandle(handle):
                    raise ObservationError('Owned query handle close failed', {'pid': pid})
                mapping.pop(pid)
                if pid in self.episodes:
                    episode = self.episodes[pid]
                    if episode < len(self.job_context.identity_history):
                        self.job_context.identity_closed(episode, exited)
                    else:
                        self.audit({'kind': 'handle_closed_without_registered_episode', 'pid': pid,
                            'actual_handle_exit_observed': exited, 'handle_closed': True})
