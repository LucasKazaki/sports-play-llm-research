import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
from verify_demo_candidate import REQUIRED_CHECKS, bound_path, verify


def frozen(tmp_path):
    (tmp_path / "candidate.md").write_text("[Evidence](receipt.json)", encoding="utf-8")
    (tmp_path / "receipt.json").write_text(json.dumps({
        "schema_version": "playground-demo-readiness-v1", "passed": True,
        "checks": {name: True for name in REQUIRED_CHECKS}, "failures": [], "evidence": [],
        "performance_claim_allowed": False, "shareable_candidate_promoted": False,
    }), encoding="utf-8")
    return {"schema_version": "playground-candidate-evidence-index-v1", "candidate": "candidate.md",
            "promotion_allowed": False, "performance_claim_allowed": False, "rehearsal_receipt": "receipt.json",
            "files": [{"path": p, "sha256": hashlib.sha256((tmp_path / p).read_bytes()).hexdigest()}
                      for p in ["candidate.md", "receipt.json"]]}


def test_frozen_candidate_detects_modified_or_missing_evidence(tmp_path):
    index = frozen(tmp_path)
    assert verify(tmp_path, index)["passed"]
    (tmp_path / "receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Hash mismatch"):
        verify(tmp_path, index)
    (tmp_path / "receipt.json").unlink()
    with pytest.raises(ValueError, match="Missing exact"):
        verify(tmp_path, index)


@pytest.mark.parametrize("text,reason", [("Placeholder: future evidence", "placeholder"), ("[Evidence](invented.json)", "Unbound")])
def test_candidate_rejects_placeholders_and_unbound_links(tmp_path, text, reason):
    index = frozen(tmp_path)
    (tmp_path / "candidate.md").write_text(text, encoding="utf-8")
    index["files"][0]["sha256"] = hashlib.sha256((tmp_path / "candidate.md").read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=reason):
        verify(tmp_path, index)


def test_candidate_rejects_promoted_or_escaped_inputs(tmp_path):
    index = frozen(tmp_path)
    index["promotion_allowed"] = True
    with pytest.raises(ValueError, match="promotion"):
        verify(tmp_path, index)
    with pytest.raises(ValueError, match="escaped"):
        bound_path(tmp_path, "../outside.json")
