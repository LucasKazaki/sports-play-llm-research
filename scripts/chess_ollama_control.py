"""Small local general-model control; no training or engine-answer inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from chess_stockfish_distill import legal_action, save, digest


def build_prompt(row, representation):
    import chess
    board = chess.Board(row["fen"])
    packet = {"fen": row["fen"], "side_to_move": "white" if board.turn else "black"}
    if representation == "board_and_legal_moves":
        packet["pieces"] = {chess.square_name(sq): piece.symbol() for sq, piece in board.piece_map().items()}
        packet["legal_moves"] = sorted(move.uci() for move in board.legal_moves)
    elif representation != "fen_only":
        raise ValueError("unknown representation")
    return ("Choose the best chess move for the side to move in this current position. "
            "Return only JSON with a move_uci string in UCI notation, for example {\"move_uci\":\"e2e4\"}. "
            "Do not provide an explanation. Capital piece letters are White, lowercase Black.\n" +
            json.dumps(packet, sort_keys=True))


def run(labels_path, model, out, count=4):
    if not 1 <= count <= 64:
        raise ValueError("bounded development count required")
    labels = json.loads(Path(labels_path).read_text())
    rows = labels["splits"]["development"][:count]
    base = "http://127.0.0.1:11434"
    def post(route, payload, timeout=180):
        request = Request(base+route, json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    identity = post("/api/show", {"model": model}, 30)
    tags = json.load(urlopen(base+"/api/tags", timeout=30))
    matched = next((item for item in tags["models"] if item["name"] == model), None)
    if not matched:
        raise ValueError("requested installed model absent")
    receipt = {"schema": "chess.local-ollama-control.v1", "model": matched,
               "model_details": identity.get("details"), "labels_sha256": digest(labels_path),
               "declared_before_generation": {"count_per_condition": count, "conditions": ["fen_only", "board_and_legal_moves"],
                  "options": {"temperature": 0, "seed": 4082026, "num_predict": 96, "num_ctx": 4096},
                  "think": False, "source": "first four development positions; no holdout", "weights_updated": False},
               "conditions": {}}
    save(out, receipt)
    try:
        for condition in receipt["declared_before_generation"]["conditions"]:
            results = []
            receipt["conditions"][condition] = {"count": count, "records": results}
            for row in rows:
                prompt = build_prompt(row, condition)
                started = time.perf_counter()
                record = {"id": row["id"], "fen": row["fen"], "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                          "prompt": prompt, "teacher_move_uci": row["teacher_move_uci"], "legal": False, "match": False}
                try:
                    raw = post("/api/generate", {"model": model, "prompt": prompt, "stream": False, "think": False,
                               "format": {"type": "object", "properties": {"move_uci": {"type": "string"}},
                                          "required": ["move_uci"], "additionalProperties": False},
                               "options": receipt["declared_before_generation"]["options"], "keep_alive": "5m"})
                    output = json.loads(raw["response"])
                    move = output.get("move_uci")
                    record.update({"raw_output": raw["response"], "move_uci": move,
                                   "legal": legal_action(row["fen"], move), "backend": {k: raw.get(k) for k in (
                                       "done", "done_reason", "eval_count", "load_duration", "total_duration")}})
                    record["match"] = record["legal"] and move == row["teacher_move_uci"]
                except (OSError, ValueError, KeyError, TypeError) as error:
                    record["error"] = f"{type(error).__name__}: {error}"
                record["elapsed_seconds"] = round(time.perf_counter()-started, 3)
                results.append(record)
                receipt["conditions"][condition].update({"raw_legal_count": sum(r["legal"] for r in results),
                                                         "top1_match_count": sum(r["match"] for r in results),
                                                         "completed": len(results)})
                save(out, receipt)
                print(json.dumps({"condition": condition, "done": len(results), "legal": record["legal"], "match": record["match"]}), flush=True)
    finally:
        post("/api/generate", {"model": model, "keep_alive": 0}, 30)
    receipt["limitations"] = ["Four-position development smoke test; no strength or population estimate.",
                                "Legal-move-list input is tool assisted; report separately from FEN-only control.",
                                "No weight updates; installed model display alias is preserved alongside backend family and digest."]
    save(out, receipt)
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--count", type=int, default=4)
    args = p.parse_args()
    run(args.labels, args.model, args.out, args.count)
