import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import soccermaster_longform.pipeline as module
from soccermaster_longform.pipeline import Window


def _window(duration: int = 60, frames: int = 12) -> Window:
    return Window(
        window_id="smw-fixture",
        role="test_dense",
        source_scope_id="opaque-source",
        source_half=1,
        media_path="C:/private/fixture.mkv",
        media_sha256="a" * 64,
        start_seconds=120.0,
        duration_seconds=duration,
        frame_count=frames,
        ordinal=0,
    )


def _report(frame_ids: list[str]) -> dict:
    return {
        "schema_version": module.REPORT_VERSION,
        "visual_only": True,
        "abstain": False,
        "abstention_reason": "",
        "window_summary": "An anonymous player sends a long pass toward the right channel.",
        "events": [{
            "event_type": "long_ball",
            "start_frame_id": frame_ids[0],
            "end_frame_id": frame_ids[-1],
            "primary_action": "Long forward pass",
            "sequence_detail": "A player strikes from deep and teammates advance.",
            "outcome": "Reception is not visible.",
            "participants": [{
                "player_reference": "deep player in the dark kit",
                "visible_jersey_number": None,
                "identity_basis": "appearance_only",
                "team_reference": "team_in_possession",
                "role_in_event": "passer",
                "observable_action": "plays a long forward pass",
            }],
            "phase_of_play": "progression",
            "field_areas": ["middle_third", "right_flank"],
            "evidence_frame_ids": [frame_ids[0], frame_ids[-1]],
            "coaching_relevance": "Review direct progression and supporting runs.",
            "search_terms": ["long ball", "right channel"],
            "uncertainties": ["Sparse frames do not show the complete flight."],
            "confidence": 0.62,
        }],
        "tactics_observed": ["Direct progression is visually plausible."],
        "coach_search_terms": ["long ball", "direct progression"],
        "overall_uncertainties": ["No player or team identity is available."],
    }


def test_dense_plan_covers_exact_half_with_45_windows() -> None:
    windows = module.build_dense_windows(
        source_scope_id="test", source_half=1, media_path="private.mkv", media_sha256="0" * 64,
        duration_seconds=2700.0,
    )
    assert len(windows) == 45
    assert windows[0].start_seconds == 0
    assert windows[-1].end_seconds == 2700
    assert all(right.start_seconds - left.start_seconds <= 60 for left, right in zip(windows, windows[1:]))
    assert all(item.frame_count == 12 for item in windows)


def test_dense_plan_includes_overlapping_tail_without_gap() -> None:
    windows = module.build_dense_windows(
        source_scope_id="test", source_half=2, media_path="private.mkv", media_sha256="0" * 64,
        duration_seconds=2717.25,
    )
    assert windows[-1].end_seconds == pytest.approx(2717.25)
    assert windows[-2].end_seconds >= windows[-1].start_seconds


def test_duration_stress_uses_eight_twelve_and_sixteen_frames() -> None:
    windows = module._stress_windows(
        role="test_stress", source_scope_id="test", source_half=1, media_path="private.mkv",
        media_sha256="0" * 64, duration_seconds=2700, fraction=0.37, start_ordinal=0,
    )
    assert [(item.duration_seconds, item.frame_count) for item in windows] == [(30, 8), (60, 12), (120, 16)]


def test_report_schema_contains_soccer_specific_multi_event_contract() -> None:
    schema = module.report_json_schema(["F00", "F01", "F02"])
    root = schema["json_schema"]["schema"]
    event = root["properties"]["events"]["items"]
    assert root["properties"]["events"]["maxItems"] == 4
    assert "offside" in event["properties"]["event_type"]["enum"]
    assert "long_ball" in event["properties"]["event_type"]["enum"]
    assert "participants" in event["required"]
    assert "evidence_frame_ids" in event["required"]
    actor = event["properties"]["participants"]["items"]
    assert actor["properties"]["visible_jersey_number"] == {"type": "null"}
    assert "jersey_number_visible" not in actor["properties"]["identity_basis"]["enum"]


def test_validator_accepts_evidence_bound_detailed_report() -> None:
    frame_ids = ["F00", "F01", "F02"]
    assert module.validate_report(_report(frame_ids), frame_ids) == []


def test_validator_rejects_all_jersey_number_claims_at_224p() -> None:
    frame_ids = ["F00", "F01"]
    report = _report(frame_ids)
    participant = report["events"][0]["participants"][0]
    participant["visible_jersey_number"] = "8"
    participant["identity_basis"] = "appearance_only"
    assert any("visible_jersey_number" in item for item in module.validate_report(report, frame_ids))
    participant["visible_jersey_number"] = None
    participant["identity_basis"] = "jersey_number_visible"
    assert any("ontology" in item for item in module.validate_report(report, frame_ids))


