"""Deterministic terminal-outcome accounting; an unreviewed prototype contract.

Run with --manifest frozen.json --records outcomes.json[l] [--output report.json].
No model, network, media decoding, or changes to existing scorers are involved.

The caller's evaluation manifest has schema ``playground-evaluation-manifest/v1``,
a boolean ``synthetic``, ``methods`` (method_id/model_revision), ``requests``, and
optional ``judgments``. Each request freezes REQUEST_FIELDS below, plus an
annotation_sha256 when human_answerability is resolved (null otherwise).
Each supplied judgment freezes request_id, method_id, prediction_sha256,
annotation_sha256, judgment_origin="independent_annotation", and JUDGMENT_FIELDS.
Its annotation hash must equal the resolved request's frozen annotation bundle.
Judgments are separate caller-supplied evaluation evidence; they are not model
outputs. This evaluation manifest is frozen before accounting, not asserted to
be the experiment's pre-inference preregistration. input_manifest_sha256 denotes
the separately frozen model-input manifest, avoiding a circular file hash.

Every record is one final outcome and supplies REQUEST_FIELDS, method_id,
model_revision, synthetic, prediction_sha256, terminal_status, failure_reason,
no_output, answered, and JUDGMENT_FIELDS. Input attempt logs are not rewritten;
this validator cannot establish that an upstream attempt history is complete.

Hashes are checked for syntax and equality to the caller's manifest. This does
not verify source/prediction bytes, actual human independence, rights, or frozen
timing. All returned arithmetic is descriptive; scientific_validation is false.
Synthetic inputs must declare synthetic=true in the manifest and every record.
Design source: research/fixtures/evaluation-outcome-contract-v1.json (unreviewed).
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


MANIFEST_SCHEMA = "playground-evaluation-manifest/v1"
REPORT_SCHEMA = "playground-evaluation-outcomes/v1"
REQUEST_FIELDS = (
    "request_id", "original_match_id", "source_asset_sha256", "split_id",
    "input_manifest_sha256", "human_answerability", "endpoint_eligible",
    "exclusion_reason", "field_evidence_required",
)
CORRECTNESS_FIELDS = (
    "answer_correct", "temporal_grounding_correct", "field_grounding_correct",
)
JUDGMENT_FIELDS = (*CORRECTNESS_FIELDS, "field_calibration_valid")
FAILURES = {"timeout", "malformed", "validation_failed"}
STATUSES = {"answered", "abstained", *FAILURES}


class OutcomeValidationError(ValueError):
    """Input is inconsistent with the frozen accounting contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OutcomeValidationError(message)


def stable_id(value: Any, field: str) -> None:
    require(isinstance(value, str) and bool(value.strip()) and value == value.strip(),
            f"{field}: nonempty stable string required")


def exact_hash(value: Any, field: str) -> None:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"{field}: exact lowercase SHA-256 required")


def boolean(value: Any, field: str, *, nullable: bool = False) -> None:
    require(type(value) is bool or (nullable and value is None),
            f"{field}: {'boolean or null' if nullable else 'boolean'} required")


def required(row: Any, fields: tuple[str, ...], label: str) -> None:
    require(isinstance(row, dict), f"{label}: object required")
    for field in fields:
        require(field in row, f"{label}: missing {field}")


