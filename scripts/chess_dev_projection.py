"""Build or check a deterministic development-only view of verified real source.

This performs source integrity and legal replay checks only. It makes no engine
or model calls and does not score, copy or display train/test positions or labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from chess_real_data import verify


def projection_bytes(data: Path) -> bytes:
    verification = verify(data)
    raw = (data / "manifest.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != verification["manifest_sha256"]:
        raise ValueError("source_manifest_changed_during_projection")
    manifest = json.loads(raw)
    if "items" not in manifest:
        raise ValueError("source_manifest_missing_items")
    # Fixed fields, not a copied manifest/item dictionary: source solution,
    # theme and rating labels never enter this model-facing source packet.
    items = [{
        "position_id": item["position_id"], "game_id": item["game_id"],
        "game_url": item["game_url"], "split": "dev",
        "source_fen": item["source_fen"], "setup_move": item["setup_move"],
        "fen": item["fen"], "provenance_kind": "real_public_game_derived_puzzle",
    } for item in manifest["items"] if item["split"] == "dev"]
    items.sort(key=lambda item: item["position_id"])
    if len(items) != 8 or len({item["game_id"] for item in items}) != 8:
        raise ValueError("expected_eight_distinct_development_games")
    value = {
        "schema": "chess-dev-source-projection/v1",
        "source_manifest_sha256": digest,
        "source_url": "https://database.lichess.org/lichess_db_puzzle.csv.zst",
        "license": "CC0-1.0",
        "source_file_hashes": {name: manifest["files"][name]["sha256"] for name in
                              ("source-page.html", "source-prefix.csv.zst.part", "sample.csv")},
        "source_split_counts": verification["split_counts"],
        "selected_split": "dev", "selected_count": len(items),
        "items": items,
        "boundaries": [
            "Verified real development source only; no synthetic replacement positions.",
            "The source FEN precedes the opponent setup move; fen is the resulting decision position.",
            "Solution, theme and rating labels are omitted; train/test items are omitted entirely.",
            "Source integrity and legal replay are not outcome scoring or explanation-quality evidence.",
            "The original eight test cases remain unscored; no claim of past model blinding is established here.",
            "A deterministic source projection grants no extra read, inference, acceptance or progress authority.",
        ],
    }
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded) > 16_384:
        raise ValueError("development_projection_exceeds_grounding_context_limit")
    return encoded


def create_projection(data: Path, output: Path) -> dict:
    encoded = projection_bytes(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encoded)
    return summary(encoded)


def check_projection(data: Path, projection: Path) -> dict:
    encoded = projection_bytes(data)
    if projection.read_bytes() != encoded:
        raise ValueError("development_projection_does_not_match_verified_source")
    return summary(encoded)


def summary(encoded: bytes) -> dict:
    return {"schema": "chess-dev-source-projection-check/v1", "passed": True,
            "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded),
            "development_positions": 8, "engine_calls": 0, "model_calls": 0,
            "test_outcomes_scored": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "check"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (create_projection if args.command == "create" else check_projection)(args.data, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
