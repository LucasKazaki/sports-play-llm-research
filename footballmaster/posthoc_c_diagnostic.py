"""Run the frozen six-window guarded-prompt diagnostic after primary sealing.

This is deliberately separate from the primary test.  It can describe structural
output differences only; it cannot select a prompt, replace the primary result,
or support an accuracy or improvement claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .longform import (
    PROMPT_CANDIDATES,
    PROMPT_MAX_TOKENS,
    PROMPT_REQUEST_POLICY,
    Window,
    canonical_json,
    load_windows,
    read_json,
    run_one,
    scan_package_isolation,
    sha256_bytes,
    sha256_file,
    utc_now,
    verify_seal,
    write_json,
)


SCHEMA_VERSION = "footballmaster-posthoc-c-diagnostic-v1"
PLAN_SHA256 = "ebb5b6e8bf91c1cbe38225d20e25dfc58cef451e4676abe265c2171fd87fd675"
PROMPT_ID = "candidate_c_event_guarded_3200"
PROMPT_SHA256 = "6543517d0637f71d337d924e47facdf87204ead49eeb68d47237ed7996657fff"
PRIMARY_SEAL_ROOT = "7a8260cc109e6cf60433c186d5000030fdf38aa905382460aae1dbd0960ec8f1"
MODEL = "google/gemma-4-e4b"
ENDPOINT = "http://127.0.0.1:1240/v1"
DENOMINATOR = 6
DEFAULT_OUTPUT = Path("artifacts/footballmaster/longform-v2-posthoc-c-diagnostic")
DEFAULT_PRIMARY = Path("artifacts/footballmaster/longform-v2")


def _window_bindings(plan: dict[str, Any], primary_dir: Path) -> list[Window]:
    primary = {window.window_id: window for window in load_windows(primary_dir / "window-manifest.jsonl")}
    selected: list[Window] = []
    for planned in plan.get("windows", []):
        window = primary.get(str(planned.get("window_id")))
        if window is None:
            raise ValueError(f"diagnostic window is absent from primary manifest: {planned.get('window_id')}")
        expected = {
            "window_id": window.window_id,
            "game_id": window.game_id,
            "asset_id": window.asset_id,
            "duration_seconds": window.duration_seconds,
            "start_seconds": window.start_seconds,
            "fraction_index": window.fraction_index,
            "media_path": window.media_path,
            "media_sha256": window.media_sha256,
        }
        if planned != expected or window.split != "test":
            raise ValueError(f"diagnostic window binding changed: {window.window_id}")
        selected.append(window)
    if len(selected) != DENOMINATOR or len({window.window_id for window in selected}) != DENOMINATOR:
        raise ValueError("diagnostic requires exactly six unique frozen test windows")
    return selected


def validate_preflight(project_root: Path, primary_dir: Path, output_dir: Path) -> tuple[dict[str, Any], list[Window]]:
    plan_path = output_dir / "diagnostic-plan.json"
    clearance_path = output_dir / "diagnostic-clearance.json"
    if sha256_file(plan_path) != PLAN_SHA256:
        raise ValueError("frozen diagnostic plan changed")
    plan = read_json(plan_path)
    if (
        plan.get("schema_version") != "footballmaster-posthoc-c-diagnostic-plan-v1"
        or plan.get("status") != "frozen_before_diagnostic_calls"
        or plan.get("prediction_seal_root_hash") != PRIMARY_SEAL_ROOT
        or plan.get("prompt_id") != PROMPT_ID
        or plan.get("prompt_sha256") != PROMPT_SHA256
        or plan.get("max_tokens") != 3200
        or plan.get("planned_call_denominator") != DENOMINATOR
    ):
        raise ValueError("frozen diagnostic protocol identity changed")
    if plan.get("input_contract") != {
        "ordered_silent_jpeg_frames": True,
        "audio": False,
        "commentary": False,
        "source_titles_filenames_team_names_rosters_labels": False,
    }:
        raise ValueError("diagnostic silent-input boundary changed")
    prompt_text = PROMPT_CANDIDATES[PROMPT_ID]
    if sha256_bytes(prompt_text.encode("utf-8")) != PROMPT_SHA256:
        raise ValueError("guarded diagnostic prompt text changed")
    if PROMPT_MAX_TOKENS[PROMPT_ID] != 3200:
        raise ValueError("guarded diagnostic token budget changed")
    if PROMPT_REQUEST_POLICY[PROMPT_ID] != "structured-3200-compact-recovery-v2":
        raise ValueError("guarded diagnostic recovery policy changed")
    primary_seal = verify_seal(primary_dir)
    if primary_seal.get("root_hash") != PRIMARY_SEAL_ROOT:
        raise ValueError("primary prediction seal root changed")
    clearance = read_json(clearance_path)
    required_clearance = {
        "authorized": True,
        "authorized_by": "/root",
        "diagnostic_plan_sha256": PLAN_SHA256,
        "primary_prediction_seal_sha256": sha256_file(primary_dir / "prediction-seal.json"),
        "primary_prediction_seal_root_hash": PRIMARY_SEAL_ROOT,
        "prompt_id": PROMPT_ID,
        "prompt_sha256": PROMPT_SHA256,
        "max_tokens": 3200,
        "planned_call_denominator": DENOMINATOR,
        "model": MODEL,
        "endpoint": ENDPOINT,
    }
    if any(clearance.get(key) != value for key, value in required_clearance.items()):
        raise PermissionError("diagnostic clearance does not bind the frozen plan and primary seal")
    windows = _window_bindings(plan, primary_dir)
    for window in windows:
        media = project_root / window.media_path
        if not media.is_file() or sha256_file(media) != window.media_sha256:
            raise ValueError(f"diagnostic source media changed: {window.window_id}")
    if scan_package_isolation(project_root):
        raise ValueError("football package isolation failed")
    return plan, windows


def run_diagnostic(
    project_root: Path, primary_dir: Path, output_dir: Path, timeout_seconds: int
) -> dict[str, Any]:
    if (output_dir / "diagnostic-seal.json").is_file():
        verify_diagnostic_seal(output_dir)
        raise RuntimeError("diagnostic outputs are sealed; additional model calls are forbidden")
    _, windows = validate_preflight(project_root, primary_dir, output_dir)
    receipts = []
    for index, window in enumerate(windows, start=1):
        receipt = run_one(
            project_root,
            output_dir,
            window,
            PROMPT_ID,
            PROMPT_CANDIDATES[PROMPT_ID],
            ENDPOINT,
            MODEL,
            timeout_seconds,
        )
        receipts.append(receipt)
        write_json(
            output_dir / "diagnostic-state.json",
            {
                "schema_version": "footballmaster-posthoc-c-diagnostic-state-v1",
                "updated_at_utc": utc_now(),
                "status": "running" if index < DENOMINATOR else "calls_complete_pending_seal",
                "plan_sha256": PLAN_SHA256,
                "terminal_receipts": index,
                "HTTP_attempts": sum(int(item.get("attempt_count", 0)) for item in receipts),
                "model_calls_started": True,
                "posthoc_only": True,
            },
        )
    return read_json(output_dir / "diagnostic-state.json")


def _validate_terminal(output_dir: Path, window: Window) -> dict[str, Any]:
    base = output_dir / "runs" / PROMPT_ID / window.window_id
    receipt_path = base / "receipt.json"
    raw_path = base / "raw-response.json"
    normalized_path = base / "normalized-report.json"
    if not all(path.is_file() for path in (receipt_path, raw_path, normalized_path)):
        raise RuntimeError(f"incomplete diagnostic window: {window.window_id}")
    receipt = read_json(receipt_path)
    if (
        receipt.get("status") not in {"complete", "abstained"}
        or receipt.get("window_id") != window.window_id
        or receipt.get("game_id") != window.game_id
        or receipt.get("split") != "test"
        or receipt.get("media_sha256") != window.media_sha256
        or receipt.get("prompt_id") != PROMPT_ID
        or receipt.get("prompt_sha256") != PROMPT_SHA256
        or receipt.get("request_policy_id") != "structured-3200-compact-recovery-v2"
        or receipt.get("max_tokens") != 3200
        or receipt.get("model") != MODEL
        or receipt.get("endpoint_origin") != ENDPOINT
    ):
        raise RuntimeError(f"diagnostic terminal identity changed: {window.window_id}")
    if sha256_file(raw_path) != receipt.get("raw_response_sha256"):
        raise RuntimeError(f"diagnostic raw response changed: {window.window_id}")
    if sha256_file(normalized_path) != receipt.get("normalized_report_sha256"):
        raise RuntimeError(f"diagnostic normalized report changed: {window.window_id}")
    contract = receipt.get("input_contract", {})
    if (
        contract.get("audio_used") is not False
        or contract.get("commentary_used") is not False
        or contract.get("source_metadata_in_prompt") is not False
        or len(contract.get("ordered_frames", [])) != 8
    ):
        raise RuntimeError(f"diagnostic input contract changed: {window.window_id}")
    for index, frame in enumerate(contract["ordered_frames"]):
        path = base / "frames" / f"F{index:02d}.jpg"
        if (
            frame.get("frame_id") != f"F{index:02d}"
            or not path.is_file()
            or frame.get("sha256") != sha256_file(path)
            or frame.get("bytes") != path.stat().st_size
        ):
            raise RuntimeError(f"diagnostic frame changed: {window.window_id}/F{index:02d}")
    attempts = receipt.get("attempts", [])
    if not attempts or len(attempts) != receipt.get("attempt_count"):
        raise RuntimeError(f"diagnostic attempt denominator changed: {window.window_id}")
    for attempt in attempts:
        request = attempt.get("request_receipt", {})
        if request.get("audio_used") is not False or request.get("metadata_fields_used") != []:
            raise RuntimeError(f"diagnostic attempt input changed: {window.window_id}")
        if len(request.get("frames", [])) not in {4, 8}:
            raise RuntimeError(f"diagnostic recovery frame count changed: {window.window_id}")
    return receipt


def _seal_paths(output_dir: Path) -> list[Path]:
    fixed = [output_dir / "diagnostic-plan.json", output_dir / "diagnostic-clearance.json"]
    runs = sorted(path for path in (output_dir / "runs").rglob("*") if path.is_file())
    return fixed + runs


def seal_diagnostic(project_root: Path, primary_dir: Path, output_dir: Path) -> dict[str, Any]:
    seal_path = output_dir / "diagnostic-seal.json"
    if seal_path.is_file():
        return verify_diagnostic_seal(output_dir)
    _, windows = validate_preflight(project_root, primary_dir, output_dir)
    for window in windows:
        _validate_terminal(output_dir, window)
    paths = _seal_paths(output_dir)
    files = {
        path.relative_to(output_dir).as_posix(): sha256_file(path)
        for path in sorted(paths, key=lambda item: item.relative_to(output_dir).as_posix())
    }
    seal = {
        "schema_version": "footballmaster-posthoc-c-diagnostic-seal-v1",
        "sealed_at_utc": utc_now(),
        "status": "sealed_before_structural_comparison",
        "terminal_window_denominator": DENOMINATOR,
        "file_count": len(files),
        "files": files,
        "root_hash": sha256_bytes(canonical_json(files)),
        "primary_predictions_modified": False,
        "accuracy_or_improvement_measured": False,
        "comparison_performed_before_seal": False,
    }
    write_json(seal_path, seal)
    return seal


def verify_diagnostic_seal(output_dir: Path) -> dict[str, Any]:
    seal = read_json(output_dir / "diagnostic-seal.json")
    files = seal.get("files", {})
    if sha256_bytes(canonical_json(files)) != seal.get("root_hash"):
        raise ValueError("diagnostic seal root changed")
    for relative, expected in files.items():
        path = output_dir / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"diagnostic sealed file changed: {relative}")
    current_runs = {
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / "runs").rglob("*")
        if path.is_file()
    }
    if current_runs != {relative for relative in files if relative.startswith("runs/")}:
        raise ValueError("diagnostic run artifact set changed after seal")
    if seal.get("terminal_window_denominator") != DENOMINATOR:
        raise ValueError("diagnostic seal denominator changed")
    return seal


def internally_unsupported_scoring_count(report: dict[str, Any]) -> int:
    """Count scoring labels lacking scoring evidence in the model's own text.

    This is a deterministic internal-consistency audit, not visual ground truth.
    """
    markers = (
        "score",
        "scoring",
        "touchdown",
        "goal line",
        "official signal",
        "field goal",
        "extra point",
        "conversion",
        "celebrat",
    )
    count = 0
    for event in report.get("events", []):
        if event.get("event_type") != "scoring":
            continue
        text = " ".join(
            str(event.get(field, ""))
            for field in ("action", "outcome", "field_context", "uncertainties")
        ).lower()
        if not any(marker in text for marker in markers):
            count += 1
    return count


def explicitly_negated_scoring_count(report: dict[str, Any]) -> int:
    """Count scoring labels whose own text explicitly denies scoring evidence.

    This catches a known false negative in the marker-only consistency check:
    phrases such as ``no scoring evidence`` contain a scoring marker even though
    the model is contradicting its ``event_type=scoring`` label. It remains a
    text-only structural audit, not visual ground truth.
    """
    negations = (
        "no score",
        "no scoring",
        "not scoring",
        "without scoring",
        "does not score",
        "did not score",
        "no touchdown",
        "not a touchdown",
    )
    count = 0
    for event in report.get("events", []):
        if event.get("event_type") != "scoring":
            continue
        text = " ".join(
            str(event.get(field, ""))
            for field in ("action", "outcome", "field_context", "uncertainties")
        ).lower()
        if any(negation in text for negation in negations):
            count += 1
    return count


def _summarize(rows: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    reports = [normalized["report"] for normalized, _ in rows]
    receipts = [receipt for _, receipt in rows]
    return {
        "terminal_valid_count": sum(bool(receipt.get("valid")) for receipt in receipts),
        "abstain_count": sum(bool(report.get("abstain")) for report in reports),
        "abstain_with_nonempty_events_count": sum(
            bool(report.get("abstain")) and bool(report.get("events")) for report in reports
        ),
        "unsupported_scoring_event_count": sum(
            internally_unsupported_scoring_count(report) for report in reports
        ),
        "explicitly_negated_scoring_event_count": sum(
            explicitly_negated_scoring_count(report) for report in reports
        ),
        "scoring_event_count_model_outputs_not_truth": sum(
            event.get("event_type") == "scoring"
            for report in reports
            for event in report.get("events", [])
        ),
        "reported_event_count_model_outputs_not_truth": sum(
            len(report.get("events", [])) for report in reports
        ),
        "HTTP_attempts": sum(int(receipt.get("attempt_count", 0)) for receipt in receipts),
        "elapsed_seconds": sum(float(receipt.get("total_elapsed_seconds", 0.0)) for receipt in receipts),
    }


def build_comparison(primary_dir: Path, output_dir: Path) -> dict[str, Any]:
    seal = verify_diagnostic_seal(output_dir)
    plan = read_json(output_dir / "diagnostic-plan.json")
    windows = _window_bindings(plan, primary_dir)
    c_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    a_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for window in windows:
        c_base = output_dir / "runs" / PROMPT_ID / window.window_id
        a_base = primary_dir / "runs" / "candidate_a_direct" / window.window_id
        c_rows.append((read_json(c_base / "normalized-report.json"), read_json(c_base / "receipt.json")))
        a_rows.append((read_json(a_base / "normalized-report.json"), read_json(a_base / "receipt.json")))
    guarded = _summarize(c_rows)
    primary = _summarize(a_rows)
    metrics = {
        "schema_version": "footballmaster-posthoc-c-structural-comparison-v1",
        "generated_at_utc": utc_now(),
        "diagnostic_seal_root_hash": seal["root_hash"],
        "window_denominator": DENOMINATOR,
        "same_fixed_windows": True,
        "candidate_a_primary_frozen": primary,
        "candidate_c_posthoc_guarded": guarded,
        "descriptive_delta_c_minus_a": {
            key: guarded[key] - primary[key]
            for key in (
                "terminal_valid_count",
                "abstain_count",
                "abstain_with_nonempty_events_count",
                "unsupported_scoring_event_count",
                "explicitly_negated_scoring_event_count",
                "scoring_event_count_model_outputs_not_truth",
                "reported_event_count_model_outputs_not_truth",
                "HTTP_attempts",
                "elapsed_seconds",
            )
        },
        "unsupported_scoring_definition": (
            "event_type=scoring with no scoring marker in the model's own action/outcome/"
            "field_context/uncertainty text; internal consistency only, not visual truth"
        ),
        "explicitly_negated_scoring_definition": (
            "event_type=scoring paired with an explicit textual negation such as 'no scoring'; "
            "internal contradiction only, not visual truth"
        ),
        "accuracy_measured": False,
        "prompt_selection_allowed": False,
        "heldout_performance_claim_allowed": False,
        "model_improvement_claim_allowed": False,
        "primary_result_replacement_allowed": False,
    }
    write_json(output_dir / "diagnostic-metrics.json", metrics)
    report = f"""# Guarded C3200 Post-hoc Diagnostic

