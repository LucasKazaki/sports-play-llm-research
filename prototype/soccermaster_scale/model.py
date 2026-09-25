"""Frozen-image-feature soccer event probe with reproducible training/evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from .manifest import load_examples, sha256_file
from .reports import build_report, validate_report
from .taxonomy import CLASS_NAMES


BACKBONE_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "mobilenet/model/mobilenetv2-12.onnx"
)
BACKBONE_DOCS = "https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet"
BACKBONE_RECEIPT_SCHEMA = "playground-soccermaster-backbone-receipt-v1"
FEATURE_INDEX_SCHEMA = "playground-soccermaster-feature-index-v1"
PACKAGE_RECEIPT_SCHEMA = "playground-soccermaster-model-package-receipt-v1"
MODEL_CONFIG_SCHEMA = "playground-soccermaster-model-config-v1"
PREDICTION_SCHEMA = "playground-soccermaster-prediction-v1"


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_backbone(*, output_path: Path, receipt_path: Path) -> dict[str, Any]:
    if output_path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema_version") == BACKBONE_RECEIPT_SCHEMA and sha256_file(output_path) == receipt.get("sha256"):
            FrozenMobileNet(output_path)
            return receipt
        raise ValueError("existing soccer backbone or receipt failed closed verification")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.download")
    request = urllib.request.Request(BACKBONE_URL, headers={"User-Agent": "PlayGround-SoccerMaster-Research/1.0"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as sink:
        final_url = response.geturl()
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            sink.write(block)
    if temporary.stat().st_size < 1_000_000:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("downloaded soccer backbone is unexpectedly small")
    FrozenMobileNet(temporary)
    temporary.replace(output_path)
    receipt = {
        "schema_version": BACKBONE_RECEIPT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": "ONNX Model Zoo MobileNetV2-1.0-fp32 opset 12",
        "origin": "ImageNet-pretrained frozen image classifier; not trained by this project",
        "requested_url": BACKBONE_URL,
        "final_url": final_url,
        "documentation_url": BACKBONE_DOCS,
        "sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
        "download_seconds": time.perf_counter() - started,
        "license_note": "ONNX Model Zoo repository/model provenance; review upstream license before redistributing weights.",
    }
    _write_json(receipt_path, receipt)
    return receipt


class FrozenMobileNet:
    """Independent SoccerMaster wrapper around a frozen ONNX image backbone."""

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(8, os.cpu_count() or 1))
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) < 1:
            raise ValueError("unexpected MobileNetV2 ONNX input/output contract")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name
        self.input_shape = inputs[0].shape

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_AREA)
        crop = resized[16:240, 16:240]
        values = crop.astype(np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        values = (values - mean) / std
        return np.transpose(values, (2, 0, 1))

    def describe(self, frames: list[np.ndarray]) -> np.ndarray:
        batch = np.stack([self._preprocess(frame) for frame in frames], axis=0)
        dynamic_batch = self.input_shape[0] in {None, "None", "batch_size", "N"} or isinstance(self.input_shape[0], str)
        if dynamic_batch:
            output = np.asarray(self.session.run([self.output_name], {self.input_name: batch})[0], dtype=np.float32)
        else:
            output = np.concatenate([
                np.asarray(self.session.run([self.output_name], {self.input_name: item[None]})[0], dtype=np.float32)
                for item in batch
            ], axis=0)
        output = output.reshape(len(frames), -1)
        if output.shape[1] != 1000 or not np.isfinite(output).all():
            raise RuntimeError(f"unexpected or non-finite MobileNet output: {output.shape}")
        return output


def _read_frames(cap: cv2.VideoCapture, times_s: list[float]) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for timestamp in times_s:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"frame decode failed at {timestamp:.3f}s")
        frames.append(frame)
    return frames


def aggregate_descriptors(descriptors: np.ndarray) -> np.ndarray:
    if descriptors.ndim != 2 or descriptors.shape[0] != 12 or descriptors.shape[1] != 1000:
        raise ValueError("expected exactly 12 x 1000 frame descriptors")
    edges = (descriptors[:3].mean(axis=0) + descriptors[-3:].mean(axis=0)) / 2.0
    center = descriptors[4:8].mean(axis=0)
    return np.concatenate([
        descriptors.mean(axis=0),
        descriptors.std(axis=0),
        descriptors.max(axis=0),
        descriptors[-1] - descriptors[0],
        center - edges,
    ]).astype(np.float32)


def extract_features(
    *, examples_path: Path, raw_root: Path, backbone_path: Path,
    feature_dir: Path, feature_index_path: Path,
) -> dict[str, Any]:
    examples = load_examples(examples_path)
    feature_dir.mkdir(parents=True, exist_ok=True)
    extractor = FrozenMobileNet(backbone_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in examples:
        if row["ground_truth"]["single_label_eligible"]:
            grouped[row["video_relative_path"]].append(row)
    started = time.perf_counter()
    extracted = 0
    reused = 0
    failures: list[dict[str, str]] = []
    for relative_path, rows in sorted(grouped.items()):
        video_path = (raw_root / relative_path).resolve()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError("could not open a manifest-bound video during feature extraction")
        try:
            for row in sorted(rows, key=lambda item: item["window_start_s"]):
                output_path = feature_dir / f"{row['example_id']}.npy"
                if output_path.is_file():
                    try:
                        cached = np.load(output_path, allow_pickle=False)
                        if cached.shape == (5000,) and cached.dtype == np.float32 and np.isfinite(cached).all():
                            reused += 1
                            continue
                    except (OSError, ValueError):
                        pass
                    output_path.unlink(missing_ok=True)
                start_s = float(row["window_start_s"])
                end_s = float(row["window_end_s"])
                times_s = [start_s + (index + 0.5) * (end_s - start_s) / 12.0 for index in range(12)]
                try:
                    frames = _read_frames(cap, times_s)
                    feature = aggregate_descriptors(extractor.describe(frames))
                    temporary = output_path.with_name(f".{output_path.name}.tmp.npy")
                    np.save(temporary, feature, allow_pickle=False)
                    temporary.replace(output_path)
                    extracted += 1
                except Exception as exc:  # persist the exact bounded failure and continue unaffected rows
                    failures.append({"example_id": row["example_id"], "error_type": type(exc).__name__, "error": str(exc)})
        finally:
            cap.release()
    if failures:
        _write_json(feature_dir.parent / "feature-failures.json", failures)
        raise RuntimeError(f"feature extraction failed for {len(failures)} examples")
    entries = []
    eligible_ids = sorted(row["example_id"] for row in examples if row["ground_truth"]["single_label_eligible"])
    for example_id in eligible_ids:
        path = feature_dir / f"{example_id}.npy"
        feature = np.load(path, allow_pickle=False)
        if feature.shape != (5000,) or feature.dtype != np.float32 or not np.isfinite(feature).all():
            raise RuntimeError(f"feature cache verification failed: {example_id}")
        entries.append({"example_id": example_id, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    index = {
        "schema_version": FEATURE_INDEX_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "example_count": len(entries),
        "feature_dimension": 5000,
        "frames_per_example": 12,
        "visual_only": True,
        "backbone_sha256": sha256_file(backbone_path),
        "examples_sha256": sha256_file(examples_path),
        "elapsed_seconds": time.perf_counter() - started,
        "newly_extracted": extracted,
        "reused_from_verified_shape_cache": reused,
        "entries": entries,
    }
    _write_json(feature_index_path, index)
    return index


def _load_matrix(examples: list[dict[str, Any]], feature_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    x = np.stack([np.load(feature_dir / f"{row['example_id']}.npy", allow_pickle=False) for row in examples]).astype(np.float32)
    lookup = {name: index for index, name in enumerate(CLASS_NAMES)}
    y = np.asarray([lookup[row["ground_truth"]["class_name"]] for row in examples], dtype=np.int64)
    return x, y


def _projection(input_dim: int, output_dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal((input_dim, output_dim), dtype=np.float32) / math.sqrt(output_dim)).astype(np.float32)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def _fit_head(
    x: np.ndarray, y: np.ndarray, *, class_count: int, learning_rate: float,
    l2: float, epochs: int, seed: int,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    counts = np.bincount(y, minlength=class_count).astype(np.float64)
    priors = (counts + 0.1) / (counts.sum() + 0.1 * class_count)
    weights = np.zeros((x.shape[1], class_count), dtype=np.float64)
    bias = np.log(priors)
    sample_weights = np.asarray([
        math.sqrt(counts.sum() / max(1.0, class_count * counts[label])) if counts[label] else 0.0
        for label in y
    ], dtype=np.float64)
    sample_weights /= sample_weights.mean()
    m_w = np.zeros_like(weights)
    v_w = np.zeros_like(weights)
    m_b = np.zeros_like(bias)
    v_b = np.zeros_like(bias)
    history: list[dict[str, float]] = []
    x64 = x.astype(np.float64)
    for epoch in range(1, epochs + 1):
        probabilities = _softmax(x64 @ weights + bias)
        onehot = np.eye(class_count, dtype=np.float64)[y]
        difference = (probabilities - onehot) * sample_weights[:, None] / len(y)
        gradient_w = x64.T @ difference + l2 * weights
        gradient_b = difference.sum(axis=0)
        m_w = 0.9 * m_w + 0.1 * gradient_w
        v_w = 0.999 * v_w + 0.001 * (gradient_w * gradient_w)
        m_b = 0.9 * m_b + 0.1 * gradient_b
        v_b = 0.999 * v_b + 0.001 * (gradient_b * gradient_b)
        correction_m = 1.0 - 0.9 ** epoch
        correction_v = 1.0 - 0.999 ** epoch
        weights -= learning_rate * (m_w / correction_m) / (np.sqrt(v_w / correction_v) + 1e-8)
        bias -= learning_rate * (m_b / correction_m) / (np.sqrt(v_b / correction_v) + 1e-8)
        if epoch == 1 or epoch % 50 == 0 or epoch == epochs:
            loss = -np.sum(sample_weights * np.log(np.maximum(probabilities[np.arange(len(y)), y], 1e-12))) / len(y)
            loss += 0.5 * l2 * float(np.sum(weights * weights))
            history.append({"epoch": float(epoch), "weighted_loss": float(loss)})
    return weights.astype(np.float32), bias.astype(np.float32), history


def _confusion(y_true: np.ndarray, y_pred: np.ndarray, class_count: int) -> np.ndarray:
    matrix = np.zeros((class_count, class_count), dtype=np.int64)
    for truth, prediction in zip(y_true, y_pred, strict=True):
        matrix[int(truth), int(prediction)] += 1
    return matrix


def classification_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = probabilities.argmax(axis=1)
    matrix = _confusion(y_true, predictions, len(CLASS_NAMES))
    per_class: dict[str, dict[str, Any]] = {}
    f1_values_all: list[float] = []
    f1_values_supported: list[float] = []
    recalls_supported: list[float] = []
    for index, name in enumerate(CLASS_NAMES):
        tp = int(matrix[index, index])
        fp = int(matrix[:, index].sum() - tp)
        fn = int(matrix[index, :].sum() - tp)
        support = int(matrix[index, :].sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values_all.append(f1)
        if support:
            f1_values_supported.append(f1)
            recalls_supported.append(recall)
        per_class[name] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    top3 = np.argsort(probabilities, axis=1)[:, -3:]
    top3_accuracy = float(np.mean([truth in row for truth, row in zip(y_true, top3, strict=True)]))
    accuracy = float(np.mean(predictions == y_true))
    n = len(y_true)
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (accuracy + z * z / (2 * n)) / denominator
    half_width = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / denominator
    return {
        "n": n,
        "accuracy": accuracy,
        "top3_accuracy": top3_accuracy,
        "macro_f1_all_14_taxonomy_classes": float(np.mean(f1_values_all)),
        "macro_f1_supported_classes": float(np.mean(f1_values_supported)) if f1_values_supported else 0.0,
        "balanced_accuracy_supported_classes": float(np.mean(recalls_supported)) if recalls_supported else 0.0,
        "wilson_95_accuracy_interval": [max(0.0, center - half_width), min(1.0, center + half_width)],
        "confusion_matrix": matrix.tolist(),
        "class_order": list(CLASS_NAMES),
        "per_class": per_class,
    }


def _select_abstention_threshold(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    confidence = probabilities.max(axis=1)
    prediction = probabilities.argmax(axis=1)
    candidates = [round(value, 2) for value in np.arange(0.0, 0.91, 0.05)]
    records = []
    for threshold in candidates:
        selected = confidence >= threshold
        coverage = float(np.mean(selected))
        accuracy = float(np.mean(prediction[selected] == y_true[selected])) if selected.any() else 0.0
        records.append({"threshold": threshold, "coverage": coverage, "selective_accuracy": accuracy})
    feasible = [row for row in records if row["coverage"] >= 0.20]
    chosen = max(feasible, key=lambda row: (row["selective_accuracy"], row["coverage"], -row["threshold"]))
    return {"selection_split": "valid", "minimum_coverage": 0.20, "chosen": chosen, "candidates": records}


def _select_hyperparameters(
    x_train: np.ndarray, y_train: np.ndarray, x_valid: np.ndarray, y_valid: np.ndarray,
    *, epochs: int, seed: int,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, list[dict[str, float]], list[dict[str, Any]]]:
    candidates = [
        {"learning_rate": 0.03, "l2": 1e-4},
        {"learning_rate": 0.01, "l2": 1e-4},
        {"learning_rate": 0.03, "l2": 1e-3},
        {"learning_rate": 0.01, "l2": 1e-3},
        {"learning_rate": 0.01, "l2": 1e-2},
    ]
    trials: list[dict[str, Any]] = []
    best: tuple[float, float, int] | None = None
    best_payload = None
    for ordinal, settings in enumerate(candidates):
        weights, bias, history = _fit_head(
            x_train, y_train, class_count=len(CLASS_NAMES),
            learning_rate=settings["learning_rate"], l2=settings["l2"],
            epochs=epochs, seed=seed + ordinal,
        )
        metrics = classification_metrics(y_valid, _softmax(x_valid @ weights + bias))
        trial = {**settings, "epochs": epochs, "valid_metrics": metrics, "loss_history": history}
        trials.append(trial)
        score = (
            metrics["macro_f1_supported_classes"],
            metrics["balanced_accuracy_supported_classes"],
            ordinal * -1,
        )
        if best is None or score > best:
            best = score
            best_payload = (settings, weights, bias, history)
    assert best_payload is not None
    settings, weights, bias, history = best_payload
    return settings, weights, bias, history, trials


def _majority_baseline(y_train: np.ndarray, y_test: np.ndarray) -> dict[str, Any]:
    majority = int(np.bincount(y_train, minlength=len(CLASS_NAMES)).argmax())
    probabilities = np.zeros((len(y_test), len(CLASS_NAMES)), dtype=np.float32)
    probabilities[:, majority] = 1.0
    return {"majority_class": CLASS_NAMES[majority], "metrics": classification_metrics(y_test, probabilities)}


def train_and_evaluate(
    *, examples_path: Path, feature_dir: Path, feature_index_path: Path,
    backbone_receipt_path: Path, corpus_receipt_path: Path,
    output_dir: Path, projection_dim: int = 256, projection_seed: int = 20260827,
    epochs: int = 350,
) -> dict[str, Any]:
    started_wall = datetime.now(timezone.utc)
    started = time.perf_counter()
    examples_all = [row for row in load_examples(examples_path) if row["ground_truth"]["single_label_eligible"]]
    by_split = {split: [row for row in examples_all if row["split"] == split] for split in ("train", "valid", "test")}
    if any(not by_split[split] for split in by_split):
        raise ValueError("training requires non-empty train/valid/test eligible examples")
    game_sets = {split: {row["game_id"] for row in rows} for split, rows in by_split.items()}
    if game_sets["train"] & game_sets["valid"] or game_sets["train"] & game_sets["test"] or game_sets["valid"] & game_sets["test"]:
        raise ValueError("game leakage across training splits")
    feature_index = json.loads(feature_index_path.read_text(encoding="utf-8"))
    if feature_index.get("schema_version") != FEATURE_INDEX_SCHEMA or feature_index.get("examples_sha256") != sha256_file(examples_path):
        raise ValueError("feature index is not bound to the frozen examples")
    indexed = {item["example_id"]: item for item in feature_index.get("entries", [])}
    for row in examples_all:
        item = indexed.get(row["example_id"])
        path = feature_dir / f"{row['example_id']}.npy"
        if not item or not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"feature cache receipt mismatch: {row['example_id']}")

    matrices: dict[str, np.ndarray] = {}
    labels: dict[str, np.ndarray] = {}
    for split in ("train", "valid", "test"):
        matrices[split], labels[split] = _load_matrix(by_split[split], feature_dir)
    mean = matrices["train"].mean(axis=0)
    scale = matrices["train"].std(axis=0)
    scale[scale < 1e-6] = 1.0
    projection = _projection(matrices["train"].shape[1], projection_dim, projection_seed)
    projected = {
        split: (((matrix - mean) / scale) @ projection).astype(np.float32)
        for split, matrix in matrices.items()
    }
    projected_mean = projected["train"].mean(axis=0)
    projected_scale = projected["train"].std(axis=0)
    projected_scale[projected_scale < 1e-6] = 1.0
    normalized = {split: ((value - projected_mean) / projected_scale).astype(np.float32) for split, value in projected.items()}
    selection, weights, bias, history, trials = _select_hyperparameters(
        normalized["train"], labels["train"], normalized["valid"], labels["valid"],
        epochs=epochs, seed=projection_seed,
    )
    probabilities = {split: _softmax(normalized[split] @ weights + bias).astype(np.float32) for split in normalized}
    valid_threshold = _select_abstention_threshold(labels["valid"], probabilities["valid"])
    threshold = float(valid_threshold["chosen"]["threshold"])
    test_metrics = classification_metrics(labels["test"], probabilities["test"])
    test_confidence = probabilities["test"].max(axis=1)
    test_prediction = probabilities["test"].argmax(axis=1)
    selected_test = test_confidence >= threshold
    selective = {
        "threshold": threshold,
        "coverage": float(np.mean(selected_test)),
        "selected_n": int(selected_test.sum()),
        "selective_accuracy": float(np.mean(test_prediction[selected_test] == labels["test"][selected_test])) if selected_test.any() else 0.0,
    }
    baseline = _majority_baseline(labels["train"], labels["test"])
    per_game: dict[str, dict[str, Any]] = {}
    for game_id in sorted(game_sets["test"]):
        indexes = np.asarray([index for index, row in enumerate(by_split["test"]) if row["game_id"] == game_id])
        per_game[game_id] = classification_metrics(labels["test"][indexes], probabilities["test"][indexes])

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.npz"
    np.savez_compressed(
        checkpoint_path,
        weights=weights, bias=bias, raw_mean=mean.astype(np.float32), raw_scale=scale.astype(np.float32),
        projected_mean=projected_mean.astype(np.float32), projected_scale=projected_scale.astype(np.float32),
    )
    checkpoint_hash = sha256_file(checkpoint_path)
    generation = hashlib.sha256((checkpoint_hash + sha256_file(examples_path) + sha256_file(feature_index_path)).encode("ascii")).hexdigest()[:24]
    prediction_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for row, probability, truth in zip(by_split["test"], probabilities["test"], labels["test"], strict=True):
        order = np.argsort(probability)[::-1][:5]
        top_k = [{"class_name": CLASS_NAMES[int(index)], "probability": float(probability[index])} for index in order]
        predicted = int(order[0])
        prediction_rows.append({
            "schema_version": PREDICTION_SCHEMA,
            "model_generation": generation,
            "example_id": row["example_id"],
            "game_id": row["game_id"],
            "split": "test",
            "ground_truth_class": CLASS_NAMES[int(truth)],
            "predicted_class": CLASS_NAMES[predicted],
            "confidence": float(probability[predicted]),
            "top_k": top_k,
            "correct": predicted == int(truth),
            "abstained": float(probability[predicted]) < threshold,
            "candidate_time_s": float(row["candidate_time_s"]),
        })
        report = build_report(
            example=row, predicted_class=CLASS_NAMES[predicted], confidence=float(probability[predicted]),
            top_k=top_k, abstention_threshold=threshold, model_generation=generation,
        )
        validate_report(report)
        report_rows.append(report)
    predictions_path = output_dir / "test-predictions.jsonl"
    reports_path = output_dir / "test-event-reports.jsonl"
    _write_jsonl(predictions_path, prediction_rows)
    _write_jsonl(reports_path, report_rows)

    elapsed = time.perf_counter() - started
    metrics = {
        "schema_version": "playground-soccermaster-evaluation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_generation": generation,
        "evaluation_boundary": "Frozen test games; label-centered single-label-eligible event candidates plus deterministic background windows. Not dense spotting.",
        "test": test_metrics,
        "selective_test": selective,
        "majority_baseline": baseline,
        "per_test_game": per_game,
        "validation_abstention_selection": valid_threshold,
        "performance_claim_allowed": False,
        "reason": "Eight-game pilot with label-centered candidates is feasibility evidence, not a generalization or coaching-effect result.",
    }
    metrics_path = output_dir / "metrics.json"
    _write_json(metrics_path, metrics)
    config = {
        "schema_version": MODEL_CONFIG_SCHEMA,
        "model_generation": generation,
        "sport": "soccer",
        "architecture": {
            "frozen_backbone": "ONNX Model Zoo MobileNetV2 ImageNet 1000-score descriptors",
            "frames_per_window": 12,
            "window_s": 12.0,
            "raw_feature_dimension": 5000,
            "aggregation": ["mean", "standard_deviation", "max", "last_minus_first", "center_minus_edges"],
            "fixed_random_projection_dimension": projection_dim,
            "projection_seed": projection_seed,
            "learned_head": "class-balanced multinomial softmax",
            "class_names": list(CLASS_NAMES),
        },
        "training": {
            "train_examples": len(by_split["train"]),
            "valid_examples": len(by_split["valid"]),
            "test_examples": len(by_split["test"]),
            "train_games": len(game_sets["train"]),
            "valid_games": len(game_sets["valid"]),
            "test_games": len(game_sets["test"]),
            "hyperparameter_selection": "validation macro-F1, then validation balanced accuracy; test untouched",
            "selected": {**selection, "epochs": epochs},
            "abstention_selection": "validation-only maximum selective accuracy subject to at least 20% coverage",
            "abstention_threshold": threshold,
            "learned_parameter_count": int(weights.size + bias.size),
            "persisted_train_fit_values": int(weights.size + bias.size + mean.size + scale.size + projected_mean.size + projected_scale.size),
        },
        "bound_inputs": {
            "examples_sha256": sha256_file(examples_path),
            "feature_index_sha256": sha256_file(feature_index_path),
            "backbone_receipt_sha256": sha256_file(backbone_receipt_path),
            "corpus_receipt_sha256": sha256_file(corpus_receipt_path),
        },
        "claims": {
            "learned": ["14-way candidate-window event/background class probability"],
            "deterministic": ["window timestamps", "abstention decision", "report prose template"],
            "not_learned": ["candidate discovery", "player identity", "team identity", "field location", "trajectory", "long ball", "formation", "tactical intent"],
        },
        "code_independence": {
            "footballmaster_imported": False,
            "multisport_demo_imported": False,
            "package": "prototype.soccermaster_scale",
        },
    }
    config_path = output_dir / "model-config.json"
    _write_json(config_path, config)
    training_log = {
        "schema_version": "playground-soccermaster-training-log-v1",
        "started_at": started_wall.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "onnxruntime_provider": "CPUExecutionProvider",
        },
        "hyperparameter_trials": trials,
        "selected_loss_history": history,
    }
    training_log_path = output_dir / "training-log.json"
    _write_json(training_log_path, training_log)
    artifact_paths = [checkpoint_path, metrics_path, config_path, predictions_path, reports_path, training_log_path]
    receipt = {
        "schema_version": PACKAGE_RECEIPT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "trained_and_frozen_test_evaluated",
        "model_generation": generation,
        "artifacts": [
            {"name": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in artifact_paths
        ],
        "external_bindings": {
            "examples_sha256": sha256_file(examples_path),
            "feature_index_sha256": sha256_file(feature_index_path),
            "backbone_receipt_sha256": sha256_file(backbone_receipt_path),
            "corpus_receipt_sha256": sha256_file(corpus_receipt_path),
        },
        "split_leakage_check": {"unit": "whole_game", "pairwise_disjoint": True},
        "performance_claim_allowed": False,
    }
    receipt_path = output_dir / "package-receipt.json"
    _write_json(receipt_path, receipt)
    return {"status": receipt["status"], "model_generation": generation, "metrics": metrics, "receipt": receipt}


def _forward_from_checkpoint(raw: np.ndarray, checkpoint: Any, projection_dim: int, projection_seed: int) -> np.ndarray:
    projection = _projection(raw.shape[1], projection_dim, projection_seed)
    normalized_raw = (raw - checkpoint["raw_mean"]) / checkpoint["raw_scale"]
    projected = normalized_raw @ projection
    normalized = (projected - checkpoint["projected_mean"]) / checkpoint["projected_scale"]
    return _softmax(normalized @ checkpoint["weights"] + checkpoint["bias"])


def verify_package(
    *, output_dir: Path, examples_path: Path, feature_dir: Path,
    feature_index_path: Path, backbone_receipt_path: Path, corpus_receipt_path: Path,
) -> dict[str, Any]:
    receipt_path = output_dir / "package-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != PACKAGE_RECEIPT_SCHEMA:
        raise ValueError("unexpected SoccerMaster model package receipt")
    expected = {item["name"]: item for item in receipt.get("artifacts", [])}
    required = {
        "checkpoint.npz", "metrics.json", "model-config.json", "test-predictions.jsonl",
        "test-event-reports.jsonl", "training-log.json",
    }
    if set(expected) != required:
        raise ValueError("model package artifact set mismatch")
    for name, item in expected.items():
        path = output_dir / name
        if not path.is_file() or path.stat().st_size != item.get("bytes") or sha256_file(path) != item.get("sha256"):
            raise ValueError(f"model package artifact mismatch: {name}")
    bindings = receipt.get("external_bindings", {})
    if bindings != {
        "examples_sha256": sha256_file(examples_path),
        "feature_index_sha256": sha256_file(feature_index_path),
        "backbone_receipt_sha256": sha256_file(backbone_receipt_path),
        "corpus_receipt_sha256": sha256_file(corpus_receipt_path),
    }:
        raise ValueError("model package external bindings mismatch")
    config = json.loads((output_dir / "model-config.json").read_text(encoding="utf-8"))
    if config.get("code_independence", {}).get("footballmaster_imported") is not False:
        raise ValueError("soccer package does not attest football independence")
    examples = [row for row in load_examples(examples_path) if row["split"] == "test" and row["ground_truth"]["single_label_eligible"]]
    raw, y_true = _load_matrix(examples, feature_dir)
    with np.load(output_dir / "checkpoint.npz", allow_pickle=False) as checkpoint:
        probabilities = _forward_from_checkpoint(
            raw, checkpoint, int(config["architecture"]["fixed_random_projection_dimension"]),
            int(config["architecture"]["projection_seed"]),
        )
    predictions = _read_jsonl(output_dir / "test-predictions.jsonl")
    if [row["example_id"] for row in predictions] != [row["example_id"] for row in examples]:
        raise ValueError("frozen test prediction order/IDs mismatch")
    calculated = probabilities.argmax(axis=1)
    if any(row["predicted_class"] != CLASS_NAMES[int(value)] for row, value in zip(predictions, calculated, strict=True)):
        raise ValueError("saved predictions do not reproduce")
    if any(abs(float(row["confidence"]) - float(probabilities[index, calculated[index]])) > 1e-6 for index, row in enumerate(predictions)):
        raise ValueError("saved prediction confidence does not reproduce")
    saved_metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))["test"]
    calculated_metrics = classification_metrics(y_true, probabilities)
    for key in ("accuracy", "top3_accuracy", "macro_f1_all_14_taxonomy_classes", "macro_f1_supported_classes", "balanced_accuracy_supported_classes"):
        if abs(float(saved_metrics[key]) - float(calculated_metrics[key])) > 1e-8:
            raise ValueError(f"saved metric does not reproduce: {key}")
    reports = _read_jsonl(output_dir / "test-event-reports.jsonl")
    if len(reports) != len(examples):
        raise ValueError("test event report count mismatch")
    for report in reports:
        validate_report(report)
    return {
        "status": "pass",
        "model_generation": receipt["model_generation"],
        "test_examples": len(examples),
        "recomputed_accuracy": calculated_metrics["accuracy"],
        "artifact_hashes_verified": len(required),
        "reports_verified": len(reports),
    }