def _manifest(manifest: Any) -> tuple[dict, dict, dict]:
    required(manifest, ("schema", "synthetic", "requests", "methods"), "manifest")
    require(manifest["schema"] == MANIFEST_SCHEMA, "unknown manifest schema")
    boolean(manifest["synthetic"], "manifest.synthetic")
    for name in ("requests", "methods"):
        require(isinstance(manifest[name], list) and bool(manifest[name]), f"{name}: nonempty list required")
    requests, methods, judgments = {}, {}, {}
    match_splits, asset_matches = {}, {}
    for request in manifest["requests"]:
        required(request, (*REQUEST_FIELDS, "annotation_sha256"), "manifest request")
        for field in ("request_id", "original_match_id", "split_id"):
            stable_id(request[field], field)
        for field in ("source_asset_sha256", "input_manifest_sha256"):
            exact_hash(request[field], field)
        boolean(request["endpoint_eligible"], "endpoint_eligible")
        boolean(request["field_evidence_required"], "field_evidence_required")
        require(request["human_answerability"] in ("answerable", "unanswerable", "unresolved"),
                "invalid human_answerability")
        if request["human_answerability"] == "unresolved":
            require(request["annotation_sha256"] is None, "unresolved answerability must not claim an annotation hash")
        else:
            exact_hash(request["annotation_sha256"], "annotation_sha256")
        if request["endpoint_eligible"]:
            require(request["exclusion_reason"] is None, "eligible request cannot have an exclusion reason")
        else:
            stable_id(request["exclusion_reason"], "exclusion_reason")
        rid, match, split = request["request_id"], request["original_match_id"], request["split_id"]
        require(rid not in requests, f"duplicate manifest request: {rid}")
        require(match not in match_splits or match_splits[match] == split,
                "original match crosses frozen splits")
        asset = request["source_asset_sha256"]
        require(asset not in asset_matches or asset_matches[asset] == match,
                "one source asset assigned to multiple original matches")
        match_splits[match], asset_matches[asset], requests[rid] = split, match, request
    for method in manifest["methods"]:
        required(method, ("method_id", "model_revision"), "method")
        for field in ("method_id", "model_revision"):
            stable_id(method[field], field)
        require(method["method_id"] not in methods, "duplicate method_id")
        methods[method["method_id"]] = method
    require(isinstance(manifest.get("judgments", []), list), "judgments: list required")
    for judgment in manifest.get("judgments", []):
        required(judgment, ("request_id", "method_id", "prediction_sha256", "annotation_sha256",
                            "judgment_origin", *JUDGMENT_FIELDS), "judgment")
        stable_id(judgment["request_id"], "judgment.request_id")
        stable_id(judgment["method_id"], "judgment.method_id")
        key = (judgment["request_id"], judgment["method_id"])
        require(key[0] in requests and key[1] in methods, "judgment outside requested arms")
        require(key not in judgments, "duplicate frozen judgment")
        require(judgment["judgment_origin"] == "independent_annotation", "independent judgment origin required")
        exact_hash(judgment["prediction_sha256"], "judgment.prediction_sha256")
        exact_hash(judgment["annotation_sha256"], "judgment.annotation_sha256")
        require(requests[key[0]]["human_answerability"] != "unresolved",
                "unresolved request cannot have a frozen judgment")
        require(judgment["annotation_sha256"] == requests[key[0]]["annotation_sha256"],
                "judgment annotation hash differs from frozen request annotation bundle")
        for field in JUDGMENT_FIELDS:
            boolean(judgment[field], field, nullable=True)
        judgments[key] = judgment
    return requests, methods, judgments


