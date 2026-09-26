"""Command-line interface for the independent FootballMaster pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import FOOTBALL_CONFIG, load_config
from .pipeline import (
    DEFAULT_BACKBONE,
    DEFAULT_BACKBONE_URL,
    DEFAULT_EXAMPLES,
    DEFAULT_SOURCES,
    PROJECT_ROOT,
    _atomic_json,
    acquire_backbone,
    load_examples,
    predict_video,
    train_pipeline,
    verify_run,
)
from .search import build_index_from_package, evaluate_package, search_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="footballmaster",
        description="Standalone American-football video training, evaluation, indexing, and retrieval.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    acquire = sub.add_parser("acquire-backbone", help="Acquire the public frozen visual backbone.")
    acquire.add_argument("--out", type=Path, default=DEFAULT_BACKBONE)
    acquire.add_argument("--url", default=DEFAULT_BACKBONE_URL)
    acquire.add_argument("--expected-sha256")

    audit = sub.add_parser("audit-data", help="Validate schema, rights, hashes, and source-disjoint splits.")
    audit.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    audit.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    audit.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    audit.add_argument("--no-media", action="store_true")

    train = sub.add_parser("train", help="Train and seal an American-football visual probe package.")
    train.add_argument("--config", type=Path)
    train.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    train.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    train.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    train.add_argument("--out", type=Path, required=True)
    train.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    train.add_argument("--frames", type=int)
    train.add_argument("--pca-components", type=int)
    train.add_argument("--epochs", type=int)
    train.add_argument("--learning-rate", type=float)
    train.add_argument("--l2", type=float)
    train.add_argument("--replace", action="store_true")

    evaluate = sub.add_parser("evaluate", help="Recompute a sealed split from prediction records.")
    evaluate.add_argument("--model-dir", type=Path, required=True)
    evaluate.add_argument("--split", choices=FOOTBALL_CONFIG.splits, default="test")

    index = sub.add_parser("build-index", help="Build a standalone full-text index from a trained package.")
    index.add_argument("--model-dir", type=Path, required=True)
    index.add_argument("--out", type=Path, required=True)
    index.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    index.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    index.add_argument("--project-root", type=Path, default=PROJECT_ROOT)

    search = sub.add_parser("search", help="Search a FootballMaster SQLite index.")
    search.add_argument("--index", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)

    predict = sub.add_parser("predict", help="Run the trained coarse probe on one local clip.")
    predict.add_argument("--model-dir", type=Path, required=True)
    predict.add_argument("--video", type=Path, required=True)
    predict.add_argument("--clip-id", required=True)
    predict.add_argument("--expected-sha256")
    predict.add_argument("--backbone", type=Path)
    predict.add_argument("--out", type=Path)

    verify = sub.add_parser("verify", help="Verify all package hashes and structural gates.")
    verify.add_argument("--model-dir", type=Path, required=True)
    return parser


def _serializable_training(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "output_dir": str(result["output_dir"]),
        "backup": None if result["backup"] is None else str(result["backup"]),
        "checkpoint": str(result["checkpoint"]),
        "search_index": str(result["search_index"]),
        "run_receipt": str(result["run_receipt"]),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "acquire-backbone":
        return acquire_backbone(args.out, url=args.url, expected_sha256=args.expected_sha256)
    if args.command == "audit-data":
        _, audit = load_examples(
            args.examples, args.sources, project_root=args.project_root, require_media=not args.no_media
        )
        return audit
    if args.command == "train":
        config = load_config(args.config)
        return _serializable_training(train_pipeline(
            examples_path=args.examples,
            source_manifest_path=args.sources,
            backbone_path=args.backbone,
            output_dir=args.out,
            frame_count=args.frames if args.frames is not None else config.frame_count,
            pca_components=args.pca_components if args.pca_components is not None else config.pca_components,
            epochs=args.epochs if args.epochs is not None else config.epochs,
            learning_rate=args.learning_rate if args.learning_rate is not None else config.learning_rate,
            l2=args.l2 if args.l2 is not None else config.l2,
            project_root=args.project_root,
            replace=args.replace,
        ))
    if args.command == "evaluate":
        return evaluate_package(args.model_dir, split=args.split)
    if args.command == "build-index":
        return build_index_from_package(
            args.model_dir, args.out, examples_path=args.examples, source_manifest_path=args.sources,
            project_root=args.project_root,
        )
    if args.command == "search":
        return search_index(args.index, args.query, limit=args.limit)
    if args.command == "predict":
        result = predict_video(
            args.model_dir, args.video, clip_id=args.clip_id,
            expected_sha256=args.expected_sha256, backbone_path=args.backbone,
        )
        if args.out:
            _atomic_json(args.out, result)
        return result
    return verify_run(args.model_dir)


def main(argv: list[str] | None = None) -> int:
    result = run(build_parser().parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0
