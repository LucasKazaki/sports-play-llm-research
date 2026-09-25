"""Offline broker intake uses retained real Lichess bytes, never generated games."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("chess_broker_pipeline", ROOT / "scripts/chess_real_data.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
DATA = ROOT / "data/open/chess/lichess-real-seed-v1"
SOURCE = "https://database.lichess.org/lichess_db_puzzle.csv.zst"


@pytest.fixture
def broker(tmp_path):
    parent = tmp_path / "data/open/chess/broker-source-v1"
    parent.mkdir(parents=True)
    old = json.loads((DATA / "manifest.json").read_text())
    page = (DATA / "source-page.html").read_bytes()
    prefix = (DATA / "source-prefix.csv.zst.part").read_bytes()
    (parent / "source-page.html").write_bytes(page)
    (parent / "puzzles.csv.zst.part").write_bytes(prefix)
    receipt = {"schema": "project-public-data-acquisition/v1", "source": "lichess-puzzle-prefix",
        "target": "data/open/chess/broker-source-v1", "synthetic": False, "fullArchive": False,
        "license": {"spdx": "CC0-1.0", "evidenceFile": "source-page.html", "marker": "CC0"},
        "page": {"url": pipeline.SOURCE_PAGE, "file": "source-page.html", "bytes": len(page),
            "sha256": pipeline.sha(page), "status": 200, "headers": {"etag": None, "lastModified": None,
                "contentType": "text/html", "contentRange": None}},
        "prefix": {"url": SOURCE, "file": "puzzles.csv.zst.part", "bytes": len(prefix),
            "sha256": pipeline.sha(prefix), "requestedMaxBytes": pipeline.MAX_COMPRESSED, "status": 206,
            "headers": {"etag": old["acquisition"]["etag"], "lastModified": old["acquisition"]["last_modified"],
                "contentType": "application/zstd", "contentRange": old["acquisition"]["content_range"]}},
        "retrievedAt": old["created_at"], "timeoutMs": 45000}
    receipt_path = parent / "receipt.json"
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    return receipt_path, receipt, tmp_path / "derived"


def run_offline(broker):
    receipt_path, _, output = broker
    with patch.object(pipeline, "urlopen", side_effect=AssertionError("Offline intake must never access the network")) as opener:
        result = pipeline.acquire(output, from_broker=receipt_path)
    opener.assert_not_called()
    return result


def test_broker_intake_replays_24_actual_games_without_any_network(broker):
    receipt_path, receipt, output = broker
    original = {file.name: file.read_bytes() for file in receipt_path.parent.iterdir()}
    result = run_offline(broker)
    assert result["real_games"] == 24
    assert result["replayed_plies"] == 122
    assert result["split_counts"] == {"train": 8, "dev": 8, "test": 8}
    assert result["synthetic_items"] == result["test_outcomes_scored"] == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["items"] == json.loads((DATA / "manifest.json").read_text())["items"]
    assert (output / "source-page.html").read_bytes() == original["source-page.html"]
    assert (output / "source-prefix.csv.zst.part").read_bytes() == original["puzzles.csv.zst.part"]
    assert (output / "broker-receipt.json").read_bytes() == original["receipt.json"]
    acquisition = manifest["acquisition"]["broker"]
    assert acquisition["receipt_sha256"] == pipeline.sha(original["receipt.json"])
    assert acquisition["retrieved_at"] == receipt["retrievedAt"]
    assert acquisition["source"] == "lichess-puzzle-prefix"
    assert acquisition["target"] == receipt["target"]
    assert "not authenticate" in acquisition["assurance"]
    assert manifest["full_database_downloaded"] is False
    assert "not full upstream archive" in manifest["hash_scope"]
    assert {file.name: file.read_bytes() for file in receipt_path.parent.iterdir()} == original


@pytest.mark.parametrize("section,key,value", [
    (None, "schema", "other/v1"), (None, "source", "arbitrary-url"),
    (None, "target", "../outside"), (None, "target", "data/open/chess/different"),
    (None, "fullArchive", True), (None, "synthetic", True),
    ("license", "spdx", "unknown"), ("license", "evidenceFile", "../outside.html"),
    ("license", "marker", "not-in-page"),
    ("page", "url", "https://example.org/"), ("prefix", "url", "https://example.org/archive.zst"),
    ("page", "file", "../source-page.html"), ("prefix", "file", "../puzzles.csv.zst.part"),
    ("prefix", "requestedMaxBytes", pipeline.MAX_COMPRESSED + 1),
    ("prefix", "bytes", pipeline.MAX_COMPRESSED + 1), ("page", "bytes", 1),
    ("prefix", "sha256", "0" * 64), ("page", "status", 302), ("prefix", "status", 404),
])
def test_invalid_broker_contract_rejected_before_output_or_network(broker, section, key, value):
    receipt_path, receipt, output = broker
    (receipt[section] if section else receipt)[key] = value
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    with pytest.raises(ValueError):
        run_offline(broker)
    assert not output.exists()


@pytest.mark.parametrize("artifact", ["source-page.html", "puzzles.csv.zst.part"])
def test_retained_broker_bytes_cannot_be_tampered(broker, artifact):
    receipt_path, _, output = broker
    file = receipt_path.parent / artifact
    file.write_bytes(file.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="hash|bytes"):
        run_offline(broker)
    assert not output.exists()


@pytest.mark.parametrize("change", ["rights", "link", "range"])
def test_valid_hashes_do_not_replace_rights_link_and_prefix_checks(broker, change):
    receipt_path, receipt, output = broker
    if change == "range":
        receipt["prefix"]["headers"]["contentRange"] = "bytes 1-262144/304429328"
    else:
        file = receipt_path.parent / "source-page.html"
        text = file.read_text(encoding="utf-8")
        text = text.replace("CC0", "ZZZ") if change == "rights" else text.replace("lichess_db_puzzle.csv.zst", "not-puzzles.csv.zst")
        data = text.encode()
        file.write_bytes(data)
        receipt["page"].update({"bytes": len(data), "sha256": pipeline.sha(data)})
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    with pytest.raises(ValueError):
        run_offline(broker)
    assert not output.exists()


def test_symlinked_broker_artifact_rejected(broker):
    receipt_path, _, output = broker
    source = receipt_path.parent / "source-page.html"
    real = receipt_path.parent / "retained.html"
    source.rename(real)
    try:
        os.symlink(real, source)
    except OSError as error:
        pytest.skip("Host cannot create symlink fixture: " + str(error))
    with pytest.raises(ValueError, match="symlink|reparse"):
        run_offline(broker)
    assert not output.exists()


def test_reparse_attribute_rejected_even_without_host_symlink_privilege(broker):
    receipt_path, _, output = broker
    artifact = receipt_path.parent / "source-page.html"
    original = Path.lstat
    def observed(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400) if path == artifact else value
    with patch.object(Path, "lstat", observed), pytest.raises(ValueError, match="symlink|reparse"):
        run_offline(broker)
    assert not output.exists()


@pytest.mark.parametrize("remote", [r"\\server\share\receipt.json", "//server/share/receipt.json", r"\\?\C:\receipt.json"])
def test_offline_paths_reject_unc_and_device_names_before_filesystem_access(broker, remote):
    _, _, output = broker
    with patch.object(Path, "stat", side_effect=AssertionError("No filesystem access for UNC/device inputs")), \
            patch.object(Path, "lstat", side_effect=AssertionError("No filesystem access for UNC/device inputs")):
        with pytest.raises(ValueError, match="local_path_required"):
            pipeline.acquire(output, from_broker=remote)


def test_retained_receipt_copy_is_hash_bound_after_import(broker):
    _, _, output = broker
    run_offline(broker)
    receipt = output / "broker-receipt.json"
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(ValueError, match="broker_receipt_hash_mismatch"):
        pipeline.verify(output)


def test_bounded_200_prefix_retains_explicit_partial_hash_scope(broker):
    receipt_path, receipt, output = broker
    receipt["prefix"]["status"] = 200
    receipt["prefix"]["headers"]["contentRange"] = None
    receipt["prefix"]["headers"]["contentLength"] = "304429328"
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    assert run_offline(broker)["real_games"] == 24
    assert json.loads((output / "manifest.json").read_text())["full_database_downloaded"] is False


@pytest.mark.parametrize("content_length", [None, "262144", "not-a-length"])
def test_http_200_requires_preserved_evidence_of_remaining_archive_bytes(broker, content_length):
    receipt_path, receipt, output = broker
    receipt["prefix"]["status"] = 200
    receipt["prefix"]["headers"]["contentRange"] = None
    receipt["prefix"]["headers"]["contentLength"] = content_length
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    with pytest.raises(ValueError, match="remaining|content_length"):
        run_offline(broker)
    assert not output.exists()


def test_offline_page_bound_matches_broker_two_mib_contract(broker):
    receipt_path, receipt, _ = broker
    file = receipt_path.parent / "source-page.html"
    page = file.read_bytes().ljust(2 * 1024 * 1024, b" ")
    file.write_bytes(page)
    receipt["page"].update({"bytes": len(page), "sha256": pipeline.sha(page)})
    receipt_path.write_bytes(pipeline.json_bytes(receipt))
    assert run_offline(broker)["real_games"] == 24


def test_direct_acquire_still_uses_existing_bounded_source_requests(broker):
    receipt_path, receipt, output = broker
    class Response:
        def __init__(self, file, status, headers=None):
            self.data = (receipt_path.parent / file).read_bytes()
            self.status, self.headers, self.url = status, headers or {}, SOURCE
        def read(self, size):
            assert size <= 1024 * 1024
            return self.data[:size]
        def __enter__(self): return self
        def __exit__(self, *args): pass
    responses = [Response("source-page.html", 200), Response("puzzles.csv.zst.part", 206,
        {"Content-Range": receipt["prefix"]["headers"]["contentRange"]})]
    with patch.object(pipeline, "urlopen", side_effect=responses) as opener:
        assert pipeline.acquire(output)["real_games"] == 24
    assert opener.call_count == 2
    assert opener.call_args_list[1].args[0].get_header("Range") == "bytes=0-262143"
    assert not (output / "broker-receipt.json").exists()


def test_offline_cli_preserves_existing_data_flag(broker, capsys):
    receipt_path, _, output = broker
    with patch("sys.argv", ["chess_real_data.py", "acquire", "--data", str(output), "--from-broker", str(receipt_path)]), \
            patch.object(pipeline, "urlopen", side_effect=AssertionError("No network")):
        pipeline.main()
    assert json.loads(capsys.readouterr().out)["real_games"] == 24


def test_existing_output_is_not_overwritten(broker):
    _, _, output = broker
    output.mkdir()
    (output / "keep.txt").write_text("retained")
    with pytest.raises(ValueError, match="intake_directory_not_empty"):
        run_offline(broker)
    assert (output / "keep.txt").read_text() == "retained"
