"""Synthetic controls for the native local-model development probe; no HTTP."""
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/local-model-experiment-v1.py"
spec = importlib.util.spec_from_file_location("local_model_experiment", SOURCE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def raw_plan(**changes):
    value = {"intent_summary": "Synthetic query", "event_types": [],
             "search_terms": ["cutback"], "participant_terms": [], "phases": [],
             "field_areas": [], "explanation": "A shot is mentioned only in this explanation."}
    value.update(changes)
    return value


def response(plan, **changes):
    value = {"model": probe.MODEL, "choices": [{"finish_reason": "stop",
             "message": {"content": json.dumps(plan)}}]}
    value.update(changes)
    return value


def test_schema_valid_action_omission_is_not_guard_success():
    result = probe.assess(response(raw_plan()), "Find cutbacks leading to a shot")
    assert result["schema_valid"] is True
    assert result["action_guard_pass"] is False
    assert result["missing_action_concepts"] == ["shot"]


def test_explanation_cannot_rescue_missing_executable_evidence():
    result = probe.assess(response(raw_plan(search_terms=["cutback", "shot"])), "Find cutbacks leading to a shot")
    assert result["action_guard_pass"] is True
    assert probe.assess(response(raw_plan(event_types=["invented_type"])), "Find cutbacks")["schema_valid"] is False


@pytest.mark.parametrize("bad", [
    {"model": probe.MODEL, "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
    {"model": probe.MODEL, "choices": [{"finish_reason": "stop", "message": {"content": "not JSON"}}]},
    response(raw_plan(), model="unbound-model"),
])
def test_truncated_malformed_or_wrong_identity_cannot_count_as_model_success(bad):
    result = probe.assess(bad, "Find cutbacks")
    assert result["model_completed"] is False
    assert result["action_guard_pass"] is False


def test_order_probe_is_not_rescued_by_preserving_both_action_words(tmp_path):
    cases = probe.build_cases()
    forward = next(c for c in cases if c["id"] == "cutback_then_shot")
    reverse = next(c for c in cases if c["id"] == "shot_then_cutback")
    plan = probe.search.fallback_query_plan(forward["query"], "synthetic baseline")
    assert probe.rank_case(tmp_path / "forward.sqlite3", forward, plan)["matches_engineered_expectation"] is False
    assert probe.rank_case(tmp_path / "reverse.sqlite3", reverse, plan)["matches_engineered_expectation"] is True


def test_failures_and_budget_skips_stay_in_every_requested_denominator():
    rows = [{"status": "timeout", "assessment": None}, {"status": "budget_not_attempted", "assessment": None}]
    summary = probe.summarize(rows)
    assert summary["requested_cases"] == 2
    assert summary["model_completed"] == 0
    assert summary["action_guard_pass"] == 0
    assert summary["model_action_guard_fraction_all_requested"] == 0
    assert summary["selective_top1_risk"] is None


def test_development_fixture_is_explicit_and_no_expected_answers_enter_prompt():
    cases = probe.build_cases()
    assert len(cases) == 8
    assert len({case["id"] for case in cases}) == 8
    for case in cases:
        payload = probe.payload_for(case)
        text = json.dumps(payload)
        assert "SYNTHETIC-EVENT" not in text
        assert "expected_top1" not in text
        assert probe.search.AUDIT_WARNING not in text


def test_endpoint_and_output_are_pinned_to_project_local_probe():
    assert probe.ENDPOINT == "http://127.0.0.1:1234/v1"
    with pytest.raises(ValueError):
        probe.request_json("https://example.com/v1/models", timeout=0.01)
