"""Authored software fixtures only; no saved learned response or heldout input."""
import builtins
import copy
import importlib.util
import json
from pathlib import Path
import sys

import chess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/chess_queen_claim_audit_v1.py'
spec = importlib.util.spec_from_file_location('queen_claim_audit_tested', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture(claim=None, *, fen=chess.STARTING_FEN, branch=None, turn='white', text='White has eight pawns.', resolution='explicit'):
    raw = json.dumps({'status': 'completed', 'input': {'fen': fen}, 'raw_text': text}, ensure_ascii=False).encode()
    row = {'claim_id': 'claim-1', 'span': {'start': 0, 'end': len(text), 'sha256': audit.digest(text.encode())},
           'context': {'resolution': resolution, 'branch_uci': branch or [], 'expected_turn': turn},
           'claim': claim or {'kind': 'piece_count', 'color': 'white', 'piece_type': 'pawn', 'expected': 8}}
    annotations = {'schema': audit.ANNOTATION_SCHEMA, 'response_sha256': audit.digest(raw),
                   'raw_text_sha256': audit.digest(text.encode()), 'claims': [row]}
    return raw, annotations


def result(claim=None, **kwargs):
    return audit.audit_response(*fixture(claim, **kwargs))['claims'][0]


def counts(color='white', **changes):
    expected = dict(zip(audit.PIECES[:5], (8, 2, 2, 2, 1)))
    expected.update(changes)
    return {'kind': 'material_count', 'color': color, 'expected': expected}


def attack(start, target, kind='rook', color='white', expected=True):
    return {'kind': 'geometric_attacks_square', 'piece': {'color': color, 'type': kind},
            'from_square': start, 'target_square': target, 'expected': expected}


def variation(moves, expected=True):
    return {'kind': 'legal_variation', 'moves_uci': moves, 'expected': expected}


def protocol():
    plan = {'schema': audit.PROTOCOL_SCHEMA, 'implementation_sha256': audit.digest(SOURCE.read_bytes()),
            'contract': audit.CONTRACT, 'manual_semantic_review_before_authored_measurement': True,
            'response_pool': {'responses': [{'index': 0, 'path': 'authored-test-fixture.json', 'sha256': audit.digest(fixture()[0])}]}}
    raw = json.dumps(plan).encode()
    return raw, audit.digest(raw)


def test_exact_source_counts_and_honest_annotation_denominators():
    raw, annotations = fixture()
    second = copy.deepcopy(annotations['claims'][0]);second['claim_id'] = 'false'
    second['claim']['expected'] = 7
    unknown = copy.deepcopy(second);unknown['claim_id'] = 'unknown';unknown['claim']['kind'] = 'wins_material'
    annotations['claims'] += [second, unknown]
    out = audit.audit_response(raw, annotations)
    assert out['summary'] == {'annotated': 3, 'supported': 1, 'contradicted': 1, 'unassessed': 1,
                              'assessed_annotation_fraction': 2/3, 'supported_fraction_among_assessed': .5}
    assert out['semantic_mapping_automatically_verified'] is False
    assert out['whole_prose_coverage_established'] is False and out['evaluation_only'] is True
    assert out['claims'][0]['exact_raw_text'] == 'White has eight pawns.'
    assert out['response_sha256'] == audit.digest(raw)


@pytest.mark.parametrize('field', ['response_sha256', 'raw_text_sha256'])
def test_wrong_source_or_text_hash_rejects_before_unsupported_verdict(field):
    raw, annotations = fixture({'kind': 'unknown'})
    annotations[field] = '0'*64
    with pytest.raises(audit.BindingError):audit.audit_response(raw, annotations)


@pytest.mark.parametrize('change', [{'start': -1}, {'start': True}, {'end': 9999}, {'end': 0}, {'sha256': '0'*64}])
def test_bad_span_is_hard_error_even_if_other_claim_would_be_supported(change):
    raw, annotations = fixture()
    bad = copy.deepcopy(annotations['claims'][0]);bad['claim_id'] = 'later';bad['span'].update(change)
    annotations['claims'].append(bad)
    with pytest.raises(audit.BindingError):audit.audit_response(raw, annotations)


def test_unicode_offsets_are_code_points_and_same_text_response_bytes_still_bound():
    text = '♟️ A pawn. Queen’s move.'
    raw, annotations = fixture(text=text)
    start, end = text.index('Queen'), len(text)
    annotations['claims'][0]['span'] = {'start': start, 'end': end, 'sha256': audit.digest(text[start:end].encode())}
    assert audit.audit_response(raw, annotations)['claims'][0]['exact_raw_text'] == 'Queen’s move.'
    with pytest.raises(audit.BindingError):audit.audit_response(raw+b' ', annotations)


def test_duplicate_ids_keys_nonfinite_and_invalid_utf8_fail_integrity():
    raw, annotations = fixture();annotations['claims'].append(copy.deepcopy(annotations['claims'][0]))
    with pytest.raises(audit.BindingError):audit.audit_response(raw, annotations)
    for bad in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b''):
        with pytest.raises(audit.BindingError):audit.decode_json(bad)


