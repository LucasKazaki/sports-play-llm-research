from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from build_soccernet_clips import (
    SOCCERNET_TO_PLAY_TYPE,
    overlapping_segments,
    select_visible_events,
    transcript_segments,
)


def test_mapping_matches_soccernet_v2_fine_grained_labels() -> None:
    assert SOCCERNET_TO_PLAY_TYPE["Corner"] == "corner_kick"
    assert SOCCERNET_TO_PLAY_TYPE["Shots on target"] == "shot_on_target"
    assert SOCCERNET_TO_PLAY_TYPE["Shots off target"] == "shot_off_target"


def test_event_selection_is_visible_and_deterministic() -> None:
    labels = {"annotations": [
        {"gameTime": "1 - 00:01", "label": "Foul", "position": "1000", "visibility": "not shown"},
        {"gameTime": "1 - 00:02", "label": "Foul", "position": "2000", "visibility": "visible"},
        {"gameTime": "2 - 00:03", "label": "Foul", "position": "3000", "visibility": "visible"},
    ]}
    selected = select_visible_events(labels, half=1, source_labels=["Foul"])
    assert selected[0]["position"] == "2000"


def test_event_selection_rejects_unavailable_occurrence() -> None:
    with pytest.raises(ValueError, match="only 0 visible"):
        select_visible_events({"annotations": []}, half=1, source_labels=["Goal"])


def test_transcript_alignment_includes_overlapping_boundaries() -> None:
    segments = transcript_segments({"segments": {
        "0": [0.0, 1.0, "before"],
        "1": [2.0, 4.0, "overlap"],
        "2": [6.0, 7.0, "after"],
    }})
    selected = overlapping_segments(segments, start_s=3.0, end_s=6.0)
    assert [item["segment_id"] for item in selected] == ["1"]
