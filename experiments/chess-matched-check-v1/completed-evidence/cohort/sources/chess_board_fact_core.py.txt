"""FEN-only input boundary and strict eight-field immediate-move diagnostic."""
import json
import chess

FIELDS = ("moving_piece", "moving_colour", "is_capture", "captured_piece", "gives_check",
          "is_castling", "is_en_passant", "promotion_piece")
PIECES = ("pawn", "knight", "bishop", "rook", "queen", "king")
BOOL_FIELDS = ("is_capture", "gives_check", "is_castling", "is_en_passant")
CONDITIONS = ("fen_uci", "fen_uci_piece_map")
SCHEMA = {"type": "object", "additionalProperties": False, "required": list(FIELDS), "properties": {
    "moving_piece": {"enum": [*PIECES, "unknown"]},
    "moving_colour": {"enum": ["white", "black", "unknown"]},
    "captured_piece": {"enum": [*PIECES, None, "unknown"]},
    "promotion_piece": {"enum": ["queen", "rook", "bishop", "knight", None, "unknown"]},
    **{name: {"anyOf": [{"type": "boolean"}, {"const": "unknown"}]} for name in BOOL_FIELDS}}}
INSTRUCTION = (
    "For the selected legal chess move, infer only its immediate board facts from the given pre-move position. "
    "Return one JSON object with exactly the eight schema fields. No explanation or strategic evaluation. "
    "moving_piece and moving_colour describe the piece before it moves; is_capture includes en passant; "
    "captured_piece is null when there is no capture; gives_check concerns the opponent immediately after the move; "
    "promotion_piece is the promoted piece name or null if there is no promotion. "
    "Use the string unknown for any field you cannot determine. Boolean fields must be true, false or unknown. "
    "Capital board symbols are White, lowercase Black; a null map entry is an empty square.\n"
    "Response schema: " + json.dumps(SCHEMA, sort_keys=True, separators=(",", ":")) + "\nInput: ")


def board_and_move(fen, uci):
    board, move = chess.Board(fen), chess.Move.from_uci(uci)
    if not board.is_valid() or board.chess960 or move not in board.legal_moves:
        raise ValueError("valid orthodox pre-move board and legal selected move required")
    return board, move


def build_prompt(row, condition):
    # Select exactly these fields; no label/source/annotation/transition access.
    fen, uci = row["fen"], row["selected_uci"]
    board, _ = board_and_move(fen, uci)
    packet = {"fen": fen, "selected_uci": uci}
    if condition == "fen_uci_piece_map":
        packet["pieces"] = {chess.square_name(sq): board.piece_at(sq).symbol() if board.piece_at(sq) else None
                            for sq in chess.SQUARES}
    elif condition != "fen_uci":
        raise ValueError("unknown representation")
    return INSTRUCTION + json.dumps(packet, sort_keys=True, separators=(",", ":"))


def expected_facts(fen, uci):
    board, move = board_and_move(fen, uci)
    moving = board.piece_at(move.from_square)
    ep = board.is_en_passant(move)
    victim = board.piece_at(move.to_square) if not ep else chess.Piece(chess.PAWN, not moving.color)
    return {"moving_piece": chess.piece_name(moving.piece_type),
            "moving_colour": "white" if moving.color else "black", "is_capture": board.is_capture(move),
            "captured_piece": chess.piece_name(victim.piece_type) if victim else None,
            "gives_check": board.gives_check(move), "is_castling": board.is_castling(move),
            "is_en_passant": ep, "promotion_piece": chess.piece_name(move.promotion) if move.promotion else None}


def independent_facts(fen, uci):
    """Separate push/material/geometry/attack route; no move-predicate helpers."""
    board, move = board_and_move(fen, uci)
    moving = board.piece_at(move.from_square)
    before_enemy = {sq: p for sq, p in board.piece_map().items() if p.color != moving.color}
    after = board.copy(stack=False)
    after.push(move)
    enemy_after = {sq for sq, p in after.piece_map().items() if p.color != moving.color}
    removed = set(before_enemy) - enemy_after
    if len(removed) > 1:
        raise ValueError("unexpected orthodox capture transition")
    victim = before_enemy[next(iter(removed))] if removed else None
    return {"moving_piece": chess.piece_name(moving.piece_type),
            "moving_colour": "white" if moving.color else "black", "is_capture": bool(removed),
            "captured_piece": chess.piece_name(victim.piece_type) if victim else None,
            "gives_check": after.is_attacked_by(moving.color, after.king(not moving.color)),
            "is_castling": moving.piece_type == chess.KING and abs(chess.square_file(move.to_square) - chess.square_file(move.from_square)) == 2,
            "is_en_passant": moving.piece_type == chess.PAWN and chess.square_file(move.from_square) != chess.square_file(move.to_square) and board.piece_at(move.to_square) is None,
            "promotion_piece": chess.piece_name(after.piece_at(move.to_square).piece_type) if len(uci) == 5 else None}


def parse_facts(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("nonfinite JSON constant")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if type(value) is not dict or set(value) != set(FIELDS):
        raise ValueError("exact eight-field JSON object required")
    for field, item in value.items():
        if field in BOOL_FIELDS:
            if type(item) is not bool and not (type(item) is str and item == "unknown"):
                raise ValueError("Boolean or unknown required: " + field)
        else:
            allowed = SCHEMA["properties"][field]["enum"]
            if item is not None and type(item) is not str:
                raise ValueError("categorical type required: " + field)
            if item not in allowed:
                raise ValueError("unknown categorical value: " + field)
    return value
