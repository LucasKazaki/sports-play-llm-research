"""Offline check of one model-named, conditional promotion contrast.

This version is a development checker, not a model runner or quality verdict.
All four moves in a claim must come from the model before this evaluator replays
them. No engine search, answer label, or reply menu enters the input projection.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v5 as proposal_v5
import chess_no_forward_teaching_v8 as teaching_v8
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-endgame-promotion-contrast-input/v11'
CLAIM_SCHEMA = 'chess-endgame-promotion-contrast-output/v11'
RESULT_SCHEMA = 'chess-endgame-promotion-contrast-evaluation/v11'
KIND = 'promotion_contrast'
SCOPE = 'one_shared_reply_only'
PLY = 93
CLAIM_FIELDS = ('schema', 'kind', 'selected_uci', 'alternative_uci',
                'shared_reply_uci', 'selected_capture_uci', 'scope')
PROMPT = """Use only the verified pre-move board and selected move in the user JSON.
The qualified score is an observation, not a reason or comparison. If you can
name another legal rook move from the same square, one opponent promotion move
legal after both roots, and a selected-branch rook capture of the promoted
piece, return exactly the typed JSON claim below. An offline checker will test
both branches after your answer. You have no reply list, engine line, alternative
score, post-move board, or Game Review label. Do not claim that a reply is
forced, a capture is safe, a move is better or worse, or what Stockfish intends.
If unsure, abstain. Return one exact JSON object with no prose:
{"schema":"chess-endgame-promotion-contrast-output/v11","kind":"abstention"}
or:
{"schema":"chess-endgame-promotion-contrast-output/v11",
"kind":"promotion_contrast","selected_uci":"...","alternative_uci":"...",
"shared_reply_uci":"...","selected_capture_uci":"...",
"scope":"one_shared_reply_only"}"""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise tactical.ClaimRejected(reason)


def _verified_case(packet_bytes: bytes, packet_sha256: str,
                   source_binding: dict) -> tuple[dict, chess.Board, chess.Move]:
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    _require(teaching_v8._case(packet, board, selected) == 'passed_pawn' and
             packet['source']['selected_ply'] == PLY,
             'unsupported_development_case')
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.ROOK, board.turn), 'selected_piece_not_rook')
    return packet, board, selected


def _projection(packet: dict, packet_sha256: str) -> dict:
    # Explicit nine-field allowlist. Packet shape and fresh source are checked
    # before this function is reached; no evaluator continuation is projected.
    return {
        'schema': INPUT_SCHEMA, 'source_packet_sha256': packet_sha256,
        'source': packet['source'], 'fen': packet['fen'],
        'side_to_move': packet['side_to_move'],
        'selected_move': packet['selected_move'],
        'transition': packet['transition'],
        'engine_observation': packet['engine_observation'],
        'assertion_kinds': [KIND, 'abstention'],
    }


def build_generator_input(packet_bytes: bytes, packet_sha256: str, *,
                          source_binding: dict) -> bytes:
    """Prepare safe bytes for a future runner; this module never dispatches."""
    packet, _, _ = _verified_case(packet_bytes, packet_sha256, source_binding)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes: bytes, packet_sha256: str, *,
                       source_binding: dict) -> list[dict]:
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _after(board: chess.Board, move: chess.Move) -> chess.Board:
    result = board.copy(stack=False)
    result.push(move)
    return result


def _contrast(board: chess.Board, selected: chess.Move,
              claim: dict) -> tuple[dict | None, str | None, str | None]:
    """Replay only named moves, then inspect immediate rook captures."""
    _require(claim['selected_uci'] == selected.uci(), 'selected_move_mismatch')
    _require(claim['scope'] == SCOPE, 'unsupported_scope')
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.ROOK, board.turn), 'selected_piece_not_rook')
    alternative = tactical._legal_move(board, claim['alternative_uci'],
                                       'illegal_model_alternative')
    _require(alternative != selected and
             alternative.from_square == selected.from_square,
             'alternative_not_distinct_same_rook')
    selected_after = _after(board, selected)
    alternative_after = _after(board, alternative)
    reply_selected = tactical._legal_move(selected_after,
                                           claim['shared_reply_uci'],
                                           'reply_not_legal_after_selected')
    reply_alternative = tactical._legal_move(alternative_after,
                                              claim['shared_reply_uci'],
                                              'reply_not_legal_after_alternative')
    _require(reply_selected == reply_alternative and
             reply_selected.promotion in chess.PIECE_TYPES and
             reply_selected.promotion not in (chess.KING, chess.PAWN),
             'shared_reply_not_promotion')
    _require(selected_after.piece_at(reply_selected.from_square) ==
             chess.Piece(chess.PAWN, not board.turn) and
             alternative_after.piece_at(reply_alternative.from_square) ==
             chess.Piece(chess.PAWN, not board.turn),
             'shared_reply_not_opponent_pawn')
    selected_reply_san = selected_after.san(reply_selected)
    alternative_reply_san = alternative_after.san(reply_alternative)
    selected_replied = _after(selected_after, reply_selected)
    alternative_replied = _after(alternative_after, reply_alternative)
    target = reply_selected.to_square
    promoted = chess.Piece(reply_selected.promotion, not board.turn)
    _require(selected_replied.piece_at(target) == promoted and
             alternative_replied.piece_at(target) == promoted,
             'promoted_piece_target_mismatch')
    capture = tactical._legal_move(selected_replied,
                                    claim['selected_capture_uci'],
                                    'illegal_selected_capture')
    _require(capture.from_square == selected.to_square and
             capture.to_square == target and
             selected_replied.piece_at(capture.from_square) ==
             chess.Piece(chess.ROOK, board.turn) and
             selected_replied.is_capture(capture),
             'selected_capture_not_promoted_piece')
    immediate_rook_captures = [
        move.uci() for move in alternative_replied.legal_moves
        if (move.to_square == target and
            alternative_replied.is_capture(move) and
            alternative_replied.piece_at(move.from_square) ==
            chess.Piece(chess.ROOK, board.turn))]
    if immediate_rook_captures:
        return None, None, 'alternative_has_immediate_rook_capture'
    selected_san = board.san(selected)
    alternative_san = board.san(alternative)
    capture_san = selected_replied.san(capture)
    witness = {
        'selected_uci': selected.uci(), 'selected_san': selected_san,
        'alternative_uci': alternative.uci(),
        'alternative_san': alternative_san,
        'shared_reply_uci': reply_selected.uci(),
        'selected_reply_san': selected_reply_san,
        'alternative_reply_san': alternative_reply_san,
        'promoted_piece': promoted.symbol().upper(),
        'promotion_square': chess.square_name(target),
        'selected_capture_uci': capture.uci(),
        'selected_capture_san': capture_san,
        'alternative_immediate_rook_captures': [],
    }
    text = (f'After {selected_san}, if the opponent plays '
            f'{selected_reply_san}, {capture_san} is a legal rook capture '
            f'of the promoted piece. After {alternative_san} and the same '
            'legal reply, no immediate rook capture of that piece is legal. '
            'This is one conditional line; it does not establish that the '
            'reply is forced, that the capture is safe, or that either root '
            'move is better.')
    return witness, text, None


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Check source first, then one raw model claim, without model or engine."""
    packet, board, selected = _verified_case(packet_bytes, packet_sha256,
                                              source_binding)
    base = {
        'schema': RESULT_SCHEMA,
        'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(
            _projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'v5_source_dependency_sha256': cf.file_digest(Path(proposal_v5.__file__)),
        'v8_case_dependency_sha256': cf.file_digest(Path(teaching_v8.__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'development_case': True, 'quality_evaluated': False,
        'model_calls_v11': 0, 'engine_calls_v11': 0,
    }
    witness = teaching_text = None
    try:
        claim, parsed_raw = teaching_v8._parse_claim(raw_response)
        _require(claim.get('schema') == CLAIM_SCHEMA, 'invalid_claim_schema')
        kind = claim.get('kind')
        _require(type(kind) is str and kind in (KIND, 'abstention'),
                 'unsupported_claim_kind')
        if kind == 'abstention':
            tactical._exact(claim, ('schema', 'kind'),
                            'invalid_abstention_shape')
            decision, reason = 'model_abstention', 'model_abstained'
        else:
            tactical._exact(claim, CLAIM_FIELDS, 'invalid_claim_shape')
            witness, teaching_text, no_witness = _contrast(board, selected,
                                                            claim)
            if no_witness:
                decision, reason = 'evaluator_abstention', no_witness
            else:
                decision, reason = 'verified_conditional_board_fact', None
        response_sha256 = cf.digest(parsed_raw)
    except tactical.ClaimRejected as error:
        decision, reason = 'rejected', str(error)
        response_sha256 = tactical._response_digest(raw_response)
    accounting = {
        'responses': 1,
        'model_abstentions': int(decision == 'model_abstention'),
        'evaluator_abstentions': int(decision == 'evaluator_abstention'),
        'rejections': int(decision == 'rejected'),
        'verified_conditional_board_facts': int(
            decision == 'verified_conditional_board_fact'),
    }
    return {**base, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason,
            'witness': witness, 'teaching_text': teaching_text,
            'accounting': accounting}
