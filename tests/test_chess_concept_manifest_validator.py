import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from prototype.chess_concept_manifest_validator import validate_seed_manifest

H0 = "0" * 64
H1 = "1" * 64

def item():
    return {
        "position_id":"fixture-1", "game_id":"game-1", "split":"train",
        "source_url":"https://example.invalid/cc0-fixture.pgn",
        "license":"CC0-1.0", "rights_status":"verified",
        "retrieved_at":"2026-09-17T18:00:00Z", "source_bytes_sha256":H0,
        "fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "move_uci":"e2e4", "move_context":"1. e4",
        "transition_sha256":H0, "legal_replay_hash":H0,
    }

class SeedManifestTests(unittest.TestCase):
    def test_valid_synthetic_fixture(self):
        self.assertTrue(validate_seed_manifest({"schema_version":"chessconcept-seed-manifest/v1","items":[item()]})["valid"])
    def test_rejects_rights_and_unpinned_metadata(self):
        value = item(); value["license"] = "unknown"; value["retrieved_at"] = "today"
        errors = validate_seed_manifest({"schema_version":"chessconcept-seed-manifest/v1","items":[value]})["errors"]
        self.assertIn("item[0]:unverified_source_rights", errors)
        self.assertIn("item[0]:invalid_retrieval_timestamp", errors)
    def test_rejects_duplicate_transition_and_game_split_leakage(self):
        first = item(); second = item()
        second["position_id"] = "fixture-2"; second["split"] = "test"; second["transition_sha256"] = H1
        errors = validate_seed_manifest({"schema_version":"chessconcept-seed-manifest/v1","items":[first, second]})["errors"]
        self.assertIn("item[1]:duplicate_position_transition", errors)
        self.assertIn("item[1]:game_split_leakage:game-1", errors)
    def test_rejects_impossible_board_state(self):
        value = item(); value["fen"] = "8/8/8/8/8/8/8/8 w - - 0 1"
        self.assertIn("item[0]:invalid_fen_board_state", validate_seed_manifest({"schema_version":"chessconcept-seed-manifest/v1","items":[value]})["errors"])

if __name__ == "__main__":
    unittest.main()