def validate_outcomes(manifest: Any, records: Any) -> list[dict]:
    """Reject invalid rows or incomplete arms; return the same unmodified rows."""
    requests, methods, judgments = _manifest(manifest)
    require(isinstance(records, list), "outcomes: list required")
    expected = {(request, method) for request in requests for method in methods}
    seen = set()
    for row in records:
        required(row, (*REQUEST_FIELDS, "method_id", "model_revision", "synthetic", "prediction_sha256",
                       "terminal_status", "failure_reason", "no_output", "answered", *JUDGMENT_FIELDS), "outcome")
        stable_id(row["request_id"], "request_id")
        stable_id(row["method_id"], "method_id")
        key = row["request_id"], row["method_id"]
        require(key in expected, "outcome outside frozen request/arm manifest")
        require(key not in seen, f"duplicate terminal outcome: {key}")
        seen.add(key)
        for field in REQUEST_FIELDS:
            require(type(row[field]) is type(requests[key[0]][field]) and row[field] == requests[key[0]][field],
                    f"{field}: differs from frozen request manifest")
        require(row["model_revision"] == methods[key[1]]["model_revision"], "model_revision differs from frozen arm")
        require(type(row["synthetic"]) is bool and row["synthetic"] == manifest["synthetic"], "synthetic marker mismatch")
        require(not {"primary_success", "coverage", "selective_risk", "primary_accuracy"}.intersection(row),
                "derived metrics/success flags must not be supplied by outcome rows")
        status = row["terminal_status"]
        require(isinstance(status, str) and status in STATUSES, "unknown terminal_status")
        boolean(row["answered"], "answered")
        require(row["answered"] == (status == "answered"), "answered inconsistent with terminal_status")
        boolean(row["no_output"], "no_output")
        if status in FAILURES:
            stable_id(row["failure_reason"], "failure_reason")
        else:
            require(row["failure_reason"] is None, "ordinary answer/abstention must have null failure_reason")
        if row["prediction_sha256"] is None:
            require(status in {"timeout", "validation_failed"} and row["no_output"],
                    "null prediction hash requires explicit no-output failure")
        else:
            exact_hash(row["prediction_sha256"], "prediction_sha256")
            require(row["no_output"] is False, "retained prediction conflicts with no_output")
        for field in JUDGMENT_FIELDS:
            boolean(row[field], field, nullable=True)
        if status != "answered" or row["human_answerability"] == "unresolved" or not row["endpoint_eligible"]:
            require(all(row[field] is None for field in JUDGMENT_FIELDS),
                    "nonanswer, unresolved, or excluded outcome must not claim correctness")
        if not row["field_evidence_required"]:
            require(row["field_grounding_correct"] is None and row["field_calibration_valid"] is None,
                    "inapplicable field evidence must remain null")
        if row["field_calibration_valid"] is not True:
            require(row["field_grounding_correct"] is None, "field correctness requires valid calibration")
        if row["human_answerability"] == "unanswerable":
            require(all(row[field] is not True for field in CORRECTNESS_FIELDS),
                    "human-unanswerable request cannot claim correct answer/evidence")
        judgment = judgments.get(key)
        if judgment is not None:
            require(judgment["prediction_sha256"] == row["prediction_sha256"], "judgment prediction hash mismatch")
            require(all(row[field] is judgment[field] for field in JUDGMENT_FIELDS), "outcome differs from independent judgment")
        else:
            require(all(row[field] is None for field in JUDGMENT_FIELDS),
                    "correctness requires a separate frozen independent judgment")
    require(seen == expected, f"missing terminal outcomes: {sorted(expected - seen)}")
    return records


def _joint_success(row: dict) -> bool:
    return (row["answered"] and row["human_answerability"] == "answerable"
            and row["answer_correct"] is True and row["temporal_grounding_correct"] is True
            and (not row["field_evidence_required"] or
                 (row["field_calibration_valid"] is True and row["field_grounding_correct"] is True)))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _cohort(rows: list[dict]) -> dict:
    eligible = [row for row in rows if row["endpoint_eligible"]]
    primary = [row for row in eligible if row["human_answerability"] == "answerable"]
    answered = [row for row in eligible if row["answered"]]
    blockers = []
    if any(row["human_answerability"] == "unresolved" for row in rows):
        blockers.append("unresolved_human_answerability")
    for row in answered:
        if row["human_answerability"] != "answerable":
            continue  # Resolved unanswerable requests cannot support an answer.
        if row["answer_correct"] is None or row["temporal_grounding_correct"] is None:
            blockers.append("missing_independent_correctness")
        if row["field_evidence_required"] and (row["field_calibration_valid"] is None or
                (row["field_calibration_valid"] and row["field_grounding_correct"] is None)):
            blockers.append("unresolved_field_evidence")
    status_counts = Counter(row["terminal_status"] for row in rows)
    counts = {
        "requested": len(rows), "eligible": len(eligible), "excluded": len(rows) - len(eligible),
        "human_answerable": sum(row["human_answerability"] == "answerable" for row in rows),
        "human_unanswerable": sum(row["human_answerability"] == "unanswerable" for row in rows),
        "human_unresolved": sum(row["human_answerability"] == "unresolved" for row in rows),
        "primary_denominator": len(primary), "eligible_answered": len(answered),
        "answered": status_counts["answered"], "abstained": status_counts["abstained"],
        "failures": sum(status_counts[status] for status in FAILURES),
        "terminal_statuses": {status: status_counts[status] for status in sorted(STATUSES)},
        "exclusion_reasons": dict(sorted(Counter(row["exclusion_reason"] for row in rows if not row["endpoint_eligible"]).items())),
        "failure_reasons": dict(sorted(Counter(row["failure_reason"] for row in rows if row["terminal_status"] in FAILURES).items())),
        "original_matches_requested": len({row["original_match_id"] for row in rows}),
        "original_matches_eligible": len({row["original_match_id"] for row in eligible}),
        "original_matches_primary": len({row["original_match_id"] for row in primary}),
    }
    metrics = None
    if not blockers:
        successes = sum(_joint_success(row) for row in primary)
        answer_errors = sum(row["human_answerability"] == "unanswerable" or row["answer_correct"] is not True for row in answered)
        joint_errors = sum(not _joint_success(row) for row in answered)
        metrics = {"primary_successes": successes, "primary_joint_success_rate": _ratio(successes, len(primary)),
                   "coverage": _ratio(len(answered), len(eligible)), "answer_errors": answer_errors,
                   "joint_errors": joint_errors, "answer_selective_risk": _ratio(answer_errors, len(answered)),
                   "joint_selective_risk": _ratio(joint_errors, len(answered))}
    return {"method_id": rows[0]["method_id"], "split_id": rows[0]["split_id"],
            "cohort_definition": "All frozen requests for this method/split; coverage/risk use endpoint-eligible requests, including resolved human-unanswerable requests. Primary uses eligible human-answerable requests.",
            "counts": counts, "scoring_ready": not blockers, "scoring_blockers": sorted(set(blockers)), "metrics": metrics}


