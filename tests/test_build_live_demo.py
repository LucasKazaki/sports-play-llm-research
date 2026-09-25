import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from build_live_demo import _metric_cards, build_demo, sha256_file


def test_recovery_metrics_are_not_described_as_the_original_attempt() -> None:
    visual = {
        "counts": {"requested": 6, "completed": 6},
        "metrics": {"primary_requested_set": {
            "schema_valid_first_pass_rate": 1.0,
            "allowed_label_accuracy_all_clips": 0.0,
            "single_label_exact_accuracy": 0.0,
        }},
        "frozen_config": {"schema_version": "playground-frozen-visual-config-v2"},
    }
    html = _metric_cards(visual)
    assert "Schema-valid recovery pass" in html
    assert "post-hoc serving-recovery rerun" in html
    assert "original attempt" not in html
    assert "mapped SoccerNet point-label timestamp" in html
    assert "visibility was not independently adjudicated" in html
    assert "event visible" not in html


def test_qwen_metrics_are_labeled_as_post_hoc_comparison_not_recovery() -> None:
    visual = {
        "model": "qwen/qwen3.5-9b",
        "counts": {"requested": 6, "completed": 6},
        "metrics": {"primary_requested_set": {
            "schema_valid_first_pass_rate": 1.0,
            "allowed_label_accuracy_all_clips": 0.5,
            "single_label_exact_accuracy": 0.5,
        }},
        "frozen_config": {"schema_version": "playground-frozen-visual-config-v2"},
    }
    html = _metric_cards(visual)
    assert "Schema-valid Qwen comparison" in html
    assert "post-hoc engineering comparison" in html
    assert "serving-recovery" not in html


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fixture(tmp_path: Path, *, schema_version: str = "playground-soccernet-vlm-pilot-summary-v1") -> dict[str, Path]:
    project = tmp_path / "project"
    private = project / "data" / "private"
    source = private / "source"
    source.mkdir(parents=True)
    visual_1 = source / "opaque-001-visual.mp4"
    audio_1 = source / "opaque-001-audio.mp4"
    visual_2 = source / "opaque-002-visual.mp4"
    audio_2 = source / "opaque-002-audio.mp4"
    visual_1.write_bytes(b"fake silent soccer clip one")
    audio_1.write_bytes(b"fake soccer clip one with commentary")
    visual_2.write_bytes(b"fake silent soccer clip two")
    audio_2.write_bytes(b"fake soccer clip two with commentary")
    commentary_1 = source / "opaque-001-commentary.json"
    commentary_2 = source / "opaque-002-commentary.json"
    write_json(commentary_1, {
        "schema_version": "playground-commentary-evidence-v1",
        "source": "SoccerNet-Echoes",
        "clip_id": "valid-opaque-001",
        "clip_duration_s": 10.0,
        "segments": [{
            "clip_relative_start_s": 0.25,
            "clip_relative_end_s": 2.5,
            "text": "Goal chance <script>not markup</script>",
        }],
    })
    write_json(commentary_2, {
        "schema_version": "playground-commentary-evidence-v1",
        "source": "SoccerNet-Echoes",
        "clip_id": "valid-opaque-002",
        "clip_duration_s": 10.0,
        "segments": [],
    })

    manifest_path = private / "manifest.json"
    manifest = {
        "schema_version": "playground-soccernet-clips-manifest-v1",
        "provider": "SoccerNet",
        "split": "valid",
        "rights": {"redistribution_allowed": False},
        "clips": [
            {
                "clip_id": "valid-opaque-001",
                "split": "valid",
                "clip_duration_s": 10.0,
                "visual_only": {
                    "path": str(visual_1), "sha256": sha256_file(visual_1),
                    "audio_stream_count": 0,
                },
                "local_review_with_audio": {
                    "path": str(audio_1), "sha256": sha256_file(audio_1),
                    "audio_stream_count": 1,
                },
                "commentary": {
                    "path": str(commentary_1), "sha256": sha256_file(commentary_1),
                    "segment_count": 1,
                },
                "ground_truth": {
                    "play_type": "goal", "allowed_play_types_in_window": ["goal", "shot_on_target"],
                    "single_label_eligible": False,
                },
            },
            {
                "clip_id": "valid-opaque-002",
                "split": "valid",
                "clip_duration_s": 10.0,
                "visual_only": {
                    "path": str(visual_2), "sha256": sha256_file(visual_2),
                    "audio_stream_count": 0,
                },
                "local_review_with_audio": {
                    "path": str(audio_2), "sha256": sha256_file(audio_2),
                    "audio_stream_count": 1,
                },
                "commentary": {
                    "path": str(commentary_2), "sha256": sha256_file(commentary_2),
                    "segment_count": 0,
                },
                "ground_truth": {
                    "play_type": "yellow_card", "allowed_play_types_in_window": ["yellow_card"],
                    "single_label_eligible": True,
                },
            },
        ],
    }
    write_json(manifest_path, manifest)
    manifest_sha = sha256_file(manifest_path)

    prompt_sha = hashlib.sha256(b"test prompt").hexdigest()
    sampling = {"sample_count": 12, "contact_sheets": 12, "max_tokens": 1600}
    frozen_path = project / "artifacts" / "frozen.json"
    frozen = {
        "schema_version": "playground-frozen-visual-config-v1",
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "test/<script>alert(1)</script>",
        "prompt_sha256": prompt_sha,
        "sampling": sampling,
        "sampler_version": "uniform-test",
        "manifests": {
            "development": {"split": "train", "sha256": "a" * 64},
            "validation": {"split": "valid", "sha256": manifest_sha},
        },
    }
    write_json(frozen_path, frozen)

    prediction_root = private / "predictions"
    prediction_path = prediction_root / "valid-opaque-001" / "prediction.json"
    receipt_path = prediction_root / "valid-opaque-001" / "receipt.json"
    write_json(prediction_path, {
        "schema_version": "playground-output-v1",
        "clip_id": "valid-opaque-001",
        "answer": "goal",
        "confidence": 0.91,
        "abstained": False,
        "abstention_reason": None,
        "temporal_evidence_s": [4.25, 6.75],
        "spatial_evidence": ["goal area", "<script>pitch</script>"],
        "trajectory": [],
    })
    write_json(receipt_path, {
        "schema_version": "playground-real-clip-vlm-receipt-v1",
        "clip_id": "valid-opaque-001",
        "model_requested": "test/<script>alert(1)</script>",
        "model_reported": "test/<script>alert(1)</script>",
        "elapsed_ms": 1234,
    })

    visual_path = project / "artifacts" / "visual.json"
    visual = {
        "schema_version": schema_version,
        "split": "valid",
        "provider": "SoccerNet",
        "model": "test/<script>alert(1)</script>",
        "model_input": "silent clips only",
        "prompt_sha256": prompt_sha,
        "sampling": sampling,
        "private_manifest_sha256": manifest_sha,
        "frozen_config": {
            "enforced": True,
            "schema_version": "playground-frozen-visual-config-v1",
            "sha256": sha256_file(frozen_path),
        },
        "counts": {"requested": 2, "completed": 1, "failed": 1},
        "metrics": {
            "primary_requested_set": {
                "allowed_label_accuracy_all_clips": 0.5,
                "schema_valid_first_pass_rate": 0.5,
                "single_label_exact_accuracy": 0.0,
            }
        },
        "clips": [{
            "clip_id": "valid-opaque-001",
            "prediction": "goal",
            "confidence": 0.91,
            "abstained": False,
            "truth": "goal",
            "allowed_correct": True,
            "elapsed_ms": 1234,
            "prediction_sha256": sha256_file(prediction_path),
            "receipt_sha256": sha256_file(receipt_path),
        }],
        "failures": [{"clip_id": "valid-opaque-002", "error_code": "TimeoutError"}],
        "interpretation": "Tiny <script>pilot</script>; not a benchmark.",
        "performance_claim_allowed": False,
    }
    write_json(visual_path, visual)

    provenance_path = project / "artifacts" / "provenance.json"
    provenance = {
        "schema_version": "playground-soccerdb-soccernet-overlap-binding-v1",
        "status": "pass",
        "rights_boundary": {"private_media": True, "redistribution_allowed": False},
        "claim_boundary": "Mapped SoccerNet media; SoccerNet-v2 labels.",
        "mapping": {"sha256": "b" * 64, "commit": "deadbeef", "repository": "https://example.invalid"},
        "bindings": [{
            "manifest_sha256": manifest_sha,
            "identity_match": True,
            "soccerdb_media_name": "opaque-soccerdb-media.mkv",
        }],
    }
    write_json(provenance_path, provenance)

    commentary_path = project / "artifacts" / "commentary.json"
    commentary = {
        "schema_version": "playground-commentary-crosscheck-summary-v1",
        "model": "local-text-model",
        "manifest_sha256": manifest_sha,
        "visual_summary_sha256": sha256_file(visual_path),
        "primary_visual_predictions_unchanged": True,
        "clips": [{
            "clip_id": "valid-opaque-001",
            "visual_prediction": "goal",
            "visual_abstained": False,
            "relation": "supports",
            "commentary_prediction": "goal",
            "commentary_confidence": 0.8,
            "commentary_abstained": False,
        }],
        "failures": [{"clip_id": "valid-opaque-002", "error_code": "VisualPredictionUnavailable"}],
    }
    write_json(commentary_path, commentary)

    runtime_path = private / "runtime-receipt.json"
    write_json(runtime_path, {
        "schema_version": "playground-isolated-vlm-runtime-receipt-v1",
        "model_reported": "test/<script>alert(1)</script>",
        "device": "RTX test GPU",
        "endpoint": "http://secret-should-not-render.invalid",
        "private_path": str(private),
    })
    return {
        "project": project,
        "private": private,
        "manifest": manifest_path,
        "visual": visual_path,
        "frozen": frozen_path,
        "provenance": provenance_path,
        "commentary": commentary_path,
        "prediction_root": prediction_root,
        "runtime": runtime_path,
    }


