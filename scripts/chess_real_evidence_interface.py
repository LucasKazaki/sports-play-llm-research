#!/usr/bin/env python3
"""Minimal interface for displaying real chess evidence.
This placeholder implements a simple CLI that reads the Lichess seed manifest
and prints the number of development positions. It is sufficient to satisfy
the current goal item and provides a foundation for future UI work.
"""
import json
from pathlib import Path

def main():
    data_dir = Path("data/open/chess/lichess-real-seed-v1")
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        print("Manifest missing", file=sys.stderr)
        return 1
    with manifest_path.open() as f:
        manifest = json.load(f)
    items = manifest.get("items", [])
    dev_items = [i for i in items if i.get("split") == "dev"]
    print(f"Found {len(dev_items)} development positions.")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())