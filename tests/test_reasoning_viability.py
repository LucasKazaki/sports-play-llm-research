import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import reasoning_viability as module


def _packet():
    evaluation = {
        "denominator": 50,
        "valid_response_count": 50,
        "exact_correct_count": 3,
        "exact_accuracy_counting_abstentions_and_failures_as_wrong": 0.06,
        "abstention_rate_over_valid": 0.48,
        "performance_claim_allowed": False,
        "detailed_claim_factuality_evaluated": False,
        "detailed_claims_safe_for_coach_search": False,
    }
    longform = {
        "window_denominator": 96,
        "valid_response_count": 96,
        "vlm_reported_event_count": 361,
        "detailed_claim_factuality_measured": False,
        "event_accuracy_measured_before_seal": False,
    }
    return module.build_evidence_packet(evaluation, longform)


def _decision(packet):
    return {
        "verdict": "systems_only",
        "supported_findings": ["The long-form local run produced 96 valid responses across 96 windows."],
        "blocked_claims": list(module.BLOCKED_CLAIMS),
        "next_experiment": "Run a held-out comparison with adjudicated factuality labels.",
        "evidence_checks": module.expected_checks(packet),
    }


def test_packet_preserves_measured_boundaries() -> None:
    packet = _packet()
    assert packet["fifty_clip_local_vlm"]["exact_accuracy"] == 0.06
    assert packet["ninety_six_window_local_vlm"]["valid_response_count"] == 96
    assert packet["soccer_master_boundary"]["official_checkpoint_locally_reproduced"] is False


def test_loopback_gate_rejects_remote_endpoint() -> None:
    module.ensure_loopback("http://127.0.0.1:1234/v1")
    try:
        module.ensure_loopback("https://example.com/v1")
    except ValueError as exc:
        assert "loopback-only" in str(exc)
    else:
        raise AssertionError("remote endpoint was not rejected")


def test_valid_decision_passes_frozen_checks() -> None:
    packet = _packet()
    assert module.validate_decision(_decision(packet), packet) == []


def test_inflated_verdict_and_changed_metric_fail() -> None:
    packet = _packet()
    decision = _decision(packet)
    decision["verdict"] = "coach_ready"
    decision["evidence_checks"]["fifty_clip_accuracy"] = 0.6
    failures = module.validate_decision(decision, packet)
    assert any("systems_only" in item for item in failures)
    assert any("exactly" in item for item in failures)


def test_longform_window_unit_is_semantically_checked() -> None:
    packet = _packet()
    decision = _decision(packet)
    decision["supported_findings"] = ["The model returned 96 valid responses across 96 clips."]
    failures = module.validate_decision(decision, packet)
    assert any("96 windows" in item for item in failures)


def test_response_parser_accepts_json_and_fenced_json() -> None:
    packet = _packet()
    encoded = json.dumps(_decision(packet))
    assert module.parse_response(encoded)["verdict"] == "systems_only"
    assert module.parse_response(f"```json\n{encoded}\n```")["verdict"] == "systems_only"


def test_prompt_names_every_required_blocked_claim() -> None:
    system, _ = module.prompts(_packet())
    for claim in module.BLOCKED_CLAIMS:
        assert system.count(claim) == 1


@pytest.mark.parametrize("key,replacement", [
    ("longform_factuality_measured", 0),
    ("official_checkpoint_reproduced", 0),
    ("longform_valid_responses", 96.0),
])
def test_equal_python_values_cannot_change_frozen_evidence_types(key, replacement):
    packet = _packet()
    decision = _decision(packet)
    decision["evidence_checks"][key] = replacement
    assert module.validate_decision(decision, packet)


@pytest.mark.parametrize("extra", [
    "The system reliably understands soccer semantics across 96 windows.",
    "All 96 windows prove that the official SoccerMaster checkpoint was reproduced.",
    "The run produced 960 events across 96 windows.",
])
def test_valid_counts_do_not_certify_additional_unsupported_prose(extra):
    packet = _packet()
    decision = _decision(packet)
    decision["supported_findings"].append(extra)
    assert module.validate_decision(decision, packet)


@pytest.mark.parametrize("extra", [{}, [], "coach_ready", "unknown_claim"])
def test_invalid_blocked_claim_members_return_failures_without_raising(extra):
    packet = _packet()
    decision = _decision(packet)
    decision["blocked_claims"].append(extra)
    assert module.validate_decision(decision, packet)