## Boundary

This is a six-window, post-seal structural diagnostic on the predeclared subset. It cannot replace the 36-window candidate-A primary test, select a prompt, or support accuracy, held-out performance, or model-improvement claims.

## Same-window structural counts

| Output | Primary A | Post-hoc C3200 | C − A |
|---|---:|---:|---:|
| Terminal valid | {primary['terminal_valid_count']} | {guarded['terminal_valid_count']} | {guarded['terminal_valid_count'] - primary['terminal_valid_count']} |
| Abstain | {primary['abstain_count']} | {guarded['abstain_count']} | {guarded['abstain_count'] - primary['abstain_count']} |
| Abstain + nonempty events | {primary['abstain_with_nonempty_events_count']} | {guarded['abstain_with_nonempty_events_count']} | {guarded['abstain_with_nonempty_events_count'] - primary['abstain_with_nonempty_events_count']} |
| Internally unsupported scoring labels | {primary['unsupported_scoring_event_count']} | {guarded['unsupported_scoring_event_count']} | {guarded['unsupported_scoring_event_count'] - primary['unsupported_scoring_event_count']} |
| Explicitly negated scoring labels | {primary['explicitly_negated_scoring_event_count']} | {guarded['explicitly_negated_scoring_event_count']} | {guarded['explicitly_negated_scoring_event_count'] - primary['explicitly_negated_scoring_event_count']} |
| All scoring labels (unverified output) | {primary['scoring_event_count_model_outputs_not_truth']} | {guarded['scoring_event_count_model_outputs_not_truth']} | {guarded['scoring_event_count_model_outputs_not_truth'] - primary['scoring_event_count_model_outputs_not_truth']} |
| All emitted events (unverified output) | {primary['reported_event_count_model_outputs_not_truth']} | {guarded['reported_event_count_model_outputs_not_truth']} | {guarded['reported_event_count_model_outputs_not_truth'] - primary['reported_event_count_model_outputs_not_truth']} |
| HTTP attempts | {primary['HTTP_attempts']} | {guarded['HTTP_attempts']} | {guarded['HTTP_attempts'] - primary['HTTP_attempts']} |

