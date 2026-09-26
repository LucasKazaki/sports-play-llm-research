"""Local-only dependency discovery for the Chess Concept Model."""
import importlib.metadata
import importlib.util
import json
import shutil
import sys

MODULES = ("chess", "stockfish")
EXECUTABLES = ("stockfish", "stockfish.exe")

def probe():
    modules = {name: importlib.util.find_spec(name) is not None for name in MODULES}
    executables = {name: shutil.which(name) for name in EXECUTABLES}
    distributions = sorted({str(d.metadata.get("Name", "")) for d in importlib.metadata.distributions() if "chess" in str(d.metadata.get("Name", "")).lower() or "stockfish" in str(d.metadata.get("Name", "")).lower()})
    return {
        "schema_version":"chess-environment-probe/v1",
        "python":sys.executable,
        "modules":modules,
        "executables":executables,
        "installed_chess_related_distributions":distributions,
        "engine_ready":bool(modules["chess"] and any(executables.values()))
    }

if __name__ == "__main__":
    print(json.dumps(probe(), sort_keys=True))
