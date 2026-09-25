"""Regression for truthful elapsed query timing; only mocked transport."""
import json
from types import SimpleNamespace
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
import multisport_search_demo_server as server

@pytest.mark.parametrize("adapter", [server.soccer_adapter, server.football_adapter])
@pytest.mark.parametrize("fails", [False, True])
def test_query_latency_includes_success_and_failed_attempt(monkeypatch, adapter, fails):
    # Advance a fake monotonic clock only while the transport is entered.
    clock = [100.0]
    import time
    monkeypatch.setattr(time, "perf_counter", lambda: clock[0])
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self):
            return json.dumps({"model": "fixture-model", "choices": [{"message": {
                "content": json.dumps({"search_terms": ["pass"], "event_types": []})}}]}).encode()
    def transport(*args, **kwargs):
        clock[0] += 1.25
        if fails:
            raise OSError("fixture transport failure")
        return Reply()
    monkeypatch.setattr(adapter.urllib.request, "urlopen", transport)
    result = adapter.interpret_query("show passes", endpoint="http://127.0.0.1:1234/v1", model="fixture-model")
    assert result.get("latency_ms") == 1250
    assert result["source"] == ("deterministic_literal_fallback" if fails else "local_query_llm")

@pytest.mark.parametrize("sport", ["soccer", "football"])
def test_longform_wrapper_preserves_measured_query_time(monkeypatch, sport):
    adapter = getattr(server, sport + "_adapter")
    monkeypatch.setattr(adapter, "search_context", lambda *a, **kw: {
        "interpretation": {"source": "local_query_llm", "requested_model": "fixture-model",
            "search_terms": ["pass"], "event_types": [], "latency_ms": 1250},
        "results": [], "result_count": 0, "ranking_note": "fixture"})
    context = SimpleNamespace(soccer_longform=object(), football_longform=object(),
        endpoint="http://127.0.0.1:1234/v1", demo_status="SYSTEMS GO / SEMANTIC NO-GO", warning="fixture")
    result = getattr(server, "search_" + sport + "_longform")(context, "show passes")
    assert result["interpretation"]["latency_ms"] == 1250
