"""Tests for the separate v2 harder-cohort protocol guardrails."""

import copy
import importlib.util
import json
from pathlib import Path

import chess
import pytest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "chess_harder_cohort_protocol_v2", ROOT / "scripts/chess_harder_cohort_protocol_v2.py"
)
protocol_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol_module)


def write_base_manifest(tmp_path):
    path = tmp_path / "base-manifest.json"
    path.write_text(json.dumps({
        "schema": "chess-real-seed/v1",
        "items": [{
            "game_id": "old-game",
            "position_id": "old-position",
            "source_fen": chess.STARTING_FEN,
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        }],
    }), encoding="utf-8")
    return path


def valid_protocol(base_path):
    return {
        "schema": protocol_module.PROTOCOL_SCHEMA,
        "protocol_id": "higher-rated-game-disjoint-v2",
        "frozen_at": "2026-09-23T14:37:34Z",
        "source": {
            "canonical_url": protocol_module.LICHESS_PUZZLE_URL,
            "rights_url": protocol_module.LICHESS_RIGHTS_URL,
            "license": "CC0-1.0",
            "hash_algorithm": "sha256",
            "max_additional_compressed_bytes": 1024 * 1024,
            "full_archive": False,
        },
        "cohort": {
            "target_positions": 3,
            "rating_strata": [{"id": "2000-2399", "minimum": 2000, "maximum": 2399, "positions": 3}],
            "theme_strata": [{"theme": "fork", "minimum_positions": 1}],
        },
        "split": {"game_disjoint": True, "counts": {"train": 1, "dev": 1, "heldout": 1}, "heldout_sealed": True},
        "exclusion": {"v1_manifest_sha256": protocol_module.sha256_bytes(base_path.read_bytes())},
        "generator_contract": {
            "allowed_fields": ["fen"],
            "forbidden_fields": list(protocol_module.FORBIDDEN_GENERATOR_FIELDS),
        },
        "outcome_accounting": {
            "raw_outputs_retained": True,
            "abstentions_retained": True,
            "legal_replay_required": True,
            "independent_evaluation_required": True,
            "no_engine_or_model_before_freeze": True,
        },
    }


def item(position_id, game_id, source_fen, move_uci, split):
    board = chess.Board(source_fen)
    move = chess.Move.from_uci(move_uci)
    assert move in board.legal_moves
    board.push(move)
    return {
        "position_id": position_id,
        "game_id": game_id,
        "source_fen": source_fen,
        "fen": board.fen(),
        "setup_move": move_uci,
        "legal_replay": [{"before": source_fen, "uci": move_uci, "after": board.fen()}],
        "split": split,
    }


def staged_manifest(protocol):
    first_source = "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1"
    first = item("new-position-1", "new-game-1", first_source, "e7e5", "train")
    second_source = first["fen"]
    second = item("new-position-2", "new-game-2", second_source, "g1f3", "dev")
    third_source = second["fen"]
    third = item("new-position-3", "new-game-3", third_source, "b8c6", "heldout")
    return {
        "schema": protocol_module.COHORT_SCHEMA,
        "protocol_sha256": protocol_module.sha256_json(protocol),
        "acquisition": {
            "canonical_url": protocol_module.LICHESS_PUZZLE_URL,
            "rights_url": protocol_module.LICHESS_RIGHTS_URL,
            "license": "CC0-1.0",
            "retrieved_at": "2026-09-23T15:00:00Z",
            "source_page_sha256": "1" * 64,
            "prefix_sha256": "2" * 64,
            "compressed_bytes": 4096,
            "full_archive": False,
        },
        "strata_audit_sha256": "0" * 64,
        "items": [first, second, third],
    }


def strata_audit(protocol, manifest):
    return {
        "schema": protocol_module.STRATA_AUDIT_SCHEMA,
        "protocol_sha256": protocol_module.sha256_json(protocol),
        "cohort_payload_sha256": protocol_module.sha256_json(
            protocol_module._staged_manifest_payload(manifest)
        ),
        "sealed_at": "2026-09-23T15:00:01Z",
        "exposure": "evaluator-only",
        "entries": [
            {"position_id": "new-position-1", "rating": 2200, "themes": ["fork"]},
            {"position_id": "new-position-2", "rating": 2201, "themes": ["fork"]},
            {"position_id": "new-position-3", "rating": 2202, "themes": ["fork"]},
        ],
    }


def bind_strata_audit(protocol, manifest):
    audit = strata_audit(protocol, manifest)
    manifest["strata_audit_sha256"] = protocol_module.sha256_json(audit)
    return audit


