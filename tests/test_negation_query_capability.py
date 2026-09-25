"""Offline HTTP capability regression; all records and expectations are development fixtures."""

from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
import search_demo_server as module


def http_query(query, monkeypatch, transport_mode):
    calls = {"transport": 0, "fallback": 0, "ranker": 0}
    original_fallback = module.fallback_query_plan
    plan = {"intent_summary": "Invented query test", "event_types": [],
            "search_terms": ["cutback", "shot", "corner", "foul", "pass", "goal", "throw in", "free kick"],
            "participant_terms": [], "phases": [], "field_areas": [], "explanation": "Synthetic test only"}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return json.dumps({"model": "synthetic", "choices": [{"message": {"content": json.dumps(plan)}}]}).encode()
    def transport(*_args, **_kwargs):
        calls["transport"] += 1
        if transport_mode == "timeout":
            raise TimeoutError("synthetic outage; no socket used")
        return Response()
    def fallback(*args, **kwargs):
        calls["fallback"] += 1
        return original_fallback(*args, **kwargs)
    def ranker(*_args, **_kwargs):
        calls["ranker"] += 1
        return []
    body = json.dumps({"query": query}).encode()
    handler = object.__new__(module.DemoHandler)
    handler.path = "/api/search"
    handler.headers = {"content-length": str(len(body))}
    handler.rfile, handler.wfile = BytesIO(body), BytesIO()
    handler.server = SimpleNamespace(demo_context=SimpleNamespace(endpoint="http://127.0.0.1:1/v1", model="synthetic",
                                                               database=Path("unused"), audit={}))
    observed = {}
    handler.send_response = lambda status: observed.update(status=int(status))
    handler.send_header = lambda *_args: None
    handler.end_headers = lambda: None
    with monkeypatch.context() as patch:
        patch.setattr(module, "_loopback_urlopen", transport)
        patch.setattr(module, "fallback_query_plan", fallback)
        patch.setattr(module, "rank_saved_events", ranker)
        module.DemoHandler.do_POST(handler)
    return {**observed, "body": json.loads(handler.wfile.getvalue()), "calls": calls}


@pytest.mark.parametrize("mode", ["saved_response", "timeout"])
@pytest.mark.parametrize("query", [
    "Find cutbacks without a shot", "Show corners without a foul.",
    "Show passes without shots.", "SHOW CUTBACKS WITHOUT-A-SHOT.",
    "Show cutbacks without any shot on goal.", "Show goals without the pass.",
    "Show cutbacks without a free-kick.", "Show passes without a throw-in.",
])
def test_explicit_action_negation_is_rejected_before_transport_fallback_and_ranker(monkeypatch, mode, query):
    observed = http_query(query, monkeypatch, mode)
    assert observed["status"] == 422
    assert observed["body"]["error_code"] == "unsupported_negation_constraint"
    assert "not supported" in observed["body"]["error"]
    assert "results" not in observed["body"]
    assert observed["calls"] == {"transport": 0, "fallback": 0, "ranker": 0}


@pytest.mark.parametrize("mode", ["saved_response", "timeout"])
@pytest.mark.parametrize("query", [
    "Show cutbacks near a shot.", "Show shots on goal.",
    "Show corners from the second half.", "Show passes without hesitation.",
    "Show a pass without a goalkeeper in view.", "Show a pass without a cornerback in view.",
])
def test_positive_and_nonaction_controls_keep_the_existing_path(monkeypatch, mode, query):
    observed = http_query(query, monkeypatch, mode)
    assert observed["status"] == 200
    assert observed["calls"] == {"transport": 1, "fallback": int(mode == "timeout"), "ranker": 1}


@pytest.mark.parametrize("query", [None, "", " ", "x" * 501])
def test_invalid_input_still_uses_existing_bad_request_response(monkeypatch, query):
    observed = http_query(query, monkeypatch, "timeout")
    assert observed["status"] == 400
    assert observed["calls"] == {"transport": 0, "fallback": 0, "ranker": 0}
