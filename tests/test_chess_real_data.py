"""Real-source provenance, legal transitions, leakage and score regressions."""
import copy
import importlib.util
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import chess
import chess.engine
import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("chess_real_data", ROOT / "scripts/chess_real_data.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
DATA = ROOT / "data/open/chess/lichess-real-seed-v1"


def test_real_sample_is_source_bound_legal_and_game_disjoint():
    result = pipeline.verify(DATA)
    assert result["real_games"] == 24
    assert result["replayed_plies"] == 122
    assert result["split_counts"] == {"train": 8, "dev": 8, "test": 8}
    assert result["synthetic_items"] == result["test_outcomes_scored"] == 0


def test_puzzle_setup_move_is_not_mistaken_for_the_solution():
    manifest = json.loads((DATA / "manifest.json").read_text())
    item = manifest["items"][0]
    source = chess.Board(item["source_fen"])
    source.push_uci(item["setup_move"])
    assert source.fen() == item["fen"]
    assert source.turn != chess.Board(item["source_fen"]).turn
    assert chess.Move.from_uci(item["target_move"]) in source.legal_moves


@pytest.mark.parametrize("name", ["source-page.html", "source-prefix.csv.zst.part", "sample.csv"])
def test_tampered_source_bytes_are_rejected(tmp_path, name):
    shutil.copytree(DATA, tmp_path / "data")
    path = tmp_path / "data" / name
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        pipeline.verify(tmp_path / "data")


@pytest.mark.parametrize("field,value", [("split", "dev"), ("target_move", "a1a8"), ("game_id", "fakegame")])
def test_manifest_cannot_invent_moves_games_or_reassign_holdout(tmp_path, field, value):
    shutil.copytree(DATA, tmp_path / "data")
    path = tmp_path / "data/manifest.json"
    manifest = json.loads(path.read_text())
    target = next(item for item in manifest["items"] if item["split"] == "test")
    target[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="does_not_match_legal_source_replay"):
        pipeline.verify(tmp_path / "data")


def test_illegal_move_never_gets_a_factual_description():
    with pytest.raises(ValueError, match="illegal_candidate_move"):
        pipeline.transition_facts(chess.STARTING_FEN, "e2e5")


def test_en_passant_description_is_a_capture_despite_empty_destination():
    facts = pipeline.transition_facts("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6")
    assert facts["capture"] and facts["en_passant"]
    assert not facts["gives_check"]
    assert chess.Board(facts["fen_after"]).piece_at(chess.D5) is None


def test_castling_moves_both_pieces_and_does_not_invent_capture():
    facts = pipeline.transition_facts("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1")
    assert facts["castling"] and not facts["capture"]
    assert chess.Board(facts["fen_after"]).piece_at(chess.F1).piece_type == chess.ROOK


def test_mate_is_not_reported_as_centipawn_score_and_black_pov_is_preserved():
    class FakeEngine:
        def analyse(self, board, limit, game):
            return {"pv": [chess.Move.from_uci("e7e5")],
                    "score": chess.engine.PovScore(chess.engine.Mate(3), chess.BLACK)}
    board = chess.Board()
    board.push_uci("e2e4")
    result = pipeline.engine_result(FakeEngine(), board, 10000, object())
    assert result["score_cp"] is None
    assert result["mate_in"] == 3
    assert result["score_perspective"] == "side_to_move"


def test_engine_inputs_exclude_labels_and_test_positions_and_failures_keep_denominator(tmp_path):
    observed = []
    class FakeEngine:
        id = {"name": "explicit test double"}
        def configure(self, options): pass
        def analyse(self, board, limit, game):
            observed.append(board.fen())
            raise TimeoutError("deliberate test failure")
        def quit(self): pass
    with patch.object(chess.engine.SimpleEngine, "popen_uci", return_value=FakeEngine()):
        result = pipeline.baseline(DATA, Path(__file__), tmp_path / "receipt.json")
    manifest = json.loads((DATA / "manifest.json").read_text())
    allowed = {item["fen"] for item in manifest["items"] if item["split"] == "dev"}
    assert len(observed) == 1 and set(observed).issubset(allowed)
    for row in result["summary"].values():
        assert row == {"requested": 8, "completed": 0, "accepted_solution": 0, "exact_solution_match": 0}
    assert result["test_outcomes_scored"] == 0


def test_existing_baseline_is_never_overwritten(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text("keep")
    with pytest.raises(ValueError, match="baseline_output_exists"):
        pipeline.baseline(DATA, Path(__file__), path)
    assert path.read_text() == "keep"
