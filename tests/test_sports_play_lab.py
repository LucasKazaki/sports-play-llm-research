import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))

from sports_play_lab import (
    annotation_agreement,
    evaluate,
    generate_frame_review_packet,
    generate_synthetic_clip,
    paired_condition_comparison,
    run_agreement_fixture,
    run_corruption_experiment,
    run_evidence_perturbation_fixture,
    run_severity_experiment,
    run_scoring_fixture,
    score_benchmark,
    sample_frames,
    prediction_payload,
    trajectory_baseline,
    validate_annotation_export,
    validate_frame_review,
    validate_prediction_payload,
)


def test_synthetic_pipeline_produces_grounded_prediction(tmp_path: Path) -> None:
    video_path, gt_path = generate_synthetic_clip(tmp_path)
    assert video_path.exists() and video_path.stat().st_size > 0
    samples = sample_frames(video_path, count=8)
    assert len(samples) == 8
    assert all(len(digest) == 64 for _, _, digest in samples)

    prediction = trajectory_baseline(video_path)
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8"))
    metrics = evaluate(prediction, ground_truth)
    assert prediction.answer == "left_corner_cross_into_penalty_area"
    assert prediction.abstained is False
    assert metrics["answer_exact_match"] == 1.0
    assert metrics["spatial_evidence_f1"] == 1.0
    assert metrics["ball_detections"] >= 3
    assert "Synthetic" in metrics["warning"]


def test_empty_visual_evidence_abstains(tmp_path: Path) -> None:
    import cv2
    import numpy as np

    path = tmp_path / "empty.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (128, 96))
    assert writer.isOpened()
    for _ in range(10):
        writer.write(np.zeros((96, 128, 3), dtype=np.uint8))
    writer.release()

    prediction = trajectory_baseline(path)
    assert prediction.abstained is True
    assert prediction.answer == "insufficient_visual_evidence"


def test_corruption_experiment_exposes_wrong_grounding_propagation(tmp_path: Path) -> None:
    receipt = run_corruption_experiment(tmp_path, seed=7)
    assert receipt["summary"]["scenario_count"] == 4
    assert receipt["summary"]["corrupted_wrong_non_abstained_count"] == 2
    assert receipt["summary"]["corrupted_abstention_count"] == 1
    payload = json.loads((tmp_path / "corruption_results.json").read_text(encoding="utf-8"))
    assert payload["scenarios"]["clean"]["metrics"]["answer_exact_match"] == 1.0
    assert payload["scenarios"]["drop_to_two_detections"]["prediction"]["abstained"] is True
    assert payload["scenarios"]["reverse_temporal_order"]["wrong_non_abstained_answer"] is True
    assert payload["scenarios"]["systematic_x_shift"]["wrong_non_abstained_answer"] is True


def test_validity_gate_reduces_synthetic_selective_risk(tmp_path: Path) -> None:
    receipt = run_severity_experiment(tmp_path)
    count_only = receipt["policies"]["count_only"]
    gated = receipt["policies"]["validity_gated"]
    assert count_only["covered"] == 9
    assert count_only["covered_errors"] == 7
    assert count_only["selective_risk"] == 7 / 9
    assert gated["covered"] == 2
    assert gated["covered_errors"] == 0
    assert gated["selective_risk"] == 0.0
    payload = json.loads((tmp_path / "severity_results.json").read_text(encoding="utf-8"))
    reversed_points = list(reversed(trajectory_baseline(tmp_path / "left_corner_cross.mp4").trajectory))
    from sports_play_lab import prediction_from_trajectory

    rejected = prediction_from_trajectory(reversed_points, validity_gate=True)
    assert rejected.abstained is True
    assert "timestamps" in rejected.abstention_reason
    assert payload["warning"].startswith("Toy single-class")


def test_output_contract_accepts_grounded_and_abstained_predictions(tmp_path: Path) -> None:
    video_path, _ = generate_synthetic_clip(tmp_path)
    grounded = prediction_payload(
        trajectory_baseline(video_path), clip_id="synthetic-left-corner-cross-v1", question_id="q1"
    )
    assert validate_prediction_payload(grounded) == []

    from sports_play_lab import prediction_from_trajectory

    abstained = prediction_payload(
        prediction_from_trajectory([]), clip_id="empty", question_id="q1"
    )
    assert validate_prediction_payload(abstained) == []


