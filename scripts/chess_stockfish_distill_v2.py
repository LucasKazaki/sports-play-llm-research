"""Separately versioned native-format experiment; v1 results stay unchanged."""
from __future__ import annotations
import argparse
import csv
import io
import json
import random
import shutil
from pathlib import Path

import chess_stockfish_distill as core

_parse_v1 = core.parse_action


def prompt_for(row):
    return f"P: {row['fen']:90}M:"


def target_for(row):
    pairs = list(row["candidates"])
    # Preserve pairing, with reproducible candidate ordering independent of model output.
    random.Random(row["id"]).shuffle(pairs)
    moves = " ".join(c["move_uci"] for c in pairs)
    scores = " ".join(f"#{c['mate']}" if c["mate"] is not None else str(round(c["score_cp"]/100, 2)) for c in pairs)
    return f" {moves:30}E: {scores:40}B: {row['teacher_move_uci']}\n"


def make_example(row, tokenizer):
    prefix = prompt_for(row)
    text = prefix + target_for(row) + tokenizer.eos_token
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = encoded["input_ids"]
    labels = []
    for token, (start, end) in zip(ids, encoded["offset_mapping"]):
        if start < len(prefix) < end:
            raise ValueError("token crosses generator/supervision boundary")
        labels.append(-100 if start < len(prefix) else token)
    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    if ids[:len(prefix_ids)] != prefix_ids or labels[:len(prefix_ids)] != [-100]*len(prefix_ids):
        raise ValueError("training prefix differs from inference prefix")
    if all(x == -100 for x in labels):
        raise ValueError("no completion labels")
    return ids, labels


def parse_action(completion):
    # M: is already in the prompt; preserve the raw completion separately.
    return _parse_v1(completion if completion.lstrip().startswith("M:") else "M:" + completion)


def reaccount(out):
    """Repair action accounting from retained text, with no generation or training."""
    receipt_path = out / "receipt.json"
    preserved = out / "receipt-before-action-parser-repair.json"
    if preserved.exists():
        raise ValueError("original receipt already preserved; do not repeat repair")
    receipt = json.loads(receipt_path.read_text())
    if core.digest(out / "checkpoint/model.safetensors") != receipt["model"]["checkpoint_sha256"]:
        raise ValueError("saved checkpoint identity changed")
    rows = 0
    for conditions in receipt["evaluation"].values():
        for result in conditions.values():
            if len(result["records"]) != result["count"]:
                raise ValueError("incomplete denominator")
            for record in result["records"]:
                move, fallback = parse_action(record["raw_output"])
                record.update(move_uci=move, used_candidate_fallback=fallback,
                              legal=core.legal_action(record["fen"], move))
                record["match"] = record["legal"] and move == record["teacher_move_uci"]
                rows += 1
            result.update(raw_legal_count=sum(r["legal"] for r in result["records"]),
                          top1_match_count=sum(r["match"] for r in result["records"]),
                          fallback_count=sum(r["used_candidate_fallback"] for r in result["records"]),
                          failures=sum(r["move_uci"] is None for r in result["records"]))
    shutil.copyfile(receipt_path, preserved)
    shutil.copyfile(Path(__file__), out / "executed-accounting.py")
    receipt["accounting_repair"] = {"reason": "M: marker was supplied in prompt, absent from raw completion fallback parsing",
                                     "original_receipt_sha256": core.digest(preserved),
                                     "implementation_sha256": core.digest(Path(__file__)),
                                     "rows_recomputed": rows, "model_calls": 0, "optimizer_updates": 0,
                                     "raw_outputs_changed": False}
    core.save(receipt_path, receipt)
    return receipt


def acquire(protocol, out, previous, protocol_path):
    import zstandard
    prior = json.loads((previous / "dataset.json").read_text())
    source = previous / "source-prefix.csv.zst.part"
    if core.digest(source) != prior["acquisition"]["sha256"]:
        raise ValueError("previous retained source hash mismatch")
    games, positions = core.historical_exclusions(core.ROOT / "data/open/chess/lichess-real-seed-v1/manifest.json")
    for rows in prior["splits"].values():
        for row in rows:
            games.add(row["game_id"])
            positions.add(core.board_key(row["fen"]))
    counts = {k: protocol["splits"][k] for k in ("train", "development", "holdout")}
    with source.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as text:
            splits, rejected = core.select_rows(csv.DictReader(text), counts, protocol["splits"]["seed"], games, positions)
    shutil.copyfile(source, out / source.name)
    result = {"schema": "chess.stockfish-distillation.dataset.v2", "acquisition": prior["acquisition"],
              "source_reused": True, "previous_dataset_sha256": core.digest(previous / "dataset.json"),
              "protocol_sha256": core.digest(protocol_path),
              "rights": protocol["source_rights"], "exclusions": {"games": len(games), "board_keys": len(positions)},
              "selection_rejections": rejected, "splits": splits}
    core.save(out / "dataset.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("acquire", "label", "train", "reaccount"))
    parser.add_argument("--out", type=Path, default=core.ROOT / "data/private/chess-distill-v2")
    parser.add_argument("--previous", type=Path, default=core.ROOT / "data/private/chess-distill-v1")
    parser.add_argument("--protocol", type=Path, default=core.ROOT / "research/stockfish-distillation-protocol-v2.json")
    args = parser.parse_args(argv)
    protocol = json.loads(args.protocol.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    if args.phase == "reaccount":
        result = reaccount(args.out)
        print(json.dumps(result["accounting_repair"]))
        return
    # Explicit narrow dependency injection preserves the original v1 implementation.
    core.prompt_for, core.target_for, core.make_example = prompt_for, target_for, make_example
    core.parse_action = parse_action
    if args.phase == "acquire":
        if (args.out / "dataset.json").exists():
            raise ValueError("refusing to replace frozen dataset")
        result = acquire(protocol, args.out, args.previous, args.protocol)
        print(json.dumps({"splits": {k: len(v) for k, v in result["splits"].items()}}), flush=True)
    elif args.phase == "label":
        if (args.out / "labels.json").exists():
            raise ValueError("refusing to replace teacher labels")
        core.label(protocol, json.loads((args.out / "dataset.json").read_text()),
                   args.previous / "tools/stockfish/stockfish-windows-x86-64-universal.exe", args.out)
    else:
        if (args.out / "checkpoint").exists():
            raise ValueError("refusing to retrain existing checkpoint")
        # Retain the exact source bytes before any baseline, optimizer or holdout call.
        shutil.copyfile(Path(__file__), args.out / "executed-wrapper.py")
        shutil.copyfile(Path(core.__file__), args.out / "executed-core.py")
        result = core.train_and_evaluate(protocol, json.loads((args.out / "labels.json").read_text()),
                                         args.out, args.previous / "base-model", args.protocol)
        result["schema"] = "chess.stockfish-distillation.v2"
        result["implementation"] = {"wrapper_sha256": core.digest(args.out / "executed-wrapper.py"),
                                    "core_sha256": core.digest(args.out / "executed-core.py")}
        result["v1_holdout_used"] = False
        core.save(args.out / "receipt.json", result)
        print(json.dumps({"trained": True, "checkpoint_sha256": result["model"]["checkpoint_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
