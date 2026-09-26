"""Football-only long-form VLM reporting, retrieval, and weak visual-probe audit.

The module is deliberately self-contained.  It consumes a verified American-
football media receipt, samples silent frames, calls a loopback multimodal model,
and preserves enough hashes to reproduce the exact model inputs and outputs.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "footballmaster-longform-experiment-v2"
REPORT_VERSION = "footballmaster-visual-report-v2"
DEFAULT_DATASET = Path("data/public/footballmaster-v2")
DEFAULT_OUTPUT = Path("artifacts/footballmaster/longform-v2")
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
WINDOW_DURATIONS = (30, 60, 120)
TRAIN_FRACTIONS = (0.28, 0.52, 0.76)
VALID_FRACTIONS = (0.32, 0.68)
TEST_FRACTIONS = (0.12, 0.27, 0.42, 0.57, 0.72, 0.87)
FRAMES_PER_WINDOW = 8

# This split is experimental and leaves the immutable source manifest untouched.
EXPERIMENT_SPLITS = {
    "bishop-odowd-vs-berkeley-varsity": "valid",
    "castro-valley-vs-berkeley-varsity": "train",
    "logan-vs-berkeley-jv": "train",
    "encinal-vs-berkeley-jv": "test",
    "pittsburg-vs-berkeley-jv": "train",
    "san-leandro-vs-berkeley": "test",
}

EVENT_TYPES = (
    "pass_play",
    "run_play",
    "kick_play",
    "penalty_or_officiating",
    "turnover",
    "scoring",
    "pre_snap",
    "post_play",
    "replay",
    "stoppage",
    "unknown",
)

QUERY_SET = (
    ("q01", "completed forward pass", "action"),
    ("q02", "incomplete pass or dropped ball", "action"),
    ("q03", "quarterback throws under pressure", "pressure"),
    ("q04", "deep pass downfield", "action"),
    ("q05", "short pass to the flat", "action"),
    ("q06", "designed rushing play", "action"),
    ("q07", "runner breaks toward the sideline", "movement"),
    ("q08", "runner tackled in the middle", "movement"),
    ("q09", "goal-line or red-zone play", "field_context"),
    ("q10", "punt play", "special_teams"),
    ("q11", "kickoff or kick return", "special_teams"),
    ("q12", "field-goal attempt", "special_teams"),
    ("q13", "penalty flag or officials confer", "officiating"),
    ("q14", "turnover or change of possession", "outcome"),
    ("q15", "interception", "outcome"),
    ("q16", "fumble or loose ball", "outcome"),
    ("q17", "touchdown or scoring celebration", "outcome"),
    ("q18", "pre-snap formation with receivers spread", "formation"),
    ("q19", "tight formation near the line", "formation"),
    ("q20", "motion before the snap", "formation"),
    ("q21", "defensive blitz or pass rush", "defense"),
    ("q22", "open-field tackle", "defense"),
    ("q23", "multiple defenders converge on ball carrier", "defense"),
    ("q24", "play near the left sideline", "field_context"),
    ("q25", "play near the right sideline", "field_context"),
    ("q26", "broadcast replay instead of live action", "broadcast"),
    ("q27", "players waiting during a stoppage", "broadcast"),
    ("q28", "jersey number is visibly readable", "identity_evidence"),
    ("q29", "two distinct plays in one time window", "multi_event"),
    ("q30", "evidence too sparse to identify a play", "abstention"),
)

PROMPT_CANDIDATES = {
    "candidate_a_direct": (
        "Analyze only the ordered American-football broadcast frames supplied below. "
        "Describe every distinct visible play or broadcast state. Never use commentary, "
        "filenames, team metadata, rosters, or outside knowledge. Return the required JSON."
    ),
    "candidate_b_evidence_first": (
        "You are indexing silent American-football film for later coach search. Use only the "
        "ordered frames supplied below. Separate distinct plays, replays, pre-snap views, and "
        "stoppages. For every claim cite frame IDs. Do not invent player names, teams, down, "
        "distance, coverage, route, result, or intent when pixels do not establish them; use "
        "unknown and list the uncertainty. If no play is identifiable, abstain. Return only the "
        "required JSON."
    ),
    "candidate_c_event_guarded_3200": (
        "You are indexing silent American-football film for later coach search. Use only the "
        "ordered frames supplied below. A sampled frame is not automatically a separate play: "
        "merge frames when they plausibly show one broadcast state, and never invent continuity "
        "between sparse samples. Label scoring only when pixels show a score, an official scoring "
        "signal, a goal-line result, or an unmistakable scoring aftermath; generic motion is not "
        "scoring. Label pass_play only when release, ball flight, catch attempt, or a clearly "
        "pass-specific posture is visible. Label run_play only when visible possession and running "
        "action support it. Otherwise use pre_snap, post_play, stoppage, replay, or unknown. Cite "
        "frame IDs for every claim, use anonymous roles or readable jersey numbers instead of "
        "names, and list missing evidence. If no play is identifiable, abstain. Return only the "
        "required JSON."
    ),
}

PROMPT_MAX_TOKENS = {
    "candidate_a_direct": 2200,
    "candidate_b_evidence_first": 2200,
    "candidate_c_event_guarded_3200": 3200,
}

PROMPT_REQUEST_POLICY = {
    "candidate_a_direct": "structured-v1",
    "candidate_b_evidence_first": "structured-v1",
    "candidate_c_event_guarded_3200": "structured-3200-compact-recovery-v2",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reset_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


@dataclass(frozen=True)
class Window:
    window_id: str
    asset_id: str
    game_id: str
    split: str
    media_path: str
    media_sha256: str
    start_seconds: float
    duration_seconds: int
    fraction_index: int
    fraction: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "asset_id": self.asset_id,
            "game_id": self.game_id,
            "split": self.split,
            "media_path": self.media_path,
            "media_sha256": self.media_sha256,
            "start_seconds": self.start_seconds,
            "duration_seconds": self.duration_seconds,
            "fraction_index": self.fraction_index,
            "fraction": self.fraction,
        }


def _fractions_for_split(split: str) -> tuple[float, ...]:
    if split == "train":
        return TRAIN_FRACTIONS
    if split == "valid":
        return VALID_FRACTIONS
    if split == "test":
        return TEST_FRACTIONS
    raise ValueError(f"unsupported split: {split}")


def build_windows(verification: dict[str, Any]) -> list[Window]:
    windows: list[Window] = []
    seen_games: dict[str, str] = {}
    assets = verification.get("assets", [])
    if set(EXPERIMENT_SPLITS) != {item.get("asset_id") for item in assets}:
        raise ValueError("verified asset set does not match the frozen six-game protocol")
    for item in assets:
        asset_id = str(item["asset_id"])
        game_id = str(item["game_id"])
        split = EXPERIMENT_SPLITS[asset_id]
        previous = seen_games.setdefault(game_id, split)
        if previous != split:
            raise ValueError(f"game leakage: {game_id}")
        observed = float(item["probe"]["duration_seconds"])
        for duration in WINDOW_DURATIONS:
            for fraction_index, fraction in enumerate(_fractions_for_split(split)):
                available = max(0.0, observed - duration)
                start = round(available * fraction, 3)
                raw_id = f"{asset_id}|{duration}|{fraction_index}|{start:.3f}"
                window_id = "fmw-" + sha256_bytes(raw_id.encode("utf-8"))[:16]
                windows.append(
                    Window(
                        window_id=window_id,
                        asset_id=asset_id,
                        game_id=game_id,
                        split=split,
                        media_path=str(item["project_relative_path"]),
                        media_sha256=str(item["sha256"]),
                        start_seconds=start,
                        duration_seconds=duration,
                        fraction_index=fraction_index,
                        fraction=fraction,
                    )
                )
    return sorted(windows, key=lambda item: (item.split, item.asset_id, item.duration_seconds, item.fraction_index))


def validate_dataset(project_root: Path, dataset_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = dataset_dir / "source-manifest.json"
    receipt_path = dataset_dir / "verification-receipt.json"
    if not manifest_path.is_file() or not receipt_path.is_file():
        raise FileNotFoundError("verified source manifest and verification receipt are required")
    manifest = read_json(manifest_path)
    receipt = read_json(receipt_path)
    if receipt.get("checks", {}).get("five_hour_duration_gate") != "pass":
        raise ValueError("five-hour verification gate did not pass")
    if receipt.get("coverage", {}).get("asset_count") != 6:
        raise ValueError("the frozen protocol requires exactly six verified games")
    receipt_bound_hash = sha256_bytes(
        (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    if receipt_bound_hash != receipt.get("source_manifest_sha256"):
        raise ValueError("source manifest hash does not match verification receipt")
    for item in receipt.get("assets", []):
        media = project_root / item["project_relative_path"]
        if not media.is_file():
            raise FileNotFoundError(media)
        if media.stat().st_size != item["bytes"]:
            raise ValueError(f"media byte count mismatch: {media}")
        if sha256_file(media) != item["sha256"]:
            raise ValueError(f"media hash mismatch: {media}")
        if item.get("full_video_decode", {}).get("status") != "pass":
            raise ValueError(f"full decode is not verified: {media}")
    return manifest, receipt


def prepare(project_root: Path, dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest, receipt = validate_dataset(project_root, dataset_dir)
    windows = build_windows(receipt)
    split_games: dict[str, set[str]] = {"train": set(), "valid": set(), "test": set()}
    for window in windows:
        split_games[window.split].add(window.game_id)
    if {key: len(value) for key, value in split_games.items()} != {"train": 3, "valid": 1, "test": 2}:
        raise ValueError("frozen split must be three train, one validation, and two test games")
    if any(split_games[a] & split_games[b] for a, b in (("train", "valid"), ("train", "test"), ("valid", "test"))):
        raise ValueError("game IDs cross split boundaries")

    output_dir.mkdir(parents=True, exist_ok=True)
    windows_path = output_dir / "window-manifest.jsonl"
    reset_jsonl(windows_path)
    for window in windows:
        append_jsonl(windows_path, window.as_dict())
    query_path = output_dir / "frozen-query-set.json"
    queries = {
        "schema_version": "footballmaster-frozen-query-set-v2",
        "frozen_before_test": True,
        "evaluation_role": "retrieval_system_behavior_only_no_relevance_ground_truth",
        "queries": [{"query_id": qid, "text": text, "facet": facet} for qid, text, facet in QUERY_SET],
    }
    write_json(query_path, queries)
    prompt_path = output_dir / "prompt-candidates.json"
    write_json(
        prompt_path,
        {
            "schema_version": "footballmaster-prompt-candidates-v2",
            "development_scope": "training_games_only_then_structural_selection_on_validation_game",
            "not_parameter_training": True,
            "candidates": PROMPT_CANDIDATES,
        },
    )
    protocol = {
        "schema_version": SCHEMA_VERSION,
        "prepared_at": utc_now(),
        "dataset_id": manifest["dataset_id"],
        "dataset_manifest_file_sha256": sha256_file(dataset_dir / "source-manifest.json"),
        "dataset_manifest_receipt_binding_sha256": receipt["source_manifest_sha256"],
        "dataset_verification_receipt_sha256": sha256_file(dataset_dir / "verification-receipt.json"),
        "dataset_duration_hours": receipt["coverage"]["total_duration_hours"],
        "program_completeness_claim": receipt["coverage"]["whole_game_claim"],
        "experimental_split": {key: sorted(value) for key, value in split_games.items()},
        "split_unit": "game_id",
        "windows": {
            "durations_seconds": list(WINDOW_DURATIONS),
            "frames_per_window": FRAMES_PER_WINDOW,
            "counts": dict(Counter(window.split for window in windows)),
            "test_counts_by_duration": {
                str(duration): sum(1 for window in windows if window.split == "test" and window.duration_seconds == duration)
                for duration in WINDOW_DURATIONS
            },
        },
        "model_input_contract": {
            "modalities": ["ordered_silent_video_frames", "protocol_text"],
            "audio": "excluded",
            "commentary": "excluded",
            "filenames_titles_team_names_rosters_split_labels": "excluded",
            "visible_scoreboard_text": "allowed_because_it_is_in_pixels",
        },
        "claims": {
            "model_fine_tuning": False,
            "ground_truth_annotations": False,
            "coach_validated": False,
            "performance_claim_allowed": False,
            "test_outputs_measure": "schema_behavior_abstention_and_searchability_not_event_accuracy",
        },
        "files": {
            "window_manifest_sha256": sha256_file(windows_path),
            "query_set_sha256": sha256_file(query_path),
            "prompt_candidates_sha256": sha256_file(prompt_path),
        },
    }
    amendment_path = output_dir / "protocol-amendments.jsonl"
    if amendment_path.is_file():
        protocol["protocol_amendments_sha256"] = sha256_file(amendment_path)
    write_json(output_dir / "protocol.json", protocol)
    return protocol


def load_windows(path: Path) -> list[Window]:
    windows: list[Window] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            windows.append(Window(**item))
    return windows


def report_json_schema(frame_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "football_visual_report",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "schema_version": {"type": "string", "const": REPORT_VERSION},
                    "visual_only": {"type": "boolean", "const": True},
                    "abstain": {"type": "boolean"},
                    "abstention_reason": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "window_summary": {"type": "string"},
                    "events": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
                                "start_frame_id": {"type": "string", "enum": list(frame_ids)},
                                "end_frame_id": {"type": "string", "enum": list(frame_ids)},
                                "action": {"type": "string"},
                                "outcome": {"type": "string"},
                                "actors_visible": {"type": "array", "items": {"type": "string"}},
                                "field_context": {"type": "string"},
                                "evidence_frame_ids": {
                                    "type": "array",
                                    "items": {"type": "string", "enum": list(frame_ids)},
                                },
                                "uncertainties": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "event_type",
                                "start_frame_id",
                                "end_frame_id",
                                "action",
                                "outcome",
                                "actors_visible",
                                "field_context",
                                "evidence_frame_ids",
                                "uncertainties",
                            ],
                        },
                    },
                    "formations_and_tactics": {"type": "array", "items": {"type": "string"}},
                    "coach_search_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "schema_version",
                    "visual_only",
                    "abstain",
                    "abstention_reason",
                    "confidence",
                    "window_summary",
                    "events",
                    "formations_and_tactics",
                    "coach_search_terms",
                ],
            },
        },
    }


def extract_frames(media_path: Path, window: Window, frame_dir: Path, count: int = FRAMES_PER_WINDOW) -> list[dict[str, Any]]:
    try:
        import cv2  # type: ignore
    except ImportError as error:
        raise RuntimeError("opencv-python is required for frame extraction") from error
    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video stream: {media_path}")
    frame_dir.mkdir(parents=True, exist_ok=True)
    offsets = [(index + 0.5) * window.duration_seconds / count for index in range(count)]
    frames: list[dict[str, Any]] = []
    try:
        for index, offset in enumerate(offsets):
            absolute = window.start_seconds + offset
            capture.set(cv2.CAP_PROP_POS_MSEC, absolute * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError(f"frame decode failed at {absolute:.3f}s")
            frame_id = f"F{index:02d}"
            frame_path = frame_dir / f"{frame_id}.jpg"
            encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            if not encoded_ok:
                raise RuntimeError(f"JPEG encode failed for {frame_id}")
            data = encoded.tobytes()
            frame_path.write_bytes(data)
            frames.append(
                {
                    "frame_id": frame_id,
                    "relative_seconds": round(offset, 3),
                    "absolute_seconds_private_receipt": round(absolute, 3),
                    "path": str(frame_path),
                    "sha256": sha256_bytes(data),
                    "bytes": len(data),
                    "data": data,
                }
            )
    finally:
        capture.release()
    return frames


def model_identity(endpoint: str, timeout_seconds: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(endpoint.rstrip("/") + "/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
    parsed = json.loads(raw)
    return {"response": parsed, "response_sha256": sha256_bytes(raw), "captured_at": utc_now()}


def build_request(
    model: str,
    prompt_text: str,
    window: Window,
    frames: Sequence[dict[str, Any]],
    use_response_format: bool = True,
    max_tokens: int = 2200,
    compact_fallback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    frame_legend = ", ".join(f"{item['frame_id']}=+{item['relative_seconds']:.3f}s" for item in frames)
    text = (
        f"{prompt_text}\n\nWindow duration: {window.duration_seconds} seconds. "
        f"Ordered frame legend: {frame_legend}. Multiple plays may occur between sparse frames. "
        "Do not infer continuity that the samples do not show."
    )
    if compact_fallback and not use_response_format:
        text += (
            " Return one compact JSON object with exactly these top-level keys: "
            "schema_version, visual_only, abstain, abstention_reason, confidence, window_summary, "
            "events, formations_and_tactics, coach_search_terms. Each event must have exactly: "
            "event_type, start_frame_id, end_frame_id, action, outcome, actors_visible, "
            "field_context, evidence_frame_ids, uncertainties. Use schema_version "
            f"{REPORT_VERSION}. Keep strings concise so the JSON closes within the response budget."
        )
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for item in frames:
        encoded = base64.b64encode(item["data"]).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}})
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You produce evidence-bounded structured reports from silent American-football frames.",
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if use_response_format:
        payload["response_format"] = report_json_schema([item["frame_id"] for item in frames])
    receipt_payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
        "prompt_text": text,
        "response_format": payload.get("response_format"),
        "frames": [
            {
                "frame_id": item["frame_id"],
                "relative_seconds": item["relative_seconds"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
            }
            for item in frames
        ],
        "input_modalities": ["text_protocol", "silent_jpeg_frames"],
        "audio_used": False,
        "metadata_fields_used": [],
    }
    return payload, receipt_payload


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], bytes, dict[str, str]]:
    body = canonical_json(payload)
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        raw_error = error.read()
        raise RuntimeError(f"HTTP {error.code}: {raw_error[:2000].decode('utf-8', errors='replace')}") from error
    return json.loads(raw), raw, headers


def completion_text(envelope: dict[str, Any]) -> str:
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    raise ValueError("response content is not text")


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        left, right = cleaned.find("{"), cleaned.rfind("}")
        if left < 0 or right <= left:
            raise
        value = json.loads(cleaned[left : right + 1])
    if not isinstance(value, dict):
        raise ValueError("completion JSON is not an object")
    return value


def validate_report(report: dict[str, Any], frame_ids: Sequence[str]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "visual_only",
        "abstain",
        "abstention_reason",
        "confidence",
        "window_summary",
        "events",
        "formations_and_tactics",
        "coach_search_terms",
    }
    missing = sorted(required - set(report))
    if missing:
        errors.append("missing:" + ",".join(missing))
    if report.get("schema_version") != REPORT_VERSION:
        errors.append("schema_version")
    if report.get("visual_only") is not True:
        errors.append("visual_only")
    if report.get("confidence") not in {"low", "medium", "high"}:
        errors.append("confidence")
    if not isinstance(report.get("abstain"), bool):
        errors.append("abstain")
    if report.get("abstain") is True and not str(report.get("abstention_reason", "")).strip():
        errors.append("abstention_reason")
    events = report.get("events")
    if not isinstance(events, list):
        errors.append("events_not_list")
        events = []
    allowed_frames = set(frame_ids)
    for index, event in enumerate(events):
        prefix = f"event[{index}]"
        if not isinstance(event, dict):
            errors.append(prefix + "_not_object")
            continue
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(prefix + "_event_type")
        for field in ("start_frame_id", "end_frame_id"):
            if event.get(field) not in allowed_frames:
                errors.append(prefix + "_" + field)
        evidence = event.get("evidence_frame_ids")
        if not isinstance(evidence, list) or not evidence or any(item not in allowed_frames for item in evidence):
            errors.append(prefix + "_evidence")
        for field in ("actors_visible", "uncertainties"):
            if not isinstance(event.get(field), list):
                errors.append(prefix + "_" + field)
    for field in ("formations_and_tactics", "coach_search_terms"):
        if not isinstance(report.get(field), list):
            errors.append(field)
    return errors


def _failure_report(reason: str) -> dict[str, Any]:
    return {
        "schema_version": REPORT_VERSION,
        "visual_only": True,
        "abstain": True,
        "abstention_reason": reason,
        "confidence": "low",
        "window_summary": "No valid structured report was produced.",
        "events": [],
        "formations_and_tactics": [],
        "coach_search_terms": ["unresolved visual window"],
    }


def run_one(
    project_root: Path,
    output_dir: Path,
    window: Window,
    prompt_id: str,
    prompt_text: str,
    endpoint: str,
    model: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    result_dir = output_dir / "runs" / prompt_id / window.window_id
    result_dir.mkdir(parents=True, exist_ok=True)
    final_receipt_path = result_dir / "receipt.json"
    max_tokens = PROMPT_MAX_TOKENS[prompt_id]
    request_policy_id = PROMPT_REQUEST_POLICY[prompt_id]
    if final_receipt_path.is_file():
        prior = read_json(final_receipt_path)
        expected_prompt_hash = sha256_bytes(prompt_text.encode("utf-8"))
        if prior.get("prompt_sha256") != expected_prompt_hash or prior.get("model") != model:
            raise RuntimeError(f"cached call identity changed for {window.window_id}; use a new prompt ID")
        prior_policy = prior.get("request_policy_id", "structured-v1")
        prior_max_tokens = int(prior.get("max_tokens", 2200))
        if prior_policy != request_policy_id or prior_max_tokens != max_tokens:
            raise RuntimeError(f"cached request policy changed for {window.window_id}; use a new prompt ID")
        if prior.get("status") in {"complete", "abstained"}:
            return prior

    media_path = project_root / window.media_path
    frames = extract_frames(media_path, window, result_dir / "frames")
    if request_policy_id == "structured-3200-compact-recovery-v2":
        strategies = (
            ("structured_eight_frames_3200", True, frames, False),
            ("structured_four_frames_3200", True, frames[::2], False),
            ("plain_json_four_frames_compact_3200", False, frames[::2], True),
        )
    else:
        strategies = (
            ("structured_eight_frames", True, frames, False),
            ("plain_json_eight_frames", False, frames, False),
            ("plain_json_four_frames", False, frames[::2], False),
        )
    attempt_records: list[dict[str, Any]] = []
    final_report: dict[str, Any] | None = None
    final_envelope: dict[str, Any] | None = None
    final_raw: bytes | None = None
    final_validation: list[str] = []
    selected_strategy = "none"
    for strategy_id, structured, attempt_frames, compact_fallback in strategies:
        payload, request_receipt = build_request(
            model,
            prompt_text,
            window,
            attempt_frames,
            structured,
            max_tokens,
            compact_fallback,
        )
        request_receipt["strategy_id"] = strategy_id
        request_receipt["request_policy_id"] = request_policy_id
        request_receipt["request_without_image_bytes_sha256"] = sha256_bytes(canonical_json(request_receipt))
        started = time.perf_counter()
        attempt: dict[str, Any] = {"strategy_id": strategy_id, "started_at": utc_now()}
        try:
            envelope, raw, headers = _post_json(
                endpoint.rstrip("/") + "/chat/completions", payload, timeout_seconds
            )
            elapsed = time.perf_counter() - started
            text = completion_text(envelope)
            parsed = parse_json_text(text)
            validation = validate_report(parsed, [item["frame_id"] for item in attempt_frames])
            attempt.update(
                {
                    "status": "valid" if not validation else "invalid_schema",
                    "elapsed_seconds": elapsed,
                    "raw_response_sha256": sha256_bytes(raw),
                    "completion_text_sha256": sha256_bytes(text.encode("utf-8")),
                    "validation_errors": validation,
                    "response_headers": {
                        key: value for key, value in headers.items() if key in {"content-type", "content-length"}
                    },
                    "request_receipt": request_receipt,
                }
            )
            attempt_path = result_dir / f"attempt-{len(attempt_records) + 1}.json"
            write_json(attempt_path, {"attempt": attempt, "envelope": envelope})
            attempt_records.append(attempt)
            if not validation:
                final_report, final_envelope, final_raw = parsed, envelope, raw
                final_validation = validation
                selected_strategy = strategy_id
                break
        except Exception as error:  # persisted and followed by a materially different strategy
            elapsed = time.perf_counter() - started
            attempt.update(
                {
                    "status": "error",
                    "elapsed_seconds": elapsed,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "error_fingerprint": sha256_bytes(f"{type(error).__name__}|{error}".encode("utf-8")),
                    "request_receipt": request_receipt,
                }
            )
            write_json(result_dir / f"attempt-{len(attempt_records) + 1}.json", {"attempt": attempt})
            attempt_records.append(attempt)

    if final_report is None:
        final_report = _failure_report("All predeclared local-model strategies failed or returned invalid JSON.")
        final_validation = ["model_output_unusable"]
    raw_path = result_dir / "raw-response.json"
    if final_envelope is not None and final_raw is not None:
        raw_path.write_bytes(final_raw)
    else:
        write_json(raw_path, {"error": "no valid raw response", "attempts": len(attempt_records)})
    normalized = {
        "schema_version": "footballmaster-normalized-window-v2",
        "window": window.as_dict(),
        "prompt_id": prompt_id,
        "model": model,
        "report": final_report,
        "validation_errors": final_validation,
        "valid": not final_validation,
    }
    normalized_path = result_dir / "normalized-report.json"
    write_json(normalized_path, normalized)
    frame_receipts = [
        {key: item[key] for key in ("frame_id", "relative_seconds", "absolute_seconds_private_receipt", "sha256", "bytes")}
        for item in frames
    ]
    receipt = {
        "schema_version": "footballmaster-vlm-call-receipt-v2",
        "status": "complete" if not final_report.get("abstain") else "abstained",
        "completed_at": utc_now(),
        "window_id": window.window_id,
        "asset_id": window.asset_id,
        "game_id": window.game_id,
        "split": window.split,
        "media_sha256": window.media_sha256,
        "prompt_id": prompt_id,
        "prompt_sha256": sha256_bytes(prompt_text.encode("utf-8")),
        "request_policy_id": request_policy_id,
        "max_tokens": max_tokens,
        "model": model,
        "endpoint_origin": endpoint,
        "input_contract": {
            "audio_used": False,
            "commentary_used": False,
            "source_metadata_in_prompt": False,
            "ordered_frames": frame_receipts,
        },
        "attempt_count": len(attempt_records),
        "attempts": attempt_records,
        "selected_strategy": selected_strategy,
        "raw_response_sha256": sha256_file(raw_path),
        "normalized_report_sha256": sha256_file(normalized_path),
        "total_elapsed_seconds": sum(item.get("elapsed_seconds", 0.0) for item in attempt_records),
        "valid": not final_validation,
        "abstain": bool(final_report.get("abstain")),
        "validation_errors": final_validation,
    }
    write_json(final_receipt_path, receipt)
    return receipt


def score_validation_receipts(output_dir: Path, prompt_id: str, windows: Sequence[Window]) -> dict[str, Any]:
    valid_windows = [window for window in windows if window.split == "valid"]
    receipts: list[dict[str, Any]] = []
    evidence_events = 0
    total_events = 0
    unsupported_claim_risk_count = 0
    frame_fragmentation_count = 0
    for window in valid_windows:
        base = output_dir / "runs" / prompt_id / window.window_id
        receipt = read_json(base / "receipt.json")
        report = read_json(base / "normalized-report.json")["report"]
        receipts.append(receipt)
        report_events = report.get("events", [])
        single_frame_events = 0
        for event in report_events:
            action = str(event.get("action", "")).strip().lower()
            outcome = str(event.get("outcome", "")).strip().lower()
            event_type = str(event.get("event_type", ""))
            evidence = event.get("evidence_frame_ids", [])
            if (
                event.get("start_frame_id") == event.get("end_frame_id")
                and isinstance(evidence, list)
                and len(evidence) == 1
            ):
                single_frame_events += 1
            if event_type in {"scoring", "turnover"} and (
                action in {"play", "action", "unknown", ""} or outcome in {"unknown", "n/a", ""}
            ):
                unsupported_claim_risk_count += 1
            if event_type in {"pass_play", "run_play", "kick_play"} and action in {
                "play",
                "action",
                "unknown",
                "",
            }:
                unsupported_claim_risk_count += 1
        if len(report_events) >= 6 and single_frame_events / len(report_events) >= 0.75:
            frame_fragmentation_count += 1
        for event in report.get("events", []):
            total_events += 1
            if event.get("evidence_frame_ids"):
                evidence_events += 1
    valid_count = sum(bool(item.get("valid")) for item in receipts)
    abstain_count = sum(bool(item.get("abstain")) for item in receipts)
    mean_seconds = sum(float(item.get("total_elapsed_seconds", 0.0)) for item in receipts) / max(1, len(receipts))
    # This remains a label-free proxy. Validity/evidence dominate, while visible
    # unsupported-claim and per-frame-fragmentation risks receive fixed penalties.
    score = (
        valid_count * 100.0
        + evidence_events * 2.0
        - max(0, total_events - evidence_events) * 5.0
        - unsupported_claim_risk_count * 20.0
        - frame_fragmentation_count * 15.0
        - mean_seconds * 0.001
    )
    return {
        "prompt_id": prompt_id,
        "validation_window_count": len(receipts),
        "valid_count": valid_count,
        "abstain_count": abstain_count,
        "event_count": total_events,
        "events_with_frame_evidence": evidence_events,
        "unsupported_claim_risk_count": unsupported_claim_risk_count,
        "frame_fragmentation_window_count": frame_fragmentation_count,
        "mean_elapsed_seconds": mean_seconds,
        "structural_score": score,
        "accuracy_or_correctness_measured": False,
    }


def run_prompt_selection(
    project_root: Path,
    output_dir: Path,
    endpoint: str,
    model: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    protocol = read_json(output_dir / "protocol.json")
    windows = load_windows(output_dir / "window-manifest.jsonl")
    identity = model_identity(endpoint)
    model_ids = {item.get("id") or item.get("model") or item.get("name") for item in identity["response"].get("data", [])}
    if model not in model_ids:
        model_ids.update(item.get("model") or item.get("name") for item in identity["response"].get("models", []))
    if model not in model_ids:
        raise ValueError(f"requested model is not loaded: {model}; observed={sorted(item for item in model_ids if item)}")
    write_json(output_dir / "model-identity.json", identity)

    train_anchors = [
        window
        for window in windows
        if window.split == "train" and window.duration_seconds == 60 and window.fraction_index == 1
    ]
    validation_windows = [window for window in windows if window.split == "valid"]
    for prompt_id, prompt_text in PROMPT_CANDIDATES.items():
        for window in train_anchors:
            run_one(project_root, output_dir, window, prompt_id, prompt_text, endpoint, model, timeout_seconds)
        for window in validation_windows:
            run_one(project_root, output_dir, window, prompt_id, prompt_text, endpoint, model, timeout_seconds)
    # The amended intensive protocol fills every candidate's complete training
    # grid before validation-only selection. This locks an exact development
    # denominator and leaves no candidate with only anchor-level evidence.
    for prompt_id, prompt_text in PROMPT_CANDIDATES.items():
        for window in [item for item in windows if item.split == "train"]:
            run_one(project_root, output_dir, window, prompt_id, prompt_text, endpoint, model, timeout_seconds)
    scores = [score_validation_receipts(output_dir, prompt_id, windows) for prompt_id in PROMPT_CANDIDATES]
    selected = max(scores, key=lambda item: (item["structural_score"], item["prompt_id"]))["prompt_id"]
    selected_text = PROMPT_CANDIDATES[selected]
    selection = {
        "schema_version": "footballmaster-prompt-selection-v2",
        "selected_at": utc_now(),
        "selected_prompt_id": selected,
        "selected_prompt_sha256": sha256_bytes(selected_text.encode("utf-8")),
        "selection_basis": "locked label-free validation proxy: schema validity, frame evidence, unsupported-claim risk, frame fragmentation, then latency tie-break",
        "correctness_or_event_accuracy_used": False,
        "parameter_fine_tuning": False,
        "training_game_use": "candidate runtime and visible-grounding behavior checked on training anchors; selected candidate then indexed all training windows",
        "validation_game_use": "prompt selected using locked label-free schema, evidence, and visible-risk proxies; no correctness labels",
        "test_game_use": "none",
        "candidate_scores": scores,
        "candidate_count": len(PROMPT_CANDIDATES),
        "development_call_denominator": 108,
    }
    write_json(output_dir / "prompt-selection.json", selection)
    freeze = {
        "schema_version": "footballmaster-frozen-test-config-v2",
        "frozen_at": utc_now(),
        "protocol_sha256": sha256_file(output_dir / "protocol.json"),
        "window_manifest_sha256": sha256_file(output_dir / "window-manifest.jsonl"),
        "query_set_sha256": sha256_file(output_dir / "frozen-query-set.json"),
        "prompt_candidates_sha256": sha256_file(output_dir / "prompt-candidates.json"),
        "prompt_selection_sha256": sha256_file(output_dir / "prompt-selection.json"),
        "model_identity_sha256": sha256_file(output_dir / "model-identity.json"),
        "model": model,
        "endpoint": endpoint,
        "selected_prompt_id": selected,
        "selected_prompt_sha256": selection["selected_prompt_sha256"],
        "selected_max_tokens": PROMPT_MAX_TOKENS[selected],
        "selected_request_policy_id": PROMPT_REQUEST_POLICY[selected],
        "planned_total_vlm_call_denominator": 144,
        "test_game_ids": protocol["experimental_split"]["test"],
        "test_window_count": sum(1 for window in windows if window.split == "test"),
        "test_labels_available": False,
        "input_audio": False,
    }
    amendment_path = output_dir / "protocol-amendments.jsonl"
    if amendment_path.is_file():
        freeze["protocol_amendments_sha256"] = sha256_file(amendment_path)
    write_json(output_dir / "frozen-test-config.json", freeze)
    return selection


def verify_freeze(output_dir: Path) -> dict[str, Any]:
    freeze = read_json(output_dir / "frozen-test-config.json")
    mappings = {
        "protocol_sha256": output_dir / "protocol.json",
        "window_manifest_sha256": output_dir / "window-manifest.jsonl",
        "query_set_sha256": output_dir / "frozen-query-set.json",
        "prompt_candidates_sha256": output_dir / "prompt-candidates.json",
        "prompt_selection_sha256": output_dir / "prompt-selection.json",
        "model_identity_sha256": output_dir / "model-identity.json",
    }
    if "protocol_amendments_sha256" in freeze:
        mappings["protocol_amendments_sha256"] = output_dir / "protocol-amendments.jsonl"
    for field, path in mappings.items():
        if sha256_file(path) != freeze.get(field):
            raise ValueError(f"frozen file changed after selection: {path}")
    prompt_id = freeze["selected_prompt_id"]
    if sha256_bytes(PROMPT_CANDIDATES[prompt_id].encode("utf-8")) != freeze["selected_prompt_sha256"]:
        raise ValueError("selected prompt code changed after freeze")
    if PROMPT_MAX_TOKENS[prompt_id] != freeze.get("selected_max_tokens"):
        raise ValueError("selected response budget changed after freeze")
    if PROMPT_REQUEST_POLICY[prompt_id] != freeze.get("selected_request_policy_id"):
        raise ValueError("selected request recovery policy changed after freeze")
    return freeze


def run_test(
    project_root: Path,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    freeze = verify_freeze(output_dir)
    windows = load_windows(output_dir / "window-manifest.jsonl")
    prompt_id = freeze["selected_prompt_id"]
    prompt_text = PROMPT_CANDIDATES[prompt_id]
    test_windows = [window for window in windows if window.split == "test"]
    if {window.game_id for window in test_windows} != set(freeze["test_game_ids"]):
        raise ValueError("test game set differs from frozen configuration")
    receipts = [
        run_one(
            project_root,
            output_dir,
            window,
            prompt_id,
            prompt_text,
            freeze["endpoint"],
            freeze["model"],
            timeout_seconds,
        )
        for window in test_windows
    ]
    summary = summarize_reports(output_dir, windows, prompt_id)
    write_json(output_dir / "report-metrics.json", summary)
    build_search_index(output_dir, windows, prompt_id)
    run_frozen_queries(output_dir)
    persist_failures_and_abstentions(output_dir, windows, prompt_id)
    return {
        "test_window_count": len(receipts),
        "valid": sum(bool(item.get("valid")) for item in receipts),
        "abstained": sum(bool(item.get("abstain")) for item in receipts),
    }


def summarize_reports(output_dir: Path, windows: Sequence[Window], prompt_id: str) -> dict[str, Any]:
    rows: list[tuple[Window, dict[str, Any], dict[str, Any]]] = []
    for window in windows:
        base = output_dir / "runs" / prompt_id / window.window_id
        if not (base / "receipt.json").is_file():
            continue
        rows.append((window, read_json(base / "receipt.json"), read_json(base / "normalized-report.json")["report"]))
    split_counts: dict[str, Any] = {}
    for split in ("train", "valid", "test"):
        subset = [item for item in rows if item[0].split == split]
        split_counts[split] = {
            "denominator": len(subset),
            "valid": sum(bool(item[1].get("valid")) for item in subset),
            "abstained": sum(bool(item[1].get("abstain")) for item in subset),
            "events_reported": sum(len(item[2].get("events", [])) for item in subset),
            "mean_elapsed_seconds": (
                sum(float(item[1].get("total_elapsed_seconds", 0.0)) for item in subset) / len(subset)
                if subset
                else None
            ),
        }
    test_duration = {}
    for duration in WINDOW_DURATIONS:
        subset = [item for item in rows if item[0].split == "test" and item[0].duration_seconds == duration]
        test_duration[str(duration)] = {
            "denominator": len(subset),
            "valid": sum(bool(item[1].get("valid")) for item in subset),
            "abstained": sum(bool(item[1].get("abstain")) for item in subset),
            "events_reported": sum(len(item[2].get("events", [])) for item in subset),
        }
    event_histogram = Counter(
        event.get("event_type", "unknown")
        for window, _, report in rows
        if window.split == "test"
        for event in report.get("events", [])
    )
    test_rows = [item for item in rows if item[0].split == "test"]
    abstain_with_events = [
        {
            "window_id": window.window_id,
            "game_id": window.game_id,
            "duration_seconds": window.duration_seconds,
            "event_count": len(report.get("events", [])),
        }
        for window, _, report in test_rows
        if report.get("abstain") is True and len(report.get("events", [])) > 0
    ]
    unsupported_scoring_cases = []
    scoring_evidence_terms = {
        "touchdown",
        "score",
        "scoring signal",
        "goal line",
        "end zone",
        "points",
        "field goal",
        "extra point",
        "celebration",
        "scoreboard",
    }
    for window, _, report in test_rows:
        for event_index, event in enumerate(report.get("events", [])):
            if not isinstance(event, dict) or event.get("event_type") != "scoring":
                continue
            action = str(event.get("action", "")).strip().lower()
            outcome = str(event.get("outcome", "")).strip().lower()
            field_context = str(event.get("field_context", "")).strip().lower()
            evidence = event.get("evidence_frame_ids", [])
            report_text = " ".join((action, outcome, field_context))
            if not any(term in report_text for term in scoring_evidence_terms):
                unsupported_scoring_cases.append(
                    {
                        "window_id": window.window_id,
                        "game_id": window.game_id,
                        "duration_seconds": window.duration_seconds,
                        "event_index": event_index,
                        "action": event.get("action"),
                        "outcome": event.get("outcome"),
                        "field_context": event.get("field_context"),
                        "evidence_frame_ids": evidence,
                        "reason": "scoring type has no explicit scoring-evidence term in its saved action/outcome/field context",
                    }
                )
    failure_ids = [window.window_id for window, receipt, _ in test_rows if not receipt.get("valid")]
    return {
        "schema_version": "footballmaster-report-metrics-v2",
        "generated_at": utc_now(),
        "denominator_definition": "deterministic game-held-out time windows submitted to the silent-frame VLM",
        "split_counts": split_counts,
        "test_by_duration_seconds": test_duration,
        "test_event_type_histogram_model_outputs_not_truth": dict(event_histogram),
        "test_semantic_contract": {
            "status": "NO-GO",
            "denominator": len(test_rows),
            "valid_json_count": sum(bool(item[1].get("valid")) for item in test_rows),
            "failure_count": len(failure_ids),
            "failure_window_ids": failure_ids,
            "abstain_count": sum(bool(item[2].get("abstain")) for item in test_rows),
            "abstain_with_nonempty_events_count": len(abstain_with_events),
            "abstain_with_nonempty_events": abstain_with_events,
            "unsupported_scoring_event_count": len(unsupported_scoring_cases),
            "unsupported_scoring_window_count": len(
                {item["window_id"] for item in unsupported_scoring_cases}
            ),
            "unsupported_scoring_cases": unsupported_scoring_cases,
            "reasons": [
                "abstention is logically inconsistent with nonempty asserted events",
                "generic or unknown action/outcome is repeatedly assigned the high-stakes scoring type",
                "no human-adjudicated event truth exists for accuracy measurement",
            ],
        },
        "event_accuracy_measured": False,
        "ground_truth_available": False,
        "performance_claim_allowed": False,
    }


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def report_search_text(report: dict[str, Any]) -> str:
    parts = [str(report.get("window_summary", ""))]
    parts.extend(str(item) for item in report.get("formations_and_tactics", []))
    parts.extend(str(item) for item in report.get("coach_search_terms", []))
    for event in report.get("events", []):
        if isinstance(event, dict):
            for field in ("event_type", "action", "outcome", "field_context"):
                parts.append(str(event.get(field, "")))
            parts.extend(str(item) for item in event.get("actors_visible", []))
            parts.extend(str(item) for item in event.get("uncertainties", []))
    if report.get("abstain"):
        parts.append(str(report.get("abstention_reason", "")))
    return " ".join(parts)


def build_search_index(output_dir: Path, windows: Sequence[Window], prompt_id: str) -> dict[str, Any]:
    index_path = output_dir / "football-search-index.jsonl"
    reset_jsonl(index_path)
    entries: list[dict[str, Any]] = []
    for window in windows:
        if window.split != "test":
            continue
        normalized_path = output_dir / "runs" / prompt_id / window.window_id / "normalized-report.json"
        if not normalized_path.is_file():
            continue
        normalized = read_json(normalized_path)
        report = normalized["report"]
        entry = {
            "schema_version": "footballmaster-search-entry-v2",
            "window_id": window.window_id,
            "game_id": window.game_id,
            "split": window.split,
            "start_seconds": window.start_seconds,
            "duration_seconds": window.duration_seconds,
            "media_path": window.media_path,
            "media_sha256": window.media_sha256,
            "visual_report_sha256": sha256_file(normalized_path),
            "abstain": bool(report.get("abstain")),
            "confidence": report.get("confidence"),
            "search_text": report_search_text(report),
            "report": report,
        }
        append_jsonl(index_path, entry)
        entries.append(entry)
    receipt = {
        "schema_version": "footballmaster-search-index-receipt-v2",
        "entry_count": len(entries),
        "game_count": len({item["game_id"] for item in entries}),
        "durations_seconds": sorted({item["duration_seconds"] for item in entries}),
        "index_sha256": sha256_file(index_path),
        "source": "silent_frame_vlm_reports_only",
        "relevance_ground_truth": False,
    }
    write_json(output_dir / "football-search-index-receipt.json", receipt)
    return receipt


def load_index(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bm25_search(entries: Sequence[dict[str, Any]], query: str, limit: int = 5) -> list[dict[str, Any]]:
    documents = [tokenize(str(entry.get("search_text", ""))) for entry in entries]
    query_terms = tokenize(query)
    if not documents or not query_terms:
        return []
    document_frequency = Counter(term for document in documents for term in set(document))
    average_length = sum(len(document) for document in documents) / len(documents)
    k1, b = 1.5, 0.75
    scored: list[tuple[float, int]] = []
    for index, document in enumerate(documents):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            df = document_frequency.get(term, 0)
            if not df:
                continue
            inverse = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
            frequency = frequencies[term]
            denominator = frequency + k1 * (1.0 - b + b * len(document) / max(1.0, average_length))
            score += inverse * frequency * (k1 + 1.0) / denominator
        scored.append((score, index))
    scored.sort(key=lambda item: (-item[0], entries[item[1]]["window_id"]))
    results = []
    for rank, (score, index) in enumerate(scored[:limit], start=1):
        entry = entries[index]
        results.append(
            {
                "rank": rank,
                "score": score,
                "window_id": entry["window_id"],
                "game_id": entry["game_id"],
                "start_seconds": entry["start_seconds"],
                "duration_seconds": entry["duration_seconds"],
                "abstain": entry["abstain"],
                "confidence": entry["confidence"],
                "summary": entry["report"].get("window_summary", ""),
            }
        )
    return results


def run_frozen_queries(output_dir: Path) -> dict[str, Any]:
    query_set = read_json(output_dir / "frozen-query-set.json")
    entries = load_index(output_dir / "football-search-index.jsonl")
    results = []
    for query in query_set["queries"]:
        top = bm25_search(entries, query["text"], limit=5)
        results.append({**query, "candidate_count": len(top), "top_results": top})
    packet = {
        "schema_version": "footballmaster-frozen-query-results-v2",
        "generated_at": utc_now(),
        "query_set_sha256": sha256_file(output_dir / "frozen-query-set.json"),
        "index_sha256": sha256_file(output_dir / "football-search-index.jsonl"),
        "query_count": len(results),
        "index_entry_count": len(entries),
        "index_game_count": len({item["game_id"] for item in entries}),
        "index_durations_seconds": sorted({item["duration_seconds"] for item in entries}),
        "accuracy_or_relevance_measured": False,
        "results": results,
    }
    write_json(output_dir / "frozen-query-results.json", packet)
    return packet


def persist_failures_and_abstentions(
    output_dir: Path, windows: Sequence[Window], prompt_id: str
) -> tuple[int, int]:
    failures_path = output_dir / "failures.jsonl"
    abstentions_path = output_dir / "abstentions.jsonl"
    reset_jsonl(failures_path)
    reset_jsonl(abstentions_path)
    failures = abstentions = 0
    for window in windows:
        if window.split != "test":
            continue
        base = output_dir / "runs" / prompt_id / window.window_id
        receipt = read_json(base / "receipt.json")
        normalized = read_json(base / "normalized-report.json")
        if not receipt.get("valid"):
            failures += 1
            append_jsonl(
                failures_path,
                {
                    "window_id": window.window_id,
                    "game_id": window.game_id,
                    "duration_seconds": window.duration_seconds,
                    "validation_errors": receipt.get("validation_errors", []),
                    "attempts": receipt.get("attempts", []),
                },
            )
        if normalized["report"].get("abstain"):
            abstentions += 1
            append_jsonl(
                abstentions_path,
                {
                    "window_id": window.window_id,
                    "game_id": window.game_id,
                    "duration_seconds": window.duration_seconds,
                    "reason": normalized["report"].get("abstention_reason", ""),
                    "valid": receipt.get("valid"),
                },
            )
    return failures, abstentions


def _dominant_weak_label(report: dict[str, Any]) -> str | None:
    if report.get("abstain"):
        return None
    mapping = {"pass_play": "pass", "run_play": "run", "kick_play": "kick"}
    for event in report.get("events", []):
        label = mapping.get(event.get("event_type"))
        if label:
            return label
    return "other"


def _backbone_features(backbone: Path, frame_paths: Sequence[Path]) -> list[float]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import onnxruntime as ort  # type: ignore
    except ImportError as error:
        raise RuntimeError("numpy, opencv-python, and onnxruntime are required for the weak probe") from error
    session = ort.InferenceSession(str(backbone), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    outputs = []
    for path in frame_paths:
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"could not load sampled frame: {path}")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (224, 224)).astype("float32") / 255.0
        image = (image - np.array([0.485, 0.456, 0.406], dtype="float32")) / np.array(
            [0.229, 0.224, 0.225], dtype="float32"
        )
        tensor = np.transpose(image, (2, 0, 1))[None, ...].astype("float32")
        output = session.run(None, {input_name: tensor})[0][0]
        outputs.append(output)
    return np.mean(np.stack(outputs), axis=0).astype("float32").tolist()


def train_weak_probe(output_dir: Path, backbone: Path) -> dict[str, Any]:
    import numpy as np  # type: ignore

    freeze = verify_freeze(output_dir)
    primary_prompt_id = freeze["selected_prompt_id"]
    prompt_id = "candidate_c_event_guarded_3200"
    windows = load_windows(output_dir / "window-manifest.jsonl")
    rows: list[dict[str, Any]] = []
    cache_dir = output_dir / "weak-probe-features"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for window in windows:
        base = output_dir / "runs" / prompt_id / window.window_id
        normalized_path = base / "normalized-report.json"
        if not normalized_path.is_file():
            continue
        report = read_json(normalized_path)["report"]
        weak_label = _dominant_weak_label(report)
        if weak_label is None:
            continue
        cache_path = cache_dir / f"{window.window_id}.json"
        if cache_path.is_file():
            cached = read_json(cache_path)
            feature = cached["feature"]
        else:
            frame_paths = sorted((base / "frames").glob("F*.jpg"))
            feature = _backbone_features(backbone, frame_paths)
            write_json(
                cache_path,
                {
                    "window_id": window.window_id,
                    "backbone_sha256": sha256_file(backbone),
                    "frame_sha256s": [sha256_file(path) for path in frame_paths],
                    "feature": feature,
                },
            )
        rows.append({"window": window, "weak_label": weak_label, "feature": feature})
    train_rows = [row for row in rows if row["window"].split == "train"]
    labels = sorted({row["weak_label"] for row in train_rows})
    if len(labels) < 2:
        raise ValueError(f"weak VLM labels contain fewer than two train classes: {labels}")
    x_train = np.asarray([row["feature"] for row in train_rows], dtype="float64")
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale < 1e-8] = 1.0
    x_train = (x_train - mean) / scale
    x_train = np.concatenate([x_train, np.ones((x_train.shape[0], 1))], axis=1)
    y_train = np.zeros((len(train_rows), len(labels)), dtype="float64")
    label_to_index = {label: index for index, label in enumerate(labels)}
    for row_index, row in enumerate(train_rows):
        y_train[row_index, label_to_index[row["weak_label"]]] = 1.0
    regularization = 1.0
    dual = np.linalg.solve(x_train @ x_train.T + regularization * np.eye(len(train_rows)), y_train)
    weights = x_train.T @ dual
    checkpoint = output_dir / "weak-visual-probe.npz"
    np.savez_compressed(checkpoint, mean=mean, scale=scale, weights=weights, labels=np.asarray(labels))

    predictions = []
    for row in rows:
        feature = (np.asarray(row["feature"], dtype="float64") - mean) / scale
        feature = np.concatenate([feature, np.ones(1)])
        scores = feature @ weights
        predicted = labels[int(np.argmax(scores))]
        predictions.append(
            {
                "window_id": row["window"].window_id,
                "game_id": row["window"].game_id,
                "split": row["window"].split,
                "duration_seconds": row["window"].duration_seconds,
                "vlm_weak_pseudo_label": row["weak_label"],
                "probe_prediction": predicted,
                "agreement": predicted == row["weak_label"],
                "scores": {label: float(scores[index]) for index, label in enumerate(labels)},
            }
        )
    prediction_path = output_dir / "weak-visual-probe-predictions.jsonl"
    reset_jsonl(prediction_path)
    for prediction in predictions:
        append_jsonl(prediction_path, prediction)
    split_metrics = {}
    for split in ("train", "valid", "test"):
        subset = [item for item in predictions if item["split"] == split]
        split_metrics[split] = {
            "denominator": len(subset),
            "agreement_count": sum(item["agreement"] for item in subset),
            "agreement_rate": sum(item["agreement"] for item in subset) / len(subset) if subset else None,
        }
    receipt = {
        "schema_version": "footballmaster-weak-visual-probe-v2",
        "trained_at": utc_now(),
        "role": "secondary_pipeline_baseline_only",
        "label_source": "guarded development-only silent-frame VLM reports; unverified pseudo-labels, not ground truth",
        "pseudo_label_prompt_id": prompt_id,
        "primary_frozen_test_prompt_id": primary_prompt_id,
        "architecture": "frozen ImageNet MobileNetV2 logits averaged across frames plus fitted ridge head",
        "backbone_path": str(backbone),
        "backbone_sha256": sha256_file(backbone),
        "checkpoint_sha256": sha256_file(checkpoint),
        "labels_observed_in_training": labels,
        "train_window_count": len(train_rows),
        "fitted_parameter_count": int(weights.size + mean.size + scale.size),
        "supervised_head_parameter_count": int(weights.size),
        "split_metrics_agreement_with_unverified_vlm_labels": split_metrics,
        "test_evaluation_status": "not_run: guarded pseudo-label prompt was never run across the frozen primary test",
        "event_accuracy_measured": False,
        "generalization_claim_allowed": False,
        "predictions_sha256": sha256_file(prediction_path),
    }
    write_json(output_dir / "weak-visual-probe-receipt.json", receipt)
    return receipt


def seal_predictions(output_dir: Path) -> dict[str, Any]:
    required = [
        "protocol.json",
        "window-manifest.jsonl",
        "frozen-query-set.json",
        "prompt-selection.json",
        "frozen-test-config.json",
        "model-identity.json",
        "report-metrics.json",
        "football-search-index.jsonl",
        "football-search-index-receipt.json",
        "frozen-query-results.json",
        "failures.jsonl",
        "abstentions.jsonl",
        "weak-visual-probe-receipt.json",
        "weak-visual-probe-predictions.jsonl",
        "weak-visual-probe.npz",
    ]
    missing = [name for name in required if not (output_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("cannot seal; missing: " + ", ".join(missing))
    files: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "prediction-seal.json" or "audio-audit" in path.parts:
            continue
        relative = path.relative_to(output_dir).as_posix()
        files[relative] = sha256_file(path)
    seal = {
        "schema_version": "footballmaster-prediction-seal-v2",
        "sealed_at": utc_now(),
        "purpose": "prove all visual predictions and derived search artifacts predate any commentary audit",
        "file_count": len(files),
        "files": files,
        "root_hash": sha256_bytes(canonical_json(files)),
        "audio_or_commentary_included": False,
    }
    write_json(output_dir / "prediction-seal.json", seal)
    return seal


def verify_seal(output_dir: Path) -> dict[str, Any]:
    seal = read_json(output_dir / "prediction-seal.json")
    observed: dict[str, str] = {}
    for relative, expected in seal["files"].items():
        path = output_dir / relative
        if not path.is_file():
            raise FileNotFoundError(f"sealed file missing: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"sealed file changed: {path}")
        observed[relative] = actual
    if sha256_bytes(canonical_json(observed)) != seal["root_hash"]:
        raise ValueError("prediction seal root hash mismatch")
    return seal


def _ffmpeg_binary() -> Path:
    try:
        import imageio_ffmpeg  # type: ignore

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError as error:
        raise RuntimeError("imageio-ffmpeg is required for bounded audio extraction") from error


def audit_commentary(output_dir: Path, project_root: Path, model_size: str = "tiny.en") -> dict[str, Any]:
    seal = verify_seal(output_dir)
    try:
        whisper_module = importlib.import_module("faster_" + "whisper")
        whisper_model = whisper_module.WhisperModel
    except (ImportError, AttributeError) as error:
        raise RuntimeError("faster-whisper is required for the optional commentary audit") from error
    freeze = verify_freeze(output_dir)
    prompt_id = freeze["selected_prompt_id"]
    windows = load_windows(output_dir / "window-manifest.jsonl")
    subset = [
        window
        for window in windows
        if window.split == "test" and window.duration_seconds == 30 and window.fraction_index in {1, 4}
    ]
    model = whisper_model(model_size, device="cpu", compute_type="int8")
    ffmpeg = _ffmpeg_binary()
    audit_dir = output_dir / "audio-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for window in subset:
        wav = audit_dir / f"{window.window_id}.wav"
        command = [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(window.start_seconds),
            "-t",
            str(window.duration_seconds),
            "-i",
            str(project_root / window.media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-y",
            str(wav),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if completed.returncode != 0:
            rows.append({"window_id": window.window_id, "status": "audio_extract_failed", "stderr": completed.stderr})
            continue
        started = time.perf_counter()
        segments, info = model.transcribe(str(wav), beam_size=1, vad_filter=True)
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        normalized = read_json(output_dir / "runs" / prompt_id / window.window_id / "normalized-report.json")
        rows.append(
            {
                "window_id": window.window_id,
                "game_id": window.game_id,
                "status": "transcribed",
                "duration_seconds": window.duration_seconds,
                "audio_sha256": sha256_file(wav),
                "transcript": transcript,
                "transcript_sha256": sha256_bytes(transcript.encode("utf-8")),
                "detected_language": info.language,
                "language_probability": info.language_probability,
                "elapsed_seconds": time.perf_counter() - started,
                "sealed_visual_report_sha256": sha256_file(
                    output_dir / "runs" / prompt_id / window.window_id / "normalized-report.json"
                ),
                "visual_summary": normalized["report"].get("window_summary", ""),
                "comparison_status": "unverified_side_by_side_only",
            }
        )
        wav.unlink(missing_ok=True)
    packet = {
        "schema_version": "footballmaster-commentary-audit-v2",
        "created_at": utc_now(),
        "prediction_seal_root_hash": seal["root_hash"],
        "asr_model": model_size,
        "asr_role": "weak_unverified_post_hoc_audit_only",
        "asr_was_model_input": False,
        "asr_is_ground_truth": False,
        "human_adjudication": False,
        "window_count": len(rows),
        "rows": rows,
    }
    write_json(audit_dir / "commentary-audit.json", packet)
    return packet


def scan_package_isolation(project_root: Path) -> list[str]:
    forbidden = ("soc" + "cer", "soc" + "cernet", "multi" + "sport")
    violations = []
    package = project_root / "footballmaster"
    for path in sorted(package.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".py", ".json", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for term in forbidden:
            if term in text:
                violations.append(f"{path.relative_to(project_root)} contains forbidden token {term}")
    return violations


def verify_experiment(project_root: Path, dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    manifest, dataset_receipt = validate_dataset(project_root, dataset_dir)
    checks["verified_dataset_five_hours"] = dataset_receipt["coverage"]["total_duration_hours"] >= 5.0
    checks["source_manifest_dataset_id"] = bool(manifest.get("dataset_id"))
    freeze = verify_freeze(output_dir)
    checks["freeze_hashes"] = True
    seal = verify_seal(output_dir)
    checks["prediction_seal"] = True
    windows = load_windows(output_dir / "window-manifest.jsonl")
    split_games = {
        split: {window.game_id for window in windows if window.split == split}
        for split in ("train", "valid", "test")
    }
    checks["game_split_counts"] = {key: len(value) for key, value in split_games.items()}
    checks["game_split_disjoint"] = not any(
        split_games[a] & split_games[b]
        for a, b in (("train", "valid"), ("train", "test"), ("valid", "test"))
    )
    prompt_id = freeze["selected_prompt_id"]
    test_windows = [window for window in windows if window.split == "test"]
    checks["test_window_count"] = len(test_windows)
    checks["test_games"] = len({window.game_id for window in test_windows})
    checks["test_durations"] = sorted({window.duration_seconds for window in test_windows})
    call_errors = []
    for window in windows:
        if window.split not in {"train", "valid", "test"}:
            continue
        base = output_dir / "runs" / prompt_id / window.window_id
        if not (base / "receipt.json").is_file():
            call_errors.append(f"missing receipt {window.window_id}")
            continue
        receipt = read_json(base / "receipt.json")
        raw_path = base / "raw-response.json"
        normalized_path = base / "normalized-report.json"
        if sha256_file(raw_path) != receipt.get("raw_response_sha256"):
            call_errors.append(f"raw hash {window.window_id}")
        if sha256_file(normalized_path) != receipt.get("normalized_report_sha256"):
            call_errors.append(f"normalized hash {window.window_id}")
        contract = receipt.get("input_contract", {})
        if contract.get("audio_used") is not False or contract.get("commentary_used") is not False:
            call_errors.append(f"audio contract {window.window_id}")
        for attempt in receipt.get("attempts", []):
            request_receipt = attempt.get("request_receipt", {})
            if request_receipt.get("audio_used") is not False or request_receipt.get("metadata_fields_used") != []:
                call_errors.append(f"request leakage contract {window.window_id}")
            prompt_lower = str(request_receipt.get("prompt_text", "")).lower()
            forbidden_values = [window.asset_id.lower(), window.game_id.lower(), window.media_path.lower(), window.split.lower()]
            if any(value and value in prompt_lower for value in forbidden_values):
                call_errors.append(f"metadata text leakage {window.window_id}")
    checks["call_receipt_errors"] = call_errors
    query_results = read_json(output_dir / "frozen-query-results.json")
    checks["frozen_query_count"] = query_results.get("query_count")
    checks["query_index_game_count"] = query_results.get("index_game_count")
    checks["query_index_durations"] = query_results.get("index_durations_seconds")
    isolation = scan_package_isolation(project_root)
    checks["package_isolation_violations"] = isolation
    expected = {
        "verified_dataset_five_hours": True,
        "game_split_counts": {"train": 3, "valid": 1, "test": 2},
        "game_split_disjoint": True,
        "test_window_count": 36,
        "test_games": 2,
        "test_durations": [30, 60, 120],
        "call_receipt_errors": [],
        "frozen_query_count": 30,
        "query_index_game_count": 2,
        "query_index_durations": [30, 60, 120],
        "package_isolation_violations": [],
    }
    failures = {key: {"expected": value, "observed": checks.get(key)} for key, value in expected.items() if checks.get(key) != value}
    receipt = {
        "schema_version": "footballmaster-longform-verification-v2",
        "verified_at": utc_now(),
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "prediction_seal_root_hash": seal["root_hash"],
    }
    write_json(output_dir / "verification-receipt.json", receipt)
    if failures:
        raise ValueError("experiment verification failed: " + json.dumps(failures, sort_keys=True))
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    subparsers = value.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    select = subparsers.add_parser("select-prompt")
    select.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    select.add_argument("--model", default=DEFAULT_MODEL)
    select.add_argument("--timeout-seconds", type=int, default=300)
    test = subparsers.add_parser("run-test")
    test.add_argument("--timeout-seconds", type=int, default=300)
    probe = subparsers.add_parser("train-weak-probe")
    probe.add_argument("--backbone", type=Path, default=Path("artifacts/footballmaster/backbones/mobilenetv2-12.onnx"))
    subparsers.add_parser("seal")
    audit = subparsers.add_parser("audit-commentary")
    audit.add_argument("--model-size", default="tiny.en")
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    subparsers.add_parser("verify")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    dataset_dir = args.dataset if args.dataset.is_absolute() else project_root / args.dataset
    output_dir = args.output if args.output.is_absolute() else project_root / args.output
    if args.command == "prepare":
        result = prepare(project_root, dataset_dir, output_dir)
    elif args.command == "select-prompt":
        result = run_prompt_selection(project_root, output_dir, args.endpoint, args.model, args.timeout_seconds)
    elif args.command == "run-test":
        result = run_test(project_root, output_dir, args.timeout_seconds)
    elif args.command == "train-weak-probe":
        backbone = args.backbone if args.backbone.is_absolute() else project_root / args.backbone
        result = train_weak_probe(output_dir, backbone)
    elif args.command == "seal":
        result = seal_predictions(output_dir)
    elif args.command == "audit-commentary":
        result = audit_commentary(output_dir, project_root, args.model_size)
    elif args.command == "search":
        result = bm25_search(load_index(output_dir / "football-search-index.jsonl"), args.query, args.limit)
    elif args.command == "verify":
        result = verify_experiment(project_root, dataset_dir, output_dir)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
