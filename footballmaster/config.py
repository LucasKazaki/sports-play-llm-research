"""FootballMaster-owned configuration and immutable ontology defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FootballConfig:
    sport: str
    target_name: str
    target_classes: tuple[str, str]
    positive_fine_labels: frozenset[str]
    negative_fine_labels: frozenset[str]
    splits: tuple[str, str, str]
    rights_allowed: str
    frame_count: int
    pca_components: int
    epochs: int
    learning_rate: float
    l2: float

    @property
    def supported_fine_labels(self) -> frozenset[str]:
        return self.positive_fine_labels | self.negative_fine_labels


FOOTBALL_CONFIG = FootballConfig(
    sport="american_football",
    target_name="is_touchdown",
    target_classes=("not_touchdown", "touchdown"),
    positive_fine_labels=frozenset({"touchdown_pass", "rushing_touchdown"}),
    negative_fine_labels=frozenset({"kickoff_return", "field_goal_attempt", "interception_practice"}),
    splits=("train", "valid", "test"),
    rights_allowed="approved_for_local_research",
    frame_count=8,
    pca_components=16,
    epochs=500,
    learning_rate=0.05,
    l2=0.1,
)


def _require_number(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return result


def load_config(path: Path | None = None) -> FootballConfig:
    """Load a strict FootballMaster configuration without accepting foreign fields."""
    if path is None:
        return FOOTBALL_CONFIG
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration must be a JSON object")
    allowed = {
        "schema_version", "sport", "target_name", "target_classes", "positive_fine_labels",
        "negative_fine_labels", "splits", "rights_allowed", "frame_count", "pca_components",
        "epochs", "learning_rate", "l2",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unsupported configuration fields: {sorted(unknown)}")
    if raw.get("schema_version") != "footballmaster-config-v1":
        raise ValueError("unsupported configuration schema")
    if raw.get("sport") != "american_football":
        raise ValueError("configuration sport must be american_football")
    if raw.get("target_name") != FOOTBALL_CONFIG.target_name:
        raise ValueError("target_name must preserve the configured FootballMaster task")
    classes = tuple(raw.get("target_classes", ()))
    if classes != ("not_touchdown", "touchdown"):
        raise ValueError("target_classes must preserve the binary touchdown contract")
    splits = tuple(raw.get("splits", ()))
    if splits != ("train", "valid", "test"):
        raise ValueError("splits must be train, valid, test")
    positives = frozenset(raw.get("positive_fine_labels", ()))
    negatives = frozenset(raw.get("negative_fine_labels", ()))
    if not positives or not negatives or positives & negatives:
        raise ValueError("fine-label target sets must be non-empty and disjoint")
    if positives != FOOTBALL_CONFIG.positive_fine_labels or negatives != FOOTBALL_CONFIG.negative_fine_labels:
        raise ValueError("fine-label sets are immutable in this model version")
    if raw.get("rights_allowed") != FOOTBALL_CONFIG.rights_allowed:
        raise ValueError("rights_allowed cannot weaken the local-research gate")
    frame_count = int(_require_number(raw.get("frame_count"), "frame_count", minimum=2))
    if frame_count > 64:
        raise ValueError("frame_count must be at most 64")
    return FootballConfig(
        sport="american_football",
        target_name=FOOTBALL_CONFIG.target_name,
        target_classes=(classes[0], classes[1]),
        positive_fine_labels=positives,
        negative_fine_labels=negatives,
        splits=(splits[0], splits[1], splits[2]),
        rights_allowed=FOOTBALL_CONFIG.rights_allowed,
        frame_count=frame_count,
        pca_components=int(_require_number(raw.get("pca_components"), "pca_components", minimum=1)),
        epochs=int(_require_number(raw.get("epochs"), "epochs", minimum=1)),
        learning_rate=_require_number(raw.get("learning_rate"), "learning_rate", minimum=0.0),
        l2=_require_number(raw.get("l2"), "l2", minimum=0.0),
    )
