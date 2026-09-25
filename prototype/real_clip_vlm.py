"""Run an LLM-only soccer play-type probe on a locally authorized real clip.

This module deliberately contains no hand-engineered play classifier, tracker, or
visual detector.  It samples and hashes video frames, sends contact sheets to a
loopback-only multimodal model, validates the structured answer, and records a
provenance receipt.  It is suitable for a SoccerDB clip only after its approved
local manifest and terms record exist; it never downloads or authenticates to a
dataset provider.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from openai_compatible_adapter import LocalOpenAICompatibleAdapter
from sports_play_lab import OUTPUT_SCHEMA_VERSION, validate_prediction_payload


DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "zai-org/glm-4.6v-flash"
PLAY_TYPES = (
    "penalty_kick", "kick_off", "goal", "substitution", "offside",
    "shot_on_target", "shot_off_target", "clearance", "ball_out_of_play",
    "throw_in", "foul", "indirect_free_kick", "direct_free_kick",
    "corner_kick", "yellow_card", "red_card", "second_yellow_red_card",
    "background_or_other",
)
SAMPLER_VERSION = "uniform-contact-sheets-v2-single-frame-full-resolution"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def uniform_sample_timestamps(*, frame_count: int, fps: float, count: int) -> list[float]:
    if frame_count < 1 or not math.isfinite(fps) or fps <= 0 or count < 1:
        raise ValueError("sampling metadata is invalid")
    indices = np.linspace(0, frame_count - 1, num=min(count, frame_count), dtype=int)
    return [float(index / fps) for index in indices.tolist()]


def sample_video(video_path: Path, *, count: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Uniformly sample and hash decoded frames without inferring a play label."""
    if count < 1:
        raise ValueError("count must be positive")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if frame_count < 1 or not math.isfinite(fps) or fps <= 0:
        cap.release()
        raise RuntimeError("Video metadata is invalid")
    indices = np.linspace(0, frame_count - 1, num=min(count, frame_count), dtype=int)
    frames: list[dict[str, Any]] = []
    for ordinal, index in enumerate(indices.tolist()):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f"Could not decode frame {index}")
        frames.append({
            "ordinal": ordinal,
            "frame_index": int(index),
            "timestamp_s": float(index / fps),
            "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
            "frame": frame,
        })
    cap.release()
    metadata = {
        "clip_sha256": sha256_file(video_path),
        "frame_count": frame_count,
        "fps": fps,
        "duration_s": frame_count / fps,
        "sample_count": len(frames),
    }
    return metadata, frames


