#!/usr/bin/env python3
"""Validate the bounded, open SoccerTrack v2 local intake.

This is an acquisition-integrity and structural validator only. Its OpenCV
readability probe is explicitly limited to local acquisition validation; it
never sends pixels to a model, creates clips, scores sports semantics, or
reports a benchmark result. BAS label values are inspected only long enough to
confirm the published fixed 12-class structure and are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


OFFICIAL_SPLITS = {
    "official_bas_train": ["117092", "117093", "118575", "118576", "118577", "128058", "132877"],
    "official_bas_validation": ["118578"],
    "official_bas_test": ["128057", "132831"],
}
EXPECTED_MATCH_IDS = {match_id for group in OFFICIAL_SPLITS.values() for match_id in group}


class ValidationError(RuntimeError):
    """Raised for an invalid local acquisition or split contract."""


def fail(message: str) -> None:
    raise ValidationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def under_root(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"receipt path escapes data root: {relative_path}") from exc
    return candidate


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{name} must be an object")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{name} must be a list")
    return value


def require_match_id(value: Any, context: str) -> str:
    match_id = str(value) if isinstance(value, int) else value
    if not isinstance(match_id, str) or match_id not in EXPECTED_MATCH_IDS:
        fail(f"{context} must be one of the pinned official SoccerTrack match IDs")
    return match_id


def _managed_files(root: Path, directory: Path, suffix: str) -> set[str]:
    parent = root / directory
    if not parent.is_dir():
        fail(f"managed source directory is missing: {directory.as_posix()}")
    files = [path for path in parent.rglob("*") if path.is_file()]
    unexpected = [path.resolve().relative_to(root.resolve()).as_posix() for path in files if path.suffix.lower() != suffix]
    if unexpected:
        fail(f"unexpected unmanaged file under {directory.as_posix()}: {sorted(unexpected)}")
    return {
        path.resolve().relative_to(root.resolve()).as_posix()
        for path in files
    }


def validate_receipt_and_files(root: Path, receipt: dict[str, Any]) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    if receipt.get("schema_version") != "soccertrack-v2-source-provenance-v1":
        fail("unexpected receipt schema_version")
    if receipt.get("dataset_id") != "SoccerTrack-v2":
        fail("receipt does not identify SoccerTrack-v2")
    if receipt.get("data_license") != "CC-BY-4.0":
        fail("receipt does not record CC-BY-4.0 for the media")
    if not isinstance(receipt.get("source_url"), str) or not receipt["source_url"].startswith("https://"):
        fail("receipt source_url is missing or invalid")
    if not isinstance(receipt.get("license_url"), str) or not receipt["license_url"].startswith("https://"):
        fail("receipt license_url is missing or invalid")
    if not isinstance(receipt.get("source_revision"), str) or len(receipt["source_revision"]) < 7:
        fail("receipt source_revision is missing or invalid")

    records = require_list(receipt.get("files"), "files")
    if len(records) < 2 or len(records) % 2:
        fail("receipt must contain one media and one annotation record for each acquired match")

    media: list[tuple[str, Path]] = []
    annotations: list[tuple[str, Path]] = []
    recorded_media_paths: set[str] = set()
    recorded_annotation_paths: set[str] = set()
    seen_kind_match: set[tuple[str, str]] = set()
    for index, item in enumerate(records):
        record = require_mapping(item, f"files[{index}]")
        kind = record.get("kind")
        if kind not in {"media", "annotation"}:
            fail(f"unsupported receipt file kind: {kind!r}")
        match_id = require_match_id(record.get("match_id"), f"files[{index}].match_id")
        if (kind, match_id) in seen_kind_match:
            fail(f"duplicate {kind} record for match {match_id}")
        seen_kind_match.add((kind, match_id))
        relative_path = record.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            fail(f"files[{index}].relative_path is missing")
        local_path = under_root(root, relative_path)
        if not local_path.is_file():
            fail(f"receipt file is absent: {relative_path}")
        expected_bytes = record.get("bytes")
        if not isinstance(expected_bytes, int) or expected_bytes <= 0:
            fail(f"files[{index}].bytes must be a positive integer")
        if local_path.stat().st_size != expected_bytes:
            fail(
                f"byte mismatch for {relative_path}: "
                f"expected {expected_bytes}, found {local_path.stat().st_size}"
            )
        expected_hash = record.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            fail(f"files[{index}].sha256 is invalid")
        if sha256_file(local_path) != expected_hash.lower():
            fail(f"sha256 mismatch for {relative_path}")

        path_parts = Path(relative_path).as_posix().split("/")
        if kind == "media":
            if (
                len(path_parts) != 3
                or path_parts[:2] != ["media", match_id]
                or local_path.suffix.lower() != ".mp4"
                or local_path.name != f"{match_id}_panorama_1st_half.mp4"
                or record.get("half") != 1
            ):
                fail(f"media record has an invalid first-half SoccerTrack layout: {relative_path}")
            if record.get("official_reported_content_type") != "video/mp4":
                fail("media content type was not recorded as video/mp4")
            if record.get("official_reported_bytes") != expected_bytes:
                fail("media byte count disagrees with official listing")
            media.append((match_id, local_path))
            recorded_media_paths.add(relative_path)
        else:
            if (
                len(path_parts) != 3
                or path_parts[:2] != ["annotations", "bas"]
                or local_path.suffix.lower() != ".json"
                or local_path.name != f"{match_id}_12_class_events.json"
            ):
                fail(f"annotation record has an invalid SoccerTrack BAS layout: {relative_path}")
            annotations.append((match_id, local_path))
            recorded_annotation_paths.add(relative_path)

    media_ids = {match_id for match_id, _ in media}
    annotation_ids = {match_id for match_id, _ in annotations}
    if media_ids != annotation_ids:
        fail(f"media/BAS match mismatch: media_only={sorted(media_ids - annotation_ids)}; bas_only={sorted(annotation_ids - media_ids)}")
    if recorded_media_paths != _managed_files(root, Path("media"), ".mp4"):
        fail("unrecorded or missing MP4 under the managed public media tree")
    if recorded_annotation_paths != _managed_files(root, Path("annotations") / "bas", ".json"):
        fail("unrecorded or missing BAS JSON under the managed public annotation tree")
    return sorted(media), sorted(annotations)


def validate_media(media_path: Path) -> dict[str, Any]:
    """Perform the acquisition-only local readability probe for one MP4."""

    with media_path.open("rb") as handle:
        header = handle.read(64)
    if b"ftyp" not in header[:32]:
        fail("media does not have an ISO Base Media File Format header")

    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ValidationError("OpenCV is required for readable-media validation") from exc

    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        fail("OpenCV could not open the acquired MP4")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if width < 1280 or height < 720 or fps <= 0 or frame_count <= 0:
            fail(
                "MP4 metadata is implausible: "
                f"width={width}, height={height}, fps={fps}, frames={frame_count}"
            )
        decoded_frame = None
        decoded_at_s = None
        for sample_s in (0.0, 30.0):
            capture.set(cv2.CAP_PROP_POS_MSEC, sample_s * 1000.0)
            ok, frame = capture.read()
            if ok and frame is not None and frame.size:
                decoded_frame = frame
                decoded_at_s = sample_s
                break
        if decoded_frame is None or decoded_at_s is None:
            fail("OpenCV could not decode a sampled frame from the MP4")
        if float(decoded_frame.std()) <= 1.0:
            fail("decoded media frame has implausibly low pixel variation")
    finally:
        capture.release()

    return {
        "container": "mp4",
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count_reported": frame_count,
        "decoded_sample_seconds": decoded_at_s,
        "decoded_frame_shape": list(decoded_frame.shape),
        "decoded_frame_std": round(float(decoded_frame.std()), 6),
        "decoder_check_scope": "local_acquisition_readability_only_no_model_transport_or_event_inference",
    }


def validate_annotation(annotation_path: Path, expected_match_id: str) -> dict[str, Any]:
    data = require_mapping(json.loads(annotation_path.read_text(encoding="utf-8")), "annotation")
    if str(data.get("match_id")) != expected_match_id:
        fail("annotation match_id does not join to the acquired media match")
    actions = require_list(data.get("actions"), "annotation.actions")
    if not actions:
        fail("annotation.actions is empty")
    labels: Counter[str] = Counter()
    half_prefixes: Counter[str] = Counter()
    noncanonical_game_time_count = 0
    for index, action in enumerate(actions):
        row = require_mapping(action, f"annotation.actions[{index}]")
        label = row.get("label")
        if not isinstance(label, str) or not label:
            fail(f"annotation.actions[{index}].label is invalid")
        labels[label] += 1
        try:
            int(row.get("position"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"annotation.actions[{index}].position is invalid") from exc
        game_time = row.get("gameTime")
        if not isinstance(game_time, str) or not game_time:
            fail(f"annotation.actions[{index}].gameTime is invalid")
        if game_time.startswith("1 - "):
            half_prefixes["1"] += 1
        elif game_time.startswith("2 - "):
            half_prefixes["2"] += 1
        else:
            # Record a source-format caveat rather than guessing a half from
            # text. This acquisition intentionally makes no semantic repair.
            noncanonical_game_time_count += 1
    if len(labels) != 12:
        fail(f"expected 12 BAS labels, found {len(labels)}")
    fps = data.get("fps")
    if not isinstance(fps, (int, float)) or fps <= 0:
        fail("annotation fps is invalid")
    return {
        "match_id": expected_match_id,
        "fps": fps,
        "actions": len(actions),
        "fixed_label_count": len(labels),
        "game_time_half_prefix_counts": dict(sorted(half_prefixes.items())),
        "game_time_without_canonical_half_prefix": noncanonical_game_time_count,
        "label_values_emitted": False,
    }


def validate_split_plan(
    receipt: dict[str, Any], split_plan: dict[str, Any], acquired_match_ids: Iterable[str]
) -> dict[str, Any]:
    if split_plan.get("schema_version") != "soccertrack-v2-open-game-split-v1":
        fail("unexpected split-plan schema_version")
    if split_plan.get("source_revision") != receipt.get("source_revision"):
        fail("split plan and receipt use different source revisions")
    if split_plan.get("unit_of_split") != "match_id":
        fail("split plan must operate at match_id level")
    groups = require_mapping(split_plan.get("game_level_splits"), "game_level_splits")
    if set(groups) != set(OFFICIAL_SPLITS):
        fail("split plan must contain the three official BAS split groups")
    flattened: list[str] = []
    for group_name, expected_ids in OFFICIAL_SPLITS.items():
        values = require_list(groups[group_name], f"game_level_splits.{group_name}")
        if values != expected_ids:
            fail(f"split plan does not preserve the pinned official {group_name} order and membership")
        flattened.extend(values)
    if set(flattened) != EXPECTED_MATCH_IDS or len(flattened) != len(EXPECTED_MATCH_IDS):
        fail("split plan must assign each official public match exactly once")

    expected_partition = {
        match_id: partition for partition, match_ids in OFFICIAL_SPLITS.items() for match_id in match_ids
    }
    acquired = sorted(set(acquired_match_ids))
    expected_acquisition = [
        {
            "match_id": match_id,
            "half": 1,
            "split": expected_partition[match_id],
            "role": "heldout_sealed_unscored" if expected_partition[match_id] == "official_bas_test" else "development_only_unscored",
        }
        for match_id in acquired
    ]
    recorded_acquisitions = require_list(split_plan.get("media_acquisitions"), "media_acquisitions")
    if recorded_acquisitions != expected_acquisition:
        fail("media_acquisitions must exactly identify the acquired first halves and their pinned official roles")

    heldout = sorted(match_id for match_id in acquired if expected_partition[match_id] == "official_bas_test")
    development = sorted(match_id for match_id in acquired if expected_partition[match_id] != "official_bas_test")
    missing_heldout = sorted(set(OFFICIAL_SPLITS["official_bas_test"]) - set(heldout))
    return {
        "official_bas_train_matches": len(OFFICIAL_SPLITS["official_bas_train"]),
        "official_bas_validation_matches": len(OFFICIAL_SPLITS["official_bas_validation"]),
        "official_bas_heldout_test_matches": len(OFFICIAL_SPLITS["official_bas_test"]),
        "acquired_development_match_ids": development,
        "acquired_heldout_match_ids": heldout,
        "unacquired_official_heldout_match_ids": missing_heldout,
        "official_heldout_coverage_status": "complete" if not missing_heldout else "incomplete",
        "heldout_evaluation_ready": False,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=repo_root / "data" / "open" / "soccertrack-v2",
        help="SoccerTrack v2 bounded sample root",
    )
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--split-plan", type=Path, default=None)
    args = parser.parse_args()

    root = args.data_root.resolve()
    receipt_path = (args.receipt or root / "source-provenance.json").resolve()
    split_plan_path = (args.split_plan or root / "game-level-split-plan.json").resolve()
    try:
        receipt = require_mapping(json.loads(receipt_path.read_text(encoding="utf-8")), "receipt")
        split_plan = require_mapping(json.loads(split_plan_path.read_text(encoding="utf-8")), "split plan")
        media_paths, annotation_paths = validate_receipt_and_files(root, receipt)
        annotation_by_match = dict(annotation_paths)
        media = [{"match_id": match_id, **validate_media(path)} for match_id, path in media_paths]
        annotation = [validate_annotation(path, match_id) for match_id, path in sorted(annotation_by_match.items())]
        split = validate_split_plan(receipt, split_plan, (match_id for match_id, _ in media_paths))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 1

    print(
        json.dumps(
            {
                "status": "pass",
                "media": media,
                "annotation": annotation,
                "split": split,
                "semantic_evaluation": "not_run",
                "model_transport": "not_run",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
