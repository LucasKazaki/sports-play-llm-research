"""Move-only native classifier pilot with bounded parallel Stockfish teachers."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import io
import json
import random
import shutil
import time
from pathlib import Path

import chess
import chess.engine
import chess_stockfish_distill as core


def acquire(protocol, protocol_path, out):
    import zstandard
    previous = [core.ROOT / f"data/private/chess-distill-v{v}" for v in (1, 2)]
    source = previous[0] / "source-prefix.csv.zst.part"
    first = json.loads((previous[0] / "dataset.json").read_text())
    if core.digest(source) != first["acquisition"]["sha256"]:
        raise ValueError("retained source identity mismatch")
    games, positions = core.historical_exclusions(core.ROOT / "data/open/chess/lichess-real-seed-v1/manifest.json")
    previous_ids = set()
    previous_hashes = []
    for directory in previous:
        manifest = json.loads((directory / "dataset.json").read_text())
        previous_hashes.append(core.digest(directory / "dataset.json"))
        for rows in manifest["splits"].values():
            for row in rows:
                games.add(row["game_id"])
                positions.add(core.board_key(row["fen"]))
                previous_ids.add(row["id"])
    # Include both roles of every prior source puzzle, not just its presented board.
    with source.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as text:
            for row in csv.DictReader(text):
                if row["PuzzleId"] not in previous_ids:
                    continue
                positions.add(core.board_key(row["FEN"]))
                previous_ids.remove(row["PuzzleId"])
                if not previous_ids:
                    break
    if previous_ids:
        raise ValueError("prior puzzle roles absent from exact retained prefix")
    counts = {k: protocol["splits"][k] for k in ("train", "development", "holdout")}
    with source.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as text:
            splits, rejected = core.select_rows(csv.DictReader(text), counts, protocol["splits"]["seed"], games, positions)
    result = {"schema": "chess.classifier.dataset.v3", "protocol_sha256": core.digest(protocol_path),
              "source": first["acquisition"], "source_reused": True, "previous_manifest_sha256": previous_hashes,
              "exclusions": {"games": len(games), "board_keys": len(positions)},
              "selection_rejections": rejected, "splits": splits}
    core.save(out / "dataset.json", result)
    return result


def label_batch(engine_path, settings, rows):
    labelled = []
    with chess.engine.SimpleEngine.popen_uci(engine_path, timeout=60) as engine:
        engine.configure({"Threads": 1, "Hash": settings["hash_mb_per_worker"]})
        if "19" not in engine.id.get("name", ""):
            raise ValueError("pinned Stockfish19 required")
        for split, row in rows:
            board = chess.Board(row["fen"])
            engine.configure({"Clear Hash": None})
            observation = None
            with engine.analysis(board, chess.engine.Limit(nodes=settings["nodes"]),
                                 info=chess.engine.INFO_SCORE | chess.engine.INFO_PV | chess.engine.INFO_BASIC) as analysis:
                for event in analysis:
                    if "score" in event:
                        score = event["score"].pov(board.turn)
                        observation = {"cp": score.score(), "mate": score.mate(),
                                       "lowerbound": bool(event.get("lowerbound")), "upperbound": bool(event.get("upperbound")),
                                       "perspective": "side_to_move", "depth": event.get("depth"), "nodes": event.get("nodes"),
                                       "move_uci": event["pv"][0].uci() if event.get("pv") else None}
                final = analysis.wait()
            if final.move not in board.legal_moves:
                raise ValueError("completed teacher bestmove is not legal")
            labelled.append((split, {**row, "teacher_move_uci": final.move.uci(), "score_observation": observation}))
    return labelled


def label(protocol, dataset, out):
    settings = protocol["teacher"]
    engine = core.ROOT / "data/private/chess-distill-v1/tools/stockfish/stockfish-windows-x86-64-universal.exe"
    rows = [(split, row) for split, items in dataset["splits"].items() for row in items]
    chunks = [rows[i:i+256] for i in range(0, len(rows), 256)]
    result = {"schema": "chess.classifier.labels.v3", "dataset_sha256": core.digest(out / "dataset.json"),
              "engine": {"name": "Stockfish19", "sha256": core.digest(engine), "settings": settings},
              "splits": {key: [] for key in dataset["splits"]}}
    started, done = time.perf_counter(), 0
    with ProcessPoolExecutor(max_workers=settings["workers"]) as pool:
        futures = [pool.submit(label_batch, str(engine), settings, chunk) for chunk in chunks]
        for future in as_completed(futures):
            for split, row in future.result():
                result["splits"][split].append(row)
                done += 1
            print(json.dumps({"phase": "parallel_teacher", "done": done, "total": len(rows),
                              "workers": settings["workers"], "seconds": round(time.perf_counter()-started, 2)}), flush=True)
    # Restore frozen source ordering independently of process scheduling.
    for split, items in dataset["splits"].items():
        by_id = {row["id"]: row for row in result["splits"][split]}
        result["splits"][split] = [by_id[row["id"]] for row in items]
    result["elapsed_seconds"] = time.perf_counter()-started
    core.save(out / "labels.json", result)
    return result


def encode_rows(rows, contract):
    from chess_classifier_adapter import encode_fen
    good, failures = [], []
    for index, row in enumerate(rows):
        try:
            item = encode_fen(row["fen"], contract)
            label = contract["label2id"][row["teacher_move_uci"]]
            good.append((index, item["input_ids"], label))
        except (ValueError, KeyError) as error:
            failures.append({"index": index, "id": row["id"], "error": str(error)})
    return good, failures


def evaluate(model, rows, contract, device, prefix, out, batch_size):
    import numpy as np
    import torch
    from chess_classifier_adapter import rank_logits
    good, failures = encode_rows(rows, contract)
    records = [{"id": r["id"], "game_id": r["game_id"], "fen": r["fen"], "teacher_move_uci": r["teacher_move_uci"],
                "raw_legal": False, "raw_match": False, "top3_match": False, "masked_match": False} for r in rows]
    for failed in failures:
        records[failed["index"]]["error"] = failed["error"]
    all_logits, loss_sum, loss_count = [], 0.0, 0
    model_failure = None
    started = time.perf_counter()
    model.eval()
    with torch.inference_mode():
        for offset in range(0, len(good), batch_size):
            batch = good[offset:offset+batch_size]
            ids = torch.tensor([item[1] for item in batch], dtype=torch.long, device=device)
            if model_failure is not None:
                all_logits.append(np.full((len(batch), len(contract["id2label"])), np.nan, dtype=np.float32))
                for index, _, _ in batch:
                    records[index]["error"] = "not_run_after_model_failure"
                continue
            try:
                logits = model(input_ids=ids, attention_mask=torch.ones_like(ids)).logits
                if not torch.is_tensor(logits) or tuple(logits.shape) != (len(batch), len(contract["id2label"])):
                    raise ValueError("model logits shape does not match input batch and1968classes")
                logits = logits.float()
                values = logits.cpu().numpy()
            except Exception as error:
                # Stop further calls; preserve every planned row in the denominator.
                model_failure = type(error).__name__
                all_logits.append(np.full((len(batch), len(contract["id2label"])), np.nan, dtype=np.float32))
                for index, _, _ in batch:
                    records[index]["error"] = "model_call_failed:" + model_failure
                continue
            all_logits.append(values)
            for (index, _, target), vector in zip(batch, values):
                if not np.isfinite(vector).all():
                    records[index]["error"] = "nonfinite model logits"
                    continue
                ranking = rank_logits(rows[index]["fen"], vector.tolist(), contract["id2label"], top_k=3)
                raw, masked = ranking["raw_topk"], ranking["legal_topk"]
                raw_move = raw[0]["move_uci"]
                masked_move = masked[0]["move_uci"] if masked else None
                records[index].update(raw_topk=raw, legal_topk=masked,
                                      raw_legal=raw[0]["legal"], raw_move_uci=raw_move, masked_move_uci=masked_move,
                                      raw_match=raw_move == rows[index]["teacher_move_uci"],
                                      top3_match=any(c["move_uci"] == rows[index]["teacher_move_uci"] for c in raw),
                                      masked_match=masked_move == rows[index]["teacher_move_uci"])
                loss_sum += float(torch.nn.functional.cross_entropy(logits.new_tensor(vector).unsqueeze(0),
                                  torch.tensor([target], device=device)))
                loss_count += 1
    logits_path = out / f"{prefix}-logits.npy"
    np.save(logits_path, np.concatenate(all_logits) if all_logits else np.empty((0, len(contract["id2label"]))))
    result = {"count": len(rows), "encoded_count": len(good), "raw_legal_count": sum(r["raw_legal"] for r in records),
              "raw_top1_match_count": sum(r["raw_match"] for r in records), "raw_top3_match_count": sum(r["top3_match"] for r in records),
              "masked_top1_match_count": sum(r["masked_match"] for r in records),
              "failure_count": sum("error" in r for r in records), "cross_entropy": loss_sum/loss_count if loss_count else None,
              "model_failure_stop": model_failure,
              "cross_entropy_count": loss_count, "elapsed_seconds": time.perf_counter()-started,
              "logits_sha256": core.digest(logits_path), "records": records}
    core.save(out / f"{prefix}.json", result)
    return result


def selection_key(step, result):
    return result["raw_top1_match_count"], result["raw_legal_count"], -step


def train(protocol, protocol_path, out):
    import platform
    import torch
    import transformers
    from transformers import LlamaForSequenceClassification
    from chess_classifier_adapter import load_native_contract
    settings = protocol["training"]
    base_path = out / "base-model"
    contract = load_native_contract(base_path)
    labels = json.loads((out / "labels.json").read_text())
    encoded, rejected = encode_rows(labels["splits"]["train"], contract)
    if not encoded:
        raise ValueError("no training rows encoded")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(4)
    torch.manual_seed(settings["seed"])
    model = LlamaForSequenceClassification.from_pretrained(base_path, local_files_only=True,
                                                          attn_implementation="sdpa").float().to(device)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    checkpoint_root = out / "checkpoints"
    if checkpoint_root.exists():
        raise ValueError("refusing to replace an existing training run")
    checkpoint_root.mkdir()
    for file in (Path(__file__), Path(core.__file__), core.ROOT / "scripts/chess_classifier_adapter.py", protocol_path):
        shutil.copyfile(file, out / ("executed-"+file.name))
    evaluations = {0: evaluate(model, labels["splits"]["development"], contract, device, "base-development", out, protocol["evaluation"]["batch_size"])}
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings["learning_rate"], weight_decay=settings["weight_decay"])
    rng, order, training_log = random.Random(settings["seed"]), [], []
    model.train()
    started = time.perf_counter()
    for step in range(1, settings["steps"]+1):
        if len(order) < settings["batch_size"]:
            new_order = list(range(len(encoded)))
            rng.shuffle(new_order)
            order.extend(new_order)
        chosen, order = order[:settings["batch_size"]], order[settings["batch_size"]:]
        ids = torch.tensor([encoded[i][1] for i in chosen], dtype=torch.long, device=device)
        target = torch.tensor([encoded[i][2] for i in chosen], dtype=torch.long, device=device)
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=ids, attention_mask=torch.ones_like(ids), labels=target).loss
        if not torch.isfinite(loss):
            raise ValueError("nonfinite classifier loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), settings["gradient_clip"])
        optimizer.step()
        training_log.append({"step": step, "loss": float(loss.detach())})
        if step % 32 == 0:
            core.save(out / "training-log.json", training_log)
            print(json.dumps({"phase": "classifier_train", **training_log[-1], "seconds": round(time.perf_counter()-started, 2)}), flush=True)
        if step in settings["checkpoint_steps"]:
            model.save_pretrained(checkpoint_root / f"step-{step}", safe_serialization=True)
            evaluations[step] = evaluate(model, labels["splits"]["development"], contract, device,
                                         f"step-{step}-development", out, protocol["evaluation"]["batch_size"])
            model.train()
    training_seconds = time.perf_counter()-started
    selected_step = max(evaluations, key=lambda step: selection_key(step, evaluations[step]))
    selected_path = base_path if selected_step == 0 else checkpoint_root / f"step-{selected_step}"
    selection = {"selected_step": selected_step, "selected_model_sha256": core.digest(selected_path / "model.safetensors"),
                 "development_candidates": {str(k): {x: y for x, y in v.items() if x != "records"} for k, v in evaluations.items()},
                 "rule": protocol["selection"], "holdout_opened": False}
    core.save(out / "selection-before-holdout.json", selection)
    del optimizer, model
    if device == "cuda":
        torch.cuda.empty_cache()
    base = LlamaForSequenceClassification.from_pretrained(base_path, local_files_only=True, attn_implementation="sdpa").float().to(device)
    baseline_holdout = evaluate(base, labels["splits"]["holdout"], contract, device, "base-holdout", out, protocol["evaluation"]["batch_size"])
    if selected_step == 0:
        selected_holdout = baseline_holdout
    else:
        del base
        if device == "cuda":
            torch.cuda.empty_cache()
        selected = LlamaForSequenceClassification.from_pretrained(selected_path, local_files_only=True, attn_implementation="sdpa").float().to(device)
        selected_holdout = evaluate(selected, labels["splits"]["holdout"], contract, device, "selected-holdout", out, protocol["evaluation"]["batch_size"])
    receipt = {"schema": "chess.stockfish-classifier.v3", "protocol_sha256": core.digest(protocol_path),
               "dataset_sha256": core.digest(out / "dataset.json"), "labels_sha256": core.digest(out / "labels.json"),
               "model": {"source": protocol["base_model"], "revision": protocol["base_revision"],
                         "base_sha256": core.digest(base_path / "model.safetensors"), "selected_step": selected_step,
                         "selected_sha256": core.digest(selected_path / "model.safetensors")},
               "training": {**settings, "encoded_count": len(encoded), "rejected_rows": rejected,
                            "presentations": settings["steps"]*settings["batch_size"], "elapsed_seconds_including_dev_checks": training_seconds},
               "selection_receipt_sha256": core.digest(out / "selection-before-holdout.json"),
               "evaluation": {"baseline": {"development": evaluations[0], "holdout": baseline_holdout},
                              "selected": {"development": evaluations[selected_step], "holdout": selected_holdout}},
               "runtime": {"device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
                           "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
                           "python": platform.python_version(), "torch": torch.__version__, "transformers": transformers.__version__},
               "limitations": ["Tactical prefix convenience sample; unknown upstream pretraining overlap.",
                               "Raw and legal-mask outcomes are separate; masked legality does not establish model board understanding.",
                               "Move-only classifier is not a language/commentary model, and no Elo or sports competence is established.",
                               "Development checkpoint selection is declared; heldout is used only after selection.",
                               "Experimental candidate, no automatic model-default or scientific promotion."]}
    core.save(out / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("acquire", "label", "train"))
    parser.add_argument("--out", type=Path, default=core.ROOT / "data/private/chess-classifier-v3")
    parser.add_argument("--protocol", type=Path, default=core.ROOT / "research/chess-classifier-protocol-v3.json")
    args = parser.parse_args(argv)
    protocol = json.loads(args.protocol.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    if args.phase == "acquire":
        if (args.out / "dataset.json").exists():
            raise ValueError("dataset already frozen")
        result = acquire(protocol, args.protocol, args.out)
        print(json.dumps({"splits": {k: len(v) for k, v in result["splits"].items()}}))
    elif args.phase == "label":
        if (args.out / "labels.json").exists():
            raise ValueError("labels already frozen")
        label(protocol, json.loads((args.out / "dataset.json").read_text()), args.out)
    else:
        result = train(protocol, args.protocol, args.out)
        print(json.dumps({"selected_step": result["model"]["selected_step"], "cuda_peak_allocated_bytes": result["runtime"]["cuda_peak_allocated_bytes"]}))


if __name__ == "__main__":
    main()
