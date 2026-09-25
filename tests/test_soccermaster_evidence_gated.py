import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import soccermaster_evidence_gated.pipeline as module


def _frames() -> list[module.FrameDescriptor]:
    return [module.FrameDescriptor(f"F{index:02d}", float(index)) for index in range(6)]


def _proposal(stage: str, event_type: str = "foul", *, abstain: bool = False) -> dict:
    return {
        "schema_version": module.PROPOSAL_SCHEMA_VERSION,
        "stage_id": stage,
        "abstain": abstain,
        "abstention_reason": "No continuous view." if abstain else "",
        "event_type": "unknown" if abstain else event_type,
        "pre_frame_id": None if abstain else "F01",
        "anchor_frame_id": None if abstain else "F03",
        "post_frame_id": None if abstain else "F05",
        "event_description": "One bounded visual claim.",
        "uncertainties": ["Sparse broadcast frames."],
        "confidence": 0.5,
    }


def _audit(event_type: str = "foul", *, verdict: str = "supported", goal_evidence: str = "not_applicable") -> dict:
    return {
        "schema_version": module.AUDIT_SCHEMA_VERSION,
        "stage_id": "evidence_audit",
        "candidate_event_type": event_type,
        "verdict": verdict,
        "pre_frame_id": "F01",
        "anchor_frame_id": "F03",
        "post_frame_id": "F05",
        "visible_evidence": ["Visible before/action/after context."],
        "goal_visual_evidence": goal_evidence,
        "uncertainties": ["Silent sampled frames."],
    }


def test_preregistration_is_zero_call_vlm_only_semantics_contract() -> None:
    protocol = module.protocol_template()
    assert module.protocol_errors(protocol) == []
    assert protocol["execution_gate"]["model_calls_made"] == 0
    assert protocol["execution_gate"]["this_package_permits_network_inference"] is False
    assert protocol["scope"]["event_semantics_source"] == "VLM calls only"
    assert protocol["data_contract"]["test_window_quotas"] == module.DIAGNOSTIC_QUOTAS


def test_payload_is_anonymous_and_excludes_labels_and_source_identity() -> None:
    payload = module.build_model_payload("proposal_a", _frames())
    encoded = json.dumps(payload).lower()
    assert "media_path" not in encoded
    assert "source_scope" not in encoded
    assert "game_id" not in encoded
    assert payload["model_input_contract"]["labels_used"] is False
    assert payload["ordered_frames"] == [
        {"frame_id": f"F{index:02d}", "relative_seconds": float(index)} for index in range(6)
    ]


def test_audit_payload_requires_only_a_vlm_authored_candidate_type() -> None:
    payload = module.build_model_payload("evidence_audit", _frames(), "goal")
    assert payload["candidate"] == {"candidate_event_type": "goal"}
    with pytest.raises(ValueError, match="concrete"):
        module.build_model_payload("evidence_audit", _frames(), "unknown")


def test_proposal_rejects_frame_as_event_structure_and_unordered_evidence() -> None:
    report = _proposal("proposal_a")
    report["post_frame_id"] = "F03"
    assert "evidence_frames_not_distinct" in module.validate_proposal(report, _frames(), "proposal_a")
    report = _proposal("proposal_a")
    report["pre_frame_id"] = "F05"
    assert "evidence_frames_not_chronological" in module.validate_proposal(report, _frames(), "proposal_a")
    report = _proposal("proposal_a")
    report["events"] = [{"event_type": "foul"}, {"event_type": "offside"}]
    assert any(item.startswith("unexpected:events") for item in module.validate_proposal(report, _frames(), "proposal_a"))


def test_goal_gate_requires_direct_vlm_audit_evidence() -> None:
    proposal_a = _proposal("proposal_a", "goal")
    proposal_b = _proposal("proposal_b", "goal")
    withheld = module.gate_vlm_claim(proposal_a, proposal_b, _audit("goal", goal_evidence="post_goal_restart_only"), _frames())
    assert withheld["accepted"] is False
    assert withheld["gate_reason"] == "goal_missing_direct_vlm_visual_evidence"
    accepted = module.gate_vlm_claim(proposal_a, proposal_b, _audit("goal", goal_evidence="ball_crosses_goal_line"), _frames())
    assert accepted["accepted"] is True
    assert accepted["event_type"] == "goal"