def write_contact_sheets(frames: Iterable[dict[str, Any]], *, out_dir: Path, sheets: int) -> list[Path]:
    """Create labeled contact sheets solely as the VLM's visual input representation."""
    frame_list = list(frames)
    if sheets < 1:
        raise ValueError("sheets must be positive")
    groups = [list(group) for group in np.array_split(np.array(frame_list, dtype=object), min(sheets, len(frame_list)))]
    result: list[Path] = []
    for sheet_index, group_array in enumerate(groups):
        group = list(group_array)
        if len(group) == 1:
            rows, cols = 1, 1
            cell_height, cell_width = 720, 1280
        elif len(group) == 2:
            rows, cols = 1, 2
            cell_height, cell_width = 360, 640
        else:
            rows, cols = 2, 2
            cell_height, cell_width = 360, 640
        canvas = np.zeros((rows * cell_height, cols * cell_width, 3), dtype=np.uint8)
        for cell, item in enumerate(group):
            row, col = divmod(cell, cols)
            image = cv2.resize(item["frame"], (cell_width, cell_height), interpolation=cv2.INTER_AREA)
            canvas[row * cell_height:(row + 1) * cell_height, col * cell_width:(col + 1) * cell_width] = image
            label = f"t={item['timestamp_s']:.2f}s  frame={item['frame_index']}"
            cv2.rectangle(canvas, (col * cell_width, row * cell_height),
                          (col * cell_width + 290, row * cell_height + 34), (0, 0, 0), -1)
            cv2.putText(canvas, label, (col * cell_width + 10, row * cell_height + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
        path = out_dir / f"contact-sheet-{sheet_index + 1:02d}.png"
        if not cv2.imwrite(str(path), canvas):
            raise RuntimeError(f"Could not write contact sheet: {path}")
        result.append(path)
    return result


def image_data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def prompt() -> str:
    labels = ", ".join(PLAY_TYPES)
    return (
        "You are classifying the primary observable soccer play at the target moment near the middle of a short clip, "
        "shown as chronological visual contact sheets. Earlier or later actions can be context rather than the target. "
        f"Choose exactly one normalized play type from: {labels}. "
        "Classify the underlying restart or action, not merely its outcome. Use the fine-grained event: "
        "distinguish direct_free_kick from indirect_free_kick; shot_on_target from "
        "shot_off_target; and yellow_card from red_card. Classify the underlying restart when its setup and execution "
        "are visible. If the referee visibly holds up a colored card at the target moment, choose the corresponding card "
        "event even when an earlier foul caused it. Choose goal only when the centered sequence visibly establishes that "
        "the ball crossed the line, the score changed, or players clearly celebrate a scored goal. A view of the goal, a "
        "goalkeeper, or a post-shot player close-up alone is not evidence of a goal; choose the supported shot class or "
        "abstain when the outcome is not visible. "
        "Use only what is visible in the supplied frames. Do not use team knowledge, score context, audio, or source metadata. "
        "If a single play type is not visually supported, abstain. Return strict JSON with exactly these keys: "
        "answer, confidence, temporal_evidence_s, spatial_evidence, trajectory, abstained, abstention_reason. "
        "For a non-abstention, answer must be one listed play type, confidence must be 0 to 1, "
        "temporal_evidence_s must be exactly one two-number JSON array [start_seconds,end_seconds] identifying the "
        "supported interval with start_seconds strictly less than end_seconds (never strings and never a list of individual "
        "timestamps). If the evidence is clearest in one sampled frame, use that frame timestamp as the start and the next "
        "sampled timestamp as the end; never repeat the same timestamp twice. Spatial_evidence must be a non-empty list of coarse visible regions, "
        "and trajectory must be an empty list. For abstention, use answer insufficient_visual_evidence, confidence 0, "
        "temporal_evidence_s [0,0], empty spatial_evidence and trajectory, and a concise abstention_reason. "
        "Never use abstained, unknown, or none as the answer string; the exact abstention answer is insufficient_visual_evidence."
    )


def structured_response_format(sample_timestamps: Iterable[float] | None = None) -> dict[str, Any]:
    """Constrain first-pass local-model output without repairing it afterward."""
    timestamps = list(sample_timestamps or [])
    valid_intervals = [
        [round(float(start), 6), round(float(end), 6)]
        for start, end in zip(timestamps, timestamps[1:]) if float(end) > float(start)
    ]
    required = [
        "answer", "confidence", "temporal_evidence_s", "spatial_evidence",
        "trajectory", "abstained", "abstention_reason",
    ]
    abstention_schema = {
        "type": "object",
        "properties": {
            "answer": {"const": "insufficient_visual_evidence"},
            "confidence": {"const": 0},
            "temporal_evidence_s": {"enum": [[0, 0]]},
            "spatial_evidence": {
                "type": "array", "items": {"type": "string"},
                "minItems": 0, "maxItems": 0, "enum": [[]],
            },
            "trajectory": {
                "type": "array", "items": {"type": "object"},
                "minItems": 0, "maxItems": 0, "enum": [[]],
            },
            "abstained": {"const": True},
            "abstention_reason": {"type": "string", "minLength": 1},
        },
        "required": required,
        "additionalProperties": False,
    }
    prediction_schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "enum": list(PLAY_TYPES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "temporal_evidence_s": (
                {"enum": valid_intervals} if valid_intervals else {
                    "type": "array", "items": {"type": "number"},
                    "minItems": 2, "maxItems": 2, "uniqueItems": True,
                }
            ),
            "spatial_evidence": {
                "type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1,
            },
            "trajectory": {"enum": [[]]},
            "abstained": {"const": False},
            "abstention_reason": {"const": None},
        },
        "required": required,
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "soccer_play_visual_prediction",
            "strict": True,
            "schema": {"oneOf": [abstention_schema, prediction_schema]},
        },
    }


def parse_json_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        raise ValueError("assistant content is not text")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("assistant content is not a JSON object")
    return parsed