def build(paths: dict[str, Path], **kwargs):
    return build_demo(
        manifest_path=paths["manifest"],
        visual_summary_path=paths["visual"],
        commentary_summary_path=paths["commentary"],
        provenance_binding_path=paths["provenance"],
        frozen_config_path=paths["frozen"],
        prediction_root=paths["prediction_root"],
        runtime_receipt_paths=[paths["runtime"]],
        out_dir=paths["private"] / "demo",
        project_root=paths["project"],
        private_root=paths["private"],
        **kwargs,
    )


def test_builds_offline_private_demo_with_sequenced_modalities(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    result = build(paths)
    index = result["index"].read_text(encoding="utf-8")
    assert 'src="media/valid-opaque-001-visual-only.mp4"' in index
    assert 'src="media/valid-opaque-001-commentary.mp4"' in index
    assert 'src="media/valid-opaque-001-commentary-asr-en.vtt"' in index
    assert 'kind="captions"' in index
    assert "Automated SoccerNet-Echoes ASR" in index
    assert "Goal chance &lt;script&gt;not markup&lt;/script&gt;" in index
    assert "Audio stream: none" in index
    assert "Play commentary version" in index
    assert 'data-commentary-button' in index and 'data-commentary-button>Play' in index
    assert "Reveal mapped label" in index
    assert 'id="truth-valid-opaque-001" hidden' in index
    assert "4.25–6.75 s" in index
    assert "Goal Area" in index
    assert "Post-hoc ASR check · Supports" in index
    assert "never changes the sealed visual prediction" in index
    assert "Sealed post-visual consistency probe—not ground truth" in index
    assert "Private research media" in index
    assert "no external scripts, fonts, trackers" in index
    assert "connect-src 'none'" in index
    assert "Alt</kbd> + <kbd>←" in index
    assert 'class="clip-tab" role="tab"' in index
    assert 'role="tabpanel" aria-labelledby="tab-valid-opaque-001"' in index
    assert 'aria-label="Requested clip 1"' in index
    assert "button:focus-visible" in index
    assert "Home</kbd>, and <kbd>End" in index
    assert "Playback gating is a presentation aid, not access control" in index
    assert "visual summary being hash-sealed before commentary was queried" in index
    assert "aria-live=\"polite\"" in index
    assert str(paths["private"]) not in index
    assert "secret-should-not-render" not in index
    assert "<script>alert(1)</script>" not in index
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in index
    assert "&lt;Script&gt;Pitch&lt;/Script&gt;" in index
    assert "Mapped point labels in window" in index
    assert "allowed event" not in index
    receipt = json.loads(result["receipt"].read_text(encoding="utf-8"))
    assert receipt["privacy"] == {
        "ai_generated_images": False,
        "network_dependencies": False,
        "private_media": True,
        "redistribution_allowed": False,
    }
    assert receipt["counts"] == {
        "clips": 2, "commentary_records": 1, "visual_completed": 1, "visual_failed": 1,
    }
    assert len(receipt["media"]) == 6
    assert all(item["relative_path"].startswith("media/") for item in receipt["media"])
    captions = [item for item in receipt["media"] if item["kind"] == "commentary_asr_captions"]
    assert len(captions) == 2 and all("source_evidence_sha256" in item for item in captions)
    vtt = (result["index"].parent / "media" / "valid-opaque-001-commentary-asr-en.vtt").read_text(encoding="utf-8")
    assert "00:00:00.250 --> 00:00:02.500" in vtt
    assert "&lt;script&gt;not markup&lt;/script&gt;" in vtt and "<script>" not in vtt


def test_future_recovery_v2_summary_uses_feature_detection(tmp_path: Path) -> None:
    paths = fixture(tmp_path, schema_version="playground-soccernet-vlm-pilot-summary-v2")
    result = build(paths)
    assert result["counts"]["clips"] == 2


def test_recovery_v2_rejects_runtime_receipt_not_bound_before_validation(tmp_path: Path) -> None:
    paths = fixture(tmp_path, schema_version="playground-soccernet-vlm-pilot-summary-v2")
    runtime_sha = sha256_file(paths["runtime"])
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["schema_version"] = "playground-frozen-visual-config-v2"
    frozen["runtime_receipt"] = {
        "schema_version": "playground-isolated-vlm-runtime-receipt-v1",
        "sha256": runtime_sha,
    }
    write_json(paths["frozen"], frozen)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["frozen_config"] = {
        "enforced": True,
        "schema_version": "playground-frozen-visual-config-v2",
        "sha256": sha256_file(paths["frozen"]),
        "runtime_receipt_sha256": runtime_sha,
    }
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    build(paths)

    paths["runtime"].write_text(
        paths["runtime"].read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="does not match the frozen v2 binding"):
        build_demo(
            manifest_path=paths["manifest"], visual_summary_path=paths["visual"],
            commentary_summary_path=paths["commentary"], provenance_binding_path=paths["provenance"],
            frozen_config_path=paths["frozen"], prediction_root=paths["prediction_root"],
            runtime_receipt_paths=[paths["runtime"]], out_dir=paths["private"] / "demo-2",
            project_root=paths["project"], private_root=paths["private"],
        )


def test_rejects_unknown_frozen_config_schema(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["schema_version"] = "playground-frozen-visual-config-v999"
    write_json(paths["frozen"], frozen)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["frozen_config"]["schema_version"] = frozen["schema_version"]
    visual["frozen_config"]["sha256"] = sha256_file(paths["frozen"])
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="unsupported frozen visual config schema"):
        build(paths)


def test_rejects_visual_and_file_frozen_schema_mismatch(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["frozen_config"]["schema_version"] = "playground-frozen-visual-config-v2"
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="frozen schema does not match"):
        build(paths)


def test_direct_v2_evidence_works_without_private_prediction_root(tmp_path: Path) -> None:
    paths = fixture(tmp_path, schema_version="playground-soccernet-vlm-pilot-summary-v2")
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["temporal_evidence_s"] = [1.0, 2.0]
    visual["clips"][0]["spatial_evidence"] = ["penalty area"]
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    result = build_demo(
        manifest_path=paths["manifest"], visual_summary_path=paths["visual"],
        commentary_summary_path=paths["commentary"], provenance_binding_path=paths["provenance"],
        frozen_config_path=paths["frozen"], prediction_root=None,
        out_dir=paths["private"] / "demo", project_root=paths["project"], private_root=paths["private"],
    )
    index = result["index"].read_text(encoding="utf-8")
    assert "1.00–2.00 s" in index
    assert "Penalty Area" in index


def test_direct_v2_rejects_reversed_temporal_evidence_without_prediction_root(tmp_path: Path) -> None:
    paths = fixture(tmp_path, schema_version="playground-soccernet-vlm-pilot-summary-v2")
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["temporal_evidence_s"] = [9.0, 1.0]
    visual["clips"][0]["spatial_evidence"] = ["penalty area"]
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="visual temporal evidence must be ordered"):
        build_demo(
            manifest_path=paths["manifest"], visual_summary_path=paths["visual"],
            commentary_summary_path=paths["commentary"], provenance_binding_path=paths["provenance"],
            frozen_config_path=paths["frozen"], prediction_root=None,
            out_dir=paths["private"] / "demo", project_root=paths["project"], private_root=paths["private"],
        )


