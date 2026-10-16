"""Read-only, bounded artifact checks for the one admitted authored UI request.

No model, engine, HTTP, browser, process or resource APIs. The only source
executed is the separately reviewed pure draft checker, after exact hash checks.
OS/UI observations remain attributed root observations, not helper measurements.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO = Path('C:/Users/lucas/Documents/Codex/2026-10-15/go/work/repos/sports-play-llm-research')
PLAN = REPO / 'experiments/chess-tutor-draft-checks-daytime-v1/protocol.json'
PLAN_SHA = '459bcbf0ec8902535e8304fd8a3ea4c99be109b3baca8389c754d5d433875263'
REQUEST_ID = '9431d3a155a146c0851dcaa2be10e80b'
MAX_BYTES = 8 * 1024 * 1024


class CheckFailure(ValueError):
    pass


def need(condition, label):
    if not condition:
        raise CheckFailure(label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bytes_at(path):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    need(0 < len(raw) <= MAX_BYTES, 'bounded_nonempty_file')
    return raw


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def nonfinite(_):
        raise CheckFailure('nonfinite_json_value')
    result = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=nonfinite)
    need(type(result) is dict, 'json_object_required')
    return result


def read(path):
    return parse(bytes_at(path))


def binding(path):
    raw = bytes_at(path)
    return {'path': str(Path(path).resolve()), 'bytes': len(raw), 'sha256': digest(raw)}


def check_binding(row):
    actual = binding(row['path'])
    need(actual['sha256'] == row['sha256'], 'bound_file_hash')
    if 'bytes' in row:
        need(actual['bytes'] == row['bytes'], 'bound_file_length')
    return actual


def same_job(left, right):
    """Polling elapsed time is the sole permitted public-job difference."""
    return ({key: value for key, value in left.items() if key != 'elapsed_seconds'}
            == {key: value for key, value in right.items() if key != 'elapsed_seconds'})


def all_spans(value, text):
    count = 0
    if type(value) is dict:
        if {'start', 'end', 'unit', 'sha256'} <= value.keys():
            start, end = value['start'], value['end']
            need(value['unit'] == 'unicode_code_points', 'span_unit')
            need(type(start) is int and type(end) is int and 0 <= start <= end <= len(text), 'span_bounds')
            need(digest(text[start:end].encode('utf-8')) == value['sha256'], 'span_hash')
            count += 1
        for item in value.values():
            count += all_spans(item, text)
    elif type(value) is list:
        for item in value:
            count += all_spans(item, text)
    return count


def verify(evidence, closure_path):
    plan_raw = bytes_at(PLAN)
    need(digest(plan_raw) == PLAN_SHA, 'frozen_protocol_hash')
    plan = parse(plan_raw)
    ready = read(check_binding(plan['frozen_readiness'])['path'])
    source_rows = [*ready['exact_current_sources'], *ready['verified_unchanged_boundary_files'],
                   ready['original_manual_qualification'],
                   *ready['qualified_runtime_bindings_rehashed_metadata_only']]
    source_bindings = [check_binding(row) for row in source_rows]
    for key in ('source_review', 'seven_path_manifest', 'existing_service', 'restart_rejection'):
        check_binding(plan[key])
    qualification = read(ready['original_manual_qualification']['path'])
    q = qualification['bindings']
    # Exact hash reads only: do not parse historical authored prose or any held data.
    qualification_hashes = [check_binding({'path': str(REPO / row['path']), 'sha256': row['sha256']})
                            for row in q.values()]
    need(qualification['status'] == 'approved_for_authored_ui', 'original_manual_qualification_status')

    folder = Path(plan['actual_artifacts']['controller_folder_template'].replace('{request_id}', REQUEST_ID))
    paths = {name: folder / filename for name, filename in {
        'input': 'input.json', 'response': 'response.json', 'worker': 'worker.json',
        'verification': 'draft-checks-v1.json'}.items()}
    raw_bytes = {name: bytes_at(path) for name, path in paths.items()}
    objects = {name: parse(raw) for name, raw in raw_bytes.items()}
    packet, raw, worker, checks = (objects[name] for name in ('input', 'response', 'worker', 'verification'))
    input_template = bytes_at(check_binding(plan['request']['controller_input_bytes'])['path'])
    canonical_template = bytes_at(check_binding(plan['request']['generator_canonical_packet'])['path'])
    need(raw_bytes['input'] == input_template, 'direct_input_file_byte_comparison')
    need(packet == plan['request']['packet'], 'original_packet_exact')
    canonical = json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()
    need(canonical == canonical_template, 'prospective_canonical_packet')
    need(raw['input'] == packet, 'raw_input_exact')
    need(raw['input_sha256'] == digest(canonical), 'raw_canonical_hash_semantics')
    need(digest(raw_bytes['input']) != raw['input_sha256'], 'file_and_canonical_hashes_remain_distinct')
    need(raw['status'] == 'completed' and raw['finish_reason'] == 'eos', 'complete_EOS_response')
    need(type(raw.get('generated_tokens')) is list and len(raw['generated_tokens']) > 0, 'actual_generation_token_record')

    arguments = [value.replace('{request_id}', REQUEST_ID)
                 for value in plan['frozen_launch']['child_arguments_template']]
    need(digest(json.dumps(plan['frozen_launch']['child_arguments_template']).encode())
         == plan['frozen_launch']['template_sha256_default_json_list'], 'frozen_argument_template_hash')
    need(worker['arguments_sha256'] == digest(json.dumps(arguments).encode()), 'expanded_worker_arguments_hash')
    need(worker['schema'] == 'chess.gpu-worker.v1' and worker['status'] == 'completed'
         and worker['exit_code'] == 0 and worker['child_exited_before_lease_release'] is True,
         'closed_successful_worker')
    need(type(worker['child_pid']) is int and worker['child_pid'] > 0, 'owned_child_identity')
    need(Path(worker['script']).as_posix() == Path(q['adapter']['path']).as_posix(), 'worker_script_identity')
    need(Path(worker['lock']).resolve() == (REPO / 'data/private/chess-gpu-owner.lock').resolve(), 'shared_lease_identity')

    need(raw['candidate_id'] == plan['request']['candidate_id'], 'original_candidate_identity')
    provenance = {
        'adapter_sha256': 'adapter', 'base_adapter_sha256': 'base_adapter',
        'nf4_protocol_sha256': 'kernel_protocol', 'diagnostic_receipt_sha256': 'kernel_receipt',
        'asset_manifest_sha256': 'asset_manifest', 'source_manifest_sha256': 'source_manifest'}
    for name, role in provenance.items():
        need(raw[name] == q[role]['sha256'], 'raw_source_and_protocol_provenance')
    for key in ('max_new_tokens', 'maximum_seconds', 'temperature', 'seed',
                'generation_mode', 'precision_profile', 'use_kv_cache'):
        need(raw['settings'][key] == plan['fixed_generation'][key], 'frozen_generation_setting')
    for key in ('start_physical_available_bytes', 'start_commit_headroom_bytes', 'start_gpu_free_bytes',
                'stop_physical_available_bytes', 'stop_commit_headroom_bytes', 'stop_gpu_free_bytes'):
        need(raw['resource_policy'][key] == plan['resources'][key], 'frozen_resource_floor')
    input_audit = raw['no_forward_input_audit']
    need(input_audit['passed'] is True and input_audit['engine_evaluation_or_pv_input'] is False
         and input_audit['selected_move_supplied'] is False, 'no_forward_input_audit')
    need(raw['quantization']['status'] == 'loaded_and_verified'
         and raw['quantization']['actual_decoder_inventory']['linear4bit_count'] == 252,
         'qualified_NF4_inventory')

    public_path = evidence / 'terminal-public-job.json'
    public = read(public_path)
    need(public['request_id'] == REQUEST_ID and public['status'] == 'completed'
         and public['fixture'] is False, 'actual_original_public_job')
    context = public['context']
    need(context['position'] == read(plan['request']['browser_request']['path'])['position']
         and context['fen'] == packet['fen'] and context['kind'] == 'position'
         and context['selected_uci'] is None, 'actual_public_context')
    result = public['result']
    need(all(key in result and result[key] == value for key, value in raw.items()), 'all_raw_result_fields_preserved')
    need(set(result) - set(raw) == {'execution'}, 'only_separate_execution_metadata_added')
    need(not result.get('ui_validation_error'), 'no_runtime_validation_error')
    execution = result['execution']
    need(execution['qualification_sha256'] == plan['request']['qualification']['sha256'], 'public_qualification_identity')
    need(execution['canonical_provenance']['response_binding_verified'] is True, 'actual_canonical_binding_gate')
    need(execution['canonical_provenance']['parity_protocol_sha256'] == q['parity_protocol']['sha256']
         and execution['canonical_provenance']['parity_receipt_sha256'] == q['parity_receipt']['sha256'],
         'canonical_preflight_identity')
    need(public['verification'] == checks, 'public_and_retained_checker_equal')
    need(checks['request_id'] == REQUEST_ID and checks['input_sha256'] == digest(raw_bytes['input'])
         and checks['response_sha256'] == digest(raw_bytes['response'])
         and checks['raw_text_sha256'] == digest(raw['raw_text'].encode('utf-8')), 'actual_checker_byte_bindings')
    need(checks['context'] == plan['software_acceptance']['checker_context'], 'checker_original_context')
    need(checks['whole_prose_assessed'] is False and checks['engine_calls'] == 0
         and checks['generator_repairs'] == 0, 'checker_scope_limits')
    need(checks['status'] in ('checked', 'unassessed'), 'usable_limited_checker_status')
    if checks['status'] == 'unassessed':
        need(checks['claims'] == [], 'normal_zero_match_unassessed')

    checker_path = REPO / 'prototype/chess_tutor_v1/draft_checks_v1.py'
    need(checks['verifier_sha256'] == digest(bytes_at(checker_path)), 'actual_verifier_identity')
    need(checks['parser_sha256'] == q['base_adapter']['sha256'], 'actual_parser_identity')
    spec = importlib.util.spec_from_file_location('_daytime_reviewed_pure_checks', checker_path)
    pure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pure)
    expected = pure.audit_bytes(raw_bytes['response'], raw_bytes['input'], digest(raw_bytes['input']),
                                packet, context, raw, qualified=True)
    expected['request_id'] = REQUEST_ID
    need(expected == checks, 'independent_pure_checker_recomputation')
    span_count = all_spans(checks, raw['raw_text'])
    for claim in checks['claims']:
        span = claim['span']
        need(raw['raw_text'][span['start']:span['end']] == claim['exact_raw_text'], 'exact_claim_excerpt')
    need(not any(name == 'torch' or name.startswith('torch.') or name == 'transformers'
                 or name.startswith('transformers.') or name.startswith('bitsandbytes') for name in sys.modules),
         'no_learned_runtime_import')

    exports = {name: read(evidence / (name + '-evidence.json')) for name in ('current', 'stale', 'restored')}
    for name in ('current', 'restored'):
        value = exports[name]
        need(value['board']['fen'] == packet['fen'], 'current_and_restored_board')
        need(type(value['coaching']) is dict and same_job(value['coaching'], public), 'current_and_restored_original_job')
        need(value['coaching']['verification'] == checks, 'export_checker_preserved')
        need(all(value['coaching']['result'][key] == item for key, item in raw.items()), 'export_raw_fields_preserved')
    need(exports['stale']['coaching'] is None and exports['stale']['board']['fen'] != packet['fen'], 'stale_export_excludes_coaching')
    need({key: value for key, value in exports['current'].items() if key != 'coaching'}
         == {key: value for key, value in exports['restored'].items() if key != 'coaching'},
         'return_restores_retained_position_evidence')

    closure = read(closure_path)
    need(closure['request_id'] == REQUEST_ID and closure['protocol_sha256'] == PLAN_SHA, 'root_closure_binding')
    need(closure['actual_ui_submissions'] == 1 and closure['owned_child_pid'] == worker['child_pid'], 'one_actual_request_and_child')
    for key in ('owned_child_absent', 'shared_lease_free', 'no_new_coaching_request_on_return', 'return_used_retained_position'):
        need(closure[key] is True, 'attributed_root_closure_observation')
    need(type(closure['observed_at_utc']) is str, 'root_observation_time_retained')
    # These pre-UI snapshots must have been saved by root before its export/navigation
    # actions. Their chronology is an attributed observation for independent review.
    for name, path in paths.items():
        before = closure['before_ui_artifacts'][name]
        need(Path(before['path']).resolve() == path.resolve(), 'pre_UI_artifact_path_identity')
        after = binding(path)
        need(before['sha256'] == after['sha256'] and before['bytes'] == after['bytes'], 'original_bytes_unchanged_after_UI')

    artifacts = [binding(path) for path in [*paths.values(), public_path, closure_path,
        *[evidence / (name + '-evidence.json') for name in exports]]]
    return {
        'status': 'artifact_checks_passed_root_observations_bound',
        'protocol': binding(PLAN), 'request_id': REQUEST_ID,
        'source_and_runtime_metadata_bindings_rehashed': len(source_bindings),
        'qualification_file_bindings_rehashed_without_semantic_reads': len(qualification_hashes),
        'artifacts': artifacts,
        'observed_raw_metadata': {'status': raw['status'], 'finish_reason': raw['finish_reason'],
            'generated_token_count': len(raw['generated_tokens']), 'candidate_id': raw['candidate_id'],
            'generation_mode': raw['settings']['generation_mode'],
            'precision_profile': raw['settings']['precision_profile']},
        'limited_checks': {'status': checks['status'], 'matched_statement_count': len(checks['claims']),
            'span_hashes_checked': span_count, 'whole_prose_assessed': False,
            'supported': sum(row['status'] == 'supported' for row in checks['claims']),
            'contradicted': sum(row['status'] == 'contradicted' for row in checks['claims']),
            'unassessed': sum(row['status'] == 'unassessed' for row in checks['claims'])},
        'validated': ['prospective exact input bytes', 'distinct canonical packet hash meaning',
            'source/runtime/worker argument bindings', 'completed EOS and owned worker closure record',
            'raw public/export field preservation', 'separate pure rule-check recomputation and spans',
            'current/stale/restored export contexts', 'unchanged original artifacts after UI actions'],
        'root_observations_bound_not_measured_by_helper': ['owned child absent', 'shared lease free',
            'one actual UI submission', 'return uses retained position with no new coaching request',
            'before-UI snapshot chronology'],
        'independent_closed_review_still_required': ['admission timing and actual resource samples',
            'browser screenshots and visible controls', 'root process and lease observations',
            'pre-UI snapshot chronology and complete planned/failed/unknown accounting'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True,
                        help='Root evidence directory containing terminal-public-job and three exports.')
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    need(not args.out.exists(), 'create_only_result')
    need(args.out.resolve() not in {PLAN.resolve(), Path(__file__).resolve(), args.closure.resolve()}, 'output_not_input')
    job_folder = (REPO / 'data/private/chess-tutor-v1/coaching' / REQUEST_ID).resolve()
    need(not args.out.resolve().is_relative_to(job_folder), 'output_outside_original_controller_artifacts')
    need(args.out.resolve().parent == Path(__file__).resolve().parent, 'output_in_owned_helper_work_directory')
    report = {'schema': 'chess.daytime.closed-artifact-verification.v1', 'status': 'failed',
              'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'helper_sha256': digest(bytes_at(__file__)), 'protocol_sha256': PLAN_SHA,
              'request_id': REQUEST_ID, 'model_engine_GPU_HTTP_browser_process_calls': 0,
              'production_source_or_original_artifact_edits': 0,
              'quality_or_trained_profile_admission': False,
              'scope': 'Read-only artifact engineering checks. Root OS/UI observations are bound, not independently observed here. No whole-prose or model capability assessment.'}
    try:
        report.update(verify(args.evidence, args.closure))
    except Exception as error:
        report['failure_type'] = type(error).__name__
        report['failed_check'] = str(error) if isinstance(error, CheckFailure) else 'Missing, malformed or unexpected artifact; no content repaired.'
    with args.out.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': report['status'], 'out': str(args.out),
                      'sha256': digest(bytes_at(args.out)), 'failed_check': report.get('failed_check')}))
    return 0 if report['status'] == 'artifact_checks_passed_root_observations_bound' else 1


if __name__ == '__main__':
    raise SystemExit(main())