Both scoring checks are only model-internal text-consistency checks. The marker-only unsupported count can miss negated phrases because ``no scoring evidence`` still contains the word ``scoring``; the explicit-negation row makes that failure visible. There are no event labels or retrieval judgments in this diagnostic.
"""
    (output_dir / "DIAGNOSTIC_REPORT.md").write_text(report, encoding="utf-8")
    files = {
        name: sha256_file(output_dir / name)
        for name in ("diagnostic-metrics.json", "DIAGNOSTIC_REPORT.md")
    }
    receipt = {
        "schema_version": "footballmaster-posthoc-c-diagnostic-results-receipt-v1",
        "created_at_utc": utc_now(),
        "diagnostic_seal_sha256": sha256_file(output_dir / "diagnostic-seal.json"),
        "diagnostic_seal_root_hash": seal["root_hash"],
        "comparison_after_diagnostic_seal": True,
        "files": files,
        "root_hash": sha256_bytes(canonical_json(files)),
        "accuracy_measured": False,
        "model_improvement_claim_allowed": False,
    }
    write_json(output_dir / "diagnostic-results-receipt.json", receipt)
    return metrics


def verify_final(project_root: Path, primary_dir: Path, output_dir: Path) -> dict[str, Any]:
    primary_seal = verify_seal(primary_dir)
    diagnostic_seal = verify_diagnostic_seal(output_dir)
    results = read_json(output_dir / "diagnostic-results-receipt.json")
    errors = []
    for relative, expected in results.get("files", {}).items():
        path = output_dir / relative
        if not path.is_file() or sha256_file(path) != expected:
            errors.append(relative)
    if sha256_bytes(canonical_json(results.get("files", {}))) != results.get("root_hash"):
        errors.append("results root")
    metrics = read_json(output_dir / "diagnostic-metrics.json")
    checks = {
        "primary_seal_unchanged": primary_seal.get("root_hash") == PRIMARY_SEAL_ROOT,
        "diagnostic_seal_terminal_denominator": diagnostic_seal.get("terminal_window_denominator"),
        "comparison_after_seal": results.get("comparison_after_diagnostic_seal"),
        "window_denominator": metrics.get("window_denominator"),
        "same_fixed_windows": metrics.get("same_fixed_windows"),
        "accuracy_disabled": metrics.get("accuracy_measured") is False,
        "selection_disabled": metrics.get("prompt_selection_allowed") is False,
        "improvement_claim_disabled": metrics.get("model_improvement_claim_allowed") is False,
        "result_file_errors": errors,
        "package_isolation_violations": scan_package_isolation(project_root),
    }
    expected = {
        "primary_seal_unchanged": True,
        "diagnostic_seal_terminal_denominator": DENOMINATOR,
        "comparison_after_seal": True,
        "window_denominator": DENOMINATOR,
        "same_fixed_windows": True,
        "accuracy_disabled": True,
        "selection_disabled": True,
        "improvement_claim_disabled": True,
        "result_file_errors": [],
        "package_isolation_violations": [],
    }
    failures = {
        key: {"expected": value, "observed": checks.get(key)}
        for key, value in expected.items()
        if checks.get(key) != value
    }
    receipt = {
        "schema_version": "footballmaster-posthoc-c-diagnostic-verification-v1",
        "verified_at_utc": utc_now(),
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "posthoc_only": True,
        "accuracy_measured": False,
    }
    write_json(output_dir / "diagnostic-verification-receipt.json", receipt)
    if failures:
        raise ValueError("post-hoc diagnostic verification failed: " + json.dumps(failures, sort_keys=True))
    write_json(
        output_dir / "diagnostic-state.json",
        {
            "schema_version": "footballmaster-posthoc-c-diagnostic-state-v1",
            "updated_at_utc": utc_now(),
            "status": "final_verified_posthoc_nonperformance",
            "terminal_receipts": DENOMINATOR,
            "diagnostic_seal_sha256": sha256_file(output_dir / "diagnostic-seal.json"),
            "diagnostic_seal_root_hash": diagnostic_seal["root_hash"],
            "results_receipt_sha256": sha256_file(output_dir / "diagnostic-results-receipt.json"),
            "verification_receipt_sha256": sha256_file(output_dir / "diagnostic-verification-receipt.json"),
            "primary_predictions_modified": False,
            "accuracy_measured": False,
        },
    )
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    commands = value.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--timeout-seconds", type=int, default=300)
    commands.add_parser("seal")
    commands.add_parser("build-comparison")
    commands.add_parser("verify")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    primary_dir = args.primary if args.primary.is_absolute() else project_root / args.primary
    output_dir = args.output if args.output.is_absolute() else project_root / args.output
    if args.command == "run":
        result = run_diagnostic(project_root, primary_dir, output_dir, args.timeout_seconds)
    elif args.command == "seal":
        result = seal_diagnostic(project_root, primary_dir, output_dir)
    elif args.command == "build-comparison":
        result = build_comparison(primary_dir, output_dir)
    elif args.command == "verify":
        result = verify_final(project_root, primary_dir, output_dir)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
