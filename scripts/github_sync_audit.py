"""Produce a conservative, deterministic candidate list for GitHub mirroring.

The Sports project contains private/restricted media and large generated data.
This utility never stages, commits, pushes, or reads credentials. It only
identifies small source-of-truth candidates and fails closed on known secrets.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_MAX_BYTES = 2 * 1024 * 1024
ROOT_FILES = frozenset({
    ".gitignore", "AGENTS.md", "GOAL_WORK.json", "PROJECT_GUIDE.md", "README.md",
    "RUN_LOG.md", "pytest.ini", "requirements-windows-py311.lock.txt", "LICENSE", "NOTICE", "SECURITY.md", "CONTRIBUTING.md",
})
ALLOWED_ROOTS = frozenset({"demo", "footballmaster", "prototype", "reports", "research", "scripts", "tests"})
ALLOWED_SUFFIXES = frozenset({
    ".css", ".html", ".ini", ".js", ".json", ".md", ".mjs", ".ps1", ".py", ".schema",
    ".toml", ".txt", ".yaml", ".yml", ".cmd",
})
DENIED_COMPONENTS = frozenset({
    ".agent", ".agent-runtime", ".codex-work", ".git", ".pytest_cache", "__pycache__",
    "node_modules", "secrets", "secret", "credentials",
})
SECRET_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
)


def _relative(root: Path, candidate: Path) -> str:
    return candidate.relative_to(root).as_posix()


def exclusion_reason(relative: str, size: int, max_bytes: int) -> str | None:
    parts = tuple(Path(relative).parts)
    if not parts:
        return "invalid_path"
    if parts[:3] == ("data", "open", "chess") and parts[-1] == "source-page.html":
        return "upstream_source_snapshot"
    if relative == "research/archit-next-meeting-soccermaster-brief-2026-08-27.html":
        return "candidate_deliverable_review_required"
    if any(part in DENIED_COMPONENTS or part.startswith(".venv") for part in parts):
        return "local_runtime_or_secret_path"
    if parts[0] in {"artifacts", "data"} and parts[:2] == ("data", "private"):
        return "private_data"
    if parts[:2] == ("data", "public"):
        return "public_raw_data"
    if parts[:3] == ("data", "open", "chess") and "media" in parts:
        return "raw_media"
    if parts[0] == "artifacts":
        return "generated_artifact"
    if len(parts) == 1:
        if relative not in ROOT_FILES:
            return "root_file_not_allowlisted"
    elif parts[0] in ALLOWED_ROOTS:
        pass
    elif parts[:3] == ("data", "open", "chess"):
        pass
    else:
        return "path_not_allowlisted"
    suffix = Path(relative).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES and relative != ".gitignore":
        return "file_type_not_allowlisted"
    if size > max_bytes:
        return "file_exceeds_byte_budget"
    return None


def secret_findings(path: Path, relative: str) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if b"\0" in raw:
        return [{"path": relative, "reason": "binary_content"}]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [{"path": relative, "reason": "non_utf8_content"}]
    return [
        {"path": relative, "reason": "recognized_secret_signature"}
        for pattern in SECRET_PATTERNS if pattern.search(text)
    ]


def audit_repository(root: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"repository root does not exist: {root}")
    candidates: list[str] = []
    excluded = Counter()
    violations: list[dict[str, str]] = []
    scanned_files = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            if path.is_file():
                violations.append({"path": _relative(root, path), "reason": "symlink"})
            continue
        if not path.is_file():
            continue
        scanned_files += 1
        relative = _relative(root, path)
        reason = exclusion_reason(relative, path.stat().st_size, max_bytes)
        if reason:
            excluded[reason] += 1
            continue
        findings = secret_findings(path, relative)
        if findings:
            violations.extend(findings)
            continue
        candidates.append(relative)
    return {
        "schemaVersion": 1,
        "root": str(root),
        "maxBytesPerFile": max_bytes,
        "scannedFiles": scanned_files,
        "eligiblePaths": candidates,
        "excludedByReason": dict(sorted(excluded.items())),
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)
    if args.max_bytes < 1:
        parser.error("--max-bytes must be positive")
    try:
        report = audit_repository(args.root, args.max_bytes)
    except (OSError, ValueError) as error:
        print(json.dumps({"schemaVersion": 1, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
