"""Read-only immediate-job context and narrowly measured snapshot absence."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def normalized(path):
    return os.path.normcase(os.path.abspath(path))


def evidence_snapshot(parents, target):
    return {'complete': True, 'entry_count': len(parents), 'target_present': target in parents,
        'parent_of_target': parents.get(target),
        'sha256': hashlib.sha256(json.dumps(sorted(parents.items())).encode()).hexdigest()}


class JobContext:
    """No job/process assignment or termination; baseline handles are query-only."""
    def __init__(self, os_api, outer_pid=None, venv_image=None, base_image=None,
                 audit=None, clock=time.monotonic, delay=time.sleep):
        self.os = os_api
        self.outer = os.getpid() if outer_pid is None else outer_pid
        self.venv = normalized(venv_image or sys.executable)
        self.base = normalized(base_image or sys._base_executable)
        self.audit = audit or (lambda value: None)
        self.clock = clock
        self.delay = delay
        self.handles = {}
        self.records = {}
        self.absences = {}  # Phase-wide: a new child must not forget earlier absent IDs.
        try:
            parents = self.os.snapshot()
            members = self.members()
            if self.outer not in parents or self.outer not in members:
                raise ValueError('Outer missing from complete system/job observations')
            handle, outer = self.os.retain(self.outer, parents[self.outer], termination_rights=False)
            self.handles[self.outer] = handle
            self.records[self.outer] = outer
            if outer['image'] != self.base or not outer['in_job']:
                raise ValueError('Actual outer base interpreter/job differs')
            launcher = outer
            if self.venv != self.base:
                parent = parents[self.outer]
                if parent not in members or parent not in parents:
                    raise ValueError('Exact outer venv ancestor not in immediate current job')
                handle, launcher = self.os.retain(parent, parents[parent], termination_rights=False)
                self.handles[parent] = handle
                self.records[parent] = launcher
                if (launcher['image'] != self.venv or not launcher['in_job']
                    or outer['parent_pid'] != launcher['pid'] or launcher['created'] > outer['created']):
                    raise ValueError('Outer ancestry image/creation/parent differs')
            remaining = members - set(self.records)
            if len(remaining) > 1:
                raise ValueError('Unexpected immediate-job baseline members')
            for pid in remaining:
                if parents.get(pid) != launcher['pid']:
                    raise ValueError('Unexpected outer-context ancestor/descendant')
                handle, record = self.os.retain(pid, parents[pid], termination_rights=False)
                self.handles[pid] = handle
                self.records[pid] = record
                if (record['image'] != self.os.console_image() or not record['in_job']
                    or record['created'] < launcher['created']):
                    raise ValueError('Only observed canonical launcher console belongs in baseline')
            self.baseline = set(self.records)
            self.assert_baseline_only('context_initialized')
            self.audit({'kind': 'outer_context_retained', **self.describe()})
        except BaseException:
            self.close()
            raise

    def members(self):
        values = self.os.current_job_pids()
        if (not isinstance(values, (list, tuple, set)) or any(type(pid) is not int or pid <= 0 for pid in values)
            or len(values) != len(set(values))):
            raise ValueError('Complete unique positive current-job PID list required')
        return set(values)

    def describe(self):
        return {'scope': 'QueryInformationJobObject(NULL): immediate current job, including nested children; no named-job identity claim',
            'outer_pid': self.outer, 'baseline': list(self.records.values()),
            'baseline_query_handles_live': all(not self.os.exited(h) for h in self.handles.values()),
            'baseline_handles_have_termination_rights': False,
            'unretained_absent_entries': list(self.absences.values())}

    def reject_absent_reappearance(self, parents, members):
        if set(self.absences) & (set(parents) | set(parents.values()) | set(members)):
            raise ValueError('Previously absent PID reappeared/reused or became ancestry parent')

    def assert_baseline_only(self, stage):
        members = self.members()
        parents = self.os.snapshot()
        self.reject_absent_reappearance(parents, members)
        if members != self.baseline:
            raise ValueError('Immediate job has active members outside stable outer baseline: ' + repr(sorted(members - self.baseline)))
        for pid, record in self.records.items():
            if self.os.exited(self.handles[pid]) or parents.get(pid) != record['parent_pid']:
                raise ValueError('Outer baseline handle exited or ancestry changed')
        value = {'kind': 'job_baseline_only', 'stage': stage, 'active_pids': sorted(members),
            'baseline_handles_live': True, 'at_monotonic': self.clock()}
        self.audit(value)
        return value

    def certify_absence(self, observation, parent, parent_handle, wait_budget):
        """Absence is never process EXIT, identity, ancestry or kill authority."""
        pid = observation.get('pid')
        if (type(pid) is not int or pid <= 0 or observation.get('stage') != 'OpenProcess'
            or observation.get('open_process_winerror') != 87
            or observation.get('parent_pid') != parent['pid']):
            raise ValueError('Only exact positive-PID OpenProcess87 under known runtime is eligible')
        maximum_ms = wait_budget()
        if type(maximum_ms) is not int or not 10 <= maximum_ms <= 1000:
            raise RuntimeError('No bounded observation budget remains')
        started = self.clock()
        self.audit({'kind': 'absence_measurement_started', 'observation': observation,
            'runtime_parent': parent, 'maximum_observation_ms': maximum_ms})
        readings = []
        for index in range(2):
            if index:
                self.delay(.01)
            if wait_budget() <= 0 or (self.clock() - started) * 1000 >= maximum_ms:
                raise RuntimeError('Owned absence observation expired/cancelled')
            if self.os.exited(parent_handle):
                raise ValueError('Known runtime parent no longer live')
            parents = self.os.snapshot()
            members = self.members()
            self.reject_absent_reappearance(parents, members)
            if (pid in parents or pid in members or pid in parents.values()
                or parent['pid'] not in members or parent['pid'] not in parents
                or self.os.exited(parent_handle)):
                raise ValueError('PID present/reused/parent-role or known parent ambiguous')
            reading = {'at_monotonic': self.clock(), 'system': evidence_snapshot(parents, pid),
                'current_job_pids': sorted(members), 'target_in_job': False,
                'known_runtime_parent_live': True, 'known_runtime_parent_in_job': True}
            readings.append(reading)
            self.audit({'kind': 'fresh_absence_observation', 'pid': pid, 'index': index, **reading})
        if wait_budget() <= 0 or (self.clock() - started) * 1000 >= maximum_ms:
            raise RuntimeError('Owned absence observation expired before classification')
        value = {'pid': pid, 'snapshot_parent_pid': parent['pid'], 'open_process_winerror': 87,
            'identity_status': 'unretained_snapshot_entry_absent', 'observations': readings,
            'runtime_parent': parent, 'stable_handle_retained': False, 'identity_verified': False,
            'exit_proved': False, 'termination_permitted': False,
            'maximum_observation_ms': maximum_ms, 'elapsed_seconds': self.clock() - started}
        self.audit({'kind': 'snapshot_entry_classified_absent', **value})
        self.absences[pid] = value
        return value

    def close(self):
        for handle in self.handles.values():
            self.os.k.CloseHandle(handle)
        self.handles.clear()
