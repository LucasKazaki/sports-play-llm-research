"""Build a private, offline live-demo UI from hash-bound SoccerNet results.

The generated site never contacts a network service.  It copies the already
derived private clips into another directory below ``data/private`` and keeps
the visual-only result, commentary check, and mapped annotation visibly
separate.  It is intentionally a renderer, not an inference path.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIVATE_ROOT = PROJECT_ROOT / "data" / "private"
DEMO_RECEIPT_SCHEMA = "playground-private-live-demo-receipt-v1"
_SAFE_CLIP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {token}")
            ),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _require_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not _is_within(resolved, root):
        raise ValueError(f"{label} must stay below the private data root")
    return resolved


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _require_clip_id(value: Any) -> str:
    if not isinstance(value, str) or not _SAFE_CLIP_ID.fullmatch(value):
        raise ValueError("clip IDs must be opaque, filename-safe identifiers")
    return value


def _require_unit_interval(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{label} must be finite and within [0, 1]")
    return float(value)


def _require_temporal_pair(
    value: Any, label: str, *, duration_s: float = 10.0, allow_zero: bool = False
) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two timestamps")
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(float(item))
        for item in value
    ):
        raise ValueError(f"{label} timestamps must be finite numbers")
    start, end = (float(value[0]), float(value[1]))
    if start < 0.0 or end < start or end > duration_s or (end == start and not allow_zero):
        raise ValueError(f"{label} must be ordered within the clip duration")
    return [start, end]


def _validate_evidence_contract(
    record: dict[str, Any], *, abstained: bool, label: str, require_presence: bool
) -> None:
    """Validate the exact evidence contract used by the visual runner.

    A non-abstained result must cite both a positive-duration sampled interval
    and at least one spatial cue.  An abstention may use a null interval (when
    evidence is omitted from a public summary) or the runner's explicit
    ``[0, 0]`` sentinel, and must not claim a spatial cue.
    """
    has_temporal = "temporal_evidence_s" in record and record.get("temporal_evidence_s") is not None
    has_spatial = "spatial_evidence" in record and record.get("spatial_evidence") is not None
    if abstained:
        if has_temporal:
            temporal = _require_temporal_pair(
                record.get("temporal_evidence_s"), f"{label} temporal evidence", allow_zero=True
            )
            if temporal != [0.0, 0.0]:
                raise ValueError(f"{label} abstention must use a null or zero temporal interval")
        if has_spatial:
            spatial = record.get("spatial_evidence")
            if not isinstance(spatial, list) or spatial:
                raise ValueError(f"{label} abstention must use empty spatial evidence")
        return

    if require_presence and (not has_temporal or not has_spatial):
        raise ValueError(f"{label} non-abstention must include temporal and spatial evidence")
    if has_temporal:
        _require_temporal_pair(record.get("temporal_evidence_s"), f"{label} temporal evidence")
    if has_spatial:
        spatial = record.get("spatial_evidence")
        if (
            not isinstance(spatial, list)
            or any(not isinstance(value, str) or not value.strip() for value in spatial)
            or (require_presence and not spatial)
        ):
            raise ValueError(f"{label} spatial evidence must be a nonempty list of strings")


def _resolve_private_media(
    raw_path: Any, *, project_root: Path, private_root: Path, label: str
) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(f"{label} has no media path")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = _require_within(candidate, private_root, label)
    if not resolved.is_file():
        raise ValueError(f"{label} media file does not exist")
    return resolved


def _as_records(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be a list of objects")
    return value


def _validate_manifest_and_visual(
    manifest: dict[str, Any], manifest_path: Path,
    visual: dict[str, Any], visual_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if manifest.get("schema_version") != "playground-soccernet-clips-manifest-v1":
        raise ValueError("unsupported private clip manifest schema")
    if manifest.get("provider") != "SoccerNet" or visual.get("provider") != "SoccerNet":
        raise ValueError("presenter-facing SoccerNet claims require SoccerNet provider bindings")
    clips = _as_records(manifest.get("clips"), "manifest clips")
    if not clips:
        raise ValueError("manifest must contain at least one clip")
    split = manifest.get("split")
    if not isinstance(split, str) or not split:
        raise ValueError("manifest split is missing")
    if split != "valid":
        raise ValueError("presenter-facing demo requires the designated valid split")
    if visual.get("split") != split:
        raise ValueError("visual summary split does not match the manifest")
    manifest_sha = sha256_file(manifest_path)
    bound_sha = visual.get("private_manifest_sha256", visual.get("manifest_sha256"))
    if bound_sha != manifest_sha:
        raise ValueError("visual summary is not hash-bound to this private manifest")

    manifest_by_id: dict[str, dict[str, Any]] = {}
    for clip in clips:
        clip_id = _require_clip_id(clip.get("clip_id"))
        if clip_id in manifest_by_id:
            raise ValueError("manifest clip IDs must be unique")
        if clip.get("split", split) != split:
            raise ValueError("manifest clip split is inconsistent")
        duration = clip.get("clip_duration_s")
        if (
            not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(float(duration))
            or not math.isclose(float(duration), 10.0, rel_tol=0.0, abs_tol=0.01)
        ):
            raise ValueError("presenter-facing clips must be 10 seconds long")
        truth = clip.get("ground_truth")
        if not isinstance(truth, dict) or not isinstance(truth.get("play_type"), str):
            raise ValueError("each private clip must include its mapped annotation")
        manifest_by_id[clip_id] = clip

    completed = _as_records(visual.get("clips", []), "visual completed clips")
    failures = _as_records(visual.get("failures", []), "visual failures")
    visual_by_id: dict[str, dict[str, Any]] = {}
    failure_by_id: dict[str, dict[str, Any]] = {}
    for item in completed:
        clip_id = _require_clip_id(item.get("clip_id"))
        if clip_id not in manifest_by_id or clip_id in visual_by_id:
            raise ValueError("visual completed clip IDs are duplicated or not in the manifest")
        if not isinstance(item.get("prediction"), str) or not isinstance(item.get("abstained"), bool):
            raise ValueError("visual completed records need prediction and abstained fields")
        confidence = _require_unit_interval(item.get("confidence"), "visual confidence")
        if item["abstained"]:
            if item["prediction"] != "insufficient_visual_evidence" or confidence != 0.0:
                raise ValueError("visual abstention fields are inconsistent")
        elif item["prediction"] == "insufficient_visual_evidence":
            raise ValueError("visual non-abstention cannot use the insufficiency sentinel")
        _validate_evidence_contract(
            item, abstained=item["abstained"], label="visual", require_presence=False
        )
        truth = item.get("truth")
        if truth is not None and truth != manifest_by_id[clip_id]["ground_truth"]["play_type"]:
            raise ValueError("public summary truth does not match private manifest truth")
        visual_by_id[clip_id] = item
    for item in failures:
        clip_id = _require_clip_id(item.get("clip_id"))
        if clip_id not in manifest_by_id or clip_id in failure_by_id or clip_id in visual_by_id:
            raise ValueError("visual failure clip IDs are duplicated or overlap completed clips")
        if not isinstance(item.get("error_code"), str):
            raise ValueError("visual failure records need an error_code")
        failure_by_id[clip_id] = item

    expected = set(manifest_by_id)
    observed = set(visual_by_id) | set(failure_by_id)
    if observed != expected:
        raise ValueError("visual summary must account for every requested manifest clip exactly once")
    counts = visual.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("visual summary counts are missing")
    if (
        counts.get("requested") != len(clips)
        or counts.get("completed") != len(completed)
        or counts.get("failed") != len(failures)
    ):
        raise ValueError("visual summary counts are inconsistent")
    if not isinstance(visual.get("model"), str) or not visual["model"]:
        raise ValueError("visual summary model is missing")
    if not isinstance(visual.get("schema_version"), str):
        raise ValueError("visual summary schema version is missing")
    if visual["schema_version"] not in {
        "playground-soccernet-vlm-pilot-summary-v1",
        "playground-soccernet-vlm-pilot-summary-v2",
    }:
        raise ValueError("unsupported visual summary family")

    # Recompute every audience-facing primary metric from the bound manifest
    # and per-clip records.  A hash-consistent summary with tampered aggregate
    # rates must not reach the live demo.
    allowed_correct = 0
    exact_single_correct = 0
    single_requested = 0
    single_completed = 0
    for clip_id, clip in manifest_by_id.items():
        truth = clip["ground_truth"]
        allowed = truth.get("allowed_play_types_in_window", [truth["play_type"]])
        if not isinstance(allowed, list) or any(not isinstance(value, str) for value in allowed):
            raise ValueError("manifest allowed labels must be a list of strings")
        single = truth.get("single_label_eligible") is True
        if single:
            single_requested += 1
        item = visual_by_id.get(clip_id)
        if item is None:
            continue
        if single:
            single_completed += 1
        prediction = item["prediction"]
        abstained = item["abstained"]
        expected_allowed = not abstained and prediction in allowed
        expected_exact = not abstained and prediction == truth["play_type"]
        if item.get("allowed_correct") is not expected_allowed:
            raise ValueError("visual clip allowed_correct disagrees with the bound manifest")
        if "single_label_eligible" in item and item.get("single_label_eligible") is not single:
            raise ValueError("visual clip single-label eligibility disagrees with the bound manifest")
        if "exact_correct" in item and item.get("exact_correct") is not expected_exact:
            raise ValueError("visual clip exact_correct disagrees with the bound manifest")
        allowed_correct += int(expected_allowed)
        exact_single_correct += int(single and expected_exact)

    optional_count_checks = {
        "single_label_eligible_requested": single_requested,
        "single_label_eligible_completed": single_completed,
    }
    for key, expected in optional_count_checks.items():
        if key in counts and counts.get(key) != expected:
            raise ValueError("visual summary single-label counts are inconsistent")

    primary = visual.get("metrics", {}).get("primary_requested_set")
    if not isinstance(primary, dict):
        raise ValueError("visual summary primary requested-set metrics are missing")
    expected_rates: dict[str, float | None] = {
        "schema_valid_first_pass_rate": len(completed) / len(clips),
        "allowed_label_accuracy_all_clips": allowed_correct / len(clips),
        "single_label_exact_accuracy": (
            exact_single_correct / single_requested if single_requested else None
        ),
    }
    for key, expected in expected_rates.items():
        actual = primary.get(key)
        if expected is None:
            if actual is not None:
                raise ValueError(f"visual summary metric {key} must be null without eligible clips")
            continue
        if (
            not isinstance(actual, (int, float))
            or isinstance(actual, bool)
            or not math.isfinite(float(actual))
            or not 0.0 <= float(actual) <= 1.0
            or not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12)
        ):
            raise ValueError(f"visual summary metric {key} is inconsistent")
    return clips, visual_by_id, failure_by_id


def _validate_frozen_config(
    frozen: dict[str, Any], frozen_path: Path,
    manifest: dict[str, Any], manifest_path: Path,
    visual: dict[str, Any],
) -> str:
    frozen_sha = sha256_file(frozen_path)
    visual_frozen = visual.get("frozen_config")
    if not isinstance(visual_frozen, dict) or visual_frozen.get("enforced") is not True:
        raise ValueError("the demo requires a visual summary produced under an enforced frozen config")
    frozen_schema = frozen.get("schema_version")
    if frozen_schema not in {
        "playground-frozen-visual-config-v1",
        "playground-frozen-visual-config-v2",
    }:
        raise ValueError("unsupported frozen visual config schema")
    if visual_frozen.get("schema_version") != frozen_schema:
        raise ValueError("visual summary frozen schema does not match the supplied config")
    if visual_frozen.get("sha256") != frozen_sha:
        raise ValueError("visual summary is not bound to the supplied frozen config")
    manifests = frozen.get("manifests")
    if not isinstance(manifests, dict):
        raise ValueError("frozen config manifest bindings are missing")
    binding = manifests.get("validation")
    if not isinstance(binding, dict) or binding.get("sha256") != sha256_file(manifest_path):
        raise ValueError("frozen config validation role is not bound to the supplied manifest")
    if frozen.get("model") != visual.get("model"):
        raise ValueError("frozen model does not match the visual summary")
    if frozen.get("prompt_sha256") != visual.get("prompt_sha256"):
        raise ValueError("frozen prompt does not match the visual summary")
    if frozen.get("sampling") != visual.get("sampling"):
        raise ValueError("frozen sampling settings do not match the visual summary")
    endpoint = frozen.get("endpoint")
    parsed = urlparse(endpoint) if isinstance(endpoint, str) else None
    if (
        parsed is None or parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None or parsed.password is not None
    ):
        raise ValueError("frozen config endpoint must be a credential-free loopback URL")
    return frozen_sha


def _validate_provenance(
    provenance: dict[str, Any], provenance_path: Path,
    manifest_path: Path,
) -> tuple[str, dict[str, Any]]:
    if provenance.get("schema_version") != "playground-soccerdb-soccernet-overlap-binding-v1":
        raise ValueError("unsupported SoccerDB/SoccerNet provenance schema")
    if provenance.get("status") != "pass":
        raise ValueError("SoccerDB/SoccerNet provenance binding did not pass")
    rights = provenance.get("rights_boundary")
    if not isinstance(rights, dict) or rights.get("private_media") is not True or rights.get("redistribution_allowed") is not False:
        raise ValueError("provenance binding does not enforce private non-redistributable media")
    manifest_sha = sha256_file(manifest_path)
    bindings = _as_records(provenance.get("bindings"), "provenance bindings")
    matches = [item for item in bindings if item.get("manifest_sha256") == manifest_sha]
    if len(matches) != 1 or matches[0].get("identity_match") is not True:
        raise ValueError("no unique SoccerDB identity binding matches this manifest")
    mapping = provenance.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("provenance mapping metadata is missing")
    _require_hash(mapping.get("sha256"), "mapping hash")
    return sha256_file(provenance_path), matches[0]


def _validate_commentary(
    commentary: dict[str, Any], commentary_path: Path,
    manifest_path: Path, visual_path: Path,
    visual_by_id: dict[str, dict[str, Any]], failure_clip_ids: set[str],
) -> tuple[str, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if commentary.get("schema_version") != "playground-commentary-crosscheck-summary-v1":
        raise ValueError("unsupported commentary cross-check schema")
    if commentary.get("manifest_sha256") != sha256_file(manifest_path):
        raise ValueError("commentary summary is not bound to this manifest")
    if commentary.get("visual_summary_sha256") != sha256_file(visual_path):
        raise ValueError("commentary summary is not bound to this visual summary")
    if commentary.get("primary_visual_predictions_unchanged") is not True:
        raise ValueError("commentary summary does not preserve the visual predictions")
    records = _as_records(commentary.get("clips", []), "commentary clips")
    failures = _as_records(commentary.get("failures", []), "commentary failures")
    record_by_id: dict[str, dict[str, Any]] = {}
    failure_by_id: dict[str, dict[str, Any]] = {}
    clip_ids = set(visual_by_id) | failure_clip_ids
    for item in records:
        clip_id = _require_clip_id(item.get("clip_id"))
        if clip_id not in clip_ids or clip_id in record_by_id:
            raise ValueError("commentary clip IDs are duplicated or not in the manifest")
        if item.get("relation") not in {"supports", "contradicts", "uninformative"}:
            raise ValueError("commentary relation is invalid")
        visual_item = visual_by_id.get(clip_id)
        if visual_item is None:
            raise ValueError("a commentary completion cannot exist without a visual prediction")
        if (
            item.get("visual_prediction") != visual_item.get("prediction")
            or item.get("visual_abstained") != visual_item.get("abstained")
        ):
            raise ValueError("commentary record does not preserve its bound visual prediction")
        commentary_prediction = item.get("commentary_prediction")
        commentary_abstained = item.get("commentary_abstained")
        if not isinstance(commentary_prediction, str) or not isinstance(commentary_abstained, bool):
            raise ValueError("commentary prediction fields are missing")
        commentary_confidence = _require_unit_interval(
            item.get("commentary_confidence"), "commentary confidence"
        )
        if commentary_abstained:
            if commentary_prediction != "insufficient_commentary_evidence" or commentary_confidence != 0.0:
                raise ValueError("commentary abstention fields are inconsistent")
        elif commentary_prediction == "insufficient_commentary_evidence":
            raise ValueError("commentary non-abstention cannot use the insufficiency sentinel")
        if visual_item.get("abstained") is True or visual_item.get("prediction") == "insufficient_visual_evidence":
            expected_relation = "uninformative"
        elif commentary_abstained or commentary_prediction == "insufficient_commentary_evidence":
            expected_relation = "uninformative"
        elif commentary_prediction == visual_item.get("prediction"):
            expected_relation = "supports"
        else:
            expected_relation = "contradicts"
        if item.get("relation") != expected_relation:
            raise ValueError("commentary relation disagrees with the sealed visual prediction")
        record_by_id[clip_id] = item
    for item in failures:
        clip_id = _require_clip_id(item.get("clip_id"))
        if clip_id not in clip_ids or clip_id in failure_by_id or clip_id in record_by_id:
            raise ValueError("commentary failure IDs are duplicated or overlap completed checks")
        failure_by_id[clip_id] = item
    if set(record_by_id) | set(failure_by_id) != clip_ids:
        raise ValueError("commentary summary must account for every requested clip exactly once")
    counts = commentary.get("counts")
    if isinstance(counts, dict) and (
        counts.get("requested") != len(clip_ids)
        or counts.get("crosschecks_completed") != len(records)
        or counts.get("failed_or_not_evaluated") != len(failures)
    ):
        raise ValueError("commentary summary counts are inconsistent")
    return sha256_file(commentary_path), record_by_id, failure_by_id


def _load_commentary_evidence(
    clip: dict[str, Any], *, project_root: Path, private_root: Path
) -> tuple[list[dict[str, Any]], str]:
    clip_id = clip["clip_id"]
    metadata = clip.get("commentary")
    if not isinstance(metadata, dict):
        raise ValueError(f"hash-bound commentary evidence is missing for {clip_id}")
    source = _resolve_private_media(
        metadata.get("path"), project_root=project_root, private_root=private_root,
        label=f"commentary evidence {clip_id}",
    )
    expected_sha = _require_hash(metadata.get("sha256"), "commentary evidence hash")
    if sha256_file(source) != expected_sha:
        raise ValueError(f"commentary evidence hash is stale for {clip_id}")
    evidence = _load_object(source, "commentary evidence")
    if evidence.get("schema_version") != "playground-commentary-evidence-v1":
        raise ValueError(f"unsupported commentary evidence schema for {clip_id}")
    if evidence.get("clip_id") != clip_id or evidence.get("source") != "SoccerNet-Echoes":
        raise ValueError(f"commentary evidence identity is invalid for {clip_id}")
    duration = evidence.get("clip_duration_s")
    if (
        not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not math.isfinite(float(duration))
        or not math.isclose(float(duration), float(clip["clip_duration_s"]), rel_tol=0.0, abs_tol=0.01)
    ):
        raise ValueError(f"commentary evidence duration is invalid for {clip_id}")
    segments = _as_records(evidence.get("segments"), "commentary evidence segments")
    if metadata.get("segment_count") != len(segments):
        raise ValueError(f"commentary evidence segment count is stale for {clip_id}")
    prior_start = -1.0
    clean: list[dict[str, Any]] = []
    for position, segment in enumerate(segments):
        interval = _require_temporal_pair(
            [segment.get("clip_relative_start_s"), segment.get("clip_relative_end_s")],
            f"commentary segment {position + 1}",
            duration_s=float(clip["clip_duration_s"]),
        )
        if interval[0] < prior_start:
            raise ValueError(f"commentary segments are not ordered for {clip_id}")
        prior_start = interval[0]
        text_value = segment.get("text")
        if not isinstance(text_value, str) or not text_value.strip():
            raise ValueError(f"commentary segment text is missing for {clip_id}")
        clean.append({"start": interval[0], "end": interval[1], "text": text_value.strip()})
    return clean, expected_sha


def _vtt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000.0))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _render_vtt(segments: list[dict[str, Any]]) -> str:
    cues = ["WEBVTT", "", "NOTE Automated SoccerNet-Echoes ASR; noisy post-hoc evidence, not ground truth.", ""]
    for index, segment in enumerate(segments, start=1):
        safe_text = html.escape(" ".join(segment["text"].splitlines()), quote=False)
        cues.extend([
            str(index),
            f"{_vtt_timestamp(segment['start'])} --> {_vtt_timestamp(segment['end'])}",
            safe_text,
            "",
        ])
    return "\n".join(cues)


def _transcript_html(segments: list[dict[str, Any]]) -> str:
    if not segments:
        return '<p class="muted">No automated ASR segment overlaps this clip.</p>'
    return "".join(
        '<li><time>' + _esc(_format_seconds([segment["start"], segment["end"]]))
        + '</time><span>' + _esc(segment["text"]) + '</span></li>'
        for segment in segments
    )


def _load_private_prediction(
    clip_id: str, visual_item: dict[str, Any], prediction_root: Path | None,
    private_root: Path, expected_model: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if prediction_root is None:
        return None, None
    prediction_dir = _require_within(prediction_root / clip_id, private_root, "prediction directory")
    prediction_path = prediction_dir / "prediction.json"
    receipt_path = prediction_dir / "receipt.json"
    if not prediction_path.is_file() or not receipt_path.is_file():
        raise ValueError(f"private prediction or receipt is missing for {clip_id}")
    expected_prediction_sha = _require_hash(visual_item.get("prediction_sha256"), "prediction hash")
    expected_receipt_sha = _require_hash(visual_item.get("receipt_sha256"), "prediction receipt hash")
    if sha256_file(prediction_path) != expected_prediction_sha or sha256_file(receipt_path) != expected_receipt_sha:
        raise ValueError(f"private prediction receipt binding is stale for {clip_id}")
    prediction = _load_object(prediction_path, "private visual prediction")
    receipt = _load_object(receipt_path, "private visual receipt")
    if prediction.get("schema_version") != "playground-output-v1":
        raise ValueError(f"private prediction schema is unsupported for {clip_id}")
    if receipt.get("schema_version") != "playground-real-clip-vlm-receipt-v1":
        raise ValueError(f"private prediction receipt schema is unsupported for {clip_id}")
    if prediction.get("clip_id") != clip_id or receipt.get("clip_id") != clip_id:
        raise ValueError(f"private prediction is bound to the wrong clip for {clip_id}")
    answer = prediction.get("answer", prediction.get("prediction"))
    if answer != visual_item.get("prediction") or prediction.get("abstained") != visual_item.get("abstained"):
        raise ValueError(f"private prediction disagrees with the public visual summary for {clip_id}")
    if (
        receipt.get("model_requested") != expected_model
        or receipt.get("model_reported") != expected_model
    ):
        raise ValueError(f"private prediction receipt model disagrees with the frozen visual model for {clip_id}")
    private_confidence = _require_unit_interval(
        prediction.get("confidence"), "private prediction confidence"
    )
    if not math.isclose(
        private_confidence,
        _require_unit_interval(visual_item.get("confidence"), "visual confidence"),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(f"private prediction confidence disagrees with the public summary for {clip_id}")
    _validate_evidence_contract(
        prediction,
        abstained=prediction.get("abstained") is True,
        label="private prediction",
        require_presence=True,
    )
    if prediction.get("abstained") is True:
        if prediction.get("temporal_evidence_s") != [0, 0] or prediction.get("spatial_evidence") != []:
            raise ValueError(f"private prediction abstention must explicitly use [0, 0] and [] for {clip_id}")
        reason = prediction.get("abstention_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"private prediction abstention reason is missing for {clip_id}")
    elif prediction.get("abstention_reason") not in (None, ""):
        raise ValueError(f"private prediction non-abstention reason must be null for {clip_id}")
    return prediction, receipt


def _scalar(value: Any) -> str | None:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _runtime_projection(path: Path) -> dict[str, str]:
    receipt = _load_object(path, "runtime receipt")
    projection: dict[str, str] = {"sha256": sha256_file(path)}
    # Only allowlisted operational metadata is rendered.  Paths, endpoints,
    # prompts, environment variables, and arbitrary receipt fields stay out.
    for key in (
        "schema_version", "model", "model_requested", "model_reported",
        "backend", "runtime", "device", "gpu", "application", "elapsed_ms",
    ):
        value = _scalar(receipt.get(key))
        if value is not None:
            projection[key] = value
    return projection


def _validate_runtime_receipts(
    frozen: dict[str, Any], visual: dict[str, Any],
    runtime_receipts: list[dict[str, str]],
) -> None:
    """Require the recovery demo to use the runtime receipt frozen before validation."""
    if frozen.get("schema_version") != "playground-frozen-visual-config-v2":
        return
    frozen_runtime = frozen.get("runtime_receipt")
    if not isinstance(frozen_runtime, dict):
        raise ValueError("frozen v2 runtime receipt binding is missing")
    if frozen_runtime.get("schema_version") != "playground-isolated-vlm-runtime-receipt-v1":
        raise ValueError("frozen v2 runtime receipt schema is unsupported")
    expected_sha = _require_hash(
        frozen_runtime.get("sha256"), "frozen v2 runtime receipt hash"
    )
    visual_frozen = visual.get("frozen_config")
    if (
        not isinstance(visual_frozen, dict)
        or visual_frozen.get("runtime_receipt_sha256") != expected_sha
    ):
        raise ValueError("visual summary is not bound to the frozen v2 runtime receipt")
    supplied = {item.get("sha256") for item in runtime_receipts}
    if expected_sha not in supplied:
        raise ValueError("supplied runtime receipt does not match the frozen v2 binding")
    matching = [item for item in runtime_receipts if item.get("sha256") == expected_sha]
    if len(matching) != 1 or matching[0].get("schema_version") != "playground-isolated-vlm-runtime-receipt-v1":
        raise ValueError("supplied v2 runtime receipt schema is unsupported")


def _format_label(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "Not available"
    return value.replace("_", " ").strip().title()


def _format_percent(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _format_confidence(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "Not reported"
    return f"{100.0 * float(value):.0f}%"


def _format_seconds(value: Any) -> str:
    if (
        not isinstance(value, list) or len(value) != 2
        or any(not isinstance(item, (int, float)) or isinstance(item, bool) for item in value)
    ):
        return "Not available"
    return f"{float(value[0]):.2f}–{float(value[1]):.2f} s"


def _short_hash(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "not recorded"
    return f"{value[:12]}…" if len(value) > 12 else value


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _tags(values: Any, *, empty: str = "Not available") -> str:
    if not isinstance(values, list) or not values:
        return f'<span class="muted">{_esc(empty)}</span>'
    clean = [str(item) for item in values if isinstance(item, (str, int, float))]
    if not clean:
        return f'<span class="muted">{_esc(empty)}</span>'
    return "".join(f'<span class="tag">{_esc(_format_label(item))}</span>' for item in clean)


def _metric_cards(visual: dict[str, Any]) -> str:
    counts = visual["counts"]
    primary = visual.get("metrics", {}).get("primary_requested_set", {})
    if not isinstance(primary, dict):
        primary = {}
    model_id = str(visual.get("model", ""))
    is_qwen_comparison = model_id == "qwen/qwen3.5-9b"
    is_recovery = (
        visual.get("frozen_config", {}).get("schema_version") == "playground-frozen-visual-config-v2"
        and not is_qwen_comparison
    )
    if is_qwen_comparison:
        schema_label = "Schema-valid Qwen comparison"
        schema_note = "Strict structured output on the explicitly post-hoc engineering comparison."
    elif is_recovery:
        schema_label = "Schema-valid recovery pass"
        schema_note = "Strict structured output on the post-hoc serving-recovery rerun."
    else:
        schema_label = "Schema-valid first pass"
        schema_note = "Strict structured output on the original attempt."
    cards = [
        ("Requested clips", str(counts.get("requested", "—")), "Every requested clip stays in the denominator."),
        ("Completed", f'{counts.get("completed", "—")}/{counts.get("requested", "—")}', "Timeouts and malformed outputs are failures, not exclusions."),
        (schema_label, _format_percent(primary.get("schema_valid_first_pass_rate")), schema_note),
        (
            "Allowed-label accuracy",
            _format_percent(primary.get("allowed_label_accuracy_all_clips")),
            "Correct if the prediction matches any mapped SoccerNet point-label timestamp in the 10 s window; visibility was not independently adjudicated.",
        ),
        ("Single-label exact", _format_percent(primary.get("single_label_exact_accuracy")), "Exact accuracy only on windows with one mapped label; failures count wrong."),
    ]
    return "".join(
        '<div class="metric-card">'
        f'<span class="metric-label">{_esc(label)}</span>'
        f'<strong>{_esc(value)}</strong><small>{_esc(note)}</small></div>'
        for label, value, note in cards
    )


def _commentary_panel(
    clip_id: str, audio_src: str, caption_src: str, transcript: str,
    record: dict[str, Any] | None, failure: dict[str, Any] | None,
    commentary_included: bool,
) -> str:
    if record is not None:
        relation = _format_label(record.get("relation"))
        prediction = _format_label(record.get("commentary_prediction"))
        confidence = _format_confidence(record.get("commentary_confidence"))
        detail = (
            f'<div class="commentary-result relation-{_esc(record.get("relation"))}">'
            f'<span class="eyebrow">Post-hoc ASR check · {_esc(relation)}</span>'
            f'<strong>{_esc(prediction)}</strong><span>Confidence {confidence}</span></div>'
        )
    elif failure is not None:
        detail = (
            '<div class="commentary-result relation-uninformative">'
            f'<span class="eyebrow">Post-hoc ASR check · Not evaluated</span>'
            f'<strong>{_esc(_format_label(failure.get("error_code")))}</strong></div>'
        )
    elif commentary_included:
        detail = (
            '<div class="commentary-result relation-uninformative"><span class="eyebrow">'
            'Post-hoc ASR check · No record</span><strong>Unavailable for this clip</strong></div>'
        )
    else:
        detail = (
            '<div class="commentary-result relation-uninformative"><span class="eyebrow">'
            'Post-hoc ASR check</span><strong>Not run in this build</strong></div>'
        )
    cid = _esc(clip_id)
    return f"""
      <div class="unlock-row">
        <button class="secondary commentary-button" type="button" disabled
                aria-expanded="false" aria-controls="commentary-{cid}"
                data-commentary-button>Play commentary version</button>
        <span class="unlock-note" data-unlock-note>Unlocks after the silent clip ends.</span>
      </div>
      <section class="commentary-panel" id="commentary-{cid}" hidden>
        <div class="separation-note"><strong>Sealed post-visual consistency probe—not ground truth.</strong> Audio was withheld from the visual request. Automated ASR describes the same broadcast event and never changes the sealed visual prediction.</div>
        <video class="video commentary-video" controls playsinline preload="none" hidden
               aria-label="Commentary version for clip {cid}" aria-describedby="transcript-{cid}"
               data-commentary-player>
          <source src="{_esc(audio_src)}" type="video/mp4">
          <track kind="captions" srclang="en" label="Automated SoccerNet-Echoes ASR" src="{_esc(caption_src)}" default>
          Your browser does not support local MP4 playback.
        </video>
        {detail}
        <details class="transcript" id="transcript-{cid}"><summary>Automated ASR transcript · noisy evidence</summary>
          <p class="transcript-warning">SoccerNet-Echoes ASR may be incomplete or wrong. It is a post-hoc modality probe, not an annotation.</p>
          <ol>{transcript}</ol>
        </details>
      </section>
    """


def _truth_panel(clip_id: str, truth: dict[str, Any], visual_item: dict[str, Any] | None) -> str:
    play_type = _format_label(truth.get("play_type"))
    allowed = truth.get("allowed_play_types_in_window", [truth.get("play_type")])
    eligible = "Single-label window" if truth.get("single_label_eligible") is True else "Multi-event window"
    if visual_item is None:
        comparison = "No prediction was returned. The failure remains incorrect in the primary metric."
        comparison_class = "comparison-failed"
    elif visual_item.get("allowed_correct") is True:
        comparison = "The prediction matches one of the mapped point-label timestamps in this window."
        comparison_class = "comparison-correct"
    else:
        comparison = "The prediction does not match the mapped point-label set for this window."
        comparison_class = "comparison-wrong"
    cid = _esc(clip_id)
    return f"""
      <div class="truth-actions">
        <button class="secondary truth-button" type="button" disabled aria-expanded="false"
                aria-controls="truth-{cid}" data-truth-button>Reveal mapped label</button>
      </div>
      <section class="truth-panel" id="truth-{cid}" hidden>
        <span class="eyebrow">SoccerNet-v2 center point label · hidden from model</span>
        <div class="truth-grid"><div><strong>{_esc(play_type)}</strong><span>{_esc(eligible)}</span></div>
        <div><span class="field-label">Mapped point labels in window</span><div class="tag-row">{_tags(allowed)}</div></div></div>
        <p class="comparison {_esc(comparison_class)}">{_esc(comparison)}</p>
      </section>
    """


def _clip_card(
    index: int, total: int, clip: dict[str, Any],
    visual_item: dict[str, Any] | None, visual_failure: dict[str, Any] | None,
    prediction: dict[str, Any] | None, receipt: dict[str, Any] | None,
    commentary_record: dict[str, Any] | None, commentary_failure: dict[str, Any] | None,
    commentary_included: bool,
    visual_src: str, audio_src: str, caption_src: str, transcript: str,
) -> str:
    clip_id = clip["clip_id"]
    cid = _esc(clip_id)
    if visual_failure is not None:
        result_title = "No visual prediction"
        result_value = _format_label(visual_failure.get("error_code"))
        result_note = "The first-pass failure remains in the requested-set denominator."
        status_class = "status-failed"
        confidence = "Not available"
        temporal = "Not available"
        spatial: Any = []
        abstention = ""
        latency = "Not completed"
    else:
        assert visual_item is not None
        result_title = "Visual-only prediction"
        result_value = _format_label(visual_item.get("prediction"))
        confidence = _format_confidence(visual_item.get("confidence"))
        is_abstained = visual_item.get("abstained") is True
        status_class = "status-abstained" if is_abstained else "status-completed"
        result_note = "The model abstained instead of forcing a play label." if is_abstained else "Returned under the frozen structured-output contract."
        merged = dict(visual_item)
        if prediction is not None:
            merged.update(prediction)
        temporal = "Not claimed (abstained)" if is_abstained else _format_seconds(merged.get("temporal_evidence_s"))
        spatial = [] if is_abstained else merged.get("spatial_evidence", [])
        reason = merged.get("abstention_reason")
        abstention = (
            f'<p class="abstention"><strong>Why it abstained:</strong> {_esc(reason)}</p>'
            if isinstance(reason, str) and reason else ""
        )
        elapsed = visual_item.get("elapsed_ms", receipt.get("elapsed_ms") if receipt else None)
        latency = f"{int(elapsed):,} ms" if isinstance(elapsed, (int, float)) else "Not reported"
    return f"""
    <article class="clip-card" id="clip-{cid}" role="tabpanel" aria-labelledby="tab-{cid}"
             data-clip-card data-clip-index="{index}" {'hidden' if index else ''}>
      <div class="clip-header">
        <div><span class="eyebrow">Requested clip {index + 1} of {total}</span><h2>{cid}</h2></div>
        <div class="badge-row"><span class="badge visual-badge">Visual only</span><span class="badge">10-second event window</span></div>
      </div>
      <div class="demo-grid">
        <section class="viewer-panel" aria-labelledby="viewer-title-{cid}">
          <div class="panel-heading"><div><span class="step">1</span><h3 id="viewer-title-{cid}">Watch without audio</h3></div><span class="audio-state">Audio stream: none</span></div>
          <video class="video visual-video" controls playsinline preload="metadata"
                 aria-label="Silent visual-only soccer clip {cid}" data-visual-player>
            <source src="{_esc(visual_src)}" type="video/mp4">
            Your browser does not support local MP4 playback.
          </video>
          <p class="watch-note" data-watch-note>Watch the full 10 seconds to unlock commentary and the mapped label.</p>
        </section>
        <section class="result-panel {status_class}" aria-labelledby="result-title-{cid}">
          <div class="panel-heading"><div><span class="step">2</span><h3 id="result-title-{cid}">Inspect the frozen result</h3></div></div>
          <span class="eyebrow">{_esc(result_title)}</span>
          <div class="prediction">{_esc(result_value)}</div>
          <p class="result-note">{_esc(result_note)}</p>{abstention}
          <dl class="evidence-grid">
            <div><dt>Model self-score (uncalibrated)</dt><dd>{_esc(confidence)}</dd></div>
            <div><dt>Temporal evidence</dt><dd>{_esc(temporal)}</dd></div>
            <div><dt>Latency</dt><dd>{_esc(latency)}</dd></div>
            <div class="wide"><dt>Spatial evidence</dt><dd class="tag-row">{_tags(spatial)}</dd></div>
          </dl>
          <p class="evidence-caveat">Evidence fields are model-reported. Neither the self-score nor temporal/spatial grounding was externally evaluated.</p>
        </section>
      </div>
      <section class="reveal-zone" aria-label="Post-visual review">
        <div class="panel-heading"><div><span class="step">3</span><h3>Check audio and labels afterward</h3></div></div>
        <div class="post-grid">
          <div>{_commentary_panel(clip_id, audio_src, caption_src, transcript, commentary_record, commentary_failure, commentary_included)}</div>
          <div>{_truth_panel(clip_id, clip['ground_truth'], visual_item)}</div>
        </div>
      </section>
    </article>
    """


def _technical_panel(
    visual: dict[str, Any], manifest: dict[str, Any], frozen: dict[str, Any], frozen_sha: str,
    provenance: dict[str, Any], binding: dict[str, Any], provenance_sha: str,
    commentary: dict[str, Any] | None, commentary_sha: str | None,
    runtime_receipts: list[dict[str, str]], manifest_sha: str, visual_sha: str,
) -> str:
    mapping = provenance.get("mapping", {})
    sampling = visual.get("sampling", {})
    runtime_rows = "".join(
        '<li><code>' + _esc(_short_hash(item.get("sha256"))) + '</code> · '
        + _esc(item.get("model_reported", item.get("model", item.get("schema_version", "receipt"))))
        + (f' · {_esc(item["device"])}' if "device" in item else "") + '</li>'
        for item in runtime_receipts
    ) or '<li class="muted">No separate runtime receipt supplied; per-clip receipts remain hash-bound.</li>'
    commentary_text = (
        f'{_esc(commentary.get("model", "text model"))} · {_esc(_short_hash(commentary_sha))}'
        if commentary is not None and commentary_sha is not None else "Not included in this build"
    )
    first_clip = manifest.get("clips", [{}])[0]
    source_meta = first_clip.get("visual_only", {}) if isinstance(first_clip, dict) else {}
    source_width = source_meta.get("width", "not recorded") if isinstance(source_meta, dict) else "not recorded"
    source_height = source_meta.get("height", "not recorded") if isinstance(source_meta, dict) else "not recorded"
    sample_count = sampling.get("sample_count", "—")
    sheet_count = sampling.get("contact_sheets", sample_count)
    model_id = str(visual.get("model", ""))
    tuning_note = (
        "No weight updates. Qwen was selected post hoc after Gemma results; "
        "the visual prompt, taxonomy, and schema were reused."
        if model_id == "qwen/qwen3.5-9b" else
        "No weight updates. Development clips were used for prompt, schema, and runtime engineering."
    )
    return f"""
    <details class="technical">
      <summary>Technical inspection · hashes, runtime, and provenance</summary>
      <div class="technical-grid">
        <section><span class="eyebrow">Inference contract</span><dl>
          <div><dt>Model</dt><dd>{_esc(visual.get('model'))}</dd></div>
          <div><dt>Input</dt><dd>Physically silent MP4 → {_esc(sample_count)} uniformly sampled stills from {_esc(source_width)}×{_esc(source_height)} source, packaged as {_esc(sheet_count)} image sheet(s); no native video/audio path</dd></div>
          <div><dt>Prompt SHA</dt><dd><code>{_esc(_short_hash(visual.get('prompt_sha256')))}</code></dd></div>
          <div><dt>Frozen config SHA</dt><dd><code>{_esc(_short_hash(frozen_sha))}</code></dd></div>
          <div><dt>Sampler</dt><dd>{_esc(frozen.get('sampler_version', 'not recorded'))}</dd></div>
        </dl></section>
        <section><span class="eyebrow">Dataset binding</span><dl>
          <div><dt>Provider</dt><dd>{_esc(manifest.get('provider', 'SoccerNet'))}</dd></div>
          <div><dt>Split</dt><dd>{_esc(manifest.get('split'))}</dd></div>
          <div><dt>Manifest SHA</dt><dd><code>{_esc(_short_hash(manifest_sha))}</code></dd></div>
          <div><dt>SoccerDB media ID</dt><dd><code>{_esc(binding.get('soccerdb_media_name', 'not recorded'))}</code></dd></div>
          <div><dt>Mapping commit</dt><dd><code>{_esc(_short_hash(mapping.get('commit')))}</code></dd></div>
          <div><dt>Mapping SHA</dt><dd><code>{_esc(_short_hash(mapping.get('sha256')))}</code></dd></div>
        </dl></section>
        <section><span class="eyebrow">Artifact seals</span><dl>
          <div><dt>Visual summary</dt><dd><code>{_esc(_short_hash(visual_sha))}</code></dd></div>
          <div><dt>Provenance receipt</dt><dd><code>{_esc(_short_hash(provenance_sha))}</code></dd></div>
          <div><dt>Commentary check</dt><dd>{commentary_text}</dd></div>
          <div><dt>Visual predictions changed by audio?</dt><dd>No</dd></div>
          <div><dt>Weight fine-tuning?</dt><dd>{_esc(tuning_note)}</dd></div>
        </dl></section>
        <section><span class="eyebrow">Runtime receipts</span><ul class="receipt-list">{runtime_rows}</ul></section>
      </div>
      <p class="claim-boundary">{_esc(provenance.get('claim_boundary', 'SoccerDB/SoccerNet identity is hash-bound; evaluation labels come from SoccerNet-v2.'))}</p>
    </details>
    """


def _render_html(
    *, cards: str, visual: dict[str, Any], manifest: dict[str, Any],
    technical: str, commentary: dict[str, Any] | None,
) -> str:
    counts = visual["counts"]
    clip_buttons = "".join(
        f'<button type="button" class="clip-tab" role="tab" id="tab-{_esc(clip["clip_id"])}" data-clip-tab="{i}" aria-label="Requested clip {i + 1}" aria-controls="clip-{_esc(clip["clip_id"])}" aria-selected="{"true" if i == 0 else "false"}">{i + 1}</button>'
        for i, clip in enumerate(manifest["clips"])
    )
    commentary_badge = "Sealed commentary consistency probe" if commentary is not None else "Commentary probe pending"
    interpretation = visual.get("interpretation", "Tiny feasibility run; not a benchmark estimate.")
    model_id = str(visual.get("model", ""))
    is_qwen_comparison = model_id == "qwen/qwen3.5-9b"
    is_recovery = (
        visual.get("frozen_config", {}).get("schema_version") == "playground-frozen-visual-config-v2"
        and not is_qwen_comparison
    )
    if is_qwen_comparison:
        run_badge = "Post-hoc Qwen engineering comparison"
        run_disclosure = (
            " This UI shows Qwen selected after the Gemma results on the same six clips. "
            "The decoded frames match, but their image-sheet grouping differs; do not read this as a causal model ranking."
        )
    elif is_recovery:
        run_badge = "Post-hoc serving-recovery rerun"
        run_disclosure = (
            " This UI shows the explicitly post-hoc serving-recovery rerun on the same clips; "
            "the failed original pass is preserved in the report and presentation."
        )
    else:
        run_badge = "Untouched primary pass"
        run_disclosure = ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; media-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>PlayGround · Real Soccer VLM Demo</title>
  <style>
    :root {{ color-scheme: light; --ink:#10221a; --muted:#586a61; --paper:#f7faf7; --card:#fff; --line:#d8e4dc; --green:#0b6b3a; --lime:#c9f05b; --navy:#112b2b; --red:#a73a2a; --amber:#94610a; --shadow:0 18px 48px rgba(19,50,35,.10); }}
    * {{ box-sizing:border-box; }} [hidden] {{ display:none !important; }}
    html {{ scroll-behavior:smooth; }} body {{ margin:0; background:var(--paper); color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.45; }}
    button,summary,video {{ font:inherit; }} button {{ cursor:pointer; }} button:disabled {{ cursor:not-allowed; opacity:.48; }}
    :focus-visible {{ outline:3px solid #2c7ef8; outline-offset:3px; }}
    .skip {{ position:absolute; left:1rem; top:-5rem; padding:.7rem 1rem; background:#fff; color:#000; z-index:20; }} .skip:focus {{ top:1rem; }}
    .sr-status {{ position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }}
    .privacy {{ background:#5f1d14; color:#fff; padding:.62rem clamp(1rem,4vw,4rem); font-size:.86rem; letter-spacing:.02em; display:flex; gap:.75rem; align-items:center; }}
    .privacy strong {{ text-transform:uppercase; font-size:.76rem; background:#fff; color:#5f1d14; padding:.2rem .42rem; border-radius:.2rem; }}
    header {{ background:var(--navy); color:#fff; padding:clamp(2.4rem,6vw,5.8rem) clamp(1rem,5vw,5rem) 2.4rem; }}
    .hero {{ max-width:1220px; margin:auto; display:grid; grid-template-columns:minmax(0,1.35fr) minmax(260px,.65fr); gap:3rem; align-items:end; }}
    .kicker,.eyebrow {{ display:block; text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; font-weight:800; color:var(--green); }} header .kicker {{ color:var(--lime); }}
    h1 {{ margin:.5rem 0 1rem; max-width:780px; font-size:clamp(2.25rem,5vw,5rem); line-height:.98; letter-spacing:-.045em; }}
    .lede {{ font-size:clamp(1rem,1.6vw,1.25rem); color:#d7e5dd; max-width:760px; }}
    .method-pills,.badge-row {{ display:flex; flex-wrap:wrap; gap:.45rem; }} .method-pills span,.badge {{ border:1px solid rgba(255,255,255,.26); border-radius:999px; padding:.38rem .65rem; font-size:.76rem; }}
    .hero-stat {{ border-left:1px solid rgba(255,255,255,.25); padding-left:2rem; }} .hero-stat strong {{ display:block; font-size:3.2rem; color:var(--lime); line-height:1; }} .hero-stat span {{ color:#c8d8cf; }}
    main {{ max-width:1220px; margin:auto; padding:2rem clamp(1rem,3vw,2.25rem) 5rem; }}
    .metric-strip {{ display:grid; grid-template-columns:repeat(5,1fr); gap:.8rem; margin-top:-3.2rem; position:relative; }}
    .metric-card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:1rem; box-shadow:var(--shadow); min-height:150px; display:flex; flex-direction:column; }}
    .metric-card strong {{ font-size:2rem; letter-spacing:-.04em; margin:.45rem 0; }} .metric-card small {{ color:var(--muted); margin-top:auto; }} .metric-label {{ font-size:.73rem; text-transform:uppercase; font-weight:800; letter-spacing:.08em; color:var(--green); }}
    .run-note {{ margin:1.25rem 0 2rem; padding:1rem 1.2rem; border-left:4px solid var(--amber); background:#fff7de; color:#553d12; border-radius:0 10px 10px 0; }}
    .clip-nav {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:2rem 0 1rem; }} .tabs {{ display:flex; gap:.4rem; flex-wrap:wrap; }}
    .clip-tab,.nav-button,.secondary {{ border:1px solid var(--line); color:var(--ink); background:#fff; border-radius:9px; min-width:2.6rem; padding:.62rem .8rem; font-weight:750; }} .clip-tab[aria-selected="true"] {{ background:var(--green); color:#fff; border-color:var(--green); }} .nav-buttons {{ display:flex; gap:.45rem; }}
    a:focus-visible,button:focus-visible,summary:focus-visible,video:focus-visible {{ outline:3px solid var(--lime); outline-offset:3px; }}
    .clip-card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; overflow:hidden; box-shadow:var(--shadow); }}
    .clip-header {{ padding:1.2rem 1.35rem; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:1rem; align-items:center; }} .clip-header h2 {{ margin:.18rem 0 0; font-size:1.05rem; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
    .clip-header .badge {{ color:var(--muted); border-color:var(--line); }} .clip-header .visual-badge {{ color:var(--green); background:#e7f7ec; border-color:#b9dec7; }}
    .demo-grid {{ display:grid; grid-template-columns:minmax(0,1.34fr) minmax(300px,.66fr); }} .viewer-panel,.result-panel {{ padding:1.35rem; }} .viewer-panel {{ background:#eff5f0; }} .result-panel {{ border-left:1px solid var(--line); }}
    .panel-heading {{ display:flex; align-items:center; justify-content:space-between; gap:.8rem; margin-bottom:1rem; }} .panel-heading>div {{ display:flex; align-items:center; gap:.65rem; }} .panel-heading h3 {{ margin:0; font-size:1rem; }} .step {{ display:grid; place-items:center; width:1.7rem; height:1.7rem; background:var(--ink); color:#fff; border-radius:50%; font-size:.78rem; font-weight:800; }}
    .audio-state {{ font-size:.72rem; font-weight:750; color:var(--green); }} .video {{ width:100%; display:block; background:#07110c; border-radius:12px; aspect-ratio:16/9; }} .watch-note,.result-note,.evidence-caveat {{ color:var(--muted); font-size:.84rem; }}
    .prediction {{ font-size:clamp(2rem,4vw,3.35rem); font-weight:850; letter-spacing:-.045em; line-height:1.03; margin:.4rem 0 .7rem; }}
    .status-completed {{ box-shadow:inset 5px 0 var(--green); }} .status-abstained {{ box-shadow:inset 5px 0 var(--amber); }} .status-failed {{ box-shadow:inset 5px 0 var(--red); }}
    .abstention {{ background:#fff4d6; padding:.7rem; border-radius:8px; font-size:.84rem; }}
    .evidence-grid {{ margin:1.2rem 0 0; display:grid; grid-template-columns:1fr 1fr; gap:.8rem; }} .evidence-grid div {{ padding-top:.7rem; border-top:1px solid var(--line); }} .evidence-grid .wide {{ grid-column:1/-1; }} dt,.field-label {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:800; }} dd {{ margin:.25rem 0 0; font-weight:700; }}
    .tag-row {{ display:flex; gap:.35rem; flex-wrap:wrap; }} .tag {{ display:inline-block; border-radius:999px; background:#e7f1ea; color:#214b33; padding:.25rem .55rem; font-size:.73rem; font-weight:700; }} .muted {{ color:var(--muted); }}
    .reveal-zone {{ border-top:1px solid var(--line); padding:1.35rem; }} .post-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }} .post-grid>div {{ border:1px solid var(--line); border-radius:12px; padding:1rem; min-height:104px; }}
    .unlock-row {{ display:flex; align-items:center; gap:.8rem; flex-wrap:wrap; }} .secondary {{ color:var(--green); }} .unlock-note {{ color:var(--muted); font-size:.78rem; }}
    .commentary-panel,.truth-panel {{ margin-top:1rem; }} .separation-note {{ padding:.72rem; border-left:3px solid var(--green); background:#edf7ef; font-size:.82rem; margin-bottom:.8rem; }} .commentary-video {{ margin-bottom:.8rem; }}
    .transcript {{ margin-top:.8rem; border-top:1px solid var(--line); padding-top:.7rem; }} .transcript summary {{ cursor:pointer; font-weight:800; }} .transcript-warning {{ color:var(--muted); font-size:.78rem; }} .transcript ol {{ margin:.6rem 0 0; padding:0; list-style:none; display:grid; gap:.45rem; }} .transcript li {{ display:grid; grid-template-columns:95px 1fr; gap:.65rem; font-size:.82rem; }} .transcript time {{ color:var(--green); font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.75rem; }}
    .commentary-result {{ border-radius:9px; padding:.75rem; display:grid; grid-template-columns:1fr auto; gap:.25rem .7rem; align-items:center; }} .commentary-result .eyebrow {{ grid-column:1/-1; }} .commentary-result span:last-child {{ color:var(--muted); font-size:.78rem; }} .relation-supports {{ background:#e6f5e9; }} .relation-contradicts {{ background:#fae7e2; }} .relation-uninformative {{ background:#f1f3f1; }}
    .truth-grid {{ display:grid; grid-template-columns:.7fr 1.3fr; gap:1rem; margin-top:.45rem; }} .truth-grid strong {{ display:block; font-size:1.55rem; }} .truth-grid span {{ color:var(--muted); font-size:.78rem; }} .comparison {{ padding:.65rem; border-radius:8px; font-weight:700; font-size:.84rem; }} .comparison-correct {{ background:#e6f5e9; }} .comparison-wrong,.comparison-failed {{ background:#fae7e2; }}
    .technical {{ margin-top:1.5rem; border:1px solid var(--line); border-radius:14px; background:#fff; }} .technical summary {{ padding:1rem 1.2rem; font-weight:800; cursor:pointer; }} .technical-grid {{ border-top:1px solid var(--line); padding:1.2rem; display:grid; grid-template-columns:repeat(2,1fr); gap:1.5rem; }} .technical dl {{ margin:.5rem 0; }} .technical dl div {{ display:grid; grid-template-columns:140px 1fr; gap:.5rem; padding:.38rem 0; border-bottom:1px solid #edf1ee; }} .technical dd {{ overflow-wrap:anywhere; font-weight:600; }} code {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.82em; }} .receipt-list {{ margin:.6rem 0; padding-left:1.2rem; }} .claim-boundary {{ margin:0 1.2rem 1.2rem; background:#f0f4f1; padding:.8rem; border-radius:8px; color:var(--muted); font-size:.83rem; }}
    .keyboard-help {{ color:var(--muted); font-size:.78rem; margin-top:.8rem; }} kbd {{ background:#fff; border:1px solid var(--line); border-bottom-width:2px; border-radius:4px; padding:.05rem .3rem; }}
    footer {{ max-width:1220px; margin:auto; padding:0 clamp(1rem,3vw,2.25rem) 3rem; color:var(--muted); font-size:.8rem; }}
    @media (max-width:900px) {{ .hero,.demo-grid,.post-grid {{ grid-template-columns:1fr; }} .hero-stat {{ border-left:0; padding-left:0; }} .metric-strip {{ grid-template-columns:repeat(2,1fr); margin-top:1rem; }} .result-panel {{ border-left:0; border-top:1px solid var(--line); }} .technical-grid {{ grid-template-columns:1fr; }} }}
    @media (max-width:560px) {{ .metric-strip {{ grid-template-columns:1fr; }} .clip-header,.clip-nav {{ align-items:flex-start; flex-direction:column; }} .truth-grid,.technical dl div {{ grid-template-columns:1fr; }} .nav-buttons {{ width:100%; }} .nav-button {{ flex:1; }} }}
    @media (prefers-reduced-motion:reduce) {{ html {{ scroll-behavior:auto; }} * {{ transition:none !important; }} }}
  </style>
</head>
<body>
  <a class="skip" href="#demo">Skip to demo</a>
  <div class="privacy"><strong>Private research media</strong><span>Authorized non-commercial demo only · do not copy, publish, stream, or redistribute.</span></div>
  <header>
    <div class="hero">
      <div><span class="kicker">PlayGround · local VLM feasibility study</span><h1>Can a local VLM classify a curated soccer event window from silent frames?</h1>
      <p class="lede">Given a label-selected 10-second SoccerNet window, the model receives ordered stills and must return one closed-taxonomy action label or abstain. Audio and mapped labels stay outside the visual request.</p>
      <div class="method-pills"><span>Real footage</span><span>Local model</span><span>Silent visual pass</span><span>{_esc(commentary_badge)}</span><span>{_esc(run_badge)}</span></div></div>
      <div class="hero-stat"><strong>{_esc(counts.get('requested'))}</strong><span>curated 10-second clips from one match; a case study, not a population estimate</span></div>
    </div>
  </header>
  <main id="demo">
    <section class="metric-strip" aria-label="Primary requested-set metrics">{_metric_cards(visual)}</section>
    <p class="run-note"><strong>Read this as a systems result, not a benchmark.</strong> {_esc(interpretation + run_disclosure)}</p>
    <p class="claim-boundary"><strong>Interface disclosure.</strong> Playback gating is a presentation aid, not access control. Experimental separation comes from the visual summary being hash-sealed before commentary was queried; this static local page contains already-computed evidence.</p>
    <nav class="clip-nav" aria-label="Choose demo clip"><div class="tabs" role="tablist" aria-label="Requested clips">{clip_buttons}</div>
      <div class="nav-buttons"><button class="nav-button" type="button" data-prev>Previous clip</button><button class="nav-button" type="button" data-next>Next clip</button></div></nav>
    <div class="sr-status" aria-live="polite" data-status></div>
    {cards}
    <p class="keyboard-help"><kbd>←</kbd>/<kbd>→</kbd>, <kbd>Home</kbd>, and <kbd>End</kbd> navigate focused clip tabs; <kbd>Alt</kbd> + <kbd>←</kbd>/<kbd>→</kbd> works anywhere. Native video controls remain fully keyboard accessible.</p>
    {technical}
  </main>
  <footer>Offline artifact · no external scripts, fonts, trackers, or network requests · visual predictions are fixed before commentary is opened.</footer>
  <script>
  (() => {{
    const cards = [...document.querySelectorAll('[data-clip-card]')];
    const tabs = [...document.querySelectorAll('[data-clip-tab]')];
    const status = document.querySelector('[data-status]');
    let current = 0;
    const pauseAll = except => document.querySelectorAll('video').forEach(v => {{ if (v !== except) v.pause(); }});
    function show(index, focusTab = false) {{
      current = (index + cards.length) % cards.length;
      cards.forEach((card, i) => card.hidden = i !== current);
      tabs.forEach((tab, i) => {{ tab.setAttribute('aria-selected', i === current ? 'true' : 'false'); tab.tabIndex = i === current ? 0 : -1; }});
      pauseAll(null);
      status.textContent = `Showing requested clip ${{current + 1}} of ${{cards.length}}`;
      if (focusTab) tabs[current].focus();
    }}
    tabs.forEach((tab, i) => {{
      tab.addEventListener('click', () => show(i));
      tab.addEventListener('keydown', event => {{
        let target = null;
        if (event.key === 'ArrowRight') target = i + 1;
        if (event.key === 'ArrowLeft') target = i - 1;
        if (event.key === 'Home') target = 0;
        if (event.key === 'End') target = tabs.length - 1;
        if (target === null) return;
        event.preventDefault(); show(target, true);
      }});
    }});
    document.querySelector('[data-prev]').addEventListener('click', () => show(current - 1, true));
    document.querySelector('[data-next]').addEventListener('click', () => show(current + 1, true));
    document.addEventListener('keydown', event => {{
      if (!event.altKey || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return;
      event.preventDefault(); show(current + (event.key === 'ArrowRight' ? 1 : -1), true);
    }});
    cards.forEach(card => {{
      const visual = card.querySelector('[data-visual-player]');
      const commentaryButton = card.querySelector('[data-commentary-button]');
      const truthButton = card.querySelector('[data-truth-button]');
      const note = card.querySelector('[data-unlock-note]');
      const watchNote = card.querySelector('[data-watch-note]');
      visual.addEventListener('play', () => pauseAll(visual));
      visual.addEventListener('ended', () => {{
        commentaryButton.disabled = false; truthButton.disabled = false;
        note.textContent = 'Silent first pass complete.'; watchNote.textContent = 'Visual review complete. Commentary and labels are now unlocked.';
        status.textContent = `Silent review complete for validation clip ${{current + 1}}; commentary and mapped label unlocked.`;
      }});
      commentaryButton.addEventListener('click', () => {{
        const panel = card.querySelector('#' + commentaryButton.getAttribute('aria-controls'));
        const player = panel.querySelector('[data-commentary-player]');
        panel.hidden = false; player.hidden = false; commentaryButton.setAttribute('aria-expanded', 'true');
        pauseAll(player); const attempt = player.play(); if (attempt) attempt.catch(() => {{}});
      }});
      truthButton.addEventListener('click', () => {{
        const panel = card.querySelector('#' + truthButton.getAttribute('aria-controls'));
        const opening = panel.hidden; panel.hidden = !opening;
        truthButton.setAttribute('aria-expanded', opening ? 'true' : 'false');
        truthButton.textContent = opening ? 'Hide mapped label' : 'Reveal mapped label';
      }});
    }});
    show(0);
  }})();
  </script>
</body>
</html>
"""