def evaluate_outcomes(manifest: Any, records: Any) -> dict:
    rows = validate_outcomes(manifest, records)
    keys = sorted({(row["method_id"], row["split_id"]) for row in rows})
    return {"schema": REPORT_SCHEMA, "valid": True, "synthetic": manifest["synthetic"],
            "scientific_validation": False, "source_bytes_verified": False, "annotator_independence_verified": False,
            "metrics_kind": "synthetic_test_only" if manifest["synthetic"] else "caller_evidence_descriptive_accounting",
            "requested_pairs": len(manifest["requests"]) * len(manifest["methods"]), "observed_final_rows": len(rows),
            "cohorts": [_cohort([row for row in rows if (row["method_id"], row["split_id"]) == key]) for key in keys]}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise OutcomeValidationError(f"non-finite JSON value: {value}")
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject_constant)


def _failure_report(error: Exception, manifest: Any = None, records: Any = None) -> dict:
    requested_pairs = None
    try:
        requests, methods, _ = _manifest(manifest)
        requested_pairs = len(requests) * len(methods)
    except OutcomeValidationError:
        pass
    return {"schema": REPORT_SCHEMA, "valid": False, "scientific_validation": False,
            "synthetic": manifest.get("synthetic") if isinstance(manifest, dict) and type(manifest.get("synthetic")) is bool else None,
            "requested_pairs": requested_pairs,
            "observed_final_rows": len(records) if isinstance(records, list) else None,
            "metrics": None, "error": str(error)}


def _write_report(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    manifest, records, safe_output, exit_code = None, None, False, 0
    try:
        if args.output:
            for input_path in (args.manifest, args.records):
                require(args.output.resolve() != input_path.resolve() and
                        not (args.output.exists() and input_path.exists() and args.output.samefile(input_path)),
                        "output must not overwrite an input")
        safe_output = True
        manifest_bytes = args.manifest.read_bytes()
        manifest = _json(manifest_bytes.decode("utf-8-sig"))
        record_bytes = args.records.read_bytes()
        text = record_bytes.decode("utf-8-sig")
        records = [_json(line) for line in text.splitlines() if line.strip()] if args.records.suffix.lower() == ".jsonl" else _json(text)
        report = evaluate_outcomes(manifest, records)
        report["evaluation_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        report["outcome_file_sha256"] = hashlib.sha256(record_bytes).hexdigest()
    except (ValueError, OSError, UnicodeError) as error:
        report, exit_code = _failure_report(error, manifest, records), 1
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output and safe_output:
        try:
            _write_report(args.output, rendered)
        except OSError as error:
            rendered = json.dumps(_failure_report(error, manifest, records), sort_keys=True) + "\n"
            exit_code = 1
    sys.stdout.write(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