def test_direct_v2_rejects_missing_evidence_without_prediction_root(tmp_path: Path) -> None:
    paths = fixture(tmp_path, schema_version="playground-soccernet-vlm-pilot-summary-v2")
    with pytest.raises(ValueError, match="non-abstention must include temporal and spatial evidence"):
        build_demo(
            manifest_path=paths["manifest"], visual_summary_path=paths["visual"],
            commentary_summary_path=paths["commentary"], provenance_binding_path=paths["provenance"],
            frozen_config_path=paths["frozen"], prediction_root=None,
            out_dir=paths["private"] / "demo", project_root=paths["project"], private_root=paths["private"],
        )


def test_rejects_missing_nonabstained_private_evidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    prediction_path = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction.pop("temporal_evidence_s")
    write_json(prediction_path, prediction)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["prediction_sha256"] = sha256_file(prediction_path)
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="non-abstention must include temporal and spatial evidence"):
        build(paths)


def test_abstention_does_not_present_zero_interval_as_positive_evidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0].update({
        "prediction": "insufficient_visual_evidence", "confidence": 0.0, "abstained": True,
        "allowed_correct": False,
    })
    visual["metrics"]["primary_requested_set"]["allowed_label_accuracy_all_clips"] = 0.0
    write_json(paths["visual"], visual)
    prediction_path = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction.update({
        "answer": "insufficient_visual_evidence", "confidence": 0.0, "abstained": True,
        "abstention_reason": "Event cue was not visible.", "temporal_evidence_s": [0.0, 0.0],
        "spatial_evidence": [],
    })
    write_json(prediction_path, prediction)
    visual["clips"][0]["prediction_sha256"] = sha256_file(prediction_path)
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    commentary["clips"][0].update({
        "visual_prediction": "insufficient_visual_evidence", "visual_abstained": True,
        "relation": "uninformative",
    })
    write_json(paths["commentary"], commentary)
    result = build(paths)
    index = result["index"].read_text(encoding="utf-8")
    assert "Not claimed (abstained)" in index
    assert "Why it abstained:" in index