def rebind_strata_audit(manifest, audit):
    manifest["strata_audit_sha256"] = protocol_module.sha256_json(audit)


def test_valid_protocol_returns_only_redacted_preacquisition_summary(tmp_path):
    base = write_base_manifest(tmp_path)
    result = protocol_module.validate_protocol(valid_protocol(base), base)
    text = json.dumps(result, sort_keys=True)
    assert result["target_positions"] == 3
    assert result["gate_flags"] == {
        "acquisition_completed": False,
        "commentary_capability_passed": False,
        "heldout_evaluated": False,
    }
    assert "old-game" not in text and chess.STARTING_FEN not in text
    assert "solution" not in text and "engine_pv" not in text


@pytest.mark.parametrize("mutation, error", [
    (lambda value: value["source"].update({"max_additional_compressed_bytes": protocol_module.MAX_ADDITIONAL_COMPRESSED_BYTES + 1}), "protocol_compressed_budget_invalid"),
    (lambda value: value["cohort"].update({"target_positions": protocol_module.MAX_POSITIONS + 1}), "protocol_target_positions_invalid"),
    (lambda value: value["split"].update({"heldout_sealed": False}), "protocol_split_invalid"),
    (lambda value: value["generator_contract"].update({"allowed_fields": ["fen", "target_move"]}), "protocol_generator_contract_invalid"),
    (lambda value: value["outcome_accounting"].update({"raw_outputs_retained": False}), "protocol_outcome_accounting_invalid"),
])
def test_protocol_rejects_unfrozen_budget_split_leakage_or_accounting(tmp_path, mutation, error):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    mutation(protocol)
    with pytest.raises(ValueError, match=error):
        protocol_module.validate_protocol(protocol, base)


