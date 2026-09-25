"""Executable smoke harness for evidence-grounded short-play analysis.

This module deliberately uses a deterministic synthetic clip and a color/trajectory
baseline. It validates video I/O, temporal sampling, explicit evidence, metrics, and
receipts without pretending to measure real SoccerNet or VLM performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class EvidencePoint:
    timestamp_s: float
    x_norm: float
    y_norm: float
    frame_sha256: str


@dataclass(frozen=True)
class Prediction:
    answer: str
    confidence: float
    temporal_evidence_s: tuple[float, float]
    spatial_evidence: tuple[str, ...]
    trajectory: tuple[EvidencePoint, ...]
    abstained: bool = False
    abstention_reason: str | None = None


OUTPUT_SCHEMA_VERSION = "playground-output-v1"
ANNOTATION_SCHEMA_VERSION = "playground-annotations-v2"
FRAME_REVIEW_SCHEMA_VERSION = "playground-frame-review-v1"


def prediction_payload(prediction: Prediction, *, clip_id: str, question_id: str) -> dict:
    """Serialize a prediction under the frozen, model-agnostic v1 contract."""
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "clip_id": clip_id,
        "question_id": question_id,
        **asdict(prediction),
    }


def validate_prediction_payload(payload: object) -> list[str]:
    """Return deterministic structural and cross-field semantic errors.

    JSON Schema captures the portable shape in ``playground-output.schema.json``;
    this dependency-free validator additionally enforces abstention and evidence
    consistency that ordinary schema validation cannot express cleanly.
    """
    if not isinstance(payload, dict):
        return ["output must be a JSON object"]
    errors: list[str] = []
    required = {
        "schema_version", "clip_id", "question_id", "answer", "confidence",
        "temporal_evidence_s", "spatial_evidence", "trajectory", "abstained",
        "abstention_reason",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
        return errors
    if payload["schema_version"] != OUTPUT_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {OUTPUT_SCHEMA_VERSION}")
    for field in ("clip_id", "question_id", "answer"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            errors.append(f"{field} must be a non-empty string")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
        errors.append("confidence must be a finite number")
    elif not 0.0 <= confidence <= 1.0:
        errors.append("confidence must be between 0 and 1")
    abstained = payload["abstained"]
    if not isinstance(abstained, bool):
        errors.append("abstained must be boolean")
    reason = payload["abstention_reason"]
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        errors.append("abstention_reason must be null or a non-empty string")

    interval = payload["temporal_evidence_s"]
    valid_interval = (
        isinstance(interval, (list, tuple)) and len(interval) == 2
        and all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in interval)
    )
    if not valid_interval:
        errors.append("temporal_evidence_s must contain two finite numbers")
    elif interval[0] < 0 or interval[1] < interval[0]:
        errors.append("temporal_evidence_s must be non-negative and ordered")

    regions = payload["spatial_evidence"]
    if not isinstance(regions, (list, tuple)) or any(not isinstance(v, str) or not v.strip() for v in regions):
        errors.append("spatial_evidence must be an array of non-empty strings")
    trajectory = payload["trajectory"]
    if not isinstance(trajectory, (list, tuple)):
        errors.append("trajectory must be an array")
        trajectory = []
    last_timestamp = -math.inf
    for index, point in enumerate(trajectory):
        if not isinstance(point, dict):
            errors.append(f"trajectory[{index}] must be an object")
            continue
        if set(point) != {"timestamp_s", "x_norm", "y_norm", "frame_sha256"}:
            errors.append(f"trajectory[{index}] must contain exactly timestamp_s, x_norm, y_norm, frame_sha256")
            continue
        timestamp = point["timestamp_s"]
        coordinates = (point["x_norm"], point["y_norm"])
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
                or not math.isfinite(timestamp) or timestamp < 0):
            errors.append(f"trajectory[{index}].timestamp_s must be finite and non-negative")
        elif timestamp <= last_timestamp:
            errors.append("trajectory timestamps must be strictly increasing")
        else:
            last_timestamp = timestamp
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in coordinates):
            errors.append(f"trajectory[{index}] coordinates must be finite and normalized to [0,1]")
        digest = point["frame_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append(f"trajectory[{index}].frame_sha256 must be 64 lowercase hexadecimal characters")

    if abstained is True:
        if payload["answer"] != "insufficient_visual_evidence":
            errors.append("abstained output must use answer insufficient_visual_evidence")
        if confidence != 0.0:
            errors.append("abstained output must have confidence 0")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("abstained output must provide abstention_reason")
        if valid_interval and list(interval) != [0.0, 0.0]:
            errors.append("abstained output must use temporal_evidence_s [0,0]")
        if isinstance(regions, (list, tuple)) and len(regions) != 0:
            errors.append("abstained output must not claim spatial_evidence")
    elif abstained is False:
        if reason is not None:
            errors.append("non-abstained output must have null abstention_reason")
        if valid_interval and interval[1] <= interval[0]:
            errors.append("non-abstained output must cite a positive-duration temporal interval")
        if not trajectory and (not isinstance(regions, (list, tuple)) or not regions):
            errors.append("non-abstained output must cite trajectory or spatial evidence")
    return errors


def validate_annotation_export(payload: object, manifest: object, rubric: object) -> list[str]:
    """Validate annotation semantics and exact binding to a frozen manifest."""
    if not isinstance(payload, dict) or payload.get("schema_version") != ANNOTATION_SCHEMA_VERSION:
        return [f"export schema_version must equal {ANNOTATION_SCHEMA_VERSION}"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        return ["frozen manifest must contain an items array"]
    if not isinstance(rubric, dict) or rubric.get("schema_version") != "annotation-rubric-v2":
        return ["rubric schema_version must equal annotation-rubric-v2"]
    if not isinstance(payload.get("items"), list):
        return ["export must contain an items array"]
    errors: list[str] = []
    frozen = {(v.get("clip_id"), v.get("question_id")): v for v in manifest["items"] if isinstance(v, dict)}
    if len(frozen) != len(manifest["items"]):
        errors.append("frozen manifest contains malformed or duplicate items")
    seen: set[tuple[object, object]] = set()
    allowed_answerability = set(rubric.get("answerability", []))
    allowed_types = set(rubric.get("question_types", []))
    allowed_regions = set(rubric.get("pitch_regions", []))
    allowed_reasons = set(rubric.get("unanswerable_reason_codes", []))
    allowed_roles = set(rubric.get("evidence_entity_roles", []))
    trajectory_required = set(rubric.get("trajectory_required_for", []))
    validity_rubric = rubric.get("spatial_validity", {})
    validity_fields = {
        "camera_visibility": set(validity_rubric.get("camera_visibility", [])),
        "calibration_validity": set(validity_rubric.get("calibration_validity", [])),
        "ball_localization": set(validity_rubric.get("ball_localization", [])),
        "identity_resolution": set(validity_rubric.get("identity_resolution", [])),
    }
    allowed_spatial_failures = set(validity_rubric.get("failure_reason_codes", []))

    def finite(value: object) -> bool:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

    required = {"clip_id", "question_id", "clip_sha256", "duration_s", "question_type",
                "answerability", "canonical_answer", "accepted_aliases", "temporal_intervals",
                "spatial_regions", "trajectory", "trajectory_unavailable", "spatial_validity",
                "unanswerable_reason_code", "evidence_entities", "rationale_note"}
    for index, item in enumerate(payload["items"]):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required - item.keys())
        if missing:
            errors.append(f"{prefix} missing required fields: {', '.join(missing)}")
            continue
        key = (item["clip_id"], item["question_id"])
        if key in seen:
            errors.append(f"{prefix} duplicates clip/question key")
        seen.add(key)
        expected = frozen.get(key)
        if expected is None:
            errors.append(f"{prefix} has no exact frozen-manifest match")
        else:
            for field in ("clip_sha256", "duration_s"):
                if item[field] != expected.get(field):
                    errors.append(f"{prefix}.{field} does not match frozen manifest")
        digest, duration = item["clip_sha256"], item["duration_s"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append(f"{prefix}.clip_sha256 must be 64 lowercase hexadecimal characters")
        if not finite(duration) or duration <= 0:
            errors.append(f"{prefix}.duration_s must be finite and positive")
            duration = 0.0
        if item["question_type"] not in allowed_types:
            errors.append(f"{prefix}.question_type is not in the rubric")
        answerability = item["answerability"]
        if answerability not in allowed_answerability:
            errors.append(f"{prefix}.answerability is not in the rubric")
        aliases, intervals = item["accepted_aliases"], item["temporal_intervals"]
        regions, trajectory, entities = item["spatial_regions"], item["trajectory"], item["evidence_entities"]
        if not isinstance(aliases, list) or any(not isinstance(v, str) or not v.strip() for v in aliases):
            errors.append(f"{prefix}.accepted_aliases must contain only non-empty strings")
        if not isinstance(regions, list) or any(v not in allowed_regions for v in regions):
            errors.append(f"{prefix}.spatial_regions contains a value outside the rubric")
        if not isinstance(entities, list) or any(v not in allowed_roles for v in entities):
            errors.append(f"{prefix}.evidence_entities contains a value outside the rubric")
        if not isinstance(intervals, list):
            errors.append(f"{prefix}.temporal_intervals must be an array")
            intervals = []
        previous_end = -math.inf
        for j, interval in enumerate(intervals):
            valid = isinstance(interval, list) and len(interval) == 2 and all(finite(v) for v in interval)
            if not valid or interval[0] < 0 or interval[1] <= interval[0] or interval[1] > duration:
                errors.append(f"{prefix}.temporal_intervals[{j}] must be positive, ordered, and within duration")
            elif interval[0] < previous_end:
                errors.append(f"{prefix}.temporal_intervals must be ordered and non-overlapping")
            else:
                previous_end = interval[1]
        if not isinstance(trajectory, list):
            errors.append(f"{prefix}.trajectory must be an array")
            trajectory = []
        previous_t = -math.inf
        for j, point in enumerate(trajectory):
            valid = (isinstance(point, dict) and set(point) == {"timestamp_s", "x_norm", "y_norm"}
                     and all(finite(point.get(v)) for v in ("timestamp_s", "x_norm", "y_norm")))
            if not valid:
                errors.append(f"{prefix}.trajectory[{j}] must contain exactly three finite numeric fields")
                continue
            if not 0 <= point["timestamp_s"] <= duration or point["timestamp_s"] <= previous_t:
                errors.append(f"{prefix}.trajectory timestamps must strictly increase within duration")
            previous_t = point["timestamp_s"]
            if not 0 <= point["x_norm"] <= 1 or not 0 <= point["y_norm"] <= 1:
                errors.append(f"{prefix}.trajectory[{j}] coordinates must be normalized to [0,1]")
        unavailable, reason = item["trajectory_unavailable"], item["unanswerable_reason_code"]
        if not isinstance(unavailable, bool):
            errors.append(f"{prefix}.trajectory_unavailable must be boolean")
        validity = item["spatial_validity"]
        required_validity = {"spatial_evidence_usable", *validity_fields, "failure_reason_codes"}
        if not isinstance(validity, dict) or set(validity) != required_validity:
            errors.append(f"{prefix}.spatial_validity must contain exactly the rubric validity fields")
        else:
            usable, failures = validity["spatial_evidence_usable"], validity["failure_reason_codes"]
            if not isinstance(usable, bool):
                errors.append(f"{prefix}.spatial_validity.spatial_evidence_usable must be boolean")
            for field, allowed in validity_fields.items():
                if validity[field] not in allowed:
                    errors.append(f"{prefix}.spatial_validity.{field} is not in the rubric")
            if not isinstance(failures, list):
                errors.append(f"{prefix}.spatial_validity.failure_reason_codes must be unique rubric values")
                failures = []
            elif len(set(failures)) != len(failures) or any(
                    value not in allowed_spatial_failures for value in failures):
                errors.append(f"{prefix}.spatial_validity.failure_reason_codes must be unique rubric values")
                failures = []
            expected = {
                ("camera_visibility", "partially_out_of_view"): "camera_partially_out_of_view",
                ("camera_visibility", "out_of_view"): "camera_out_of_view",
                ("calibration_validity", "insufficient_pitch_lines"): "insufficient_pitch_lines",
                ("calibration_validity", "failed"): "calibration_failed",
                ("ball_localization", "unsupported_airborne_3d"): "unsupported_airborne_ball_3d",
                ("identity_resolution", "unresolved"): "unresolved_identity",
            }
            for (field, state), failure in expected.items():
                if validity[field] == state and failure not in failures:
                    errors.append(f"{prefix}.spatial_validity state {state} requires failure reason {failure}")
            has_spatial = bool(regions or trajectory)
            if usable is True:
                if failures:
                    errors.append(f"{prefix} usable spatial evidence must not carry failure reasons")
                if has_spatial and (validity["camera_visibility"] != "in_view" or validity["calibration_validity"] != "valid"):
                    errors.append(f"{prefix} positive spatial evidence requires in-view camera and valid calibration")
            elif usable is False:
                if not failures:
                    errors.append(f"{prefix} unusable spatial evidence must provide a failure reason")
                if has_spatial:
                    errors.append(f"{prefix} unusable spatial evidence must not contain regions or trajectory")
            if has_spatial and usable is not True:
                errors.append(f"{prefix} positive spatial evidence requires spatial_evidence_usable=true")
        if answerability == "answerable":
            if not isinstance(item["canonical_answer"], str) or not item["canonical_answer"].strip():
                errors.append(f"{prefix} answerable item must have a canonical_answer")
            if not intervals:
                errors.append(f"{prefix} answerable item must have temporal evidence")
            if reason is not None:
                errors.append(f"{prefix} answerable item must not have an unanswerable_reason_code")
            if item["question_type"] in trajectory_required and not trajectory and unavailable is not True:
                errors.append(f"{prefix} required trajectory must be present or explicitly unavailable")
            if trajectory and unavailable is True:
                errors.append(f"{prefix} cannot contain a trajectory and mark it unavailable")
        elif answerability in {"insufficient_visual_evidence", "invalid_question"}:
            if bool(item["canonical_answer"] or aliases or intervals or regions or trajectory or entities):
                errors.append(f"{prefix} unanswerable/invalid item must not contain positive answer or evidence")
            if reason not in allowed_reasons:
                errors.append(f"{prefix} unanswerable/invalid item must have a rubric reason code")
        if not isinstance(item["rationale_note"], str) or not item["rationale_note"].strip():
            errors.append(f"{prefix}.rationale_note must be a non-empty string")
    for key in sorted(set(frozen) - seen):
        errors.append(f"frozen-manifest item missing from export: {key!r}")
    return errors


def validate_frame_review(worksheet: object, annotation_export: object, manifest: object) -> list[str]:
    """Validate a frame-review worksheet and fail metric eligibility closed.

    The gate verifies provenance and review receipts; it does not decide whether a
    reviewer's visual judgment is correct. Metric eligibility requires an independent
    reviewer, tight frame boundaries, auditable calibration, six passed quality
    checks, a second annotator, and an adjudicator.
    """
    if not isinstance(worksheet, dict) or worksheet.get("schema_version") != FRAME_REVIEW_SCHEMA_VERSION:
        return [f"worksheet schema_version must equal {FRAME_REVIEW_SCHEMA_VERSION}"]
    if not isinstance(annotation_export, dict) or not isinstance(annotation_export.get("items"), list):
        return ["annotation export must contain an items array"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        return ["annotation manifest must contain an items array"]
    errors: list[str] = []
    key = (worksheet.get("clip_id"), worksheet.get("question_id"))
    annotations = {(v.get("clip_id"), v.get("question_id")): v
                   for v in annotation_export["items"] if isinstance(v, dict)}
    frozen = {(v.get("clip_id"), v.get("question_id")): v
              for v in manifest["items"] if isinstance(v, dict)}
    annotation, frozen_item = annotations.get(key), frozen.get(key)
    if annotation is None or frozen_item is None:
        return ["worksheet must have an exact annotation and manifest item match"]
    for field in ("clip_sha256", "duration_s"):
        if worksheet.get(field) != annotation.get(field) or worksheet.get(field) != frozen_item.get(field):
            errors.append(f"worksheet.{field} must match annotation and manifest")

    video = worksheet.get("video_metadata")
    if not isinstance(video, dict):
        errors.append("video_metadata must be an object")
        video = {}
    fps_num, fps_den = video.get("fps_numerator"), video.get("fps_denominator")
    frame_count = video.get("decoded_frame_count")
    if (isinstance(fps_num, bool) or not isinstance(fps_num, int) or fps_num <= 0
            or isinstance(fps_den, bool) or not isinstance(fps_den, int) or fps_den <= 0):
        errors.append("video_metadata fps numerator and denominator must be positive integers")
        fps = None
    else:
        fps = fps_num / fps_den
    if isinstance(frame_count, bool) or not isinstance(frame_count, int) or frame_count <= 0:
        errors.append("video_metadata.decoded_frame_count must be a positive integer")
        frame_count = 0

    frames = worksheet.get("reviewed_frames")
    if not isinstance(frames, list) or not frames:
        errors.append("reviewed_frames must be a non-empty array")
        frames = []
    frame_by_index: dict[int, dict] = {}
    for index, frame in enumerate(frames):
        prefix = f"reviewed_frames[{index}]"
        if not isinstance(frame, dict):
            errors.append(f"{prefix} must be an object")
            continue
        frame_index, timestamp = frame.get("frame_index"), frame.get("timestamp_s")
        digest = frame.get("decoded_frame_sha256")
        if (isinstance(frame_index, bool) or not isinstance(frame_index, int)
                or frame_index < 0 or frame_index >= frame_count):
            errors.append(f"{prefix}.frame_index must be within decoded frame range")
        elif frame_index in frame_by_index:
            errors.append(f"{prefix}.frame_index must be unique")
        else:
            frame_by_index[frame_index] = frame
        if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
                or not math.isfinite(timestamp) or timestamp < 0
                or timestamp >= float(worksheet.get("duration_s", 0))):
            errors.append(f"{prefix}.timestamp_s must be finite and within clip duration")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            errors.append(f"{prefix}.decoded_frame_sha256 must be 64 lowercase hexadecimal characters")

    review = worksheet.get("independent_review")
    if not isinstance(review, dict):
        errors.append("independent_review must be an object")
        review = {}
    draft_author, reviewer = review.get("draft_author_id"), review.get("reviewer_id")
    independent = (isinstance(draft_author, str) and bool(draft_author.strip())
                   and isinstance(reviewer, str) and bool(reviewer.strip()) and reviewer != draft_author)
    if reviewer is not None and not independent:
        errors.append("reviewer_id must be non-empty and differ from draft_author_id")

    boundary = worksheet.get("temporal_boundary_review")
    if not isinstance(boundary, dict):
        errors.append("temporal_boundary_review must be an object")
        boundary = {}
    tight = boundary.get("tight_boundaries_confirmed") is True
    start_index, end_index = boundary.get("start_frame_index"), boundary.get("end_frame_index")
    if tight:
        if not independent:
            errors.append("tight boundaries require an independent reviewer")
        # Intervals are half open: start is the first included frame and end is
        # an exclusive boundary position. End may therefore equal frame_count.
        valid_end = (isinstance(end_index, int) and not isinstance(end_index, bool)
                     and isinstance(start_index, int) and not isinstance(start_index, bool)
                     and start_index < end_index <= frame_count)
        if start_index not in frame_by_index or not valid_end or end_index - 1 not in frame_by_index:
            errors.append("tight boundaries require a reviewed start frame and reviewed frame before an ordered end-exclusive boundary")
        else:
            intervals = annotation.get("temporal_intervals", [])
            start_timestamp = float(frame_by_index[start_index]["timestamp_s"])
            end_timestamp = (float(worksheet["duration_s"]) if end_index == frame_count
                             else float(frame_by_index[end_index]["timestamp_s"]))
            expected = [start_timestamp, end_timestamp]
            if (len(intervals) != 1 or len(intervals[0]) != 2
                    or any(abs(float(a) - float(b)) > 1e-6 for a, b in zip(intervals[0], expected))):
                errors.append("annotation temporal interval must match confirmed half-open boundary timestamps")
    elif start_index is not None or end_index is not None:
        errors.append("unconfirmed boundaries must use null start/end frame indices")

    calibration = worksheet.get("calibration_review")
    if not isinstance(calibration, dict):
        errors.append("calibration_review must be an object")
        calibration = {}
    calibration_valid = calibration.get("status") == "valid"
    if calibration_valid:
        digest = calibration.get("evidence_artifact_sha256")
        support = calibration.get("supporting_frame_indices")
        if not independent:
            errors.append("valid calibration requires an independent reviewer")
        if not isinstance(calibration.get("method"), str) or not calibration["method"].strip():
            errors.append("valid calibration requires a method")
        if not isinstance(support, list) or not support or any(v not in frame_by_index for v in support):
            errors.append("valid calibration requires supporting reviewed frame indices")
        count = calibration.get("correspondence_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 4:
            errors.append("valid calibration requires at least four correspondences")
        for field in ("mean_reprojection_error_px", "max_reprojection_error_px"):
            value = calibration.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                errors.append(f"valid calibration requires finite non-negative {field}")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            errors.append("valid calibration requires an evidence artifact SHA-256")

    checks = worksheet.get("item_quality_checks")
    required_checks = {"answer_supported", "play_specific", "visual_evidence_sufficient",
                       "no_absent_event", "no_answer_leakage", "unique_unambiguous_answer"}
    if not isinstance(checks, dict) or set(checks) != required_checks:
        errors.append("item_quality_checks must contain exactly the six protocol checks")
        checks_pass = False
    else:
        allowed = {"passed", "failed", "not_reviewed"}
        if any(value not in allowed for value in checks.values()):
            errors.append("item_quality_checks values must be passed, failed, or not_reviewed")
        checks_pass = all(value == "passed" for value in checks.values())

    governance = worksheet.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
        governance = {}
    roles_named = all(isinstance(v, str) and bool(v.strip()) for v in
                      (governance.get("second_annotator_id"), governance.get("adjudicator_id")))
    derived_eligible = bool(independent and tight and calibration_valid and checks_pass and roles_named)
    declared = worksheet.get("eligible_for_metrics")
    if not isinstance(declared, bool):
        errors.append("eligible_for_metrics must be boolean")
    elif declared != derived_eligible:
        errors.append(f"eligible_for_metrics must equal derived gate result {str(derived_eligible).lower()}")
    manifest_declared = manifest.get("review_gate", {}).get("eligible_for_metrics")
    if manifest_declared != derived_eligible:
        errors.append(f"manifest review_gate.eligible_for_metrics must equal derived gate result {str(derived_eligible).lower()}")
    return errors


def generate_frame_review_packet(video_path: Path, worksheet_path: Path, out_dir: Path,
                                 *, frames_per_page: int = 24) -> dict:
    """Render every decoded frame into hash-bound reviewer contact sheets.

    This prepares human review material only. It neither fills the worksheet nor
    makes a visual, calibration, independence, or metric-eligibility judgment.
    """
    if frames_per_page <= 0:
        raise ValueError("frames_per_page must be positive")
    worksheet = json.loads(worksheet_path.read_text(encoding="utf-8"))
    if worksheet.get("schema_version") != FRAME_REVIEW_SCHEMA_VERSION:
        raise ValueError(f"worksheet schema_version must equal {FRAME_REVIEW_SCHEMA_VERSION}")
    clip_digest = hashlib.sha256(video_path.read_bytes()).hexdigest()
    if clip_digest != worksheet.get("clip_sha256"):
        raise ValueError("video SHA-256 does not match worksheet")
    metadata = worksheet.get("video_metadata", {})
    fps_num, fps_den = metadata.get("fps_numerator"), metadata.get("fps_denominator")
    expected_count = metadata.get("decoded_frame_count")
    if not all(isinstance(v, int) and not isinstance(v, bool) and v > 0
               for v in (fps_num, fps_den, expected_count)):
        raise ValueError("worksheet must contain positive rational FPS and decoded frame count")
    fps = fps_num / fps_den
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    frames: list[np.ndarray] = []
    frame_records: list[dict] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        index = len(frames)
        timestamp_s = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        frames.append(frame)
        frame_records.append({
            "frame_index": index,
            "timestamp_s": timestamp_s,
            "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
        })
    cap.release()
    if len(frames) != expected_count:
        raise RuntimeError(f"decoded {len(frames)} frames; worksheet expects {expected_count}")

    out_dir.mkdir(parents=True, exist_ok=True)
    columns = 6
    rows = math.ceil(frames_per_page / columns)
    thumb_width, thumb_height, label_height = 213, 120, 30
    page_records: list[dict] = []
    for page_number, first in enumerate(range(0, len(frames), frames_per_page), start=1):
        last = min(first + frames_per_page, len(frames))
        canvas = np.full((rows * (thumb_height + label_height), columns * thumb_width, 3), 255, np.uint8)
        for slot, frame_index in enumerate(range(first, last)):
            row, column = divmod(slot, columns)
            x, y = column * thumb_width, row * (thumb_height + label_height)
            thumb = cv2.resize(frames[frame_index], (thumb_width, thumb_height), interpolation=cv2.INTER_AREA)
            canvas[y:y + thumb_height, x:x + thumb_width] = thumb
            label = f"f={frame_index:03d}  pts={frame_records[frame_index]['timestamp_s']:.6f}s"
            cv2.putText(canvas, label, (x + 5, y + thumb_height + 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.43, (0, 0, 0), 1, cv2.LINE_AA)
        name = f"contact-sheet-{first:03d}-{last - 1:03d}.png"
        path = out_dir / name
        if not cv2.imwrite(str(path), canvas):
            raise RuntimeError(f"could not write contact sheet: {path}")
        page_records.append({
            "page": page_number, "path": name, "first_frame_index": first,
            "last_frame_index": last - 1,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    packet = {
        "schema_version": "playground-frame-review-packet-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "Reviewer preparation only; no human visual, temporal, spatial, calibration, reliability, or model claim.",
        "clip_id": worksheet.get("clip_id"), "question_id": worksheet.get("question_id"),
        "clip_sha256": clip_digest,
        "worksheet_sha256": hashlib.sha256(worksheet_path.read_bytes()).hexdigest(),
        "fps_numerator": fps_num, "fps_denominator": fps_den,
        "decoded_frame_count": len(frames),
        "end_exclusive_boundary_index": len(frames),
        "end_exclusive_boundary_timestamp_s": float(worksheet["duration_s"]),
        "frames_per_page": frames_per_page, "pages": page_records, "frames": frame_records,
    }
    _write_json(out_dir / "frame-index.json", packet)
    instructions = f"""# Independent frame-review packet — {worksheet.get('clip_id')}

