"""Build a private searchable coaching-event index from authorized match video.

The software in this module performs only deterministic video windowing, uniform
frame sampling, contract validation, provenance recording, and lexical search.
It contains no soccer-event detector or hand-coded rule for deciding that a foul,
offside, long ball, or any other play occurred.  Every soccer-semantic field is
produced by the configured loopback VLM from visual frames alone.

The index is resumable: a whole match half can be planned once, interrupted, and
continued without rerunning completed windows.  Raw frames, model responses, and
the SQLite database must remain under ``data/private`` because SoccerNet footage
is not redistributable by this project.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from openai_compatible_adapter import LocalOpenAICompatibleAdapter
from real_clip_vlm import parse_json_content, sha256_file, write_contact_sheets, write_json


REPORT_SCHEMA_VERSION = "playground-coaching-window-report-v1"
INDEX_SCHEMA_VERSION = "playground-searchable-match-index-v1"
SAMPLER_VERSION = "fixed-overlap-uniform-visual-frames-v1"
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"

# This ontology constrains vocabulary for later retrieval; it does not determine
# which label applies.  That decision is made only by the VLM from supplied frames.
EVENT_TYPES = (
    "offside", "foul", "long_ball", "short_pass", "through_ball", "cross",
    "corner_kick", "free_kick", "penalty_kick", "throw_in", "goal_kick",
    "kick_off", "shot_on_target", "shot_off_target", "goal", "save", "tackle",
    "interception", "clearance", "header", "dribble", "ball_recovery", "turnover",
    "press", "duel", "set_piece", "card", "substitution", "other",
)
PHASES = (
    "build_up", "progression", "chance_creation", "transition_to_attack",
    "transition_to_defense", "sustained_attack", "defending", "set_piece",
    "stoppage", "unknown",
)
FIELD_AREAS = (
    "defensive_third", "middle_third", "attacking_third", "left_flank",
    "right_flank", "central_channel", "penalty_area", "goal_area", "corner",
    "unknown",
)
TEAM_REFERENCES = ("attacking_team", "defending_team", "home_team", "away_team", "unknown")
PARTICIPANT_ROLES = ("actor", "receiver", "teammate", "opponent", "referee", "other")
IDENTITY_BASES = ("role_only", "appearance_only", "jersey_number_visible", "none")


@dataclass(frozen=True)
class VideoMetadata:
    path: str
    sha256: str
    frame_count: int
    fps: float
    duration_s: float
    width: int
    height: int


@dataclass(frozen=True)
class Window:
    window_id: str
    ordinal: int
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 3)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _exact_keys(value: dict[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{field} keys must exactly equal {sorted(expected)}")


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _unique_text_list(value: Any, field: str, *, allowed: Sequence[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    normalized = [_nonempty_text(item, f"{field} item") for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    if allowed is not None and any(item not in allowed for item in normalized):
        raise ValueError(f"{field} contains a value outside the frozen ontology")
    return normalized


def video_metadata(video_path: Path) -> VideoMetadata:
    if not video_path.is_file():
        raise FileNotFoundError(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()
    if frame_count < 1 or not math.isfinite(fps) or fps <= 0 or width < 1 or height < 1:
        raise RuntimeError("Video metadata is invalid")
    return VideoMetadata(
        path=str(video_path.resolve()), sha256=sha256_file(video_path), frame_count=frame_count,
        fps=fps, duration_s=frame_count / fps, width=width, height=height,
    )


def _safe_identifier(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    if not result:
        raise ValueError("match_id must contain an alphanumeric character")
    return result


def plan_windows(
    *, match_id: str, duration_s: float, window_s: float = 30.0, stride_s: float = 25.0,
    start_s: float = 0.0, end_s: float | None = None,
) -> list[Window]:
    """Plan fixed overlapping windows and guarantee coverage through the tail."""
    duration_s = _finite_number(duration_s, "duration_s")
    window_s = _finite_number(window_s, "window_s")
    stride_s = _finite_number(stride_s, "stride_s")
    start_s = _finite_number(start_s, "start_s")
    end_s = duration_s if end_s is None else _finite_number(end_s, "end_s")
    if duration_s <= 0 or window_s <= 0 or stride_s <= 0:
        raise ValueError("duration, window, and stride must be positive")
    if stride_s > window_s:
        raise ValueError("stride_s must be no greater than window_s so coverage has no gaps")
    if start_s < 0 or end_s > duration_s + 1e-6 or end_s <= start_s:
        raise ValueError("requested time range is outside the video")

    safe_match = _safe_identifier(match_id)
    span = end_s - start_s
    starts: list[float]
    if span <= window_s:
        starts = [start_s]
    else:
        starts = []
        cursor = start_s
        while cursor + window_s < end_s - 1e-9:
            starts.append(cursor)
            cursor += stride_s
        tail_start = max(start_s, end_s - window_s)
        if not starts or tail_start > starts[-1] + 1e-6:
            starts.append(tail_start)

    result: list[Window] = []
    seen: set[tuple[int, int]] = set()
    for start in starts:
        actual_end = min(end_s, start + window_s)
        start_ms = int(round(start * 1000))
        end_ms = int(round(actual_end * 1000))
        key = (start_ms, end_ms)
        if key in seen:
            continue
        seen.add(key)
        result.append(Window(
            window_id=f"{safe_match}-w{start_ms:09d}-{end_ms:09d}",
            ordinal=len(result), start_s=start_ms / 1000.0, end_s=end_ms / 1000.0,
        ))
    return result


def sample_window(video_path: Path, window: Window, *, count: int) -> list[dict[str, Any]]:
    """Uniformly decode frames; this function makes no soccer-semantic decision."""
    if count < 2:
        raise ValueError("sample count must be at least two")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not math.isfinite(fps) or fps <= 0 or frame_count < 1:
        cap.release()
        raise RuntimeError("Video metadata is invalid")
    first = max(0, int(math.ceil(window.start_s * fps)))
    last = min(frame_count - 1, int(math.floor(window.end_s * fps - 1)))
    if last <= first:
        cap.release()
        raise RuntimeError("Window does not contain enough decodable frames")
    indices = np.linspace(first, last, num=min(count, last - first + 1), dtype=int).tolist()
    indices = list(dict.fromkeys(int(index) for index in indices))
    frames: list[dict[str, Any]] = []
    try:
        for ordinal, index in enumerate(indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Could not decode frame {index}")
            frames.append({
                "ordinal": ordinal, "frame_index": index,
                "timestamp_s": round(index / fps, 3),
                "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                "frame": frame,
            })
    finally:
        cap.release()
    return frames


def image_data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def coaching_prompt(window: Window, sample_timestamps: Iterable[float]) -> str:
    timestamps = ", ".join(f"{value:.3f}" for value in sample_timestamps)
    labels = ", ".join(EVENT_TYPES)
    phases = ", ".join(PHASES)
    areas = ", ".join(FIELD_AREAS)
    return (
        "You are a soccer video analyst creating a visual-only coaching search record. "
        f"The chronological frames cover match time {window.start_s:.3f}s to {window.end_s:.3f}s; "
        f"sampled frame timestamps are exactly: {timestamps}. "
        "Report every distinct, visually supported soccer event in this window, up to four events, rather than choosing "
        "one label. An event can be a restart, pass pattern, defensive action, duel, transition, shot, or stoppage. "
        f"event_types may use only: {labels}. phase_of_play may use only: {phases}. "
        f"field_areas may use only: {areas}. "
        "For each event, write a concrete primary_action, detailed_description, outcome, and why a coach may retrieve it. "
        "Include useful coaching tags and plain retrieval keywords such as long ball, offside, foul, switch of play, player "
        "number, team role, or tactical phase only when the frames support them. Do not infer events from clock timing, "
        "team reputation, source filename, assumed soccer rules, or an event list: infer only from the supplied pixels. "
        "Temporal evidence must use exactly two listed sample timestamps, start before end, and evidence_frames must cite "
        "listed timestamps with a short account of what is visible. "
        "Never guess a player's real-world name. Identify a player only as a visible role/appearance description or a "
        "clearly readable jersey number. Set visible_jersey_number to null unless the digits are readable; identity_basis "
        "must describe that limitation. role_in_event is relational: a passer, shooter, tackler, saver, or clearer is an "
        "actor; a target is a receiver; describe playing position such as goalkeeper only in player_reference. Camera "
        "cuts can break continuity, so state uncertainty. Offside and many fouls "
        "often require evidence not visible in broadcast samples: abstain from that event claim unless visually supported. "
        "If no soccer event is adequately visible, return an empty events list, report_abstained true, and explain why. "
        "Otherwise report_abstained must be false and abstention_reason must be null. Return only strict JSON matching the schema."
    )


def structured_response_format(sample_timestamps: Iterable[float]) -> dict[str, Any]:
    timestamps = [round(float(value), 3) for value in sample_timestamps]
    participant_properties = {
            "player_reference": {"type": "string", "minLength": 1},
            "team_reference": {"type": "string", "enum": list(TEAM_REFERENCES)},
            "role_in_event": {"type": "string", "enum": list(PARTICIPANT_ROLES)},
            "action": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    }
    participant_required = [
        "player_reference", "visible_jersey_number", "team_reference", "role_in_event",
        "action", "identity_basis", "confidence",
    ]
    participant = {
        "oneOf": [
            {
                "type": "object", "additionalProperties": False, "required": participant_required,
                "properties": participant_properties | {
                    "visible_jersey_number": {"type": "string", "pattern": "^[0-9]{1,3}$"},
                    "identity_basis": {"const": "jersey_number_visible"},
                },
            },
            {
                "type": "object", "additionalProperties": False, "required": participant_required,
                "properties": participant_properties | {
                    "visible_jersey_number": {"const": None},
                    "identity_basis": {"type": "string", "enum": ["role_only", "appearance_only", "none"]},
                },
            },
        ],
    }
    evidence = {
        "type": "object", "additionalProperties": False,
        "required": ["timestamp_s", "observation"],
        "properties": {
            "timestamp_s": {"type": "number", "enum": timestamps},
            "observation": {"type": "string", "minLength": 1},
        },
    }
    event = {
        "type": "object", "additionalProperties": False,
        "required": [
            "event_types", "primary_action", "temporal_evidence_s", "evidence_frames",
            "participants", "phase_of_play", "field_areas", "outcome", "detailed_description",
            "coaching_relevance", "coaching_tags", "retrieval_keywords", "uncertainty", "confidence",
        ],
        "properties": {
            "event_types": {"type": "array", "items": {"type": "string", "enum": list(EVENT_TYPES)}, "minItems": 1, "uniqueItems": True},
            "primary_action": {"type": "string", "minLength": 1},
            "temporal_evidence_s": {
                "type": "array", "prefixItems": [
                    {"type": "number", "enum": timestamps}, {"type": "number", "enum": timestamps},
                ], "minItems": 2, "maxItems": 2,
            },
            "evidence_frames": {"type": "array", "items": evidence, "minItems": 1, "uniqueItems": True},
            "participants": {"type": "array", "items": participant, "maxItems": 8},
            "phase_of_play": {"type": "string", "enum": list(PHASES)},
            "field_areas": {"type": "array", "items": {"type": "string", "enum": list(FIELD_AREAS)}, "minItems": 1, "uniqueItems": True},
            "outcome": {"type": "string", "minLength": 1},
            "detailed_description": {"type": "string", "minLength": 1},
            "coaching_relevance": {"type": "string", "minLength": 1},
            "coaching_tags": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "uniqueItems": True},
            "retrieval_keywords": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "uniqueItems": True},
            "uncertainty": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "soccer_coaching_window_report", "strict": True,
            "schema": {
                "type": "object", "additionalProperties": False,
                "required": ["window_summary", "events", "report_abstained", "abstention_reason", "overall_uncertainty"],
                "properties": {
                    "window_summary": {"type": "string", "minLength": 1},
                    "events": {"type": "array", "items": event, "minItems": 0, "maxItems": 4},
                    "report_abstained": {"type": "boolean"},
                    "abstention_reason": {"type": ["string", "null"]},
                    "overall_uncertainty": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def validate_model_report(
    raw: dict[str, Any], *, window: Window, sample_timestamps: Iterable[float], match_id: str,
) -> dict[str, Any]:
    """Fail closed on malformed, ungrounded, or identity-overclaiming output."""
    _exact_keys(raw, {"window_summary", "events", "report_abstained", "abstention_reason", "overall_uncertainty"}, "report")
    summary = _nonempty_text(raw["window_summary"], "window_summary")
    uncertainty = _nonempty_text(raw["overall_uncertainty"], "overall_uncertainty")
    events = raw["events"]
    if not isinstance(events, list) or len(events) > 4:
        raise ValueError("events must be a list with at most four items")
    abstained = raw["report_abstained"]
    if not isinstance(abstained, bool):
        raise ValueError("report_abstained must be boolean")
    reason = raw["abstention_reason"]
    if not events:
        if abstained is not True or not isinstance(reason, str) or not reason.strip():
            raise ValueError("an empty report must use explicit abstention semantics")
    elif abstained is not False or reason is not None:
        raise ValueError("a report containing events must not be marked abstained")

    allowed_timestamps = {round(float(value), 3) for value in sample_timestamps}
    event_keys = {
        "event_types", "primary_action", "temporal_evidence_s", "evidence_frames", "participants",
        "phase_of_play", "field_areas", "outcome", "detailed_description", "coaching_relevance",
        "coaching_tags", "retrieval_keywords", "uncertainty", "confidence",
    }
    participant_keys = {
        "player_reference", "visible_jersey_number", "team_reference", "role_in_event", "action",
        "identity_basis", "confidence",
    }
    normalized_events: list[dict[str, Any]] = []
    for ordinal, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise ValueError(f"event {ordinal} must be an object")
        _exact_keys(event, event_keys, f"event {ordinal}")
        event_types = _unique_text_list(event["event_types"], f"event {ordinal}.event_types", allowed=EVENT_TYPES)
        interval = event["temporal_evidence_s"]
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError(f"event {ordinal}.temporal_evidence_s must contain two timestamps")
        start = round(_finite_number(interval[0], "temporal start"), 3)
        end = round(_finite_number(interval[1], "temporal end"), 3)
        if start not in allowed_timestamps or end not in allowed_timestamps or start >= end:
            raise ValueError(f"event {ordinal} temporal evidence must be an increasing sampled-frame pair")
        if start < window.start_s - 0.05 or end > window.end_s + 0.05:
            raise ValueError(f"event {ordinal} temporal evidence is outside the window")

        evidence_frames = event["evidence_frames"]
        if not isinstance(evidence_frames, list) or not evidence_frames:
            raise ValueError(f"event {ordinal}.evidence_frames must be non-empty")
        normalized_evidence: list[dict[str, Any]] = []
        seen_evidence: set[float] = set()
        for evidence in evidence_frames:
            if not isinstance(evidence, dict):
                raise ValueError("evidence frame must be an object")
            _exact_keys(evidence, {"timestamp_s", "observation"}, "evidence frame")
            timestamp = round(_finite_number(evidence["timestamp_s"], "evidence timestamp"), 3)
            if timestamp not in allowed_timestamps or not (start <= timestamp <= end):
                raise ValueError("evidence timestamp must be a sampled frame inside the event interval")
            if timestamp in seen_evidence:
                raise ValueError("evidence timestamps must be unique within an event")
            seen_evidence.add(timestamp)
            normalized_evidence.append({"timestamp_s": timestamp, "observation": _nonempty_text(evidence["observation"], "evidence observation")})

        participants = event["participants"]
        if not isinstance(participants, list) or len(participants) > 8:
            raise ValueError("participants must be a list with at most eight items")
        normalized_participants: list[dict[str, Any]] = []
        for participant in participants:
            if not isinstance(participant, dict):
                raise ValueError("participant must be an object")
            _exact_keys(participant, participant_keys, "participant")
            number = participant["visible_jersey_number"]
            if number is not None:
                number = _nonempty_text(number, "visible_jersey_number")
                if not re.fullmatch(r"\d{1,3}", number):
                    raise ValueError("visible_jersey_number must contain only one to three digits")
                if participant["identity_basis"] != "jersey_number_visible":
                    raise ValueError("a jersey number requires identity_basis=jersey_number_visible")
            elif participant["identity_basis"] == "jersey_number_visible":
                raise ValueError("jersey_number_visible basis requires a visible jersey number")
            if participant["team_reference"] not in TEAM_REFERENCES:
                raise ValueError("participant team_reference is outside the ontology")
            if participant["role_in_event"] not in PARTICIPANT_ROLES:
                raise ValueError("participant role_in_event is outside the ontology")
            if participant["identity_basis"] not in IDENTITY_BASES:
                raise ValueError("participant identity_basis is outside the ontology")
            p_conf = _finite_number(participant["confidence"], "participant confidence")
            if not 0 <= p_conf <= 1:
                raise ValueError("participant confidence must be between zero and one")
            normalized_participants.append({
                "player_reference": _nonempty_text(participant["player_reference"], "player_reference"),
                "visible_jersey_number": number,
                "team_reference": participant["team_reference"],
                "role_in_event": participant["role_in_event"],
                "action": _nonempty_text(participant["action"], "participant action"),
                "identity_basis": participant["identity_basis"], "confidence": p_conf,
            })

        phase = event["phase_of_play"]
        if phase not in PHASES:
            raise ValueError("phase_of_play is outside the ontology")
        confidence = _finite_number(event["confidence"], "event confidence")
        if not 0 <= confidence <= 1:
            raise ValueError("event confidence must be between zero and one")
        event_id = f"{window.window_id}:e{ordinal:02d}"
        normalized_events.append({
            "event_id": event_id, "event_types": event_types,
            "primary_action": _nonempty_text(event["primary_action"], "primary_action"),
            "temporal_evidence_s": [start, end], "evidence_frames": normalized_evidence,
            "participants": normalized_participants, "phase_of_play": phase,
            "field_areas": _unique_text_list(event["field_areas"], "field_areas", allowed=FIELD_AREAS),
            "outcome": _nonempty_text(event["outcome"], "outcome"),
            "detailed_description": _nonempty_text(event["detailed_description"], "detailed_description"),
            "coaching_relevance": _nonempty_text(event["coaching_relevance"], "coaching_relevance"),
            "coaching_tags": _unique_text_list(event["coaching_tags"], "coaching_tags"),
            "retrieval_keywords": _unique_text_list(event["retrieval_keywords"], "retrieval_keywords"),
            "uncertainty": _nonempty_text(event["uncertainty"], "event uncertainty"),
            "confidence": confidence,
        })

    return {
        "schema_version": REPORT_SCHEMA_VERSION, "match_id": match_id,
        "window_id": window.window_id, "window_start_s": window.start_s, "window_end_s": window.end_s,
        "window_summary": summary, "events": normalized_events, "report_abstained": abstained,
        "abstention_reason": None if reason is None else reason.strip(), "overall_uncertainty": uncertainty,
    }


def _request_vlm(
    *, endpoint: str, model: str, prompt_text: str, sheet_paths: Sequence[Path],
    response_format: dict[str, Any], max_tokens: int, timeout_s: int,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    adapter = LocalOpenAICompatibleAdapter(endpoint, model)
    payload = adapter.build_request(prompt_text, [image_data_url(path) for path in sheet_paths])
    payload["messages"][0]["content"] = (
        "Analyze only the supplied chronological soccer frames. Do not use audio or outside knowledge. "
        "Return only the strict coaching-window JSON requested by the user."
    )
    payload["response_format"] = response_format
    payload["temperature"] = 0
    payload["max_tokens"] = max_tokens
    started = time.perf_counter()
    request = Request(
        endpoint.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local VLM request failed with HTTP {exc.code}: {body}") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return raw_response, payload, elapsed_ms


def require_private_output(path: Path) -> Path:
    resolved = path.resolve()
    lowered = [part.lower() for part in resolved.parts]
    if not any(lowered[index:index + 2] == ["data", "private"] for index in range(len(lowered) - 1)):
        raise ValueError("search index and raw VLM outputs must remain under data/private")
    return resolved


def initialize_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS windows (
            window_id TEXT PRIMARY KEY,
            ordinal INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            start_s REAL NOT NULL,
            end_s REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','running','complete','failed')),
            report_json TEXT,
            error_type TEXT,
            error_message TEXT,
            elapsed_ms INTEGER,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            window_id TEXT NOT NULL REFERENCES windows(window_id) ON DELETE CASCADE,
            event_types_json TEXT NOT NULL,
            primary_action TEXT NOT NULL,
            start_s REAL NOT NULL,
            end_s REAL NOT NULL,
            confidence REAL NOT NULL,
            report_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS event_search USING fts5(
            event_id UNINDEXED,
            searchable_text,
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )
    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (INDEX_SCHEMA_VERSION,))
    connection.commit()
    return connection


def _searchable_text(event: dict[str, Any], report: dict[str, Any]) -> str:
    participant_text = " ".join(
        " ".join(filter(None, [
            participant["player_reference"], participant["visible_jersey_number"],
            participant["team_reference"], participant["role_in_event"], participant["action"],
        ]))
        for participant in event["participants"]
    )
    return " ".join([
        " ".join(event["event_types"]), event["primary_action"], event["phase_of_play"],
        " ".join(event["field_areas"]), event["outcome"], event["detailed_description"],
        event["coaching_relevance"], " ".join(event["coaching_tags"]),
        " ".join(event["retrieval_keywords"]), event["uncertainty"], participant_text,
        report["window_summary"],
    ])


def store_report(connection: sqlite3.Connection, report: dict[str, Any], *, elapsed_ms: int) -> None:
    report_json = json.dumps(report, ensure_ascii=False, sort_keys=True)
    window_id = report["window_id"]
    with connection:
        old_ids = [row[0] for row in connection.execute("SELECT event_id FROM events WHERE window_id=?", (window_id,))]
        for event_id in old_ids:
            connection.execute("DELETE FROM event_search WHERE event_id=?", (event_id,))
        connection.execute("DELETE FROM events WHERE window_id=?", (window_id,))
        connection.execute(
            "UPDATE windows SET status='complete', report_json=?, error_type=NULL, error_message=NULL, elapsed_ms=?, updated_at=? WHERE window_id=?",
            (report_json, elapsed_ms, utc_now(), window_id),
        )
        for event in report["events"]:
            event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
            connection.execute(
                "INSERT INTO events(event_id,window_id,event_types_json,primary_action,start_s,end_s,confidence,report_json) VALUES(?,?,?,?,?,?,?,?)",
                (
                    event["event_id"], window_id, json.dumps(event["event_types"]), event["primary_action"],
                    event["temporal_evidence_s"][0], event["temporal_evidence_s"][1], event["confidence"], event_json,
                ),
            )
            connection.execute(
                "INSERT INTO event_search(event_id,searchable_text) VALUES(?,?)",
                (event["event_id"], _searchable_text(event, report)),
            )


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query.casefold(), flags=re.UNICODE)
    if not tokens:
        raise ValueError("query must contain a word or number")
    # Exact-token matching is intentional: a request for ``goal`` must not match
    # ``goalkeeper`` merely because the words share a prefix.  Query expansion or
    # semantic retrieval belongs in a separately evaluated retrieval condition.
    return " AND ".join(f'"{token}"' for token in tokens[:20])


def search_index(
    database: Path, query: str, *, limit: int = 10, min_confidence: float = 0.0,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    if not 0 <= min_confidence <= 1:
        raise ValueError("min_confidence must be between zero and one")
    if event_type is not None and event_type not in EVENT_TYPES:
        raise ValueError("event_type is outside the ontology")
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        sql = (
            "SELECT e.event_id,e.window_id,e.event_types_json,e.primary_action,e.start_s,e.end_s,e.confidence,e.report_json,"
            "bm25(event_search) AS rank FROM event_search JOIN events e ON e.event_id=event_search.event_id "
            "WHERE event_search MATCH ? AND e.confidence>=?"
        )
        params: list[Any] = [_fts_query(query), min_confidence]
        if event_type is not None:
            sql += " AND EXISTS (SELECT 1 FROM json_each(e.event_types_json) WHERE value=?)"
            params.append(event_type)
        sql += " ORDER BY rank ASC,e.start_s ASC LIMIT ?"
        params.append(limit)
        rows = connection.execute(sql, params).fetchall()
        return [{
            "event_id": row["event_id"], "window_id": row["window_id"],
            "event_types": json.loads(row["event_types_json"]), "primary_action": row["primary_action"],
            "start_s": row["start_s"], "end_s": row["end_s"], "confidence": row["confidence"],
            "rank": row["rank"], "report": json.loads(row["report_json"]),
        } for row in rows]
    finally:
        connection.close()


def _match_clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:06.3f}"


def compact_search_results(query: str, results: Sequence[dict[str, Any]]) -> str:
    """Render a meeting-friendly view while retaining the machine JSON path."""
    lines = [f'Search: "{query}"', f"Matches: {len(results)}"]
    for index, result in enumerate(results, start=1):
        report = result["report"]
        participants = "; ".join(
            f"{item['player_reference']}: {item['action']}"
            + (f" (jersey {item['visible_jersey_number']})" if item["visible_jersey_number"] else "")
            for item in report["participants"]
        ) or "identity/participants not visually supportable"
        evidence = "; ".join(
            f"{_match_clock(item['timestamp_s'])} {item['observation']}"
            for item in report["evidence_frames"]
        )
        lines.extend([
            "",
            f"[{index}] {_match_clock(result['start_s'])}-{_match_clock(result['end_s'])} | confidence {result['confidence']:.2f}",
            f"Types: {', '.join(result['event_types'])}",
            f"Action: {result['primary_action']}",
            f"Detail: {report['detailed_description']}",
            f"Players: {participants}",
            f"Coach use: {report['coaching_relevance']}",
            f"Evidence: {evidence}",
            f"Uncertainty: {report['uncertainty']}",
        ])
    if not results:
        lines.extend(["", "No indexed VLM report contained every search term."])
    return "\n".join(lines)


def index_match(
    *, video_path: Path, match_id: str, out_dir: Path, source_reference: str,
    source_manifest: Path | None = None, endpoint: str = DEFAULT_ENDPOINT, model: str = DEFAULT_MODEL,
    window_s: float = 30.0, stride_s: float = 25.0, start_s: float = 0.0,
    end_s: float | None = None, sample_count: int = 16, sheets: int = 4,
    max_tokens: int = 5000, timeout_s: int = 300, max_windows: int | None = None,
) -> dict[str, Any]:
    out_dir = require_private_output(out_dir)
    # Fail before decoding or packaging private frames if a non-loopback endpoint
    # was supplied.  _request_vlm repeats the same boundary check before sending.
    LocalOpenAICompatibleAdapter(endpoint, model)
    if source_manifest is not None and not source_manifest.is_file():
        raise FileNotFoundError(source_manifest)
    metadata = video_metadata(video_path)
    windows = plan_windows(
        match_id=match_id, duration_s=metadata.duration_s, window_s=window_s,
        stride_s=stride_s, start_s=start_s, end_s=end_s,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    database = out_dir / "search-index.sqlite3"
    connection = initialize_database(database)
    source_manifest_sha = None if source_manifest is None else sha256_file(source_manifest)
    configuration = {
        "schema_version": INDEX_SCHEMA_VERSION, "match_id": match_id,
        "source_reference": source_reference, "source_manifest_sha256": source_manifest_sha,
        "video": asdict(metadata), "window_s": window_s, "stride_s": stride_s,
        "requested_start_s": start_s, "requested_end_s": metadata.duration_s if end_s is None else end_s,
        "sample_count": sample_count, "sheets": sheets, "sampler_version": SAMPLER_VERSION,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "prompt_contract_version": "visual-coaching-search-v1",
        "endpoint": endpoint, "model": model, "max_tokens": max_tokens,
        "semantic_inference_boundary": "All soccer-event fields come from the VLM; code only windows, samples, validates, stores, and searches.",
        "audio_supplied_to_vlm": False,
    }
    config_json = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    existing_config = connection.execute("SELECT value FROM metadata WHERE key='configuration_sha256'").fetchone()
    config_sha = hashlib.sha256(config_json.encode("utf-8")).hexdigest()
    if existing_config is not None and existing_config[0] != config_sha:
        connection.close()
        raise ValueError("resume configuration drift: use a new private output directory")
    with connection:
        connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('configuration_sha256',?)", (config_sha,))
        connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('configuration_json',?)", (config_json,))
        for window in windows:
            connection.execute(
                "INSERT OR IGNORE INTO windows(window_id,ordinal,match_id,start_s,end_s,status,updated_at) VALUES(?,?,?,?,?,'pending',?)",
                (window.window_id, window.ordinal, match_id, window.start_s, window.end_s, utc_now()),
            )
    write_json(out_dir / "index-plan.json", {
        "configuration": configuration, "configuration_sha256": config_sha,
        "windows": [asdict(window) | {"duration_s": window.duration_s} for window in windows],
    })

    selected: list[Window] = []
    for window in windows:
        row = connection.execute("SELECT status FROM windows WHERE window_id=?", (window.window_id,)).fetchone()
        if row is not None and row["status"] == "complete":
            continue
        selected.append(window)
        if max_windows is not None and len(selected) >= max_windows:
            break

    completed: list[str] = []
    failures: list[dict[str, str]] = []
    model_reported: set[str] = set()
    for window in selected:
        window_dir = out_dir / "windows" / window.window_id
        window_dir.mkdir(parents=True, exist_ok=True)
        with connection:
            connection.execute(
                "UPDATE windows SET status='running',error_type=NULL,error_message=NULL,updated_at=? WHERE window_id=?",
                (utc_now(), window.window_id),
            )
        try:
            frames = sample_window(video_path, window, count=sample_count)
            sheet_paths = write_contact_sheets(frames, out_dir=window_dir, sheets=sheets)
            timestamps = [item["timestamp_s"] for item in frames]
            prompt_text = coaching_prompt(window, timestamps)
            response_format = structured_response_format(timestamps)
            write_json(window_dir / "input-manifest.json", {
                "schema_version": "playground-coaching-window-input-v1", "match_id": match_id,
                "window": asdict(window) | {"duration_s": window.duration_s},
                "source_reference": source_reference, "video_sha256": metadata.sha256,
                "source_manifest_sha256": source_manifest_sha,
                "frames": [{key: value for key, value in item.items() if key != "frame"} for item in frames],
                "contact_sheets": [{"path": str(path), "sha256": sha256_file(path)} for path in sheet_paths],
                "audio_supplied_to_vlm": False,
            })
            write_json(window_dir / "request-manifest.json", {
                "endpoint": endpoint.rstrip("/") + "/chat/completions", "model": model,
                "prompt": prompt_text, "response_format": response_format, "temperature": 0,
                "max_tokens": max_tokens,
                "image_inputs": [{"path": str(path), "sha256": sha256_file(path)} for path in sheet_paths],
            })
            raw_response, _payload, elapsed_ms = _request_vlm(
                endpoint=endpoint, model=model, prompt_text=prompt_text, sheet_paths=sheet_paths,
                response_format=response_format, max_tokens=max_tokens, timeout_s=timeout_s,
            )
            write_json(window_dir / "raw-response.json", raw_response)
            reported = raw_response.get("model")
            if isinstance(reported, str):
                model_reported.add(reported)
            content = raw_response.get("choices", [{}])[0].get("message", {}).get("content")
            parsed = parse_json_content(content)
            report = validate_model_report(parsed, window=window, sample_timestamps=timestamps, match_id=match_id)
            write_json(window_dir / "report.json", report)
            write_json(window_dir / "receipt.json", {
                "schema_version": "playground-coaching-window-receipt-v1", "recorded_at": utc_now(),
                "window_id": window.window_id, "video_sha256": metadata.sha256,
                "model_requested": model, "model_reported": reported, "endpoint": endpoint,
                "elapsed_ms": elapsed_ms, "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
                "response_format_sha256": hashlib.sha256(json.dumps(response_format, sort_keys=True).encode("utf-8")).hexdigest(),
                "input_manifest_sha256": sha256_file(window_dir / "input-manifest.json"),
                "report_sha256": sha256_file(window_dir / "report.json"),
                "audio_supplied_to_vlm": False, "performance_claim_allowed": False,
            })
            store_report(connection, report, elapsed_ms=elapsed_ms)
            completed.append(window.window_id)
        except Exception as exc:  # Persist the window failure and continue the match.
            failure = {"window_id": window.window_id, "error_type": type(exc).__name__, "error_message": str(exc)}
            failures.append(failure)
            write_json(window_dir / "failure.json", failure | {"recorded_at": utc_now()})
            with connection:
                connection.execute(
                    "UPDATE windows SET status='failed',error_type=?,error_message=?,updated_at=? WHERE window_id=?",
                    (type(exc).__name__, str(exc), utc_now(), window.window_id),
                )

    counts = dict(connection.execute("SELECT status,COUNT(*) FROM windows GROUP BY status").fetchall())
    event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    connection.close()
    receipt = {
        "schema_version": "playground-searchable-match-run-receipt-v1", "recorded_at": utc_now(),
        "configuration_sha256": config_sha, "database": str(database), "database_sha256": sha256_file(database),
        "planned_windows": len(windows), "selected_this_run": len(selected), "completed_this_run": completed,
        "failures_this_run": failures, "status_counts": counts, "indexed_event_count": event_count,
        "model_requested": model, "models_reported": sorted(model_reported),
        "audio_supplied_to_vlm": False, "performance_claim_allowed": False,
        "interpretation": "A resumable systems run over private real footage; model reports require human adjudication before accuracy or coaching-validity claims.",
    }
    write_json(out_dir / "run-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Print deterministic windows without running a VLM")
    plan.add_argument("--video", type=Path, required=True)
    plan.add_argument("--match-id", required=True)
    plan.add_argument("--window-s", type=float, default=30.0)
    plan.add_argument("--stride-s", type=float, default=25.0)
    plan.add_argument("--start-s", type=float, default=0.0)
    plan.add_argument("--end-s", type=float)

    index = subparsers.add_parser("index", help="Analyze pending windows and update the private index")
    index.add_argument("--video", type=Path, required=True)
    index.add_argument("--match-id", required=True)
    index.add_argument("--out", type=Path, required=True)
    index.add_argument("--source-reference", required=True)
    index.add_argument("--source-manifest", type=Path)
    index.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    index.add_argument("--model", default=DEFAULT_MODEL)
    index.add_argument("--window-s", type=float, default=30.0)
    index.add_argument("--stride-s", type=float, default=25.0)
    index.add_argument("--start-s", type=float, default=0.0)
    index.add_argument("--end-s", type=float)
    index.add_argument("--sample-count", type=int, default=16)
    index.add_argument("--sheets", type=int, default=4)
    index.add_argument("--max-tokens", type=int, default=5000)
    index.add_argument("--timeout-s", type=int, default=300)
    index.add_argument("--max-windows", type=int)

    search = subparsers.add_parser("search", help="Search indexed VLM coaching reports")
    search.add_argument("--database", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--min-confidence", type=float, default=0.0)
    search.add_argument("--event-type", choices=EVENT_TYPES)
    search.add_argument("--compact", action="store_true", help="Print a concise coach-facing result")

    args = parser.parse_args()
    if args.command == "plan":
        metadata = video_metadata(args.video)
        windows = plan_windows(
            match_id=args.match_id, duration_s=metadata.duration_s, window_s=args.window_s,
            stride_s=args.stride_s, start_s=args.start_s, end_s=args.end_s,
        )
        print(json.dumps({"video_duration_s": metadata.duration_s, "windows": [asdict(item) for item in windows]}, indent=2))
        return 0
    if args.command == "search":
        results = search_index(
            args.database, args.query, limit=args.limit, min_confidence=args.min_confidence,
            event_type=args.event_type,
        )
        if args.compact:
            print(compact_search_results(args.query, results))
        else:
            print(json.dumps({"query": args.query, "count": len(results), "results": results}, indent=2, ensure_ascii=False))
        return 0
    receipt = index_match(
        video_path=args.video, match_id=args.match_id, out_dir=args.out,
        source_reference=args.source_reference, source_manifest=args.source_manifest,
        endpoint=args.endpoint, model=args.model, window_s=args.window_s, stride_s=args.stride_s,
        start_s=args.start_s, end_s=args.end_s, sample_count=args.sample_count, sheets=args.sheets,
        max_tokens=args.max_tokens, timeout_s=args.timeout_s, max_windows=args.max_windows,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 2 if receipt["failures_this_run"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
