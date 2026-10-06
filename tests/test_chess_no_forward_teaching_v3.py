"""Synthetic teaching-contrast controls plus an optional local practice binding."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward
import chess_no_forward_teaching_v3 as teaching
import chess_tactical_hypothesis_v2 as tactical
import chess_user_game_no_forward_v1 as user_packet


FEN = '2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20'
ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ROOT / 'artifacts/chess-user-reviews/chesscom-184866057876'
PRACTICE_PACKET = ROOT / 'artifacts/chess-user-game-no-forward-v1/chesscom-184866057876/ply39-played.json'
PRACTICE_PACKET_SHA256 = '02c5f3955bf1649534e62b505659e6915ef98800b76938b9a6c00d44d82c7eec'
PRACTICE_PGN_SHA256 = '684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075'
PRACTICE_REVIEW_SHA256 = 'b76e4746eadf4b85775468df0ee7324272dcb677673efe58dd8d4a8b40a3b730'
PRACTICE_PAGE_SHA256 = 'ed6ddf506897c76fce2856fb4e82e3c2a2a9ae6a8f48bfd93efb3c31b4b27a5b'


def packet_for(fen=FEN, selected_uci='c2c3'):
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    assert board.is_valid() and selected in board.legal_moves
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
                               'score': {'type': 'cp', 'value': -471, 'bound': 'exact',
                                         'order': 'engine_score',
                                         'perspective': 'side_to_move',
                                         'side_to_move': 'white'},
                               'observation_only': True,
                               'independently_reproduced': False},
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
    }
    raw = cf.canonical(packet)
    return raw, cf.digest(raw)


def q_claim():
    return {
        'schema': teaching.CLAIM_SCHEMA, 'kind': teaching.CLAIM_KIND,
        'selected_uci': 'c2c3', 'alternative_uci': 'c2e4',
        'common_reply_uci': 'd7d4',
        'option': {'piece': 'queen', 'to': 'b7', 'promotion': None,
                   'property': 'capture_with_check'},
        'relation': 'legal_only_after_alternative',
        'modality': 'possible_if_common_reply',
        'uncertainty': 'other_replies_and_engine_intent_unverified',
    }


@pytest.fixture
def bound_source(tmp_path, monkeypatch):
    """Mock the owning encoder while proving the evaluator invokes it."""
    binding = {
        'schema': tactical.BINDING_SCHEMA, 'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(tmp_path / 'game.pgn'), 'review_dir': str(tmp_path / 'review'),
        'pgn_sha256': '1' * 64, 'review_sha256': '2' * 64,
        'page_sha256': '3' * 64, 'role': 'played',
    }
    calls = []

    def exact_encoder(pgn, review, pgn_sha, review_sha, page_sha, *, role, packet):
        calls.append((pgn, review, pgn_sha, review_sha, page_sha, role))
        assert pgn == tmp_path / 'game.pgn'
        assert review == tmp_path / 'review'
        assert (pgn_sha, review_sha, page_sha, role) == (
            '1' * 64, '2' * 64, '3' * 64, 'played')
        return cf.canonical(packet)

    monkeypatch.setattr(user_packet, 'encode_packet', exact_encoder)
    return binding, calls


def checked(raw, digest, claim, binding):
    return teaching.evaluate(raw, digest, cf.canonical(claim), source_binding=binding)


def test_qc3_conditional_option_and_fixed_sentence(bound_source):
    binding, calls = bound_source
    raw, digest = packet_for()
    result = checked(raw, digest, q_claim(), binding)
    assert result['decision'] == 'verified_conditional_option'
    assert result['reason'] is None
    assert 'Qe4' in result['teaching_text']
    assert 'Qxd4' in result['teaching_text']
    assert 'Qxb7+' in result['teaching_text']
    assert 'Qc3' in result['teaching_text']
    assert "engine's reasoning remain unchecked" in result['teaching_text']
    assert result['model_calls'] == result['engine_calls'] == 0
    assert result['quality_evaluated'] is False
    assert len(calls) == 1


def test_promoted_pawn_is_not_called_a_moved_queen(bound_source):
    binding, _ = bound_source
    fen = '1r6/P6k/8/8/8/8/8/6K1 w - - 0 1'
    raw, digest = packet_for(fen, 'a7a8q')
    claim = q_claim()
    claim.update(selected_uci='a7a8q', alternative_uci='a7b8q',
                 common_reply_uci='h7h6',
                 option={'piece': 'queen', 'to': 'e5', 'promotion': None,
                         'property': 'legal'})
    result = checked(raw, digest, claim, binding)
    assert result['decision'] == 'verified_conditional_option'
    assert 'promoted queen' in result['teaching_text']
    assert 'moved queen' not in result['teaching_text']


def test_generator_projection_has_no_answer_or_future(bound_source):
    binding, calls = bound_source
    raw, digest = packet_for()
    safe = teaching.build_generator_input(raw, digest, source_binding=binding)
    value = json.loads(safe)
    assert safe == cf.canonical(value)
    assert set(value) == {'schema', 'source_packet_sha256', 'source', 'fen',
                          'side_to_move', 'selected_move', 'transition',
                          'engine_observation', 'assertion_kinds'}
    assert value['schema'] == teaching.INPUT_SCHEMA
    assert value['source_packet_sha256'] == digest
    assert value['assertion_kinds'] == [teaching.CLAIM_KIND, 'abstention']
    assert value['selected_move']['uci'] == 'c2c3'
    assert b'c2e4' not in safe and b'd7d4' not in safe and b'e4b7' not in safe
    assert b'pv_uci' not in safe and b'fen_after' not in safe
    messages = teaching.generator_messages(raw, digest, source_binding=binding)
    assert messages == [{'role': 'system', 'content': teaching.PROMPT},
                        {'role': 'user', 'content': safe.decode('utf-8')}]
    assert len(calls) == 2


@pytest.mark.parametrize(('mutate', 'reason'), [
    (lambda c: c.update(common_reply_uci='a8a1'), 'reply_illegal_after_selected'),
    (lambda c: c['option'].update(to='g7'), 'option_not_exclusive_to_alternative'),
    (lambda c: c['option'].update(piece='rook'), 'option_piece_mismatch'),
    (lambda c: c['option'].update(to='z9'), 'invalid_option_square'),
    (lambda c: c['option'].update(property='mate'), 'false_option_property'),
    (lambda c: c.update(alternative_uci='c2c3'), 'alternative_not_same_moved_piece'),
    (lambda c: c.update(modality='forced'), 'forced_or_best_modality_forbidden'),
    (lambda c: c.update(uncertainty='Stockfish intended this'),
     'unsupported_uncertainty'),
    (lambda c: c.update(prose='This wins by force.'), 'invalid_claim_shape'),
    (lambda c: c.update(score=376), 'invalid_claim_shape'),
    (lambda c: c.update(pv_uci=['d7d4']), 'invalid_claim_shape'),
])
def test_false_ambiguous_or_unsupported_claims_rejected(bound_source, mutate, reason):
    binding, _ = bound_source
    raw, digest = packet_for()
    claim = q_claim()
    mutate(claim)
    result = checked(raw, digest, claim, binding)
    assert result['decision'] == 'rejected' and result['reason'] == reason
    assert result['teaching_text'] is None


def test_common_reply_must_really_be_the_same_action(bound_source):
    binding, _ = bound_source
    fen = '6k1/8/8/2b5/8/8/3Q4/4K3 w - - 0 1'
    raw, digest = packet_for(fen, 'd2c3')
    claim = q_claim()
    claim.update(selected_uci='d2c3', alternative_uci='d2e3',
                 common_reply_uci='c5b4')
    # Bb4 gives check only after Qe3, so "same reply" hides a real difference.
    result = checked(raw, digest, claim, binding)
    assert result['decision'] == 'rejected'
    assert result['reason'] == 'ambiguous_common_reply'


def test_abstention_duplicate_json_and_untyped_prose(bound_source):
    binding, _ = bound_source
    raw, digest = packet_for()
    abstain = {'schema': teaching.CLAIM_SCHEMA, 'kind': 'abstention',
               'reason': 'no_defensible_option_difference'}
    result = checked(raw, digest, abstain, binding)
    assert result['decision'] == 'admissible_abstention'
    assert result['teaching_text'] is None
    abstain['engine_reason'] = 'because Stockfish says so'
    assert checked(raw, digest, abstain, binding)['reason'] == 'invalid_abstention_shape'
    assert teaching.evaluate(raw, digest, b'This move is best.',
                             source_binding=binding)['reason'] == 'invalid_response_json'
    duplicate = b'{"schema":"chess-no-forward-teaching-output/v3","schema":"wrong"}'
    assert teaching.evaluate(raw, digest, duplicate,
                             source_binding=binding)['reason'] == 'duplicate_json_key'


def test_source_hash_and_fresh_reprojection_are_required(bound_source, monkeypatch):
    binding, _ = bound_source
    raw, digest = packet_for()
    with pytest.raises(tactical.ClaimRejected, match='source_packet_hash_mismatch'):
        checked(raw, '0' * 64, q_claim(), binding)
    with pytest.raises(tactical.ClaimRejected, match='invalid_source_binding'):
        checked(raw, digest, q_claim(), {})
    changed = json.loads(raw)
    changed['pv_uci'] = ['d7d4']
    changed_raw = cf.canonical(changed)
    with pytest.raises(tactical.ClaimRejected, match='source_verification_failed'):
        checked(changed_raw, cf.digest(changed_raw), q_claim(), binding)
    monkeypatch.setattr(user_packet, 'encode_packet', lambda *args, **kwargs: b'wrong')
    with pytest.raises(tactical.ClaimRejected, match='source_packet_reprojection_mismatch'):
        checked(raw, digest, q_claim(), binding)


def test_real_qc3_source_bound_practice_when_local_assets_exist():
    pgn = PRACTICE / 'source.pgn'
    review = PRACTICE / 'review-v3-paired-explanation-20261006'
    if not all(path.exists() for path in (pgn, review / 'review.json',
                                          review / 'index.html', PRACTICE_PACKET)):
        pytest.skip('ignored local practice assets are not present')
    raw = PRACTICE_PACKET.read_bytes()
    binding = {
        'schema': tactical.BINDING_SCHEMA, 'packet_schema': user_packet.SCHEMA,
        'pgn_path': str(pgn), 'review_dir': str(review),
        'pgn_sha256': PRACTICE_PGN_SHA256,
        'review_sha256': PRACTICE_REVIEW_SHA256,
        'page_sha256': PRACTICE_PAGE_SHA256, 'role': 'played',
    }
    result = checked(raw, PRACTICE_PACKET_SHA256, q_claim(), binding)
    assert result['decision'] == 'verified_conditional_option'
    assert 'Qxb7+' in result['teaching_text']
    binding['page_sha256'] = '0' * 64
    with pytest.raises(tactical.ClaimRejected, match='source_verification_failed'):
        checked(raw, PRACTICE_PACKET_SHA256, q_claim(), binding)