def test_validator_requires_explicit_abstention_contract() -> None:
    frame_ids = ["F00", "F01"]
    report = _report(frame_ids)
    report["events"] = []
    assert "prediction_contract" in module.validate_report(report, frame_ids)
    report.update({"abstain": True, "abstention_reason": "No field view is visible."})
    assert module.validate_report(report, frame_ids) == []


def test_request_receipt_excludes_source_metadata_and_absolute_time() -> None:
    window = _window(duration=60, frames=2)
    frames = [
        {"frame_id": "F00", "relative_seconds": 15.0, "sha256": "1" * 64, "bytes": 3, "redacted_rows": 36, "data": b"abc"},
        {"frame_id": "F01", "relative_seconds": 45.0, "sha256": "2" * 64, "bytes": 3, "redacted_rows": 36, "data": b"def"},
    ]
    _payload, receipt = module.build_request(
        model=module.DEFAULT_MODEL, prompt_text=module.PROMPT_CANDIDATES["candidate_a_direct_v2"],
        window=window, frames=frames, response_mode="strict_json_schema",
    )
    assert receipt["audio_used"] is False
    assert receipt["labels_used"] is False
    assert receipt["absolute_timestamps_used"] is False
    assert receipt["source_metadata_fields_used"] == []
    encoded = json.dumps(receipt).lower()
    assert window.media_path.lower() not in encoded
    assert window.source_scope_id.lower() not in encoded
    assert "120.0" not in encoded
    assert "always set visible_jersey_number to null" in receipt["prompt_text"]
    assert "never infer or transcribe a jersey number" in receipt["prompt_text"]


def test_delivery_prompt_is_fixed_number_disabled_evidence_first_v3() -> None:
    assert list(module.DELIVERY_PROMPTS) == ["candidate_b_evidence_first_v3_number_disabled"]
    prompt = next(iter(module.DELIVERY_PROMPTS.values()))
    assert module.PROMPT_CANDIDATES["candidate_b_evidence_first_v2"] in prompt
    assert "always return visible_jersey_number as null" in prompt


def test_extract_frames_blacks_out_scoreboard_region(tmp_path: Path) -> None:
    video = tmp_path / "fixture.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 90))
    assert writer.isOpened()
    for _ in range(30):
        frame = np.full((90, 160, 3), 220, dtype=np.uint8)
        frame[25:, :] = (20, 140, 40)
        writer.write(frame)
    writer.release()
    window = Window(
        window_id="smw-redaction", role="test_stress", source_scope_id="opaque", source_half=1,
        media_path=str(video), media_sha256="a" * 64, start_seconds=0, duration_seconds=3,
        frame_count=2, ordinal=0,
    )
    frames = module.extract_frames(video, window, tmp_path / "frames")
    image = cv2.imread(frames[0]["path"])
    assert image is not None
    assert float(image[:6, :].mean()) < 2.0
    assert frames[0]["relative_seconds"] == pytest.approx(0.75)
    assert frames[0]["absolute_seconds_private_receipt"] == pytest.approx(0.75)


def test_loopback_gate_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        module._loopback_endpoint("https://example.com/v1")


def test_bm25_search_returns_only_positive_scoring_rows() -> None:
    entries = [
        {"window_id": "a", "window_role": "test_dense", "source_half": 1, "start_seconds": 0, "duration_seconds": 60, "abstain": False, "search_text": "long ball right channel", "report": {"window_summary": "Long ball."}},
        {"window_id": "b", "window_role": "test_dense", "source_half": 1, "start_seconds": 60, "duration_seconds": 60, "abstain": False, "search_text": "corner kick delivery", "report": {"window_summary": "Corner."}},
    ]
    results = module.bm25_search(entries, "long ball", limit=5)
    assert [item["window_id"] for item in results] == ["a"]
    assert module.bm25_search(entries, "penalty", limit=5) == []


def test_actual_protocol_is_frozen_at_required_scale() -> None:
    private_root = ROOT / module.DEFAULT_PRIVATE_ROOT
    artifact_root = ROOT / module.DEFAULT_ARTIFACT_ROOT
    protocol = module.verify_protocol(private_root, artifact_root)
    assert protocol["test"]["dense_window_count"] == 90
    assert protocol["test"]["total_window_denominator"] == 96
    assert protocol["test"]["minimum_ordered_frames"] >= 8
    assert protocol["source"]["untouched_by_existing_eight_game_manifest"] is True
    source = module.read_json(artifact_root / "source-verification-receipt.json")
    assert source["labels_semantics_opened"] is False


