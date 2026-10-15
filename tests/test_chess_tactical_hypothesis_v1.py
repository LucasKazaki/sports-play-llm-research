"""Synthetic legal-replay controls; these are not commentary-quality evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward
import chess_tactical_hypothesis_v1 as tactical


def source_packet(fen=chess.STARTING_FEN, selected_uci='e2e4'):
    """Build an exact-shape synthetic packet, not a real source receipt."""
    board = chess.Board(fen)
    selected = chess.Move.from_uci(selected_uci)
    transition = cf.transition_evidence(board, selected)
    packet = {
        'schema': no_forward.SCHEMA,
        'source': {field: 'synthetic-fixture' for field in no_forward.SOURCE_FIELDS},
        'fen': board.fen(), 'side_to_move': chess.COLOR_NAMES[board.turn],
        'selected_move': {'uci': selected_uci, 'san': board.san(selected)},
        'transition': {key: transition[key] for key in no_forward.TRANSITION_FIELDS},
        'engine_observation': {
            'evidence_id': 'synthetic', 'engine_sha256': '0' * 64,
            'score': {'type': 'centipawn', 'value': 0, 'perspective': 'white',
                      'side_to_move': chess.COLOR_NAMES[board.turn], 'bound': 'exact',
                      'order': 1},
            'observation_only': True, 'independently_reproduced': False,
        },
        'concept_vocabulary': list(no_forward.CONCEPTS),
        'assertion_kinds': list(no_forward.ASSERTIONS),
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


def evaluate(packet, digest, value):
    return tactical.evaluate(packet, digest, json.dumps(value).encode('utf-8'))


@pytest.mark.parametrize('assertion', [
    claim('e2e4', ['d7d5', 'e4d5'], 'capture', 'white', 'd5', 'pawn', 2),
    claim('e2e4', ['f7f5', 'd1h5'], 'check', 'white', 'e8', 'king', 2),
    claim('f2f3', ['e7e5', 'g2g4', 'd8h4'], 'mate', 'black', 'e1', 'king', 3),
])
def test_legally_replayed_capture_check_and_mate(assertion):
    packet, digest = source_packet(selected_uci=assertion['candidate_uci'])
    result = evaluate(packet, digest, assertion)
    assert result['decision'] == 'verified_possible_event'
    assert result['candidate_is_selected'] is True
    assert result['plies_replayed'] == len(assertion['continuation_uci'])
    assert result['packet_sha256'] == digest


@pytest.mark.parametrize('kind', ['attacks_piece', 'new_attack'])
def test_reply_attacks_queen_after_legal_selected_move(kind):
    fen = 'k7/8/8/8/3q4/8/8/4Q2K w - - 0 1'
    packet, digest = source_packet(fen, 'h1h2')
    assertion = claim('h1h2', ['d4c3'], kind, 'black', 'e1', 'queen', 1)
    assert evaluate(packet, digest, assertion)['decision'] == 'verified_possible_event'


def test_model_may_propose_legal_alternative_but_it_is_not_ranked_best():
    packet, digest = source_packet(selected_uci='e2e4')
    assertion = claim('d2d4', ['d7d5', 'c2c4'], 'new_attack',
                      'white', 'd5', 'pawn', 2)
    result = evaluate(packet, digest, assertion)
    assert result['decision'] == 'verified_possible_event'
    assert result['candidate_is_selected'] is False
    assert 'best' not in json.dumps(result)


def test_en_passant_capture_identifies_captured_square_not_landing_square():
    fen = '4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1'
    packet, digest = source_packet(fen, 'd7d5')
    assertion = claim('d7d5', ['e5d6'], 'capture', 'white', 'd5', 'pawn', 1)
    assert evaluate(packet, digest, assertion)['decision'] == 'verified_possible_event'
    assertion['event']['target']['square'] = 'd6'
    assert evaluate(packet, digest, assertion)['reason'] == 'false_tactical_event'


@pytest.mark.parametrize(('change', 'expected_reason'), [
    (lambda c: c['event'].update(kind='mate'), 'king_event_target_required'),
    (lambda c: c['event'].update(actor='black'), 'event_actor_mismatch'),
    (lambda c: c['event']['target'].update(square='e5'), 'false_tactical_event'),
    (lambda c: c['event']['target'].update(piece='queen'), 'false_tactical_event'),
    (lambda c: c['event'].update(actor='black', ply=1), 'false_tactical_event'),
    (lambda c: c.update(candidate_uci='a1a8'), 'illegal_candidate_move'),
    (lambda c: c.update(continuation_uci=['e7e5', 'e2e4']), 'illegal_continuation_move'),
    (lambda c: c.update(continuation_uci=['e7e5', 'g1f3', 'b8c6', 'f1c4', 'g8f6']),
     'invalid_continuation_length'),
    (lambda c: c.update(modality='forced'), 'forced_or_best_modality_forbidden'),
    (lambda c: c.update(uncertainty='best Stockfish line'),
     'invalid_uncertainty_qualifier'),
    (lambda c: c.update(score='+300'), 'invalid_claim_shape'),
    (lambda c: c.update(pv_uci=['e7e5']), 'invalid_claim_shape'),
    (lambda c: c.update(teaching_text='This forces a win.'), 'invalid_claim_shape'),
    (lambda c: c['event'].update(ply=True), 'invalid_event_ply'),
])
def test_false_illegal_unbounded_or_leaky_hypotheses_rejected(change, expected_reason):
    packet, digest = source_packet()
    assertion = claim('e2e4', ['d7d5', 'e4d5'], 'capture', 'white', 'd5', 'pawn', 2)
    change(assertion)
    result = evaluate(packet, digest, assertion)
    assert result['decision'] == 'rejected'
    assert result['reason'] == expected_reason


def test_false_capture_and_false_check_are_not_strategy_evidence():
    packet, digest = source_packet()
    capture = claim('e2e4', ['e7e5'], 'capture', 'black', 'e4', 'pawn', 1)
    check = claim('e2e4', ['e7e5'], 'check', 'black', 'e1', 'king', 1)
    assert evaluate(packet, digest, capture)['reason'] == 'false_tactical_event'
    assert evaluate(packet, digest, check)['reason'] == 'false_tactical_event'


def test_preexisting_attack_is_not_new_attack():
    fen = 'k3r3/8/8/8/8/8/8/4Q2K w - - 0 1'
    packet, digest = source_packet(fen, 'h1h2')
    assertion = claim('h1h2', ['e8e7'], 'new_attack', 'black', 'e1', 'queen', 1)
    assert evaluate(packet, digest, assertion)['reason'] == 'false_tactical_event'
    assertion['event']['kind'] = 'attacks_piece'
    assert evaluate(packet, digest, assertion)['decision'] == 'verified_possible_event'


def test_abstention_is_exact_and_cannot_hide_a_line_or_free_prose():
    packet, digest = source_packet()
    abstain = {'schema': tactical.CLAIM_SCHEMA, 'kind': 'abstention',
               'reason': 'no_defensible_line'}
    assert evaluate(packet, digest, abstain)['decision'] == 'admissible_abstention'
    abstain['continuation_uci'] = ['e7e5']
    assert evaluate(packet, digest, abstain)['reason'] == 'invalid_claim_shape'
    abstain.pop('continuation_uci')
    abstain['reason'] = 'Stockfish proves the best move'
    assert evaluate(packet, digest, abstain)['reason'] == 'invalid_abstention_reason'


def test_duplicate_keys_and_untrusted_prose_are_rejected():
    packet, digest = source_packet()
    duplicate = b'{"schema":"chess-tactical-hypothesis/v1","schema":"wrong"}'
    assert tactical.evaluate(packet, digest, duplicate)['reason'] == 'duplicate_json_key'
    assert tactical.evaluate(packet, digest, b'This move wins.')['reason'] == 'invalid_response_json'
    assert tactical.evaluate(packet, digest, '\ud800')['reason'] == 'invalid_response_encoding'
    deeply_nested = b'[' * 1100 + b'0' + b']' * 1100
    assert tactical.evaluate(packet, digest, deeply_nested)['reason'] == 'invalid_response_json'


def test_source_packet_hash_and_forbidden_fields_fail_before_replay():
    packet, digest = source_packet()
    assertion = claim('e2e4', ['d7d5', 'e4d5'], 'capture', 'white', 'd5', 'pawn', 2)
    with pytest.raises(tactical.ClaimRejected, match='source_packet_hash_mismatch'):
        evaluate(packet, '0' * 64, assertion)
    changed = json.loads(packet)
    changed['pv_uci'] = ['d7d5']
    changed_raw = cf.canonical(changed)
    with pytest.raises(tactical.ClaimRejected, match='invalid_source_packet'):
        evaluate(changed_raw, cf.digest(changed_raw), assertion)
