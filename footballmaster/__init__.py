"""Standalone American-football video research package.

The package owns its data contract, target mapping, feature extraction,
training, evaluation, indexing, and retrieval implementation.  Integrations
with multi-sport applications must depend on the package's serialized artifact
contract rather than importing application code into this package.
"""

from .config import FOOTBALL_CONFIG, FootballConfig, load_config
from .pipeline import (
    DescriptorResult,
    Example,
    LearnedHead,
    Projection,
    TARGET_CLASSES,
    TARGET_NAME,
    acquire_backbone,
    build_search_index,
    evaluate_predictions,
    fit_projection,
    fit_softmax_head,
    load_examples,
    predict_video,
    target_from_labels,
    train_pipeline,
    verify_run,
)
from .search import build_index_from_package, evaluate_package, search_index

__all__ = [
    "FOOTBALL_CONFIG",
    "FootballConfig",
    "load_config",
    "DescriptorResult",
    "Example",
    "LearnedHead",
    "Projection",
    "TARGET_CLASSES",
    "TARGET_NAME",
    "acquire_backbone",
    "build_search_index",
    "evaluate_predictions",
    "fit_projection",
    "fit_softmax_head",
    "load_examples",
    "predict_video",
    "target_from_labels",
    "train_pipeline",
    "verify_run",
    "build_index_from_package",
    "evaluate_package",
    "search_index",
]
