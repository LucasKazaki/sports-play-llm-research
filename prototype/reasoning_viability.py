"""Evaluate a local text reasoner over saved soccer-model evidence.

This module does not inspect video or change the underlying VLM predictions.
It asks a loopback-only text model to turn already sealed aggregate evidence
into a conservative research decision, then deterministically checks that the
model copied the evidence correctly and respected the project's claim gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALUATION = ROOT / "artifacts/soccermaster-scale-v1/vlm-eval-v1/evaluation.json"
DEFAULT_LONGFORM = ROOT / "artifacts/soccermaster-longform-v1/report-metrics.json"
DEFAULT_OUTPUT = ROOT / "artifacts/local-reasoning-viability-v1"
DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
SCHEMA_VERSION = "playground-local-reasoning-viability-v1"

VERDICTS = ["systems_only", "promising_but_unvalidated", "coach_ready"]
BLOCKED_CLAIMS = [
    "reliable_soccer_semantics",
    "coach_ready",
    "calibrated_confidence",
    "official_soccermaster_checkpoint_reproduced",
]
REQUIRED_BLOCKED_CLAIMS = set(BLOCKED_CLAIMS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def ensure_loopback(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("reasoning endpoint must be loopback-only")


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def build_evidence_packet(evaluation: dict[str, Any], longform: dict[str, Any]) -> dict[str, Any]:
    return {
        "fifty_clip_local_vlm": {
            "denominator": evaluation["denominator"],
            "valid_response_count": evaluation["valid_response_count"],
            "exact_correct_count": evaluation["exact_correct_count"],
            "exact_accuracy": evaluation["exact_accuracy_counting_abstentions_and_failures_as_wrong"],
            "abstention_rate_over_valid": evaluation["abstention_rate_over_valid"],
            "performance_claim_allowed": evaluation["performance_claim_allowed"],
            "detailed_claim_factuality_evaluated": evaluation["detailed_claim_factuality_evaluated"],
            "detailed_claims_safe_for_coach_search": evaluation["detailed_claims_safe_for_coach_search"],
        },
        "ninety_six_window_local_vlm": {
            "window_denominator": longform["window_denominator"],
            "valid_response_count": longform["valid_response_count"],
            "vlm_reported_event_count": longform["vlm_reported_event_count"],
            "detailed_claim_factuality_measured": longform["detailed_claim_factuality_measured"],
            "event_accuracy_measured_before_seal": longform["event_accuracy_measured_before_seal"],
        },
        "soccer_master_boundary": {
            "experiment_kind": "local SoccerMaster-scale/long-form scaffold with local VLM outputs",
            "official_checkpoint_locally_reproduced": False,
            "paper_metrics_locally_reproduced": False,
        },
        "confidence_boundary": "VLM confidence fields are generated self-scores, not calibrated probabilities.",
    }


def response_format() -> dict[str, Any]:
    checks = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "fifty_clip_exact_correct",
            "fifty_clip_denominator",
            "fifty_clip_accuracy",
            "fifty_clip_abstention_rate",
            "longform_valid_responses",
            "longform_window_denominator",
            "longform_factuality_measured",
            "official_checkpoint_reproduced",
        ],
        "properties": {
            "fifty_clip_exact_correct": {"type": "integer"},
            "fifty_clip_denominator": {"type": "integer"},
            "fifty_clip_accuracy": {"type": "number"},
            "fifty_clip_abstention_rate": {"type": "number"},
            "longform_valid_responses": {"type": "integer"},
            "longform_window_denominator": {"type": "integer"},
            "longform_factuality_measured": {"type": "boolean"},
            "official_checkpoint_reproduced": {"type": "boolean"},
        },
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "soccer_evidence_reasoning_decision",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["verdict", "supported_findings", "blocked_claims", "next_experiment", "evidence_checks"],
                "properties": {
                    "verdict": {"type": "string", "enum": VERDICTS},
                    "supported_findings": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                        "maxItems": 6,
                    },
                    "blocked_claims": {
                        "type": "array",
                        "items": {"type": "string", "enum": BLOCKED_CLAIMS},
                        "uniqueItems": True,
                    },
                    "next_experiment": {"type": "string", "minLength": 1},
                    "evidence_checks": checks,
                },
            },
        },
    }


def prompts(packet: dict[str, Any]) -> tuple[str, str]:
    required_claims = ", ".join(BLOCKED_CLAIMS)
    system = (
        "You are the evidence-bound reasoning layer for a soccer video research prototype. "
        "Use only the supplied JSON. Copy all requested counts, rates, and units exactly; the long-form denominator is "
        "windows, not clips. A schema-valid VLM response is not "
        "evidence that its soccer interpretation is correct. If performance claims are disallowed, factuality is "
        "unmeasured, confidence is uncalibrated, or the official SoccerMaster checkpoint was not reproduced, block the "
        "corresponding claims. For this frozen packet, blocked_claims must contain each of these values exactly once: "
        f"{required_claims}. Choose systems_only unless the packet directly supports a stronger verdict. "
        "For supported_findings, select exact sentences from allowed_supported_findings below; "
        "do not paraphrase or add assertions. Include the long-form response/window sentence. "
        "The next_experiment field is an unverified proposal, not a supported finding. Return only JSON."
    )
    user = (
        "Decide whether these local VLM and SoccerMaster-related results support a coach-facing semantic system. "
        "State only supported findings, list every blocked claim, and propose one falsifiable next experiment.\n\n"
        + json.dumps(packet, sort_keys=True, separators=(",", ":"))
        + "\n\nallowed_supported_findings:\n"
        + json.dumps(allowed_supported_findings(packet), ensure_ascii=False)
    )
    return system, user


def parse_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("response must be a JSON object")
    return value


def expected_checks(packet: dict[str, Any]) -> dict[str, Any]:
    short = packet["fifty_clip_local_vlm"]
    longform = packet["ninety_six_window_local_vlm"]
    boundary = packet["soccer_master_boundary"]
    return {
        "fifty_clip_exact_correct": short["exact_correct_count"],
        "fifty_clip_denominator": short["denominator"],
        "fifty_clip_accuracy": short["exact_accuracy"],
        "fifty_clip_abstention_rate": short["abstention_rate_over_valid"],
        "longform_valid_responses": longform["valid_response_count"],
        "longform_window_denominator": longform["window_denominator"],
        "longform_factuality_measured": longform["detailed_claim_factuality_measured"],
        "official_checkpoint_reproduced": boundary["official_checkpoint_locally_reproduced"],
    }


def allowed_supported_findings(packet: dict[str, Any]) -> list[str]:
    """Render supported prose from sealed fields; arbitrary prose has no factual oracle."""
    short = packet["fifty_clip_local_vlm"]
    longform = packet["ninety_six_window_local_vlm"]
    findings = [
        f"The long-form local run produced {longform['valid_response_count']} valid responses "
        f"across {longform['window_denominator']} windows.",
        f"The short local run recorded {short['exact_correct_count']} exact correct answers "
        f"out of {short['denominator']} cases.",
        f"The long-form local VLM reported {longform['vlm_reported_event_count']} events; "
        "this count does not establish event accuracy.",
        packet["confidence_boundary"],
    ]
    if longform["detailed_claim_factuality_measured"] is False:
        findings.append("Detailed-claim factuality has not been measured for the long-form local run.")
    if packet["soccer_master_boundary"]["official_checkpoint_locally_reproduced"] is False:
        findings.append("The official SoccerMaster checkpoint has not been reproduced locally.")
    return findings


def validate_decision(value: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not isinstance(value, dict):
        return ["response must be a JSON object"]
    if set(value) != {"verdict", "supported_findings", "blocked_claims", "next_experiment", "evidence_checks"}:
        failures.append("top-level keys differ from the frozen contract")
    if value.get("verdict") != "systems_only":
        failures.append("verdict must remain systems_only for this evidence packet")
    blocked = value.get("blocked_claims")
    if (not isinstance(blocked, list) or not all(isinstance(item, str) for item in blocked)
            or len(blocked) != len(BLOCKED_CLAIMS) or set(blocked) != REQUIRED_BLOCKED_CLAIMS):
        failures.append("blocked_claims must contain exactly every required claim once")
    checks = value.get("evidence_checks")
    expected = expected_checks(packet)
    if (not isinstance(checks, dict) or checks.keys() != expected.keys()
            or any(type(checks[key]) is not type(item) or checks[key] != item for key, item in expected.items())):
        failures.append("evidence checks did not copy the supplied values and types exactly")
    findings = value.get("supported_findings")
    if not isinstance(findings, list) or not findings or not all(isinstance(item, str) and item.strip() for item in findings):
        failures.append("supported_findings must be a non-empty text list")
    else:
        normalized_findings = " ".join(findings).casefold()
        if re.search(r"\b96\W*clip", normalized_findings):
            failures.append("the long-form denominator is 96 windows, not 96 clips")
        if not any("96" in item and "window" in item.casefold() for item in findings):
            failures.append("supported findings must preserve the 96-window unit")
        allowed = allowed_supported_findings(packet)
        if len(findings) > 6 or any(item not in allowed for item in findings):
            failures.append("supported findings must select only exact evidence-rendered sentences; other prose is unverified")
        if allowed[0] not in findings:
            failures.append("supported findings must include the exact response/window counts from the evidence")
    if not isinstance(value.get("next_experiment"), str) or not value["next_experiment"].strip():
        failures.append("next_experiment must be non-empty text")
    return failures


def run(*, endpoint: str, model: str, evaluation_path: Path, longform_path: Path, output_root: Path, timeout_s: int) -> dict[str, Any]:
    ensure_loopback(endpoint)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    longform = json.loads(longform_path.read_text(encoding="utf-8"))
    packet = build_evidence_packet(evaluation, longform)
    system, user = prompts(packet)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": response_format(),
        "temperature": 0,
        "max_tokens": 1200,
    }
    request = Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    started_at = utc_now()
    started = time.perf_counter()
    with build_opener(ProxyHandler({}), RejectRedirects()).open(request, timeout=timeout_s) as response:
        response_json = json.loads(response.read().decode("utf-8"))
    latency_ms = round((time.perf_counter() - started) * 1000)
    raw_text = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
    decision = parse_response(raw_text)
    failures = validate_decision(decision, packet)

    request_record = {
        "schema_version": SCHEMA_VERSION,
        "endpoint": endpoint,
        "model_requested": model,
        "evidence_packet": packet,
        "system_prompt": system,
        "user_prompt": user,
        "response_format": response_format(),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not failures else "fail",
        "decision": decision,
        "deterministic_failures": failures,
    }
    write_json_atomic(output_root / "request.json", request_record)
    write_json_atomic(output_root / "raw-response.json", response_json)
    write_json_atomic(output_root / "result.json", result)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "status": result["status"],
        "endpoint": endpoint,
        "model_requested": model,
        "model_reported": response_json.get("model"),
        "latency_ms": latency_ms,
        "source_files": {
            str(evaluation_path.relative_to(ROOT)): sha256_file(evaluation_path),
            str(longform_path.relative_to(ROOT)): sha256_file(longform_path),
        },
        "request_sha256": sha256_file(output_root / "request.json"),
        "raw_response_sha256": sha256_file(output_root / "raw-response.json"),
        "result_sha256": sha256_file(output_root / "result.json"),
        "evidence_packet_sha256": canonical_sha256(packet),
        "deterministic_failures": failures,
        "boundary": "This tests local text reasoning over sealed aggregate evidence; it does not test video perception or reproduce the official SoccerMaster checkpoint.",
    }
    write_json_atomic(output_root / "run-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--longform", type=Path, default=DEFAULT_LONGFORM)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-s", type=int, default=90)
    args = parser.parse_args()
    receipt = run(
        endpoint=args.endpoint,
        model=args.model,
        evaluation_path=args.evaluation.resolve(),
        longform_path=args.longform.resolve(),
        output_root=args.output_root.resolve(),
        timeout_s=args.timeout_s,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
