"""Real source projection tests; no engine/model requests or heldout scoring."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("chess_dev_projection", ROOT / "scripts/chess_dev_projection.py")
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)
DATA = ROOT / "data/open/chess/lichess-real-seed-v1"


def test_exact_eight_real_development_records_with_source_hash_and_no_other_split_content():
    raw = projection.projection_bytes(DATA)
    result = json.loads(raw)
    source = json.loads((DATA / "manifest.json").read_bytes())
    selected = sorted((item for item in source["items"] if item["split"] == "dev"), key=lambda item: item["position_id"])
    assert len(result["items"]) == 8
    assert result["selected_split"] == "dev"
    assert result["source_manifest_sha256"] == hashlib.sha256((DATA / "manifest.json").read_bytes()).hexdigest()
    assert result["source_split_counts"] == {"dev": 8, "train": 8, "test": 8}
    for actual, expected in zip(result["items"], selected):
        assert set(actual) == {"position_id", "game_id", "game_url", "split", "source_fen", "setup_move", "fen", "provenance_kind"}
        assert all(actual[key] == expected[key] for key in actual)
    text = raw.decode()
    for item in source["items"]:
        if item["split"] == "dev":
            continue
        # Scan the entire serialized packet, including nested strings/metadata.
        for key in ("position_id", "game_id", "game_url", "source_fen", "fen"):
            assert item[key] not in text
    for field in ("target_move", "solution_uci", "themes", "rating", "legal_replay"):
        assert f'"{field}"' not in text
    assert len(raw) < 16_384


def test_repeated_creation_is_byte_deterministic_and_check_is_read_only(tmp_path):
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    report = projection.create_projection(DATA, first)
    assert projection.create_projection(DATA, second) == report
    assert first.read_bytes() == second.read_bytes()
    before = first.stat().st_mtime_ns
    assert projection.check_projection(DATA, first) == report
    assert first.stat().st_mtime_ns == before
    assert report["engine_calls"] == report["model_calls"] == report["test_outcomes_scored"] == 0


@pytest.mark.parametrize("mutation", ["fabricated_position", "heldout_item", "nested_heldout_metadata"])
def test_forged_or_expanded_projection_is_rejected(tmp_path, mutation):
    source = json.loads((DATA / "manifest.json").read_bytes())
    heldout = next(item for item in source["items"] if item["split"] == "test")
    value = json.loads(projection.projection_bytes(DATA))
    if mutation == "fabricated_position":
        value["items"][0]["game_url"] = "https://lichess.org/FakeGame"
    elif mutation == "heldout_item":
        value["items"][0] = heldout
    else:
        value["debug"] = {"nested": [json.dumps(heldout)]}
    output = tmp_path / "modified.json"
    output.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="does_not_match_verified_source"):
        projection.check_projection(DATA, output)


def test_tampered_source_cannot_be_projected(tmp_path):
    copied = tmp_path / "source"
    shutil.copytree(DATA, copied)
    with (copied / "sample.csv").open("ab") as stream:
        stream.write(b"fabricated row\n")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        projection.create_projection(copied, tmp_path / "output.json")
    assert not (tmp_path / "output.json").exists()


def test_existing_projection_is_never_overwritten(tmp_path):
    output = tmp_path / "existing.json"
    output.write_bytes(b"retained evidence")
    with pytest.raises(FileExistsError):
        projection.create_projection(DATA, output)
    assert output.read_bytes() == b"retained evidence"
