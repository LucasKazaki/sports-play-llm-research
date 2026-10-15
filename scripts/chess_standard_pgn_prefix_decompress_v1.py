#!/usr/bin/env python3
"""Bounded offline decompression of a caller-pinned standard PGN zstd prefix.

This bridge does not acquire data or authenticate its upstream origin. A later
broker receipt must bind the compressed bytes to Lichess before its output can
be used as a source-bound real-game cohort. No game, engine, or model is read.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

import zstandard


SCHEMA = "chess-standard-pgn-prefix-decompression/v1"
COMPRESSED_PREFIX_BYTES = 1_048_576
MAX_DECOMPRESSED_BYTES = 16 * 1_048_576
MAX_WINDOW_BYTES = 16 * 1_048_576
CHUNK_BYTES = 65_536
ZSTANDARD_VERSION = "0.25.0"
BROKER_SCHEMA = "project-standard-pgn-acquisition/v1"
BROKER_SOURCE = "lichess-standard-rated-2025-09-prefix"
ARCHIVE_URL = ("https://database.lichess.org/standard/"
               "lichess_db_standard_rated_2025-09.pgn.zst")
SOURCE_FILE = "standard.pgn.zst.part"
BROKER_FILE = "acquisition-receipt.json"
SOURCE_DIRECTORY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\Z")
ZSTD_FRAME_MAGIC = 0xFD2FB528
SKIPPABLE_MIN = 0x184D2A50
SKIPPABLE_MAX = 0x184D2A5F
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frame_offset(raw: bytes) -> int:
    """Locate a standard frame after complete leading skippable frames."""
    offset = 0
    while offset + 4 <= len(raw):
        magic = int.from_bytes(raw[offset:offset + 4], "little")
        if magic == ZSTD_FRAME_MAGIC:
            return offset
        if not SKIPPABLE_MIN <= magic <= SKIPPABLE_MAX or offset + 8 > len(raw):
            raise ValueError("invalid_zstd_frame_lead")
        skipped = int.from_bytes(raw[offset + 4:offset + 8], "little")
        if skipped > len(raw) - offset - 8:
            raise ValueError("incomplete_skippable_frame")
        offset += 8 + skipped
    raise ValueError("missing_standard_zstd_frame")


def _decompress_bounded(raw: bytes) -> tuple[bytes, int]:
    offset = _frame_offset(raw)
    chunks: list[bytes] = []
    total = 0
    try:
        with zstandard.ZstdDecompressor(max_window_size=MAX_WINDOW_BYTES).stream_reader(
                io.BytesIO(raw), read_across_frames=True) as reader:
            while True:
                chunk = reader.read(min(CHUNK_BYTES, MAX_DECOMPRESSED_BYTES - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DECOMPRESSED_BYTES:
                    raise ValueError("decompressed_prefix_exceeds_cap")
                chunks.append(chunk)
    except zstandard.ZstdError as error:
        raise ValueError("invalid_zstd_prefix") from error
    if total == 0:
        raise ValueError("empty_decompressed_prefix")
    return b"".join(chunks), offset


def decode_pinned_prefix(raw: bytes, expected_sha256: str) -> tuple[bytes, dict]:
    """Decode exactly one 1 MiB source prefix, retaining its limited assurance."""
    if zstandard.__version__ != ZSTANDARD_VERSION:
        raise ValueError("zstandard_version_changed")
    if not isinstance(raw, bytes) or len(raw) != COMPRESSED_PREFIX_BYTES:
        raise ValueError("invalid_compressed_prefix_byte_count")
    if (not isinstance(expected_sha256, str)
            or HEX_SHA256.fullmatch(expected_sha256) is None):
        raise ValueError("invalid_expected_sha256")
    if sha256(raw) != expected_sha256:
        raise ValueError("compressed_prefix_hash_mismatch")
    decompressed, frame_offset = _decompress_bounded(raw)
    receipt = {
        "schema": SCHEMA,
        "status": "caller_pinned_offline_decompression_only",
        "upstream_broker_verified": False,
        "full_archive": False,
        "source_assurance": "compressed prefix bytes and caller SHA256 only; official broker binding pending",
        "compressed": {"bytes": len(raw), "sha256": expected_sha256,
                       "standard_frame_offset": frame_offset},
        "decompressed": {"file": "prefix.pgn", "bytes": len(decompressed),
                         "sha256": sha256(decompressed),
                         "max_bytes": MAX_DECOMPRESSED_BYTES},
        "decoder": {"source_sha256": sha256(Path(__file__).read_bytes()),
                    "zstandard_version": zstandard.__version__,
                    "read_across_frames": True,
                    "max_window_bytes": MAX_WINDOW_BYTES},
    }
    return decompressed, receipt


def _canonical(receipt: dict) -> bytes:
    return (json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _read_exact(path: Path) -> bytes:
    with path.open("rb") as source:
        raw = source.read(COMPRESSED_PREFIX_BYTES + 1)
    return raw


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _path_within(candidate: Path, root: Path) -> tuple[Path, tuple[str, ...]]:
    """Check lexical containment before resolving links or opening anything."""
    if ".." in candidate.parts:
        raise ValueError("parent_traversal_path")
    absolute = Path(os.path.abspath(candidate))
    root_absolute = Path(os.path.abspath(root))
    try:
        relative = absolute.relative_to(root_absolute)
    except ValueError as error:
        raise ValueError("path_outside_project_boundary") from error
    return absolute, relative.parts


def _no_reparse_components(path: Path, project_root: Path) -> None:
    absolute, parts = _path_within(path, project_root)
    current = Path(os.path.abspath(project_root))
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        info = current.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or bool(getattr(info, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
                or os.path.normcase(os.path.realpath(current))
                != os.path.normcase(os.path.abspath(current))):
            raise ValueError("reparse_path_component")
    if os.path.normcase(os.path.realpath(absolute)) != os.path.normcase(os.path.abspath(absolute)):
        raise ValueError("reparse_path_component")


def _checked_source_path(compressed_path: Path) -> tuple[Path, str]:
    root = _project_root()
    source_root = root / "data" / "open" / "chess"
    path, parts = _path_within(compressed_path, source_root)
    if (len(parts) != 2 or SOURCE_DIRECTORY.fullmatch(parts[0]) is None
            or parts[1] != SOURCE_FILE):
        raise ValueError("invalid_standard_prefix_source_path")
    _no_reparse_components(path, root)
    if not path.is_file() or path.lstat().st_nlink != 1:
        raise ValueError("invalid_standard_prefix_source_file")
    return path, f"data/open/chess/{parts[0]}"


def _checked_output_path(output_dir: Path, *, must_exist: bool) -> Path:
    root = _project_root()
    output_root = root / "artifacts" / "chess-standard-pgn-prefix-decompression-v1"
    path, parts = _path_within(output_dir, output_root)
    if len(parts) != 1 or SOURCE_DIRECTORY.fullmatch(parts[0]) is None:
        raise ValueError("invalid_standard_prefix_output_path")
    _no_reparse_components(path, root)
    if must_exist and not path.is_dir():
        raise ValueError("invalid_output_directory")
    return path


def _checked_broker_receipt(source: Path, target: str, raw_sha256: str,
                            broker_receipt_sha256: str) -> str:
    if (not isinstance(broker_receipt_sha256, str)
            or HEX_SHA256.fullmatch(broker_receipt_sha256) is None):
        raise ValueError("invalid_broker_receipt_sha256")
    path = source.parent / BROKER_FILE
    _no_reparse_components(path, _project_root())
    if not path.is_file() or path.lstat().st_nlink != 1 or path.stat().st_size > 32_768:
        raise ValueError("invalid_broker_receipt_file")
    encoded = path.read_bytes()
    if sha256(encoded) != broker_receipt_sha256:
        raise ValueError("broker_receipt_hash_mismatch")
    try:
        receipt = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid_broker_receipt_json") from error
    if not isinstance(receipt, dict):
        raise ValueError("invalid_broker_receipt_fields")
    prefix = receipt.get("prefix")
    license_record = receipt.get("license")
    if (receipt.get("schema") != BROKER_SCHEMA
            or receipt.get("status") != "fetched"
            or receipt.get("source") != BROKER_SOURCE
            or receipt.get("target") != target
            or receipt.get("synthetic") is not False
            or receipt.get("fullArchive") is not False
            or not isinstance(license_record, dict)
            or license_record.get("spdx") != "CC0-1.0"
            or not isinstance(prefix, dict)
            or prefix.get("url") != ARCHIVE_URL
            or prefix.get("file") != SOURCE_FILE
            or prefix.get("bytes") != COMPRESSED_PREFIX_BYTES
            or prefix.get("requestedMaxBytes") != COMPRESSED_PREFIX_BYTES
            or prefix.get("sha256") != raw_sha256
            or prefix.get("status") not in (200, 206)):
        raise ValueError("invalid_broker_receipt_fields")
    return broker_receipt_sha256


def _source_bytes_and_binding(compressed_path: Path, expected_sha256: str,
                              broker_receipt_sha256: str) -> tuple[bytes, str]:
    path, target = _checked_source_path(compressed_path)
    raw = _read_exact(path)
    if sha256(raw) != expected_sha256:
        raise ValueError("compressed_prefix_hash_mismatch")
    return raw, _checked_broker_receipt(path, target, expected_sha256,
                                        broker_receipt_sha256)


def materialize(compressed_path: Path, expected_sha256: str, output_dir: Path,
                broker_receipt_sha256: str) -> dict:
    output_dir = _checked_output_path(output_dir, must_exist=False)
    raw, broker_digest = _source_bytes_and_binding(
        compressed_path, expected_sha256, broker_receipt_sha256)
    decompressed, receipt = decode_pinned_prefix(raw, expected_sha256)
    receipt["broker_receipt"] = {"file": BROKER_FILE, "sha256": broker_digest,
                                 "field_consistency_checked": True,
                                 "native_execution_binding_verified": False}
    _no_reparse_components(output_dir.parent, _project_root())
    output_dir.parent.mkdir(exist_ok=True)
    _no_reparse_components(output_dir.parent, _project_root())
    output_dir.mkdir(parents=False, exist_ok=False)
    with (output_dir / "prefix.pgn").open("xb") as destination:
        destination.write(decompressed)
    with (output_dir / "receipt.json").open("xb") as destination:
        destination.write(_canonical(receipt))
    return receipt


def verify(compressed_path: Path, expected_sha256: str, output_dir: Path,
           broker_receipt_sha256: str) -> dict:
    output_dir = _checked_output_path(output_dir, must_exist=True)
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("invalid_output_directory")
    if {path.name for path in output_dir.iterdir()} != {"prefix.pgn", "receipt.json"}:
        raise ValueError("output_file_set_changed")
    for name in ("prefix.pgn", "receipt.json"):
        path = output_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("output_file_type_changed")
    if ((output_dir / "prefix.pgn").stat().st_size > MAX_DECOMPRESSED_BYTES
            or (output_dir / "receipt.json").stat().st_size > 8192):
        raise ValueError("output_file_size_changed")
    raw, broker_digest = _source_bytes_and_binding(
        compressed_path, expected_sha256, broker_receipt_sha256)
    decompressed, receipt = decode_pinned_prefix(raw, expected_sha256)
    receipt["broker_receipt"] = {"file": BROKER_FILE, "sha256": broker_digest,
                                 "field_consistency_checked": True,
                                 "native_execution_binding_verified": False}
    with (output_dir / "prefix.pgn").open("rb") as source:
        observed = source.read(MAX_DECOMPRESSED_BYTES + 1)
    if observed != decompressed or (output_dir / "receipt.json").read_bytes() != _canonical(receipt):
        raise ValueError("decompression_output_or_receipt_changed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "verify"))
    parser.add_argument("--compressed-prefix", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--broker-receipt-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    action = materialize if args.action == "run" else verify
    print(_canonical(action(args.compressed_prefix, args.sha256, args.output_dir,
                            args.broker_receipt_sha256)).decode(), end="")


if __name__ == "__main__":
    main()
