"""Evaluator-only occupation and variation checks over pinned development evidence.

This module never builds a generator prompt or calls a model/engine. Its source
packet contains evaluator-only continuations and must not be sent to a generator.
Verified legality does not establish forced play, strategy or teaching quality.
"""
from __future__ import annotations

from pathlib import Path
import re

import chess
import chess_counterfactual_evidence as cf
import chess_typed_position_evidence as adapter

SCHEMA = 'chess-extended-claim-check/v1'
MAX_VARIATION_PLIES = 64
EVALUATOR_ONLY = True


def _abstain(reason):
    return {'schema': SCHEMA, 'status': 'abstain', 'reason': reason}


def _replayed_claim(board, selected_uci, retained_pv, evidence_id, claim):
    """Private legal kernel; public callers must use the source-bound entry point."""
    if not isinstance(claim, dict):
        return _abstain('unsupported_claim_shape')
    if not isinstance(board, chess.Board) or not board.is_valid():
        return _abstain('invalid_starting_board')
    try:
        selected = chess.Move.from_uci(selected_uci)
    except (ValueError, TypeError, AttributeError):
        return _abstain('invalid_selected_move')
    if selected not in board.legal_moves:
        return _abstain('illegal_selected_move')
    if claim.get('kind') == 'square_occupation':
        if set(claim) != {'kind', 'board', 'square', 'piece'}:
            return _abstain('unsupported_occupation_fields')
        if claim['board'] not in ('before', 'after_selected_move'):
            return _abstain('unsupported_board_stage')
        square = claim['square']
        if not isinstance(square, str) or not re.fullmatch('[a-h][1-8]', square):
            return _abstain('invalid_square')
        piece = claim['piece']
        if piece is not None and (not isinstance(piece, dict) or set(piece) != {'type', 'color'}
                or piece['type'] not in ('pawn', 'knight', 'bishop', 'rook', 'queen', 'king')
                or piece['color'] not in ('white', 'black')):
            return _abstain('invalid_piece_claim')
        replay = board.copy(stack=True)
        if claim['board'] == 'after_selected_move':
            replay.push(selected)
        observed = replay.piece_at(chess.parse_square(square))
        actual = None if observed is None else {
            'type': chess.piece_name(observed.piece_type), 'color': chess.COLOR_NAMES[observed.color]}
        if cf.canonical(piece) != cf.canonical(actual):
            return _abstain('contradicted_by_replayed_occupation')
        return {'schema': SCHEMA, 'status': 'verified_board_fact', 'kind': 'square_occupation',
                'evidence_id': evidence_id, 'board': claim['board'], 'square': square}
    if claim.get('kind') == 'variation_legality':
        if set(claim) != {'kind', 'origin', 'moves_uci'}:
            return _abstain('unsupported_variation_fields')
        if claim['origin'] not in ('asserted_variation', 'retained_engine_pv'):
            return _abstain('unsupported_variation_origin')
        moves = claim['moves_uci']
        if not isinstance(moves, list) or not 1 <= len(moves) <= MAX_VARIATION_PLIES:
            return _abstain('empty_or_excessive_variation')
        if any(not isinstance(move, str) or not re.fullmatch('[a-h][1-8][a-h][1-8][qrbn]?', move)
               for move in moves):
            return _abstain('invalid_uci_variation')
        if moves[0] != selected_uci:
            return _abstain('variation_does_not_start_with_selected_move')
        retained = claim['origin'] == 'retained_engine_pv'
        if retained and moves != retained_pv:
            return _abstain('differs_from_retained_engine_pv')
        replay = board.copy(stack=True)
        for index, text in enumerate(moves):
            move = chess.Move.from_uci(text)
            if move not in replay.legal_moves:
                return {**_abstain('illegal_variation_move'), 'failed_ply': index + 1}
            replay.push(move)
        return {'schema': SCHEMA, 'status': 'verified_legal_variation', 'evidence_id': evidence_id,
                'plies': len(moves), 'origin': claim['origin'], 'legality_only': True,
                'engine_attribution_verified': retained, 'engine_scores_independently_reproduced': False}
    return _abstain('unsupported_claim_or_quality_assertion')


def validate_extended_claim(data_root, source_receipt_path, expected_source_sha256, packet,
                            position_id, evidence_id, claim):
    """Validate source integrity first, then a single strict structured assertion.

    Integrity errors raise ValueError rather than becoming a plausible claim
    verdict. Unknown references and unsupported/contradicted claims abstain.
    Only the retained development projection is used for board reconstruction.
    This evaluator is not a no-forward generator packet or a capability result.
    """
    adapter.validate_typed_position_evidence(data_root, source_receipt_path,
                                           expected_source_sha256, packet)
    if not isinstance(position_id, str) or not isinstance(evidence_id, str):
        return _abstain('invalid_reference_type')
    row = next((r for r in packet['positions'] if r['position_id'] == position_id), None)
    if row is None or row['status'] != 'succeeded':
        return _abstain('unknown_or_failed_position')
    candidate = next((c for c in row['engine_evidence'] if c['evidence_id'] == evidence_id), None)
    if candidate is None:
        return _abstain('unknown_position_bound_evidence')
    projection, _ = cf.load_development(Path(data_root))
    case = next(c for c in projection['items'] if c['position_id'] == position_id)
    result = _replayed_claim(cf.board_for(case), candidate['move_uci'], candidate['pv_uci'],
                             evidence_id, claim)
    return {**result, 'source_receipt_sha256': expected_source_sha256,
            'typed_packet_sha256': cf.digest(cf.canonical(packet)),
            'validator_sha256': cf.file_digest(Path(__file__)),
            'evaluation_only': True}
