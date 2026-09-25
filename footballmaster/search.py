"""Independent evaluation, index construction, and retrieval operations."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .pipeline import (
    PROJECT_ROOT,
    SPLITS,
    build_search_index,
    evaluate_predictions,
    load_examples,
    sha256_file,
    verify_run,
)
from .schema import SEARCH_RESULT_SCHEMA_VERSION, validate_model_card, validate_search_result


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_number} must be an object")
        rows.append(value)
    if not rows:
        raise ValueError(f"{path.name} contains no records")
    return rows


def evaluate_package(model_dir: Path, *, split: str = "test") -> dict[str, Any]:
    """Recompute one split directly from the sealed prediction records."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    model_dir = model_dir.resolve()
    verification = verify_run(model_dir)
    rows = [row for row in _jsonl(model_dir / "predictions.jsonl") if row.get("split") == split]
    if not rows:
        raise ValueError(f"no prediction records for split {split}")
    targets = np.array([int(row["source_target"]) for row in rows], dtype=int)
    predictions = np.array([int(row["predicted_value"]) for row in rows], dtype=int)
    metrics = evaluate_predictions(targets, predictions)
    recorded = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))[split]
    comparable = ("n_examples", "accuracy", "macro_f1", "balanced_accuracy", "confusion_matrix")
    mismatches = {key: {"recorded": recorded.get(key), "recomputed": metrics.get(key)}
                  for key in comparable if recorded.get(key) != metrics.get(key)}
    if mismatches:
        raise RuntimeError(f"recomputed evaluation differs from sealed metrics: {mismatches}")
    return {
        "schema_version": "footballmaster-evaluation-v1",
        "sport": "american_football",
        "model_dir": str(model_dir),
        "generation_id": verification["generation_id"],
        "split": split,
        "source_ids": sorted({str(row["source_id"]) for row in rows}),
        "metrics": metrics,
        "matches_sealed_metrics": True,
        "performance_claim_allowed": False,
    }


def build_index_from_package(
    model_dir: Path,
    output_dir: Path,
    *,
    examples_path: Path,
    source_manifest_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build a search index from hash-bound model outputs and football data only."""
    model_dir = model_dir.resolve()
    output_dir = output_dir.resolve()
    card_path = model_dir / "model-card.json"
    predictions_path = model_dir / "predictions.jsonl"
    if not card_path.is_file():
        raise FileNotFoundError(card_path)
    card = validate_model_card(json.loads(card_path.read_text(encoding="utf-8")))
    if card.get("predictions_sha256") != sha256_file(predictions_path):
        raise RuntimeError("prediction records do not match the model card")
    examples, audit = load_examples(
        examples_path, source_manifest_path, project_root=project_root, require_media=True
    )
    ordered = sorted(examples, key=lambda item: (SPLITS.index(item.split), item.source_id, item.clip_id))
    by_clip: dict[str, Mapping[str, Any]] = {}
    for row in _jsonl(predictions_path):
        clip_id = str(row.get("clip_id", ""))
        if not clip_id or clip_id in by_clip:
            raise ValueError("prediction clip identifiers must be non-empty and unique")
        by_clip[clip_id] = row
    expected_ids = {example.clip_id for example in ordered}
    if set(by_clip) != expected_ids:
        raise RuntimeError("predictions and audited examples do not have identical clip coverage")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = build_search_index(
        output_dir,
        ordered,
        [dict(by_clip[example.clip_id]) for example in ordered],
        model_card_sha256=sha256_file(card_path),
        examples_sha256=audit["examples_sha256"],
    )
    return {
        "schema_version": "footballmaster-index-build-v1",
        "sport": "american_football",
        "database": str(result["database"]),
        "index_plan": str(output_dir / "index-plan.json"),
        "window_count": result["plan"]["window_count"],
        "model_card_sha256": sha256_file(card_path),
        "predictions_sha256": sha256_file(predictions_path),
    }


def _fts_terms(query: str) -> list[str]:
    terms: list[str] = []
    for value in re.findall(r"[a-z0-9_]+", query.casefold()):
        if len(value) < 2:
            continue
        if value not in terms:
            terms.append(value)
    if not terms:
        raise ValueError("query must contain at least one searchable term")
    return terms[:24]


def _validate_index(connection: sqlite3.Connection) -> None:
    tables = {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}
    required = {"metadata", "windows", "events", "event_search"}
    missing = required - tables
    if missing:
        raise RuntimeError(f"index is missing required tables: {sorted(missing)}")
    sport = connection.execute("SELECT value FROM metadata WHERE key='sport'").fetchone()
    if sport is None or sport[0] != "american_football":
        raise RuntimeError("index sport must be american_football")


def search_index(index_path: Path, query: str, *, limit: int = 10) -> dict[str, Any]:
    """Run bounded full-text retrieval without importing application or other-sport code."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    index_path = index_path.resolve()
    if not index_path.is_file():
        raise FileNotFoundError(index_path)
    terms = _fts_terms(query)
    expression = " OR ".join(f'"{term}"' for term in terms)
    connection = sqlite3.connect(f"file:{index_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _validate_index(connection)
        rows = connection.execute(
            """
            SELECT e.event_id, e.window_id, e.primary_action, e.start_s, e.end_s,
                   e.confidence, e.report_json, w.clip_id, w.source_id, w.split,
                   w.media_path, bm25(event_search) AS lexical_score
            FROM event_search
            JOIN events e ON e.event_id = event_search.event_id
            JOIN windows w ON w.window_id = e.window_id
            WHERE event_search MATCH ?
            ORDER BY lexical_score, e.event_id
            LIMIT ?
            """,
            (expression, limit),
        ).fetchall()
    finally:
        connection.close()
    results: list[dict[str, Any]] = []
    for row in rows:
        report = json.loads(row["report_json"])
        results.append({
            "event_id": row["event_id"],
            "window_id": row["window_id"],
            "clip_id": row["clip_id"],
            "source_id": row["source_id"],
            "split": row["split"],
            "media_path": row["media_path"],
            "primary_action": row["primary_action"],
            "start_s": row["start_s"],
            "end_s": row["end_s"],
            "confidence": row["confidence"],
            "lexical_score": row["lexical_score"],
            "report": report,
        })
    output = {
        "schema_version": SEARCH_RESULT_SCHEMA_VERSION,
        "sport": "american_football",
        "query": query,
        "index": str(index_path),
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "count": len(results),
        "results": results,
    }
    return validate_search_result(output)
