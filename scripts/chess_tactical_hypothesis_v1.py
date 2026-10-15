"""Offline replay of one model-proposed tactical event; never a quality verdict.

The caller supplies the canonical, previously source-verified no-forward packet
and its frozen SHA-256. This module reads no engine receipt or PV, makes no model
or engine call, and never returns a continuation to a generator. A verified
event means only that it occurs on the proposed legal line, not that the line
is likely, forced, best, or a reason Stockfish preferred a move.
"""
from __future__ import annotations

import hashlib
import json
import re

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_packet as no_forward


CLAIM_SCHEMA = 'chess-tactical-hypothesis/v1'
RESULT_SCHEMA = 'chess-tactical-hypothesis-evaluation/v1'
MAX_RESPONSE_BYTES = 16_384
MAX_CONTINUATION_PLIES = 4
EVENT_KINDS = frozenset(('capture', 'check', 'attacks_piece', 'new_attack', 'mate'))
PIECE_NAMES = frozenset(('pawn', 'knight', 'bishop', 'rook', 'queen', 'king'))
ABSTENTION_REASONS = frozenset(('insufficient_evidence', 'no_defensible_line',
                               'unverified_strategy'))
SHA256 = re.compile(r'[0-9a-f]{64}\Z')


class ClaimRejected(ValueError):
    """A stable, non-prose rejection code for an untrusted model assertion."""


def _require(condition, code):
    if not condition:
        raise ClaimRejected(code)


def _exact(value, keys, code):
    _require(type(value) is dict and set(value) == set(keys), code)


def _parse_json(raw):
    _require(type(raw) in (bytes, str), 'invalid_response_type')
    if type(raw) is str:
        try:
            raw = raw.encode('utf-8')
        except UnicodeError as error:
            raise ClaimRejected('invalid_response_encoding') from error
    _require(0 < len(raw) <= MAX_RESPONSE_BYTES, 'invalid_response_length')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, 'duplicate_json_key')
            value[key] = item
        return value

    def no_constant(_value):
        raise ClaimRejected('invalid_json_constant')

    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                          parse_constant=no_constant), raw
    except ClaimRejected:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        raise ClaimRejected('invalid_response_json') from error


def _response_digest(raw):
    if type(raw) is str:
        try:
            raw = raw.encode('utf-8')
        except UnicodeError:
            return None
    return hashlib.sha256(raw).hexdigest() if type(raw) is bytes else None


def _source_board(packet_bytes, expected_packet_sha256):
    """Check the exact no-forward shape and selected legal move, before replay."""
    _require(type(packet_bytes) is bytes and 0 < len(packet_bytes) <= no_forward.MAX_PACKET_BYTES,
             'invalid_source_packet_bytes')
    _require(type(expected_packet_sha256) is str and SHA256.fullmatch(expected_packet_sha256),
             'invalid_expected_packet_sha256')
    _require(cf.digest(packet_bytes) == expected_packet_sha256, 'source_packet_hash_mismatch')
    try:
        packet = json.loads(packet_bytes)
        no_forward._shape(packet)
        _require(cf.canonical(packet) == packet_bytes, 'source_packet_not_canonical')
        board = chess.Board(packet['fen'])
        _require(board.is_valid(), 'invalid_source_board')
        _require(packet['side_to_move'] == chess.COLOR_NAMES[board.turn],
                 'source_side_mismatch')
        selected = chess.Move.from_uci(packet['selected_move']['uci'])
        _require(selected in board.legal_moves, 'source_selected_move_illegal')
        _require(packet['selected_move']['san'] == board.san(selected),
                 'source_selected_san_mismatch')
        return board, selected
    except ClaimRejected:
        raise
    except (TypeError, KeyError, ValueError, RecursionError, chess.InvalidMoveError) as error:
        raise ClaimRejected('invalid_source_packet') from error


def _legal_move(board, uci, code):
    _require(type(uci) is str and 4 <= len(uci) <= 5, code)
    try:
        move = chess.Move.from_uci(uci)
    except (ValueError, chess.InvalidMoveError) as error:
        raise ClaimRejected(code) from error
    _require(move.uci() == uci and move in board.legal_moves, code)
    return move


def _event_shape(event, line_length):
    _exact(event, ('kind', 'actor', 'target', 'ply'), 'invalid_event_shape')
    _require(type(event['kind']) is str and event['kind'] in EVENT_KINDS,
             'unsupported_event_kind')
    _require(event['actor'] in ('white', 'black'), 'invalid_event_actor')
    _require(type(event['ply']) is int and 1 <= event['ply'] <= line_length,
             'invalid_event_ply')
    _exact(event['target'], ('square', 'piece'), 'invalid_event_target_shape')
    square = event['target']['square']
    _require(type(square) is str and re.fullmatch(r'[a-h][1-8]', square) is not None,
             'invalid_event_target_square')
    _require(type(event['target']['piece']) is str and
             event['target']['piece'] in PIECE_NAMES, 'invalid_event_target_piece')
    if event['kind'] in ('check', 'mate'):
        _require(event['target']['piece'] == 'king', 'king_event_target_required')
    if event['kind'] in ('attacks_piece', 'new_attack'):
        _require(event['target']['piece'] != 'king', 'use_check_for_king_attack')


