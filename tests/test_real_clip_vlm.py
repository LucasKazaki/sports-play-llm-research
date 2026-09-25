import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))

from real_clip_vlm import (
    PLAY_TYPES,
    normalise_model_output,
    parse_json_content,
    prompt,
    structured_response_format,
    write_contact_sheets,
)


def _answer(**changes):
    result = {
        "answer": "corner_kick",
        "confidence": 0.7,
        "temporal_evidence_s": [0.2, 4.1],
        "spatial_evidence": ["left-corner", "penalty-area"],
        "trajectory": [],
        "abstained": False,
        "abstention_reason": None,
    }
    result.update(changes)
    return result


def test_normalise_model_output_accepts_a_taxonomy_label() -> None:
    prediction = normalise_model_output(_answer(), clip_id="real-001", question_id="play-type-q1")
    assert prediction["answer"] in PLAY_TYPES
    assert prediction["clip_id"] == "real-001"
    assert prediction["trajectory"] == []


def test_normalise_model_output_requires_a_taxonomy_label() -> None:
    with pytest.raises(ValueError, match="fixed soccer play taxonomy"):
        normalise_model_output(_answer(answer="cross"), clip_id="real-001", question_id="play-type-q1")


def test_normalise_model_output_enforces_abstention_semantics() -> None:
    with pytest.raises(ValueError, match="prediction contract failed"):
        normalise_model_output(
            _answer(answer="insufficient_visual_evidence", confidence=0.2, abstained=True,
                    abstention_reason="view blocked", temporal_evidence_s=[0.0, 0.0], spatial_evidence=[]),
            clip_id="real-001", question_id="play-type-q1",
        )


def test_normalise_model_output_converts_empty_non_abstention_reason_to_null() -> None:
    prediction = normalise_model_output(
        _answer(abstention_reason=""), clip_id="real-001", question_id="play-type-q1"
    )
    assert prediction["abstention_reason"] is None


def test_parse_json_content_accepts_fenced_json() -> None:
    parsed = parse_json_content("```json\n{\"answer\": \"corner_kick\"}\n```")
    assert parsed == {"answer": "corner_kick"}


def test_prompt_prioritises_restart_type_over_outcome() -> None:
    instruction = prompt()
    assert "underlying restart or action" in instruction
    assert "not merely its outcome" in instruction
    assert "penalty_kick" in instruction


def test_prompt_spells_out_the_exact_abstention_contract() -> None:
    instruction = prompt()
    assert "exact abstention answer is insufficient_visual_evidence" in instruction
    assert "never a list of individual timestamps" in instruction
    assert "start_seconds strictly less than end_seconds" in instruction
    assert "never repeat the same timestamp twice" in instruction


def test_structured_response_format_fixes_the_answer_and_interval_shape() -> None:
    response_format = structured_response_format([0.0, 1.0, 2.0])
    schema = response_format["json_schema"]["schema"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    abstention, prediction = schema["oneOf"]
    assert abstention["properties"]["answer"]["const"] == "insufficient_visual_evidence"
    assert abstention["properties"]["temporal_evidence_s"]["enum"] == [[0, 0]]
    assert abstention["properties"]["spatial_evidence"]["maxItems"] == 0
    assert prediction["additionalProperties"] is False
    assert "yellow_card" in prediction["properties"]["answer"]["enum"]
    assert prediction["properties"]["temporal_evidence_s"]["enum"] == [[0.0, 1.0], [1.0, 2.0]]


def test_one_frame_per_sheet_uses_full_resolution_for_small_visual_cues(tmp_path: Path) -> None:
    frame = np.full((224, 398, 3), 180, dtype=np.uint8)
    paths = write_contact_sheets(
        [{"frame": frame, "timestamp_s": 5.0, "frame_index": 125}],
        out_dir=tmp_path,
        sheets=1,
    )
    rendered = cv2.imread(str(paths[0]))
    assert rendered.shape[:2] == (720, 1280)
