import json
import sqlite3
import sys
from pathlib import Path

import pytest
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import search_demo_server as module


def _plan(**overrides):
    raw = {
        "intent_summary": "Find goalkeeper shots in the goal area.",
        "event_types": ["shot_on_target"],
        "search_terms": ["shot"],
        "participant_terms": ["goalkeeper"],
        "phases": ["chance_creation"],
        "field_areas": ["goal_area"],
        "explanation": "Use requested action, role, phase, and field filters.",
    }
    raw.update(overrides)
    return module.validate_query_plan(raw)


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE windows(window_id TEXT PRIMARY KEY, match_id TEXT, status TEXT);
        CREATE TABLE events(event_id TEXT PRIMARY KEY,window_id TEXT,start_s REAL,end_s REAL,confidence REAL,report_json TEXT);
    """)
    event = {
        "event_types": ["shot_on_target", "save"], "primary_action": "Shot and save",
        "phase_of_play": "chance_creation", "field_areas": ["goal_area"],
        "outcome": "Saved", "detailed_description": "A shot reaches the goalkeeper.",
        "coaching_relevance": "Review shot selection.", "coaching_tags": ["finishing"],
        "retrieval_keywords": ["shot", "goalkeeper"], "uncertainty": "Low",
        "participants": [{"player_reference": "Goalkeeper", "action": "save"}],
    }
    connection.execute("INSERT INTO windows VALUES('w1','m1','complete')")
    connection.execute("INSERT INTO events VALUES('e1','w1',10,12,0.7,?)", (json.dumps(event),))
    connection.commit(); connection.close()


def test_strict_query_plan_validation_and_remote_endpoint_gate() -> None:
    assert _plan()["event_types"] == ["shot_on_target"]
    with pytest.raises(ValueError, match="keys"):
        module.validate_query_plan({"search_terms": ["shot"]})
    with pytest.raises(ValueError, match="loopback"):
        module.ensure_loopback_endpoint("https://example.com/v1")


def test_loopback_transport_disables_proxies_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeOpener:
        def open(self, target, *, timeout):
            observed["target"] = target
            observed["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(*handlers):
        observed["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(module, "build_opener", fake_build_opener)
    with module._loopback_urlopen("http://127.0.0.1:1240/v1/models", timeout=1.25):
        pass

    proxy = next(handler for handler in observed["handlers"] if isinstance(handler, module.ProxyHandler))
    redirect = next(handler for handler in observed["handlers"] if isinstance(handler, module._NoRedirectHandler))
    assert proxy.proxies == {}
    assert redirect.redirect_request(None, None, 302, "Found", {}, "https://example.com") is None
    assert observed["target"] == "http://127.0.0.1:1240/v1/models"
    assert observed["timeout"] == 1.25

    with pytest.raises(ValueError, match="loopback"):
        module._loopback_urlopen("https://example.com/v1/models", timeout=1)


def test_literal_fallback_is_explicit_and_does_not_invent_event_filters() -> None:
    plan = module.fallback_query_plan("Show me long balls by number 8", "offline")
    assert plan["event_types"] == []
    assert "long" in plan["search_terms"] and "8" in plan["search_terms"]
    assert "offline" in plan["explanation"]


def test_deterministic_rank_exposes_match_evidence(tmp_path: Path) -> None:
    database = tmp_path / "search.sqlite3"
    _database(database)
    results = module.rank_saved_events(database, _plan())
    assert len(results) == 1
    assert results[0]["event_id"] == "e1"
    assert results[0]["score"] == 16.0
    assert {item["kind"] for item in results[0]["matched_on"]} == {
        "event_type", "search_term", "participant", "phase", "field_area",
    }


def test_goal_token_does_not_match_goalkeeper_prefix() -> None:
    assert not module._contains_phrase("goalkeeper makes a save", "goal")
    assert module._contains_phrase("a goal is scored", "goal")


def test_query_prompt_contains_no_heldout_labels_or_audit_warning() -> None:
    system, user = module.query_interpreter_prompt("find goalkeeper shots")
    joined = (system + user).casefold()
    assert "held-out" not in joined
    assert "factually wrong" not in joined
    assert "coach query: find goalkeeper shots" in joined


def test_query_llm_outage_returns_labeled_literal_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args, **_kwargs):
        raise URLError("fixture offline")

    monkeypatch.setattr(module, "_loopback_urlopen", offline)
    result = module.interpret_coach_query("find long balls by number 8", timeout_s=0.01)
    assert result["source"] == "deterministic_literal_fallback"
    assert result["plan"]["event_types"] == []
    assert "URLError" in result["error"]
    assert result["reported_model"] is None


def _model_response(monkeypatch, plan, *, reported_model="fixture-model"):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            raw = {key: value for key, value in plan.items() if key != "schema_version"}
            return json.dumps({"model": reported_model, "choices": [
                {"message": {"content": json.dumps(raw)}}
            ]}).encode()

    monkeypatch.setattr(module, "_loopback_urlopen", lambda *_args, **_kwargs: Response())


def test_schema_valid_plan_cannot_hide_missing_action_in_explanation(monkeypatch):
    # Constructed regression for the documented September 3 cutback/shot omission.
    # This is a software check, not a replay of an independently scored coach query.
    _model_response(monkeypatch, _plan(
        intent_summary="Find cutbacks and shots", event_types=[],
        search_terms=["cutback"], participant_terms=[], phases=[], field_areas=[],
        explanation="Find cutbacks and a shot.",
    ))
    result = module.interpret_coach_query("Find cutbacks and a shot")
    assert result["source"] == "deterministic_literal_fallback"
    assert "shot" in result["plan"]["search_terms"]
    assert "omitted requested action concepts: shot" in result["error"]
    assert result["reported_model"] == "fixture-model"


@pytest.mark.parametrize("query,plan", [
    ("find shots", _plan(search_terms=["finishing"])),
    ("find the goalkeeper", _plan(event_types=[], search_terms=["goalkeeper"])),
    ("find cutbacks and shots", _plan(search_terms=["cut back"])),
])
def test_guard_accepts_action_in_executable_fields_without_prefix_false_alarm(monkeypatch, query, plan):
    _model_response(monkeypatch, plan)
    result = module.interpret_coach_query(query)
    assert result["source"] == "local_query_llm"


def test_success_without_reported_identity_does_not_invent_one(monkeypatch):
    _model_response(monkeypatch, _plan(), reported_model=None)
    result = module.interpret_coach_query("find shots", model="requested-only")
    assert result["source"] == "local_query_llm"
    assert result["requested_model"] == "requested-only"
    assert result["reported_model"] is None


def test_literal_fallback_keeps_actions_after_long_query_prefix():
    result = module.fallback_query_plan(
        "Please find clips involving our home team wearing blue playing near the left side with a cutback and shot",
        "fixture error",
    )
    assert "cutback" in result["search_terms"]
    assert "shot" in result["search_terms"]


def test_goal_area_is_not_evidence_that_goal_action_was_preserved(monkeypatch):
    _model_response(monkeypatch, _plan(
        event_types=[], search_terms=["goalkeeper"],
        participant_terms=["goalkeeper"], field_areas=["goal_area"],
    ))
    result = module.interpret_coach_query("Find goals")
    assert result["source"] == "deterministic_literal_fallback"
    assert "omitted requested action concepts: goal" in result["error"]



# Regression: participant filter validation with multiple attributes
# The guard must reject plans that attach multiple participant attributes without a bounded positive binding.
def test_participant_filter_rejects_multiple_attributes_without_positive_binding(monkeypatch):
    """Regression for the documented September 3 multi-attribute rejection."""
    _model_response(monkeypatch, _plan(
        intent_summary="Find shots by the goalkeeper",
        event_types=["shot_on_target"],
        search_terms=["shot", "goalkeeper"],
        participant_terms=["goalkeeper", "red kit"],  # Multiple attributes without positive binding
        phases=[], field_areas=[], explanation="Find shots and goalkeeper.",
    ))
    result = module.interpret_coach_query("Find shots by the goalkeeper")
    assert result["source"] == "deterministic_literal_fallback"
    assert "omitted requested action concepts: goal" in result["error"] or \
           "unsupported participant attributes without a bounded positive single-participant binding" in result["error"]

# Operator-directed synthetic event-type eligibility regressions (2026-09-08).
# Saved report tags are not visual ground truth. No media or model calls occur.
def _eligibility_v1_database(path, records):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE windows(window_id TEXT PRIMARY KEY, match_id TEXT, status TEXT);
            CREATE TABLE events(event_id TEXT PRIMARY KEY,window_id TEXT,start_s REAL,end_s REAL,confidence REAL,report_json TEXT);
        """)
        connection.execute("INSERT INTO windows VALUES('SYNTHETIC-WINDOW','SYNTHETIC-MATCH','complete')")
        for row in records:
            connection.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (
                row["event_id"], "SYNTHETIC-WINDOW", row["start_s"], row["start_s"] + 1,
                row.get("confidence", 0.5), json.dumps(row["report"]),
            ))
    return path


