#!/usr/bin/env python3
"""Collect normalized GothamChess source metadata without downloading media.

This helper intentionally invokes yt-dlp in metadata-only mode. Full videos,
audio, subtitles, descriptions, thumbnails, comments, and formats are neither
written nor copied into the repository.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "research/gothamchess-ai-agent-discovery-2026-10-14.json"
)
DEFAULT_OUTPUT = (
    ROOT / "data/private/gothamchess-ai-agent/yt-dlp-metadata.json"
)
OUTPUT_SCHEMA = "sports-play-llm.chess.creator-metadata-receipt.v1"
ALLOWED_METADATA_FIELDS = (
    "id",
    "title",
    "channel",
    "channel_id",
    "uploader",
    "uploader_id",
    "upload_date",
    "duration",
    "webpage_url",
    "availability",
)


def build_command(executable: str, url: str) -> list[str]:
    """Return the fixed metadata-only yt-dlp command."""
    if not executable.strip():
        raise ValueError("yt-dlp executable must be non-empty")
    if not url.startswith("https://www.youtube.com/watch?v="):
        raise ValueError(f"unsupported source URL: {url!r}")
    return [
        executable,
        "--skip-download",
        "--no-playlist",
        "--no-warnings",
        "--dump-single-json",
        url,
    ]


def normalize_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only the small public metadata surface required for provenance."""
    result = {
        field: payload[field]
        for field in ALLOWED_METADATA_FIELDS
        if field in payload and payload[field] is not None
    }
    if not isinstance(result.get("id"), str) or not result["id"]:
        raise ValueError("yt-dlp response did not contain a usable video id")
    return result


def _default_runner(
    command: Sequence[str],
    *,
    capture_output: bool,
    text: bool,
    check: bool,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
    )


def collect(
    manifest_path: Path,
    output_path: Path,
    *,
    executable: str = "yt-dlp",
    runner: Callable[..., subprocess.CompletedProcess[str]] = _default_runner,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = manifest.get("source_policy", {})
    if policy.get("classification") != "discovery_only":
        raise ValueError("manifest must retain discovery_only classification")

    videos = manifest.get("videos")
    if not isinstance(videos, list) or not videos:
        raise ValueError("manifest videos must be a non-empty array")

    records: list[dict[str, Any]] = []
    for video in videos:
        expected_id = video.get("youtube_id")
        url = video.get("watch_url")
        if not isinstance(expected_id, str) or not isinstance(url, str):
            raise ValueError("each manifest video requires youtube_id and watch_url")

        completed = runner(
            build_command(executable, url),
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        payload = json.loads(completed.stdout)
        normalized = normalize_metadata(payload)
        if normalized["id"] != expected_id:
            raise ValueError(
                f"source identity mismatch: expected {expected_id!r}, "
                f"received {normalized['id']!r}"
            )
        normalized["expected_title"] = video.get("title")
        normalized["expected_published_date"] = video.get("published_date")
        records.append(normalized)

    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    receipt = {
        "schema": OUTPUT_SCHEMA,
        "fetched_at_utc": fetched_at,
        "manifest_path": str(manifest_path),
        "collector": {
            "backend": "yt-dlp",
            "mode": "metadata_only",
            "media_downloaded": False,
            "subtitles_downloaded": False,
            "thumbnails_downloaded": False,
            "descriptions_retained": False,
        },
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--yt-dlp", default="yt-dlp", dest="executable")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = collect(
            args.manifest,
            args.output,
            executable=args.executable,
        )
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {len(receipt['records'])} metadata records to {args.output}; "
        "no media or subtitles were downloaded."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
