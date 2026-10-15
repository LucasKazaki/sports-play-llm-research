"""Offline, source-bound check of one conditional chess teaching contrast.

The generator input is a strict projection of one verified pre-move packet. It
contains no proposed alternative, reply, continuation, review label or PV. A
model may propose those moves in typed output; only this evaluator replays them.
The fixed sentence reports a legal option difference, not Stockfish intent,
move quality, forced play or independently established teaching quality.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v3'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v3'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v3'
CLAIM_KIND = 'conditional_option_difference'
REASONS = frozenset(('insufficient_evidence', 'no_common_reply',
                     'no_defensible_option_difference'))
PROPERTIES = frozenset(('legal', 'capture', 'check', 'capture_with_check', 'mate'))
PIECES = frozenset(('pawn', 'knight', 'bishop', 'rook', 'queen', 'king'))
PROMOTIONS = {None: None, 'q': chess.QUEEN, 'r': chess.ROOK,
              'b': chess.BISHOP, 'n': chess.KNIGHT}
PROMPT = """Explain only the one selected legal move in the supplied pre-move board.
The score is an observation, not a reason or a ranking. You have no engine line,
alternative score, post-move board or review label. You may propose one legal
alternative by the SAME piece from the SAME square, one opponent reply that is
legal after either move, and one later option for that moved piece. The output
claims only a conditional difference in option legality, never that the reply
is best, forced, or chosen by Stockfish. Return only JSON, with exactly either:
{"schema":"chess-no-forward-teaching-output/v3","kind":"abstention",
 "reason":"insufficient_evidence"}
or:
{"schema":"chess-no-forward-teaching-output/v3",
 "kind":"conditional_option_difference","selected_uci":"COPY_SELECTED_UCI",
 "alternative_uci":"PROPOSE_LEGAL_UCI","common_reply_uci":"PROPOSE_LEGAL_UCI",
 "option":{"piece":"pawn|knight|bishop|rook|queen|king",
           "to":"SQUARE","promotion":null,
           "property":"legal|capture|check|capture_with_check|mate"},
 "relation":"legal_only_after_alternative",
 "modality":"possible_if_common_reply",
 "uncertainty":"other_replies_and_engine_intent_unverified"}
