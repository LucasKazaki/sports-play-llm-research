import io, json, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from chess_concept_model import generate

def packet():
    return {"schema_version":"position-evidence/v1","position_id":"p1","game_id":"g1","split":"dev","fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","move_uci":"e2e4","legal_replay_hash":"0" * 64,"legal_board_verified":True,"source":{"source_id":"test","game_ref":"g1","license":"CC0-1.0","rights_status":"verified"},"engine_evidence":[{"id":"best","move_uci":"e2e4","score_cp":20},{"id":"alt","move_uci":"d2d4","score_cp":12}],"commentary_evidence":[]}

class ModelTests(unittest.TestCase):
    def test_accepts_valid_grounded_model_json(self):
        answer = {"abstain":False,"verdict":"concept_explanation","confidence":0.6,"concepts":["center"],"engine_evidence_refs":["best"],"commentary_evidence_refs":[],"move_summary":"The move contests the center.","primary_concepts":[{"concept":"center","claim":"The top candidate supports central control.","evidence_refs":["best"]}],"limitations":["Fixture evidence only."]}
        response = {"choices":[{"message":{"content":json.dumps(answer)}}]}
        result = generate(packet(), request_opener=lambda request, timeout: io.StringIO(json.dumps(response)))
        self.assertFalse(result["abstain"]); self.assertEqual(result["concepts"], ["center"])
    def test_rejects_invalid_model_json(self):
        response = {"choices":[{"message":{"content":"not json"}}]}
        result = generate(packet(), request_opener=lambda request, timeout: io.StringIO(json.dumps(response)))
        self.assertTrue(result["abstain"]); self.assertEqual(result["reason"], "local_model_response_unusable")
    def test_never_calls_model_for_invalid_position(self):
        value = packet(); value["legal_board_verified"] = False
        result = generate(value, request_opener=lambda request, timeout: self.fail("model should not be called"))
        self.assertTrue(result["abstain"]); self.assertEqual(result["reason"], "invalid_position_evidence")
    def test_reports_shape_for_invalid_primary_concepts(self):
        answer = {"abstain":False,"verdict":"concept_explanation","confidence":0.6,"concepts":["center"],"engine_evidence_refs":["best"],"commentary_evidence_refs":[],"move_summary":"The move contests the center.","primary_concepts":{"concept":"center"},"limitations":["Fixture evidence only."]}
        response = {"choices":[{"message":{"content":json.dumps(answer)}}]}
        result = generate(packet(), request_opener=lambda request, timeout: io.StringIO(json.dumps(response)))
        self.assertTrue(result["abstain"]); self.assertEqual(result["rejected_model_shape"]["primary_concepts_type"], "dict")

    def test_rejects_explicit_wrong_moving_piece_claim(self):
        value = packet(); value["fen"] = "r5rk/1ppqb1pp/2bpNp2/p3nP2/P3P3/2N3B1/1PP1Q1PP/3R1RK1 b - - 4 19"; value["move_uci"] = "e5f7"
        answer = {"abstain":False,"verdict":"concept_explanation","confidence":0.6,"concepts":["center"],"engine_evidence_refs":["best"],"commentary_evidence_refs":[],"move_summary":"The move e5f7 is advancing a pawn.","primary_concepts":[{"concept":"center","claim":"The top candidate supports central control.","evidence_refs":["best"]}],"limitations":["Fixture evidence only."]}
        response = {"choices":[{"message":{"content":json.dumps(answer)}}]}
        result = generate(value, request_opener=lambda request, timeout: io.StringIO(json.dumps(response)))
        self.assertTrue(result["abstain"]); self.assertEqual(result["reason"], "model_claim_conflicts_with_board")

    def test_package_import_supports_the_model_guard(self):
        result = subprocess.run([sys.executable, '-c', 'from prototype.chess_concept_model import generate; print(generate.__name__)'], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'generate')

    def test_marks_synthetic_fixture_as_not_engine_evidence(self):
        value = packet(); value["source"]["source_id"] = "synthetic-contract-fixture"
        answer = {"abstain":False,"verdict":"concept_explanation","confidence":0.6,"concepts":["center"],"engine_evidence_refs":["best"],"commentary_evidence_refs":[],"move_summary":"The move contests the center.","primary_concepts":[{"concept":"center","claim":"The candidate supports central control.","evidence_refs":["best"]}],"limitations":["Fixture evidence only."]}
        response = {"choices":[{"message":{"content":json.dumps(answer)}}]}
        result = generate(value, request_opener=lambda request, timeout: io.StringIO(json.dumps(response)))
        self.assertIn("Synthetic contract fixture: candidate references are not engine receipts.", result["limitations"])

if __name__ == "__main__": unittest.main()