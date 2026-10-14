#!/usr/bin/env python3
"""Validate and summarize the chess-specialist model registry.

The validator is deliberately dependency-free so it can run before any candidate
model environment is installed. It prevents upstream claims, unresolved licenses,
or a general-purpose control from being promoted as production evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "sports-play-llm.chess-specialist-model-registry.v1"

ALLOWED_ROLES = {
    "general_control",
    "move_policy",
    "human_move_policy",
    "world_model",
    "chess_reasoning_trace",
    "commentary_generator",
}
ALLOWED_TRAINING_TYPES = {
    "general_purpose",
    "chess_move_policy",
    "chess_language_model",
    "chess_world_model",
    "joint_policy_language",
    "human_move_model",
}
ALLOWED_EVIDENCE_STATUSES = {
    "project_control_only",
    "upstream_only",
    "locally_smoke_tested",
    "project_reproduced",
    "project_benchmarked",
}
ALLOWED_ELIGIBILITY = {
    "control_only",
    "unverified_candidate",
    "benchmark_candidate",
    "production_candidate",
    "rejected",
}
ALLOWED_CLAIM_STATUSES = {
    "upstream_unreproduced",
    "project_reproduced",
}
RESOLVED_LICENSE_STATUSES = {
    "existing_project_dependency",
    "verified_mit",
    "verified_apache_2_0",
    "verified_bsd_3_clause",
    "verified_project_compatible",
}


def _require_text(value: Any, field: str, errors: list[str], prefix: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{field} must be a non-empty string")
        return None
    return value


def validate_registry(document: Any) -> list[str]:
    """Return deterministic validation errors; an empty list means valid."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["registry root must be a JSON object"]

    if document.get("schema") != SCHEMA:
        errors.append(f"schema must equal {SCHEMA!r}")

    models = document.get("models")
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for index, model in enumerate(models):
        prefix = f"models[{index}]"
        if not isinstance(model, dict):
            errors.append(f"{prefix} must be an object")
            continue

        model_id = _require_text(model.get("id"), "id", errors, prefix)
        if model_id:
            if model_id in seen_ids:
                errors.append(f"{prefix}.id duplicates {model_id!r}")
            seen_ids.add(model_id)
            prefix = f"model[{model_id}]"

        _require_text(model.get("display_name"), "display_name", errors, prefix)

        roles = model.get("roles")
        if not isinstance(roles, list) or not roles:
            errors.append(f"{prefix}.roles must be a non-empty array")
        else:
            unknown_roles = sorted(set(roles) - ALLOWED_ROLES)
            if unknown_roles:
                errors.append(f"{prefix}.roles contains unknown values: {unknown_roles}")
            if len(roles) != len(set(roles)):
                errors.append(f"{prefix}.roles must not contain duplicates")

        training_type = model.get("training_type")
        if training_type not in ALLOWED_TRAINING_TYPES:
            errors.append(
                f"{prefix}.training_type must be one of {sorted(ALLOWED_TRAINING_TYPES)}"
            )

        specialized = model.get("chess_specialized")
        if not isinstance(specialized, bool):
            errors.append(f"{prefix}.chess_specialized must be boolean")
            specialized = None

        evidence_status = model.get("evidence_status")
        if evidence_status not in ALLOWED_EVIDENCE_STATUSES:
            errors.append(
                f"{prefix}.evidence_status must be one of "
                f"{sorted(ALLOWED_EVIDENCE_STATUSES)}"
            )

        eligibility = model.get("production_eligibility")
        if eligibility not in ALLOWED_ELIGIBILITY:
            errors.append(
                f"{prefix}.production_eligibility must be one of "
                f"{sorted(ALLOWED_ELIGIBILITY)}"
            )

        license_status = _require_text(
            model.get("license_status"), "license_status", errors, prefix
        )
        _require_text(model.get("weights_status"), "weights_status", errors, prefix)

        source_url = model.get("source_url")
        if source_url is not None and (
            not isinstance(source_url, str) or not source_url.startswith("https://")
        ):
            errors.append(f"{prefix}.source_url must be null or an https URL")

        training_evidence = model.get("training_evidence")
        if not isinstance(training_evidence, dict):
            errors.append(f"{prefix}.training_evidence must be an object")
        else:
            scope = _require_text(
                training_evidence.get("scope"),
                "training_evidence.scope",
                errors,
                prefix,
            )
            _require_text(
                training_evidence.get("source"),
                "training_evidence.source",
                errors,
                prefix,
            )
            if specialized is True and scope == "none_chess_specific":
                errors.append(
                    f"{prefix} is marked chess-specialized but records no "
                    "chess-specific training"
                )

        if specialized is False:
            if training_type != "general_purpose":
                errors.append(
                    f"{prefix} is not chess-specialized, so training_type must be "
                    "'general_purpose'"
                )
            if eligibility not in {"control_only", "rejected"}:
                errors.append(
                    f"{prefix} is general-purpose and may only be control_only or rejected"
                )
        elif specialized is True:
            if source_url is None:
                errors.append(f"{prefix} is chess-specialized and requires source_url")
            if eligibility == "control_only":
                errors.append(
                    f"{prefix} is chess-specialized and cannot use control_only eligibility"
                )

        claims = model.get("claimed_metrics")
        if not isinstance(claims, list):
            errors.append(f"{prefix}.claimed_metrics must be an array")
            claims = []
        for claim_index, claim in enumerate(claims):
            claim_prefix = f"{prefix}.claimed_metrics[{claim_index}]"
            if not isinstance(claim, dict):
                errors.append(f"{claim_prefix} must be an object")
                continue
            _require_text(claim.get("metric"), "metric", errors, claim_prefix)
            status = claim.get("status")
            if status not in ALLOWED_CLAIM_STATUSES:
                errors.append(
                    f"{claim_prefix}.status must be one of "
                    f"{sorted(ALLOWED_CLAIM_STATUSES)}"
                )
            if status == "project_reproduced" and evidence_status in {
                "upstream_only",
                "project_control_only",
            }:
                errors.append(
                    f"{claim_prefix} cannot be project_reproduced while model evidence "
                    f"is {evidence_status!r}"
                )

        if eligibility == "production_candidate":
            if evidence_status != "project_benchmarked":
                errors.append(
                    f"{prefix} cannot be production_candidate without "
                    "project_benchmarked evidence"
                )
            if license_status not in RESOLVED_LICENSE_STATUSES:
                errors.append(
                    f"{prefix} cannot be production_candidate with unresolved "
                    f"license_status {license_status!r}"
                )
            weights_status = model.get("weights_status", "")
            if not isinstance(weights_status, str) or "unverified" in weights_status:
                errors.append(
                    f"{prefix} cannot be production_candidate with unverified weights"
                )

    return errors