def _copy_bound_media(
    source: Path, expected_sha: str, destination: Path, *, label: str
) -> dict[str, Any]:
    _require_hash(expected_sha, f"{label} hash")
    if sha256_file(source) != expected_sha:
        raise ValueError(f"{label} hash is stale")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256_file(destination) != expected_sha:
        raise RuntimeError(f"{label} copy failed verification")
    return {"kind": label, "relative_path": destination.relative_to(destination.parents[1]).as_posix(), "sha256": expected_sha}


def build_demo(
    *, manifest_path: Path, visual_summary_path: Path,
    provenance_binding_path: Path, frozen_config_path: Path,
    out_dir: Path, commentary_summary_path: Path | None = None,
    prediction_root: Path | None = None,
    runtime_receipt_paths: Iterable[Path] = (),
    project_root: Path = PROJECT_ROOT, private_root: Path = DEFAULT_PRIVATE_ROOT,
    replace: bool = False,
) -> dict[str, Any]:
    """Build and verify one self-contained private demo directory."""
    project_root = project_root.resolve()
    private_root = private_root.resolve()
    if not private_root.is_dir():
        raise ValueError("private data root does not exist")
    manifest_path = _require_within(manifest_path, private_root, "clip manifest")
    out_dir = out_dir.resolve()
    if out_dir == private_root or not _is_within(out_dir, private_root):
        raise ValueError("demo output must be a child directory of the private data root")
    if prediction_root is not None:
        prediction_root = _require_within(prediction_root, private_root, "prediction root")

    visual_summary_path = visual_summary_path.resolve()
    provenance_binding_path = provenance_binding_path.resolve()
    frozen_config_path = frozen_config_path.resolve()
    manifest = _load_object(manifest_path, "private clip manifest")
    visual = _load_object(visual_summary_path, "visual summary")
    provenance = _load_object(provenance_binding_path, "provenance binding")
    frozen = _load_object(frozen_config_path, "frozen visual config")
    clips, visual_by_id, failure_by_id = _validate_manifest_and_visual(
        manifest, manifest_path, visual, visual_summary_path
    )
    rights = manifest.get("rights")
    if not isinstance(rights, dict) or rights.get("redistribution_allowed") is not False:
        raise ValueError("private manifest must explicitly forbid redistribution")
    frozen_sha = _validate_frozen_config(frozen, frozen_config_path, manifest, manifest_path, visual)
    provenance_sha, binding = _validate_provenance(provenance, provenance_binding_path, manifest_path)

    commentary: dict[str, Any] | None = None
    commentary_sha: str | None = None
    commentary_by_id: dict[str, dict[str, Any]] = {}
    commentary_failures: dict[str, dict[str, Any]] = {}
    if commentary_summary_path is not None:
        commentary_summary_path = commentary_summary_path.resolve()
        commentary = _load_object(commentary_summary_path, "commentary summary")
        commentary_sha, commentary_by_id, commentary_failures = _validate_commentary(
            commentary, commentary_summary_path, manifest_path, visual_summary_path,
            visual_by_id, set(failure_by_id),
        )

    runtime_receipts = [_runtime_projection(Path(path).resolve()) for path in runtime_receipt_paths]
    _validate_runtime_receipts(frozen, visual, runtime_receipts)
    manifest_sha = sha256_file(manifest_path)
    visual_sha = sha256_file(visual_summary_path)

    backup: Path | None = None
    if out_dir.exists():
        if not replace:
            raise FileExistsError("refusing to overwrite an existing demo; pass --replace for a recoverable backup")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = out_dir.with_name(f"{out_dir.name}.backup-{stamp}")
        suffix = 1
        while backup.exists():
            backup = out_dir.with_name(f"{out_dir.name}.backup-{stamp}-{suffix}")
            suffix += 1

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))
    media_records: list[dict[str, Any]] = []
    cards: list[str] = []
    try:
        for index, clip in enumerate(clips):
            clip_id = clip["clip_id"]
            commentary_segments, commentary_evidence_sha = _load_commentary_evidence(
                clip, project_root=project_root, private_root=private_root
            )
            visual_meta = clip.get("visual_only")
            audio_meta = clip.get("local_review_with_audio")
            if not isinstance(visual_meta, dict) or visual_meta.get("audio_stream_count") != 0:
                raise ValueError(f"visual-only media declaration is invalid for {clip_id}")
            if not isinstance(audio_meta, dict) or not isinstance(audio_meta.get("audio_stream_count"), int) or audio_meta["audio_stream_count"] < 1:
                raise ValueError(f"commentary media declaration is invalid for {clip_id}")
            visual_source = _resolve_private_media(
                visual_meta.get("path"), project_root=project_root, private_root=private_root,
                label=f"visual-only clip {clip_id}",
            )
            audio_source = _resolve_private_media(
                audio_meta.get("path"), project_root=project_root, private_root=private_root,
                label=f"commentary clip {clip_id}",
            )
            if _is_within(visual_source, out_dir) or _is_within(audio_source, out_dir):
                raise ValueError("demo output cannot contain its own source media")
            visual_rel = f"media/{clip_id}-visual-only.mp4"
            audio_rel = f"media/{clip_id}-commentary.mp4"
            caption_rel = f"media/{clip_id}-commentary-asr-en.vtt"
            media_records.append(_copy_bound_media(
                visual_source, visual_meta.get("sha256"), stage / visual_rel,
                label="silent_visual",
            ))
            media_records.append(_copy_bound_media(
                audio_source, audio_meta.get("sha256"), stage / audio_rel,
                label="local_commentary_review",
            ))
            caption_path = stage / caption_rel
            caption_path.write_text(_render_vtt(commentary_segments), encoding="utf-8", newline="\n")
            media_records.append({
                "kind": "commentary_asr_captions",
                "relative_path": caption_rel,
                "sha256": sha256_file(caption_path),
                "source_evidence_sha256": commentary_evidence_sha,
            })
            visual_item = visual_by_id.get(clip_id)
            prediction: dict[str, Any] | None = None
            receipt: dict[str, Any] | None = None
            if visual_item is not None:
                prediction, receipt = _load_private_prediction(
                    clip_id, visual_item, prediction_root, private_root, visual["model"]
                )
                if prediction is None:
                    _validate_evidence_contract(
                        visual_item,
                        abstained=visual_item.get("abstained") is True,
                        label="visual summary",
                        require_presence=True,
                    )
            cards.append(_clip_card(
                index, len(clips), clip, visual_item, failure_by_id.get(clip_id),
                prediction, receipt, commentary_by_id.get(clip_id), commentary_failures.get(clip_id),
                commentary is not None, visual_rel, audio_rel, caption_rel,
                _transcript_html(commentary_segments),
            ))

        technical = _technical_panel(
            visual, manifest, frozen, frozen_sha, provenance, binding, provenance_sha,
            commentary, commentary_sha, runtime_receipts, manifest_sha, visual_sha,
        )
        site = _render_html(
            cards="".join(cards), visual=visual, manifest=manifest,
            technical=technical, commentary=commentary,
        )
        index_path = stage / "index.html"
        index_path.write_text(site, encoding="utf-8", newline="\n")
        receipt = {
            "schema_version": DEMO_RECEIPT_SCHEMA,
            "created_at": _utc_now(),
            "privacy": {
                "private_media": True,
                "redistribution_allowed": False,
                "network_dependencies": False,
                "ai_generated_images": False,
            },
            "inputs": {
                "manifest_sha256": manifest_sha,
                "visual_summary_sha256": visual_sha,
                "frozen_config_sha256": frozen_sha,
                "provenance_binding_sha256": provenance_sha,
                "commentary_summary_sha256": commentary_sha,
                "runtime_receipt_sha256": [item["sha256"] for item in runtime_receipts],
            },
            "model": visual["model"],
            "split": manifest["split"],
            "counts": {
                "clips": len(clips),
                "visual_completed": len(visual_by_id),
                "visual_failed": len(failure_by_id),
                "commentary_records": len(commentary_by_id),
            },
            "media": media_records,
            "index_sha256": sha256_file(index_path),
        }
        (stage / "demo-receipt.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        if backup is not None:
            out_dir.rename(backup)
        stage.rename(out_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        if backup is not None and backup.exists() and not out_dir.exists():
            backup.rename(out_dir)
        raise

    return {
        "index": out_dir / "index.html",
        "receipt": out_dir / "demo-receipt.json",
        "backup": backup,
        "counts": receipt["counts"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--visual-summary", type=Path, required=True)
    parser.add_argument("--commentary-summary", type=Path)
    parser.add_argument("--provenance-binding", type=Path, required=True)
    parser.add_argument("--frozen-config", type=Path, required=True)
    parser.add_argument("--prediction-root", type=Path)
    parser.add_argument("--runtime-receipt", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--replace", action="store_true", help="Move an existing demo to a timestamped private backup.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = build_demo(
        manifest_path=args.manifest,
        visual_summary_path=args.visual_summary,
        commentary_summary_path=args.commentary_summary,
        provenance_binding_path=args.provenance_binding,
        frozen_config_path=args.frozen_config,
        prediction_root=args.prediction_root,
        runtime_receipt_paths=args.runtime_receipt,
        out_dir=args.out,
        project_root=args.project_root,
        private_root=args.private_root,
        replace=args.replace,
    )
    print(json.dumps({
        "status": "pass",
        "index": str(result["index"]),
        "receipt": str(result["receipt"]),
        "backup": str(result["backup"]) if result["backup"] else None,
        "counts": result["counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
