import json, subprocess, sys, tempfile, threading, unittest
from pathlib import Path
from urllib.request import urlopen
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from chess_concept_demo import make_preview_server
DEMO = ROOT / "prototype" / "chess_concept_demo.py"
FIXTURE = ROOT / "demo" / "chessconcept-evidence-only-fixture-v1.json"

def packet():
    return {"schema_version":"position-evidence/v1","position_id":"demo-1","game_id":"demo-game","split":"dev","fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","move_uci":"e2e4","legal_replay_hash":"0000000000000000000000000000000000000000000000000000000000000000","legal_board_verified":True,"source":{"source_id":"cc0-fixture","game_ref":"fixture","license":"CC0-1.0","rights_status":"verified"},"engine_evidence":[{"id":"best","move_uci":"e2e4","score_cp":20},{"id":"alt","move_uci":"d2d4","score_cp":12}],"commentary_evidence":[{"id":"note","source_ref":"not-ingested"}]}

class ChessConceptDemoTests(unittest.TestCase):
    def run_demo(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.json"; path.write_text(json.dumps(value), encoding="utf-8")
            return subprocess.run([sys.executable, str(DEMO), "--packet", str(path)], cwd=ROOT, text=True, capture_output=True)
    def test_valid_packet_is_evidence_only_abstention(self):
        result = self.run_demo(packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["verdict"], "abstain")
        self.assertEqual(output["reason"], "local_generator_not_configured")
        self.assertEqual(output["engine_candidates"][0]["id"], "best")
        self.assertEqual(len(output["board_before"]), 8)
        self.assertIn("not a human explanation", output["limitations"][1])
    def test_cli_abstention_payload_conforms_to_explanation_contract(self):
        from prototype.chess_concept_schema_validator import validate_explanation
        result = self.run_demo(packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(validate_explanation(packet(), json.loads(result.stdout))["valid"])
    def test_invalid_board_evidence_is_rejected(self):
        value = packet(); value["legal_board_verified"] = False
        result = self.run_demo(value)
        self.assertEqual(result.returncode, 2)
        self.assertIn("legal_board_not_verified", json.loads(result.stdout)["validation_errors"])
    def test_loopback_preview_serves_only_fixed_local_packet(self):
        server = make_preview_server(packet(), "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            with urlopen("http://127.0.0.1:%d/api/review" % server.server_port, timeout=3) as response:
                body = json.loads(response.read())
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(body["reason"], "local_generator_not_configured")
        finally:
            server.shutdown(); thread.join(timeout=3); server.server_close()
    def test_preview_rejects_non_loopback_host(self):
        with self.assertRaises(ValueError): make_preview_server(packet(), "0.0.0.0", 0)
    def test_packaged_fixture_fails_closed(self):
        result = subprocess.run([sys.executable, str(DEMO), "--packet", str(FIXTURE)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["reason"], "invalid_position_evidence")

    def test_readiness_command_is_finite_and_safe(self):
        result = subprocess.run([sys.executable, str(DEMO), "--packet", str(FIXTURE), "--readiness"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertTrue(status["ready"])
        self.assertEqual(status["scope"], "loopback-only")
        self.assertTrue(status["safe_abstention"])
        self.assertEqual(status["review_reason"], "invalid_position_evidence")

    def test_cli_preview_serves_loopback_health_and_stops(self):
        socket = __import__("socket"); time = __import__("time")
        probe = socket.socket(); probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]; probe.close()
        process = subprocess.Popen([sys.executable, str(DEMO), "--packet", str(FIXTURE), "--serve", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            health = None
            for _ in range(20):
                try:
                    with urlopen("http://127.0.0.1:%d/health" % port, timeout=0.5) as response:
                        health = json.loads(response.read())
                    break
                except OSError:
                    time.sleep(0.1)
            self.assertEqual(health, {"status": "ok", "scope": "loopback-only"})
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()

if __name__ == "__main__":
    unittest.main()