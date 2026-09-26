import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from prototype.chess_concept_schema_validator import validate_explanation, validate_manifest, validate_position

def packet():
    return {"schema_version":"position-evidence/v1","position_id":"p1","game_id":"g1","split":"train","fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","move_uci":"e2e4","legal_replay_hash":"0000000000000000000000000000000000000000000000000000000000000000","legal_board_verified":True,"source":{"source_id":"lichess-study-example","game_ref":"game-1","license":"CC0-1.0","rights_status":"verified"},"engine_evidence":[{"id":"best","move_uci":"e2e4","score_cp":20},{"id":"alt","move_uci":"d2d4","score_cp":12}],"commentary_evidence":[{"id":"note-1","source_ref":"rights-reviewed-note"}]}

class ChessConceptGateTests(unittest.TestCase):
    def test_valid_packet_and_grounded_explanation(self):
        p = packet()
        self.assertTrue(validate_position(p)["valid"])
        x = {"abstain":False,"verdict":"concept_explanation","confidence":0.72,"move_summary":"The move contests the center.","concepts":["center"],"primary_concepts":[{"concept":"center","claim":"It controls central squares.","evidence_refs":["best"]}],"engine_evidence_refs":["best"],"commentary_evidence_refs":["note-1"],"limitations":["Synthetic evidence only; no legal replay."]}
        self.assertTrue(validate_explanation(p, x)["valid"])
    def test_accepts_verified_us_public_domain_source_and_rejects_unverified_status(self):
        p = packet(); p["source"] = {"source_id":"gutenberg-blue-book-16377","game_ref":"game-1/ply-38","license":"public-domain-USA","rights_status":"verified"}
        self.assertTrue(validate_position(p)["valid"])
        p["source"]["rights_status"] = "unverified"
        self.assertIn("unverified_source_rights", validate_position(p)["errors"])

    def test_rejects_unstructured_nonabstaining_explanation(self):
        x = {"abstain":False,"confidence":0.72,"concepts":["center"],"engine_evidence_refs":["best"],"commentary_evidence_refs":[]}
        errors = validate_explanation(packet(), x)["errors"]
        self.assertIn("invalid_verdict", errors)
        self.assertIn("missing_move_summary", errors)
        self.assertIn("invalid_primary_concepts", errors)
        self.assertIn("invalid_limitations", errors)
    def test_rejects_unverified_board_and_malformed_fen(self):
        p = packet(); p["legal_board_verified"] = False; p["fen"] = "bad fen"
        errors = validate_position(p)["errors"]
        self.assertIn("legal_board_not_verified", errors); self.assertIn("invalid_fen_syntax", errors)
    def test_rejects_basic_invalid_board_states(self):
        p = packet(); p["fen"] = "8/8/8/8/8/8/8/8 w - - 0 1"
        self.assertIn("invalid_fen_board_state", validate_position(p)["errors"])
        p = packet(); p["fen"] = "8/8/8/8/8/8/4k3/4K3 w - - 0 1"
        self.assertIn("invalid_fen_board_state", validate_position(p)["errors"])
    def test_missing_engine_requires_abstention(self):
        p = packet(); p["engine_evidence"] = []
        x = {"abstain":False,"confidence":0.5,"concepts":["center"],"engine_evidence_refs":[],"commentary_evidence_refs":[]}
        self.assertIn("missing_engine_requires_abstention", validate_explanation(p, x)["errors"])
    def test_rejects_cross_attribution_and_manifest_leakage(self):
        p = packet()
        x = {"abstain":False,"confidence":0.5,"concepts":["center"],"engine_evidence_refs":["note-1"],"commentary_evidence_refs":[]}
        self.assertIn("invalid_engine_evidence_refs", validate_explanation(p, x)["errors"])
        q = packet(); q["position_id"] = "p2"; q["split"] = "test"
        errors = validate_manifest({"items":[p, q]})["errors"]
        self.assertIn("duplicate_position_transition", errors); self.assertIn("game_split_leakage:g1", errors)
    def test_schema_declares_evidence_contract(self):
        schema = json.loads((Path(__file__).parents[1] / "prototype" / "chess_concept.schema.json").read_text())
        self.assertIn("engine_evidence", schema["required"]); self.assertEqual(schema["properties"]["legal_board_verified"]["const"], True)
    def test_requires_legal_replay_binding(self):
        p = packet(); del p["legal_replay_hash"]
        self.assertIn("missing:legal_replay_hash", validate_position(p)["errors"])
        p = packet(); p["legal_replay_hash"] = "not-a-hash"
        self.assertIn("invalid_legal_replay_hash", validate_position(p)["errors"])
    def test_schema_requires_legal_replay_hash(self):
        schema = json.loads((Path(__file__).parents[1] / "prototype" / "chess_concept.schema.json").read_text())
        self.assertIn("legal_replay_hash", schema["required"])
        self.assertEqual(schema["properties"]["legal_replay_hash"]["pattern"], "^[0-9a-f]{64}$")
    def test_rejects_legacy_concept_vocabulary(self):
        x = {"abstain":False,"verdict":"concept_explanation","confidence":0.5,"move_summary":"Fixture only.","concepts":["activity"],"primary_concepts":[{"concept":"activity","claim":"Legacy value.","evidence_refs":["best"]}],"engine_evidence_refs":["best"],"commentary_evidence_refs":[],"limitations":["Synthetic fixture only."]}
        errors = validate_explanation(packet(), x)["errors"]
        self.assertIn("invalid_concepts", errors)
        self.assertIn("invalid_primary_concepts", errors)

    def test_valid_abstention_is_permitted_without_claim_fields(self):
        x = {"abstain":True,"verdict":"abstain","confidence":0.0,"concepts":[],"engine_evidence_refs":[],"commentary_evidence_refs":[]}
        self.assertTrue(validate_explanation(packet(), x)["valid"])
    def test_rejects_abstention_verdict_mismatch(self):
        x = {"abstain":True,"verdict":"concept_explanation","confidence":0.0,"concepts":[],"engine_evidence_refs":[],"commentary_evidence_refs":[]}
        self.assertIn("verdict_abstention_mismatch", validate_explanation(packet(), x)["errors"])

if __name__ == "__main__":
    unittest.main()
