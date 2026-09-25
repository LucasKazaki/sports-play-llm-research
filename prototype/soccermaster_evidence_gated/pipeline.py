"""Preflight-only evidence-gated SoccerMaster VLM diagnostic protocol.

The prior complete-match VLM study was structurally reliable but semantically
unsafe: it could emit one event per sampled frame, hallucinate goals, and use
weak temporal evidence.  This new, separately versioned protocol is a
*pre-registered diagnostic*, not a result.  It deliberately has no HTTP,
OpenAI, model-server, CV, classifier, or event-heuristic implementation.

Future event semantics are authored only by three local VLM calls:

* a single-claim proposer;
* a blinded second proposer on the same frames; and
* a claim-conditioned visual evidence auditor.

Deterministic code only samples anonymous frames, validates schemas and
chronology, compares VLM-authored controlled-vocabulary fields, gates
publication/index admission, seals files, and evaluates against labels after
predictions are sealed.  It never inspects pixels or infers a soccer event.

No inference entry point exists in this package.  A later, separately
reviewed executor must bind the protocol hash, a private held-out data lock,
and an explicit root authorization receipt before it can send local frames to
a VLM.  The commands here are safe dry-run/preflight checks only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROTOCOL_VERSION = "soccermaster-evidence-gated-protocol-v1"
PRIVATE_BINDING_VERSION = "soccermaster-evidence-gated-private-binding-v1"
PROPOSAL_SCHEMA_VERSION = "soccermaster-evidence-gated-proposal-v1"
AUDIT_SCHEMA_VERSION = "soccermaster-evidence-gated-audit-v1"
DEFAULT_ARTIFACT_ROOT = Path("artifacts/soccermaster-evidence-gated-v1")
DEFAULT_PROTOCOL_PATH = DEFAULT_ARTIFACT_ROOT / "preregistration.json"

# These are deliberately limited to SoccerNet-v2 labels that can form a
# reproducible, group-held-out diagnostic subset.  They are evaluator labels;
# their values never appear in a future VLM request.
DIAGNOSTIC_EVENT_TYPES = ("goal", "offside", "foul", "corner_kick")
DIAGNOSTIC_QUOTAS = {
    "goal": 4,
    "offside": 8,
    "foul": 8,
    "corner_kick": 8,
    "background": 12,
}
EVENT_TYPES = (*DIAGNOSTIC_EVENT_TYPES, "unknown")
FRAME_OFFSETS_SECONDS = (-12, -9, -6, -4, -2, -1, 0, 1, 2, 4, 6, 9, 12)
DIRECT_GOAL_EVIDENCE = ("ball_crosses_goal_line", "ball_visibly_in_goal")
GOAL_AUDIT_EVIDENCE = (*DIRECT_GOAL_EVIDENCE, "post_goal_restart_only", "none", "not_applicable")
AUDIT_VERDICTS = ("supported", "insufficient", "contradicted")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FrameDescriptor:
    """Anonymous frame metadata permitted in a future visual request."""

    frame_id: str
    relative_seconds: float


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def _frame_ids(frames: Sequence[FrameDescriptor]) -> list[str]:
    values = [frame.frame_id for frame in frames]
    if len(values) != len(set(values)) or not values:
        raise ValueError("frame IDs must be non-empty and unique")
    return values


def _frame_positions(frames: Sequence[FrameDescriptor]) -> dict[str, int]:
    return {frame.frame_id: index for index, frame in enumerate(frames)}


def proposer_prompt() -> str:
    return (
        "You are reviewing ordered, silent, scoreboard-redacted soccer frames. Return exactly one visually grounded "
        "event claim or abstain; never emit one event per frame. Use only visible pixels and anonymous frame IDs. "
        "The event can occur anywhere in the sequence. Do not infer names, teams, score, commentary, game identity, "
        "or hidden continuity. For a goal, require direct visual evidence of the ball crossing the line or visibly in "
        "the goal; celebration, replay, score graphics, or a later restart alone are insufficient. Cite distinct pre, "
        "anchor, and post frames. If that chain is not visible, abstain. Return only the requested JSON."
    )


def audit_prompt() -> str:
    return (
        "You are an evidence auditor for one proposed soccer event. Inspect only the ordered, silent, "
        "scoreboard-redacted frames and the anonymous candidate claim. Decide supported, insufficient, or contradicted. "
        "Cite distinct pre, anchor, and post frames and describe only what each frame visibly establishes. Do not use "
        "score graphics, commentary, names, teams, external knowledge, or label information. A goal is supported only "
        "when direct visual evidence shows ball-line crossing or ball visibly in the goal; restart/celebration/replay "
        "alone must be marked insufficient or contradicted. Return only the requested JSON."
    )


def protocol_template() -> dict[str, Any]:
    """Return the immutable public preregistration template.

    It has no source names, raw paths, label values, media, VLM response, or
    authorization.  A private binding is required before any execution can be
    considered, and this package still cannot execute model calls itself.
    """

    return {
        "schema_version": PROTOCOL_VERSION,
        "status": "preregistered_template_no_model_calls",
        "protocol_id": "soccermaster-evidence-gated-v1",
        "created_at": "2026-08-30T00:00:00Z",
        "scope": {
            "purpose": "diagnose and suppress frame-as-event, unsupported-goal, and weak-temporal-evidence failures",
            "comparison_boundary": "within a new held-out diagnostic run only; not a replacement for previous frozen studies",
            "vlm_parameter_training": False,
            "event_semantics_source": "VLM calls only",
            "deterministic_code_role": [
                "anonymous frame sampling",
                "schema, evidence-ID, and chronology validation",
                "VLM-output agreement gating",
                "hash sealing, retrieval, and post-seal evaluation",
            ],
            "deterministic_code_must_not": [
                "inspect pixels to classify an event",
                "derive a soccer event from motion, OCR, audio, score, or metadata",
                "repair, relabel, or create an event type",
            ],
        },
        "data_contract": {
            "private_only": True,
            "raw_media_redistribution_allowed": False,
            "minimum_heldout_game_groups": 2,
            "development_and_heldout_groups_disjoint": True,
            "heldout_groups_must_be_new_relative_to_all_prior_vlm_input_media": True,
            "labeled_subset": "private SoccerNet-v2 label lock; labels are evaluator-only and never model input",
            "test_window_quotas": DIAGNOSTIC_QUOTAS,
            "positive_window_seconds": 30,
            "negative_window_seconds": 30,
            "event_center_jitter_seconds": [-6, 6],
            "background_event_exclusion_radius_seconds": 15,
            "one_atomic_claim_per_window": True,
            "window_count": sum(DIAGNOSTIC_QUOTAS.values()),
        },
        "visual_input_contract": {
            "modalities": ["ordered_silent_scoreboard_redacted_frames"],
            "frame_offsets_seconds": list(FRAME_OFFSETS_SECONDS),
            "frame_count": len(FRAME_OFFSETS_SECONDS),
            "audio": "excluded",
            "commentary": "excluded",
            "labels": "excluded",
            "filenames_source_paths_game_identity_team_names_scores_absolute_clock": "excluded",
            "anonymous_frame_fields": ["frame_id", "relative_seconds", "image_bytes"],
            "private_redaction_gate": "full-frame overlay audit must pass before a model request; a fixed top-strip mask alone is insufficient",
        },
        "vlm_stages": [
            {
                "stage_id": "proposal_a",
                "blind_to_other_model_outputs": True,
                "prompt": proposer_prompt(),
                "schema_version": PROPOSAL_SCHEMA_VERSION,
            },
            {
                "stage_id": "proposal_b",
                "blind_to_other_model_outputs": True,
                "prompt": proposer_prompt(),
                "schema_version": PROPOSAL_SCHEMA_VERSION,
                "independence_caveat": "separate role-conditioned call; the same local model family is not statistically independent",
            },
            {
                "stage_id": "evidence_audit",
                "blind_to_labels_and_proposal_b": True,
                "candidate_conditioned_on": "proposal_a only",
                "prompt": audit_prompt(),
                "schema_version": AUDIT_SCHEMA_VERSION,
            },
        ],
        "acceptance_gate": {
            "proposal_a_and_b_must_name_the_same_event_type": True,
            "each_nonabstaining_proposal_requires_distinct_ordered_pre_anchor_post_frames": True,
            "audit_verdict_must_equal": "supported",
            "minimum_pre_to_post_seconds": 2.0,
            "goal_requires_vlm_audit_direct_evidence": list(DIRECT_GOAL_EVIDENCE),
            "failure_action": "abstain; never deterministically substitute a different event type",
            "accepted_text_origin": "proposal_a only; deterministic code only admits or withholds it",
        },
        "evaluation": {
            "prediction_seal_before_labels_opened": True,
            "primary_metrics": [
                "raw_vs_accepted_claim_count",
                "raw_vs_accepted_goal_claim_count",
                "abstention_and_gate_reason_rates",
                "coarse_type_time_corroboration_against_locked_labels",
                "VLM_anchor_time_error_against_locked_label_time",
                "same-window_frame_as_event_multiplicity",
            ],
            "secondary_human_review": "blinded atomic visual support judgment, required before coach-utility claims",
            "forbidden_claims_without_new_human_gold": [
                "detailed-report factuality",
                "coach utility",
                "generalized event accuracy",
                "player identity",
                "full-match search readiness",
            ],
        },
        "execution_gate": {
            "model_calls_made": 0,
            "root_authorization_required_after_review": True,
            "authorization_receipt_must_bind": ["protocol_sha256", "private_binding_sha256", "local_model_identity_sha256"],
            "this_package_permits_network_inference": False,
        },
    }


def private_binding_json_schema() -> dict[str, Any]:
    """Public schema for a private data lock; it intentionally names no source."""

    hash_list = {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}
    hash_value = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Private SoccerMaster evidence-gated v1 data binding",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "status", "development_group_hashes", "heldout_group_hashes", "heldout_media_hashes",
            "new_source_group_acquisition_receipts_sha256", "label_lock_sha256", "visual_window_manifest_sha256",
            "media_allowlist_sha256", "historic_vlm_input_media_lock_sha256", "heldout_media_overlap_with_historic_vlm_inputs",
            "redaction_policy_sha256", "full_frame_overlay_audit_status", "full_frame_overlay_audited_sample_count",
            "input_manifest_excludes_ground_truth", "input_manifest_excludes_source_identity", "model_input_labels_used",
            "private_labels_opened_for_sampling_only", "local_model_endpoint_loopback_only", "test_model_calls_made",
            "test_window_counts", "test_window_ids_sha256",
        ],
        "properties": {
            "schema_version": {"const": PRIVATE_BINDING_VERSION},
            "status": {"const": "prepared_before_model_inference"},
            "development_group_hashes": hash_list,
            "heldout_group_hashes": {**hash_list, "minItems": 2},
            "heldout_media_hashes": hash_list,
            "new_source_group_acquisition_receipts_sha256": {**hash_list, "minItems": 2},
            "label_lock_sha256": hash_value,
            "visual_window_manifest_sha256": hash_value,
            "media_allowlist_sha256": hash_value,
            "historic_vlm_input_media_lock_sha256": hash_value,
            "heldout_media_overlap_with_historic_vlm_inputs": {"const": False},
            "redaction_policy_sha256": hash_value,
            "full_frame_overlay_audit_status": {"const": "pass"},
            "full_frame_overlay_audited_sample_count": {"type": "integer", "minimum": 6},
            "input_manifest_excludes_ground_truth": {"const": True},
            "input_manifest_excludes_source_identity": {"const": True},
            "model_input_labels_used": {"const": False},
            "private_labels_opened_for_sampling_only": {"const": True},
            "local_model_endpoint_loopback_only": {"const": True},
            "test_model_calls_made": {"const": 0},
            "test_window_counts": {
                "type": "object",
                "additionalProperties": False,
                "required": list(DIAGNOSTIC_QUOTAS),
                "properties": {key: {"const": value} for key, value in DIAGNOSTIC_QUOTAS.items()},
            },
            "test_window_ids_sha256": hash_value,
        },
        "description": "Private-only evaluator/source binding. Labels and source identities must not enter a VLM payload.",
    }


def write_preregistration(path: Path, *, replace_unsealed: bool = False) -> dict[str, Any]:
    protocol = protocol_template()
    if path.is_file():
        existing = read_json(path)
        if canonical_json(existing) == canonical_json(protocol):
            return existing
        if not replace_unsealed:
            raise ValueError("preregistration already exists and differs; refuse overwrite without --replace-unsealed")
        if existing.get("execution_gate", {}).get("model_calls_made") != 0:
            raise ValueError("refuse to replace a preregistration after any recorded model call")
    write_json(path, protocol)
    return protocol


def write_private_binding_schema(path: Path) -> dict[str, Any]:
    schema = private_binding_json_schema()
    write_json(path, schema)
    return schema


def proposal_json_schema(frame_ids: Sequence[str]) -> dict[str, Any]:
    if not frame_ids:
        raise ValueError("proposal schema needs frame IDs")
    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "schema_version", "stage_id", "abstain", "abstention_reason", "event_type", "pre_frame_id",
            "anchor_frame_id", "post_frame_id", "event_description", "uncertainties", "confidence",
        ],
        "properties": {
            "schema_version": {"const": PROPOSAL_SCHEMA_VERSION},
            "stage_id": {"enum": ["proposal_a", "proposal_b"]},
            "abstain": {"type": "boolean"},
            "abstention_reason": {"type": "string"},
            "event_type": {"enum": EVENT_TYPES},
            "pre_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "anchor_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "post_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "event_description": {"type": "string", "maxLength": 360},
            "uncertainties": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    }


def audit_json_schema(frame_ids: Sequence[str]) -> dict[str, Any]:
    if not frame_ids:
        raise ValueError("audit schema needs frame IDs")
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "schema_version", "stage_id", "candidate_event_type", "verdict", "pre_frame_id", "anchor_frame_id",
            "post_frame_id", "visible_evidence", "goal_visual_evidence", "uncertainties",
        ],
        "properties": {
            "schema_version": {"const": AUDIT_SCHEMA_VERSION},
            "stage_id": {"const": "evidence_audit"},
            "candidate_event_type": {"enum": EVENT_TYPES},
            "verdict": {"enum": AUDIT_VERDICTS},
            "pre_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "anchor_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "post_frame_id": {"type": ["string", "null"], "enum": [*frame_ids, None]},
            "visible_evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
            "goal_visual_evidence": {"enum": GOAL_AUDIT_EVIDENCE},
            "uncertainties": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        },
        "additionalProperties": False,
    }


def build_model_payload(
    stage_id: str,
    frames: Sequence[FrameDescriptor],
    candidate_event_type: str | None = None,
) -> dict[str, Any]:
    """Build the non-image part of a future local VLM request.

    This is intentionally a data-only payload plan.  It contains no media
    path, source identity, label, score, team name, absolute clock, or model
    transport fields.  A reviewed executor may attach private image bytes only
    after the execution gate has been satisfied.
    """

    frame_ids = _frame_ids(frames)
    if stage_id in {"proposal_a", "proposal_b"}:
        prompt = proposer_prompt()
        schema = proposal_json_schema(frame_ids)
        candidate: dict[str, str] | None = None
    elif stage_id == "evidence_audit":
        if candidate_event_type not in EVENT_TYPES or candidate_event_type == "unknown":
            raise ValueError("evidence audit needs a concrete VLM-proposed event type")
        prompt = audit_prompt()
        schema = audit_json_schema(frame_ids)
        candidate = {"candidate_event_type": candidate_event_type}
    else:
        raise ValueError(f"unknown VLM stage: {stage_id}")
    return {
        "stage_id": stage_id,
        "system_prompt": prompt,
        "candidate": candidate,
        "ordered_frames": [{"frame_id": frame.frame_id, "relative_seconds": frame.relative_seconds} for frame in frames],
        "json_schema": schema,
        "model_input_contract": {
            "audio_used": False,
            "commentary_used": False,
            "labels_used": False,
            "source_metadata_used": False,
            "absolute_timestamps_used": False,
            "image_bytes_attached": False,
        },
    }


def _errors_for_evidence_chain(
    response: Mapping[str, Any], frames: Sequence[FrameDescriptor], *, prefix: str = "") -> list[str]:
    errors: list[str] = []
    positions = _frame_positions(frames)
    values = [response.get(field) for field in ("pre_frame_id", "anchor_frame_id", "post_frame_id")]
    if any(not isinstance(value, str) or value not in positions for value in values):
        return [prefix + "missing_or_unknown_evidence_frame"]
    pre, anchor, post = (str(value) for value in values)
    if len({pre, anchor, post}) != 3:
        errors.append(prefix + "evidence_frames_not_distinct")
    if not (positions[pre] < positions[anchor] < positions[post]):
        errors.append(prefix + "evidence_frames_not_chronological")
    return errors


def validate_proposal(response: Mapping[str, Any], frames: Sequence[FrameDescriptor], expected_stage: str) -> list[str]:
    errors: list[str] = []
    schema = proposal_json_schema(_frame_ids(frames))
    required = schema["required"]
    for field in required:
        if field not in response:
            errors.append(f"missing:{field}")
    extras = sorted(set(response) - set(schema["properties"]))
    if extras:
        errors.append("unexpected:" + ",".join(extras))
    if errors:
        return errors
    if response.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        errors.append("schema_version")
    if response.get("stage_id") != expected_stage:
        errors.append("stage_id")
    if not isinstance(response.get("abstain"), bool):
        errors.append("abstain")
        return errors
    event_type = response.get("event_type")
    if event_type not in EVENT_TYPES:
        errors.append("event_type")
    confidence = response.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append("confidence")
    if not isinstance(response.get("abstention_reason"), str):
        errors.append("abstention_reason")
    if not isinstance(response.get("event_description"), str) or len(str(response.get("event_description", ""))) > 360:
        errors.append("event_description")
    if not isinstance(response.get("uncertainties"), list):
        errors.append("uncertainties")
    if response.get("abstain"):
        if event_type != "unknown":
            errors.append("abstention_requires_unknown_event")
        if not str(response.get("abstention_reason", "")).strip():
            errors.append("abstention_requires_reason")
        if any(response.get(field) is not None for field in ("pre_frame_id", "anchor_frame_id", "post_frame_id")):
            errors.append("abstention_requires_null_evidence")
    else:
        if event_type == "unknown":
            errors.append("claim_requires_concrete_event")
        errors.extend(_errors_for_evidence_chain(response, frames))
    return errors


def validate_audit(
    response: Mapping[str, Any], frames: Sequence[FrameDescriptor], candidate_event_type: str,
) -> list[str]:
    errors: list[str] = []
    schema = audit_json_schema(_frame_ids(frames))
    required = schema["required"]
    for field in required:
        if field not in response:
            errors.append(f"missing:{field}")
    extras = sorted(set(response) - set(schema["properties"]))
    if extras:
        errors.append("unexpected:" + ",".join(extras))
    if errors:
        return errors
    if response.get("schema_version") != AUDIT_SCHEMA_VERSION:
        errors.append("schema_version")
    if response.get("stage_id") != "evidence_audit":
        errors.append("stage_id")
    if response.get("candidate_event_type") != candidate_event_type:
        errors.append("candidate_event_type")
    if response.get("verdict") not in AUDIT_VERDICTS:
        errors.append("verdict")
    if response.get("goal_visual_evidence") not in GOAL_AUDIT_EVIDENCE:
        errors.append("goal_visual_evidence")
    if not isinstance(response.get("visible_evidence"), list) or not response.get("visible_evidence"):
        errors.append("visible_evidence")
    if not isinstance(response.get("uncertainties"), list):
        errors.append("uncertainties")
    if response.get("verdict") == "supported":
        errors.extend(_errors_for_evidence_chain(response, frames))
    if candidate_event_type != "goal" and response.get("goal_visual_evidence") != "not_applicable":
        errors.append("non_goal_requires_not_applicable_goal_evidence")
    return errors


def _span_seconds(response: Mapping[str, Any], frames: Sequence[FrameDescriptor]) -> float | None:
    by_id = {frame.frame_id: frame.relative_seconds for frame in frames}
    pre = response.get("pre_frame_id")
    post = response.get("post_frame_id")
    if not isinstance(pre, str) or not isinstance(post, str) or pre not in by_id or post not in by_id:
        return None
    return float(by_id[post] - by_id[pre])


def gate_vlm_claim(
    proposal_a: Mapping[str, Any],
    proposal_b: Mapping[str, Any],
    audit: Mapping[str, Any],
    frames: Sequence[FrameDescriptor],
) -> dict[str, Any]:
    """Admit or withhold a *VLM-authored* proposal without semantic inference.

    The only event-type information this function sees was emitted by the VLM.
    It does not read images, score a vision feature, or substitute a label.  A
    rejected claim is withheld as abstention; it is never deterministically
    retyped into another soccer event.
    """

    errors = {
        "proposal_a": validate_proposal(proposal_a, frames, "proposal_a"),
        "proposal_b": validate_proposal(proposal_b, frames, "proposal_b"),
        "audit": [],
    }
    candidate = proposal_a.get("event_type") if not proposal_a.get("abstain") else "unknown"
    if isinstance(candidate, str) and candidate in EVENT_TYPES and candidate != "unknown":
        errors["audit"] = validate_audit(audit, frames, candidate)
    else:
        errors["audit"] = ["no_concrete_proposal_a_candidate"]
    if any(errors.values()):
        return {"accepted": False, "event_type": "unknown", "gate_reason": "invalid_vlm_schema", "validation_errors": errors}
    if bool(proposal_a["abstain"]):
        return {"accepted": False, "event_type": "unknown", "gate_reason": "proposal_a_abstained", "validation_errors": errors}
    if bool(proposal_b["abstain"]):
        return {"accepted": False, "event_type": "unknown", "gate_reason": "proposal_b_abstained", "validation_errors": errors}
    if proposal_a["event_type"] != proposal_b["event_type"]:
        return {"accepted": False, "event_type": "unknown", "gate_reason": "proposal_type_disagreement", "validation_errors": errors}
    if audit["verdict"] != "supported":
        return {"accepted": False, "event_type": "unknown", "gate_reason": f"audit_{audit['verdict']}", "validation_errors": errors}
    span = _span_seconds(proposal_a, frames)
    if span is None or span < 2.0:
        return {"accepted": False, "event_type": "unknown", "gate_reason": "proposal_a_temporal_span_under_2s", "validation_errors": errors}
    span_b = _span_seconds(proposal_b, frames)
    if span_b is None or span_b < 2.0:
        return {"accepted": False, "event_type": "unknown", "gate_reason": "proposal_b_temporal_span_under_2s", "validation_errors": errors}
    if proposal_a["event_type"] == "goal" and audit["goal_visual_evidence"] not in DIRECT_GOAL_EVIDENCE:
        return {"accepted": False, "event_type": "unknown", "gate_reason": "goal_missing_direct_vlm_visual_evidence", "validation_errors": errors}
    return {
        "accepted": True,
        "event_type": proposal_a["event_type"],
        "anchor_frame_id": proposal_a["anchor_frame_id"],
        "accepted_text_origin": "proposal_a",
        "gate_reason": "accepted_vlm_consensus_and_evidence",
        "validation_errors": errors,
    }


def _binding_errors(binding: Mapping[str, Any], protocol: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    unexpected = sorted(set(binding) - set(private_binding_json_schema()["properties"]))
    if unexpected:
        errors.append("unexpected_private_binding_fields:" + ",".join(unexpected))
    if binding.get("schema_version") != PRIVATE_BINDING_VERSION:
        errors.append("binding_schema_version")
    if binding.get("status") != "prepared_before_model_inference":
        errors.append("binding_status")
    for key in ("development_group_hashes", "heldout_group_hashes", "heldout_media_hashes", "new_source_group_acquisition_receipts_sha256"):
        values = binding.get(key)
        if not isinstance(values, list) or not values or not all(_is_hash(value) for value in values):
            errors.append(key)
    development = set(binding.get("development_group_hashes", []))
    heldout = set(binding.get("heldout_group_hashes", []))
    for key in ("development_group_hashes", "heldout_group_hashes", "heldout_media_hashes", "new_source_group_acquisition_receipts_sha256"):
        values = binding.get(key)
        if isinstance(values, list) and len(values) != len(set(values)):
            errors.append("duplicate:" + key)
    if development & heldout:
        errors.append("group_overlap")
    if len(heldout) < int(protocol["data_contract"]["minimum_heldout_game_groups"]):
        errors.append("insufficient_heldout_game_groups")
    if len(set(binding.get("new_source_group_acquisition_receipts_sha256", []))) < len(heldout):
        errors.append("insufficient_new_source_receipts")
    for key in ("label_lock_sha256", "visual_window_manifest_sha256", "media_allowlist_sha256", "historic_vlm_input_media_lock_sha256", "redaction_policy_sha256"):
        if not _is_hash(binding.get(key)):
            errors.append(key)
    if binding.get("heldout_media_overlap_with_historic_vlm_inputs") is not False:
        errors.append("heldout_media_overlap_with_historic_vlm_inputs")
    if binding.get("input_manifest_excludes_ground_truth") is not True:
        errors.append("input_manifest_excludes_ground_truth")
    if binding.get("input_manifest_excludes_source_identity") is not True:
        errors.append("input_manifest_excludes_source_identity")
    if binding.get("test_model_calls_made") != 0:
        errors.append("test_model_calls_made")
    counts = binding.get("test_window_counts")
    if counts != protocol["data_contract"]["test_window_quotas"]:
        errors.append("test_window_counts")
    if not _is_hash(binding.get("test_window_ids_sha256")):
        errors.append("test_window_ids_sha256")
    if binding.get("private_labels_opened_for_sampling_only") is not True:
        errors.append("private_labels_opened_for_sampling_only")
    if binding.get("model_input_labels_used") is not False:
        errors.append("model_input_labels_used")
    if binding.get("full_frame_overlay_audit_status") != "pass":
        errors.append("full_frame_overlay_audit_status")
    if not isinstance(binding.get("full_frame_overlay_audited_sample_count"), int) or binding["full_frame_overlay_audited_sample_count"] < 6:
        errors.append("full_frame_overlay_audited_sample_count")
    if binding.get("local_model_endpoint_loopback_only") is not True:
        errors.append("local_model_endpoint_loopback_only")
    return errors


def protocol_errors(protocol: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if protocol.get("schema_version") != PROTOCOL_VERSION:
        errors.append("protocol_schema_version")
    if protocol.get("status") != "preregistered_template_no_model_calls":
        errors.append("protocol_status")
    if protocol.get("execution_gate", {}).get("model_calls_made") != 0:
        errors.append("model_calls_made_not_zero")
    if protocol.get("execution_gate", {}).get("root_authorization_required_after_review") is not True:
        errors.append("root_authorization_gate")
    if protocol.get("execution_gate", {}).get("this_package_permits_network_inference") is not False:
        errors.append("network_inference_must_be_disabled")
    if protocol.get("data_contract", {}).get("test_window_quotas") != DIAGNOSTIC_QUOTAS:
        errors.append("diagnostic_quotas")
    if protocol.get("data_contract", {}).get("heldout_groups_must_be_new_relative_to_all_prior_vlm_input_media") is not True:
        errors.append("fresh_heldout_groups")
    if protocol.get("visual_input_contract", {}).get("frame_offsets_seconds") != list(FRAME_OFFSETS_SECONDS):
        errors.append("frame_offsets")
    if not str(protocol.get("visual_input_contract", {}).get("private_redaction_gate", "")).strip():
        errors.append("full_frame_redaction_gate")
    stages = protocol.get("vlm_stages")
    if not isinstance(stages, list) or [stage.get("stage_id") for stage in stages] != ["proposal_a", "proposal_b", "evidence_audit"]:
        errors.append("vlm_stages")
    forbidden = protocol.get("scope", {}).get("deterministic_code_must_not", [])
    if "inspect pixels to classify an event" not in forbidden:
        errors.append("semantic_boundary")
    return errors


def preflight(protocol: Mapping[str, Any], binding: Mapping[str, Any] | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """Validate a template/binding without accessing a model, media, or labels."""

    p_errors = protocol_errors(protocol)
    b_errors = _binding_errors(binding, protocol) if binding is not None and not p_errors else ([] if binding is None else ["binding_not_checked_due_to_protocol_errors"])
    binding_contract_valid = not p_errors and binding is not None and not b_errors
    ready = binding_contract_valid and not dry_run
    return {
        "schema_version": "soccermaster-evidence-gated-preflight-receipt-v1",
        "generated_at": utc_now(),
        "status": "pass" if not p_errors and not b_errors else "fail",
        "mode": "synthetic_contract_dry_run" if dry_run else "template_or_private_binding_preflight",
        "protocol_sha256": sha256_bytes(canonical_json(protocol)),
        "private_binding_supplied": binding is not None,
        "private_binding_sha256": sha256_bytes(canonical_json(binding)) if binding is not None else None,
        "protocol_errors": p_errors,
        "binding_errors": b_errors,
        "binding_contract_valid": binding_contract_valid,
        "heldout_binding_ready": ready,
        "binding_is_synthetic": dry_run,
        "inference_permitted": False,
        "model_calls_made_by_this_command": 0,
        "media_or_labels_read_by_this_command": False,
        "execution_note": "No model-execution path exists in this package; a later reviewed executor must receive a root authorization receipt.",
        "claim_boundary": "Preflight validates protocol integrity only. It is not model quality, event accuracy, or coach-utility evidence.",
    }


def example_private_binding() -> dict[str, Any]:
    """Synthetic only: tests binding rules without naming or touching real media."""

    digest = lambda text: sha256_bytes(text.encode("utf-8"))
    return {
        "schema_version": PRIVATE_BINDING_VERSION,
        "status": "prepared_before_model_inference",
        "development_group_hashes": [digest("development-group-a"), digest("development-group-b")],
        "heldout_group_hashes": [digest("heldout-group-a"), digest("heldout-group-b")],
        "heldout_media_hashes": [digest("heldout-media-a"), digest("heldout-media-b"), digest("heldout-media-c"), digest("heldout-media-d")],
        "new_source_group_acquisition_receipts_sha256": [digest("new-source-receipt-a"), digest("new-source-receipt-b")],
        "label_lock_sha256": digest("private-label-lock"),
        "visual_window_manifest_sha256": digest("anonymous-window-manifest"),
        "media_allowlist_sha256": digest("private-media-allowlist"),
        "historic_vlm_input_media_lock_sha256": digest("all-historic-vlm-media-inputs"),
        "heldout_media_overlap_with_historic_vlm_inputs": False,
        "redaction_policy_sha256": digest("full-frame-overlay-redaction-policy"),
        "full_frame_overlay_audit_status": "pass",
        "full_frame_overlay_audited_sample_count": 6,
        "local_model_endpoint_loopback_only": True,
        "input_manifest_excludes_ground_truth": True,
        "input_manifest_excludes_source_identity": True,
        "model_input_labels_used": False,
        "private_labels_opened_for_sampling_only": True,
        "test_model_calls_made": 0,
        "test_window_counts": dict(DIAGNOSTIC_QUOTAS),
        "test_window_ids_sha256": digest("opaque-window-ids"),
    }


def dry_run(protocol_path: Path, output_path: Path) -> dict[str, Any]:
    protocol = read_json(protocol_path)
    receipt = preflight(protocol, example_private_binding(), dry_run=True)
    if receipt["status"] != "pass" or receipt["binding_contract_valid"] is not True or receipt["heldout_binding_ready"] is not False:
        raise ValueError("synthetic protocol dry run failed")
    write_json(output_path, receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    subparsers = value.add_subparsers(dest="command", required=True)
    make = subparsers.add_parser("write-preregistration")
    make.add_argument("--output", type=Path, default=DEFAULT_PROTOCOL_PATH)
    make.add_argument("--replace-unsealed", action="store_true")
    binding_schema = subparsers.add_parser("write-private-binding-schema")
    binding_schema.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_ROOT / "private-binding.schema.json")
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_ROOT / "dry-run-receipt.json")
    check = subparsers.add_parser("preflight")
    check.add_argument("--binding", type=Path)
    check.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_ROOT / "preflight-receipt.json")
    check.add_argument("--require-binding", action="store_true")
    return value


def _resolve(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    protocol_path = _resolve(project_root, args.protocol)
    if args.command == "write-preregistration":
        output = _resolve(project_root, args.output)
        result: Mapping[str, Any] = write_preregistration(output, replace_unsealed=args.replace_unsealed)
    elif args.command == "write-private-binding-schema":
        output = _resolve(project_root, args.output)
        result = write_private_binding_schema(output)
    elif args.command == "dry-run":
        output = _resolve(project_root, args.output)
        result = dry_run(protocol_path, output)
    elif args.command == "preflight":
        protocol = read_json(protocol_path)
        binding = read_json(_resolve(project_root, args.binding)) if args.binding else None
        if args.require_binding and binding is None:
            raise ValueError("--require-binding was set but no private binding was supplied")
        result = preflight(protocol, binding)
        output = _resolve(project_root, args.output)
        write_json(output, result)
        if result["status"] != "pass":
            raise ValueError("preflight failed")
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
