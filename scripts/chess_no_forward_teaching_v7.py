"""Check one model-authored, no-forward conditional queen-defense comparison.

The model gets nine pre-move fields and names its own alternative, common
reply, follow-up captures, defender, protected branch, and lesson draft. This
module only verifies those choices after generation. It never chooses a
replacement line, attributes the motif to the engine, or rates teaching value.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v5 as proposal_v5
import chess_no_forward_teaching_v6 as defense_v6
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v7'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v7'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v7'
CLAIM_KIND = 'conditional_queen_defense'
MECHANISM = 'sole_bishop_defense_blocks_king_capture'
CLAIM_FIELDS = ('schema', 'kind', 'selected_uci', 'alternative_uci',
                'reply_uci', 'selected_capture_uci',
                'alternative_capture_uci', 'protected_branch',
                'defender_square', 'hypothesis', 'lesson_draft')
PROMPT = """Use only the source-bound pre-move board and selected move in the
user JSON. Its engine score is a qualified observation, not a reason. You have
no engine continuation, post-move board, opponent reply list, alternative
score, or Game Review label. If you can legally replay one alternative by the
same piece from the same square, one reply with identical SAN in both branches,
and a checking queen capture in each branch, you may propose a comparison.
Choose the reply and captures yourself. Name which branch's queen is protected
by exactly one bishop from an immediate king capture and its bishop square;
the other capture must allow the immediate king capture. Do not say that the
alternative prevents the common reply, is best, explains the score, or forces
the continuation. An offline checker will verify every selected move and a
strictly bounded lesson draft. If unsure, abstain. Return only JSON, exactly:
{"schema":"chess-no-forward-teaching-output/v7","kind":"abstention"}
or:
{"schema":"chess-no-forward-teaching-output/v7",
 "kind":"conditional_queen_defense","selected_uci":"COPY_SELECTED_UCI",
 "alternative_uci":"LEGAL_SAME_ORIGIN_UCI","reply_uci":"SHARED_REPLY_UCI",
 "selected_capture_uci":"QUEEN_CAPTURE_UCI_IN_SELECTED_BRANCH",
 "alternative_capture_uci":"QUEEN_CAPTURE_UCI_IN_ALTERNATIVE_BRANCH",
 "protected_branch":"selected_OR_alternative","defender_square":"BISHOP_SQUARE",
 "hypothesis":{"mechanism":"sole_bishop_defense_blocks_king_capture",
               "scope":"one_shared_reply_only"},
 "lesson_draft":"If OPPONENT replies REPLY_SAN, after UNSAFE_MOVE_SAN UNSAFE_CAPTURE_SAN permits KING_CAPTURE_SAN to take the queen. After PROTECTED_MOVE_SAN PROTECTED_CAPTURE_SAN is protected by the bishop on BISHOP_SQUARE, so HYPOTHETICAL_KING_CAPTURE_SAN is illegal. This is one conditional line; other replies and move quality are unchecked."}
The lesson wording and punctuation must match this pattern with board-accurate
values; this limits what a mechanical checker can certify. Do not add prose."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise tactical.ClaimRejected(reason)


def _projection(packet: dict, packet_sha256: str) -> dict:
    projected = proposal_v5._projection(packet, packet_sha256)
    projected['schema'] = INPUT_SCHEMA
    projected['assertion_kinds'] = [CLAIM_KIND, 'abstention']
    return projected


