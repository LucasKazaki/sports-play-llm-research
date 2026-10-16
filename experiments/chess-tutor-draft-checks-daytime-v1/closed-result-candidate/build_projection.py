"""Positive metadata projection only. No runtime calls or private payload copy.

Run once after root's closed helper. This builder reads only selected metadata
records semantically; raw input/response/export payloads are read for hashing
only, never decoded here. Public projection and helper review remain pending.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CHAT = Path('C:/Users/lucas/Documents/Codex/2026-10-16/first-i-want-you-to-look')
OUT = Path(__file__).resolve().parent
WORK = CHAT / 'work/daytime/tutor-draft-checks-integration-v1'
EVIDENCE = REPO / 'data/private/chess-tutor-draft-checks-daytime-v1/attempt-1'
JOB = REPO / 'data/private/chess-tutor-v1/coaching/9431d3a155a146c0851dcaa2be10e80b'
PLAN = OUT.parent / 'protocol.json'
PLAN_SHA = '459bcbf0ec8902535e8304fd8a3ea4c99be109b3baca8389c754d5d433875263'
HELPER_SHA = 'a878f1c936652f6c14af0e8bb2ba663f8f9448b028119f06ff1060e2e3edb786'
ACTUAL_AUDIT = CHAT / 'work/queen-review/daytime-tutor-draft-checks-integration-closed-review-v2.json'
ACTUAL_AUDIT_SHA = 'fa1157f7b56cf41d3489561df3fb3ec2589febb56150c799d944d82ddc77f0c9'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    if path.is_relative_to(REPO):
        location = 'repo:' + path.relative_to(REPO).as_posix()
    elif path.is_relative_to(CHAT):
        location = 'task:' + path.relative_to(CHAT).as_posix()
    else:
        raise ValueError('Unlisted source location')
    return {'location': location, 'bytes': len(raw), 'sha256': digest(raw)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def checked(row):
    actual = binding(row['path'])
    assert actual['sha256'] == row['sha256']
    if 'bytes' in row:
        assert actual['bytes'] == row['bytes']
    return actual


assert binding(PLAN)['sha256'] == PLAN_SHA
plan = read(PLAN)
ready = read(plan['frozen_readiness']['path'])
assert binding(plan['frozen_readiness']['path'])['sha256'] == plan['frozen_readiness']['sha256']
helper_path = WORK / 'closed-verification-1.json'
assert binding(helper_path)['sha256'] == HELPER_SHA
helper = read(helper_path)
assert helper['status'] == 'artifact_checks_passed_root_observations_bound'
assert helper['protocol_sha256'] == PLAN_SHA
closure = read(EVIDENCE / 'closure.json')
worker = read(JOB / 'worker.json')
verification = read(JOB / 'draft-checks-v1.json')
admission = read(EVIDENCE / 'admission.json')
after = read(EVIDENCE / 'source-and-process-after.json')
assert binding(ACTUAL_AUDIT)['sha256'] == ACTUAL_AUDIT_SHA
actual_audit = read(ACTUAL_AUDIT)
assert actual_audit['status'] == 'passed' and actual_audit['protocol_sha256'] == PLAN_SHA
actual_manifest_entry_count = len(read(EVIDENCE / 'artifact-manifest.json')['files'])
assert actual_manifest_entry_count == 21

assert closure['planned'] == closure['completed'] == closure['actual_ui_submissions'] == 1
assert all(closure[key] == 0 for key in ('partial', 'failed', 'active_unknown', 'not_run'))
assert closure['actual_worker_launches'] == closure['confirmed_generation_requests'] == 1
assert closure['generated_tokens'] == helper['observed_raw_metadata']['generated_token_count'] == 527
assert worker['status'] == 'completed' and worker['exit_code'] == 0
assert worker['child_exited_before_lease_release'] is True
assert round(worker['elapsed_seconds'], 3) == 69.906
assert helper['limited_checks']['status'] == verification['status'] == 'unassessed'
assert helper['limited_checks']['matched_statement_count'] == len(verification['claims']) == 0
assert helper['limited_checks']['span_hashes_checked'] == 2
assert verification['whole_prose_assessed'] is False
assert verification['context']['selected_uci'] is None
assert closure['formal_quality_promotion'] is False
assert admission['admitted'] is True and len(admission['fixed_resource_samples']) == 2
assert after['source_changes'] is False and after['in_memory_byte_attestation'] is False

source_rows = [*ready['exact_current_sources'], *ready['verified_unchanged_boundary_files']]
source_pins = [checked(row) for row in source_rows]
runtime_pins = [{'role': row['role'], **checked(row)}
                for row in ready['qualified_runtime_bindings_rehashed_metadata_only']]
private_bindings = [checked(row) for row in helper['artifacts']]
extra_paths = [helper_path, WORK / 'verify_closed.py', EVIDENCE / 'closure.json',
    EVIDENCE / 'admission.json', EVIDENCE / 'intent.json', EVIDENCE / 'dispatch-link.json',
    EVIDENCE / 'before-ui-artifacts.json', EVIDENCE / 'source-and-process-after.json',
    EVIDENCE / 'artifact-manifest.json', JOB / 'worker.log', JOB / 'controller.log']
private_bindings.extend(binding(path) for path in extra_paths)
by_location = {row['location']: row for row in private_bindings}
private_bindings = list(by_location.values())

result = {
    'schema': 'chess.tutor-draft-checks-daytime.public-result-candidate.v1',
    'status': 'candidate_pending_independent_public_projection_and_helper_review',
    'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'One authored original-manual UI integration. Engineering metadata only; no model-quality or whole-prose conclusion.',
    'projection_builder': binding(__file__),
    'prospective_protocol': binding(PLAN),
    'source_readiness': binding(plan['frozen_readiness']['path']),
    'existing_service_provenance': binding(plan['existing_service']['path']),
    'original_runtime_qualification': binding(ready['original_manual_qualification']['path']),
    'prior_source_review': binding(plan['source_review']['path']),
    'independent_prospective_plan_review': binding(CHAT / 'work/queen-review/daytime-tutor-draft-checks-integration-plan-review.json'),
    'root_closed_helper': binding(helper_path),
    'independent_actual_UI_closed_audit': {'status': 'passed', 'report': binding(ACTUAL_AUDIT),
        'scope': 'Actual original-manual UI integration evidence; excludes separate pending helper-source/result and public-projection reviews.'},
    'actual_private_artifact_manifest_entry_count': actual_manifest_entry_count,
    'actual_accounting': {
        'planned': 1, 'completed': 1, 'partial': 0, 'failed': 0, 'active_unknown': 0, 'not_run': 0,
        'actual_UI_submissions': closure['actual_ui_submissions'],
        'actual_worker_launches': closure['actual_worker_launches'],
        'confirmed_generation_requests': closure['confirmed_generation_requests'],
        'completion_status': helper['observed_raw_metadata']['status'],
        'finish_reason': helper['observed_raw_metadata']['finish_reason'],
        'generated_token_count': helper['observed_raw_metadata']['generated_token_count'],
        'worker_elapsed_seconds_rounded_3dp': round(worker['elapsed_seconds'], 3),
        'worker_exit_code': worker['exit_code'],
        'child_exited_before_lease_release': worker['child_exited_before_lease_release'],
        'root_observed_child_absent': closure['owned_child_absent'],
        'root_observed_shared_lease_free': closure['shared_lease_free'],
        'selected_move_supplied': False,
        'source': 'Already-spent authored board; no fresh held or reserve input.',
    },
    'input_identities': {
        'saved_input_file_bytes': 72,
        'saved_input_file_sha256': verification['input_sha256'],
        'normalized_packet_bytes': 60,
        'raw_response_normalized_packet_sha256': plan['prospective_input_identity_contract']['expected_raw_response_input_sha256'],
        'meanings': 'The saved-file digest binds exact controller bytes. The raw response field retains its frozen sorted-compact normalized-packet meaning. These are distinct identities.',
        'prospective_templates_and_actual_byte_comparison': 'The closed helper passed the direct comparison; no reconstructed old expected hash or old failure repair.',
    },
    'retained_response_bindings': {
        'response_file_sha256': verification['response_sha256'],
        'raw_text_utf8_sha256': verification['raw_text_sha256'],
        'verifier_sha256': verification['verifier_sha256'],
        'native_parser_sha256': verification['parser_sha256'],
    },
    'limited_checker_result': {
        'status': 'unassessed', 'matched_statement_count': 0, 'hashed_text_spans_checked': 2,
        'supported_matched_statements': 0, 'contradicted_matched_statements': 0,
        'whole_prose_assessed': False,
        'meaning': 'No statements matched the narrow canonical grammar. Two text-span hashes were checked; they are not two accepted factual claims. Other prose remains unassessed.',
        'generator_repairs': verification['generator_repairs'], 'checker_engine_calls': verification['engine_calls'],
    },
    'actual_runtime_metadata': dict(helper['observed_raw_metadata']),
    'engineering_evidence': {
        'closed_helper_status': helper['status'],
        'reviewed_source_and_runtime_bindings_rehashed': helper['source_and_runtime_metadata_bindings_rehashed'],
        'qualification_bindings_hashed_without_semantic_reads': helper['qualification_file_bindings_rehashed_without_semantic_reads'],
        'current_export_retained_original_job_and_raw_fields': True,
        'stale_export_excluded_coaching': True,
        'restored_export_matched_current_export_bytes': next(row['sha256'] for row in private_bindings if row['location'].endswith('/current-evidence.json'))
            == next(row['sha256'] for row in private_bindings if row['location'].endswith('/restored-evidence.json')),
        'original_artifact_bytes_unchanged_after_UI': True,
        'return_used_retained_position_root_observation': closure['return_used_retained_position'],
        'no_new_coaching_request_on_return_root_observation': closure['no_new_coaching_request_on_return'],
        'in_memory_byte_attestation': False,
        'loaded_source_limit': 'Original-start provenance plus unchanged reviewed disk source and actual captured-input/checker behavior. Disk hashes alone do not attest in-memory Python bytecode.',
        'browser_label_difference': 'Plan prose said Return to this position; the actual control said Return to that position. A label wait timed out without a click, then the observed control was clicked once. No second coaching request.',
    },
    'resources_and_window': {
        'startup_GiB_physical_commit_GPU': [6, 10, 10],
        'running_GiB_physical_commit_GPU': [4, 4, 1],
        'admission_observed_at_utc': admission['observed_at_utc'],
        'root_recorded_startup_sample_count': len(admission['fixed_resource_samples']),
        'root_recorded_samples_spaced_at_least_one_second': admission['samples_spaced_at_least_one_second'],
        'root_recorded_admitted': admission['admitted'],
        'closure_observed_at_utc': closure['observed_at_utc'],
        'last_admission_utc': plan['operation_window']['last_admission_utc'],
        'close_by_utc': plan['operation_window']['close_and_owned_cleanup_by_utc'],
        'user_work_cutoff_utc': plan['operation_window']['user_cutoff_utc'],
        'no_retry_or_floor_change': True,
    },
    'governance': {
        'independent_actual_UI_closed_review': 'Passed in the exact corrected v2 report bound above; 21 manifest entries plus the separately hashed manifest are 22 files. The older wording draft is preserved.',
        'independent_helper_source_result_and_public_projection_review': 'Pending when this candidate was sealed. Root helper PASS is separately attributed and not part of the initial runtime source GO.',
        'root_OS_and_UI_observations': 'Bound observations; the pure helper did not operate or independently measure processes, locks or browser actions.',
        'human_chess_expert_validation': False, 'formal_coaching_quality_claim': False,
        'whole_prose_quality_claim': False, 'trained_profile_admission': False,
        'trained_profile_remains_unavailable': True,
        'older_failed_or_unadmitted_attempts_preserved': True,
        'publication_scope': 'Hashes and aggregate engineering metadata only. No response prose, token IDs, positions, public job objects, export payloads, screenshots, references or private file contents copied.',
    },
    'source_pins': source_pins,
    'runtime_source_and_metadata_pins': runtime_pins,
    'private_evidence_hashes_only': private_bindings,
}
assert result['input_identities']['saved_input_file_sha256'] == '07124a60c3dc4aaab070ae6250b143e4a93ca4f09b3afea7e02a5d755ab4e2d7'
assert result['input_identities']['raw_response_normalized_packet_sha256'] == '5284f66597ca7599b3292f1f404aaf979f86c917b7ef292cb10b2e004f9bae4e'
write(OUT / 'result-candidate.json', result)

public_files = [Path(__file__).resolve(), OUT / 'README.md', OUT / 'result-candidate.json']
manifest = {'schema': 'chess.metadata-projection-manifest.v1',
    'scope': 'New metadata projection only; zero private payload copies.',
    'files': [binding(path) for path in public_files],
    'private_payload_files_copied': 0, 'actual_model_engine_GPU_HTTP_browser_process_calls': 0,
    'projection_source_records': ['closed helper metadata', 'worker metadata', 'root closure/admission/source metadata',
        'verification hashes/status/counts only', 'reviewed source/qualification metadata'],
    'raw_input_response_export_semantic_reads': 0,
    'pending_independent_helper_and_public_projection_review': True}
write(OUT / 'evidence-manifest.json', manifest)
print(json.dumps({'result': binding(OUT / 'result-candidate.json'), 'manifest': binding(OUT / 'evidence-manifest.json')}, indent=2))
