"""Real retained dev observations; altered receipts are synthetic software probes only."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_typed_position_evidence as adapter

DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
SOURCE_SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'


@pytest.fixture
def packet():
    return adapter.build_typed_position_evidence(DATA, SOURCE, SOURCE_SHA)


def check(packet, source=SOURCE, sha=SOURCE_SHA):
    return adapter.validate_typed_position_evidence(DATA, source, sha, packet)


def test_real_receipt_preserves_all_observations_and_no_invented_commentary(packet):
    source = json.loads(SOURCE.read_bytes())
    result = check(packet)
    assert result['complete'] and result['requested_positions'] == result['successful_positions'] == 8
    assert result['legal_candidates'] == 16 and result['qualified_candidates'] == 4
    assert result['engine_calls'] == result['model_calls'] == result['test_outcomes_scored'] == 0
    assert result['engine_scores_independently_reproduced'] is False
    for row, original in zip(packet['positions'], source['results']):
        assert row['engine_evidence'] == original['candidates']
        assert row['commentary_evidence'] == [] and row['split'] == 'dev'
        assert row['source_url'] == original['source_url']
        assert row['schema'] == 'position-evidence/v2'
    assert all('score_cp' not in c for r in packet['positions'] for c in r['engine_evidence'])


@pytest.mark.parametrize('mutation', [
    'id', 'foreign', 'reorder', 'drop_position', 'drop_candidate', 'illegal_pv',
    'forged_transition', 'boolean_score', 'float_score', 'perspective', 'mate_as_cp',
    'bound_as_exact', 'drop_bound', 'source_hash', 'engine_settings', 'denominator',
    'invent_commentary', 'forged_score_rehashed', 'schema', 'extra_key',
])
def test_tampering_fails_even_when_internal_hashes_are_recomputed(packet, mutation):
    row = packet['positions'][0]
    candidate = row['engine_evidence'][0]
    if mutation == 'id': candidate['evidence_id'] = 'chess-candidate:' + '0' * 64
    elif mutation == 'foreign': row['position_id'] = 'foreign'
    elif mutation == 'reorder': packet['positions'].reverse()
    elif mutation == 'drop_position': packet['positions'].pop()
    elif mutation == 'drop_candidate': row['engine_evidence'].pop()
    elif mutation == 'illegal_pv': candidate['pv_uci'] = ['a1a8']
    elif mutation == 'forged_transition': candidate['transition']['capture'] = not candidate['transition']['capture']
    elif mutation == 'boolean_score': candidate['score']['value'] = True
    elif mutation == 'float_score': candidate['score']['value'] = float(candidate['score']['value'])
    elif mutation == 'perspective': candidate['score']['perspective'] = 'white'
    elif mutation == 'mate_as_cp':
        next(c for r in packet['positions'] for c in r['engine_evidence'] if c['score']['type'] == 'mate')['score']['type'] = 'cp'
    elif mutation == 'bound_as_exact':
        next(c for r in packet['positions'] for c in r['engine_evidence'] if c['score']['bound'] != 'exact')['score']['bound'] = 'exact'
    elif mutation == 'drop_bound': del candidate['score']['bound']
    elif mutation == 'source_hash': packet['source_receipt_sha256'] = '0' * 64
    elif mutation == 'engine_settings': packet['engine']['settings']['threads'] = 2
    elif mutation == 'denominator': packet['requested_positions'] = 7
    elif mutation == 'invent_commentary': row['commentary_evidence'] = [{'human': 'invented'}]
    elif mutation == 'forged_score_rehashed':
        candidate['score']['value'] += 1
        candidate['evidence_id'] = cf.candidate_id(row, candidate, packet['source_manifest_sha256'], packet['engine']['sha256'])
    elif mutation == 'schema': row['schema'] = 'position-evidence/v1'
    elif mutation == 'extra_key': packet['quality'] = 'proven'
    with pytest.raises(ValueError, match='pinned_source'):
        check(packet)


def synthetic_receipt(tmp_path, mutate):
    source = json.loads(SOURCE.read_bytes())
    mutate(source)
    output = tmp_path / 'synthetic-software-probe.json'
    cf.write_receipt(source, output)
    return output, cf.file_digest(output)


@pytest.mark.parametrize('direction', ['delivered', 'received'])
def test_synthetic_zero_mate_direction_is_preserved_without_cp_coercion(tmp_path, direction):
    def mutate(source):
        row = source['results'][0]
        candidate = row['candidates'][0]
        candidate['score'].update(type='mate', value=0, mate_zero=direction)
        candidate['evidence_id'] = cf.candidate_id(row, candidate, source['source_manifest_sha256'], source['engine']['sha256'])
    source, sha = synthetic_receipt(tmp_path, mutate)
    packet = adapter.build_typed_position_evidence(DATA, source, sha)
    assert check(packet, source, sha)['integrity_passed']
    assert packet['positions'][0]['engine_evidence'][0]['score']['mate_zero'] == direction
    packet['positions'][0]['engine_evidence'][0]['score']['mate_zero'] = 'received' if direction == 'delivered' else 'delivered'
    with pytest.raises(ValueError): check(packet, source, sha)


def test_synthetic_failure_retains_denominator_error_and_no_fake_candidate(tmp_path):
    def mutate(source):
        source['results'][2].update(status='failed', candidates=[], error={'type': 'SyntheticProbe', 'message': 'software control only'})
    source, sha = synthetic_receipt(tmp_path, mutate)
    packet = adapter.build_typed_position_evidence(DATA, source, sha)
    result = check(packet, source, sha)
    assert not result['complete'] and result['requested_positions'] == 8
    assert result['successful_positions'] == 7 and result['failed_positions'] == 1 and result['legal_candidates'] == 14
    assert packet['positions'][2]['engine_evidence'] == []
    assert adapter.validate_claim(DATA, source, sha, packet, packet['positions'][2]['position_id'], 'invented', {})['status'] == 'abstain'
    packet['positions'].pop(2)
    with pytest.raises(ValueError): check(packet, source, sha)


def test_changed_source_bytes_cannot_be_rebound_by_rehashing_a_candidate(tmp_path, packet):
    def mutate(source):
        row = source['results'][0]
        candidate = row['candidates'][0]
        candidate['score']['value'] += 3
        candidate['evidence_id'] = cf.candidate_id(row, candidate, source['source_manifest_sha256'], source['engine']['sha256'])
    source, _ = synthetic_receipt(tmp_path, mutate)
    with pytest.raises(ValueError, match='pinned_source_receipt_changed'):
        check(packet, source, SOURCE_SHA)


def test_all_real_transition_fields_verify_and_false_boolean_claims_abstain(packet):
    for row in packet['positions']:
        for candidate in row['engine_evidence']:
            for field, value in candidate['transition'].items():
                claim = {'kind': 'board_fact', 'field': field, 'value': value}
                result = adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, row['position_id'], candidate['evidence_id'], claim)
                assert result['status'] == 'verified_board_fact'
            for value in (not candidate['transition']['capture'], int(candidate['transition']['capture'])):
                claim = {'kind': 'board_fact', 'field': 'capture', 'value': value}
                assert adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, row['position_id'], candidate['evidence_id'], claim)['status'] == 'abstain'


def test_engine_observation_is_not_a_quality_or_superiority_claim(packet):
    for row in packet['positions']:
        for candidate in row['engine_evidence']:
            call = lambda claim, evidence_id=candidate['evidence_id']: adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, row['position_id'], evidence_id, claim)
            result = call({'kind': 'engine_observation', 'score': candidate['score']})
            assert result['status'] == 'verified_engine_observation' and not result['independently_reproduced']
            score = copy.deepcopy(candidate['score']); score['value'] += 1
            assert call({'kind': 'engine_observation', 'score': score})['status'] == 'abstain'
            for claim in ({'kind': 'better_than', 'other': 'candidate'}, {'kind': 'concept', 'name': 'winning_attack'},
                          {'kind': 'board_fact', 'field': 'teaching_quality', 'value': 'excellent'}, 'unsupported prose'):
                assert call(claim)['status'] == 'abstain'
            assert call({}, 'unknown')['status'] == 'abstain'
    first, second = packet['positions'][:2]
    assert adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, first['position_id'], second['engine_evidence'][0]['evidence_id'], {})['status'] == 'abstain'
    assert adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, 'unknown', first['engine_evidence'][0]['evidence_id'], {})['status'] == 'abstain'


def test_claim_api_rejects_an_unvalidated_packet_before_judgment(packet):
    row = packet['positions'][0]
    candidate = row['engine_evidence'][0]
    candidate['transition']['capture'] = not candidate['transition']['capture']
    with pytest.raises(ValueError):
        adapter.validate_claim(DATA, SOURCE, SOURCE_SHA, packet, row['position_id'], candidate['evidence_id'],
                               {'kind': 'board_fact', 'field': 'capture', 'value': candidate['transition']['capture']})


def test_build_cli_create_only_and_verify_retained_result(tmp_path, monkeypatch, capsys):
    output = tmp_path / 'typed.json'
    args = ['adapter', 'build', '--data', str(DATA), '--source', str(SOURCE), '--source-sha256', SOURCE_SHA, '--output', str(output)]
    monkeypatch.setattr(sys, 'argv', args)
    assert adapter.main() == 0
    assert json.loads(capsys.readouterr().out)['legal_candidates'] == 16
    with pytest.raises(FileExistsError): adapter.main()
    args[1] = 'verify'
    assert adapter.main() == 0