def build_generator_input(packet_bytes: bytes, packet_sha256: str, *,
                          source_binding: dict) -> bytes:
    packet, _, _ = proposal_v5._verified(packet_bytes, packet_sha256,
                                         source_binding)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes: bytes, packet_sha256: str, *,
                       source_binding: dict) -> list[dict]:
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _checked_claim(board: chess.Board, selected: chess.Move,
                   claim: dict) -> chess.Move:
    tactical._exact(claim, CLAIM_FIELDS, 'invalid_claim_shape')
    _require(claim['kind'] == CLAIM_KIND, 'unsupported_claim_kind')
    _require(claim['selected_uci'] == selected.uci(), 'selected_move_mismatch')
    tactical._exact(claim['hypothesis'], ('mechanism', 'scope'),
                    'invalid_hypothesis_shape')
    _require(claim['hypothesis'] == {
        'mechanism': MECHANISM, 'scope': 'one_shared_reply_only'},
        'unsupported_hypothesis')
    _require(claim['protected_branch'] in ('selected', 'alternative'),
             'invalid_protected_branch')
    _require(type(claim['defender_square']) is str,
             'invalid_defender_square')
    try:
        chess.parse_square(claim['defender_square'])
    except ValueError as error:
        raise tactical.ClaimRejected('invalid_defender_square') from error
    _require(type(claim['lesson_draft']) is str and
             0 < len(claim['lesson_draft']) <= 400,
             'invalid_lesson_draft')
    alternative = tactical._legal_move(board, claim['alternative_uci'],
                                       'illegal_alternative')
    _require(alternative != selected and
             alternative.from_square == selected.from_square,
             'alternative_not_same_moved_piece')
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.QUEEN, board.turn),
             'selected_piece_not_queen')
    return alternative


def _model_line(board: chess.Board, selected: chess.Move,
                alternative: chess.Move, claim: dict) -> tuple:
    """Replay only the moves named by the model; never enumerate a substitute."""
    selected_board = board.copy(stack=False)
    alternative_board = board.copy(stack=False)
    selected_board.push(selected)
    alternative_board.push(alternative)
    selected_reply = tactical._legal_move(selected_board, claim['reply_uci'],
                                          'illegal_model_reply')
    alternative_reply = tactical._legal_move(
        alternative_board, claim['reply_uci'], 'illegal_model_reply')
    reply_san = selected_board.san(selected_reply)
    _require(reply_san == alternative_board.san(alternative_reply),
             'different_reply_san')
    selected_board.push(selected_reply)
    alternative_board.push(alternative_reply)
    selected_capture = tactical._legal_move(
        selected_board, claim['selected_capture_uci'],
        'illegal_selected_capture')
    alternative_capture = tactical._legal_move(
        alternative_board, claim['alternative_capture_uci'],
        'illegal_alternative_capture')
    return (selected_board, alternative_board, selected_capture,
            alternative_capture, reply_san)


def _checked_contrast(board: chess.Board, selected: chess.Move,
                      alternative: chess.Move, claim: dict) -> tuple[dict | None, str]:
    selected_board, alternative_board, selected_capture, alternative_capture, reply_san = (
        _model_line(board, selected, alternative, claim))
    selected_detail = defense_v6._capture_with_check(
        selected_board, selected_capture, selected.to_square)
    alternative_detail = defense_v6._capture_with_check(
        alternative_board, alternative_capture, alternative.to_square)
    if selected_detail is None or alternative_detail is None:
        return None, reply_san
    if claim['protected_branch'] == 'alternative':
        unsafe_board, unsafe_move, unsafe_detail = (
            selected_board, selected_capture, selected_detail)
        safe_board, safe_move, safe_detail = (
            alternative_board, alternative_capture, alternative_detail)
    else:
        unsafe_board, unsafe_move, unsafe_detail = (
            alternative_board, alternative_capture, alternative_detail)
        safe_board, safe_move, safe_detail = (
            selected_board, selected_capture, selected_detail)
    contrast = defense_v6._checked_pair(
        unsafe_board, safe_board, unsafe_move, safe_move,
        claim['reply_uci'], reply_san,
        selected_detail=unsafe_detail, alternative_detail=safe_detail)
    if contrast is None:
        # If the other branch, rather than the named branch, has the complete
        # protected/unsafe relationship, the model's directional claim is false.
        other = defense_v6._checked_pair(
            safe_board, unsafe_board, safe_move, unsafe_move,
            claim['reply_uci'], reply_san,
            selected_detail=safe_detail, alternative_detail=unsafe_detail)
        _require(other is None, 'unverified_protected_branch')
        return None, reply_san
    _require(contrast['alternative_capture']['defenders'] == [
        {'square': claim['defender_square'], 'piece': 'bishop'}],
        'defender_square_mismatch')
    # v6's private pair helper names its parameters by safety role. Restore
    # the model's actual selected/alternative labels before returning a v7
    # witness, including when the selected move is the protected one.
    return {**contrast,
            'selected_capture': selected_detail,
            'alternative_capture': alternative_detail,
            'unprotected_capture': contrast['selected_capture'],
            'protected_capture': contrast['alternative_capture'],
            'protected_branch': claim['protected_branch']}, reply_san


