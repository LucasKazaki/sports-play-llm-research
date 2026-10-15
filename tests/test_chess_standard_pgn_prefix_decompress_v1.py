"""Synthetic controls for the offline standard-PGN prefix bridge."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import zstandard


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "chess_standard_pgn_prefix_decompress_v1",
    ROOT / "scripts/chess_standard_pgn_prefix_decompress_v1.py")
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


@pytest.fixture(scope="module")
def synthetic_prefix() -> tuple[bytes, bytes]:
    # Incompressible source assures the synthetic zstd frame crosses the fixed
    # 1 MiB byte cut. This is a decoder fixture, not a chess-game source.
    source = hashlib.shake_256(b"standard-pgn-prefix-bridge-v1").digest(1_300_000)
    compressed = zstandard.ZstdCompressor(level=1).compress(source)
    assert len(compressed) > bridge.COMPRESSED_PREFIX_BYTES
    return compressed[:bridge.COMPRESSED_PREFIX_BYTES], source


@pytest.fixture
def bound_paths(synthetic_prefix, tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "_project_root", lambda: tmp_path)
    raw, _ = synthetic_prefix
    source_dir = tmp_path / "data" / "open" / "chess" / "synthetic-prefix"
    source_dir.mkdir(parents=True)
    source = source_dir / bridge.SOURCE_FILE
    source.write_bytes(raw)
    broker = {
        "schema": bridge.BROKER_SCHEMA, "status": "fetched",
        "source": bridge.BROKER_SOURCE,
        "target": "data/open/chess/synthetic-prefix",
        "synthetic": False, "fullArchive": False,
        "license": {"spdx": "CC0-1.0"},
        "prefix": {"url": bridge.ARCHIVE_URL, "file": bridge.SOURCE_FILE,
                   "bytes": bridge.COMPRESSED_PREFIX_BYTES,
                   "requestedMaxBytes": bridge.COMPRESSED_PREFIX_BYTES,
                   "sha256": bridge.sha256(raw), "status": 206},
    }
    receipt_path = source_dir / bridge.BROKER_FILE
    receipt_path.write_text(json.dumps(broker), encoding="utf-8")
    output_root = (tmp_path / "artifacts" /
                   "chess-standard-pgn-prefix-decompression-v1")
    output_root.parent.mkdir(parents=True)
    return source, bridge.sha256(raw), bridge.sha256(receipt_path.read_bytes()), output_root


def test_truncated_frame_decompresses_only_bounded_source_prefix(synthetic_prefix):
    raw, source = synthetic_prefix
    decoded, receipt = bridge.decode_pinned_prefix(raw, bridge.sha256(raw))
    assert len(decoded) > 0
    assert len(decoded) < len(source)
    assert source.startswith(decoded)
    assert receipt["upstream_broker_verified"] is False
    assert receipt["full_archive"] is False
    assert receipt["compressed"]["bytes"] == 1_048_576
    assert receipt["decompressed"]["sha256"] == bridge.sha256(decoded)
    assert receipt["decoder"]["max_window_bytes"] == bridge.MAX_WINDOW_BYTES
    assert "official broker binding pending" in receipt["source_assurance"]


def test_skippable_lead_in_and_corruption_are_distinguished():
    standard = zstandard.ZstdCompressor(write_checksum=True).compress(b"[Event \"Synthetic\"]\n")
    skippable = (0x184D2A50).to_bytes(4, "little") + (4).to_bytes(4, "little") + b"meta"
    decoded, offset = bridge._decompress_bounded(skippable + standard)
    assert decoded == b"[Event \"Synthetic\"]\n"
    assert offset == len(skippable)
    with pytest.raises(ValueError, match="incomplete_skippable_frame"):
        bridge._decompress_bounded(skippable[:-1])
    with pytest.raises(ValueError, match="invalid_zstd_frame_lead"):
        bridge._decompress_bounded(b"junk" + standard)
    corrupt = standard[:-1] + bytes((standard[-1] ^ 0x80,))
    with pytest.raises(ValueError, match="invalid_zstd_prefix"):
        bridge._decompress_bounded(corrupt)


def test_decompressed_bomb_is_stopped_at_fixed_cap():
    compressed = zstandard.ZstdCompressor().compress(
        b"A" * (bridge.MAX_DECOMPRESSED_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds_cap"):
        bridge._decompress_bounded(compressed)


def test_oversized_frame_window_is_rejected_before_output():
    params = zstandard.ZstdCompressionParameters.from_level(
        1, window_log=25, write_content_size=False)
    raw = bytearray(zstandard.ZstdCompressor(compression_params=params).compress(b"A" * 1000))
    assert zstandard.get_frame_parameters(raw).window_size <= bridge.MAX_WINDOW_BYTES
    raw[5] = 0x78  # Advertise a 32 MiB window in this synthetic frame header.
    assert zstandard.get_frame_parameters(raw).window_size == 32 * 1_048_576
    with pytest.raises(ValueError, match="invalid_zstd_prefix"):
        bridge._decompress_bounded(bytes(raw))


def test_exact_size_and_hash_fail_closed_before_decode(synthetic_prefix):
    raw, _ = synthetic_prefix
    with pytest.raises(ValueError, match="byte_count"):
        bridge.decode_pinned_prefix(raw[:-1], bridge.sha256(raw[:-1]))
    with pytest.raises(ValueError, match="invalid_expected_sha256"):
        bridge.decode_pinned_prefix(raw, "bad")
    with pytest.raises(ValueError, match="hash_mismatch"):
        bridge.decode_pinned_prefix(raw, "0" * 64)
    with pytest.raises(ValueError, match="invalid_zstd_frame_lead"):
        bridge.decode_pinned_prefix(b"X" * bridge.COMPRESSED_PREFIX_BYTES,
                                    bridge.sha256(b"X" * bridge.COMPRESSED_PREFIX_BYTES))


def test_materialize_and_verify_recompute_exact_output_and_receipt(bound_paths):
    source, source_sha, broker_sha, output_root = bound_paths
    out = output_root / "derived"
    receipt = bridge.materialize(source, source_sha, out, broker_sha)
    assert bridge.verify(source, source_sha, out, broker_sha) == receipt
    assert receipt["broker_receipt"]["sha256"] == broker_sha
    assert receipt["broker_receipt"]["native_execution_binding_verified"] is False
    with pytest.raises(FileExistsError):
        bridge.materialize(source, source_sha, out, broker_sha)
    receipt_path = out / "receipt.json"
    original = receipt_path.read_bytes()
    receipt_path.write_bytes(original.replace(b'"full_archive":false', b'"full_archive":true'))
    with pytest.raises(ValueError, match="receipt_changed"):
        bridge.verify(source, source_sha, out, broker_sha)
    receipt_path.write_bytes(original)
    decoded = out / "prefix.pgn"
    decoded.write_bytes(decoded.read_bytes() + b"x")
    with pytest.raises(ValueError, match="output_or_receipt_changed"):
        bridge.verify(source, source_sha, out, broker_sha)


def test_verify_rejects_extra_file_and_source_change(bound_paths):
    source, source_sha, broker_sha, output_root = bound_paths
    out = output_root / "derived"
    bridge.materialize(source, source_sha, out, broker_sha)
    (out / "unbound.txt").write_text("x")
    with pytest.raises(ValueError, match="file_set_changed"):
        bridge.verify(source, source_sha, out, broker_sha)
    (out / "unbound.txt").unlink()
    raw = source.read_bytes()
    source.write_bytes(raw[:-1] + bytes((raw[-1] ^ 0x01,)))
    with pytest.raises(ValueError, match="hash_mismatch"):
        bridge.verify(source, source_sha, out, broker_sha)


def test_verify_caps_receipt_before_reading_it(bound_paths):
    source, source_sha, broker_sha, output_root = bound_paths
    out = output_root / "derived"
    bridge.materialize(source, source_sha, out, broker_sha)
    (out / "receipt.json").write_bytes(b"X" * 8193)
    with pytest.raises(ValueError, match="file_size_changed"):
        bridge.verify(source, source_sha, out, broker_sha)


def test_source_and_output_path_escape_rejected_before_read(bound_paths, tmp_path):
    source, source_sha, broker_sha, output_root = bound_paths
    with pytest.raises(ValueError, match="outside_project_boundary"):
        bridge.materialize(tmp_path / "foreign.zst", source_sha,
                           output_root / "derived", broker_sha)
    with pytest.raises(ValueError, match="parent_traversal_path"):
        bridge.materialize(source.parent / ".." / source.parent.name / source.name,
                           source_sha, output_root / "derived", broker_sha)
    with pytest.raises(ValueError, match="outside_project_boundary"):
        bridge.materialize(source, source_sha, tmp_path / "elsewhere", broker_sha)
    assert not (output_root / "derived").exists()


def test_broker_receipt_pin_and_fields_required(bound_paths):
    source, source_sha, broker_sha, output_root = bound_paths
    out = output_root / "derived"
    with pytest.raises(ValueError, match="broker_receipt_hash_mismatch"):
        bridge.materialize(source, source_sha, out, "0" * 64)
    broker_path = source.parent / bridge.BROKER_FILE
    record = json.loads(broker_path.read_text(encoding="utf-8"))
    record["source"] = "lichess-puzzle-prefix"
    broker_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_broker_receipt_fields"):
        bridge.materialize(source, source_sha, out,
                           bridge.sha256(broker_path.read_bytes()))
    assert not out.exists()


def test_symlinked_source_parent_is_rejected(bound_paths, tmp_path):
    source, source_sha, broker_sha, output_root = bound_paths
    linked = source.parent.parent / "linked-source"
    try:
        linked.symlink_to(source.parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Host cannot create a symlink fixture")
    with pytest.raises(ValueError, match="reparse_path_component"):
        bridge.materialize(linked / bridge.SOURCE_FILE, source_sha,
                           output_root / "derived", broker_sha)
