import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "footballmaster"

from footballmaster import (
    DescriptorResult,
    build_index_from_package,
    evaluate_package,
    search_index,
    train_pipeline,
)
from footballmaster.config import FOOTBALL_CONFIG, load_config


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixtureExtractor:
    identity = {
        "kind": "deterministic_test_fixture",
        "name": "football-only-fixture",
        "sha256": "b" * 64,
        "path": "",
        "trained_by_this_project": False,
    }

    def extract(self, video_path: Path, *, frame_count: int) -> DescriptorResult:
        positive = "positive" in video_path.stem
        sign = 1.0 if positive else -1.0
        descriptor = np.array(
            [sign, 0.7 * sign, 0.2, -0.4 * sign, 1.0, 0.3 * sign,
             -0.8 * sign, 0.6, 0.9 * sign, -0.1, 0.5 * sign, 0.05],
            dtype=float,
        )
        return DescriptorResult(
            descriptor=descriptor,
            sampled_frame_indices=tuple(range(frame_count)),
            sampled_frame_sha256=tuple(
                hashlib.sha256(f"{video_path.name}:{index}".encode()).hexdigest()
                for index in range(frame_count)
            ),
            decoded_fps=10.0,
            decoded_frame_count=10,
            decoded_duration_seconds=1.0,
            backbone_output_dimension=2,
        )


def _fixture(root: Path) -> tuple[Path, Path]:
    media_root = root / "data" / "public" / "footballmaster" / "media"
    media_root.mkdir(parents=True)
    rows = []
    assets = []
    specs = [
        ("train-positive-a", "train-pos-a", "train", "touchdown_pass", True),
        ("train-positive-b", "train-pos-b", "train", "rushing_touchdown", True),
        ("train-negative-a", "train-neg-a", "train", "kickoff_return", False),
        ("train-negative-b", "train-neg-b", "train", "field_goal_attempt", False),
        ("valid-positive", "valid-pos", "valid", "touchdown_pass", True),
        ("valid-negative", "valid-neg", "valid", "field_goal_attempt", False),
        ("test-positive", "test-pos", "test", "rushing_touchdown", True),
        ("test-negative", "test-neg", "test", "interception_practice", False),
    ]
    for ordinal, (clip_id, source_id, split, label, target) in enumerate(specs):
        media_path = media_root / f"{clip_id}.webm"
        media_path.write_bytes(f"football-only-fixture-{clip_id}".encode())
        relative = media_path.relative_to(root).as_posix()
        source_page = f"https://commons.wikimedia.org/wiki/File:{clip_id}.webm"
        asset = {
            "asset_id": clip_id,
            "source_id": source_id,
            "split": split,
            "fine_label": label,
            "is_touchdown": target,
            "canonical_page_url": source_page,
            "license_spdxish": "CC-BY-4.0",
            "license_name": "Creative Commons Attribution 4.0 International",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "creator": f"Fixture author {ordinal}",
            "creator_url": f"https://example.test/author/{ordinal}",
            "conditions": ["Attribution", "License link"],
            "project_relative_media_path": relative,
            "downloaded_sha256": _sha(media_path),
            "observed_duration_seconds": 1.0,
            "rights_disposition": "approved_for_local_research",
            "training_allowed": True,
            "redistribution_allowed": True,
        }
        assets.append(asset)
        rows.append({
            "clip_id": clip_id,
            "source_id": source_id,
            "split": split,
            "project_relative_media_path": relative,
            "sha256": _sha(media_path),
            "start_seconds": 0.0,
            "end_seconds": 1.0,
            "duration_seconds": 1.0,
            "labels": [label],
            "label_provenance": "source_description_weak_label",
            "adjudication_status": "not_human_adjudicated",
            "source_page_url": source_page,
            "license_spdxish": "CC-BY-4.0",
            "rights_disposition": "approved_for_local_research",
            "training_allowed": True,
            "redistribution_allowed": True,
            "audio_in_model": False,
            "is_touchdown": target,
            "notes": "isolated runtime fixture",
        })
    manifest = root / "data" / "public" / "footballmaster" / "source-manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "assets": assets}), encoding="utf-8")
    examples = root / "data" / "public" / "footballmaster" / "examples.jsonl"
    examples.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return examples, manifest


