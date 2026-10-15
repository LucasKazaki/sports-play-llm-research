"""Offline control-flow checks; fixture bytes are not real acquisition evidence."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import collect_gothamchess_media as media

FIRST = "sskvj1_ehx4"
SECOND = "ulLBRyVrI1Y"


def manifest(tmp_path, ids=(FIRST,)):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"videos": [{"youtube_id": item, "watch_url": f"https://www.youtube.com/watch?v={item}"} for item in ids]}), encoding="utf-8")
    return path


def payload(video_id=FIRST, **overrides):
    return {"id": video_id, "channel_id": media.CHANNEL_ID, "title": "AI plays chess", "availability": "public", "description": "private prose https://example.org/source.pgn", **overrides}


class Extractor:
    def __init__(self, options, action):
        self.options, self.action = options, action

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def extract_info(self, url, download=False):
        return self.action(self.options, url, download)


def test_metadata_only_never_fetches_media_or_retains_description(tmp_path):
    calls = []

    def action(options, url, download):
        calls.append((options, url, download))
        return payload()

    result = media.collect(manifest(tmp_path), tmp_path / "private", factory=lambda opts: Extractor(opts, action))
    assert result["status"] == "completed"
    assert result["mode"] == "metadata_only"
    assert result["records"][0]["status"] == "metadata_verified"
    assert "description" not in result["records"][0]["metadata"]
    assert result["records"][0]["pgn_link_candidates"] == ["https://example.org/source.pgn"]
    assert len(calls) == 1 and calls[0][2] is False
    assert calls[0][0]["writesubtitles"] is False
    assert calls[0][0]["writeinfojson"] is False


def test_download_verifies_identity_first_then_hashes_exact_bytes(tmp_path):
    root = tmp_path / "private"
    calls = []

    def action(options, url, download):
        calls.append(download)
        if download:
            (root / f"{FIRST}.mp4").write_bytes(b"fixture video, not real media")
        return payload()

    result = media.collect(manifest(tmp_path), root, download=True, factory=lambda opts: Extractor(opts, action))
    assert calls == [False, True]
    record = result["records"][0]
    assert record["status"] == "downloaded"
    assert record["files"] == [{"path": f"{FIRST}.mp4", "bytes": 29, "sha256": hashlib.sha256(b"fixture video, not real media").hexdigest()}]
    assert json.loads((root / "collection-receipt.json").read_text()) == result
    assert result["training_allowed"] is False


@pytest.mark.parametrize("override", [{"id": SECOND}, {"channel_id": "other-channel"}, {"availability": "private"}, {"availability": "subscriber_only"}])
def test_source_mismatch_or_restriction_prevents_download(tmp_path, override):
    downloads = []

    def action(options, url, download):
        downloads.append(download)
        return payload(**override)

    result = media.collect(manifest(tmp_path), tmp_path / "private", download=True, factory=lambda opts: Extractor(opts, action))
    assert downloads == [False]
    assert result["status"] == "incomplete"
    assert result["records"][0]["status"] == "failed"


def test_failure_keeps_denominator_and_continues_next_source(tmp_path):
    def action(options, url, download):
        if FIRST in url:
            raise RuntimeError("unavailable https://cdn.example/media?secret=123")
        return payload(SECOND)

    root = tmp_path / "private"
    result = media.collect(manifest(tmp_path, (FIRST, SECOND)), root, factory=lambda opts: Extractor(opts, action))
    assert [item["status"] for item in result["records"]] == ["failed", "metadata_verified"]
    assert "secret" not in result["records"][0]["error"]
    assert json.loads((root / "collection-receipt.json").read_text())["status"] == "incomplete"


def test_download_success_without_final_file_is_failure(tmp_path):
    result = media.collect(manifest(tmp_path), tmp_path / "private", download=True, factory=lambda opts: Extractor(opts, lambda *args: payload()))
    assert result["records"][0]["status"] == "failed"
    assert "nonempty final media" in result["records"][0]["error"]


def test_unmerged_intermediate_stream_is_not_complete_video(tmp_path):
    root = tmp_path / "private"

    def action(options, url, download):
        if download:
            (root / f"{FIRST}.f399.mp4").write_bytes(b"unmerged stream")
        return payload()

    result = media.collect(manifest(tmp_path), root, download=True, factory=lambda opts: Extractor(opts, action))
    assert result["records"][0]["status"] == "failed"
    assert result["records"][0]["files"] == []


@pytest.mark.parametrize("ids", [(FIRST, FIRST), (), ("../escape",), (FIRST, SECOND, "PVVA-_wvKks", "12345678901")])
def test_invalid_manifest_is_rejected_before_factory(tmp_path, ids):
    with pytest.raises(ValueError):
        media.collect(manifest(tmp_path, ids), tmp_path / "private", factory=lambda _: pytest.fail("must not run"))


def test_mismatched_url_is_rejected():
    with pytest.raises(ValueError, match="URL"):
        media.validate_source({"youtube_id": FIRST, "watch_url": "https://example.org/"})


def test_bounded_channel_scan_records_order_and_title_candidates(tmp_path):
    def action(options, url, download):
        assert download is False
        assert options["playlistend"] == 40
        assert options["extract_flat"] == "in_playlist"
        return {"id": media.CHANNEL_ID, "entries": [payload(title="Tournament recap"), payload(SECOND, title="GPT-6 VS OPUS") ]}

    result = media.discover(tmp_path / "scan.json", factory=lambda opts: Extractor(opts, action))
    assert result["status"] == "completed"
    assert [item["ai_title_candidate"] for item in result["records"]] == [False, True]
    assert [item["channel_listing_ordinal"] for item in result["records"]] == [1, 2]


def test_failed_scan_retains_receipt(tmp_path):
    result = media.discover(tmp_path / "scan.json", factory=lambda opts: Extractor(opts, lambda *args: {"id": "other"}))
    assert result["status"] == "failed"
    assert (tmp_path / "scan.json").is_file()


def test_cli_destination_cannot_escape_private_media_root(tmp_path):
    with pytest.raises(ValueError, match="ignored"):
        media.private_destination(tmp_path)
    assert media.private_destination(media.PRIVATE_ROOT / "media") == (media.PRIVATE_ROOT / "media").resolve()
