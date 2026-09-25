"""Select one legal, actually played annotated position from the Blue Book corpus."""
import argparse, hashlib, json
from pathlib import Path
import chess.pgn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pgn", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--minimum-game-index", type=int, default=1)
    args = parser.parse_args()
    if args.minimum_game_index < 1: raise SystemExit("minimum_game_index_must_be_positive")
    stream = Path(args.pgn).open(encoding="utf-8")
    index = 0
    while game := chess.pgn.read_game(stream):
        index += 1
        if index < args.minimum_game_index: continue
        board = game.board()
        for ply, node in enumerate(game.mainline(), 1):
            if node.move not in board.legal_moves: break
            if node.comment.strip():
                game_text = str(game)
                source_ref = "gutenberg-blue-book-16377/game-%d/ply-%d" % (index, ply)
                fixture = {"schema_version":"position-evidence/v1", "position_id":source_ref, "game_id":"blue-book-16377-%d" % index, "split":"dev", "fen":board.fen(), "move_uci":node.move.uci(), "legal_replay_hash":hashlib.sha256(game_text.encode("utf-8")).hexdigest(), "legal_board_verified":board.is_valid(), "source":{"source_id":"gutenberg-blue-book-16377","game_ref":source_ref,"license":"public-domain-USA","rights_status":"verified"}, "engine_evidence":[], "commentary_evidence":[{"id":"blue-book-comment-1","source_ref":source_ref,"text":node.comment.strip()}], "limitations":["This is a real historically played position with public-domain book commentary.","Engine evidence is added separately and explanation quality remains unevaluated."]}
                Path(args.output).write_text(json.dumps(fixture, indent=2, sort_keys=True)+"\n", encoding="utf-8")
                print(json.dumps({"real_commentary_fixture_ok":True,"game":index,"ply":ply,"move_uci":node.move.uci(),"comment":node.comment.strip()}, sort_keys=True)); return
            board.push(node.move)
    raise SystemExit("no_legal_commented_position")

if __name__ == "__main__": main()
