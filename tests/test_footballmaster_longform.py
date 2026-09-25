from __future__ import annotations

import json
from pathlib import Path

import pytest

from footballmaster.longform import (
    EVENT_TYPES,
    EXPERIMENT_SPLITS,
    QUERY_SET,
    Window,
    bm25_search,
    build_request,
    build_windows,
    parse_json_text,
    report_search_text,
    scan_package_isolation,
    validate_report,
)


def _verification() -> dict:
    assets = []
    for index, (asset_id, split) in enumerate(EXPERIMENT_SPLITS.items()):
        assets.append(
            {
                "asset_id": asset_id,
                "game_id": f"game-{index}",
                "split": split,
                "project_relative_path": f"data/media/{index}.mp4",
                "sha256": f"{index:064d}",
                "probe": {"duration_seconds": 3600.0},
            }
        )
    return {"assets": assets}


def test_frozen_split_and_multiscale_window_counts() -> None:
    windows = build_windows(_verification())
    split_games = {
        split: {item.game_id for item in windows if item.split == split}
        for split in ("train", "valid", "test")
    }
    assert {key: len(value) for key, value in split_games.items()} == {"train": 3, "valid": 1, "test": 2}
    assert not split_games["train"] & split_games["valid"]
    assert not split_games["train"] & split_games["test"]
    assert not split_games["valid"] & split_games["test"]
    test_windows = [item for item in windows if item.split == "test"]
    assert len(test_windows) == 36
    assert {item.duration_seconds for item in test_windows} == {30, 60, 120}


def test_request_receipt_excludes_audio_and_source_metadata() -> None:
    window = Window("w", "private-asset", "private-game", "test", "private/file.mp4", "a" * 64, 10.0, 60, 0, 0.5)
    frames = [
        {
            "frame_id": "F00",
            "relative_seconds": 5.0,
            "sha256": "b" * 64,
            "bytes": 3,
            "data": b"abc",
        }
    ]
    payload, receipt = build_request("model", "Inspect visible football action.", window, frames)
    encoded = json.dumps(payload).lower()
    assert "private-asset" not in encoded
    assert "private-game" not in encoded
    assert "private/file.mp4" not in encoded
    assert receipt["audio_used"] is False
    assert receipt["metadata_fields_used"] == []
    assert receipt["input_modalities"] == ["text_protocol", "silent_jpeg_frames"]


def test_report_validation_requires_frame_evidence() -> None:
    report = {
        "schema_version": "footballmaster-visual-report-v2",
        "visual_only": True,
        "abstain": False,
        "abstention_reason": "",
        "confidence": "medium",
        "window_summary": "A visible run ends near the sideline.",
        "events": [
            {
                "event_type": "run_play",
                "start_frame_id": "F00",
                "end_frame_id": "F01",
                "action": "runner moves right",
                "outcome": "unknown",
                "actors_visible": ["ball carrier; identity unknown"],
                "field_context": "near sideline",
                "evidence_frame_ids": ["F00", "F01"],
                "uncertainties": ["yardage unknown"],
            }
        ],
        "formations_and_tactics": ["formation not established"],
        "coach_search_terms": ["run right", "sideline"],
    }
    assert validate_report(report, ["F00", "F01"]) == []
    report["events"][0]["evidence_frame_ids"] = ["F99"]
    assert any("evidence" in item for item in validate_report(report, ["F00", "F01"]))
    assert "run_play" in EVENT_TYPES


def test_json_parser_accepts_fenced_object() -> None:
    assert parse_json_text("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_search_uses_only_report_text_and_is_deterministic() -> None:
    report = {
        "window_summary": "Quarterback completes a pass toward the right sideline.",
        "formations_and_tactics": [],
        "coach_search_terms": ["completed pass", "right sideline"],
        "events": [
            {
                "event_type": "pass_play",
                "action": "forward pass",
                "outcome": "complete",
                "field_context": "right sideline",
                "actors_visible": [],
                "uncertainties": [],
            }
        ],
        "abstain": False,
    }
    entries = [
        {"window_id": "b", "game_id": "g2", "start_seconds": 60, "duration_seconds": 30, "abstain": False, "confidence": "high", "search_text": "punt return", "report": {"window_summary": "punt"}},
        {"window_id": "a", "game_id": "g1", "start_seconds": 10, "duration_seconds": 60, "abstain": False, "confidence": "medium", "search_text": report_search_text(report), "report": report},
    ]
    results = bm25_search(entries, "completed pass right sideline", 2)
    assert results[0]["window_id"] == "a"
    assert len(QUERY_SET) == 30


def test_package_has_no_cross_sport_dependency_tokens() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert scan_package_isolation(project_root) == []