The evaluator will reject illegal or unsupported claims. If unsure, abstain.
Do not add prose, scores, PVs, reasons attributed to the engine, or move labels."""


def _require(condition, reason):
    if not condition:
        raise tactical.ClaimRejected(reason)


def _verified(packet_bytes, packet_sha256, source_binding):
    board, selected = tactical._source_board(packet_bytes, packet_sha256, source_binding)
    return json.loads(packet_bytes), board, selected


def _projection(packet, packet_sha256):
    """Project only prior, allowed fields; replace the old assertion declaration."""
    return {
        'schema': INPUT_SCHEMA, 'source_packet_sha256': packet_sha256,
        'source': packet['source'], 'fen': packet['fen'],
        'side_to_move': packet['side_to_move'],
        'selected_move': packet['selected_move'],
        'transition': packet['transition'],
        'engine_observation': packet['engine_observation'],
        'assertion_kinds': [CLAIM_KIND, 'abstention'],
    }


def build_generator_input(packet_bytes, packet_sha256, *, source_binding):
    """Return safe canonical user bytes after fresh source verification; no POST."""
    packet, _, _ = _verified(packet_bytes, packet_sha256, source_binding)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes, packet_sha256, *, source_binding):
    """Return exactly the system prompt and safe packet for a future runner."""
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _move(board, uci, reason):
    return tactical._legal_move(board, uci, reason)


def _option(board, origin, target, promotion):
    move = chess.Move(origin, target, promotion=PROMOTIONS[promotion])
    return move, move in board.legal_moves


def _property_holds(board, option, prop):
    if prop in ('capture', 'capture_with_check') and not board.is_capture(option):
        return False
    if prop in ('check', 'capture_with_check', 'mate'):
        after = board.copy(stack=False)
        after.push(option)
        if prop == 'mate':
            return after.is_checkmate()
        return after.is_check()
    return True


def _check_claim(board, selected, claim):
    tactical._exact(claim, ('schema', 'kind', 'selected_uci', 'alternative_uci',
                            'common_reply_uci', 'option', 'relation', 'modality',
                            'uncertainty'), 'invalid_claim_shape')
    _require(claim['kind'] == CLAIM_KIND, 'unsupported_claim_kind')
    _require(claim['selected_uci'] == selected.uci(), 'selected_move_mismatch')
    _require(claim['relation'] == 'legal_only_after_alternative',
             'unsupported_relation')
    _require(claim['modality'] == 'possible_if_common_reply',
             'forced_or_best_modality_forbidden')
    _require(claim['uncertainty'] == 'other_replies_and_engine_intent_unverified',
             'unsupported_uncertainty')
    alternative = _move(board, claim['alternative_uci'], 'illegal_alternative')
    _require(alternative != selected and alternative.from_square == selected.from_square,
             'alternative_not_same_moved_piece')
    option = claim['option']
    tactical._exact(option, ('piece', 'to', 'promotion', 'property'),
                    'invalid_option_shape')
    _require(type(option['piece']) is str and option['piece'] in PIECES,
             'invalid_option_piece')
    _require(type(option['to']) is str and tactical.SQUARE.fullmatch(option['to']),
             'invalid_option_square')
    _require(type(option['promotion']) in (str, type(None)) and
             option['promotion'] in PROMOTIONS, 'invalid_option_promotion')
    _require(type(option['property']) is str and option['property'] in PROPERTIES,
             'invalid_option_property')
    selected_board = board.copy(stack=False)
    alternative_board = board.copy(stack=False)
    selected_san, alternative_san = board.san(selected), board.san(alternative)
    selected_board.push(selected)
    alternative_board.push(alternative)
    reply_uci = claim['common_reply_uci']
    selected_reply = _move(selected_board, reply_uci, 'reply_illegal_after_selected')
    alternative_reply = _move(alternative_board, reply_uci,
                              'reply_illegal_after_alternative')
    selected_reply_san = selected_board.san(selected_reply)
    alternative_reply_san = alternative_board.san(alternative_reply)
    _require(selected_reply_san == alternative_reply_san,
             'ambiguous_common_reply')
    selected_board.push(selected_reply)
    alternative_board.push(alternative_reply)
    mover = board.turn
    selected_piece = selected_board.piece_at(selected.to_square)
    alternative_piece = alternative_board.piece_at(alternative.to_square)
    _require(selected_piece is not None and alternative_piece is not None and
             selected_piece.color == alternative_piece.color == mover and
             selected_piece.piece_type == alternative_piece.piece_type,
             'moved_piece_not_comparable_after_reply')
    _require(chess.piece_name(selected_piece.piece_type) == option['piece'],
             'option_piece_mismatch')
    target = chess.parse_square(option['to'])
    selected_option, selected_legal = _option(selected_board, selected.to_square,
                                             target, option['promotion'])
    alternative_option, alternative_legal = _option(
        alternative_board, alternative.to_square, target, option['promotion'])
    _require(alternative_legal and not selected_legal,
             'option_not_exclusive_to_alternative')
    _require(_property_holds(alternative_board, alternative_option,
                             option['property']), 'false_option_property')
    option_san = alternative_board.san(alternative_option)
    opponent = 'Black' if mover == chess.WHITE else 'White'
    piece_origin = 'promoted' if alternative.promotion is not None else 'moved'
    sentence = (
        f'After {alternative_san}, if {opponent} plays {alternative_reply_san}, '
        f'the {piece_origin} {option["piece"]} can play {option_san}. '
        f'After {selected_san} and the same reply, that piece cannot legally '
        f'move to {option["to"]}. Other replies and the engine\'s reasoning '
        'remain unchecked.'
    )
    return sentence


def evaluate(packet_bytes, packet_sha256, raw_response, *, source_binding):
    """Return only checked fixed-template text, or an abstention/rejection.

    Source failures raise; untrusted response failures become rejected results.
    No engine, model, network or evaluator PV is used.
    """
    packet, board, selected = _verified(packet_bytes, packet_sha256, source_binding)
    base = {
        'schema': RESULT_SCHEMA, 'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(_projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'model_calls': 0, 'engine_calls': 0, 'quality_evaluated': False,
    }
    try:
        claim, raw = tactical._parse_json(raw_response)
        _require(type(claim) is dict, 'invalid_claim_shape')
        _require(claim.get('schema') == CLAIM_SCHEMA, 'invalid_claim_schema')
        if claim.get('kind') == 'abstention':
            tactical._exact(claim, ('schema', 'kind', 'reason'), 'invalid_abstention_shape')
            _require(type(claim['reason']) is str and claim['reason'] in REASONS,
                     'invalid_abstention_reason')
            decision, reason, teaching_text = 'admissible_abstention', claim['reason'], None
        else:
            teaching_text = _check_claim(board, selected, claim)
            decision, reason = 'verified_conditional_option', None
        response_sha256 = cf.digest(raw)
    except tactical.ClaimRejected as error:
        decision, reason, teaching_text = 'rejected', str(error), None
        response_sha256 = tactical._response_digest(raw_response)
    return {**base, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason, 'teaching_text': teaching_text}
