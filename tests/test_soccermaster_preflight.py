import copy
import hashlib
import json
from pathlib import Path
import pytest
from prototype import soccermaster_preflight as m

D = "a" * 64

def scope():
    return {"component": "encoder_event_head", "source_revision": "b" * 40,
            "checkpoint_hashes": {"backbone": "c" * 64, "event_head": "d" * 64},
            "media_sha256": D, "input_contract_sha256": "e" * 64,
            "max_gpu_memory_bytes": 8 * m.GIB, "max_model_calls": 1,
            "remote_processing": False, "spend_usd": 0}

def binding(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": name, "sha256": m.file_hash(path)}

def approval(tmp_path, kind="rights", **changes):
    data = {"schema_version": "playground-soccermaster-approval-v1",
            "kind": kind, "decision": "approved", "issuer": "fixture-reviewer",
            "approved_at": "2026-01-01T00:00:00Z", "scope_sha256": m.canonical_hash(scope())}
    data.update(changes)
    return binding(tmp_path, kind + ".json", data)

def test_plan_is_deterministic_and_label_free():
    plan = m.frame_plan("clip_01", 10, D)
    assert plan == m.frame_plan("clip_01", 10, D)
    assert len(plan["frames"]) == 30
    assert plan["frames"][0]["offset_s"] == 0
    assert plan["frames"][-1]["offset_s"] < 10
    assert plan["shape"] == [30, 512, 512, 3]
    assert plan["labels_included"] is False
    assert plan["official_tensor_normalization"] == "unverified"

@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf"), "10"])
def test_plan_rejects_invalid_duration(value):
    with pytest.raises(m.PreflightError):
        m.frame_plan("clip_01", value, D)

@pytest.mark.parametrize("value", ["../clip", "a/b", "a:b", "team name", "", None])
def test_plan_rejects_path_or_identity_shaped_ids(value):
    with pytest.raises(m.PreflightError):
        m.frame_plan(value, 10, D)

def test_rgb_adapter_really_checks_bytes_and_never_claims_inference():
    plan = m.frame_plan("fixture_01", 5, D)
    raw = bytes(512 * 512 * 3)
    result = m.adapt_rgb_frames(plan, [raw] * 30)
    assert len(result["frame_sha256"]) == 30
    assert result["frame_sha256"][0] == hashlib.sha256(raw).hexdigest()
    assert result["total_raw_bytes"] == 23592960
    assert result["model_calls"] == 0
    assert result["official_callable_compatible"] is False
    assert result["source_and_redaction_verified"] is False

@pytest.mark.parametrize("count,size", [(29, 786432), (31, 786432), (30, 1)])
def test_rgb_adapter_rejects_wrong_count_or_shape(count, size):
    with pytest.raises(m.PreflightError):
        m.adapt_rgb_frames(m.frame_plan("fixture", 5, D), [bytes(size)] * count)

def test_rgb_adapter_rejects_plan_tamper():
    plan = m.frame_plan("fixture", 5, D)
    plan["frames"][0]["offset_s"] = 1
    with pytest.raises(m.PreflightError):
        m.adapt_rgb_frames(plan, [bytes(786432)] * 30)

@pytest.mark.parametrize("key,value", [
    ("max_gpu_memory_bytes", 9 * m.GIB), ("max_gpu_memory_bytes", True),
    ("max_model_calls", 2), ("max_model_calls", True),
    ("spend_usd", 0.01), ("spend_usd", False), ("remote_processing", True),
    ("source_revision", D), ("media_sha256", "unknown"),
])
def test_scope_rejects_out_of_budget_and_unpinned_assets(key, value):
    value_scope = scope()
    value_scope[key] = value
    with pytest.raises(m.PreflightError):
        m.validate_scope(value_scope)

@pytest.mark.parametrize("kind", m.APPROVAL_KINDS)
def test_approvals_are_separate_content_bound_records(tmp_path, kind):
    receipt = m.verify_approval(tmp_path, kind, approval(tmp_path, kind), scope())
    assert receipt["kind"] == kind
    assert receipt["validation"] == "content_binding_only_not_independent_issuer_authentication"

def test_approval_wrong_kind_cannot_satisfy_another_gate(tmp_path):
    with pytest.raises(m.PreflightError):
        m.verify_approval(tmp_path, "license", approval(tmp_path, "rights"), scope())

def test_approval_tampering_rejected(tmp_path):
    spec = approval(tmp_path)
    (tmp_path / spec["path"]).write_text("{}")
    with pytest.raises(m.PreflightError, match="hash mismatch"):
        m.verify_approval(tmp_path, "rights", spec, scope())

def test_approval_experiment_drift_rejected(tmp_path):
    spec = approval(tmp_path)
    changed = scope()
    changed["media_sha256"] = "f" * 64
    with pytest.raises(m.PreflightError, match="different experiment"):
        m.verify_approval(tmp_path, "rights", spec, changed)

@pytest.mark.parametrize("date", ["yesterday", "2026-01-01", "2999-01-01T00:00:00Z"])
def test_approval_requires_valid_past_zoned_time(tmp_path, date):
    with pytest.raises(m.PreflightError):
        m.verify_approval(tmp_path, "rights", approval(tmp_path, approved_at=date), scope())

@pytest.mark.parametrize("path", ["../elsewhere", "//server/file", "\\\\server\\file",
                                  "https://host/path", "secrets/key.json", "credentials/a"])
def test_explicit_local_paths_cannot_escape_or_access_network(tmp_path, path):
    with pytest.raises(m.PreflightError):
        m._local(tmp_path, path)

def output_case():
    ontology = {"class_names": ["fixture_a", "fixture_b"], "mapping_status": "verified",
                "source_sha256": D}
    provenance = {"source_revision": "b" * 40, "backbone_sha256": D, "head_sha256": D,
                  "input_manifest_sha256": D, "ontology_sha256": m.canonical_hash(ontology),
                  "run_receipt_sha256": D}
    payload = {"schema_version": "playground-soccermaster-raw-output-v1",
               "origin": "synthetic_contract_fixture", "provenance": provenance.copy(),
               "event_logits": [-2.0, 1.5], "semantic_embedding": [0.0, 0.1, -0.2]}
    return payload, provenance, ontology

def test_synthetic_output_is_explicit_and_cannot_become_semantic_claim():
    payload, provenance, ontology = output_case()
    result = m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)
    assert result["origin"] == "synthetic_contract_fixture"
    assert result["official_execution_verified"] is False
    assert result["semantic_status"] == "UNADJUDICATED"
    assert result["performance_claim_allowed"] is False
    assert result["coach_report_generated"] is False

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "0.4"])
def test_logits_reject_nonfinite_and_non_numeric(bad):
    payload, provenance, ontology = output_case()
    payload["event_logits"][0] = bad
    with pytest.raises(m.PreflightError):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)

