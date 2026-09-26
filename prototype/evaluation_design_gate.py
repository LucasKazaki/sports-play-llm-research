"""Offline evaluation-design checks, never scientific or processing authorization."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone

SCHEMA = "playground-evaluation-design-v1"
REQUIRED_EVIDENCE = {"rights_scope", "annotation_protocol", "independent_review",
                    "adjudication_plan", "history_overlap_audit", "frozen_analysis_plan"}

def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key: " + key)
            out[key] = value
        return out
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))

def check_manifest(raw, root):
    root = Path(root).resolve()
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    def identity(value):
        return isinstance(value, str) and bool(value.strip()) and value == value.strip()
    def digest(value):
        return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None
    if not isinstance(raw, dict):
        raise ValueError("manifest must be an object")
    require(set(raw) == {"schema_version", "evidence_kind", "clips",
                         "development_group_ids", "evidence"}, "manifest keys differ")
    require(raw.get("schema_version") == SCHEMA, "unsupported schema")
    kind = raw.get("evidence_kind")
    require(kind in {"synthetic_fixture", "real_candidate"}, "unknown evidence kind")
    clips, development, evidence = (raw.get(k) for k in
                                   ("clips", "development_group_ids", "evidence"))
    if not isinstance(clips, list) or not isinstance(development, list) or not isinstance(evidence, dict):
        raise ValueError("clips/development_group_ids/evidence have invalid types")
    require(all(identity(g) for g in development), "invalid development group")
    dev = {g for g in development if identity(g)}
    require(len(dev) == len(development), "duplicate development group")
    ids, groups, hashes, test_groups, test_hashes = set(), {}, {}, set(), set()
    test_count = 0
    for i, clip in enumerate(clips):
        label = "clip[" + str(i) + "]"
        if not isinstance(clip, dict):
            errors.append(label + " must be an object")
            continue
        require(set(clip) == {"clip_id", "group_id", "source_sha256", "split"},
                label + " keys differ")
        cid, gid, sha, split = (clip.get(k) for k in
                                ("clip_id", "group_id", "source_sha256", "split"))
        if not identity(cid) or not identity(gid) or not digest(sha):
            errors.append(label + " invalid identity/digest")
            continue
        require(cid not in ids, "duplicate clip ID: " + cid)
        ids.add(cid)
        require(split in {"development", "validation", "test"}, label + " invalid split")
        if split not in {"development", "validation", "test"}:
            continue
        if gid in groups:
            require(groups[gid] == split, "group crosses splits: " + gid)
        groups[gid] = split
        if sha in hashes:
            require(hashes[sha] == split, "source bytes cross splits: " + cid)
        hashes[sha] = split
        if split == "test":
            require(sha not in test_hashes, "duplicate test input bytes: " + cid)
            test_hashes.add(sha)
            test_count += 1
            test_groups.add(gid)
            require(gid not in dev, "test group exposed during development: " + gid)
    require(6 <= test_count <= 15, "benchmark requires 6-15 test clips")
    require(bool(test_groups), "no test source groups")
    require(set(evidence) == REQUIRED_EVIDENCE, "required evidence roles differ")
    bound = []
    for role in sorted(REQUIRED_EVIDENCE):
        item = evidence.get(role)
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            errors.append("missing or malformed evidence: " + role)
            continue
        path, expected = item["path"], item["sha256"]
        if not identity(path) or not digest(expected):
            errors.append("invalid evidence binding: " + role)
            continue
        supplied = Path(path)
        if supplied.is_absolute() or ".." in supplied.parts or ":" in path or "\\" in path:
            errors.append("evidence path must be portable relative: " + role)
            continue
        target = (root / supplied).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append("evidence escapes root: " + role)
            continue
        if not target.is_file():
            errors.append("evidence missing: " + role)
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        require(actual == expected, "evidence digest mismatch: " + role)
        bound.append({"role": role, "path": path, "sha256": actual})
    return {
        "schema_version": "playground-evaluation-design-check-v1",
        "status": "PASS_STRUCTURAL_ONLY" if not errors else "BLOCKED",
        "errors": errors, "test_clips": test_count,
        "test_groups": len(test_groups), "evidence_kind": kind,
        "bindings": bound,
        "scientific_validation": False, "processing_authorized": False,
        "annotation_independence_verified": False,
        "limitations": [
            "Declared groups require an independently checked match/derivative/history mapping.",
            "Evidence hashes bind bytes, not authenticity, adequacy, consent or reviewer independence.",
            "Six to fifteen clips are a feasibility study, not a powered population benchmark.",
            "No source media, annotation contents or model outputs are semantically evaluated.",
            "PASS_STRUCTURAL_ONLY never grants inference, rights, spending or publication."
        ]
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    content = args.manifest.read_bytes()
    result = check_manifest(strict_json(content.decode("utf-8-sig")), args.manifest.parent)
    result["manifest_sha256"] = hashlib.sha256(content).hexdigest()
    result["observed_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"]}))
    return 0 if result["status"] == "PASS_STRUCTURAL_ONLY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
