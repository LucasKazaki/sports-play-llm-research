"""Evidence-grounded soccer event report contract.

The report deliberately refuses player, formation, and tactical claims because
the scaled pilot does not supervise them.  Every populated claim records its
origin so retrieval cannot silently promote metadata to a learned result.
"""

from __future__ import annotations

from typing import Any

from .taxonomy import EVENT_DESCRIPTIONS, UNSUPPORTED_COACH_QUERIES


REPORT_SCHEMA_VERSION = "playground-soccermaster-event-report-v1"


def build_report(
    *, example: dict[str, Any], predicted_class: str, confidence: float,
    top_k: list[dict[str, Any]], abstention_threshold: float,
    model_generation: str,
) -> dict[str, Any]:
    abstained = confidence < abstention_threshold
    candidate_time = float(example["candidate_time_s"])
    start = float(example["window_start_s"])
    end = float(example["window_end_s"])
    if abstained:
        summary = (
            f"Abstained at {candidate_time:.1f}s: the learned soccer event head's top class "
            f"was {predicted_class} at {confidence:.3f}, below the validation-selected "
            f"threshold {abstention_threshold:.3f}."
        )
    else:
        summary = f"At candidate time {candidate_time:.1f}s, {EVENT_DESCRIPTIONS[predicted_class]}"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "example_id": example["example_id"],
        "game_id": example["game_id"],
        "split": example["split"],
        "model_generation": model_generation,
        "prediction": {
            "class_name": predicted_class,
            "confidence": confidence,
            "top_k": top_k,
            "abstained": abstained,
            "abstention_threshold": abstention_threshold,
            "abstention_reason": "top probability below validation-selected threshold" if abstained else None,
            "claim_origin": "learned_multiclass_visual_probe",
        },
        "temporal_evidence": {
            "candidate_time_s": candidate_time,
            "window_start_s": start,
            "window_end_s": end,
            "sampled_frame_times_s": [
                start + (index + 0.5) * (end - start) / 12.0 for index in range(12)
            ],
            "claim_origin": "deterministic_window_metadata",
            "warning": "The candidate time is label-centered during this evaluation; it is not a learned dense-spotting timestamp.",
        },
        "coach_report": {
            "summary": summary,
            "actor": None,
            "team": None,
            "field_location": None,
            "movement_or_trajectory": None,
            "tactical_context": None,
            "outcome_beyond_event_class": None,
            "unsupported_fields": list(UNSUPPORTED_COACH_QUERIES),
            "claim_origin": "deterministic_template_grounded_only_in_prediction_and_window",
        },
        "retrieval_document": {
            "text": (
                f"soccer candidate {candidate_time:.1f}s; predicted {predicted_class}; "
                f"confidence {confidence:.3f}; {'abstained' if abstained else 'accepted'}; "
                "player team location formation intent unavailable"
            ),
            "safe_for_player_specific_retrieval": False,
        },
        "input_contract": {
            "visual_only": True,
            "audio_used": False,
            "source_label_used_as_model_input": False,
            "player_identity_supervision": False,
        },
    }


def validate_report(report: dict[str, Any]) -> None:
    required = {
        "schema_version", "example_id", "game_id", "split", "model_generation",
        "prediction", "temporal_evidence", "coach_report", "retrieval_document", "input_contract",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise ValueError("soccer report has an unexpected schema")
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError("soccer report schema version mismatch")
    prediction = report["prediction"]
    if not 0.0 <= float(prediction["confidence"]) <= 1.0:
        raise ValueError("prediction confidence outside [0,1]")
    if report["input_contract"] != {
        "visual_only": True,
        "audio_used": False,
        "source_label_used_as_model_input": False,
        "player_identity_supervision": False,
    }:
        raise ValueError("soccer report violates the visual-only evidence boundary")
    coach = report["coach_report"]
    for key in ("actor", "team", "field_location", "movement_or_trajectory", "tactical_context", "outcome_beyond_event_class"):
        if coach.get(key) is not None:
            raise ValueError(f"unsupported coach-report field must remain null: {key}")

