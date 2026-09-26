"""Regression tests for the bounded SoccerTrack acquisition validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_soccertrack_v2_open_sample.py"
SPEC = importlib.util.spec_from_file_location("soccertrack_open_validator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _receipt() -> dict[str, object]:
    return {"source_revision": "6f5c47cd3a5c38b074c44e9c98dfba48daa230d3"}


def _split_plan() -> dict[str, object]:
    return {
        "schema_version": "soccertrack-v2-open-game-split-v1",
        "source_revision": _receipt()["source_revision"],
        "unit_of_split": "match_id",
        "game_level_splits": validator.OFFICIAL_SPLITS,
        "media_acquisitions": [
            {
                "match_id": "117092",
                "half": 1,
                "split": "official_bas_train",
                "role": "development_only_unscored",
            },
            {
                "match_id": "128057",
                "half": 1,
                "split": "official_bas_test",
                "role": "heldout_sealed_unscored",
            },
        ],
    }


def test_split_validator_keeps_one_new_game_heldout_and_unscored() -> None:
    result = validator.validate_split_plan(_receipt(), _split_plan(), ["117092", "128057"])
    assert result["acquired_development_match_ids"] == ["117092"]
    assert result["acquired_heldout_match_ids"] == ["128057"]
    assert result["unacquired_official_heldout_match_ids"] == ["132831"]
    assert result["official_heldout_coverage_status"] == "incomplete"
    assert result["heldout_evaluation_ready"] is False


def test_split_validator_rejects_role_or_half_reassignment() -> None:
    plan = _split_plan()
    acquisitions = plan["media_acquisitions"]
    assert isinstance(acquisitions, list)
    acquisitions[1] = {
        "match_id": "128057",
        "half": 2,
        "split": "official_bas_train",
        "role": "development_only_unscored",
    }
    with pytest.raises(validator.ValidationError, match="media_acquisitions"):
        validator.validate_split_plan(_receipt(), plan, ["117092", "128057"])
