"""Synthetic structural controls; no holdout source or protected case is opened."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_holdout_freeze_card_v1 as freeze


def digest(label: str | bytes) -> str:
    return hashlib.sha256(label.encode() if isinstance(label, str) else label).hexdigest()


def encoded(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def fixture():
    """Synthetic metadata only; the URLs and digests are not source evidence."""
    month = '2025-10'
    url = f'https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst'
    def snapshot(label, url):
        return {'url': url,
                'body_sha256': digest(label + '-body'),
                'headers_sha256': digest(label + '-headers'),
                'http_status': 200, 'fetched_utc': '2026-10-06T05:00:00Z'}
    components = {name: {'version': f'{name}/v1', 'sha256': digest('component-' + name)}
                  for name in freeze.COMPONENTS}
    components['no_forward_packet']['version'] = 'chess-holdout-no-forward/v1'
    components['control_packet']['version'] = 'chess-holdout-insufficient-observation/v1'
    components['request_schema']['version'] = 'chess-holdout-request/v1'
    components['validator']['version'] = 'chess-holdout-freeze-card-validator/v1'
    components['validator']['sha256'] = digest(Path(freeze.__file__).read_bytes())
    oracle = {'schema': 'chess-protected-exclusion-oracle/v1', 'status': 'passed',
              'registry_sha256': digest('protected-registry'),
              'oracle_code_sha256': digest('oracle-code'),
              'protected_sets': list(freeze.PROTECTED_SETS),
              'keys': list(freeze.EXCLUSION_KEYS), 'mode': 'count_only',
              'before_ranking': True, 'sealed_details_exposed': False}
    audit = {'schema': 'chess-holdout-no-forward-audit/v1', 'status': 'passed',
             'packet_sha256': components['no_forward_packet']['sha256'],
             'control_packet_sha256': components['control_packet']['sha256'],
             'request_schema_sha256': components['request_schema']['sha256'],
             'audit_code_sha256': digest('audit-code'),
             'forbidden_fields_rejected_pre_dispatch': list(freeze.FORBIDDEN_FIELDS),
             'control_answer_leak_rejected': True, 'model_calls': 0}
    card = {
        'schema': freeze.SCHEMA, 'study_id': 'Synthetic October software card',
        'state': 'prospective_unfrozen',
        'source': {'archive_url': url, 'month': month,
                   'archive_sha256': digest('published-archive'),
                   'source_page': snapshot('source-page', 'https://database.lichess.org/'),
                   'file_list': snapshot('file-list',
                       'https://database.lichess.org/standard/list.txt'),
                   'checksum_page': snapshot('checksum-page',
                       'https://database.lichess.org/standard/sha256sums.txt'),
                   'rights_page': snapshot('rights-page', 'https://database.lichess.org/'),
                   'rights': {'license': 'CC0', 'scope': 'standard_rated_export',
                              'exact_file_link_url': url,
                              'linked_in_source_page': True},
                   'broker': {'name': 'holdout-standard-broker', 'version': 'v1',
                              'code_sha256': digest('broker'),
                              'approved_url': url, 'approved_end_exclusive': 200000,
                              'approved_decompressed_cap': 5000000},
                   'range': {'start': 0, 'end_exclusive': 200000},
                   'caps': {'compressed_bytes': 200000,
                            'decompressed_bytes': 5000000,
                            'games_scanned': 2000, 'positions_examined': 10000,
                            'engine_searches': 2000},
                   'provenance_policy': {
                       'retained_fields': ['url', 'fetched_utc', 'http_status',
                           'response_headers_sha256', 'compressed_byte_count',
                           'compressed_sha256', 'decompressed_byte_count',
                           'decompressed_sha256'],
                       'prefix_rule': 'hash_actual_retained_bytes_not_archive_checksum',
                       'reject_development_prefix_overlap': True}},
        'exclusion': {'registry_sha256': oracle['registry_sha256'],
                      'oracle_code_sha256': oracle['oracle_code_sha256'],
                      'oracle_receipt_sha256': digest(encoded(oracle)),
                      'protected_sets': list(freeze.PROTECTED_SETS),
                      'keys': list(freeze.EXCLUSION_KEYS),
                      'canonical_position_fields': list(freeze.POSITION_FIELDS),
                      'before_ranking': True, 'one_case_per_game': True,
                      'unique_holdout_positions': True},
        'components': components,
        'calibration': {'development_manifest_sha256': digest('development-manifest'),
                        'receipt_sha256': digest('calibration-receipt'),
                        'development_months': ['2025-09'],
                        'development_archive_sha256': digest('september-archive'),
                        'development_prefix_sha256': digest('september-prefix'),
                        'model_settings_sha256': digest('model-settings'),
                        'component_hashes': {
                            name: components[name]['sha256']
                            for name in freeze.CALIBRATED_COMPONENTS}},
        'sampling': {'seed_sha256': digest('frozen-seed'),
                     'rank_rule': 'sha256_seed_namespaced_game_id_ply',
                     'tie_break': 'lexical_game_id_then_ply',
                     'primary_priority': list(freeze.STRATA),
                     'primary_targets': {name: 40 for name in freeze.STRATA},
                     'control_target': 40, 'distinct_game_target': 240,
                     'shortfall_rule': 'report_incomplete_no_replacement',
                     'no_adaptive_top_up': True, 'overlapping_tags_retained': True,
                     'rules': {'inferior_exact_loss_cp': 150,
                               'material_loss_cp': 100,
                               'endgame_max_nonpawn_nonking': 6,
                               'defensive_detector_sha256': digest('defense-detector'),
                               'tactic_detector_sha256': digest('tactic-detector'),
                               'review_quiet_defensive_endgame_before_output': True}},
        'engine': {'binary_sha256': digest('engine-binary'),
                   'version': 'Stockfish synthetic pin', 'threads': 1,
                   'hash_mib': 16, 'initial_nodes': 10000,
                   'recheck_nodes': 50000, 'score_perspective': 'mover',
                   'inferior_score_rule': 'unrestricted_root_exact_cp_both_budgets',
                   'bound_policy': 'unresolved_not_exact',
                   'mate_policy': 'unresolved_no_cp_conversion',
                   'stability_rule': 'same_label_at_both_budgets'},
        'no_forward': {'packet_version': 'chess-holdout-no-forward/v1',
                       'packet_sha256': components['no_forward_packet']['sha256'],
                       'control_packet_sha256': components['control_packet']['sha256'],
                       'request_schema_sha256': components['request_schema']['sha256'],
                       'prompt_sha256': components['prompt']['sha256'],
                       'model_sha256': components['model']['sha256'],
                       'model_settings_sha256': digest('model-settings'),
                       'call_seed': 17,
                       'audit_code_sha256': audit['audit_code_sha256'],
                       'audit_receipt_sha256': digest(encoded(audit)),
                       'allowed_packet_fields': list(freeze.ALLOWED_PACKET_FIELDS),
                       'forbidden_fields': list(freeze.FORBIDDEN_FIELDS),
                       'control_shape_rule':
                           'separate_insufficient_observation_no_answer_leak',
                       'dispatch_gate': 'reject_forbidden_fields_before_post'},
        'attempts': {'scheduled': 240, 'one_per_case': True,
                     'same_case_retry': False, 'raw_bytes_retained': True,
                     'error_bytes_retained': True,
                     'observed_model_identity': True,
                     'timestamps_and_latency': True, 'parser_result_retained': True,
                     'append_only_manifest': True,
                     'raw_seal_before_evaluator_and_human': True,
                     'outcomes': list(freeze.ATTEMPT_OUTCOMES),
                     'per_attempt_fields': list(freeze.ATTEMPT_FIELDS),
                     'all_failures_in_denominator': True,
                     'main_missing_score': 0, 'main_abstention_score': 0,
                     'control_failure_withhold_score': 0,
                     'timeout_latency': 'censored_reported',
                     'asserted_fact_denominator': True,
                     'waterfall_rejections': list(freeze.WATERFALL),
                     'shortfalls_reported': True},
        'review': {'reviewers': [
                       {'name': 'Morgan Chen', 'qualification': 'chess_teacher',
                        'qualification_sha256': digest('morgan-qualification'),
                        'conflict_disclosed': True, 'independent': True},
                       {'name': 'Taylor Shah', 'qualification': 'chess_researcher',
                        'qualification_sha256': digest('taylor-qualification'),
                        'conflict_disclosed': True, 'independent': True}],
                   'adjudicator': 'Jordan Patel',
                   'receipt_reviewer': 'Riley Diaz',
                   'rubric_version': 'v1', 'rubric_sha256': digest('rubric'),
                   'sample_budget': 240, 'blind_initial_ratings': True,
                   'initial_ratings_retained': True,
                   'disagreements_retained': True,
                   'all_emitted_claims_reviewed': True},
        'decision': {'state': 'prospectively_approved_thresholds',
                     'legal_board_accuracy': 1.0, 'engine_accuracy': 1.0,
                     'strategic_supported_fraction': 0.95,
                     'teaching_overall': [170, 200],
                     'teaching_each_stratum': [32, 40],
                     'main_abstention_overall_max': [10, 200],
                     'main_abstention_each_stratum_max': [4, 40],
                     'control_withhold_min': [38, 40],
                     'typed_output_min': [228, 240],
                     'zero_invented_facts': True,
                     'wilson_intervals': '95_percent_overall_and_each_stratum',
                     'quality_gate_separate': True,
                     'chesscom_parity_claim': False},
    }
    return card, oracle, audit


def write_inputs(tmp_path: Path, card: dict, oracle: dict, audit: dict):
    paths = [tmp_path / name for name in ('card.json', 'oracle.json', 'audit.json')]
    for path, value in zip(paths, (card, oracle, audit)):
        path.write_bytes(encoded(value))
    return paths


def test_synthetic_card_creates_only_a_structural_candidate_receipt(tmp_path):
    card, oracle, audit = fixture()
    card_path, oracle_path, audit_path = write_inputs(tmp_path, card, oracle, audit)
    output = tmp_path / 'receipt'
    args = ['--card', str(card_path), '--oracle-receipt', str(oracle_path),
            '--audit-receipt', str(audit_path), '--output-dir', str(output)]
    assert freeze.main(['validate', *args]) == 0
    raw = (output / 'receipt.json').read_bytes()
    receipt = json.loads(raw)
    assert receipt['status'] == 'prospective_structural_candidate_only'
    assert receipt['holdout_frozen'] is False
    assert receipt['source_or_game_content_checked'] is False
    assert receipt['protected_exclusions_applied_to_cases'] is False
    assert receipt['engine_calls'] == receipt['model_calls'] == 0
    assert freeze.main(['verify', *args]) == 0
    assert (output / 'receipt.json').read_bytes() == raw
    with pytest.raises(FileExistsError):
        freeze.main(['validate', *args])
    (output / 'receipt.json').write_bytes(raw + b'changed')
    with pytest.raises(freeze.CardError, match='receipt_differs_from_inputs'):
        freeze.main(['verify', *args])


@pytest.mark.parametrize('change,reason', [
    (lambda card, *_: card['source'].update(month='2025-09'),
     'not_exact_standard_rated_file_for_month'),
    (lambda card, *_: card['source'].update(month='2025-99'),
     'source.month'),
    (lambda card, *_: card['source'].update(
        archive_url=card['source']['archive_url'].replace(
            'database.lichess.org/', 'database.lichess.org:443/')),
     'not_exact_standard_rated_file_for_month'),
    (lambda card, *_: card['source']['broker'].update(approved_url='https://other.invalid/file'),
     'source.broker.approved_url'),
    (lambda card, *_: card['source']['range'].update(end_exclusive=200001),
     'source.broker.approved_end_exclusive'),
    (lambda card, *_: card['source']['caps'].update(games_scanned=239),
     'cannot_reach_distinct_game_target'),
    (lambda card, *_: card['source']['caps'].update(engine_searches=479),
     'below_minimum_120_cases_two_roots_two_budgets'),
    (lambda card, *_: card['source']['file_list'].update(url='https://database.lichess.org/'),
     'source.file_list.url'),
    (lambda card, *_: card['source']['rights_page'].update(
        url='https://database.lichess.org:443/'), 'source.rights_page.url'),
    (lambda card, *_: card['source'].update(
        archive_sha256=card['calibration']['development_archive_sha256']),
     'same_as_development_archive'),
    (lambda card, *_: card['calibration']['component_hashes'].update(
        prompt=digest('changed-prompt')), 'calibration.component_hashes.prompt'),
    (lambda card, *_: card['calibration'].update(development_months=['2025-99']),
     'calibration.development_months'),
    (lambda card, *_: card['calibration'].update(development_months=['2025-08']),
     'missing_known_standard_development_month'),
    (lambda card, *_: card['engine'].update(recheck_nodes=10000),
     'must_exceed_initial_budget'),
    (lambda card, *_: card['sampling']['primary_targets'].update(quiet=39),
     'sampling.primary_targets.quiet'),
    (lambda card, *_: card['attempts'].update(scheduled=239),
     'attempts.scheduled'),
    (lambda card, *_: card['attempts'].update(main_abstention_score=2),
     'attempts.main_abstention_score'),
    (lambda card, *_: card['attempts'].update(control_failure_withhold_score=1),
     'attempts.control_failure_withhold_score'),
    (lambda card, *_: card['attempts']['per_attempt_fields'].remove(
        'full_request_sha256'), 'attempts.per_attempt_fields'),
    (lambda card, *_: card['attempts'].update(
        raw_seal_before_evaluator_and_human=False),
     'attempts.raw_seal_before_evaluator_and_human'),
    (lambda card, *_: card['review']['reviewers'][1].update(name='Morgan Chen'),
     'not_distinct_or_no_qualified'),
    (lambda card, *_: card['decision'].update(typed_output_min=[228, 239]),
     'decision.typed_output_min'),
])
def test_cross_field_and_denominator_failures(change, reason):
    card, oracle, audit = fixture()
    change(card, oracle, audit)
    with pytest.raises(freeze.CardError, match=reason):
        freeze.validate(card, oracle, audit)


def test_protected_oracle_and_no_forward_receipts_are_bound_to_card(tmp_path):
    card, oracle, audit = fixture()
    bad_oracle = deepcopy(oracle)
    bad_oracle['protected_sets'].remove('cohort_24_including_sealed')
    with pytest.raises(freeze.CardError, match='oracle_receipt.protected_sets'):
        freeze.validate(card, bad_oracle, audit)
    bad_oracle = deepcopy(oracle)
    bad_oracle['sealed_details_exposed'] = True
    with pytest.raises(freeze.CardError, match='sealed_details_exposed'):
        freeze.validate(card, bad_oracle, audit)
    bad_audit = deepcopy(audit)
    bad_audit['forbidden_fields_rejected_pre_dispatch'].remove('post_move_fen')
    with pytest.raises(freeze.CardError, match='forbidden_fields_rejected_pre_dispatch'):
        freeze.validate(card, oracle, bad_audit)
    bad_audit = deepcopy(audit)
    bad_audit['model_calls'] = 1
    with pytest.raises(freeze.CardError, match='audit_receipt.model_calls'):
        freeze.validate(card, oracle, bad_audit)
    paths = write_inputs(tmp_path, card, oracle, audit)
    paths[1].write_bytes(encoded({**oracle, 'mode': 'detail_exposing'}))
    with pytest.raises(freeze.CardError, match='receipt_bytes_changed'):
        freeze.main(['validate', '--card', str(paths[0]),
                     '--oracle-receipt', str(paths[1]),
                     '--audit-receipt', str(paths[2]),
                     '--output-dir', str(tmp_path / 'must-not-exist')])
    assert not (tmp_path / 'must-not-exist').exists()


def test_dev_packet_placeholder_and_unaccounted_failures_reject():
    card, oracle, audit = fixture()
    card['components']['no_forward_packet']['version'] = 'chess-no-forward-generator-input/v1'
    with pytest.raises(freeze.CardError, match='no_forward_packet.version'):
        freeze.validate(card, oracle, audit)
    card, oracle, audit = fixture()
    changed = digest('different-validator-source')
    card['components']['validator']['sha256'] = changed
    card['calibration']['component_hashes']['validator'] = changed
    with pytest.raises(freeze.CardError, match='components.validator.sha256'):
        freeze.validate(card, oracle, audit)
    card, oracle, audit = fixture()
    card['attempts']['outcomes'].remove('not_run')
    with pytest.raises(freeze.CardError, match='attempts.outcomes'):
        freeze.validate(card, oracle, audit)
    card, oracle, audit = fixture()
    card['source']['archive_sha256'] = '0' * 64
    with pytest.raises(freeze.CardError, match='placeholder_digest'):
        freeze.validate(card, oracle, audit)


def test_duplicate_unknown_and_missing_json_fields_fail_without_output(tmp_path):
    card, oracle, audit = fixture()
    paths = write_inputs(tmp_path, card, oracle, audit)
    raw = paths[0].read_bytes()
    paths[0].write_bytes(raw.replace(b'"state":"prospective_unfrozen"',
                 b'"state":"prospective_unfrozen","state":"prospective_unfrozen"'))
    with pytest.raises(freeze.CardError, match='duplicate_json_key'):
        freeze.main(['validate', '--card', str(paths[0]),
                     '--oracle-receipt', str(paths[1]),
                     '--audit-receipt', str(paths[2]),
                     '--output-dir', str(tmp_path / 'duplicate-output')])
    assert not (tmp_path / 'duplicate-output').exists()
    card, oracle, audit = fixture()
    card['sealed_game_pgn'] = '1. e4 e5'
    with pytest.raises(freeze.CardError, match='unknown'):
        freeze.validate(card, oracle, audit)
    card, oracle, audit = fixture()
    del card['decision']['control_withhold_min']
    with pytest.raises(freeze.CardError, match='missing'):
        freeze.validate(card, oracle, audit)
