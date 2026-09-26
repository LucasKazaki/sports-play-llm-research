"""Synthetic capability tests; no real players, media, labels or model calls."""
import pytest
from test_multisport_query_capability import (
    fail_closed_external_access, http_query, counters, transport, raw_plan,
    patch_rankers, interpret,
)

REJECTED = [
    ("legacy-soccer", "Find only shots by player 10"),
    ("longform-soccer", "Only show passes by #8"),
    ("legacy-soccer", "Show passes only by players wearing red"),
    ("longform-soccer", "Find passes by only jersey 10"),
    ("longform-soccer", "Show passes by player 8 only"),
    ("legacy-football", "Find only runs by player 10"),
    ("longform-football", "Only show passes by #8"),
    ("legacy-football", "Show passes only by players wearing red"),
    ("longform-football", "Find passes by only jersey 10"),
    ("longform-football", "Show passes by player 8 only"),
]

@pytest.mark.parametrize("mode", ["success", "timeout", "disabled"])
@pytest.mark.parametrize("route,query", REJECTED)
def test_explicit_identity_restriction_rejected_before_transport(monkeypatch, route, query, mode):
    result = http_query(monkeypatch, route, query, mode)
    assert result["status"] == 422
    assert result["body"]["error_code"] == "unsupported_participant_constraint"
    assert result["body"]["code"] == "unsupported_participant_constraint"
    assert "not supported" in result["body"]["error"]
    assert "results" not in result["body"]
    assert result["calls"] == counters()

@pytest.mark.parametrize("mode", ["success", "timeout", "disabled"])
@pytest.mark.parametrize("route", ["legacy-soccer", "longform-soccer", "legacy-football", "longform-football"])
def test_direct_interpreter_also_rejects_before_transport(monkeypatch, route, mode):
    calls = counters()
    transport(monkeypatch, raw_plan(route), mode, calls)
    patch_rankers(monkeypatch, calls)
    caught = None
    try:
        interpret(route, "Find only passes by player 10")
    except ValueError as error:
        caught = error
    assert getattr(caught, "code", None) == "unsupported_participant_constraint"
    assert calls == counters()

CONTROLS = [
    ("legacy-soccer", "Find shots by player 10"),
    ("longform-soccer", "Show me passes by player 10 wearing red kit."),
    ("legacy-football", "Find passes by jersey 010."),
    ("longform-football", "Find passes by player 10"),
    ("legacy-soccer", "Find only shots"),
    ("longform-soccer", "Find passes only after halftime"),
    ("legacy-football", "Find only passes"),
    ("longform-football", "Find only passes at 10:30"),
    ("legacy-soccer", "Find only shots by player 10.5"),
    ("longform-soccer", "Find only shots by jersey 10:30"),
    ("legacy-football", "Find only shots by player 10"),
    ("longform-football", "Find only cutbacks by player 10"),
]

@pytest.mark.parametrize("mode", ["success", "timeout", "disabled"])
@pytest.mark.parametrize("route,query", CONTROLS)
def test_text_preferences_nonparticipant_only_and_sport_boundaries(monkeypatch, route, query, mode):
    result = http_query(monkeypatch, route, query, mode)
    assert result["status"] == 200
    assert "error_code" not in result["body"]
    assert result["calls"]["ranker"] == 1
    assert result["calls"]["transport"] == (0 if mode == "disabled" else 1)
