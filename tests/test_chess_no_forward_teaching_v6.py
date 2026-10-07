"""Synthetic offline v6 checks; no model, engine, or review-page call."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import chess_counterfactual_evidence as cf  # noqa: E402
import chess_no_forward_packet as no_forward  # noqa: E402
import chess_no_forward_teaching_v5 as v5  # noqa: E402
import chess_no_forward_teaching_v6 as teaching  # noqa: E402
import chess_tactical_hypothesis_v2 as tactical  # noqa: E402
import chess_user_game_no_forward_v1 as user_packet  # noqa: E402


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'


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

    def exact_encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        assert (pgn_sha, review_sha, page_sha, role) == (
            '1' * 64, '2' * 64, '3' * 64, 'played')
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', exact_encoder)
    return source


def proposal(alternative='c2e4'):
    return {'schema': v5.CLAIM_SCHEMA, 'kind': v5.CLAIM_KIND,
            'selected_uci': 'c2c3', 'alternative_uci': alternative}


def focus_for(packet_sha256, *, reply_uci='d7d4', reply_san='Qxd4'):
    return {'schema': teaching.FOCUS_SCHEMA,
            'source_packet_sha256': packet_sha256,
            'reply_uci': reply_uci, 'reply_san': reply_san}


def evaluate(binding, *, fen=FEN, alternative='c2e4', focused=True):
    raw, digest = packet_for(fen)
    return teaching.evaluate(raw, digest, cf.canonical(proposal(alternative)),
                             source_binding=binding,
                             focus_reply=focus_for(digest) if focused else None)


def board_after_line(*sans, fen=FEN):
    board = chess.Board(fen)
    for san in sans:
        board.push_san(san)
    return board


def test_generator_is_byte_for_byte_v5_and_contains_only_nine_pre_move_fields(binding):
    raw, digest = packet_for()
    v6_input = teaching.build_generator_input(raw, digest, source_binding=binding)
    assert v6_input == v5.build_generator_input(raw, digest, source_binding=binding)
    assert teaching.generator_messages(raw, digest, source_binding=binding) == (
        v5.generator_messages(raw, digest, source_binding=binding))
    projected = json.loads(v6_input)
    assert set(projected) == {'schema', 'source_packet_sha256', 'source', 'fen',
                              'side_to_move', 'selected_move', 'transition',
                              'engine_observation', 'assertion_kinds'}
    assert projected['schema'] == v5.INPUT_SCHEMA
    assert projected['assertion_kinds'] == [v5.CLAIM_KIND, 'abstention']
    for forbidden in ('c2e4', 'd7d4', 'Qxb7', 'Kxc7', 'post_move_fen', 'pv_uci',
                      'legal_reply_candidates', 'defenders', 'review_label'):
        assert forbidden not in v6_input.decode('utf-8')


def test_exact_practice_line_legal_replies_defenders_and_counterfactual(binding):
    chosen = board_after_line('Qc3', 'Qxd4', 'Qxc7+')
    other = board_after_line('Qe4', 'Qxd4', 'Qxb7+')
    assert [chosen.san(move) for move in chosen.legal_moves] == ['Kxc7']
    assert [other.san(move) for move in other.legal_moves] == ['Kd7']
    assert list(chosen.attackers(chess.WHITE, chess.C7)) == []
    assert list(other.attackers(chess.WHITE, chess.B7)) == [chess.F3]
    assert chess.Move.from_uci('c8c7') in chosen.legal_moves
    assert chess.Move.from_uci('c8b7') not in other.legal_moves
    without_bishop = other.copy(stack=False)
    without_bishop.remove_piece_at(chess.F3)
    assert chess.Move.from_uci('c8b7') in without_bishop.legal_moves
    result = evaluate(binding)
    assert result['decision'] == 'verified_queen_defense_contrast'
    assert result['defense_contrast_status'] == 'verified_unique_pair'
    assert result['model_alternative_uci'] == 'c2e4'
    assert result['defense_search_counts']['qualified_defense_pair_count'] == 1
    assert result['defense_comparison_scope'] == 'one_caller_supplied_shared_reply'
    assert result['caller_supplied_focus_reply']['reply_san'] == 'Qxd4'
    witness = result['defense_contrast']
    assert (witness['reply_uci'], witness['reply_san']) == ('d7d4', 'Qxd4')
    assert (witness['selected_capture']['san'],
            witness['alternative_capture']['san']) == ('Qxc7+', 'Qxb7+')
    assert witness['selected_capture']['captured_piece'] == 'pawn'
    assert witness['alternative_capture']['captured_piece'] == 'pawn'
    assert witness['selected_capture']['defenders'] == []
    assert witness['alternative_capture']['defenders'] == [
        {'square': 'f3', 'piece': 'bishop'}]
    assert witness['selected_capture']['legal_opponent_replies'] == [
        {'uci': 'c8c7', 'san': 'Kxc7'}]
    assert witness['alternative_capture']['legal_opponent_replies'] == [
        {'uci': 'c8d7', 'san': 'Kd7'}]
    assert witness['bishop_removal_makes_king_capture_legal'] is True
    assert witness['bishop_removal_king_capture_san'] == 'Kxb7'
    assert 'bishop on f3 protects b7' in result['teaching_text']
    assert 'Kxc7 legally takes the queen' in result['teaching_text']
    assert 'only legal reply' in result['teaching_text']
    assert result['quality_evaluated'] is False
    assert result['model_calls'] == result['engine_calls'] == 0


def test_both_queen_trades_reach_identical_board():
    selected = board_after_line('Qc3', 'Qxd4', 'Qxd4', 'Rxd4')
    alternative = board_after_line('Qe4', 'Qxd4', 'Qxd4', 'Rxd4')
    assert selected.fen() == alternative.fen()


def test_extra_defender_prevents_bishop_causal_claim(binding):
    board = chess.Board(FEN)
    board.set_piece_at(chess.A6, chess.Piece(chess.BISHOP, chess.WHITE))
    result = evaluate(binding, fen=board.fen())
    assert result['decision'] != 'verified_queen_defense_contrast'
    assert result['defense_contrast'] is None
    assert result['teaching_text'] is None or 'bishop on f3 protects' not in result['teaching_text']
    alternative = board_after_line('Qe4', 'Qxd4', fen=board.fen())
    capture = chess.Move.from_uci('e4b7')
    detail = teaching._capture_with_check(alternative, capture, chess.E4)
    assert detail['defenders'] == [
        {'square': 'f3', 'piece': 'bishop'}, {'square': 'a6', 'piece': 'bishop'}]
    assert teaching._sole_bishop_causes_king_capture_to_fail(
        alternative, capture, detail) is None


def test_defended_selected_destination_prevents_immediate_loss_claim(binding):
    board = chess.Board(FEN)
    board.remove_piece_at(chess.B1)
    board.set_piece_at(chess.C1, chess.Piece(chess.ROOK, chess.WHITE))
    result = evaluate(binding, fen=board.fen())
    assert result['decision'] != 'verified_queen_defense_contrast'
    selected = board_after_line('Qc3', 'Qxd4', 'Qxc7+', fen=board.fen())
    assert chess.C1 in selected.attackers(chess.WHITE, chess.C7)
    assert chess.Move.from_uci('c8c7') not in selected.legal_moves
    # The all-reply search can still find a different valid line: ...Nc2
    # places the knight between the rook on c1 and the queen's c7 square.
    all_replies = evaluate(binding, fen=board.fen(), focused=False)
    assert all_replies['decision'] == 'verified_queen_defense_contrast'
    assert all_replies['defense_contrast']['reply_san'] == 'Nc2'


def test_absent_bishop_and_different_capture_type_do_not_make_contrast(binding):
    without_bishop = chess.Board(FEN)
    without_bishop.remove_piece_at(chess.F3)
    no_defender = evaluate(binding, fen=without_bishop.fen())
    assert no_defender['decision'] != 'verified_queen_defense_contrast'
    assert no_defender['defense_contrast'] is None
    captured_knight = chess.Board(FEN)
    captured_knight.set_piece_at(chess.C7, chess.Piece(chess.KNIGHT, chess.BLACK))
    mismatch = evaluate(binding, fen=captured_knight.fen())
    assert mismatch['decision'] != 'verified_queen_defense_contrast'
    assert mismatch['defense_contrast'] is None


def test_nonchecking_capture_and_nonadjacent_king_do_not_qualify():
    selected = board_after_line('Qc3', 'Qxd4')
    alternative = board_after_line('Qe4', 'Qxd4')
    assert teaching._checked_pair(
        selected, alternative, chess.Move.from_uci('c3d4'),
        chess.Move.from_uci('e4d4'), 'd7d4', 'Qxd4') is None
    far_king = alternative.copy(stack=False)
    far_king.remove_piece_at(chess.C8)
    far_king.set_piece_at(chess.H8, chess.Piece(chess.KING, chess.BLACK))
    assert teaching._capture_with_check(
        far_king, chess.Move.from_uci('e4b7'), chess.E4) is None


def test_common_reply_requires_both_legality_and_identical_san():
    missing = chess.Board('7k/3q4/8/8/2QP4/8/8/6K1 w - - 0 1')
    positions, _ = teaching._common_reply_boards(
        missing, chess.Move.from_uci('c4c3'), chess.Move.from_uci('c4d5'))
    assert 'd7d4' not in [item[0] for item in positions]
    changed_san = chess.Board('7k/3q4/4p3/8/3P2K1/8/2Q5/8 w - - 0 1')
    chosen_after = changed_san.copy(stack=False)
    other_after = changed_san.copy(stack=False)
    chosen_after.push(chess.Move.from_uci('c2c3'))
    other_after.push(chess.Move.from_uci('c2e4'))
    reply = chess.Move.from_uci('d7d4')
    assert reply in chosen_after.legal_moves
    assert reply in other_after.legal_moves
    assert chosen_after.san(reply) != other_after.san(reply)
    positions, _ = teaching._common_reply_boards(
        changed_san, chess.Move.from_uci('c2c3'), chess.Move.from_uci('c2e4'))
    assert 'd7d4' not in [item[0] for item in positions]


def test_nonunique_legal_reply_cannot_be_described_as_only_reply(binding):
    board = chess.Board(FEN)
    board.remove_piece_at(chess.D8)
    result = evaluate(binding, fen=board.fen())
    if result['decision'] == 'verified_queen_defense_contrast':
        witness = result['defense_contrast']
        for branch in ('selected_capture', 'alternative_capture'):
            option = witness[branch]
            if len(option['legal_opponent_replies']) > 1:
                assert f'After {option["san"]}, Black\'s only legal reply' not in (
                    result['teaching_text'])
    else:
        assert result['defense_contrast'] is None


def test_real_unscoped_ambiguity_falls_back_without_convenient_reply(binding):
    result = evaluate(binding, focused=False)
    assert result['defense_contrast_status'] == 'ambiguous'
    assert result['defense_contrast'] is None
    assert result['defense_search_counts']['qualified_defense_pair_count'] > 1
    assert result['defense_comparison_scope'] == 'all_shared_replies'
    assert result['decision'] != 'verified_queen_defense_contrast'


def test_focus_requires_exact_packet_and_reply_and_never_enters_generator(binding):
    raw, digest = packet_for()
    for bad in (dict(focus_for(digest), source_packet_sha256='0' * 64),
                dict(focus_for(digest), reply_uci='not-a-move')):
        with pytest.raises(tactical.ClaimRejected):
            teaching.evaluate(raw, digest, cf.canonical(proposal()),
                              source_binding=binding, focus_reply=bad)
    wrong_san = teaching.evaluate(
        raw, digest, cf.canonical(proposal()), source_binding=binding,
        focus_reply=focus_for(digest, reply_san='Qxd4+'))
    assert wrong_san['defense_contrast_status'] == 'focused_reply_not_comparable'
    assert wrong_san['defense_contrast'] is None
    assert wrong_san['teaching_text'] is None
    assert wrong_san['witness'] is None
    assert b'd7d4' not in teaching.build_generator_input(
        raw, digest, source_binding=binding)


def test_focused_nd5_cannot_publish_v5_witness_from_qxd4(binding):
    raw, digest = packet_for()
    result = teaching.evaluate(
        raw, digest, cf.canonical(proposal()), source_binding=binding,
        focus_reply=focus_for(digest, reply_uci='e3d5', reply_san='Nd5'))
    assert result['caller_supplied_focus_reply']['reply_san'] == 'Nd5'
    assert result['defense_comparison_scope'] == 'one_caller_supplied_shared_reply'
    assert result['defense_contrast_status'] in (
        'no_qualified_pair', 'focused_reply_not_comparable')
    assert result['decision'] == 'evaluator_abstention'
    assert result['teaching_text'] is None
    assert result['witness'] is None
    assert result['generic_witness'] is None


def test_different_proposal_is_never_replaced_and_v5_shape_stays_strict(binding):
    other = evaluate(binding, alternative='c2b3')
    assert other['model_alternative_uci'] == 'c2b3'
    assert other['decision'] != 'verified_queen_defense_contrast'
    assert other['teaching_text'] is None or 'Qe4' not in other['teaching_text']
    raw, digest = packet_for()
    verbose = dict(proposal(), hypothesis='queen_can_move_to_e4')
    rejected = teaching.evaluate(raw, digest, cf.canonical(verbose),
                                 source_binding=binding)
    assert rejected['decision'] == 'rejected'
    assert rejected['reason'] == 'invalid_claim_shape'
    assert rejected['defense_contrast_status'] == 'not_evaluated'
    abstention = {'schema': v5.CLAIM_SCHEMA, 'kind': 'abstention'}
    abstained = teaching.evaluate(raw, digest, cf.canonical(abstention),
                                  source_binding=binding)
    assert abstained['decision'] == 'model_abstention'
    assert abstained['defense_contrast_status'] == 'not_evaluated'
