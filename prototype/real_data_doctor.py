"""Fail-closed integrity doctor for the private SoccerNet feasibility pilot."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / "data" / "private").resolve()
EXPECTED_MANIFEST_SCHEMA = "playground-soccernet-clips-manifest-v1"
EXPECTED_RECEIPT_SCHEMA = "playground-soccernet-acquisition-receipt-v1"
OPAQUE_CLIP_ID = re.compile(r"^(train|valid)-[0-9a-f]{8}-h[12]-[0-9]{3}$")
SECRET_KEYS = {"password", "passwd", "api_key", "apikey", "access_token", "refresh_token", "secret"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
        return True
    except (FileNotFoundError, ValueError, OSError):
        return False


def find_secret_keys(value: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SECRET_KEYS:
                hits.append(f"{prefix}.{key}")
            hits.extend(find_secret_keys(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_secret_keys(child, f"{prefix}[{index}]"))
    return hits


def validate_loopback_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("endpoint must be plain HTTP on loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain credentials, query, or fragment")
    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("endpoint path must be /v1")
    if parsed.port is None:
        raise ValueError("endpoint must include an explicit port")
    return endpoint.rstrip("/")


def probe_streams(ffmpeg: Path, media: Path) -> dict[str, int]:
    completed = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(media)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    diagnostic = completed.stderr
    return {
        "video": len(re.findall(r"Stream #.*Video:", diagnostic)),
        "audio": len(re.findall(r"Stream #.*Audio:", diagnostic)),
    }


def validate_stream_role(streams: dict[str, int], *, expected_audio: int) -> None:
    if streams.get("video", 0) < 1 or streams.get("audio") != expected_audio:
        raise ValueError("derived media stream isolation failed")


def sanitized_failure_report(exc: Exception) -> dict[str, str]:
    return {
        "schema_version": "playground-real-data-doctor-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "error_code": type(exc).__name__,
    }


def dependency_versions() -> dict[str, str]:
    packages = {
        "SoccerNet": "SoccerNet",
        "rapidocr_onnxruntime": "rapidocr-onnxruntime",
        "cv2": "opencv-python-headless",
        "numpy": "numpy",
        "imageio_ffmpeg": "imageio-ffmpeg",
        "pytest": "pytest",
    }
    versions: dict[str, str] = {}
    for module_name, distribution_name in packages.items():
        importlib.import_module(module_name)
        try:
            versions[distribution_name] = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            module = importlib.import_module(module_name)
            versions[distribution_name] = str(getattr(module, "__version__", "installed"))
    return versions


def verify_receipt(receipt_path: Path, source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != EXPECTED_RECEIPT_SCHEMA or receipt.get("provider") != "SoccerNet":
        raise ValueError("unsupported acquisition receipt")
    if find_secret_keys(receipt):
        raise ValueError("acquisition receipt contains a secret-shaped key")
    authorization = receipt.get("authorization", {})
    if authorization.get("credential_persisted") is not False:
        raise ValueError("credential_persisted must be false")
    if authorization.get("redistribution_allowed") is not False:
        raise ValueError("redistribution_allowed must be false")
    game = receipt.get("selection", {}).get("game")
    split = receipt.get("selection", {}).get("split")
    if not isinstance(game, str) or not game or split not in {"train", "valid"}:
        raise ValueError("receipt selection is invalid")
    verified_files: list[dict[str, Any]] = []
    for item in receipt.get("downloaded_files", []):
        relative_path = item.get("relative_path")
        if not isinstance(relative_path, str):
            raise ValueError("download receipt path is invalid")
        candidate = source_root / Path(relative_path)
        if not is_within(candidate, source_root):
            raise ValueError("downloaded source escaped the private source root")
        if candidate.stat().st_size != item.get("bytes") or sha256_file(candidate) != item.get("sha256"):
            raise ValueError("downloaded source hash or byte count is stale")
        verified_files.append({"name": item.get("name"), "bytes": item["bytes"], "sha256": item["sha256"]})
    if not verified_files:
        raise ValueError("receipt has no downloaded files")
    return receipt, {
        "split": split,
        "receipt_sha256": sha256_file(receipt_path),
        "file_count": len(verified_files),
        "files": verified_files,
    }


def verify_manifest(
    manifest_path: Path, receipt_path: Path, source_root: Path, echoes_root: Path, ffmpeg: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt, receipt_public = verify_receipt(receipt_path, source_root)
    if manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA:
        raise ValueError("unsupported derived manifest schema")
    if manifest.get("provider") != "SoccerNet" or manifest.get("split") != receipt["selection"]["split"]:
        raise ValueError("manifest provider/split does not match the receipt")
    if manifest.get("acquisition_receipt_sha256") != sha256_file(receipt_path):
        raise ValueError("manifest acquisition receipt hash is stale")
    source_by_name = {item["name"]: item for item in receipt["downloaded_files"]}
    video_item = source_by_name.get(f"{manifest.get('source_half')}_224p.mkv")
    label_item = source_by_name.get("Labels-v2.json")
    if not video_item or not label_item:
        raise ValueError("receipt lacks the authorized video or labels")
    if manifest.get("source_video_sha256") != video_item["sha256"]:
        raise ValueError("manifest source video hash does not match receipt")
    if manifest.get("source_labels_sha256") != label_item["sha256"]:
        raise ValueError("manifest source labels hash does not match receipt")
    transcript_path = (
        echoes_root / "Dataset" / "whisper_v2_en" / Path(receipt["selection"]["game"])
        / f"{manifest.get('source_half')}_asr.json"
    )
    if not is_within(transcript_path, echoes_root):
        raise ValueError("Echoes transcript escaped the public source root")
    if sha256_file(transcript_path) != manifest.get("echoes_transcript_sha256"):
        raise ValueError("manifest Echoes transcript hash is stale")
    rights = manifest.get("rights", {})
    if rights.get("redistribution_allowed") is not False or rights.get("credential_persisted") is not False:
        raise ValueError("manifest rights boundary is invalid")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("manifest contains no clips")
    seen: set[str] = set()
    public_clips: list[dict[str, Any]] = []
    for clip in clips:
        clip_id = clip.get("clip_id")
        if not isinstance(clip_id, str) or not OPAQUE_CLIP_ID.fullmatch(clip_id) or clip_id in seen:
            raise ValueError("clip IDs must be unique and opaque")
        seen.add(clip_id)
        if clip.get("split") != manifest["split"] or clip.get("source_half") != manifest.get("source_half"):
            raise ValueError("clip split/half does not match its manifest")
        duration = float(clip.get("clip_duration_s", -1))
        if not 5.0 <= duration <= 10.0:
            raise ValueError("derived clips must be 5 to 10 seconds")
        streams_public: dict[str, dict[str, int]] = {}
        for field, expected_audio in (("visual_only", 0), ("local_review_with_audio", 1)):
            media = clip.get(field, {})
            candidate = Path(str(media.get("path", "")))
            if not is_within(candidate, PRIVATE_ROOT):
                raise ValueError("derived media escaped data/private")
            if candidate.stat().st_size != media.get("bytes") or sha256_file(candidate) != media.get("sha256"):
                raise ValueError("derived media hash or byte count is stale")
            streams = probe_streams(ffmpeg, candidate)
            validate_stream_role(streams, expected_audio=expected_audio)
            streams_public[field] = streams
        commentary_meta = clip.get("commentary", {})
        commentary_path = Path(str(commentary_meta.get("path", "")))
        if not is_within(commentary_path, PRIVATE_ROOT):
            raise ValueError("commentary evidence escaped data/private")
        if sha256_file(commentary_path) != commentary_meta.get("sha256"):
            raise ValueError("commentary evidence hash is stale")
        commentary = json.loads(commentary_path.read_text(encoding="utf-8"))
        if commentary.get("clip_id") != clip_id or commentary.get("source_half") != clip.get("source_half"):
            raise ValueError("commentary evidence is bound to the wrong clip")
        if commentary.get("source_transcript_sha256") != manifest.get("echoes_transcript_sha256"):
            raise ValueError("commentary transcript source hash is stale")
        if abs(float(commentary.get("clip_duration_s", -1)) - duration) > 0.05:
            raise ValueError("commentary duration does not match clip duration")
        segments = commentary.get("segments", [])
        if len(segments) != commentary_meta.get("segment_count"):
            raise ValueError("commentary segment count is stale")
        for segment in segments:
            start = float(segment.get("clip_relative_start_s", -1))
            end = float(segment.get("clip_relative_end_s", -1))
            if start < 0 or end <= start or end > duration + 0.05:
                raise ValueError("commentary segment is outside clip bounds")
        public_clips.append({
            "clip_id": clip_id,
            "visual_sha256": clip["visual_only"]["sha256"],
            "review_sha256": clip["local_review_with_audio"]["sha256"],
            "commentary_sha256": commentary_meta["sha256"],
            "streams": streams_public,
        })
    return manifest, {
        "split": manifest["split"],
        "manifest_sha256": sha256_file(manifest_path),
        "receipt": receipt_public,
        "clip_count": len(public_clips),
        "clips": public_clips,
    }


def endpoint_health(endpoint: str, model: str) -> dict[str, Any]:
    base = validate_loopback_endpoint(endpoint)
    opener = build_opener(ProxyHandler({}))
    request = Request(base + "/models", method="GET", headers={"Accept": "application/json"})
    with opener.open(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    ids = {item.get("id") for item in payload.get("data", []) if isinstance(item, dict)}
    if model not in ids:
        raise ValueError("requested model is not advertised by the loopback endpoint")
    return {
        "boundary": "loopback-only",
        "status": "ready",
        "requested_model": model,
        "requested_model_available": True,
    }


def build_report(
    *, train_manifest: Path, valid_manifest: Path, train_receipt: Path, valid_receipt: Path,
    source_root: Path, echoes_root: Path, endpoint: str, model: str,
) -> dict[str, Any]:
    expected_python = (ROOT / ".venv-soccernet" / "Scripts" / "python.exe").resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise ValueError("doctor must run with .venv-soccernet\\Scripts\\python.exe")
    versions = dependency_versions()
    import imageio_ffmpeg
    ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve(strict=True)
    ffmpeg_version = subprocess.run(
        [str(ffmpeg), "-version"], capture_output=True, text=True, timeout=10, check=True,
    ).stdout.splitlines()[0]
    train, train_public = verify_manifest(train_manifest, train_receipt, source_root, echoes_root, ffmpeg)
    valid, valid_public = verify_manifest(valid_manifest, valid_receipt, source_root, echoes_root, ffmpeg)
    if train.get("split") != "train" or valid.get("split") != "valid":
        raise ValueError("expected disjoint train and valid splits")
    if train.get("source_game") == valid.get("source_game"):
        raise ValueError("train and valid manifests refer to the same game")
    if {item["clip_id"] for item in train["clips"]} & {item["clip_id"] for item in valid["clips"]}:
        raise ValueError("train and valid clip IDs overlap")
    return {
        "schema_version": "playground-real-data-doctor-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "python": {"version": sys.version.split()[0], "environment": ".venv-soccernet"},
        "dependencies": versions,
        "ffmpeg": {"version": ffmpeg_version},
        "splits": [train_public, valid_public],
        "train_valid_disjoint": True,
        "endpoint": endpoint_health(endpoint, model),
        "rights_boundary": {"private_media": True, "redistribution_allowed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", type=Path, default=ROOT / "data/private/soccerdb-overlap-derived/train-game-000-v1-manifest.json")
    parser.add_argument("--valid-manifest", type=Path, default=ROOT / "data/private/soccerdb-overlap-derived/valid-game-000-v1-manifest.json")
    parser.add_argument("--train-receipt", type=Path, default=ROOT / "artifacts/soccernet-private-receipt/soccerdb-overlap-train-game-000.json")
    parser.add_argument("--valid-receipt", type=Path, default=ROOT / "artifacts/soccernet-private-receipt/soccerdb-overlap-valid-game-000.json")
    parser.add_argument("--source-root", type=Path, default=ROOT / "data/private/soccernet-soccerdb-overlap")
    parser.add_argument("--echoes-root", type=Path, default=ROOT / "data/public/sn-echoes")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="google/gemma-4-e4b")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/soccernet-pilot-v1/real-data-doctor.json")
    args = parser.parse_args()
    try:
        report = build_report(
            train_manifest=args.train_manifest, valid_manifest=args.valid_manifest,
            train_receipt=args.train_receipt, valid_receipt=args.valid_receipt,
            source_root=args.source_root, echoes_root=args.echoes_root,
            endpoint=args.endpoint, model=args.model,
        )
    except Exception as exc:
        report = sanitized_failure_report(exc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "splits": [s["clip_count"] for s in report["splits"]], "endpoint": report["endpoint"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
