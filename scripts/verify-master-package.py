"""Finite native verification of the SoccerMaster master package.
No downloads, model calls, server left running, promotion, or reset application.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def frozen():
    base = ROOT / "artifacts/footballmaster/pilot-v1"
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p)
            for p in sorted(base.rglob("*")) if p.is_file()}

def dump(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")

def demo(output):
    sys.path.insert(0, str(ROOT / "prototype"))
    import multisport_search_demo_server as server_module
    from demo_readiness import rehearsal
    context = server_module.load_multisport_context(query_llm_enabled=False)
    server = server_module.build_server(context, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = rehearsal("http://127.0.0.1:" + str(server.server_address[1]), output / "demo")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    if thread.is_alive():
        raise RuntimeError("Finite demo server failed shutdown")
    print(json.dumps({"demo_passed": result["passed"], "checks": len(result["checks"]),
                      "failures": result["failures"], "visual_model_calls": 0,
                      "query_model_calls": 0, "server_closed": True}))
    return result["passed"]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--demo-only", action="store_true")
    args = parser.parse_args()
    output = args.out.resolve()
    output.relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    before = frozen()
    dump(output / "frozen-before.json", before)
    stages = []
    if not args.demo_only:
        ps = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        for name in ("doctor", "reproduce", "verify", "smoke-test", "collect-logs", "safe-reset"):
            command = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / ("scripts/" + name + ".ps1"))]
            started = datetime.now(timezone.utc).isoformat()
            with (output / (name + ".stdout.log")).open("xb") as stdout, (output / (name + ".stderr.log")).open("xb") as stderr:
                result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
            stages.append({"name": name, "argv": command, "exit_code": result.returncode,
                           "started_at": started,
                           "stdout_sha256": sha(output / (name + ".stdout.log")),
                           "stderr_sha256": sha(output / (name + ".stderr.log"))})
            print(json.dumps(stages[-1]), flush=True)
    try:
        demo_passed = demo(output)
        demo_error = None
    except Exception as error:
        demo_passed = False
        demo_error = type(error).__name__ + ": " + str(error)
    after = frozen()
    dump(output / "frozen-after.json", after)
    result = {"schema": "soccermaster-master-local-verification/v1",
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "python": sys.executable, "script_sha256": sha(Path(__file__)),
              "stages": stages, "demo_passed": demo_passed, "demo_error": demo_error,
              "frozen_file_count": len(before), "frozen_unchanged": before == after,
              "reset_applied": False, "scientific_validation": False,
              "performance_claim_allowed": False, "shareable_candidate_promoted": False,
              "passed": all(s["exit_code"] == 0 for s in stages) and demo_passed and before == after}
    dump(output / "verification.json", result)
    print(json.dumps(result), flush=True)
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
