"""Offline-first, rights-gated benchmark runner for hosted soccer video VLMs.

The runner is provider-neutral.  Its built-in Gemini adapter is intentionally
unreachable unless every clip explicitly permits Google Gemini processing, a
runtime credential exists, and the caller opts into remote execution.  Dry-run
and fixture providers make the complete receipt/parser/resume path testable
without a network call, private-media upload, or spend.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = Path(__file__).with_name("coach-event-report.prompt.txt")
SCHEMA_PATH = Path(__file__).with_name("coach-event-report.schema.json")
INPUT_SCHEMA_VERSION = "playground-hosted-video-benchmark-input-v1"
RUN_SCHEMA_VERSION = "playground-hosted-video-benchmark-run-v1"
REPORT_SCHEMA_VERSION = "playground-coach-event-report-v1"
PRIMARY_SEAL_SCHEMA_VERSION = "playground-hosted-video-primary-seal-v1"
POSTHOC_SCHEMA_VERSION = "playground-hosted-video-posthoc-audit-v1"
VIDEO_CONDITION = "physically_silent_video_only"
CURRENT_GEMINI_MODEL = "gemini-3.7-flash"
GEMINI_PROCESSOR_ID = "google_gemini"
SECRET_NAMES = {"api_key", "apikey", "credential", "credentials", "password", "secret", "token"}
SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"),
)
CLIP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
EVENT_ID_PATTERN = re.compile(r"^e[0-9]{2,}$")
PHASES = {"build_up", "progression", "final_third", "transition", "restart", "stoppage", "mixed", "unclear"}
TEAM_SIDES = {"left_attacking", "right_attacking", "both_or_contested", "official", "unknown"}
PARTICIPANT_TEAM_SIDES = {"left_attacking", "right_attacking", "official", "unknown"}
IDENTITY_BASES = {"visible_name_graphic", "visible_jersey_number", "role_or_position", "appearance_only", "unknown"}
POSSESSION_TEAMS = {"left_attacking", "right_attacking", "none", "unknown"}
POSSESSION_STATES = {"controlled", "contested", "loose", "out_of_play", "unknown"}
REPLAY_STATES = {"live_main_camera", "replay", "closeup_or_graphic", "uncertain"}
TERMINAL_CLIP_STATES = {"complete", "parse_failed", "provider_failed"}
PRIMARY_ARTIFACT_NAMES = {
    "request-receipt.json", "result.json", "raw-response.json", "event-report.json",
    "parse-failure.json", "provider-failure.json", "attempts-manifest.json",
}


SCORING_CONTRACT = {
    "schema_version": "playground-hosted-video-scoring-contract-v1",
    "event_mapping": "exact_event_type",
    "time_unit": "seconds",
    "minimum_interval_iou": 0.5,
    "maximum_peak_error_s": 1.0,
    "matching": "maximum_cardinality_one_to_one",
    "scope": "descriptive_event_and_time_only",
}


class BenchmarkGateError(ValueError):
    """A fail-closed pre-upload gate did not pass."""


class ReportValidationError(ValueError):
    """A provider response did not satisfy the frozen event-report contract."""


def _strict_json(text: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


@dataclass(frozen=True)
class ClipSpec:
    clip_id: str
    video_path: Path
    sha256: str
    mime_type: str
    rights: dict[str, Any]
    held_out: dict[str, str | None]


@dataclass(frozen=True)
class MediaProbe:
    video_streams: int
    audio_streams: int
    duration_s: float
    probe_tool: str


@dataclass(frozen=True)
class ProviderResult:
    response_text: str
    raw_response: Any
    model_reported: str
    provider_metadata: dict[str, Any]


class VideoProvider(Protocol):
    provider_id: str
    remote: bool

    def infer(
        self,
        *,
        clip_id: str,
        video_path: Path,
        mime_type: str,
        prompt: str,
        response_schema: dict[str, Any],
        model: str,
        credential: str | None,
    ) -> ProviderResult:
        """Return an unparsed provider response."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_private_output(path: Path) -> Path:
    resolved = path.resolve()
    lowered = [part.lower() for part in resolved.parts]
    if not any(lowered[index:index + 2] == ["data", "private"] for index in range(len(lowered) - 1)):
        raise BenchmarkGateError("raw hosted-model outputs must remain under data/private")
    return resolved


def _secret_key_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SECRET_NAMES or normalized.endswith("_api_key"):
                paths.append(f"{prefix}.{key}")
            paths.extend(_secret_key_paths(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_secret_key_paths(child, f"{prefix}[{index}]"))
    return paths


def _redact_text(text: str, secrets: Sequence[str]) -> str:
    safe = text
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", safe)
    return safe


def redact_secrets(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SECRET_NAMES or normalized.endswith("_api_key"):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = redact_secrets(child, secrets)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_secrets(child, secrets) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), secrets)


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportValidationError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ReportValidationError(f"{label} keys differ; missing={missing}; extra={extra}")
    return value


