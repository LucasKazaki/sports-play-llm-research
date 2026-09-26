"""Verify a frozen publication package's file identities; never promote it."""
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = "artifacts/soccermaster-publication-20260913/evidence-index-v1.json"

def verify(index_path):
    raw = json.loads(index_path.read_text(encoding="utf-8-sig"))
    if raw.get("schema_version") != "soccermaster-publication-evidence-index-v1":
        raise ValueError("unsupported index")
    seen, errors = set(), []
    for row in raw["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append("nonrelative path: " + str(relative))
            continue
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError:
            errors.append("path escapes project")
            continue
        if str(relative) in seen:
            errors.append("duplicate entry: " + str(relative))
        seen.add(str(relative))
        if not path.is_file():
            errors.append("missing: " + str(relative))
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != row["sha256"] or path.stat().st_size != row["bytes"]:
            errors.append("identity mismatch: " + str(relative))
    if not seen:
        errors.append("empty index")
    return {"integrity_passed": not errors, "entries": len(raw["files"]),
            "errors": errors, "scientific_validation": False,
            "promotion_authorized": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, default=ROOT / DEFAULT)
    args = p.parse_args()
    result = verify(args.index.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["integrity_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