def render_markdown(document: dict[str, Any]) -> str:
    """Render a compact review report after validation."""
    errors = validate_registry(document)
    if errors:
        raise ValueError("invalid registry:\n" + "\n".join(f"- {item}" for item in errors))

    models = document["models"]
    specialized = sum(bool(item["chess_specialized"]) for item in models)
    controls = sum(item["production_eligibility"] == "control_only" for item in models)
    statuses = Counter(item["evidence_status"] for item in models)

    lines = [
        "# Chess specialist registry report",
        "",
        f"- Registry status: `{document.get('status', 'UNKNOWN')}`",
        f"- Total entries: **{len(models)}**",
        f"- Chess-specialized entries: **{specialized}**",
        f"- General controls: **{controls}**",
        "- Evidence: "
        + ", ".join(f"`{key}`={value}" for key, value in sorted(statuses.items())),
        "",
        "| Model | Specialized | Roles | Evidence | Eligibility | License | Weights |",
        "|---|---:|---|---|---|---|---|",
    ]
    for model in models:
        lines.append(
            "| {name} | {specialized} | {roles} | `{evidence}` | `{eligibility}` | "
            "`{license}` | `{weights}` |".format(
                name=model["display_name"].replace("|", r"\|"),
                specialized="yes" if model["chess_specialized"] else "no",
                roles=", ".join(model["roles"]).replace("|", r"\|"),
                evidence=model["evidence_status"],
                eligibility=model["production_eligibility"],
                license=model["license_status"],
                weights=model["weights_status"],
            )
        )

    pending = [
        model["display_name"]
        for model in models
        if model["production_eligibility"] == "unverified_candidate"
    ]
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "No model is promoted by registry membership alone. Upstream claims remain "
            "unreproduced until the project benchmark records the exact revision, "
            "runtime, split, and metrics.",
            "",
            "## Pending candidates",
            "",
        ]
    )
    lines.extend(f"- {name}" for name in pending)
    return "\n".join(lines) + "\n"


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path, help="Path to registry JSON")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional Markdown report path; otherwise print to stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = load_registry(args.registry)
        errors = validate_registry(document)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        report = render_markdown(document)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        else:
            print(report, end="")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
