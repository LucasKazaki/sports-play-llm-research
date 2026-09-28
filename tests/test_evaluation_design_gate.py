import copy, hashlib, json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototype"))
from evaluation_design_gate import check_manifest, strict_json, SCHEMA, REQUIRED_EVIDENCE

@pytest.fixture
def design(tmp_path):
    evidence = {}
    for role in REQUIRED_EVIDENCE:
        content = ("SYNTHETIC " + role).encode()
        (tmp_path / (role + ".txt")).write_bytes(content)
        evidence[role] = {"path": role + ".txt", "sha256": hashlib.sha256(content).hexdigest()}
    return {"schema_version": SCHEMA, "evidence_kind": "synthetic_fixture",
            "clips": [{"clip_id": "c" + str(i), "group_id": "g" + str(i),
                       "source_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
                       "split": "test"} for i in range(6)],
            "development_group_ids": ["old-development-match"], "evidence": evidence}, tmp_path

def test_structural_pass_never_authorizes_science(design):
    raw, root = design
    result = check_manifest(raw, root)
    assert result["status"] == "PASS_STRUCTURAL_ONLY"
    assert result["test_clips"] == 6 and result["test_groups"] == 6
    assert result["scientific_validation"] is False
    assert result["processing_authorized"] is False
    assert result["annotation_independence_verified"] is False

@pytest.mark.parametrize("mutation,expected", [
    ("group", "group crosses splits"), ("bytes", "source bytes cross splits"),
    ("history", "test group exposed"), ("duplicate", "duplicate clip ID"),
    ("small", "6-15 test clips"), ("role", "required evidence roles"),
    ("escape", "portable relative"), ("digest", "digest mismatch"),
    ("unknown", "manifest keys differ")])
def test_design_rejects_false_readiness(design, mutation, expected):
    raw, root = design
    if mutation in {"group", "bytes"}:
        added = copy.deepcopy(raw["clips"][0])
        added["clip_id"] = "dev"
        added["split"] = "development"
        if mutation == "bytes":
            added["group_id"] = "different-declared-group"
        raw["clips"].append(added)
    elif mutation == "history": raw["development_group_ids"].append("g0")
    elif mutation == "duplicate": raw["clips"][1]["clip_id"] = "c0"
    elif mutation == "small": raw["clips"].pop()
    elif mutation == "role": del raw["evidence"]["independent_review"]
    elif mutation == "escape": raw["evidence"]["rights_scope"]["path"] = "../outside"
    elif mutation == "digest": (root / "rights_scope.txt").write_text("tampered")
    elif mutation == "unknown": raw["approved"] = True
    result = check_manifest(raw, root)
    assert result["status"] == "BLOCKED"
    assert any(expected in e for e in result["errors"])

@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_strict_json_rejects_ambiguous_input(text):
    with pytest.raises(ValueError): strict_json(text)

def test_real_declarations_do_not_authenticate_evidence(design):
    raw, root = design
    raw["evidence_kind"] = "real_candidate"
    result = check_manifest(raw, root)
    assert not result["annotation_independence_verified"]
    assert not result["scientific_validation"]

def test_bad_clip_type_and_missing_evidence_fail(design):
    raw, root = design
    raw["clips"][0] = None
    (root / "rights_scope.txt").unlink()
    assert check_manifest(raw, root)["status"] == "BLOCKED"

@pytest.mark.parametrize("all_same", [False, True])
def test_repeated_test_input_bytes_cannot_complete_cohort(design, all_same):
    raw, root = design
    if all_same:
        for row in raw["clips"]:
            row["source_sha256"] = raw["clips"][0]["source_sha256"]
    else:
        raw["clips"][-1]["source_sha256"] = raw["clips"][0]["source_sha256"]
    result = check_manifest(raw, root)
    assert result["status"] == "BLOCKED"
    assert any("duplicate test input bytes" in error for error in result["errors"])