def test_soccer_longform_package_has_no_cross_sport_dependency_tokens() -> None:
    assert module._scan_package_isolation(ROOT) == []


def test_annotation_parser_keeps_only_visible_mapped_events(tmp_path: Path) -> None:
    labels = tmp_path / "Labels-v2.json"
    module.write_json(labels, {
        "annotations": [
            {"gameTime": "1 - 03:10", "position": "190000", "label": "Offside", "visibility": "visible"},
            {"gameTime": "1 - 04:10", "position": "250000", "label": "Foul", "visibility": "not shown"},
            {"gameTime": "2 - 01:00", "position": "60000", "label": "Unknown label", "visibility": "visible"},
        ]
    })
    rows = module._load_annotations(labels)
    assert len(rows) == 1
    assert rows[0]["source_half"] == 1
    assert rows[0]["event_type"] == "offside"
    assert rows[0]["position_seconds"] == 190


def test_annotation_evaluator_verifies_seal_before_opening_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    labels_opened = False

    def reject_seal(*_args, **_kwargs):
        raise ValueError("seal mismatch")

    def forbidden_labels(_path):
        nonlocal labels_opened
        labels_opened = True
        raise AssertionError("labels must not open")

    monkeypatch.setattr(module, "verify_seal", reject_seal)
    monkeypatch.setattr(module, "_load_annotations", forbidden_labels)
    with pytest.raises(ValueError, match="seal mismatch"):
        module.evaluate_annotations(tmp_path / "data/private/run", tmp_path / "artifacts")
    assert labels_opened is False


def test_visual_prediction_seal_fails_closed_after_tamper(tmp_path: Path) -> None:
    private_root = tmp_path / "data/private/run"
    artifact_root = tmp_path / "artifacts"
    private_file = private_root / "experiment/window.txt"
    public_file = artifact_root / "protocol.txt"
    private_file.parent.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    private_file.write_text("private\n", encoding="utf-8")
    public_file.write_text("public\n", encoding="utf-8")
    files = {
        "private/window.txt": module.sha256_file(private_file),
        "public/protocol.txt": module.sha256_file(public_file),
    }
    module.write_json(artifact_root / "prediction-seal.json", {
        "schema_version": "soccermaster-longform-visual-prediction-seal-v1",
        "files": files,
        "root_hash": module.sha256_bytes(module.canonical_json(files)),
    })
    assert module.verify_seal(private_root, artifact_root)["root_hash"]
    public_file.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        module.verify_seal(private_root, artifact_root)


def test_run_one_persists_and_resumes_verified_visual_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video = tmp_path / "fixture.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 90))
    assert writer.isOpened()
    for frame_index in range(40):
        frame = np.full((90, 160, 3), 40 + frame_index, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    window = Window(
        window_id="smw-resume", role="test_stress", source_scope_id="opaque", source_half=1,
        media_path=str(video), media_sha256=module.sha256_file(video), start_seconds=0,
        duration_seconds=3, frame_count=2, ordinal=0,
    )
    calls = 0

    def fake_post(_url, payload, _timeout):
        nonlocal calls
        calls += 1
        content = json.dumps(_report(["F00", "F01"]))
        envelope = {"model": module.DEFAULT_MODEL, "choices": [{"message": {"content": content}}]}
        return envelope, module.canonical_json(envelope)

    monkeypatch.setattr(module, "_post_json", fake_post)
    private_root = tmp_path / "data/private/soccer"
    first = module.run_one(
        private_root=private_root, window=window, prompt_id="candidate_a_direct_v2",
        prompt_text=module.PROMPT_CANDIDATES["candidate_a_direct_v2"], endpoint=module.DEFAULT_ENDPOINT,
        model=module.DEFAULT_MODEL, timeout_seconds=10,
    )
    assert first["valid"] is True
    assert first["attempt_count"] == 1
    assert first["selected_strategy"] == "strict_json_schema_all_frames"
    second = module.run_one(
        private_root=private_root, window=window, prompt_id="candidate_a_direct_v2",
        prompt_text=module.PROMPT_CANDIDATES["candidate_a_direct_v2"], endpoint=module.DEFAULT_ENDPOINT,
        model=module.DEFAULT_MODEL, timeout_seconds=10,
    )
    assert second == first
    assert calls == 1
