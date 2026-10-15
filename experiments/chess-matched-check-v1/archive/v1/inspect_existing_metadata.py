"""Workspace-only reconstruction of already-spent evidence; no new cohort search."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time

import chess
import chess.pgn
import pyarrow
import pyarrow.parquet as pq
import zstandard

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT / "work/repos/sports-play-llm-research"
GAME_ID = re.compile(r"([A-Za-z0-9]{8})(?:/(?:white|black))?(?:#[0-9]+)?")


def bind(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read(name):
    return json.loads((REPO / name).read_text(encoding="utf-8"))


def canonical_game_id(native):
    match = GAME_ID.fullmatch(native) if type(native) is str else None
    if match is None:
        raise ValueError("Malformed existing GameId")
    return match.group(1)


def valid_board(fen):
    board = chess.Board(fen)
    if board.chess960 or not board.is_valid():
        raise ValueError("Invalid existing board")
    return board


def key(fen):
    return " ".join(valid_board(fen).fen().split()[:4])


def save_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    started = time.monotonic()
    protocol_name = "experiments/chess-fact-sft-v1/protocol.json"
    protocol = read(protocol_name)
    required = dict(protocol["intake"]["prior_exclusions"]["required_files_sha256"])
    additions = [
        protocol_name, "scripts/chess_fact_sft_intake.py", "scripts/chess_board_fact_core.py",
        "scripts/chess_board_fact_diagnostic.py", "scripts/chess_fact_sft_common.py",
        "data/private/chess-fact-sft-v1/acquisition-v2.json",
        "data/private/chess-fact-sft-v1/cohort/frozen-data.json",
        "data/private/chess-fact-sft-v1/cohort/dataset.json",
        "data/private/chess-fact-sft-v1/cohort/exclusion-registry.json",
        "data/private/chess-fact-sft-v1/cohort/train-inputs.json",
        "data/private/chess-fact-sft-v1/cohort/dev-inputs.json",
        "data/private/chess-fact-sft-v1/cohort/holdout-inputs.json",
        "data/open/chess/autonomy-broker-derived-20260919-v1/manifest.json",
        "data/open/chess/autonomy-broker-derived-20260919-v1/broker-receipt.json",
        "data/open/chess/autonomy-broker-20260919-v1/acquisition-receipt.json",
        "experiments/gotham-illustrative-v1/source-ledger.json",
        "experiments/gotham-constructed-middlegame-v1/source-reference.json",
        "experiments/gotham-constructed-middlegame-v1/move-inputs.json",
        "experiments/gotham-constructed-middlegame-v1/fact-inputs.json",
        "experiments/gotham-constructed-middlegame-v1/protocol.json",
        "experiments/gotham-constructed-middlegame-v1/freeze-manifest.json",
        "data/private/chess-fact-sft-v1/native-run-v3/checkpoint-512/manifest.json",
        "data/private/chess-fact-sft-v1/native-run-v3/checkpoint-512/adapter/adapter_config.json",
        "data/private/chess-fact-sft-v1/models/base/config.json",
        "data/private/chess-fact-sft-v1/models/base/generation_config.json",
        "data/private/chess-fact-sft-v1/models/base/tokenizer_config.json",
        "data/private/chess-fact-sft-v1/models/base/tokenizer.json",
        "data/private/chess-fact-sft-v1/models/base/merges.txt",
        "data/private/chess-fact-sft-v1/models/base/vocab.json",
    ]
    source = protocol["acquisition"]["source_path"]
    paths = sorted(set(required) | set(additions) | {source})
    before = {name: bind(REPO / name) for name in paths}
    for name, expected in required.items():
        assert before[name]["sha256"] == expected, name
    assert before[source] == {"bytes": protocol["acquisition"]["source_bytes"],
                              "sha256": protocol["acquisition"]["source_sha256"]}
    frozen = read("data/private/chess-fact-sft-v1/cohort/frozen-data.json")
    for name in ("dataset.json", "exclusion-registry.json", "train-inputs.json", "dev-inputs.json", "holdout-inputs.json"):
        full = "data/private/chess-fact-sft-v1/cohort/" + name
        assert before[full]["sha256"] == frozen["files_sha256"][name], name

    games, boards, puzzle_rows = set(), set(), {}
    stages = {}

    def stage(name, extra=None):
        stages[name] = {"games": len(games), "board_keys": len(boards), **(extra or {})}

    seed = read("data/open/chess/lichess-real-seed-v1/manifest.json")
    for row in seed["items"]:
        games.add(canonical_game_id(row["game_id"]))
        boards.add(key(row["fen"]))
        for ply in row.get("legal_replay", []):
            boards.update((key(ply["before"]), key(ply["after"])))
    stage("historical_seed")
    old_names = ("chess-distill-v1", "chess-distill-v2", "chess-classifier-v3", "chess-move-only-lm-v4")
    for name in old_names:
        data = read("data/private/" + name + "/dataset.json")
        for rows in data["splits"].values():
            for row in rows:
                assert row["id"] not in puzzle_rows, "Prior duplicate puzzle identity"
                puzzle_rows[row["id"]] = row
                games.add(canonical_game_id(row["game_id"]))
                boards.add(key(row["fen"]))

    missing = set(puzzle_rows)
    source_prefix = REPO / "data/private/chess-distill-v1/source-prefix.csv.zst.part"
    prior_rows_scanned = 0
    with source_prefix.open("rb") as raw:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                prior_rows_scanned += 1
                if row["PuzzleId"] not in missing:
                    continue
                board = valid_board(row["FEN"])
                setup = chess.Move.from_uci(row["Moves"].split(maxsplit=1)[0])
                assert setup in board.legal_moves
                boards.add(key(board.fen()))
                board.push(setup)
                assert board.fen() == puzzle_rows[row["PuzzleId"]]["fen"]
                missing.remove(row["PuzzleId"])
                if not missing:
                    break
    assert not missing
    stage("reconstructed_historical_and_v1_to_v4", {"registered_puzzle_rows": len(puzzle_rows), "retained_prefix_rows_replayed": prior_rows_scanned})
    assert {k: stages["reconstructed_historical_and_v1_to_v4"][k] for k in ("games", "board_keys")} == {"games": 21688, "board_keys": 43474}

    fact_rows = read("data/private/chess-board-facts-v1/dataset.json")["rows"]
    for row in fact_rows:
        board = valid_board(row["source_before_fen"])
        setup = chess.Move.from_uci(row["setup_uci"])
        assert setup in board.legal_moves
        boards.add(key(board.fen()))
        board.push(setup)
        assert board.fen() == row["fen"]
        games.add(canonical_game_id(row["game_id"]))
        boards.add(key(row["fen"]))
    stage("with_spent_fact_panel")

    rollout_games = rollout_plies = 0
    with (REPO / "experiments/chess-rollout-stress-v1/games.pgn").open(encoding="utf-8") as stream:
        while (game := chess.pgn.read_game(stream)) is not None:
            assert not game.errors
            board = valid_board(game.board().fen())
            boards.add(key(board.fen()))
            for move in game.mainline_moves():
                assert move in board.legal_moves
                board.push(move)
                boards.add(key(board.fen()))
                rollout_plies += 1
            rollout_games += 1
    assert rollout_games == 64 and rollout_plies == 4784
    video = read("experiments/gotham-illustrative-v1/fen-inputs.json")["positions"]
    for row in video:
        boards.add(key(row["pre_move_fen"]))
    original_registry = read("data/private/chess-fact-sft-v1/cohort/exclusion-registry.json")
    assert games == set(original_registry["games"])
    assert boards == set(original_registry["board_keys"])
    stage("exact_primary_registry_reproduced", {"rollout_games": rollout_games, "rollout_plies": rollout_plies, "illustrative_preboards": len(video)})

    derived = read("data/open/chess/autonomy-broker-derived-20260919-v1/manifest.json")
    before_extra = (len(games), len(boards))
    for row in derived["items"]:
        games.add(canonical_game_id(row["game_id"]))
        boards.add(key(row["fen"]))
        for ply in row.get("legal_replay", []):
            boards.update((key(ply["before"]), key(ply["after"])))
    stage("legacy_derived_manifest_union", {"manifest_items": len(derived["items"]), "new_games": len(games)-before_extra[0], "new_board_keys":len(boards)-before_extra[1]})

    primary = read("data/private/chess-fact-sft-v1/cohort/dataset.json")
    primary_count = 0
    all_fact_rows = list(fact_rows)
    for split in ("train", "dev", "holdout"):
        rows = primary["splits"][split]
        inputs = read("data/private/chess-fact-sft-v1/cohort/" + split + "-inputs.json")["rows"]
        assert [{k: row[k] for k in ("case_id", "fen", "selected_uci")} for row in rows] == inputs
        for row in rows:
            board = valid_board(row["source_before_fen"])
            setup = chess.Move.from_uci(row["setup_uci"])
            assert setup in board.legal_moves
            boards.add(key(board.fen()))
            board.push(setup)
            assert board.fen() == row["fen"]
            assert canonical_game_id(row["native_game_id"]) == row["game_id"]
            games.add(row["game_id"])
            boards.add(key(board.fen()))
            primary_count += 1
        all_fact_rows.extend(rows)
    assert primary_count == 8576
    stage("with_all_primary_games_and_both_source_roles", {"primary_positions": primary_count})
    for row in all_fact_rows:
        board = valid_board(row["fen"])
        move = chess.Move.from_uci(row["selected_uci"])
        assert move in board.legal_moves
        board.push(move)
        boards.add(key(board.fen()))
    stage("with_all_known_fact_selected_successors", {"selected_moves_replayed":len(all_fact_rows)})

    ledger = read("experiments/gotham-illustrative-v1/source-ledger.json")
    video_history_plies = 0
    for scene in ledger["scenes"]:
        board = chess.Board()
        boards.add(key(board.fen()))
        for san in scene["history_san"].split():
            board.push_san(san)
            boards.add(key(board.fen()))
            video_history_plies += 1
        assert board.fen() == scene["pre_move_fen"]
        # Existing evaluator observation is used solely to mark a spent board.
        # It never participates in new pairing, prompts or model generation.
        move = chess.Move.from_uci(scene["next_displayed_move_evaluator_only"]["next_displayed_move_uci"])
        assert move in board.legal_moves
        board.push(move)
        boards.add(key(board.fen()))
    stage("with_known_video_histories_and_displayed_successors", {"history_plies":video_history_plies,"displayed_successors":len(ledger["scenes"])})

    constructed = read("experiments/gotham-constructed-middlegame-v1/move-inputs.json")["positions"]
    facts = read("experiments/gotham-constructed-middlegame-v1/fact-inputs.json")["positions"]
    for row in constructed:
        boards.add(key(row["fen"]))
    for row in facts:
        board = valid_board(row["fen"])
        move = chess.Move.from_uci(row["selected_uci"])
        assert move in board.legal_moves
        boards.add(key(board.fen()))
        board.push(move)
        boards.add(key(board.fen()))
    stage("with_known_constructed_board_and_supplied_fact_successor", {"constructed_preboards":len(constructed),"given_moves":len(facts)})

    metadata = pq.ParquetFile(REPO / source)
    source_info = {
        "rows": metadata.metadata.num_rows, "row_groups": metadata.metadata.num_row_groups,
        "columns": metadata.schema.names,
        "row_group_rows": [metadata.metadata.row_group(i).num_rows for i in range(metadata.metadata.num_row_groups)],
        "field_types": {field.name:str(field.type) for field in metadata.schema_arrow},
        "new_source_rows_read": 0, "new_pairs_searched": 0, "new_cohort_rows_selected": 0,
    }
    registry = {
        "schema":"chess.matched-check.known-history-registry.metadata.v1",
        "status":"Existing evidence reconstruction only; no new cohort selected",
        "games":sorted(games), "board_keys":sorted(boards), "stages":stages,
        "source_bindings_before":before,
        "limitations":[
            "Known-history disjointness only; unknown upstream pretraining and original Gotham game identities remain unresolved.",
            "Current active illustration outputs were not read. Only immutable known inputs and their rule-constructible supplied-move successors were added.",
            "The existing source answer tail is never used: old prefix replay reads only the first setup token of already registered puzzle IDs.",
        ],
    }
    after = {name:bind(REPO / name) for name in paths}
    assert before == after
    save_new(HERE / "known-history-exclusions.json", registry)
    report = {
        "schema":"chess.matched-check.source-exclusion-metadata.v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"PASS: existing exclusions reconstructed and bound; no new cohort or model call",
        "source":protocol["acquisition"], "parquet_metadata_only":source_info,
        "stages":stages, "known_registry":bind(HERE / "known-history-exclusions.json"),
        "file_bindings_before":before, "file_bindings_after":after,
        "runtime":{"python":sys.version,"interpreter":str(Path(sys.executable).resolve()),
                   "chess":chess.__version__,"pyarrow":pyarrow.__version__,"zstandard":zstandard.__version__,
                   "chess_source":bind(Path(chess.__file__)),"pgn_source":bind(Path(chess.pgn.__file__))},
        "inspector":bind(Path(__file__)), "seconds":time.monotonic()-started,
        "calls":{"new_source_data_row_reads":0,"new_pair_enumerations":0,"new_cohort_selection":0,
                 "pretrained_weight_loads":0,"pretrained_forwards":0,"GPU":0,"engine":0,"network":0},
    }
    save_new(HERE / "source-and-exclusion-metadata.json", report)
    print(json.dumps({k:report[k] for k in ("status","parquet_metadata_only","stages","known_registry","seconds","calls")},indent=2))


if __name__ == "__main__":
    main()
