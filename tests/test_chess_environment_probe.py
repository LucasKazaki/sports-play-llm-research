import json, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from chess_environment_probe import EXECUTABLES, MODULES, probe

class ChessEnvironmentProbeTests(unittest.TestCase):
    def test_probe_is_structured_and_local(self):
        result = probe()
        self.assertEqual(result["schema_version"], "chess-environment-probe/v1")
        self.assertEqual(set(result["modules"]), set(MODULES))
        self.assertEqual(set(result["executables"]), set(EXECUTABLES))
        self.assertIsInstance(result["engine_ready"], bool)
    def test_cli_emits_json(self):
        run = subprocess.run([sys.executable, str(ROOT / "prototype" / "chess_environment_probe.py")], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["python"], sys.executable)

if __name__ == "__main__":
    unittest.main()