def _eligibility_v1_record(identifier, event_types, *, start=10, text="An event.", **fields):
    report = {"event_types": event_types, "primary_action": text,
              "participants": [], "field_areas": [], "phase_of_play": "unknown"}
    report.update(fields)
    return {"event_id": "SYNTHETIC-" + identifier, "start_s": start, "report": report}


def test_eligibility_v1_exact_saved_absent_shot_plan(tmp_path):
    fixture = json.loads((ROOT / "artifacts/project-capability-20260908/event-type-eligibility-v1/saved-absent-shot-fixture.json").read_text(encoding="utf-8"))
    assert fixture["synthetic"] is True
    assert fixture["case"]["query"] == "Show the first shot on goal."
    plan = module.validate_query_plan(fixture["raw_model_plan"], query=fixture["case"]["query"])
    database = _eligibility_v1_database(tmp_path / "saved.sqlite3", fixture["case"]["records"])
    # Before repair this returns pass-only, score 3 from middle_third alone.
    assert module.rank_saved_events(database, plan) == []


def test_eligibility_v1_optional_and_text_boosts_cannot_rescue_mismatched_type(tmp_path):
    records = [_eligibility_v1_record("pass", ["short_pass"], text="A shot by the goalkeeper in midfield.",
               participants=[{"player_reference": "goalkeeper", "action": "shot"}],
               phase_of_play="chance_creation", field_areas=["goal_area"])]
    database = _eligibility_v1_database(tmp_path / "boosts.sqlite3", records)
    # Deliberately contradictory synthetic prose exercises precedence: explicit
    # report tags decide this software filter; neither is a visual truth claim.
    assert module.rank_saved_events(database, _plan()) == []