def test_provenance_mismatch_rejected():
    payload, provenance, ontology = output_case()
    payload["provenance"]["head_sha256"] = "f" * 64
    with pytest.raises(m.PreflightError, match="provenance"):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)

def test_ontology_class_count_and_order_bound():
    payload, provenance, ontology = output_case()
    payload["event_logits"].append(0)
    with pytest.raises(m.PreflightError, match="count"):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)
    payload, provenance, ontology = output_case()
    ontology["class_names"].reverse()
    with pytest.raises(m.PreflightError, match="ontology hash"):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)

def test_unresolved_23_24_mapping_fails_closed():
    payload, provenance, ontology = output_case()
    ontology["mapping_status"] = "unresolved"
    with pytest.raises(m.PreflightError, match="unresolved"):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)

def test_rich_report_cannot_be_invented_from_logits():
    payload, provenance, ontology = output_case()
    payload["coach_report"] = "A goal was scored"
    with pytest.raises(m.PreflightError):
        m.validate_model_output(payload, expected_provenance=provenance, ontology=ontology)

def minimum_config():
    return {"schema_version": "playground-soccermaster-preflight-config-v1",
            "sources": [], "scope": scope(),
            "approvals": dict.fromkeys(m.APPROVAL_KINDS),
            "assets": dict.fromkeys(("source_code", "backbone", "event_head", "siglip_config")),
            "official_entrypoint": None, "normalization": None,
            "ontology": {"mapping_status": "unresolved"}}

def machine():
    return {"packages": {"torch": None, "transformers": None}, "gpu": {"status": "unavailable"}}

def test_preflight_missing_gates_are_receipt_not_success(tmp_path):
    result = m.preflight(minimum_config(), root=tmp_path, inventory=machine())
    assert result["status"] == "BLOCKED"
    for kind in m.APPROVAL_KINDS:
        assert kind + "_approval_absent" in result["blockers"]
    assert result["assets"]["backbone"]["status"] == "not_supplied"
    assert result["model_calls"] == result["network_calls"] == 0
    assert result["checkpoint_deserializations"] == result["official_code_imports"] == 0
    assert result["performance_claim_allowed"] is False

def test_source_capture_and_hash_are_checked(tmp_path):
    snap = binding(tmp_path, "snapshot.txt", {"text": "fixture"})
    receipt = binding(tmp_path, "capture.json", {
        "sha256": snap["sha256"].upper(), "httpStatus": 200,
        "bytes": (tmp_path / "snapshot.txt").stat().st_size,
        "capturedAtUtc": "2026-01-01T00:00:00Z", "url": "https://example.invalid/",
        "serverOwnedRuntimeReceipt": False})
    config = minimum_config()
    config["sources"] = [{"snapshot": snap, "receipt": receipt}]
    result = m.preflight(config, root=tmp_path, inventory=machine())
    assert len(result["sources"]) == 1
    assert result["sources"][0]["freshness"] == "historical_snapshot_not_a_current_remote_check"
    (tmp_path / "snapshot.txt").write_text("changed")
    result = m.preflight(config, root=tmp_path, inventory=machine())
    assert result["sources"] == []
    assert any("source_evidence" in item for item in result["blockers"])

def test_checkpoint_is_hashed_never_deserialized(tmp_path):
    config = minimum_config()
    path = tmp_path / "backbone.pt"
    path.write_bytes(b"fixture-not-a-checkpoint")
    digest = m.file_hash(path)
    config["scope"]["checkpoint_hashes"]["backbone"] = digest
    config["assets"]["backbone"] = {"path": "backbone.pt", "sha256": digest}
    result = m.preflight(config, root=tmp_path, inventory=machine())
    assert result["assets"]["backbone"]["status"] == "hash_verified_only"
    assert result["assets"]["backbone"]["deserialized"] is False

def test_even_supplied_gate_flags_cannot_trigger_official_inference(tmp_path):
    config = minimum_config()
    config["official_entrypoint"] = "untrusted.module"
    config["normalization"] = "untrusted"
    config["ontology"] = {"mapping_status": "verified"}
    result = m.preflight(config, root=tmp_path, inventory=machine())
    assert result["status"] == "BLOCKED"
    assert "official_inference_transport_not_implemented" in result["blockers"]
