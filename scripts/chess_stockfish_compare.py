"""Write a bounded Stockfish comparison receipt for one chess fixture."""
import argparse, hashlib, json, subprocess
from pathlib import Path
import chess, chess.engine

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--multipv", type=int, default=2)
    args = parser.parse_args()
    engine_path, packet_path, output_path = Path(args.engine), Path(args.packet), Path(args.output)
    if not engine_path.is_file(): raise SystemExit("engine_missing")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    board = chess.Board(packet["fen"])
    proposed = chess.Move.from_uci(packet["move_uci"])
    if proposed not in board.legal_moves: raise SystemExit("fixture_move_illegal")
    handshake = subprocess.run([str(engine_path)], input="uci\nisready\nquit\n", text=True, capture_output=True, timeout=30, check=True)
    if "uciok" not in handshake.stdout or "readyok" not in handshake.stdout: raise SystemExit("uci_handshake_failed")
    engine = chess.engine.SimpleEngine.popen_uci(str(engine_path))
    try: infos = engine.analyse(board, chess.engine.Limit(depth=args.depth), multipv=args.multipv)
    finally: engine.quit()
    candidates = []
    for rank, info in enumerate(infos, 1):
        pv = info.get("pv") or []
        if not pv: raise SystemExit("missing_principal_variation")
        score = info["score"].pov(board.turn).score(mate_score=100000)
        candidates.append({"id":"stockfish-19-multipv-%d" % rank, "rank":rank, "move_uci":pv[0].uci(), "score_cp":score, "pv_uci":[move.uci() for move in pv]})
    rank = next((item["rank"] for item in candidates if item["move_uci"] == proposed.uci()), None)
    receipt = {"schema_version":"stockfish-comparison-receipt/v1", "engine":{"origin":"https://stockfishchess.org/download/", "archive_sha256":"3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7", "binary_sha256":sha256(engine_path), "uci_handshake":"uciok+readyok", "depth":args.depth}, "input":{"packet":str(packet_path).replace("\\","/"), "position_id":packet["position_id"], "fen":packet["fen"], "proposed_move_uci":proposed.uci(), "source_id":packet["source"]["source_id"]}, "engine_evidence":candidates, "comparison":{"matches_top_candidate":proposed.uci()==candidates[0]["move_uci"], "proposed_move_rank":rank}, "boundaries":["The input packet is a synthetic contract fixture.", "Synthetic candidate references remain distinct from these engine receipts.", "One bounded comparison is not model calibration, training, or chess-quality evaluation.", "No creator commentary or video was used."]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"engine_comparison_ok":True, "top_move":candidates[0]["move_uci"], "proposed_move":proposed.uci(), "match":receipt["comparison"]["matches_top_candidate"], "output":str(output_path)}, sort_keys=True))

if __name__ == "__main__": main()
