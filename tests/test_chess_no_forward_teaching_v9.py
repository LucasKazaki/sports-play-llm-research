"""Synthetic v9 source-bound checks; no model, engine, or site call."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_v8 as v8  # noqa: E402
import chess_no_forward_teaching_v9 as teaching  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


def packet_for(ply: int):
    _, fen, selected_uci = v8.CASES[ply]
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {'pgn_sha256': v8.PGN_SHA256,
                   'review_receipt_sha256': '2' * 64,
                   'review_page_sha256': '3' * 64,
                   'selected_ply': ply, 'move_role': 'played',
                   'use_role': user_packet.USE_ROLE},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected.uci(), 'san': board.san(selected)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'name': 'synthetic', 'sha256': '4' * 64,
                               'score': {'type': 'cp', 'value': 0,
                                         'bound': 'exact', 'order': 'engine_score',
                                         'perspective': 'side_to_move',
                                         'side_to_move': chess.COLOR_NAMES[board.turn]},
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    return raw, cf.digest(raw)


@pytest.fixture
def binding(tmp_path, monkeypatch):
    source = {
        'schema': tactical.BINDING_SCHEMA,
        'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'),
        'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': v8.PGN_SHA256,
        'review_sha256': '2' * 64, 'page_sha256': '3' * 64,
        'role': 'played',
    }

    def encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        if (pgn_sha, review_sha, page_sha, role) != (
                v8.PGN_SHA256, '2' * 64, '3' * 64, 'played'):
            return b'changed_source'
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', encoder)
    return source


def claim(ply: int):
    kind, _, selected = v8.CASES[ply]
    result = {'schema': teaching.CLAIM_SCHEMA, 'kind': kind,
              'selected_uci': selected, 'scope': teaching.SCOPE}
    result.update({
        33: {'attacker_square': 'c3', 'target_square': 'c3',
             'alternative_uci': 'a1c1', 'alternative_target_square': 'c3',
             'conditional_reply_uci': 'c3d1'},
        46: {'attacked_queen_square': 'c3',
             'reply_uci': 'c3d4', 'recapture_uci': 'd8d4'},
        57: {'supported_rook_square': 'c3', 'target_pawn_square': 'c6',
             'alternative_uci': 'a1b1', 'open_file': 'b'},
        93: {'pawn_square': 'b2', 'conditional_line': {
             'reply_uci': 'a4a2', 'capture_uci': 'b8b2',
             'recapture_uci': 'a2b2'}},
    }[ply])
    return result


def evaluate(binding, ply: int, proposed=None):
    raw, sha = packet_for(ply)
    return teaching.evaluate(raw, sha, cf.canonical(proposed or claim(ply)),
                             source_binding=binding)


@pytest.mark.parametrize('ply', [33, 46, 57, 93])
def test_four_typed_claims_use_board_replay_only(binding, ply):
    result = evaluate(binding, ply)
    assert result['decision'] == 'verified_typed_board_claim'
    assert result['case_kind'] == result['model_kind'] == claim(ply)['kind']
    assert result['witness'] and result['teaching_text']
    assert result['model_calls'] == result['engine_calls'] == 0
    assert result['comparison']['status'] == 'abstain'
    assert result['comparison']['delta_cp'] is None
    assert result['quality_evaluated'] is False
    for forbidden in (' is best', ' is worse', 'Stockfish chose',
                      'forced continuation', ' wins '):
        assert forbidden not in result['teaching_text']


def test_queen_alternative_and_conditional_capture_are_checked(binding):
    result = evaluate(binding, 33)
    witness = result['witness']
    assert witness['alternative_uci'] == 'a1c1'
    assert witness['alternative_san'] == 'Rc1'
    assert witness['conditional_reply_san'] == 'Nxd1'
    assert 'leaves the queen' in result['teaching_text']
    assert 'one legal reply' in result['teaching_text']
    assert 'neither move is ranked' in result['teaching_text']
    no_line = evaluate(binding, 33,
                       dict(claim(33), conditional_reply_uci=None))
    assert no_line['decision'] == 'verified_typed_board_claim'
    assert no_line['witness']['conditional_reply_uci'] is None
    assert 'Nxd1' not in no_line['teaching_text']


@pytest.mark.parametrize('updates,reason', [
    ({'alternative_uci': 'd1b3'}, 'unverified_nonqueen_alternative'),
    ({'alternative_uci': 'a1a2'}, 'alternative_does_not_attack_target'),
    ({'alternative_target_square': 'd6'}, 'alternative_does_not_attack_target'),
    ({'conditional_reply_uci': 'd7c6'}, 'unverified_queen_capture_reply'),
    ({'conditional_reply_uci': 'c3a2'}, 'unverified_queen_capture_reply'),
    ({'conditional_reply_uci': 'g1h2'}, 'illegal_model_reply'),
])
def test_false_queen_alternative_or_reply_never_displays(binding, updates, reason):
    result = evaluate(binding, 33, dict(claim(33), **updates))
    assert result['decision'] == 'rejected'
    assert result['reason'] == reason
    assert result['teaching_text'] is None


def test_rook_open_file_choice_has_no_rank_or_causal_claim(binding):
    result = evaluate(binding, 57)
    assert result['witness']['alternative_san'] == 'Rb1'
    assert 'open b-file' in result['teaching_text']
    assert 'neither move is ranked' in result['teaching_text']
    assert 'inspect pawn-free files' in result['teaching_text']
    for updates in ({'alternative_uci': 'a1a2', 'open_file': 'a'},
                    {'alternative_uci': 'a1b1', 'open_file': 'c'},
                    {'target_pawn_square': 'e6'}):
        rejected = evaluate(binding, 57, dict(claim(57), **updates))
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


def test_capture_and_passer_lines_remain_conditional(binding):
    trade = evaluate(binding, 46)
    assert trade['witness']['reply_san'] == 'Qxd4'
    assert trade['witness']['recapture_san'] == 'Rxd4'
    assert 'other legal replies' in trade['teaching_text']
    assert 'count legal replies' in trade['teaching_text']
    passer = evaluate(binding, 93)
    assert passer['witness']['conditional_line']['recapture_san'] == 'Rxb2'
    assert 'does not prove a safe capture' in passer['teaching_text']
    assert 'replay a reply and recapture' in passer['teaching_text']
    for ply, updates in ((46, {'recapture_uci': 'h8d8'}),
                         (93, {'conditional_line': {'reply_uci': 'a4a2',
                           'capture_uci': 'b8b2', 'recapture_uci': 'c5b4'}})):
        rejected = evaluate(binding, ply, dict(claim(ply), **updates))
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


@pytest.mark.parametrize('ply', [33, 46, 57, 93])
def test_projection_remains_nine_pre_move_fields(binding, ply):
    raw, sha = packet_for(ply)
    safe = teaching.build_generator_input(raw, sha, source_binding=binding)
    projected = json.loads(safe)
    assert set(projected) == {'schema', 'source_packet_sha256', 'source',
                              'fen', 'side_to_move', 'selected_move',
                              'transition', 'engine_observation',
                              'assertion_kinds'}
    assert projected['schema'] == teaching.INPUT_SCHEMA
    assert projected['assertion_kinds'] == list(teaching.KINDS)
    assert projected['source_packet_sha256'] == sha
    for forbidden in ('pv_uci', 'post_move_fen', 'review_label',
                      'legal_reply_candidates', 'alternative_score',
                      'chesscom_card', 'expected_mechanism'):
        assert forbidden not in safe.decode('utf-8').lower()


@pytest.mark.parametrize('field,value', [
    ('pv_uci', ['d7d4']),
    ('post_move_fen', 'future'),
    ('continuation', ['c3d1']),
    ('review_label', 'inaccuracy'),
    ('alternative_score', 99),
    ('future_feature', 'threat'),
    ('human_annotation', 'move bad'),
    ('chesscom_card', 'best'),
])
def test_nested_hidden_fields_fail_preflight(binding, field, value):
    raw, _ = packet_for(33)
    packet = json.loads(raw)
    packet['engine_observation'][field] = value
    changed = cf.canonical(packet)
    with pytest.raises((tactical.ClaimRejected, ValueError)):
        teaching.build_generator_input(changed, cf.digest(changed),
                                       source_binding=binding)


def test_wrong_source_case_and_output_scope_fail(binding):
    raw, sha = packet_for(33)
    with pytest.raises(tactical.ClaimRejected):
        teaching.evaluate(raw, sha, cf.canonical(claim(33)),
                          source_binding=dict(binding, pgn_sha256='5' * 64))
    packet = json.loads(raw)
    packet['source']['selected_ply'] = 46
    changed = cf.canonical(packet)
    with pytest.raises(tactical.ClaimRejected):
        teaching.evaluate(changed, cf.digest(changed), cf.canonical(claim(33)),
                          source_binding=binding)
    for updates in ({'kind': 'passed_pawn'}, {'selected_uci': 'd1b3'},
                    {'scope': 'best_move'}, {'lesson_draft': 'Rc1 loses'}):
        result = teaching.evaluate(raw, sha,
                                   cf.canonical(dict(claim(33), **updates)),
                                   source_binding=binding)
        assert result['decision'] == 'rejected'
        assert result['teaching_text'] is None


def test_malformed_or_extra_claims_fail_closed_with_raw_hash(binding):
    raw, sha = packet_for(33)
    responses = (
        b'{"schema":"chess-no-forward-teaching-output/v9",'
        b'"kind":"abstention","kind":"queen_escape"}',
        b'{"schema":"chess-no-forward-teaching-output/v9",'
        b'"kind":"abstention","overflow":1e999}',
        b'{"schema":"chess-no-forward-teaching-output/v9",'
        b'"kind":"abstention","overflow":NaN}',
        b'{"schema":"chess-no-forward-teaching-output/v9",'
        b'"kind":"abstention","extra":' + b'[' * 1300 + b']' * 1300 + b'}',
    )
    for response in responses:
        result = teaching.evaluate(raw, sha, response, source_binding=binding)
        assert result['decision'] == 'rejected'
        assert result['response_sha256'] == cf.digest(response)
        assert result['teaching_text'] is None
    abstention = teaching.evaluate(
        raw, sha, cf.canonical({'schema': teaching.CLAIM_SCHEMA,
                                'kind': 'abstention'}), source_binding=binding)
    assert abstention['decision'] == 'model_abstention'
    assert abstention['teaching_text'] is None


def test_evaluator_score_gate_abstains_on_bound_and_defers_exact_pair():
    score = {'type': 'cp', 'value': -235, 'bound': 'exact',
             'order': 'engine_score', 'perspective': 'side_to_move',
             'side_to_move': 'white'}
    bounded = dict(score, value=-87, bound='upper')
    outcome = teaching.comparison_admissibility(score, bounded)
    assert outcome == {'status': 'abstain', 'reason': 'mate_or_bounded_score',
                       'delta_cp': None}
    exact = teaching.comparison_admissibility(score,
                                               dict(score, value=-87))
    assert exact == {'status': 'deferred',
                     'reason': 'verified_paired_evaluator_receipt_required',
                     'delta_cp': None}
    assert teaching.comparison_admissibility(score, None)['status'] == 'abstain'
    with pytest.raises(ValueError):
        teaching.comparison_admissibility(score,
                                           dict(score, side_to_move='black'))
