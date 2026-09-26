import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from real_data_doctor import (
    find_secret_keys,
    is_within,
    sanitized_failure_report,
    validate_loopback_endpoint,
    validate_stream_role,
    verify_receipt,
)


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:1234/v1",
    "http://example.com:1234/v1",
    "http://user:pass@127.0.0.1:1234/v1",
    "http://127.0.0.1:1234/v1?token=x",
    "http://127.0.0.1:1234/v1#fragment",
])
def test_endpoint_rejects_non_loopback_or_secret_bearing_forms(endpoint: str) -> None:
    with pytest.raises(ValueError):
        validate_loopback_endpoint(endpoint)


def test_endpoint_accepts_explicit_loopback_v1() -> None:
    assert validate_loopback_endpoint("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"


def test_secret_key_scan_allows_boundary_flags_but_rejects_credentials() -> None:
    assert find_secret_keys({"authorization": {"credential_persisted": False}}) == []
    assert find_secret_keys({"nested": {"api_key": "x"}}) == ["$.nested.api_key"]


def test_path_containment_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "data" / "private"
    root.mkdir(parents=True)
    inside = root / "clip.mp4"
    inside.write_bytes(b"clip")
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"clip")
    assert is_within(inside, root)
    assert not is_within(outside, root)


def test_receipt_fails_closed_on_stale_source_hash(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = source_root / "game" / "1_224p.mkv"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"real")
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps({
        "schema_version": "playground-soccernet-acquisition-receipt-v1",
        "provider": "SoccerNet",
        "authorization": {"credential_persisted": False, "redistribution_allowed": False},
        "selection": {"game": "game", "split": "train"},
        "downloaded_files": [{
            "name": "1_224p.mkv", "relative_path": "game/1_224p.mkv",
            "bytes": 4, "sha256": "0" * 64,
        }],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        verify_receipt(receipt_path, source_root)


def test_stream_roles_reject_audio_leakage_and_missing_review_audio() -> None:
    validate_stream_role({"video": 1, "audio": 0}, expected_audio=0)
    validate_stream_role({"video": 1, "audio": 1}, expected_audio=1)
    with pytest.raises(ValueError, match="stream isolation"):
        validate_stream_role({"video": 1, "audio": 1}, expected_audio=0)
    with pytest.raises(ValueError, match="stream isolation"):
        validate_stream_role({"video": 1, "audio": 0}, expected_audio=1)


def test_failure_report_redacts_raw_exception_and_paths(tmp_path: Path) -> None:
    secret_path = tmp_path / "data" / "private" / "clip.mp4"
    report = sanitized_failure_report(RuntimeError(f"failed at {secret_path}"))
    encoded = json.dumps(report)
    assert report["status"] == "fail"
    assert report["error_code"] == "RuntimeError"
    assert str(secret_path) not in encoded
    assert "failed at" not in encoded
