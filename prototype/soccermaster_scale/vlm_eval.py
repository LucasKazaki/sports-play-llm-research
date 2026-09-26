"""Frozen, silent, held-out SoccerNet evaluation for a local video-language model.

Inference reads an input manifest that contains no labels.  Labels live in a
separate frozen file and are opened only by the scoring stage after every raw
model response is persisted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from .manifest import load_examples, sha256_file, stable_id
from .model import classification_metrics
from .taxonomy import CLASS_NAMES


INPUT_SCHEMA = "playground-soccermaster-vlm-frozen-inputs-v1"
LABEL_SCHEMA = "playground-soccermaster-vlm-sealed-labels-v1"
SUBSET_RECEIPT_SCHEMA = "playground-soccermaster-vlm-subset-receipt-v1"
PREDICTION_SCHEMA = "playground-soccermaster-vlm-prediction-v1"
RUN_RECEIPT_SCHEMA = "playground-soccermaster-vlm-run-receipt-v1"
EVALUATION_SCHEMA = "playground-soccermaster-vlm-evaluation-v1"
MODEL_ID = "google/gemma-4-e4b"
ENDPOINT = "http://127.0.0.1:1240/v1"
FRAME_COUNT = 8
SHEETS = 2


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as sink:
        for row in rows:
            sink.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _prompt() -> str:
    classes = ", ".join(CLASS_NAMES)
    return (
        "You are analyzing eight chronological silent broadcast frames from a 12-second soccer window. "
        "The target action is near the middle, but context before and after may be required. Use only visible pixels. "
        f"Choose exactly one event_class from: {classes}; or insufficient_visual_evidence. "
        "Do not infer a player name, team name, match identity, score, or tactical intent. Distinguish the observable "
        "event itself from a replay, reaction, close-up, or generic stoppage. If the primary class is not visually "
        "supported, abstain. Return strict JSON with exactly these keys: event_class, confidence, "
        "evidence_frame_indices, observable_summary, actor_detail, team_detail, field_region, ball_trajectory, "
        "abstained, abstention_reason. evidence_frame_indices must contain only integers 0 through 7. "
        "actor_detail and team_detail must be 'unavailable' unless directly readable in the frames. field_region must "
        "be one of defensive_third, middle_third, attacking_third, penalty_area, touchline, goal_area, unknown. "
        "ball_trajectory must be a short visible-only description or 'unavailable'. For abstention use "
        "event_class insufficient_visual_evidence, confidence 0, an empty evidence_frame_indices list, and a concise "
        "abstention_reason. For a prediction, abstained must be false, evidence_frame_indices must be non-empty, and "
        "abstention_reason must be an empty string."
    )


def _response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "soccermaster_visual_event",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "event_class": {"type": "string", "enum": [*CLASS_NAMES, "insufficient_visual_evidence"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_frame_indices": {
                        "type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 7},
                        "minItems": 0, "maxItems": 8, "uniqueItems": True,
                    },
                    "observable_summary": {"type": "string", "minLength": 1},
                    "actor_detail": {"type": "string", "minLength": 1},
                    "team_detail": {"type": "string", "minLength": 1},
                    "field_region": {
                        "type": "string",
                        "enum": ["defensive_third", "middle_third", "attacking_third", "penalty_area", "touchline", "goal_area", "unknown"],
                    },
                    "ball_trajectory": {"type": "string", "minLength": 1},
                    "abstained": {"type": "boolean"},
                    "abstention_reason": {"type": "string"},
                },
                "required": [
                    "event_class", "confidence", "evidence_frame_indices", "observable_summary", "actor_detail",
                    "team_detail", "field_region", "ball_trajectory", "abstained", "abstention_reason",
                ],
                "additionalProperties": False,
            },
        },
    }


def _prompt_sha256() -> str:
    return hashlib.sha256(_prompt().encode("utf-8")).hexdigest()


def _schema_sha256() -> str:
    return hashlib.sha256(json.dumps(_response_format(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _wilson_interval(successes: int, total: int) -> list[float]:
    if total < 1 or successes < 0 or successes > total:
        raise ValueError("invalid Wilson interval counts")
    probability = successes / total
    z = 1.959963984540054
    denominator = 1.0 + z * z / total
    center = (probability + z * z / (2.0 * total)) / denominator
    half_width = z * math.sqrt(probability * (1.0 - probability) / total + z * z / (4.0 * total * total)) / denominator
    return [max(0.0, center - half_width), min(1.0, center + half_width)]


def _round_robin_by_game(rows: list[dict[str, Any]], maximum: int, seed: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["game_id"]].append(row)
    for game_id in grouped:
        grouped[game_id].sort(key=lambda row: stable_id(seed, row["example_id"], length=64))
    selected: list[dict[str, Any]] = []
    game_ids = sorted(grouped)
    while len(selected) < maximum:
        changed = False
        for game_id in game_ids:
            if grouped[game_id] and len(selected) < maximum:
                selected.append(grouped[game_id].pop(0))
                changed = True
        if not changed:
            break
    return selected


def freeze_subset(
    *, examples_path: Path, private_dir: Path, public_receipt_path: Path,
    per_class: int = 4, seed: str = "soccermaster-vlm-heldout-20260827-v1",
) -> dict[str, Any]:
    input_path = private_dir / "frozen-inputs.json"
    labels_path = private_dir / "sealed-labels.json"
    if input_path.exists() or labels_path.exists() or public_receipt_path.exists():
        raise FileExistsError("refusing to overwrite an existing frozen VLM subset")
    candidates = [
        row for row in load_examples(examples_path)
        if row["split"] == "test" and row["ground_truth"]["single_label_eligible"]
    ]
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_class[row["ground_truth"]["class_name"]].append(row)
    selected: list[dict[str, Any]] = []
    for class_name in CLASS_NAMES:
        selected.extend(_round_robin_by_game(by_class[class_name], per_class, seed + class_name))
    selected.sort(key=lambda row: stable_id(seed, row["example_id"], length=64))
    inputs = {
        "schema_version": INPUT_SCHEMA,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "selection": {
            "source_split": "test",
            "per_class_maximum": per_class,
            "seed": seed,
            "single_label_eligible_only": True,
            "stratified_by_ground_truth_before_inference": True,
            "round_robin_across_test_games": True,
        },
        "input_contract": {
            "visual_only": True,
            "audio_used": False,
            "labels_present": False,
            "frames_per_window": FRAME_COUNT,
            "contact_sheets": SHEETS,
            "candidate_boundary": "label-centered evaluation window; candidate discovery is not evaluated",
        },
        "examples": [{
            "example_id": row["example_id"],
            "game_id": row["game_id"],
            "source_half": row["source_half"],
            "video_relative_path": row["video_relative_path"],
            "window_start_s": row["window_start_s"],
            "window_end_s": row["window_end_s"],
        } for row in selected],
    }
    labels = {
        "schema_version": LABEL_SCHEMA,
        "frozen_at": inputs["frozen_at"],
        "join_key": "example_id",
        "scoring_only": True,
        "labels": [{
            "example_id": row["example_id"],
            "class_name": row["ground_truth"]["class_name"],
            "source_label": row["ground_truth"]["source_label"],
        } for row in selected],
    }
    private_dir.mkdir(parents=True, exist_ok=True)
    _write_json(input_path, inputs)
    _write_json(labels_path, labels)
    counts = Counter(item["class_name"] for item in labels["labels"])
    receipt = {
        "schema_version": SUBSET_RECEIPT_SCHEMA,
        "frozen_at": inputs["frozen_at"],
        "status": "frozen_before_inference",
        "input_count": len(selected),
        "class_counts": {name: counts.get(name, 0) for name in CLASS_NAMES},
        "test_game_count": len({row["game_id"] for row in selected}),
        "inputs_sha256": sha256_file(input_path),
        "sealed_labels_sha256": sha256_file(labels_path),
        "source_examples_sha256": sha256_file(examples_path),
        "prompt_sha256": _prompt_sha256(),
        "response_format_sha256": _schema_sha256(),
        "labels_absent_from_inference_manifest": all("ground_truth" not in row and "class_name" not in row for row in inputs["examples"]),
        "performance_claim_allowed": False,
        "safety": {"contains_credentials": False, "contains_raw_media": False, "contains_raw_media_paths": False},
    }
    if not receipt["labels_absent_from_inference_manifest"] or len(selected) < 20:
        raise RuntimeError("frozen VLM subset failed the minimum sealed-label contract")
    _write_json(public_receipt_path, receipt)
    return receipt


def _decode_window_frames(video_path: Path, start_s: float, end_s: float) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("could not open manifest-bound VLM source video")
    frames: list[np.ndarray] = []
    try:
        for index in range(FRAME_COUNT):
            timestamp = start_s + (index + 0.5) * (end_s - start_s) / FRAME_COUNT
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(f"frame decode failed for VLM input index {index}")
            frames.append(frame)
    finally:
        cap.release()
    return frames


def _write_sheets(frames: list[np.ndarray], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for sheet_index in range(SHEETS):
        canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
        group = frames[sheet_index * 4:(sheet_index + 1) * 4]
        for offset, frame in enumerate(group):
            row, col = divmod(offset, 2)
            resized = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            y, x = row * 360, col * 640
            canvas[y:y + 360, x:x + 640] = resized
            global_index = sheet_index * 4 + offset
            cv2.rectangle(canvas, (x, y), (x + 118, y + 34), (0, 0, 0), -1)
            cv2.putText(canvas, f"frame {global_index}", (x + 8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
        path = output_dir / f"contact-sheet-{sheet_index + 1:02d}.jpg"
        if not cv2.imwrite(str(path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
            raise RuntimeError("failed to write VLM contact sheet")
        paths.append(path)
    return paths


def _data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _loopback_json(url: str, *, payload: dict[str, Any] | None = None, timeout: float = 240) -> dict[str, Any]:
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("VLM evaluation is restricted to a loopback endpoint")
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"accept": "application/json", "content-type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("local VLM endpoint returned a non-object")
    return value


def _parse_content(raw: dict[str, Any]) -> dict[str, Any]:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("local VLM response lacks choices")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("local VLM response lacks assistant text")
    text = message["content"].strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("local VLM assistant content is not a JSON object")
    return value


def _validate_prediction(value: dict[str, Any], example_id: str, model_reported: Any) -> dict[str, Any]:
    keys = {
        "event_class", "confidence", "evidence_frame_indices", "observable_summary", "actor_detail",
        "team_detail", "field_region", "ball_trajectory", "abstained", "abstention_reason",
    }
    if set(value) != keys:
        raise ValueError("VLM prediction keys violate frozen schema")
    answer = value["event_class"]
    confidence = float(value["confidence"])
    evidence = value["evidence_frame_indices"]
    if answer not in {*CLASS_NAMES, "insufficient_visual_evidence"} or not 0 <= confidence <= 1:
        raise ValueError("VLM class/confidence invalid")
    if not isinstance(evidence, list) or any(type(index) is not int or index not in range(FRAME_COUNT) for index in evidence) or len(evidence) != len(set(evidence)):
        raise ValueError("VLM evidence-frame indices invalid")
    if not isinstance(value["abstained"], bool):
        raise ValueError("VLM abstained flag invalid")
    if value["abstained"]:
        if answer != "insufficient_visual_evidence" or evidence or confidence != 0:
            raise ValueError("VLM abstention fields are inconsistent")
    elif answer == "insufficient_visual_evidence" or not evidence or value["abstention_reason"] not in {"", None}:
        raise ValueError("VLM prediction fields are inconsistent")
    for key in ("observable_summary", "actor_detail", "team_detail", "field_region", "ball_trajectory"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"VLM detail field invalid: {key}")
    return {
        "schema_version": PREDICTION_SCHEMA,
        "example_id": example_id,
        "model_requested": MODEL_ID,
        "model_reported": model_reported,
        **value,
    }


def run_inference(
    *, frozen_inputs_path: Path, subset_receipt_path: Path, raw_root: Path,
    private_run_dir: Path, public_run_receipt_path: Path,
    runtime_receipt_path: Path,
) -> dict[str, Any]:
    frozen = _read_json(frozen_inputs_path)
    subset = _read_json(subset_receipt_path)
    if frozen.get("schema_version") != INPUT_SCHEMA or subset.get("schema_version") != SUBSET_RECEIPT_SCHEMA:
        raise ValueError("unsupported frozen VLM subset")
    if sha256_file(frozen_inputs_path) != subset.get("inputs_sha256"):
        raise ValueError("frozen VLM input hash mismatch")
    runtime = _read_json(runtime_receipt_path)
    runtime_model = runtime.get("model", {}).get("identifier")
    if runtime_model != MODEL_ID:
        raise ValueError("runtime receipt model identity mismatch")
    health = _loopback_json(ENDPOINT.removesuffix("/v1") + "/health", timeout=10)
    models = _loopback_json(ENDPOINT + "/models", timeout=10)
    served_ids = sorted(item.get("id") for item in models.get("data", []) if isinstance(item, dict))
    if health.get("status") not in {"ok", "ready"} or served_ids != [MODEL_ID]:
        raise RuntimeError("local VLM health/model identity verification failed")
    private_run_dir.mkdir(parents=True, exist_ok=True)
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    latencies: list[float] = []
    reused_verified_responses = 0
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    for ordinal, item in enumerate(frozen["examples"], start=1):
        example_id = item["example_id"]
        example_dir = private_run_dir / example_id
        prediction_path = example_dir / "prediction.json"
        per_receipt_path = example_dir / "receipt.json"
        if prediction_path.exists() and per_receipt_path.exists():
            existing_receipt = _read_json(per_receipt_path)
            if (
                existing_receipt.get("schema_version") == RUN_RECEIPT_SCHEMA
                and existing_receipt.get("example_id") == example_id
                and existing_receipt.get("prompt_sha256") == _prompt_sha256()
                and existing_receipt.get("response_format_sha256") == _schema_sha256()
                and existing_receipt.get("prediction_sha256") == sha256_file(prediction_path)
            ):
                successes.append(_read_json(prediction_path))
                latencies.append(float(existing_receipt["elapsed_ms"]))
                reused_verified_responses += 1
                continue
            raise ValueError(f"existing VLM result failed closed verification: {example_id}")
        try:
            frames = _decode_window_frames(
                raw_root / item["video_relative_path"], float(item["window_start_s"]), float(item["window_end_s"]),
            )
            sheets = _write_sheets(frames, example_dir)
            input_manifest = {
                "schema_version": "playground-soccermaster-vlm-example-input-v1",
                "example_id": example_id,
                "labels_present": False,
                "visual_only": True,
                "audio_used": False,
                "frame_count": FRAME_COUNT,
                "contact_sheets": [{"name": path.name, "sha256": sha256_file(path)} for path in sheets],
            }
            input_manifest_path = example_dir / "input-manifest.json"
            _write_json(input_manifest_path, input_manifest)
            content: list[dict[str, Any]] = [{"type": "text", "text": _prompt()}]
            content.extend({"type": "image_url", "image_url": {"url": _data_url(path)}} for path in sheets)
            payload = {
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": content}],
                "temperature": 0,
                "max_tokens": 1400,
                "response_format": _response_format(),
            }
            request_record = {
                "model": MODEL_ID,
                "prompt": _prompt(),
                "prompt_sha256": _prompt_sha256(),
                "response_format": _response_format(),
                "image_inputs": input_manifest["contact_sheets"],
                "temperature": 0,
                "max_tokens": 1400,
                "endpoint_boundary": "loopback only",
            }
            request_path = example_dir / "request.json"
            _write_json(request_path, request_record)
            request_started = time.perf_counter()
            raw = _loopback_json(ENDPOINT + "/chat/completions", payload=payload, timeout=240)
            elapsed_ms = (time.perf_counter() - request_started) * 1000.0
            raw_path = example_dir / "raw-response.json"
            _write_json(raw_path, raw)
            prediction = _validate_prediction(_parse_content(raw), example_id, raw.get("model"))
            _write_json(prediction_path, prediction)
            per_receipt = {
                "schema_version": RUN_RECEIPT_SCHEMA,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "ordinal": ordinal,
                "example_id": example_id,
                "model_requested": MODEL_ID,
                "model_reported": raw.get("model"),
                "endpoint_boundary": "Only the configured loopback OpenAI-compatible endpoint was contacted.",
                "elapsed_ms": elapsed_ms,
                "input_manifest_sha256": sha256_file(input_manifest_path),
                "request_sha256": sha256_file(request_path),
                "raw_response_sha256": sha256_file(raw_path),
                "prediction_sha256": sha256_file(prediction_path),
                "prompt_sha256": _prompt_sha256(),
                "response_format_sha256": _schema_sha256(),
            }
            _write_json(per_receipt_path, per_receipt)
            successes.append(prediction)
            latencies.append(elapsed_ms)
        except Exception as exc:
            failure = {
                "example_id": example_id,
                "ordinal": ordinal,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            failures.append(failure)
            _write_json(example_dir / "failure.json", failure)
    _write_jsonl(private_run_dir / "predictions.jsonl", successes)
    _write_json(private_run_dir / "failures.json", failures)
    raw_index_rows: list[dict[str, Any]] = []
    for item in frozen["examples"]:
        example_id = item["example_id"]
        example_dir = private_run_dir / example_id
        per_receipt_path = example_dir / "receipt.json"
        failure_path = example_dir / "failure.json"
        if per_receipt_path.is_file():
            per_receipt = _read_json(per_receipt_path)
            raw_index_rows.append({
                "example_id": example_id,
                "status": "valid_response",
                "receipt_sha256": sha256_file(per_receipt_path),
                "raw_response_sha256": per_receipt["raw_response_sha256"],
                "prediction_sha256": per_receipt["prediction_sha256"],
            })
        elif failure_path.is_file():
            raw_index_rows.append({
                "example_id": example_id,
                "status": "failure",
                "failure_sha256": sha256_file(failure_path),
            })
        else:
            raise RuntimeError(f"VLM run lacks a terminal record for {example_id}")
    raw_index_path = private_run_dir / "raw-response-index.jsonl"
    _write_jsonl(raw_index_path, raw_index_rows)
    wall_clock_this_invocation = time.perf_counter() - started
    accumulated_model_request_seconds = sum(latencies) / 1000.0
    run_receipt = {
        "schema_version": "playground-soccermaster-vlm-batch-receipt-v1",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not failures else "complete_with_failures",
        "frozen_input_count": len(frozen["examples"]),
        "valid_response_count": len(successes),
        "failure_count": len(failures),
        "denominator": len(frozen["examples"]),
        "elapsed_seconds": accumulated_model_request_seconds,
        "wall_clock_this_invocation_seconds": wall_clock_this_invocation,
        "resumed_verified_response_count": reused_verified_responses,
        "latency_ms": {
            "minimum": min(latencies) if latencies else None,
            "median": float(np.median(latencies)) if latencies else None,
            "maximum": max(latencies) if latencies else None,
            "mean": float(np.mean(latencies)) if latencies else None,
        },
        "model_requested": MODEL_ID,
        "served_model_ids_before_run": served_ids,
        "runtime_receipt_sha256": sha256_file(runtime_receipt_path),
        "frozen_inputs_sha256": sha256_file(frozen_inputs_path),
        "subset_receipt_sha256": sha256_file(subset_receipt_path),
        "predictions_sha256": sha256_file(private_run_dir / "predictions.jsonl"),
        "failures_sha256": sha256_file(private_run_dir / "failures.json"),
        "raw_response_index_sha256": sha256_file(raw_index_path),
        "prompt_sha256": _prompt_sha256(),
        "response_format_sha256": _schema_sha256(),
        "labels_loaded_during_inference": False,
        "audio_used": False,
        "performance_claim_allowed": False,
    }
    _write_json(public_run_receipt_path, run_receipt)
    return run_receipt


def score(
    *, frozen_inputs_path: Path, sealed_labels_path: Path, subset_receipt_path: Path,
    private_run_dir: Path, public_run_receipt_path: Path, output_dir: Path,
) -> dict[str, Any]:
    frozen = _read_json(frozen_inputs_path)
    labels_record = _read_json(sealed_labels_path)
    subset = _read_json(subset_receipt_path)
    run_receipt = _read_json(public_run_receipt_path)
    if sha256_file(frozen_inputs_path) != subset.get("inputs_sha256") or sha256_file(sealed_labels_path) != subset.get("sealed_labels_sha256"):
        raise ValueError("frozen VLM input/label receipt mismatch")
    if run_receipt.get("frozen_inputs_sha256") != sha256_file(frozen_inputs_path):
        raise ValueError("VLM run is not bound to frozen inputs")
    input_ids = [row["example_id"] for row in frozen["examples"]]
    labels = {row["example_id"]: row["class_name"] for row in labels_record["labels"]}
    if set(input_ids) != set(labels):
        raise ValueError("sealed-label join keys do not match frozen inputs")
    predictions = {
        row["example_id"]: row
        for row in [json.loads(line) for line in (private_run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    }
    class_index = {name: index for index, name in enumerate(CLASS_NAMES)}
    y_true = np.asarray([class_index[labels[example_id]] for example_id in input_ids], dtype=np.int64)
    probability = np.zeros((len(input_ids), len(CLASS_NAMES)), dtype=np.float32)
    scored_rows: list[dict[str, Any]] = []
    valid = 0
    abstentions = 0
    detail_nonempty = 0
    evidence_compliant = 0
    for index, example_id in enumerate(input_ids):
        prediction = predictions.get(example_id)
        truth = labels[example_id]
        if prediction is None:
            predicted = "invalid_or_failed_response"
            correct = False
            abstained = False
            confidence = 0.0
            evidence = []
        else:
            valid += 1
            abstained = bool(prediction["abstained"])
            if abstained:
                abstentions += 1
                predicted = "insufficient_visual_evidence"
                correct = False
            else:
                predicted = prediction["event_class"]
                probability[index, class_index[predicted]] = 1.0
                correct = predicted == truth
                if prediction["evidence_frame_indices"]:
                    evidence_compliant += 1
            confidence = float(prediction["confidence"])
            evidence = prediction["evidence_frame_indices"]
            if prediction["observable_summary"].strip():
                detail_nonempty += 1
        scored_rows.append({
            "schema_version": "playground-soccermaster-vlm-scored-example-v1",
            "example_id": example_id,
            "ground_truth_class": truth,
            "predicted_class": predicted,
            "confidence": confidence,
            "abstained": abstained,
            "correct": correct,
            "evidence_frame_indices": evidence,
        })
    # Invalid/abstained rows remain all-zero and argmax to background, so compute
    # direct exact accuracy separately while using a background prediction only
    # for the fixed-shape macro-F1 contract; both numbers are explicitly named.
    direct_accuracy = sum(row["correct"] for row in scored_rows) / len(scored_rows)
    fixed_metrics = classification_metrics(y_true, probability)
    non_abstained = [row for row in scored_rows if row["predicted_class"] in CLASS_NAMES]
    direct_correct = sum(row["correct"] for row in scored_rows)
    non_abstained_correct = sum(row["correct"] for row in non_abstained)
    truth_counts = Counter(labels.values())
    majority_class, majority_count = max(truth_counts.items(), key=lambda item: (item[1], -CLASS_NAMES.index(item[0])))
    prediction_counts = Counter(row["predicted_class"] for row in scored_rows)
    metrics = {
        "schema_version": EVALUATION_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_boundary": "Frozen, label-centered, silent held-out test windows; labels joined only after inference. This is event classification, not dense spotting.",
        "denominator": len(input_ids),
        "valid_response_count": valid,
        "failure_count": len(input_ids) - valid,
        "valid_response_rate": valid / len(input_ids),
        "abstention_count": abstentions,
        "abstention_rate_over_valid": abstentions / valid if valid else 0.0,
        "exact_accuracy_counting_abstentions_and_failures_as_wrong": direct_accuracy,
        "exact_correct_count": direct_correct,
        "exact_accuracy_wilson_95_interval": _wilson_interval(direct_correct, len(scored_rows)),
        "non_abstained_count": len(non_abstained),
        "non_abstained_accuracy": non_abstained_correct / len(non_abstained) if non_abstained else 0.0,
        "non_abstained_accuracy_wilson_95_interval": _wilson_interval(non_abstained_correct, len(non_abstained)) if non_abstained else None,
        "stratified_subset_majority_baseline": {
            "class_name": majority_class,
            "correct_count": majority_count,
            "accuracy": majority_count / len(scored_rows),
        },
        "predicted_class_counts_including_abstention_and_failure": dict(sorted(prediction_counts.items())),
        "forced_background_confusion_metrics_for_fixed_14_class_shape": fixed_metrics,
        "evidence_nonempty_rate_over_non_abstained": evidence_compliant / len(non_abstained) if non_abstained else 0.0,
        "observable_summary_nonempty_rate_over_valid": detail_nonempty / valid if valid else 0.0,
        "detailed_claim_factuality_evaluated": False,
        "detailed_claims_safe_for_coach_search": False,
        "detail_warning": "Non-empty VLM prose is not evidence of correctness; player, trajectory, outcome, and tactical detail require separate human annotation and entailment scoring.",
        "class_counts": subset["class_counts"],
        "labels_sealed_until_scoring": True,
        "audio_used": False,
        "candidate_discovery_evaluated": False,
        "performance_claim_allowed": False,
        "reason": "Small stratified subset from two held-out games with label-centered candidates; no calibration or coaching validation.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    scored_path = output_dir / "scored-predictions.jsonl"
    metrics_path = output_dir / "evaluation.json"
    _write_jsonl(scored_path, scored_rows)
    _write_json(metrics_path, metrics)
    package_receipt = {
        "schema_version": "playground-soccermaster-vlm-evaluation-package-v1",
        "generated_at": metrics["generated_at"],
        "status": "scored",
        "artifacts": [
            {"name": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in (scored_path, metrics_path)
        ],
        "bindings": {
            "frozen_inputs_sha256": sha256_file(frozen_inputs_path),
            "sealed_labels_sha256": sha256_file(sealed_labels_path),
            "subset_receipt_sha256": sha256_file(subset_receipt_path),
            "run_receipt_sha256": sha256_file(public_run_receipt_path),
        },
        "raw_response_location": "data/private/soccermaster-scale-v1/vlm-eval/run-v1",
        "performance_claim_allowed": False,
    }
    _write_json(output_dir / "package-receipt.json", package_receipt)
    return metrics


def verify_evaluation(
    *, frozen_inputs_path: Path, sealed_labels_path: Path, subset_receipt_path: Path,
    private_run_dir: Path, public_run_receipt_path: Path, output_dir: Path,
) -> dict[str, Any]:
    subset = _read_json(subset_receipt_path)
    run = _read_json(public_run_receipt_path)
    package = _read_json(output_dir / "package-receipt.json")
    checks = {
        "inputs_hash": sha256_file(frozen_inputs_path) == subset.get("inputs_sha256"),
        "labels_hash": sha256_file(sealed_labels_path) == subset.get("sealed_labels_sha256"),
        "labels_not_loaded_inference": run.get("labels_loaded_during_inference") is False,
        "visual_only": run.get("audio_used") is False,
        "denominator_consistent": run.get("frozen_input_count") == subset.get("input_count"),
        "predictions_hash": sha256_file(private_run_dir / "predictions.jsonl") == run.get("predictions_sha256"),
        "failures_hash": sha256_file(private_run_dir / "failures.json") == run.get("failures_sha256"),
        "raw_response_index_hash": sha256_file(private_run_dir / "raw-response-index.jsonl") == run.get("raw_response_index_sha256"),
        "prompt_hash": run.get("prompt_sha256") == subset.get("prompt_sha256") == _prompt_sha256(),
        "schema_hash": run.get("response_format_sha256") == subset.get("response_format_sha256") == _schema_sha256(),
    }
    artifacts = {row["name"]: row for row in package.get("artifacts", [])}
    for name in ("scored-predictions.jsonl", "evaluation.json"):
        path = output_dir / name
        item = artifacts.get(name, {})
        checks[f"artifact_{name}"] = path.is_file() and path.stat().st_size == item.get("bytes") and sha256_file(path) == item.get("sha256")
    metrics = _read_json(output_dir / "evaluation.json")
    scored = [json.loads(line) for line in (output_dir / "scored-predictions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    checks["scored_count"] = len(scored) == metrics.get("denominator") == subset.get("input_count")
    checks["direct_accuracy"] = abs(float(metrics["exact_accuracy_counting_abstentions_and_failures_as_wrong"]) - sum(row["correct"] for row in scored) / len(scored)) < 1e-12
    raw_index = [json.loads(line) for line in (private_run_dir / "raw-response-index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    checks["raw_response_index_count"] = len(raw_index) == subset.get("input_count")
    checks["raw_response_hashes"] = all(
        (
            row["status"] == "valid_response"
            and (private_run_dir / row["example_id"] / "raw-response.json").is_file()
            and sha256_file(private_run_dir / row["example_id"] / "raw-response.json") == row["raw_response_sha256"]
        )
        or (
            row["status"] == "failure"
            and (private_run_dir / row["example_id"] / "failure.json").is_file()
            and sha256_file(private_run_dir / row["example_id"] / "failure.json") == row["failure_sha256"]
        )
        for row in raw_index
    )
    if not all(checks.values()):
        raise ValueError("VLM evaluation verification failed: " + ",".join(key for key, value in checks.items() if not value))
    return {"status": "pass", "checks": checks, "denominator": len(scored), "exact_accuracy": metrics["exact_accuracy_counting_abstentions_and_failures_as_wrong"]}
