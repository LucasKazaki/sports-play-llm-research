"""Offline typed-commentary checks for four known Chess.com development plies.

The model sees only the nine verified pre-move projection fields. It chooses a
mechanism and every square, alternative, and conditional move that its claim
needs. The checker replays those choices after generation and renders only
bounded sentences. It neither picks a convenient line nor measures teaching
quality or engine intent.
"""
from __future__ import annotations

import json
from pathlib import Path

import chess

import chess_counterfactual_evidence as cf
import chess_no_forward_teaching_v5 as proposal_v5
import chess_no_forward_teaching_v7 as teaching_v7
import chess_tactical_hypothesis_v2 as tactical


INPUT_SCHEMA = 'chess-no-forward-teaching-input/v8'
CLAIM_SCHEMA = 'chess-no-forward-teaching-output/v8'
RESULT_SCHEMA = 'chess-no-forward-teaching-evaluation/v8'
SCOPE = 'board_geometry_or_named_line_only'
KINDS = ('queen_escape', 'checking_capture', 'rook_coordination',
         'passed_pawn', 'abstention')
PGN_SHA256 = '684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075'
CASES = {
    33: ('queen_escape', '2kr3r/pppq3p/3bpp2/6p1/1P1P4/P1n1PBBP/5PP1/R2Q1RK1 w - - 1 17', 'd1c2'),
    46: ('checking_capture', '2kr3r/pp5p/2p1pp2/3q2p1/PP1P4/2Q3PP/6P1/R1R3K1 b - - 0 23', 'd5d4'),
    57: ('rook_coordination', '7r/2k4p/p1p1pp2/P5p1/3r4/2R3PP/6PK/R7 w - - 0 29', 'a1c1'),
    93: ('passed_pawn', '7R/8/2p5/2k2p1P/r7/7K/1p4P1/8 w - - 4 47', 'h8b8'),
}
CLAIM_FIELDS = {
    'queen_escape': ('schema', 'kind', 'selected_uci', 'attacker_square',
                     'target_square', 'scope'),
    'checking_capture': ('schema', 'kind', 'selected_uci',
                         'attacked_queen_square', 'reply_uci',
                         'recapture_uci', 'scope'),
    'rook_coordination': ('schema', 'kind', 'selected_uci',
                          'supported_rook_square', 'target_pawn_square',
                          'alternative_uci', 'open_file', 'scope'),
    'passed_pawn': ('schema', 'kind', 'selected_uci', 'pawn_square',
                    'conditional_line', 'scope'),
}
PROMPT = """Use only the source-bound pre-move board, selected legal move,
transition facts, and qualified engine observation in the user JSON. The score
is an observation, not a rationale. You have no engine continuation, opponent
reply list, alternative score, future board, or Game Review label. Choose one
typed mechanism only if you can name its exact squares and legal moves; the
offline checker will replay your choices. Any conditional line is one possible
line, not forced play. Do not call a move good, best, bad, worse, a win, or
Stockfish's reason. If unsure, abstain. Return only one exact JSON object:
{"schema":"chess-no-forward-teaching-output/v8","kind":"abstention"}
or a typed claim with schema, kind, selected_uci, and scope set to
"board_geometry_or_named_line_only", plus exactly these fields:
- queen_escape: attacker_square, target_square;
- checking_capture: attacked_queen_square, reply_uci, recapture_uci;
- rook_coordination: supported_rook_square, target_pawn_square,
  alternative_uci, open_file;
- passed_pawn: pawn_square, conditional_line, where conditional_line is null
  or exactly {"reply_uci":"...","capture_uci":"...","recapture_uci":"..."}.
All moves are UCI. Do not add a lesson draft, evaluation, ranking, or prose."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise tactical.ClaimRejected(reason)


def _projection(packet: dict, packet_sha256: str) -> dict:
    projected = teaching_v7._projection(packet, packet_sha256)
    projected['schema'] = INPUT_SCHEMA
    projected['assertion_kinds'] = list(KINDS)
    return projected


def build_generator_input(packet_bytes: bytes, packet_sha256: str, *,
                          source_binding: dict) -> bytes:
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    _case(packet, board, selected)
    return cf.canonical(_projection(packet, packet_sha256))


def generator_messages(packet_bytes: bytes, packet_sha256: str, *,
                       source_binding: dict) -> list[dict]:
    safe = build_generator_input(packet_bytes, packet_sha256,
                                 source_binding=source_binding)
    return [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': safe.decode('utf-8')}]


def _case(packet: dict, board: chess.Board, selected: chess.Move) -> str:
    source = packet['source']
    _require(source.get('pgn_sha256') == PGN_SHA256 and
             source.get('move_role') == 'played' and
             type(source.get('selected_ply')) is int and
             source['selected_ply'] in CASES, 'unsupported_development_case')
    kind, fen, uci = CASES[source['selected_ply']]
    _require(board.fen() == fen and selected.uci() == uci,
             'development_case_position_mismatch')
    return kind


def _parse_claim(raw: bytes) -> tuple[dict, bytes]:
    _require(type(raw) is bytes and 0 < len(raw) <= tactical.MAX_RESPONSE_BYTES,
             'invalid_response_length')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, 'duplicate_json_key')
            value[key] = item
        return value

    def invalid_number(_value):
        # No v8 claim field accepts any number. This also rejects 1e999 before
        # Python can turn it into infinity inside an otherwise valid object.
        raise tactical.ClaimRejected('invalid_json_number')

    def invalid_constant(_value):
        raise tactical.ClaimRejected('invalid_json_constant')

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                           parse_int=invalid_number, parse_float=invalid_number,
                           parse_constant=invalid_constant)
    except tactical.ClaimRejected:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        raise tactical.ClaimRejected('invalid_response_json') from error
    _require(type(value) is dict, 'invalid_claim_shape')
    return value, raw


def _square(value: object, reason: str) -> int:
    _require(type(value) is str, reason)
    try:
        return chess.parse_square(value)
    except ValueError as error:
        raise tactical.ClaimRejected(reason) from error


def _move(board: chess.Board, uci: object, reason: str) -> chess.Move:
    return tactical._legal_move(board, uci, reason)


def _after(board: chess.Board, move: chess.Move) -> chess.Board:
    result = board.copy(stack=False)
    result.push(move)
    return result


def _queen_escape(board: chess.Board, selected: chess.Move,
                  claim: dict) -> tuple[dict, str]:
    origin, target = selected.from_square, selected.to_square
    attacker = _square(claim['attacker_square'], 'invalid_attacker_square')
    target_square = _square(claim['target_square'], 'invalid_target_square')
    enemy = not board.turn
    _require(board.piece_at(origin) == chess.Piece(chess.QUEEN, board.turn) and
             board.piece_at(attacker) == chess.Piece(chess.KNIGHT, enemy) and
             board.attackers(enemy, origin) == {attacker} and
             target != origin, 'unverified_queen_threat')
    after = _after(board, selected)
    _require(target_square == attacker and
             target_square in after.attacks(target) and
             after.piece_at(target_square) == chess.Piece(chess.KNIGHT, enemy),
             'unverified_queen_counterattack')
    witness = {'attacker_square': claim['attacker_square'],
               'target_square': claim['target_square'],
               'selected_san': board.san(selected)}
    text = (f'Before {witness["selected_san"]}, the opposing knight on '
            f'{claim["attacker_square"]} attacks the queen on '
            f'{chess.square_name(origin)}. {witness["selected_san"]} moves '
            f'the queen off that square and attacks the knight. This does '
            'not establish move quality or a forced win of the knight.')
    return witness, text


def _checking_capture(board: chess.Board, selected: chess.Move,
                      claim: dict) -> tuple[dict, str]:
    queen_square = _square(claim['attacked_queen_square'],
                           'invalid_attacked_queen_square')
    captured = board.piece_at(selected.to_square)
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.QUEEN, board.turn) and
             board.is_capture(selected) and
             captured == chess.Piece(chess.PAWN, not board.turn),
             'unverified_pawn_capture')
    after = _after(board, selected)
    _require(after.is_check() and
             after.piece_at(queen_square) ==
             chess.Piece(chess.QUEEN, not board.turn) and
             queen_square in after.attacks(selected.to_square),
             'unverified_check_or_queen_attack')
    _require(len(list(after.legal_moves)) > 1, 'unverified_reply_choice')
    reply = _move(after, claim['reply_uci'], 'illegal_model_reply')
    _require(reply.from_square == queen_square and
             reply.to_square == selected.to_square and
             after.is_capture(reply), 'unverified_queen_trade_reply')
    reply_san = after.san(reply)
    after_reply = _after(after, reply)
    recapture = _move(after_reply, claim['recapture_uci'],
                      'illegal_model_recapture')
    _require(after_reply.is_capture(recapture) and
             recapture.to_square == selected.to_square and
             after_reply.piece_at(recapture.from_square) ==
             chess.Piece(chess.ROOK, board.turn) and
             after_reply.piece_at(recapture.to_square) ==
             chess.Piece(chess.QUEEN, not board.turn),
             'unverified_queen_trade_recapture')
    recapture_san = after_reply.san(recapture)
    witness = {'attacked_queen_square': claim['attacked_queen_square'],
               'reply_uci': reply.uci(), 'reply_san': reply_san,
               'recapture_uci': recapture.uci(),
               'recapture_san': recapture_san,
               'legal_reply_count': len(list(after.legal_moves))}
    text = (f'{board.san(selected)} captures a pawn and checks the opposing '
            f'king. The queen on {chess.square_name(selected.to_square)} also '
            f'attacks the opposing queen on {claim["attacked_queen_square"]}. '
            f'If the opponent replies {reply_san}, {recapture_san} is a legal '
            'recapture. This is one conditional queen trade; other legal '
            'replies and move quality remain unchecked.')
    return witness, text


def _rook_coordination(board: chess.Board, selected: chess.Move,
                       claim: dict) -> tuple[dict, str]:
    support = _square(claim['supported_rook_square'],
                      'invalid_supported_rook_square')
    pawn = _square(claim['target_pawn_square'],
                   'invalid_target_pawn_square')
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.ROOK, board.turn) and
             not board.is_capture(selected), 'unverified_quiet_rook_move')
    after = _after(board, selected)
    _require(after.piece_at(support) == chess.Piece(chess.ROOK, board.turn) and
             support in after.attacks(selected.to_square) and
             after.piece_at(pawn) == chess.Piece(chess.PAWN, not board.turn) and
             pawn in after.attacks(support) and
             chess.square_file(selected.to_square) == chess.square_file(support),
             'unverified_rook_support')
    _require((chess.square_rank(selected.to_square) < chess.square_rank(support))
             if board.turn == chess.WHITE else
             (chess.square_rank(selected.to_square) > chess.square_rank(support)),
             'unverified_rook_behind')
    alternative = _move(board, claim['alternative_uci'],
                        'illegal_model_alternative')
    _require(alternative != selected and
             board.piece_at(alternative.from_square) ==
             chess.Piece(chess.ROOK, board.turn),
             'unverified_rook_alternative')
    file_name = claim['open_file']
    _require(type(file_name) is str and len(file_name) == 1 and
             file_name in 'abcdefgh' and
             chess.FILE_NAMES[chess.square_file(alternative.to_square)] == file_name,
             'open_file_mismatch')
    file_number = chess.square_file(alternative.to_square)
    _require(all(chess.square_file(square) != file_number
                 for color in chess.COLORS
                 for square in board.pieces(chess.PAWN, color)),
             'alternative_file_not_open')
    alternative_san = board.san(alternative)
    witness = {'supported_rook_square': claim['supported_rook_square'],
               'target_pawn_square': claim['target_pawn_square'],
               'alternative_uci': alternative.uci(),
               'alternative_san': alternative_san,
               'open_file': file_name}
    text = (f'{board.san(selected)} places a rook behind the rook on '
            f'{claim["supported_rook_square"]}, which attacks the opposing '
            f'pawn on {claim["target_pawn_square"]}. {alternative_san} is a '
            f'legal rook move to the open {file_name}-file. These are '
            'geometric options; neither move is ranked, and a pawn win is '
            'unchecked.')
    return witness, text


def _passed_pawn(board: chess.Board, selected: chess.Move,
                 claim: dict) -> tuple[dict, str]:
    pawn = _square(claim['pawn_square'], 'invalid_pawn_square')
    _require(board.piece_at(selected.from_square) ==
             chess.Piece(chess.ROOK, board.turn) and
             board.piece_at(pawn) == chess.Piece(chess.PAWN, not board.turn),
             'unverified_rook_pawn')
    pawn_color = not board.turn
    pawn_file, pawn_rank = chess.square_file(pawn), chess.square_rank(pawn)
    enemy_pawns_ahead = (
        square for square in board.pieces(chess.PAWN, board.turn)
        if abs(chess.square_file(square) - pawn_file) <= 1 and
        ((chess.square_rank(square) > pawn_rank) if pawn_color == chess.WHITE
         else (chess.square_rank(square) < pawn_rank)))
    _require(next(enemy_pawns_ahead, None) is None, 'pawn_not_passed')
    after = _after(board, selected)
    _require(chess.square_file(selected.to_square) == pawn_file and
             pawn in after.attacks(selected.to_square) and
             ((chess.square_rank(selected.to_square) < pawn_rank)
              if pawn_color == chess.WHITE else
              (chess.square_rank(selected.to_square) > pawn_rank)),
             'unverified_pawn_attack_from_behind')
    line = claim['conditional_line']
    witness = {'pawn_square': claim['pawn_square'], 'conditional_line': None}
    text = (f'{board.san(selected)} places a rook behind the opposing passed '
            f'pawn on {claim["pawn_square"]} and attacks it along the file.')
    if line is None:
        return witness, text + (' This is a geometric attack; whether the '
                                'pawn can be captured safely and move quality '
                                'are unchecked.')
    tactical._exact(line, ('reply_uci', 'capture_uci', 'recapture_uci'),
                    'invalid_conditional_line_shape')
    reply = _move(after, line['reply_uci'], 'illegal_model_reply')
    reply_san = after.san(reply)
    after_reply = _after(after, reply)
    capture = _move(after_reply, line['capture_uci'],
                    'illegal_model_pawn_capture')
    _require(capture.from_square == selected.to_square and
             capture.to_square == pawn and
             after_reply.is_capture(capture) and
             after_reply.piece_at(pawn) ==
             chess.Piece(chess.PAWN, not board.turn),
             'unverified_pawn_capture')
    capture_san = after_reply.san(capture)
    after_capture = _after(after_reply, capture)
    recapture = _move(after_capture, line['recapture_uci'],
                      'illegal_model_rook_recapture')
    _require(after_capture.is_capture(recapture) and
             recapture.to_square == pawn and
             after_capture.piece_at(pawn) ==
             chess.Piece(chess.ROOK, board.turn),
             'unverified_rook_recapture')
    recapture_san = after_capture.san(recapture)
    witness['conditional_line'] = {
        'reply_uci': reply.uci(), 'reply_san': reply_san,
        'capture_uci': capture.uci(), 'capture_san': capture_san,
        'recapture_uci': recapture.uci(), 'recapture_san': recapture_san}
    text += (f' If the opponent replies {reply_san}, {capture_san} can be '
             f'answered by {recapture_san}, recapturing the rook. This one '
             'line shows why the pawn attack alone does not prove a safe '
             'capture; other replies and move quality are unchecked.')
    return witness, text


CHECKERS = {'queen_escape': _queen_escape,
            'checking_capture': _checking_capture,
            'rook_coordination': _rook_coordination,
            'passed_pawn': _passed_pawn}


def evaluate(packet_bytes: bytes, packet_sha256: str, raw_response: bytes, *,
             source_binding: dict) -> dict:
    """Verify one raw model claim against one of four source-bound positions."""
    packet, board, selected = proposal_v5._verified(
        packet_bytes, packet_sha256, source_binding)
    case_kind = _case(packet, board, selected)
    base = {
        'schema': RESULT_SCHEMA,
        'packet_sha256': packet_sha256,
        'source_binding_sha256': cf.digest(cf.canonical(source_binding)),
        'generator_input_sha256': cf.digest(cf.canonical(_projection(packet, packet_sha256))),
        'evaluator_sha256': cf.file_digest(Path(__file__)),
        'v5_source_dependency_sha256': cf.file_digest(Path(proposal_v5.__file__)),
        'v7_projection_dependency_sha256': cf.file_digest(Path(teaching_v7.__file__)),
        'tactical_dependency_sha256': cf.file_digest(Path(tactical.__file__)),
        'case_kind': case_kind, 'model_calls': 0, 'engine_calls': 0,
        'quality_evaluated': False,
    }
    witness = teaching_text = model_kind = None
    try:
        claim, parsed_raw = _parse_claim(raw_response)
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
            witness, teaching_text = CHECKERS[model_kind](board, selected, claim)
            decision, reason = 'verified_typed_board_claim', None
        response_sha256 = cf.digest(parsed_raw)
    except tactical.ClaimRejected as error:
        decision, reason = 'rejected', str(error)
        response_sha256 = tactical._response_digest(raw_response)
    return {**base, 'response_sha256': response_sha256,
            'decision': decision, 'reason': reason,
            'model_kind': model_kind, 'witness': witness,
            'teaching_text': teaching_text}
