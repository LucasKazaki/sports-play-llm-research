"""Verify the published SoccerDB-to-SoccerNet identity binding, fail closed.

This verifier deliberately reads only metadata.  The resulting artifact names
the public mapping rows and cryptographic receipts/manifests, but never emits a
private filesystem path, a download URL, or an access credential.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAPPING_SCHEMA_VERSION = "playground-soccerdb-soccernet-overlap-binding-v1"
RECEIPT_SCHEMA_VERSION = "playground-soccernet-acquisition-receipt-v1"
MANIFEST_SCHEMA_VERSION = "playground-soccernet-clips-manifest-v1"
MAPPING_REPOSITORY = "https://github.com/newsdata/SoccerDB"
MAPPING_COMMIT = "ac9c9c50d14b683b8eca464f55a700cffb95b629"
MAPPING_RELATIVE_PATH = "dataset/video_dataset/SoccerDB2SoccerNet.csv"
MAPPING_SOURCE_URL = (
    f"https://raw.githubusercontent.com/newsdata/SoccerDB/{MAPPING_COMMIT}/"
    f"{MAPPING_RELATIVE_PATH}"
)
EXPECTED_MAPPING_SHA256 = "53c445988019ee4b50ed408fae949f903a90afbe02158c62296559a769493b02"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_CLIP_ID = re.compile(r"^(train|valid)-[0-9a-f]{8}-h[12]-[0-9]{3}$")
_SOCCERDB_MAPPED_MEDIA_NAME = re.compile(r"^[0-9a-f]{30,34}_[12]\.mkv$")
_SOCCERDB_UNMAPPED_MEDIA_NAME = re.compile(r"^[0-9a-f]{30,34}\.mp4$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_SECRET_KEYS = {
    "password", "passwd", "api_key", "apikey", "access_token",
    "refresh_token", "secret", "authorization_header",
}


@dataclass(frozen=True)
class ExpectedBinding:
    split: str
    soccerdb_media_name: str
    soccernet_game: str
    source_half: int

    @property
    def soccernet_media_name(self) -> str:
        return f"{self.soccernet_game}/{self.source_half}.mkv"


EXPECTED_BINDINGS = {
    "train": ExpectedBinding(
        split="train",
        soccerdb_media_name="89dd050adc1811e897b86c96cfde8f_1.mkv",
        soccernet_game=(
            "europe_uefa-champions-league/2015-2016/"
            "2015-11-24 - 22-45 Barcelona 6 - 1 AS Roma"
        ),
        source_half=1,
    ),
    "valid": ExpectedBinding(
        split="valid",
        soccerdb_media_name="84d91850dc1811e897b86c96cfde8f_1.mkv",
        soccernet_game=(
            "europe_uefa-champions-league/2015-2016/"
            "2015-11-04 - 22-45 Barcelona 3 - 0 BATE"
        ),
        source_half=1,
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path, kind: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{kind} must be a JSON object")
    return value


def _secret_key_paths(value: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SECRET_KEYS:
                hits.append(f"{prefix}.{key}")
            hits.extend(_secret_key_paths(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_secret_key_paths(child, f"{prefix}[{index}]"))
    return hits


def _validate_relative_posix_path(value: str, kind: str) -> None:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or "\\" in value or ".." in path.parts:
        raise ValueError(f"{kind} must be a safe relative POSIX identity")


def load_published_mapping(mapping_path: Path) -> tuple[list[dict[str, str]], str]:
    """Load only the hash-pinned, two-column mapping published by SoccerDB."""
    mapping_sha256 = sha256_file(mapping_path)
    if mapping_sha256 != EXPECTED_MAPPING_SHA256:
        raise ValueError("published SoccerDB mapping SHA-256 mismatch")
    with mapping_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["SoccerDB Name", "SoccerNet Name"]:
            raise ValueError("published SoccerDB mapping has an unexpected header")
        rows = list(reader)
    if not rows:
        raise ValueError("published SoccerDB mapping contains no rows")
    for row in rows:
        if set(row) != {"SoccerDB Name", "SoccerNet Name"}:
            raise ValueError("published SoccerDB mapping contains an unexpected column")
        soccerdb_name = row["SoccerDB Name"]
        soccernet_name = row["SoccerNet Name"]
        if not isinstance(soccerdb_name, str) or not isinstance(soccernet_name, str):
            raise ValueError("published SoccerDB mapping contains a non-string media name")
        if soccernet_name:
            if not _SOCCERDB_MAPPED_MEDIA_NAME.fullmatch(soccerdb_name):
                raise ValueError("published SoccerDB mapping contains an invalid mapped SoccerDB media name")
            if not soccernet_name.endswith(".mkv"):
                raise ValueError("published SoccerDB mapping contains an invalid SoccerNet media name")
            _validate_relative_posix_path(soccernet_name, "SoccerNet media name")
        elif not _SOCCERDB_UNMAPPED_MEDIA_NAME.fullmatch(soccerdb_name):
            raise ValueError("published SoccerDB mapping contains an invalid unmapped SoccerDB media name")
    return rows, mapping_sha256


def _downloaded_file(receipt: dict[str, Any], name: str) -> dict[str, Any]:
    files = receipt.get("downloaded_files")
    if not isinstance(files, list):
        raise ValueError("acquisition receipt downloaded_files must be a list")
    matches = [item for item in files if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"acquisition receipt must bind exactly one {name}")
    item = matches[0]
    digest = item.get("sha256")
    relative_path = item.get("relative_path")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("acquisition receipt contains an invalid file hash")
    if not isinstance(relative_path, str):
        raise ValueError("acquisition receipt contains an invalid relative path")
    _validate_relative_posix_path(relative_path, "receipt file path")
    return item


def verify_binding_pair(
    *, expected: ExpectedBinding, mapping_rows: list[dict[str, str]],
    receipt_path: Path, manifest_path: Path,
) -> tuple[dict[str, Any], set[str]]:
    """Bind one private receipt/manifest pair to one exact public mapping row."""
    receipt = _json_object(receipt_path, "acquisition receipt")
    manifest = _json_object(manifest_path, "derived manifest")
    if _secret_key_paths(receipt) or _secret_key_paths(manifest):
        raise ValueError("private metadata contains a secret-shaped key")
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION or receipt.get("provider") != "SoccerNet":
        raise ValueError("unsupported SoccerNet acquisition receipt")
    authorization = receipt.get("authorization")
    if not isinstance(authorization, dict):
        raise ValueError("acquisition receipt authorization boundary is missing")
    if authorization.get("credential_persisted") is not False:
        raise ValueError("acquisition receipt must attest credential_persisted=false")
    if authorization.get("redistribution_allowed") is not False:
        raise ValueError("acquisition receipt must attest redistribution_allowed=false")
    selection = receipt.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("acquisition receipt selection is missing")
    if selection.get("split") != expected.split or selection.get("game") != expected.soccernet_game:
        raise ValueError(f"{expected.split} receipt does not identify the expected SoccerNet match")
    _validate_relative_posix_path(expected.soccernet_game, "expected SoccerNet game")

    source_video = _downloaded_file(receipt, f"{expected.source_half}_224p.mkv")
    source_labels = _downloaded_file(receipt, "Labels-v2.json")
    expected_video_relative_path = f"{expected.soccernet_game}/{expected.source_half}_224p.mkv"
    expected_labels_relative_path = f"{expected.soccernet_game}/Labels-v2.json"
    if source_video.get("relative_path") != expected_video_relative_path:
        raise ValueError("acquisition receipt video path does not match the expected match and half")
    if source_labels.get("relative_path") != expected_labels_relative_path:
        raise ValueError("acquisition receipt label path does not match the expected match")

    receipt_sha256 = sha256_file(receipt_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION or manifest.get("provider") != "SoccerNet":
        raise ValueError("unsupported SoccerNet derived manifest")
    if manifest.get("split") != expected.split:
        raise ValueError("derived manifest split does not match the expected binding")
    if manifest.get("acquisition_receipt_sha256") != receipt_sha256:
        raise ValueError("derived manifest acquisition receipt hash is stale")
    if manifest.get("source_game") != PurePosixPath(expected.soccernet_game).name:
        raise ValueError("derived manifest source game does not match the expected binding")
    if manifest.get("source_half") != expected.source_half:
        raise ValueError("derived manifest source half does not match the expected binding")
    if manifest.get("source_video_sha256") != source_video["sha256"]:
        raise ValueError("derived manifest source video hash does not match its receipt")
    if manifest.get("source_labels_sha256") != source_labels["sha256"]:
        raise ValueError("derived manifest source label hash does not match its receipt")
    rights = manifest.get("rights")
    if not isinstance(rights, dict):
        raise ValueError("derived manifest rights boundary is missing")
    if rights.get("credential_persisted") is not False or rights.get("redistribution_allowed") is not False:
        raise ValueError("derived manifest rights boundary is invalid")

    matching_rows = [row for row in mapping_rows if row["SoccerNet Name"] == expected.soccernet_media_name]
    if len(matching_rows) != 1:
        raise ValueError(f"published mapping must contain exactly one {expected.split} SoccerNet media identity")
    mapped_soccerdb_name = matching_rows[0]["SoccerDB Name"]
    if mapped_soccerdb_name != expected.soccerdb_media_name:
        raise ValueError(f"published mapping {expected.split} SoccerDB media identity is unexpected")

    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("derived manifest contains no clips")
    clip_ids: list[str] = []
    for clip in clips:
        if not isinstance(clip, dict):
            raise ValueError("derived manifest contains an invalid clip record")
        clip_id = clip.get("clip_id")
        if (
            not isinstance(clip_id, str)
            or not _OPAQUE_CLIP_ID.fullmatch(clip_id)
            or not clip_id.startswith(expected.split + "-")
            or clip.get("split") != expected.split
            or clip.get("source_half") != expected.source_half
        ):
            raise ValueError("derived manifest clip identity does not match its binding")
        clip_ids.append(clip_id)
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError("derived manifest clip IDs must be unique")

    public_binding = {
        "split": expected.split,
        "soccerdb_media_name": mapped_soccerdb_name,
        "soccernet_media_name": expected.soccernet_media_name,
        "source_half": expected.source_half,
        "receipt_sha256": receipt_sha256,
        "manifest_sha256": sha256_file(manifest_path),
        "clip_count": len(clip_ids),
        "clip_ids": clip_ids,
        "identity_match": True,
    }
    return public_binding, set(clip_ids)


def _assert_public_safe(value: Any) -> None:
    if _secret_key_paths(value):
        raise ValueError("public binding artifact contains a secret-shaped key")

    def walk(child: Any) -> None:
        if isinstance(child, dict):
            for item in child.values():
                walk(item)
        elif isinstance(child, list):
            for item in child:
                walk(item)
        elif isinstance(child, str):
            normalized = child.replace("\\", "/").lower()
            if (
                _WINDOWS_ABSOLUTE_PATH.match(child)
                or child.startswith("\\\\")
                or "/data/private/" in "/" + normalized.strip("/") + "/"
            ):
                raise ValueError("public binding artifact contains a private or absolute path")

    walk(value)


def build_binding_report(
    *, mapping_path: Path, train_receipt_path: Path, valid_receipt_path: Path,
    train_manifest_path: Path, valid_manifest_path: Path,
) -> dict[str, Any]:
    rows, mapping_sha256 = load_published_mapping(mapping_path)
    bindings: list[dict[str, Any]] = []
    split_clip_ids: dict[str, set[str]] = {}
    for split, receipt_path, manifest_path in (
        ("train", train_receipt_path, train_manifest_path),
        ("valid", valid_receipt_path, valid_manifest_path),
    ):
        binding, clip_ids = verify_binding_pair(
            expected=EXPECTED_BINDINGS[split],
            mapping_rows=rows,
            receipt_path=receipt_path,
            manifest_path=manifest_path,
        )
        bindings.append(binding)
        split_clip_ids[split] = clip_ids
    if split_clip_ids["train"] & split_clip_ids["valid"]:
        raise ValueError("train and valid clip IDs overlap")
    if bindings[0]["soccerdb_media_name"] == bindings[1]["soccerdb_media_name"]:
        raise ValueError("train and valid bindings resolve to the same SoccerDB media")

    report = {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "mapping": {
            "repository": MAPPING_REPOSITORY,
            "commit": MAPPING_COMMIT,
            "relative_path": MAPPING_RELATIVE_PATH,
            "source_url": MAPPING_SOURCE_URL,
            "sha256": mapping_sha256,
        },
        "bindings": bindings,
        "train_valid_disjoint": True,
        "claim_boundary": (
            "These are SoccerNet match halves identified by SoccerDB's published mapping; "
            "the evaluation labels remain SoccerNet-v2 point labels, not SoccerDB event segments."
        ),
        "rights_boundary": {
            "private_media": True,
            "credential_persisted": False,
            "redistribution_allowed": False,
        },
    }
    _assert_public_safe(report)
    return report


def write_report_exclusive(path: Path, report: dict[str, Any]) -> None:
    _assert_public_safe(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as sink:
            sink.write(payload)
    except FileExistsError as exc:
        raise FileExistsError("refusing to overwrite an existing overlap binding artifact") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mapping", type=Path,
        default=ROOT / "data/public/SoccerDB-metadata" / MAPPING_RELATIVE_PATH,
    )
    parser.add_argument(
        "--train-receipt", type=Path,
        default=ROOT / "artifacts/soccernet-private-receipt/soccerdb-overlap-train-game-000.json",
    )
    parser.add_argument(
        "--valid-receipt", type=Path,
        default=ROOT / "artifacts/soccernet-private-receipt/soccerdb-overlap-valid-game-000.json",
    )
    parser.add_argument(
        "--train-manifest", type=Path,
        default=ROOT / "data/private/soccerdb-overlap-derived/train-game-000-v1-manifest.json",
    )
    parser.add_argument(
        "--valid-manifest", type=Path,
        default=ROOT / "data/private/soccerdb-overlap-derived/valid-game-000-v1-manifest.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_binding_report(
        mapping_path=args.mapping,
        train_receipt_path=args.train_receipt,
        valid_receipt_path=args.valid_receipt,
        train_manifest_path=args.train_manifest,
        valid_manifest_path=args.valid_manifest,
    )
    write_report_exclusive(args.output, report)
    print(json.dumps({
        "status": report["status"],
        "mapping_sha256": report["mapping"]["sha256"],
        "bindings": [
            {"split": item["split"], "soccerdb_media_name": item["soccerdb_media_name"]}
            for item in report["bindings"]
        ],
        "artifact_sha256": sha256_file(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
