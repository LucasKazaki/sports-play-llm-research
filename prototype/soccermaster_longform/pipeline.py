"""Dense, visual-only SoccerNet long-form reporting and search evaluation.

This package performs deterministic windowing, scoreboard redaction, uniform
frame sampling, local VLM requests, contract validation, retrieval, and a
strictly post-seal annotation evaluation.  It does not contain a heuristic
soccer-event detector or a learned non-VLM classifier.  Soccer semantics in
the primary index come only from the frozen local VLM reports.

Raw SoccerNet media, frames, responses, source names, and indexes stay below
``data/private``.  Public artifacts contain hashes, aggregate measurements,
and explicit claim limitations, but no NDA media or credentials.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL_VERSION = "soccermaster-longform-protocol-v1"
REPORT_VERSION = "soccermaster-longform-visual-report-v2-number-disabled"
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_PRIVATE_ROOT = Path("data/private/soccermaster-longform-v1")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/soccermaster-longform-v1")
DEFAULT_SCALE_MANIFEST = Path("data/private/soccermaster-scale-v1/experiment/manifest.json")
DEFAULT_SCALE_RAW_ROOT = Path("data/private/soccermaster-scale-v1/raw")
TEST_ACQUISITION_RELATIVE = Path("acquisition/test-game-002.json")
FRAME_COUNTS = {30: 8, 60: 12, 120: 16}
DENSE_DURATION_SECONDS = 60
DENSE_STRIDE_SECONDS = 60
SCOREBOARD_REDACTION_TOP_FRACTION = 0.16
TEST_STRESS_FRACTION = 0.37
VALIDATION_FRACTIONS = {1: 0.31, 2: 0.69}

EVENT_TYPES = (
    "offside",
    "foul",
    "long_ball",
    "short_pass",
    "through_ball",
    "switch_of_play",
    "cross",
    "corner_kick",
    "free_kick",
    "penalty_kick",
    "throw_in",
    "goal_kick",
    "kick_off",
    "shot_on_target",
    "shot_off_target",
    "goal",
    "save",
    "tackle",
    "interception",
    "clearance",
    "header",
    "aerial_duel",
    "ground_duel",
    "dribble",
    "ball_recovery",
    "turnover",
    "press",
    "counterpress",
    "transition",
    "set_piece",
    "card",
    "substitution",
    "ball_out_of_play",
    "replay",
    "stoppage",
    "other",
    "unknown",
)
PHASES = (
    "build_up",
    "progression",
    "chance_creation",
    "transition_to_attack",
    "transition_to_defense",
    "sustained_attack",
    "defending",
    "set_piece",
    "stoppage",
    "unknown",
)
FIELD_AREAS = (
    "defensive_third",
    "middle_third",
    "attacking_third",
    "left_flank",
    "right_flank",
    "central_channel",
    "penalty_area",
    "goal_area",
    "corner",
    "unknown",
)
TEAM_REFERENCES = ("attacking_team", "defending_team", "team_in_possession", "other_team", "unknown")
IDENTITY_BASES = ("role_only", "appearance_only", "none")

QUERY_SET = (
    ("sq01", "offside run or offside decision", "offside"),
    ("sq02", "foul tackle referee stoppage", "foul"),
    ("sq03", "long ball over the defensive line", "long_ball"),
    ("sq04", "through ball into space", "through_ball"),
    ("sq05", "switch of play across the field", "switch_of_play"),
    ("sq06", "cross into the penalty area", "cross"),
    ("sq07", "corner kick delivery", "corner_kick"),
    ("sq08", "free kick restart", "free_kick"),
    ("sq09", "shot on target", "shot_on_target"),
    ("sq10", "goalkeeper save", "save"),
    ("sq11", "high press and ball recovery", "press"),
    ("sq12", "transition to attack", "transition"),
    ("sq13", "turnover under pressure", "turnover"),
    ("sq14", "aerial duel or header", "aerial_duel"),
    ("sq15", "dribble past an opponent", "dribble"),
    ("sq16", "defensive clearance", "clearance"),
    ("sq17", "throw in restart", "throw_in"),
    ("sq18", "player jersey number visibly readable", "identity_evidence"),
    ("sq19", "multiple distinct events in one minute", "multi_event"),
    ("sq20", "insufficient visual evidence or uncertain continuity", "abstention"),
)

PROMPT_CANDIDATES = {
    "candidate_a_direct_v2": (
        "Analyze only the ordered, silent soccer frames supplied below. Create a detailed coach-search report for every "
        "distinct visually supported event, merging frames that plausibly show one sequence and returning no more than four "
        "events. Keep every free-text field to one concise sentence. Never use audio, commentary, outside knowledge, team "
        "identity, score, filenames, match identity, player names, or source metadata. Return only the required JSON."
    ),
    "candidate_b_evidence_first_v2": (
        "You are indexing silent soccer footage for later evidence-grounded search. Use only the ordered frames supplied "
        "below. Merge frames that plausibly show one sequence and return no more than four distinct events, replays, or "
        "stoppages. Keep every free-text field to one concise sentence and cite frame IDs for every event. Do not invent "
        "player names, team names, score, tactical intent, ball trajectory, outcome, offside, or a foul when pixels do not "
        "establish them; state uncertainty or abstain. Return only the required JSON."
    ),
}

DELIVERY_PROMPTS = {
    "candidate_b_evidence_first_v3_number_disabled": (
        PROMPT_CANDIDATES["candidate_b_evidence_first_v2"]
        + " The 224p source is insufficient for reliable jersey-numeral identity: never infer or transcribe a jersey "
        "number, always return visible_jersey_number as null, and use only role_only, appearance_only, or none as the "
        "identity_basis."
    ),
}
ALL_PROMPTS = {**PROMPT_CANDIDATES, **DELIVERY_PROMPTS}

SOCCERNET_LABEL_TO_EVENT = {
    "Ball out of play": "ball_out_of_play",
    "Throw-in": "throw_in",
    "Foul": "foul",
    "Indirect free-kick": "free_kick",
    "Direct free-kick": "free_kick",
    "Corner": "corner_kick",
    "Shots on target": "shot_on_target",
    "Shots off target": "shot_off_target",
    "Goal": "goal",
    "Penalty": "penalty_kick",
    "Kick-off": "kick_off",
    "Yellow card": "card",
    "Red card": "card",
    "Yellow->red card": "card",
    "Offside": "offside",
    "Substitution": "substitution",
    "Clearance": "clearance",
}


@dataclass(frozen=True)
class Window:
    window_id: str
    role: str
    source_scope_id: str
    source_half: int
    media_path: str
    media_sha256: str
    start_seconds: float
    duration_seconds: int
    frame_count: int
    ordinal: int

    @property
    def end_seconds(self) -> float:
        return round(self.start_seconds + self.duration_seconds, 3)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def stable_id(*parts: object, length: int = 18) -> str:
    return sha256_bytes("\x1f".join(str(item).replace("\\", "/") for item in parts).encode("utf-8"))[:length]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as sink:
        for row in rows:
            sink.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def require_private(path: Path) -> Path:
    resolved = path.resolve()
    parts = [item.lower() for item in resolved.parts]
    if not any(parts[index:index + 2] == ["data", "private"] for index in range(len(parts) - 1)):
        raise ValueError("SoccerNet source data and raw VLM outputs must remain below data/private")
    return resolved


def _loopback_endpoint(endpoint: str) -> None:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("private SoccerNet frames may be sent only to a loopback endpoint")


def _probe_video(path: Path) -> dict[str, Any]:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open video: {path.name}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok_first, first = capture.read()
    # Some Matroska indexes report a nominal terminal frame that OpenCV cannot
    # return even though ffmpeg decodes the stream cleanly.  Probe the latest
    # reliably addressable frame and rely on the independent full ffmpeg pass
    # below for the complete-stream gate.
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 2))
    ok_last, last = capture.read()
    capture.release()
    if not ok_first or first is None or not ok_last or last is None or frame_count < 2 or fps <= 0 or width < 1 or height < 1:
        raise RuntimeError(f"video failed first/last-frame probe: {path.name}")
    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration_seconds": frame_count / fps,
        "width": width,
        "height": height,
        "first_frame_sha256": sha256_bytes(first.tobytes()),
        "last_frame_sha256": sha256_bytes(last.tobytes()),
    }


def verify_source(project_root: Path, private_root: Path, artifact_root: Path) -> dict[str, Any]:
    """Hash, probe, and fully decode the newly acquired two-half test game."""
    private_root = require_private(private_root)
    receipt_path = private_root / TEST_ACQUISITION_RELATIVE
    receipt = read_json(receipt_path)
    if receipt.get("schema_version") != "playground-soccernet-acquisition-receipt-v1":
        raise ValueError("unsupported SoccerNet acquisition receipt")
    authorization = receipt.get("authorization", {})
    if authorization.get("credential_persisted") is not False or authorization.get("redistribution_allowed") is not False:
        raise ValueError("acquisition receipt does not preserve the private authorization boundary")
    records = {str(item.get("name")): item for item in receipt.get("downloaded_files", []) if isinstance(item, dict)}
    if set(records) != {"1_224p.mkv", "2_224p.mkv", "Labels-v2.json"}:
        raise ValueError("source receipt must bind exactly two 224p halves plus SoccerNet-v2 labels")
    try:
        import imageio_ffmpeg  # type: ignore
    except ImportError as error:
        raise RuntimeError("imageio-ffmpeg is required for full decode verification") from error
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    raw_root = private_root / "raw"
    assets: list[dict[str, Any]] = []
    for name in ("1_224p.mkv", "2_224p.mkv"):
        record = records[name]
        path = raw_root / str(record["relative_path"])
        if not path.is_file() or path.stat().st_size != int(record["bytes"]):
            raise FileNotFoundError(f"receipt-bound media is missing or truncated: {name}")
        observed_sha = sha256_file(path)
        if observed_sha != record["sha256"]:
            raise ValueError(f"source hash mismatch: {name}")
        probe = _probe_video(path)
        completed = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
            capture_output=True,
            timeout=300,
        )
        if completed.returncode != 0 or completed.stderr:
            raise RuntimeError(f"full video-only decode failed for {name}: {completed.stderr[:1000]!r}")
        assets.append({
            "half": int(name[0]),
            "bytes": path.stat().st_size,
            "sha256": observed_sha,
            "probe": probe,
            "full_video_decode": "pass",
        })
    label_record = records["Labels-v2.json"]
    labels_path = raw_root / str(label_record["relative_path"])
    if not labels_path.is_file() or sha256_file(labels_path) != label_record["sha256"]:
        raise ValueError("sealed SoccerNet annotation file hash mismatch")
    result = {
        "schema_version": "soccermaster-longform-source-verification-v1",
        "verified_at": utc_now(),
        "status": "pass",
        "provider": "SoccerNet",
        "official_split": receipt["selection"]["split"],
        "official_split_index": receipt["selection"]["game_index"],
        "source_scope_id": "snt-" + stable_id(receipt["selection"]["game"]),
        "game_name_redacted_from_public_receipt": True,
        "acquisition_receipt_sha256": sha256_file(receipt_path),
        "labels_sha256": label_record["sha256"],
        "labels_semantics_opened": False,
        "assets": assets,
        "rights": {
            "access": "user-authorized SoccerNet NDA access",
            "allowed_use": "local non-commercial research",
            "redistribution_allowed": False,
            "credential_persisted": False,
        },
        "checks": {
            "two_complete_halves": len(assets) == 2,
            "receipt_hashes": True,
            "first_and_last_frames": True,
            "full_video_decode": True,
            "disk_free_gib_after_verification": round(shutil.disk_usage(project_root).free / (1024 ** 3), 3),
        },
    }
    artifact_root.mkdir(parents=True, exist_ok=True)
    write_json(artifact_root / "source-verification-receipt.json", result)
    return result


def _window_id(scope: str, role: str, half: int, start: float, duration: int) -> str:
    return "smw-" + stable_id(scope, role, half, f"{start:.3f}", duration)


def build_dense_windows(
    *, source_scope_id: str, source_half: int, media_path: str, media_sha256: str,
    duration_seconds: float, start_ordinal: int = 0,
) -> list[Window]:
    """Build gap-free <=60-second-stride windows through a complete half."""
    if duration_seconds < DENSE_DURATION_SECONDS:
        raise ValueError("a dense test half must be at least 60 seconds")
    starts: list[float] = []
    cursor = 0.0
    while cursor + DENSE_DURATION_SECONDS <= duration_seconds + 1e-6:
        starts.append(round(cursor, 3))
        cursor += DENSE_STRIDE_SECONDS
    tail = round(max(0.0, duration_seconds - DENSE_DURATION_SECONDS), 3)
    if not starts or tail > starts[-1] + 1e-6:
        starts.append(tail)
    windows = [
        Window(
            window_id=_window_id(source_scope_id, "test_dense", source_half, start, DENSE_DURATION_SECONDS),
            role="test_dense",
            source_scope_id=source_scope_id,
            source_half=source_half,
            media_path=media_path,
            media_sha256=media_sha256,
            start_seconds=start,
            duration_seconds=DENSE_DURATION_SECONDS,
            frame_count=FRAME_COUNTS[DENSE_DURATION_SECONDS],
            ordinal=start_ordinal + index,
        )
        for index, start in enumerate(starts)
    ]
    if windows[0].start_seconds != 0 or windows[-1].end_seconds < duration_seconds - 1e-3:
        raise AssertionError("dense plan does not cover the complete half")
    if any(left.end_seconds < right.start_seconds - 1e-6 for left, right in zip(windows, windows[1:])):
        raise AssertionError("dense plan contains a temporal gap")
    if any(right.start_seconds - left.start_seconds > DENSE_STRIDE_SECONDS + 1e-6 for left, right in zip(windows, windows[1:])):
        raise AssertionError("dense plan exceeds the frozen stride")
    return windows


def _stress_windows(
    *, role: str, source_scope_id: str, source_half: int, media_path: str,
    media_sha256: str, duration_seconds: float, fraction: float, start_ordinal: int,
) -> list[Window]:
    result: list[Window] = []
    for index, duration in enumerate((30, 60, 120)):
        start = round(max(0.0, duration_seconds - duration) * fraction, 3)
        result.append(Window(
            window_id=_window_id(source_scope_id, role, source_half, start, duration),
            role=role,
            source_scope_id=source_scope_id,
            source_half=source_half,
            media_path=media_path,
            media_sha256=media_sha256,
            start_seconds=start,
            duration_seconds=duration,
            frame_count=FRAME_COUNTS[duration],
            ordinal=start_ordinal + index,
        ))
    return result


def _artifact_paths(project_root: Path, private_root: Path, artifact_root: Path) -> tuple[Path, Path]:
    private = private_root if private_root.is_absolute() else project_root / private_root
    public = artifact_root if artifact_root.is_absolute() else project_root / artifact_root
    return require_private(private), public.resolve()


def _prior_media_hashes(project_root: Path) -> set[str]:
    hashes: set[str] = set()
    prior = project_root / "data/private/soccermaster-scale-v1/vlm-eval"
    if not prior.exists():
        return hashes
    for path in prior.rglob("input-manifest.json"):
        try:
            value = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        candidate = value.get("video_sha256")
        if isinstance(candidate, str):
            hashes.add(candidate)
    return hashes


def prepare(
    project_root: Path, private_root: Path = DEFAULT_PRIVATE_ROOT,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    scale_manifest: Path = DEFAULT_SCALE_MANIFEST,
    scale_raw_root: Path = DEFAULT_SCALE_RAW_ROOT,
) -> dict[str, Any]:
    """Freeze source selection, windows, prompts, schemas, queries, and spot checks."""
    private_root, artifact_root = _artifact_paths(project_root, private_root, artifact_root)
    scale_manifest = scale_manifest if scale_manifest.is_absolute() else project_root / scale_manifest
    scale_raw_root = scale_raw_root if scale_raw_root.is_absolute() else project_root / scale_raw_root
    source_verification = read_json(artifact_root / "source-verification-receipt.json")
    if source_verification.get("status") != "pass" or len(source_verification.get("assets", [])) != 2:
        raise ValueError("verified two-half untouched test source is required")
    acquisition_path = private_root / TEST_ACQUISITION_RELATIVE
    acquisition = read_json(acquisition_path)
    source_game = str(acquisition["selection"]["game"]).replace("\\", "/")
    test_scope = str(source_verification["source_scope_id"])
    if source_verification.get("official_split") != "test" or source_verification.get("official_split_index") != 2:
        raise ValueError("frozen protocol requires official SoccerNet test index 2")
    existing = read_json(scale_manifest)
    existing_games = {str(item.get("source_game", "")).replace("\\", "/") for item in existing.get("games", [])}
    if source_game in existing_games:
        raise ValueError("selected test game is not untouched by the existing eight-game scale experiment")
    test_records = {str(item["name"]): item for item in acquisition["downloaded_files"]}
    prior_hashes = _prior_media_hashes(project_root)
    test_video_hashes = {str(test_records[name]["sha256"]) for name in ("1_224p.mkv", "2_224p.mkv")}
    if test_video_hashes & prior_hashes:
        raise ValueError("selected test media appeared in a prior SoccerMaster VLM input receipt")

    validation_games = sorted(
        (item for item in existing.get("games", []) if item.get("split") == "valid"),
        key=lambda item: str(item["game_id"]),
    )
    if not validation_games:
        raise ValueError("existing scale manifest has no validation game")
    validation_game = validation_games[0]
    validation_scope = str(validation_game["game_id"])

    source_lock = {
        "schema_version": "soccermaster-longform-private-source-lock-v1",
        "created_at": utc_now(),
        "test": {
            "source_scope_id": test_scope,
            "source_game": source_game,
            "labels_path": str((private_root / "raw" / str(test_records["Labels-v2.json"]["relative_path"])).resolve()),
            "labels_sha256": test_records["Labels-v2.json"]["sha256"],
            "halves": [],
        },
        "validation": {"source_scope_id": validation_scope, "halves": []},
        "privacy": "This file contains SoccerNet source paths and must remain below data/private.",
    }
    source_assets = {int(item["half"]): item for item in source_verification["assets"]}
    for half in (1, 2):
        name = f"{half}_224p.mkv"
        test_path = (private_root / "raw" / str(test_records[name]["relative_path"])).resolve()
        source_lock["test"]["halves"].append({
            "half": half,
            "media_path": str(test_path),
            "media_sha256": test_records[name]["sha256"],
            "duration_seconds": source_assets[half]["probe"]["duration_seconds"],
        })
        validation_half = next(item for item in validation_game["halves"] if int(item["half"]) == half)
        validation_path = (scale_raw_root / str(validation_half["video_relative_path"])).resolve()
        if not validation_path.is_file() or sha256_file(validation_path) != validation_half["media"]["sha256"]:
            raise ValueError("validation media failed existing manifest binding")
        source_lock["validation"]["halves"].append({
            "half": half,
            "media_path": str(validation_path),
            "media_sha256": validation_half["media"]["sha256"],
            "duration_seconds": validation_half["media"]["duration_s"],
        })
    write_json(private_root / "experiment/source-lock.json", source_lock)

    windows: list[Window] = []
    for item in source_lock["validation"]["halves"]:
        windows.extend(_stress_windows(
            role="validation_select", source_scope_id=validation_scope, source_half=int(item["half"]),
            media_path=str(item["media_path"]), media_sha256=str(item["media_sha256"]),
            duration_seconds=float(item["duration_seconds"]), fraction=VALIDATION_FRACTIONS[int(item["half"])],
            start_ordinal=len(windows),
        ))
    for item in source_lock["test"]["halves"]:
        windows.extend(build_dense_windows(
            source_scope_id=test_scope, source_half=int(item["half"]), media_path=str(item["media_path"]),
            media_sha256=str(item["media_sha256"]), duration_seconds=float(item["duration_seconds"]),
            start_ordinal=len(windows),
        ))
    for item in source_lock["test"]["halves"]:
        windows.extend(_stress_windows(
            role="test_stress", source_scope_id=test_scope, source_half=int(item["half"]),
            media_path=str(item["media_path"]), media_sha256=str(item["media_sha256"]),
            duration_seconds=float(item["duration_seconds"]), fraction=TEST_STRESS_FRACTION,
            start_ordinal=len(windows),
        ))
    if len({item.window_id for item in windows}) != len(windows):
        raise AssertionError("window IDs are not unique")
    window_path = private_root / "experiment/window-manifest.jsonl"
    write_jsonl(window_path, (item.as_dict() for item in windows))

    artifact_root.mkdir(parents=True, exist_ok=True)
    prompt_path = artifact_root / "prompt-candidates.json"
    write_json(prompt_path, {
        "schema_version": "soccermaster-longform-prompt-candidates-v1",
        "selection_scope": "label-free structural behavior on one pre-existing validation game only",
        "parameter_training": False,
        "candidates": PROMPT_CANDIDATES,
        "delivery_prompts": DELIVERY_PROMPTS,
        "delivery_rule": "Freeze the evidence-first v3 number-disabled prompt after six fresh validation delivery checks regardless of outcome.",
    })
    query_path = artifact_root / "frozen-query-set.json"
    write_json(query_path, {
        "schema_version": "soccermaster-longform-frozen-query-set-v1",
        "frozen_before_test": True,
        "derived_from_test_labels_or_outputs": False,
        "relevance_ground_truth_available": False,
        "queries": [{"query_id": qid, "text": text, "facet": facet} for qid, text, facet in QUERY_SET],
    })
    schema_path = artifact_root / "response-schema-receipt.json"
    schema_hashes = {
        str(count): sha256_bytes(canonical_json(report_json_schema([f"F{index:02d}" for index in range(count)])))
        for count in sorted(set(FRAME_COUNTS.values()))
    }
    write_json(schema_path, {
        "schema_version": "soccermaster-longform-response-schema-receipt-v1",
        "report_version": REPORT_VERSION,
        "jersey_number_claims_allowed": False,
        "identity_bases": list(IDENTITY_BASES),
        "frame_count_to_response_schema_sha256": schema_hashes,
    })
    dense = [item for item in windows if item.role == "test_dense"]
    stress = [item for item in windows if item.role == "test_stress"]
    validation = [item for item in windows if item.role == "validation_select"]
    spot_checks: list[str] = []
    for half in (1, 2):
        half_dense = [item for item in dense if item.source_half == half]
        for index in (0, len(half_dense) // 2, len(half_dense) - 1):
            spot_checks.append(half_dense[index].window_id)
    amendment_path = artifact_root / "pre-inference-amendments.jsonl"
    protocol = {
        "schema_version": PROTOCOL_VERSION,
        "prepared_at": utc_now(),
        "status": "frozen_before_validation_and_test_inference",
        "source": {
            "provider": "SoccerNet",
            "official_split": "test",
            "official_split_index": 2,
            "test_source_scope_id": test_scope,
            "source_game_name_public": False,
            "complete_halves": 2,
            "duration_seconds": sum(float(item["duration_seconds"]) for item in source_lock["test"]["halves"]),
            "media_sha256s": sorted(test_video_hashes),
            "labels_sha256": test_records["Labels-v2.json"]["sha256"],
            "labels_semantics_opened_during_prepare": False,
            "untouched_by_existing_eight_game_manifest": True,
            "untouched_by_prior_vlm_input_receipts": True,
            "source_verification_receipt_sha256": sha256_file(artifact_root / "source-verification-receipt.json"),
            "private_source_lock_sha256": sha256_file(private_root / "experiment/source-lock.json"),
        },
        "validation": {
            "source_scope_id": validation_scope,
            "window_count": len(validation),
            "durations_seconds": [30, 60, 120],
            "prompt_selection_uses_labels": False,
            "prompt_selection_uses_semantic_correctness": False,
        },
        "test": {
            "dense_window_seconds": DENSE_DURATION_SECONDS,
            "dense_stride_seconds": DENSE_STRIDE_SECONDS,
            "dense_window_count": len(dense),
            "dense_counts_by_half": {str(half): sum(item.source_half == half for item in dense) for half in (1, 2)},
            "duration_stress_window_count": len(stress),
            "stress_durations_seconds": [30, 60, 120],
            "total_window_denominator": len(dense) + len(stress),
            "minimum_ordered_frames": min(item.frame_count for item in dense + stress),
            "spot_check_window_ids": spot_checks,
        },
        "model_input_contract": {
            "modalities": ["protocol_text", "ordered_silent_scoreboard_redacted_jpeg_frames"],
            "audio": "excluded",
            "commentary": "excluded",
            "labels": "excluded",
            "filenames_team_names_scores_game_identity_absolute_clock_source_metadata": "excluded",
            "relative_frame_offsets": "included",
            "scoreboard_redaction_top_fraction": SCOREBOARD_REDACTION_TOP_FRACTION,
        },
        "recovery": {
            "predeclared_strategies": [
                "strict_json_schema_all_frames",
                "json_object_all_frames",
                "json_object_half_frames",
            ],
            "maximum_attempts_per_window": 3,
            "every_attempt_persisted": True,
        },
        "claims": {
            "vlm_parameter_training": False,
            "prompt_selection": "validation-only frozen structural selection, not parameter fine-tuning",
            "test_is_single_game": True,
            "dense_event_spotting_accuracy_claim_allowed": False,
            "detailed_claim_factuality_evaluated": False,
            "coach_utility_validated": False,
            "performance_claim_allowed": False,
        },
        "files": {
            "private_window_manifest_sha256": sha256_file(window_path),
            "prompt_candidates_sha256": sha256_file(prompt_path),
            "query_set_sha256": sha256_file(query_path),
            "response_schema_receipt_sha256": sha256_file(schema_path),
        },
    }
    if amendment_path.is_file():
        protocol["files"]["pre_inference_amendments_sha256"] = sha256_file(amendment_path)
    if len(dense) < 90 or len(stress) != 6 or len(validation) != 6:
        raise RuntimeError("frozen long-form scale target was not met")
    write_json(artifact_root / "protocol-receipt.json", protocol)
    return protocol


def load_windows(path: Path) -> list[Window]:
    return [Window(**item) for item in read_jsonl(path)]


def report_json_schema(frame_ids: Sequence[str]) -> dict[str, Any]:
    actor = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "player_reference": {"type": "string"},
            "visible_jersey_number": {"type": "null"},
            "identity_basis": {"type": "string", "enum": list(IDENTITY_BASES)},
            "team_reference": {"type": "string", "enum": list(TEAM_REFERENCES)},
            "role_in_event": {"type": "string"},
            "observable_action": {"type": "string"},
        },
        "required": [
            "player_reference", "visible_jersey_number", "identity_basis", "team_reference",
            "role_in_event", "observable_action",
        ],
    }
    event = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
            "start_frame_id": {"type": "string", "enum": list(frame_ids)},
            "end_frame_id": {"type": "string", "enum": list(frame_ids)},
            "primary_action": {"type": "string"},
            "sequence_detail": {"type": "string"},
            "outcome": {"type": "string"},
            "participants": {"type": "array", "items": actor, "maxItems": 4},
            "phase_of_play": {"type": "string", "enum": list(PHASES)},
            "field_areas": {"type": "array", "items": {"type": "string", "enum": list(FIELD_AREAS)}, "uniqueItems": True},
            "evidence_frame_ids": {"type": "array", "items": {"type": "string", "enum": list(frame_ids)}, "minItems": 1, "uniqueItems": True},
            "coaching_relevance": {"type": "string"},
            "search_terms": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "event_type", "start_frame_id", "end_frame_id", "primary_action", "sequence_detail", "outcome",
            "participants", "phase_of_play", "field_areas", "evidence_frame_ids", "coaching_relevance",
            "search_terms", "uncertainties", "confidence",
        ],
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "soccermaster_longform_visual_report",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "schema_version": {"type": "string", "const": REPORT_VERSION},
                    "visual_only": {"type": "boolean", "const": True},
                    "abstain": {"type": "boolean"},
                    "abstention_reason": {"type": "string"},
                    "window_summary": {"type": "string"},
                    "events": {"type": "array", "items": event, "maxItems": 4},
                    "tactics_observed": {"type": "array", "items": {"type": "string"}},
                    "coach_search_terms": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                    "overall_uncertainties": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "schema_version", "visual_only", "abstain", "abstention_reason", "window_summary", "events",
                    "tactics_observed", "coach_search_terms", "overall_uncertainties",
                ],
            },
        },
    }


def extract_frames(media_path: Path, window: Window, frame_dir: Path) -> list[dict[str, Any]]:
    """Decode ordered frames and redact broadcast score/clock overlays."""
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        raise RuntimeError("could not open the receipt-bound private video")
    frame_dir.mkdir(parents=True, exist_ok=True)
    offsets = [(index + 0.5) * window.duration_seconds / window.frame_count for index in range(window.frame_count)]
    frames: list[dict[str, Any]] = []
    try:
        for index, relative in enumerate(offsets):
            absolute = window.start_seconds + relative
            capture.set(cv2.CAP_PROP_POS_MSEC, absolute * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError(f"frame decode failed at private offset {absolute:.3f}s")
            height, width = frame.shape[:2]
            redacted_rows = max(1, int(math.ceil(height * SCOREBOARD_REDACTION_TOP_FRACTION)))
            frame[:redacted_rows, :] = 0
            frame_id = f"F{index:02d}"
            encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not encoded_ok:
                raise RuntimeError(f"JPEG encoding failed for {frame_id}")
            data = encoded.tobytes()
            path = frame_dir / f"{frame_id}.jpg"
            path.write_bytes(data)
            frames.append({
                "frame_id": frame_id,
                "relative_seconds": round(relative, 3),
                "absolute_seconds_private_receipt": round(absolute, 3),
                "path": str(path),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "width": width,
                "height": height,
                "redacted_rows": redacted_rows,
                "data": data,
            })
    finally:
        capture.release()
    return frames


def build_request(
    *, model: str, prompt_text: str, window: Window, frames: Sequence[dict[str, Any]],
    response_mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    frame_ids = [str(item["frame_id"]) for item in frames]
    legend = ", ".join(f"{item['frame_id']}=+{item['relative_seconds']:.3f}s" for item in frames)
    event_types = ", ".join(EVENT_TYPES)
    phases = ", ".join(PHASES)
    areas = ", ".join(FIELD_AREAS)
    text = (
        f"{prompt_text}\n\n"
        f"The anonymous window lasts {window.duration_seconds} seconds. Ordered relative frame legend: {legend}. "
        "The top broadcast overlay region has been blacked out so score, clock, and team abbreviations are unavailable. "
        "Do not treat each frame as an event. Merge frames that plausibly show one sequence; report at most four distinct "
        "events and do not assume continuity. Keep every free-text field to one concise sentence, use at most four "
        "participants per event, and prefer uncertainty over verbose speculation. "
        f"event_type must be one of: {event_types}. phase_of_play must be one of: {phases}. "
        f"field_areas values must be from: {areas}. "
        "Each event must contain event_type, start_frame_id, end_frame_id, primary_action, sequence_detail, outcome, "
        "participants, phase_of_play, field_areas, evidence_frame_ids, coaching_relevance, search_terms, uncertainties, "
        "and confidence. Every participant must use an anonymous role or appearance description, relative team reference, "
        "role, and observable action. The 224p inputs cannot support reliable numeral identity: never infer or transcribe "
        "a jersey number, always set visible_jersey_number to null, and use identity_basis role_only, appearance_only, or "
        "none. Never output a real player or team name. Do not call an event offside or a foul unless the sampled pixels "
        "establish it. If no event is supported, "
        "set abstain true, use an empty events list, and explain the missing evidence. Otherwise abstain must be false and "
        "abstention_reason must be empty. Return strict JSON with schema_version, visual_only, abstain, abstention_reason, "
        "window_summary, events, tactics_observed, coach_search_terms, and overall_uncertainties."
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for frame in frames:
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(frame["data"]).decode("ascii")},
        })
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Produce evidence-bounded structured reports from silent, anonymized soccer frames only.",
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "max_tokens": 3600,
        "stream": False,
    }
    if response_mode == "strict_json_schema":
        payload["response_format"] = report_json_schema(frame_ids)
    elif response_mode == "json_object":
        payload["response_format"] = {"type": "json_object"}
    else:
        raise ValueError(f"unknown response mode: {response_mode}")
    request_receipt = {
        "model": model,
        "temperature": 0,
        "max_tokens": 3600,
        "stream": False,
        "prompt_text": text,
        "response_format": payload["response_format"],
        "frames": [
            {
                "frame_id": item["frame_id"],
                "relative_seconds": item["relative_seconds"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "scoreboard_redacted_rows": item["redacted_rows"],
            }
            for item in frames
        ],
        "input_modalities": ["text_protocol", "silent_scoreboard_redacted_jpeg_frames"],
        "audio_used": False,
        "commentary_used": False,
        "labels_used": False,
        "absolute_timestamps_used": False,
        "filenames_used": False,
        "team_names_used": False,
        "scores_used": False,
        "source_metadata_fields_used": [],
    }
    return payload, request_receipt


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], bytes]:
    body = canonical_json(payload)
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"local VLM HTTP {error.code}: {detail[:2000]}") from error
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("local VLM response envelope is not an object")
    return parsed, raw


def _completion_text(envelope: dict[str, Any]) -> str:
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


def _parse_json_text(text: str) -> dict[str, Any]:
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
        value = json.loads(cleaned[left:right + 1])
    if not isinstance(value, dict):
        raise ValueError("completion JSON is not an object")
    return value


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} must be {'text' if allow_empty else 'non-empty text'}")
    return value.strip()


def _text_list(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be {'a non-empty' if nonempty else 'a'} list")
    result = [_text(item, f"{field} item") for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f"{field} contains duplicates")
    return result


def validate_report(report: dict[str, Any], frame_ids: Sequence[str]) -> list[str]:
    """Fail closed on malformed evidence, identity, and abstention contracts."""
    errors: list[str] = []
    expected = {
        "schema_version", "visual_only", "abstain", "abstention_reason", "window_summary", "events",
        "tactics_observed", "coach_search_terms", "overall_uncertainties",
    }
    if set(report) != expected:
        errors.append("report_keys")
    if report.get("schema_version") != REPORT_VERSION:
        errors.append("schema_version")
    if report.get("visual_only") is not True:
        errors.append("visual_only")
    abstain = report.get("abstain")
    if not isinstance(abstain, bool):
        errors.append("abstain")
    try:
        _text(report.get("window_summary"), "window_summary")
        _text_list(report.get("tactics_observed"), "tactics_observed")
        _text_list(report.get("coach_search_terms"), "coach_search_terms")
        _text_list(report.get("overall_uncertainties"), "overall_uncertainties")
    except ValueError as error:
        errors.append(str(error))
    events = report.get("events")
    if not isinstance(events, list) or len(events) > 4:
        errors.append("events")
        events = []
    reason = report.get("abstention_reason")
    if abstain is True and (events or not isinstance(reason, str) or not reason.strip()):
        errors.append("abstention_contract")
    if abstain is False and (not events or reason not in {"", None}):
        errors.append("prediction_contract")
    allowed_frames = list(frame_ids)
    frame_positions = {frame_id: index for index, frame_id in enumerate(allowed_frames)}
    event_keys = {
        "event_type", "start_frame_id", "end_frame_id", "primary_action", "sequence_detail", "outcome",
        "participants", "phase_of_play", "field_areas", "evidence_frame_ids", "coaching_relevance",
        "search_terms", "uncertainties", "confidence",
    }
    participant_keys = {
        "player_reference", "visible_jersey_number", "identity_basis", "team_reference", "role_in_event",
        "observable_action",
    }
    for index, event in enumerate(events):
        prefix = f"event[{index}]"
        if not isinstance(event, dict) or set(event) != event_keys:
            errors.append(prefix + ".keys")
            continue
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(prefix + ".event_type")
        start, end = event.get("start_frame_id"), event.get("end_frame_id")
        if start not in frame_positions or end not in frame_positions or (
            start in frame_positions and end in frame_positions and frame_positions[start] > frame_positions[end]
        ):
            errors.append(prefix + ".interval")
        for field in ("primary_action", "sequence_detail", "outcome", "coaching_relevance"):
            try:
                _text(event.get(field), f"{prefix}.{field}")
            except ValueError as error:
                errors.append(str(error))
        if event.get("phase_of_play") not in PHASES:
            errors.append(prefix + ".phase")
        areas = event.get("field_areas")
        if not isinstance(areas, list) or not areas or len(set(areas)) != len(areas) or any(item not in FIELD_AREAS for item in areas):
            errors.append(prefix + ".field_areas")
        evidence = event.get("evidence_frame_ids")
        if (
            not isinstance(evidence, list) or not evidence or len(set(evidence)) != len(evidence)
            or any(item not in frame_positions for item in evidence)
        ):
            errors.append(prefix + ".evidence")
        for field in ("search_terms", "uncertainties"):
            try:
                _text_list(event.get(field), f"{prefix}.{field}", nonempty=(field == "search_terms"))
            except ValueError as error:
                errors.append(str(error))
        confidence = event.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            errors.append(prefix + ".confidence")
        participants = event.get("participants")
        if not isinstance(participants, list) or len(participants) > 4:
            errors.append(prefix + ".participants")
            continue
        for p_index, participant in enumerate(participants):
            pfx = f"{prefix}.participant[{p_index}]"
            if not isinstance(participant, dict) or set(participant) != participant_keys:
                errors.append(pfx + ".keys")
                continue
            for field in ("player_reference", "role_in_event", "observable_action"):
                try:
                    _text(participant.get(field), f"{pfx}.{field}")
                except ValueError as error:
                    errors.append(str(error))
            basis = participant.get("identity_basis")
            number = participant.get("visible_jersey_number")
            if basis not in IDENTITY_BASES or participant.get("team_reference") not in TEAM_REFERENCES:
                errors.append(pfx + ".ontology")
            if number is not None:
                errors.append(pfx + ".visible_jersey_number")
    return errors


def _failure_report(reason: str) -> dict[str, Any]:
    return {
        "schema_version": REPORT_VERSION,
        "visual_only": True,
        "abstain": True,
        "abstention_reason": reason,
        "window_summary": "No valid structured visual report was produced.",
        "events": [],
        "tactics_observed": [],
        "coach_search_terms": ["unresolved visual window"],
        "overall_uncertainties": [reason],
    }


def _run_directory(private_root: Path, window: Window, prompt_id: str) -> Path:
    phase = "validation" if window.role == "validation_select" else "test"
    return private_root / "experiment/runs" / phase / prompt_id / window.window_id


def run_one(
    *, private_root: Path, window: Window, prompt_id: str, prompt_text: str,
    endpoint: str, model: str, timeout_seconds: int,
) -> dict[str, Any]:
    _loopback_endpoint(endpoint)
    result_dir = _run_directory(private_root, window, prompt_id)
    result_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = result_dir / "receipt.json"
    prompt_sha = sha256_bytes(prompt_text.encode("utf-8"))
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        raw_path = result_dir / "raw-response.json"
        normalized_path = result_dir / "normalized-report.json"
        if (
            receipt.get("window_id") != window.window_id
            or receipt.get("prompt_sha256") != prompt_sha
            or receipt.get("model") != model
            or not raw_path.is_file()
            or not normalized_path.is_file()
            or receipt.get("raw_response_sha256") != sha256_file(raw_path)
            or receipt.get("normalized_report_sha256") != sha256_file(normalized_path)
        ):
            raise RuntimeError(f"cached result failed closed identity verification: {window.window_id}")
        return receipt

    media_path = Path(window.media_path)
    if not media_path.is_file():
        raise FileNotFoundError("receipt-bound private media is missing")
    frames = extract_frames(media_path, window, result_dir / "frames")
    strategies = (
        ("strict_json_schema_all_frames", "strict_json_schema", frames),
        ("json_object_all_frames", "json_object", frames),
        ("json_object_half_frames", "json_object", frames[::2]),
    )
    attempt_records: list[dict[str, Any]] = []
    final_report: dict[str, Any] | None = None
    final_envelope: dict[str, Any] | None = None
    selected_strategy = "none"
    model_reported: str | None = None
    for strategy_id, mode, attempt_frames in strategies:
        payload, request_receipt = build_request(
            model=model, prompt_text=prompt_text, window=window, frames=attempt_frames, response_mode=mode,
        )
        request_receipt["strategy_id"] = strategy_id
        request_receipt["request_without_image_bytes_sha256"] = sha256_bytes(canonical_json(request_receipt))
        attempt: dict[str, Any] = {
            "strategy_id": strategy_id,
            "started_at": utc_now(),
            "request_receipt": request_receipt,
        }
        started = time.perf_counter()
        envelope: dict[str, Any] | None = None
        try:
            envelope, raw = _post_json(endpoint.rstrip("/") + "/chat/completions", payload, timeout_seconds)
            text = _completion_text(envelope)
            parsed = _parse_json_text(text)
            validation = validate_report(parsed, [str(item["frame_id"]) for item in attempt_frames])
            attempt.update({
                "status": "valid" if not validation else "invalid_schema",
                "elapsed_seconds": time.perf_counter() - started,
                "raw_response_sha256": sha256_bytes(raw),
                "completion_text_sha256": sha256_bytes(text.encode("utf-8")),
                "validation_errors": validation,
            })
            write_json(result_dir / f"attempt-{len(attempt_records) + 1}.json", {"attempt": attempt, "envelope": envelope})
            attempt_records.append(attempt)
            if not validation:
                final_report = parsed
                final_envelope = envelope
                model_reported = envelope.get("model") if isinstance(envelope.get("model"), str) else None
                selected_strategy = strategy_id
                break
        except Exception as error:
            attempt.update({
                "status": "error",
                "elapsed_seconds": time.perf_counter() - started,
                "error_type": type(error).__name__,
                "error": str(error),
                "error_fingerprint": sha256_bytes(f"{type(error).__name__}|{error}".encode("utf-8")),
            })
            write_json(result_dir / f"attempt-{len(attempt_records) + 1}.json", {"attempt": attempt, "envelope": envelope})
            attempt_records.append(attempt)
    if final_report is None:
        final_report = _failure_report("All three predeclared request/validation strategies failed.")
        final_envelope = {}
    frame_receipts = [
        {
            "frame_id": item["frame_id"],
            "relative_seconds": item["relative_seconds"],
            "absolute_seconds_private_receipt": item["absolute_seconds_private_receipt"],
            "sha256": item["sha256"],
            "bytes": item["bytes"],
            "scoreboard_redacted_rows": item["redacted_rows"],
        }
        for item in frames
    ]
    normalized = {
        "schema_version": "soccermaster-longform-normalized-window-v1",
        "window_id": window.window_id,
        "role": window.role,
        "source_half": window.source_half,
        "relative_frame_seconds": {item["frame_id"]: item["relative_seconds"] for item in frames},
        "report": final_report,
    }
    write_json(result_dir / "raw-response.json", final_envelope)
    write_json(result_dir / "normalized-report.json", normalized)
    valid = selected_strategy != "none"
    receipt = {
        "schema_version": "soccermaster-longform-vlm-call-receipt-v1",
        "recorded_at": utc_now(),
        "window_id": window.window_id,
        "window_role": window.role,
        "source_half": window.source_half,
        "media_sha256": window.media_sha256,
        "model": model,
        "model_reported": model_reported,
        "prompt_id": prompt_id,
        "prompt_sha256": prompt_sha,
        "status": "failed" if not valid else ("abstained" if final_report.get("abstain") else "complete"),
        "valid": valid,
        "abstain": bool(final_report.get("abstain")),
        "selected_strategy": selected_strategy,
        "attempt_count": len(attempt_records),
        "attempts": attempt_records,
        "total_elapsed_seconds": sum(float(item.get("elapsed_seconds", 0.0)) for item in attempt_records),
        "input_contract": {
            "visual_only": True,
            "audio_used": False,
            "commentary_used": False,
            "labels_used": False,
            "filenames_used": False,
            "team_names_used": False,
            "scores_used": False,
            "source_metadata_used": False,
            "absolute_timestamps_used": False,
            "scoreboard_redaction_top_fraction": SCOREBOARD_REDACTION_TOP_FRACTION,
            "ordered_frames": frame_receipts,
        },
        "raw_response_sha256": sha256_file(result_dir / "raw-response.json"),
        "normalized_report_sha256": sha256_file(result_dir / "normalized-report.json"),
        "performance_claim_allowed": False,
    }
    write_json(receipt_path, receipt)
    return receipt


def model_identity(endpoint: str, timeout_seconds: int = 20) -> dict[str, Any]:
    _loopback_endpoint(endpoint)
    request = urllib.request.Request(endpoint.rstrip("/") + "/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
    parsed = json.loads(raw)
    return {"response": parsed, "response_sha256": sha256_bytes(raw), "captured_at": utc_now()}


def _prompt_score(private_root: Path, prompt_id: str, windows: Sequence[Window]) -> dict[str, Any]:
    receipts = [read_json(_run_directory(private_root, window, prompt_id) / "receipt.json") for window in windows]
    valid = sum(bool(item.get("valid")) for item in receipts)
    primary = sum(item.get("selected_strategy") == "strict_json_schema_all_frames" for item in receipts)
    mean_attempts = sum(int(item.get("attempt_count", 0)) for item in receipts) / max(1, len(receipts))
    mean_latency = sum(float(item.get("total_elapsed_seconds", 0.0)) for item in receipts) / max(1, len(receipts))
    return {
        "prompt_id": prompt_id,
        "validation_window_count": len(receipts),
        "valid_count": valid,
        "valid_rate": valid / max(1, len(receipts)),
        "strict_primary_success_count": primary,
        "mean_attempts_per_window": mean_attempts,
        "mean_elapsed_seconds_per_window": mean_latency,
        "abstention_count": sum(bool(item.get("abstain")) for item in receipts),
        "selection_uses_labels": False,
        "selection_uses_semantic_correctness": False,
    }


def verify_protocol(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    protocol = read_json(artifact_root / "protocol-receipt.json")
    if protocol.get("schema_version") != PROTOCOL_VERSION:
        raise ValueError("unsupported frozen protocol")
    bindings = {
        "private_window_manifest_sha256": private_root / "experiment/window-manifest.jsonl",
        "prompt_candidates_sha256": artifact_root / "prompt-candidates.json",
        "query_set_sha256": artifact_root / "frozen-query-set.json",
        "response_schema_receipt_sha256": artifact_root / "response-schema-receipt.json",
    }
    if "pre_inference_amendments_sha256" in protocol.get("files", {}):
        bindings["pre_inference_amendments_sha256"] = artifact_root / "pre-inference-amendments.jsonl"
    for field, path in bindings.items():
        if not path.is_file() or sha256_file(path) != protocol.get("files", {}).get(field):
            raise ValueError(f"frozen protocol file changed: {field}")
    if sha256_file(private_root / "experiment/source-lock.json") != protocol["source"]["private_source_lock_sha256"]:
        raise ValueError("private source lock changed after protocol freeze")
    return protocol


def run_prompt_selection(
    *, private_root: Path, artifact_root: Path, endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL, timeout_seconds: int = 300,
) -> dict[str, Any]:
    protocol = verify_protocol(private_root, artifact_root)
    windows = [item for item in load_windows(private_root / "experiment/window-manifest.jsonl") if item.role == "validation_select"]
    if len(windows) != 6:
        raise ValueError("frozen validation selection must contain six windows")
    identity = model_identity(endpoint)
    served = [item.get("id") for item in identity.get("response", {}).get("data", []) if isinstance(item, dict)]
    if served != [model]:
        raise RuntimeError(f"loopback runtime model identity mismatch: {served}")
    write_json(artifact_root / "model-identity.json", identity)
    for prompt_id, prompt_text in PROMPT_CANDIDATES.items():
        for window in windows:
            run_one(
                private_root=private_root, window=window, prompt_id=prompt_id, prompt_text=prompt_text,
                endpoint=endpoint, model=model, timeout_seconds=timeout_seconds,
            )
    scores = [_prompt_score(private_root, prompt_id, windows) for prompt_id in PROMPT_CANDIDATES]
    development_selected = sorted(
        scores,
        key=lambda item: (
            -int(item["valid_count"]),
            -int(item["strict_primary_success_count"]),
            float(item["mean_attempts_per_window"]),
            float(item["mean_elapsed_seconds_per_window"]),
            str(item["prompt_id"]),
        ),
    )[0]
    development_prompt_id = str(development_selected["prompt_id"])
    if development_prompt_id != "candidate_b_evidence_first_v2":
        raise RuntimeError("the predeclared evidence-first delivery adaptation no longer matches validation selection")
    if len(DELIVERY_PROMPTS) != 1:
        raise RuntimeError("exactly one fixed safety-adapted delivery prompt is required")
    prompt_id, prompt_text = next(iter(DELIVERY_PROMPTS.items()))
    for window in windows:
        run_one(
            private_root=private_root, window=window, prompt_id=prompt_id, prompt_text=prompt_text,
            endpoint=endpoint, model=model, timeout_seconds=timeout_seconds,
        )
    delivery_score = _prompt_score(private_root, prompt_id, windows)
    selection = {
        "schema_version": "soccermaster-longform-prompt-selection-v1",
        "selected_at": utc_now(),
        "selected_prompt_id": prompt_id,
        "selected_prompt_sha256": sha256_bytes(prompt_text.encode("utf-8")),
        "candidate_scores": scores,
        "development_selected_prompt_id": development_prompt_id,
        "development_selected_prompt_sha256": sha256_bytes(PROMPT_CANDIDATES[development_prompt_id].encode("utf-8")),
        "delivery_validation": delivery_score,
        "selection_basis": "Label-free v2 structural selection, then a predeclared conservative 224p number-disabled v3 adaptation run on all six validation windows and frozen regardless of delivery-check outcome.",
        "delivery_freeze_regardless_of_validation_outcome": True,
        "jersey_number_claims_allowed": False,
        "labels_or_annotations_opened": False,
        "semantic_correctness_judged": False,
        "parameter_training": False,
    }
    write_json(artifact_root / "prompt-selection.json", selection)
    freeze = {
        "schema_version": "soccermaster-longform-frozen-test-config-v1",
        "locked_at": utc_now(),
        "protocol_receipt_sha256": sha256_file(artifact_root / "protocol-receipt.json"),
        "private_window_manifest_sha256": sha256_file(private_root / "experiment/window-manifest.jsonl"),
        "prompt_candidates_sha256": sha256_file(artifact_root / "prompt-candidates.json"),
        "prompt_selection_sha256": sha256_file(artifact_root / "prompt-selection.json"),
        "query_set_sha256": sha256_file(artifact_root / "frozen-query-set.json"),
        "response_schema_receipt_sha256": sha256_file(artifact_root / "response-schema-receipt.json"),
        "model_identity_sha256": sha256_file(artifact_root / "model-identity.json"),
        "selected_prompt_id": prompt_id,
        "selected_prompt_sha256": selection["selected_prompt_sha256"],
        "endpoint": endpoint,
        "model": model,
        "test_window_denominator": protocol["test"]["total_window_denominator"],
        "dense_window_denominator": protocol["test"]["dense_window_count"],
        "input_audio": False,
        "input_commentary": False,
        "input_labels": False,
        "input_source_metadata": False,
        "test_labels_semantics_opened": False,
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "frozen-test-config.json", freeze)
    return selection


def verify_freeze(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    verify_protocol(private_root, artifact_root)
    freeze = read_json(artifact_root / "frozen-test-config.json")
    bindings = {
        "protocol_receipt_sha256": artifact_root / "protocol-receipt.json",
        "private_window_manifest_sha256": private_root / "experiment/window-manifest.jsonl",
        "prompt_candidates_sha256": artifact_root / "prompt-candidates.json",
        "prompt_selection_sha256": artifact_root / "prompt-selection.json",
        "query_set_sha256": artifact_root / "frozen-query-set.json",
        "response_schema_receipt_sha256": artifact_root / "response-schema-receipt.json",
        "model_identity_sha256": artifact_root / "model-identity.json",
    }
    for field, path in bindings.items():
        if not path.is_file() or sha256_file(path) != freeze.get(field):
            raise ValueError(f"frozen test binding changed: {field}")
    prompt_id = str(freeze["selected_prompt_id"])
    if prompt_id not in ALL_PROMPTS or sha256_bytes(ALL_PROMPTS[prompt_id].encode("utf-8")) != freeze["selected_prompt_sha256"]:
        raise ValueError("selected prompt implementation changed after freeze")
    return freeze


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def report_search_text(report: dict[str, Any]) -> str:
    values: list[str] = [str(report.get("window_summary", ""))]
    values.extend(str(item) for item in report.get("tactics_observed", []))
    values.extend(str(item) for item in report.get("coach_search_terms", []))
    values.extend(str(item) for item in report.get("overall_uncertainties", []))
    for event in report.get("events", []):
        if not isinstance(event, dict):
            continue
        for field in (
            "event_type", "primary_action", "sequence_detail", "outcome", "phase_of_play", "coaching_relevance",
        ):
            values.append(str(event.get(field, "")))
        for field in ("field_areas", "search_terms", "uncertainties"):
            values.extend(str(item) for item in event.get(field, []))
        for participant in event.get("participants", []):
            if isinstance(participant, dict):
                for field in (
                    "player_reference", "visible_jersey_number", "team_reference", "role_in_event", "observable_action",
                ):
                    values.append(str(participant.get(field, "")))
    if report.get("abstain"):
        values.append(str(report.get("abstention_reason", "")))
    return " ".join(values)


def build_search_index(private_root: Path, artifact_root: Path, windows: Sequence[Window], prompt_id: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for window in windows:
        if window.role not in {"test_dense", "test_stress"}:
            continue
        normalized_path = _run_directory(private_root, window, prompt_id) / "normalized-report.json"
        if not normalized_path.is_file():
            continue
        normalized = read_json(normalized_path)
        report = normalized["report"]
        entries.append({
            "schema_version": "soccermaster-longform-search-entry-v1",
            "window_id": window.window_id,
            "window_role": window.role,
            "source_half": window.source_half,
            "start_seconds": window.start_seconds,
            "duration_seconds": window.duration_seconds,
            "visual_report_sha256": sha256_file(normalized_path),
            "abstain": bool(report.get("abstain")),
            "search_text": report_search_text(report),
            "report": report,
        })
    index_path = private_root / "experiment/soccer-search-index.jsonl"
    write_jsonl(index_path, entries)
    receipt = {
        "schema_version": "soccermaster-longform-search-index-receipt-v1",
        "generated_at": utc_now(),
        "entry_count": len(entries),
        "dense_entry_count": sum(item["window_role"] == "test_dense" for item in entries),
        "stress_entry_count": sum(item["window_role"] == "test_stress" for item in entries),
        "half_count": len({item["source_half"] for item in entries}),
        "durations_seconds": sorted({item["duration_seconds"] for item in entries}),
        "index_sha256": sha256_file(index_path),
        "index_location": "data/private only",
        "semantic_source": "frozen silent-frame local VLM reports only",
        "retrieval_algorithm": "deterministic BM25 over VLM-authored report text",
        "relevance_ground_truth": False,
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "search-index-receipt.json", receipt)
    return receipt


def bm25_search(entries: Sequence[dict[str, Any]], query: str, limit: int = 5) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    documents = [tokenize(str(item.get("search_text", ""))) for item in entries]
    terms = tokenize(query)
    if not documents or not terms:
        return []
    document_frequency = Counter(term for document in documents for term in set(document))
    average_length = sum(len(document) for document in documents) / len(documents)
    k1, b = 1.5, 0.75
    scores: list[tuple[float, int]] = []
    for index, document in enumerate(documents):
        frequency = Counter(document)
        score = 0.0
        for term in terms:
            df = document_frequency.get(term, 0)
            if not df:
                continue
            inverse = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
            count = frequency[term]
            denominator = count + k1 * (1.0 - b + b * len(document) / max(1.0, average_length))
            score += inverse * count * (k1 + 1.0) / denominator
        if score > 0:
            scores.append((score, index))
    scores.sort(key=lambda item: (-item[0], entries[item[1]]["window_id"]))
    results: list[dict[str, Any]] = []
    for rank, (score, index) in enumerate(scores[:limit], start=1):
        item = entries[index]
        results.append({
            "rank": rank,
            "score": score,
            "window_id": item["window_id"],
            "window_role": item["window_role"],
            "source_half": item["source_half"],
            "start_seconds": item["start_seconds"],
            "duration_seconds": item["duration_seconds"],
            "abstain": item["abstain"],
            "summary": item["report"].get("window_summary", ""),
        })
    return results


def run_frozen_queries(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    freeze = verify_freeze(private_root, artifact_root)
    query_path = artifact_root / "frozen-query-set.json"
    if sha256_file(query_path) != freeze["query_set_sha256"]:
        raise ValueError("query set drifted after test freeze")
    index_path = private_root / "experiment/soccer-search-index.jsonl"
    entries = read_jsonl(index_path)
    rows: list[dict[str, Any]] = []
    for query in read_json(query_path)["queries"]:
        top = bm25_search(entries, query["text"], limit=5)
        rows.append({**query, "candidate_count": len(top), "top_results": top})
    packet = {
        "schema_version": "soccermaster-longform-frozen-query-results-v1",
        "generated_at": utc_now(),
        "query_set_sha256": sha256_file(query_path),
        "private_index_sha256": sha256_file(index_path),
        "query_count": len(rows),
        "index_entry_count": len(entries),
        "dense_index_entry_count": sum(item["window_role"] == "test_dense" for item in entries),
        "accuracy_or_relevance_measured_before_annotation_join": False,
        "results": rows,
    }
    write_json(artifact_root / "frozen-query-results.json", packet)
    return packet


def _summarize_test_receipts(receipts: Sequence[dict[str, Any]], windows: Sequence[Window]) -> dict[str, Any]:
    elapsed = [float(item.get("total_elapsed_seconds", 0.0)) for item in receipts]
    event_count = 0
    event_histogram: Counter[str] = Counter()
    for receipt, window in zip(receipts, windows):
        report = read_json(_run_directory(Path(receipt["_private_root"]), window, str(receipt["prompt_id"])) / "normalized-report.json")["report"]
        for event in report.get("events", []):
            event_count += 1
            event_histogram[str(event.get("event_type", "unknown"))] += 1
    return {
        "schema_version": "soccermaster-longform-report-metrics-v1",
        "generated_at": utc_now(),
        "window_denominator": len(receipts),
        "dense_window_denominator": sum(item.role == "test_dense" for item in windows),
        "stress_window_denominator": sum(item.role == "test_stress" for item in windows),
        "valid_response_count": sum(bool(item.get("valid")) for item in receipts),
        "failure_count": sum(not bool(item.get("valid")) for item in receipts),
        "abstention_count": sum(bool(item.get("abstain")) for item in receipts),
        "model_request_count_including_recoveries": sum(int(item.get("attempt_count", 0)) for item in receipts),
        "primary_strict_success_count": sum(item.get("selected_strategy") == "strict_json_schema_all_frames" for item in receipts),
        "recovery_strategy_counts": dict(sorted(Counter(str(item.get("selected_strategy")) for item in receipts).items())),
        "latency_seconds_per_window": {
            "minimum": min(elapsed) if elapsed else None,
            "median": statistics.median(elapsed) if elapsed else None,
            "mean": statistics.fmean(elapsed) if elapsed else None,
            "maximum": max(elapsed) if elapsed else None,
            "accumulated": sum(elapsed),
        },
        "vlm_reported_event_count": event_count,
        "vlm_event_type_histogram_unverified": dict(sorted(event_histogram.items())),
        "event_accuracy_measured_before_seal": False,
        "detailed_claim_factuality_measured": False,
        "performance_claim_allowed": False,
    }


def run_test(
    *, private_root: Path, artifact_root: Path, timeout_seconds: int = 300,
) -> dict[str, Any]:
    freeze = verify_freeze(private_root, artifact_root)
    prompt_id = str(freeze["selected_prompt_id"])
    prompt_text = ALL_PROMPTS[prompt_id]
    windows = [
        item for item in load_windows(private_root / "experiment/window-manifest.jsonl")
        if item.role in {"test_dense", "test_stress"}
    ]
    if len(windows) != int(freeze["test_window_denominator"]):
        raise ValueError("test window denominator differs from frozen configuration")
    receipts: list[dict[str, Any]] = []
    for window in windows:
        receipt = run_one(
            private_root=private_root, window=window, prompt_id=prompt_id, prompt_text=prompt_text,
            endpoint=str(freeze["endpoint"]), model=str(freeze["model"]), timeout_seconds=timeout_seconds,
        )
        receipt = dict(receipt)
        receipt["_private_root"] = str(private_root)
        receipts.append(receipt)
    metrics = _summarize_test_receipts(receipts, windows)
    write_json(artifact_root / "report-metrics.json", metrics)
    index_receipt = build_search_index(private_root, artifact_root, windows, prompt_id)
    query_results = run_frozen_queries(private_root, artifact_root)
    run_receipt = {
        "schema_version": "soccermaster-longform-test-run-receipt-v1",
        "completed_at": utc_now(),
        "status": "complete" if metrics["failure_count"] == 0 else "complete_with_failures",
        "frozen_test_config_sha256": sha256_file(artifact_root / "frozen-test-config.json"),
        "window_denominator": len(windows),
        "dense_window_denominator": metrics["dense_window_denominator"],
        "stress_window_denominator": metrics["stress_window_denominator"],
        "valid_response_count": metrics["valid_response_count"],
        "failure_count": metrics["failure_count"],
        "abstention_count": metrics["abstention_count"],
        "model_request_count_including_recoveries": metrics["model_request_count_including_recoveries"],
        "model": freeze["model"],
        "selected_prompt_id": prompt_id,
        "selected_prompt_sha256": freeze["selected_prompt_sha256"],
        "report_metrics_sha256": sha256_file(artifact_root / "report-metrics.json"),
        "private_index_sha256": index_receipt["index_sha256"],
        "frozen_query_results_sha256": sha256_file(artifact_root / "frozen-query-results.json"),
        "labels_loaded_during_inference": False,
        "audio_used": False,
        "commentary_used": False,
        "source_metadata_used": False,
        "annotation_accuracy_measured": False,
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "test-run-receipt.json", run_receipt)
    return {"run_receipt": run_receipt, "metrics": metrics, "query_count": query_results["query_count"]}


def seal_predictions(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    required_public = (
        "source-verification-receipt.json",
        "protocol-receipt.json",
        "prompt-candidates.json",
        "frozen-query-set.json",
        "response-schema-receipt.json",
        "model-identity.json",
        "prompt-selection.json",
        "frozen-test-config.json",
        "report-metrics.json",
        "search-index-receipt.json",
        "frozen-query-results.json",
        "test-run-receipt.json",
    )
    missing = [name for name in required_public if not (artifact_root / name).is_file()]
    if missing:
        raise FileNotFoundError("cannot seal incomplete visual run: " + ", ".join(missing))
    files: dict[str, str] = {}
    private_experiment = private_root / "experiment"
    for path in sorted(private_experiment.rglob("*")):
        if path.is_file():
            files["private/" + path.relative_to(private_experiment).as_posix()] = sha256_file(path)
    excluded_public = {
        "prediction-seal.json", "annotation-evaluation.json", "annotation-evaluation-receipt.json",
        "spot-check-adjudication.json", "verification-receipt.json", "package-receipt.json",
    }
    for path in sorted(artifact_root.rglob("*")):
        if path.is_file() and path.name not in excluded_public:
            files["public/" + path.relative_to(artifact_root).as_posix()] = sha256_file(path)
    seal = {
        "schema_version": "soccermaster-longform-visual-prediction-seal-v1",
        "sealed_at": utc_now(),
        "purpose": "prove all visual model outputs and frozen retrieval results predate annotation evaluation",
        "file_count": len(files),
        "files": files,
        "root_hash": sha256_bytes(canonical_json(files)),
        "audio_or_commentary_included": False,
        "annotation_semantics_opened_before_seal": False,
    }
    write_json(artifact_root / "prediction-seal.json", seal)
    return seal


def verify_seal(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    seal = read_json(artifact_root / "prediction-seal.json")
    observed: dict[str, str] = {}
    for key, expected in seal.get("files", {}).items():
        scope, relative = key.split("/", 1)
        base = private_root / "experiment" if scope == "private" else artifact_root
        path = base / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"sealed visual artifact changed: {key}")
        observed[key] = expected
    if sha256_bytes(canonical_json(observed)) != seal.get("root_hash"):
        raise ValueError("visual prediction seal root hash mismatch")
    return seal


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    value = successes / total
    denominator = 1 + z * z / total
    center = (value + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(value * (1 - value) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _load_annotations(labels_path: Path) -> list[dict[str, Any]]:
    labels = read_json(labels_path)
    raw = labels.get("annotations")
    if not isinstance(raw, list):
        raise ValueError("SoccerNet-v2 label file has no annotations")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("visibility") != "visible":
            continue
        event_type = SOCCERNET_LABEL_TO_EVENT.get(str(item.get("label")))
        game_time = str(item.get("gameTime", ""))
        if event_type is None or not re.match(r"^[12] - ", game_time):
            continue
        rows.append({
            "annotation_id": "ann-" + stable_id(game_time, item.get("position"), item.get("label")),
            "source_half": int(game_time[0]),
            "position_seconds": float(item["position"]) / 1000.0,
            "source_label": str(item["label"]),
            "event_type": event_type,
        })
    return sorted(rows, key=lambda item: (item["source_half"], item["position_seconds"], item["annotation_id"]))


def evaluate_annotations(private_root: Path, artifact_root: Path, tolerance_seconds: float = 6.0) -> dict[str, Any]:
    """Open SoccerNet labels only after sealing and evaluate—not detect—events."""
    seal = verify_seal(private_root, artifact_root)
    freeze = verify_freeze(private_root, artifact_root)
    source_lock = read_json(private_root / "experiment/source-lock.json")
    labels_path = Path(source_lock["test"]["labels_path"])
    if sha256_file(labels_path) != source_lock["test"]["labels_sha256"]:
        raise ValueError("post-seal annotation hash mismatch")
    annotations = _load_annotations(labels_path)
    windows = [
        item for item in load_windows(private_root / "experiment/window-manifest.jsonl")
        if item.role == "test_dense"
    ]
    prompt_id = str(freeze["selected_prompt_id"])
    window_reports: dict[str, dict[str, Any]] = {}
    for window in windows:
        window_reports[window.window_id] = read_json(
            _run_directory(private_root, window, prompt_id) / "normalized-report.json"
        )
    joined: list[dict[str, Any]] = []
    for annotation in annotations:
        candidates = [
            item for item in windows
            if item.source_half == annotation["source_half"]
            and item.start_seconds <= annotation["position_seconds"]
            and (annotation["position_seconds"] < item.end_seconds or math.isclose(annotation["position_seconds"], item.end_seconds))
        ]
        window = sorted(candidates, key=lambda item: (item.start_seconds, item.window_id))[0] if candidates else None
        if window is None:
            joined.append({**annotation, "window_id": None, "type_present_in_window_report": False, "temporally_corroborated": False})
            continue
        normalized = window_reports[window.window_id]
        relative = normalized["relative_frame_seconds"]
        matches: list[dict[str, Any]] = []
        for event in normalized["report"].get("events", []):
            if event.get("event_type") != annotation["event_type"]:
                continue
            start = window.start_seconds + float(relative[event["start_frame_id"]])
            end = window.start_seconds + float(relative[event["end_frame_id"]])
            matches.append({
                "start_seconds": start,
                "end_seconds": end,
                "temporally_corroborated": start - tolerance_seconds <= annotation["position_seconds"] <= end + tolerance_seconds,
            })
        joined.append({
            **annotation,
            "window_id": window.window_id,
            "type_present_in_window_report": bool(matches),
            "temporally_corroborated": any(item["temporally_corroborated"] for item in matches),
        })
    predicted_rows: list[dict[str, Any]] = []
    supported_types = set(SOCCERNET_LABEL_TO_EVENT.values())
    for window in windows:
        normalized = window_reports[window.window_id]
        relative = normalized["relative_frame_seconds"]
        for event_index, event in enumerate(normalized["report"].get("events", [])):
            event_type = str(event.get("event_type"))
            if event_type not in supported_types:
                continue
            start = window.start_seconds + float(relative[event["start_frame_id"]])
            end = window.start_seconds + float(relative[event["end_frame_id"]])
            corroborated = any(
                item["source_half"] == window.source_half
                and item["event_type"] == event_type
                and start - tolerance_seconds <= item["position_seconds"] <= end + tolerance_seconds
                for item in annotations
            )
            predicted_rows.append({
                "prediction_id": f"{window.window_id}:e{event_index + 1:02d}",
                "window_id": window.window_id,
                "source_half": window.source_half,
                "event_type": event_type,
                "temporally_corroborated": corroborated,
            })
    class_rows: dict[str, dict[str, Any]] = {}
    for event_type in sorted(set(item["event_type"] for item in annotations) | set(item["event_type"] for item in predicted_rows)):
        truth = [item for item in joined if item["event_type"] == event_type]
        predictions = [item for item in predicted_rows if item["event_type"] == event_type]
        recalled = sum(item["temporally_corroborated"] for item in truth)
        corroborated = sum(item["temporally_corroborated"] for item in predictions)
        class_rows[event_type] = {
            "annotation_support": len(truth),
            "temporally_corroborated_annotations": recalled,
            "annotation_recall": recalled / len(truth) if truth else None,
            "vlm_prediction_count": len(predictions),
            "temporally_corroborated_predictions": corroborated,
            "restricted_precision": corroborated / len(predictions) if predictions else None,
        }
    recall_count = sum(item["temporally_corroborated"] for item in joined)
    precision_count = sum(item["temporally_corroborated"] for item in predicted_rows)

    query_packet = read_json(artifact_root / "frozen-query-results.json")
    annotations_by_window: dict[str, set[str]] = {}
    for item in joined:
        if item["window_id"] is not None:
            annotations_by_window.setdefault(str(item["window_id"]), set()).add(str(item["event_type"]))
    query_corroboration: list[dict[str, Any]] = []
    for query in query_packet["results"]:
        facet = str(query["facet"])
        if facet not in supported_types:
            continue
        results = query["top_results"]
        corroborated = sum(facet in annotations_by_window.get(str(item["window_id"]), set()) for item in results)
        query_corroboration.append({
            "query_id": query["query_id"],
            "facet": facet,
            "retrieved_count": len(results),
            "annotation_corroborated_count": corroborated,
            "annotation_corroborated_precision_at_up_to_5": corroborated / len(results) if results else None,
        })
    evaluation = {
        "schema_version": "soccermaster-longform-post-seal-annotation-evaluation-v1",
        "evaluated_at": utc_now(),
        "visual_prediction_seal_root_hash": seal["root_hash"],
        "labels_sha256": sha256_file(labels_path),
        "labels_opened_only_after_visual_prediction_seal_verified": True,
        "annotation_role": "post-hoc evaluator only; annotations did not generate candidates or model reports",
        "dense_window_denominator": len(windows),
        "mapped_visible_annotation_denominator": len(joined),
        "temporally_corroborated_annotation_count": recall_count,
        "restricted_mapped_annotation_recall": recall_count / len(joined) if joined else None,
        "restricted_mapped_annotation_recall_wilson_95": _wilson(recall_count, len(joined)),
        "mapped_vlm_prediction_denominator": len(predicted_rows),
        "temporally_corroborated_prediction_count": precision_count,
        "restricted_mapped_prediction_precision": precision_count / len(predicted_rows) if predicted_rows else None,
        "restricted_mapped_prediction_precision_wilson_95": _wilson(precision_count, len(predicted_rows)),
        "temporal_tolerance_seconds": tolerance_seconds,
        "per_event_type": class_rows,
        "frozen_query_annotation_corroboration": query_corroboration,
        "unscored_event_types": sorted(set(EVENT_TYPES) - supported_types),
        "detailed_prose_actor_outcome_tactics_factuality_evaluated": False,
        "evaluation_limitations": [
            "SoccerNet-v2 labels cover selected broadcast actions, not every pass, duel, press, tactical phase, or coaching concept.",
            "The VLM sees sparse frames, not continuous video tokens, so temporal corroboration is tolerance-based.",
            "One newly held-out game is insufficient for a generalization or deployment claim.",
            "A matching event type near an annotation does not validate the report's actor, outcome, trajectory, or tactical prose.",
        ],
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "annotation-evaluation.json", evaluation)
    private_eval = private_root / "evaluation"
    write_jsonl(private_eval / "annotation-joins.jsonl", joined)
    write_jsonl(private_eval / "mapped-vlm-predictions.jsonl", predicted_rows)
    receipt = {
        "schema_version": "soccermaster-longform-annotation-evaluation-receipt-v1",
        "generated_at": utc_now(),
        "prediction_seal_root_hash": seal["root_hash"],
        "evaluation_sha256": sha256_file(artifact_root / "annotation-evaluation.json"),
        "private_annotation_join_sha256": sha256_file(private_eval / "annotation-joins.jsonl"),
        "private_prediction_join_sha256": sha256_file(private_eval / "mapped-vlm-predictions.jsonl"),
        "labels_opened_post_seal": True,
        "annotation_is_evaluator_not_detector": True,
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "annotation-evaluation-receipt.json", receipt)
    return evaluation


def prepare_spotcheck_packet(private_root: Path, artifact_root: Path) -> dict[str, Any]:
    verify_seal(private_root, artifact_root)
    protocol = read_json(artifact_root / "protocol-receipt.json")
    freeze = verify_freeze(private_root, artifact_root)
    selected = set(protocol["test"]["spot_check_window_ids"])
    windows = {
        item.window_id: item
        for item in load_windows(private_root / "experiment/window-manifest.jsonl")
        if item.window_id in selected
    }
    joins = read_jsonl(private_root / "evaluation/annotation-joins.jsonl")
    rows: list[dict[str, Any]] = []
    for window_id in protocol["test"]["spot_check_window_ids"]:
        window = windows[window_id]
        result_dir = _run_directory(private_root, window, str(freeze["selected_prompt_id"]))
        frames = sorted((result_dir / "frames").glob("F*.jpg"))
        rows.append({
            "window_id": window_id,
            "source_half": window.source_half,
            "start_seconds": window.start_seconds,
            "duration_seconds": window.duration_seconds,
            "normalized_report_path": str((result_dir / "normalized-report.json").resolve()),
            "normalized_report_sha256": sha256_file(result_dir / "normalized-report.json"),
            "frame_paths": [str(path.resolve()) for path in frames],
            "frame_sha256s": [sha256_file(path) for path in frames],
            "post_seal_annotations_in_window": [
                {key: item[key] for key in ("annotation_id", "position_seconds", "source_label", "event_type")}
                for item in joins if item.get("window_id") == window_id
            ],
        })
    packet = {
        "schema_version": "soccermaster-longform-private-spotcheck-packet-v1",
        "generated_at": utc_now(),
        "selection_frozen_before_test": True,
        "visual_prediction_seal_root_hash": read_json(artifact_root / "prediction-seal.json")["root_hash"],
        "window_count": len(rows),
        "rows": rows,
    }
    write_json(private_root / "evaluation/spot-check-packet.json", packet)
    return packet


def _scan_package_isolation(project_root: Path) -> list[str]:
    violations: list[str] = []
    package_root = project_root / "prototype/soccermaster_longform"
    forbidden = ("football" + "master", "multi" + "sport")
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for token in forbidden:
            if token in text:
                violations.append(f"{path.relative_to(project_root).as_posix()} contains forbidden token {token}")
    return violations


def _source_identity_terms(source_game: str) -> list[str]:
    basename = source_game.replace("\\", "/").split("/")[-1]
    match = re.match(r"^\d{4}-\d{2}-\d{2} - \d{2}-\d{2} (.+?) \d+ - \d+ (.+)$", basename)
    if not match:
        return [basename.lower()]
    return [match.group(1).lower(), match.group(2).lower(), basename.lower()]


def verify_experiment(project_root: Path, private_root: Path, artifact_root: Path) -> dict[str, Any]:
    source = read_json(artifact_root / "source-verification-receipt.json")
    protocol = verify_protocol(private_root, artifact_root)
    freeze = verify_freeze(private_root, artifact_root)
    seal = verify_seal(private_root, artifact_root)
    windows = load_windows(private_root / "experiment/window-manifest.jsonl")
    validation = [item for item in windows if item.role == "validation_select"]
    dense = [item for item in windows if item.role == "test_dense"]
    stress = [item for item in windows if item.role == "test_stress"]
    test_windows = dense + stress
    prompt_id = str(freeze["selected_prompt_id"])
    call_errors: list[str] = []
    receipts: list[dict[str, Any]] = []
    for candidate_id in ALL_PROMPTS:
        for window in validation:
            path = _run_directory(private_root, window, candidate_id) / "receipt.json"
            if not path.is_file():
                call_errors.append(f"missing validation receipt {candidate_id}:{window.window_id}")
            else:
                receipts.append(read_json(path))
    for window in test_windows:
        path = _run_directory(private_root, window, prompt_id) / "receipt.json"
        if not path.is_file():
            call_errors.append(f"missing test receipt {window.window_id}")
        else:
            receipts.append(read_json(path))
    source_lock = read_json(private_root / "experiment/source-lock.json")
    forbidden_identity = _source_identity_terms(str(source_lock["test"]["source_game"]))
    for receipt in receipts:
        result_dir: Path | None = None
        window_id = str(receipt.get("window_id"))
        matching = next((item for item in windows if item.window_id == window_id), None)
        if matching is None:
            call_errors.append(f"unknown receipt window {window_id}")
            continue
        result_dir = _run_directory(private_root, matching, str(receipt.get("prompt_id")))
        raw_path = result_dir / "raw-response.json"
        normalized_path = result_dir / "normalized-report.json"
        if not raw_path.is_file() or receipt.get("raw_response_sha256") != sha256_file(raw_path):
            call_errors.append(f"raw response hash {window_id}")
        if not normalized_path.is_file() or receipt.get("normalized_report_sha256") != sha256_file(normalized_path):
            call_errors.append(f"normalized report hash {window_id}")
        contract = receipt.get("input_contract", {})
        expected_false = (
            "audio_used", "commentary_used", "labels_used", "filenames_used", "team_names_used", "scores_used",
            "source_metadata_used", "absolute_timestamps_used",
        )
        if any(contract.get(field) is not False for field in expected_false):
            call_errors.append(f"input leakage contract {window_id}")
        if contract.get("scoreboard_redaction_top_fraction") != SCOREBOARD_REDACTION_TOP_FRACTION:
            call_errors.append(f"scoreboard redaction contract {window_id}")
        for attempt in receipt.get("attempts", []):
            request_receipt = attempt.get("request_receipt", {})
            request_text = str(request_receipt.get("prompt_text", "")).lower()
            if any(term and term in request_text for term in forbidden_identity):
                call_errors.append(f"source identity text leakage {window_id}")
            if (
                request_receipt.get("audio_used") is not False
                or request_receipt.get("commentary_used") is not False
                or request_receipt.get("labels_used") is not False
                or request_receipt.get("absolute_timestamps_used") is not False
                or request_receipt.get("source_metadata_fields_used") != []
            ):
                call_errors.append(f"attempt leakage contract {window_id}")
        first_frame = result_dir / "frames/F00.jpg"
        if first_frame.is_file():
            import cv2  # type: ignore

            image = cv2.imread(str(first_frame))
            if image is None:
                call_errors.append(f"redacted frame decode {window_id}")
            else:
                redacted_rows = max(1, int(math.ceil(image.shape[0] * SCOREBOARD_REDACTION_TOP_FRACTION)))
                audit_rows = max(1, redacted_rows // 2)
                if float(image[:audit_rows, :].mean()) > 2.0:
                    call_errors.append(f"scoreboard pixels not blacked out {window_id}")

    evaluation = read_json(artifact_root / "annotation-evaluation.json")
    evaluation_receipt = read_json(artifact_root / "annotation-evaluation-receipt.json")
    query_results = read_json(artifact_root / "frozen-query-results.json")
    metrics = read_json(artifact_root / "report-metrics.json")
    run_receipt = read_json(artifact_root / "test-run-receipt.json")
    spot_path = artifact_root / "spot-check-adjudication.json"
    spot = read_json(spot_path) if spot_path.is_file() else {}
    expected_spots = set(protocol["test"]["spot_check_window_ids"])
    observed_spots = {str(item.get("window_id")) for item in spot.get("rows", []) if isinstance(item, dict)}
    isolation = _scan_package_isolation(project_root)
    checks: dict[str, Any] = {
        "source_status": source.get("status"),
        "source_complete_halves": len(source.get("assets", [])),
        "source_full_decode": all(item.get("full_video_decode") == "pass" for item in source.get("assets", [])),
        "source_labels_unopened_at_verification": source.get("labels_semantics_opened") is False,
        "untouched_test_game": protocol["source"].get("untouched_by_existing_eight_game_manifest") is True and protocol["source"].get("untouched_by_prior_vlm_input_receipts") is True,
        "validation_window_count": len(validation),
        "validation_prompt_call_denominator": len(validation) * len(ALL_PROMPTS),
        "dense_window_count": len(dense),
        "dense_counts_by_half": {str(half): sum(item.source_half == half for item in dense) for half in (1, 2)},
        "stress_window_count": len(stress),
        "stress_durations": sorted({item.duration_seconds for item in stress}),
        "minimum_test_frames": min(item.frame_count for item in test_windows),
        "test_window_denominator": len(test_windows),
        "test_valid_response_count": metrics.get("valid_response_count"),
        "test_failure_count": metrics.get("failure_count"),
        "run_denominator_binding": run_receipt.get("window_denominator") == len(test_windows),
        "call_receipt_errors": call_errors,
        "visual_prediction_seal": bool(seal.get("root_hash")),
        "labels_opened_only_post_seal": evaluation.get("labels_opened_only_after_visual_prediction_seal_verified") is True,
        "annotation_is_evaluator": evaluation_receipt.get("annotation_is_evaluator_not_detector") is True,
        "annotation_denominator": evaluation.get("mapped_visible_annotation_denominator"),
        "frozen_query_count": query_results.get("query_count"),
        "private_index_entry_count": query_results.get("index_entry_count"),
        "spot_check_window_ids": sorted(observed_spots),
        "spot_check_receipt_bound": spot.get("prediction_seal_root_hash") == seal.get("root_hash"),
        "spot_check_judgment_counts": spot.get("judgment_counts"),
        "input_anonymization_audit_status": spot.get("input_anonymization_audit", {}).get("status"),
        "team_name_pixels_fully_unavailable": spot.get("input_anonymization_audit", {}).get("status") != "failed_in_at_least_one_sampled_frame",
        "performance_claim_allowed": spot.get("performance_claim_allowed"),
        "package_isolation_violations": isolation,
    }
    expected = {
        "source_status": "pass",
        "source_complete_halves": 2,
        "source_full_decode": True,
        "source_labels_unopened_at_verification": True,
        "untouched_test_game": True,
        "validation_window_count": 6,
        "validation_prompt_call_denominator": 18,
        "dense_window_count": 90,
        "dense_counts_by_half": {"1": 45, "2": 45},
        "stress_window_count": 6,
        "stress_durations": [30, 60, 120],
        "minimum_test_frames": 8,
        "test_window_denominator": 96,
        "run_denominator_binding": True,
        "call_receipt_errors": [],
        "visual_prediction_seal": True,
        "labels_opened_only_post_seal": True,
        "annotation_is_evaluator": True,
        "frozen_query_count": len(QUERY_SET),
        "private_index_entry_count": 96,
        "spot_check_window_ids": sorted(expected_spots),
        "spot_check_receipt_bound": True,
        "spot_check_judgment_counts": {
            "supported": 0,
            "partially_supported": 2,
            "unsupported": 4,
            "abstention_appropriate": 0,
        },
        "input_anonymization_audit_status": "failed_in_at_least_one_sampled_frame",
        "team_name_pixels_fully_unavailable": False,
        "performance_claim_allowed": False,
        "package_isolation_violations": [],
    }
    failures = {key: {"expected": value, "observed": checks.get(key)} for key, value in expected.items() if checks.get(key) != value}
    result = {
        "schema_version": "soccermaster-longform-verification-receipt-v1",
        "verified_at": utc_now(),
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "visual_prediction_seal_root_hash": seal["root_hash"],
        "independent_verification": "pending distinct agent",
    }
    write_json(artifact_root / "verification-receipt.json", result)
    if failures:
        raise ValueError("SoccerMaster long-form verification failed: " + json.dumps(failures, sort_keys=True))
    return result


def write_technical_report(project_root: Path, private_root: Path, artifact_root: Path, report_path: Path) -> Path:
    protocol = read_json(artifact_root / "protocol-receipt.json")
    selection = read_json(artifact_root / "prompt-selection.json")
    metrics = read_json(artifact_root / "report-metrics.json")
    evaluation = read_json(artifact_root / "annotation-evaluation.json")
    queries = read_json(artifact_root / "frozen-query-results.json")
    spot = read_json(artifact_root / "spot-check-adjudication.json")
    test_hours = float(protocol["source"]["duration_seconds"]) / 3600.0
    validity = metrics["valid_response_count"] / metrics["window_denominator"] if metrics["window_denominator"] else 0.0
    abstention = metrics["abstention_count"] / metrics["window_denominator"] if metrics["window_denominator"] else 0.0
    recall = evaluation.get("restricted_mapped_annotation_recall")
    precision = evaluation.get("restricted_mapped_prediction_precision")
    query_hits = sum(item["candidate_count"] > 0 for item in queries["results"])
    spot_supported = sum(item.get("overall_judgment") == "supported" for item in spot.get("rows", []))
    spot_partial = sum(item.get("overall_judgment") == "partially_supported" for item in spot.get("rows", []))
    spot_unsupported = sum(item.get("overall_judgment") == "unsupported" for item in spot.get("rows", []))
    v2_requests = round(sum(
        float(item["validation_window_count"]) * float(item["mean_attempts_per_window"])
        for item in selection["candidate_scores"]
    ))
    delivery_requests = round(
        float(selection["delivery_validation"]["validation_window_count"])
        * float(selection["delivery_validation"]["mean_attempts_per_window"])
    )
    recall_text = "not estimable" if recall is None else (
        f"{recall:.3%} ({evaluation['temporally_corroborated_annotation_count']}/"
        f"{evaluation['mapped_visible_annotation_denominator']})"
    )
    precision_text = "not estimable" if precision is None else (
        f"{precision:.3%} ({evaluation['temporally_corroborated_prediction_count']}/"
        f"{evaluation['mapped_vlm_prediction_denominator']})"
    )
    lines = [
        "# SoccerMaster long-form VLM/search scale experiment",
        "",
        "**Status:** completed single-game held-out systems experiment; deployment and coach-utility **NO-GO**",
        "",
        "## Answer first",
        "",
        f"The pipeline densely indexed both halves of one newly acquired, untouched authorized SoccerNet test game ({test_hours:.3f} h) with 90 contiguous 60-second windows at a 60-second stride, plus six locked 30/60/120-second stress windows. "
        f"The selected local Gemma prompt produced {metrics['valid_response_count']}/{metrics['window_denominator']} schema-valid test reports ({validity:.1%}); {metrics['abstention_count']}/{metrics['window_denominator']} reports abstained ({abstention:.1%}).",
        "",
        "This is a larger real-footage VLM/search experiment, not evidence that the prose is correct or useful to coaches. SoccerNet labels were opened only after every visual output and query result was hash-sealed. The post-hoc evaluator covers selected SoccerNet-v2 actions, not long balls, most passes, duels, pressing, player identity, or tactics.",
        "",
        "## Frozen protocol",
        "",
        "| Property | Frozen value |",
        "|---|---:|",
        f"| New official SoccerNet test games | 1 |",
        f"| Complete halves | 2 |",
        f"| Dense visual test calls | {protocol['test']['dense_window_count']} |",
        f"| Duration-stress test calls | {protocol['test']['duration_stress_window_count']} |",
        f"| Total test denominator | {protocol['test']['total_window_denominator']} |",
        f"| v2 structural-selection window/candidate pairs | 12 |",
        f"| v2 actual requests including recovery | {v2_requests} |",
        f"| v3 number-disabled delivery checks / requests | 6 / {delivery_requests} |",
        f"| Final frozen development + test window denominator | {18 + protocol['test']['total_window_denominator']} |",
        f"| Final frozen development + test actual requests | {v2_requests + delivery_requests + metrics['model_request_count_including_recoveries']} |",
        f"| Preserved pre-amendment diagnostic requests | 3 |",
        f"| Minimum ordered frames | {protocol['test']['minimum_ordered_frames']} |",
        f"| Selected prompt | `{selection['selected_prompt_id']}` |",
        "",
        "Prompt selection used only schema validity, strict first-attempt success, attempts, and latency on a pre-existing validation game. It used no correctness labels and is prompt selection—not parameter fine-tuning. The selected evidence-first v2 prompt was conservatively adapted to a number-disabled v3 contract after low-resolution validation exposed unsupported numeral claims; v3 then passed 6/6 fresh structural delivery checks before test freeze.",
        "",
        "## Leakage and privacy controls",
        "",
        "- No audio, commentary, labels, filenames, scores, game identity, source metadata, or absolute match clock was deliberately supplied as nonvisual request data.",
        "- The prompt prohibited player/team names and the v3 schema prohibited all jersey-number claims.",
        "- The top 16% of every frame was blacked out before inference to remove the broadcast score/clock overlay.",
        "- **Post-seal anonymization failure:** one of six predeclared checks contained a readable lower-third team-name graphic outside that top mask. The model report did not repeat the name, but the experiment is not fully identity-leakage-free and no leakage-free performance claim is allowed.",
        "- Requests used only anonymous relative frame IDs and offsets.",
        "- Raw media, redacted frames, raw responses, source names, labels, and the full search index remain under `data/private` and are not redistributable.",
        "- A visual prediction seal binds the prompt, all requests/responses/reports, index, and frozen query results before annotations were parsed.",
        "",
        "## Structural and latency results",
        "",
        f"- Valid reports: {metrics['valid_response_count']}/{metrics['window_denominator']}.",
        f"- Runtime failures: {metrics['failure_count']}/{metrics['window_denominator']}.",
        f"- Strict first-attempt successes: {metrics['primary_strict_success_count']}/{metrics['window_denominator']}.",
        f"- VLM-authored events: {metrics['vlm_reported_event_count']} (unverified before annotation join).",
        f"- Median/mean/max per-window request time: {metrics['latency_seconds_per_window']['median']:.3f} / {metrics['latency_seconds_per_window']['mean']:.3f} / {metrics['latency_seconds_per_window']['maximum']:.3f} seconds.",
        "",
        "## Post-seal SoccerNet evaluator",
        "",
        f"Mapped visible SoccerNet annotations: {evaluation['mapped_visible_annotation_denominator']}. "
        f"Tolerance-based restricted annotation recall was {recall_text}.",
        f"Restricted precision among VLM predictions whose types exist in the SoccerNet mapping was {precision_text}.",
        "",
        "These restricted numbers are not dense action-spotting mAP and do not score detailed prose. Matching a coarse event type near an annotation does not validate actor, outcome, trajectory, tactical interpretation, or coaching relevance.",
        "",
        "## Search behavior and direct inspection",
        "",
        f"The frozen BM25 query suite returned at least one VLM-authored candidate for {query_hits}/{queries['query_count']} queries. No human relevance set exists, so this measures only whether the reports are searchable.",
        f"A predeclared six-window first/middle/last visual audit judged {spot_supported}/6 reports fully supported, {spot_partial}/6 partially supported, and {spot_unsupported}/6 unsupported. These six windows are illustrative rather than a factuality-rate estimate, but they independently demonstrate major event and continuity hallucinations despite 100% schema validity.",
        "",
        "## Safe claims",
        "",
        "- The system can reproducibly window and process a complete two-half SoccerNet game with a silent local VLM and build a searchable private index.",
        "- Protocol, model inputs, recoveries, outputs, retrieval queries, and the post-seal annotation join are receipt-bound and resumable.",
        "- The experiment directly measures schema reliability, latency, abstention, coarse annotation corroboration, and deterministic retrieval behavior on one game.",
        "",
        "## Unsafe claims / no-go boundary",
        "",
        "- Do not claim full-match event detection performance, generalization, player identification, detailed report factuality, tactical understanding, or coach utility.",
        "- Do not claim that all identity-bearing pixels were removed; the direct audit found a lower-third team-name overlay outside the fixed mask.",
        "- Do not call SoccerNet annotation matching an event detector; it is an evaluator applied after visual outputs were sealed.",
        "- Do not expose or redistribute SoccerNet video, frames, labels, raw responses, or private source paths.",
        "",
        "## Next experiment",
        "",
        "Freeze a multi-game dense test set, add independent atomic human annotations for actor/action/outcome/tactics, compare sparse frames against true video-token models, report SoccerNet action-spotting mAP where applicable, and measure retrieval precision with coach-authored queries and blinded relevance judgments.",
        "",
        "## Reproducibility anchors",
        "",
        f"- Protocol receipt SHA-256: `{sha256_file(artifact_root / 'protocol-receipt.json')}`",
        f"- Frozen test config SHA-256: `{sha256_file(artifact_root / 'frozen-test-config.json')}`",
        f"- Visual prediction seal root: `{read_json(artifact_root / 'prediction-seal.json')['root_hash']}`",
        f"- Annotation evaluation SHA-256: `{sha256_file(artifact_root / 'annotation-evaluation.json')}`",
    ]
    report_path = report_path if report_path.is_absolute() else project_root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, report_path)
    return report_path


def package_receipt(artifact_root: Path, report_path: Path) -> dict[str, Any]:
    names = (
        "source-verification-receipt.json", "protocol-receipt.json", "prompt-candidates.json",
        "frozen-query-set.json", "response-schema-receipt.json", "model-identity.json",
        "prompt-selection.json", "frozen-test-config.json", "report-metrics.json",
        "search-index-receipt.json", "frozen-query-results.json", "test-run-receipt.json",
        "prediction-seal.json", "annotation-evaluation.json", "annotation-evaluation-receipt.json",
        "spot-check-adjudication.json", "verification-receipt.json",
    )
    files = []
    for name in names:
        path = artifact_root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing package artifact: {name}")
        files.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    files.append({"name": str(report_path), "bytes": report_path.stat().st_size, "sha256": sha256_file(report_path)})
    value = {
        "schema_version": "soccermaster-longform-package-receipt-v1",
        "generated_at": utc_now(),
        "status": "implementation_verified_independent_review_pending",
        "artifacts": files,
        "private_raw_location": "data/private/soccermaster-longform-v1",
        "raw_media_redistribution_allowed": False,
        "performance_claim_allowed": False,
    }
    write_json(artifact_root / "package-receipt.json", value)
    return value


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    value.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    subparsers = value.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify-source")
    subparsers.add_parser("prepare")
    select = subparsers.add_parser("select-prompt")
    select.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    select.add_argument("--model", default=DEFAULT_MODEL)
    select.add_argument("--timeout-seconds", type=int, default=300)
    test = subparsers.add_parser("run-test")
    test.add_argument("--timeout-seconds", type=int, default=300)
    subparsers.add_parser("seal")
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--tolerance-seconds", type=float, default=6.0)
    subparsers.add_parser("prepare-spotcheck")
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    subparsers.add_parser("verify")
    report = subparsers.add_parser("report")
    report.add_argument("--report-path", type=Path, default=Path("research/soccermaster-longform-technical-report-2026-08-27.md"))
    package = subparsers.add_parser("package")
    package.add_argument("--report-path", type=Path, default=Path("research/soccermaster-longform-technical-report-2026-08-27.md"))
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    private_root, artifact_root = _artifact_paths(project_root, args.private_root, args.artifacts)
    if args.command == "verify-source":
        result: Any = verify_source(project_root, private_root, artifact_root)
    elif args.command == "prepare":
        result = prepare(project_root, private_root, artifact_root)
    elif args.command == "select-prompt":
        result = run_prompt_selection(
            private_root=private_root, artifact_root=artifact_root, endpoint=args.endpoint,
            model=args.model, timeout_seconds=args.timeout_seconds,
        )
    elif args.command == "run-test":
        result = run_test(private_root=private_root, artifact_root=artifact_root, timeout_seconds=args.timeout_seconds)
    elif args.command == "seal":
        result = seal_predictions(private_root, artifact_root)
    elif args.command == "evaluate":
        result = evaluate_annotations(private_root, artifact_root, args.tolerance_seconds)
    elif args.command == "prepare-spotcheck":
        result = prepare_spotcheck_packet(private_root, artifact_root)
    elif args.command == "search":
        result = bm25_search(read_jsonl(private_root / "experiment/soccer-search-index.jsonl"), args.query, args.limit)
    elif args.command == "verify":
        result = verify_experiment(project_root, private_root, artifact_root)
    elif args.command == "report":
        result = {"report": str(write_technical_report(project_root, private_root, artifact_root, args.report_path))}
    elif args.command == "package":
        report_path = args.report_path if args.report_path.is_absolute() else project_root / args.report_path
        result = package_receipt(artifact_root, report_path)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