**Question:** Which type of restart leads to the goal in this clip?  
**Scope:** Human-review preparation only. Opening these sheets does not approve the draft annotation.

## Identity
- Clip SHA-256: `{clip_digest}`
- Worksheet SHA-256: `{packet['worksheet_sha256']}`
- Sequentially decoded frames: `{len(frames)}`; nominal rate `{fps_num}/{fps_den}` fps
- Sheets: `{len(page_records)}`; every decoded frame appears exactly once and is indexed in `frame-index.json`.
- Use the decoded PTS in `frame-index.json`; do not infer timestamps as `frame_index/fps`.

## Boundary convention
Record a half-open interval `[start_frame_index, end_frame_index)`. The start is the first included frame. The end is the first excluded frame, so it may equal `{len(frames)}` at the clip boundary `{float(worksheet['duration_s']):.6f}` seconds; then frame `{len(frames) - 1}` is the final included visual frame. For an internal end boundary, use that first-excluded frame's decoded PTS. Review the start frame and the frame immediately before the end boundary.

## Independent reviewer procedure
1. Verify the clip and worksheet hashes above before review.
2. Inspect all sheets in order, then inspect the source clip for motion/context.
3. Decide whether the video itself uniquely supports the answer, without relying on the filename, source description, or this draft's answer.
4. Mark each of the six worksheet quality checks independently. Reject or revise on any failed check.
5. If visually answerable, choose the tight first included frame and end-exclusive boundary. Add the start frame and frame before the end boundary, with hashes from `frame-index.json`, to `reviewed_frames`.
6. Do not mark calibration `valid` from contact sheets alone. A separate hash-bound calibration artifact, correspondences, and reprojection errors are required.
7. Sign only with a reviewer ID distinct from `durable-loop-agent`; do not fill other roles unless they actually performed their work.

