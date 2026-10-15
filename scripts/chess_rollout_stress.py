"""Finite rollout software stress panel; no strength or real-data gate claim."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import time

import chess
import chess.engine
import chess.pgn

from chess_classifier_adapter import encode_fen, load_native_contract, rank_logits
from chess_stockfish_distill import ROOT, digest, save


def opening_board(opening):
    board = chess.Board()
    for uci in opening["uci"]:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError("illegal opening fixture:" + opening["id"])
        board.push(move)
    return board


def make_games(protocol):
    games = []
    for model in protocol["conditions"]["models"]:
        for mode in protocol["conditions"]["modes"]:
            for opening in protocol["openings"]:
                for colour in protocol["conditions"]["model_colours"]:
                    games.append({"id": ":".join((model, mode, opening["id"], colour)),
                                  "model": model, "mode": mode, "opening": opening["id"],
                                  "model_colour": colour, "board": opening_board(opening),
                                  "opening_plies": len(opening["uci"]), "additional_plies": 0,
                                  "decisions": [], "moves": [], "termination": None,
                                  "result": "*", "error": None})
    if len(games) != protocol["conditions"]["planned_games"] or len({g["id"] for g in games}) != len(games):
        raise ValueError("planned game count/identity mismatch")
    return games


def finish_if_needed(game, max_plies):
    if game["termination"] is not None:
        return True
    outcome = game["board"].outcome(claim_draw=True)
    if outcome is not None:
        game.update(termination=outcome.termination.name.lower(), result=outcome.result())
    elif game["additional_plies"] >= max_plies:
        game["termination"] = "ply_cap"
    return game["termination"] is not None


def apply_model(game, vector, contract, logit_row):
    board = game["board"]
    ranked = rank_logits(board.fen(), vector, contract["id2label"], top_k=3)
    raw = ranked["raw_choice_uci"]
    selected = ranked["legal_choice_uci"] if game["mode"] == "legal_mask" else raw
    decision = {"fen": board.fen(), "logit_row": logit_row, "raw_uci": raw,
                "raw_legal": ranked["raw_choice_is_legal"], "applied_uci": None,
                "mask_intervened": game["mode"] == "legal_mask" and raw != selected,
                "raw_top3": ranked["raw_topk"]}
    game["decisions"].append(decision)
    if selected is None:
        game["termination"] = "no_represented_legal_action"
        return
    move = chess.Move.from_uci(selected)
    if move not in board.legal_moves:
        game["termination"] = "raw_illegal"
        return
    decision["applied_uci"] = selected
    game["moves"].append({"actor": "model", "fen": board.fen(), "uci": selected})
    board.push(move)
    game["additional_plies"] += 1


def game_record(game):
    return {key: value for key, value in game.items() if key != "board"} | {"final_fen": game["board"].fen()}


def export_pgn(game):
    pgn = chess.pgn.Game.from_board(game["board"])
    pgn.headers.update(Event="Designed local rollout software stress", Site="Local",
                       White=game["model"] if game["model_colour"] == "white" else "Stockfish19-10knodes",
                       Black=game["model"] if game["model_colour"] == "black" else "Stockfish19-10knodes",
                       Result=game["result"], Termination=game["termination"] or "not_run",
                       TestId=game["id"], PolicyMode=game["mode"])
    return str(pgn)


def aggregate(games):
    groups = {}
    for model in sorted({g["model"] for g in games}):
        for mode in sorted({g["mode"] for g in games}):
            group = [g for g in games if g["model"] == model and g["mode"] == mode]
            decisions = [d for g in group for d in g["decisions"]]
            groups[model + ":" + mode] = {
                "planned_games": len(group),
                "terminations": dict(Counter(g["termination"] or "not_run" for g in group)),
                "chess_results": dict(Counter(g["result"] for g in group)),
                "model_decisions": len(decisions),
                "raw_legal_decisions": sum(d["raw_legal"] for d in decisions),
                "mask_interventions": sum(d["mask_intervened"] for d in decisions),
                "additional_plies": sum(g["additional_plies"] for g in group),
            }
    return groups


def run(protocol_path, out, base_dir, selected_dir, engine_path):
    import numpy as np
    import torch
    from transformers import LlamaForSequenceClassification

    if out.exists():
        raise ValueError("refusing to replace an existing stress run")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    games = make_games(protocol)
    models = {"base": base_dir, "selected_step_512": selected_dir}
    expected = protocol["model_binding"]
    for name, directory in models.items():
        key = "base_weight_sha256" if name == "base" else "selected_weight_sha256"
        if digest(directory / "model.safetensors") != expected[key]:
            raise ValueError("model weight identity mismatch:" + name)
    if digest(engine_path) != protocol["opponent"]["sha256"]:
        raise ValueError("opponent executable identity mismatch")
    contracts, contract_failures = {}, {}
    for name, directory in models.items():
        try:
            contracts[name] = load_native_contract(directory)
        except Exception as error:
            contract_failures[name] = type(error).__name__
    out.mkdir(parents=True)
    snapshots = {}
    for path in (Path(__file__), ROOT / "scripts/chess_classifier_adapter.py",
                 ROOT / "scripts/chess_stockfish_distill.py", protocol_path):
        destination = out / ("executed-" + path.name)
        shutil.copyfile(path, destination)
        snapshots[destination.name] = digest(destination)
    contract_sources = {name: value.get("source_sha256", {}) for name, value in contracts.items()}
    save(out / "before-calls.json", {"protocol_sha256": digest(protocol_path), "source_snapshots": snapshots,
                                    "planned_ids": [g["id"] for g in games], "model_binding": expected,
                                    "native_contract_source_sha256": contract_sources,
                                    "contract_failures": contract_failures})
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    started = time.perf_counter()
    logit_files = {}
    for name, directory in models.items():
        model_games = [g for g in games if g["model"] == name]
        try:
            if name in contract_failures:
                raise ValueError("native contract failed:" + contract_failures[name])
            contract = contracts[name]
            model = LlamaForSequenceClassification.from_pretrained(directory, local_files_only=True,
                                        attn_implementation="sdpa").float().to(device).eval()
        except Exception as error:
            for game in model_games:
                game.update(termination="model_load_error", error=type(error).__name__)
            save(out / f"{name}-games.json", [game_record(g) for g in model_games])
            continue
        vectors = []
        try:
            engine_context = chess.engine.SimpleEngine.popen_uci(str(engine_path), timeout=60)
        except Exception as error:
            for game in model_games:
                game.update(termination="opponent_start_error", error=type(error).__name__)
            save(out / f"{name}-games.json", [game_record(g) for g in model_games])
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
            continue
        with engine_context as engine:
            opponent = protocol["opponent"]
            try:
                engine.configure({"Threads": opponent["threads"], "Hash": opponent["hash_mb"]})
            except Exception as error:
                for game in model_games:
                    game.update(termination="opponent_configuration_error", error=type(error).__name__)
            while any(g["termination"] is None for g in model_games):
                pending = []
                for game in model_games:
                    if finish_if_needed(game, protocol["conditions"]["max_additional_plies"]):
                        continue
                    if game["board"].turn == (game["model_colour"] == "white"):
                        try:
                            pending.append((game, encode_fen(game["board"].fen(), contract)))
                        except Exception as error:
                            game.update(termination="adapter_error", error=type(error).__name__)
                if pending:
                    try:
                        ids = torch.tensor([item[1]["input_ids"] for item in pending], device=device)
                        with torch.inference_mode():
                            batch_logits = model(input_ids=ids, attention_mask=torch.ones_like(ids)).logits
                        if tuple(batch_logits.shape) != (len(pending), len(contract["id2label"])):
                            raise ValueError("model logits shape mismatch")
                        values = batch_logits.float().cpu().numpy()
                    except Exception as error:
                        for game, _ in pending:
                            game.update(termination="model_call_error", error=type(error).__name__)
                    else:
                        for (game, _), vector in zip(pending, values):
                            row = len(vectors)
                            vectors.append(vector.copy())
                            try:
                                apply_model(game, vector.tolist(), contract, row)
                            except Exception as error:
                                game.update(termination="model_output_error", error=type(error).__name__,
                                            failed_output={"logit_row": row, "fen": game["board"].fen(),
                                                           "error": type(error).__name__})
                for game in model_games:
                    if finish_if_needed(game, protocol["conditions"]["max_additional_plies"]):
                        continue
                    if game["board"].turn != (game["model_colour"] == "white"):
                        try:
                            engine.configure({"Clear Hash": None})
                            move = engine.play(game["board"], chess.engine.Limit(nodes=opponent["nodes_per_move"]), game=game["id"]).move
                            if move not in game["board"].legal_moves:
                                raise ValueError("illegal opponent move")
                            game["moves"].append({"actor": "opponent", "fen": game["board"].fen(), "uci": move.uci()})
                            game["board"].push(move)
                            game["additional_plies"] += 1
                        except Exception as error:
                            game.update(termination="opponent_error", error=type(error).__name__)
                save(out / f"{name}-games.json", [game_record(g) for g in model_games])
                print(json.dumps({"model": name, "finished": sum(g["termination"] is not None for g in model_games),
                                  "total": len(model_games), "model_calls": len(vectors)}), flush=True)
        logit_path = out / f"{name}-logits.npy"
        np.save(logit_path, np.array(vectors, dtype=np.float32).reshape(-1, len(contract["id2label"])))
        logit_files[name] = {"path": logit_path.name, "rows": len(vectors), "sha256": digest(logit_path)}
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
    pgn_path = out / "games.pgn"
    pgn_path.write_text("\n\n".join(export_pgn(g) for g in games) + "\n", encoding="utf-8")
    records_path = out / "games.json"
    save(records_path, [game_record(g) for g in games])
    receipt = {"schema": "chess.rollout.stress.receipt.v1", "protocol_sha256": digest(protocol_path),
               "source_snapshots": snapshots, "model_binding": expected, "engine_sha256": digest(engine_path),
               "native_contract_source_sha256": contract_sources, "contract_failures": contract_failures,
               "planned_games": len(games), "aggregate": aggregate(games), "elapsed_seconds": time.perf_counter()-started,
               "runtime": {"device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
                           "torch": torch.__version__, "python_chess": chess.__version__},
               "artifacts": {"games_json_sha256": digest(records_path), "pgn_sha256": digest(pgn_path), "logits": logit_files},
               "limitations": protocol["limitations"]}
    save(out / "receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "research/chess-rollout-stress-protocol-v1.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/private/chess-rollout-stress-v1")
    parser.add_argument("--base-dir", type=Path, default=ROOT / "data/private/chess-classifier-v3/base-model")
    parser.add_argument("--selected-dir", type=Path, default=ROOT / "data/private/chess-classifier-v3/checkpoints/step-512")
    parser.add_argument("--engine", type=Path, default=ROOT / "data/private/chess-distill-v1/tools/stockfish/stockfish-windows-x86-64-universal.exe")
    args = parser.parse_args()
    print(json.dumps(run(args.protocol, args.out, args.base_dir, args.selected_dir, args.engine)))
