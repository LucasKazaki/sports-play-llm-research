"""Build opaque, event-centered SoccerNet clips for visual-only VLM evaluation.

Official labels select evaluation windows and remain outside the model request.
Each event produces a silent MP4 for the VLM, an audio-bearing local review MP4,
and an independently aligned SoccerNet-Echoes transcript record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2


SOCCERNET_TO_PLAY_TYPE = {
    "Penalty": "penalty_kick",
    "Kick-off": "kick_off",
    "Goal": "goal",
    "Substitution": "substitution",
    "Offside": "offside",
    "Shots on target": "shot_on_target",
    "Shots off target": "shot_off_target",
    "Clearance": "clearance",
    "Ball out of play": "ball_out_of_play",
    "Throw-in": "throw_in",
    "Foul": "foul",
    "Indirect free-kick": "indirect_free_kick",
    "Direct free-kick": "direct_free_kick",
    "Corner": "corner_kick",
    "Yellow card": "yellow_card",
    "Red card": "red_card",
    "Yellow->red card": "second_yellow_red_card",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def half_annotations(labels: dict[str, Any], *, half: int) -> list[dict[str, Any]]:
    prefix = f"{half} - "
    annotations = labels.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("labels must contain an annotations list")
    return [item for item in annotations if str(item.get("gameTime", "")).startswith(prefix)]


def select_visible_events(
    labels: dict[str, Any], *, half: int, source_labels: Iterable[str], occurrence: int = 0,
) -> list[dict[str, Any]]:
    if occurrence < 0:
        raise ValueError("occurrence must be non-negative")
    half_items = half_annotations(labels, half=half)
    selected: list[dict[str, Any]] = []
    for source_label in source_labels:
        if source_label not in SOCCERNET_TO_PLAY_TYPE:
            raise ValueError(f"unknown SoccerNet-v2 label: {source_label}")
        candidates = [
            item for item in half_items
            if item.get("label") == source_label and item.get("visibility") == "visible"
        ]
        if occurrence >= len(candidates):
            raise ValueError(
                f"requested occurrence {occurrence} for {source_label}, but only {len(candidates)} visible events exist"
            )
        selected.append(candidates[occurrence])
    return selected


def transcript_segments(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    raw = transcript.get("segments")
    if not isinstance(raw, dict):
        raise ValueError("Echoes transcript must contain a segments object")
    normalized: list[dict[str, Any]] = []
    for key, value in raw.items():
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError(f"invalid transcript segment {key}")
        normalized.append({
            "segment_id": str(key),
            "start_s": float(value[0]),
            "end_s": float(value[1]),
            "text": str(value[2]).strip(),
        })
    return sorted(normalized, key=lambda item: (item["start_s"], item["end_s"]))


def overlapping_segments(
    segments: Iterable[dict[str, Any]], *, start_s: float, end_s: float,
) -> list[dict[str, Any]]:
    return [
        item for item in segments
        if float(item["end_s"]) > start_s and float(item["start_s"]) < end_s
    ]


def run_ffmpeg(arguments: list[str]) -> None:
    import imageio_ffmpeg

    executable = imageio_ffmpeg.get_ffmpeg_exe()
    completed = subprocess.run(
        [executable, "-hide_banner", "-loglevel", "error", *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({completed.returncode}): {completed.stderr.strip()}")


def probe_streams(path: Path) -> dict[str, int]:
    import imageio_ffmpeg

    completed = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, check=False,
    )
    diagnostic = completed.stderr
    return {
        "video_stream_count": len(re.findall(r"Stream #.*?: Video:", diagnostic)),
        "audio_stream_count": len(re.findall(r"Stream #.*?: Audio:", diagnostic)),
    }


def media_metadata(path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open generated video: {path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok, first = cap.read()
    cap.release()
    if not ok or first is None or frame_count < 1 or fps <= 0:
        raise RuntimeError(f"generated video failed decode verification: {path}")
    streams = probe_streams(path)
    if streams["video_stream_count"] < 1:
        raise RuntimeError(f"generated video has no video stream: {path}")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "frame_count": frame_count,
        "fps": fps,
        "duration_s": frame_count / fps,
        "width": width,
        "height": height,
        **streams,
    }


def build(
    *, game_directory: Path, split: str, half: int, source_labels: list[str],
    echoes_transcript: Path, out_dir: Path, manifest_path: Path,
    acquisition_receipt: Path, seconds_before: float, seconds_after: float, occurrence: int,
) -> dict[str, Any]:
    source_video = game_directory / f"{half}_224p.mkv"
    labels_path = game_directory / "Labels-v2.json"
    if not source_video.is_file() or not labels_path.is_file() or not echoes_transcript.is_file() or not acquisition_receipt.is_file():
        missing = [str(path) for path in (source_video, labels_path, echoes_transcript, acquisition_receipt) if not path.is_file()]
        raise FileNotFoundError(f"missing source files: {missing}")
    out_resolved = out_dir.resolve()
    out_parts = [part.lower() for part in out_resolved.parts]
    if not any(out_parts[index:index + 2] == ["data", "private"] for index in range(len(out_parts) - 1)):
        raise ValueError("derived SoccerNet media must remain under data/private")
    if echoes_transcript.parent.name != game_directory.name or echoes_transcript.name != f"{half}_asr.json":
        raise ValueError("Echoes transcript path does not match the selected game and half")
    receipt = json.loads(acquisition_receipt.read_text(encoding="utf-8"))
    if receipt.get("provider") != "SoccerNet" or receipt.get("authorization", {}).get("credential_persisted") is not False:
        raise ValueError("acquisition receipt does not prove the expected SoccerNet private-access boundary")
    receipt_hashes = {item["name"]: item["sha256"] for item in receipt.get("downloaded_files", [])}
    if receipt_hashes.get(source_video.name) != sha256_file(source_video) or receipt_hashes.get("Labels-v2.json") != sha256_file(labels_path):
        raise ValueError("acquisition receipt hashes do not match source video and labels")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    transcript = json.loads(echoes_transcript.read_text(encoding="utf-8"))
    asr_segments = transcript_segments(transcript)
    events = select_visible_events(
        labels, half=half, source_labels=source_labels, occurrence=occurrence,
    )
    all_half_events = half_annotations(labels, half=half)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    duration = seconds_before + seconds_after

    for ordinal, event in enumerate(events, start=1):
        event_s = float(event["position"]) / 1000.0
        clip_start_s = max(0.0, event_s - seconds_before)
        game_key = hashlib.sha256(game_directory.name.encode("utf-8")).hexdigest()[:8]
        clip_id = f"{split}-{game_key}-h{half}-{ordinal:03d}"
        silent_path = out_dir / f"{clip_id}-visual-only.mp4"
        review_path = out_dir / f"{clip_id}-local-review-with-audio.mp4"
        transcript_path = out_dir / f"{clip_id}-commentary.json"

        common = [
            "-ss", f"{clip_start_s:.3f}", "-i", str(source_video),
            "-t", f"{duration:.3f}", "-map", "0:v:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        ]
        run_ffmpeg([*common, "-an", "-y", str(silent_path)])
        run_ffmpeg([
            *common, "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k",
            "-y", str(review_path),
        ])
        aligned = overlapping_segments(
            asr_segments, start_s=clip_start_s, end_s=clip_start_s + duration,
        )
        visible_events_in_window = [
            item for item in all_half_events
            if item.get("visibility") == "visible"
            and item.get("label") in SOCCERNET_TO_PLAY_TYPE
            and clip_start_s <= float(item["position"]) / 1000.0 <= clip_start_s + duration
        ]
        allowed_play_types = sorted({
            SOCCERNET_TO_PLAY_TYPE[item["label"]] for item in visible_events_in_window
        })
        transcript_record = {
            "schema_version": "playground-commentary-evidence-v1",
            "clip_id": clip_id,
            "source": "SoccerNet-Echoes",
            "asr_variant": echoes_transcript.parts[echoes_transcript.parts.index("Dataset") + 1]
            if "Dataset" in echoes_transcript.parts else "unknown",
            "source_transcript_sha256": sha256_file(echoes_transcript),
            "source_half": half,
            "clip_start_in_half_s": clip_start_s,
            "clip_duration_s": duration,
            "segments": [
                {
                    **item,
                    "clip_relative_start_s": max(0.0, item["start_s"] - clip_start_s),
                    "clip_relative_end_s": min(duration, item["end_s"] - clip_start_s),
                }
                for item in aligned
            ],
            "warning": "ASR commentary is a noisy post-hoc check, not ground truth and not VLM input.",
        }
        write_json(transcript_path, transcript_record)
        silent_metadata = media_metadata(silent_path)
        review_metadata = media_metadata(review_path)
        if silent_metadata["audio_stream_count"] != 0:
            raise RuntimeError(f"visual-only clip unexpectedly contains audio: {silent_path}")
        if review_metadata["audio_stream_count"] < 1:
            raise RuntimeError(f"review clip does not contain commentator audio: {review_path}")
        records.append({
            "clip_id": clip_id,
            "split": split,
            "source_half": half,
            "source_event_time_s": event_s,
            "clip_start_in_half_s": clip_start_s,
            "clip_duration_s": duration,
            "ground_truth": {
                "soccernet_label": event["label"],
                "play_type": SOCCERNET_TO_PLAY_TYPE[event["label"]],
                "visibility": event["visibility"],
                "allowed_play_types_in_window": allowed_play_types,
                "single_label_eligible": len(allowed_play_types) == 1,
                "visible_events_in_window": [
                    {
                        "soccernet_label": item["label"],
                        "play_type": SOCCERNET_TO_PLAY_TYPE[item["label"]],
                        "event_time_s": float(item["position"]) / 1000.0,
                    }
                    for item in visible_events_in_window
                ],
            },
            "visual_only": silent_metadata,
            "local_review_with_audio": review_metadata,
            "commentary": {
                "path": str(transcript_path),
                "sha256": sha256_file(transcript_path),
                "segment_count": len(aligned),
            },
        })

    manifest = {
        "schema_version": "playground-soccernet-clips-manifest-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": "SoccerNet",
        "split": split,
        "source_game": game_directory.name,
        "source_half": half,
        "source_video_sha256": sha256_file(source_video),
        "source_labels_sha256": sha256_file(labels_path),
        "echoes_transcript_sha256": sha256_file(echoes_transcript),
        "acquisition_receipt_sha256": sha256_file(acquisition_receipt),
        "selection": {
            "labels": source_labels,
            "occurrence": occurrence,
            "visibility": "visible",
            "seconds_before": seconds_before,
            "seconds_after": seconds_after,
        },
        "model_input_policy": "Only visual_only files may be sent to the VLM; labels and commentary are held out.",
        "rights": receipt["authorization"],
        "clips": records,
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-directory", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "valid", "test"), required=True)
    parser.add_argument("--half", type=int, choices=(1, 2), default=1)
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--echoes-transcript", type=Path, required=True)
    parser.add_argument("--acquisition-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seconds-before", type=float, default=5.0)
    parser.add_argument("--seconds-after", type=float, default=5.0)
    parser.add_argument("--occurrence", type=int, default=0)
    args = parser.parse_args()
    manifest = build(
        game_directory=args.game_directory, split=args.split, half=args.half,
        source_labels=args.labels, echoes_transcript=args.echoes_transcript,
        out_dir=args.out, manifest_path=args.manifest, acquisition_receipt=args.acquisition_receipt,
        seconds_before=args.seconds_before, seconds_after=args.seconds_after,
        occurrence=args.occurrence,
    )
    print(json.dumps({
        "status": "clips_built_and_verified",
        "split": manifest["split"],
        "clip_count": len(manifest["clips"]),
        "clip_ids": [item["clip_id"] for item in manifest["clips"]],
        "manifest": str(args.manifest),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