def test_package_has_no_cross_sport_source_or_absolute_application_imports() -> None:
    files = sorted(path for path in PACKAGE.rglob("*") if path.suffix in {".py", ".json"})
    assert files
    forbidden_text = ("soccer", "soccernet", "soccermaster", "multisport_search_demo_server", "search_demo_server")
    allowed_import_roots = set(sys.stdlib_module_names) | {
        "__future__", "cv2", "imageio_ffmpeg", "numpy", "onnxruntime",
    }
    for path in files:
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        for token in forbidden_text:
            assert token not in lowered, f"{path.relative_to(ROOT)} contains forbidden token {token}"
        if path.suffix != ".py":
            continue
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed_import_roots
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] in allowed_import_roots


def test_default_config_is_owned_and_strict() -> None:
    loaded = load_config(PACKAGE / "resources" / "default-config.json")
    assert loaded == FOOTBALL_CONFIG
    assert loaded.sport == "american_football"
    assert loaded.supported_fine_labels == {
        "touchdown_pass", "rushing_touchdown", "kickoff_return",
        "field_goal_attempt", "interception_practice",
    }


def test_import_succeeds_with_cross_sport_modules_blocked() -> None:
    script = r'''
import importlib.abc
import json
import sys

class DenyCrossSport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        lowered = fullname.casefold()
        if "soccer" in lowered:
            raise RuntimeError("cross-sport import attempted: " + fullname)
        return None

sys.meta_path.insert(0, DenyCrossSport())
import footballmaster
print(json.dumps({
    "module": footballmaster.__name__,
    "cross_sport_modules": sorted(name for name in sys.modules if "soccer" in name.casefold()),
}))
'''
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30
    )
    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence == {"module": "footballmaster", "cross_sport_modules": []}


def test_independent_train_evaluate_index_and_cli_search_runtime(tmp_path: Path) -> None:
    examples, sources = _fixture(tmp_path)
    model_dir = tmp_path / "artifacts" / "footballmaster" / "isolated-v1"
    result = train_pipeline(
        examples_path=examples,
        source_manifest_path=sources,
        backbone_path=tmp_path / "unused.onnx",
        output_dir=model_dir,
        frame_count=4,
        pca_components=2,
        epochs=40,
        learning_rate=0.1,
        l2=0.01,
        project_root=tmp_path,
        extractor=FixtureExtractor(),
    )
    assert result["status"] == "pass"
    card = json.loads((model_dir / "model-card.json").read_text(encoding="utf-8"))
    assert card["architecture_scope"] == "football_only"
    assert "soccer" not in json.dumps(card).casefold()

    evaluation = evaluate_package(model_dir, split="test")
    assert evaluation["matches_sealed_metrics"] is True
    assert evaluation["metrics"]["accuracy"] == 1.0

    index_dir = tmp_path / "standalone-index"
    indexed = build_index_from_package(
        model_dir,
        index_dir,
        examples_path=examples,
        source_manifest_path=sources,
        project_root=tmp_path,
    )
    assert indexed["window_count"] == 8
    searched = search_index(index_dir / "search-index.sqlite3", "touchdown pass", limit=5)
    assert searched["sport"] == "american_football"
    assert searched["count"] >= 1
    assert all(item["media_path"].startswith("data/public/footballmaster/media/") for item in searched["results"])

    command = [
        sys.executable, "-m", "footballmaster", "search",
        "--index", str(index_dir / "search-index.sqlite3"),
        "--query", "rushing touchdown", "--limit", "2",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    cli_result = json.loads(completed.stdout)
    assert cli_result["sport"] == "american_football"
    assert cli_result["count"] >= 1


def test_compatibility_wrapper_delegates_to_the_package() -> None:
    prototype = ROOT / "prototype"
    if str(prototype) not in sys.path:
        sys.path.insert(0, str(prototype))
    import footballmaster_pilot

    assert footballmaster_pilot.train_pipeline.__module__ == "footballmaster.pipeline"
    assert footballmaster_pilot.verify_run.__module__ == "footballmaster.pipeline"
