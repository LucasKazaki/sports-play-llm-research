"""Offline descriptive scoring of hash-bound hosted-video event-card runs.

Consumes only sealed primary outputs and posthoc labels. It performs no inference,
opens no source media, and never rewrites labels or primary outputs. This is not
proof of annotation independence or scientific validity.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from hosted_video_benchmark import (
    BenchmarkGateError, SCORING_CONTRACT, _strict_json, _verify_existing_primary_seal,
    _verify_existing_posthoc, _load_resumable_result, sha256_file,
    validate_event_report, write_json_atomic, require_private_output,
)

LABEL_SCHEMA = "playground-hosted-video-labels-v1"
REPORT_SCHEMA = "playground-hosted-video-scoring-v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchmarkGateError(message)


def number(value: Any, label: str) -> float:
    require(not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value), label + " must be finite")
    return float(value)


def validate_labels(raw: Any, *, clip_id: str, input_sha256: str, duration_s: float) -> dict:
    require(isinstance(raw, dict), "labels must be an object")
    require(set(raw) == {"schema_version", "clip_id", "source_sha256", "duration_s",
                        "time_unit", "annotation_origin", "events"}, "label keys differ from contract")
    require(raw["schema_version"] == LABEL_SCHEMA, "unsupported label schema")
    require(raw["clip_id"] == clip_id, "label clip mismatch")
    require(raw["source_sha256"] == input_sha256, "label source hash mismatch")
    require(raw["time_unit"] == "seconds", "label time_unit must be seconds")
    require(number(raw["duration_s"], "label duration") == duration_s, "label duration mismatch")
    require(raw["annotation_origin"] in {"synthetic_fixture", "independent_annotation"},
            "label annotation origin is unsupported")
    require(isinstance(raw["events"], list) and len(raw["events"]) <= 100, "invalid label events")
    seen = set()
    for event in raw["events"]:
        require(isinstance(event, dict) and set(event) == {
            "label_id", "event_type", "start_s", "peak_s", "end_s"}, "invalid label event keys")
        identity = event["label_id"]
        require(isinstance(identity, str) and bool(identity.strip()) and identity not in seen,
                "label ids must be nonempty and unique")
        seen.add(identity)
        require(isinstance(event["event_type"], str) and bool(event["event_type"].strip())
                and event["event_type"] == event["event_type"].strip(), "invalid label event type")
        start, peak, end = (number(event[key], key) for key in ("start_s", "peak_s", "end_s"))
        require(0 <= start <= peak <= end <= duration_s and start < end,
                "label intervals must be positive and within source duration")
    return raw


def interval_iou(left: dict, right: dict) -> float:
    overlap = max(0.0, min(left["end_s"], right["end_s"]) - max(left["start_s"], right["start_s"]))
    union = max(left["end_s"], right["end_s"]) - min(left["start_s"], right["start_s"])
    return overlap / union if union else 0.0


def match_events(predictions: list[dict], labels: list[dict]) -> list[dict]:
    """Maximum-cardinality bipartite matching; stable IDs resolve equal choices."""
    pred = sorted(predictions, key=lambda item: item["event_id"])
    gold = sorted(labels, key=lambda item: item["label_id"])
    edges = {
        p: [g for g in range(len(gold))
            if pred[p]["event_type"] == gold[g]["event_type"]
            and interval_iou(pred[p], gold[g]) >= SCORING_CONTRACT["minimum_interval_iou"]
            and abs(pred[p]["peak_s"] - gold[g]["peak_s"]) <= SCORING_CONTRACT["maximum_peak_error_s"]]
        for p in range(len(pred))
    }
    owners: dict[int, int] = {}
    def augment(p: int, seen: set[int]) -> bool:
        for g in edges[p]:
            if g in seen:
                continue
            seen.add(g)
            if g not in owners or augment(owners[g], seen):
                owners[g] = p
                return True
        return False
    for p in range(len(pred)):
        augment(p, set())
    return [{
        "event_id": pred[p]["event_id"], "label_id": gold[g]["label_id"],
        "interval_iou": interval_iou(pred[p], gold[g]),
        "peak_error_s": abs(pred[p]["peak_s"] - gold[g]["peak_s"]),
    } for g, p in sorted(owners.items())]


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir).resolve()
    run_path = run_dir / "run-manifest.json"
    run = _strict_json(run_path.read_text(encoding="utf-8"))
    seal = _verify_existing_primary_seal(run_dir, run["run_fingerprint"])
    require(seal is not None, "scoring requires a primary seal")
    require(run.get("primary_seal_sha256") == sha256_file(run_dir / "primary-seal.json"),
            "run primary seal binding changed")
    clip_order = run.get("clip_order")
    require(isinstance(clip_order, list) and len(clip_order) == len(set(clip_order))
            and 1 <= len(clip_order) <= 15, "invalid run clip order")
    require(set(clip_order) == {item["clip_id"] for item in seal["files"]},
            "seal clip membership differs from requested clips")
    if run.get("protocol_phase") == "benchmark":
        require(len(clip_order) >= 6, "benchmark phase requires at least six clips")
    audit = _verify_existing_posthoc(out_dir=run_dir, run_manifest=run, primary_seal=seal)
    audit_by_clip = {}
    if audit is not None:
        for row in audit["records"]:
            require(row["clip_id"] not in audit_by_clip, "duplicate posthoc clip")
            audit_by_clip[row["clip_id"]] = row
        require(set(audit_by_clip) == set(clip_order), "posthoc clip membership mismatch")
    rows = []
    saved = []
    for clip_id in clip_order:
        clip_dir = run_dir / clip_id
        result = _strict_json((clip_dir / "result.json").read_text(encoding="utf-8"))
        request = _strict_json((clip_dir / "request-receipt.json").read_text(encoding="utf-8"))
        require(result["clip_id"] == request["clip_id"] == clip_id, "primary clip mismatch")
        require(result["input_sha256"] == request["input_sha256"], "primary input hash mismatch")
        require(result["request_receipt_sha256"] == sha256_file(clip_dir / "request-receipt.json"),
                "primary request binding mismatch")
        _load_resumable_result(clip_dir, result["input_fingerprint"])
        saved.append(result)
        row = {"clip_id": clip_id, "status": result["status"], "latency_ms": result["latency_ms"],
               "labels_eligible": False, "annotation_origin": None, "abstained": None,
               "predicted_events": None, "gold_events": None, "true_positive": None,
               "false_positive": None, "false_negative": None, "exact_event_set": None,
               "matches": [], "failure_taxonomy": []}
        if result["status"] != "complete":
            row["failure_taxonomy"].append("provider_failure" if result["status"] == "provider_failed"
                                            else "malformed_or_invalid_report")
        report = None
        duration = number(request["media_probe"]["duration_s"], "source duration")
        if result["status"] == "complete":
            report = validate_event_report(
                _strict_json((clip_dir / "event-report.json").read_text(encoding="utf-8")),
                clip_id=clip_id, duration_s=duration)
            row["abstained"] = report["report_abstained"] or (bool(report["events"]) and all(e["abstain"] for e in report["events"]))
            if row["abstained"]:
                row["failure_taxonomy"].append("abstention")
        posthoc = audit_by_clip.get(clip_id)
        evidence = posthoc["evidence"]["held_out_labels"] if posthoc else None
        if evidence is None:
            row["failure_taxonomy"].append("labels_unavailable")
        elif not request.get("held_out_labels_sha256"):
            row["failure_taxonomy"].append("labels_not_frozen_before_inference")
        else:
            require(posthoc["primary_result_sha256"] == sha256_file(clip_dir / "result.json"),
                    "posthoc result binding mismatch")
            require(evidence["sha256"] == evidence.get("frozen_sha256")
                    == request["held_out_labels_sha256"], "label freeze binding mismatch")
            require(request.get("scoring_contract") == SCORING_CONTRACT,
                    "scoring contract differs from pre-inference receipt")
            labels = validate_labels(evidence["content"], clip_id=clip_id,
                                     input_sha256=result["input_sha256"], duration_s=duration)
            row["labels_eligible"] = True
            row["annotation_origin"] = labels["annotation_origin"]
            if run["provider"] == "local_fixture":
                require(labels["annotation_origin"] == "synthetic_fixture",
                        "fixture provider cannot claim independent semantic evaluation")
            predictions = [e for e in report["events"] if not e["abstain"]] if report else []
            gold = labels["events"]
            matches = match_events(predictions, gold)
            tp = len(matches)
            row.update(predicted_events=len(predictions), gold_events=len(gold), true_positive=tp,
                       false_positive=len(predictions)-tp, false_negative=len(gold)-tp, matches=matches)
            # A valid abstention is distinct from a verified empty/background event set.
            row["exact_event_set"] = (tp == len(predictions) == len(gold)) if report and not row["abstained"] else False
            if row["false_positive"]:
                row["failure_taxonomy"].append("unmatched_predicted_event")
            if row["false_negative"]:
                row["failure_taxonomy"].append("missed_labeled_event")
            paired = {m["event_id"] for m in matches}
            if any(p["event_id"] not in paired and any(p["event_type"] == g["event_type"] for g in gold)
                   for p in predictions):
                row["failure_taxonomy"].append("same_type_unmatched_temporal_or_duplicate")
        rows.append(row)
    require(run.get("clips") == saved, "run summaries differ from sealed clip results")
    eligible = [row for row in rows if row["labels_eligible"]]
    origins = sorted({row["annotation_origin"] for row in eligible})
    # Never mix synthetic and human-label cohorts into one number.
    require(len(origins) <= 1, "mixed annotation origins require separate runs")
    tp = sum(row["true_positive"] for row in eligible)
    fp = sum(row["false_positive"] for row in eligible)
    fn = sum(row["false_negative"] for row in eligible)
    complete = sum(row["status"] == "complete" for row in rows)
    abstained = sum(row["abstained"] is True for row in rows)
    exact = sum(row["exact_event_set"] is True for row in rows)
    return {
        "schema_version": REPORT_SCHEMA, "scorer_sha256": sha256_file(Path(__file__)),
        "run_manifest_sha256": sha256_file(run_path),
        "primary_seal_sha256": sha256_file(run_dir / "primary-seal.json"),
        "posthoc_audit_sha256": sha256_file(run_dir / "posthoc-audit.json") if audit else None,
        "scoring_contract": SCORING_CONTRACT,
        "truth_boundary": "SYSTEMS GO / SEMANTIC NO-GO", "scientific_validation": False,
        "scope": "descriptive event-type and time matching; exact ontology mapping only",
        "annotation_origin": origins[0] if origins else None,
        "annotation_independence_verified": False,
        "study_size": {"minimum": 6, "target": [10, 15], "observed": len(rows),
                       "meets_minimum": len(rows) >= 6, "meets_target": 10 <= len(rows) <= 15},
        "counts": {"requested": len(rows), "complete": complete, "failed": len(rows)-complete,
                   "abstained": abstained, "labels_eligible": len(eligible),
                   "labels_ineligible": len(rows)-len(eligible), "exact_event_set": exact,
                   "true_positive": tp, "false_positive": fp, "false_negative": fn},
        "metrics": {"schema_valid_rate_all_requests": ratio(complete, len(rows)),
                    "nonabstained_coverage_all_requests": ratio(complete-abstained, len(rows)),
                    "event_precision_labeled_cohort": ratio(tp, tp+fp),
                    "event_recall_labeled_cohort": ratio(tp, tp+fn),
                    "event_f1_labeled_cohort": ratio(2*tp, 2*tp+fp+fn),
                    "exact_event_set_rate_labeled_cohort": ratio(exact, len(eligible)),
                    "known_exact_success_rate_all_requests": ratio(exact, len(rows))},
        "not_scored": ["unsupported detail", "replay correctness", "identity correctness",
                       "field coordinates", "retrieval relevance", "calibration", "coach usefulness"],
        "limits": ["No population estimate from 6–15 clips.", "Commentary is never ground truth.",
                   "Unmatched predictions are not automatically hallucinations; annotation completeness needs review.",
                   "Missing labels stay explicit and do not become semantic ground truth."],
        "clips": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require_private_output(output.parent)
    require(not output.exists(), "scoring output already exists; use a fresh output path")
    report = score_run(args.run_dir)
    write_json_atomic(output, report)
    print(json.dumps({"output": str(output), "counts": report["counts"],
                      "truth_boundary": report["truth_boundary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
