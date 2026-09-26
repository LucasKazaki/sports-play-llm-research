"""Run and score the frozen visual-only VLM prompt on a private SoccerNet clip manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freeze_visual_config import verify_frozen_config
from isolated_vlm_runtime import verify_live_runtime_receipt
from real_clip_vlm import (
    SAMPLER_VERSION,
    prompt,
    run,
    sha256_file,
    structured_response_format,
    uniform_sample_timestamps,
    write_json,
)


def require_private_output(path: Path) -> Path:
    resolved = path.resolve()
    parts = [part.lower() for part in resolved.parts]
    if not any(parts[index:index + 2] == ["data", "private"] for index in range(len(parts) - 1)):
        raise ValueError("raw VLM outputs and contact sheets must remain under data/private")
    return resolved


def safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def macro_f1(records: list[dict[str, str]]) -> float | None:
    labels = sorted({item["truth"] for item in records} | {item["prediction"] for item in records})
    if not labels:
        return None
    scores: list[float] = []
    for label in labels:
        tp = sum(item["truth"] == label and item["prediction"] == label for item in records)
        fp = sum(item["truth"] != label and item["prediction"] == label for item in records)
        fn = sum(item["truth"] == label and item["prediction"] != label for item in records)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def summarize(
    *, manifest: dict[str, Any], completed: list[dict[str, Any]], failures: list[dict[str, str]],
    model: str, manifest_path: Path, sample_count: int, sheets: int, max_tokens: int,
    frozen_config_receipt: dict[str, str] | None = None,
) -> dict[str, Any]:
    requested_ids = [item.get("clip_id") for item in manifest["clips"]]
    completed_ids = [item.get("clip_id") for item in completed]
    failure_ids = [item.get("clip_id") for item in failures]
    if any(not isinstance(value, str) or not value for value in requested_ids):
        raise ValueError("every requested clip must have a non-empty clip_id")
    if len(requested_ids) != len(set(requested_ids)):
        raise ValueError("requested clip_ids must be unique")
    if len(completed_ids) != len(set(completed_ids)) or len(failure_ids) != len(set(failure_ids)):
        raise ValueError("completed and failure clip_ids must each be unique")
    if set(completed_ids) & set(failure_ids):
        raise ValueError("completed and failure clip_ids must be disjoint")
    if set(completed_ids) | set(failure_ids) != set(requested_ids):
        raise ValueError("completed and failure clip_ids must account for the requested set exactly")
    requested = len(manifest["clips"])
    requested_eligible = sum(
        bool(item["ground_truth"]["single_label_eligible"]) for item in manifest["clips"]
    )
    eligible = [item for item in completed if item["single_label_eligible"]]
    paired = [{"truth": item["truth"], "prediction": item["prediction"]} for item in eligible]
    exact = sum(item["prediction"] == item["truth"] for item in eligible)
    allowed = sum(item["prediction"] in item["allowed_play_types"] for item in completed)
    latencies = [item["elapsed_ms"] for item in completed]
    confusion = Counter((item["truth"], item["prediction"]) for item in eligible)
    frozen_config_summary = {
        "enforced": frozen_config_receipt is not None,
        "schema_version": None if frozen_config_receipt is None else frozen_config_receipt["schema_version"],
        "sha256": None if frozen_config_receipt is None else frozen_config_receipt["sha256"],
    }
    if frozen_config_receipt is not None and frozen_config_receipt.get("runtime_receipt_sha256"):
        frozen_config_summary["runtime_receipt_sha256"] = frozen_config_receipt["runtime_receipt_sha256"]
    return {
        "schema_version": "playground-soccernet-vlm-pilot-summary-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": "SoccerNet",
        "split": manifest["split"],
        "model": model,
        "sampling": {"sample_count": sample_count, "contact_sheets": sheets, "max_tokens": max_tokens},
        "model_input": "sampled visual frames from physically silent event clips",
        "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
        "private_manifest_sha256": sha256_file(manifest_path),
        "frozen_config": frozen_config_summary,
        "counts": {
            "requested": requested,
            "completed": len(completed),
            "failed": len(failures),
            "single_label_eligible_requested": requested_eligible,
            "single_label_eligible_completed": len(eligible),
        },
        "metrics": {
            "primary_requested_set": {
                "single_label_exact_accuracy": safe_rate(exact, requested_eligible),
                "allowed_label_accuracy_all_clips": safe_rate(allowed, requested),
                "schema_valid_first_pass_rate": safe_rate(len(completed), requested),
            },
            "secondary_completed_only": {
                "single_label_exact_accuracy": safe_rate(exact, len(eligible)),
                "single_label_macro_f1": macro_f1(paired),
                "allowed_label_accuracy_all_clips": safe_rate(allowed, len(completed)),
                "median_latency_ms": statistics.median(latencies) if latencies else None,
            },
        },
        "confusion_completed_only": [
            {"truth": truth, "prediction": prediction, "count": count}
            for (truth, prediction), count in sorted(confusion.items())
        ],
        "clips": completed,
        "failures": failures,
        "performance_claim_allowed": False,
        "metric_policy": (
            "Failed or malformed first-pass responses count as incorrect in primary requested-set rates; "
            "completed-only metrics and confusion are secondary diagnostics."
        ),
        "interpretation": (
            "Descriptive one-match feasibility result only. It is not a benchmark estimate: clips were not independently "
            "adjudicated, the sample is tiny, and match-level uncertainty cannot be estimated."
        ),
    }


def run_batch(
    *, manifest_path: Path, private_out: Path, public_summary: Path,
    endpoint: str, model: str, sample_count: int, sheets: int, max_tokens: int,
    frozen_config_path: Path | None = None,
    runtime_receipt_path: Path | None = None,
) -> dict[str, Any]:
    private_out = require_private_output(private_out)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frozen_config_receipt = None
    if frozen_config_path is not None:
        frozen_config_receipt = verify_frozen_config(
            frozen_config_path=frozen_config_path,
            manifest_path=manifest_path,
            manifest=manifest,
            endpoint=endpoint,
            model=model,
            sample_count=sample_count,
            sheets=sheets,
            max_tokens=max_tokens,
            runtime_receipt_path=runtime_receipt_path,
        )
    elif runtime_receipt_path is not None:
        raise ValueError("a runtime receipt can be enforced only through a frozen v2 configuration")
    if frozen_config_receipt is not None and frozen_config_receipt.get("runtime_receipt_sha256"):
        if runtime_receipt_path is None:  # guarded above; keeps the type narrow below
            raise ValueError("frozen v2 configuration requires its runtime receipt")
        verify_live_runtime_receipt(
            receipt_path=runtime_receipt_path,
            model=model,
            endpoint=endpoint,
        )
    completed: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for clip in manifest["clips"]:
        if frozen_config_receipt is not None and frozen_config_receipt.get("runtime_receipt_sha256"):
            verify_live_runtime_receipt(
                receipt_path=runtime_receipt_path,  # type: ignore[arg-type]
                model=model,
                endpoint=endpoint,
            )
        clip_id = clip["clip_id"]
        clip_out = private_out / clip_id
        prediction_path = clip_out / "prediction.json"
        receipt_path = clip_out / "receipt.json"
        try:
            if prediction_path.is_file() and receipt_path.is_file():
                prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                sample_timestamps = uniform_sample_timestamps(
                    frame_count=int(clip["visual_only"]["frame_count"]),
                    fps=float(clip["visual_only"]["fps"]),
                    count=sample_count,
                )
                expected = {
                    "model_requested": model,
                    "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
                    "response_format_sha256": hashlib.sha256(
                        json.dumps(
                            structured_response_format(sample_timestamps),
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "sampler_version": SAMPLER_VERSION,
                    "clip_sha256": clip["visual_only"]["sha256"],
                    "source_manifest_sha256": sha256_file(manifest_path),
                    "sample_count": sample_count,
                    "sheets": sheets,
                    "max_tokens": max_tokens,
                    "endpoint": endpoint,
                }
                mismatches = [key for key, value in expected.items() if receipt.get(key) != value]
                request_path = clip_out / "request.json"
                input_manifest_path = clip_out / "input-manifest.json"
                if not request_path.is_file() or not input_manifest_path.is_file():
                    mismatches.append("cached_files")
                else:
                    if receipt.get("request_sha256") != sha256_file(request_path):
                        mismatches.append("request_sha256")
                    if receipt.get("input_manifest_sha256") != sha256_file(input_manifest_path):
                        mismatches.append("input_manifest_sha256")
                if mismatches:
                    raise RuntimeError("stale cached run: " + ",".join(sorted(set(mismatches))))
            else:
                result = run(
                    video_path=Path(clip["visual_only"]["path"]),
                    clip_id=clip_id,
                    out_dir=clip_out,
                    source_reference=(
                        f"SoccerNet NDA-authorized local research clip; split={manifest['split']}; "
                        f"half={manifest['source_half']}; opaque id={clip_id}"
                    ),
                    source_manifest=manifest_path,
                    endpoint=endpoint,
                    model=model,
                    sample_count=sample_count,
                    sheets=sheets,
                    max_tokens=max_tokens,
                )
                prediction = result["prediction"]
                receipt = result["receipt"]
            truth = clip["ground_truth"]
            completed.append({
                "clip_id": clip_id,
                "truth": truth["play_type"],
                "allowed_play_types": truth["allowed_play_types_in_window"],
                "single_label_eligible": truth["single_label_eligible"],
                "prediction": prediction["answer"],
                "confidence": prediction["confidence"],
                "abstained": prediction["abstained"],
                "exact_correct": prediction["answer"] == truth["play_type"],
                "allowed_correct": prediction["answer"] in truth["allowed_play_types_in_window"],
                "elapsed_ms": receipt["elapsed_ms"],
                "model_reported": receipt.get("model_reported"),
                "prediction_sha256": sha256_file(prediction_path),
                "receipt_sha256": sha256_file(receipt_path),
            })
        except Exception as exc:  # retain other clips and make failures explicit
            detail_path = private_out / clip_id / "batch-failure.json"
            write_json(detail_path, {"clip_id": clip_id, "error_type": type(exc).__name__, "error": str(exc)})
            failures.append({"clip_id": clip_id, "error_code": type(exc).__name__})
    summary = summarize(
        manifest=manifest, completed=completed, failures=failures,
        model=model, manifest_path=manifest_path, sample_count=sample_count,
        sheets=sheets, max_tokens=max_tokens, frozen_config_receipt=frozen_config_receipt,
    )
    write_json(public_summary, summary)
    if failures:
        raise RuntimeError(f"{len(failures)} VLM clip runs failed; see {public_summary}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="zai-org/glm-4.6v-flash")
    parser.add_argument("--sample-count", type=int, default=12)
    parser.add_argument("--sheets", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=2400)
    parser.add_argument(
        "--frozen-config", type=Path,
        help="Fail closed unless this sealed config matches the runtime and manifest before inference.",
    )
    parser.add_argument(
        "--runtime-receipt", type=Path,
        help="Required when the frozen v2 configuration binds an isolated-runtime receipt.",
    )
    args = parser.parse_args()
    summary = run_batch(
        manifest_path=args.manifest, private_out=args.private_out,
        public_summary=args.summary, endpoint=args.endpoint, model=args.model,
        sample_count=args.sample_count, sheets=args.sheets, max_tokens=args.max_tokens,
        frozen_config_path=args.frozen_config,
        runtime_receipt_path=args.runtime_receipt,
    )
    print(json.dumps({"status": "complete", "counts": summary["counts"], "metrics": summary["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
