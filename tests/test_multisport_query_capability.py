"""SYNTHETIC DEVELOPMENT: real query boundaries, fixture transport, no inference.

The parameter file is frozen before execution. No private index/label loader or
video is used. These cases measure bounded software behavior, not sports accuracy.
"""
from io import BytesIO
import json
from pathlib import Path
import socket
import sqlite3
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
import multisport_search_demo_server as multi

SOCCER = multi.soccer_adapter
FOOTBALL = multi.football_adapter
PACKAGE = ROOT / "artifacts/publication-readiness-20260908/multisport-query-capability-v1"
CASES = json.loads((PACKAGE / "synthetic-cases.json").read_text(encoding="utf-8"))["cases"]
ENDPOINT = "http://127.0.0.1:1/v1"


@pytest.fixture(autouse=True)
def fail_closed_external_access(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Unexpected socket/provider/index-loader use in a synthetic capability test")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(multi.soccer_server, "_loopback_urlopen", forbidden)
    monkeypatch.setattr(SOCCER.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(SOCCER, "load_context", forbidden)
    monkeypatch.setattr(FOOTBALL, "load_context", forbidden)
    monkeypatch.setattr(multi, "load_soccer_context", forbidden)
    monkeypatch.setattr(multi, "load_football_context", forbidden)


def route_parts(route):
    backend, sport = route.split("-", 1)
    return backend, sport, SOCCER if sport == "soccer" else FOOTBALL


def raw_plan(route, *, field="search_terms", proposed=None):
    backend, _sport, _adapter = route_parts(route)
    raw = {"search_terms": ["passes"], "event_types": []}
    if backend == "legacy":
        raw.update(intent_summary="SYNTHETIC capability fixture", participant_terms=[], phases=[],
                   field_areas=[], explanation="Synthetic terms only; no visual or scientific claim")
    if proposed is not None:
        raw.setdefault(field, []).append(proposed)
    return raw


def transport(monkeypatch, raw, mode, calls):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return json.dumps({"model": "SYNTHETIC-no-inference", "choices": [
                {"message": {"content": json.dumps(raw)}}]}).encode("utf-8")
    def open_fixture(*_args, **_kwargs):
        calls["transport"] += 1
        if mode == "timeout":
            raise TimeoutError("SYNTHETIC provider outage; no socket opened")
        if mode == "disabled":
            raise AssertionError("Disabled query mode reached provider transport")
        return Response()
    monkeypatch.setattr(multi.soccer_server, "_loopback_urlopen", open_fixture)
    # Both standalone adapters use the same stdlib urllib.request module.
    monkeypatch.setattr(SOCCER.urllib.request, "urlopen", open_fixture)


def patch_rankers(monkeypatch, calls):
    def legacy(_context, plan, **_kwargs):
        calls["ranker"] += 1
        calls["rank_inputs"].append(plan)
        return []
    def bm25(_entries, query, _limit):
        calls["ranker"] += 1
        calls["rank_inputs"].append(query)
        return []
    monkeypatch.setattr(multi, "rank_saved_events", legacy)
    monkeypatch.setattr(SOCCER, "_bm25", bm25)
    monkeypatch.setattr(FOOTBALL, "_bm25", bm25)


def counters():
    return {"transport": 0, "ranker": 0, "fallback": 0, "rank_inputs": []}


def context(route):
    backend, sport, _adapter = route_parts(route)
    standalone = SimpleNamespace(endpoint=ENDPOINT, model="SYNTHETIC", entries=())
    return SimpleNamespace(
        sport=sport, spec=multi.SPORT_SPECS[sport], available=True, endpoint=ENDPOINT,
        model="SYNTHETIC", database=Path("UNUSED-SYNTHETIC.sqlite3"),
        soccer_longform=standalone if backend == "longform" and sport == "soccer" else None,
        football_longform=standalone if backend == "longform" and sport == "football" else None,
        demo_status="SYNTHETIC SOFTWARE ONLY", warning="No real sports data", audit=(),
    )


def http_query(monkeypatch, route, query, mode="success", raw=None):
    calls = counters()
    transport(monkeypatch, raw if raw is not None else raw_plan(route), mode, calls)
    patch_rankers(monkeypatch, calls)
    old_fallback = multi.fallback_query_plan
    def fallback(*args, **kwargs):
        calls["fallback"] += 1
        return old_fallback(*args, **kwargs)
    monkeypatch.setattr(multi, "fallback_query_plan", fallback)
    backend, sport, _adapter = route_parts(route)
    body = json.dumps({"sport": sport, "query": query}).encode("utf-8")
    handler = object.__new__(multi.MultiSportHandler)
    handler.path = "/api/search"
    handler.headers = {"content-length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.server = SimpleNamespace(multisport_context=SimpleNamespace(
        sports={sport: context(route)}, query_llm_enabled=mode != "disabled"))
    observed = {}
    handler.send_response = lambda status: observed.update(status=int(status))
    handler.send_header = lambda *_args: None
    handler.end_headers = lambda: None
    multi.MultiSportHandler.do_POST(handler)
    return {**observed, "body": json.loads(handler.wfile.getvalue()), "calls": calls}


def interpret(route, query):
    backend, sport, adapter = route_parts(route)
    if backend == "legacy":
        return multi.interpret_coach_query(query, spec=multi.SPORT_SPECS[sport],
                                          endpoint=ENDPOINT, model="SYNTHETIC")
    return adapter.interpret_query(query, endpoint=ENDPOINT, model="SYNTHETIC")


def assert_unsupported(observed):
    assert observed["status"] == 422
    assert observed["body"]["error_code"] == "unsupported_negation_constraint"
    assert observed["body"]["code"] == "unsupported_negation_constraint"
    assert "not supported" in observed["body"]["error"]
    assert "results" not in observed["body"]
    assert observed["calls"] == counters()


def direct_negation(monkeypatch, case):
    calls = counters()
    route, query = case["route"], case["query"]
    transport(monkeypatch, raw_plan(route), case["mode"], calls)
    patch_rankers(monkeypatch, calls)
    backend, sport, adapter = route_parts(route)
    caught = None
    try:
        if case["kind"] == "direct_negation":
            interpret(route, query)
        elif case["kind"] == "search_negation":
            adapter.search_context(SimpleNamespace(endpoint=ENDPOINT, model="SYNTHETIC", entries=()),
                                   query, use_query_llm=case["mode"] != "disabled")
        else:
            multi.fallback_query_plan(query, "SYNTHETIC offline", multi.SPORT_SPECS[sport])
    except ValueError as error:
        caught = error
    assert getattr(caught, "code", None) == "unsupported_negation_constraint"
    assert calls == counters()


def attribute_case(monkeypatch, case):
    raw = raw_plan(case["route"], field=case["field"], proposed=case["proposed"])
    observed = http_query(monkeypatch, case["route"], case["query"], raw=raw)
    assert observed["status"] == 200
    assert observed["calls"]["transport"] == 1
    assert observed["calls"]["ranker"] == 1
    trace = observed["body"]["interpretation"]
    if case["reject"]:
        assert trace["source"] == "deterministic_literal_fallback"
        assert trace["plan"]["participant_terms"] == []
        assert "unsupported participant attributes" in trace["error"]
        assert "does not enforce participant or exclusion constraints" in trace["error"]
        # The football wrapper nests its compact interpretation. It must retain
        # the exact invalid response now, without calling it a successful plan.
        retained = trace["raw_interpretation"]
        if isinstance(retained, dict):
            retained = retained.get("raw_interpretation")
        assert json.loads(retained) == raw
        backend, _sport, _adapter = route_parts(case["route"])
        if backend == "longform":
            assert trace["plan"]["search_terms"] == [case["query"]]
            assert observed["calls"]["rank_inputs"] == [case["query"] + " " + case["query"]]
    else:
        assert trace["source"] == "local_query_llm"
        assert trace["error"] is None
        assert case["proposed"] in trace["plan"][case["field"]]


def ranking_witness(monkeypatch, tmp_path, case):
    route = case["route"]
    calls = counters()
    raw = raw_plan(route, proposed="wearing red kit")
    transport(monkeypatch, raw, "success", calls)
    interpreted = interpret(route, "Find passes")
    backend, sport, adapter = route_parts(route)
    if backend == "legacy":
        database = tmp_path / "SYNTHETIC.sqlite3"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE windows(window_id TEXT, match_id TEXT, status TEXT)")
        connection.execute("CREATE TABLE events(event_id TEXT,window_id TEXT,start_s REAL,end_s REAL,confidence REAL,report_json TEXT)")
        connection.execute("INSERT INTO windows VALUES('synthetic','synthetic','complete')")
        for event_id, kit in (("a-neutral", "wearing white kit"), ("z-red", "wearing red kit")):
            report = {"event_types": [], "detailed_description": "passes", "participants": [{"kit": kit}]}
            connection.execute("INSERT INTO events VALUES(?,?,0,1,0.5,?)", (event_id, "synthetic", json.dumps(report)))
        connection.commit()
        connection.close()
        ranked = multi.rank_saved_events(SimpleNamespace(available=True, database=database, sport=sport),
                                          interpreted["plan"])
        top = ranked[0]["event_id"]
    else:
        # Equal document lengths and lexical match, differing only in invented
        # expansion vocabulary. This is an engineered tie/ranking witness.
        entries = [
            {"window_id": "a-neutral", "search_text": "passes plain neutral calm steady"},
            {"window_id": "z-red", "search_text": "passes wearing red kit player"},
        ]
        expanded = " ".join(["Find passes", *interpreted["search_terms"], *interpreted["event_types"]])
        top = adapter._bm25(entries, expanded, 2)[0][1]["window_id"]
    assert top == "a-neutral", "Unrequested model kit vocabulary still boosts the synthetic red report"
    assert calls["transport"] == 1


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_frozen_case(monkeypatch, tmp_path, case):
    kind = case["kind"]
    if kind == "http_negation":
        assert_unsupported(http_query(monkeypatch, case["route"], case["query"], case["mode"]))
    elif kind in {"direct_negation", "search_negation", "fallback_negation"}:
        direct_negation(monkeypatch, case)
    elif kind == "http_control":
        observed = http_query(monkeypatch, case["route"], case["query"], case["mode"])
        assert observed["status"] == 200
        assert observed["calls"]["transport"] == int(case["mode"] != "disabled")
        assert observed["calls"]["ranker"] == 1
        expected = "local_query_llm" if case["mode"] == "success" else "deterministic_literal_fallback"
        assert observed["body"]["interpretation"]["source"] == expected
    elif kind == "http_invalid":
        observed = http_query(monkeypatch, case["route"], case["query"])
        assert observed["status"] == 400
        assert observed["calls"] == counters()
    elif kind == "attribute":
        attribute_case(monkeypatch, case)
    elif kind == "ranking_witness":
        ranking_witness(monkeypatch, tmp_path, case)
    elif kind == "profile_boundary":
        observed = http_query(monkeypatch, case["route"], case["query"], case["mode"])
        if case["reject"]:
            assert_unsupported(observed)
        else:
            assert observed["status"] == 200
            assert observed["calls"]["ranker"] == 1
    elif kind == "source_origins":
        for module, name in ((multi, "multisport_search_demo_server.py"), (SOCCER, "soccer_longform_adapter.py"),
                             (FOOTBALL, "football_longform_adapter.py")):
            assert Path(module.__file__).resolve() == (ROOT / "prototype" / name).resolve()
        if hasattr(multi, "query_caps"):
            assert Path(multi.query_caps.__file__).resolve() == (ROOT / "prototype/query_capabilities.py").resolve()
    else:
        raise AssertionError("Unknown frozen synthetic case kind: " + kind)
