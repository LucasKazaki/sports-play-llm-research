"""One finite, loopback-only development experiment for Company Runtime.

Eight text queries; invented report records; no media/holdout access, model
loading, training, credentials, Studio API access, scheduler or automatic retry.
The synthetic expectations are engineering oracles, not human soccer labels.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
import search_demo_server as search

ENDPOINT = "http://127.0.0.1:1234/v1"
MODEL = "loops-gtx1080-qwen3-4b"
OUT = ROOT / "artifacts/project-capability-20260908/local-model-experiment-v1"
FIXTURE = ROOT / "research/fixtures/coach-query-design-cases-v2.json"
PREVIOUS = ROOT / "artifacts/college-sports-market-20260907/query-development-probe.json"
MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT_S = 25
BUDGET_S = 240
MAX_TOKENS = 900


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def event(name, text, start, types, areas=()):
    return {"event_id": "SYNTHETIC-EVENT-" + name, "start_s": start,
            "report": {"event_types": types, "primary_action": text,
                       "field_areas": list(areas), "phase_of_play": "unknown",
                       "participants": [], "detailed_description": text,
                       "uncertainty": "Invented development record; no visual observation."}}


def build_cases():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
    assert fixture["scientific_validation"] is False and fixture["frozen_for_evaluation"] is False
    cases = [{"id": row["id"], "query": row["humanQuestion"],
              "origin": "exact existing unreviewed development design question"}
             for row in fixture["cases"]]
    assert [row["id"] for row in cases] == ["visible_event", "absent_event", "repeated_event", "distractor", "insufficient_view"]
    for row in fixture["cases"]:
        assert row["mediaBinding"] is None and row["goldAnswer"] is None
    old = json.loads(PREVIOUS.read_text(encoding="utf-8-sig"))
    assert old["query"] == "Find cutbacks leading to a shot"
    cases.extend([
        {"id": "cutback_then_shot", "query": old["query"], "origin": "exact existing September 7 development probe query"},
        {"id": "cutback_without_shot", "query": "Find cutbacks without a shot", "origin": "new explicit negation development contrast"},
        {"id": "shot_then_cutback", "query": "Find shots followed by a cutback", "origin": "new explicit reverse-order development contrast"},
    ])
    corpus = {
        "visible_event": ([event("visible-reception", "A pass is received inside the penalty area.", 20, ["short_pass"], ["penalty_area"]), event("midfield-reception", "A pass is received in midfield.", 10, ["short_pass"], ["middle_third"])], "visible-reception", "Explicit invented location text"),
        "absent_event": ([event("pass-only", "A pass is received in midfield.", 10, ["short_pass"], ["middle_third"])], None, "Invented corpus has no shot; expected empty selection"),
        "repeated_event": ([event("first-corner", "A corner delivery.", 10, ["corner_kick"]), event("second-corner", "A corner delivery.", 20, ["corner_kick"])], "second-corner", "Second occurrence by invented event start; descriptions are equal"),
        "distractor": ([event("unrelated-pass", "A nearby unrelated pass.", 10, ["short_pass"]), event("through-pass", "A through pass.", 20, ["through_ball"])], "through-pass", "Explicit invented through-pass target versus unrelated distractor"),
        "insufficient_view": ([event("occluded", "The ball is occluded and control is unknown.", 10, ["other"])], None, "No invented record supports player control; retrieval is not an answer or abstention mechanism"),
    }
    ordering = [event("reverse", "A shot happens before a cutback.", 10, ["cross", "shot_on_target"]), event("cutback-only", "A cutback only.", 20, ["cross"]), event("forward", "A cutback happens before a shot.", 30, ["cross", "shot_on_target"])]
    corpus.update({
        "cutback_then_shot": (ordering, "forward", "Explicit invented cutback-before-shot relation"),
        "cutback_without_shot": (ordering, "cutback-only", "Only invented cutback-only record lacks a shot"),
        "shot_then_cutback": (ordering, "reverse", "Explicit invented shot-before-cutback relation"),
    })
    for case in cases:
        records, expected, rule = corpus[case["id"]]
        case.update(records=records, expected_top1=None if expected is None else "SYNTHETIC-EVENT-" + expected,
                    synthetic_expectation_rule=rule, synthetic=True, scientific_metric_eligible=False)
    return cases


def payload_for(case):
    system, user = search.query_interpreter_prompt(case["query"])
    return {"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": search.query_plan_response_format(), "temperature": 0, "max_tokens": MAX_TOKENS, "stream": False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request_json(url, payload=None, *, timeout, receipt_name=None):
    if url not in {ENDPOINT + "/models", ENDPOINT + "/chat/completions"}:
        raise ValueError("Only the pinned local model endpoints are admitted")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if receipt_name:
        write(receipt_name, {"url": url, "http_status": status, "received_at": now(),
                            "body": raw[:MAX_RESPONSE_BYTES].decode("utf-8", errors="replace"),
                            "body_sha256": hashlib.sha256(raw).hexdigest(),
                            "response_truncated_by_byte_cap": len(raw) > MAX_RESPONSE_BYTES})
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Model response exceeded the frozen byte cap")
    if not 200 <= status < 300:
        raise ValueError("Local model HTTP status " + str(status) + "; raw response retained")
    return json.loads(raw.decode("utf-8"))


def assess(raw, query):
    result = {"model_completed": False, "schema_valid": False, "action_guard_pass": False,
              "reported_model": None, "finish_reason": None, "raw_plan": None, "missing_action_concepts": []}
    try:
        result["reported_model"] = raw.get("model")
        choice = raw["choices"][0]
        result["finish_reason"] = choice.get("finish_reason")
        if result["reported_model"] != MODEL:
            raise ValueError("Response model identity is missing or differs from requested alias")
        if result["finish_reason"] != "stop":
            raise ValueError("Response did not finish normally; truncations remain failures")
        plan = json.loads(choice["message"]["content"])
        normalized = search.validate_query_plan(plan)
        result.update(model_completed=True, schema_valid=True, raw_plan=normalized)
        executable = " ".join(normalized["event_types"] + normalized["search_terms"])
        covered = set(search._action_concepts(executable))
        result["missing_action_concepts"] = [term for term in search._action_concepts(query) if term not in covered]
        search.validate_query_plan(plan, query=query)
        result["action_guard_pass"] = True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        result["error"] = str(error)
    return result


def rank_case(database, case, plan):
    with sqlite3.connect(database) as db:
        db.executescript("CREATE TABLE windows(window_id TEXT PRIMARY KEY,match_id TEXT,status TEXT); CREATE TABLE events(event_id TEXT PRIMARY KEY,window_id TEXT,start_s REAL,end_s REAL,confidence REAL,report_json TEXT);")
        db.execute("INSERT INTO windows VALUES('SYNTHETIC-WINDOW','SYNTHETIC-MATCH','complete')")
        for row in case["records"]:
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (row["event_id"], "SYNTHETIC-WINDOW", row["start_s"], row["start_s"] + 1, 0.5, json.dumps(row["report"])))
    ranked = search.rank_saved_events(database, plan, limit=len(case["records"]))
    top = ranked[0]["event_id"] if ranked else None
    return {"top1": top, "expected_top1": case["expected_top1"], "matches_engineered_expectation": top == case["expected_top1"],
            "ranked": [{key: row[key] for key in ("event_id", "score", "matched_on")} for row in ranked]}


def summarize(rows):
    total = len(rows)
    summary = {"requested_cases": total, "status_counts": dict(Counter(row["status"] for row in rows)),
               "model_completed": sum(bool((row.get("assessment") or {}).get("model_completed")) for row in rows),
               "schema_valid": sum(bool((row.get("assessment") or {}).get("schema_valid")) for row in rows),
               "action_guard_pass": sum(bool((row.get("assessment") or {}).get("action_guard_pass")) for row in rows)}
    summary["model_action_guard_fraction_all_requested"] = summary["action_guard_pass"] / total if total else None
    summary["arms"] = {}
    for arm in ("literal_baseline", "raw_model", "guarded_model_with_fallback"):
        outcomes = [(row.get("arms") or {}).get(arm) for row in rows]
        correct = sum(bool(outcome and outcome["matches_engineered_expectation"]) for outcome in outcomes)
        answered = [outcome for outcome in outcomes if outcome and outcome["top1"] is not None]
        summary["arms"][arm] = {"requested_denominator": total, "available_rankings": sum(outcome is not None for outcome in outcomes),
            "engineered_expectation_matches": correct, "match_fraction_all_requested": correct / total if total else None,
            "nonempty_top1_count": len(answered), "selective_top1_risk": sum(not outcome["matches_engineered_expectation"] for outcome in answered) / len(answered) if answered else None}
    summary["selective_top1_risk"] = summary["arms"]["raw_model"]["selective_top1_risk"]
    summary["interpretation"] = "Synthetic development selection checks only. Fallback is a separate system arm, never model success. Empty retrieval is not a validated abstention answer. No scientific accuracy or frontier-quality claim."
    return summary


def main():
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Use --run for one finite experiment; output must not already exist")
    cases = build_cases()
    # Exclusive creation prevents a replay from overwriting or launching calls.
    OUT.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), FIXTURE, PREVIOUS, ROOT / "tests/test_local_model_experiment.py", *(ROOT / "prototype" / name for name in ("search_demo_server.py", "searchable_match_vlm.py", "real_clip_vlm.py"))]
    source_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in sources}
    contract = {"schema": "native-local-model-development-v1", "frozen_at": now(), "source_sha256": source_hashes,
        "model_requested": MODEL, "endpoint": ENDPOINT, "max_model_calls": 8, "request_timeout_s": REQUEST_TIMEOUT_S,
        "max_tokens_per_request": MAX_TOKENS, "max_response_bytes": MAX_RESPONSE_BYTES, "overall_budget_s_checked_between_requests": BUDGET_S,
        "automatic_retries": 0, "temperature": 0, "cases": cases, "payloads": [payload_for(case) for case in cases],
        "primary_engineering_check": "Existing lexical action guard pass count over all eight requested cases; schema validity is reported separately.",
        "secondary_checks": "Engineered top1/empty-selection expectations on invented text records, same raw response with and without the existing action guard, literal fallback, latency and failures.",
        "stop_go": "Do not promote autonomous query/retrieval quality from this test. Any omitted action, timeout, identity/malformed failure, or negation/order/ordinal selection error blocks a full-constraint guarantee; retain exact example for a separate repair.",
        "media_used": False, "heldout_files_or_labels_used": False, "training_performed": False, "scientific_validation": False,
        "model_weight_hash": None, "weight_identity_limit": "Endpoint alias and response model field only; not an independently hashed checkpoint.",
        "previous_probe_boundary": "Prior operator-run single-query probe is a query/provenance source only; it is not a matched model-quality comparator."}
    write("contract.json", contract)
    started = time.perf_counter()
    metadata_error = None
    try:
        metadata = request_json(ENDPOINT + "/models", timeout=5, receipt_name="wire-model-metadata.json")
        selected = [row for row in metadata.get("data", []) if row.get("id") == MODEL]
        if len(selected) != 1:
            raise ValueError("Exactly one requested model alias must already be listed; no model loading is performed")
        write("model-metadata.json", {"captured_at": now(), "selected_model": selected[0], "response_sha256": hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()})
    except (HTTPError, URLError, OSError, ValueError, TypeError) as error:
        metadata_error = type(error).__name__ + ": " + str(error)
        write("model-metadata.json", {"captured_at": now(), "error": metadata_error})
    rows = []
    for ordinal, case in enumerate(cases):
        row = {"case_id": case["id"], "query": case["query"], "status": "not_attempted", "attempted_model_call": False, "assessment": None, "arms": {}}
        baseline = search.fallback_query_plan(case["query"], "Frozen deterministic baseline; no model involved")
        row["literal_plan"] = baseline
        row["arms"]["literal_baseline"] = rank_case(OUT / f"{ordinal}-literal.sqlite3", case, baseline)
        elapsed = time.perf_counter() - started
        call_started = time.perf_counter()
        if metadata_error:
            row.update(status="model_metadata_failure", error=metadata_error)
        elif elapsed >= BUDGET_S:
            row["status"] = "budget_not_attempted"
        else:
            try:
                row["attempted_model_call"] = True
                raw = request_json(ENDPOINT + "/chat/completions", contract["payloads"][ordinal], timeout=min(REQUEST_TIMEOUT_S, BUDGET_S - elapsed), receipt_name=f"wire-response-{ordinal:02d}-{case['id']}.json")
                write(f"response-{ordinal:02d}-{case['id']}.json", raw)
                row["assessment"] = assess(raw, case["query"])
                row["status"] = "model_response" if row["assessment"]["model_completed"] else "invalid_model_response"
                if row["assessment"]["schema_valid"]:
                    row["arms"]["raw_model"] = rank_case(OUT / f"{ordinal}-raw.sqlite3", case, row["assessment"]["raw_plan"])
                row["usage_reported"] = raw.get("usage")
            except (HTTPError, URLError, OSError, ValueError, TypeError) as error:
                row.update(status="timeout" if isinstance(error, TimeoutError) else "request_failure", error=type(error).__name__ + ": " + str(error))
        row["latency_ms"] = round((time.perf_counter() - call_started) * 1000, 3)
        accepted = bool(row["assessment"] and row["assessment"]["action_guard_pass"])
        row["guarded_source"] = "same_saved_model_response" if accepted else "deterministic_literal_fallback"
        row["arms"]["guarded_model_with_fallback"] = rank_case(OUT / f"{ordinal}-guarded.sqlite3", case, row["assessment"]["raw_plan"] if accepted else baseline)
        rows.append(row)
        write(f"outcome-{ordinal:02d}-{case['id']}.json", row)
        print(json.dumps({"case_id": case["id"], "status": row["status"], "guarded_source": row["guarded_source"], "latency_ms": row["latency_ms"]}), flush=True)
    summary = summarize(rows)
    source_changes = [name for name, digest in source_hashes.items() if sha(ROOT / name) != digest]
    write("results.json", {"finished_at": now(), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "summary": summary, "source_changes_during_experiment": source_changes, "rows": rows, "python": sys.version, "platform": platform.platform(), "scientific_validation": False})
    write("manifest.json", {"created_at": now(), "files": {path.name: sha(path) for path in sorted(OUT.iterdir()) if path.is_file()}, "source_sha256": source_hashes})
    print(json.dumps({"status": "artifact_complete", "source_changes_during_experiment": source_changes, "summary": summary}), flush=True)
    if source_changes:
        raise SystemExit("Sources changed during experiment: result is not eligible for comparison")


if __name__ == "__main__":
    main()