def test_protocol_requires_exact_rating_denominator_and_opaque_base_hash(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    protocol["cohort"]["rating_strata"][0]["positions"] = 2
    with pytest.raises(ValueError, match="protocol_rating_strata_do_not_cover_target"):
        protocol_module.validate_protocol(protocol, base)
    protocol = valid_protocol(base)
    protocol["exclusion"]["v1_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="base_manifest_hash_mismatch"):
        protocol_module.validate_protocol(protocol, base)


def test_protocol_rejects_overlapping_rating_strata(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    protocol["cohort"]["rating_strata"] = [
        {"id": "2000-2199", "minimum": 2000, "maximum": 2199, "positions": 1},
        {"id": "2100-2399", "minimum": 2100, "maximum": 2399, "positions": 2},
    ]
    with pytest.raises(ValueError, match="protocol_rating_strata_overlap"):
        protocol_module.validate_protocol(protocol, base)


def test_protocol_rejects_raw_exclusion_data_and_summary_is_create_only(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    protocol["exclusion"]["old_game_ids"] = ["old-game"]
    with pytest.raises(ValueError, match="protocol_exclusion_invalid"):
        protocol_module.validate_protocol(protocol, base)
    output = tmp_path / "summary.json"
    first = protocol_module.write_protocol_summary(output, valid_protocol(base), base)
    assert json.loads(output.read_text()) == first
    with pytest.raises(ValueError, match="protocol_summary_exists"):
        protocol_module.write_protocol_summary(output, valid_protocol(base), base)


def test_staged_manifest_is_game_position_fen_disjoint_and_legal(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    result = protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    assert result["item_count"] == 3
    assert result["split_counts"] == {"train": 1, "dev": 1, "heldout": 1}
    assert result["legal_replay_passed"] and result["base_exclusion_passed"]
    assert result["strata_audit_passed"] and result["acquisition_after_protocol_freeze"]
    assert result["gate_flags"]["heldout_evaluated"] is False
    text = json.dumps(result, sort_keys=True)
    assert "new-position" not in text and "2200" not in text and "fork" not in text


@pytest.mark.parametrize("mutation, error", [
    (lambda manifest: manifest["items"][0].update({"game_id": "old-game"}), "cohort_reuses_frozen_v1_position"),
    (lambda manifest: manifest["items"][1].update({"position_id": manifest["items"][0]["position_id"]}), "cohort_duplicates_internally"),
    (lambda manifest: manifest["items"][0]["legal_replay"].append(copy.deepcopy(manifest["items"][0]["legal_replay"][0])), "cohort_replay_must_not_include_future_moves"),
    (lambda manifest: manifest["items"][0].update({"target_move": "e2e4"}), "cohort_item_invalid"),
])
def test_staged_manifest_rejects_reuse_future_moves_and_answer_fields(tmp_path, mutation, error):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    mutation(manifest)
    with pytest.raises(ValueError, match=error):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)


def test_staged_manifest_binds_protocol_and_acquisition_budget(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    manifest["protocol_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="cohort_protocol_binding_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    manifest["acquisition"]["compressed_bytes"] = 2 * 1024 * 1024
    with pytest.raises(ValueError, match="cohort_acquisition_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)


@pytest.mark.parametrize("mutation, error", [
    (lambda audit: audit["entries"].pop(), "cohort_strata_audit_item_binding_invalid"),
    (lambda audit: audit["entries"].append(copy.deepcopy(audit["entries"][0])), "cohort_strata_audit_item_binding_invalid"),
    (lambda audit: audit["entries"][0].update({"rating": 1999}), "cohort_strata_rating_invalid"),
    (lambda audit: audit["entries"][0].update({"themes": ["pin"]}), "cohort_strata_theme_invalid"),
    (lambda audit: audit.update({"exposure": "generator"}), "cohort_strata_audit_invalid"),
    (lambda audit: audit["entries"][0].update({"solution": "e2e4"}), "cohort_strata_audit_invalid"),
])
def test_staged_manifest_requires_sealed_complete_evaluator_only_strata(tmp_path, mutation, error):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    mutation(audit)
    rebind_strata_audit(manifest, audit)
    with pytest.raises(ValueError, match=error):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)


def test_staged_manifest_binds_strata_and_requires_post_freeze_acquisition(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    audit["entries"][0]["rating"] = 2203
    with pytest.raises(ValueError, match="cohort_strata_audit_binding_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    manifest["acquisition"]["retrieved_at"] = protocol["frozen_at"]
    with pytest.raises(ValueError, match="cohort_acquisition_precedes_protocol_freeze"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    audit["sealed_at"] = manifest["acquisition"]["retrieved_at"]
    rebind_strata_audit(manifest, audit)
    with pytest.raises(ValueError, match="cohort_strata_audit_not_sealed_after_acquisition"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    manifest["acquisition"]["retrieved_at"] = "2099-01-01T00:00:00Z"
    audit = bind_strata_audit(protocol, manifest)
    with pytest.raises(ValueError, match="cohort_acquisition_after_validation"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    audit["sealed_at"] = "2099-01-01T00:00:00Z"
    rebind_strata_audit(manifest, audit)
    with pytest.raises(ValueError, match="cohort_strata_audit_after_validation"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)


def test_staged_manifest_commits_the_sidecar_to_its_current_payload(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    manifest["items"][0]["game_id"] = "new-game-replaced"
    with pytest.raises(ValueError, match="cohort_strata_audit_payload_binding_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    manifest["strata_audit_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="cohort_strata_audit_binding_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    audit["protocol_sha256"] = "0" * 64
    rebind_strata_audit(manifest, audit)
    with pytest.raises(ValueError, match="cohort_strata_audit_protocol_binding_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)


def test_staged_validation_receipt_is_create_only_and_redacted(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    receipt = tmp_path / "staged-validation.json"
    result = protocol_module.write_staged_validation(receipt, protocol, manifest, audit, base)
    assert json.loads(receipt.read_text()) == result
    assert result["cohort_manifest_sha256"] == protocol_module.sha256_json(manifest)
    text = receipt.read_text()
    assert "new-position" not in text and "2200" not in text and "fork" not in text
    with pytest.raises(ValueError, match="staged_validation_exists"):
        protocol_module.write_staged_validation(receipt, protocol, manifest, audit, base)


def test_staged_manifest_enforces_actual_rating_and_theme_denominators(tmp_path):
    base = write_base_manifest(tmp_path)
    protocol = valid_protocol(base)
    protocol["cohort"]["rating_strata"] = [
        {"id": "2000-2199", "minimum": 2000, "maximum": 2199, "positions": 1},
        {"id": "2200-2399", "minimum": 2200, "maximum": 2399, "positions": 2},
    ]
    protocol["cohort"]["theme_strata"][0]["minimum_positions"] = 3
    protocol["cohort"]["theme_strata"].append({"theme": "pin", "minimum_positions": 1})
    manifest = staged_manifest(protocol)
    audit = bind_strata_audit(protocol, manifest)
    with pytest.raises(ValueError, match="cohort_rating_strata_counts_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
    audit["entries"][0]["themes"] = ["pin"]
    audit["entries"][1]["rating"] = 2100
    rebind_strata_audit(manifest, audit)
    with pytest.raises(ValueError, match="cohort_theme_strata_counts_invalid"):
        protocol_module.validate_staged_manifest(protocol, manifest, audit, base)
