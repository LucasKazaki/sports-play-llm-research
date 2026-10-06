"""Development-only typed alternatives and conditional consequences.

The generator receives nine source-bound pre-move fields, never a continuation,
alternative score, or Game Review card. It names exact moves and squares. This
offline checker replays those names and renders bounded board facts. Comparison
scores remain evaluator-only and no move ranking is emitted here.
"""
from __future__ import annotations

from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v5 as proposal_v5
import chess_no_forward_teaching_v8 as v8
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v9'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v9'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v9'
SCOPE = v8.SCOPE
KINDS = v8.KINDS
CLAIM_FIELDS = {
    **v8.CLAIM_FIELDS,
    'queen_escape': ('schema', 'kind', 'selected_uci', 'attacker_square',
                     'target_square', 'alternative_uci',
                     'alternative_target_square', 'conditional_reply_uci',
                     'scope'),
}
PROMPT = """Use only the source-bound pre-move board, selected legal move,
transition facts, and qualified engine observation in the user JSON. That score
is an observation, not a reason. You have no engine continuation, opponent
reply list, alternative score, future board, or Game Review label. Select one
typed mechanism only if you can name its exact squares and legal moves. The
offline checker will replay your choices. A conditional line is one possible
line, not forced play. Do not call any move good, best, bad, worse, a win, or
Stockfish's reason. If unsure, abstain. Return only one exact JSON object:
{"schema":"chess-no-forward-teaching-output/v9","kind":"abstention"}
or a typed claim with schema, kind, selected_uci, and scope set to
"board_geometry_or_named_line_only", plus exactly these fields:
- queen_escape: attacker_square, target_square, alternative_uci,
  alternative_target_square, conditional_reply_uci (null or UCI);
- checking_capture: attacked_queen_square, reply_uci, recapture_uci;
- rook_coordination: supported_rook_square, target_pawn_square,
  alternative_uci, open_file;
- passed_pawn: pawn_square, conditional_line, where conditional_line is null
  or exactly {"reply_uci":"...","capture_uci":"...","recapture_uci":"..."}.
For queen_escape, name a different legal non-queen move that attacks the named
opposing knight; if you name a reply, it must be legal after that alternative.
All moves are UCI. Do not add a lesson draft, evaluation, ranking, or prose."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise tactical.ClaimRejected(reason)


def _projection(packet: dict, packet_sha256: str) -> dict:
    projected = v8._projection(packet, packet_sha256)
    projected['schema'] = INPUT_SCHEMA
    projected['assertion_kinds'] = list(KINDS)
    return projected


def build_generator_input(packet_bytes: bytes, packet_sha256: str, *,
                          source_binding: dict) -> bytes:
    """Reverify retained source and case before exposing the nine-field input."""
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    v8._case(packet, board, selected)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes: bytes, packet_sha256: str, *,
                       source_binding: dict) -> list[dict]:
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _queen_alternative(board: chess.Board, selected: chess.Move,
                       claim: dict) -> tuple[dict, str]:
    # The selected-branch facts are the existing v8 replay, not a copied label.
    selected_witness, _ = v8._queen_escape(board, selected, claim)
    alternative = v8._move(board, claim['alternative_uci'],
                           'illegal_model_alternative')
    _require(alternative != selected and
             board.piece_at(alternative.from_square) is not None and
             board.piece_at(alternative.from_square).piece_type != chess.QUEEN,
             'unverified_nonqueen_alternative')
    target = v8._square(claim['alternative_target_square'],
                        'invalid_alternative_target_square')
    attacker = v8._square(claim['attacker_square'],
                          'invalid_attacker_square')
    enemy = not board.turn
    after_alternative = v8._after(board, alternative)
    queen_square = selected.from_square
    _require(target == attacker and
             after_alternative.piece_at(target) ==
             chess.Piece(chess.KNIGHT, enemy) and
             target in after_alternative.attacks(alternative.to_square) and
             after_alternative.piece_at(queen_square) ==
             chess.Piece(chess.QUEEN, board.turn) and
             attacker in after_alternative.attackers(enemy, queen_square),
             'alternative_does_not_attack_target')
    alternative_san = board.san(alternative)
    witness = {**selected_witness,
               'alternative_uci': alternative.uci(),
               'alternative_san': alternative_san,
               'alternative_target_square': claim['alternative_target_square'],
               'conditional_reply_uci': None,
               'conditional_reply_san': None}
    text = (f'{selected_witness["selected_san"]} moves the queen off '
            f'{chess.square_name(queen_square)}, which the opposing knight on '
            f'{claim["attacker_square"]} attacks, and counterattacks that knight. '
            f'{alternative_san} is another legal choice: the moved piece attacks '
            f'that knight, but leaves the queen on '
            f'{chess.square_name(queen_square)} under attack.')
    reply_uci = claim['conditional_reply_uci']
    if reply_uci is not None:
        reply = v8._move(after_alternative, reply_uci,
                         'illegal_model_reply')
        _require(reply.from_square == attacker and
                 reply.to_square == queen_square and
                 after_alternative.is_capture(reply) and
                 after_alternative.piece_at(reply.from_square) ==
                 chess.Piece(chess.KNIGHT, enemy) and
                 after_alternative.piece_at(reply.to_square) ==
                 chess.Piece(chess.QUEEN, board.turn),
                 'unverified_queen_capture_reply')
        reply_san = after_alternative.san(reply)
        witness['conditional_reply_uci'] = reply.uci()
        witness['conditional_reply_san'] = reply_san
        text += (f' If the opponent replies {reply_san}, the knight captures '
                 'that queen. This is one legal reply; other replies are '
                 'unchecked.')
    else:
        text += ' No opponent reply has been checked.'
    text += (' These are board facts; neither move is ranked. When comparing '
             'choices, check what each move leaves attacked.')
    return witness, text


CHECKERS = {**v8.CHECKERS, 'queen_escape': _queen_alternative}
CUES = {
    'checking_capture': (
        'When a checking capture also attacks a queen, count legal replies '
        'before treating an exchange as forced.'),
    'rook_coordination': (
        'When comparing rook moves, inspect pawn-free files and what each '
        'rook supports or attacks.'),
    'passed_pawn': (
        'When a rook attacks a passed pawn, replay a reply and recapture '
        'before treating the pawn as won.'),
}


def comparison_admissibility(played_score: dict | None,
                             alternative_score: dict | None) -> dict:
    """Evaluator-side guard; never computes or displays an ordering.

    A provenance-verified, predeclared paired evaluator is a separate future
    step. Even two exact values here remain deferred without that receipt.
    """
    if played_score is None or alternative_score is None:
        return {'status': 'abstain', 'reason': 'missing_paired_score',
                'delta_cp': None}
    expected = {'type', 'value', 'bound', 'order', 'perspective',
                'side_to_move'}
    for score in (played_score, alternative_score):
        if (type(score) is not dict or set(score) != expected or
                score['type'] not in ('cp', 'mate') or
                type(score['value']) is not int or
                score['bound'] not in ('exact', 'lower', 'upper') or
                score['order'] != 'engine_score' or
                score['perspective'] != 'side_to_move' or
                score['side_to_move'] not in ('white', 'black')):
            raise ValueError('invalid_evaluator_score')
    if played_score['side_to_move'] != alternative_score['side_to_move']:
        raise ValueError('comparison_perspective_mismatch')
    if (played_score['type'] != 'cp' or alternative_score['type'] != 'cp' or
            played_score['bound'] != 'exact' or
            alternative_score['bound'] != 'exact'):
        return {'status': 'abstain', 'reason': 'mate_or_bounded_score',
                'delta_cp': None}
    return {'status': 'deferred',
            'reason': 'verified_paired_evaluator_receipt_required',
            'delta_cp': None}


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Check one raw claim without model or engine calls or score ordering."""
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    case_kind = v8._case(packet, board, selected)
    base = {
        'schema': RESULT_SCHEMA,
        'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(
            _projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'v8_source_dependency_sha256': cf.file_digest(Path(v8.__file__)),
        'v5_source_dependency_sha256': cf.file_digest(Path(proposal_v5.__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'case_kind': case_kind, 'model_calls': 0, 'engine_calls': 0,
        'quality_evaluated': False,
    }
    witness = teaching_text = model_kind = None
    try:
        claim, parsed_raw = v8._parse_claim(raw_response)
        _require(claim.get('schema') == CLAIM_SCHEMA, 'invalid_claim_schema')
        model_kind = claim.get('kind')
        _require(type(model_kind) is str and model_kind in KINDS,
                 'unsupported_claim_kind')
        if model_kind == 'abstention':
            tactical._exact(claim, ('schema', 'kind'), 'invalid_abstention_shape')
            decision, reason = 'model_abstention', 'model_abstained'
        else:
            tactical._exact(claim, CLAIM_FIELDS[model_kind],
                            'invalid_claim_shape')
            _require(model_kind == case_kind, 'claim_kind_case_mismatch')
            _require(claim['selected_uci'] == selected.uci(),
                     'selected_move_mismatch')
            _require(claim['scope'] == SCOPE, 'unsupported_scope')
            witness, teaching_text = CHECKERS[model_kind](board, selected,
                                                            claim)
            if model_kind in CUES:
                teaching_text += ' ' + CUES[model_kind]
            decision, reason = 'verified_typed_board_claim', None
        response_sha256 = cf.digest(parsed_raw)
    except tactical.ClaimRejected as error:
        decision, reason = 'rejected', str(error)
        response_sha256 = tactical._response_digest(raw_response)
    comparison_reason = (
        'claim_rejected' if decision == 'rejected' else
        'no_model_named_alternative' if model_kind in
        ('checking_capture', 'passed_pawn', 'abstention') else
        'separate_verified_paired_evaluator_not_run')
    return {**base, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason,
            'model_kind': model_kind, 'witness': witness,
            'teaching_text': teaching_text,
            'comparison': {'status': 'abstain', 'reason': comparison_reason,
                           'delta_cp': None}}
