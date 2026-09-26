"""Strict validators for FootballMaster-owned serialized boundaries."""

from __future__ import annotations

from typing import Any, Mapping


MODEL_CARD_SCHEMA_VERSION = "footballmaster-pilot-model-card-v1"
SEARCH_RESULT_SCHEMA_VERSION = "footballmaster-search-result-v1"
ARCHITECTURE_SCOPE = "football_only"


def validate_model_card(card: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "generation_id", "model_name", "sport", "architecture_scope",
        "actual_trained_parameters", "checkpoint_sha256", "config_sha256", "metrics_sha256",
        "predictions_sha256", "training_log_sha256", "evaluated_target", "limitations",
        "intended_use", "prohibited_claims",
    }
    missing = required - set(card)
    if missing:
        raise ValueError(f"model card is missing required fields: {sorted(missing)}")
    if card.get("schema_version") != MODEL_CARD_SCHEMA_VERSION:
        raise ValueError("unsupported model-card schema")
    if card.get("sport") != "american_football":
        raise ValueError("model-card sport must be american_football")
    if card.get("architecture_scope") != ARCHITECTURE_SCOPE:
        raise ValueError("model-card architecture_scope must be football_only")
    if card.get("actual_trained_parameters") is not True:
        raise ValueError("model card must identify actually trained parameters")
    return dict(card)


def validate_search_result(result: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "sport", "query", "index", "count", "results"}
    missing = required - set(result)
    if missing:
        raise ValueError(f"search result is missing required fields: {sorted(missing)}")
    if result.get("schema_version") != SEARCH_RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported search-result schema")
    if result.get("sport") != "american_football":
        raise ValueError("search-result sport must be american_football")
    if not isinstance(result.get("results"), list) or result.get("count") != len(result["results"]):
        raise ValueError("search-result count must match results")
    return dict(result)