def _text(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ReportValidationError(f"{label} must be non-empty text")
    return value.strip()


def _number(value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ReportValidationError(f"{label} must be a finite number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ReportValidationError(f"{label} is below {minimum}")
    if maximum is not None and number > maximum:
        raise ReportValidationError(f"{label} is above {maximum}")
    return number


def _choice(value: Any, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ReportValidationError(f"{label} is outside the frozen ontology")
    return str(value)


def _text_list(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum or (maximum is not None and len(value) > maximum):
        raise ReportValidationError(f"{label} has an invalid list length")
    return [_text(item, f"{label}[{index}]") or "" for index, item in enumerate(value)]


def _validate_participant(value: Any, label: str) -> dict[str, Any]:
    participant = _exact_keys(
        value,
        {"reference", "team_side", "role", "visible_jersey_number", "identity_basis", "action", "confidence"},
        label,
    )
    number = _text(participant["visible_jersey_number"], f"{label}.visible_jersey_number", nullable=True)
    basis = _choice(participant["identity_basis"], IDENTITY_BASES, f"{label}.identity_basis")
    if number is not None and not re.fullmatch(r"[0-9]{1,3}", number):
        raise ReportValidationError(f"{label}.visible_jersey_number must contain one to three digits")
    if number is not None and basis != "visible_jersey_number":
        raise ReportValidationError(f"{label} jersey evidence requires identity_basis=visible_jersey_number")
    if number is None and basis == "visible_jersey_number":
        raise ReportValidationError(f"{label} visible_jersey_number basis requires a number")
    return {
        "reference": _text(participant["reference"], f"{label}.reference"),
        "team_side": _choice(participant["team_side"], PARTICIPANT_TEAM_SIDES, f"{label}.team_side"),
        "role": _text(participant["role"], f"{label}.role"),
        "visible_jersey_number": number,
        "identity_basis": basis,
        "action": _text(participant["action"], f"{label}.action"),
        "confidence": _number(participant["confidence"], f"{label}.confidence", minimum=0, maximum=1),
    }


def validate_event_report(raw: Any, *, clip_id: str, duration_s: float) -> dict[str, Any]:
    """Fail closed on malformed, temporally invalid, or identity-inconsistent JSON."""
    report = _exact_keys(
        raw,
        {
            "schema_version", "clip_id", "video_condition", "window_summary", "dominant_phase",
            "events", "report_abstained", "abstention_reason", "overall_uncertainty", "coverage_limit",
        },
        "report",
    )
    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise ReportValidationError("report.schema_version is unsupported")
    if report["clip_id"] != clip_id:
        raise ReportValidationError("report.clip_id does not match the input clip")
    if report["video_condition"] != VIDEO_CONDITION:
        raise ReportValidationError("report.video_condition does not preserve the silent primary condition")
    events = report["events"]
    if not isinstance(events, list) or len(events) > 20:
        raise ReportValidationError("report.events must contain at most twenty event cards")
    if not isinstance(report["report_abstained"], bool):
        raise ReportValidationError("report.report_abstained must be boolean")
    report_reason = _text(report["abstention_reason"], "report.abstention_reason", nullable=True)
    if events and (report["report_abstained"] or report_reason is not None):
        raise ReportValidationError("a report with events cannot use report-level abstention")
    if not events and (not report["report_abstained"] or report_reason is None):
        raise ReportValidationError("an empty report requires an explicit abstention reason")

    event_keys = {
        "event_id", "event_type", "event_subtype", "start_s", "peak_s", "end_s", "phase_of_play",
        "restart_context", "team_side", "primary_actor", "secondary_participants", "ball_action",
        "possession", "origin_pitch_region", "destination_pitch_region", "movement_direction",
        "action_sequence", "tactical_intent", "outcome", "coach_relevance", "evidence",
        "replay_status", "alternatives", "uncertainties", "confidence", "abstain", "abstention_reason",
    }
    normalized_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, event_value in enumerate(events):
        label = f"report.events[{index}]"
        event = _exact_keys(event_value, event_keys, label)
        event_id = _text(event["event_id"], f"{label}.event_id") or ""
        if not EVENT_ID_PATTERN.fullmatch(event_id) or event_id in seen_ids:
            raise ReportValidationError(f"{label}.event_id must be unique and match eNN")
        seen_ids.add(event_id)
        start_s = _number(event["start_s"], f"{label}.start_s", minimum=0, maximum=duration_s)
        peak_s = _number(event["peak_s"], f"{label}.peak_s", minimum=0, maximum=duration_s)
        end_s = _number(event["end_s"], f"{label}.end_s", minimum=0, maximum=duration_s)
        if not start_s <= peak_s <= end_s or start_s == end_s:
            raise ReportValidationError(f"{label} must satisfy start_s <= peak_s <= end_s with nonzero duration")

        secondary = event["secondary_participants"]
        if not isinstance(secondary, list) or len(secondary) > 12:
            raise ReportValidationError(f"{label}.secondary_participants must contain at most twelve entries")
        possession = _exact_keys(event["possession"], {"team_side", "state", "confidence", "visibility_limit"}, f"{label}.possession")
        evidence = event["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ReportValidationError(f"{label}.evidence must be non-empty")
        normalized_evidence: list[dict[str, Any]] = []
        for evidence_index, evidence_value in enumerate(evidence):
            evidence_label = f"{label}.evidence[{evidence_index}]"
            item = _exact_keys(evidence_value, {"timestamp_s", "visible_support"}, evidence_label)
            timestamp_s = _number(item["timestamp_s"], f"{evidence_label}.timestamp_s", minimum=start_s, maximum=end_s)
            normalized_evidence.append({
                "timestamp_s": timestamp_s,
                "visible_support": _text(item["visible_support"], f"{evidence_label}.visible_support"),
            })
        if not isinstance(event["abstain"], bool):
            raise ReportValidationError(f"{label}.abstain must be boolean")
        event_reason = _text(event["abstention_reason"], f"{label}.abstention_reason", nullable=True)
        if event["abstain"] != (event_reason is not None):
            raise ReportValidationError(f"{label} abstention flag and reason disagree")

        normalized_events.append({
            "event_id": event_id,
            "event_type": _text(event["event_type"], f"{label}.event_type"),
            "event_subtype": _text(event["event_subtype"], f"{label}.event_subtype", nullable=True),
            "start_s": start_s,
            "peak_s": peak_s,
            "end_s": end_s,
            "phase_of_play": _choice(event["phase_of_play"], PHASES, f"{label}.phase_of_play"),
            "restart_context": _text(event["restart_context"], f"{label}.restart_context", nullable=True),
            "team_side": _choice(event["team_side"], TEAM_SIDES, f"{label}.team_side"),
            "primary_actor": _validate_participant(event["primary_actor"], f"{label}.primary_actor"),
            "secondary_participants": [
                _validate_participant(item, f"{label}.secondary_participants[{participant_index}]")
                for participant_index, item in enumerate(secondary)
            ],
            "ball_action": _text(event["ball_action"], f"{label}.ball_action"),
            "possession": {
                "team_side": _choice(possession["team_side"], POSSESSION_TEAMS, f"{label}.possession.team_side"),
                "state": _choice(possession["state"], POSSESSION_STATES, f"{label}.possession.state"),
                "confidence": _number(possession["confidence"], f"{label}.possession.confidence", minimum=0, maximum=1),
                "visibility_limit": _text(possession["visibility_limit"], f"{label}.possession.visibility_limit"),
            },
            "origin_pitch_region": _text(event["origin_pitch_region"], f"{label}.origin_pitch_region", nullable=True),
            "destination_pitch_region": _text(event["destination_pitch_region"], f"{label}.destination_pitch_region", nullable=True),
            "movement_direction": _text(event["movement_direction"], f"{label}.movement_direction", nullable=True),
            "action_sequence": _text_list(event["action_sequence"], f"{label}.action_sequence", minimum=1),
            "tactical_intent": _text(event["tactical_intent"], f"{label}.tactical_intent"),
            "outcome": _text(event["outcome"], f"{label}.outcome"),
            "coach_relevance": _text(event["coach_relevance"], f"{label}.coach_relevance"),
            "evidence": normalized_evidence,
            "replay_status": _choice(event["replay_status"], REPLAY_STATES, f"{label}.replay_status"),
            "alternatives": _text_list(event["alternatives"], f"{label}.alternatives"),
            "uncertainties": _text_list(event["uncertainties"], f"{label}.uncertainties", minimum=1),
            "confidence": _number(event["confidence"], f"{label}.confidence", minimum=0, maximum=1),
            "abstain": event["abstain"],
            "abstention_reason": event_reason,
        })

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "clip_id": clip_id,
        "video_condition": VIDEO_CONDITION,
        "window_summary": _text(report["window_summary"], "report.window_summary"),
        "dominant_phase": _choice(report["dominant_phase"], PHASES, "report.dominant_phase"),
        "events": normalized_events,
        "report_abstained": report["report_abstained"],
        "abstention_reason": report_reason,
        "overall_uncertainty": _text(report["overall_uncertainty"], "report.overall_uncertainty"),
        "coverage_limit": _text(report["coverage_limit"], "report.coverage_limit"),
    }


def _resolve_path(manifest_path: Path, raw_path: Any, label: str, *, must_exist: bool = True) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise BenchmarkGateError(f"{label} must be a non-empty path")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = manifest_path.parent / candidate
    candidate = candidate.resolve()
    if must_exist and not candidate.is_file():
        raise BenchmarkGateError(f"{label} does not exist")
    return candidate


def load_manifest(manifest_path: Path) -> tuple[dict[str, Any], list[ClipSpec]]:
    manifest_path = manifest_path.resolve()
    manifest = _strict_json(manifest_path.read_text(encoding="utf-8"))
    if _secret_key_paths(manifest):
        raise BenchmarkGateError("the input manifest must never contain credentials or secret-shaped keys")
    top = _exact_keys(
        manifest,
        {"schema_version", "study_id", "protocol_phase", "video_condition", "cost_policy", "clips"},
        "manifest",
    )
    if top["schema_version"] != INPUT_SCHEMA_VERSION:
        raise BenchmarkGateError("unsupported input manifest schema")
    if not isinstance(top["study_id"], str) or not CLIP_ID_PATTERN.fullmatch(top["study_id"]):
        raise BenchmarkGateError("study_id must be opaque and filesystem-safe")
    if top["protocol_phase"] not in {"development", "benchmark"}:
        raise BenchmarkGateError("protocol_phase must be development or benchmark")
    if top["video_condition"] != VIDEO_CONDITION:
        raise BenchmarkGateError("the primary benchmark condition must be physically_silent_video_only")
    if top["cost_policy"] != "zero_spend_only":
        raise BenchmarkGateError("cost_policy must be zero_spend_only")
    clips_value = top["clips"]
    if not isinstance(clips_value, list) or not 1 <= len(clips_value) <= 15:
        raise BenchmarkGateError("the manifest must contain between one and fifteen clips")
    if top["protocol_phase"] == "benchmark" and len(clips_value) < 6:
        raise BenchmarkGateError("benchmark phase requires at least six clips; use development for smaller checks")

    clips: list[ClipSpec] = []
    seen: set[str] = set()
    for index, raw in enumerate(clips_value):
        clip = _exact_keys(raw, {"clip_id", "video_path", "sha256", "mime_type", "rights", "held_out"}, f"manifest.clips[{index}]")
        clip_id = clip["clip_id"]
        if not isinstance(clip_id, str) or not CLIP_ID_PATTERN.fullmatch(clip_id) or clip_id in seen:
            raise BenchmarkGateError("clip_id values must be unique, opaque, and filesystem-safe")
        seen.add(clip_id)
        video_path = _resolve_path(manifest_path, clip["video_path"], f"{clip_id}.video_path")
        expected_sha = clip["sha256"]
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise BenchmarkGateError(f"{clip_id}.sha256 is invalid")
        if sha256_file(video_path) != expected_sha:
            raise BenchmarkGateError(f"{clip_id} video hash is stale")
        if clip["mime_type"] not in {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska"}:
            raise BenchmarkGateError(f"{clip_id}.mime_type is unsupported")
        rights = _exact_keys(
            clip["rights"],
            {"third_party_processing_permitted", "approved_processors", "rights_record_id", "decision_date"},
            f"{clip_id}.rights",
        )
        if not isinstance(rights["third_party_processing_permitted"], bool):
            raise BenchmarkGateError(f"{clip_id} third-party rights decision must be explicit")
        if not isinstance(rights["approved_processors"], list) or any(
            not isinstance(item, str) or not item for item in rights["approved_processors"]
        ):
            raise BenchmarkGateError(f"{clip_id}.approved_processors must be an explicit string list")
        for field in ("rights_record_id", "decision_date"):
            if not isinstance(rights[field], str) or not rights[field].strip():
                raise BenchmarkGateError(f"{clip_id}.rights.{field} must be non-empty")
        held_keys = {"labels_path", "commentary_path"}
        if isinstance(clip["held_out"], dict) and "labels_sha256" in clip["held_out"]:
            held_keys.add("labels_sha256")
        held_out = _exact_keys(clip["held_out"], held_keys, f"{clip_id}.held_out")
        label_sha = held_out.get("labels_sha256")
        if label_sha is not None and (
            not isinstance(label_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", label_sha)
            or held_out["labels_path"] is None
        ):
            raise BenchmarkGateError(f"{clip_id}.held_out.labels_sha256 is invalid")
        normalized_held_out: dict[str, str | None] = {}
        for field in ("labels_path", "commentary_path"):
            value = held_out[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise BenchmarkGateError(f"{clip_id}.held_out.{field} must be a path or null")
            normalized_held_out[field] = value
        normalized_held_out["labels_sha256"] = label_sha
        clips.append(ClipSpec(
            clip_id=clip_id,
            video_path=video_path,
            sha256=expected_sha,
            mime_type=clip["mime_type"],
            rights=dict(rights),
            held_out=normalized_held_out,
        ))
    clips.sort(key=lambda item: item.clip_id)
    return manifest, clips


def resolve_ffmpeg_executable() -> Path:
    """Resolve an existing ffmpeg binary without coupling to the active Python environment."""
    configured = os.environ.get("PLAYGROUND_FFMPEG_PATH", "").strip()
    if configured:
        path = Path(configured).resolve()
        if path.is_file():
            return path
        raise BenchmarkGateError("PLAYGROUND_FFMPEG_PATH does not name an existing file")
    try:
        import imageio_ffmpeg
    except ImportError:
        imageio_ffmpeg = None
    if imageio_ffmpeg is not None:
        path = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
        if path.is_file():
            return path
    on_path = shutil.which("ffmpeg")
    if on_path:
        return Path(on_path).resolve()
    bundled = sorted((ROOT / ".venv-soccernet" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries").glob("ffmpeg*.exe"))
    if bundled:
        return bundled[0].resolve()
    raise BenchmarkGateError("physical silence verification requires an existing ffmpeg executable")


def default_media_probe(video_path: Path) -> MediaProbe:
    """Use a resolved ffmpeg executable to prove the file has no audio stream."""
    ffmpeg = resolve_ffmpeg_executable()
    completed = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(video_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    diagnostic = completed.stderr
    video_streams = len(re.findall(r"Stream #.*Video:", diagnostic))
    audio_streams = len(re.findall(r"Stream #.*Audio:", diagnostic))
    duration_match = re.search(r"Duration:\s*([0-9]{2}):([0-9]{2}):([0-9]+(?:\.[0-9]+)?)", diagnostic)
    if video_streams < 1 or duration_match is None:
        raise BenchmarkGateError("media probe could not verify a decodable video stream and duration")
    hours, minutes, seconds = duration_match.groups()
    duration_s = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise BenchmarkGateError("media probe returned an invalid duration")
    return MediaProbe(video_streams, audio_streams, duration_s, f"imageio-ffmpeg:{ffmpeg.name}")


def _credential_from_environment(environment: Mapping[str, str]) -> tuple[str, str]:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = environment.get(name, "").strip()
        if value:
            return name, value
    raise BenchmarkGateError("Gemini credential is absent; set GEMINI_API_KEY or GOOGLE_API_KEY at runtime")


def _require_remote_rights(clips: Sequence[ClipSpec], processor_id: str) -> None:
    blocked = [
        clip.clip_id for clip in clips
        if clip.rights["third_party_processing_permitted"] is not True
        or processor_id not in clip.rights["approved_processors"]
    ]
    if blocked:
        raise BenchmarkGateError(
            "hosted upload refused: every clip must explicitly permit third-party processing and name the processor; "
            + ",".join(blocked)
        )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    for method_name in ("model_dump", "to_json_dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                result = method(mode="json") if method_name == "model_dump" else method()
            except TypeError:
                result = method()
            return _json_safe(result)
    return str(value)


class FixtureVideoProvider:
    """Local deterministic provider for dry software validation; it never opens the video."""

    provider_id = "local_fixture"
    remote = False

    def __init__(self, responses: Mapping[str, Any]) -> None:
        self._responses = dict(responses)

    @classmethod
    def from_path(cls, path: Path) -> "FixtureVideoProvider":
        payload = _strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("responses"), dict):
            raise BenchmarkGateError("mock fixture must contain a responses object keyed by clip_id")
        if _secret_key_paths(payload):
            raise BenchmarkGateError("mock fixture must not contain credentials")
        return cls(payload["responses"])

    def infer(
        self,
        *,
        clip_id: str,
        video_path: Path,
        mime_type: str,
        prompt: str,
        response_schema: dict[str, Any],
        model: str,
        credential: str | None,
    ) -> ProviderResult:
        del video_path, mime_type, prompt, response_schema, credential
        if clip_id not in self._responses:
            raise RuntimeError(f"mock fixture has no response for {clip_id}")
        fixture = self._responses[clip_id]
        if isinstance(fixture, dict) and "response_text" in fixture:
            text = fixture["response_text"]
            raw = fixture.get("raw_response", fixture)
            reported = fixture.get("model_reported", model)
        else:
            text = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
            raw = {"fixture_report": fixture}
            reported = model
        if not isinstance(text, str) or not isinstance(reported, str):
            raise RuntimeError("mock fixture response is invalid")
        return ProviderResult(text, raw, reported, {"transport": "offline_fixture"})


class GeminiVideoProvider:
    """Google Gen AI SDK adapter; imported lazily only after all upload gates pass."""

    provider_id = GEMINI_PROCESSOR_ID
    remote = True

    def __init__(
        self,
        *,
        client_factory: Callable[[str], Any] | None = None,
        poll_interval_s: float = 2.0,
        processing_timeout_s: float = 300.0,
    ) -> None:
        self._client_factory = client_factory
        self._poll_interval_s = poll_interval_s
        self._processing_timeout_s = processing_timeout_s

    def _client(self, credential: str) -> tuple[Any, str]:
        if self._client_factory is not None:
            return self._client_factory(credential), "injected-test-client"
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Gemini execution requires the optional google-genai package") from exc
        try:
            version = importlib.metadata.version("google-genai")
        except importlib.metadata.PackageNotFoundError:
            version = "installed-version-unknown"
        return genai.Client(api_key=credential), version

    @staticmethod
    def _state_name(uploaded: Any) -> str:
        state = getattr(uploaded, "state", None)
        name = getattr(state, "name", state)
        return str(name or "UNKNOWN").upper()

    def infer(
        self,
        *,
        clip_id: str,
        video_path: Path,
        mime_type: str,
        prompt: str,
        response_schema: dict[str, Any],
        model: str,
        credential: str | None,
    ) -> ProviderResult:
        del clip_id
        if not credential:
            raise BenchmarkGateError("Gemini adapter received no runtime credential")
        client, sdk_version = self._client(credential)
        uploaded = None

        def cleanup_uploaded_file() -> dict[str, Any]:
            name = getattr(uploaded, "name", None) if uploaded is not None else None
            if not name:
                return {"status": "unknown_no_identifier", "file_name": None,
                        "error_type": None, "error": None}
            record = {"status": "pending", "file_name": _redact_text(str(name), [credential]),
                      "error_type": None, "error": None}
            try:
                client.files.delete(name=name)
                record["status"] = "succeeded"
            except Exception as cleanup_error:
                record.update(status="failed", error_type=type(cleanup_error).__name__,
                              error=_redact_text(str(cleanup_error), [credential]))
            return record

        try:
            uploaded = client.files.upload(file=str(video_path), config={"mime_type": mime_type})
            deadline = time.monotonic() + self._processing_timeout_s
            while self._state_name(uploaded) == "PROCESSING":
                if time.monotonic() >= deadline:
                    raise TimeoutError("Gemini file processing exceeded the bounded timeout")
                time.sleep(self._poll_interval_s)
                uploaded = client.files.get(name=uploaded.name)
            state = self._state_name(uploaded)
            if state not in {"ACTIVE", "SUCCEEDED", "READY"}:
                raise RuntimeError(f"Gemini file processing ended in state {state}")
            response = client.models.generate_content(
                model=model,
                contents=[uploaded, prompt],
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_json_schema": response_schema,
                },
            )
            response_text = getattr(response, "text", None)
            if not isinstance(response_text, str) or not response_text.strip():
                raise RuntimeError("Gemini response contained no JSON text")
            model_reported = getattr(response, "model_version", None) or model
            result = ProviderResult(
                response_text=response_text,
                raw_response=_json_safe(response),
                model_reported=str(model_reported),
                provider_metadata={"sdk": "google-genai", "sdk_version": sdk_version},
            )
        except Exception as primary_error:
            primary_error.provider_metadata = {
                "sdk": "google-genai", "sdk_version": sdk_version,
                "remote_file_cleanup": cleanup_uploaded_file(),
            }
            raise
        else:
            result.provider_metadata["remote_file_cleanup"] = cleanup_uploaded_file()
            return result


def _contract() -> tuple[str, dict[str, Any], str, str]:
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    schema = _strict_json(SCHEMA_PATH.read_text(encoding="utf-8"))
    return prompt_template, schema, sha256_file(PROMPT_PATH), sha256_file(SCHEMA_PATH)


def _render_prompt(template: str, clip_id: str) -> str:
    if template.count("{{CLIP_ID}}") != 1:
        raise BenchmarkGateError("frozen prompt must contain exactly one {{CLIP_ID}} placeholder")
    return template.replace("{{CLIP_ID}}", clip_id)


def _verify_attempt_history(clip_dir: Path) -> list[dict[str, Any]]:
    manifest_path = clip_dir / "attempts-manifest.json"
    if not manifest_path.exists():
        return []
    manifest = _strict_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "playground-hosted-video-attempts-v1":
        raise BenchmarkGateError("invalid attempt history schema")
    attempts = manifest.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise BenchmarkGateError("invalid attempt history")
    for number, attempt in enumerate(attempts, 1):
        if attempt.get("attempt") != number or not isinstance(attempt.get("files"), dict):
            raise BenchmarkGateError("invalid attempt sequence")
        if "result.json" not in attempt["files"]:
            raise BenchmarkGateError("attempt result missing")
        for name, expected in attempt["files"].items():
            if name not in PRIMARY_ARTIFACT_NAMES - {"attempts-manifest.json"}:
                raise BenchmarkGateError("invalid attempt artifact name")
            path = clip_dir / "attempts" / f"{number:04d}" / name
            if not path.is_file() or sha256_file(path) != expected:
                raise BenchmarkGateError("attempt history hash changed")
    return attempts


def _preserve_attempt(clip_dir: Path) -> None:
    result_path = clip_dir / "result.json"
    if not result_path.is_file():
        return
    attempts = _verify_attempt_history(clip_dir)
    result = _strict_json(result_path.read_text(encoding="utf-8"))
    names = {"request-receipt.json", "result.json"}
    if result["status"] == "provider_failed":
        names.add("provider-failure.json")
    else:
        names.add("raw-response.json")
        names.add("event-report.json" if result["status"] == "complete" else "parse-failure.json")
    files = {name: sha256_file(clip_dir / name) for name in sorted(names)}
    if attempts and attempts[-1]["files"] == files:
        return
    number = len(attempts) + 1
    target = clip_dir / "attempts" / f"{number:04d}"
    target.mkdir(parents=True, exist_ok=True)
    for name, expected in files.items():
        path = target / name
        if path.exists() and sha256_file(path) != expected:
            raise BenchmarkGateError("interrupted attempt archive conflicts")
        if not path.exists():
            path.write_bytes((clip_dir / name).read_bytes())
    attempts.append({"attempt": number, "status": result["status"], "files": files})
    write_json_atomic(clip_dir / "attempts-manifest.json", {
        "schema_version": "playground-hosted-video-attempts-v1", "attempts": attempts,
    })


def _load_resumable_result(clip_dir: Path, expected_input_fingerprint: str) -> dict[str, Any] | None:
    _verify_attempt_history(clip_dir)
    result_path = clip_dir / "result.json"
    if not result_path.is_file():
        return None
    result = _strict_json(result_path.read_text(encoding="utf-8"))
    if result.get("input_fingerprint") != expected_input_fingerprint:
        raise BenchmarkGateError("stale cached run: input fingerprint changed")
    if result.get("status") == "provider_failed":
        return None
    if result.get("status") not in {"complete", "parse_failed"}:
        raise BenchmarkGateError("stale cached run: clip status is not resumable")
    receipt_path = clip_dir / "request-receipt.json"
    raw_path = clip_dir / "raw-response.json"
    if not receipt_path.is_file() or not raw_path.is_file():
        raise BenchmarkGateError("stale cached run: a required primary receipt is missing")
    receipt = _strict_json(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("input_fingerprint") != expected_input_fingerprint:
        raise BenchmarkGateError("stale cached run: request receipt fingerprint changed")
    if result.get("request_receipt_sha256") != sha256_file(receipt_path):
        raise BenchmarkGateError("stale cached run: request receipt hash changed")
    if result.get("raw_response_sha256") != sha256_file(raw_path):
        raise BenchmarkGateError("stale cached run: raw response hash changed")
    if result["status"] == "complete":
        report_path = clip_dir / "event-report.json"
        if not report_path.is_file() or result.get("event_report_sha256") != sha256_file(report_path):
            raise BenchmarkGateError("stale cached run: event report hash changed")
    else:
        failure_path = clip_dir / "parse-failure.json"
        if not failure_path.is_file() or result.get("parse_failure_sha256") != sha256_file(failure_path):
            raise BenchmarkGateError("stale cached run: parse failure hash changed")
    return result


def _primary_seal(out_dir: Path, run_fingerprint: str, clip_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    for result in clip_results:
        clip_dir = out_dir / result["clip_id"]
        for name in sorted(PRIMARY_ARTIFACT_NAMES):
            path = clip_dir / name
            if path.is_file():
                files.append({"clip_id": result["clip_id"], "kind": name, "sha256": sha256_file(path)})
    seal = {
        "schema_version": PRIMARY_SEAL_SCHEMA_VERSION,
        "sealed_at": utc_now(),
        "run_fingerprint": run_fingerprint,
        "terminal_clip_count": len(clip_results),
        "files": sorted(files, key=lambda item: (item["clip_id"], item["kind"])),
        "labels_or_commentary_opened": False,
    }
    write_json_atomic(out_dir / "primary-seal.json", seal)
    return seal


def _verify_existing_primary_seal(out_dir: Path, run_fingerprint: str) -> dict[str, Any] | None:
    """Refuse to resume or reseal if any previously sealed primary receipt changed."""
    seal_path = out_dir / "primary-seal.json"
    if not seal_path.is_file():
        return None
    seal = _exact_keys(
        _strict_json(seal_path.read_text(encoding="utf-8")),
        {
            "schema_version", "sealed_at", "run_fingerprint", "terminal_clip_count",
            "files", "labels_or_commentary_opened",
        },
        "primary seal",
    )
    if seal["schema_version"] != PRIMARY_SEAL_SCHEMA_VERSION or seal["run_fingerprint"] != run_fingerprint:
        raise BenchmarkGateError("existing primary seal belongs to a different immutable run")
    if seal["labels_or_commentary_opened"] is not False:
        raise BenchmarkGateError("existing primary seal has an invalid evidence-separation flag")
    files = seal["files"]
    if not isinstance(files, list) or not files:
        raise BenchmarkGateError("existing primary seal contains no artifact hashes")
    seen: set[tuple[str, str]] = set()
    kinds_by_clip: dict[str, set[str]] = {}
    for index, raw in enumerate(files):
        item = _exact_keys(raw, {"clip_id", "kind", "sha256"}, f"primary seal file {index}")
        clip_id = item["clip_id"]
        kind = item["kind"]
        expected_sha = item["sha256"]
        if not isinstance(clip_id, str) or not CLIP_ID_PATTERN.fullmatch(clip_id):
            raise BenchmarkGateError("existing primary seal contains an invalid clip id")
        if kind not in PRIMARY_ARTIFACT_NAMES:
            raise BenchmarkGateError("existing primary seal contains an unsupported artifact kind")
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise BenchmarkGateError("existing primary seal contains an invalid artifact hash")
        identity = (clip_id, kind)
        if identity in seen:
            raise BenchmarkGateError("existing primary seal contains a duplicate artifact")
        seen.add(identity)
        kinds_by_clip.setdefault(clip_id, set()).add(kind)
        path = out_dir / clip_id / kind
        if not path.is_file() or sha256_file(path) != expected_sha:
            raise BenchmarkGateError(f"existing primary seal hash mismatch for {clip_id}/{kind}")
    if any(not {"request-receipt.json", "result.json"}.issubset(kinds) for kinds in kinds_by_clip.values()):
        raise BenchmarkGateError("existing primary seal omits a required request or result receipt")
    for clip_id in kinds_by_clip:
        _verify_attempt_history(out_dir / clip_id)
    if seal["terminal_clip_count"] != len(kinds_by_clip):
        raise BenchmarkGateError("existing primary seal terminal clip count is stale")
    return seal


def _open_posthoc(
    *,
    manifest_path: Path,
    clips: Sequence[ClipSpec],
    out_dir: Path,
    primary_seal: dict[str, Any],
) -> dict[str, Any]:
    seal_path = out_dir / "primary-seal.json"
    if not seal_path.is_file():
        raise RuntimeError("post-hoc evidence cannot open before the primary seal exists")
    persisted_seal = _strict_json(seal_path.read_text(encoding="utf-8"))
    if persisted_seal != primary_seal:
        raise RuntimeError("post-hoc evidence refused a stale or replaced primary seal")
    result_by_clip = {
        item["clip_id"]: item
        for item in (_strict_json((out_dir / clip.clip_id / "result.json").read_text(encoding="utf-8")) for clip in clips)
    }
    records: list[dict[str, Any]] = []
    for clip in clips:
        evidence: dict[str, Any] = {}
        for field, kind in (("labels_path", "held_out_labels"), ("commentary_path", "auxiliary_commentary")):
            raw_path = clip.held_out[field]
            if raw_path is None:
                evidence[kind] = None
                continue
            path = _resolve_path(manifest_path, raw_path, f"{clip.clip_id}.{field}")
            evidence_sha = sha256_file(path)
            frozen_sha = clip.held_out.get("labels_sha256") if field == "labels_path" else None
            if frozen_sha is not None and evidence_sha != frozen_sha:
                raise BenchmarkGateError(f"{clip.clip_id} held-out labels changed after freeze")
            content = _strict_json(path.read_text(encoding="utf-8"))
            evidence[kind] = {"sha256": evidence_sha, "content": content}
            if field == "labels_path":
                evidence[kind]["frozen_sha256"] = frozen_sha
        records.append({
            "clip_id": clip.clip_id,
            "primary_result_sha256": sha256_file(out_dir / clip.clip_id / "result.json"),
            "primary_status": result_by_clip[clip.clip_id]["status"],
            "evidence": evidence,
        })
    audit = {
        "schema_version": POSTHOC_SCHEMA_VERSION,
        "opened_at": utc_now(),
        "primary_seal_sha256": sha256_file(seal_path),
        "policy": (
            "Held-out labels were unavailable to the provider and opened only after the primary seal. "
            "Commentary is auxiliary evidence, not ground truth, and cannot revise the sealed prediction."
        ),
        "records": records,
    }
    write_json_atomic(out_dir / "posthoc-audit.json", audit)
    return audit


def _verify_existing_posthoc(
    *, out_dir: Path, run_manifest: dict[str, Any], primary_seal: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Verify an already-opened audit and make it an irreversible boundary for provider calls."""
    path = out_dir / "posthoc-audit.json"
    if not path.is_file():
        return None
    if primary_seal is None:
        raise BenchmarkGateError("post-hoc audit exists without a primary seal")
    expected_sha = run_manifest.get("posthoc_audit_sha256")
    if not isinstance(expected_sha, str) or expected_sha != sha256_file(path):
        raise BenchmarkGateError("post-hoc audit is not hash-bound by the run manifest")
    audit = _strict_json(path.read_text(encoding="utf-8"))
    if audit.get("schema_version") != POSTHOC_SCHEMA_VERSION:
        raise BenchmarkGateError("post-hoc audit schema is unsupported")
    if audit.get("primary_seal_sha256") != sha256_file(out_dir / "primary-seal.json"):
        raise BenchmarkGateError("post-hoc audit is bound to a different primary seal")
    return audit


def run_benchmark(
    *,
    manifest_path: Path,
    private_out: Path,
    provider: VideoProvider,
    model: str,
    dry_run: bool = False,
    execute_remote: bool = False,
    zero_spend_confirmed: bool = False,
    open_held_out: bool = False,
    environment: Mapping[str, str] | None = None,
    media_probe: Callable[[Path], MediaProbe] = default_media_probe,
) -> dict[str, Any]:
    """Validate the full batch before any provider call, then persist resumable private receipts."""
    if not isinstance(model, str) or not model.strip():
        raise BenchmarkGateError("model must be non-empty")
    out_dir = require_private_output(private_out)
    manifest_path = manifest_path.resolve()
    manifest, clips = load_manifest(manifest_path)
    prompt_template, response_schema, prompt_sha, schema_sha = _contract()
    runner_sha = sha256_file(Path(__file__).resolve())
    probes: dict[str, MediaProbe] = {}
    for clip in clips:
        probe = media_probe(clip.video_path)
        if probe.video_streams < 1 or probe.audio_streams != 0 or probe.duration_s <= 0:
            raise BenchmarkGateError(f"{clip.clip_id} failed physical silent-video verification")
        probes[clip.clip_id] = probe

    env = dict(os.environ if environment is None else environment)
    credential_name: str | None = None
    credential: str | None = None
    rights_ready = all(
        clip.rights["third_party_processing_permitted"] is True
        and provider.provider_id in clip.rights["approved_processors"]
        for clip in clips
    )
    credential_present = False
    if provider.remote:
        if not dry_run:
            if not execute_remote:
                raise BenchmarkGateError("remote provider execution requires explicit execute_remote=True")
            if not zero_spend_confirmed:
                raise BenchmarkGateError(
                    "remote provider execution requires confirmation that the selected account/model route cannot incur spend"
                )
            _require_remote_rights(clips, provider.provider_id)
            credential_name, credential = _credential_from_environment(env)
            credential_present = True
        else:
            credential_present = any(env.get(name, "").strip() for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"))

    run_fingerprint = canonical_sha256({
        "schema_version": RUN_SCHEMA_VERSION,
        "input_manifest_sha256": sha256_file(manifest_path),
        "provider": provider.provider_id,
        "model": model,
        "prompt_sha256": prompt_sha,
        "response_schema_sha256": schema_sha,
        "runner_sha256": runner_sha,
        "video_condition": VIDEO_CONDITION,
        "scoring_contract": SCORING_CONTRACT,
    })
    existing_primary_seal = _verify_existing_primary_seal(out_dir, run_fingerprint)
    run_path = out_dir / "run-manifest.json"
    existing: dict[str, Any] | None = None
    if existing_primary_seal is not None and not run_path.is_file():
        raise BenchmarkGateError("existing primary seal has no run manifest")
    if run_path.is_file():
        existing = _strict_json(run_path.read_text(encoding="utf-8"))
        if existing.get("run_fingerprint") != run_fingerprint:
            raise BenchmarkGateError("existing run manifest belongs to a different immutable run")
        expected_immutable = {
            "schema_version": RUN_SCHEMA_VERSION,
            "input_manifest_sha256": sha256_file(manifest_path),
            "study_id": manifest["study_id"],
            "protocol_phase": manifest["protocol_phase"],
            "provider": provider.provider_id,
            "model_requested": model,
            "prompt_sha256": prompt_sha,
            "response_schema_sha256": schema_sha,
            "runner_sha256": runner_sha,
            "video_condition": VIDEO_CONDITION,
            "cost_policy": "zero_spend_only",
            "clip_order": [clip.clip_id for clip in clips],
            "truth_boundary": "SYSTEMS GO / SEMANTIC NO-GO",
        }
        mismatches = [key for key, expected in expected_immutable.items() if existing.get(key) != expected]
        if mismatches:
            raise BenchmarkGateError("existing run manifest immutable fields changed: " + ",".join(mismatches))
        if existing_primary_seal is not None and existing.get("primary_seal_sha256") != sha256_file(out_dir / "primary-seal.json"):
            raise BenchmarkGateError("existing run manifest primary seal hash changed")
    run_manifest: dict[str, Any] = existing or {
        "schema_version": RUN_SCHEMA_VERSION,
        "created_at": utc_now(),
        "run_fingerprint": run_fingerprint,
        "input_manifest_sha256": sha256_file(manifest_path),
        "study_id": manifest["study_id"],
        "protocol_phase": manifest["protocol_phase"],
        "provider": provider.provider_id,
        "model_requested": model,
        "prompt_sha256": prompt_sha,
        "response_schema_sha256": schema_sha,
        "runner_sha256": runner_sha,
        "video_condition": VIDEO_CONDITION,
        "cost_policy": "zero_spend_only",
        "zero_spend_confirmed": bool(zero_spend_confirmed),
        "credential": {"present": credential_present, "environment_variable": credential_name},
        "rights_ready_for_selected_provider": rights_ready,
        "clip_order": [clip.clip_id for clip in clips],
        "clips": [],
        "status": "preflight_complete",
        "truth_boundary": "SYSTEMS GO / SEMANTIC NO-GO",
    }
    run_manifest["updated_at"] = utc_now()
    run_manifest["credential"] = {"present": credential_present, "environment_variable": credential_name}
    run_manifest["rights_ready_for_selected_provider"] = rights_ready
    run_manifest["zero_spend_confirmed"] = bool(zero_spend_confirmed)
    existing_posthoc = _verify_existing_posthoc(
        out_dir=out_dir,
        run_manifest=run_manifest,
        primary_seal=existing_primary_seal,
    )
    if dry_run:
        run_manifest["status"] = "validated_no_inference"
        run_manifest["preflight"] = [
            {
                "clip_id": clip.clip_id,
                "input_sha256": clip.sha256,
                "physical_streams": asdict(probes[clip.clip_id]),
                "third_party_processing_permitted": clip.rights["third_party_processing_permitted"],
                "selected_provider_approved": provider.provider_id in clip.rights["approved_processors"],
            }
            for clip in clips
        ]
        write_json_atomic(run_path, run_manifest)
        return run_manifest

    clip_results: list[dict[str, Any]] = []
    provider_invocation_count = 0
    for clip in clips:
        probe = probes[clip.clip_id]
        prompt = _render_prompt(prompt_template, clip.clip_id)
        input_fingerprint = canonical_sha256({
            "run_fingerprint": run_fingerprint,
            "clip_id": clip.clip_id,
            "clip_sha256": clip.sha256,
            "duration_s": probe.duration_s,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        })
        clip_dir = out_dir / clip.clip_id
        result_path = clip_dir / "result.json"
        cached_result = _load_resumable_result(clip_dir, input_fingerprint)
        if cached_result is not None:
            clip_results.append(cached_result)
            continue

        if existing_posthoc is not None:
            raise BenchmarkGateError(
                "provider invocation refused because held-out evidence was already opened; use a fresh output directory"
            )

        clip_dir.mkdir(parents=True, exist_ok=True)
        _preserve_attempt(clip_dir)
        request_receipt = {
            "schema_version": "playground-hosted-video-request-receipt-v1",
            "attempt_number": len(_verify_attempt_history(clip_dir)) + 1,
            "requested_at": utc_now(),
            "clip_id": clip.clip_id,
            "input_fingerprint": input_fingerprint,
            "input_sha256": clip.sha256,
            "mime_type": clip.mime_type,
            "media_probe": asdict(probe),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_template_sha256": prompt_sha,
            "response_schema_sha256": schema_sha,
            "runner_sha256": runner_sha,
            "provider": provider.provider_id,
            "model_requested": model,
            "rights_record_id": clip.rights["rights_record_id"],
            "credential_environment_variable": credential_name,
            "credential_persisted": False,
            "held_out_opened_before_request": False,
            "held_out_labels_sha256": clip.held_out.get("labels_sha256"),
            "scoring_contract": SCORING_CONTRACT,
        }
        write_json_atomic(clip_dir / "request-receipt.json", request_receipt)
        request_receipt_sha256 = sha256_file(clip_dir / "request-receipt.json")
        secrets = [credential] if credential else []
        started = time.perf_counter()
        try:
            provider_invocation_count += 1
            provider_result = provider.infer(
                clip_id=clip.clip_id,
                video_path=clip.video_path,
                mime_type=clip.mime_type,
                prompt=prompt,
                response_schema=response_schema,
                model=model,
                credential=credential,
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            raw_wrapper = {
                "schema_version": "playground-hosted-video-raw-response-v1",
                "clip_id": clip.clip_id,
                "provider": provider.provider_id,
                "model_requested": model,
                "model_reported": provider_result.model_reported,
                "latency_ms": latency_ms,
                "input_sha256": clip.sha256,
                "response_text": provider_result.response_text,
                "provider_response": provider_result.raw_response,
                "provider_metadata": provider_result.provider_metadata,
            }
            raw_wrapper = redact_secrets(raw_wrapper, secrets)
            write_json_atomic(clip_dir / "raw-response.json", raw_wrapper)
            try:
                parsed = _strict_json(provider_result.response_text)
                normalized = validate_event_report(parsed, clip_id=clip.clip_id, duration_s=probe.duration_s)
                normalized = redact_secrets(normalized, secrets)
                write_json_atomic(clip_dir / "event-report.json", normalized)
                result = {
                    "schema_version": "playground-hosted-video-clip-result-v1",
                    "clip_id": clip.clip_id,
                    "status": "complete",
                    "input_fingerprint": input_fingerprint,
                    "input_sha256": clip.sha256,
                    "request_receipt_sha256": request_receipt_sha256,
                    "model_requested": model,
                    "model_reported": provider_result.model_reported,
                    "latency_ms": latency_ms,
                    "raw_response_sha256": sha256_file(clip_dir / "raw-response.json"),
                    "event_report_sha256": sha256_file(clip_dir / "event-report.json"),
                    "parse_failure_sha256": None,
                    "event_count": len(normalized["events"]),
                    "parse_failure": None,
                }
            except Exception as exc:
                failure = {
                    "schema_version": "playground-hosted-video-parse-failure-v1",
                    "clip_id": clip.clip_id,
                    "error_type": type(exc).__name__,
                    "error": _redact_text(str(exc), secrets),
                    "raw_response_sha256": sha256_file(clip_dir / "raw-response.json"),
                }
                write_json_atomic(clip_dir / "parse-failure.json", failure)
                result = {
                    "schema_version": "playground-hosted-video-clip-result-v1",
                    "clip_id": clip.clip_id,
                    "status": "parse_failed",
                    "input_fingerprint": input_fingerprint,
                    "input_sha256": clip.sha256,
                    "request_receipt_sha256": request_receipt_sha256,
                    "model_requested": model,
                    "model_reported": provider_result.model_reported,
                    "latency_ms": latency_ms,
                    "raw_response_sha256": sha256_file(clip_dir / "raw-response.json"),
                    "event_report_sha256": None,
                    "parse_failure_sha256": sha256_file(clip_dir / "parse-failure.json"),
                    "event_count": None,
                    "parse_failure": failure,
                }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000)
            failure = {
                "schema_version": "playground-hosted-video-provider-failure-v1",
                "clip_id": clip.clip_id,
                "error_type": type(exc).__name__,
                "error": _redact_text(str(exc), secrets),
                "latency_ms": latency_ms,
                "provider_metadata": redact_secrets(_json_safe(getattr(exc, "provider_metadata", {})), secrets),
            }
            write_json_atomic(clip_dir / "provider-failure.json", failure)
            result = {
                "schema_version": "playground-hosted-video-clip-result-v1",
                "clip_id": clip.clip_id,
                "status": "provider_failed",
                "input_fingerprint": input_fingerprint,
                "input_sha256": clip.sha256,
                "request_receipt_sha256": request_receipt_sha256,
                "model_requested": model,
                "model_reported": None,
                "latency_ms": latency_ms,
                "raw_response_sha256": None,
                "event_report_sha256": None,
                "parse_failure_sha256": None,
                "event_count": None,
                "parse_failure": None,
            }
        write_json_atomic(result_path, result)
        _preserve_attempt(clip_dir)
        clip_results.append(result)
        run_manifest["clips"] = clip_results
        run_manifest["status"] = "running"
        run_manifest["updated_at"] = utc_now()
        write_json_atomic(run_path, run_manifest)

    if len(clip_results) != len(clips) or any(item["status"] not in TERMINAL_CLIP_STATES for item in clip_results):
        raise RuntimeError("primary run did not reach a terminal state for every clip")
    failure_count = sum(item["status"] != "complete" for item in clip_results)
    expected_counts = {
        "requested": len(clips),
        "complete": len(clips) - failure_count,
        "failed": failure_count,
    }
    if provider_invocation_count == 0 and existing_primary_seal is not None:
        persisted_run = _strict_json(run_path.read_text(encoding="utf-8"))
        if persisted_run.get("clips") != clip_results:
            raise BenchmarkGateError("existing run manifest cached clip summaries changed")
        if persisted_run.get("counts") != expected_counts:
            raise BenchmarkGateError("existing run manifest counts changed")
        expected_status = (
            ("complete_with_posthoc_audit" if failure_count == 0 else "complete_with_failures_and_posthoc_audit")
            if existing_posthoc is not None
            else ("primary_sealed" if failure_count == 0 else "primary_sealed_with_failures")
        )
        if persisted_run.get("status") != expected_status:
            raise BenchmarkGateError("existing run manifest status changed")
    if provider_invocation_count == 0 and existing_primary_seal is not None:
        seal = existing_primary_seal
    else:
        seal = _primary_seal(out_dir, run_fingerprint, clip_results)
    run_manifest["clips"] = clip_results
    run_manifest["primary_seal_sha256"] = sha256_file(out_dir / "primary-seal.json")
    run_manifest["counts"] = expected_counts
    run_manifest["status"] = "primary_sealed" if failure_count == 0 else "primary_sealed_with_failures"
    run_manifest["updated_at"] = utc_now()
    provider_failure_count = sum(item["status"] == "provider_failed" for item in clip_results)
    if existing_posthoc is not None and provider_invocation_count == 0:
        return _strict_json(run_path.read_text(encoding="utf-8"))
    if provider_invocation_count == 0 and existing_primary_seal is not None and not open_held_out:
        return _strict_json(run_path.read_text(encoding="utf-8"))
    if open_held_out and provider_failure_count:
        write_json_atomic(run_path, run_manifest)
        raise BenchmarkGateError(
            "held-out evidence cannot open while provider failures remain retryable; retry first or use a fresh output directory"
        )
    if open_held_out:
        write_json_atomic(run_path, run_manifest)
        audit = _open_posthoc(
            manifest_path=manifest_path,
            clips=clips,
            out_dir=out_dir,
            primary_seal=seal,
        )
        run_manifest["posthoc_audit_sha256"] = sha256_file(out_dir / "posthoc-audit.json")
        run_manifest["status"] = (
            "complete_with_posthoc_audit" if failure_count == 0
            else "complete_with_failures_and_posthoc_audit"
        )
        run_manifest["posthoc_policy"] = audit["policy"]
    write_json_atomic(run_path, run_manifest)
    return run_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--provider", choices=("mock", "gemini"), default="mock")
    parser.add_argument("--model", default=CURRENT_GEMINI_MODEL)
    parser.add_argument("--mock-responses", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-remote", action="store_true")
    parser.add_argument(
        "--confirm-zero-spend",
        action="store_true",
        help="Confirm the selected Gemini account/model route is currently free and cannot incur paid usage.",
    )
    parser.add_argument("--open-held-out", action="store_true")
    args = parser.parse_args()
    if args.provider == "mock":
        if args.mock_responses is None and not args.dry_run:
            parser.error("--mock-responses is required for a non-dry-run mock provider")
        provider: VideoProvider = (
            FixtureVideoProvider.from_path(args.mock_responses)
            if args.mock_responses is not None else FixtureVideoProvider({})
        )
    else:
        provider = GeminiVideoProvider()
    summary = run_benchmark(
        manifest_path=args.manifest,
        private_out=args.private_out,
        provider=provider,
        model=args.model,
        dry_run=args.dry_run,
        execute_remote=args.execute_remote,
        zero_spend_confirmed=args.confirm_zero_spend,
        open_held_out=args.open_held_out,
    )
    print(json.dumps({
        "status": summary["status"],
        "run_fingerprint": summary["run_fingerprint"],
        "clip_count": len(summary.get("clip_order", [])),
        "remote_execution_authorized": bool(
            provider.remote and not args.dry_run and args.execute_remote and args.confirm_zero_spend
        ),
    }, indent=2))
    return 2 if summary.get("counts", {}).get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
