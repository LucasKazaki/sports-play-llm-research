"""Separately versioned move-only language-policy training and frozen selection."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import contextlib
import csv
import io
import json
from pathlib import Path
import random
import re
import shutil
import time

import chess
import chess_stockfish_distill as core
import chess_classifier_experiment_v3 as classifier


def prompt_for(row):
    fen = row["fen"]
    if not isinstance(fen, str) or len(fen) > 90 or not chess.Board(fen).is_valid():
        raise ValueError("unsupported native FEN")
    return f"P: {fen:90}M:"


def parse_action(output):
    text = output.strip()
    if text.startswith("M:"):
        text = text[2:].lstrip()
    first = text.split(maxsplit=1)[0] if text else ""
    return first if re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", first) else None


def make_example(row, tokenizer):
    if not core.legal_action(row["fen"], row["teacher_move_uci"]):
        raise ValueError("illegal completion supervision")
    prefix = prompt_for(row)
    text = prefix + " " + row["teacher_move_uci"] + tokenizer.eos_token
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids, labels = encoded["input_ids"], []
    for token, (start, end) in zip(ids, encoded["offset_mapping"]):
        if start < len(prefix) < end:
            raise ValueError("token crosses supervision boundary")
        labels.append(-100 if start < len(prefix) else token)
    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    if ids[:len(prefix_ids)] != prefix_ids or labels[:len(prefix_ids)] != [-100] * len(prefix_ids):
        raise ValueError("training and inference prefix differ")
    if all(value == -100 for value in labels):
        raise ValueError("no completion supervision")
    return ids, labels


def acquire(protocol, protocol_path, out):
    import zstandard
    source = core.ROOT / "data/private/chess-distill-v1/source-prefix.csv.zst.part"
    first = json.loads((source.parent / "dataset.json").read_text())
    if core.digest(source) != first["acquisition"]["sha256"]:
        raise ValueError("retained source identity mismatch")
    games, boards = core.historical_exclusions(core.ROOT / "data/open/chess/lichess-real-seed-v1/manifest.json")
    ids, previous = set(), {}
    for name in ("chess-distill-v1", "chess-distill-v2", "chess-classifier-v3"):
        path = core.ROOT / "data/private" / name / "dataset.json"
        previous[name] = core.digest(path)
        for rows in json.loads(path.read_text())["splits"].values():
            for row in rows:
                games.add(row["game_id"])
                boards.add(core.board_key(row["fen"]))
                ids.add(row["id"])
    # Reconstruct the other role of every prior puzzle, never only its setup result.
    with source.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row["PuzzleId"] in ids:
                    boards.add(core.board_key(row["FEN"]))
                    ids.remove(row["PuzzleId"])
                if not ids:
                    break
    if ids:
        raise ValueError("prior source-board roles absent from retained prefix")
    counts = {name: protocol["splits"][name] for name in ("train", "development", "holdout")}
    with source.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as stream:
            splits, rejected = core.select_rows(csv.DictReader(stream), counts, protocol["splits"]["seed"], games, boards)
    dataset = {"schema": "chess.move-only-lm.dataset.v4", "protocol_sha256": core.digest(protocol_path),
               "source": first["acquisition"], "source_reused": True, "previous_manifests": previous,
               "exclusions": {"games": len(games), "board_keys": len(boards)},
               "selection_rejections": rejected, "splits": splits}
    core.save(out / "dataset.json", dataset)
    return dataset


def label(protocol, dataset, out):
    settings = protocol["teacher"]
    engine = core.ROOT / "data/private/chess-distill-v1/tools/stockfish/stockfish-windows-x86-64-universal.exe"
    if core.digest(engine) != settings["sha256"]:
        raise ValueError("teacher identity mismatch")
    if (out / "before-teacher-calls.json").exists():
        raise ValueError("refusing to replace an existing teacher attempt")
    teacher_source = {}
    for path in (Path(__file__), Path(core.__file__), Path(classifier.__file__)):
        copy = out / ("teacher-executed-" + path.name)
        shutil.copyfile(path, copy)
        teacher_source[copy.name] = core.digest(copy)
    core.save(out / "before-teacher-calls.json", {"dataset_sha256": core.digest(out / "dataset.json"),
              "protocol_sha256": dataset["protocol_sha256"], "source_sha256": teacher_source,
              "engine_sha256": core.digest(engine), "settings": settings})
    rows = [(split, row) for split, values in dataset["splits"].items() for row in values]
    labelled = {split: {} for split in dataset["splits"]}
    started, done = time.perf_counter(), 0
    with ProcessPoolExecutor(max_workers=settings["workers"]) as pool:
        futures = [pool.submit(classifier.label_batch, str(engine), settings, rows[i:i+256])
                   for i in range(0, len(rows), 256)]
        for future in as_completed(futures):
            for split, row in future.result():
                labelled[split][row["id"]] = row
                done += 1
            print(json.dumps({"phase": "teacher", "done": done, "total": len(rows)}), flush=True)
    result = {"schema": "chess.move-only-lm.labels.v4", "dataset_sha256": core.digest(out / "dataset.json"),
              "protocol_sha256": dataset["protocol_sha256"], "before_teacher_sha256": core.digest(out / "before-teacher-calls.json"),
              "engine": {"sha256": core.digest(engine), "settings": settings},
              "elapsed_seconds": time.perf_counter()-started,
              "splits": {split: [labelled[split][row["id"]] for row in values] for split, values in dataset["splits"].items()}}
    core.save(out / "labels.json", result)
    return result


def evaluate(model, tokenizer, rows, protocol, device, out, prefix):
    import torch
    size = protocol["generation"]["batch_size"]
    tokenizer.padding_side = "left"
    records, stopped = [], None
    started = time.perf_counter()
    model.eval()
    for offset in range(0, len(rows), size):
        batch = rows[offset:offset+size]
        if stopped:
            records.extend({"id": row["id"], "game_id": row["game_id"], "fen": row["fen"],
                            "teacher_move_uci": row["teacher_move_uci"], "legal": False, "match": False,
                            "move_uci": None, "error": "not_run_after_backend_failure"} for row in batch)
            continue
        try:
            inputs = tokenizer([prompt_for(row) for row in batch], return_tensors="pt", padding=True,
                               add_special_tokens=False).to(device)
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=protocol["generation"]["max_new_tokens"],
                                           do_sample=False, pad_token_id=tokenizer.pad_token_id,
                                           eos_token_id=tokenizer.eos_token_id)
            if not torch.is_tensor(generated) or generated.ndim != 2 or generated.shape[0] != len(batch) or generated.shape[1] < inputs["input_ids"].shape[1]:
                raise ValueError("generation batch shape mismatch")
            tokens = generated[:, inputs["input_ids"].shape[1]:].cpu().tolist()
            outputs = tokenizer.batch_decode(tokens, skip_special_tokens=True)
            if len(outputs) != len(batch):
                raise ValueError("decoded batch shape mismatch")
        except Exception as error:
            stopped = type(error).__name__
            records.extend({"id": row["id"], "game_id": row["game_id"], "fen": row["fen"],
                            "teacher_move_uci": row["teacher_move_uci"], "legal": False, "match": False,
                            "move_uci": None, "error": "backend_failure:" + stopped} for row in batch)
            continue
        for row, output, generated_ids in zip(batch, outputs, tokens):
            move = parse_action(output)
            legal = core.legal_action(row["fen"], move)
            records.append({"id": row["id"], "game_id": row["game_id"], "fen": row["fen"],
                            "teacher_move_uci": row["teacher_move_uci"], "raw_output": output,
                            "generated_token_ids": generated_ids, "move_uci": move,
                            "legal": legal, "match": legal and move == row["teacher_move_uci"]})
    result = {"count": len(rows), "accounted": len(records), "raw_parse_count": sum(r["move_uci"] is not None for r in records),
              "raw_legal_count": sum(r["legal"] for r in records), "raw_match_count": sum(r["match"] for r in records),
              "backend_failure_count": sum("error" in r for r in records), "backend_failure_stop": stopped,
              "elapsed_seconds": time.perf_counter()-started, "records": records}
    core.save(out / (prefix + ".json"), result)
    return result


def selection_key(step, result):
    return result["raw_match_count"], result["raw_legal_count"], -step


def validate_training_bindings(protocol, protocol_path, dataset, labels, out):
    if dataset["protocol_sha256"] != core.digest(protocol_path) or labels["protocol_sha256"] != core.digest(protocol_path):
        raise ValueError("dataset/label protocol binding mismatch")
    if labels["dataset_sha256"] != core.digest(out / "dataset.json"):
        raise ValueError("label dataset binding mismatch")
    if labels["engine"]["sha256"] != protocol["teacher"]["sha256"] or labels["engine"]["settings"] != protocol["teacher"]:
        raise ValueError("label teacher identity/settings mismatch")
    for split in ("train", "development", "holdout"):
        source_rows, label_rows = dataset["splits"][split], labels["splits"][split]
        if len(source_rows) != protocol["splits"][split] or len(label_rows) != len(source_rows):
            raise ValueError("label/source split count mismatch")
        for source, target in zip(source_rows, label_rows):
            if any(source[key] != target[key] for key in ("id", "game_id", "fen")):
                raise ValueError("label/source row identity mismatch")
            if not core.legal_action(target["fen"], target["teacher_move_uci"]):
                raise ValueError("illegal teacher label")


def train(protocol, protocol_path, out):
    import platform
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    base = core.ROOT / "data/private/chess-distill-v1/base-model"
    if core.digest(base / "model.safetensors") != protocol["base_weight_sha256"]:
        raise ValueError("base model identity mismatch")
    checkpoint_root = out / "checkpoints"
    if checkpoint_root.exists():
        raise ValueError("refusing to overwrite a retained training attempt")
    dataset = json.loads((out / "dataset.json").read_text())
    labels = json.loads((out / "labels.json").read_text())
    validate_training_bindings(protocol, protocol_path, dataset, labels, out)
    checkpoint_root.mkdir()
    source_hashes = {}
    for path in (Path(__file__), Path(core.__file__), Path(classifier.__file__), protocol_path):
        copy = out / ("executed-" + path.name)
        shutil.copyfile(path, copy)
        source_hashes[copy.name] = core.digest(copy)
    metadata_hashes = {p.name: core.digest(p) for p in base.iterdir() if p.is_file() and p.suffix in (".json", ".txt", ".md")}
    core.save(out / "before-model-calls.json", {"source_sha256": source_hashes, "base_metadata_sha256": metadata_hashes,
                                               "model_sha256": core.digest(base / "model.safetensors"),
                                               "labels_sha256": core.digest(out / "labels.json")})
    settings = protocol["training"]
    torch.set_num_threads(protocol["resource_policy"]["torch_cpu_threads"])
    torch.manual_seed(settings["seed"])
    rng = random.Random(settings["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    examples = [make_example(row, tokenizer) for row in labels["splits"]["train"]]
    dev_examples = [make_example(row, tokenizer) for row in labels["splits"]["development"]]
    model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, attn_implementation="sdpa").float().to(device)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    evaluations = {0: evaluate(model, tokenizer, labels["splits"]["development"], protocol, device, out, "base-development")}
    losses = {0: core.completion_nll(model, dev_examples, tokenizer.pad_token_id, device, 16)}
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings["learning_rate"], weight_decay=settings["weight_decay"])
    bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
    log, order = [], []
    started = time.perf_counter()
    model.train()
    for step in range(1, settings["steps"]+1):
        if len(order) < settings["batch_size"]:
            refill = list(range(len(examples)))
            rng.shuffle(refill)
            order.extend(refill)
        chosen, order = order[:settings["batch_size"]], order[settings["batch_size"]:]
        inputs = {k: v.to(device) for k, v in core.collate([examples[i] for i in chosen], tokenizer.pad_token_id, torch).items()}
        optimizer.zero_grad(set_to_none=True)
        precision = torch.autocast("cuda", dtype=torch.bfloat16) if bf16 else contextlib.nullcontext()
        with precision:
            loss = model(**inputs).loss
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), settings["gradient_clip"])
        optimizer.step()
        log.append({"step": step, "loss": float(loss.detach())})
        if step % 32 == 0:
            core.save(out / "training-log.json", log)
            print(json.dumps({"phase": "train", "step": step, "loss": log[-1]["loss"],
                              "seconds": round(time.perf_counter()-started, 2)}), flush=True)
        if step in settings["checkpoint_steps"]:
            directory = checkpoint_root / f"step-{step}"
            model.save_pretrained(directory, safe_serialization=True)
            tokenizer.save_pretrained(directory)
            evaluations[step] = evaluate(model, tokenizer, labels["splits"]["development"], protocol, device, out,
                                         f"step-{step}-development")
            losses[step] = core.completion_nll(model, dev_examples, tokenizer.pad_token_id, device, 16)
            model.train()
    seconds = time.perf_counter()-started
    core.save(out / "training-log.json", log)
    selected_step = max(evaluations, key=lambda step: selection_key(step, evaluations[step]))
    selected_dir = base if selected_step == 0 else checkpoint_root / f"step-{selected_step}"
    selection = {"selected_step": selected_step, "selected_weight_sha256": core.digest(selected_dir / "model.safetensors"),
                 "development_candidates": {str(k): {field: value for field, value in result.items() if field != "records"}
                                            for k, result in evaluations.items()}, "development_nll": losses,
                 "rule": protocol["selection"], "holdout_opened": False}
    core.save(out / "selection-before-holdout.json", selection)
    del model, optimizer
    if device == "cuda":
        torch.cuda.empty_cache()
    model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, attn_implementation="sdpa").float().to(device)
    baseline_holdout = evaluate(model, tokenizer, labels["splits"]["holdout"], protocol, device, out, "base-holdout")
    if selected_step == 0:
        selected_holdout = baseline_holdout
    else:
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
        model = AutoModelForCausalLM.from_pretrained(selected_dir, local_files_only=True, attn_implementation="sdpa").float().to(device)
        selected_holdout = evaluate(model, tokenizer, labels["splits"]["holdout"], protocol, device, out, "selected-holdout")
    receipt = {"schema": "chess.move-only-lm.receipt.v4", "protocol_sha256": core.digest(protocol_path),
               "dataset_sha256": core.digest(out / "dataset.json"), "labels_sha256": core.digest(out / "labels.json"),
               "model": {"source": protocol["base_model"], "revision": protocol["base_revision"],
                         "base_weight_sha256": protocol["base_weight_sha256"], "selected_step": selected_step,
                         "selected_weight_sha256": core.digest(selected_dir / "model.safetensors")},
               "source_sha256": source_hashes, "base_metadata_sha256": metadata_hashes,
               "training": {**settings, "encoded_positions": len(examples), "presentations": settings["steps"]*settings["batch_size"],
                            "elapsed_seconds_including_dev_checks": seconds, "development_nll": losses,
                            "log_sha256": core.digest(out / "training-log.json")},
               "selection_sha256": core.digest(out / "selection-before-holdout.json"),
               "evaluation": {"baseline": {"development": evaluations[0], "holdout": baseline_holdout},
                              "selected": {"development": evaluations[selected_step], "holdout": selected_holdout}},
               "runtime": {"device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
                           "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
                           "bfloat16_autocast": bf16, "python": platform.python_version(),
                           "torch": torch.__version__, "transformers": transformers.__version__},
               "promotion_policy": protocol["promotion_policy"], "task_change": protocol["generation"]["task_change"]}
    core.save(out / "receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("acquire", "label", "train"))
    parser.add_argument("--protocol", type=Path, default=core.ROOT / "research/stockfish-move-only-lm-protocol-v4.json")
    parser.add_argument("--out", type=Path, default=core.ROOT / "data/private/chess-move-only-lm-v4")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / {"acquire": "dataset.json", "label": "labels.json", "train": "checkpoints"}[args.phase]
    if target.exists():
        raise ValueError("refusing to overwrite a retained phase")
    if args.phase == "acquire":
        result = acquire(protocol, args.protocol, args.out)
        print(json.dumps({"splits": {k: len(v) for k, v in result["splits"].items()}}))
    elif args.phase == "label":
        dataset = json.loads((args.out / "dataset.json").read_text())
        if dataset["protocol_sha256"] != core.digest(args.protocol):
            raise ValueError("teacher phase protocol changed after dataset selection")
        result = label(protocol, dataset, args.out)
        print(json.dumps({"teacher_seconds": result["elapsed_seconds"]}))
    else:
        result = train(protocol, args.protocol, args.out)
        print(json.dumps({"selected_step": result["model"]["selected_step"], "runtime": result["runtime"]}))