def test_material_counts_never_infer_advantage_and_promotion_changes_type():
    assert result(counts())['observed']['queen'] == 1
    assert result(counts(queen=0))['status'] == 'contradicted'
    observed = result(counts(pawn=0, knight=0, bishop=0, rook=0),
                      fen='7k/P7/8/8/8/8/8/7K w - - 0 1', branch=['a7a8q'], turn='black')
    assert observed['status'] == 'supported'
    assert 'advantage' in observed['scope'] and 'point score' in observed['scope']
    assert result({'kind': 'material_advantage', 'expected': True})['status'] == 'unassessed'


@pytest.mark.parametrize('context_change,reason', [
    ({'resolution': 'ambiguous'}, 'ambiguous_or_unresolved_context'),
    ({'expected_turn': 'black'}, 'context_turn_mismatch'),
    ({'fen': chess.STARTING_FEN}, 'unsupported_context_fields'),
    ({'branch_uci': ['e2e2']}, 'invalid_context_branch_or_turn'),
    ({'branch_uci': ['bad']}, 'invalid_context_branch_or_turn'),
])
def test_stale_ambiguous_or_replacement_context_is_unassessed(context_change, reason):
    raw, annotations = fixture();annotations['claims'][0]['context'].update(context_change)
    out = audit.audit_response(raw, annotations)['claims'][0]
    assert out['status'] == 'unassessed' and out['reason'] == reason


def test_illegal_earlier_context_never_forces_a_later_false_claim():
    out = result(attack('f2', 'e8', 'pawn'), branch=['e2e4', 'e2e3'])
    assert out['status'] == 'unassessed' and out['reason'] == 'illegal_context_prefix'
    assert out['prefix_failure']['failed_ply'] == 2
    assert out['prefix_failure']['legal_prefix_uci'] == ['e2e4']
    assert out['prefix_failure']['turn'] == 'black'
    assert 'observed' not in out


def test_branch_and_claim_line_are_separate_and_turns_are_enforced():
    out = result(variation(['c7c5', 'g1f3']), branch=['e2e4'], turn='black')
    assert out['status'] == 'supported' and out['variation']['plies'] == 2
    bad = result(variation(['e2e4', 'e2e3']))
    assert bad['status'] == 'contradicted' and bad['observed'] is False
    assert bad['variation']['failed_ply'] == 2 and bad['variation']['turn'] == 'black'
    assert result(variation(['e2e4', 'e2e3'], expected=False))['status'] == 'supported'


def test_pinned_geometry_includes_attack_but_never_legal_recapture():
    fen = '4r1k1/8/8/8/8/8/4R3/4K3 w - - 0 1'
    out = result(attack('e2', 'f2'), fen=fen)
    assert out['status'] == 'supported' and out['attacker_is_pinned'] is True
    assert 'Not legal capture/recapture' in out['scope']
    assert result(variation(['e2f2']), fen=fen)['status'] == 'contradicted'
    assert result(attack('e2', 'e8'), fen=fen)['observed'] is True


def test_geometry_respects_blockers_friendly_target_and_attacker_identity():
    assert result(attack('a1', 'a8'))['status'] == 'contradicted'
    friendly = result(attack('a1', 'a2'))
    assert friendly['observed'] is True and friendly['target_occupant'] == 'p'
    assert result(attack('f2', 'e8', 'pawn'))['status'] == 'contradicted'
    assert result(attack('a3', 'a8'))['status'] == 'unassessed'
    assert result(attack('a1', 'a8', 'queen'))['reason'] == 'attacker_identity_not_present'


def test_en_passant_legal_replay_and_capture_counts():
    fen = '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1'
    assert result(variation(['e5d6']), fen=fen)['status'] == 'supported'
    claim = {'kind': 'piece_count', 'color': 'black', 'piece_type': 'pawn', 'expected': 0}
    assert result(claim, fen=fen, branch=['e5d6'], turn='black')['observed'] == 0
    no_ep = fen.replace(' d6 ', ' - ')
    assert result(variation(['e5d6']), fen=no_ep)['status'] == 'contradicted'


def test_castling_uses_real_rook_motion_and_cannot_be_replayed_twice():
    fen = 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
    assert result(variation(['e1g1', 'e8c8']), fen=fen)['status'] == 'supported'
    out = result(attack('f1', 'f8'), fen=fen, branch=['e1g1'], turn='black')
    assert out['status'] == 'supported'
    assert result(variation(['e1g1']), fen=fen, branch=['e1g1', 'e8c8'])['status'] == 'contradicted'


def test_terminal_prefix_stops_and_mainline_never_validates_other_prose():
    fen = '6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1'
    good = result(variation(['g5d8']), fen=fen)
    assert good['status'] == 'supported'
    bad = result(variation(['g5d8', 'g8h8']), fen=fen)
    assert bad['variation']['reason'] == 'game_over' and bad['variation']['failed_ply'] == 2
    later = result(attack('f2', 'e8', 'pawn'), fen=fen, branch=['g5d8', 'g8h8'])
    assert later['status'] == 'unassessed'
    draw = '7k/8/8/8/8/8/R7/K7 w - - 150 76'
    assert result(variation(['a2a8']), fen=draw)['variation']['reason'] == 'game_over'


