"""Offline tests for the metadata-only GothamChess yt-dlp collector."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_gothamchess_metadata as collector


MANIFEST = ROOT / "research/gothamchess-ai-agent-discovery-2026-10-14.json"


def test_build_command_is_metadata_only():
    command = collector.build_command(
        "yt-dlp", "https://www.youtube.com/watch?v=sskvj1_ehx4"
    )
    assert command == [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--no-warnings",
        "--dump-single-json",
        "https://www.youtube.com/watch?v=sskvj1_ehx4",
    ]
    forbidden_fragments = (
        "--write-subs",
        "--write-auto-subs",
        "--write-thumbnail",
        "--extract-audio",
        "--format",
        "-f",
        "-o",
        "--output",
    )
    assert not any(item in command for item in forbidden_fragments)


def test_collector_writes_only_normalized_metadata(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    calls = []
    payloads = {
        item["youtube_id"]: {
            "id": item["youtube_id"],
            "title": item["title"],
            "channel": "GothamChess",
            "channel_id": "UCQHX6ViZmPsWiYSFAyS0a3Q",
            "upload_date": item["published_date"].replace("-", ""),
            "duration": 1234,
            "webpage_url": item["watch_url"],
            "description": "must not be retained",
            "formats": [{"url": "must not be retained"}],
            "subtitles": {"en": [{"url": "must not be retained"}]},
        }
        for item in manifest["videos"]
    }

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        video_id = command[-1].split("v=", 1)[1]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payloads[video_id]),
            stderr="",
        )

    output = tmp_path / "metadata.json"
    receipt = collector.collect(
        MANIFEST,
        output,
        runner=fake_runner,
        fetched_at="2026-10-14T14:57:00Z",
    )

    assert len(calls) == 3
    assert all("--skip-download" in command for command, _ in calls)
    assert receipt["collector"] == {
        "backend": "yt-dlp",
        "mode": "metadata_only",
        "media_downloaded": False,
        "subtitles_downloaded": False,
        "thumbnails_downloaded": False,
        "descriptions_retained": False,
    }
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == receipt
    for record in receipt["records"]:
        assert "description" not in record
        assert "formats" not in record
        assert "subtitles" not in record


def test_collector_rejects_source_identity_mismatch(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reduced = dict(manifest)
    reduced["videos"] = [manifest["videos"][0]]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(reduced), encoding="utf-8")

    def fake_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"id": "wrong-id", "title": "wrong"}),
            stderr="",
        )

    with pytest.raises(ValueError, match="source identity mismatch"):
        collector.collect(
            manifest_path,
            tmp_path / "metadata.json",
            runner=fake_runner,
        )


def test_collector_rejects_manifest_without_discovery_only_policy(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["source_policy"]["classification"] = "training_corpus"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="discovery_only"):
        collector.collect(path, tmp_path / "metadata.json", runner=lambda *a, **k: None)


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/sskvj1_ehx4",
        "https://example.com/video",
        "file:///tmp/video.mp4",
    ],
)
def test_build_command_rejects_noncanonical_sources(url):
    with pytest.raises(ValueError, match="unsupported source URL"):
        collector.build_command("yt-dlp", url)
