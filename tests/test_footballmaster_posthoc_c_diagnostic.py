from __future__ import annotations

import json
from pathlib import Path

import pytest

from footballmaster.longform import PROMPT_CANDIDATES, canonical_json, sha256_bytes, sha256_file
from footballmaster.posthoc_c_diagnostic import (
    DENOMINATOR,
    PLAN_SHA256,
    PROMPT_ID,
    PROMPT_SHA256,
    explicitly_negated_scoring_count,
    internally_unsupported_scoring_count,
    verify_diagnostic_seal,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_guarded_prompt_and_frozen_denominator_are_exact() -> None:
    assert DENOMINATOR == 6
    assert PLAN_SHA256 == "ebb5b6e8bf91c1cbe38225d20e25dfc58cef451e4676abe265c2171fd87fd675"
    assert sha256_bytes(PROMPT_CANDIDATES[PROMPT_ID].encode("utf-8")) == PROMPT_SHA256


def test_unsupported_scoring_is_internal_text_consistency_not_truth() -> None:
    report = {
        "events": [
            {
                "event_type": "scoring",
                "action": "players align before the snap",
                "outcome": "play awaits the snap",
                "field_context": "midfield",
                "uncertainties": [],
            },
            {
                "event_type": "scoring",
                "action": "official raises both arms for a touchdown signal",
                "outcome": "touchdown",
                "field_context": "goal line",
                "uncertainties": [],
            },
            {"event_type": "pre_snap", "action": "alignment"},
        ]
    }
    assert internally_unsupported_scoring_count(report) == 1


def test_negated_scoring_is_not_hidden_by_marker_match() -> None:
    report = {
        "events": [
            {
                "event_type": "scoring",
                "action": "pre_snap",
                "outcome": "No scoring evidence visible.",
                "field_context": "midfield",
                "uncertainties": [],
            },
            {
                "event_type": "scoring",
                "action": "touchdown signal",
                "outcome": "touchdown",
                "field_context": "goal line",
                "uncertainties": [],
            },
        ]
    }
    assert internally_unsupported_scoring_count(report) == 0
    assert explicitly_negated_scoring_count(report) == 1


def test_diagnostic_seal_detects_run_mutation(tmp_path: Path) -> None:
    output = tmp_path / "diagnostic"
    run_file = output / "runs" / PROMPT_ID / "window" / "receipt.json"
    _write_json(run_file, {"status": "complete"})
    files = {run_file.relative_to(output).as_posix(): sha256_file(run_file)}
    _write_json(
        output / "diagnostic-seal.json",
        {
            "terminal_window_denominator": 6,
            "files": files,
            "root_hash": sha256_bytes(canonical_json(files)),
        },
    )
    assert verify_diagnostic_seal(output)["terminal_window_denominator"] == 6
    run_file.write_text("mutated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sealed file changed"):
        verify_diagnostic_seal(output)