def test_eligibility_v1_typed_match_needs_no_optional_metadata(tmp_path):
    records = [_eligibility_v1_record("shot", ["shot_on_target"])]
    database = _eligibility_v1_database(tmp_path / "type-only.sqlite3", records)
    result = module.rank_saved_events(database, _plan(search_terms=['unused']))
    assert [row["event_id"] for row in result] == ["SYNTHETIC-shot"]
    assert result[0]["score"] == 6.0
    assert result[0]["matched_on"] == [{"kind": "event_type", "value": "shot_on_target", "weight": 6.0}]


def test_eligibility_v1_alternatives_are_or_and_existing_tiebreak_is_unchanged(tmp_path):
    records = [
        dict(_eligibility_v1_record("high-confidence", ["shot_on_target"], start=30), confidence=0.9),
        _eligibility_v1_record("late", ["shot_on_target"], start=20),
        _eligibility_v1_record("early-b", ["shot_off_target"], start=10),
        _eligibility_v1_record("early-a", ["shot_on_target"], start=10),
    ]
    database = _eligibility_v1_database(tmp_path / "alternatives.sqlite3", records)
    plan = _plan(event_types=["shot_on_target", "shot_off_target"], search_terms=["unused"],
                 participant_terms=[], phases=[], field_areas=[])
    result = module.rank_saved_events(database, plan)
    assert [row["event_id"] for row in result] == ["SYNTHETIC-high-confidence", "SYNTHETIC-early-a", "SYNTHETIC-early-b", "SYNTHETIC-late"]
    assert [row["score"] for row in result] == [6.0, 6.0, 6.0, 6.0]


