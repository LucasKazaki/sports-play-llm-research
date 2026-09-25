"""Regression coverage for the conservative GitHub mirror allowlist."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("github_sync_audit", ROOT / "scripts" / "github_sync_audit.py")
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


def write(root: Path, relative: str, content: str = "ok") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_curated_mirror_includes_source_and_small_chess_provenance_only(tmp_path):
    write(tmp_path, ".gitignore")
    write(tmp_path, "README.md")
    write(tmp_path, "pytest.ini")
    write(tmp_path, "requirements-windows-py311.lock.txt")
    write(tmp_path, "footballmaster/pipeline.py")
    write(tmp_path, "scripts/tool.py")
    write(tmp_path, "research/decision.md")
    write(tmp_path, "research/archit-next-meeting-soccermaster-brief-2026-08-27.html")
    write(tmp_path, "data/open/chess/v1/manifest.json")
    write(tmp_path, "data/open/chess/v1/source-page.html")
    write(tmp_path, "data/open/chess/v1/media/clip.mp4")
    write(tmp_path, "data/private/notes.md")
    write(tmp_path, "data/public/record.json")
    write(tmp_path, "artifacts/raw-result.json")
    write(tmp_path, ".agent/runtime.json")
    write(tmp_path, "prototype/model.gguf")

    report = audit.audit_repository(tmp_path)

    assert report["violations"] == []
    assert set(report["eligiblePaths"]) == {
        ".gitignore", "README.md", "pytest.ini", "requirements-windows-py311.lock.txt", "data/open/chess/v1/manifest.json",
        "research/decision.md", "scripts/tool.py", "footballmaster/pipeline.py",
    }
    assert report["excludedByReason"]["raw_media"] == 1
    assert report["excludedByReason"]["private_data"] == 1
    assert report["excludedByReason"]["public_raw_data"] == 1
    assert report["excludedByReason"]["generated_artifact"] == 1
    assert report["excludedByReason"]["local_runtime_or_secret_path"] == 1
    assert report["excludedByReason"]["file_type_not_allowlisted"] == 1
    assert report["excludedByReason"]["upstream_source_snapshot"] == 1
    assert report["excludedByReason"]["candidate_deliverable_review_required"] == 1


def test_recognized_secret_signature_fails_closed(tmp_path):
    marker = "gh" + "p_1234567890abcdefABCDEF"
    write(tmp_path, "README.md", "do not mirror " + marker)

    report = audit.audit_repository(tmp_path)

    assert report["eligiblePaths"] == []
    assert report["violations"] == [{"path": "README.md", "reason": "recognized_secret_signature"}]


def test_byte_budget_excludes_large_otherwise_eligible_file(tmp_path):
    write(tmp_path, "research/large.md", "x" * 33)

    report = audit.audit_repository(tmp_path, max_bytes=32)

    assert report["eligiblePaths"] == []
    assert report["excludedByReason"] == {"file_exceeds_byte_budget": 1}
