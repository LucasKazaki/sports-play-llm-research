import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import footballmaster_pilot as module
from footballmaster_pilot import (
    DescriptorResult,
    TARGET_CLASSES,
    evaluate_predictions,
    fit_projection,
    fit_softmax_head,
    load_examples,
    target_from_labels,
    train_pipeline,
    verify_run,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path, *, leak: bool = False, denied: bool = False) -> tuple[Path, Path]:
    media = root / "data" / "public" / "footballmaster" / "media"
    media.mkdir(parents=True)
    specs = [
        ("train-pos", "train-source-pos", "train", "touchdown_pass", True),
        ("train-neg", "train-source-neg", "train", "kickoff_return", False),
        ("train-pos-2", "train-source-pos-2", "train", "rushing_touchdown", True),
        ("train-neg-2", "train-source-neg-2", "train", "field_goal_attempt", False),
        ("valid-pos", "valid-source-pos", "valid", "rushing_touchdown", True),
        ("valid-neg", "valid-source-neg", "valid", "field_goal_attempt", False),
        ("test-pos", "train-source-pos" if leak else "test-source-pos", "test", "touchdown_pass", True),
        ("test-neg", "test-source-neg", "test", "interception_practice", False),
    ]
    assets = []
    rows = []
    for ordinal, (clip_id, source_id, split, fine_label, target) in enumerate(specs):
        path = media / f"{clip_id}.webm"
        path.write_bytes((clip_id + "-fixture-bytes").encode("utf-8"))
        relative = path.relative_to(root).as_posix()
        allowed = not (denied and ordinal == 0)
        rights = "approved_for_local_research" if allowed else "hold"
        asset = {
            "asset_id": clip_id,
            "source_id": source_id,
            "split": split,
            "fine_label": fine_label,
            "is_touchdown": target,
            "canonical_page_url": f"https://commons.wikimedia.org/wiki/File:{clip_id}.webm",
            "license_spdxish": "CC-BY-4.0",
            "license_name": "Creative Commons Attribution 4.0 International",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "creator": f"Fixture creator {ordinal}",
            "creator_url": f"https://example.test/creator/{ordinal}",
            "conditions": ["Attribution", "License link"],
            "project_relative_media_path": relative,
            "downloaded_sha256": _sha(path),
            "observed_duration_seconds": 1.0,
            "rights_disposition": rights,
            "training_allowed": allowed,
            "redistribution_allowed": True,
        }
        assets.append(asset)
        rows.append({
            "clip_id": clip_id,
            "source_id": source_id,
            "split": split,
            "project_relative_media_path": relative,
            "sha256": _sha(path),
            "start_seconds": 0.0,
            "end_seconds": 1.0,
            "duration_seconds": 1.0,
            "labels": [fine_label],
            "is_touchdown": target,
            "label_provenance": "source_description_weak_label",
            "adjudication_status": "not_human_adjudicated",
            "source_page_url": asset["canonical_page_url"],
            "license_spdxish": "CC-BY-4.0",
            "rights_disposition": rights,
            "training_allowed": allowed,
            "redistribution_allowed": True,
            "audio_in_model": False,
            "notes": "test fixture",
        })
    sources = root / "data" / "public" / "footballmaster" / "source-manifest.json"
    sources.write_text(json.dumps({"schema_version": 1, "assets": assets}), encoding="utf-8")
    examples = root / "data" / "public" / "footballmaster" / "examples.jsonl"
    examples.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return examples, sources


class FakeExtractor:
    identity = {
        "kind": "deterministic_test_fixture",
        "name": "fake",
        "sha256": "a" * 64,
        "path": "",
        "trained_by_this_project": False,
    }

    def extract(self, video_path: Path, *, frame_count: int) -> DescriptorResult:
        positive = "pos" in video_path.stem
        base = 1.0 if positive else -1.0
        descriptor = np.array(
            [base, 0.8 * base, base + 0.1, -0.5 * base, 0.25, 1.0,
             0.3 * base, -0.7 * base, 0.4, -0.2, 0.9 * base, 0.05],
            dtype=float,
        )
        return DescriptorResult(
            descriptor=descriptor,
            sampled_frame_indices=tuple(range(frame_count)),
            sampled_frame_sha256=tuple(hashlib.sha256(f"{video_path.name}-{i}".encode()).hexdigest() for i in range(frame_count)),
            decoded_fps=10.0,
            decoded_frame_count=10,
            decoded_duration_seconds=1.0,
            backbone_output_dimension=2,
        )


def test_frozen_target_mapping_is_unambiguous() -> None:
    assert target_from_labels(["touchdown_pass"]) == 1
    assert target_from_labels(["field_goal_attempt"]) == 0
    with pytest.raises(ValueError, match="unsupported"):
        target_from_labels(["formation_trips"])
    with pytest.raises(ValueError, match="unambiguously"):
        target_from_labels(["touchdown_pass", "kickoff_return"])


def test_real_public_manifest_passes_rights_hash_and_source_split_audit() -> None:
    examples, audit = load_examples()
    assert len(examples) == 9
    assert audit["all_media_hashes_verified"] is True
    assert audit["all_sources_disjoint_across_splits"] is True
    assert audit["target_counts_by_split"] == {
        "train": {"not_touchdown": 2, "touchdown": 2},
        "valid": {"not_touchdown": 1, "touchdown": 1},
        "test": {"not_touchdown": 1, "touchdown": 2},
    }


