"""Offline tests for the chess-specialist model registry."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import chess_specialist_registry as registry


REGISTRY_PATH = ROOT / "research/chess-specialist-model-registry-v1.json"


def load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def model(document, model_id):
    return next(item for item in document["models"] if item["id"] == model_id)


def test_committed_registry_is_valid_and_keeps_general_route_as_control():
    document = load_registry()
    assert registry.validate_registry(document) == []
    current = model(document, "loops-cpu-gpt-oss-20b")
    assert current["chess_specialized"] is False
    assert current["production_eligibility"] == "control_only"
    assert all(
        item["production_eligibility"] != "production_candidate"
        for item in document["models"]
    )


def test_general_model_cannot_be_promoted_as_specialist_candidate():
    document = load_registry()
    current = model(document, "loops-cpu-gpt-oss-20b")
    current["production_eligibility"] = "benchmark_candidate"
    errors = registry.validate_registry(document)
    assert any("general-purpose" in error and "control_only" in error for error in errors)


def test_specialist_requires_chess_training_evidence_and_source():
    document = load_registry()
    candidate = model(document, "rook-lm-124m")
    candidate["source_url"] = None
    candidate["training_evidence"]["scope"] = "none_chess_specific"
    errors = registry.validate_registry(document)
    assert any("requires source_url" in error for error in errors)
    assert any("records no chess-specific training" in error for error in errors)


def test_upstream_claim_cannot_be_labeled_project_reproduced():
    document = load_registry()
    candidate = model(document, "rook-clf-9m")
    candidate["claimed_metrics"][0]["status"] = "project_reproduced"
    errors = registry.validate_registry(document)
    assert any("cannot be project_reproduced" in error for error in errors)


def test_production_candidate_requires_project_benchmark_and_resolved_license():
    document = load_registry()
    candidate = model(document, "rook-lm-124m")
    candidate["production_eligibility"] = "production_candidate"
    errors = registry.validate_registry(document)
    assert any("project_benchmarked" in error for error in errors)
    assert any("unresolved license_status" in error for error in errors)
    assert any("unverified weights" in error for error in errors)


def test_report_lists_control_and_pending_candidates():
    report = registry.render_markdown(load_registry())
    assert "General controls: **1**" in report
    assert "ROOK-LM-124M" in report
    assert "Existing local GPT-OSS 20B route" in report
    assert "No model is promoted by registry membership alone." in report


def test_duplicate_model_ids_are_rejected():
    document = load_registry()
    document["models"].append(copy.deepcopy(document["models"][0]))
    errors = registry.validate_registry(document)
    assert any("duplicates" in error for error in errors)


def test_render_refuses_invalid_registry():
    document = load_registry()
    document["schema"] = "wrong"
    with pytest.raises(ValueError, match="invalid registry"):
        registry.render_markdown(document)
