from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from prototype.soccermaster_scale import CLASS_NAMES, SOCCERNET_TO_CLASS
from prototype.soccermaster_scale.manifest import (
    EXAMPLE_SCHEMA_VERSION,
    _background_examples,
    _event_examples,
    _require_private,
)
from prototype.soccermaster_scale.model import (
    _projection,
    aggregate_descriptors,
    classification_metrics,
)
from prototype.soccermaster_scale.reports import build_report, validate_report
from prototype.soccermaster_scale.vlm_eval import (
    INPUT_SCHEMA,
    _validate_prediction,
    freeze_subset,
)


def test_taxonomy_is_soccer_specific_and_rich() -> None:
    assert len(CLASS_NAMES) == 14
    assert {"offside", "foul", "goal", "shot", "corner_kick", "throw_in"} <= set(CLASS_NAMES)
    assert SOCCERNET_TO_CLASS["Shots on target"] == "shot"
    assert SOCCERNET_TO_CLASS["Direct free-kick"] == "free_kick"


def test_soccer_package_imports_no_football_or_multisport_modules() -> None:
    package = Path(__file__).resolve().parents[1] / "prototype/soccermaster_scale"
    imported: list[str] = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
    assert not [name for name in imported if "footballmaster" in name.lower() or "multisport" in name.lower()]


def test_private_manifest_boundary_rejects_public_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="data/private"):
        _require_private(tmp_path / "public")


def test_event_examples_flag_conflicting_nearby_class() -> None:
    events = [
        {"position_s": 20.0, "source_label": "Foul", "class_name": "foul", "team": "home"},
        {"position_s": 22.0, "source_label": "Direct free-kick", "class_name": "free_kick", "team": "away"},
    ]
    rows = _event_examples(
        split="test", game_id="game-a", half=1, duration_s=100.0,
        video_relative_path="game/1_224p.mkv", events=events,
        window_s=12.0, ambiguity_radius_s=4.0,
    )
    assert len(rows) == 2
    assert not rows[0]["ground_truth"]["single_label_eligible"]
    assert rows[0]["ground_truth"]["nearby_classes"] == ["free_kick"]


def test_background_sampling_respects_exclusion_and_maximum() -> None:
    events = [{"position_s": 50.0, "source_label": "Foul", "class_name": "foul", "team": "home"}]
    rows = _background_examples(
        split="train", game_id="game-a", half=1, duration_s=180.0,
        video_relative_path="game/1_224p.mkv", events=events, window_s=12.0,
        stride_s=10.0, exclusion_radius_s=15.0, maximum=6,
    )
    assert len(rows) == 6
    assert all(abs(row["candidate_time_s"] - 50.0) > 15.0 for row in rows)
    assert all(row["ground_truth"]["class_name"] == "background" for row in rows)


def test_feature_aggregation_has_expected_shape_and_temporal_delta() -> None:
    values = np.arange(12 * 1000, dtype=np.float32).reshape(12, 1000)
    feature = aggregate_descriptors(values)
    assert feature.shape == (5000,)
    np.testing.assert_allclose(feature[3000:4000], values[-1] - values[0])


def test_projection_is_deterministic_and_seed_sensitive() -> None:
    first = _projection(10, 4, 123)
    second = _projection(10, 4, 123)
    third = _projection(10, 4, 124)
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, third)


def test_classification_metrics_recompute_exact_accuracy() -> None:
    truth = np.asarray([0, 1, 2], dtype=np.int64)
    probabilities = np.zeros((3, len(CLASS_NAMES)), dtype=np.float32)
    probabilities[0, 0] = 1
    probabilities[1, 1] = 1
    probabilities[2, 1] = 1
    metrics = classification_metrics(truth, probabilities)
    assert metrics["n"] == 3
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["top3_accuracy"] == pytest.approx(2 / 3)


def _example(class_name: str = "offside") -> dict[str, object]:
    return {
        "schema_version": EXAMPLE_SCHEMA_VERSION,
        "example_id": "soc-example",
        "split": "test",
        "game_id": "game-one",
        "source_half": 1,
        "video_relative_path": "game/1_224p.mkv",
        "window_start_s": 10.0,
        "window_end_s": 22.0,
        "candidate_time_s": 16.0,
        "ground_truth": {
            "class_name": class_name,
            "source_label": "Offside",
            "team": "home",
            "visibility": "visible",
            "nearby_classes": [],
            "single_label_eligible": True,
        },
        "sampling_origin": "test fixture",
    }


def test_detailed_report_keeps_unsupported_coach_claims_null() -> None:
    report = build_report(
        example=_example(), predicted_class="offside", confidence=0.8,
        top_k=[{"class_name": "offside", "probability": 0.8}],
        abstention_threshold=0.5, model_generation="generation-a",
    )
    validate_report(report)
    assert report["coach_report"]["actor"] is None
    assert report["coach_report"]["tactical_context"] is None
    assert not report["retrieval_document"]["safe_for_player_specific_retrieval"]


def test_detailed_report_validator_rejects_hallucinated_player() -> None:
    report = build_report(
        example=_example(), predicted_class="offside", confidence=0.8,
        top_k=[{"class_name": "offside", "probability": 0.8}],
        abstention_threshold=0.5, model_generation="generation-a",
    )
    report["coach_report"]["actor"] = "Player 9"
    with pytest.raises(ValueError, match="actor"):
        validate_report(report)


def test_vlm_prediction_cross_field_contract() -> None:
    value = {
        "event_class": "foul",
        "confidence": 0.7,
        "evidence_frame_indices": [3, 4],
        "observable_summary": "A challenge is followed by a stoppage.",
        "actor_detail": "unavailable",
        "team_detail": "unavailable",
        "field_region": "middle_third",
        "ball_trajectory": "unavailable",
        "abstained": False,
        "abstention_reason": "",
    }
    prediction = _validate_prediction(value, "soc-a", "google/gemma-4-e4b")
    assert prediction["event_class"] == "foul"
    value["evidence_frame_indices"] = []
    with pytest.raises(ValueError, match="inconsistent"):
        _validate_prediction(value, "soc-a", "google/gemma-4-e4b")


def test_freeze_vlm_subset_separates_labels_from_inputs(tmp_path: Path) -> None:
    rows = []
    for class_index, class_name in enumerate(CLASS_NAMES):
        for copy in range(2):
            row = _example(class_name)
            row["example_id"] = f"soc-{class_index:02d}-{copy}"
            row["game_id"] = f"game-{copy}"
            row["ground_truth"]["source_label"] = class_name
            rows.append(row)
    examples_path = tmp_path / "examples.jsonl"
    examples_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    private = tmp_path / "private"
    receipt_path = tmp_path / "receipt.json"
    receipt = freeze_subset(
        examples_path=examples_path, private_dir=private,
        public_receipt_path=receipt_path, per_class=2,
    )
    frozen = json.loads((private / "frozen-inputs.json").read_text(encoding="utf-8"))
    labels = json.loads((private / "sealed-labels.json").read_text(encoding="utf-8"))
    assert frozen["schema_version"] == INPUT_SCHEMA
    assert receipt["input_count"] == len(CLASS_NAMES) * 2
    assert all("class_name" not in row and "ground_truth" not in row for row in frozen["examples"])
    assert {row["example_id"] for row in frozen["examples"]} == {row["example_id"] for row in labels["labels"]}

