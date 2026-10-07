"""Synthetic evaluator controls only; no engine, model or quality measurement."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_packet as lichess_packet
import chess_tactical_hypothesis_v2 as tactical
import chess_user_game_no_forward_v1 as user_packet


def source_packet(fen=chess.STARTING_FEN, selected_uci='e2e4', *, user=False):
    """An exact-shape fixture; source encoders are mocked in the fixture below."""
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    assert board.is_valid() and selected in board.legal_moves
    transition = cf.transition_evidence(board, selected)
    score = {'type': 'centipawn', 'value': 0, 'perspective': 'white',
             'side_to_move': chess.COLOR_NAMES[board.turn], 'bound': 'exact',
             'order': 1}
    if user:
        source = {'pgn_sha256': '1' * 64, 'review_receipt_sha256': '2' * 64,
                  'review_page_sha256': '3' * 64, 'selected_ply': 1,
                  'move_role': 'played', 'use_role': user_packet.USE_ROLE}
        observation = {'name': 'synthetic', 'sha256': '0' * 64, 'score': score,
                       'observation_only': True, 'independently_reproduced': False}
        schema = user_packet.SCHEMA
    else:
        source = {field: 'synthetic-fixture' for field in lichess_packet.SOURCE_FIELDS}
        observation = {'evidence_id': 'synthetic', 'engine_sha256': '0' * 64,
                       'score': score, 'observation_only': True,
                       'independently_reproduced': False}
        schema = lichess_packet.SCHEMA
    packet = {
        'schema': schema, 'source': source, 'fen': board.fen(),
        'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected_uci, 'san': board.san(selected)},
        'transition': {key: transition[key] for key in lichess_packet.TRANSITION_FIELDS},
        'engine_observation': observation,
        'concept_vocabulary': list(lichess_packet.CONCEPTS),
        'assertion_kinds': list(lichess_packet.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    return raw, cf.digest(raw)


def claim(candidate, continuation, kind, actor, square, piece, ply):
    return {
        'schema': tactical.CLAIM_SCHEMA, 'kind': 'tactical_hypothesis',
        'candidate_uci': candidate, 'continuation_uci': continuation,
        'event': {'kind': kind, 'actor': actor,
                  'target': {'square': square, 'piece': piece}, 'ply': ply},
        'modality': 'possible_if_line', 'uncertainty': 'other_replies_unchecked',
    }


@pytest.fixture
def source_binding(tmp_path, monkeypatch):
    """Require the encoder call, with no actual source, engine or model call."""
    typed = tmp_path / 'typed.json'
    typed.write_text('{}', encoding='utf-8')
    binding = {
        'schema': tactical.BINDING_SCHEMA,
        'packet_schema': lichess_packet.SCHEMA,
        'data_root': str(tmp_path),
        'source_receipt_path': str(tmp_path / 'receipt.json'),
        'source_sha256': '4' * 64,
        'typed_packet_path': str(typed),
        'position_id': 'synthetic-position', 'evidence_id': 'synthetic-evidence',
    }
    calls = []

    def exact_reprojection(data_root, source, source_sha, typed_packet,
                           position_id, evidence_id, packet):
        calls.append(('lichess', source_sha, position_id, evidence_id))
        assert data_root == tmp_path and source == tmp_path / 'receipt.json'
        assert typed_packet == {}
        return cf.canonical(packet)

    def user_reprojection(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        calls.append(('user', pgn_sha, review_sha, page_sha, role))
        assert pgn == tmp_path / 'game.pgn' and review == tmp_path / 'review'
        return cf.canonical(packet)

    monkeypatch.setattr(lichess_packet, 'encode_no_forward_packet', exact_reprojection)
    monkeypatch.setattr(user_packet, 'encode_packet', user_reprojection)
    return binding, calls, tmp_path


def user_binding(source_binding):
    _, calls, tmp_path = source_binding
    return ({'schema': tactical.BINDING_SCHEMA, 'packet_schema': user_packet.SCHEMA,
             'pgn_path': str(tmp_path / 'game.pgn'),
             'review_dir': str(tmp_path / 'review'),
             'pgn_sha256': '1' * 64, 'review_sha256': '2' * 64,
             'page_sha256': '3' * 64, 'role': 'played'}, calls)


def evaluate(raw, digest, assertion, binding):
    return tactical.evaluate(raw, digest, cf.canonical(assertion), source_binding=binding)


@pytest.mark.parametrize(('fen', 'candidate', 'kind', 'square', 'piece'), [
    ('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', 'e4d5', 'capture', 'd5', 'pawn'),
    ('4k3/8/8/8/8/8/8/R6K w - - 0 1', 'a1e1', 'check', 'e8', 'king'),
])
def test_candidate_move_immediate_capture_and_check(source_binding, fen, candidate,
                                                    kind, square, piece):
    binding, calls, _ = source_binding
    raw, digest = source_packet(fen, candidate)
    assertion = claim(candidate, [], kind, 'white', square, piece, 0)
    result = evaluate(raw, digest, assertion, binding)
    assert result['decision'] == 'verified_possible_event'
    assert result['plies_replayed'] == 0
    assert result['event_semantics'] == 'conditional_legal_line_event'
    assert len(calls) == 1


def test_candidate_move_immediate_mate(source_binding):
    binding, _, _ = source_binding
    board = chess.Board()
    for uci in ('f2f3', 'e7e5', 'g2g4'):
        board.push_uci(uci)
    raw, digest = source_packet(board.fen(), 'd8h4')
    result = evaluate(raw, digest, claim('d8h4', [], 'mate', 'black',
                                         'e1', 'king', 0), binding)
    assert result['decision'] == 'verified_possible_event'


@pytest.mark.parametrize('user', [False, True])
def test_later_event_replays_full_line_under_both_packet_shapes(source_binding, user):
    binding = user_binding(source_binding)[0] if user else source_binding[0]
    raw, digest = source_packet(selected_uci='e2e4', user=user)
    assertion = claim('e2e4', ['d7d5', 'e4d5'], 'capture',
                      'white', 'd5', 'pawn', 2)
    result = evaluate(raw, digest, assertion, binding)
    assert result['decision'] == 'verified_possible_event'
    assert result['plies_replayed'] == 2
    assert source_binding[1][-1][0] == ('user' if user else 'lichess')


def test_pinned_piece_attack_is_geometric_and_not_a_legal_capture(source_binding):
    binding, _, _ = source_binding
    fen = '4r1k1/8/8/8/8/b7/4R2P/4K3 w - - 0 1'
    board = chess.Board(fen)
    board.push_uci('e2e3')
    assert board.is_attacked_by(chess.WHITE, chess.A3)
    assert chess.Move.from_uci('e3a3') not in board.legal_moves
    raw, digest = source_packet(fen, 'e2e3')
    assertion = claim('e2e3', [], 'new_geometric_attack',
                      'white', 'a3', 'bishop', 0)
    result = evaluate(raw, digest, assertion, binding)
    assert result['decision'] == 'verified_possible_event'
    assert result['event_semantics'] == 'geometric_attack_map_including_pinned_attackers'
    assertion['event']['kind'] = 'geometric_attack'
    assert evaluate(raw, digest, assertion, binding)['decision'] == 'verified_possible_event'
    assertion['event']['kind'] = 'new_attack'
    assert evaluate(raw, digest, assertion, binding)['reason'] == 'unsupported_event_kind'


@pytest.mark.parametrize(('change', 'reason'), [
    (lambda c: c['event'].update(actor='black'), 'event_actor_mismatch'),
    (lambda c: c['event']['target'].update(square='d6'), 'false_tactical_event'),
    (lambda c: c['event']['target'].update(piece='queen'), 'false_tactical_event'),
    (lambda c: c['event'].update(ply=1), 'invalid_event_ply'),
    (lambda c: c['event'].update(ply=True), 'invalid_event_ply'),
    (lambda c: c.update(candidate_uci='e4e6'), 'illegal_candidate_move'),
    (lambda c: c.update(continuation_uci=['d5d4']), 'illegal_continuation_move'),
    (lambda c: c.update(continuation_uci=['e8e7'] * 5), 'invalid_continuation_length'),
    (lambda c: c.update(modality='forced'), 'forced_or_best_modality_forbidden'),
    (lambda c: c.update(uncertainty='best Stockfish line'), 'invalid_uncertainty_qualifier'),
    (lambda c: c.update(prose='This wins by force.'), 'invalid_claim_shape'),
    (lambda c: c.update(score='+3.0'), 'invalid_claim_shape'),
    (lambda c: c.update(pv_uci=['e8e7']), 'invalid_claim_shape'),
])
def test_false_unbounded_or_leaky_claim_rejected(source_binding, change, reason):
    binding, _, _ = source_binding
    fen = '4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1'
    raw, digest = source_packet(fen, 'e4d5')
    assertion = claim('e4d5', [], 'capture', 'white', 'd5', 'pawn', 0)
    change(assertion)
    result = evaluate(raw, digest, assertion, binding)
    assert result['decision'] == 'rejected' and result['reason'] == reason


def test_wrong_ply_which_is_in_range_is_false(source_binding):
    binding, _, _ = source_binding
    raw, digest = source_packet()
    assertion = claim('e2e4', ['d7d5'], 'capture', 'white', 'd5', 'pawn', 1)
    assert evaluate(raw, digest, assertion, binding)['reason'] == 'event_actor_mismatch'


def test_legal_reply_line_does_not_make_a_false_event_true(source_binding):
    binding, _, _ = source_binding
    raw, digest = source_packet()
    assertion = claim('e2e4', ['e7e5'], 'capture', 'black', 'e4', 'pawn', 1)
    assert evaluate(raw, digest, assertion, binding)['reason'] == 'false_tactical_event'
    assertion['event'] = {'kind': 'check', 'actor': 'black',
                          'target': {'square': 'e1', 'piece': 'king'}, 'ply': 1}
    assert evaluate(raw, digest, assertion, binding)['reason'] == 'false_tactical_event'


def test_en_passant_capture_uses_captured_pawn_square(source_binding):
    binding, _, _ = source_binding
    fen = '4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1'
    raw, digest = source_packet(fen, 'd7d5')
    assertion = claim('d7d5', ['e5d6'], 'capture', 'white', 'd5', 'pawn', 1)
    assert evaluate(raw, digest, assertion, binding)['decision'] == 'verified_possible_event'
    assertion['event']['target']['square'] = 'd6'
    assert evaluate(raw, digest, assertion, binding)['reason'] == 'false_tactical_event'


def test_abstention_and_non_json_prose(source_binding):
    binding, _, _ = source_binding
    raw, digest = source_packet()
    abstain = {'schema': tactical.CLAIM_SCHEMA, 'kind': 'abstention',
               'reason': 'no_defensible_line'}
    assert evaluate(raw, digest, abstain, binding)['decision'] == 'admissible_abstention'
    abstain['score'] = 2
    assert evaluate(raw, digest, abstain, binding)['reason'] == 'invalid_claim_shape'
    assert tactical.evaluate(raw, digest, b'This is best.', source_binding=binding)[
        'reason'] == 'invalid_response_json'
    duplicate = b'{"schema":"chess-tactical-hypothesis/v2","schema":"wrong"}'
    assert tactical.evaluate(raw, digest, duplicate, source_binding=binding)[
        'reason'] == 'duplicate_json_key'


def test_source_hash_shape_and_reprojection_must_pass_before_claim(source_binding,
                                                                   monkeypatch):
    binding, _, _ = source_binding
    raw, digest = source_packet()
    assertion = claim('e2e4', [], 'check', 'white', 'e8', 'king', 0)
    with pytest.raises(tactical.ClaimRejected, match='source_packet_hash_mismatch'):
        evaluate(raw, '0' * 64, assertion, binding)
    with pytest.raises(tactical.ClaimRejected, match='invalid_source_binding'):
        evaluate(raw, digest, assertion, {})
    changed = json.loads(raw)
    changed['pv_uci'] = ['e7e5']
    changed_raw = cf.canonical(changed)
    with pytest.raises(tactical.ClaimRejected, match='source_verification_failed'):
        evaluate(changed_raw, cf.digest(changed_raw), assertion, binding)
    monkeypatch.setattr(lichess_packet, 'encode_no_forward_packet', lambda *args: b'wrong')
    with pytest.raises(tactical.ClaimRejected, match='source_packet_reprojection_mismatch'):
        evaluate(raw, digest, assertion, binding)


def test_upstream_source_rejection_is_not_a_claim_result(source_binding, monkeypatch):
    binding, _, _ = source_binding
    raw, digest = source_packet()

    def reject(*args):
        raise ValueError('upstream source mismatch')

    monkeypatch.setattr(lichess_packet, 'encode_no_forward_packet', reject)
    with pytest.raises(tactical.ClaimRejected, match='source_verification_failed'):
        tactical.evaluate(raw, digest, b'{}', source_binding=binding)


def test_user_source_binding_must_match_packet_schema(source_binding):
    raw, digest = source_packet(user=True)
    with pytest.raises(tactical.ClaimRejected, match='source_binding_schema_mismatch'):
        tactical.evaluate(raw, digest, b'{}', source_binding=source_binding[0])