def test_real_vp9_clip_samples_sequentially_despite_last_frame_seek_drift() -> None:
    path = ROOT / "data" / "public" / "footballmaster" / "media" / "touchdown-pass-milton-davis-2018.webm"
    frames, indices, fps, total = module._uniform_video_frames(path, 8)
    assert len(frames) == len(indices) == 8
    assert indices == sorted(indices)
    assert indices[0] == 0
    assert indices[-1] >= total - 2
    assert fps > 0


def test_manifest_fails_closed_on_training_rights_hold(tmp_path: Path) -> None:
    examples, sources = _write_fixture(tmp_path, denied=True)
    with pytest.raises(PermissionError, match="not approved"):
        load_examples(examples, sources, project_root=tmp_path)


def test_manifest_rejects_source_group_leakage(tmp_path: Path) -> None:
    examples, sources = _write_fixture(tmp_path, leak=True)
    with pytest.raises(ValueError, match="source leakage"):
        load_examples(examples, sources, project_root=tmp_path)


def test_manifest_rejects_media_hash_drift(tmp_path: Path) -> None:
    examples, sources = _write_fixture(tmp_path)
    target = tmp_path / "data" / "public" / "footballmaster" / "media" / "test-neg.webm"
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="media hash mismatch"):
        load_examples(examples, sources, project_root=tmp_path)


def test_projection_and_softmax_are_actual_fitted_parameters() -> None:
    values = np.array([
        [-2.0, -1.0, 0.0], [-1.5, -0.8, 0.2], [1.5, 0.8, -0.1], [2.0, 1.0, 0.1]
    ])
    targets = np.array([0, 0, 1, 1])
    projection = fit_projection(values, 2)
    embedded = projection.transform(values)
    head, log = fit_softmax_head(
        embedded, targets, embedded, targets, epochs=100, learning_rate=0.1, l2=0.01
    )
    assert projection.components.shape[0] >= 1
    assert head.parameter_count > 0
    assert np.linalg.norm(head.weights) > 0
    assert evaluate_predictions(targets, np.argmax(head.probabilities(embedded), axis=1))["accuracy"] == 1.0
    assert log[-1]["epoch"] == 100


def test_end_to_end_training_writes_checkpoint_metrics_and_demo_index(tmp_path: Path) -> None:
    examples, sources = _write_fixture(tmp_path)
    output = tmp_path / "artifacts" / "footballmaster" / "pilot-v1"
    result = train_pipeline(
        examples_path=examples,
        source_manifest_path=sources,
        backbone_path=tmp_path / "unused.onnx",
        output_dir=output,
        frame_count=4,
        pca_components=2,
        epochs=80,
        learning_rate=0.1,
        l2=0.01,
        project_root=tmp_path,
        extractor=FakeExtractor(),
    )
    assert result["status"] == "pass"
    for filename in (
        "footballmaster-pilot-v1.npz", "model-config.json", "model-card.json", "metrics.json",
        "training-log.jsonl", "predictions.jsonl", "data-audit.json", "feature-receipts.json",
        "search-index.sqlite3", "index-plan.json", "run-receipt.json",
    ):
        assert (output / filename).is_file()
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["test"]["n_examples"] == 2
    assert metrics["test"]["source_count"] == 2
    assert metrics["performance_claim_allowed"] is False
    card = json.loads((output / "model-card.json").read_text(encoding="utf-8"))
    assert card["actual_trained_parameters"] is True
    assert card["architecture_scope"] == "football_only"
    assert card["learned_head_parameter_count"] > 0
    assert card["learned_parameter_count"] == (
        card["unsupervised_train_fitted_projection_parameter_count"]
        + card["supervised_learned_parameter_count"]
    )
    assert card["total_persisted_fitted_numeric_state_count"] > card["learned_parameter_count"]
    verification = verify_run(output)
    assert verification["status"] == "pass"
    assert len(verification["generation_id"]) == 24
    assert verification["event_count"] == 8
    import sqlite3
    connection = sqlite3.connect(output / "search-index.sqlite3")
    try:
        event = json.loads(connection.execute("SELECT report_json FROM events LIMIT 1").fetchone()[0])
    finally:
        connection.close()
    assert event["source_attribution"]["creator"].startswith("Fixture creator")
    assert event["source_attribution"]["license_url"].startswith("https://")


def test_run_verifier_detects_checkpoint_tampering(tmp_path: Path) -> None:
    examples, sources = _write_fixture(tmp_path)
    output = tmp_path / "artifacts" / "footballmaster" / "pilot-v1"
    train_pipeline(
        examples_path=examples, source_manifest_path=sources, backbone_path=tmp_path / "unused.onnx",
        output_dir=output, frame_count=2, pca_components=1, epochs=5, project_root=tmp_path,
        extractor=FakeExtractor(),
    )
    checkpoint = output / "footballmaster-pilot-v1.npz"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tamper")
    with pytest.raises(RuntimeError, match="binding failed"):
        verify_run(output)


def test_accuracy_interval_exposes_tiny_sample_uncertainty() -> None:
    metrics = evaluate_predictions(np.array([0, 1, 1]), np.array([0, 0, 1]))
    lower, upper = metrics["accuracy_wilson_95"]
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert lower < metrics["accuracy"] < upper
    assert upper - lower > 0.5
    assert metrics["confusion_matrix"]["values"] == [[1, 0], [1, 1]]
