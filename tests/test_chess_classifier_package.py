import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from chess_classifier_package import package_checkpoint, METADATA
from chess_stockfish_distill import digest


@pytest.fixture
def package_dirs(tmp_path):
    # Small metadata fixture from the locally acquired pinned model, never its weights.
    source = ROOT / "data/private/chess-classifier-v3/base-model"
    if not source.exists():
        pytest.skip("optional local pinned metadata absent")
    base, checkpoint = tmp_path / "base", tmp_path / "checkpoint"
    base.mkdir()
    checkpoint.mkdir()
    for name in (*METADATA, "config.json"):
        shutil.copyfile(source / name, base / name)
    shutil.copyfile(source / "config.json", checkpoint / "config.json")
    (checkpoint / "model.safetensors").write_bytes(b"synthetic unchanged weight identity")
    return base, checkpoint


def test_metadata_package_preserves_weights_and_is_idempotent(package_dirs):
    base, checkpoint = package_dirs
    before = digest(checkpoint / "model.safetensors")
    receipt = package_checkpoint(base, checkpoint)
    assert receipt["weight_sha256_before"] == receipt["weight_sha256_after"] == before
    assert receipt["remote_python_executed"] is False
    assert package_checkpoint(base, checkpoint)["metadata_sha256"] == receipt["metadata_sha256"]


def test_mapping_mismatch_rejected_before_any_metadata_copy(package_dirs):
    base, checkpoint = package_dirs
    path = checkpoint / "config.json"
    config = json.loads(path.read_text())
    config["id2label"]["0"] = "e2e4"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="native contract differs"):
        package_checkpoint(base, checkpoint)
    assert not (checkpoint / "tokenizer.json").exists()
    assert (checkpoint / "model.safetensors").read_bytes() == b"synthetic unchanged weight identity"


def test_conflicting_metadata_is_not_overwritten(package_dirs):
    base, checkpoint = package_dirs
    (checkpoint / "tokenizer.json").write_bytes(b"different metadata")
    with pytest.raises(ValueError, match="refusing to replace"):
        package_checkpoint(base, checkpoint)
    assert (checkpoint / "tokenizer.json").read_bytes() == b"different metadata"