## Six quality checks
- `answer_supported`: approved visual/source basis supports the answer.
- `play_specific`: not answerable from commonsense alone.
- `visual_evidence_sufficient`: decisive evidence is visible.
- `no_absent_event`: no unsupported event is introduced.
- `no_answer_leakage`: wording/options do not reveal the answer.
- `unique_unambiguous_answer`: one supported answer; not ill-posed or weakly grounded.

Decoded-pixel hashes are decoder-specific audit aids. The clip SHA-256 is the canonical media identity.
"""
    (out_dir / "REVIEW_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    receipt = {
        key: packet[key] for key in (
            "schema_version", "created_at", "claim_boundary", "clip_id", "question_id",
            "clip_sha256", "worksheet_sha256", "decoded_frame_count",
            "end_exclusive_boundary_index", "end_exclusive_boundary_timestamp_s", "frames_per_page")
    }
    receipt.update({
        "page_count": len(page_records),
        "frame_index_sha256": hashlib.sha256((out_dir / "frame-index.json").read_bytes()).hexdigest(),
        "instructions_sha256": hashlib.sha256((out_dir / "REVIEW_INSTRUCTIONS.md").read_bytes()).hexdigest(),
        "page_sha256": {page["path"]: page["sha256"] for page in page_records},
    })
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_synthetic_clip(out_dir: Path, *, fps: int = 15, seconds: int = 8) -> tuple[Path, Path]:
    """Generate a left-corner-to-box play and machine-readable ground truth."""
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / "left_corner_cross.mp4"
    gt_path = out_dir / "ground_truth.json"
    width, height = 640, 360
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open an MP4 writer")

    total = fps * seconds
    for index in range(total):
        t = index / max(total - 1, 1)
        frame = np.full((height, width, 3), (42, 122, 42), dtype=np.uint8)
        # Pitch markings.
        cv2.rectangle(frame, (20, 20), (620, 340), (240, 240, 240), 2)
        cv2.line(frame, (320, 20), (320, 340), (240, 240, 240), 2)
        cv2.circle(frame, (320, 180), 45, (240, 240, 240), 2)
        cv2.rectangle(frame, (500, 95), (620, 265), (240, 240, 240), 2)
        # Players: fixed, high-contrast markers; no text label leakage.
        for point in [(90, 300), (365, 205), (470, 160)]:
            cv2.circle(frame, point, 9, (20, 20, 230), -1)  # red team (BGR)
        for point in [(410, 150), (500, 210), (535, 125)]:
            cv2.circle(frame, point, 9, (230, 70, 30), -1)  # blue team
        # A curved yellow-ball trajectory: left corner toward penalty area.
        x = int(42 + 475 * t)
        y = int(315 - 155 * t - 65 * math.sin(math.pi * t))
        cv2.circle(frame, (x, y), 7, (0, 255, 255), -1)
        writer.write(frame)
    writer.release()

    ground_truth = {
        "clip_id": "synthetic-left-corner-cross-v1",
        "question": "Which restart and progression are shown?",
        "answer": "left_corner_cross_into_penalty_area",
        "temporal_evidence_s": [0.0, float(seconds)],
        "spatial_evidence": ["left-corner", "penalty-area"],
        "synthetic": True,
        "purpose": "pipeline smoke test only",
        "fps": fps,
        "duration_s": seconds,
    }
    _write_json(gt_path, ground_truth)
    return video_path, gt_path


def sample_frames(video_path: Path, *, count: int = 12) -> list[tuple[float, np.ndarray, str]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if frame_count <= 0 or fps <= 0:
        raise RuntimeError("Video metadata is invalid")
    indices = np.linspace(0, frame_count - 1, num=min(count, frame_count), dtype=int)
    samples: list[tuple[float, np.ndarray, str]] = []
    for index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read frame {index}")
        digest = hashlib.sha256(frame.tobytes()).hexdigest()
        samples.append((float(index) / fps, frame, digest))
    cap.release()
    return samples


def _detect_yellow_ball(frame: np.ndarray) -> tuple[float, float] | None:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([20, 130, 130]), np.array([42, 255, 255]))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 10:
        return None
    moments = cv2.moments(contour)
    if moments["m00"] == 0:
        return None
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def trajectory_baseline(video_path: Path) -> Prediction:
    samples = sample_frames(video_path)
    points: list[EvidencePoint] = []
    for timestamp, frame, digest in samples:
        detected = _detect_yellow_ball(frame)
        if detected is None:
            continue
        x, y = detected
        height, width = frame.shape[:2]
        points.append(EvidencePoint(timestamp, x / width, y / height, digest))
    return prediction_from_trajectory(points)


def prediction_from_trajectory(
    points: Iterable[EvidencePoint], *, validity_gate: bool = False
) -> Prediction:
    """Reason over a tool trajectory, optionally rejecting invalid/unsupported evidence.

    ``validity_gate=False`` preserves the iteration-003 count-only baseline. The
    gated policy rejects reversed timestamps, invalid normalized coordinates, and
    endpoint patterns outside the one play class this toy classifier supports.
    """
    points = list(points)
    if len(points) < 3:
        return Prediction(
            answer="insufficient_visual_evidence",
            confidence=0.0,
            temporal_evidence_s=(0.0, 0.0),
            spatial_evidence=(),
            trajectory=tuple(points),
            abstained=True,
            abstention_reason="fewer than three ball detections",
        )
    if validity_gate:
        if any(
            not math.isfinite(value) or not 0.0 <= value <= 1.0
            for point in points
            for value in (point.x_norm, point.y_norm)
        ):
            return _abstain(points, "trajectory contains invalid normalized coordinates")
        if any(right.timestamp_s <= left.timestamp_s for left, right in zip(points, points[1:])):
            return _abstain(points, "trajectory timestamps are not strictly increasing")
    start, end = points[0], points[-1]
    is_left_corner = start.x_norm < 0.15 and start.y_norm > 0.75
    reaches_box = end.x_norm > 0.70 and 0.25 < end.y_norm < 0.75
    if is_left_corner and reaches_box:
        answer = "left_corner_cross_into_penalty_area"
        regions = ("left-corner", "penalty-area")
        confidence = min(0.99, 0.65 + 0.03 * len(points))
    else:
        if validity_gate:
            return _abstain(points, "trajectory endpoints do not support a known play label")
        answer = "other_progression"
        regions = ()
        confidence = 0.55
    return Prediction(
        answer=answer,
        confidence=confidence,
        temporal_evidence_s=(start.timestamp_s, end.timestamp_s),
        spatial_evidence=regions,
        trajectory=tuple(points),
    )


def _abstain(points: list[EvidencePoint], reason: str) -> Prediction:
    return Prediction(
        answer="insufficient_visual_evidence",
        confidence=0.0,
        temporal_evidence_s=(0.0, 0.0),
        spatial_evidence=(),
        trajectory=tuple(points),
        abstained=True,
        abstention_reason=reason,
    )


def run_severity_experiment(out_dir: Path) -> dict:
    """Compare count-only and validity-gated policies over deterministic x shifts."""
    video_path, gt_path = generate_synthetic_clip(out_dir)
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))
    clean_points = list(trajectory_baseline(video_path).trajectory)
    severities = [round(step * 0.05, 2) for step in range(9)]
    policies = {"count_only": False, "validity_gated": True}
    rows: list[dict] = []
    summaries: dict[str, dict] = {}
    for policy, gated in policies.items():
        covered = 0
        covered_errors = 0
        for severity in severities:
            shifted = [
                EvidencePoint(
                    p.timestamp_s,
                    float(np.clip(p.x_norm + severity, 0.0, 1.0)),
                    p.y_norm,
                    p.frame_sha256,
                )
                for p in clean_points
            ]
            prediction = prediction_from_trajectory(shifted, validity_gate=gated)
            correct = prediction.answer == ground_truth["answer"]
            if not prediction.abstained:
                covered += 1
                covered_errors += int(not correct)
            rows.append(
                {
                    "policy": policy,
                    "x_shift": severity,
                    "answer": prediction.answer,
                    "correct": correct,
                    "abstained": prediction.abstained,
                    "abstention_reason": prediction.abstention_reason,
                }
            )
        summaries[policy] = {
            "items": len(severities),
            "covered": covered,
            "coverage": covered / len(severities),
            "covered_errors": covered_errors,
            "selective_risk": covered_errors / covered if covered else None,
        }
    payload = {
        "evidence_class": "deterministic synthetic post-detection fault injection",
        "severities": severities,
        "policies": summaries,
        "rows": rows,
        "warning": "Toy single-class rule baseline; not VLM or real-soccer performance.",
    }
    results_path = out_dir / "severity_results.json"
    _write_json(results_path, payload)
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": "python prototype/sports_play_lab.py severity --out " + str(out_dir),
        "python": sys.version,
        "opencv": cv2.__version__,
        "fault_boundary": "post-detection x-coordinate shifts",
        "results_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
        "policies": summaries,
        "artifacts": [str(video_path), str(gt_path), str(results_path)],
        "warning": payload["warning"],
    }
    _write_json(out_dir / "severity_receipt.json", receipt)
    return receipt


def run_corruption_experiment(out_dir: Path, *, seed: int = 7) -> dict:
    """Measure deterministic propagation from corrupted tool evidence to the answer.

    This is a synthetic fault-injection experiment, not a robustness claim about a VLM
    or real soccer. Corruptions are applied after visual detection to isolate the
    structured trajectory-to-answer boundary.
    """
    video_path, gt_path = generate_synthetic_clip(out_dir)
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))
    clean = trajectory_baseline(video_path)
    points = list(clean.trajectory)
    rng = np.random.default_rng(seed)

    shifted = [
        EvidencePoint(
            p.timestamp_s,
            float(np.clip(p.x_norm + rng.normal(0.30, 0.01), 0.0, 1.0)),
            p.y_norm,
            p.frame_sha256,
        )
        for p in points
    ]
    scenarios = {
        "clean": points,
        "drop_to_two_detections": points[:2],
        "reverse_temporal_order": list(reversed(points)),
        "systematic_x_shift": shifted,
    }
    results: dict[str, dict] = {}
    for name, scenario_points in scenarios.items():
        prediction = prediction_from_trajectory(scenario_points)
        metrics = evaluate(prediction, ground_truth)
        results[name] = {
            "corruption_applied": name != "clean",
            "prediction": asdict(prediction),
            "metrics": metrics,
            "wrong_non_abstained_answer": bool(
                not prediction.abstained and metrics["answer_exact_match"] == 0.0
            ),
        }

    summary = {
        "scenario_count": len(results),
        "corrupted_scenario_count": len(results) - 1,
        "corrupted_wrong_non_abstained_count": sum(
            int(v["wrong_non_abstained_answer"])
            for k, v in results.items()
            if k != "clean"
        ),
        "corrupted_abstention_count": sum(
            int(v["prediction"]["abstained"])
            for k, v in results.items()
            if k != "clean"
        ),
        "warning": "Deterministic synthetic fault injection; not VLM or real-soccer performance.",
    }
    _write_json(out_dir / "corruption_results.json", {"seed": seed, "summary": summary, "scenarios": results})
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": "python prototype/sports_play_lab.py corruption --out " + str(out_dir) + f" --seed {seed}",
        "seed": seed,
        "python": sys.version,
        "opencv": cv2.__version__,
        "video_sha256": hashlib.sha256(video_path.read_bytes()).hexdigest(),
        "fault_boundary": "post-detection structured trajectory input",
        "summary": summary,
        "artifacts": [str(gt_path), str(video_path), str(out_dir / "corruption_results.json")],
    }
    _write_json(out_dir / "corruption_receipt.json", receipt)
    return receipt


def _f1(predicted: Iterable[str], expected: Iterable[str]) -> float:
    p, e = set(predicted), set(expected)
    if not p and not e:
        return 1.0
    if not p or not e:
        return 0.0
    precision, recall = len(p & e) / len(p), len(p & e) / len(e)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _interval_iou(predicted: Iterable[float], expected: Iterable[float]) -> float:
    ps, pe = map(float, predicted)
    es, ee = map(float, expected)
    intersection = max(0.0, min(pe, ee) - max(ps, es))
    union = max(pe, ee) - min(ps, es)
    return intersection / union if union > 0 else 0.0


def _trajectory_recall(
    predicted: Iterable[dict], expected: Iterable[dict], *, time_tolerance_s: float, distance_tolerance: float
) -> float:
    """Fraction of gold points having a prediction within temporal/spatial tolerance."""
    predicted, expected = list(predicted), list(expected)
    if not expected:
        return 1.0
    matches = 0
    for gold in expected:
        if any(
            abs(float(point["timestamp_s"]) - float(gold["timestamp_s"])) <= time_tolerance_s
            and math.hypot(float(point["x_norm"]) - float(gold["x_norm"]),
                           float(point["y_norm"]) - float(gold["y_norm"])) <= distance_tolerance
            for point in predicted
        ):
            matches += 1
    return matches / len(expected)


def _cohen_kappa(left: list[str], right: list[str]) -> tuple[float, float | None]:
    """Return observed agreement and unweighted Cohen's kappa.

    Kappa is undefined when both annotators use one identical category, because
    expected agreement is one. We preserve that case as ``None`` rather than
    reporting a misleading perfect chance-corrected score.
    """
    if len(left) != len(right) or not left:
        raise ValueError("kappa inputs must have the same positive length")
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    categories = set(left) | set(right)
    expected = sum(
        (left.count(category) / len(left)) * (right.count(category) / len(right))
        for category in categories
    )
    return observed, None if expected == 1.0 else (observed - expected) / (1.0 - expected)


def _trajectory_displacement(left: Iterable[dict], right: Iterable[dict], *, samples: int = 20) -> dict | None:
    """Interpolate two annotation trajectories over shared time and compare them."""
    left, right = list(left), list(right)
    if not left or not right or samples < 2:
        return None
    start = max(float(left[0]["timestamp_s"]), float(right[0]["timestamp_s"]))
    end = min(float(left[-1]["timestamp_s"]), float(right[-1]["timestamp_s"]))
    if end <= start:
        return None

    def interpolate(points: list[dict], timestamp: float) -> tuple[float, float]:
        for first, second in zip(points, points[1:]):
            t0, t1 = float(first["timestamp_s"]), float(second["timestamp_s"])
            if t0 <= timestamp <= t1:
                weight = (timestamp - t0) / (t1 - t0) if t1 > t0 else 0.0
                return (
                    float(first["x_norm"]) + weight * (float(second["x_norm"]) - float(first["x_norm"])),
                    float(first["y_norm"]) + weight * (float(second["y_norm"]) - float(first["y_norm"])),
                )
        point = points[0] if timestamp <= float(points[0]["timestamp_s"]) else points[-1]
        return float(point["x_norm"]), float(point["y_norm"])

    timestamps = np.linspace(start, end, samples)
    distances = []
    for timestamp in timestamps:
        lx, ly = interpolate(left, float(timestamp))
        rx, ry = interpolate(right, float(timestamp))
        distances.append(math.hypot(lx - rx, ly - ry))
    return {"overlap_s": end - start, "sample_count": samples,
            "normalized_ade": sum(distances) / len(distances), "normalized_fde": distances[-1]}


def annotation_agreement(left: Iterable[dict], right: Iterable[dict]) -> dict:
    """Compute pre-adjudication agreement for two locked annotation exports.

    This is dataset-free metric plumbing. Empty/empty region sets are excluded,
    and answer/evidence comparisons require both annotators to mark an item
    answerable. No synthetic value produced here is human reliability evidence.
    """
    left, right = list(left), list(right)
    left_by_key = {(v["clip_id"], v["question_id"]): v for v in left}
    right_by_key = {(v["clip_id"], v["question_id"]): v for v in right}
    if len(left_by_key) != len(left) or len(right_by_key) != len(right):
        raise ValueError("duplicate clip/question key")
    if set(left_by_key) != set(right_by_key) or not left_by_key:
        raise ValueError("annotation keys must match exactly and be non-empty")

    keys = sorted(left_by_key)
    left_labels = [left_by_key[key]["answerability"] for key in keys]
    right_labels = [right_by_key[key]["answerability"] for key in keys]
    observed, kappa = _cohen_kappa(left_labels, right_labels)
    rows, answer_hits, temporal_ious, region_f1s = [], [], [], []
    availability_hits, trajectory_distances = [], []
    for key in keys:
        a, b = left_by_key[key], right_by_key[key]
        both_answerable = a["answerability"] == b["answerability"] == "answerable"
        row = {"clip_id": key[0], "question_id": key[1],
               "answerability_agree": a["answerability"] == b["answerability"]}
        if both_answerable:
            answers_a = {str(a.get("canonical_answer", "")).strip().casefold(),
                         *(str(v).strip().casefold() for v in a.get("accepted_aliases", []))}
            answers_b = {str(b.get("canonical_answer", "")).strip().casefold(),
                         *(str(v).strip().casefold() for v in b.get("accepted_aliases", []))}
            answers_a.discard("")
            answers_b.discard("")
            answer_hit = bool(answers_a & answers_b)
            temporal_iou = max(
                (_interval_iou(x, y) for x in a.get("temporal_intervals", [])
                 for y in b.get("temporal_intervals", [])), default=0.0)
            answer_hits.append(float(answer_hit))
            temporal_ious.append(temporal_iou)
            row.update({"answer_alias_agree": answer_hit, "temporal_iou": temporal_iou})
            regions_a, regions_b = a.get("spatial_regions", []), b.get("spatial_regions", [])
            if regions_a or regions_b:
                region_f1 = _f1(regions_a, regions_b)
                region_f1s.append(region_f1)
                row["pitch_region_f1"] = region_f1
        relevant_trajectory = bool(a.get("trajectory") or b.get("trajectory")
                                   or a.get("trajectory_unavailable") or b.get("trajectory_unavailable"))
        if relevant_trajectory:
            availability_hit = bool(a.get("trajectory")) == bool(b.get("trajectory"))
            availability_hits.append(float(availability_hit))
            row["trajectory_availability_agree"] = availability_hit
            displacement = _trajectory_displacement(a.get("trajectory", []), b.get("trajectory", []))
            if displacement is not None:
                trajectory_distances.append(displacement["normalized_ade"])
                row["trajectory_displacement"] = displacement
        rows.append(row)

    mean = lambda values: sum(values) / len(values) if values else None
    return {
        "item_count": len(rows),
        "answerability": {"observed_agreement": observed, "cohen_kappa": kappa},
        "answer_alias": {"eligible_count": len(answer_hits), "agreement": mean(answer_hits)},
        "temporal_evidence": {"eligible_count": len(temporal_ious), "mean_iou": mean(temporal_ious),
                              "iou_values": temporal_ious},
        "pitch_regions": {"eligible_count": len(region_f1s), "mean_set_f1": mean(region_f1s),
                          "f1_values": region_f1s},
        "trajectory_availability": {"eligible_count": len(availability_hits),
                                    "observed_agreement": mean(availability_hits)},
        "trajectory_displacement": {"eligible_count": len(trajectory_distances),
                                    "mean_normalized_ade": mean(trajectory_distances),
                                    "normalized_ade_values": trajectory_distances},
        "rows": rows,
        "warning": "Deterministic synthetic agreement fixture; not human inter-annotator reliability.",
    }


def _selective_curve(rows: list[dict], *, correctness_field: str = "answer_correct") -> dict:
    """Build a tie-safe risk/coverage curve over non-abstained answers.

    Equal-confidence items enter together so arbitrary key ordering cannot change
    AURC. Coverage uses all benchmark items as the denominator; AURC is normalized
    over the coverage actually attained by the system, while maximum coverage is
    reported separately.
    """
    covered = [row for row in rows if not row["abstained"]]
    points = [{"confidence_threshold": None, "coverage": 0.0, "selective_risk": None,
               "covered_count": 0}]
    cumulative_count = 0
    cumulative_correct = 0.0
    partial_area = 0.0
    previous_coverage = 0.0
    for threshold in sorted({row["confidence"] for row in covered}, reverse=True):
        members = [row for row in covered if row["confidence"] == threshold]
        cumulative_count += len(members)
        cumulative_correct += sum(row[correctness_field] for row in members)
        coverage = cumulative_count / len(rows) if rows else 0.0
        risk = 1.0 - cumulative_correct / cumulative_count
        partial_area += (coverage - previous_coverage) * risk
        previous_coverage = coverage
        points.append({"confidence_threshold": threshold, "coverage": coverage,
                       "selective_risk": risk, "covered_count": cumulative_count})
    return {
        "points": points,
        "max_coverage": previous_coverage,
        "partial_area": partial_area,
        "aurc_over_attained_coverage": partial_area / previous_coverage if previous_coverage else None,
        "correctness_field": correctness_field,
        "definition": "Tie-grouped right-step risk integral, normalized over attained non-abstained coverage.",
    }


def _coverage_at_risk(curve: dict, targets: Iterable[float] = (0.01, 0.05, 0.10)) -> dict:
    """Maximum attained coverage whose observed selective risk is at most each target."""
    values = {}
    for target in targets:
        eligible = [point["coverage"] for point in curve["points"]
                    if point["selective_risk"] is not None and point["selective_risk"] <= target]
        values[f"{100 * target:g}%"] = max(eligible, default=0.0)
    return {
        "values": values,
        "definition": "Maximum tie-safe attained coverage at observed selective risk <= target.",
    }


def _calibration_report(rows: list[dict], *, correctness_field: str, bins: int) -> dict:
    """Return answered-item ECE and the bins needed for a reliability diagram."""
    covered = [row for row in rows if not row["abstained"]]
    diagram = []
    ece = 0.0
    for bin_index in range(bins):
        low, high = bin_index / bins, (bin_index + 1) / bins
        members = [
            row for row in covered
            if low <= row["confidence"] < high
            or (bin_index == bins - 1 and row["confidence"] == 1.0)
        ]
        count = len(members)
        mean_confidence = sum(row["confidence"] for row in members) / count if count else None
        empirical_accuracy = sum(row[correctness_field] for row in members) / count if count else None
        if count:
            ece += count / len(covered) * abs(empirical_accuracy - mean_confidence)
        diagram.append({
            "lower_inclusive": low,
            "upper_exclusive": high,
            "includes_one": bin_index == bins - 1,
            "count": count,
            "mean_confidence": mean_confidence,
            "empirical_accuracy": empirical_accuracy,
        })
    return {
        "correctness_field": correctness_field,
        "covered_count": len(covered),
        "bin_count": bins,
        "ece": ece if covered else None,
        "reliability_diagram": diagram,
        "definition": "Equal-width answered-item ECE; explicit abstentions are excluded.",
    }


def _grouped_bootstrap(
    rows: list[dict], *, replicates: int, seed: int, group_field: str = "clip_id",
) -> dict:
    """Percentile CIs from group resampling, preserving within-group questions."""
    if replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    groups: dict[object, list[dict]] = {}
    for row in rows:
        if group_field not in row or row[group_field] is None:
            raise ValueError(f"bootstrap group field {group_field!r} missing from a scored item")
        groups.setdefault(row[group_field], []).append(row)
    group_ids = list(groups)
    rng = np.random.default_rng(seed)
    samples: dict[str, list[float]] = {
        "answer_accuracy": [], "joint_grounded_accuracy": [], "coverage": [],
        "selective_risk": [], "selective_aurc": [], "joint_grounded_selective_aurc": [],
        "coverage_at_answer_risk_1%": [], "coverage_at_answer_risk_5%": [],
        "coverage_at_answer_risk_10%": [], "coverage_at_joint_grounded_risk_1%": [],
        "coverage_at_joint_grounded_risk_5%": [], "coverage_at_joint_grounded_risk_10%": [],
    }
    for _ in range(replicates):
        sampled_rows = [row for index in rng.integers(0, len(group_ids), size=len(group_ids))
                        for row in groups[group_ids[int(index)]]]
        covered = [row for row in sampled_rows if not row["abstained"]]
        samples["answer_accuracy"].append(
            sum(row["answer_correct"] for row in sampled_rows) / len(sampled_rows))
        samples["joint_grounded_accuracy"].append(
            sum(row["joint_grounded_correct"] for row in sampled_rows) / len(sampled_rows))
        samples["coverage"].append(len(covered) / len(sampled_rows))
        answer_curve = _selective_curve(sampled_rows)
        joint_curve = _selective_curve(
            sampled_rows, correctness_field="joint_grounded_correct"
        )
        if covered:
            samples["selective_risk"].append(
                1.0 - sum(row["answer_correct"] for row in covered) / len(covered))
            aurc = answer_curve["aurc_over_attained_coverage"]
            if aurc is not None:
                samples["selective_aurc"].append(aurc)
            joint_aurc = joint_curve["aurc_over_attained_coverage"]
            if joint_aurc is not None:
                samples["joint_grounded_selective_aurc"].append(joint_aurc)
        # Coverage-at-risk is defined as zero when a replicate has no answered
        # items, so every bootstrap replicate contributes to these endpoints.
        answer_c = _coverage_at_risk(answer_curve)["values"]
        joint_c = _coverage_at_risk(joint_curve)["values"]
        for target in ("1%", "5%", "10%"):
            samples[f"coverage_at_answer_risk_{target}"].append(answer_c[target])
            samples[f"coverage_at_joint_grounded_risk_{target}"].append(joint_c[target])
    intervals = {}
    for metric, values in samples.items():
        intervals[metric] = None if not values else {
            "lower": float(np.percentile(values, 2.5)),
            "upper": float(np.percentile(values, 97.5)),
            "valid_replicates": len(values),
        }
    return {
        "method": "percentile grouped bootstrap",
        "confidence_level": 0.95,
        "replicates": replicates,
        "seed": seed,
        "group_field": group_field,
        "group_count": len(group_ids),
        "intervals": intervals,
    }


def _exact_paired_binary_test(clean_correct: list[float], corrupt_correct: list[float]) -> dict:
    """Two-sided exact sign/binomial test over discordant paired binary outcomes."""
    clean_wins = sum(a == 1.0 and b == 0.0 for a, b in zip(clean_correct, corrupt_correct))
    corrupt_wins = sum(a == 0.0 and b == 1.0 for a, b in zip(clean_correct, corrupt_correct))
    discordant = clean_wins + corrupt_wins
    if discordant == 0:
        p_value = 1.0
    else:
        smaller = min(clean_wins, corrupt_wins)
        lower_tail = sum(math.comb(discordant, k) for k in range(smaller + 1)) / (2 ** discordant)
        p_value = min(1.0, 2.0 * lower_tail)
    return {
        "clean_correct_corrupt_incorrect": clean_wins,
        "clean_incorrect_corrupt_correct": corrupt_wins,
        "discordant_count": discordant,
        "two_sided_exact_p_value": p_value,
        "definition": "Two-sided exact sign/binomial test with null discordant direction probability 0.5.",
    }


def paired_condition_comparison(
    clean: dict, corrupt: dict, *, group_field: str = "clip_id",
    bootstrap_replicates: int = 1000, bootstrap_seed: int = 20260806,
) -> dict:
    """Compare aligned clean/corrupt scored rows with group-resampled paired deltas."""
    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    clean_rows = {(row["clip_id"], row["question_id"]): row for row in clean.get("rows", [])}
    corrupt_rows = {(row["clip_id"], row["question_id"]): row for row in corrupt.get("rows", [])}
    if not clean_rows or set(clean_rows) != set(corrupt_rows):
        raise ValueError("clean and corrupt scored keys must match exactly and be non-empty")

    delta_fields = {
        "confidence_delta": "confidence",
        "abstention_delta": "abstained",
        "answer_correctness_delta": "answer_correct",
        "joint_grounded_correctness_delta": "joint_grounded_correct",
    }
    pairs, transitions = [], {
        "correct_to_incorrect": 0, "incorrect_to_correct": 0,
        "answer_to_abstain": 0, "abstain_to_answer": 0, "unchanged": 0,
    }
    for key in sorted(clean_rows):
        left, right = clean_rows[key], corrupt_rows[key]
        if group_field not in left or group_field not in right or left[group_field] != right[group_field]:
            raise ValueError(f"paired group field {group_field!r} must exist and match for {key!r}")
        row = {"clip_id": key[0], "question_id": key[1], group_field: left[group_field]}
        for delta_name, field in delta_fields.items():
            row[delta_name] = float(right[field]) - float(left[field])
        if not left["abstained"] and right["abstained"]:
            transition = "answer_to_abstain"
        elif left["abstained"] and not right["abstained"]:
            transition = "abstain_to_answer"
        elif left["answer_correct"] == 1.0 and right["answer_correct"] == 0.0:
            transition = "correct_to_incorrect"
        elif left["answer_correct"] == 0.0 and right["answer_correct"] == 1.0:
            transition = "incorrect_to_correct"
        else:
            transition = "unchanged"
        transitions[transition] += 1
        row["answer_transition"] = transition
        pairs.append(row)

    point_estimates = {
        name: sum(row[name] for row in pairs) / len(pairs) for name in delta_fields
    }
    groups: dict[object, list[dict]] = {}
    for row in pairs:
        groups.setdefault(row[group_field], []).append(row)
    group_ids = list(groups)
    rng = np.random.default_rng(bootstrap_seed)
    samples = {name: [] for name in delta_fields}
    for _ in range(bootstrap_replicates):
        sampled = [row for index in rng.integers(0, len(group_ids), size=len(group_ids))
                   for row in groups[group_ids[int(index)]]]
        for name in delta_fields:
            samples[name].append(sum(row[name] for row in sampled) / len(sampled))
    intervals = {
        name: {"lower": float(np.percentile(values, 2.5)),
               "upper": float(np.percentile(values, 97.5)),
               "valid_replicates": len(values)}
        for name, values in samples.items()
    }
    clean_ordered = [clean_rows[key] for key in sorted(clean_rows)]
    corrupt_ordered = [corrupt_rows[key] for key in sorted(corrupt_rows)]
    return {
        "pair_count": len(pairs),
        "point_estimates": point_estimates,
        "answer_transitions": transitions,
        "exact_paired_tests": {
            "answer_correctness": _exact_paired_binary_test(
                [row["answer_correct"] for row in clean_ordered],
                [row["answer_correct"] for row in corrupt_ordered]),
            "joint_grounded_correctness": _exact_paired_binary_test(
                [row["joint_grounded_correct"] for row in clean_ordered],
                [row["joint_grounded_correct"] for row in corrupt_ordered]),
        },
        "bootstrap_confidence_intervals": {
            "method": "percentile grouped paired bootstrap", "confidence_level": 0.95,
            "replicates": bootstrap_replicates, "seed": bootstrap_seed,
            "group_field": group_field, "group_count": len(group_ids), "intervals": intervals,
        },
        "pairs": pairs,
        "warning": "Paired statistical plumbing; interpretation depends on preregistered independent groups.",
    }


def score_benchmark(
    predictions: Iterable[dict], annotations: Iterable[dict], *, temporal_iou_threshold: float = 0.5,
    region_f1_threshold: float = 0.5, trajectory_ade_threshold: float = 0.1,
    trajectory_time_tolerance_s: float = 0.5, trajectory_distance_tolerance: float = 0.1,
    calibration_bins: int = 5, bootstrap_replicates: int = 1000, bootstrap_seed: int = 20260806,
    bootstrap_group_field: str = "clip_id", operational_confidence_threshold: float = 0.5,
) -> dict:
    """Score frozen v1 outputs without requiring a model or external dataset.

    Joint grounded correctness requires answer correctness, temporal IoU and region
    F1 at their thresholds, plus normalized trajectory ADE at or below the frozen
    threshold when the gold item has a trajectory. Missing/no-overlap required
    trajectories are misses, not zero error. Unanswerable items are correct only
    when the system abstains.
    """
    predictions = list(predictions)
    annotations = list(annotations)
    gold_by_key = {(v["clip_id"], v["question_id"]): v for v in annotations}
    pred_by_key = {(v["clip_id"], v["question_id"]): v for v in predictions}
    if len(gold_by_key) != len(annotations) or len(pred_by_key) != len(predictions):
        raise ValueError("duplicate clip/question key")
    if set(gold_by_key) != set(pred_by_key):
        raise ValueError("prediction and annotation keys must match exactly")
    if not gold_by_key:
        raise ValueError("benchmark inputs must be non-empty")
    if calibration_bins < 1:
        raise ValueError("calibration_bins must be positive")
    if not math.isfinite(operational_confidence_threshold) or not 0.0 <= operational_confidence_threshold <= 1.0:
        raise ValueError("operational_confidence_threshold must be finite and in [0,1]")

    rows: list[dict] = []
    for key in sorted(gold_by_key):
        gold, prediction = gold_by_key[key], pred_by_key[key]
        aliases = {str(v).strip().casefold() for v in gold.get("accepted_aliases", [])}
        aliases.add(str(gold.get("canonical_answer") or "").strip().casefold())
        answerable = gold["answerability"] == "answerable"
        answer_correct = (not prediction["abstained"] and prediction["answer"].strip().casefold() in aliases) if answerable else bool(prediction["abstained"])
        temporal_iou = max(
            (_interval_iou(prediction["temporal_evidence_s"], interval) for interval in gold.get("temporal_intervals", [])),
            default=(1.0 if not answerable and prediction["abstained"] else 0.0),
        )
        temporal_hit = float(temporal_iou > 0.0)
        region_f1 = _f1(prediction.get("spatial_evidence", []), gold.get("spatial_regions", []))
        trajectory_recall = _trajectory_recall(
            prediction.get("trajectory", []), gold.get("trajectory", []),
            time_tolerance_s=trajectory_time_tolerance_s, distance_tolerance=trajectory_distance_tolerance,
        )
        trajectory_required = bool(gold.get("trajectory"))
        displacement = _trajectory_displacement(
            prediction.get("trajectory", []), gold.get("trajectory", [])
        ) if trajectory_required else None
        trajectory_ade = displacement["normalized_ade"] if displacement is not None else None
        trajectory_fde = displacement["normalized_fde"] if displacement is not None else None
        trajectory_hit = not trajectory_required or (
            trajectory_ade is not None and trajectory_ade <= trajectory_ade_threshold
        )
        grounded = bool(
            answer_correct and temporal_iou >= temporal_iou_threshold
            and region_f1 >= region_f1_threshold
            and trajectory_hit
        )
        confidence = float(prediction["confidence"])
        if bootstrap_group_field not in gold:
            raise ValueError(
                f"bootstrap group field {bootstrap_group_field!r} missing from annotation {key!r}"
            )
        rows.append({
            "clip_id": key[0], "question_id": key[1], "answer_correct": float(answer_correct),
            bootstrap_group_field: gold[bootstrap_group_field],
            "temporal_iou": temporal_iou, "temporal_hit": temporal_hit,
            "pitch_region_f1": region_f1, "trajectory_recall_at_tolerance": trajectory_recall,
            "trajectory_required": trajectory_required, "trajectory_normalized_ade": trajectory_ade,
            "trajectory_normalized_fde": trajectory_fde, "trajectory_ade_hit": trajectory_hit,
            "joint_grounded_correct": float(grounded), "confidence": confidence,
            # Calibration is defined over answered (covered) items. The frozen
            # contract forces abstentions to confidence=0, which is not a
            # probability that the abstention decision itself is correct.
            "brier_score": None if prediction["abstained"] else (confidence - float(answer_correct)) ** 2,
            "abstained": bool(prediction["abstained"]),
        })

    covered = [row for row in rows if not row["abstained"]]
    operational_rows = [
        row for row in covered if row["confidence"] >= operational_confidence_threshold
    ]
    operational_point = {
        "confidence_threshold": operational_confidence_threshold,
        "covered_count": len(operational_rows),
        "coverage": len(operational_rows) / len(rows),
        "answer_selective_risk": (
            1.0 - sum(row["answer_correct"] for row in operational_rows) / len(operational_rows)
            if operational_rows else None
        ),
        "joint_grounded_selective_risk": (
            1.0 - sum(row["joint_grounded_correct"] for row in operational_rows) / len(operational_rows)
            if operational_rows else None
        ),
    }
    answer_calibration = _calibration_report(
        rows, correctness_field="answer_correct", bins=calibration_bins
    )
    joint_calibration = _calibration_report(
        rows, correctness_field="joint_grounded_correct", bins=calibration_bins
    )
    mean = lambda field: sum(row[field] for row in rows) / len(rows) if rows else 0.0
    trajectory_rows = [row for row in rows if row["trajectory_required"]]
    measured_trajectories = [row for row in trajectory_rows if row["trajectory_normalized_ade"] is not None]
    mean_brier = sum(row["brier_score"] for row in covered) / len(covered) if covered else None
    selective_curve = _selective_curve(rows)
    joint_selective_curve = _selective_curve(rows, correctness_field="joint_grounded_correct")
    bootstrap = _grouped_bootstrap(
        rows, replicates=bootstrap_replicates, seed=bootstrap_seed,
        group_field=bootstrap_group_field,
    )
    return {
        "item_count": len(rows), "answer_accuracy": mean("answer_correct"),
        "mean_temporal_iou": mean("temporal_iou"), "temporal_hit_rate": mean("temporal_hit"),
        "mean_pitch_region_f1": mean("pitch_region_f1"),
        "mean_trajectory_recall_at_tolerance": mean("trajectory_recall_at_tolerance"),
        "trajectory_required_count": len(trajectory_rows),
        "trajectory_measured_count": len(measured_trajectories),
        "trajectory_measurement_rate": len(measured_trajectories) / len(trajectory_rows) if trajectory_rows else None,
        "mean_trajectory_normalized_ade": (
            sum(row["trajectory_normalized_ade"] for row in measured_trajectories) / len(measured_trajectories)
            if measured_trajectories else None
        ),
        "mean_trajectory_normalized_fde": (
            sum(row["trajectory_normalized_fde"] for row in measured_trajectories) / len(measured_trajectories)
            if measured_trajectories else None
        ),
        "joint_grounded_accuracy": mean("joint_grounded_correct"), "mean_brier_score": mean_brier,
        "ece": answer_calibration["ece"],
        "answer_calibration": answer_calibration,
        "joint_grounded_calibration": joint_calibration,
        "coverage": len(covered) / len(rows) if rows else 0.0,
        "selective_risk": 1.0 - sum(r["answer_correct"] for r in covered) / len(covered) if covered else None,
        "selective_aurc": selective_curve["aurc_over_attained_coverage"],
        "coverage_at_answer_risk": _coverage_at_risk(selective_curve),
        "risk_coverage_curve": selective_curve,
        "joint_grounded_selective_aurc": joint_selective_curve["aurc_over_attained_coverage"],
        "coverage_at_joint_grounded_risk": _coverage_at_risk(joint_selective_curve),
        "joint_grounded_risk_coverage_curve": joint_selective_curve,
        "operational_point": operational_point,
        "bootstrap_confidence_intervals": bootstrap,
        "thresholds": {"temporal_iou": temporal_iou_threshold, "pitch_region_f1": region_f1_threshold,
                       "trajectory_normalized_ade": trajectory_ade_threshold,
                       "trajectory_time_tolerance_s": trajectory_time_tolerance_s,
                       "trajectory_distance_norm": trajectory_distance_tolerance,
                       "calibration_bins": calibration_bins,
                       "bootstrap_replicates": bootstrap_replicates,
                       "bootstrap_seed": bootstrap_seed,
                       "bootstrap_group_field": bootstrap_group_field,
                       "operational_confidence": operational_confidence_threshold},
        "rows": rows,
        "warning": "Deterministic synthetic scoring fixture; not model or real-soccer performance.",
    }


def run_scoring_fixture(out_dir: Path) -> dict:
    """Exercise scoring with a correct grounding, wrong evidence, and valid abstention."""
    digest = "0" * 64
    def point(t: float, x: float, y: float) -> dict:
        return {"timestamp_s": t, "x_norm": x, "y_norm": y, "frame_sha256": digest}
    annotations = [
        {"clip_id": "c1", "question_id": "q1", "answerability": "answerable", "canonical_answer": "cross",
         "accepted_aliases": ["cross into box"], "temporal_intervals": [[1.0, 3.0]], "spatial_regions": ["penalty-area"],
         "trajectory": [{"timestamp_s": 1.0, "x_norm": .1, "y_norm": .8}, {"timestamp_s": 3.0, "x_norm": .8, "y_norm": .4}]},
        {"clip_id": "c2", "question_id": "q2", "answerability": "answerable", "canonical_answer": "pass",
         "accepted_aliases": [], "temporal_intervals": [[2.0, 4.0]], "spatial_regions": ["midfield"], "trajectory": []},
        {"clip_id": "c3", "question_id": "q3", "answerability": "insufficient_visual_evidence", "canonical_answer": None,
         "accepted_aliases": [], "temporal_intervals": [], "spatial_regions": [], "trajectory": []},
    ]
    predictions = [
        {"clip_id": "c1", "question_id": "q1", "answer": "cross into box", "confidence": .9,
         "temporal_evidence_s": [1.0, 3.0], "spatial_evidence": ["penalty-area"],
         "trajectory": [point(1.0, .1, .8), point(3.0, .8, .4)], "abstained": False},
        {"clip_id": "c2", "question_id": "q2", "answer": "pass", "confidence": .8,
         "temporal_evidence_s": [0.0, 1.0], "spatial_evidence": ["penalty-area"],
         "trajectory": [], "abstained": False},
        {"clip_id": "c3", "question_id": "q3", "answer": "insufficient_visual_evidence", "confidence": 0.0,
         "temporal_evidence_s": [0.0, 0.0], "spatial_evidence": [], "trajectory": [], "abstained": True},
    ]
    results = score_benchmark(predictions, annotations)
    _write_json(out_dir / "annotations.json", annotations)
    _write_json(out_dir / "predictions.json", predictions)
    _write_json(out_dir / "scoring-results.json", results)
    receipt = {"created_at": datetime.now(timezone.utc).isoformat(),
               "command": "python prototype/sports_play_lab.py score-fixture --out " + str(out_dir),
               "results_sha256": hashlib.sha256((out_dir / "scoring-results.json").read_bytes()).hexdigest(),
               "summary": {k: v for k, v in results.items() if k not in {"rows", "thresholds", "warning"}},
               "warning": results["warning"]}
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def run_evidence_perturbation_fixture(out_dir: Path) -> dict:
    """Score clean, evidence-swapped, and noisy-tool counterfactual controls.

    Answers and confidence are held fixed. The evidence-swap condition rotates the
    complete evidence bundle between clips; the noisy-tool condition shifts only
    trajectory x coordinates. This is dataset-free metric plumbing, not evidence
    about a model's causal use of tools.
    """
    digest = "0" * 64

    def point(t: float, x: float, y: float) -> dict:
        return {"timestamp_s": t, "x_norm": x, "y_norm": y, "frame_sha256": digest}

    specifications = [
        ("c1", "q1", "cross", [1.0, 3.0], "left-corner",
         [point(1.0, .10, .80), point(3.0, .75, .45)], .90),
        ("c2", "q2", "pass", [4.0, 6.0], "midfield",
         [point(4.0, .30, .50), point(6.0, .60, .50)], .80),
        ("c3", "q3", "dribble", [7.0, 9.0], "right-wing",
         [point(7.0, .65, .20), point(9.0, .80, .35)], .70),
    ]
    annotations = [
        {"clip_id": clip, "question_id": question, "answerability": "answerable",
         "canonical_answer": answer, "accepted_aliases": [], "temporal_intervals": [interval],
         "spatial_regions": [region],
         "trajectory": [{k: v for k, v in p.items() if k != "frame_sha256"} for p in trajectory]}
        for clip, question, answer, interval, region, trajectory, _ in specifications
    ]
    clean = [
        {"schema_version": OUTPUT_SCHEMA_VERSION, "clip_id": clip, "question_id": question,
         "answer": answer, "confidence": confidence, "temporal_evidence_s": interval,
         "spatial_evidence": [region], "trajectory": trajectory, "abstained": False,
         "abstention_reason": None}
        for clip, question, answer, interval, region, trajectory, confidence in specifications
    ]
    swapped = []
    for index, prediction in enumerate(clean):
        donor = clean[(index + 1) % len(clean)]
        swapped.append({**prediction, "temporal_evidence_s": donor["temporal_evidence_s"],
                        "spatial_evidence": donor["spatial_evidence"],
                        "trajectory": donor["trajectory"]})
    noisy_tool = [
        {**prediction, "trajectory": [
            {**p, "x_norm": min(1.0, p["x_norm"] + .20)} for p in prediction["trajectory"]
        ]}
        for prediction in clean
    ]
    conditions = {"clean": clean, "evidence_swap": swapped, "noisy_tool_x_shift": noisy_tool}
    results = {}
    for name, predictions in conditions.items():
        contract_errors = [error for prediction in predictions
                           for error in validate_prediction_payload(prediction)]
        if contract_errors:
            raise RuntimeError(f"{name} violated frozen output contract: {contract_errors}")
        scored = score_benchmark(predictions, annotations, bootstrap_replicates=200,
                                 bootstrap_seed=20260806)
        results[name] = scored
        _write_json(out_dir / f"predictions-{name}.json", predictions)
        _write_json(out_dir / f"scoring-{name}.json", scored)

    clean_score = results["clean"]
    summary = {
        name: {
            "contract_error_count": 0,
            "answer_accuracy": result["answer_accuracy"],
            "joint_grounded_accuracy": result["joint_grounded_accuracy"],
            "mean_temporal_iou": result["mean_temporal_iou"],
            "mean_pitch_region_f1": result["mean_pitch_region_f1"],
            "mean_trajectory_normalized_ade": result["mean_trajectory_normalized_ade"],
            "joint_grounded_delta_from_clean": (
                result["joint_grounded_accuracy"] - clean_score["joint_grounded_accuracy"]),
        }
        for name, result in results.items()
    }
    _write_json(out_dir / "annotations.json", annotations)
    _write_json(out_dir / "comparison-summary.json", summary)
    paired = {
        name: paired_condition_comparison(
            clean_score, result, bootstrap_replicates=200, bootstrap_seed=20260806
        )
        for name, result in results.items() if name != "clean"
    }
    _write_json(out_dir / "paired-comparisons.json", paired)
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": "python prototype/sports_play_lab.py evidence-perturbation-fixture --out " + str(out_dir),
        "fault_boundary": "frozen prediction evidence fields; answer and confidence held fixed",
        "summary_sha256": hashlib.sha256((out_dir / "comparison-summary.json").read_bytes()).hexdigest(),
        "paired_comparisons_sha256": hashlib.sha256((out_dir / "paired-comparisons.json").read_bytes()).hexdigest(),
        "summary": summary,
        "warning": "Deterministic synthetic counterfactual controls; not VLM, causal, or real-soccer performance.",
    }
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def run_agreement_fixture(out_dir: Path) -> dict:
    """Exercise agreement metrics with three deterministic synthetic item pairs."""
    shared = {"trajectory_unavailable": False, "accepted_aliases": [],
              "temporal_intervals": [], "spatial_regions": [], "trajectory": []}
    left = [
        {**shared, "clip_id": "c1", "question_id": "q1", "answerability": "answerable",
         "canonical_answer": "cross", "accepted_aliases": ["cross into box"],
         "temporal_intervals": [[1.0, 3.0]], "spatial_regions": ["left-corner"],
         "trajectory": [{"timestamp_s": 1.0, "x_norm": .10, "y_norm": .80},
                        {"timestamp_s": 3.0, "x_norm": .80, "y_norm": .40}]},
        {**shared, "clip_id": "c2", "question_id": "q2",
         "answerability": "insufficient_visual_evidence", "canonical_answer": None},
        {**shared, "clip_id": "c3", "question_id": "q3", "answerability": "answerable",
         "canonical_answer": "pass", "temporal_intervals": [[2.0, 3.0]]},
    ]
    right = [
        {**shared, "clip_id": "c1", "question_id": "q1", "answerability": "answerable",
         "canonical_answer": "cross into box", "accepted_aliases": ["cross"],
         "temporal_intervals": [[1.5, 3.5]], "spatial_regions": ["left-corner", "penalty-area"],
         "trajectory": [{"timestamp_s": 1.0, "x_norm": .12, "y_norm": .82},
                        {"timestamp_s": 3.0, "x_norm": .82, "y_norm": .42}]},
        {**shared, "clip_id": "c2", "question_id": "q2",
         "answerability": "insufficient_visual_evidence", "canonical_answer": None},
        {**shared, "clip_id": "c3", "question_id": "q3", "answerability": "invalid_question",
         "canonical_answer": None},
    ]
    results = annotation_agreement(left, right)
    _write_json(out_dir / "annotator-a.json", left)
    _write_json(out_dir / "annotator-b.json", right)
    _write_json(out_dir / "agreement-results.json", results)
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": "python prototype/sports_play_lab.py agreement-fixture --out " + str(out_dir),
        "results_sha256": hashlib.sha256((out_dir / "agreement-results.json").read_bytes()).hexdigest(),
        "summary": {k: v for k, v in results.items() if k not in {"rows", "warning"}},
        "warning": results["warning"],
    }
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def evaluate(prediction: Prediction, ground_truth: dict) -> dict:
    correct = prediction.answer == ground_truth["answer"]
    expected_start, expected_end = map(float, ground_truth["temporal_evidence_s"])
    pred_start, pred_end = prediction.temporal_evidence_s
    temporal_coverage = max(0.0, min(pred_end, expected_end) - max(pred_start, expected_start))
    temporal_union = max(pred_end, expected_end) - min(pred_start, expected_start)
    return {
        "answer_exact_match": float(correct),
        "spatial_evidence_f1": _f1(prediction.spatial_evidence, ground_truth["spatial_evidence"]),
        "temporal_iou": temporal_coverage / temporal_union if temporal_union > 0 else 0.0,
        "brier_score": (prediction.confidence - float(correct)) ** 2,
        "abstained": prediction.abstained,
        "ball_detections": len(prediction.trajectory),
        "warning": "Synthetic smoke-test metrics; not model or real-soccer results.",
    }


def run_demo(out_dir: Path) -> dict:
    video_path, gt_path = generate_synthetic_clip(out_dir)
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))
    prediction = trajectory_baseline(video_path)
    metrics = evaluate(prediction, ground_truth)
    prediction_dict = prediction_payload(
        prediction,
        clip_id=ground_truth["clip_id"],
        question_id="restart-progression-q1",
    )
    contract_errors = validate_prediction_payload(prediction_dict)
    if contract_errors:
        raise RuntimeError("prediction violated output contract: " + "; ".join(contract_errors))
    _write_json(out_dir / "prediction.json", prediction_dict)
    _write_json(out_dir / "metrics.json", metrics)
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": "python prototype/sports_play_lab.py demo --out " + str(out_dir),
        "python": sys.version,
        "platform": platform.platform(),
        "opencv": cv2.__version__,
        "video_sha256": hashlib.sha256(video_path.read_bytes()).hexdigest(),
        "artifacts": [str(p) for p in [video_path, gt_path, out_dir / "prediction.json", out_dir / "metrics.json"]],
        "metrics": metrics,
    }
    try:
        receipt["ffmpeg_version"] = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=False
        ).stdout.splitlines()[0]
    except OSError:
        receipt["ffmpeg_version"] = "unavailable"
    _write_json(out_dir / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, required=True)
    corruption = sub.add_parser("corruption")
    corruption.add_argument("--out", type=Path, required=True)
    corruption.add_argument("--seed", type=int, default=7)
    severity = sub.add_parser("severity")
    severity.add_argument("--out", type=Path, required=True)
    annotations = sub.add_parser("validate-annotations")
    annotations.add_argument("--export", type=Path, required=True)
    annotations.add_argument("--manifest", type=Path, required=True)
    annotations.add_argument("--rubric", type=Path, required=True)
    annotations.add_argument("--report", type=Path)
    frame_review = sub.add_parser("validate-frame-review")
    frame_review.add_argument("--worksheet", type=Path, required=True)
    frame_review.add_argument("--export", type=Path, required=True)
    frame_review.add_argument("--manifest", type=Path, required=True)
    frame_review.add_argument("--report", type=Path)
    review_packet = sub.add_parser("make-frame-review-packet")
    review_packet.add_argument("--video", type=Path, required=True)
    review_packet.add_argument("--worksheet", type=Path, required=True)
    review_packet.add_argument("--out", type=Path, required=True)
    review_packet.add_argument("--frames-per-page", type=int, default=24)
    scoring = sub.add_parser("score-fixture")
    scoring.add_argument("--out", type=Path, required=True)
    perturbation = sub.add_parser("evidence-perturbation-fixture")
    perturbation.add_argument("--out", type=Path, required=True)
    agreement = sub.add_parser("agreement-fixture")
    agreement.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "demo":
        receipt = run_demo(args.out)
        print(json.dumps(receipt["metrics"], indent=2, sort_keys=True))
        return 0
    if args.command == "corruption":
        receipt = run_corruption_experiment(args.out, seed=args.seed)
        print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
        return 0
    if args.command == "severity":
        receipt = run_severity_experiment(args.out)
        print(json.dumps(receipt["policies"], indent=2, sort_keys=True))
        return 0
    if args.command == "validate-annotations":
        errors = validate_annotation_export(
            json.loads(args.export.read_text(encoding="utf-8")),
            json.loads(args.manifest.read_text(encoding="utf-8")),
            json.loads(args.rubric.read_text(encoding="utf-8")),
        )
        result = {"valid": not errors, "error_count": len(errors), "errors": errors}
        if args.report:
            _write_json(args.report, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not errors else 1
    if args.command == "validate-frame-review":
        errors = validate_frame_review(
            json.loads(args.worksheet.read_text(encoding="utf-8")),
            json.loads(args.export.read_text(encoding="utf-8")),
            json.loads(args.manifest.read_text(encoding="utf-8")),
        )
        result = {"valid": not errors, "error_count": len(errors), "errors": errors}
        if args.report:
            _write_json(args.report, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not errors else 1
    if args.command == "make-frame-review-packet":
        receipt = generate_frame_review_packet(
            args.video, args.worksheet, args.out, frames_per_page=args.frames_per_page)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    if args.command == "score-fixture":
        receipt = run_scoring_fixture(args.out)
        print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
        return 0
    if args.command == "evidence-perturbation-fixture":
        receipt = run_evidence_perturbation_fixture(args.out)
        print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
        return 0
    if args.command == "agreement-fixture":
        receipt = run_agreement_fixture(args.out)
        print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
