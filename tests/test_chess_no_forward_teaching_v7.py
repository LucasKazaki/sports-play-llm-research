"""Synthetic v7 contract checks; no model, engine, or review-site call."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_v7 as teaching  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'
LESSON = ('If Black replies Qxd4, after Qc3 Qxc7+ permits Kxc7 to take the queen. '
          'After Qe4 Qxb7+ is protected by the bishop on f3, so Kxb7 is illegal. '
          'This is one conditional line; other replies and move quality are unchecked.')


def packet_for(fen=FEN, selected_uci='c2c3'):
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    facts = cf.transition_evidence(board, selected)
    packet = {
        'schema': user_packet.SCHEMA,
        'source': {'pgn_sha256': '1' * 64, 'review_receipt_sha256': '2' * 64,
                   'review_page_sha256': '3' * 64, 'selected_ply': 39,
                   'move_role': 'played', 'use_role': user_packet.USE_ROLE},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected.uci(), 'san': board.san(selected)},
        'transition': {name: facts[name] for name in no_forward.TRANSITION_FIELDS},
        'engine_observation': {'name': 'synthetic', 'sha256': '4' * 64,
                               'score': {'type': 'cp', 'value': -471,
                                         'bound': 'exact', 'order': 'engine_score',
                                         'perspective': 'side_to_move',
                                         'side_to_move': 'white'},
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
        'schema': tactical.BINDING_SCHEMA, 'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'), 'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': '1' * 64, 'review_sha256': '2' * 64,
        'page_sha256': '3' * 64, 'role': 'played',
    }

    def encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        assert (pgn_sha, review_sha, page_sha, role) == (
            '1' * 64, '2' * 64, '3' * 64, 'played')
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', encoder)
    return source


def claim(selected='c2c3', alternative='c2e4', protected='alternative',
          selected_capture='c3c7', alternative_capture='e4b7',
          reply='d7d4', defender='f3', lesson=LESSON):
    return {'schema': teaching.CLAIM_SCHEMA, 'kind': teaching.CLAIM_KIND,
            'selected_uci': selected, 'alternative_uci': alternative,
            'reply_uci': reply,
            'selected_capture_uci': selected_capture,
            'alternative_capture_uci': alternative_capture,
            'protected_branch': protected, 'defender_square': defender,
            'hypothesis': {'mechanism': teaching.MECHANISM,
                           'scope': 'one_shared_reply_only'},
            'lesson_draft': lesson}


def evaluate(binding, proposed=None, *, selected='c2c3', fen=FEN):
    raw, sha = packet_for(fen, selected)
    return teaching.evaluate(raw, sha,
                             cf.canonical(proposed or claim()),
                             source_binding=binding)


def test_generator_has_exactly_nine_pre_move_fields_and_no_answer(binding):
    raw, sha = packet_for()
    safe = teaching.build_generator_input(raw, sha, source_binding=binding)
    projected = json.loads(safe)
    assert set(projected) == {'schema', 'source_packet_sha256', 'source', 'fen',
                              'side_to_move', 'selected_move', 'transition',
                              'engine_observation', 'assertion_kinds'}
    assert projected['schema'] == teaching.INPUT_SCHEMA
    assert projected['assertion_kinds'] == [teaching.CLAIM_KIND, 'abstention']
    for forbidden in ('c2e4', 'd7d4', 'e4b7', 'f3 protects b7', 'pv_uci',
                      'post_move_fen', 'review_label', 'legal_reply_candidates'):
        assert forbidden not in safe.decode('utf-8')


def test_model_authored_forward_direction_requires_exact_legal_cause(binding):
    result = evaluate(binding)
    assert result['decision'] == 'verified_model_conditional_comparison'
    assert result['model_alternative_uci'] == 'c2e4'
    assert result['model_reply_uci'] == 'd7d4'
    assert result['protected_branch'] == 'alternative'
    assert result['defense_contrast']['alternative_capture']['defenders'] == [
        {'square': 'f3', 'piece': 'bishop'}]
    assert result['defense_contrast']['selected_capture']['king_capture_legal'] is True
    assert result['defense_contrast']['bishop_removal_king_capture_san'] == 'Kxb7'
    assert result['teaching_text'] == LESSON
    assert result['model_calls'] == result['engine_calls'] == 0
    assert result['quality_evaluated'] is False


def test_model_authored_reverse_direction_uses_selected_protected_branch(binding):
    reversed_claim = claim(selected='c2e4', alternative='c2c3',
                           protected='selected', selected_capture='e4b7',
                           alternative_capture='c3c7')
    result = evaluate(binding, reversed_claim, selected='c2e4')
    assert result['decision'] == 'verified_model_conditional_comparison'
    assert result['model_alternative_uci'] == 'c2c3'
    assert result['protected_branch'] == 'selected'
    assert result['defense_contrast']['selected_capture']['san'] == 'Qxb7+'
    assert result['defense_contrast']['selected_capture']['defenders'] == [
        {'square': 'f3', 'piece': 'bishop'}]
    assert result['defense_contrast']['alternative_capture']['san'] == 'Qxc7+'
    assert result['defense_contrast']['alternative_capture']['defenders'] == []
    assert result['teaching_text'] == LESSON


def test_false_prevents_qxd4_causal_claim_is_rejected(binding):
    false_lesson = LESSON.replace('If Black replies Qxd4, ',
                                  'Qe4 prevents Qxd4. If Black replies Qxd4, ')
    result = evaluate(binding, claim(lesson=false_lesson))
    assert result['decision'] == 'rejected'
    assert result['reason'] == 'unsupported_lesson_draft'
    assert result['teaching_text'] is None


def test_wrong_reply_or_capture_abstains_without_substitution(binding):
    for proposed, decision in ((claim(reply='e3d5'), 'rejected'),
                               (claim(selected_capture='c3d4'), 'evaluator_abstention')):
        result = evaluate(binding, proposed)
        assert result['decision'] == decision
        assert result['defense_contrast'] is None
        assert result['teaching_text'] is None
        assert result['model_reply_uci'] == proposed['reply_uci']


def test_wrong_branch_defender_or_hypothesis_rejects(binding):
    for proposed, reason in (
            (claim(protected='selected'), 'unverified_protected_branch'),
            (claim(defender='a6'), 'defender_square_mismatch'),
            (dict(claim(), hypothesis={'mechanism': 'prevents_qxd4',
                                      'scope': 'one_shared_reply_only'}),
             'unsupported_hypothesis')):
        result = evaluate(binding, proposed)
        assert result['decision'] == 'rejected'
        assert result['reason'] == reason
        assert result['teaching_text'] is None


def test_unverified_extra_defender_abstains(binding):
    board = chess.Board(FEN)
    board.set_piece_at(chess.A6, chess.Piece(chess.BISHOP, chess.WHITE))
    result = evaluate(binding, fen=board.fen())
    assert result['decision'] == 'evaluator_abstention'
    assert result['teaching_text'] is None


def test_abstention_and_malformed_shapes_are_distinct(binding):
    raw, sha = packet_for()
    abstain = {'schema': teaching.CLAIM_SCHEMA, 'kind': 'abstention'}
    result = teaching.evaluate(raw, sha, cf.canonical(abstain), source_binding=binding)
    assert result['decision'] == 'model_abstention'
    assert result['teaching_text'] is None
    for bad in (dict(abstain, reason='unknown'), dict(claim(), pv_uci=['d7d4'])):
        result = teaching.evaluate(raw, sha, cf.canonical(bad), source_binding=binding)
        assert result['decision'] == 'rejected'
        assert result['teaching_text'] is None


def test_changed_source_binding_blocks_before_claim(binding):
    raw, sha = packet_for()
    with pytest.raises(tactical.ClaimRejected):
        teaching.evaluate(raw, sha, cf.canonical(claim()),
                          source_binding=dict(binding, unexpected='x'))
