"""Rehearse the real local demo; health alone is not presentation readiness.

This verifies systems behavior and the explicit semantic NO-GO boundary.
It makes no visual-model calls, validates no event, and promotes no deliverable.
Default checks exercise literal search; --require-local-model also requires a
successful local query-interpretation response, never a silent fallback.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("The local rehearsal does not follow redirects")


def local_base(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("Use a plain loopback HTTP origin without credentials, path, query, or fragment")
    return value.rstrip("/")


def status_checks(status: dict, require_local_model: bool = False) -> dict[str, bool]:
    return {
        "soccer_available": status.get("key") == "soccer" and status.get("available") is True,
        "sealed_longform_backend": status.get("backend") == "soccermaster_longform_v1",
        "all_96_windows_loaded": status.get("window_count") == 96,
        "both_complete_halves": status.get("coverage", {}).get("dense_entire_game_index") is True
            and status.get("coverage", {}).get("dense_window_count") == 90
            and status.get("coverage", {}).get("source_halves") == 2,
        "semantic_no_go_preserved": status.get("semantic_contract", {}).get("status") == "NO-GO"
            and "SEMANTIC NO-GO" in status.get("demo_status", ""),
        "performance_claims_blocked": status.get("performance_claim_allowed") is False,
        "labels_and_audio_excluded": status.get("labels_supplied_to_vlm") is False
            and status.get("audio_supplied_to_vlm") is False,
        "requested_query_mode": status.get("query_mode") == (
            "local_query_llm" if require_local_model else "deterministic_literal_fallback"),
    }


def search_checks(search: dict, clips: dict, require_local_model: bool = False) -> dict[str, bool]:
    results = search.get("results", [])
    plan = search.get("interpretation", {})
    checks = {
        "soccer_results_returned": search.get("sport") == "soccer" and len(results) > 0,
        "count_matches_payload": search.get("result_count") == len(results),
        "semantic_warning_visible": "SEMANTIC NO-GO" in search.get("demo_status", ""),
        "query_execution_mode": bool(plan.get("source")) and (
            plan.get("source") == "local_query_llm" and not plan.get("error")
            if require_local_model else plan.get("source") == "deterministic_literal_fallback"),
    }
    checks["all_results_have_valid_playback"] = bool(results) and all(
        r.get("clip_url") in clips
        and isinstance(r.get("relative_start_s"), (int, float))
        and isinstance(r.get("relative_end_s"), (int, float))
        and 0 <= r["relative_start_s"] < r["relative_end_s"] <= clips[r["clip_url"]]["duration_s"]
        for r in results
    )
    return checks


def rehearsal(base: str, output: Path, require_local_model: bool = False) -> dict:
    base = local_base(base)
    output.mkdir(parents=True, exist_ok=True)
    opener = build_opener(NoRedirect())
    checks: dict[str, bool] = {}
    evidence = []
    failures = []

    def fetch(route: str, payload: dict | None = None):
        req = Request(base + route, headers={"content-type": "application/json"},
                      data=json.dumps(payload).encode() if payload is not None else None)
        with opener.open(req, timeout=90 if payload else 10) as response:
            return json.load(response)

    def save(name: str, payload: dict):
        path = output / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        evidence.append({"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    try:
        health = fetch("/healthz")
        save("health.json", health)
        checks["soccer_health"] = health.get("ok") is True and health.get("sports", {}).get("soccer") is True
        status = fetch("/api/status?sport=soccer")
        save("soccer-status.json", status)
        checks.update(status_checks(status, require_local_model))
        clips = {c["clip_url"]: c for c in status.get("clips", [])}
        checks["two_half_media_routes"] = len(clips) == 2
        for route in clips:
            if not route.startswith("/media/soccer/") or urlsplit(route).netloc or ".." in route:
                raise ValueError("Unexpected soccer media route")
            request = Request(base + route, headers={"Range": "bytes=0-1023"})
            with opener.open(request, timeout=10) as response:
                sample = response.read(1025)
                content_range = response.headers.get("content-range", "")
                checks[f"media:{route}"] = (response.status == 206 and len(sample) == 1024
                    and content_range.startswith("bytes 0-1023/")
                    and response.headers.get("content-type", "").startswith("video/"))
                evidence.append({"route": route, "status": response.status,
                                 "content_range": content_range, "sample_bytes": len(sample),
                                 "sample_sha256": hashlib.sha256(sample).hexdigest()})
        for index, query in enumerate(("Show shots on goal", "Find crosses into the penalty area"), 1):
            search = fetch("/api/search", {"sport": "soccer", "query": query})
            save(f"search-{index}.json", search)
            checks.update({f"query_{index}:{k}": v for k, v in search_checks(search, clips, require_local_model).items()})
        with opener.open(base + "/", timeout=10) as response:
            html = response.read().decode("utf-8")
            checks["demo_html_available"] = response.status == 200 and "<html" in html.lower()
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
    receipt = {
        "schema_version": "playground-demo-readiness-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base, "passed": bool(checks) and all(checks.values()) and not failures,
        "scope": "Local systems rehearsal only; event correctness and coach utility remain unvalidated.",
        "query_mode_required": "local_query_llm" if require_local_model else "deterministic_literal_fallback",
        "performance_claim_allowed": False, "shareable_candidate_promoted": False,
        "visual_model_calls": 0, "checks": checks, "failures": failures, "evidence": evidence,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8771")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-local-model", action="store_true")
    args = parser.parse_args()
    result = rehearsal(args.url, args.out, args.require_local_model)
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"]),
                      "failed_checks": [k for k, v in result["checks"].items() if not v],
                      "failures": result["failures"], "receipt": str(args.out / "receipt.json")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
