"""Synthetic software regressions; no real media, labels or model calls."""
import pytest
from test_multisport_query_capability import (
    fail_closed_external_access, http_query, counters,
)

REJECTED = [
    ("legacy-soccer", "Find shots followed by a cutback"),
    ("longform-soccer", "Find shots followed by a cutback"),
    ("legacy-soccer", "Find shots that follow a cutback"),
    ("longform-soccer", "Find cutbacks before a shot"),
    ("legacy-football", "Find passes followed by runs"),
    ("longform-football", "Find runs before a pass"),
]

@pytest.mark.parametrize("mode", ["success", "timeout", "disabled"])
@pytest.mark.parametrize("route,query", REJECTED)
def test_order_rejected_before_transport_and_ranking(monkeypatch, route, query, mode):
    result = http_query(monkeypatch, route, query, mode)
    assert result["status"] == 422
    assert result["body"]["error_code"] == "unsupported_temporal_order_constraint"
    assert result["body"]["code"] == "unsupported_temporal_order_constraint"
    assert "not supported" in result["body"]["error"]
    assert "results" not in result["body"]
    assert result["calls"] == counters()

CONTROLS = [
    ("legacy-soccer", "Find shots and cutbacks"),
    ("longform-soccer", "Find shots after halftime"),
    ("legacy-football", "Find passes and runs"),
    ("longform-football", "Find passes after halftime"),
    ("legacy-football", "Find shots followed by cutbacks"),
    ("longform-football", "Find shots followed by cutbacks"),
]

@pytest.mark.parametrize("mode", ["success", "timeout", "disabled"])
@pytest.mark.parametrize("route,query", CONTROLS)
def test_nonorder_and_other_sport_controls_preserve_search(monkeypatch, route, query, mode):
    result = http_query(monkeypatch, route, query, mode)
    assert result["status"] == 200
    assert "error_code" not in result["body"]
    assert result["calls"]["ranker"] == 1
    assert result["calls"]["transport"] == (0 if mode == "disabled" else 1)
