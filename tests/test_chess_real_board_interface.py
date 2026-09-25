import subprocess
import sys
from pathlib import Path

def test_chess_real_board_interface_runs(tmp_path):
    # Run the script with the real data directory
    result = subprocess.run([sys.executable, "scripts/chess_real_board_interface.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    # Check that at least one SVG file was created
    artifacts_dir = Path("artifacts/chess-boards")
    assert any(artifacts_dir.glob("*.svg")), "No SVG files generated"
