"""Offline, source-bound replay of one conditional tactical hypothesis.

Only the caller's frozen no-forward packet and an evaluator-side source binding
enter this module. A proposed line is replayed after generation; this code has
no model or engine path and never feeds its finding back to a generator.
Geometric attacks are chess attack-map facts, including pinned attackers. They
do not assert that the attacker could legally capture the target. Even a true
event on a legal line does not explain Stockfish intent, prove best or forced
play, or establish commentary quality.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_packet as lichess_packet
import chess_typed_position_evidence as typed_evidence
import chess_user_game_no_forward_v1 as user_packet


CLAIM_SCHEMA = 'chess-tactical-hypothesis/v2'
RESULT_SCHEMA = 'chess-tactical-hypothesis-evaluation/v2'
BINDING_SCHEMA = 'chess-tactical-source-binding/v2'
MAX_RESPONSE_BYTES = 16_384
MAX_CONTINUATION_PLIES = 4
EVENT_KINDS = frozenset(('capture', 'check', 'mate', 'geometric_attack',
                         'new_geometric_attack'))
PIECE_NAMES = frozenset(('pawn', 'knight', 'bishop', 'rook', 'queen', 'king'))
ABSTENTION_REASONS = frozenset(('insufficient_evidence', 'no_defensible_line',
                               'unverified_strategy'))
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
SQUARE = re.compile(r'[a-h][1-8]\Z')
ORIGINAL_BINDING_FIELDS = ('schema', 'packet_schema', 'data_root',
                           'source_receipt_path', 'source_sha256',
                           'typed_packet_path', 'position_id', 'evidence_id')
USER_BINDING_FIELDS = ('schema', 'packet_schema', 'pgn_path', 'review_dir',
                       'pgn_sha256', 'review_sha256', 'page_sha256', 'role')


class ClaimRejected(ValueError):
    """A stable rejection code for malformed input or a false assertion."""


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


def _binding_path(binding, name):
    value = binding[name]
    _require(type(value) is str and bool(value), 'invalid_source_binding')
    return Path(value)


def _source_reprojection(packet, binding):
    """Invoke the owning packet encoder, including its fresh source checks."""
    _require(type(binding) is dict and binding.get('schema') == BINDING_SCHEMA,
             'invalid_source_binding')
    schema = packet.get('schema')
    _require(binding.get('packet_schema') == schema, 'source_binding_schema_mismatch')
    if schema == lichess_packet.SCHEMA:
        _exact(binding, ORIGINAL_BINDING_FIELDS, 'invalid_source_binding')
        for name in ('source_sha256',):
            _require(type(binding[name]) is str and SHA256.fullmatch(binding[name]),
                     'invalid_source_binding')
        for name in ('position_id', 'evidence_id'):
            _require(type(binding[name]) is str and bool(binding[name]),
                     'invalid_source_binding')
        typed_raw = typed_evidence._read_bounded(_binding_path(binding, 'typed_packet_path'))
        typed = json.loads(typed_raw)
        return lichess_packet.encode_no_forward_packet(
            _binding_path(binding, 'data_root'),
            _binding_path(binding, 'source_receipt_path'),
            binding['source_sha256'], typed, binding['position_id'],
            binding['evidence_id'], packet)
    _require(schema == user_packet.SCHEMA, 'unsupported_source_packet_schema')
    _exact(binding, USER_BINDING_FIELDS, 'invalid_source_binding')
    for name in ('pgn_sha256', 'review_sha256', 'page_sha256'):
        _require(type(binding[name]) is str and SHA256.fullmatch(binding[name]),
                 'invalid_source_binding')
    _require(type(binding['role']) is str and binding['role'] in user_packet.ROLES,
             'invalid_source_binding')
    return user_packet.encode_packet(
        _binding_path(binding, 'pgn_path'), _binding_path(binding, 'review_dir'),
        binding['pgn_sha256'], binding['review_sha256'], binding['page_sha256'],
        role=binding['role'], packet=packet)


def _source_board(packet_bytes, expected_packet_sha256, source_binding):
    """Require canonical packet bytes, pin, legal selected move and fresh source."""
    maximum = max(lichess_packet.MAX_PACKET_BYTES, user_packet.MAX_PACKET_BYTES)
    _require(type(packet_bytes) is bytes and 0 < len(packet_bytes) <= maximum,
             'invalid_source_packet_bytes')
    _require(type(expected_packet_sha256) is str and SHA256.fullmatch(expected_packet_sha256),
             'invalid_expected_packet_sha256')
    _require(cf.digest(packet_bytes) == expected_packet_sha256, 'source_packet_hash_mismatch')
    try:
        packet = json.loads(packet_bytes)
        _require(type(packet) is dict, 'invalid_source_packet')
        schema = packet.get('schema')
        if schema == lichess_packet.SCHEMA:
            lichess_packet._shape(packet)
        elif schema == user_packet.SCHEMA:
            user_packet._shape(packet)
        else:
            raise ClaimRejected('unsupported_source_packet_schema')
        _require(cf.canonical(packet) == packet_bytes, 'source_packet_not_canonical')
        _require(_source_reprojection(packet, source_binding) == packet_bytes,
                 'source_packet_reprojection_mismatch')
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
    except (OSError, TypeError, KeyError, ValueError, UnicodeError,
            RecursionError, chess.InvalidMoveError) as error:
        raise ClaimRejected('source_verification_failed') from error


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
    _require(type(event['actor']) is str and event['actor'] in ('white', 'black'),
             'invalid_event_actor')
    _require(type(event['ply']) is int and 0 <= event['ply'] <= line_length,
             'invalid_event_ply')
    _exact(event['target'], ('square', 'piece'), 'invalid_event_target_shape')
    _require(type(event['target']['square']) is str and
             SQUARE.fullmatch(event['target']['square']), 'invalid_event_target_square')
    _require(type(event['target']['piece']) is str and
             event['target']['piece'] in PIECE_NAMES, 'invalid_event_target_piece')
    if event['kind'] in ('check', 'mate'):
        _require(event['target']['piece'] == 'king', 'king_event_target_required')
    if event['kind'] in ('geometric_attack', 'new_geometric_attack'):
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
                (kind == 'geometric_attack' or
                 not before.is_attacked_by(actor, target_square)))


def _replay(board, claim):
    _exact(claim, ('schema', 'kind', 'candidate_uci', 'continuation_uci', 'event',
                   'modality', 'uncertainty'), 'invalid_hypothesis_shape')
    _require(claim['modality'] == 'possible_if_line', 'forced_or_best_modality_forbidden')
    _require(claim['uncertainty'] == 'other_replies_unchecked',
             'invalid_uncertainty_qualifier')
    continuation = claim['continuation_uci']
    _require(type(continuation) is list and
             len(continuation) <= MAX_CONTINUATION_PLIES,
             'invalid_continuation_length')
    _event_shape(claim['event'], len(continuation))
    candidate = _legal_move(board, claim['candidate_uci'], 'illegal_candidate_move')
    before = board.copy(stack=False)
    board.push(candidate)
    event_verified = (claim['event']['ply'] == 0 and
                      _event_occurs(before, board, candidate, claim['event']))
    for ply, uci in enumerate(continuation, 1):
        move = _legal_move(board, uci, 'illegal_continuation_move')
        before = board.copy(stack=False)
        board.push(move)
        if ply == claim['event']['ply']:
            event_verified = _event_occurs(before, board, move, claim['event'])
    _require(event_verified, 'false_tactical_event')
    return candidate, len(continuation)


def evaluate(packet_bytes, expected_packet_sha256, raw_response, *, source_binding):
    """Verify source upstream, then replay one exact JSON claim or abstention.

    A source failure raises ClaimRejected. Untrusted claim failures return a
    rejected decision. The result is evaluator-only and must never be sent to
    the generator. No PV or future move is read by this module.
    """
    board, selected = _source_board(packet_bytes, expected_packet_sha256, source_binding)
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
            decision, reason, selected_match, plies, semantics = (
                'admissible_abstention', claim['reason'], None, 0, None)
        else:
            _require(claim['kind'] == 'tactical_hypothesis', 'invalid_claim_kind')
            candidate, plies = _replay(board, claim)
            decision, reason, selected_match = 'verified_possible_event', None, candidate == selected
            semantics = ('geometric_attack_map_including_pinned_attackers'
                         if claim['event']['kind'] in ('geometric_attack',
                                                       'new_geometric_attack')
                         else 'conditional_legal_line_event')
        return {'schema': RESULT_SCHEMA, 'decision': decision, 'reason': reason,
                'response_sha256': cf.digest(raw), 'packet_sha256': expected_packet_sha256,
                'candidate_is_selected': selected_match, 'plies_replayed': plies,
                'event_semantics': semantics}
    except ClaimRejected as error:
        return {'schema': RESULT_SCHEMA, 'decision': 'rejected',
                'reason': str(error), 'response_sha256': _response_digest(raw_response),
                'packet_sha256': expected_packet_sha256, 'candidate_is_selected': None,
                'plies_replayed': 0, 'event_semantics': None}
