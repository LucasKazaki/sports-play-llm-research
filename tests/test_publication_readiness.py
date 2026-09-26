"""Adversarial receipt checks; invented fixtures are never soccer results."""
import json
from pathlib import Path
import sys

import pytest

from prototype.publication_audit import SOURCES, audit, main, protocol_sha256, scoped_path, sha256, verify_manifest


@pytest.fixture
def packet(tmp_path):
    seal = "a" * 64
    values = {
        "protocol": {"data_contract": {"window_count": 40}},
        "preflight": {"status": "pass", "heldout_binding_ready": False,
                      "binding_contract_valid": False, "private_binding_supplied": False},
        "metrics": {"window_denominator": 2, "dense_window_denominator": 1,
                    "stress_window_denominator": 1, "valid_response_count": 2,
                    "failure_count": 0, "performance_claim_allowed": False},
        "annotation": {"visual_prediction_seal_root_hash": seal},
        "spot_checks": {"prediction_seal_root_hash": seal,
                        "rows": [{"overall_judgment": "unsupported"}],
                        "judgment_counts": {"unsupported": 1, "supported": 0}},
        "verification": {"status": "pass", "visual_prediction_seal_root_hash": seal},
        "accounting": {"valid": True, "synthetic": True, "scientific_validation": False},
        "experiment": {"rows": [{"arms": {arm: {"matches_engineered_expectation": success}
            for arm, success in [("literal_baseline", False), ("raw_model", True), ("guarded_model_with_fallback", True)]}}]},
    }
    for name, value in values.items():
        path = tmp_path / SOURCES[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    preflight_path = tmp_path / SOURCES["preflight"]
    values["preflight"]["protocol_sha256"] = protocol_sha256(values["protocol"])
    preflight_path.write_text(json.dumps(values["preflight"]))
    manifest_path = tmp_path / SOURCES["experiment_manifest"]
    manifest_path.write_text(json.dumps({"files": {"results.json": sha256((tmp_path / SOURCES["experiment"]).read_bytes())},
                                        "source_sha256": {SOURCES["protocol"]: "b" * 64}}))
    return tmp_path


def edit(packet, name, change):
    path = packet / SOURCES[name]
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))


def test_passing_receipts_and_synthetic_scoring_do_not_grant_publication(packet):
    report = audit(packet)
    assert report["receipt_integrity_passed"]
    assert not report["publication_ready"]
    assert not report["promotion_authority"]
    blockers = {item["code"] for item in report["blockers"]}
    assert {"FRESH_COHORT_NOT_BOUND", "SEMANTIC_VALIDATION_INCOMPLETE", "NO_CONFIRMATORY_ACCOUNTING_IN_AUDITED_PACKET"} <= blockers


def test_fingerprint_ignores_generated_time_but_captures_changed_evidence(packet):
    first = audit(packet)["evidence_fingerprint"]
    assert first == audit(packet)["evidence_fingerprint"]
    edit(packet, "metrics", lambda value: value.update(failure_count=1))
    assert first != audit(packet)["evidence_fingerprint"]


def test_window_denominator_mismatch_is_integrity_failure(packet):
    edit(packet, "metrics", lambda value: value.update(window_denominator=99))
    assert "window_accounting" in audit(packet)["integrity_errors"]


def test_spot_check_summary_cannot_override_rows(packet):
    edit(packet, "spot_checks", lambda value: value.update(judgment_counts={"supported": 1}))
    assert "spot_check_counts" in audit(packet)["integrity_errors"]


def test_cross_receipt_seal_mismatch_is_failure(packet):
    edit(packet, "annotation", lambda value: value.update(visual_prediction_seal_root_hash="b" * 64))
    assert "cross_receipt_seal" in audit(packet)["integrity_errors"]


def test_protocol_mutation_invalidates_preflight_binding(packet):
    edit(packet, "protocol", lambda value: value.update(changed=True))
    assert "preflight_protocol_binding" in audit(packet)["integrity_errors"]


def test_protocol_whitespace_is_not_a_semantic_hash_mismatch(packet):
    path = packet / SOURCES["protocol"]
    path.write_text(json.dumps(json.loads(path.read_text()), indent=4))
    assert "preflight_protocol_binding" not in audit(packet)["integrity_errors"]


def test_frozen_response_mutation_is_failure(packet):
    edit(packet, "experiment", lambda value: value.update(changed=True))
    assert "frozen_local_experiment_bytes" in audit(packet)["integrity_errors"]


def test_manifest_cannot_omit_the_recounted_results(packet):
    manifest_path = packet / SOURCES["experiment_manifest"]
    unrelated = manifest_path.parent / "unrelated.txt"
    unrelated.write_bytes(b"unrelated valid file")
    edit(packet, "experiment_manifest", lambda value: value.update(files={"unrelated.txt": sha256(unrelated.read_bytes())}))
    report = audit(packet)
    assert "experiment_result_manifest_coverage" in report["integrity_errors"]
    assert not report["receipt_integrity_passed"]


def test_existing_source_cannot_be_overwritten_by_cli_output(packet, monkeypatch):
    path = packet / SOURCES["metrics"]
    before = path.read_bytes()
    monkeypatch.setattr(sys, "argv", ["audit", "--root", str(packet), "--output", SOURCES["metrics"]])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert path.read_bytes() == before


def test_matching_nonhex_seal_is_rejected(packet):
    edit(packet, "annotation", lambda value: value.update(visual_prediction_seal_root_hash="z" * 64))
    edit(packet, "verification", lambda value: value.update(visual_prediction_seal_root_hash="z" * 64))
    edit(packet, "spot_checks", lambda value: value.update(prediction_seal_root_hash="z" * 64))
    assert "cross_receipt_seal" in audit(packet)["integrity_errors"]


def test_historical_source_drift_is_reported_without_rewriting_history(packet):
    report = audit(packet)
    assert report["historical_source_comparison"]["errors"]
    assert report["receipt_integrity_passed"]


def test_missing_receipt_is_not_a_pass(packet):
    (packet / SOURCES["metrics"]).unlink()
    report = audit(packet)
    assert not report["receipt_integrity_passed"]
    assert not report["publication_ready"]


@pytest.mark.parametrize("path", ["../outside.json", "C:/outside.json", "C:outside.json", "/outside.json", "\\\\server\\share\\outside.json"])
def test_manifest_path_escape_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        scoped_path(tmp_path, path)
    assert verify_manifest(tmp_path, {path: "a" * 64})["verified"] == 0


def test_empty_manifest_cannot_pass(tmp_path):
    assert verify_manifest(tmp_path, {})["errors"]


@pytest.mark.parametrize("name,change", [
    ("metrics", {"dense_window_denominator": "bad"}),
    ("spot_checks", {"rows": [None]}),
    ("experiment", {"rows": [{"arms": {"raw_model": None}}]}),
])
def test_malformed_fields_fail_closed_without_crashing(packet, name, change):
    edit(packet, name, lambda value: value.update(change))
    report = audit(packet)
    assert report["audit_completed"]
    assert not report["receipt_integrity_passed"]
