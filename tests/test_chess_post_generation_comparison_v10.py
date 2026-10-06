"""Offline v10 sidecar tests. Every paired result is fake; no engine/model call."""
from __future__ import annotations

import copy
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_capture_v9 as capture  # noqa: E402
import chess_no_forward_teaching_v9 as teaching  # noqa: E402
import chess_no_forward_teaching_v8 as teaching_v8  # noqa: E402
import chess_post_generation_comparison_v10 as v10  # noqa: E402


def _observation(board, uci, value, *, kind='cp', bound='exact'):
    move = chess.Move.from_uci(uci)
    return {
        'move_uci': uci, 'san': board.san(move),
        'score': {'type': kind, 'value': value, 'bound': bound,
                  'order': 'engine_score', 'perspective': 'side_to_move',
                  'side_to_move': chess.COLOR_NAMES[board.turn]},
        'depth': 14, 'nodes_observed': 50_000, 'pv_uci': [uci],
    }


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(v10, 'ROOT', tmp_path)
    run_dir = tmp_path / 'artifacts' / 'v9-frozen-run'
    case_dir = run_dir / 'ply57'
    case_dir.mkdir(parents=True)
    kind, fen, selected_uci = teaching_v8.CASES[57]
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': v10.user_packet.SCHEMA,
        'source': {'pgn_sha256': capture.PGN_SHA256,
                   'review_receipt_sha256': '2' * 64,
                   'review_page_sha256': '3' * 64, 'selected_ply': 57,
                   'move_role': 'played', 'use_role': v10.user_packet.USE_ROLE},
        'fen': fen, 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected_uci, 'san': board.san(selected)},
        'transition': {name: facts[name]
                       for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {
            'name': v10.ENGINE_NAME, 'sha256': v10.previous.ENGINE_SHA256,
            'score': {'type': 'cp', 'value': -45, 'bound': 'exact',
                      'order': 'engine_score', 'perspective': 'side_to_move',
                      'side_to_move': chess.COLOR_NAMES[board.turn]},
            'observation_only': True, 'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    packet_raw = cf.canonical(packet)
    binding = {'source': 'synthetic-test-only'}
    checker = {'decision': 'verified_typed_board_claim', 'case_kind': kind,
               'packet_sha256': cf.digest(packet_raw),
               'source_binding_sha256': cf.digest(cf.canonical(binding)),
               'witness': {'alternative_uci': 'a1b1'}}
    evaluation = {'checker': checker}
    row = {'ply': 57, 'case_kind': kind, 'status': 'captured',
           'model_identity': 'matched', 'evaluation': evaluation}
    manifest = {'source_packet_sha256': cf.digest(packet_raw),
                'source_binding': binding}
    plan = {'route': {'model_id': 'fixture-model'}}
    frozen_case = {'dir': case_dir, 'manifest': manifest, 'packet': packet_raw}
    monkeypatch.setattr(capture, 'verify_run',
                        lambda *_: {'rows': [row]})
    monkeypatch.setattr(capture, '_preflight',
                        lambda *_: (plan, {57: frozen_case}))
    for name, filename in v10.UPSTREAM.items():
        path = (run_dir if name == 'plan' else case_dir) / filename
        path.write_bytes((name + '\n').encode())
    protocol_raw = v10.freeze_protocol()
    input_value = {
        'schema': v10.INPUT_SCHEMA, 'v9_run_dir': str(run_dir), 'ply': 57,
        'protocol_sha256': cf.digest(protocol_raw),
        'upstream_sha256': {
            name: cf.file_digest((run_dir if name == 'plan' else case_dir) /
                                 filename)
            for name, filename in v10.UPSTREAM.items()},
    }
    return {'run_dir': run_dir, 'case_dir': case_dir, 'board': board,
            'packet': packet, 'protocol': protocol_raw, 'input': input_value,
            'checker': checker, 'row': row}


def _evaluate(case, search, *, input_value=None, protocol=None):
    return v10.evaluate(v10._canonical_line(input_value or case['input']),
                        protocol or case['protocol'], pair_search=search)


def test_protocol_pins_v10_and_entire_v9_closure(case):
    value = v10._protocol(case['protocol'])
    assert value['evaluator_source_sha256'] == cf.file_digest(Path(v10.__file__))
    assert value['dependency_closure_sha256'] == cf.digest(
        cf.canonical(capture._implementation_hashes()))
    assert len(v10.implementation_hashes()) == 24
    assert value['searches'] == 1
    assert value['automatic_retries'] == 0


def test_freeze_input_uses_sealed_v9_bytes_without_search(case):
    assert v10.freeze_input(case['run_dir'], 57, case['protocol']) == v10._canonical_line(
        case['input'])


def test_order_independent_pair_uses_only_accepted_witness(case):
    calls = []

    def search(board, roots, protocol):
        calls.append(([move.uci() for move in roots], protocol['requested_nodes']))
        return [_observation(board, 'a1b1', 15),
                _observation(board, 'a1c1', -30)]

    receipt = _evaluate(case, search)
    assert calls == [(['a1c1', 'a1b1'], 100_000)]
    assert receipt['source']['alternative_uci'] == 'a1b1'
    assert receipt['comparison']['status'] == 'ranked'
    assert receipt['comparison']['relation'] == 'alternative_higher'
    assert receipt['comparison']['delta_cp'] == 45
    assert 'bounded 100,000-node Stockfish search' in receipt['comparison']['display_sentence']
    assert receipt['counts'] == {'model_calls_v10': 0, 'engine_calls_v10': 1,
                                 'automatic_retries': 0}
    assert receipt['engine']['settings']['root_moves_uci'] == ['a1c1', 'a1b1']
    assert [item['move_uci'] for item in receipt['engine']['paired_observations']] == ['a1b1', 'a1c1']
    assert receipt['quality_evaluated'] is False


@pytest.mark.parametrize(('played', 'alternative', 'relation'), [
    (20, -3, 'played_higher'), (0, 0, 'equal')])
def test_score_sign_and_tie(case, played, alternative, relation):
    def search(board, *_):
        return [_observation(board, 'a1c1', played),
                _observation(board, 'a1b1', alternative)]

    receipt = _evaluate(case, search)
    assert receipt['comparison']['relation'] == relation
    assert receipt['comparison']['delta_cp'] == alternative - played


@pytest.mark.parametrize(('decision', 'kind', 'reason'), [
    ('model_abstention', 'rook_coordination', 'model_abstained'),
    ('rejected', 'rook_coordination', 'claim_rejected'),
    ('verified_typed_board_claim', 'passed_pawn', 'no_model_named_alternative'),
])
def test_zero_call_abstention(case, decision, kind, reason):
    case['checker']['decision'] = decision
    case['row']['case_kind'] = kind
    if kind == 'passed_pawn':
        # The pinned ply-93 case, like a real accepted passed-pawn claim,
        # names no alternative. Mock only the verified v9 case selection.
        case['checker']['case_kind'] = kind
        case['checker']['witness'] = {'pawn_square': 'b2'}
        original = v10.teaching_v8.CASES
        v10.teaching_v8.CASES = {**original, 57: (kind, *original[57][1:])}
    called = []

    def search(*_):
        called.append(1)
        raise AssertionError('engine_must_not_run')

    try:
        receipt = _evaluate(case, search)
    finally:
        if kind == 'passed_pawn':
            v10.teaching_v8.CASES = original
    assert called == []
    assert receipt['comparison']['reason'] == reason
    assert receipt['counts']['engine_calls_v10'] == 0


@pytest.mark.parametrize(('mutation', 'reason'), [
    ('upper', 'mate_or_bounded_score'),
    ('mate', 'mate_or_bounded_score'),
    ('perspective', 'perspective_mismatch'),
    ('missing', 'missing_or_duplicate_root'),
    ('duplicate', 'missing_or_duplicate_root'),
    ('bad_pv', 'invalid_pv'),
])
def test_one_call_abstention_without_retry(case, mutation, reason):
    calls = []

    def search(board, *_):
        calls.append(1)
        played = _observation(board, 'a1c1', -30)
        other = _observation(board, 'a1b1', 15)
        if mutation == 'upper':
            other['score']['bound'] = 'upper'
        elif mutation == 'mate':
            other['score']['type'] = 'mate'
        elif mutation == 'perspective':
            other['score']['side_to_move'] = 'black'
        elif mutation == 'missing':
            return [played]
        elif mutation == 'duplicate':
            return [played, copy.deepcopy(played)]
        elif mutation == 'bad_pv':
            other['pv_uci'].append('a1a8')
        return [played, other]

    receipt = _evaluate(case, search)
    assert calls == [1]
    assert receipt['comparison']['status'] == 'abstain'
    assert receipt['comparison']['reason'] == reason
    assert receipt['counts']['engine_calls_v10'] == 1
    assert receipt['counts']['automatic_retries'] == 0


def test_engine_exception_is_retained_without_retry(case):
    called = []

    def search(*_):
        called.append(1)
        raise RuntimeError('synthetic engine failure')

    receipt = _evaluate(case, search)
    assert called == [1]
    assert receipt['engine_error'] == {
        'stage': 'search', 'type': 'RuntimeError',
        'message': 'synthetic engine failure'}
    assert receipt['comparison']['reason'] == 'engine_failure'


@pytest.mark.parametrize('name', tuple(v10.UPSTREAM))
def test_upstream_byte_tamper_rejected_before_search(case, name):
    path = (case['run_dir'] if name == 'plan' else case['case_dir']) / v10.UPSTREAM[name]
    path.write_bytes(b'changed\n')

    def search(*_):
        raise AssertionError('engine_must_not_run')

    with pytest.raises(ValueError, match=f'v10_{name}_sha256_changed'):
        _evaluate(case, search)


def test_protocol_and_path_tamper_rejected_before_search(case, tmp_path):
    def search(*_):
        raise AssertionError('engine_must_not_run')

    protocol = bytearray(case['protocol'])
    protocol[-2] = ord('0') if protocol[-2] != ord('0') else ord('1')
    with pytest.raises(ValueError):
        _evaluate(case, search, protocol=bytes(protocol))
    bad = dict(case['input'], v9_run_dir=str(tmp_path / 'outside'))
    with pytest.raises(ValueError, match='v10_run_outside_project_artifacts'):
        _evaluate(case, search, input_value=bad)


def test_cli_confines_protocol_write_to_project_artifacts(case, tmp_path):
    outside = tmp_path / 'outside-protocol.json'
    with pytest.raises(ValueError, match='v10_cli_path_outside_project_artifacts'):
        v10.main(['freeze-protocol', '--output', str(outside)])
    assert not outside.exists()
    inside = tmp_path / 'artifacts' / 'protocol.json'
    assert v10.main(['freeze-protocol', '--output', str(inside)]) == 0
    assert inside.read_bytes() == case['protocol']


def test_v9_identity_mismatch_rejected_before_search(case):
    case['row']['model_identity'] = 'mismatch'

    def search(*_):
        raise AssertionError('engine_must_not_run')

    with pytest.raises(ValueError, match='v10_v9_result_not_verified_and_evaluated'):
        _evaluate(case, search)


@pytest.mark.parametrize(('scope', 'field', 'value'), [
    ('root', 'future_fen', 'forbidden'),
    ('root', 'game_review_label', 'great_move'),
    ('engine', 'pv_uci', ['a1b1']),
    ('engine', 'alternative_score', 80),
])
def test_v9_outbound_gate_rejects_evaluator_fields(case, scope, field, value):
    packet = case['packet']
    projection = teaching._projection(packet, cf.digest(cf.canonical(packet)))
    if scope == 'root':
        projection[field] = value
    else:
        projection['engine_observation'][field] = value
    # The nested v7 gate runs before any route fields or network action.
    with pytest.raises(ValueError):
        capture.build_request(cf.canonical(projection), {})
