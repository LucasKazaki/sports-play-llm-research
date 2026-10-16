"""Direct-owned context: absence episodes never become numeric identity tombstones."""
import hashlib
import json
from job_context_direct_v1 import JobContext as Previous
from process_lineage_v5 import ObservationError

IDENTITY_POLICY = {'version': 2, 'absence_is_historical': True,
    'retained_handle_blocks_pid_reuse': True, 'query_before_termination_rights': True,
    'unknown_owned_member_fails': True, 'unrelated_numeric_occurrence_is_not_identity': True,
    'maximum_numeric_diagnostic_events': 256, 'owned_snapshot_refresh_limit': 3}


class JobContext(Previous):
    def __init__(self, *args, **kwargs):
        self.absence_history = []; self.identity_history = []; self.numeric_occurrences = set()
        self.suppressed_numeric_observations = 0
        super().__init__(*args, **kwargs)

    def witness(self, stage, parents, members, **details):
        value = {'kind': 'identity_observation', 'stage': stage,
            'complete_system_entries': len(parents),
            'snapshot_sha256': hashlib.sha256(json.dumps(sorted(parents.items())).encode()).hexdigest(),
            'current_job_pids': sorted(members), **details}
        self.audit(value)
        return value

    def reject_absent_reappearance(self, parents, members):
        """Historical method name retained for inherited calls; numeric events are not identity."""
        for pid in sorted(set(self.absences) & (set(parents) | set(parents.values()) | set(members))):
            roles = tuple(name for name, present in [('system_key', pid in parents),
                ('parent_number', pid in parents.values()), ('job_number', pid in members)] if present)
            if (pid, roles) not in self.numeric_occurrences:
                if len(self.numeric_occurrences) >= IDENTITY_POLICY['maximum_numeric_diagnostic_events']:
                    self.suppressed_numeric_observations += 1
                    if self.suppressed_numeric_observations == 1:
                        self.audit({'kind': 'numeric_diagnostic_cap_reached', 'maximum': 256,
                            'owned_candidate_and_failure_witnesses_remain_uncapped': True})
                    continue
                self.numeric_occurrences.add((pid, roles))
                self.witness('historical_absence_numeric_occurrence', parents, members,
                    pid=pid, numeric_roles=roles, identity_verified=False, exit_proved=False,
                    termination_permitted=False, classification='numeric_occurrence_only')

    def certify_absence(self, observation, parent, parent_handle, wait_budget):
        # The same exact87/two fresh observations/10ms/<=1000ms policy remains in Previous.
        # Its legacy calls now record numeric occurrences rather than globally reject history.
        value = super().certify_absence(observation, parent, parent_handle, wait_budget)
        value = {**value, 'episode_id': len(self.absence_history),
            'known_parent_identity': {'pid': parent['pid'], 'created': parent['created']}}
        self.absence_history.append(value); self.absences[value['pid']] = value
        self.audit({'kind': 'historical_absence_episode_saved', **value})
        return value

    def identity_opened(self, record, role):
        episode = {'episode_id': len(self.identity_history), 'identity': dict(record),
            'role': role, 'handle_closed': False, 'exit_proved': False}
        self.identity_history.append(episode)
        self.audit({'kind': 'identity_episode_opened', **episode})
        return episode['episode_id']

    def identity_closed(self, episode_id, exited):
        episode = self.identity_history[episode_id]
        episode.update(handle_closed=True, exit_proved=bool(exited))
        self.audit({'kind': 'identity_episode_closed', **episode})

    def assert_baseline_only(self, stage):
        # Exactly these sequential observations decide this check; no hidden resampling.
        members = self.members(); parents = self.os.snapshot(); identities = {}
        witness = self.witness('before_baseline_check', parents, members, requested_stage=stage,
            baseline_snapshot_parents={pid: parents.get(pid) for pid in self.records},
            actual_outer_parent=parents.get(self.outer), atomic_snapshot_claim=False)
        try:
            self.reject_absent_reappearance(parents, members)
            for pid, record in self.records.items():
                identities[str(pid)] = {**self.os.identity(self.handles[pid]),
                    'handle_live': not self.os.exited(self.handles[pid])}
            if self.creator is not None:
                identities['creator'] = {**self.os.identity(self.creator_handle),
                    'handle_live': not self.os.exited(self.creator_handle)}
            witness = self.witness('baseline_decision_observation', parents, members,
                requested_stage=stage, actual_handle_observations=identities,
                baseline_snapshot_parents={pid: parents.get(pid) for pid in self.records},
                actual_outer_parent=parents.get(self.outer), atomic_snapshot_claim=False)
            if members != self.baseline:
                raise ValueError('Immediate job has active members outside direct baseline')
            for pid, record in self.records.items():
                actual = identities[str(pid)]
                if (not actual['handle_live'] or actual['pid'] != record['pid']
                    or actual['created'] != record['created'] or parents.get(pid) != record['parent_pid']):
                    raise ValueError('Direct baseline identity/handle/parent differs')
            creator = identities.get('creator', {})
            if (self.creator is None or not creator.get('handle_live')
                or creator.get('pid') != self.creator['pid'] or creator.get('created') != self.creator['created']
                or self.creator['pid'] in members or parents.get(self.outer) != self.creator['pid']):
                raise ValueError('Retained direct creator identity/parent/job differs')
            value = {'kind': 'job_baseline_only', 'stage': stage, 'active_pids': sorted(members),
                'baseline_handles_live': True, 'creator_handle_live': True,
                'launch_profile': 'direct-base-owned-worker-v2', 'at_monotonic': self.clock(),
                'decision_observation': witness}
            self.audit(value); return value
        except BaseException as error:
            observation = self.witness('baseline_check_failed', parents, members,
                requested_stage=stage, actual_handle_observations=identities,
                actual_outer_parent=parents.get(self.outer),
                baseline_snapshot_parents={pid: parents.get(pid) for pid in self.records},
                decision_observation=witness, error=type(error).__name__ + ': ' + str(error))
            raise ObservationError('Direct baseline/creator proof failed', observation) from error

    def describe(self):
        return {**super().describe(), 'identity_policy': IDENTITY_POLICY,
            'absence_history': list(self.absence_history),
            'retained_identity_history': list(self.identity_history),
            'suppressed_numeric_observations_not_distinct_processes': self.suppressed_numeric_observations,
            'historical_absence_entries_are_not_identity_or_exit': True}
