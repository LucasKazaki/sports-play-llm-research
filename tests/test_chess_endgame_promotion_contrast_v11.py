"""Synthetic V11 checker tests; the known-game case is development practice."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import chess.engine
import pytest

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_endgame_promotion_contrast_v11 as checker  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


def packet_for_ply93() -> tuple[bytes, str]:
    _, fen, selected_uci = checker.teaching_v8.CASES[93]
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {
            'pgn_sha256': checker.teaching_v8.PGN_SHA256,
            'review_receipt_sha256': '2' * 64,
            'review_page_sha256': '3' * 64,
            'selected_ply': 93, 'move_role': 'played',
            'use_role': user_packet.USE_ROLE,
        },
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected.uci(), 'san': board.san(selected)},
        'transition': {name: facts[name]
                       for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {
            'name': 'synthetic', 'sha256': '4' * 64,
            'score': {'type': 'cp', 'value': 0, 'bound': 'exact',
                      'order': 'engine_score',
                      'perspective': 'side_to_move',
                      'side_to_move': chess.COLOR_NAMES[board.turn]},
            'observation_only': True,
            'independently_reproduced': False,
        },
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    return raw, cf.digest(raw)


@pytest.fixture
def binding(tmp_path, monkeypatch):
    original, _ = packet_for_ply93()
    binding_value = {
        'schema': tactical.BINDING_SCHEMA,
        'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'),
        'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': checker.teaching_v8.PGN_SHA256,
        'review_sha256': '2' * 64, 'page_sha256': '3' * 64,
        'role': 'played',
    }

    def encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        if (pgn_sha, review_sha, page_sha, role) != (
                checker.teaching_v8.PGN_SHA256, '2' * 64,
                '3' * 64, 'played'):
            raise ValueError('synthetic_source_binding_changed')
        # Stable synthetic source reprojection catches changed allowed values.
        return original

    monkeypatch.setattr(user_packet, 'encode_packet', encoder)
    return binding_value


def claim(**updates):
    result = {
        'schema': checker.CLAIM_SCHEMA, 'kind': checker.KIND,
        'selected_uci': 'h8b8', 'alternative_uci': 'h8c8',
        'shared_reply_uci': 'b2b1q',
        'selected_capture_uci': 'b8b1', 'scope': checker.SCOPE,
    }
    result.update(updates)
    return result


def evaluate(binding, response=None):
    packet, sha = packet_for_ply93()
    return checker.evaluate(packet, sha,
                            cf.canonical(claim() if response is None else response),
                            source_binding=binding)


def test_known_game_asymmetry_is_one_conditional_board_fact(binding,
                                                            monkeypatch):
    model_calls = []

    def no_model(*_args, **_kwargs):
        model_calls.append('called')
        raise AssertionError('checker must not dispatch a model')

    def no_engine(*_args, **_kwargs):
        raise AssertionError('engine must not run')

    monkeypatch.setattr(checker, 'generator_messages', no_model)
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', no_engine)
    result = evaluate(binding)
    assert model_calls == []
    assert result['decision'] == 'verified_conditional_board_fact'
    assert result['reason'] is None
    assert result['witness']['shared_reply_uci'] == 'b2b1q'
    assert result['witness']['selected_capture_san'] == 'Rxb1'
    assert result['witness']['alternative_immediate_rook_captures'] == []
    assert result['teaching_text'] == (
        'After Rb8, if the opponent plays b1=Q, Rxb1 is a legal rook capture '
        'of the promoted piece. After Rc8 and the same legal reply, no '
        'immediate rook capture of that piece is legal. This is one '
        'conditional line; it does not establish that the reply is forced, '
        'that the capture is safe, or that either root move is better.')
    assert result['model_calls_v11'] == result['engine_calls_v11'] == 0
    assert result['quality_evaluated'] is False
    assert result['accounting'] == {
        'responses': 1, 'model_abstentions': 0,
        'evaluator_abstentions': 0, 'rejections': 0,
        'verified_conditional_board_facts': 1,
    }


def test_no_forward_projection_has_only_pre_move_fields(binding):
    packet, sha = packet_for_ply93()
    safe = checker.build_generator_input(packet, sha, source_binding=binding)
    projected = json.loads(safe)
    assert set(projected) == {
        'schema', 'source_packet_sha256', 'source', 'fen',
        'side_to_move', 'selected_move', 'transition',
        'engine_observation', 'assertion_kinds'}
    assert projected['schema'] == checker.INPUT_SCHEMA
    assert projected['assertion_kinds'] == [checker.KIND, 'abstention']
    assert projected['source_packet_sha256'] == sha
    for forbidden in ('pv_uci', 'post_move_fen', 'future_feature',
                      'review_label', 'human_annotation',
                      'alternative_uci', 'shared_reply_uci',
                      'selected_capture_uci', 'b2b1q', 'h8c8'):
        assert forbidden not in safe.decode('utf-8').lower()
    messages = checker.generator_messages(packet, sha, source_binding=binding)
    assert len(messages) == 2
    assert messages[1]['content'] == safe.decode('utf-8')
    assert 'b2b1q' not in messages[0]['content']
    assert 'h8c8' not in messages[0]['content']


@pytest.mark.parametrize(('scope', 'field', 'value'), [
    ('engine_observation', 'pv_uci', ['b2b1q']),
    ('engine_observation', 'post_move_fen', 'future'),
    ('transition', 'future_feature', 'promotion'),
    ('source', 'human_annotation', 'Rc8 bad'),
    ('selected_move', 'review_label', 'best'),
])
def test_nested_evaluator_fields_rejected_before_projection(
        binding, monkeypatch, scope, field, value):
    packet, _ = packet_for_ply93()
    changed = json.loads(packet)
    changed[scope][field] = value
    raw = cf.canonical(changed)
    calls = []

    def projection(*_args):
        calls.append('projected')
        raise AssertionError('unsafe data reached projection')

    monkeypatch.setattr(checker, '_projection', projection)
    with pytest.raises((tactical.ClaimRejected, ValueError)):
        checker.build_generator_input(raw, cf.digest(raw),
                                      source_binding=binding)
    assert calls == []


def test_wrong_source_ply_and_changed_allowed_value_fail_before_claim(binding):
    packet, sha = packet_for_ply93()
    with pytest.raises(tactical.ClaimRejected):
        checker.evaluate(packet, sha, cf.canonical(claim()),
                         source_binding=dict(binding, pgn_sha256='5' * 64))
    for edit in (
        lambda p: p['source'].update(selected_ply=57),
        lambda p: p['engine_observation']['score'].update(value=12),
        lambda p: p['selected_move'].update(uci='h8c8'),
    ):
        changed = json.loads(packet)
        edit(changed)
        raw = cf.canonical(changed)
        with pytest.raises(tactical.ClaimRejected):
            checker.evaluate(raw, cf.digest(raw), cf.canonical(claim()),
                             source_binding=binding)


@pytest.mark.parametrize(('response', 'reason'), [
    (b'{"schema":"chess-endgame-promotion-contrast-output/v11",'
     b'"kind":"abstention","kind":"promotion_contrast"}',
     'duplicate_json_key'),
    (b'{"schema":"chess-endgame-promotion-contrast-output/v11",'
     b'"kind":"abstention","extra":1e999}',
     'invalid_json_number'),
    (b'{"schema":"chess-endgame-promotion-contrast-output/v11",'
     b'"kind":"abstention","extra":NaN}',
     'invalid_json_constant'),
    (b'not-json', 'invalid_response_json'),
    (b'{"schema":"chess-endgame-promotion-contrast-output/v11",'
     b'"kind":"abstention","extra":' + b'[' * 1300 + b']' * 1300 + b'}',
     'invalid_response_json'),
])
def test_malformed_duplicate_nonfinite_and_deep_json_rejected(
        binding, response, reason):
    packet, sha = packet_for_ply93()
    result = checker.evaluate(packet, sha, response, source_binding=binding)
    assert result['decision'] == 'rejected'
    assert result['reason'] == reason
    assert result['response_sha256'] == cf.digest(response)
    assert result['witness'] is result['teaching_text'] is None


@pytest.mark.parametrize(('updates', 'reason'), [
    ({'alternative_uci': 'h8b8'}, 'alternative_not_distinct_same_rook'),
    ({'alternative_uci': 'h8e5'}, 'illegal_model_alternative'),
    ({'alternative_uci': 'a4a2'}, 'illegal_model_alternative'),
    ({'shared_reply_uci': 'a4a2'}, 'shared_reply_not_promotion'),
    ({'selected_capture_uci': 'b8a8'},
     'selected_capture_not_promoted_piece'),
    ({'selected_capture_uci': 'h8b1'}, 'illegal_selected_capture'),
])
def test_invalid_named_branches_reject_without_lesson(binding, updates,
                                                       reason):
    result = evaluate(binding, claim(**updates))
    assert result['decision'] == 'rejected'
    assert result['reason'] == reason
    assert result['teaching_text'] is result['witness'] is None
    assert result['accounting']['rejections'] == 1


def test_legal_underpromotion_is_checked_without_queen_assumption(binding):
    result = evaluate(binding, claim(shared_reply_uci='b2b1n'))
    assert result['decision'] == 'verified_conditional_board_fact'
    assert result['witness']['promoted_piece'] == 'N'
    assert result['witness']['selected_capture_san'] == 'Rxb1'


@pytest.mark.parametrize('extra', [
    {'forced': True}, {'safe': True}, {'ranking': 'Rc8 is worse'},
    {'stockfish_intent': 'Stockfish wants Rb8'},
    {'lesson_draft': 'Rc8 loses the game'},
])
def test_unsupported_causal_quality_claims_rejected(binding, extra):
    result = evaluate(binding, dict(claim(), **extra))
    assert result['decision'] == 'rejected'
    assert result['reason'] == 'invalid_claim_shape'
    assert result['teaching_text'] is None


def test_wrong_scope_and_model_abstention_accounted(binding):
    wrong = evaluate(binding, claim(scope='forced_or_best'))
    assert wrong['decision'] == 'rejected'
    assert wrong['reason'] == 'unsupported_scope'
    abstain = evaluate(binding, {'schema': checker.CLAIM_SCHEMA,
                                 'kind': 'abstention'})
    assert abstain['decision'] == 'model_abstention'
    assert abstain['reason'] == 'model_abstained'
    assert abstain['teaching_text'] is abstain['witness'] is None
    assert abstain['accounting']['model_abstentions'] == 1


def synthetic_board() -> chess.Board:
    # Both b-file rook roots leave b2-b1=Q legal; both can then capture on b1.
    board = chess.Board('1R6/8/8/8/k7/7K/1p6/8 w - - 0 1')
    assert board.is_valid()
    return board


def test_reply_legal_only_on_one_branch_rejects():
    board = synthetic_board()
    selected = chess.Move.from_uci('b8b7')
    assert selected in board.legal_moves
    # Rxb2 removes the pawn, so b2-b1=Q no longer exists in that branch.
    proposed = claim(selected_uci='b8b7', alternative_uci='b8b2',
                     selected_capture_uci='b7b1')
    with pytest.raises(tactical.ClaimRejected,
                       match='reply_not_legal_after_alternative'):
        checker._contrast(board, selected, proposed)


def test_same_immediate_rook_capture_causes_evaluator_abstention():
    board = synthetic_board()
    selected = chess.Move.from_uci('b8b7')
    proposed = claim(selected_uci='b8b7', alternative_uci='b8b6',
                     selected_capture_uci='b7b1')
    witness, text, reason = checker._contrast(board, selected, proposed)
    assert witness is text is None
    assert reason == 'alternative_has_immediate_rook_capture'


def test_same_capture_is_counted_as_evaluator_abstention(binding,
                                                         monkeypatch):
    board = synthetic_board()
    selected = chess.Move.from_uci('b8b7')
    raw, sha = packet_for_ply93()
    packet = json.loads(raw)
    monkeypatch.setattr(checker, '_verified_case',
                        lambda *_args: (packet, board, selected))
    proposed = claim(selected_uci='b8b7', alternative_uci='b8b6',
                     selected_capture_uci='b7b1')
    result = checker.evaluate(raw, sha, cf.canonical(proposed),
                              source_binding=binding)
    assert result['decision'] == 'evaluator_abstention'
    assert result['reason'] == 'alternative_has_immediate_rook_capture'
    assert result['witness'] is result['teaching_text'] is None
    assert result['accounting']['evaluator_abstentions'] == 1


def test_mirrored_side_control_replays_opposite_promotion():
    original = chess.Board(checker.teaching_v8.CASES[93][1])
    board = original.mirror()
    assert board.is_valid() and board.turn == chess.BLACK
    selected = chess.Move.from_uci('h1b1')
    proposed = claim(selected_uci='h1b1', alternative_uci='h1c1',
                     shared_reply_uci='b7b8q', selected_capture_uci='b1b8')
    witness, text, reason = checker._contrast(board, selected, proposed)
    assert reason is None
    assert witness['shared_reply_uci'] == 'b7b8q'
    assert witness['selected_capture_uci'] == 'b1b8'
    assert witness['alternative_immediate_rook_captures'] == []
    assert 'This is one conditional line' in text