def test_output_contract_rejects_semantically_inconsistent_evidence(tmp_path: Path) -> None:
    video_path, _ = generate_synthetic_clip(tmp_path)
    malformed = prediction_payload(trajectory_baseline(video_path), clip_id="clip", question_id="q1")
    malformed["abstained"] = True
    malformed["abstention_reason"] = None
    malformed["trajectory"][1]["timestamp_s"] = malformed["trajectory"][0]["timestamp_s"]
    malformed["trajectory"][0]["x_norm"] = 1.2
    errors = validate_prediction_payload(malformed)
    assert any("abstained output must use answer" in error for error in errors)
    assert any("must provide abstention_reason" in error for error in errors)
    assert any("strictly increasing" in error for error in errors)
    assert any("normalized" in error for error in errors)


def test_annotation_export_validator_binds_manifest_and_semantics() -> None:
    rubric = json.loads((ROOT / "research" / "annotation-rubric-v2.json").read_text(encoding="utf-8"))
    digest = "a" * 64
    manifest = {"items": [{"clip_id": "c1", "question_id": "q1", "clip_sha256": digest, "duration_s": 8.0}]}
    item = {
        "clip_id": "c1", "question_id": "q1", "clip_sha256": digest, "duration_s": 8.0,
        "question_type": "progression-trajectory", "answerability": "answerable",
        "canonical_answer": "cross", "accepted_aliases": ["cross into box"],
        "temporal_intervals": [[1.0, 4.0]], "spatial_regions": ["left-corner"],
        "trajectory": [{"timestamp_s": 1.0, "x_norm": 0.1, "y_norm": 0.9},
                       {"timestamp_s": 4.0, "x_norm": 0.8, "y_norm": 0.4}],
        "trajectory_unavailable": False, "unanswerable_reason_code": None,
        "spatial_validity": {"spatial_evidence_usable": True, "camera_visibility": "in_view",
                             "calibration_validity": "valid", "ball_localization": "supported_ground_plane",
                             "identity_resolution": "not_required", "failure_reason_codes": []},
        "evidence_entities": ["ball"], "rationale_note": "The ball travels from corner to box.",
    }
    export = {"schema_version": "playground-annotations-v2", "items": [item]}
    assert validate_annotation_export(export, manifest, rubric) == []
    item["clip_sha256"] = "b" * 64
    item["temporal_intervals"] = [[4.0, 5.0], [3.0, 4.5]]
    item["trajectory"][1]["x_norm"] = 1.2
    errors = validate_annotation_export(export, manifest, rubric)
    assert any("does not match frozen manifest" in error for error in errors)
    assert any("ordered and non-overlapping" in error for error in errors)
    assert any("normalized" in error for error in errors)


def test_annotation_export_validator_rejects_positive_unanswerable_evidence() -> None:
    rubric = json.loads((ROOT / "research" / "annotation-rubric-v2.json").read_text(encoding="utf-8"))
    digest = "c" * 64
    manifest = {"items": [{"clip_id": "c2", "question_id": "q2", "clip_sha256": digest, "duration_s": 6.0}]}
    item = {
        "clip_id": "c2", "question_id": "q2", "clip_sha256": digest, "duration_s": 6.0,
        "question_type": "causal-evidence", "answerability": "insufficient_visual_evidence",
        "canonical_answer": "pass", "accepted_aliases": [], "temporal_intervals": [],
        "spatial_regions": [], "trajectory": [], "trajectory_unavailable": False,
        "unanswerable_reason_code": "occlusion", "evidence_entities": [],
        "spatial_validity": {"spatial_evidence_usable": False, "camera_visibility": "out_of_view",
                             "calibration_validity": "not_attempted", "ball_localization": "not_required",
                             "identity_resolution": "not_required", "failure_reason_codes": ["camera_out_of_view"]},
        "rationale_note": "The decisive contact is occluded.",
    }
    errors = validate_annotation_export(
        {"schema_version": "playground-annotations-v2", "items": [item]}, manifest, rubric
    )
    assert any("must not contain positive answer or evidence" in error for error in errors)


