#!/usr/bin/env python3
"""Validate a prospective chess holdout freeze card without opening game data.

This is a structural preflight. It reads one card and two count-only/synthetic
preflight receipts. It never fetches a source, reads a PGN, runs an engine or
model, or declares a holdout frozen. Source rights and exclusion truth need
separate independent verification before any acquisition.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


SCHEMA = 'chess-holdout-freeze-card/v1'
MAX_JSON_BYTES = 256_000
COMPONENTS = ('parser', 'selector', 'chess_rules', 'strata', 'engine_evaluator',
              'no_forward_packet', 'prompt', 'model', 'request_schema',
              'control_packet', 'validator', 'scoring')
CALIBRATED_COMPONENTS = ('strata', 'engine_evaluator', 'no_forward_packet',
                         'prompt', 'model', 'request_schema', 'control_packet',
                         'validator', 'scoring')
STRATA = ('inferior', 'endgame', 'defensive', 'tactical', 'quiet')
PROTECTED_SETS = ('training', 'prompt', 'practice', 'development', 'evaluation',
                  'historical_eight', 'cohort_24_including_sealed',
                  'standard_game_development', 'chesscom_practice')
EXCLUSION_KEYS = ('game_id', 'normalized_uci_trajectory', 'canonical_pre_move_position')
POSITION_FIELDS = ('piece_placement', 'side_to_move', 'castling_rights',
                   'legal_en_passant')
FORBIDDEN_FIELDS = ('primary_stratum', 'alternative_move', 'alternative_score',
                    'pv', 'post_move_fen', 'reply', 'future_pgn', 'theme',
                    'annotation', 'evaluator_only')
ALLOWED_PACKET_FIELDS = ('source_binding', 'pre_move_fen', 'side_to_move',
                         'played_uci', 'played_san', 'transition_facts',
                         'vocabulary', 'typed_observation')
ATTEMPT_OUTCOMES = ('typed', 'abstention', 'malformed', 'prose', 'identity_failure',
                    'http_error', 'transport_error', 'timeout', 'interrupted',
                    'oversize', 'not_run')
ATTEMPT_FIELDS = ('case_id', 'packet_sha256', 'full_request_sha256',
                  'prompt_sha256', 'model_sha256', 'model_settings_sha256',
                  'input_audit_sha256', 'raw_or_error_sha256',
                  'observed_model_identity', 'start_utc', 'end_utc',
                  'latency_ms', 'parser_result', 'outcome')
WATERFALL = ('partial_game', 'bad_id', 'variant', 'bad_result', 'illegal_move',
             'rights', 'header', 'game_overlap', 'trajectory_overlap',
             'position_overlap', 'duplicate_holdout_game',
             'duplicate_holdout_position', 'engine_failure', 'unstable_score',
             'reviewer_reject')
PLACEHOLDER = re.compile(r'(?i)\b(tbd|todo|placeholder|unknown|not set|example)\b')


class CardError(ValueError):
    """An unfilled or internally inconsistent prospective freeze card."""


def _fail(path: str, reason: str) -> None:
    raise CardError(f'{path}: {reason}')


def _object(value: object, keys: tuple[str, ...], path: str) -> dict:
    if type(value) is not dict:
        _fail(path, 'expected_object')
    missing = set(keys) - set(value)
    unknown = set(value) - set(keys)
    if missing or unknown:
        _fail(path, f'field_mismatch missing={sorted(missing)} unknown={sorted(unknown)}')
    return value


def _text(value: object, path: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        _fail(path, 'expected_nonempty_text')
    if PLACEHOLDER.search(value) or value.lower() in {'none', 'null', 'n/a'}:
        _fail(path, 'placeholder')
    return value


def _sha(value: object, path: str) -> str:
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value):
        _fail(path, 'expected_lowercase_sha256')
    if len(set(value)) < 8 or value == (value[:8] * 8):
        _fail(path, 'placeholder_digest')
    return value


def _int(value: object, path: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        _fail(path, f'expected_integer_at_least_{minimum}')
    return value


def _equal(value: object, expected: object, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, f'expected_{expected!r}')


def _sequence(value: object, expected: tuple[str, ...], path: str) -> None:
    if type(value) is not list or value != list(expected):
        _fail(path, f'expected_exact_order_{list(expected)!r}')


def _set(value: object, expected: tuple[str, ...], path: str) -> None:
    if (type(value) is not list or len(value) != len(expected)
            or any(type(item) is not str for item in value)
            or set(value) != set(expected)):
        _fail(path, f'expected_exact_set_{list(expected)!r}')


def _snapshot(value: object, path: str, expected_url: str) -> None:
    snap = _object(value, ('url', 'body_sha256', 'headers_sha256',
                           'http_status', 'fetched_utc'), path)
    url = _text(snap['url'], f'{path}.url')
    _equal(url, expected_url, f'{path}.url')
    _sha(snap['body_sha256'], f'{path}.body_sha256')
    _sha(snap['headers_sha256'], f'{path}.headers_sha256')
    _equal(snap['http_status'], 200, f'{path}.http_status')
    stamp = _text(snap['fetched_utc'], f'{path}.fetched_utc')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', stamp):
        _fail(f'{path}.fetched_utc', 'expected_utc_timestamp')
    try:
        datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as error:
        raise CardError(f'{path}.fetched_utc: invalid_calendar_timestamp') from error


def _source(card: dict) -> None:
    src = _object(card['source'], ('archive_url', 'month', 'archive_sha256',
                  'source_page', 'file_list', 'checksum_page', 'rights_page',
                  'rights', 'broker', 'range', 'caps', 'provenance_policy'), 'source')
    archive_url = _text(src['archive_url'], 'source.archive_url')
    month = src['month']
    if (type(month) is not str or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month)):
        _fail('source.month', 'invalid_calendar_month')
    canonical_url = (f'https://database.lichess.org/standard/'
                     f'lichess_db_standard_rated_{month}.pgn.zst')
    if archive_url != canonical_url:
        _fail('source.archive_url', 'not_exact_standard_rated_file_for_month')
    _sha(src['archive_sha256'], 'source.archive_sha256')
    for name, expected in (('source_page', 'https://database.lichess.org/'),
                           ('file_list', 'https://database.lichess.org/standard/list.txt'),
                           ('checksum_page',
                            'https://database.lichess.org/standard/sha256sums.txt'),
                           ('rights_page', 'https://database.lichess.org/')):
        _snapshot(src[name], f'source.{name}', expected)
    rights = _object(src['rights'], ('license', 'scope', 'exact_file_link_url',
                                    'linked_in_source_page'), 'source.rights')
    _equal(rights['license'], 'CC0', 'source.rights.license')
    _equal(rights['scope'], 'standard_rated_export', 'source.rights.scope')
    _equal(rights['exact_file_link_url'], archive_url,
           'source.rights.exact_file_link_url')
    _equal(rights['linked_in_source_page'], True,
           'source.rights.linked_in_source_page')
    broker = _object(src['broker'], ('name', 'version', 'code_sha256',
                     'approved_url', 'approved_end_exclusive',
                     'approved_decompressed_cap'), 'source.broker')
    _text(broker['name'], 'source.broker.name')
    _text(broker['version'], 'source.broker.version')
    _sha(broker['code_sha256'], 'source.broker.code_sha256')
    _equal(broker['approved_url'], archive_url, 'source.broker.approved_url')
    byte_range = _object(src['range'], ('start', 'end_exclusive'), 'source.range')
    _equal(byte_range['start'], 0, 'source.range.start')
    end = _int(byte_range['end_exclusive'], 'source.range.end_exclusive')
    _equal(broker['approved_end_exclusive'], end,
           'source.broker.approved_end_exclusive')
    caps = _object(src['caps'], ('compressed_bytes', 'decompressed_bytes',
                   'games_scanned', 'positions_examined', 'engine_searches'),
                   'source.caps')
    compressed = _int(caps['compressed_bytes'], 'source.caps.compressed_bytes')
    decompressed = _int(caps['decompressed_bytes'], 'source.caps.decompressed_bytes')
    if end > compressed:
        _fail('source.range', 'exceeds_compressed_cap')
    _equal(broker['approved_decompressed_cap'], decompressed,
           'source.broker.approved_decompressed_cap')
    if _int(caps['games_scanned'], 'source.caps.games_scanned') < 240:
        _fail('source.caps.games_scanned', 'cannot_reach_distinct_game_target')
    if _int(caps['positions_examined'], 'source.caps.positions_examined') < 240:
        _fail('source.caps.positions_examined', 'cannot_reach_case_target')
    if _int(caps['engine_searches'], 'source.caps.engine_searches') < 480:
        _fail('source.caps.engine_searches', 'below_minimum_120_cases_two_roots_two_budgets')
    policy = _object(src['provenance_policy'], ('retained_fields', 'prefix_rule',
                     'reject_development_prefix_overlap'),
                     'source.provenance_policy')
    _set(policy['retained_fields'], ('url', 'fetched_utc', 'http_status',
         'response_headers_sha256', 'compressed_byte_count',
         'compressed_sha256', 'decompressed_byte_count', 'decompressed_sha256'),
         'source.provenance_policy.retained_fields')
    _equal(policy['prefix_rule'], 'hash_actual_retained_bytes_not_archive_checksum',
           'source.provenance_policy.prefix_rule')
    _equal(policy['reject_development_prefix_overlap'], True,
           'source.provenance_policy.reject_development_prefix_overlap')


def _components(card: dict) -> None:
    components = _object(card['components'], COMPONENTS, 'components')
    for name in COMPONENTS:
        item = _object(components[name], ('version', 'sha256'), f'components.{name}')
        _text(item['version'], f'components.{name}.version')
        _sha(item['sha256'], f'components.{name}.sha256')
    for name, version in (('no_forward_packet', 'chess-holdout-no-forward/v1'),
                          ('control_packet', 'chess-holdout-insufficient-observation/v1'),
                          ('request_schema', 'chess-holdout-request/v1'),
                          ('validator', 'chess-holdout-freeze-card-validator/v1')):
        _equal(components[name]['version'], version, f'components.{name}.version')
    _equal(components['validator']['sha256'], _digest(Path(__file__).read_bytes()),
           'components.validator.sha256')
    calibration = _object(card['calibration'], ('development_manifest_sha256',
                          'receipt_sha256', 'development_months',
                          'development_archive_sha256',
                          'development_prefix_sha256', 'model_settings_sha256',
                          'component_hashes'), 'calibration')
    _sha(calibration['development_manifest_sha256'],
         'calibration.development_manifest_sha256')
    _sha(calibration['receipt_sha256'], 'calibration.receipt_sha256')
    months = calibration['development_months']
    if (type(months) is not list or not months
            or any(type(month) is not str for month in months)
            or len(months) != len(set(months))):
        _fail('calibration.development_months', 'expected_distinct_months')
    for month in months:
        if type(month) is not str or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
            _fail('calibration.development_months', 'bad_month')
    if '2025-09' not in months:
        _fail('calibration.development_months', 'missing_known_standard_development_month')
    if card['source']['month'] in months:
        _fail('source.month', 'same_as_development_source_month')
    archive = _sha(calibration['development_archive_sha256'],
                   'calibration.development_archive_sha256')
    _sha(calibration['development_prefix_sha256'],
         'calibration.development_prefix_sha256')
    if card['source']['archive_sha256'] == archive:
        _fail('source.archive_sha256', 'same_as_development_archive')
    _sha(calibration['model_settings_sha256'],
         'calibration.model_settings_sha256')
    pinned = _object(calibration['component_hashes'], CALIBRATED_COMPONENTS,
                     'calibration.component_hashes')
    for name in CALIBRATED_COMPONENTS:
        _equal(pinned[name], components[name]['sha256'],
               f'calibration.component_hashes.{name}')


def _exclusion(card: dict, oracle_receipt: dict) -> None:
    exclusion = _object(card['exclusion'], ('registry_sha256', 'oracle_code_sha256',
                         'oracle_receipt_sha256', 'protected_sets', 'keys',
                         'canonical_position_fields', 'before_ranking',
                         'one_case_per_game', 'unique_holdout_positions'), 'exclusion')
    for name in ('registry_sha256', 'oracle_code_sha256', 'oracle_receipt_sha256'):
        _sha(exclusion[name], f'exclusion.{name}')
    _set(exclusion['protected_sets'], PROTECTED_SETS, 'exclusion.protected_sets')
    _set(exclusion['keys'], EXCLUSION_KEYS, 'exclusion.keys')
    _set(exclusion['canonical_position_fields'], POSITION_FIELDS,
         'exclusion.canonical_position_fields')
    for name in ('before_ranking', 'one_case_per_game', 'unique_holdout_positions'):
        _equal(exclusion[name], True, f'exclusion.{name}')
    oracle = _object(oracle_receipt, ('schema', 'status', 'registry_sha256',
                     'oracle_code_sha256', 'protected_sets', 'keys', 'mode',
                     'before_ranking', 'sealed_details_exposed'), 'oracle_receipt')
    _equal(oracle['schema'], 'chess-protected-exclusion-oracle/v1',
           'oracle_receipt.schema')
    _equal(oracle['status'], 'passed', 'oracle_receipt.status')
    for name in ('registry_sha256', 'oracle_code_sha256'):
        _equal(oracle[name], exclusion[name], f'oracle_receipt.{name}')
    _set(oracle['protected_sets'], PROTECTED_SETS, 'oracle_receipt.protected_sets')
    _set(oracle['keys'], EXCLUSION_KEYS, 'oracle_receipt.keys')
    _equal(oracle['mode'], 'count_only', 'oracle_receipt.mode')
    _equal(oracle['before_ranking'], True, 'oracle_receipt.before_ranking')
    _equal(oracle['sealed_details_exposed'], False,
           'oracle_receipt.sealed_details_exposed')


def _sampling_engine(card: dict) -> None:
    sampling = _object(card['sampling'], ('seed_sha256', 'rank_rule', 'tie_break',
                       'primary_priority', 'primary_targets', 'control_target',
                       'distinct_game_target', 'shortfall_rule', 'no_adaptive_top_up',
                       'overlapping_tags_retained', 'rules'), 'sampling')
    _sha(sampling['seed_sha256'], 'sampling.seed_sha256')
    _equal(sampling['rank_rule'], 'sha256_seed_namespaced_game_id_ply',
           'sampling.rank_rule')
    _equal(sampling['tie_break'], 'lexical_game_id_then_ply',
           'sampling.tie_break')
    _sequence(sampling['primary_priority'], STRATA, 'sampling.primary_priority')
    targets = _object(sampling['primary_targets'], STRATA, 'sampling.primary_targets')
    for name in STRATA:
        _equal(targets[name], 40, f'sampling.primary_targets.{name}')
    _equal(sampling['control_target'], 40, 'sampling.control_target')
    _equal(sampling['distinct_game_target'], sum(targets.values()) + 40,
           'sampling.distinct_game_target')
    _equal(sampling['shortfall_rule'], 'report_incomplete_no_replacement',
           'sampling.shortfall_rule')
    _equal(sampling['no_adaptive_top_up'], True, 'sampling.no_adaptive_top_up')
    _equal(sampling['overlapping_tags_retained'], True,
           'sampling.overlapping_tags_retained')
    rules = _object(sampling['rules'], ('inferior_exact_loss_cp',
                    'material_loss_cp', 'endgame_max_nonpawn_nonking',
                    'defensive_detector_sha256', 'tactic_detector_sha256',
                    'review_quiet_defensive_endgame_before_output'), 'sampling.rules')
    _equal(rules['inferior_exact_loss_cp'], 150,
           'sampling.rules.inferior_exact_loss_cp')
    _int(rules['material_loss_cp'], 'sampling.rules.material_loss_cp')
    _equal(rules['endgame_max_nonpawn_nonking'], 6,
           'sampling.rules.endgame_max_nonpawn_nonking')
    _sha(rules['defensive_detector_sha256'],
         'sampling.rules.defensive_detector_sha256')
    _sha(rules['tactic_detector_sha256'],
         'sampling.rules.tactic_detector_sha256')
    _equal(rules['review_quiet_defensive_endgame_before_output'], True,
           'sampling.rules.review_quiet_defensive_endgame_before_output')
    engine = _object(card['engine'], ('binary_sha256', 'version', 'threads',
                     'hash_mib', 'initial_nodes', 'recheck_nodes',
                     'score_perspective', 'inferior_score_rule', 'bound_policy',
                     'mate_policy', 'stability_rule'), 'engine')
    _sha(engine['binary_sha256'], 'engine.binary_sha256')
    _text(engine['version'], 'engine.version')
    _equal(engine['threads'], 1, 'engine.threads')
    _int(engine['hash_mib'], 'engine.hash_mib')
    first = _int(engine['initial_nodes'], 'engine.initial_nodes')
    if _int(engine['recheck_nodes'], 'engine.recheck_nodes') <= first:
        _fail('engine.recheck_nodes', 'must_exceed_initial_budget')
    _equal(engine['score_perspective'], 'mover', 'engine.score_perspective')
    _equal(engine['inferior_score_rule'], 'unrestricted_root_exact_cp_both_budgets',
           'engine.inferior_score_rule')
    _equal(engine['bound_policy'], 'unresolved_not_exact', 'engine.bound_policy')
    _equal(engine['mate_policy'], 'unresolved_no_cp_conversion', 'engine.mate_policy')
    _equal(engine['stability_rule'], 'same_label_at_both_budgets',
           'engine.stability_rule')


def _no_forward(card: dict, audit_receipt: dict) -> None:
    nf = _object(card['no_forward'], ('packet_version', 'packet_sha256',
                 'control_packet_sha256', 'request_schema_sha256',
                 'prompt_sha256', 'model_sha256', 'model_settings_sha256',
                 'call_seed', 'audit_code_sha256',
                 'audit_receipt_sha256', 'allowed_packet_fields',
                 'forbidden_fields', 'control_shape_rule', 'dispatch_gate'),
                 'no_forward')
    _equal(nf['packet_version'], 'chess-holdout-no-forward/v1',
           'no_forward.packet_version')
    for field, component in (('packet_sha256', 'no_forward_packet'),
                             ('control_packet_sha256', 'control_packet'),
                             ('request_schema_sha256', 'request_schema'),
                             ('prompt_sha256', 'prompt'), ('model_sha256', 'model')):
        _equal(nf[field], card['components'][component]['sha256'],
               f'no_forward.{field}')
    _equal(nf['model_settings_sha256'], card['calibration']['model_settings_sha256'],
           'no_forward.model_settings_sha256')
    _int(nf['call_seed'], 'no_forward.call_seed', minimum=0)
    _sha(nf['audit_code_sha256'], 'no_forward.audit_code_sha256')
    _sha(nf['audit_receipt_sha256'], 'no_forward.audit_receipt_sha256')
    _set(nf['allowed_packet_fields'], ALLOWED_PACKET_FIELDS,
         'no_forward.allowed_packet_fields')
    _set(nf['forbidden_fields'], FORBIDDEN_FIELDS,
         'no_forward.forbidden_fields')
    _equal(nf['control_shape_rule'], 'separate_insufficient_observation_no_answer_leak',
           'no_forward.control_shape_rule')
    _equal(nf['dispatch_gate'], 'reject_forbidden_fields_before_post',
           'no_forward.dispatch_gate')
    audit = _object(audit_receipt, ('schema', 'status', 'packet_sha256',
                    'control_packet_sha256', 'request_schema_sha256',
                    'audit_code_sha256', 'forbidden_fields_rejected_pre_dispatch',
                    'control_answer_leak_rejected', 'model_calls'), 'audit_receipt')
    _equal(audit['schema'], 'chess-holdout-no-forward-audit/v1',
           'audit_receipt.schema')
    _equal(audit['status'], 'passed', 'audit_receipt.status')
    for name in ('packet_sha256', 'control_packet_sha256',
                 'request_schema_sha256', 'audit_code_sha256'):
        _equal(audit[name], nf[name], f'audit_receipt.{name}')
    _set(audit['forbidden_fields_rejected_pre_dispatch'], FORBIDDEN_FIELDS,
         'audit_receipt.forbidden_fields_rejected_pre_dispatch')
    _equal(audit['control_answer_leak_rejected'], True,
           'audit_receipt.control_answer_leak_rejected')
    _equal(audit['model_calls'], 0, 'audit_receipt.model_calls')


def _attempts_review_decision(card: dict) -> None:
    attempts = _object(card['attempts'], ('scheduled', 'one_per_case',
                       'same_case_retry', 'raw_bytes_retained', 'error_bytes_retained',
                       'observed_model_identity', 'timestamps_and_latency',
                       'parser_result_retained', 'append_only_manifest',
                       'raw_seal_before_evaluator_and_human', 'outcomes',
                       'per_attempt_fields',
                       'all_failures_in_denominator', 'main_missing_score',
                       'main_abstention_score', 'control_failure_withhold_score',
                       'timeout_latency',
                       'asserted_fact_denominator', 'waterfall_rejections',
                       'shortfalls_reported'), 'attempts')
    _equal(attempts['scheduled'], card['sampling']['distinct_game_target'],
           'attempts.scheduled')
    for name in ('one_per_case', 'raw_bytes_retained', 'error_bytes_retained',
                 'observed_model_identity',
                 'timestamps_and_latency', 'parser_result_retained',
                 'append_only_manifest', 'raw_seal_before_evaluator_and_human',
                 'all_failures_in_denominator', 'asserted_fact_denominator',
                 'shortfalls_reported'):
        _equal(attempts[name], True, f'attempts.{name}')
    _equal(attempts['same_case_retry'], False, 'attempts.same_case_retry')
    _set(attempts['outcomes'], ATTEMPT_OUTCOMES, 'attempts.outcomes')
    _set(attempts['per_attempt_fields'], ATTEMPT_FIELDS,
         'attempts.per_attempt_fields')
    _equal(attempts['main_missing_score'], 0, 'attempts.main_missing_score')
    _equal(attempts['main_abstention_score'], 0,
           'attempts.main_abstention_score')
    _equal(attempts['control_failure_withhold_score'], 0,
           'attempts.control_failure_withhold_score')
    _equal(attempts['timeout_latency'], 'censored_reported',
           'attempts.timeout_latency')
    _set(attempts['waterfall_rejections'], WATERFALL,
         'attempts.waterfall_rejections')
    review = _object(card['review'], ('reviewers', 'adjudicator',
                     'receipt_reviewer', 'rubric_version', 'rubric_sha256',
                     'sample_budget', 'blind_initial_ratings',
                     'initial_ratings_retained', 'disagreements_retained',
                     'all_emitted_claims_reviewed'), 'review')
    people = review['reviewers']
    if type(people) is not list or len(people) != 2:
        _fail('review.reviewers', 'expected_two_independent_named_reviewers')
    names = []
    qualified = False
    for index, person in enumerate(people):
        path = f'review.reviewers[{index}]'
        item = _object(person, ('name', 'qualification', 'qualification_sha256',
                       'conflict_disclosed', 'independent'), path)
        name = _text(item['name'], f'{path}.name')
        if len(name.split()) < 2 or any(len(part) < 2 for part in name.split()):
            _fail(f'{path}.name', 'expected_full_name')
        names.append(name.casefold())
        if item['qualification'] not in ('chess_teacher', 'rated_player',
                                          'chess_researcher'):
            _fail(f'{path}.qualification', 'unrecognized_qualification')
        qualified |= item['qualification'] in ('chess_teacher', 'rated_player')
        _sha(item['qualification_sha256'], f'{path}.qualification_sha256')
        _equal(item['conflict_disclosed'], True, f'{path}.conflict_disclosed')
        _equal(item['independent'], True, f'{path}.independent')
    if len(set(names)) != 2 or not qualified:
        _fail('review.reviewers', 'not_distinct_or_no_qualified_chess_reviewer')
    for name in ('adjudicator', 'receipt_reviewer'):
        full = _text(review[name], f'review.{name}')
        if len(full.split()) < 2 or full.casefold() in names:
            _fail(f'review.{name}', 'must_be_distinct_named_person')
        names.append(full.casefold())
    if len(set(names)) != 4:
        _fail('review', 'review_roles_not_distinct')
    _text(review['rubric_version'], 'review.rubric_version')
    _sha(review['rubric_sha256'], 'review.rubric_sha256')
    _equal(review['sample_budget'], attempts['scheduled'], 'review.sample_budget')
    for name in ('blind_initial_ratings', 'initial_ratings_retained',
                 'disagreements_retained', 'all_emitted_claims_reviewed'):
        _equal(review[name], True, f'review.{name}')
    decision = _object(card['decision'], ('state', 'legal_board_accuracy',
                       'engine_accuracy', 'strategic_supported_fraction',
                       'teaching_overall', 'teaching_each_stratum',
                       'main_abstention_overall_max',
                       'main_abstention_each_stratum_max',
                       'control_withhold_min', 'typed_output_min',
                       'zero_invented_facts', 'wilson_intervals',
                       'quality_gate_separate', 'chesscom_parity_claim'), 'decision')
    _equal(decision['state'], 'prospectively_approved_thresholds',
           'decision.state')
    _equal(decision['legal_board_accuracy'], 1.0,
           'decision.legal_board_accuracy')
    _equal(decision['engine_accuracy'], 1.0, 'decision.engine_accuracy')
    _equal(decision['strategic_supported_fraction'], 0.95,
           'decision.strategic_supported_fraction')
    _equal(decision['teaching_overall'], [170, 200],
           'decision.teaching_overall')
    _equal(decision['teaching_each_stratum'], [32, 40],
           'decision.teaching_each_stratum')
    _equal(decision['main_abstention_overall_max'], [10, 200],
           'decision.main_abstention_overall_max')
    _equal(decision['main_abstention_each_stratum_max'], [4, 40],
           'decision.main_abstention_each_stratum_max')
    _equal(decision['control_withhold_min'], [38, 40],
           'decision.control_withhold_min')
    _equal(decision['typed_output_min'], [228, 240],
           'decision.typed_output_min')
    _equal(decision['zero_invented_facts'], True,
           'decision.zero_invented_facts')
    _equal(decision['wilson_intervals'], '95_percent_overall_and_each_stratum',
           'decision.wilson_intervals')
    _equal(decision['quality_gate_separate'], True,
           'decision.quality_gate_separate')
    _equal(decision['chesscom_parity_claim'], False,
           'decision.chesscom_parity_claim')


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CardError(f'duplicate_json_key:{key}')
        result[key] = value
    return result


def _load_json(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_JSON_BYTES:
        _fail(str(path), 'empty_or_oversize_json')
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs,
                           parse_constant=lambda value: _fail('json', f'nonfinite_{value}'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CardError(f'{path}: invalid_json') from error
    if type(value) is not dict:
        _fail(str(path), 'expected_json_object')
    return raw, value


def validate(card: dict, oracle_receipt: dict, audit_receipt: dict) -> None:
    _object(card, ('schema', 'study_id', 'state', 'source', 'exclusion',
                  'components', 'calibration', 'sampling', 'engine',
                  'no_forward', 'attempts', 'review', 'decision'), 'card')
    _equal(card['schema'], SCHEMA, 'card.schema')
    _text(card['study_id'], 'card.study_id')
    _equal(card['state'], 'prospective_unfrozen', 'card.state')
    _source(card)
    _components(card)
    _sampling_engine(card)
    _exclusion(card, oracle_receipt)
    _no_forward(card, audit_receipt)
    _attempts_review_decision(card)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'verify'):
        item = sub.add_parser(name)
        item.add_argument('--card', type=Path, required=True)
        item.add_argument('--oracle-receipt', type=Path, required=True)
        item.add_argument('--audit-receipt', type=Path, required=True)
        item.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    card_raw, card = _load_json(args.card)
    oracle_raw, oracle = _load_json(args.oracle_receipt)
    audit_raw, audit = _load_json(args.audit_receipt)
    exclusion = card.get('exclusion')
    no_forward = card.get('no_forward')
    if type(exclusion) is not dict or type(no_forward) is not dict:
        _fail('card', 'missing_receipt_pins')
    oracle_pin = _sha(exclusion.get('oracle_receipt_sha256'),
                      'exclusion.oracle_receipt_sha256')
    audit_pin = _sha(no_forward.get('audit_receipt_sha256'),
                     'no_forward.audit_receipt_sha256')
    if _digest(oracle_raw) != oracle_pin:
        _fail('exclusion.oracle_receipt_sha256', 'receipt_bytes_changed')
    if _digest(audit_raw) != audit_pin:
        _fail('no_forward.audit_receipt_sha256', 'receipt_bytes_changed')
    validate(card, oracle, audit)
    receipt = {'schema': 'chess-holdout-freeze-card-validation/v1',
               'status': 'prospective_structural_candidate_only',
               'validator_source_sha256': _digest(Path(__file__).read_bytes()),
               'card_sha256': _digest(card_raw),
               'oracle_receipt_sha256': _digest(oracle_raw),
               'audit_receipt_sha256': _digest(audit_raw),
               'holdout_frozen': False, 'source_or_game_content_checked': False,
               'rights_independently_verified': False,
               'protected_exclusions_applied_to_cases': False,
               'engine_calls': 0, 'model_calls': 0}
    expected = _canonical(receipt)
    path = args.output_dir / 'receipt.json'
    if args.command == 'validate':
        args.output_dir.mkdir(parents=True, exist_ok=False)
        path.write_bytes(expected)
    elif path.read_bytes() != expected:
        _fail(str(path), 'receipt_differs_from_inputs')
    print(json.dumps({'status': receipt['status'], 'card_sha256': receipt['card_sha256'],
                      'receipt_sha256': _digest(expected), 'output': str(path)},
                     sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
