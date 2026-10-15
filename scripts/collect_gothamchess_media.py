#!/usr/bin/env python3
"""Discover GothamChess uploads and optionally retain private research copies.

Uses yt-dlp's supported Python embedding. No browser cookies, account login,
DRM workarounds, subtitle collection, or redistribution are implemented. Video
bytes and full extraction output stay in ignored data/private/gothamchess/.
The older metadata-only collector and its historical manifest are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "data/private/gothamchess"
CHANNEL_URL = "https://www.youtube.com/@GothamChess/videos"
CHANNEL_ID = "UCQHX6ViZmPsWiYSFAyS0a3Q"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
AI_TITLE = re.compile(r"\b(?:AI|GPT[- ]?\d*|ChatGPT|Claude|Gemini|Opus|Fable|Astra|Orion|Kuro|bots?)\b", re.I)
FIELDS = ("id", "title", "channel", "channel_id", "upload_date", "timestamp", "duration", "availability", "webpage_url")
MEDIA_SUFFIXES = {".mp4", ".webm", ".mkv", ".m4v"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def yt_dlp_version() -> str:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    result = {key: payload[key] for key in FIELDS if payload.get(key) is not None}
    if not VIDEO_ID.fullmatch(str(result.get("id", ""))):
        raise ValueError("extractor did not return a valid YouTube video id")
    result["webpage_url"] = f"https://www.youtube.com/watch?v={result['id']}"
    return result


def validate_source(item: dict[str, Any]) -> tuple[str, str]:
    video_id = item.get("youtube_id", item.get("id"))
    if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
        raise ValueError("source requires an 11-character YouTube id")
    url = f"https://www.youtube.com/watch?v={video_id}"
    if item.get("watch_url", item.get("webpage_url", url)) != url:
        raise ValueError("source URL does not match the declared video id")
    return video_id, url


def check_identity(payload: dict[str, Any], expected_id: str) -> None:
    if payload.get("id") != expected_id:
        raise ValueError("extracted video identity differs from requested source")
    if payload.get("channel_id") != CHANNEL_ID:
        raise ValueError("source is not from the verified GothamChess channel")
    availability = payload.get("availability")
    if availability not in (None, "public", "unlisted"):
        raise ValueError(f"source is not publicly accessible: {availability}")


def base_options() -> dict[str, Any]:
    return {
        "quiet": True,
        "noprogress": True,
        "no_warnings": False,
        "noplaylist": True,
        "retries": 2,
        "extractor_retries": 2,
        "socket_timeout": 25,
        "cachedir": False,
        "overwrites": False,
        "continuedl": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writethumbnail": False,
        "writeinfojson": False,
        "writedescription": False,
    }


def default_factory(options: dict[str, Any]) -> Any:
    import yt_dlp
    return yt_dlp.YoutubeDL(options)


def discover(output: Path, scan_limit: int = 40, *, factory: Callable = default_factory) -> dict[str, Any]:
    """Record the bounded recent-upload listing without claiming complete history."""
    if not 3 <= scan_limit <= 200:
        raise ValueError("scan limit must be between 3 and 200")
    receipt: dict[str, Any] = {
        "schema": "sports-play-llm.chess.creator-upload-scan.v1",
        "fetched_at_utc": utc_now(),
        "source_url": CHANNEL_URL,
        "scan_limit": scan_limit,
        "status": "started",
        "records": [],
        "media_downloaded": False,
    }
    write_receipt(output, receipt)
    options = {**base_options(), "skip_download": True, "extract_flat": "in_playlist", "playlistend": scan_limit}
    try:
        with factory(options) as ydl:
            payload = ydl.extract_info(CHANNEL_URL, download=False)
        if payload.get("channel_id", payload.get("id")) != CHANNEL_ID:
            raise ValueError("channel listing identity did not match GothamChess")
        for ordinal, entry in enumerate(payload.get("entries", []), 1):
            if entry is None:
                continue
            item = normalize(entry)
            item["channel_listing_ordinal"] = ordinal
            item["ai_title_candidate"] = bool(AI_TITLE.search(item.get("title", "")))
            receipt["records"].append(item)
        receipt["status"] = "completed"
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = safe_error(exc)
    receipt["finished_at_utc"] = utc_now()
    write_receipt(output, receipt)
    return receipt


def safe_error(exc: Exception) -> str:
    # Do not retain transient signed CDN URLs in versionable error summaries.
    return re.sub(r"https?://[^\s]+", "[URL omitted]", re.sub(r"\x1b\[[0-9;]*m", "", str(exc)))[:2000]


def file_record(path: Path, root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def collect(manifest_path: Path, output_root: Path, *, download: bool = False, factory: Callable = default_factory) -> dict[str, Any]:
    """Validate public source identity before each optional media acquisition.

    Each item's receipt is flushed before proceeding to the next item. Partial
    failures remain visible, and an existing complete file can be hashed again.
    Fake factories in tests exercise errors without fetching copyrighted media.
    """
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    sources = manifest.get("videos")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
        raise ValueError("manifest must identify one to three selected videos")
    validated = [validate_source(item) for item in sources]
    if len({item[0] for item in validated}) != len(validated):
        raise ValueError("manifest contains duplicate source ids")
    output_root.mkdir(parents=True, exist_ok=True)
    receipt_path = output_root / "collection-receipt.json"
    receipt: dict[str, Any] = {
        "schema": "sports-play-llm.chess.creator-private-media-receipt.v1",
        "started_at_utc": utc_now(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "mode": "private_media" if download else "metadata_only",
        "training_allowed": False,
        "redistribution_allowed": False,
        "collector": {
            "backend": "yt-dlp Python YoutubeDL",
            "yt_dlp_version": yt_dlp_version(),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "requested_format": "bv*[height<=720]+ba/b[height<=720]/b",
            "subtitles_downloaded": False,
            "cookies_used": False,
        },
        "records": [],
    }
    write_receipt(receipt_path, receipt)
    for expected_id, url in validated:
        item: dict[str, Any] = {"id": expected_id, "webpage_url": url, "status": "started", "files": []}
        receipt["records"].append(item)
        write_receipt(receipt_path, receipt)
        try:
            options = {**base_options(), "skip_download": True}
            with factory(options) as ydl:
                payload = ydl.extract_info(url, download=False)
            check_identity(payload, expected_id)
            item["metadata"] = normalize(payload)
            # Retain PGN link candidates only as discovery evidence; a URL is
            # neither a rights grant nor proof that its game matches the video.
            description = payload.get("description", "")
            item["pgn_link_candidates"] = sorted(set(re.findall(r"https?://[^\s<>\"]+\.pgn(?:\?[^\s<>\"]*)?", description, re.I)))
            if download:
                options = {
                    **base_options(),
                    "format": "bv*[height<=720]+ba/b[height<=720]/b",
                    "merge_output_format": "mp4",
                    "outtmpl": str(output_root / f"{expected_id}.%(ext)s"),
                }
                with factory(options) as ydl:
                    result = ydl.extract_info(url, download=True)
                check_identity(result, expected_id)
                paths = sorted(p for p in output_root.glob(f"{expected_id}.*") if p.is_file() and p.suffix in MEDIA_SUFFIXES and p.stem == expected_id)
                for path in paths:
                    item["files"].append(file_record(path, output_root))
                if not paths or not all(record["bytes"] > 0 for record in item["files"]):
                    raise ValueError("extractor returned without a nonempty final media file")
                item["status"] = "downloaded"
            else:
                item["status"] = "metadata_verified"
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = safe_error(exc)
        item["finished_at_utc"] = utc_now()
        write_receipt(receipt_path, receipt)
    receipt["finished_at_utc"] = utc_now()
    receipt["status"] = "completed" if all(item["status"] != "failed" for item in receipt["records"]) else "incomplete"
    write_receipt(receipt_path, receipt)
    return receipt


def private_destination(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PRIVATE_ROOT.resolve()):
        raise ValueError("destination must stay inside ignored data/private/gothamchess")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    scan = commands.add_parser("discover", help="list bounded recent channel uploads")
    scan.add_argument("--scan-limit", type=int, default=40)
    scan.add_argument("--output", type=Path, default=PRIVATE_ROOT / "latest-uploads.json")
    acquire = commands.add_parser("collect", help="validate chosen videos and optionally download private copies")
    acquire.add_argument("--manifest", type=Path, required=True)
    acquire.add_argument("--output-root", type=Path, default=PRIVATE_ROOT / "media")
    acquire.add_argument("--download", action="store_true", help="retain public media privately; never trains or redistributes")
    args = parser.parse_args(argv)
    try:
        if args.mode == "discover":
            receipt = discover(private_destination(args.output), args.scan_limit)
        else:
            receipt = collect(args.manifest, private_destination(args.output_root), download=args.download)
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: {safe_error(exc)}")
        return 1
    print(json.dumps({"status": receipt["status"], "records": len(receipt["records"])}))
    return 0 if receipt["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
