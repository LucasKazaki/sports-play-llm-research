import subprocess, sys, os

def test_interface_runs():
    # Run the script and ensure it exits with 0
    result = subprocess.run([sys.executable, "scripts/chess_real_evidence_interface.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Non-zero exit: {result.stderr}"
    assert "Found" in result.stdout
