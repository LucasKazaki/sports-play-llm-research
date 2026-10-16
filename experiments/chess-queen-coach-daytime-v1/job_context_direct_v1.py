"""Direct base process with venv getpath; parent-held owned-job proof stays parent-only."""
import hashlib
import json
import os
import sys
import time
from job_context import JobContext as Previous, normalized

PROFILE = 'direct-base-owned-worker-v2'


class JobContext(Previous):
    def __init__(self, os_api, outer_pid=None, venv_image=None, base_image=None,
                 audit=None, clock=time.monotonic, delay=time.sleep):
        self.os = os_api; self.outer = os.getpid() if outer_pid is None else outer_pid
        self.venv = normalized(venv_image or sys.executable)
        self.base = normalized(base_image or sys._base_executable)
        self.audit = audit or (lambda value: None); self.clock = clock; self.delay = delay
        self.handles = {}; self.records = {}; self.absences = {}; self.creator_handle = None
        self.creator = None
        try:
            self.audit({'kind': 'direct_context_started_before_observation', 'outer_pid': self.outer,
                'expected_base_image': self.base, 'venv_sys_executable': self.venv, 'profile': PROFILE})
            if self.venv == self.base:
                raise ValueError('Pinned venv getpath identity must differ from actual base image')
            parents = self.os.snapshot()
            self.audit({'kind': 'direct_context_system_snapshot', 'outer_pid': self.outer,
                'outer_parent_pid': parents.get(self.outer), 'complete_entry_count': len(parents),
                'snapshot_sha256': hashlib.sha256(json.dumps(sorted(parents.items())).encode()).hexdigest()})
            members = self.members()
            self.audit({'kind': 'direct_context_NULL_job_list', 'pids': sorted(members)})
            if self.outer not in parents or self.outer not in members:
                raise ValueError('Actual direct outer missing from system/current-job observations')
            handle, outer = self.os.retain(self.outer, parents[self.outer], termination_rights=False)
            self.handles[self.outer] = handle; self.records[self.outer] = outer
            self.audit({'kind': 'direct_outer_query_identity', **outer})
            if outer['image'] != self.base or not outer['in_job']:
                raise ValueError('Actual outer is not the pinned direct base interpreter in a job')
            parent = parents[self.outer]
            if type(parent) is not int or parent <= 0 or parent not in parents or parent in members:
                raise ValueError('Direct creator must be observed outside the child immediate job')
            self.audit({'kind': 'direct_creator_query_handle_attempt', 'pid': parent, 'parent_pid': parents[parent]})
            self.creator_handle, self.creator = self.os.retain(parent, parents[parent], termination_rights=False)
            self.audit({'kind': 'direct_creator_query_identity', **self.creator})
            if (self.creator['image'] != self.base or self.creator['created'] > outer['created']
                or outer['parent_pid'] != self.creator['pid']):
                raise ValueError('Direct creator base-image/creation/parent differs')
            remaining = members-{self.outer}
            if len(remaining) > 1: raise ValueError('Unexpected direct-context active members')
            for pid in remaining:
                if parents.get(pid) != self.outer: raise ValueError('Unexpected direct-context descendant')
                handle, record = self.os.retain(pid, self.outer, termination_rights=False)
                self.handles[pid] = handle; self.records[pid] = record
                self.audit({'kind': 'direct_console_query_identity', **record})
                if (record['image'] != self.os.console_image() or not record['in_job']
                    or record['created'] < outer['created']):
                    raise ValueError('Only actually observed canonical direct-outer console allowed')
            self.baseline = set(self.records)
            self.assert_baseline_only('direct_context_initialized')
            self.audit({'kind': 'direct_context_retained', **self.describe()})
        except BaseException:
            self.close(); raise

    def describe(self):
        return {**super().describe(), 'launch_profile': PROFILE, 'creator_query_identity': self.creator,
            'creator_handle_has_termination_rights': False,
            'creator_job_identity': 'Child queries only its immediate NULL job. Actual creator-owned explicit-handle membership is separately enforced/recorded by the pinned parent worker beforeGO; no child-held job handle.'}

    def assert_baseline_only(self, stage):
        members = self.members(); parents = self.os.snapshot()
        self.reject_absent_reappearance(parents, members)
        if members != self.baseline: raise ValueError('Immediate job has active members outside direct baseline')
        for pid, record in self.records.items():
            if self.os.exited(self.handles[pid]) or parents.get(pid) != record['parent_pid']:
                raise ValueError('Direct baseline handle exited or ancestry changed')
        if (self.creator is None or self.os.exited(self.creator_handle)
            or self.creator['pid'] in members or parents.get(self.outer) != self.creator['pid']):
            raise ValueError('Retained direct creator exited/changed or entered child immediate job')
        value = {'kind': 'job_baseline_only', 'stage': stage, 'active_pids': sorted(members),
            'baseline_handles_live': True, 'creator_handle_live': True, 'launch_profile': PROFILE,
            'at_monotonic': self.clock()}
        self.audit(value); return value

    def close(self):
        super().close()
        if self.creator_handle is not None:
            self.os.k.CloseHandle(self.creator_handle); self.creator_handle = None
