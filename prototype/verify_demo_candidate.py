"""Validate a frozen presentation candidate and its exact local evidence index.

This is a deterministic pre-review gate, not a scientific or promotion verdict.
It verifies existence, hashes, local Markdown link closure, and receipt fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECKS = {
    "soccer_health", "soccer_available", "sealed_longform_backend", "all_96_windows_loaded",
    "both_complete_halves", "semantic_no_go_preserved", "performance_claims_blocked",
    "labels_and_audio_excluded", "requested_query_mode", "two_half_media_routes",
    "media:/media/soccer/longform/half-1", "media:/media/soccer/longform/half-2", "demo_html_available",
} | {f"query_{i}:{name}" for i in (1, 2) for name in (
    "soccer_results_returned", "count_matches_payload", "semantic_warning_visible",
    "query_execution_mode", "all_results_have_valid_playback")}


def bound_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path == root.resolve() or not path.is_relative_to(root.resolve()):
        raise ValueError(f"Evidence path escaped the project: {relative}")
    if not path.is_file():
        raise ValueError(f"Missing exact evidence path: {relative}")
    return path


def verify(root: Path, index: dict) -> dict:
    if index.get("schema_version") != "playground-candidate-evidence-index-v1":
        raise ValueError("Unknown evidence-index schema")
    if index.get("promotion_allowed") is not False or index.get("performance_claim_allowed") is not False:
        raise ValueError("Candidate must retain promotion and performance gates")
    entries = index.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Evidence index requires a nonempty file list")
    expected = {}
    for item in entries:
        if set(item) != {"path", "sha256"} or item["path"] in expected:
            raise ValueError("Every evidence binding requires one unique path and SHA-256")
        path = bound_path(root, item["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Hash mismatch: {item['path']}")
        expected[item["path"]] = digest
    candidate_name = index.get("candidate")
    if candidate_name not in expected:
        raise ValueError("Candidate must be hash-bound")
    candidate = bound_path(root, candidate_name)
    text = candidate.read_text(encoding="utf-8")
    if re.search(r"placeholder|\bTODO\b|\bTBD\b", text, re.IGNORECASE):
        raise ValueError("Candidate contains unfinished placeholder text")
    local_links = []
    for target in re.findall(r"\]\(([^)]+)\)", text):
        parsed = urlsplit(target)
        if parsed.scheme or not parsed.path:
            continue
        resolved = (candidate.parent / unquote(parsed.path)).resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("Candidate link escaped the project")
        relative = resolved.relative_to(root.resolve()).as_posix()
        if relative not in expected:
            raise ValueError(f"Unbound candidate link: {relative}")
        local_links.append(relative)
    receipt_name = index.get("rehearsal_receipt")
    if receipt_name not in expected:
        raise ValueError("Rehearsal receipt must be hash-bound")
    receipt = json.loads(bound_path(root, receipt_name).read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "playground-demo-readiness-v1" or receipt.get("passed") is not True:
        raise ValueError("Rehearsal must have a passing recognized receipt")
    checks = receipt.get("checks", {})
    if set(checks) != REQUIRED_CHECKS or not all(v is True for v in checks.values()) or receipt.get("failures"):
        raise ValueError("Expected all 23 rehearsal checks and no execution failure")
    if receipt.get("performance_claim_allowed") is not False or receipt.get("shareable_candidate_promoted") is not False:
        raise ValueError("Rehearsal must preserve semantic/promotion boundaries")
    receipt_dir = bound_path(root, receipt_name).parent
    for item in receipt.get("evidence", []):
        if "file" in item:
            relative = (receipt_dir / item["file"]).resolve().relative_to(root.resolve()).as_posix()
            if expected.get(relative) != item.get("sha256"):
                raise ValueError(f"Receipt input lacks a matching index binding: {relative}")
    return {"schema_version": "playground-candidate-gate-v1", "passed": True,
            "candidate": candidate_name, "bound_file_count": len(expected),
            "checked_local_link_count": len(local_links), "rehearsal_check_count": len(checks),
            "performance_claim_allowed": False, "promotion_allowed": False,
            "required_next_gate": "Independent Luna reasoning review, then Terra inspection and exact promotion edit",
            "boundary": "Path/hash/schema validation only; no semantic review, source rights decision, or promotion."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = verify(ROOT, json.loads(args.index.read_text(encoding="utf-8")))
    except Exception as exc:
        result = {"passed": False, "promotion_allowed": False, "error": f"{type(exc).__name__}: {exc}"}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
