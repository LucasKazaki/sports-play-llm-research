#!/usr/bin/env python3
"""Simple CLI to display real chess boards from the Lichess seed manifest.

This script loads the manifest JSON, iterates over the items and prints an SVG board for each position.
It is intentionally minimal: it does not modify any existing logic, only provides a useful local view.
"""
import json
from pathlib import Path
import chess
import chess.svg

MANIFEST_PATH = Path("data/open/chess/lichess-real-seed-v1/manifest.json")
OUTPUT_DIR = Path("artifacts/chess-boards")


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for item in manifest.get("items", []):
        fen = item["fen"]
        board = chess.Board(fen)
        svg_path = OUTPUT_DIR / f"{item['position_id']}.svg"
        svg_path.write_text(chess.svg.board(board, size=300), encoding="utf-8")
    print(f"Generated {len(manifest.get('items', []))} board SVGs in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
