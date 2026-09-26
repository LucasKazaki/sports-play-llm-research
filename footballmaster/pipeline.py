"""Train and evaluate the rights-gated, American-football-only pilot.

This is a deliberately bounded visual-probe experiment rather than foundation-model pretraining.  It
uses a frozen ImageNet MobileNetV2 ONNX network to describe uniformly sampled
frames, deterministic temporal pooling, a train-only PCA projection, and an
actually learned regularized softmax probe.  The pilot target is the binary
``is_touchdown`` label derived from a frozen mapping of source-supported weak
event tags.  Fine-grained tags remain searchable metadata; they are not model
predictions.

The module fails closed on media hash drift, missing local-research/training
permission, source leakage across splits, or an evaluation target not observed
in training.  It never calls a hosted service and never writes a detailed VLM
report.  The exported search index marks exactly which fields are learned,
source-authored, or deterministically projected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import cv2
import numpy as np

from .config import FOOTBALL_CONFIG
from .schema import ARCHITECTURE_SCOPE, validate_model_card


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLES = PROJECT_ROOT / "data" / "public" / "footballmaster" / "examples.jsonl"
DEFAULT_SOURCES = PROJECT_ROOT / "data" / "public" / "footballmaster" / "source-manifest.json"
DEFAULT_BACKBONE = PROJECT_ROOT / "artifacts" / "footballmaster" / "backbones" / "mobilenetv2-12.onnx"
DEFAULT_BACKBONE_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "mobilenet/model/mobilenetv2-12.onnx"
)

EXAMPLES_SCHEMA_VERSION = "footballmaster-examples-jsonl-v1"
MODEL_SCHEMA_VERSION = "footballmaster-pilot-model-v1"
METRICS_SCHEMA_VERSION = "footballmaster-pilot-metrics-v1"
PREDICTION_SCHEMA_VERSION = "footballmaster-pilot-prediction-v1"
INDEX_SCHEMA_VERSION = "footballmaster-search-index-v1"
BACKBONE_RECEIPT_SCHEMA_VERSION = "footballmaster-frozen-backbone-receipt-v1"

TARGET_NAME = FOOTBALL_CONFIG.target_name
POSITIVE_FINE_LABELS = FOOTBALL_CONFIG.positive_fine_labels
NEGATIVE_FINE_LABELS = FOOTBALL_CONFIG.negative_fine_labels
SUPPORTED_FINE_LABELS = FOOTBALL_CONFIG.supported_fine_labels
TARGET_CLASSES = FOOTBALL_CONFIG.target_classes
SPLITS = FOOTBALL_CONFIG.splits
RIGHTS_ALLOWED = FOOTBALL_CONFIG.rights_allowed
LABEL_PROVENANCE = {
    "source_description_weak_label",
    "commons_source_description_weak_label_plus_contact_sheet_plausibility_check",
    "manual_visual_review",
    "derived",
}
EXAMPLE_KEYS = {
    "clip_id", "source_id", "split", "project_relative_media_path", "sha256",
    "start_seconds", "end_seconds", "duration_seconds", "labels", "label_provenance",
    "adjudication_status", "source_page_url", "license_spdxish", "rights_disposition",
    "training_allowed", "redistribution_allowed", "audio_in_model", "is_touchdown", "notes",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temporary:
            json.dump(value, temporary, ensure_ascii=False, sort_keys=True, indent=2)
            temporary.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temporary:
            for row in rows:
                temporary.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def target_from_labels(labels: Sequence[str]) -> int:
    """Map frozen weak event tags to the one evaluated binary target."""
    values = set(labels)
    unsupported = values - SUPPORTED_FINE_LABELS
    if unsupported:
        raise ValueError(f"unsupported fine labels for {TARGET_NAME}: {sorted(unsupported)}")
    positive = bool(values & POSITIVE_FINE_LABELS)
    negative = bool(values & NEGATIVE_FINE_LABELS)
    if positive == negative:
        raise ValueError("labels must map unambiguously to exactly one is_touchdown target")
    return int(positive)


@dataclass(frozen=True)
class Example:
    clip_id: str
    source_id: str
    split: str
    media_path: Path
    project_relative_media_path: str
    sha256: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    labels: tuple[str, ...]
    label_provenance: str
    adjudication_status: str
    source_page_url: str
    license_spdxish: str
    license_name: str
    license_url: str
    creator: str
    creator_url: str
    license_conditions: tuple[str, ...]
    rights_disposition: str
    training_allowed: bool
    redistribution_allowed: bool
    notes: str
    target: int

    def safe_record(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "source_id": self.source_id,
            "split": self.split,
            "project_relative_media_path": self.project_relative_media_path,
            "sha256": self.sha256,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "labels": list(self.labels),
            "label_provenance": self.label_provenance,
            "adjudication_status": self.adjudication_status,
            "source_page_url": self.source_page_url,
            "license_spdxish": self.license_spdxish,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "creator": self.creator,
            "creator_url": self.creator_url,
            "license_conditions": list(self.license_conditions),
            "rights_disposition": self.rights_disposition,
            "training_allowed": self.training_allowed,
            "redistribution_allowed": self.redistribution_allowed,
            "notes": self.notes,
            "target_name": TARGET_NAME,
            "target": self.target,
            "target_label": TARGET_CLASSES[self.target],
        }


def _load_source_assets(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("source manifest must be a JSON object")
    assets: Any = raw.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("source manifest must contain a non-empty assets list")
    by_id: dict[str, dict[str, Any]] = {}
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            raise ValueError(f"source manifest assets[{index}] must be an object")
        asset_id = _text(asset.get("asset_id"), f"assets[{index}].asset_id")
        _text(asset.get("source_id"), f"assets[{index}].source_id")
        if asset_id in by_id:
            raise ValueError("source manifest asset_id values must be unique")
        by_id[asset_id] = asset
    return by_id, raw, sha256_file(path)


def load_examples(
    examples_path: Path = DEFAULT_EXAMPLES,
    source_manifest_path: Path = DEFAULT_SOURCES,
    *,
    project_root: Path = PROJECT_ROOT,
    require_media: bool = True,
) -> tuple[list[Example], dict[str, Any]]:
    """Load and fully gate the rights/source-held-out training examples."""
    if not examples_path.is_file():
        raise FileNotFoundError(examples_path)
    source_assets, source_manifest, source_manifest_sha = _load_source_assets(source_manifest_path)
    source_ids = {_text(asset.get("source_id"), "asset.source_id") for asset in source_assets.values()}
    root = project_root.resolve()
    media_root = (root / "data" / "public" / "footballmaster" / "media").resolve()
    examples: list[Example] = []
    for line_number, line in enumerate(examples_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"examples line {line_number} is not valid JSON") from exc
        if not isinstance(row, dict) or set(row) != EXAMPLE_KEYS:
            raise ValueError(f"examples line {line_number} keys must exactly equal the v1 contract")
        clip_id = _text(row["clip_id"], f"line {line_number}.clip_id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,119}", clip_id):
            raise ValueError(f"line {line_number}.clip_id is not a safe opaque identifier")
        asset = source_assets.get(clip_id)
        if asset is None:
            raise ValueError(f"line {line_number}.clip_id is absent from source-manifest assets")
        source_id = _text(row["source_id"], f"line {line_number}.source_id")
        if source_id not in source_ids:
            raise ValueError(f"line {line_number}.source_id is absent from the source manifest")
        split = _text(row["split"], f"line {line_number}.split")
        if split not in SPLITS:
            raise ValueError(f"line {line_number}.split is unsupported")
        relative = Path(_text(row["project_relative_media_path"], f"line {line_number}.project_relative_media_path"))
        if relative.is_absolute():
            raise ValueError("media path must be project-relative")
        media_path = (root / relative).resolve()
        try:
            media_path.relative_to(media_root)
        except ValueError as exc:
            raise ValueError("media path must remain under data/public/footballmaster/media") from exc
        digest = _text(row["sha256"], f"line {line_number}.sha256").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"line {line_number}.sha256 must be a lowercase SHA-256")
        start = _finite(row["start_seconds"], f"line {line_number}.start_seconds")
        end = _finite(row["end_seconds"], f"line {line_number}.end_seconds")
        duration = _finite(row["duration_seconds"], f"line {line_number}.duration_seconds")
        if start < 0 or end <= start or duration <= 0 or abs((end - start) - duration) > 0.05:
            raise ValueError(f"line {line_number} has inconsistent temporal bounds")
        labels_raw = row["labels"]
        if not isinstance(labels_raw, list) or not labels_raw:
            raise ValueError(f"line {line_number}.labels must be a non-empty list")
        labels = tuple(_text(item, f"line {line_number}.labels") for item in labels_raw)
        if len(set(labels)) != len(labels):
            raise ValueError(f"line {line_number}.labels contains duplicates")
        target = target_from_labels(labels)
        if not isinstance(row["is_touchdown"], bool) or int(row["is_touchdown"]) != target:
            raise ValueError(f"line {line_number}.is_touchdown disagrees with the frozen label mapping")
        provenance = _text(row["label_provenance"], f"line {line_number}.label_provenance")
        if provenance not in LABEL_PROVENANCE:
            raise ValueError(f"line {line_number}.label_provenance is unsupported")
        source_url = _text(row["source_page_url"], f"line {line_number}.source_page_url")
        parsed_url = urlparse(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"line {line_number}.source_page_url must be HTTP(S)")
        license_name = _text(asset.get("license_name"), f"asset {clip_id}.license_name")
        license_url = _text(asset.get("license_url"), f"asset {clip_id}.license_url")
        creator = _text(asset.get("creator"), f"asset {clip_id}.creator")
        creator_url = _text(asset.get("creator_url"), f"asset {clip_id}.creator_url")
        for field, value in (("license_url", license_url), ("creator_url", creator_url)):
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"asset {clip_id}.{field} must be HTTP(S)")
        conditions_raw = asset.get("conditions")
        if not isinstance(conditions_raw, list) or not conditions_raw:
            raise ValueError(f"asset {clip_id}.conditions must be a non-empty list")
        conditions = tuple(_text(value, f"asset {clip_id}.conditions") for value in conditions_raw)
        rights = _text(row["rights_disposition"], f"line {line_number}.rights_disposition")
        if rights != RIGHTS_ALLOWED or row["training_allowed"] is not True:
            raise PermissionError(f"{clip_id} is not approved for local model training")
        if not isinstance(row["redistribution_allowed"], bool):
            raise ValueError(f"line {line_number}.redistribution_allowed must be boolean")
        if row["audio_in_model"] is not False:
            raise PermissionError(f"{clip_id} is not admitted for visual-only training")
        asset_bindings = {
            "asset_id": clip_id,
            "source_id": source_id,
            "split": split,
            "project_relative_media_path": relative.as_posix(),
            "downloaded_sha256": digest,
            "fine_label": labels[0] if len(labels) == 1 else None,
            "is_touchdown": bool(target),
            "canonical_page_url": source_url,
            "license_spdxish": _text(row["license_spdxish"], f"line {line_number}.license_spdxish"),
            "rights_disposition": rights,
            "training_allowed": True,
            "redistribution_allowed": row["redistribution_allowed"],
        }
        for field, expected in asset_bindings.items():
            if asset.get(field) != expected:
                raise ValueError(f"example/source-manifest binding mismatch for {clip_id}.{field}")
        observed_duration = _finite(asset.get("observed_duration_seconds"), f"asset {clip_id}.observed_duration_seconds")
        if abs(observed_duration - duration) > 0.05:
            raise ValueError(f"example/source-manifest duration mismatch for {clip_id}")
        if require_media:
            if not media_path.is_file():
                raise FileNotFoundError(media_path)
            actual_sha = sha256_file(media_path)
            if actual_sha != digest:
                raise ValueError(f"media hash mismatch for {clip_id}: expected {digest}, got {actual_sha}")
        examples.append(Example(
            clip_id=clip_id,
            source_id=source_id,
            split=split,
            media_path=media_path,
            project_relative_media_path=relative.as_posix(),
            sha256=digest,
            start_seconds=start,
            end_seconds=end,
            duration_seconds=duration,
            labels=labels,
            label_provenance=provenance,
            adjudication_status=_text(row["adjudication_status"], f"line {line_number}.adjudication_status"),
            source_page_url=source_url,
            license_spdxish=asset_bindings["license_spdxish"],
            license_name=license_name,
            license_url=license_url,
            creator=creator,
            creator_url=creator_url,
            license_conditions=conditions,
            rights_disposition=rights,
            training_allowed=True,
            redistribution_allowed=row["redistribution_allowed"],
            notes=row["notes"] if isinstance(row["notes"], str) else "",
            target=target,
        ))
    if not examples:
        raise ValueError("examples manifest is empty")
    clip_ids = [item.clip_id for item in examples]
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError("clip_id values must be unique")
    media_digests = [item.sha256 for item in examples]
    if len(media_digests) != len(set(media_digests)):
        raise ValueError("the same media bytes may not appear as multiple examples")

    sources_by_split = {split: {item.source_id for item in examples if item.split == split} for split in SPLITS}
    for left_index, left in enumerate(SPLITS):
        for right in SPLITS[left_index + 1:]:
            overlap = sources_by_split[left] & sources_by_split[right]
            if overlap:
                raise ValueError(f"source leakage between {left} and {right}: {sorted(overlap)}")
    values_by_split = {split: {item.target for item in examples if item.split == split} for split in SPLITS}
    if values_by_split["train"] != {0, 1}:
        raise ValueError("training split must contain both is_touchdown target values")
    for split in ("valid", "test"):
        if values_by_split[split] != {0, 1}:
            raise ValueError(f"{split} split must contain both source-held-out target values")
    audit = {
        "schema_version": EXAMPLES_SCHEMA_VERSION,
        "examples_sha256": sha256_file(examples_path),
        "source_manifest_sha256": source_manifest_sha,
        "source_manifest_schema_version": source_manifest.get("schema_version"),
        "source_asset_count": len(source_assets),
        "example_count": len(examples),
        "source_count": len({item.source_id for item in examples}),
        "counts_by_split": {split: sum(item.split == split for item in examples) for split in SPLITS},
        "sources_by_split": {split: sorted(values) for split, values in sources_by_split.items()},
        "target_counts_by_split": {
            split: {TARGET_CLASSES[value]: sum(item.split == split and item.target == value for item in examples) for value in (0, 1)}
            for split in SPLITS
        },
        "all_training_allowed": True,
        "all_media_hashes_verified": require_media,
        "all_sources_disjoint_across_splits": True,
        "target_mapping": {
            "target_name": TARGET_NAME,
            "positive_fine_labels": sorted(POSITIVE_FINE_LABELS),
            "negative_fine_labels": sorted(NEGATIVE_FINE_LABELS),
            "mapping_origin": "frozen source-label transform; not a pixel heuristic",
        },
        "redistribution_allowed_for_all_media": all(item.redistribution_allowed for item in examples),
    }
    return examples, audit


@dataclass(frozen=True)
class DescriptorResult:
    descriptor: np.ndarray
    sampled_frame_indices: tuple[int, ...]
    sampled_frame_sha256: tuple[str, ...]
    decoded_fps: float
    decoded_frame_count: int
    decoded_duration_seconds: float
    backbone_output_dimension: int


class ClipDescriptorExtractor(Protocol):
    identity: dict[str, Any]

    def extract(self, video_path: Path, *, frame_count: int) -> DescriptorResult:
        ...


def _uniform_video_frames(path: Path, count: int) -> tuple[list[np.ndarray], list[int], float, int]:
    if count < 2:
        raise ValueError("frame_count must be at least two")
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("imageio-ffmpeg is required for reliable video sampling") from exc
    total, duration = imageio_ffmpeg.count_frames_and_secs(path)
    total = int(total)
    duration = float(duration)
    if total < 2 or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"video metadata is invalid: {path}")
    indices = list(dict.fromkeys(np.linspace(0, total - 1, min(count, total), dtype=int).tolist()))
    frames: list[np.ndarray] = []
    decoded_indices: list[int] = []
    reader = imageio_ffmpeg.read_frames(path, pix_fmt="rgb24")
    try:
        metadata = next(reader)
        width, height = metadata["size"]
        target_ordinal = 0
        for current, raw in enumerate(reader):
            if current < indices[target_ordinal]:
                continue
            rgb = np.frombuffer(raw, dtype=np.uint8).reshape(int(height), int(width), 3)
            frames.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            decoded_indices.append(current)
            target_ordinal += 1
            if target_ordinal == len(indices):
                break
    finally:
        reader.close()
    if len(frames) != len(indices):
        raise RuntimeError(
            f"FFmpeg full-decode count was {total}, but sampled indices {indices[len(frames):]} were not decoded from {path}"
        )
    if len(frames) < 2:
        raise RuntimeError(f"fewer than two frames were decoded from {path}")
    fps = float(metadata.get("fps") or total / duration)
    if not math.isfinite(fps) or fps <= 0:
        fps = total / duration
    return frames, decoded_indices, fps, total


class FrozenMobileNetV2:
    """ONNX Model Zoo MobileNetV2 output scores used as frozen descriptors."""

    def __init__(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - environment diagnostic
            raise RuntimeError("onnxruntime is required for the frozen backbone") from exc
        self.path = path.resolve()
        self.sha256 = sha256_file(path)
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or not outputs:
            raise RuntimeError("unexpected MobileNetV2 ONNX input/output contract")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name
        self.identity = {
            "kind": "frozen_pretrained_visual_backbone",
            "name": "ONNX Model Zoo MobileNetV2-1.0-fp32 opset 12",
            "path": str(self.path),
            "sha256": self.sha256,
            "source_url": DEFAULT_BACKBONE_URL,
            "documentation_url": "https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet",
            "license": "Apache-2.0",
            "pretraining_dataset": "ImageNet ILSVRC2012 (as documented upstream)",
            "trained_by_this_project": False,
            "output_use": "1000 ImageNet class scores used only as inherited frame descriptors",
            "provider": "CPUExecutionProvider",
            "input_name": self.input_name,
            "output_name": self.output_name,
            "preprocessing": {
                "color": "RGB",
                "resize": [224, 224],
                "scale": "uint8 / 255",
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
                "layout": "NCHW",
            },
        }

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        value = resized.astype(np.float32) / 255.0
        value = (value - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )
        return np.transpose(value, (2, 0, 1))[None, ...].astype(np.float32)

    def extract(self, video_path: Path, *, frame_count: int) -> DescriptorResult:
        frames, indices, fps, total = _uniform_video_frames(video_path, frame_count)
        outputs: list[np.ndarray] = []
        hashes: list[str] = []
        for frame in frames:
            result = self.session.run([self.output_name], {self.input_name: self._preprocess(frame)})[0]
            vector = np.asarray(result, dtype=np.float64).reshape(-1)
            if vector.size < 10 or not np.all(np.isfinite(vector)):
                raise RuntimeError("frozen backbone returned an invalid descriptor")
            outputs.append(vector)
            hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
        sequence = np.stack(outputs, axis=0)
        # These operations are fixed, deterministic temporal pooling, not learned
        # event logic: appearance mean, across-time variability, and endpoint delta.
        descriptor = np.concatenate(
            [sequence.mean(axis=0), sequence.std(axis=0), sequence[-1] - sequence[0]], axis=0
        ).astype(np.float64)
        return DescriptorResult(
            descriptor=descriptor,
            sampled_frame_indices=tuple(indices),
            sampled_frame_sha256=tuple(hashes),
            decoded_fps=fps,
            decoded_frame_count=total,
            decoded_duration_seconds=total / fps,
            backbone_output_dimension=sequence.shape[1],
        )


def acquire_backbone(
    output_path: Path = DEFAULT_BACKBONE,
    *,
    url: str = DEFAULT_BACKBONE_URL,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Acquire the small public backbone and seal a provenance/runtime receipt."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"github.com", "raw.githubusercontent.com", "media.githubusercontent.com"}:
        raise ValueError("backbone URL must remain on the official GitHub delivery surface")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    if output_path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        digest = sha256_file(output_path)
        if receipt.get("sha256") != digest:
            raise RuntimeError("existing backbone does not match its sealed receipt")
        if expected_sha256 is not None and digest != expected_sha256.lower():
            raise RuntimeError("existing backbone does not match the requested SHA-256")
        FrozenMobileNetV2(output_path)
        return receipt

    request = Request(url, headers={"User-Agent": "FootballMaster-Research-Pilot/1.0"})
    handle, temporary_name = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".download", dir=output_path.parent)
    final_url = url
    try:
        with os.fdopen(handle, "wb") as temporary, urlopen(request, timeout=120) as response:
            final_url = response.geturl()
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                temporary.write(block)
        temporary_path = Path(temporary_name)
        if temporary_path.stat().st_size < 10_000_000:
            raise RuntimeError("downloaded backbone is unexpectedly small")
        digest = sha256_file(temporary_path)
        if expected_sha256 is not None and digest != expected_sha256.lower():
            raise RuntimeError(f"backbone SHA-256 mismatch: expected {expected_sha256}, got {digest}")
        # Runtime-load before publication so an LFS pointer or corrupt download fails.
        FrozenMobileNetV2(temporary_path)
        os.replace(temporary_path, output_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    receipt = {
        "schema_version": BACKBONE_RECEIPT_SCHEMA_VERSION,
        "acquired_at": utc_now(),
        "requested_url": url,
        "final_url": final_url,
        "sha256": sha256_file(output_path),
        "bytes": output_path.stat().st_size,
        "license": "Apache-2.0",
        "documentation_url": "https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet",
        "model_origin": "ONNX Model Zoo MobileNetV2 pretrained on ImageNet; not trained by this project",
        "runtime_load_verified": True,
    }
    _atomic_json(receipt_path, receipt)
    return receipt


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as temporary:
            np.savez_compressed(temporary, **arrays)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _cache_metadata(cache: Any) -> dict[str, Any]:
    raw = np.asarray(cache["metadata_json"], dtype=np.uint8).tobytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("feature-cache metadata must be an object")
    return value


def extract_feature_matrix(
    examples: Sequence[Example],
    extractor: ClipDescriptorExtractor,
    *,
    frame_count: int,
    cache_dir: Path,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Extract or validate hash-bound clip descriptors in stable example order."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[np.ndarray] = []
    receipts: list[dict[str, Any]] = []
    for example in examples:
        cache_path = cache_dir / f"{example.clip_id}.npz"
        expected_identity = {
            "clip_id": example.clip_id,
            "media_sha256": example.sha256,
            "frame_count_requested": frame_count,
            "backbone_sha256": extractor.identity["sha256"],
            "pooling": "per-dimension mean + standard deviation + last-minus-first",
            "trained_event_logic": False,
        }
        descriptor: np.ndarray
        metadata: dict[str, Any]
        if cache_path.is_file():
            with np.load(cache_path, allow_pickle=False) as cache:
                metadata = _cache_metadata(cache)
                if any(metadata.get(key) != value for key, value in expected_identity.items()):
                    raise RuntimeError(f"feature-cache binding drift for {example.clip_id}")
                descriptor = np.asarray(cache["descriptor"], dtype=np.float64)
        else:
            started = time.perf_counter()
            result = extractor.extract(example.media_path, frame_count=frame_count)
            descriptor = np.asarray(result.descriptor, dtype=np.float64)
            if descriptor.ndim != 1 or descriptor.size < 10 or not np.all(np.isfinite(descriptor)):
                raise RuntimeError(f"invalid clip descriptor for {example.clip_id}")
            duration_tolerance = max(1.5, 0.25 * example.duration_seconds)
            if abs(result.decoded_duration_seconds - example.duration_seconds) > duration_tolerance:
                raise RuntimeError(
                    f"decoded duration drift for {example.clip_id}: manifest {example.duration_seconds:.3f}s, "
                    f"decoded {result.decoded_duration_seconds:.3f}s"
                )
            metadata = expected_identity | {
                "schema_version": "footballmaster-feature-cache-v1",
                "descriptor_dimension": int(descriptor.size),
                "backbone_output_dimension": int(result.backbone_output_dimension),
                "sampled_frame_indices": list(result.sampled_frame_indices),
                "sampled_frame_sha256": list(result.sampled_frame_sha256),
                "decoded_fps": result.decoded_fps,
                "decoded_frame_count": result.decoded_frame_count,
                "decoded_duration_seconds": result.decoded_duration_seconds,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
            _atomic_npz(
                cache_path,
                descriptor=descriptor,
                metadata_json=np.frombuffer(_canonical_json(metadata), dtype=np.uint8),
            )
        if descriptor.ndim != 1 or not np.all(np.isfinite(descriptor)):
            raise RuntimeError(f"cached descriptor is invalid for {example.clip_id}")
        rows.append(descriptor)
        receipts.append(metadata | {"cache_sha256": sha256_file(cache_path)})
    dimensions = {row.size for row in rows}
    if len(dimensions) != 1:
        raise RuntimeError("descriptor dimensions are inconsistent")
    return np.stack(rows, axis=0), receipts


@dataclass(frozen=True)
class Projection:
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    components: np.ndarray

    @property
    def output_dimension(self) -> int:
        return int(self.components.shape[0])

    @property
    def fitted_state_count(self) -> int:
        return int(self.feature_mean.size + self.feature_scale.size + self.components.size)

    def transform(self, values: np.ndarray) -> np.ndarray:
        matrix = np.asarray(values, dtype=np.float64)
        if matrix.ndim == 1:
            matrix = matrix[None, :]
        if matrix.ndim != 2 or matrix.shape[1] != self.feature_mean.size:
            raise ValueError("feature dimension does not match the trained projection")
        standardized = (matrix - self.feature_mean) / self.feature_scale
        result = standardized @ self.components.T
        if not np.all(np.isfinite(result)):
            raise RuntimeError("projection produced non-finite values")
        return result


def fit_projection(train_features: np.ndarray, requested_components: int) -> Projection:
    values = np.asarray(train_features, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 3 or values.shape[1] < 2:
        raise ValueError("at least three training examples with vector descriptors are required")
    if requested_components < 1:
        raise ValueError("requested_components must be positive")
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale = np.where(scale < 1e-8, 1.0, scale)
    standardized = (values - mean) / scale
    _, singular_values, right = np.linalg.svd(standardized, full_matrices=False)
    rank = int(np.sum(singular_values > 1e-10))
    count = min(requested_components, max(1, values.shape[0] - 1), max(1, rank))
    components = right[:count].copy()
    # Fix SVD sign ambiguity so repeated CPU runs serialize equivalent projections.
    for row in components:
        pivot = int(np.argmax(np.abs(row)))
        if row[pivot] < 0:
            row *= -1
    return Projection(feature_mean=mean, feature_scale=scale, components=components)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / exponent.sum(axis=1, keepdims=True)


def _loss(probabilities: np.ndarray, targets: np.ndarray, weights: np.ndarray | None = None) -> float:
    selected = np.clip(probabilities[np.arange(targets.size), targets], 1e-12, 1.0)
    losses = -np.log(selected)
    return float(losses.mean() if weights is None else np.sum(losses * weights) / np.sum(weights))


def _class_balancing_weights(targets: np.ndarray) -> np.ndarray:
    counts = np.bincount(targets, minlength=len(TARGET_CLASSES)).astype(np.float64)
    if np.any(counts == 0):
        raise ValueError("training targets must contain both classes")
    class_weights = targets.size / (len(TARGET_CLASSES) * counts)
    return class_weights[targets]


def evaluate_predictions(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    truth = np.asarray(targets, dtype=int)
    predicted = np.asarray(predictions, dtype=int)
    if truth.ndim != 1 or predicted.shape != truth.shape or truth.size == 0:
        raise ValueError("evaluation arrays must be same-sized non-empty vectors")
    confusion = np.zeros((2, 2), dtype=int)
    for actual, guess in zip(truth, predicted):
        if actual not in (0, 1) or guess not in (0, 1):
            raise ValueError("evaluation values must be binary")
        confusion[actual, guess] += 1
    per_class: dict[str, Any] = {}
    recalls: list[float] = []
    f1_values: list[float] = []
    for value, label in enumerate(TARGET_CLASSES):
        tp = int(confusion[value, value])
        fn = int(confusion[value, :].sum() - tp)
        fp = int(confusion[:, value].sum() - tp)
        support = tp + fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision, "recall": recall, "f1": f1, "support": support,
        }
        if support:
            recalls.append(recall)
        f1_values.append(f1)
    correct = int(np.sum(truth == predicted))
    n = int(truth.size)
    accuracy = correct / n
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (accuracy + z * z / (2 * n)) / denominator
    half = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / denominator
    return {
        "n_examples": n,
        "correct": correct,
        "accuracy": accuracy,
        "accuracy_wilson_95": [max(0.0, center - half), min(1.0, center + half)],
        "balanced_accuracy": sum(recalls) / len(recalls),
        "macro_f1": sum(f1_values) / len(f1_values),
        "confusion_matrix": {
            "row_actual_column_predicted": [list(TARGET_CLASSES), list(TARGET_CLASSES)],
            "values": confusion.tolist(),
        },
        "per_class": per_class,
    }


@dataclass(frozen=True)
class LearnedHead:
    weights: np.ndarray
    bias: np.ndarray
    selected_epoch: int

    @property
    def parameter_count(self) -> int:
        return int(self.weights.size + self.bias.size)

    def probabilities(self, values: np.ndarray) -> np.ndarray:
        return _softmax(np.asarray(values, dtype=np.float64) @ self.weights + self.bias)


def fit_softmax_head(
    train_values: np.ndarray,
    train_targets: np.ndarray,
    valid_values: np.ndarray,
    valid_targets: np.ndarray,
    *,
    epochs: int = 500,
    learning_rate: float = 0.05,
    l2: float = 0.1,
) -> tuple[LearnedHead, list[dict[str, Any]]]:
    if epochs < 1 or not 0 < learning_rate <= 1 or l2 < 0:
        raise ValueError("invalid optimizer configuration")
    x = np.asarray(train_values, dtype=np.float64)
    y = np.asarray(train_targets, dtype=int)
    xv = np.asarray(valid_values, dtype=np.float64)
    yv = np.asarray(valid_targets, dtype=int)
    if x.ndim != 2 or xv.ndim != 2 or x.shape[1] != xv.shape[1] or y.size != x.shape[0] or yv.size != xv.shape[0]:
        raise ValueError("train/validation matrices do not align")
    sample_weights = _class_balancing_weights(y)
    weights = np.zeros((x.shape[1], len(TARGET_CLASSES)), dtype=np.float64)
    bias = np.zeros(len(TARGET_CLASSES), dtype=np.float64)
    best_weights = weights.copy()
    best_bias = bias.copy()
    best_epoch = 0
    best_key = (float("inf"), float("inf"))
    log: list[dict[str, Any]] = []
    y_onehot = np.eye(len(TARGET_CLASSES), dtype=np.float64)[y]
    for epoch in range(1, epochs + 1):
        train_prob = _softmax(x @ weights + bias)
        error = (train_prob - y_onehot) * sample_weights[:, None] / sample_weights.sum()
        grad_weights = x.T @ error + l2 * weights
        grad_bias = error.sum(axis=0)
        weights -= learning_rate * grad_weights
        bias -= learning_rate * grad_bias
        train_prob = _softmax(x @ weights + bias)
        valid_prob = _softmax(xv @ weights + bias)
        train_loss = _loss(train_prob, y, sample_weights) + 0.5 * l2 * float(np.sum(weights * weights))
        valid_loss = _loss(valid_prob, yv)
        valid_metrics = evaluate_predictions(yv, np.argmax(valid_prob, axis=1))
        key = (-valid_metrics["macro_f1"], valid_loss)
        if key < best_key:
            best_key = key
            best_weights = weights.copy()
            best_bias = bias.copy()
            best_epoch = epoch
        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            log.append({
                "epoch": epoch,
                "train_objective": train_loss,
                "train_accuracy": float(np.mean(np.argmax(train_prob, axis=1) == y)),
                "valid_cross_entropy": valid_loss,
                "valid_accuracy": valid_metrics["accuracy"],
                "valid_macro_f1": valid_metrics["macro_f1"],
                "weight_l2_norm": float(np.linalg.norm(weights)),
            })
    return LearnedHead(weights=best_weights, bias=best_bias, selected_epoch=best_epoch), log


def _rows_for_split(examples: Sequence[Example], split: str) -> np.ndarray:
    return np.array([index for index, item in enumerate(examples) if item.split == split], dtype=int)


def _prediction_rows(
    examples: Sequence[Example],
    embeddings: np.ndarray,
    probabilities: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example, embedding, probability in zip(examples, embeddings, probabilities):
        predicted = int(np.argmax(probability))
        rows.append({
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "sport": "american_football",
            "clip_id": example.clip_id,
            "source_id": example.source_id,
            "split": example.split,
            "media_sha256": example.sha256,
            "source_fine_labels": list(example.labels),
            "source_label_provenance": example.label_provenance,
            "source_target": example.target,
            "source_target_label": TARGET_CLASSES[example.target],
            "learned_target": TARGET_NAME,
            "predicted_value": predicted,
            "predicted_label": TARGET_CLASSES[predicted],
            "confidence": float(probability[predicted]),
            "probabilities": {TARGET_CLASSES[value]: float(probability[value]) for value in (0, 1)},
            "learned_embedding": [float(value) for value in embedding],
            "detailed_event_report": None,
            "attribution": {
                "learned": ["learned_embedding", "probabilities", "predicted_value", "predicted_label", "confidence"],
                "source_metadata": ["source_fine_labels", "source_target", "source_target_label"],
                "vlm_generated": [],
                "deterministic": ["target mapping", "argmax"],
            },
        })
    return rows


def _metrics_for_split(
    examples: Sequence[Example],
    probabilities: np.ndarray,
    split: str,
    *,
    majority_class: int,
) -> dict[str, Any]:
    indices = _rows_for_split(examples, split)
    targets = np.array([examples[index].target for index in indices], dtype=int)
    predictions = np.argmax(probabilities[indices], axis=1)
    values = evaluate_predictions(targets, predictions)
    baseline = evaluate_predictions(targets, np.full(targets.shape, majority_class, dtype=int))
    values.update({
        "split": split,
        "source_count": len({examples[index].source_id for index in indices}),
        "source_ids": sorted({examples[index].source_id for index in indices}),
        "model_cross_entropy": _loss(probabilities[indices], targets),
        "majority_baseline": baseline,
    })
    return values


def _humanize_label(value: str) -> str:
    return value.replace("_", " ")


def build_search_index(
    output_dir: Path,
    examples: Sequence[Example],
    prediction_rows: Sequence[dict[str, Any]],
    *,
    model_card_sha256: str,
    examples_sha256: str,
) -> dict[str, Any]:
    """Build a demo-compatible index without inventing VLM-authored detail."""
    database = output_dir / "search-index.sqlite3"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(
            """
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE windows (
                window_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, match_id TEXT NOT NULL,
                start_s REAL NOT NULL, end_s REAL NOT NULL, status TEXT NOT NULL,
                report_json TEXT, error_type TEXT, error_message TEXT, elapsed_ms INTEGER,
                updated_at TEXT NOT NULL, sport TEXT NOT NULL, clip_id TEXT NOT NULL,
                source_id TEXT NOT NULL, split TEXT NOT NULL, media_path TEXT NOT NULL
            );
            CREATE TABLE events (
                event_id TEXT PRIMARY KEY, window_id TEXT NOT NULL REFERENCES windows(window_id),
                event_types_json TEXT NOT NULL, primary_action TEXT NOT NULL, start_s REAL NOT NULL,
                end_s REAL NOT NULL, confidence REAL NOT NULL, report_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE event_search USING fts5(
                event_id UNINDEXED, searchable_text, tokenize='unicode61 remove_diacritics 2'
            );
            """
        )
        connection.execute("INSERT INTO metadata(key,value) VALUES('schema_version',?)", (INDEX_SCHEMA_VERSION,))
        connection.execute("INSERT INTO metadata(key,value) VALUES('sport','american_football')")
        plans: list[dict[str, Any]] = []
        for ordinal, (example, prediction) in enumerate(zip(examples, prediction_rows)):
            window_id = f"football-{example.clip_id}-w000000-{int(round(example.duration_seconds * 1000)):09d}"
            event_id = window_id + ":e01"
            fine_text = ", ".join(_humanize_label(label) for label in example.labels)
            predicted_label = prediction["predicted_label"]
            event = {
                "event_id": event_id,
                "sport": "american_football",
                "event_types": list(example.labels),
                "primary_action": fine_text,
                "phase_of_play": "unknown",
                "field_areas": ["unknown"],
                "outcome": (
                    "The source description labels this clip as a touchdown."
                    if example.target else "The source description does not label this clip as a touchdown."
                ),
                "detailed_description": (
                    f"Source-description weak label: {fine_text}. The FootballMaster pilot's learned binary probe "
                    f"predicts {predicted_label}; it does not identify players, formation, coverage, or blocking."
                ),
                "coaching_relevance": (
                    "Coarse proof-of-pipeline retrieval only. A coach must review the video before using it for instruction; "
                    "no detailed VLM report or coach validation is attached."
                ),
                "coaching_tags": list(example.labels) + [f"footballmaster_{predicted_label}"],
                "retrieval_keywords": [_humanize_label(label) for label in example.labels] + [
                    "touchdown" if predicted_label == "touchdown" else "not touchdown"
                ],
                "uncertainty": (
                    "Tiny, weakly labeled source-held-out pilot. Confidence is an uncalibrated softmax score; "
                    "this record contains no VLM-authored temporal or player evidence."
                ),
                "participants": [],
                "evidence_frames": [],
                "confidence": prediction["confidence"],
                "report_origin": "deterministic_projection_of_source_metadata_and_learned_binary_prediction",
                "learned_fields": ["predicted_label", "probabilities", "confidence", "learned_embedding"],
                "source_metadata_fields": ["event_types", "primary_action", "source target"],
                "vlm_generated_fields": [],
                "predicted_label": predicted_label,
                "probabilities": prediction["probabilities"],
                "source_target_label": prediction["source_target_label"],
                "split": example.split,
                "source_attribution": {
                    "source_page_url": example.source_page_url,
                    "creator": example.creator,
                    "creator_url": example.creator_url,
                    "license_spdxish": example.license_spdxish,
                    "license_name": example.license_name,
                    "license_url": example.license_url,
                    "conditions": list(example.license_conditions),
                    "redistribution_allowed": example.redistribution_allowed,
                },
            }
            wrapper = {
                "schema_version": "footballmaster-coarse-window-report-v1",
                "sport": "american_football",
                "window_id": window_id,
                "match_id": example.source_id,
                "window_start_s": 0.0,
                "window_end_s": example.duration_seconds,
                "window_summary": event["detailed_description"],
                "events": [event],
                "report_abstained": False,
                "abstention_reason": None,
                "overall_uncertainty": event["uncertainty"],
            }
            report_json = json.dumps(wrapper, ensure_ascii=False, sort_keys=True)
            event_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
            connection.execute(
                "INSERT INTO windows VALUES(?,?,?,?,?,'complete',?,NULL,NULL,0,?,?,?,?,?,?)",
                (
                    window_id, ordinal, example.source_id, 0.0, example.duration_seconds, report_json, utc_now(),
                    "american_football", example.clip_id, example.source_id, example.split,
                    example.project_relative_media_path,
                ),
            )
            connection.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",
                (
                    event_id, window_id, json.dumps(list(example.labels)), event["primary_action"], 0.0,
                    example.duration_seconds, prediction["confidence"], event_json,
                ),
            )
            searchable = " ".join(
                list(example.labels)
                + event["retrieval_keywords"]
                + event["coaching_tags"]
                + [event["detailed_description"], event["coaching_relevance"]]
            )
            connection.execute("INSERT INTO event_search(event_id,searchable_text) VALUES(?,?)", (event_id, searchable))
            plans.append({
                "window_id": window_id,
                "clip_id": example.clip_id,
                "source_id": example.source_id,
                "split": example.split,
                "media_path": example.project_relative_media_path,
                "media_sha256": example.sha256,
                "local_window_s": [0.0, example.duration_seconds],
                "source_window_s": [example.start_seconds, example.end_seconds],
                "source_attribution": {
                    "source_page_url": example.source_page_url,
                    "creator": example.creator,
                    "creator_url": example.creator_url,
                    "license_spdxish": example.license_spdxish,
                    "license_url": example.license_url,
                    "conditions": list(example.license_conditions),
                },
            })
        connection.commit()
    finally:
        connection.close()
    plan = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "sport": "american_football",
        "model_card_sha256": model_card_sha256,
        "examples_sha256": examples_sha256,
        "window_count": len(plans),
        "windows": plans,
        "semantic_boundary": {
            "learned": "binary is_touchdown probability only",
            "source_metadata": "fine event tags and reference binary target",
            "deterministic": "windowing, prose projection, storage, FTS indexing",
            "vlm": "none in this index",
        },
    }
    _atomic_json(output_dir / "index-plan.json", plan)
    return {"database": database, "plan": plan}


def train_pipeline(
    *,
    examples_path: Path = DEFAULT_EXAMPLES,
    source_manifest_path: Path = DEFAULT_SOURCES,
    backbone_path: Path = DEFAULT_BACKBONE,
    output_dir: Path,
    frame_count: int = 8,
    pca_components: int = 16,
    epochs: int = 500,
    learning_rate: float = 0.05,
    l2: float = 0.1,
    project_root: Path = PROJECT_ROOT,
    extractor: ClipDescriptorExtractor | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Train, evaluate, and package the complete local pilot in one sealed run."""
    if frame_count < 2 or frame_count > 64:
        raise ValueError("frame_count must be between 2 and 64")
    output_dir = output_dir.resolve()
    root = project_root.resolve()
    try:
        output_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("output_dir must remain inside the project") from exc
    examples, data_audit = load_examples(
        examples_path, source_manifest_path, project_root=project_root, require_media=True
    )
    extractor = extractor or FrozenMobileNetV2(backbone_path)
    if "sha256" not in extractor.identity or not re.fullmatch(r"[0-9a-f]{64}", str(extractor.identity["sha256"])):
        raise ValueError("extractor identity must contain a lowercase SHA-256")

    backup: Path | None = None
    if output_dir.exists():
        if not replace:
            raise FileExistsError(f"refusing to overwrite existing model run: {output_dir}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = output_dir.with_name(output_dir.name + f".backup-{stamp}")
        suffix = 1
        while backup.exists():
            backup = output_dir.with_name(output_dir.name + f".backup-{stamp}-{suffix}")
            suffix += 1
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    started = time.perf_counter()
    try:
        ordered = sorted(examples, key=lambda item: (SPLITS.index(item.split), item.source_id, item.clip_id))
        features, feature_receipts = extract_feature_matrix(
            ordered, extractor, frame_count=frame_count, cache_dir=stage / "feature-cache"
        )
        train_indices = _rows_for_split(ordered, "train")
        valid_indices = _rows_for_split(ordered, "valid")
        train_targets = np.array([ordered[index].target for index in train_indices], dtype=int)
        valid_targets = np.array([ordered[index].target for index in valid_indices], dtype=int)
        projection = fit_projection(features[train_indices], pca_components)
        embeddings = projection.transform(features)
        head, training_log = fit_softmax_head(
            embeddings[train_indices], train_targets, embeddings[valid_indices], valid_targets,
            epochs=epochs, learning_rate=learning_rate, l2=l2,
        )
        probabilities = head.probabilities(embeddings)
        prediction_rows = _prediction_rows(ordered, embeddings, probabilities)
        train_counts = np.bincount(train_targets, minlength=2)
        majority_class = int(np.flatnonzero(train_counts == train_counts.max())[0])
        metrics = {
            "schema_version": METRICS_SCHEMA_VERSION,
            "generated_at": utc_now(),
            "sport": "american_football",
            "target": TARGET_NAME,
            "classes": list(TARGET_CLASSES),
            "evaluation_unit": "rights-audited clip",
            "split_unit": "source video/source_id",
            "source_overlap": False,
            "validation_used_for": "best-epoch selection only; no taxonomy or feature changes",
            "train": _metrics_for_split(ordered, probabilities, "train", majority_class=majority_class),
            "valid": _metrics_for_split(ordered, probabilities, "valid", majority_class=majority_class),
            "test": _metrics_for_split(ordered, probabilities, "test", majority_class=majority_class),
            "majority_class_from_train": TARGET_CLASSES[majority_class],
            "claim_boundary": (
                "Descriptive tiny-pilot result only. Weak source-description labels, very small source counts, broad binary "
                "target, and no coach adjudication preclude a generalization, calibration, or coaching-utility claim."
            ),
            "performance_claim_allowed": False,
        }
        config = {
            "schema_version": MODEL_SCHEMA_VERSION,
            "created_at": utc_now(),
            "sport": "american_football",
            "model_name": "FootballMaster-Pilot-v1",
            "model_kind": "frozen_frame_descriptors_plus_fixed_temporal_pooling_plus_train-only_PCA_plus_trained_linear_probe",
            "target": {
                "name": TARGET_NAME,
                "classes": list(TARGET_CLASSES),
                "positive_fine_labels": sorted(POSITIVE_FINE_LABELS),
                "negative_fine_labels": sorted(NEGATIVE_FINE_LABELS),
                "origin": "frozen transform of source-supported weak event tags",
            },
            "data": data_audit,
            "backbone": extractor.identity,
            "sampling": {
                "frames_per_clip": frame_count,
                "strategy": "uniform over decoded local clip",
                "frame_pixels_supplied_to_learned_head": False,
            },
            "temporal_pooling": {
                "kind": "fixed mean + standard deviation + last-minus-first",
                "input_dimension": int(features.shape[1]),
                "learned": False,
            },
            "projection": {
                "kind": "train-only feature standardization and PCA via SVD",
                "requested_components": pca_components,
                "actual_components": projection.output_dimension,
                "component_parameter_count": int(projection.components.size),
                "preprocessing_stat_count": int(projection.feature_mean.size + projection.feature_scale.size),
                "total_fitted_state_count": projection.fitted_state_count,
                "fit_split": "train only",
            },
            "learned_head": {
                "kind": "two-class linear softmax probe",
                "parameter_count": head.parameter_count,
                "epochs_requested": epochs,
                "selected_epoch": head.selected_epoch,
                "learning_rate": learning_rate,
                "l2": l2,
                "class_weighting": "inverse train frequency",
                "random_initialization": "none; zero initialization",
            },
            "attribution_boundary": {
                "inherited_frozen": "MobileNetV2 ONNX ImageNet weights and 1000-score frame outputs",
                "deterministic": "uniform sampling, preprocessing, temporal pooling, target mapping, argmax, indexing",
                "fitted_train_only": "feature mean/scale, PCA components, softmax weights and bias",
                "vlm": "no VLM is called and no detailed event report is generated by this model package",
            },
            "redistribution": {
                "all_input_media_redistributable": data_audit["redistribution_allowed_for_all_media"],
                "package_status": "local research only; do not publish without a separate model-output rights review",
            },
            "code_sha256": sha256_file(Path(__file__)),
        }
        config_path = stage / "model-config.json"
        _atomic_json(config_path, config)
        checkpoint_path = stage / "footballmaster-pilot-v1.npz"
        _atomic_npz(
            checkpoint_path,
            feature_mean=projection.feature_mean,
            feature_scale=projection.feature_scale,
            pca_components=projection.components,
            head_weights=head.weights,
            head_bias=head.bias,
        )
        _atomic_jsonl(stage / "training-log.jsonl", training_log)
        _atomic_jsonl(stage / "predictions.jsonl", prediction_rows)
        _atomic_json(stage / "metrics.json", metrics)
        _atomic_json(stage / "data-audit.json", data_audit)
        _atomic_json(stage / "feature-receipts.json", {
            "schema_version": "footballmaster-feature-receipts-v1",
            "backbone_sha256": extractor.identity["sha256"],
            "items": feature_receipts,
        })
        generation_id = hashlib.sha256(
            (sha256_file(config_path) + ":" + sha256_file(checkpoint_path)).encode("ascii")
        ).hexdigest()[:24]
        model_card = {
            "schema_version": "footballmaster-pilot-model-card-v1",
            "generation_id": generation_id,
            "model_name": config["model_name"],
            "sport": "american_football",
            "architecture_scope": ARCHITECTURE_SCOPE,
            "actual_trained_parameters": True,
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "config_sha256": sha256_file(config_path),
            "metrics_sha256": sha256_file(stage / "metrics.json"),
            "predictions_sha256": sha256_file(stage / "predictions.jsonl"),
            "training_log_sha256": sha256_file(stage / "training-log.jsonl"),
            "learned_parameter_count": int(projection.components.size + head.parameter_count),
            "learned_parameter_definition": (
                "train-fitted PCA components plus supervised softmax weights/bias; excludes fitted feature mean/scale"
            ),
            "supervised_learned_parameter_count": head.parameter_count,
            "learned_head_parameter_count": head.parameter_count,
            "unsupervised_train_fitted_projection_parameter_count": int(projection.components.size),
            "train_fitted_preprocessing_stat_count": int(projection.feature_mean.size + projection.feature_scale.size),
            "total_persisted_fitted_numeric_state_count": projection.fitted_state_count + head.parameter_count,
            "frozen_backbone_file_bytes": (
                Path(extractor.identity["path"]).stat().st_size
                if isinstance(extractor.identity.get("path"), str) and Path(extractor.identity["path"]).is_file()
                else None
            ),
            "evaluated_target": TARGET_NAME,
            "test_metrics": metrics["test"],
            "limitations": [
                "Tiny weakly labeled source-held-out pilot; metrics are descriptive and high variance.",
                "Only a broad touchdown/non-touchdown target is learned.",
                "The inherited backbone was pretrained on ImageNet, not football video.",
                "Uniform frame samples and fixed pooling do not model continuous ball/player trajectories.",
                "Softmax confidence is not calibrated probability.",
                "No player identity, formation, coverage, blocking, pressure, tackle, or temporal evidence is inferred.",
                "No coach has validated usefulness or report correctness.",
            ],
            "intended_use": "Local proof-of-pipeline retrieval and representation experiment; human review required.",
            "prohibited_claims": [
                "external architecture reproduction", "foundation model", "coach-ready", "generalizes to football games",
                "fine-grained event understanding", "calibrated confidence",
            ],
        }
        validate_model_card(model_card)
        _atomic_json(stage / "model-card.json", model_card)
        index = build_search_index(
            stage, ordered, prediction_rows,
            model_card_sha256=sha256_file(stage / "model-card.json"),
            examples_sha256=data_audit["examples_sha256"],
        )
        receipt = {
            "schema_version": "footballmaster-pilot-run-receipt-v1",
            "generation_id": generation_id,
            "completed_at": utc_now(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "status": "pass",
            "sport": "american_football",
            "external_services_called": [],
            "paid_services_used": [],
            "gpu_used": False,
            "backbone_sha256": extractor.identity["sha256"],
            "examples_sha256": data_audit["examples_sha256"],
            "source_manifest_sha256": data_audit["source_manifest_sha256"],
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "model_config_sha256": sha256_file(config_path),
            "model_card_sha256": sha256_file(stage / "model-card.json"),
            "metrics_sha256": sha256_file(stage / "metrics.json"),
            "predictions_sha256": sha256_file(stage / "predictions.jsonl"),
            "training_log_sha256": sha256_file(stage / "training-log.jsonl"),
            "database_sha256": sha256_file(index["database"]),
            "index_plan_sha256": sha256_file(stage / "index-plan.json"),
            "feature_receipts_sha256": sha256_file(stage / "feature-receipts.json"),
            "source_held_out_test": True,
            "performance_claim_allowed": False,
            "package_redistribution_allowed": False,
        }
        _atomic_json(stage / "run-receipt.json", receipt)
        if backup is not None:
            output_dir.rename(backup)
        stage.rename(output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        if backup is not None and backup.exists() and not output_dir.exists():
            backup.rename(output_dir)
        raise
    return {
        "status": "pass",
        "output_dir": output_dir,
        "backup": backup,
        "test_metrics": metrics["test"],
        "checkpoint": output_dir / "footballmaster-pilot-v1.npz",
        "search_index": output_dir / "search-index.sqlite3",
        "run_receipt": output_dir / "run-receipt.json",
    }


@dataclass(frozen=True)
class LoadedPilot:
    config: dict[str, Any]
    projection: Projection
    head: LearnedHead
    extractor: ClipDescriptorExtractor


def load_pilot(model_dir: Path, *, backbone_path: Path | None = None) -> LoadedPilot:
    model_dir = model_dir.resolve()
    config_path = model_dir / "model-config.json"
    checkpoint_path = model_dir / "footballmaster-pilot-v1.npz"
    card_path = model_dir / "model-card.json"
    for path in (config_path, checkpoint_path, card_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise RuntimeError("unsupported FootballMaster model schema")
    if card.get("checkpoint_sha256") != sha256_file(checkpoint_path):
        raise RuntimeError("checkpoint does not match model card")
    if card.get("config_sha256") != sha256_file(config_path):
        raise RuntimeError("configuration does not match model card")
    validate_model_card(card)
    resolved_backbone = backbone_path or Path(config["backbone"]["path"])
    extractor = FrozenMobileNetV2(resolved_backbone)
    if extractor.identity["sha256"] != config["backbone"]["sha256"]:
        raise RuntimeError("backbone does not match trained model lineage")
    with np.load(checkpoint_path, allow_pickle=False) as values:
        projection = Projection(
            feature_mean=np.asarray(values["feature_mean"], dtype=np.float64),
            feature_scale=np.asarray(values["feature_scale"], dtype=np.float64),
            components=np.asarray(values["pca_components"], dtype=np.float64),
        )
        head = LearnedHead(
            weights=np.asarray(values["head_weights"], dtype=np.float64),
            bias=np.asarray(values["head_bias"], dtype=np.float64),
            selected_epoch=int(config["learned_head"]["selected_epoch"]),
        )
    if head.weights.shape != (projection.output_dimension, len(TARGET_CLASSES)) or head.bias.shape != (2,):
        raise RuntimeError("checkpoint tensor shapes do not match the model contract")
    return LoadedPilot(config=config, projection=projection, head=head, extractor=extractor)


def predict_video(
    model_dir: Path,
    video_path: Path,
    *,
    clip_id: str,
    expected_sha256: str | None = None,
    backbone_path: Path | None = None,
) -> dict[str, Any]:
    if not video_path.is_file():
        raise FileNotFoundError(video_path)
    digest = sha256_file(video_path)
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise RuntimeError("inference media does not match expected SHA-256")
    model = load_pilot(model_dir, backbone_path=backbone_path)
    result = model.extractor.extract(video_path, frame_count=int(model.config["sampling"]["frames_per_clip"]))
    embedding = model.projection.transform(result.descriptor)[0]
    probabilities = model.head.probabilities(embedding[None, :])[0]
    predicted = int(np.argmax(probabilities))
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "sport": "american_football",
        "clip_id": clip_id,
        "media_sha256": digest,
        "model_config_sha256": sha256_file(model_dir / "model-config.json"),
        "checkpoint_sha256": sha256_file(model_dir / "footballmaster-pilot-v1.npz"),
        "backbone_sha256": model.extractor.identity["sha256"],
        "learned_target": TARGET_NAME,
        "predicted_value": predicted,
        "predicted_label": TARGET_CLASSES[predicted],
        "confidence": float(probabilities[predicted]),
        "probabilities": {TARGET_CLASSES[value]: float(probabilities[value]) for value in (0, 1)},
        "learned_embedding": [float(value) for value in embedding],
        "sampled_frame_indices": list(result.sampled_frame_indices),
        "sampled_frame_sha256": list(result.sampled_frame_sha256),
        "detailed_event_report": None,
        "attribution": {
            "inherited_frozen": "MobileNetV2 ImageNet frame scores",
            "learned": "train-only PCA and binary softmax probe",
            "deterministic": "sampling, temporal pooling, argmax",
            "vlm": "none",
        },
        "warning": "Coarse tiny-pilot output only; confidence is not calibrated and human video review is required.",
    }


def _verify_run_snapshot(model_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    bindings = {
        "checkpoint_sha256": "footballmaster-pilot-v1.npz",
        "model_config_sha256": "model-config.json",
        "model_card_sha256": "model-card.json",
        "metrics_sha256": "metrics.json",
        "predictions_sha256": "predictions.jsonl",
        "training_log_sha256": "training-log.jsonl",
        "database_sha256": "search-index.sqlite3",
        "index_plan_sha256": "index-plan.json",
        "feature_receipts_sha256": "feature-receipts.json",
    }
    verified: dict[str, bool] = {}
    for key, filename in bindings.items():
        path = model_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        verified[key] = receipt.get(key) == actual
        if not verified[key]:
            raise RuntimeError(f"run receipt binding failed for {filename}")
    metrics = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
    config = json.loads((model_dir / "model-config.json").read_text(encoding="utf-8"))
    card = json.loads((model_dir / "model-card.json").read_text(encoding="utf-8"))
    validate_model_card(card)
    expected_generation = hashlib.sha256(
        (receipt["model_config_sha256"] + ":" + receipt["checkpoint_sha256"]).encode("ascii")
    ).hexdigest()[:24]
    if receipt.get("generation_id") != expected_generation or card.get("generation_id") != expected_generation:
        raise RuntimeError("model package generation identifier is inconsistent")
    if metrics.get("performance_claim_allowed") is not False or receipt.get("performance_claim_allowed") is not False:
        raise RuntimeError("tiny-pilot performance claim boundary is missing")
    if config.get("attribution_boundary", {}).get("vlm") != "no VLM is called and no detailed event report is generated by this model package":
        raise RuntimeError("model attribution boundary drifted")
    connection = sqlite3.connect(model_dir / "search-index.sqlite3")
    try:
        window_count = int(connection.execute("SELECT count(*) FROM windows WHERE status='complete'").fetchone()[0])
        event_count = int(connection.execute("SELECT count(*) FROM events").fetchone()[0])
        records = connection.execute("SELECT report_json FROM events").fetchall()
    finally:
        connection.close()
    if window_count < 1 or event_count != window_count:
        raise RuntimeError("search index has incomplete window/event coverage")
    for (raw,) in records:
        event = json.loads(raw)
        if event.get("vlm_generated_fields") != [] or event.get("participants") != [] or event.get("evidence_frames") != []:
            raise RuntimeError("coarse index incorrectly attributes detailed VLM evidence")
    return {
        "status": "pass",
        "model_dir": str(model_dir),
        "generation_id": expected_generation,
        "bindings": verified,
        "window_count": window_count,
        "event_count": event_count,
        "source_held_out_test": receipt.get("source_held_out_test") is True,
        "performance_claim_allowed": False,
    }


def verify_run(model_dir: Path) -> dict[str, Any]:
    """Verify a stable package snapshot without mutating it.

    A replacement run publishes by renaming a complete staging directory.  A
    concurrent reader can still open the old receipt immediately before the
    rename and then resolve new file paths afterward.  Detect that generation
    change and retry the read; a stable mismatch remains a hard failure.
    """
    model_dir = model_dir.resolve()
    receipt_path = model_dir / "run-receipt.json"
    last_error: Exception | None = None
    for _attempt in range(3):
        if not receipt_path.is_file():
            raise FileNotFoundError(receipt_path)
        before = receipt_path.read_bytes()
        try:
            receipt = json.loads(before.decode("utf-8"))
            result = _verify_run_snapshot(model_dir, receipt)
        except (FileNotFoundError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            after = receipt_path.read_bytes() if receipt_path.is_file() else b""
            if after != before:
                continue
            raise
        after = receipt_path.read_bytes() if receipt_path.is_file() else b""
        if after != before:
            continue
        return result
    raise RuntimeError("model package generation changed during three verification snapshots") from last_error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    acquire = sub.add_parser("acquire-backbone", help="Download and validate the public frozen ONNX backbone.")
    acquire.add_argument("--out", type=Path, default=DEFAULT_BACKBONE)
    acquire.add_argument("--url", default=DEFAULT_BACKBONE_URL)
    acquire.add_argument("--expected-sha256")

    audit = sub.add_parser("audit-data", help="Verify rights, hashes, split isolation, and target support.")
    audit.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    audit.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    audit.add_argument("--no-media", action="store_true", help="Schema-only audit; never sufficient for training.")

    train = sub.add_parser("train", help="Train, evaluate, and package the source-held-out pilot.")
    train.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    train.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    train.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    train.add_argument("--out", type=Path, required=True)
    train.add_argument("--frames", type=int, default=8)
    train.add_argument("--pca-components", type=int, default=16)
    train.add_argument("--epochs", type=int, default=500)
    train.add_argument("--learning-rate", type=float, default=0.05)
    train.add_argument("--l2", type=float, default=0.1)
    train.add_argument("--replace", action="store_true")

    predict = sub.add_parser("predict", help="Run the trained coarse pilot on one local clip.")
    predict.add_argument("--model-dir", type=Path, required=True)
    predict.add_argument("--video", type=Path, required=True)
    predict.add_argument("--clip-id", required=True)
    predict.add_argument("--expected-sha256")
    predict.add_argument("--backbone", type=Path)
    predict.add_argument("--out", type=Path)

    verify = sub.add_parser("verify", help="Recompute all package hash/structure gates.")
    verify.add_argument("--model-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "acquire-backbone":
        result = acquire_backbone(args.out, url=args.url, expected_sha256=args.expected_sha256)
    elif args.command == "audit-data":
        _, result = load_examples(args.examples, args.sources, require_media=not args.no_media)
    elif args.command == "train":
        result = train_pipeline(
            examples_path=args.examples,
            source_manifest_path=args.sources,
            backbone_path=args.backbone,
            output_dir=args.out,
            frame_count=args.frames,
            pca_components=args.pca_components,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
            replace=args.replace,
        )
        result = {
            **result,
            "output_dir": str(result["output_dir"]),
            "backup": None if result["backup"] is None else str(result["backup"]),
            "checkpoint": str(result["checkpoint"]),
            "search_index": str(result["search_index"]),
            "run_receipt": str(result["run_receipt"]),
        }
    elif args.command == "predict":
        result = predict_video(
            args.model_dir, args.video, clip_id=args.clip_id,
            expected_sha256=args.expected_sha256, backbone_path=args.backbone,
        )
        if args.out:
            _atomic_json(args.out, result)
    else:
        result = verify_run(args.model_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
