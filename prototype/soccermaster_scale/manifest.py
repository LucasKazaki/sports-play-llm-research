"""Build and verify a private, game-held-out SoccerNet experiment manifest."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2

from .taxonomy import CLASS_NAMES, SOCCERNET_TO_CLASS


SCHEMA_VERSION = "playground-soccermaster-scale-manifest-v1"
EXAMPLE_SCHEMA_VERSION = "playground-soccermaster-scale-example-v1"
RECEIPT_SCHEMA_VERSION = "playground-soccermaster-scale-corpus-receipt-v1"
ACQUISITION_SCHEMA_VERSION = "playground-soccernet-acquisition-receipt-v1"
HALF_FILES = ("1_224p.mkv", "2_224p.mkv")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_id(*parts: object, length: int = 20) -> str:
    joined = "\x1f".join(str(part).replace("\\", "/") for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as sink:
        for row in rows:
            sink.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _require_private(path: Path) -> Path:
    resolved = path.resolve()
    parts = [part.lower() for part in resolved.parts]
    if not any(parts[index:index + 2] == ["data", "private"] for index in range(len(parts) - 1)):
        raise ValueError("SoccerNet corpus and manifest must remain below data/private")
    return resolved


def _video_metadata(path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open SoccerNet half: {path.name}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok, first = cap.read()
    cap.release()
    if not ok or first is None or frame_count < 1 or fps <= 0 or width < 1 or height < 1:
        raise RuntimeError(f"SoccerNet half failed decode/probe: {path.name}")
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "frame_count": frame_count,
        "fps": fps,
        "duration_s": frame_count / fps,
        "width": width,
        "height": height,
        "first_frame_decoded": True,
    }


def _visible_events(labels: dict[str, Any], half: int) -> list[dict[str, Any]]:
    raw = labels.get("annotations")
    if not isinstance(raw, list):
        raise ValueError("Labels-v2.json is missing annotations")
    prefix = f"{half} - "
    events: list[dict[str, Any]] = []
    for item in raw:
        if (
            isinstance(item, dict)
            and str(item.get("gameTime", "")).startswith(prefix)
            and item.get("visibility") == "visible"
            and item.get("label") in SOCCERNET_TO_CLASS
        ):
            events.append({
                "position_s": float(item["position"]) / 1000.0,
                "source_label": str(item["label"]),
                "class_name": SOCCERNET_TO_CLASS[str(item["label"])],
                "team": str(item.get("team", "not applicable")),
            })
    return sorted(events, key=lambda item: (item["position_s"], item["source_label"]))


def _event_examples(
    *, split: str, game_id: str, half: int, duration_s: float,
    video_relative_path: str, events: list[dict[str, Any]],
    window_s: float, ambiguity_radius_s: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        position = event["position_s"]
        start_s = max(0.0, min(position - window_s / 2.0, max(0.0, duration_s - window_s)))
        end_s = min(duration_s, start_s + window_s)
        nearby = sorted({
            candidate["class_name"] for candidate in events
            if candidate is not event and abs(candidate["position_s"] - position) <= ambiguity_radius_s
        })
        conflicting = sorted(set(nearby) - {event["class_name"]})
        example_id = "soc-" + stable_id(game_id, half, round(position, 3), event["source_label"])
        rows.append({
            "schema_version": EXAMPLE_SCHEMA_VERSION,
            "example_id": example_id,
            "split": split,
            "game_id": game_id,
            "source_half": half,
            "video_relative_path": video_relative_path,
            "window_start_s": start_s,
            "window_end_s": end_s,
            "candidate_time_s": position,
            "ground_truth": {
                "class_name": event["class_name"],
                "source_label": event["source_label"],
                "team": event["team"],
                "visibility": "visible",
                "nearby_classes": nearby,
                "single_label_eligible": not conflicting,
            },
            "sampling_origin": "SoccerNet-v2 visible event annotation; label withheld from visual model input",
        })
    return rows


def _background_examples(
    *, split: str, game_id: str, half: int, duration_s: float,
    video_relative_path: str, events: list[dict[str, Any]], window_s: float,
    stride_s: float, exclusion_radius_s: float, maximum: int,
) -> list[dict[str, Any]]:
    positions = [item["position_s"] for item in events]
    candidates: list[float] = []
    center = window_s / 2.0
    while center <= duration_s - window_s / 2.0:
        if all(abs(center - position) > exclusion_radius_s for position in positions):
            candidates.append(center)
        center += stride_s
    if len(candidates) > maximum:
        # Evenly spaced deterministic subsampling covers the full half.
        if maximum == 1:
            candidates = [candidates[len(candidates) // 2]]
        else:
            indexes = [round(index * (len(candidates) - 1) / (maximum - 1)) for index in range(maximum)]
            candidates = [candidates[index] for index in indexes]
    rows: list[dict[str, Any]] = []
    for position in candidates:
        start_s = position - window_s / 2.0
        example_id = "soc-" + stable_id(game_id, half, round(position, 3), "background")
        rows.append({
            "schema_version": EXAMPLE_SCHEMA_VERSION,
            "example_id": example_id,
            "split": split,
            "game_id": game_id,
            "source_half": half,
            "video_relative_path": video_relative_path,
            "window_start_s": start_s,
            "window_end_s": start_s + window_s,
            "candidate_time_s": position,
            "ground_truth": {
                "class_name": "background",
                "source_label": None,
                "team": "not applicable",
                "visibility": "not applicable",
                "nearby_classes": [],
                "single_label_eligible": True,
            },
            "sampling_origin": "deterministic background window at least exclusion_radius_s from every visible SoccerNet-v2 event",
        })
    return rows


def build_manifest(
    *, raw_root: Path, acquisition_dir: Path, private_output_dir: Path,
    public_receipt_path: Path, window_s: float = 12.0,
    ambiguity_radius_s: float = 4.0, background_stride_s: float = 45.0,
    background_exclusion_radius_s: float = 12.0, background_per_half: int = 24,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_root = _require_private(raw_root)
    private_output_dir = _require_private(private_output_dir)
    if window_s <= 0 or ambiguity_radius_s < 0 or background_per_half < 1:
        raise ValueError("invalid sampling configuration")
    receipt_paths = sorted(acquisition_dir.glob("*-game-*.json"))
    if not receipt_paths:
        raise FileNotFoundError("no SoccerNet acquisition receipts found")

    games: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    split_games: dict[str, set[str]] = defaultdict(set)
    media_hashes: set[str] = set()
    acquisition_hashes: list[str] = []
    for receipt_path in receipt_paths:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema_version") != ACQUISITION_SCHEMA_VERSION:
            raise ValueError(f"unexpected acquisition receipt schema: {receipt_path.name}")
        authorization = receipt.get("authorization")
        if not isinstance(authorization, dict) or authorization.get("credential_persisted") is not False:
            raise ValueError(f"acquisition receipt does not prove private credential handling: {receipt_path.name}")
        selection = receipt.get("selection")
        if not isinstance(selection, dict):
            raise ValueError(f"acquisition receipt lacks selection: {receipt_path.name}")
        split = str(selection.get("split"))
        game = str(selection.get("game", "")).replace("\\", "/")
        if split not in {"train", "valid", "test"} or not game:
            raise ValueError(f"invalid split/game in {receipt_path.name}")
        if sorted(selection.get("files", [])) != sorted([*HALF_FILES, "Labels-v2.json"]):
            raise ValueError(f"receipt is not a complete two-half acquisition: {receipt_path.name}")
        game_id = "game-" + stable_id(game)
        if game_id in split_games[split]:
            raise ValueError(f"duplicate acquisition receipt for game {game_id}")
        if any(game_id in identifiers for other, identifiers in split_games.items() if other != split):
            raise ValueError(f"game leakage across splits: {game_id}")
        split_games[split].add(game_id)

        downloaded = receipt.get("downloaded_files")
        if not isinstance(downloaded, list):
            raise ValueError(f"invalid downloaded_files in {receipt_path.name}")
        by_name = {str(item.get("name")): item for item in downloaded if isinstance(item, dict)}
        labels_record = by_name.get("Labels-v2.json")
        if not isinstance(labels_record, dict):
            raise ValueError(f"missing Labels-v2 record in {receipt_path.name}")
        labels_path = raw_root / str(labels_record["relative_path"])
        if sha256_file(labels_path) != labels_record.get("sha256"):
            raise ValueError(f"label hash mismatch for {receipt_path.name}")
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        half_records: list[dict[str, Any]] = []
        for half, filename in enumerate(HALF_FILES, start=1):
            file_record = by_name.get(filename)
            if not isinstance(file_record, dict):
                raise ValueError(f"missing {filename} record in {receipt_path.name}")
            relative_path = str(file_record["relative_path"]).replace("\\", "/")
            video_path = raw_root / relative_path
            metadata = _video_metadata(video_path)
            if metadata["sha256"] != file_record.get("sha256") or metadata["bytes"] != file_record.get("bytes"):
                raise ValueError(f"media receipt mismatch for {receipt_path.name}:{filename}")
            if metadata["sha256"] in media_hashes:
                raise ValueError("duplicate video bytes across games/halves")
            media_hashes.add(metadata["sha256"])
            events = _visible_events(labels, half)
            half_examples = _event_examples(
                split=split, game_id=game_id, half=half, duration_s=metadata["duration_s"],
                video_relative_path=relative_path, events=events, window_s=window_s,
                ambiguity_radius_s=ambiguity_radius_s,
            )
            half_examples.extend(_background_examples(
                split=split, game_id=game_id, half=half, duration_s=metadata["duration_s"],
                video_relative_path=relative_path, events=events, window_s=window_s,
                stride_s=background_stride_s, exclusion_radius_s=background_exclusion_radius_s,
                maximum=background_per_half,
            ))
            examples.extend(half_examples)
            half_records.append({
                "half": half,
                "video_relative_path": relative_path,
                "media": metadata,
                "visible_event_count": len(events),
                "example_count": len(half_examples),
            })
        acquisition_hash = sha256_file(receipt_path)
        acquisition_hashes.append(acquisition_hash)
        games.append({
            "game_id": game_id,
            "split": split,
            "source_game": game,
            "acquisition_receipt_sha256": acquisition_hash,
            "labels_sha256": labels_record["sha256"],
            "halves": half_records,
        })

    required_splits = {"train", "valid", "test"}
    if set(split_games) != required_splits or any(not split_games[split] for split in required_splits):
        raise ValueError("manifest requires non-empty train, valid, and test game sets")
    if split_games["train"] & split_games["valid"] or split_games["train"] & split_games["test"] or split_games["valid"] & split_games["test"]:
        raise ValueError("game/source leakage across train/valid/test")
    if len({row["example_id"] for row in examples}) != len(examples):
        raise ValueError("duplicate example IDs")
    examples.sort(key=lambda row: (row["split"], row["game_id"], row["source_half"], row["candidate_time_s"], row["example_id"]))

    split_counts = Counter(row["split"] for row in examples)
    class_counts: dict[str, dict[str, int]] = {}
    single_label_counts: dict[str, dict[str, int]] = {}
    for split in ("train", "valid", "test"):
        class_counter = Counter(row["ground_truth"]["class_name"] for row in examples if row["split"] == split)
        single_counter = Counter(
            row["ground_truth"]["class_name"] for row in examples
            if row["split"] == split and row["ground_truth"]["single_label_eligible"]
        )
        class_counts[split] = {name: class_counter.get(name, 0) for name in CLASS_NAMES}
        single_label_counts[split] = {name: single_counter.get(name, 0) for name in CLASS_NAMES}

    total_duration_s = sum(half["media"]["duration_s"] for game in games for half in game["halves"])
    complete_games = sum(1 for game in games if len(game["halves"]) == 2)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rights": {
            "provider": "SoccerNet",
            "access": "user-authorized NDA access",
            "allowed_use": "local non-commercial research",
            "redistribution_allowed": False,
            "credentials_persisted": False,
            "raw_media_location": "data/private only",
        },
        "sampling": {
            "window_s": window_s,
            "ambiguity_radius_s": ambiguity_radius_s,
            "background_stride_s": background_stride_s,
            "background_exclusion_radius_s": background_exclusion_radius_s,
            "background_per_half": background_per_half,
            "visual_only_model_input": True,
            "candidate_boundary": "event-centered classification plus explicitly negative background windows; not dense full-match spotting",
        },
        "taxonomy": {
            "class_names": list(CLASS_NAMES),
            "soccernet_to_class": SOCCERNET_TO_CLASS,
        },
        "split_contract": {
            "unit": "whole SoccerNet game/source",
            "train_game_ids": sorted(split_games["train"]),
            "valid_game_ids": sorted(split_games["valid"]),
            "test_game_ids": sorted(split_games["test"]),
            "pairwise_disjoint": True,
            "test_labels_frozen_before_model_fit": True,
        },
        "corpus": {
            "game_count": len(games),
            "complete_game_count": complete_games,
            "video_half_count": sum(len(game["halves"]) for game in games),
            "total_duration_s": total_duration_s,
            "total_duration_hours": total_duration_s / 3600.0,
            "total_bytes": sum(half["media"]["bytes"] for game in games for half in game["halves"]),
            "example_count": len(examples),
            "split_example_counts": dict(split_counts),
            "class_counts": class_counts,
            "single_label_eligible_class_counts": single_label_counts,
        },
        "games": games,
    }
    private_output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = private_output_dir / "manifest.json"
    examples_path = private_output_dir / "examples.jsonl"
    _write_json(manifest_path, manifest)
    _write_jsonl(examples_path, examples)
    public_receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": manifest["generated_at"],
        "status": "verified",
        "rights": manifest["rights"],
        "sampling": manifest["sampling"],
        "split_contract": manifest["split_contract"],
        "corpus": manifest["corpus"],
        "manifest_sha256": sha256_file(manifest_path),
        "examples_sha256": sha256_file(examples_path),
        "acquisition_receipt_sha256s": sorted(acquisition_hashes),
        "leakage_checks": {
            "game_ids_pairwise_disjoint": True,
            "media_hashes_unique": True,
            "example_ids_unique": True,
            "raw_media_hashes_receipt_bound": True,
            "minimum_five_hours": total_duration_s >= 5 * 3600,
            "contains_complete_match": complete_games >= 1,
        },
        "safety": {
            "contains_credentials": False,
            "contains_raw_media_paths": False,
            "contains_raw_media": False,
        },
    }
    if not all(public_receipt["leakage_checks"].values()):
        raise RuntimeError("corpus does not satisfy the frozen scale/leakage contract")
    _write_json(public_receipt_path, public_receipt)
    return manifest, public_receipt


def load_examples(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("schema_version") != EXAMPLE_SCHEMA_VERSION:
                raise ValueError(f"invalid example schema at line {line_number}")
            rows.append(row)
    return rows


def verify_manifest(
    *, manifest_path: Path, examples_path: Path, public_receipt_path: Path,
    raw_root: Path,
) -> dict[str, Any]:
    raw_root = _require_private(raw_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(public_receipt_path.read_text(encoding="utf-8"))
    examples = load_examples(examples_path)
    checks = {
        "manifest_schema": manifest.get("schema_version") == SCHEMA_VERSION,
        "receipt_schema": receipt.get("schema_version") == RECEIPT_SCHEMA_VERSION,
        "manifest_hash": sha256_file(manifest_path) == receipt.get("manifest_sha256"),
        "examples_hash": sha256_file(examples_path) == receipt.get("examples_sha256"),
        "example_count": len(examples) == manifest.get("corpus", {}).get("example_count"),
        "five_hours": float(manifest.get("corpus", {}).get("total_duration_s", 0)) >= 5 * 3600,
        "complete_match": int(manifest.get("corpus", {}).get("complete_game_count", 0)) >= 1,
        "private_boundary": "private" in {part.lower() for part in manifest_path.resolve().parts},
    }
    train = set(manifest.get("split_contract", {}).get("train_game_ids", []))
    valid = set(manifest.get("split_contract", {}).get("valid_game_ids", []))
    test = set(manifest.get("split_contract", {}).get("test_game_ids", []))
    checks["game_disjoint"] = not (train & valid or train & test or valid & test)
    checks["example_ids_unique"] = len({row["example_id"] for row in examples}) == len(examples)
    checks["example_split_membership"] = all(
        row["game_id"] in {"train": train, "valid": valid, "test": test}[row["split"]]
        for row in examples
    )
    # Recheck every raw video against the immutable manifest without leaking paths.
    media_ok = True
    for game in manifest.get("games", []):
        for half in game.get("halves", []):
            path = raw_root / half["video_relative_path"]
            media_ok = media_ok and path.is_file() and sha256_file(path) == half["media"]["sha256"]
    checks["raw_media_hashes"] = media_ok
    if not all(checks.values()):
        raise ValueError("manifest verification failed: " + ",".join(key for key, value in checks.items() if not value))
    return {"status": "pass", "checks": checks, "example_count": len(examples)}

