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

import searchable_match_vlm as module
from searchable_match_vlm import (
    Window,
    coaching_prompt,
    compact_search_results,
    index_match,
    plan_windows,
    require_private_output,
    sample_window,
    search_index,
    validate_model_report,
)


def _write_video(path: Path, *, seconds: int = 3, fps: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 90))
    assert writer.isOpened()
    for frame_index in range(seconds * fps):
        frame = np.full((90, 160, 3), (frame_index * 7) % 255, dtype=np.uint8)
        cv2.putText(frame, str(frame_index), (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


def _model_report(timestamps: list[float]) -> dict:
    return {
        "window_summary": "The attacking side attempts a long diagonal pass into the right channel.",
        "events": [{
            "event_types": ["long_ball"],
            "primary_action": "Long diagonal pass toward the right attacking channel",
            "temporal_evidence_s": [timestamps[0], timestamps[-1]],
            "evidence_frames": [
                {"timestamp_s": timestamps[0], "observation": "A blue-shirted player shapes to strike from deep."},
                {"timestamp_s": timestamps[-1], "observation": "Players turn and run toward the right attacking channel."},
            ],
            "participants": [{
                "player_reference": "deep blue-shirted passer",
                "visible_jersey_number": "8",
                "team_reference": "attacking_team",
                "role_in_event": "actor",
                "action": "plays a long diagonal pass",
                "identity_basis": "jersey_number_visible",
                "confidence": 0.72,
            }],
            "phase_of_play": "progression",
            "field_areas": ["middle_third", "right_flank"],
            "outcome": "The receiving outcome is not visible in the sparse samples.",
            "detailed_description": "Player number 8 sends the ball over a defensive line toward a teammate's forward run.",
            "coaching_relevance": "Retrieve for reviewing range, body shape, and timing of direct progression.",
            "coaching_tags": ["direct progression", "switch of play"],
            "retrieval_keywords": ["long ball", "number 8", "right channel"],
            "uncertainty": "The ball is small and its full flight is not continuously visible.",
            "confidence": 0.68,
        }],
        "report_abstained": False,
        "abstention_reason": None,
        "overall_uncertainty": "Sparse frames do not prove the pass reception.",
    }


def test_window_plan_covers_long_video_without_gaps_and_includes_tail() -> None:
    windows = plan_windows(match_id="match 1", duration_s=100, window_s=30, stride_s=25)
    assert [(item.start_s, item.end_s) for item in windows] == [
        (0.0, 30.0), (25.0, 55.0), (50.0, 80.0), (70.0, 100.0),
    ]
    assert all(left.end_s >= right.start_s for left, right in zip(windows, windows[1:]))
    assert windows[0].window_id == "match-1-w000000000-000030000"


def test_window_plan_rejects_a_stride_that_would_skip_footage() -> None:
    with pytest.raises(ValueError, match="no greater than"):
        plan_windows(match_id="m", duration_s=100, window_s=20, stride_s=21)


def test_sampler_uses_absolute_timestamps_inside_requested_window(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    _write_video(video, seconds=4, fps=10)
    frames = sample_window(video, Window("m-w", 0, 1.0, 3.0), count=5)
    timestamps = [item["timestamp_s"] for item in frames]
    assert timestamps[0] >= 1.0
    assert timestamps[-1] < 3.0
    assert timestamps == sorted(timestamps)
    assert all(len(item["decoded_frame_sha256"]) == 64 for item in frames)


def test_report_validator_accepts_detailed_multi_field_event() -> None:
    window = Window("m-w000", 0, 10.0, 40.0)
    timestamps = [10.0, 20.0, 30.0, 39.9]
    report = validate_model_report(_model_report(timestamps), window=window, sample_timestamps=timestamps, match_id="m")
    assert report["schema_version"] == "playground-coaching-window-report-v1"
    assert report["events"][0]["event_types"] == ["long_ball"]
    assert report["events"][0]["participants"][0]["visible_jersey_number"] == "8"


def test_report_validator_rejects_unsupported_identity_claim() -> None:
    window = Window("m-w000", 0, 10.0, 40.0)
    timestamps = [10.0, 20.0, 30.0, 39.9]
    raw = _model_report(timestamps)
    raw["events"][0]["participants"][0]["identity_basis"] = "role_only"
    with pytest.raises(ValueError, match="jersey number requires"):
        validate_model_report(raw, window=window, sample_timestamps=timestamps, match_id="m")


def test_report_validator_rejects_non_sampled_temporal_evidence() -> None:
    window = Window("m-w000", 0, 10.0, 40.0)
    timestamps = [10.0, 20.0, 30.0, 39.9]
    raw = _model_report(timestamps)
    raw["events"][0]["temporal_evidence_s"] = [11.0, 39.9]
    with pytest.raises(ValueError, match="sampled-frame pair"):
        validate_model_report(raw, window=window, sample_timestamps=timestamps, match_id="m")


def test_empty_window_requires_explicit_abstention() -> None:
    window = Window("m-w000", 0, 0.0, 10.0)
    raw = {
        "window_summary": "The camera is on the crowd.", "events": [],
        "report_abstained": False, "abstention_reason": None,
        "overall_uncertainty": "No field view is visible.",
    }
    with pytest.raises(ValueError, match="explicit abstention"):
        validate_model_report(raw, window=window, sample_timestamps=[0.0, 9.9], match_id="m")


def test_prompt_forbids_player_name_guessing() -> None:
    prompt = coaching_prompt(Window("m-w", 0, 0.0, 30.0), [0.0, 10.0, 20.0, 29.9])
    assert "Never guess a player's real-world name" in prompt
    assert "Report every distinct" in prompt
    assert "long_ball" in prompt
    assert "a passer, shooter, tackler, saver, or clearer is an actor" in prompt
    assert "goalkeeper" not in module.PARTICIPANT_ROLES


def test_response_schema_couples_visible_number_to_identity_basis() -> None:
    response_format = module.structured_response_format([0.0, 10.0, 20.0, 29.9])
    participant = response_format["json_schema"]["schema"]["properties"]["events"]["items"]["properties"]["participants"]["items"]
    visible, abstained = participant["oneOf"]
    assert visible["properties"]["identity_basis"]["const"] == "jersey_number_visible"
    assert visible["properties"]["visible_jersey_number"]["pattern"] == "^[0-9]{1,3}$"
    assert abstained["properties"]["visible_jersey_number"]["const"] is None
    assert "jersey_number_visible" not in abstained["properties"]["identity_basis"]["enum"]


def test_private_output_gate_fails_closed(tmp_path: Path) -> None:
    accepted = tmp_path / "data" / "private" / "index"
    assert require_private_output(accepted) == accepted.resolve()
    with pytest.raises(ValueError, match="data/private"):
        require_private_output(tmp_path / "artifacts" / "index")


def test_search_uses_exact_tokens_not_misleading_prefixes() -> None:
    assert module._fts_query("goal penalty") == '"goal" AND "penalty"'


def test_index_rejects_remote_endpoint_before_private_frame_sampling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    private_out = tmp_path / "data" / "private" / "index"
    sampled = False

    def forbidden_metadata(_path):
        nonlocal sampled
        sampled = True
        raise AssertionError("private video must not be opened")

    monkeypatch.setattr(module, "video_metadata", forbidden_metadata)
    with pytest.raises(ValueError, match="loopback"):
        index_match(
            video_path=tmp_path / "private.mp4", match_id="m", out_dir=private_out,
            source_reference="fixture", endpoint="https://example.com/v1",
        )
    assert sampled is False


def test_index_is_searchable_and_resume_skips_complete_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video = tmp_path / "real-fixture.mp4"
    _write_video(video, seconds=3, fps=10)
    private_out = tmp_path / "data" / "private" / "coaching-index"
    calls = 0

    def fake_request(**kwargs):
        nonlocal calls
        calls += 1
        event_schema = kwargs["response_format"]["json_schema"]["schema"]["properties"]["events"]["items"]
        timestamps = event_schema["properties"]["temporal_evidence_s"]["prefixItems"][0]["enum"]
        content = json.dumps(_model_report(timestamps))
        return {"model": "fixture-vlm", "choices": [{"message": {"content": content}}]}, {}, 12

    monkeypatch.setattr(module, "_request_vlm", fake_request)
    first = index_match(
        video_path=video, match_id="fixture match", out_dir=private_out,
        source_reference="authorized-test-fixture", window_s=3.0, stride_s=3.0,
        sample_count=4, sheets=1, max_windows=1,
    )
    assert first["indexed_event_count"] == 1
    assert first["failures_this_run"] == []
    results = search_index(private_out / "search-index.sqlite3", "long ball number 8")
    assert len(results) == 1
    assert results[0]["event_types"] == ["long_ball"]
    assert results[0]["report"]["participants"][0]["visible_jersey_number"] == "8"
    compact = compact_search_results("long ball number 8", results)
    assert 'Search: "long ball number 8"' in compact
    assert "Types: long_ball" in compact
    assert "jersey 8" in compact
    assert "Evidence:" in compact

    second = index_match(
        video_path=video, match_id="fixture match", out_dir=private_out,
        source_reference="authorized-test-fixture", window_s=3.0, stride_s=3.0,
        sample_count=4, sheets=1, max_windows=1,
    )
    assert second["selected_this_run"] == 0
    assert calls == 1