def _expected_lesson(board: chess.Board, selected: chess.Move,
                     alternative: chess.Move, contrast: dict,
                     protected_branch: str) -> str:
    opponent = 'Black' if board.turn == chess.WHITE else 'White'
    if protected_branch == 'alternative':
        unsafe_move, safe_move = selected, alternative
    else:
        unsafe_move, safe_move = alternative, selected
    unsafe = contrast['unprotected_capture']
    safe = contrast['protected_capture']
    king_capture_san = next(
        item['san'] for item in unsafe['legal_opponent_replies']
        if item['uci'] == unsafe['king_capture_uci'])
    return (
        f'If {opponent} replies {contrast["reply_san"]}, after '
        f'{board.san(unsafe_move)} {unsafe["san"]} permits '
        f'{king_capture_san} to take the queen. After '
        f'{board.san(safe_move)} {safe["san"]} is protected by the bishop '
        f'on {safe["defenders"][0]["square"]}, so '
        f'{contrast["bishop_removal_king_capture_san"]} is illegal. '
        'This is one conditional line; other replies and move quality are '
        'unchecked.')


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Verify a frozen model response against the source board, without inference."""
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    base = {
        'schema': RESULT_SCHEMA, 'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(_projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'v5_projection_dependency_sha256': cf.file_digest(Path(proposal_v5.__file__)),
        'v6_defense_dependency_sha256': cf.file_digest(Path(defense_v6.__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'model_calls': 0, 'engine_calls': 0, 'quality_evaluated': False,
    }
    values = {'model_alternative_uci': None, 'model_reply_uci': None,
              'model_selected_capture_uci': None,
              'model_alternative_capture_uci': None,
              'protected_branch': None, 'model_lesson_sha256': None,
              'defense_contrast': None, 'teaching_text': None}
    try:
        claim, raw = tactical._parse_json(raw_response)
        _require(type(claim) is dict, 'invalid_claim_shape')
        _require(claim.get('schema') == CLAIM_SCHEMA, 'invalid_claim_schema')
        if claim.get('kind') == 'abstention':
            tactical._exact(claim, ('schema', 'kind'), 'invalid_abstention_shape')
            decision, reason = 'model_abstention', 'model_abstained'
        else:
            alternative = _checked_claim(board, selected, claim)
            values.update(
                model_alternative_uci=alternative.uci(),
                model_reply_uci=claim['reply_uci'],
                model_selected_capture_uci=claim['selected_capture_uci'],
                model_alternative_capture_uci=claim['alternative_capture_uci'],
                protected_branch=claim['protected_branch'],
                model_lesson_sha256=cf.digest(claim['lesson_draft'].encode('utf-8')))
            contrast, _ = _checked_contrast(board, selected, alternative, claim)
            if contrast is None:
                decision, reason = 'evaluator_abstention', 'no_verified_conditional_contrast'
            else:
                _require(claim['lesson_draft'] == _expected_lesson(
                    board, selected, alternative, contrast,
                    claim['protected_branch']), 'unsupported_lesson_draft')
                values.update(defense_contrast=contrast,
                              teaching_text=claim['lesson_draft'])
                decision, reason = 'verified_model_conditional_comparison', None
        response_sha256 = cf.digest(raw)
    except tactical.ClaimRejected as error:
        decision, reason = 'rejected', str(error)
        response_sha256 = tactical._response_digest(raw_response)
    return {**base, **values, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason}
