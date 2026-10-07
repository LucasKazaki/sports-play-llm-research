"""No-forward alternative proposal with an evaluator-only conditional witness.

The generator sees the same nine pre-move fields as v3. It proposes only a
same-origin alternative or abstains. All reply and later-option enumeration is
offline, after generation, and cannot be fed into this response. A witness is a
legal conditional illustration, not a claim that the alternative is better.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v3 as previous
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v4'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v4'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v4'
CLAIM_KIND = 'alternative_hypothesis'
HYPOTHESIS = 'moved_piece_conditional_option'
ABSTENTION_REASONS = frozenset(('insufficient_evidence',
                                'no_defensible_alternative'))
MAX_COMMON_REPLIES = 256
MAX_OPTIONS_EXAMINED = 8192
PROPERTY_PRIORITY = {'capture_with_check': 0, 'mate': 1,
                     'capture': 2, 'check': 3}
PROMPT = """Consider only the selected legal move in the supplied pre-move board.
The score is an observation, not a reason or move ranking. You have no engine
line, alternative score, post-move board, reply list or review label. Propose
one other legal move by the SAME piece from the SAME square if you have a
bounded hypothesis that the piece may have a different later option. Do not
invent an opponent reply or later move: an offline evaluator will search for
one legal conditional illustration after your response. Do not call the
alternative better, forced, or Stockfish's choice. Return only JSON, exactly:
{"schema":"chess-no-forward-teaching-output/v4","kind":"abstention",
 "reason":"insufficient_evidence"}
or:
{"schema":"chess-no-forward-teaching-output/v4",
 "kind":"alternative_hypothesis","selected_uci":"COPY_SELECTED_UCI",
 "alternative_uci":"PROPOSE_LEGAL_SAME_ORIGIN_UCI",
 "hypothesis":"moved_piece_conditional_option",
 "modality":"candidate_only",
 "uncertainty":"other_replies_and_engine_intent_unverified"}
If you cannot verify the alternative from the FEN, abstain. No prose or scores."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise tactical.ClaimRejected(reason)


def _verified(packet_bytes: bytes, packet_sha256: str, source_binding: dict):
    board, selected = tactical._source_board(
        packet_bytes, packet_sha256, source_binding)
    return json.loads(packet_bytes), board, selected


def _projection(packet: dict, packet_sha256: str) -> dict:
    projected = previous._projection(packet, packet_sha256)
    projected['schema'] = INPUT_SCHEMA
    projected['assertion_kinds'] = [CLAIM_KIND, 'abstention']
    return projected


def build_generator_input(packet_bytes: bytes, packet_sha256: str, *,
                          source_binding: dict) -> bytes:
    packet, _, _ = _verified(packet_bytes, packet_sha256, source_binding)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes: bytes, packet_sha256: str, *,
                       source_binding: dict) -> list[dict]:
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _checked_alternative(board: chess.Board, selected: chess.Move,
                         claim: dict) -> chess.Move:
    tactical._exact(claim, ('schema', 'kind', 'selected_uci', 'alternative_uci',
                            'hypothesis', 'modality', 'uncertainty'),
                    'invalid_claim_shape')
    _require(claim['kind'] == CLAIM_KIND, 'unsupported_claim_kind')
    _require(claim['selected_uci'] == selected.uci(), 'selected_move_mismatch')
    _require(claim['hypothesis'] == HYPOTHESIS, 'unsupported_hypothesis')
    _require(claim['modality'] == 'candidate_only', 'ranked_or_forced_claim_forbidden')
    _require(claim['uncertainty'] == 'other_replies_and_engine_intent_unverified',
             'unsupported_uncertainty')
    alternative = tactical._legal_move(board, claim['alternative_uci'],
                                        'illegal_alternative')
    _require(alternative != selected and
             alternative.from_square == selected.from_square,
             'alternative_not_same_moved_piece')
    return alternative


def _property(board: chess.Board, move: chess.Move) -> str | None:
    captured = board.is_capture(move)
    after = board.copy(stack=False)
    after.push(move)
    check = after.is_check()
    if captured and check:
        return 'capture_with_check'
    if after.is_checkmate():
        return 'mate'
    if captured:
        return 'capture'
    if check:
        return 'check'
    return None