def test_eligibility_v1_empty_type_list_preserves_literal_and_optional_ranking(tmp_path):
    records = [_eligibility_v1_record("pass", ["short_pass"], text="A shot by the goalkeeper.",
               participants=[{"player_reference": "goalkeeper", "action": "shot"}],
               phase_of_play="chance_creation", field_areas=["goal_area"])]
    database = _eligibility_v1_database(tmp_path / "empty-filter.sqlite3", records)
    result = module.rank_saved_events(database, _plan(event_types=[]))
    assert [row["event_id"] for row in result] == ["SYNTHETIC-pass"]
    assert result[0]["score"] == 10.0


# Operator-directed capability regressions. Corpus/response are saved synthetic
# development evidence; HTTP streams and provider responses below are in memory.
def _ordinal_v1_fixture():
    return json.loads((ROOT / "artifacts/project-capability-20260908/ordinal-query-capability-v1/saved-ordinal-fixture.json").read_text(encoding="utf-8"))


def _ordinal_v1_http(query, monkeypatch, transport_mode):
    from io import BytesIO
    from types import SimpleNamespace

    fixture = _ordinal_v1_fixture()
    calls = {"transport": 0, "fallback": 0, "ranker": 0}
    original_fallback = module.fallback_query_plan

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(fixture["response"]).encode("utf-8")

    def transport(*_args, **_kwargs):
        calls["transport"] += 1
        if transport_mode == "timeout":
            raise TimeoutError("synthetic provider timeout; no socket used")
        return Response()

    def fallback(*args, **kwargs):
        calls["fallback"] += 1
        return original_fallback(*args, **kwargs)

    def ranker(*_args, **_kwargs):
        calls["ranker"] += 1
        return []

    body = json.dumps({"query": query}).encode("utf-8")
    handler = object.__new__(module.DemoHandler)
    handler.path = "/api/search"
    handler.headers = {"content-length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.server = SimpleNamespace(demo_context=SimpleNamespace(
        endpoint="http://127.0.0.1:1/v1", model="synthetic-provider",
        database=Path("unused-synthetic-database"), audit={},
    ))
    observed = {"headers": {}}
    handler.send_response = lambda status: observed.update(status=int(status))
    handler.send_header = lambda name, value: observed["headers"].update({name: value})
    handler.end_headers = lambda: None
    with monkeypatch.context() as patch:
        patch.setattr(module, "_loopback_urlopen", transport)
        patch.setattr(module, "fallback_query_plan", fallback)
        patch.setattr(module, "rank_saved_events", ranker)
        module.DemoHandler.do_POST(handler)
    observed["body"] = json.loads(handler.wfile.getvalue().decode("utf-8"))
    observed["calls"] = calls
    return observed


@pytest.mark.parametrize("transport_mode", ["saved_response", "timeout"])
def test_ordinal_v1_saved_http_query_is_explicitly_unsupported(monkeypatch, transport_mode):
    fixture = _ordinal_v1_fixture()
    assert fixture["synthetic"] is True and fixture["scientific_metric_eligible"] is False
    assert fixture["case"]["query"] == "Show the second corner delivery."
    observed = _ordinal_v1_http(fixture["case"]["query"], monkeypatch, transport_mode)
    assert observed["status"] == 422
    assert observed["headers"]["content-type"] == "application/json; charset=utf-8"
    assert observed["body"]["error_code"] == "unsupported_ordinal_constraint"
    message = observed["body"]["error"]
    assert isinstance(message, str) and "not supported" in message
    assert "without an occurrence number" in message
    assert "results" not in observed["body"] and "interpretation" not in observed["body"]
    # A valid saved response and an outage must both be stopped before any work.
    assert observed["calls"] == {"transport": 0, "fallback": 0, "ranker": 0}