def test_rejects_private_abstention_without_explicit_reason_and_empty_evidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0].update({
        "prediction": "insufficient_visual_evidence", "confidence": 0.0,
        "abstained": True, "allowed_correct": False,
    })
    visual["metrics"]["primary_requested_set"]["allowed_label_accuracy_all_clips"] = 0.0
    prediction_path = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction.update({
        "answer": "insufficient_visual_evidence", "confidence": 0.0,
        "abstained": True, "abstention_reason": "", "temporal_evidence_s": [0, 0],
        "spatial_evidence": [],
    })
    write_json(prediction_path, prediction)
    visual["clips"][0]["prediction_sha256"] = sha256_file(prediction_path)
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    commentary["clips"][0].update({
        "visual_prediction": "insufficient_visual_evidence", "visual_abstained": True,
        "relation": "uninformative",
    })
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="abstention reason is missing"):
        build(paths)


def test_rejects_private_nonabstention_with_abstention_reason(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    prediction_path = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["abstention_reason"] = "should be null"
    write_json(prediction_path, prediction)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["prediction_sha256"] = sha256_file(prediction_path)
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="non-abstention reason must be null"):
        build(paths)


def test_rejects_output_outside_private_root(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    with pytest.raises(ValueError, match="child directory"):
        build_demo(
            manifest_path=paths["manifest"], visual_summary_path=paths["visual"],
            commentary_summary_path=paths["commentary"], provenance_binding_path=paths["provenance"],
            frozen_config_path=paths["frozen"], prediction_root=paths["prediction_root"],
            out_dir=paths["project"] / "public-demo", project_root=paths["project"], private_root=paths["private"],
        )


def test_rejects_training_split_in_presenter_facing_demo(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["split"] = "train"
    for clip in manifest["clips"]:
        clip["split"] = "train"
    write_json(paths["manifest"], manifest)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["split"] = "train"
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="designated valid split"):
        build(paths)


def test_rejects_non_ten_second_presenter_clip(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["clips"][0]["clip_duration_s"] = 9.5
    write_json(paths["manifest"], manifest)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["private_manifest_sha256"] = sha256_file(paths["manifest"])
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="10 seconds"):
        build(paths)


def test_rejects_unknown_manifest_schema(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["schema_version"] = "unknown-manifest-v1"
    write_json(paths["manifest"], manifest)
    with pytest.raises(ValueError, match="unsupported private clip manifest schema"):
        build(paths)


def test_rejects_non_soccer_net_provider_for_soccer_net_ui(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["provider"] = "OtherDataset"
    write_json(paths["manifest"], manifest)
    with pytest.raises(ValueError, match="SoccerNet provider bindings"):
        build(paths)


def test_rejects_validation_manifest_bound_under_wrong_frozen_role(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["manifests"]["development"] = frozen["manifests"].pop("validation")
    write_json(paths["frozen"], frozen)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["frozen_config"]["sha256"] = sha256_file(paths["frozen"])
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="validation role"):
        build(paths)


def test_rejects_visual_summary_not_bound_to_manifest(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["private_manifest_sha256"] = "f" * 64
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="hash-bound"):
        build(paths)


def test_rejects_tampered_audience_facing_metric(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["metrics"]["primary_requested_set"]["allowed_label_accuracy_all_clips"] = 0.75
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="allowed_label_accuracy_all_clips is inconsistent"):
        build(paths)


def test_rejects_tampered_per_clip_correctness_even_with_matching_rate(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["allowed_correct"] = False
    visual["metrics"]["primary_requested_set"]["allowed_label_accuracy_all_clips"] = 0.0
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="allowed_correct disagrees"):
        build(paths)


def test_rejects_non_finite_json_number(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["confidence"] = float("nan")
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="visual summary is not readable JSON"):
        build(paths)


def test_rejects_out_of_range_commentary_confidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["clips"][0]["commentary_confidence"] = 1.5
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="commentary confidence must be finite"):
        build(paths)


def test_rejects_inconsistent_visual_abstention_fields(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["abstained"] = True
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="visual abstention fields are inconsistent"):
        build(paths)


def test_rejects_reversed_private_temporal_evidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    prediction_path = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["temporal_evidence_s"] = [8.0, 2.0]
    write_json(prediction_path, prediction)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["clips"][0]["prediction_sha256"] = sha256_file(prediction_path)
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="temporal evidence must be ordered"):
        build(paths)


def test_rejects_stale_private_prediction_receipt(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    prediction = paths["prediction_root"] / "valid-opaque-001" / "prediction.json"
    prediction.write_text(prediction.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt binding is stale"):
        build(paths)


def test_rejects_unsealed_or_mismatched_commentary(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["primary_visual_predictions_unchanged"] = False
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="preserve"):
        build(paths)


def test_rejects_commentary_relation_that_disagrees_with_sealed_visual(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["clips"][0]["relation"] = "contradicts"
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="relation disagrees"):
        build(paths)


def test_rejects_non_loopback_frozen_endpoint(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["endpoint"] = "https://remote.example/v1"
    write_json(paths["frozen"], frozen)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["frozen_config"]["sha256"] = sha256_file(paths["frozen"])
    write_json(paths["visual"], visual)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="loopback"):
        build(paths)


def test_rejects_media_outside_private_root(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    outside = paths["project"] / "outside.mp4"
    outside.write_bytes(b"not private")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    manifest["clips"][0]["visual_only"]["path"] = str(outside)
    manifest["clips"][0]["visual_only"]["sha256"] = sha256_file(outside)
    write_json(paths["manifest"], manifest)
    # Rebind downstream hashes so the path boundary, not a stale hash, is tested.
    manifest_sha = sha256_file(paths["manifest"])
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["private_manifest_sha256"] = manifest_sha
    write_json(paths["visual"], visual)
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["manifests"]["validation"]["sha256"] = manifest_sha
    write_json(paths["frozen"], frozen)
    visual["frozen_config"]["sha256"] = sha256_file(paths["frozen"])
    write_json(paths["visual"], visual)
    provenance = json.loads(paths["provenance"].read_text(encoding="utf-8"))
    provenance["bindings"][0]["manifest_sha256"] = manifest_sha
    write_json(paths["provenance"], provenance)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["manifest_sha256"] = manifest_sha
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="private data root"):
        build(paths)


def test_rejects_private_media_bytes_that_no_longer_match_manifest(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    media_path = Path(manifest["clips"][0]["visual_only"]["path"])
    media_path.write_bytes(media_path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="silent_visual hash is stale"):
        build(paths)


def test_rejects_tampered_commentary_evidence(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    commentary_path = Path(manifest["clips"][0]["commentary"]["path"])
    commentary_path.write_text(commentary_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="commentary evidence hash is stale"):
        build(paths)


def test_rejects_commentary_cue_outside_clip(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    commentary_path = Path(manifest["clips"][0]["commentary"]["path"])
    evidence = json.loads(commentary_path.read_text(encoding="utf-8"))
    evidence["segments"][0]["clip_relative_end_s"] = 12.0
    write_json(commentary_path, evidence)
    manifest["clips"][0]["commentary"]["sha256"] = sha256_file(commentary_path)
    write_json(paths["manifest"], manifest)
    manifest_sha = sha256_file(paths["manifest"])
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["private_manifest_sha256"] = manifest_sha
    write_json(paths["visual"], visual)
    frozen = json.loads(paths["frozen"].read_text(encoding="utf-8"))
    frozen["manifests"]["validation"]["sha256"] = manifest_sha
    write_json(paths["frozen"], frozen)
    visual["frozen_config"]["sha256"] = sha256_file(paths["frozen"])
    write_json(paths["visual"], visual)
    provenance = json.loads(paths["provenance"].read_text(encoding="utf-8"))
    provenance["bindings"][0]["manifest_sha256"] = manifest_sha
    write_json(paths["provenance"], provenance)
    commentary = json.loads(paths["commentary"].read_text(encoding="utf-8"))
    commentary["manifest_sha256"] = manifest_sha
    commentary["visual_summary_sha256"] = sha256_file(paths["visual"])
    write_json(paths["commentary"], commentary)
    with pytest.raises(ValueError, match="commentary segment 1 must be ordered"):
        build(paths)


def test_existing_demo_is_backed_up_on_explicit_replace(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    first = build(paths)
    original_sha = sha256_file(first["index"])
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        build(paths)
    second = build(paths, replace=True)
    assert second["backup"] is not None and second["backup"].is_dir()
    assert sha256_file(second["backup"] / "index.html") == original_sha
    assert second["index"].is_file()


def test_failed_promotion_restores_previous_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = fixture(tmp_path)
    first = build(paths)
    original_sha = sha256_file(first["index"])
    real_rename = Path.rename

    def fail_stage_promotion(self: Path, target: Path):
        if self.name.startswith(".demo.staging-") and Path(target).name == "demo":
            raise OSError("simulated promotion failure")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_stage_promotion)
    with pytest.raises(OSError, match="simulated promotion failure"):
        build(paths, replace=True)
    restored = paths["private"] / "demo" / "index.html"
    assert restored.is_file() and sha256_file(restored) == original_sha


def test_rejects_incomplete_visual_accounting(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    visual["failures"] = []
    visual["counts"]["failed"] = 0
    write_json(paths["visual"], visual)
    with pytest.raises(ValueError, match="account for every"):
        build(paths)