def test_annotation_spatial_validity_fails_closed_for_all_gsr_failure_states() -> None:
    rubric = json.loads((ROOT / "research" / "annotation-rubric-v2.json").read_text(encoding="utf-8"))
    digest = "d" * 64
    cases = [
        ("camera_visibility", "out_of_view", "camera_out_of_view"),
        ("calibration_validity", "insufficient_pitch_lines", "insufficient_pitch_lines"),
        ("ball_localization", "unsupported_airborne_3d", "unsupported_airborne_ball_3d"),
        ("identity_resolution", "unresolved", "unresolved_identity"),
    ]
    for index, (field, state, reason) in enumerate(cases):
        clip_id = f"failure-{index}"
        manifest = {"items": [{"clip_id": clip_id, "question_id": "q", "clip_sha256": digest, "duration_s": 8.0}]}
        validity = {"spatial_evidence_usable": False, "camera_visibility": "in_view",
                    "calibration_validity": "valid", "ball_localization": "not_required",
                    "identity_resolution": "not_required", "failure_reason_codes": [reason]}
        validity[field] = state
        item = {"clip_id": clip_id, "question_id": "q", "clip_sha256": digest, "duration_s": 8.0,
                "question_type": "progression-trajectory", "answerability": "answerable",
                "canonical_answer": "cross", "accepted_aliases": [], "temporal_intervals": [[1.0, 3.0]],
                "spatial_regions": [], "trajectory": [], "trajectory_unavailable": True,
                "spatial_validity": validity, "unanswerable_reason_code": None,
                "evidence_entities": ["ball"],
                "rationale_note": "Temporal answer remains visible; spatial tool evidence is invalid."}
        export = {"schema_version": "playground-annotations-v2", "items": [item]}
        assert validate_annotation_export(export, manifest, rubric) == []
        item["spatial_regions"] = ["left-corner"]
        errors = validate_annotation_export(export, manifest, rubric)
        assert any("unusable spatial evidence must not contain" in error for error in errors)