def _candidate_witnesses(board: chess.Board, selected: chess.Move,
                         alternative: chess.Move) -> tuple[list[dict], dict]:
    """Enumerate legal replies and moved-piece options after generation only."""
    selected_after = board.copy(stack=False)
    alternative_after = board.copy(stack=False)
    selected_after.push(selected)
    alternative_after.push(alternative)
    selected_replies = {move.uci(): move for move in selected_after.legal_moves}
    alternative_replies = {move.uci(): move for move in alternative_after.legal_moves}
    common = sorted(set(selected_replies) & set(alternative_replies))
    if len(common) > MAX_COMMON_REPLIES:
        raise tactical.ClaimRejected('reply_search_budget_exceeded')
    counts = {'common_reply_uci_count': len(common),
              'same_san_reply_count': 0,
              'comparable_moved_piece_reply_count': 0,
              'moved_piece_options_examined': 0,
              'exclusive_concrete_witness_count': 0}
    witnesses = []
    for reply_uci in common:
        chosen_reply = selected_replies[reply_uci]
        other_reply = alternative_replies[reply_uci]
        chosen_san = selected_after.san(chosen_reply)
        other_san = alternative_after.san(other_reply)
        if chosen_san != other_san:
            continue
        reply_captures_in_both = (selected_after.is_capture(chosen_reply) and
                                  alternative_after.is_capture(other_reply))
        counts['same_san_reply_count'] += 1
        chosen_board = selected_after.copy(stack=False)
        other_board = alternative_after.copy(stack=False)
        chosen_board.push(chosen_reply)
        other_board.push(other_reply)
        chosen_piece = chosen_board.piece_at(selected.to_square)
        other_piece = other_board.piece_at(alternative.to_square)
        if (chosen_piece is None or other_piece is None or
                chosen_piece.color != other_piece.color or
                chosen_piece.color != board.turn or
                chosen_piece.piece_type != other_piece.piece_type):
            continue
        counts['comparable_moved_piece_reply_count'] += 1
        options = sorted((move for move in other_board.legal_moves
                          if move.from_square == alternative.to_square),
                         key=lambda move: move.uci())
        counts['moved_piece_options_examined'] += len(options)
        if counts['moved_piece_options_examined'] > MAX_OPTIONS_EXAMINED:
            raise tactical.ClaimRejected('option_search_budget_exceeded')
        for option in options:
            equivalent = chess.Move(selected.to_square, option.to_square,
                                    promotion=option.promotion)
            if equivalent in chosen_board.legal_moves:
                continue
            prop = _property(other_board, option)
            if prop is None:
                continue
            witnesses.append({
                'reply_uci': reply_uci, 'reply_san': other_san,
                'option_uci': option.uci(), 'option_san': other_board.san(option),
                'option_target': chess.square_name(option.to_square),
                'piece': chess.piece_name(other_piece.piece_type),
                'property': prop,
                'reply_captures_in_both_branches': reply_captures_in_both,
            })
    counts['exclusive_concrete_witness_count'] = len(witnesses)
    witnesses.sort(key=lambda item: (
        0 if item['reply_captures_in_both_branches'] else 1,
        PROPERTY_PRIORITY[item['property']], item['reply_uci'],
        item['option_uci']))
    return witnesses, counts


def _teaching_text(board: chess.Board, selected: chess.Move,
                   alternative: chess.Move, witness: dict) -> str:
    mover = 'Black' if board.turn == chess.WHITE else 'White'
    selected_san, alternative_san = board.san(selected), board.san(alternative)
    piece_origin = 'promoted' if alternative.promotion is not None else 'moved'
    return (
        f'After {alternative_san}, if {mover} plays {witness["reply_san"]}, '
        f'the {piece_origin} {witness["piece"]} can play {witness["option_san"]}. '
        f'After {selected_san} and the same reply, that piece cannot legally '
        f'move to {witness["option_target"]}. This is one conditional legal '
        'illustration; other replies, move quality, and the engine\'s reasoning '
        'remain unchecked.'
    )


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Check one model proposal and derive at most one offline legal witness."""
    packet, board, selected = _verified(packet_bytes, packet_sha256,
                                        source_binding)
    base = {
        'schema': RESULT_SCHEMA, 'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(_projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'previous_projection_dependency_sha256': cf.file_digest(Path(previous.__file__)),
        'model_calls': 0, 'engine_calls': 0, 'quality_evaluated': False,
    }
    witness = None
    counts = None
    alternative_uci = None
    try:
        claim, raw = tactical._parse_json(raw_response)
        _require(type(claim) is dict, 'invalid_claim_shape')
        _require(claim.get('schema') == CLAIM_SCHEMA, 'invalid_claim_schema')
        if claim.get('kind') == 'abstention':
            tactical._exact(claim, ('schema', 'kind', 'reason'),
                            'invalid_abstention_shape')
            _require(type(claim['reason']) is str and
                     claim['reason'] in ABSTENTION_REASONS,
                     'invalid_abstention_reason')
            decision, reason, teaching_text = 'model_abstention', claim['reason'], None
        else:
            alternative = _checked_alternative(board, selected, claim)
            alternative_uci = alternative.uci()
            witnesses, counts = _candidate_witnesses(board, selected, alternative)
            if witnesses:
                witness = witnesses[0]
                decision, reason = 'verified_conditional_option', None
                teaching_text = _teaching_text(board, selected, alternative, witness)
            else:
                decision, reason, teaching_text = (
                    'evaluator_abstention', 'no_conditional_witness', None)
        response_sha256 = cf.digest(raw)
    except tactical.ClaimRejected as error:
        decision, reason, teaching_text = 'rejected', str(error), None
        response_sha256 = tactical._response_digest(raw_response)
    return {**base, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason,
            'model_alternative_uci': alternative_uci,
            'witness': witness, 'witness_search_counts': counts,
            'teaching_text': teaching_text}