def test_ordinal_v1_word_and_numeric_occurrences_do_not_call_transport(monkeypatch):
    calls = []

    def forbidden_transport(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("ordinal query reached the fake transport")

    monkeypatch.setattr(module, "_loopback_urlopen", forbidden_transport)
    for query in [
        "Show the first shot on goal.", "Show the third corner delivery.",
        "Show the 1st corner.", "Show the 2nd corner.", "Show the 3rd free kick.",
        "Show the 12th throw-in.", "Show the 21st pass.", "SHOW THE SECOND-CORNER.",
    ]:
        with pytest.raises(ValueError, match="not supported") as caught:
            module.interpret_coach_query(query)
        assert getattr(caught.value, "code", None) == "unsupported_ordinal_constraint"
    assert calls == []


@pytest.mark.parametrize("transport_mode", ["saved_response", "timeout"])
def test_ordinal_v1_nonoccurrence_controls_preserve_http_paths(monkeypatch, transport_mode):
    for query in [
        "Show corner deliveries.", "Show corners from the second half.",
        "Show corners by the second striker.", "Show corners by jersey number 2.",
        "Show corners by #2.", "Show 2nd-half corners.", "Show first-team corners.",
    ]:
        observed = _ordinal_v1_http(query, monkeypatch, transport_mode)
        assert observed["status"] == 200, query
        assert observed["body"]["results"] == [] and observed["body"]["result_count"] == 0
        assert "error_code" not in observed["body"]
        trace = observed["body"]["interpretation"]
        assert observed["calls"] == {"transport": 1, "fallback": int(transport_mode == "timeout"), "ranker": 1}
        if transport_mode == "timeout":
            assert trace["source"] == "deterministic_literal_fallback"
            assert trace["plan"]["event_types"] == []
            assert "TimeoutError" in trace["error"]
        else:
            assert trace["source"] == "local_query_llm"
            assert trace["plan"]["event_types"] == ["corner_kick"]


def test_ordinal_v1_invalid_query_retains_existing_validation(monkeypatch):
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("invalid query reached transport")

    monkeypatch.setattr(module, "_loopback_urlopen", forbidden_transport)
    for query in [None, "", " ", "x" * 501]:
        with pytest.raises(ValueError, match="query must contain"):
            module.interpret_coach_query(query)

@pytest.mark.parametrize("transport_mode", ["saved_response", "timeout"])
@pytest.mark.parametrize("query", [
    "Find cutbacks leading to a shot",
    "Find shots followed by a cutback",
    "Find shots that follow a cutback",
])
def test_temporal_order_v1_rejects_saved_opposite_order_queries_before_work(monkeypatch, transport_mode, query):
    observed = _ordinal_v1_http(query, monkeypatch, transport_mode)
    assert observed["status"] == 422
    assert observed["body"]["error_code"] == "unsupported_temporal_order_constraint"
    assert "not supported" in observed["body"]["error"]
    assert "results" not in observed["body"] and "interpretation" not in observed["body"]
    assert observed["calls"] == {"transport": 0, "fallback": 0, "ranker": 0}

@pytest.mark.parametrize("query", [
    "Find shots and cutbacks",
    "Find shots after halftime",
    "Find cutbacks from the right flank",
])
def test_temporal_order_v1_nonorder_controls_preserve_existing_path(monkeypatch, query):
    observed = _ordinal_v1_http(query, monkeypatch, "saved_response")
    assert observed["status"] == 200
    assert "error_code" not in observed["body"]
    assert observed["calls"]["transport"] == 1
    assert observed["calls"]["ranker"] == 1
