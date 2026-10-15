"""Bounded real Stockfish supervision and actual ROOK weight updates.

This is a move-policy pilot, not a commentary or Elo evaluation. Raw data,
checkpoints and detailed inference receipts stay in ignored local storage.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UCI = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def board_key(fen):
    import chess
    return " ".join(chess.Board(fen).fen().split()[:4])


def split_for_game(game_id, seed):
    bucket = int(hashlib.sha256(f"{seed}:{game_id}".encode()).hexdigest(), 16) % 10
    return "holdout" if bucket == 0 else "development" if bucket == 1 else "train"


def historical_exclusions(path):
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    games, positions = set(), set()
    for item in frozen["items"]:
        games.add(item["game_id"])
        positions.add(board_key(item["fen"]))
        for ply in item.get("legal_replay", []):
            positions.update((board_key(ply["before"]), board_key(ply["after"])))
    return games, positions


def select_rows(rows, counts, seed, excluded_games=(), excluded_positions=()):
    import chess
    result = {key: [] for key in counts}
    seen_games, seen_positions = set(excluded_games), set(excluded_positions)
    rejected = {"invalid": 0, "duplicate_or_excluded": 0, "bucket_full": 0}
    for row in rows:
        try:
            game_id = row["GameUrl"].split("lichess.org/", 1)[1].split("/", 1)[0].split("#", 1)[0]
            if not re.fullmatch(r"[A-Za-z0-9]{8}", game_id):
                raise ValueError("invalid game id")
            board = chess.Board(row["FEN"])
            if not board.is_valid():
                raise ValueError("invalid board")
            setup = chess.Move.from_uci(row["Moves"].split()[0])
            if setup not in board.legal_moves:
                raise ValueError("illegal setup move")
            before_key = board_key(board.fen())
            board.push(setup)
            key = board_key(board.fen())
            if board.is_game_over():
                raise ValueError("terminal board")
            if game_id in seen_games or key in seen_positions or before_key in seen_positions:
                rejected["duplicate_or_excluded"] += 1
                continue
            split = split_for_game(game_id, seed)
            if len(result[split]) >= counts[split]:
                rejected["bucket_full"] += 1
                continue
            result[split].append({"id": row["PuzzleId"], "game_id": game_id,
                                  "source_url": f"https://lichess.org/{game_id}",
                                  "fen": board.fen(), "rating": int(row["Rating"])})
            seen_games.add(game_id)
            seen_positions.update((key, before_key))
        except (KeyError, ValueError, IndexError):
            rejected["invalid"] += 1
            continue
        if all(len(result[k]) == counts[k] for k in counts):
            break
    missing = {k: counts[k] - len(result[k]) for k in counts if len(result[k]) < counts[k]}
    if missing:
        raise ValueError(f"bounded source did not fill frozen splits: {missing}")
    return result, rejected


def acquire(protocol, out):
    import requests
    import zstandard
    limit = protocol["acquisition"]["maximum_compressed_bytes"]
    source = out / "source-prefix.csv.zst.part"
    response = requests.get(protocol["source_url"], headers={"Range": f"bytes=0-{limit-1}"},
                            stream=True, timeout=(15, 60))
    with response:
        response.raise_for_status()
        if response.status_code != 206 or not response.headers.get("Content-Range", "").startswith("bytes 0-"):
            raise ValueError("source must honor bounded prefix Range request")
        total = 0
        with source.open("wb") as stream:
            for chunk in response.iter_content(65536):
                if total + len(chunk) > limit:
                    raise ValueError("source exceeded compressed byte bound")
                stream.write(chunk)
                total += len(chunk)
        acquisition = {"url": protocol["source_url"], "status": response.status_code,
                       "content_range": response.headers.get("Content-Range"),
                       "etag": response.headers.get("ETag"), "bytes": total,
                       "sha256": digest(source), "captured_at": datetime.now(timezone.utc).isoformat()}
    games, positions = historical_exclusions(ROOT / "data/open/chess/lichess-real-seed-v1/manifest.json")
    counts = {k: protocol["splits"][k] for k in ("train", "development", "holdout")}
    with source.open("rb") as raw:
        reader = zstandard.ZstdDecompressor().stream_reader(raw)
        with io.TextIOWrapper(reader, encoding="utf-8") as text:
            splits, rejected = select_rows(csv.DictReader(text), counts, protocol["splits"]["seed"], games, positions)
    manifest = {"schema": "chess.stockfish-distillation.dataset.v1", "acquisition": acquisition,
                "rights": protocol["source_rights"], "exclusions": {"historical_games": len(games),
                "historical_board_keys": len(positions)}, "selection_rejections": rejected,
                "protocol_sha256": digest(ROOT / "research/stockfish-distillation-protocol-v1.json"),
                "splits": splits}
    save(out / "dataset.json", manifest)
    return manifest


def label(protocol, dataset, engine_path, out):
    import chess
    import chess.engine
    teacher = protocol["teacher"]
    labelled = {"schema": "chess.stockfish-distillation.labels.v1", "splits": {}}
    with chess.engine.SimpleEngine.popen_uci(str(engine_path), timeout=60) as engine:
        engine.configure({"Threads": teacher["threads"], "Hash": teacher["hash_mb"]})
        labelled["engine"] = {**engine.id, "sha256": digest(engine_path), "settings": teacher}
        if "19" not in engine.id.get("name", ""):
            raise ValueError("frozen protocol requires Stockfish 19")
        for split, rows in dataset["splits"].items():
            labelled["splits"][split] = []
            for i, row in enumerate(rows):
                board = chess.Board(row["fen"])
                engine.configure({"Clear Hash": None})
                infos = engine.analyse(board, chess.engine.Limit(nodes=teacher["nodes_per_position"]),
                                       multipv=teacher["multipv"])
                candidates = []
                for info in infos:
                    move = info["pv"][0]
                    if move not in board.legal_moves:
                        raise ValueError("engine returned illegal candidate")
                    score = info["score"].pov(board.turn)
                    candidates.append({"move_uci": move.uci(), "score_cp": score.score(),
                                       "mate": score.mate(), "depth": info.get("depth"),
                                       "nodes": info.get("nodes"), "lowerbound": bool(info.get("lowerbound")),
                                       "upperbound": bool(info.get("upperbound"))})
                labelled["splits"][split].append({**row, "teacher_move_uci": candidates[0]["move_uci"],
                                                  "candidates": candidates})
                if (i + 1) % 100 == 0:
                    print(json.dumps({"phase": "label", "split": split, "done": i+1}), flush=True)
    save(out / "labels.json", labelled)
    return labelled


def prompt_for(row):
    # Current position only. Do not pass the row or teacher candidate object to generation.
    return row["fen"].ljust(90)


def target_for(row):
    candidates = row["candidates"]
    moves = " ".join(c["move_uci"] for c in candidates)
    scores = " ".join(f"#{c['mate']}" if c["mate"] is not None else f"{c['score_cp']/100:.2f}" for c in candidates)
    return f"M: {moves} E: {scores} B: {row['teacher_move_uci']}"


def parse_action(output):
    for marker, fallback in (("B:", False), ("M:", True)):
        if marker in output:
            tail = output.split(marker, 1)[1].strip().split()
            if tail and UCI.fullmatch(tail[0]):
                return tail[0], fallback
    return None, False


def legal_action(fen, move):
    import chess
    try:
        return move is not None and chess.Move.from_uci(move) in chess.Board(fen).legal_moves
    except ValueError:
        return False


def make_example(row, tokenizer):
    prefix = tokenizer.encode(prompt_for(row), add_special_tokens=False)
    # Separate tokenization keeps the input/target boundary exact, with no target leakage.
    completion = tokenizer.encode(target_for(row) + tokenizer.eos_token, add_special_tokens=False)
    return prefix + completion, [-100] * len(prefix) + completion


def collate(examples, pad_id, torch):
    width = max(len(x[0]) for x in examples)
    ids, labels, mask = [], [], []
    for tokens, target in examples:
        padding = width - len(tokens)
        ids.append(tokens + [pad_id] * padding)
        labels.append(target + [-100] * padding)
        mask.append([1] * len(tokens) + [0] * padding)
    return {"input_ids": torch.tensor(ids), "attention_mask": torch.tensor(mask),
            "labels": torch.tensor(labels)}


def evaluate(model, tokenizer, rows, protocol, device):
    import chess
    import torch
    model.eval()
    records = []
    start = time.perf_counter()
    batch_size = protocol["generation"]["batch_size"]
    tokenizer.padding_side = "left"
    with torch.inference_mode():
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset+batch_size]
            inputs = tokenizer([prompt_for(row) for row in batch], return_tensors="pt", padding=True).to(device)
            generated = model.generate(**inputs, max_new_tokens=protocol["generation"]["max_new_tokens"],
                                       do_sample=False, pad_token_id=tokenizer.pad_token_id,
                                       eos_token_id=tokenizer.eos_token_id)
            outputs = tokenizer.batch_decode(generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            for row, output in zip(batch, outputs):
                move, fallback = parse_action(output)
                legal = legal_action(row["fen"], move)
                records.append({"id": row["id"], "fen": row["fen"], "raw_output": output,
                                "move_uci": move, "legal": legal, "used_candidate_fallback": fallback,
                                "teacher_move_uci": row["teacher_move_uci"],
                                "match": legal and move == row["teacher_move_uci"]})
            print(json.dumps({"phase": "evaluate", "done": len(records), "total": len(rows)}), flush=True)
    return {"count": len(rows), "raw_legal_count": sum(r["legal"] for r in records),
            "top1_match_count": sum(r["match"] for r in records),
            "fallback_count": sum(r["used_candidate_fallback"] for r in records),
            "failures": sum(r["move_uci"] is None for r in records),
            "elapsed_seconds": round(time.perf_counter()-start, 3), "records": records}


def completion_nll(model, examples, pad_id, device, batch_size):
    import torch
    model.eval()
    weighted, count = 0.0, 0
    with torch.inference_mode():
        for offset in range(0, len(examples), batch_size):
            batch = {k: v.to(device) for k, v in collate(examples[offset:offset+batch_size], pad_id, torch).items()}
            n = int((batch["labels"][:, 1:] != -100).sum())
            weighted += float(model(**batch).loss) * n
            count += n
    return weighted / count


def train_and_evaluate(protocol, labels, out, base_path, protocol_path):
    import platform
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    training = protocol["training"]
    torch.set_num_threads(8)
    torch.manual_seed(training["seed"])
    random.seed(training["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(base_path, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_path, local_files_only=True, attn_implementation="sdpa").to(device)
    before_hash = digest(Path(base_path) / "model.safetensors")
    examples = [make_example(row, tokenizer) for row in labels["splits"]["train"]]
    dev_examples = [make_example(row, tokenizer) for row in labels["splits"]["development"]]
    before = {"development": evaluate(model, tokenizer, labels["splits"]["development"], protocol, device)}
    save(out / "baseline-development.json", before)
    nll_before = completion_nll(model, dev_examples, tokenizer.pad_token_id, device, 8)
    optimizer = torch.optim.AdamW(model.parameters(), lr=training["learning_rate"], weight_decay=training["weight_decay"])
    model.train()
    rng = random.Random(training["seed"])
    order = []
    log = []
    start = time.perf_counter()
    bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
    for step in range(training["steps"]):
        if len(order) < training["batch_size"]:
            refill = list(range(len(examples)))
            rng.shuffle(refill)
            order.extend(refill)
        indices, order = order[:training["batch_size"]], order[training["batch_size"]:]
        batch = {k: v.to(device) for k, v in collate([examples[i] for i in indices], tokenizer.pad_token_id, torch).items()}
        optimizer.zero_grad(set_to_none=True)
        autocast = torch.autocast("cuda", dtype=torch.bfloat16) if bf16 else contextlib.nullcontext()
        with autocast:
            loss = model(**batch).loss
        if not torch.isfinite(loss):
            raise ValueError("non-finite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        log.append({"step": step+1, "loss": float(loss.detach())})
        if (step+1) % 10 == 0:
            print(json.dumps({"phase": "train", **log[-1], "seconds": round(time.perf_counter()-start, 1)}), flush=True)
            save(out / "training-log.json", log)
    checkpoint = out / "checkpoint"
    model.save_pretrained(checkpoint, safe_serialization=True)
    tokenizer.save_pretrained(checkpoint)
    save(out / "training-complete.json", {"steps": training["steps"], "examples_seen": training["steps"]*training["batch_size"],
                                          "elapsed_seconds": time.perf_counter()-start,
                                          "checkpoint_sha256": digest(checkpoint / "model.safetensors")})
    nll_after = completion_nll(model, dev_examples, tokenizer.pad_token_id, device, 8)
    after = {"development": evaluate(model, tokenizer, labels["splits"]["development"], protocol, device)}
    # Holdout opened only after the fixed training run and checkpoint are complete.
    after["holdout"] = evaluate(model, tokenizer, labels["splits"]["holdout"], protocol, device)
    del optimizer, model
    if device == "cuda":
        torch.cuda.empty_cache()
    base = AutoModelForCausalLM.from_pretrained(base_path, local_files_only=True, attn_implementation="sdpa").to(device)
    before["holdout"] = evaluate(base, tokenizer, labels["splits"]["holdout"], protocol, device)
    receipt = {"schema": "chess.stockfish-distillation.v1", "created_at": datetime.now(timezone.utc).isoformat(),
               "protocol_sha256": digest(protocol_path),
               "dataset": {"source_url": protocol["source_url"], "sha256": digest(out / "dataset.json"),
                           "labels_sha256": digest(out / "labels.json"),
                           **{f"{key}_count": len(rows) for key, rows in labels["splits"].items()}},
               "teacher": labels["engine"],
               "model": {"source": protocol["base_model"], "revision": protocol["base_revision"],
                         "base_sha256": before_hash, "checkpoint_sha256": digest(checkpoint / "model.safetensors")},
               "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                           "torch": torch.__version__, "transformers": transformers.__version__,
                           "device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None},
               "training": {**training, "examples_seen": training["steps"]*training["batch_size"],
                            "loss_before": nll_before, "loss_after": nll_after,
                            "optimizer_log": log, "elapsed_seconds": round(time.perf_counter()-start, 3)},
               "evaluation": {"baseline": before, "trained": after},
               "limitations": ["Tactical prefix convenience sample, not a representative chess benchmark.",
                               "Game disjointness does not exclude unknown overlap with upstream ROOK pretraining.",
                               "10,000-node Stockfish agreement is a bounded reference, not perfect chess truth.",
                               "No Elo, commentary quality, human teaching or sports transfer was measured.",
                               "No proprietary model or creator transcript was used as training data."]}
    if receipt["model"]["base_sha256"] == receipt["model"]["checkpoint_sha256"]:
        raise ValueError("checkpoint identical to base weights")
    save(out / "receipt.json", receipt)
    return receipt


def finalize_checkpoint(protocol, out, base_path, protocol_path):
    """Re-evaluate a completed checkpoint after an accounting failure; never train."""
    import platform
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    labels = json.loads((out / "labels.json").read_text())
    log = json.loads((out / "training-log.json").read_text())
    expected_steps = protocol["training"]["steps"]
    if len(log) != expected_steps or [r["step"] for r in log] != list(range(1, expected_steps+1)):
        raise ValueError("complete ordered optimizer log required")
    torch.set_num_threads(8)
    torch.manual_seed(protocol["training"]["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(base_path, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    dev_examples = [make_example(row, tokenizer) for row in labels["splits"]["development"]]
    before = json.loads((out / "baseline-development.json").read_text())
    base = AutoModelForCausalLM.from_pretrained(base_path, local_files_only=True, attn_implementation="sdpa").to(device)
    nll_before = completion_nll(base, dev_examples, tokenizer.pad_token_id, device, 8)
    before["holdout"] = evaluate(base, tokenizer, labels["splits"]["holdout"], protocol, device)
    save(out / "baseline-complete.json", before)
    del base
    if device == "cuda":
        torch.cuda.empty_cache()
    checkpoint = out / "checkpoint"
    model = AutoModelForCausalLM.from_pretrained(checkpoint, local_files_only=True, attn_implementation="sdpa").to(device)
    nll_after = completion_nll(model, dev_examples, tokenizer.pad_token_id, device, 8)
    after = {}
    for split in ("development", "holdout"):
        after[split] = evaluate(model, tokenizer, labels["splits"][split], protocol, device)
        save(out / f"trained-{split}.json", after[split])
    completion_path = out / "training-complete.json"
    timing = json.loads(completion_path.read_text()) if completion_path.exists() else {"elapsed_seconds": None}
    receipt = {"schema": "chess.stockfish-distillation.v1", "created_at": datetime.now(timezone.utc).isoformat(),
               "protocol_sha256": digest(protocol_path), "implementation_sha256": digest(Path(__file__)),
               "dataset": {"source_url": protocol["source_url"], "sha256": digest(out / "dataset.json"),
                           "labels_sha256": digest(out / "labels.json"),
                           **{f"{key}_count": len(rows) for key, rows in labels["splits"].items()}},
               "teacher": labels["engine"],
               "model": {"source": protocol["base_model"], "revision": protocol["base_revision"],
                         "base_sha256": digest(Path(base_path) / "model.safetensors"),
                         "checkpoint_sha256": digest(checkpoint / "model.safetensors")},
               "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                           "torch": torch.__version__, "transformers": transformers.__version__,
                           "device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None},
               "training": {**protocol["training"], "examples_seen": expected_steps*protocol["training"]["batch_size"],
                            "loss_before": nll_before, "loss_after": nll_after, "optimizer_log": log,
                            "elapsed_seconds": timing["elapsed_seconds"]},
               "evaluation": {"baseline": before, "trained": after},
               "recovery": {"reason": "original evaluation raised on same-square UCI a7a7 after completed training",
                            "checkpoint_retrained": False, "failed_log_sha256": digest(out / "train.log"),
                            "holdout_replayed": "fixed deterministic accounting only; no weight or hyperparameter changes"},
               "limitations": ["Tactical prefix convenience sample; not representative chess or Elo measurement.",
                               "Fresh source games are disjoint from historical seed and across this experiment; upstream pretraining overlap is unknown.",
                               "No commentary, teaching quality, creator-model equivalence or sports transfer measured.",
                               "Training wall-clock timing unavailable after original accounting failure; optimizer log and saved weights retained.",
                               "No proprietary model or creator transcript was used as training data."]}
    if receipt["model"]["base_sha256"] == receipt["model"]["checkpoint_sha256"]:
        raise ValueError("checkpoint identical to base")
    save(out / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("acquire", "label", "train", "evaluate"))
    parser.add_argument("--protocol", type=Path, default=ROOT / "research/stockfish-distillation-protocol-v1.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/private/chess-distill-v1")
    parser.add_argument("--engine", type=Path)
    parser.add_argument("--base-model", type=Path)
    args = parser.parse_args(argv)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    if args.phase == "acquire":
        result = acquire(protocol, args.out)
        print(json.dumps({"splits": {k: len(v) for k, v in result["splits"].items()}, "source": result["acquisition"]}))
    elif args.phase == "label":
        if not args.engine:
            parser.error("--engine required for label")
        result = label(protocol, json.loads((args.out / "dataset.json").read_text()), args.engine, args.out)
        print(json.dumps({"engine": result["engine"], "labelled": sum(map(len, result["splits"].values()))}))
    else:
        if not args.base_model:
            parser.error("--base-model required for train")
        if args.phase == "evaluate":
            result = finalize_checkpoint(protocol, args.out, args.base_model, args.protocol)
        else:
            result = train_and_evaluate(protocol, json.loads((args.out / "labels.json").read_text()), args.out, args.base_model, args.protocol)
        print(json.dumps({"trained": True, "checkpoint_sha256": result["model"]["checkpoint_sha256"]}))


if __name__ == "__main__":
    main()
