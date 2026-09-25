import json
import sys
from pathlib import Path, PurePosixPath

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import verify_soccerdb_overlap as overlap


def _write_mapping(path: Path, *, train_name: str | None = None, duplicate_train: bool = False) -> None:
    train = overlap.EXPECTED_BINDINGS["train"]
    valid = overlap.EXPECTED_BINDINGS["valid"]
    rows = [
        "SoccerDB Name,SoccerNet Name",
        f"{train_name or train.soccerdb_media_name},{train.soccernet_media_name}",
        f"{valid.soccerdb_media_name},{valid.soccernet_media_name}",
    ]
    if duplicate_train:
        rows.append(f"{train.soccerdb_media_name},{train.soccernet_media_name}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def _write_pair(root: Path, split: str) -> tuple[Path, Path]:
    expected = overlap.EXPECTED_BINDINGS[split]
    video_sha = ("1" if split == "train" else "2") * 64
    labels_sha = ("3" if split == "train" else "4") * 64
    receipt = {
        "schema_version": overlap.RECEIPT_SCHEMA_VERSION,
        "provider": "SoccerNet",
        "authorization": {
            "credential_persisted": False,
            "redistribution_allowed": False,
        },
        "selection": {
            "split": split,
            "game": expected.soccernet_game,
            "files": [f"{expected.source_half}_224p.mkv", "Labels-v2.json"],
        },
        "downloaded_files": [
            {
                "name": f"{expected.source_half}_224p.mkv",
                "relative_path": f"{expected.soccernet_game}/{expected.source_half}_224p.mkv",
                "bytes": 10,
                "sha256": video_sha,
            },
            {
                "name": "Labels-v2.json",
                "relative_path": f"{expected.soccernet_game}/Labels-v2.json",
                "bytes": 10,
                "sha256": labels_sha,
            },
        ],
    }
    receipt_path = root / f"{split}-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    manifest = {
        "schema_version": overlap.MANIFEST_SCHEMA_VERSION,
        "provider": "SoccerNet",
        "split": split,
        "source_game": PurePosixPath(expected.soccernet_game).name,
        "source_half": expected.source_half,
        "acquisition_receipt_sha256": overlap.sha256_file(receipt_path),
        "source_video_sha256": video_sha,
        "source_labels_sha256": labels_sha,
        "rights": {
            "credential_persisted": False,
            "redistribution_allowed": False,
        },
        "clips": [{
            "clip_id": f"{split}-abcdef12-h1-001",
            "split": split,
            "source_half": expected.source_half,
        }],
    }
    manifest_path = root / f"{split}-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return receipt_path, manifest_path


def _build_fixture_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path)
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", overlap.sha256_file(mapping_path))
    train_receipt, train_manifest = _write_pair(tmp_path, "train")
    valid_receipt, valid_manifest = _write_pair(tmp_path, "valid")
    return overlap.build_binding_report(
        mapping_path=mapping_path,
        train_receipt_path=train_receipt,
        valid_receipt_path=valid_receipt,
        train_manifest_path=train_manifest,
        valid_manifest_path=valid_manifest,
    )


def test_published_mapping_is_hash_pinned_and_contains_exact_selected_rows() -> None:
    mapping_path = ROOT / "data/public/SoccerDB-metadata" / overlap.MAPPING_RELATIVE_PATH
    rows, digest = overlap.load_published_mapping(mapping_path)
    assert digest == overlap.EXPECTED_MAPPING_SHA256
    for expected in overlap.EXPECTED_BINDINGS.values():
        matches = [row for row in rows if row["SoccerNet Name"] == expected.soccernet_media_name]
        assert matches == [{
            "SoccerDB Name": expected.soccerdb_media_name,
            "SoccerNet Name": expected.soccernet_media_name,
        }]


def test_report_binds_both_splits_without_private_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_fixture_report(tmp_path, monkeypatch)
    encoded = json.dumps(report, sort_keys=True)
    assert report["status"] == "pass"
    assert [item["split"] for item in report["bindings"]] == ["train", "valid"]
    assert all(item["identity_match"] is True for item in report["bindings"])
    assert str(tmp_path) not in encoded
    assert "data/private" not in encoded.replace("\\", "/").lower()
    assert "password" not in encoded.lower()


def test_mapping_hash_tamper_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path)
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="mapping SHA-256 mismatch"):
        overlap.load_published_mapping(mapping_path)


def test_unexpected_soccerdb_identity_fails_even_when_file_hash_is_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path, train_name="0" * 32 + "_1.mkv")
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", overlap.sha256_file(mapping_path))
    train_receipt, train_manifest = _write_pair(tmp_path, "train")
    rows, _ = overlap.load_published_mapping(mapping_path)
    with pytest.raises(ValueError, match="SoccerDB media identity is unexpected"):
        overlap.verify_binding_pair(
            expected=overlap.EXPECTED_BINDINGS["train"], mapping_rows=rows,
            receipt_path=train_receipt, manifest_path=train_manifest,
        )


def test_duplicate_exact_mapping_row_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path, duplicate_train=True)
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", overlap.sha256_file(mapping_path))
    train_receipt, train_manifest = _write_pair(tmp_path, "train")
    rows, _ = overlap.load_published_mapping(mapping_path)
    with pytest.raises(ValueError, match="exactly one train SoccerNet media identity"):
        overlap.verify_binding_pair(
            expected=overlap.EXPECTED_BINDINGS["train"], mapping_rows=rows,
            receipt_path=train_receipt, manifest_path=train_manifest,
        )


def test_stale_manifest_receipt_hash_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path)
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", overlap.sha256_file(mapping_path))
    train_receipt, train_manifest = _write_pair(tmp_path, "train")
    manifest = json.loads(train_manifest.read_text(encoding="utf-8"))
    manifest["acquisition_receipt_sha256"] = "f" * 64
    train_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    rows, _ = overlap.load_published_mapping(mapping_path)
    with pytest.raises(ValueError, match="receipt hash is stale"):
        overlap.verify_binding_pair(
            expected=overlap.EXPECTED_BINDINGS["train"], mapping_rows=rows,
            receipt_path=train_receipt, manifest_path=train_manifest,
        )


def test_secret_shaped_receipt_key_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapping_path = tmp_path / "SoccerDB2SoccerNet.csv"
    _write_mapping(mapping_path)
    monkeypatch.setattr(overlap, "EXPECTED_MAPPING_SHA256", overlap.sha256_file(mapping_path))
    train_receipt, train_manifest = _write_pair(tmp_path, "train")
    receipt = json.loads(train_receipt.read_text(encoding="utf-8"))
    receipt["authorization"]["password"] = "must-not-appear"
    train_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    rows, _ = overlap.load_published_mapping(mapping_path)
    with pytest.raises(ValueError, match="secret-shaped key"):
        overlap.verify_binding_pair(
            expected=overlap.EXPECTED_BINDINGS["train"], mapping_rows=rows,
            receipt_path=train_receipt, manifest_path=train_manifest,
        )


def test_public_safety_guard_rejects_private_absolute_path() -> None:
    with pytest.raises(ValueError, match="private or absolute path"):
        overlap._assert_public_safe({"leak": r"C:\AI\project\data\private\clip.mp4"})


def test_report_writer_is_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_fixture_report(tmp_path, monkeypatch)
    output = tmp_path / "binding.json"
    overlap.write_report_exclusive(output, report)
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "pass"
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        overlap.write_report_exclusive(output, report)
