"""Frozen, source-bound immediate-fact SFT intake; no model or engine calls."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil

import chess
import chess.pgn
import chess_board_fact_core as core
import chess_board_fact_diagnostic as historical

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SHA256 = "56602640605f890479115f30f822de027ebe702aafd5fff8a561d43f9838e765"
GAME_ID = re.compile(r"([A-Za-z0-9]{8})(?:/(?:white|black))?(?:#[0-9]+)?")
SPLITS = ("train", "dev", "holdout")
PRIOR_SOURCE = "data/private/chess-distill-v1/source-prefix.csv.zst.part"
FACT_DATA = "data/private/chess-board-facts-v1/dataset.json"
ROLLOUT = "experiments/chess-rollout-stress-v1/games.pgn"
VIDEO = "experiments/gotham-illustrative-v1/fen-inputs.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_game_id(native):
    match = GAME_ID.fullmatch(native) if type(native) is str else None
    if match is None:
        raise ValueError("malformed native GameId")
    return match.group(1)


def board_key(fen):
    return " ".join(chess.Board(fen).fen().split()[:4])


def valid_board(fen):
    board = chess.Board(fen)
    if type(board) is not chess.Board or board.chess960 or not board.is_valid():
        raise ValueError("valid orthodox board required")
    return board


def load_protocol(path):
    if sha(path) != PROTOCOL_SHA256:
        raise ValueError("frozen fact-SFT protocol changed")
    protocol = read(path)
    if protocol["schema"] != "chess.native-fact-sft.protocol.v1":
        raise ValueError("unsupported fact-SFT protocol")
    if (protocol["inputs"]["schema"] != core.SCHEMA
            or protocol["inputs"]["instruction_exact"] != core.INSTRUCTION
            or sha(Path(core.__file__)) != protocol["inputs"]["core_source_sha256"]):
        raise ValueError("frozen fact core changed")
    return protocol


def exclusion_registry(repo, protocol):
    required = protocol["intake"]["prior_exclusions"]["required_files_sha256"]
    for name, expected in required.items():
        if sha(repo / name) != expected:
            raise ValueError("prior exclusion artifact changed: " + name)
    games, boards, previous = historical.prior_exclusions(repo, repo / PRIOR_SOURCE)
    base = {"games": len(games), "board_keys": len(boards)}
    if base != protocol["intake"]["prior_exclusions"]["expected_prior_base_crosscheck"]:
        raise ValueError("reconstructed prior base counts disagree")
    stages = {"reconstructed_historical_and_v1_to_v4": dict(base)}
    spent = read(repo / FACT_DATA)["rows"]
    if len(spent) != 16:
        raise ValueError("expected sixteen spent fact games")
    for row in spent:
        before = valid_board(row["source_before_fen"])
        setup = chess.Move.from_uci(row["setup_uci"])
        if setup not in before.legal_moves:
            raise ValueError("illegal spent fact setup")
        boards.add(board_key(before.fen()))
        before.push(setup)
        if before.fen() != row["fen"]:
            raise ValueError("spent fact role disagreement")
        games.add(canonical_game_id(row["game_id"]))
        boards.add(board_key(row["fen"]))
    stages["with_spent_fact_panel"] = {"games": len(games), "board_keys": len(boards)}
    count, plies = 0, 0
    with (repo / ROLLOUT).open(encoding="utf-8") as stream:
        while (game := chess.pgn.read_game(stream)) is not None:
            if game.errors:
                raise ValueError("invalid retained rollout PGN")
            board = game.board()
            valid_board(board.fen())
            if type(board) is not chess.Board or board.chess960:
                raise ValueError("nonorthodox retained rollout")
            boards.add(board_key(board.fen()))
            for move in game.mainline_moves():
                if move not in board.legal_moves:
                    raise ValueError("illegal retained rollout move")
                board.push(move)
                valid_board(board.fen())
                boards.add(board_key(board.fen()))
                plies += 1
            count += 1
    if count != 64:
        raise ValueError("expected sixty-four retained rollout games")
    video = read(repo / VIDEO)["positions"]
    if len(video) != 3:
        raise ValueError("expected three illustrative video boards")
    for row in video:
        boards.add(board_key(valid_board(row["pre_move_fen"]).fen()))
    stages["all_spent_union"] = {"games": len(games), "board_keys": len(boards)}
    registry = {"schema": "chess.fact-sft.exclusions.v1", "required_files_sha256": required,
                "reconstructed_manifest_sha256": previous, "stages": stages,
                "rollout_games": count, "rollout_plies": plies,
                "video_boards": len(video), "games": sorted(games), "board_keys": sorted(boards)}
    return games, boards, registry


def parquet_rows(path):
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    ordinal = 0
    for group in range(parquet.metadata.num_row_groups):
        in_group = 0
        for batch in parquet.iter_batches(batch_size=4096, columns=["PuzzleId", "GameId", "FEN", "Moves"],
                                         row_groups=[group], use_threads=False):
            for row in batch.to_pylist():
                location = {"source_ordinal": ordinal, "row_group": group, "row_in_group": in_group}
                yield location, row
                ordinal += 1
                in_group += 1


def split_for(game_id, seed):
    number = int.from_bytes(hashlib.sha256(f"{seed}:{game_id}".encode()).digest(), "big") % 10
    return "train" if number < 8 else "dev" if number == 8 else "holdout"


def class_coverage(labels):
    bins = {}
    for field in core.FIELDS:
        classes = [False, True, "unknown"] if field in core.BOOL_FIELDS else core.SCHEMA["properties"][field]["enum"]
        bins[field] = {str(v).lower() if type(v) is bool else "null" if v is None else v: 0 for v in classes}
    for row in labels:
        for field, value in row["expected"].items():
            key = str(value).lower() if type(value) is bool else "null" if value is None else value
            bins[field][key] += 1
    return bins


def select_rows(rows, counts, seed, excluded_games, excluded_boards, trace=None):
    games, boards = set(excluded_games), set(excluded_boards)
    metadata = {s: [] for s in SPLITS}
    inputs = {s: [] for s in SPLITS}
    labels = {s: [] for s in SPLITS}
    rejections = Counter(invalid=0, excluded_or_duplicate=0, bucket_full=0)
    seen_ids, scanned, last_location = set(), 0, None
    for location, row in rows:
        scanned += 1
        last_location = location
        def record(outcome, split=None):
            if trace is not None:
                trace({**location, "outcome": outcome, **({"split": split} if split else {})})
        try:
            game_id = canonical_game_id(row["GameId"])
            puzzle_id = row["PuzzleId"]
            if type(puzzle_id) is not str or re.fullmatch(r"[A-Za-z0-9]+", puzzle_id) is None:
                raise ValueError("malformed puzzle identity")
            board = valid_board(row["FEN"])
            moves = row["Moves"]
            if type(moves) is not str:
                raise ValueError("nonstring setup source")
            # Only the first setup token has any role here. Never parse an answer tail.
            setup = chess.Move.from_uci(moves.split(maxsplit=1)[0])
            if setup not in board.legal_moves:
                raise ValueError("illegal source setup")
            before, before_key = board.fen(), board_key(board.fen())
            board.push(setup)
            if not board.is_valid() or board.is_game_over():
                raise ValueError("invalid or terminal setup-after board")
            after_key = board_key(board.fen())
        except (ValueError, KeyError, IndexError, TypeError):
            rejections["invalid"] += 1
            record("invalid")
            continue
        if game_id in games or before_key in boards or after_key in boards:
            rejections["excluded_or_duplicate"] += 1
            record("excluded_or_duplicate")
            continue
        split = split_for(game_id, seed)
        if len(inputs[split]) == counts[split]:
            rejections["bucket_full"] += 1
            record("bucket_full", split)
            continue
        if puzzle_id in seen_ids:
            raise ValueError("accepted puzzle identity repeated")
        legal = sorted(move.uci() for move in board.legal_moves)
        move_hash = hashlib.sha256(f"move:{seed}:{game_id}".encode()).hexdigest()
        index = int(move_hash, 16) % len(legal)
        selected = legal[index]
        expected = core.expected_facts(board.fen(), selected)
        if expected != core.independent_facts(board.fen(), selected):
            record("oracle_disagreement", split)
            raise ValueError("independent fact oracles disagree")
        core.parse_facts(json.dumps(expected))
        case_id = "fact-sft-" + puzzle_id
        inputs[split].append({"case_id": case_id, "fen": board.fen(), "selected_uci": selected})
        labels[split].append({"case_id": case_id, "expected": expected})
        metadata[split].append({"case_id": case_id, "puzzle_id": puzzle_id, "game_id": game_id,
                                "native_game_id": row["GameId"], "source_url": "https://lichess.org/" + game_id,
                                **location, "source_before_fen": before, "setup_uci": setup.uci(),
                                "fen": board.fen(), "selected_uci": selected, "legal_move_count": len(legal),
                                "selected_index": index, "move_selection_sha256": move_hash})
        games.add(game_id)
        boards.update((before_key, after_key))
        seen_ids.add(puzzle_id)
        record("accepted", split)
        if all(len(inputs[s]) == counts[s] for s in SPLITS):
            break
    missing = {s: counts[s] - len(inputs[s]) for s in SPLITS if len(inputs[s]) != counts[s]}
    if missing:
        raise ValueError("pinned source did not fill frozen quotas: " + repr(missing))
    return {"metadata": metadata, "inputs": inputs, "labels": labels,
            "coverage": {s: class_coverage(labels[s]) for s in SPLITS},
            "source_rows_scanned": scanned, "last_source_location": last_location,
            "rejections": dict(rejections)}


def freeze(repo, protocol_path, out):
    repo, protocol_path, out = Path(repo), Path(protocol_path), Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("refusing to overwrite an existing cohort or attempt")
    protocol = load_protocol(protocol_path)
    acquisition = protocol["acquisition"]
    if sha(repo / acquisition["amendment"]) != acquisition["amendment_sha256"]:
        raise ValueError("source acquisition amendment changed")
    source = repo / acquisition["source_path"]
    if source.stat().st_size != acquisition["source_bytes"] or sha(source) != acquisition["source_sha256"]:
        raise ValueError("pinned Parquet source changed")
    games, boards, registry = exclusion_registry(repo, protocol)
    out.mkdir(parents=True)
    (out / "selection-sources").mkdir()
    shutil.copyfile(protocol_path, out / "protocol.json")
    source_hashes = {}
    for path in (Path(__file__), Path(core.__file__), Path(historical.__file__)):
        destination = out / "selection-sources" / path.name
        shutil.copyfile(path, destination)
        source_hashes[destination.relative_to(out).as_posix()] = sha(destination)
    save_new(out / "exclusion-registry.json", registry)
    save_new(out / "before-selection.json", {"schema": "chess.fact-sft.before-selection.v1",
             "protocol_sha256": PROTOCOL_SHA256, "source_sha256": acquisition["source_sha256"],
             "acquisition_sha256": acquisition["amendment_sha256"],
             "exclusion_registry_sha256": sha(out / "exclusion-registry.json"),
             "selection_source_sha256": source_hashes, "model_calls": 0})
    try:
        with (out / "selection-trace.jsonl").open("x", encoding="utf-8", newline="\n") as trace:
            selected = select_rows(parquet_rows(source), protocol["intake"]["split_counts"],
                                   protocol["intake"]["seed"], games, boards,
                                   lambda event: trace.write(json.dumps(event, sort_keys=True) + "\n"))
        if sha(source) != acquisition["source_sha256"]:
            raise ValueError("Parquet source changed during selection")
        for name, expected in registry["required_files_sha256"].items():
            if sha(repo / name) != expected:
                raise ValueError("exclusion source changed during selection: " + name)
        if sha(protocol_path) != PROTOCOL_SHA256 or any(sha(out / name) != expected for name, expected in source_hashes.items()):
            raise ValueError("selection snapshot changed")
    except Exception as error:
        save_new(out / "selection-failed.json", {"type": type(error).__name__, "error": str(error),
                                               "model_calls": 0, "retry_permitted": False})
        raise
    for split in SPLITS:
        save_new(out / (split + "-inputs.json"), {"schema": "chess.fact-sft.inputs.v1", "rows": selected["inputs"][split]})
        save_new(out / (split + "-labels.json"), {"schema": "chess.fact-sft.labels.v1", "rows": selected["labels"][split]})
    dataset = {"schema": "chess.fact-sft.dataset.v1", "protocol_sha256": PROTOCOL_SHA256,
               "source": acquisition, "seed": protocol["intake"]["seed"],
               "split_counts": protocol["intake"]["split_counts"], "splits": selected["metadata"],
               "coverage": selected["coverage"], "selection_rejections": selected["rejections"],
               "source_rows_scanned": selected["source_rows_scanned"], "last_source_location": selected["last_source_location"],
               "exclusion_registry_sha256": sha(out / "exclusion-registry.json"), "python_chess": chess.__version__,
               "model_calls": 0, "limits": ["Deterministic facts, not commentary or move-strength supervision",
                   "Game/board exclusion cannot establish independence from unknown upstream pretraining",
                   "No rarity rebalancing or replacement after outcomes"]}
    save_new(out / "dataset.json", dataset)
    frozen = {"schema": "chess.fact-sft.frozen-data.v1", "protocol_sha256": PROTOCOL_SHA256,
              "files_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
              "split_counts": protocol["intake"]["split_counts"], "model_calls": 0}
    save_new(out / "frozen-data.json", frozen)
    return frozen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--protocol", type=Path, default=ROOT / "experiments/chess-fact-sft-v1/protocol.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = freeze(args.repo, args.protocol, args.out)
    print(json.dumps({"split_counts": result["split_counts"], "frozen_sha256": sha(args.out / "frozen-data.json"), "model_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
