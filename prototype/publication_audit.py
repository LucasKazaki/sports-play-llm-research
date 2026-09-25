"""Offline, bounded audit of retained soccer evidence (no model calls or scheduler).

This verifies the named receipts and recomputes their counts, not private video,
human independence, global literature novelty, or publication suitability.
Unknown evidence is never treated as a pass. Run via the project executor:
python -m prototype.publication_audit --output artifacts/publication-readiness-20260908/audit.json
Exit 0 means the audit ran; --require-ready returns 2 unless evidence is ready.
The stable evidence_fingerprint lets the runtime suppress unchanged notifications.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re


SOURCES = {
    "preflight": "artifacts/soccermaster-evidence-gated-v1/preflight-receipt.json",
    "protocol": "artifacts/soccermaster-evidence-gated-v1/preregistration.json",
    "metrics": "artifacts/soccermaster-longform-v1/report-metrics.json",
    "annotation": "artifacts/soccermaster-longform-v1/annotation-evaluation.json",
    "spot_checks": "artifacts/soccermaster-longform-v1/spot-check-adjudication.json",
    "verification": "artifacts/soccermaster-longform-v1/verification-receipt.json",
    "accounting": "artifacts/evaluation-outcomes-20260906/synthetic-accounting-report.json",
    "experiment": "artifacts/project-capability-20260908/local-model-experiment-v1/results.json",
    "experiment_manifest": "artifacts/project-capability-20260908/local-model-experiment-v1/manifest.json",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protocol_sha256(value: dict) -> str:
    # The protocol producer hashes canonical JSON, not pretty-printed file bytes.
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def scoped_path(root: Path, relative: str) -> Path:
    """Reject absolute, parent and junction/symlink escapes before reading."""
    windows = PureWindowsPath(relative)
    if windows.drive or windows.root or ".." in windows.parts:
        raise ValueError("unscoped evidence path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("evidence path escapes root")
    return path


def verify_manifest(root: Path, entries: dict) -> dict:
    if not isinstance(entries, dict) or not entries:
        return {"verified": 0, "expected": 0, "errors": ["empty or invalid manifest"]}
    errors, verified = [], 0
    for relative, expected in entries.items():
        try:
            actual = sha256(scoped_path(root, relative).read_bytes())
            if actual != expected:
                errors.append(f"hash mismatch: {relative}")
            else:
                verified += 1
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"unreadable or unscoped: {relative} ({type(error).__name__})")
    return {"verified": verified, "expected": len(entries), "errors": errors}


def audit(root: Path) -> dict:
    data, sources, errors = {}, {}, []
    for name, relative in SOURCES.items():
        try:
            raw = scoped_path(root, relative).read_bytes()
            value = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("receipt must be an object")
            data[name] = value
            sources[name] = {"path": relative, "sha256": sha256(raw), "bytes": len(raw)}
        except (OSError, ValueError, UnicodeError) as error:
            sources[name] = {"path": relative, "error": type(error).__name__}
            errors.append(f"missing or invalid source: {name}")

    checks = []
    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            errors.append(name)

    metrics = data.get("metrics", {})
    annotation = data.get("annotation", {})
    spots = data.get("spot_checks", {})
    verification = data.get("verification", {})
    preflight = data.get("preflight", {})
    protocol = data.get("protocol", {})
    accounting = data.get("accounting", {})
    experiment = data.get("experiment", {})
    n = metrics.get("window_denominator")
    count_fields = ("window_denominator", "dense_window_denominator", "stress_window_denominator",
                    "valid_response_count", "failure_count")
    check("window_accounting", all(type(metrics.get(key)) is int and metrics[key] >= 0 for key in count_fields)
          and n > 0
          and n == metrics.get("dense_window_denominator", 0) + metrics.get("stress_window_denominator", 0)
          and n == metrics.get("valid_response_count", 0) + metrics.get("failure_count", 0),
          "requested windows = dense + stress = valid responses + failures")
    rows = spots.get("rows", [])
    valid_spot_rows = isinstance(rows, list) and all(isinstance(row, dict) and
                          isinstance(row.get("overall_judgment"), str) for row in rows)
    if not valid_spot_rows:
        rows = []
    observed_counts = Counter(row.get("overall_judgment") for row in rows if isinstance(row, dict))
    expected_counts = spots.get("judgment_counts", {})
    check("spot_check_counts", valid_spot_rows and bool(rows) and isinstance(expected_counts, dict)
          and all(type(value) is int and value >= 0 for value in expected_counts.values())
          and dict(observed_counts) == {key: value for key, value in expected_counts.items() if value},
          "recounted saved row judgments; no new human or visual adjudication")
    seal = annotation.get("visual_prediction_seal_root_hash")
    check("cross_receipt_seal", isinstance(seal, str) and re.fullmatch(r"[0-9a-f]{64}", seal) is not None
          and seal == spots.get("prediction_seal_root_hash") == verification.get("visual_prediction_seal_root_hash"),
          "three receipts bind the same seal; private sealed files are not rehashed here")
    protocol_hash = protocol_sha256(protocol) if "protocol" in data else None
    check("preflight_protocol_binding", protocol_hash is not None and protocol_hash == preflight.get("protocol_sha256"),
          "current protocol canonical JSON matches retained preflight hash; file byte hash also retained")

    manifest = data.get("experiment_manifest", {})
    frozen = verify_manifest(root / Path(SOURCES["experiment_manifest"]).parent, manifest.get("files"))
    check("frozen_local_experiment_bytes", not frozen["errors"], frozen)
    result_key = Path(SOURCES["experiment"]).relative_to(Path(SOURCES["experiment_manifest"]).parent).as_posix()
    check("experiment_result_manifest_coverage", isinstance(manifest.get("files"), dict)
          and result_key in manifest["files"] and "experiment" in data
          and manifest["files"][result_key] == sources["experiment"]["sha256"],
          "recounted results.json must be explicitly hash-bound by the frozen manifest")
    historical_sources = verify_manifest(root, manifest.get("source_sha256"))
    # Code may legitimately change after a frozen experiment; report drift, not tampering.
    arms = {}
    experiment_rows = experiment.get("rows", [])
    if isinstance(experiment_rows, list) and experiment_rows and all(isinstance(row, dict)
            and isinstance(row.get("arms"), dict) for row in experiment_rows):
        for arm in ("literal_baseline", "raw_model", "guarded_model_with_fallback"):
            values = [row["arms"][arm].get("matches_engineered_expectation")
                      if isinstance(row["arms"].get(arm), dict) else None for row in experiment_rows]
            check(f"complete_engineering_arm:{arm}", len(values) == len(experiment_rows)
                  and all(type(value) is bool for value in values), "all requested cases retained")
            arms[arm] = {"successes": sum(value is True for value in values),
                         "requested": len(experiment_rows), "empirical_soccer_accuracy": False}
    else:
        check("engineering_outcomes_present", False, "missing complete saved cases")

    blockers = []
    def block(code, evidence, next_action, owner="local_project_worker"):
        blockers.append({"code": code, "evidence": evidence, "next_action": next_action, "owner": owner})
    if errors:
        block("EVIDENCE_INTEGRITY", errors, "Resolve exact missing/hash/accounting errors before citing these receipts.")
    if not (preflight.get("heldout_binding_ready") is True and preflight.get("binding_contract_valid") is True
            and preflight.get("binding_is_synthetic") is False and preflight.get("private_binding_supplied") is True):
        block("FRESH_COHORT_NOT_BOUND", {key: preflight.get(key) for key in
              ("status", "heldout_binding_ready", "binding_contract_valid", "private_binding_supplied")},
              "Inspect existing authorized source/history inventories, build an original-match-disjoint binding, and record rights, exposure and privacy checks. Keep test labels sealed.")
    anonymization = spots.get("input_anonymization_audit")
    if not isinstance(anonymization, dict):
        anonymization = {}
    if anonymization.get("performance_claim_allowed") is not True:
        block("ANONYMIZATION_NOT_VALIDATED", anonymization.get("status"),
              "Validate identity masking on development media, including lower-third graphics, before freezing new inputs.")
    if metrics.get("performance_claim_allowed") is not True or metrics.get("detailed_claim_factuality_measured") is not True:
        block("SEMANTIC_VALIDATION_INCOMPLETE", {"valid_json": metrics.get("valid_response_count"),
              "requested": n, "visual_judgments": dict(observed_counts)},
              "Collect blinded independent human judgments of answers, temporal and pitch evidence; score failures and abstentions under a frozen equal-budget comparison.", "research_annotation_and_local_evaluation")
    if accounting.get("synthetic") is not False or accounting.get("scientific_validation") is not True:
        block("NO_CONFIRMATORY_ACCOUNTING_IN_AUDITED_PACKET",
              {"synthetic": accounting.get("synthetic"), "scientific_validation": accounting.get("scientific_validation")},
              "Bind real outcomes to the frozen model-input and independent annotation manifests; retain every requested method/window outcome.")
    block("INDEPENDENT_PUBLICATION_REVIEW_REQUIRED", "No reviewed manuscript or novelty verdict is an input to this bounded audit.",
          "Review the exact manuscript, primary-source novelty matrix, grouped uncertainty, ablations, data rights and candidate receipts through the existing Luna/Terra gates.", "independent_research_review")

    fingerprint_payload = {"sources": sources, "frozen": frozen, "historical_source_drift": historical_sources}
    return {
        "schema": "playground-publication-evidence-audit/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "needs_revision", "publication_ready": False, "promotion_authority": False,
        "audit_completed": True, "receipt_integrity_passed": not errors,
        "scope": "Exact named retained receipts only; other/newer packets require a new versioned inventory. Receipt integrity does not establish scientific validity.",
        "model_calls": 0, "network_calls": 0, "private_media_read": False,
        "evidence_fingerprint": sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()),
        "sources": sources, "checks": checks, "integrity_errors": errors,
        "historical_source_comparison": historical_sources,
        "historical_source_boundary": "Drift makes the original result historical; it does not invalidate unchanged frozen responses or prove a new model improvement.",
        "observations": {
            "schema_valid_responses": metrics.get("valid_response_count"), "requested_windows": n,
            "annotation_corroboration": {"supported": annotation.get("temporally_corroborated_annotation_count"),
                                       "denominator": annotation.get("mapped_visible_annotation_denominator")},
            "prediction_corroboration": {"supported": annotation.get("temporally_corroborated_prediction_count"),
                                       "denominator": annotation.get("mapped_vlm_prediction_denominator")},
            "corroboration_boundary": "Restricted non-one-to-one time/type matching; not event detection accuracy or detailed QA grounding.",
            "saved_visual_judgments": dict(observed_counts), "engineering_selection": arms,
            "planned_fresh_windows": (protocol["data_contract"].get("window_count")
                                      if isinstance(protocol.get("data_contract"), dict) else None),
        },
        "blockers": blockers,
        "runtime_handoff": "Run only when input evidence changes or a relevant repair needs verification. Retain native job identity. Compare evidence_fingerprint; do not schedule model calls to wait or announce unchanged blockers.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    report = audit(args.root.resolve())
    output = scoped_path(args.root.resolve(), str(args.output))
    if not output.is_relative_to((args.root.resolve() / "artifacts").resolve()):
        parser.error("output must be inside the project's artifacts directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    except OSError as error:
        parser.error(f"use a new output path; existing evidence is never overwritten ({type(error).__name__})")
    print(json.dumps({key: report[key] for key in ("status", "publication_ready", "receipt_integrity_passed", "evidence_fingerprint")}))
    return 2 if args.require_ready and not report["publication_ready"] else (0 if report["receipt_integrity_passed"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