def _event_occurs(before, after, move, event):
    actor = before.turn
    _require(event['actor'] == chess.COLOR_NAMES[actor], 'event_actor_mismatch')
    target_square = chess.parse_square(event['target']['square'])
    target_piece = event['target']['piece']
    kind = event['kind']
    if kind == 'capture':
        if not before.is_capture(move):
            return False
        captured_square = move.to_square
        if before.is_en_passant(move):
            captured_square += -8 if actor == chess.WHITE else 8
        captured = before.piece_at(captured_square)
        return (target_square == captured_square and captured is not None and
                captured.color != actor and chess.piece_name(captured.piece_type) == target_piece)
    if kind in ('check', 'mate'):
        king_square = after.king(after.turn)
        return (king_square == target_square and
                (after.is_check() if kind == 'check' else after.is_checkmate()))
    victim_before = before.piece_at(target_square)
    victim_after = after.piece_at(target_square)
    present = (victim_before is not None and victim_after == victim_before and
               victim_after.color != actor and
               chess.piece_name(victim_after.piece_type) == target_piece)
    return bool(present and after.is_attacked_by(actor, target_square) and
                (kind == 'attacks_piece' or not before.is_attacked_by(actor, target_square)))


def _replay(board, claim):
    _exact(claim, ('schema', 'kind', 'candidate_uci', 'continuation_uci', 'event',
                   'modality', 'uncertainty'), 'invalid_hypothesis_shape')
    _require(claim['modality'] == 'possible_if_line', 'forced_or_best_modality_forbidden')
    _require(claim['uncertainty'] == 'other_replies_unchecked',
             'invalid_uncertainty_qualifier')
    candidate = _legal_move(board, claim['candidate_uci'], 'illegal_candidate_move')
    continuation = claim['continuation_uci']
    _require(type(continuation) is list and
             1 <= len(continuation) <= MAX_CONTINUATION_PLIES,
             'invalid_continuation_length')
    _event_shape(claim['event'], len(continuation))
    board.push(candidate)
    event_verified = False
    for ply, uci in enumerate(continuation, 1):
        move = _legal_move(board, uci, 'illegal_continuation_move')
        before = board.copy(stack=False)
        board.push(move)
        if ply == claim['event']['ply']:
            event_verified = _event_occurs(before, board, move, claim['event'])
    _require(event_verified, 'false_tactical_event')
    return candidate, len(continuation)


def evaluate(packet_bytes, expected_packet_sha256, raw_response):
    """Replay one untrusted JSON claim against a frozen no-forward input.

    Source verification must already have happened upstream. This function only
    checks packet identity/shape and a proposed conditional line. Its verdict is
    evaluator-side data; do not return it as generator input.
    """
    board, selected = _source_board(packet_bytes, expected_packet_sha256)
    try:
        claim, raw = _parse_json(raw_response)
        _exact(claim, ('schema', 'kind', 'reason') if type(claim) is dict and
               claim.get('kind') == 'abstention' else
               ('schema', 'kind', 'candidate_uci', 'continuation_uci', 'event',
                'modality', 'uncertainty'), 'invalid_claim_shape')
        _require(claim['schema'] == CLAIM_SCHEMA, 'invalid_claim_schema')
        if claim['kind'] == 'abstention':
            _require(type(claim['reason']) is str and claim['reason'] in ABSTENTION_REASONS,
                     'invalid_abstention_reason')
            return {'schema': RESULT_SCHEMA, 'decision': 'admissible_abstention',
                    'reason': claim['reason'], 'response_sha256': cf.digest(raw),
                    'packet_sha256': expected_packet_sha256, 'candidate_is_selected': None,
                    'plies_replayed': 0}
        _require(claim['kind'] == 'tactical_hypothesis', 'invalid_claim_kind')
        candidate, plies = _replay(board, claim)
        return {'schema': RESULT_SCHEMA, 'decision': 'verified_possible_event',
                'reason': None, 'response_sha256': cf.digest(raw),
                'packet_sha256': expected_packet_sha256,
                'candidate_is_selected': candidate == selected,
                'plies_replayed': plies}
    except ClaimRejected as error:
        return {'schema': RESULT_SCHEMA, 'decision': 'rejected',
                'reason': str(error), 'response_sha256': _response_digest(raw_response),
                'packet_sha256': expected_packet_sha256, 'candidate_is_selected': None,
                'plies_replayed': 0}
