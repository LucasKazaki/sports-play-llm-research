"""One legal alternative proposal; all conditional evidence stays evaluator-side.

This version removes v4's brittle fixed hypothesis, modality and uncertainty
tokens from model output. It retains v4's board-verified witness algorithm as
a pinned dependency, and does not reinterpret or repair any earlier response.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v4 as previous
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v5'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v5'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v5'
CLAIM_KIND = 'alternative_proposal'
PROMPT = """Consider only the selected legal move in the supplied pre-move board.
The score is a qualified observation, not a reason or move ranking. You have
no engine line, alternative score, post-move board, reply list, or review
label. If you can identify another legal move by the SAME piece from the SAME
square, propose exactly one. An offline checker will search for a conditional
legal illustration after your answer. A proposal is not a claim that the move
is better, forced, or chosen by Stockfish. If you cannot verify the move from
the FEN, abstain. Return only one of these exact JSON shapes, with no prose:
{"schema":"chess-no-forward-teaching-output/v5","kind":"abstention"}
or:
{"schema":"chess-no-forward-teaching-output/v5",
 "kind":"alternative_proposal","selected_uci":"COPY_SELECTED_UCI",
 "alternative_uci":"ONE_LEGAL_SAME_ORIGIN_UCI"}"""


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
    tactical._exact(claim, ('schema', 'kind', 'selected_uci', 'alternative_uci'),
                    'invalid_claim_shape')
    _require(claim['kind'] == CLAIM_KIND, 'unsupported_claim_kind')
    _require(claim['selected_uci'] == selected.uci(), 'selected_move_mismatch')
    alternative = tactical._legal_move(board, claim['alternative_uci'],
                                        'illegal_alternative')
    _require(alternative != selected and
             alternative.from_square == selected.from_square,
             'alternative_not_same_moved_piece')
    return alternative


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Check a model proposal, then derive at most one conditional witness."""
    packet, board, selected = _verified(packet_bytes, packet_sha256,
                                        source_binding)
    base = {
        'schema': RESULT_SCHEMA, 'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(_projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'witness_dependency_sha256': cf.file_digest(Path(previous.__file__)),
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
            tactical._exact(claim, ('schema', 'kind'), 'invalid_abstention_shape')
            decision, reason, teaching_text = 'model_abstention', 'model_abstained', None
        else:
            alternative = _checked_alternative(board, selected, claim)
            alternative_uci = alternative.uci()
            witnesses, counts = previous._candidate_witnesses(
                board, selected, alternative)
            if witnesses:
                witness = witnesses[0]
                decision, reason = 'verified_conditional_option', None
                teaching_text = previous._teaching_text(
                    board, selected, alternative, witness)
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