def test_frame_review_gate_keeps_unreviewed_real_pilot_out_of_metrics() -> None:
    root = ROOT / "artifacts" / "wikimedia-pilot-v1"
    worksheet = json.loads((root / "frame-review-worksheet-v1.json").read_text(encoding="utf-8"))
    export = json.loads((root / "annotation-export-v2.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "annotation-manifest-v1.json").read_text(encoding="utf-8"))
    assert validate_frame_review(worksheet, export, manifest) == []
    assert worksheet["eligible_for_metrics"] is False
    promoted = {**worksheet, "eligible_for_metrics": True}
    errors = validate_frame_review(promoted, export, manifest)
    assert any("derived gate result false" in error for error in errors)


def test_frame_review_gate_requires_matching_tight_frames_and_calibration_evidence() -> None:
    root = ROOT / "artifacts" / "wikimedia-pilot-v1"
    worksheet = json.loads((root / "frame-review-worksheet-v1.json").read_text(encoding="utf-8"))
    export = json.loads((root / "annotation-export-v2.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "annotation-manifest-v1.json").read_text(encoding="utf-8"))
    worksheet["independent_review"]["reviewer_id"] = "reviewer-b"
    worksheet["temporal_boundary_review"].update({
        "tight_boundaries_confirmed": True, "start_frame_index": 0, "end_frame_index": 238,
    })
    worksheet["item_quality_checks"] = {key: "passed" for key in worksheet["item_quality_checks"]}
    worksheet["governance"] = {"second_annotator_id": "annotator-b", "adjudicator_id": "adjudicator-c"}
    worksheet["eligible_for_metrics"] = True
    manifest["review_gate"]["eligible_for_metrics"] = True
    errors = validate_frame_review(worksheet, export, manifest)
    assert any("temporal interval must match" in error for error in errors)
    assert any("eligible_for_metrics must equal derived gate result false" in error for error in errors)


def test_frame_review_gate_accepts_boundary_after_final_frame() -> None:
    root = ROOT / "artifacts" / "wikimedia-pilot-v1"
    worksheet = json.loads((root / "frame-review-worksheet-v1.json").read_text(encoding="utf-8"))
    export = json.loads((root / "annotation-export-v2.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "annotation-manifest-v1.json").read_text(encoding="utf-8"))
    worksheet["independent_review"]["reviewer_id"] = "reviewer-b"
    worksheet["temporal_boundary_review"].update({
        "tight_boundaries_confirmed": True, "start_frame_index": 0, "end_frame_index": 239,
    })
    worksheet["calibration_review"].update({
        "status": "valid", "method": "four-point homography", "supporting_frame_indices": [0],
        "correspondence_count": 4, "mean_reprojection_error_px": 1.0,
        "max_reprojection_error_px": 2.0, "evidence_artifact_sha256": "a" * 64,
    })
    worksheet["item_quality_checks"] = {key: "passed" for key in worksheet["item_quality_checks"]}
    worksheet["governance"] = {"second_annotator_id": "annotator-b", "adjudicator_id": "adjudicator-c"}
    worksheet["eligible_for_metrics"] = True
    manifest["review_gate"]["eligible_for_metrics"] = True
    assert validate_frame_review(worksheet, export, manifest) == []


def test_frame_review_packet_renders_every_frame_and_binds_hashes(tmp_path: Path) -> None:
    video, _ = generate_synthetic_clip(tmp_path / "source", fps=15, seconds=2)
    worksheet = {
        "schema_version": "playground-frame-review-v1", "clip_id": "synthetic",
        "question_id": "q", "clip_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "duration_s": 2.0,
        "video_metadata": {"fps_numerator": 15, "fps_denominator": 1, "decoded_frame_count": 30},
    }
    worksheet_path = tmp_path / "worksheet.json"
    worksheet_path.write_text(json.dumps(worksheet), encoding="utf-8")
    receipt = generate_frame_review_packet(video, worksheet_path, tmp_path / "packet", frames_per_page=12)
    index = json.loads((tmp_path / "packet" / "frame-index.json").read_text(encoding="utf-8"))
    assert receipt["decoded_frame_count"] == 30
    assert receipt["page_count"] == 3
    assert index["end_exclusive_boundary_index"] == 30
    assert len(index["frames"]) == 30
    assert index["frames"][29]["timestamp_s"] == 29 / 15
    assert all((tmp_path / "packet" / page["path"]).exists() for page in index["pages"])


def test_benchmark_scoring_separates_answer_from_grounding(tmp_path: Path) -> None:
    receipt = run_scoring_fixture(tmp_path)
    results = json.loads((tmp_path / "scoring-results.json").read_text(encoding="utf-8"))
    assert results["item_count"] == 3
    assert results["answer_accuracy"] == 1.0
    assert results["joint_grounded_accuracy"] == 2 / 3
    assert results["coverage"] == 2 / 3
    assert results["selective_risk"] == 0.0
    assert results["selective_aurc"] == 0.0
    assert results["coverage_at_answer_risk"]["values"] == {"1%": 2 / 3, "5%": 2 / 3, "10%": 2 / 3}
    assert results["joint_grounded_selective_aurc"] == 0.25
    assert results["coverage_at_joint_grounded_risk"]["values"] == {
        "1%": 1 / 3, "5%": 1 / 3, "10%": 1 / 3,
    }
    assert results["joint_grounded_risk_coverage_curve"]["correctness_field"] == "joint_grounded_correct"
    assert results["risk_coverage_curve"]["max_coverage"] == 2 / 3
    assert results["bootstrap_confidence_intervals"]["group_count"] == 3
    assert results["bootstrap_confidence_intervals"]["replicates"] == 1000
    intervals = results["bootstrap_confidence_intervals"]["intervals"]
    assert intervals["coverage_at_answer_risk_1%"]["valid_replicates"] == 1000
    assert intervals["coverage_at_joint_grounded_risk_10%"]["valid_replicates"] == 1000
    # AURC is undefined for all-abstained resamples; valid replicate counts expose this.
    assert intervals["joint_grounded_selective_aurc"]["valid_replicates"] == intervals["selective_aurc"]["valid_replicates"]
    assert 0 < intervals["joint_grounded_selective_aurc"]["valid_replicates"] < 1000
    assert results["trajectory_required_count"] == 1
    assert results["trajectory_measured_count"] == 1
    assert results["mean_trajectory_normalized_ade"] == 0.0
    assert results["mean_trajectory_normalized_fde"] == 0.0
    assert results["rows"][1]["answer_correct"] == 1.0
    assert results["rows"][1]["joint_grounded_correct"] == 0.0
    assert results["answer_calibration"]["ece"] == results["ece"]
    assert abs(results["answer_calibration"]["ece"] - 0.15) < 1e-12
    assert abs(results["joint_grounded_calibration"]["ece"] - 0.35) < 1e-12
    assert results["answer_calibration"]["covered_count"] == 2
    assert results["joint_grounded_calibration"]["covered_count"] == 2
    assert len(results["answer_calibration"]["reliability_diagram"]) == 5
    assert sum(v["count"] for v in results["joint_grounded_calibration"]["reliability_diagram"]) == 2
    assert results["operational_point"] == {
        "confidence_threshold": 0.5,
        "covered_count": 2,
        "coverage": 2 / 3,
        "answer_selective_risk": 0.0,
        "joint_grounded_selective_risk": 0.5,
    }
    assert receipt["warning"].startswith("Deterministic synthetic")


def test_operational_confidence_threshold_is_explicit_and_validated() -> None:
    gold = [{
        "clip_id": "c", "question_id": "q", "match_id": "m", "answerability": "answerable",
        "canonical_answer": "yes", "accepted_aliases": [], "temporal_intervals": [[0.0, 1.0]],
        "spatial_regions": ["midfield"], "trajectory": [],
    }]
    prediction = [{
        "clip_id": "c", "question_id": "q", "answer": "yes", "confidence": 0.8,
        "temporal_evidence_s": [0.0, 1.0], "spatial_evidence": ["midfield"],
        "trajectory": [], "abstained": False,
    }]
    scored = score_benchmark(
        prediction, gold, operational_confidence_threshold=0.85,
        bootstrap_group_field="match_id", bootstrap_replicates=10,
    )
    assert scored["bootstrap_confidence_intervals"]["group_field"] == "match_id"
    assert scored["thresholds"]["operational_confidence"] == 0.85
    assert scored["operational_point"]["covered_count"] == 0
    assert scored["operational_point"]["coverage"] == 0.0
    assert scored["operational_point"]["answer_selective_risk"] is None
    assert scored["operational_point"]["joint_grounded_selective_risk"] is None

    for invalid in (-0.01, 1.01):
        try:
            score_benchmark(prediction, gold, operational_confidence_threshold=invalid)
        except ValueError as error:
            assert "operational_confidence_threshold" in str(error)
        else:
            raise AssertionError("expected invalid operational threshold to fail closed")


def test_benchmark_scoring_rejects_key_mismatch() -> None:
    try:
        score_benchmark([], [{"clip_id": "c", "question_id": "q"}])
    except ValueError as error:
        assert "keys must match" in str(error)
    else:
        raise AssertionError("expected exact-key mismatch to fail closed")


def test_selective_curve_is_tie_grouped_and_bootstrap_is_deterministic() -> None:
    gold, predictions = [], []
    for clip_id, answer, confidence in [("c1", "yes", 0.9), ("c1", "no", 0.9),
                                         ("c2", "yes", 0.5), ("c3", "yes", 0.1)]:
        question_id = f"q{len(gold)}"
        gold.append({"clip_id": clip_id, "question_id": question_id, "answerability": "answerable",
                     "canonical_answer": "yes", "accepted_aliases": [], "temporal_intervals": [[0.0, 1.0]],
                     "spatial_regions": ["midfield"], "trajectory": []})
        predictions.append({"clip_id": clip_id, "question_id": question_id, "answer": answer,
                            "confidence": confidence, "temporal_evidence_s": [0.0, 1.0],
                            "spatial_evidence": ["midfield"], "trajectory": [], "abstained": False})
    first = score_benchmark(predictions, gold, bootstrap_replicates=200, bootstrap_seed=17)
    second = score_benchmark(predictions, gold, bootstrap_replicates=200, bootstrap_seed=17)
    curve = first["risk_coverage_curve"]
    assert len(curve["points"]) == 4  # origin plus three unique confidence thresholds
    assert curve["points"][1]["covered_count"] == 2
    assert curve["points"][1]["selective_risk"] == 0.5
    assert abs(first["selective_aurc"] - 19 / 48) < 1e-12
    assert first["bootstrap_confidence_intervals"] == second["bootstrap_confidence_intervals"]
    assert first["bootstrap_confidence_intervals"]["group_count"] == 3


def test_bootstrap_supports_explicit_match_grouping_and_fails_closed() -> None:
    gold, predictions = [], []
    for clip_id, match_id in [("c1", "m1"), ("c2", "m1"), ("c3", "m2")]:
        gold.append({"clip_id": clip_id, "question_id": "q", "match_id": match_id,
                     "answerability": "answerable", "canonical_answer": "yes",
                     "accepted_aliases": [], "temporal_intervals": [[0.0, 1.0]],
                     "spatial_regions": ["midfield"], "trajectory": []})
        predictions.append({"clip_id": clip_id, "question_id": "q", "answer": "yes",
                            "confidence": 0.8, "temporal_evidence_s": [0.0, 1.0],
                            "spatial_evidence": ["midfield"], "trajectory": [],
                            "abstained": False})
    scored = score_benchmark(predictions, gold, bootstrap_replicates=50,
                             bootstrap_seed=3, bootstrap_group_field="match_id")
    assert scored["bootstrap_confidence_intervals"]["group_field"] == "match_id"
    assert scored["bootstrap_confidence_intervals"]["group_count"] == 2

    del gold[0]["match_id"]
    try:
        score_benchmark(predictions, gold, bootstrap_replicates=10,
                        bootstrap_group_field="match_id")
    except ValueError as error:
        assert "match_id" in str(error) and "missing" in str(error)
    else:
        raise AssertionError("expected missing custom bootstrap group to fail closed")


def test_benchmark_required_trajectory_missing_or_over_threshold_is_not_grounded() -> None:
    gold = [{
        "clip_id": "c", "question_id": "q", "answerability": "answerable",
        "canonical_answer": "cross", "accepted_aliases": [], "temporal_intervals": [[0.0, 2.0]],
        "spatial_regions": ["penalty-area"],
        "trajectory": [{"timestamp_s": 0.0, "x_norm": 0.1, "y_norm": 0.8},
                       {"timestamp_s": 2.0, "x_norm": 0.8, "y_norm": 0.4}],
    }]
    base = {"clip_id": "c", "question_id": "q", "answer": "cross", "confidence": 0.9,
            "temporal_evidence_s": [0.0, 2.0], "spatial_evidence": ["penalty-area"],
            "abstained": False}
    missing = score_benchmark([{**base, "trajectory": []}], gold)
    assert missing["rows"][0]["trajectory_normalized_ade"] is None
    assert missing["trajectory_measurement_rate"] == 0.0
    assert missing["joint_grounded_accuracy"] == 0.0

    digest = "0" * 64
    shifted = [{"timestamp_s": t, "x_norm": x + 0.2, "y_norm": y, "frame_sha256": digest}
               for t, x, y in [(0.0, 0.1, 0.8), (2.0, 0.8, 0.4)]]
    scored = score_benchmark([{**base, "trajectory": shifted}], gold, trajectory_ade_threshold=0.1)
    assert abs(scored["rows"][0]["trajectory_normalized_ade"] - 0.2) < 1e-12
    assert abs(scored["rows"][0]["trajectory_normalized_fde"] - 0.2) < 1e-12
    assert scored["rows"][0]["trajectory_ade_hit"] is False
    assert scored["joint_grounded_accuracy"] == 0.0


def test_evidence_perturbations_separate_answers_from_grounding(tmp_path: Path) -> None:
    receipt = run_evidence_perturbation_fixture(tmp_path)
    summary = receipt["summary"]
    assert summary["clean"]["answer_accuracy"] == 1.0
    assert summary["clean"]["joint_grounded_accuracy"] == 1.0
    for condition in ("evidence_swap", "noisy_tool_x_shift"):
        assert summary[condition]["contract_error_count"] == 0
        assert summary[condition]["answer_accuracy"] == 1.0
        assert summary[condition]["joint_grounded_accuracy"] == 0.0
        assert summary[condition]["joint_grounded_delta_from_clean"] == -1.0
    assert summary["evidence_swap"]["mean_temporal_iou"] == 0.0
    assert summary["evidence_swap"]["mean_pitch_region_f1"] == 0.0
    assert summary["noisy_tool_x_shift"]["mean_temporal_iou"] == 1.0
    assert summary["noisy_tool_x_shift"]["mean_pitch_region_f1"] == 1.0
    assert summary["noisy_tool_x_shift"]["mean_trajectory_normalized_ade"] > 0.1
    assert (tmp_path / "comparison-summary.json").exists()
    paired = json.loads((tmp_path / "paired-comparisons.json").read_text(encoding="utf-8"))
    swapped = paired["evidence_swap"]
    assert swapped["pair_count"] == 3
    assert swapped["point_estimates"]["answer_correctness_delta"] == 0.0
    assert swapped["point_estimates"]["joint_grounded_correctness_delta"] == -1.0
    assert swapped["exact_paired_tests"]["answer_correctness"]["discordant_count"] == 0
    joint_test = swapped["exact_paired_tests"]["joint_grounded_correctness"]
    assert joint_test["clean_correct_corrupt_incorrect"] == 3
    assert joint_test["two_sided_exact_p_value"] == 0.25
    interval = swapped["bootstrap_confidence_intervals"]["intervals"]["joint_grounded_correctness_delta"]
    assert interval == {"lower": -1.0, "upper": -1.0, "valid_replicates": 200}


def test_paired_comparison_is_grouped_and_fails_on_misalignment() -> None:
    def scored(keys, joint):
        return {"rows": [
            {"clip_id": clip, "question_id": "q", "match_id": match,
             "confidence": 0.8, "abstained": False, "answer_correct": 1.0,
             "joint_grounded_correct": value}
            for (clip, match), value in zip(keys, joint)
        ]}
    clean = scored([("c1", "m1"), ("c2", "m1"), ("c3", "m2")], [1.0, 1.0, 1.0])
    corrupt = scored([("c1", "m1"), ("c2", "m1"), ("c3", "m2")], [0.0, 0.0, 1.0])
    compared = paired_condition_comparison(
        clean, corrupt, group_field="match_id", bootstrap_replicates=50, bootstrap_seed=3)
    assert compared["bootstrap_confidence_intervals"]["group_count"] == 2
    assert compared["point_estimates"]["joint_grounded_correctness_delta"] == -2 / 3
    corrupt["rows"][0]["match_id"] = "wrong"
    try:
        paired_condition_comparison(clean, corrupt, group_field="match_id", bootstrap_replicates=10)
    except ValueError as error:
        assert "must exist and match" in str(error)
    else:
        raise AssertionError("expected paired grouping mismatch to fail closed")


def test_annotation_agreement_fixture_separates_label_and_evidence_agreement(tmp_path: Path) -> None:
    receipt = run_agreement_fixture(tmp_path)
    results = json.loads((tmp_path / "agreement-results.json").read_text(encoding="utf-8"))
    assert results["answerability"]["observed_agreement"] == 2 / 3
    assert abs(results["answerability"]["cohen_kappa"] - 0.5) < 1e-12
    assert results["answer_alias"]["agreement"] == 1.0
    assert results["temporal_evidence"]["mean_iou"] == 0.6
    assert results["pitch_regions"]["mean_set_f1"] == 2 / 3
    assert results["trajectory_availability"]["observed_agreement"] == 1.0
    assert abs(results["trajectory_displacement"]["mean_normalized_ade"] - 0.0282842712474619) < 1e-12
    assert receipt["warning"].startswith("Deterministic synthetic")


def test_annotation_agreement_rejects_key_mismatch() -> None:
    item = {"clip_id": "c", "question_id": "q", "answerability": "answerable"}
    try:
        annotation_agreement([item], [])
    except ValueError as error:
        assert "keys must match" in str(error)
    else:
        raise AssertionError("expected exact-key mismatch to fail closed")


def test_local_openai_adapter_rejects_non_loopback_endpoint() -> None:
    from openai_compatible_adapter import LocalOpenAICompatibleAdapter

    try:
        LocalOpenAICompatibleAdapter("https://api.example.com/v1", "model")
    except ValueError as error:
        assert "loopback" in str(error)
    else:
        raise AssertionError("expected remote endpoint to be rejected")


def test_local_openai_adapter_builds_separate_direct_and_tool_grounded_requests() -> None:
    from openai_compatible_adapter import LocalOpenAICompatibleAdapter

    adapter = LocalOpenAICompatibleAdapter("http://127.0.0.1:8080/v1", "local-vlm")
    frame = "data:image/jpeg;base64,AA=="
    direct = adapter.build_request("What happens?", [frame])
    tool_grounded = adapter.build_request("What happens?", [frame], tool_evidence={"ball_track": [[0.1, 0.2]]})

    assert direct["model"] == "local-vlm"
    assert direct["messages"][-1]["content"][-1]["image_url"]["url"] == frame
    assert "Tool-derived evidence" not in str(direct)
    assert "Tool-derived evidence" in str(tool_grounded)
    assert direct["response_format"]["type"] == "json_schema"
    response_schema = direct["response_format"]["json_schema"]["schema"]
    assert response_schema["required"] == [
        "answer", "confidence", "temporal_evidence_s", "spatial_evidence",
        "trajectory", "abstained", "abstention_reason",
    ]
