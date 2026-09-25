"""Check explicit moving-piece claims against a legal board transition."""
import argparse, json, re
from pathlib import Path
import chess

PIECE_NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
MOTION = re.compile(r"\b(?:advancing|moving)\s+(?:a|an|the)\s+(pawn|knight|bishop|rook|queen|king)\b", re.I)

def explanation_texts(explanation):
    values = [("move_summary", explanation.get("move_summary", ""))]
    for index, item in enumerate(explanation.get("primary_concepts", [])):
        if isinstance(item, dict): values.append((f"primary_concepts[{index}].claim", item.get("claim", "")))
    return [(field, value) for field, value in values if isinstance(value, str) and value.strip()]

def check_moving_piece(packet, explanation):
    board = chess.Board(packet["fen"])
    move = chess.Move.from_uci(packet["move_uci"])
    if move not in board.legal_moves: raise ValueError("packet_move_not_legal")
    piece = board.piece_at(move.from_square)
    if piece is None: raise ValueError("packet_move_has_no_piece")
    moving_piece = PIECE_NAMES[piece.piece_type]
    findings = []
    for field, text in explanation_texts(explanation):
        for match in MOTION.finditer(text):
            claimed = match.group(1).lower()
            if claimed != moving_piece:
                findings.append({"kind": "moving_piece_mismatch", "field": field, "claimed_piece": claimed, "actual_piece": moving_piece, "text": text})
    return {"schema_version": "chess-explanation-factuality/v1", "position_id": packet.get("position_id"), "move_uci": move.uci(), "moving_piece": moving_piece, "source": packet.get("source"), "checked_fields": [field for field, _ in explanation_texts(explanation)], "findings": findings, "passed": not findings, "limitations": ["Only explicit moving-piece motion phrases are checked.", "Strategic, tactical, and teaching claims remain unscored."]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--explanation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    explanation = json.loads(Path(args.explanation).read_text(encoding="utf-8"))
    report = check_moving_piece(packet, explanation)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"factuality_check_complete": True, "passed": report["passed"], "findings": len(report["findings"])}, sort_keys=True))

if __name__ == "__main__": main()