def test_gate_withholds_instead_of_deterministically_retyping_disagreement() -> None:
    result = module.gate_vlm_claim(_proposal("proposal_a", "foul"), _proposal("proposal_b", "offside"), _audit("foul"), _frames())
    assert result["accepted"] is False
    assert result["event_type"] == "unknown"
    assert result["gate_reason"] == "proposal_type_disagreement"


def test_private_binding_requires_disjoint_heldout_groups_and_zero_calls() -> None:
    protocol = module.protocol_template()
    binding = module.example_private_binding()
    receipt = module.preflight(protocol, binding)
    assert receipt["status"] == "pass"
    assert receipt["heldout_binding_ready"] is True
    assert receipt["binding_contract_valid"] is True
    assert receipt["inference_permitted"] is False
    binding["heldout_group_hashes"] = list(binding["development_group_hashes"])
    errors = module.preflight(protocol, binding)["binding_errors"]
    assert "group_overlap" in errors
    binding = module.example_private_binding()
    binding["heldout_media_overlap_with_historic_vlm_inputs"] = True
    errors = module.preflight(protocol, binding)["binding_errors"]
    assert "heldout_media_overlap_with_historic_vlm_inputs" in errors
    binding = module.example_private_binding()
    binding["full_frame_overlay_audit_status"] = "failed"
    errors = module.preflight(protocol, binding)["binding_errors"]
    assert "full_frame_overlay_audit_status" in errors
    binding = module.example_private_binding()
    binding["raw_label_values"] = ["must never be here"]
    errors = module.preflight(protocol, binding)["binding_errors"]
    assert any(item.startswith("unexpected_private_binding_fields:") for item in errors)


def test_public_private_binding_schema_has_the_no_contamination_requirements() -> None:
    schema = module.private_binding_json_schema()
    required = set(schema["required"])
    assert {"historic_vlm_input_media_lock_sha256", "heldout_media_overlap_with_historic_vlm_inputs", "label_lock_sha256"} <= required
    assert schema["properties"]["test_model_calls_made"] == {"const": 0}
    assert schema["properties"]["model_input_labels_used"] == {"const": False}


def test_dry_run_writes_receipt_without_model_or_private_media(tmp_path: Path) -> None:
    protocol = tmp_path / "preregistration.json"
    module.write_preregistration(protocol)
    output = tmp_path / "dry-run-receipt.json"
    result = module.dry_run(protocol, output)
    assert result["status"] == "pass"
    assert result["mode"] == "synthetic_contract_dry_run"
    assert result["binding_contract_valid"] is True
    assert result["heldout_binding_ready"] is False
    assert result["binding_is_synthetic"] is True
    assert result["model_calls_made_by_this_command"] == 0
    assert result["media_or_labels_read_by_this_command"] is False
    assert module.read_json(output) == result


def test_preregistration_refuses_accidental_replacement_after_creation(tmp_path: Path) -> None:
    protocol = tmp_path / "preregistration.json"
    module.write_preregistration(protocol)
    mutated = module.read_json(protocol)
    mutated["data_contract"]["window_count"] = 999
    module.write_json(protocol, mutated)
    with pytest.raises(ValueError, match="refuse overwrite"):
        module.write_preregistration(protocol)
    refreshed = module.write_preregistration(protocol, replace_unsealed=True)
    assert refreshed["data_contract"]["window_count"] == 40


def test_package_has_no_model_transport_or_pixel_event_inference_dependency() -> None:
    package = ROOT / "prototype" / "soccermaster_evidence_gated"
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    forbidden = ("urllib", "requests", "openai", "cv2", "onnxruntime", "torch", "VideoCapture", "_post_json")
    assert not [term for term in forbidden if term in source]
