"""Leakage-safe long-form SoccerNet VLM evaluation and retrieval."""

from .pipeline import (
    Window,
    bm25_search,
    build_dense_windows,
    prepare,
    verify_experiment,
)

__all__ = ["Window", "bm25_search", "build_dense_windows", "prepare", "verify_experiment"]
