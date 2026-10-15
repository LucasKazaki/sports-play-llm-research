"""Synthetic v8 replay and admission tests; no model, engine, or site call."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_v8 as teaching  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


def packet_for(ply: int):
    _, fen, selected_uci = teaching.CASES[ply]
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {'pgn_sha256': teaching.PGN_SHA256,
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
        'pgn_sha256': teaching.PGN_SHA256,
        'review_sha256': '2' * 64, 'page_sha256': '3' * 64,
        'role': 'played',
    }

    def encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        if (pgn_sha, review_sha, page_sha, role) != (
                teaching.PGN_SHA256, '2' * 64, '3' * 64, 'played'):
            return b'changed_source'
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', encoder)
    return source


def claim(ply: int):
    kind, _, selected = teaching.CASES[ply]
    result = {'schema': teaching.CLAIM_SCHEMA, 'kind': kind,
              'selected_uci': selected, 'scope': teaching.SCOPE}
    result.update({
        33: {'attacker_square': 'c3', 'target_square': 'c3'},
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
def test_four_model_typed_mechanisms_replay_without_model_or_engine(binding, ply):
    result = evaluate(binding, ply)
    assert result['decision'] == 'verified_typed_board_claim'
    assert result['case_kind'] == result['model_kind'] == claim(ply)['kind']
    assert result['witness'] is not None
    assert result['teaching_text']
    assert result['model_calls'] == result['engine_calls'] == 0
    assert result['quality_evaluated'] is False
    for forbidden in (' is best', ' is worse', 'Stockfish chose',
                      'forced continuation', ' wins '):
        assert forbidden not in result['teaching_text']


def test_queen_threat_direction_and_nonforced_counterattack(binding):
    result = evaluate(binding, 33)
    assert result['witness']['attacker_square'] == 'c3'
    assert 'queen on d1' in result['teaching_text']
    assert 'forced win' in result['teaching_text']
    for wrong, reason in ((dict(claim(33), attacker_square='d6'),
                           'unverified_queen_threat'),
                          (dict(claim(33), target_square='d6'),
                           'unverified_queen_counterattack')):
        rejected = evaluate(binding, 33, wrong)
        assert rejected['decision'] == 'rejected'
        assert rejected['reason'] == reason
        assert rejected['teaching_text'] is None


def test_checking_capture_conditional_trade_does_not_force_reply(binding):
    result = evaluate(binding, 46)
    assert result['witness']['legal_reply_count'] == 5
    assert result['witness']['reply_san'] == 'Qxd4'
    assert result['witness']['recapture_san'] == 'Rxd4'
    assert 'other legal replies' in result['teaching_text']
    for wrong in (dict(claim(46), attacked_queen_square='a4'),
                  dict(claim(46), reply_uci='g1h2'),
                  dict(claim(46), recapture_uci='h8d8')):
        rejected = evaluate(binding, 46, wrong)
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


def test_rook_coordination_has_model_chosen_open_file_without_ranking(binding):
    result = evaluate(binding, 57)
    assert result['witness']['alternative_uci'] == 'a1b1'
    assert result['witness']['alternative_san'] == 'Rb1'
    assert 'neither move is ranked' in result['teaching_text']
    for wrong in (dict(claim(57), supported_rook_square='a1'),
                  dict(claim(57), target_pawn_square='e6'),
                  dict(claim(57), open_file='a'),
                  dict(claim(57), alternative_uci='a1a2', open_file='a')):
        rejected = evaluate(binding, 57, wrong)
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


def test_passer_attack_and_optional_named_recapture(binding):
    result = evaluate(binding, 93)
    assert result['witness']['conditional_line']['capture_san'] == 'Rxb2'
    assert result['witness']['conditional_line']['recapture_san'] == 'Rxb2'
    assert 'does not prove a safe capture' in result['teaching_text']
    without_line = evaluate(binding, 93, dict(claim(93), conditional_line=None))
    assert without_line['decision'] == 'verified_typed_board_claim'
    assert without_line['witness']['conditional_line'] is None
    assert 'whether the pawn can be captured safely' in without_line['teaching_text']
    for wrong in (dict(claim(93), pawn_square='c6'),
                  dict(claim(93), conditional_line={
                      'reply_uci': 'a4a2', 'capture_uci': 'b8b2',
                      'recapture_uci': 'c5b4'}),
                  dict(claim(93), conditional_line={
                      'reply_uci': 'a4a2', 'capture_uci': 'b8b2',
                      'recapture_uci': 'a2b2', 'forced': True})):
        rejected = evaluate(binding, 93, wrong)
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


@pytest.mark.parametrize('ply', [33, 46, 57, 93])
def test_generator_projection_is_exactly_nine_fields_without_future_data(binding, ply):
    raw, sha = packet_for(ply)
    safe = teaching.build_generator_input(raw, sha, source_binding=binding)
    projected = json.loads(safe)
    assert set(projected) == {'schema', 'source_packet_sha256', 'source',
                              'fen', 'side_to_move', 'selected_move',
                              'transition', 'engine_observation',
                              'assertion_kinds'}
    assert projected['schema'] == teaching.INPUT_SCHEMA
    assert projected['assertion_kinds'] == list(teaching.KINDS)
    for forbidden in ('pv_uci', 'post_move_fen', 'review_label',
                      'legal_reply_candidates', 'alternative_score'):
        assert forbidden not in safe.decode('utf-8')


def test_prohibited_source_fields_fail_before_projection(binding):
    raw, _ = packet_for(33)
    packet = json.loads(raw)
    packet['engine_observation']['pv_uci'] = ['d7d4']
    changed = cf.canonical(packet)
    with pytest.raises((tactical.ClaimRejected, ValueError)):
        teaching.build_generator_input(changed, cf.digest(changed),
                                       source_binding=binding)


def test_exact_claim_shape_direction_scope_and_abstention(binding):
    raw, sha = packet_for(33)
    abstain = {'schema': teaching.CLAIM_SCHEMA, 'kind': 'abstention'}
    result = teaching.evaluate(raw, sha, cf.canonical(abstain),
                               source_binding=binding)
    assert result['decision'] == 'model_abstention'
    assert result['teaching_text'] is None
    for wrong in (dict(claim(33), kind='passed_pawn'),
                  dict(claim(33), selected_uci='d1b3'),
                  dict(claim(33), scope='best_move'),
                  dict(claim(33), lesson_draft='Qc2 is best'),
                  dict(abstain, reason='quiet')):
        rejected = teaching.evaluate(raw, sha, cf.canonical(wrong),
                                     source_binding=binding)
        assert rejected['decision'] == 'rejected'
        assert rejected['teaching_text'] is None


def test_duplicate_nonfinite_and_deep_json_fail_closed(binding):
    raw, sha = packet_for(33)
    responses = (
        b'{"schema":"chess-no-forward-teaching-output/v8",'
        b'"kind":"abstention","kind":"queen_escape"}',
        b'{"schema":"chess-no-forward-teaching-output/v8",'
        b'"kind":"abstention","overflow":1e999}',
        b'{"schema":"chess-no-forward-teaching-output/v8",'
        b'"kind":"abstention","overflow":NaN}',
        b'{"schema":"chess-no-forward-teaching-output/v8",'
        b'"kind":"abstention","extra":' + b'[' * 1300 + b']' * 1300 + b'}',
    )
    for response in responses:
        result = teaching.evaluate(raw, sha, response, source_binding=binding)
        assert result['decision'] == 'rejected'
        assert result['response_sha256'] == cf.digest(response)
        assert result['teaching_text'] is None


def test_wrong_case_or_source_binding_cannot_be_repurposed(binding):
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