def normalise_model_output(raw: dict[str, Any], *, clip_id: str, question_id: str) -> dict[str, Any]:
    """Attach immutable identifiers while rejecting malformed model semantics."""
    expected = {
        "answer", "confidence", "temporal_evidence_s", "spatial_evidence",
        "trajectory", "abstained", "abstention_reason",
    }
    if set(raw) != expected:
        raise ValueError(f"model keys must exactly equal {sorted(expected)}")
    if isinstance(raw["confidence"], bool):
        raise ValueError("confidence must not be boolean")
    try:
        confidence = float(raw["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc
    abstained = raw["abstained"]
    reason = raw["abstention_reason"]
    # Some OpenAI-compatible local servers serialize an absent nullable field as
    # an empty string.  Preserve the raw response separately, then normalize only
    # this null-equivalent representation for a non-abstained prediction.
    if abstained is False and reason == "":
        reason = None
    payload = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "clip_id": clip_id,
        "question_id": question_id,
        "answer": raw["answer"],
        "confidence": confidence,
        "temporal_evidence_s": raw["temporal_evidence_s"],
        "spatial_evidence": raw["spatial_evidence"],
        "trajectory": raw["trajectory"],
        "abstained": abstained,
        "abstention_reason": reason,
    }
    if payload["answer"] not in PLAY_TYPES and payload["answer"] != "insufficient_visual_evidence":
        raise ValueError("answer is outside the fixed soccer play taxonomy")
    errors = validate_prediction_payload(payload)
    if errors:
        raise ValueError("prediction contract failed: " + "; ".join(errors))
    if not payload["abstained"] and payload["answer"] not in PLAY_TYPES:
        raise ValueError("non-abstained answer is outside the fixed soccer play taxonomy")
    return payload


def run(
    *, video_path: Path, clip_id: str, out_dir: Path, source_reference: str,
    source_manifest: Path | None, endpoint: str, model: str, sample_count: int, sheets: int,
    max_tokens: int = 2400,
) -> dict[str, Any]:
    if not video_path.is_file():
        raise FileNotFoundError(video_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata, frames = sample_video(video_path, count=sample_count)
    sheet_paths = write_contact_sheets(frames, out_dir=out_dir, sheets=sheets)
    frame_manifest = [{key: value for key, value in item.items() if key != "frame"} for item in frames]
    manifest = {
        "schema_version": "playground-real-clip-vlm-input-v1",
        "clip_id": clip_id,
        "source_reference": source_reference,
        "source_manifest": None if source_manifest is None else {
            "path": str(source_manifest), "sha256": sha256_file(source_manifest),
        },
        "video": {"path": str(video_path), **metadata},
        "frames": frame_manifest,
        "contact_sheets": [{"path": str(path), "sha256": sha256_file(path)} for path in sheet_paths],
    }
    write_json(out_dir / "input-manifest.json", manifest)

    adapter = LocalOpenAICompatibleAdapter(endpoint, model)
    response_format = structured_response_format(item["timestamp_s"] for item in frames)
    request_payload = adapter.build_request(prompt(), [image_data_url(path) for path in sheet_paths])
    # Constrain first-pass generation; the independent project-side validator below
    # still fails closed on any cross-field violation.
    request_payload["response_format"] = response_format
    request_payload["temperature"] = 0
    request_payload["max_tokens"] = max_tokens
    write_json(out_dir / "request.json", {
        "endpoint": endpoint + "/chat/completions",
        "model": model,
        "prompt": prompt(),
        "image_inputs": manifest["contact_sheets"],
        "response_format": request_payload["response_format"],
        "temperature": request_payload["temperature"],
        "max_tokens": request_payload["max_tokens"],
    })
    started = time.perf_counter()
    request = Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"content-type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=240) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        write_json(out_dir / "endpoint-error.json", {
            "http_status": exc.code,
            "reason": exc.reason,
            "body": error_body,
            "endpoint": endpoint.rstrip("/") + "/chat/completions",
            "model": model,
        })
        raise RuntimeError(f"Local VLM request failed with HTTP {exc.code}: {error_body}") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    write_json(out_dir / "raw-response.json", raw_response)
    content = raw_response.get("choices", [{}])[0].get("message", {}).get("content")
    parsed = parse_json_content(content)
    prediction = normalise_model_output(parsed, clip_id=clip_id, question_id="play-type-q1")
    write_json(out_dir / "prediction.json", prediction)
    receipt = {
        "schema_version": "playground-real-clip-vlm-receipt-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "endpoint_boundary": "Only the configured loopback OpenAI-compatible endpoint was contacted.",
        "model_requested": model,
        "model_reported": raw_response.get("model"),
        "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
        "response_format_sha256": hashlib.sha256(
            json.dumps(response_format, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "sampler_version": SAMPLER_VERSION,
        "sample_count": sample_count,
        "sheets": sheets,
        "max_tokens": max_tokens,
        "endpoint": endpoint,
        "elapsed_ms": elapsed_ms,
        "clip_id": clip_id,
        "clip_sha256": metadata["clip_sha256"],
        "source_reference": source_reference,
        "source_manifest_sha256": None if source_manifest is None else sha256_file(source_manifest),
        "input_manifest_sha256": sha256_file(out_dir / "input-manifest.json"),
        "request_sha256": sha256_file(out_dir / "request.json"),
        "prediction_sha256": sha256_file(out_dir / "prediction.json"),
        "performance_claim_allowed": False,
        "realDataExperimentResults": None,
        "interpretation": "A single unadjudicated real clip verifies LLM interface plumbing only; it is not an accuracy, grounding, latency, or model-comparison result.",
    }
    write_json(out_dir / "receipt.json", receipt)
    return {"prediction": prediction, "receipt": receipt, "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sample-count", type=int, default=12)
    parser.add_argument("--sheets", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=2400)
    args = parser.parse_args()
    result = run(
        video_path=args.video, clip_id=args.clip_id, out_dir=args.out,
        source_reference=args.source_reference, source_manifest=args.source_manifest,
        endpoint=args.endpoint, model=args.model, sample_count=args.sample_count, sheets=args.sheets,
        max_tokens=args.max_tokens,
    )
    print(json.dumps({"prediction": result["prediction"], "elapsed_ms": result["receipt"]["elapsed_ms"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
