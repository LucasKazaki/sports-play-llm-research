"""Offline, explicit-policy SoccerNet point-label conversion for hosted scoring.

Only annotation JSON and configuration JSON are read. Media is never opened.
The caller must freeze the exact ontology, units, time policy, match, half and
clip binding. Derived intervals are scoring windows, not observed event extents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from hosted_video_benchmark import _strict_json, canonical_sha256, require_private_output, write_json_atomic
from hosted_video_scoring import LABEL_SCHEMA, validate_labels

CONFIG_SCHEMA = "playground-soccernet-point-conversion-config-v1"
RECEIPT_SCHEMA = "playground-soccernet-point-conversion-receipt-v1"
HASH = re.compile(r"[0-9a-f]{64}")
GAME_TIME = re.compile(r"([12]) - ([0-9]{2,}):([0-5][0-9])")


class ConversionError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConversionError(message)


def keys(value: Any, expected: set[str], name: str) -> dict:
    require(isinstance(value, dict) and set(value) == expected, name + " keys differ from explicit contract")
    return value


def finite(value: Any, name: str, minimum: float = 0) -> float:
    require(not isinstance(value, bool) and isinstance(value, (int, float)),
            name + " must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ConversionError(name + " must be finite") from None
    require(math.isfinite(number) and number >= minimum, name + " must be finite and within bounds")
    return number


def text(value: Any, name: str) -> str:
    require(isinstance(value, str) and bool(value.strip()) and value == value.strip(),
            name + " must be a nonempty exact string")
    return value


def hash_value(value: Any, name: str) -> str:
    require(isinstance(value, str) and bool(HASH.fullmatch(value)), name + " must be a SHA-256")
    return value


def validate_config(raw: Any) -> dict:
    config = keys(raw, {
        "schema_version", "source_annotations_sha256", "source_match_id", "half", "half_duration_s",
        "clip", "annotation_origin", "independence_evidence_sha256", "mapping", "policy",
    }, "configuration")
    require(config["schema_version"] == CONFIG_SCHEMA, "unsupported conversion configuration")
    hash_value(config["source_annotations_sha256"], "source_annotations_sha256")
    match = text(config["source_match_id"], "source_match_id")
    require("\\" not in match and all(part not in {"", ".", ".."} for part in match.split("/")),
            "match ID must use exact non-traversing SoccerNet grouping")
    require(type(config["half"]) is int and config["half"] in {1, 2}, "half must be explicitly 1 or 2")
    half_duration = finite(config["half_duration_s"], "half_duration_s")
    require(half_duration > 0, "half_duration_s must be positive")
    clip = keys(config["clip"], {"clip_id", "source_sha256", "offset_s", "duration_s"}, "clip")
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", text(clip["clip_id"], "clip_id"))),
            "clip_id must be opaque and filesystem-safe")
    hash_value(clip["source_sha256"], "clip source_sha256")
    offset = finite(clip["offset_s"], "clip offset_s")
    duration = finite(clip["duration_s"], "clip duration_s")
    require(duration > 0 and math.isfinite(offset+duration) and offset+duration <= half_duration,
            "clip bounds exceed the selected half or have zero duration")
    origin = config["annotation_origin"]
    require(origin in {"synthetic_fixture", "independent_annotation"}, "unsupported annotation_origin")
    if origin == "synthetic_fixture":
        require(config["independence_evidence_sha256"] is None,
                "synthetic fixtures cannot claim independent annotation evidence")
    else:
        hash_value(config["independence_evidence_sha256"], "independence_evidence_sha256")
    mapping = config["mapping"]
    require(isinstance(mapping, dict) and bool(mapping), "explicit nonempty ontology mapping required")
    for source, target in mapping.items():
        text(source, "mapping source label")
        if target is not None:
            text(target, "mapping target event_type")
    policy = keys(config["policy"], {
        "input_position_unit", "input_game_time_basis", "output_time_unit",
        "game_time_consistency", "point_membership", "interval_before_s",
        "interval_after_s", "boundary_policy", "visibility_policy",
    }, "policy")
    required = {
        "input_position_unit": "milliseconds", "input_game_time_basis": "half_relative_mm:ss",
        "output_time_unit": "seconds", "game_time_consistency": "floor_position_to_whole_second",
        "point_membership": "start_inclusive_end_exclusive",
    }
    for key, expected in required.items():
        require(policy[key] == expected, key + " must explicitly equal " + expected)
    before = finite(policy["interval_before_s"], "interval_before_s")
    after = finite(policy["interval_after_s"], "interval_after_s")
    require(math.isfinite(before+after) and before+after > 0, "point-to-interval extent must be positive")
    require(policy["boundary_policy"] in {"clip_to_window", "reject_crossing"}, "unsupported boundary_policy")
    require(policy["visibility_policy"] in {"visible_only", "all_annotated"}, "unsupported visibility_policy")
    return config


def parse_source(raw: Any, config: dict) -> list[dict]:
    require(isinstance(raw, dict) and {"UrlLocal", "annotations"} <= set(raw)
            and set(raw) <= {"UrlLocal", "UrlYoutube", "annotations", "gameAwayTeam", "gameDate",
                             "gameHomeTeam", "gameScore"}, "source grouping keys are invalid")
    require(raw["UrlLocal"] == config["source_match_id"], "source match grouping differs from exact match ID")
    require(isinstance(raw["annotations"], list), "SoccerNet annotations must be a list")
    rows, seen = [], set()
    for index, annotation in enumerate(raw["annotations"]):
        require(isinstance(annotation, dict)
                and {"gameTime", "position", "label", "visibility"} <= set(annotation)
                and set(annotation) <= {"gameTime", "position", "label", "visibility", "team"},
                "annotation keys or explicit half/match grouping are invalid")
        game_time = GAME_TIME.fullmatch(text(annotation["gameTime"], "gameTime"))
        require(game_time is not None, "gameTime must be explicit half - MM:SS")
        half, minutes, seconds = (int(value) for value in game_time.groups())
        position = annotation["position"]
        require((isinstance(position, str) and bool(re.fullmatch(r"[0-9]+", position)))
                or type(position) is int, "position must be integer milliseconds, not guessed seconds")
        milliseconds = int(position)
        require(0 <= milliseconds <= 2**53-1, "position milliseconds are out of exact numeric range")
        require(milliseconds // 1000 == minutes*60 + seconds,
                "gameTime and millisecond position disagree under frozen whole-second policy")
        source_label = text(annotation["label"], "source label")
        visibility = annotation["visibility"]
        require(visibility in {"visible", "not shown"}, "unsupported source visibility")
        if "team" in annotation:
            text(annotation["team"], "source team")
        identity = (half, milliseconds, source_label)
        require(identity not in seen, "duplicate half/position/source-label annotation")
        seen.add(identity)
        position_s = milliseconds / 1000.0
        if half == config["half"]:
            require(position_s <= config["half_duration_s"], "selected-half annotation exceeds half duration")
        rows.append({"source_index": index, "half": half, "position_ms": milliseconds,
                     "position_s": position_s, "source_label": source_label, "visibility": visibility})
    return rows


def convert_annotations(*, annotations_path: Path, config_path: Path, output_dir: Path) -> dict:
    annotations_path, config_path = Path(annotations_path).resolve(), Path(config_path).resolve()
    output_dir = require_private_output(Path(output_dir))
    require(not output_dir.exists(), "conversion output directory already exists; use a fresh directory")
    source_bytes = annotations_path.read_bytes()
    config_bytes = config_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    config = validate_config(_strict_json(config_bytes.decode("utf-8")))
    require(source_sha == config["source_annotations_sha256"], "source annotation bytes/hash changed")
    rows = parse_source(_strict_json(source_bytes.decode("utf-8")), config)
    clip, policy = config["clip"], config["policy"]
    selected, excluded = [], []
    for row in rows:
        reason = None
        if row["half"] != config["half"]:
            reason = "other_half"
        elif not clip["offset_s"] <= row["position_s"] < clip["offset_s"] + clip["duration_s"]:
            reason = "outside_clip_point_bounds"
        elif policy["visibility_policy"] == "visible_only" and row["visibility"] != "visible":
            reason = "visibility_policy"
        if reason is not None:
            excluded.append({"source_index": row["source_index"], "reason": reason})
            continue
        require(row["source_label"] in config["mapping"], "selected source label has no explicit ontology mapping")
        event_type = config["mapping"][row["source_label"]]
        if event_type is None:
            excluded.append({"source_index": row["source_index"], "reason": "explicit_null_mapping"})
            continue
        peak = row["position_s"] - clip["offset_s"]
        start, end = peak-policy["interval_before_s"], peak+policy["interval_after_s"]
        if policy["boundary_policy"] == "reject_crossing":
            require(start >= 0 and end <= clip["duration_s"], "derived interval crosses clip boundary")
        else:
            start, end = max(0., start), min(clip["duration_s"], end)
        require(start < end, "derived interval is empty after boundary policy")
        selected.append({**row, "event_type": event_type, "start_s": start, "peak_s": peak, "end_s": end})
    selected.sort(key=lambda row: (row["position_ms"], row["source_label"], row["event_type"]))
    identities = [(row["peak_s"], row["event_type"]) for row in selected]
    require(len(set(identities)) == len(identities), "ontology mapping collapses duplicate point/event identities")
    events, lineage = [], []
    for index, row in enumerate(selected, 1):
        label_id = f"g{index:04d}"
        events.append({"label_id": label_id, **{key: row[key] for key in ("event_type","start_s","peak_s","end_s")}})
        lineage.append({"label_id": label_id, "source_index": row["source_index"],
                        "source_label": row["source_label"], "source_half": row["half"],
                        "source_position_ms": row["position_ms"]})
    labels = {"schema_version": LABEL_SCHEMA, "clip_id": clip["clip_id"],
              "source_sha256": clip["source_sha256"], "duration_s": clip["duration_s"],
              "time_unit": "seconds", "annotation_origin": config["annotation_origin"], "events": events}
    validate_labels(labels, clip_id=clip["clip_id"], input_sha256=clip["source_sha256"], duration_s=clip["duration_s"])
    require(annotations_path.read_bytes() == source_bytes and config_path.read_bytes() == config_bytes,
            "conversion inputs changed while being processed")
    output_dir.mkdir(parents=True, exist_ok=False)
    label_path = output_dir / "labels.json"
    write_json_atomic(label_path, labels)
    labels_sha = hashlib.sha256(label_path.read_bytes()).hexdigest()
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "converter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_annotations_sha256": source_sha, "source_annotations_bytes": len(source_bytes),
        "configuration_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "mapping_sha256": canonical_sha256(config["mapping"]), "policy_sha256": canonical_sha256(policy),
        "source_match_id": config["source_match_id"], "selected_half": config["half"], "clip": clip,
        "mapping": config["mapping"], "policy": policy, "labels_sha256": labels_sha,
        "annotation_origin": config["annotation_origin"],
        "independence_evidence_sha256": config["independence_evidence_sha256"],
        "annotation_independence_verified": False, "clip_media_hash_verified": False,
        "source_annotation_count": len(rows), "converted_label_count": len(events),
        "lineage": lineage, "excluded": excluded,
        "synthetic": config["annotation_origin"] == "synthetic_fixture",
        "truth_boundary": "SYSTEMS GO / SEMANTIC NO-GO", "scientific_validation": False,
        "scope": "point-label conversion under caller-frozen policy; derived intervals are not annotated event extents",
        "limits": [
            "No source media was opened; the runner must separately verify the supplied clip hash.",
            "Dataset source labels and visibility do not establish independent human study annotation or visual answerability.",
            "An empty converted event list is no selected annotation, not verified background or correct abstention.",
            "The current frozen report schema requires an empty model report to abstain.",
            "Conversion is preparation and cannot prove that a later run was held out or frozen before inference.",
        ],
    }
    write_json_atomic(output_dir / "conversion-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--private-out", required=True, type=Path)
    args = parser.parse_args()
    receipt = convert_annotations(annotations_path=args.annotations, config_path=args.config,
                                  output_dir=args.private_out)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