@pytest.mark.parametrize('claim', [
    {'kind': 'piece_count', 'color': 'white', 'piece_type': 'pawn', 'expected': True},
    {'kind': 'material_count', 'color': 'white', 'expected': {'pawn': 8}},
    {'kind': 'legal_variation', 'moves_uci': [], 'expected': True},
    {'kind': 'legal_variation', 'moves_uci': ['e2e2'], 'expected': True},
    {'kind': 'legal_variation', 'moves_uci': ['e2e4'], 'expected': True, 'engine_best': True},
    {'kind': 'geometric_attacks_square', 'expected': True},
    {'kind': 'why_best', 'expected': 'wins'},
])
def test_unsupported_predicates_abstain_without_crash_or_true(claim):
    assert result(claim)['status'] == 'unassessed'


@pytest.mark.parametrize('fen', ['bad', '8/8/8/8/8/8/8/8 w - - 0 1', chess.STARTING_FEN.replace(' KQkq ', ' HAha ')])
def test_invalid_root_is_unassessed_not_annotator_repaired(fen):
    assert result(fen=fen)['reason'] == 'invalid_or_unsupported_response_input'


def test_source_input_extra_future_fields_abstain_and_no_model_engine_or_process_imports(monkeypatch):
    raw, annotations = fixture();response = json.loads(raw)
    response['input']['fen_after'] = chess.STARTING_FEN
    raw = json.dumps(response).encode();annotations['response_sha256'] = audit.digest(raw)
    original = builtins.__import__
    def guard(name, *args, **kwargs):
        if name.split('.')[0] in {'torch', 'transformers', 'subprocess', 'bitsandbytes'} or name == 'chess.engine':
            raise AssertionError('No learned/engine/process import')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guard)
    assert audit.audit_response(raw, annotations)['claims'][0]['status'] == 'unassessed'
    before = copy.deepcopy(annotations)
    good_raw, good_annotations = fixture()
    assert audit.audit_response(good_raw, good_annotations)['summary']['supported'] == 1
    assert annotations == before


def test_empty_annotations_do_not_claim_zero_error_full_prose():
    raw, annotations = fixture();annotations['claims'] = []
    out = audit.audit_response(raw, annotations)
    assert out['summary']['supported_fraction_among_assessed'] is None
    assert out['whole_prose_coverage_established'] is False


def test_protocol_tampering_source_change_and_create_only_cli(tmp_path, monkeypatch):
    raw_protocol, protocol_sha = protocol()
    assert audit.verify_protocol(raw_protocol, protocol_sha)['contract'] == audit.CONTRACT
    with pytest.raises(audit.BindingError):audit.verify_protocol(raw_protocol+b' ', protocol_sha)
    changed = json.loads(raw_protocol);changed['implementation_sha256'] = '0'*64
    altered = json.dumps(changed).encode()
    with pytest.raises(audit.BindingError):audit.verify_protocol(altered, audit.digest(altered))
    response, annotations = fixture()
    files = {'response': response, 'annotations': json.dumps(annotations).encode(), 'protocol': raw_protocol}
    for name, content in files.items():(tmp_path/name).write_bytes(content)
    out = tmp_path/'out.json'
    argv = ['audit', '--response', str(tmp_path/'response'), '--annotations', str(tmp_path/'annotations'),
            '--protocol', str(tmp_path/'protocol'), '--protocol-sha256', protocol_sha, '--out', str(out)]
    monkeypatch.setattr(sys, 'argv', argv)
    audit.main()
    assert json.loads(out.read_text())['summary']['supported'] == 1
    assert json.loads(out.read_text())['response_pool_index'] == 0
    before = out.read_bytes()
    with pytest.raises(FileExistsError):audit.main()
    assert out.read_bytes() == before


def test_cli_rejects_unplanned_response_even_if_annotations_have_matching_hashes(tmp_path, monkeypatch):
    response, annotations = fixture(text='A different authored fixture.')
    raw_protocol, protocol_sha = protocol()
    for name, content in {'response': response, 'annotations': json.dumps(annotations).encode(), 'protocol': raw_protocol}.items():
        (tmp_path/name).write_bytes(content)
    out = tmp_path/'must-not-exist.json'
    monkeypatch.setattr(sys, 'argv', ['audit', '--response', str(tmp_path/'response'), '--annotations', str(tmp_path/'annotations'),
        '--protocol', str(tmp_path/'protocol'), '--protocol-sha256', protocol_sha, '--out', str(out)])
    with pytest.raises(audit.BindingError, match='outside the frozen protocol pool'):audit.main()
    assert not out.exists()
    bad = json.loads(raw_protocol);bad['response_pool']['responses'] *= 2
    raw = json.dumps(bad).encode()
    with pytest.raises(audit.BindingError, match='unique exact response pool'):audit.verify_protocol(raw, audit.digest(raw))


def test_bounded_json_file(tmp_path):
    path = tmp_path/'too-big';path.write_bytes(b' '*(audit.MAX_BYTES+1))
    with pytest.raises(audit.BindingError):audit.read_bounded(path)
