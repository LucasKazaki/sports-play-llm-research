"""No-model-call SoccerTrack v2 public-media intake and validation adapter.

This adapter is intentionally an *intake boundary*, not an event detector. It
only validates paths, public-source provenance, file hashes, and matching
container-level IDs between SoccerTrack video assets and BAS JSON files.  BAS
action values are never copied to an output artifact, a VLM input manifest, or
a retrieval catalog.  The latter two are label-free and contain no source path
or game identifier.

The adapter has no network access, does not decode pixels, and contains no
model transport.  A future reviewed executor may use the anonymous visual
manifest to sample frames, but it must keep this adapter's post-hoc annotation
records outside every model request and search index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


INTAKE_SCHEMA_VERSION = "soccertrack-v2-public-intake-v1"
PROVENANCE_SCHEMA_VERSION = "soccertrack-v2-source-provenance-v1"
VIDEO_MANIFEST_SCHEMA_VERSION = "soccertrack-v2-video-manifest-v1"
SOURCE_SPLIT_SCHEMA_VERSION = "soccertrack-v2-game-source-split-v1"
VISUAL_MANIFEST_SCHEMA_VERSION = "soccertrack-v2-anonymous-visual-input-v1"
RETRIEVAL_CATALOG_SCHEMA_VERSION = "soccertrack-v2-label-free-retrieval-catalog-v1"
RECEIPT_SCHEMA_VERSION = "soccertrack-v2-intake-validation-receipt-v1"

DATASET_DIRECTORY_NAME = "soccertrack-v2"
EXPECTED_DATASET_ID = "SoccerTrack-v2"
EXPECTED_LICENSE = "CC-BY-4.0"
DEFAULT_DATASET_ROOT = Path("data/open/soccertrack-v2")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/soccertrack-v2-intake")
MEDIA_DIRECTORY = "media"
BAS_DIRECTORY = Path("annotations") / "bas"
PROVENANCE_FILENAME = "source-provenance.json"
MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv"}
HEX64 = set("0123456789abcdef")

# SoccerTrack v2's released game-level split is an external experimental
# contract, not a quantity to rebalance from local availability.  Preserving
# it prevents a later expanded acquisition from silently moving official test
# footage into development.
OFFICIAL_GAME_SPLITS = {
    "train": ("117092", "117093", "118575", "118576", "118577", "128058", "132877"),
    "validation": ("118578",),
    "test": ("128057", "132831"),
}

# These tokens may never occur in a model-input or query-retrieval artifact.
# The source/provenance manifest is deliberately separate and is allowed to
# carry annotation hashes only, never annotation content.
FORBIDDEN_DOWNSTREAM_KEYS = frozenset(
    {
        "action",
        "actions",
        "annotation",
        "annotations",
        "event",
        "event_type",
        "game_time",
        "gametime",
        "label",
        "labels",
        "player",
        "player_id",
        "position",
        "team",
    }
)


class IntakeValidationError(ValueError):
    """Raised when public-media provenance or containment is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in HEX64 for character in value)


def _is_anonymous_frame_id(value: object) -> bool:
    """Accept only an opaque, locally derived frame token.

    Frame IDs cross the intake boundary into the one model-request-shaped
    object.  Treating arbitrary caller text as an ID would allow a media path,
    source-game identifier, or annotation text to enter that object despite
    its label-free contract.  ``frame-<sha256>`` gives downstream code a
    stable, non-semantic handle while keeping source identity out of the
    request payload.
    """

    return isinstance(value, str) and value.startswith("frame-") and _is_hash(value[6:])


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntakeValidationError(f"invalid JSON object: {path}") from error
    if not isinstance(value, dict):
        raise IntakeValidationError(f"expected a JSON object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A per-process temporary name and short retry window make this atomic
    # update reliable on Windows when a filesystem indexer briefly opens the
    # prior artifact. The contents are still fully written before replacement.
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(0.1 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def assert_public_dataset_root(dataset_root: Path) -> Path:
    """Require the dedicated ``data/open/soccertrack-v2`` containment path.

    This check rejects a private SoccerNet location, a symlink escape, or a
    look-alike root.  The adapter never accepts a caller-provided media path.
    """

    root = dataset_root.resolve()
    if root.name != DATASET_DIRECTORY_NAME or root.parent.name != "open" or root.parent.parent.name != "data":
        raise IntakeValidationError("dataset root must be the dedicated data/open/soccertrack-v2 directory")
    lowered_parts = {part.lower() for part in root.parts}
    if "private" in lowered_parts or "soccernet" in lowered_parts:
        raise IntakeValidationError("private or SoccerNet locations are not valid SoccerTrack public roots")
    if not root.is_dir():
        raise IntakeValidationError(f"public SoccerTrack dataset root is missing: {root}")
    return root


def _assert_contained_regular_file(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise IntakeValidationError(f"symlinked source files are not allowed: {path}")
    resolved = path.resolve()
    if not _is_relative_to(resolved, root.resolve()):
        raise IntakeValidationError(f"source file escapes public dataset root: {path}")
    if not resolved.is_file():
        raise IntakeValidationError(f"expected regular source file: {path}")
    return resolved


def _assert_dataset_has_no_symlinks(root: Path) -> None:
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise IntakeValidationError(f"symlinks are not permitted in the public intake tree: {candidate}")


def _required_text(value: Mapping[str, Any], key: str, path: Path) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate.strip():
        raise IntakeValidationError(f"source provenance requires non-empty {key}: {path}")
    return candidate.strip()


def validate_source_provenance(dataset_root: Path) -> dict[str, Any]:
    """Read and minimally validate the separately stored public-source record."""

    root = assert_public_dataset_root(dataset_root)
    path = _assert_contained_regular_file(root, root / PROVENANCE_FILENAME)
    value = _read_json_object(path)
    if value.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        raise IntakeValidationError("unexpected SoccerTrack provenance schema version")
    if value.get("dataset_id") != EXPECTED_DATASET_ID:
        raise IntakeValidationError("provenance dataset_id is not SoccerTrack-v2")
    if value.get("data_license") != EXPECTED_LICENSE:
        raise IntakeValidationError("provenance does not declare the expected CC-BY-4.0 data license")
    source_url = _required_text(value, "source_url", path)
    license_url = _required_text(value, "license_url", path)
    if not source_url.startswith("https://") or not license_url.startswith("https://"):
        raise IntakeValidationError("source and license URLs must use HTTPS")
    if not (isinstance(value.get("source_revision"), str) and value["source_revision"].strip()) and not (
        isinstance(value.get("source_revision_status"), str) and value["source_revision_status"].strip()
    ):
        raise IntakeValidationError("provenance requires source_revision or source_revision_status")
    return {
        "provenance_relative_path": _relative(root, path),
        "provenance_sha256": sha256_file(path),
        "dataset_id": EXPECTED_DATASET_ID,
        "data_license": EXPECTED_LICENSE,
        "source_url": source_url,
        "license_url": license_url,
        "source_revision": value.get("source_revision") if isinstance(value.get("source_revision"), str) else None,
        "source_revision_status": value.get("source_revision_status")
        if isinstance(value.get("source_revision_status"), str)
        else None,
    }


def _source_game_id(value: object, context: Path) -> str:
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not value.strip() or any(character in value for character in ("/", "\\", "\x00")):
        raise IntakeValidationError(f"invalid opaque match_id in {context}")
    return value.strip()


def _discover_media(dataset_root: Path) -> list[dict[str, Any]]:
    media_root = dataset_root / MEDIA_DIRECTORY
    if not media_root.is_dir():
        raise IntakeValidationError(f"missing public media directory: {media_root}")
    files = sorted(path for path in media_root.rglob("*") if path.is_file())
    if not files:
        raise IntakeValidationError("no public SoccerTrack video files found")
    records: list[dict[str, Any]] = []
    for path in files:
        resolved = _assert_contained_regular_file(dataset_root, path)
        if resolved.suffix.lower() not in MEDIA_SUFFIXES:
            raise IntakeValidationError(f"unsupported non-video file under media: {path}")
        relative = resolved.relative_to(media_root.resolve())
        if len(relative.parts) != 2:
            raise IntakeValidationError(f"media must use media/<match_id>/<video-file> layout: {path}")
        game_id = _source_game_id(relative.parts[0], path)
        if not resolved.stem.startswith(game_id + "_"):
            raise IntakeValidationError(f"video name must start with its containing match_id: {path}")
        media_sha256 = sha256_file(resolved)
        records.append(
            {
                "asset_token": sha256_bytes(f"soccertrack-v2-media-token-v1:{media_sha256}".encode("utf-8")),
                "source_game_id": game_id,
                "media_relative_path": _relative(dataset_root, resolved),
                "media_sha256": media_sha256,
                "bytes": resolved.stat().st_size,
            }
        )
    return records


def _discover_bas_annotations(dataset_root: Path, known_game_ids: set[str]) -> list[dict[str, Any]]:
    bas_root = dataset_root / BAS_DIRECTORY
    if not bas_root.is_dir():
        raise IntakeValidationError(f"missing BAS annotation directory: {bas_root}")
    files = sorted(path for path in bas_root.rglob("*.json") if path.is_file())
    if not files:
        raise IntakeValidationError("no BAS annotation JSON files found")
    records: list[dict[str, Any]] = []
    for path in files:
        resolved = _assert_contained_regular_file(dataset_root, path)
        raw = _read_json_object(resolved)
        match_id = _source_game_id(raw.get("match_id"), resolved)
        if match_id not in known_game_ids:
            raise IntakeValidationError(f"BAS match_id has no matching public video directory: {path}")
        fps = raw.get("fps")
        if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
            raise IntakeValidationError(f"BAS annotation fps must be positive: {path}")
        actions = raw.get("actions")
        if not isinstance(actions, list):
            raise IntakeValidationError(f"BAS annotation actions must be a list: {path}")
        if not all(isinstance(item, dict) for item in actions):
            raise IntakeValidationError(f"BAS annotation actions must contain JSON objects: {path}")
        # Deliberately do not read action keys or values.  They are post-hoc
        # labels, never features or candidate events for this adapter.
        records.append(
            {
                "source_game_id": match_id,
                "bas_relative_path": _relative(dataset_root, resolved),
                "bas_sha256": sha256_file(resolved),
                "action_count": len(actions),
                "fps": float(fps),
            }
        )
    return records


def _group_by_game(records: Iterable[Mapping[str, Any]], key: str = "source_game_id") -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        game_id = str(record[key])
        grouped.setdefault(game_id, []).append(dict(record))
    return grouped


def _validate_match_links(media: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    media_by_game = _group_by_game(media)
    annotations_by_game = _group_by_game(annotations)
    media_games = set(media_by_game)
    annotation_games = set(annotations_by_game)
    if media_games != annotation_games:
        missing_annotations = sorted(media_games - annotation_games)
        missing_media = sorted(annotation_games - media_games)
        raise IntakeValidationError(
            "public video/BAS match mismatch: "
            f"missing_annotations={missing_annotations}; missing_media={missing_media}"
        )
    links: list[dict[str, Any]] = []
    for game_id in sorted(media_games):
        links.append(
            {
                "source_game_id": game_id,
                "media_asset_tokens": sorted(item["asset_token"] for item in media_by_game[game_id]),
                "bas_sha256": sorted(item["bas_sha256"] for item in annotations_by_game[game_id]),
            }
        )
    return links


def _ensure_no_annotation_content(value: Any, *, context: str) -> None:
    """Fail closed if a purported downstream artifact contains label fields."""

    if isinstance(value, dict):
        forbidden = sorted(str(key) for key in value if str(key).lower() in FORBIDDEN_DOWNSTREAM_KEYS)
        if forbidden:
            raise IntakeValidationError(f"{context} contains forbidden annotation-derived keys: {forbidden}")
        for child in value.values():
            _ensure_no_annotation_content(child, context=context)
    elif isinstance(value, list):
        for child in value:
            _ensure_no_annotation_content(child, context=context)


def build_video_manifest(dataset_root: Path) -> dict[str, Any]:
    """Build a provenance-only manifest without copying BAS action values."""

    root = assert_public_dataset_root(dataset_root)
    _assert_dataset_has_no_symlinks(root)
    provenance = validate_source_provenance(root)
    media = _discover_media(root)
    annotations = _discover_bas_annotations(root, {item["source_game_id"] for item in media})
    links = _validate_match_links(media, annotations)
    return {
        "schema_version": VIDEO_MANIFEST_SCHEMA_VERSION,
        "created_at": utc_now(),
        "source_scope": "open_licensed_soccertrack_v2_only",
        "dataset_root_relative": "data/open/soccertrack-v2",
        "private_source_paths_allowed": False,
        "provenance": provenance,
        "media": media,
        "bas_containers": annotations,
        "matching_game_links": links,
        "annotation_handling": {
            "raw_actions_copied": False,
            "action_labels_copied": False,
            "allowed_role": "post_hoc_only",
            "forbidden_roles": ["VLM_input", "query_retrieval", "candidate_generation", "deterministic_event_inference"],
        },
        "semantic_boundary": {
            "model_calls_made": 0,
            "pixels_decoded": False,
            "deterministic_event_inference": False,
        },
    }


def official_split_config() -> dict[str, Any]:
    """Return the immutable official SoccerTrack v2 game assignment."""

    return {
        "schema_version": "soccertrack-v2-official-game-split-v1",
        "train": list(OFFICIAL_GAME_SPLITS["train"]),
        "validation": list(OFFICIAL_GAME_SPLITS["validation"]),
        "test": list(OFFICIAL_GAME_SPLITS["test"]),
    }


def build_source_split(video_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Project available data onto SoccerTrack's pinned game-level split.

    The adapter never rebalances available games.  Two official test groups
    plus development data are the minimum for an evidence-gated study.  With
    fewer locally acquired groups, the source split is explicitly blocked.
    """

    if video_manifest.get("schema_version") != VIDEO_MANIFEST_SCHEMA_VERSION:
        raise IntakeValidationError("cannot split an unrecognized video manifest")
    raw_links = video_manifest.get("matching_game_links")
    if not isinstance(raw_links, list) or not raw_links:
        raise IntakeValidationError("video manifest contains no matching game links")
    game_ids = sorted({_source_game_id(item.get("source_game_id"), Path("video-manifest.json")) for item in raw_links})
    split_config = official_split_config()
    config_hash = sha256_bytes(canonical_json(split_config))
    official_partition = {
        game_id: partition for partition, game_ids_for_partition in OFFICIAL_GAME_SPLITS.items() for game_id in game_ids_for_partition
    }
    unknown = sorted(set(game_ids) - set(official_partition))
    if unknown:
        raise IntakeValidationError(f"public SoccerTrack games are absent from the pinned official split: {unknown}")
    split_names = {
        "train": "official_train_development_only",
        "validation": "official_validation_development_only",
        "test": "official_test_heldout",
    }
    games = [
        {
            "source_game_id": game_id,
            "official_partition": official_partition[game_id],
            "split": split_names[official_partition[game_id]],
            "research_partition": "heldout" if official_partition[game_id] == "test" else "development",
        }
        for game_id in game_ids
    ]
    available = {partition: sorted(game_id for game_id in game_ids if official_partition[game_id] == partition) for partition in OFFICIAL_GAME_SPLITS}
    missing_official_test = sorted(set(OFFICIAL_GAME_SPLITS["test"]) - set(available["test"]))
    if missing_official_test:
        status = "blocked_missing_official_test_games"
    elif not (available["train"] or available["validation"]):
        status = "blocked_missing_official_development_games"
    else:
        status = "official_split_ready_for_separate_review"
    plan = {
        "schema_version": SOURCE_SPLIT_SCHEMA_VERSION,
        "source_manifest_sha256": sha256_bytes(canonical_json(video_manifest)),
        "provenance_sha256": video_manifest.get("provenance", {}).get("provenance_sha256"),
        "official_split_config": split_config,
        "official_split_config_sha256": config_hash,
        "provenance_split_binding_sha256": sha256_bytes(
            canonical_json(
                {
                    "provenance_sha256": video_manifest.get("provenance", {}).get("provenance_sha256"),
                    "official_split_config_sha256": config_hash,
                }
            )
        ),
        "unit_of_assignment": "source_game_id",
        "assignment_rule": "pinned official SoccerTrack-v2 game split; labels never read",
        "minimum_groups": {"development": 1, "heldout": 2},
        "status": status,
        "games": games,
        "available_official_groups": available,
        "missing_official_test_groups": missing_official_test,
        "leakage_controls": {
            "group_level_only": True,
            "event_or_annotation_values_used": False,
            "same_source_game_cannot_cross_splits": True,
            "official_test_games_never_reassigned": True,
            "requires_separate_history_overlap_check_before_vlm_use": True,
        },
    }
    return plan


def build_anonymous_visual_manifest(video_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Strip public provenance to the narrow metadata allowed before frame work."""

    if video_manifest.get("schema_version") != VIDEO_MANIFEST_SCHEMA_VERSION:
        raise IntakeValidationError("cannot build visual manifest from an unrecognized video manifest")
    media = video_manifest.get("media")
    if not isinstance(media, list) or not media:
        raise IntakeValidationError("video manifest contains no media records")
    assets: list[dict[str, str]] = []
    for item in media:
        if not isinstance(item, dict) or not _is_hash(item.get("asset_token")):
            raise IntakeValidationError("video manifest media asset token is invalid")
        assets.append({"asset_token": item["asset_token"]})
    output = {
        "schema_version": VISUAL_MANIFEST_SCHEMA_VERSION,
        "source_manifest_sha256": sha256_bytes(canonical_json(video_manifest)),
        "assets": sorted(assets, key=lambda item: item["asset_token"]),
        "model_input_contract": {
            "allowed_fields_in_a_future_visual_request": ["frame_id", "relative_seconds", "image_bytes"],
            "annotations_or_labels_used": False,
            "source_paths_used": False,
            "source_game_identity_used": False,
            "audio_or_commentary_used": False,
            "model_calls_made": 0,
        },
    }
    _ensure_no_annotation_content(output, context="anonymous visual manifest")
    return output


def build_label_free_retrieval_catalog(video_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Write an intentionally non-semantic catalog for a later sealed VLM index.

    It cannot answer queries itself.  The only allowed future semantic entries
    are sealed, VLM-authored reports from a separately approved executor;
    BAS labels and deterministic detections are categorically excluded.
    """

    visual = build_anonymous_visual_manifest(video_manifest)
    output = {
        "schema_version": RETRIEVAL_CATALOG_SCHEMA_VERSION,
        "source_manifest_sha256": visual["source_manifest_sha256"],
        "assets": visual["assets"],
        "retrieval_status": "disabled_pending_sealed_vlm_authored_reports",
        "query_contract": {
            "semantic_entries_present": False,
            "permitted_future_semantic_source": "sealed_vlm_authored_report_only",
            "annotation_or_label_entries_allowed": False,
            "deterministic_event_entries_allowed": False,
            "source_paths_or_game_identity_allowed": False,
            "model_calls_made": 0,
        },
    }
    _ensure_no_annotation_content(output, context="label-free retrieval catalog")
    return output


def build_anonymous_visual_request(frames: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Create the only model-request-shaped object exposed by this package.

    Callers can supply anonymous frame IDs and relative times only.  Image
    bytes are intentionally out-of-band; there is no transport implementation.
    """

    if not isinstance(frames, Sequence) or isinstance(frames, (str, bytes)) or not frames:
        raise IntakeValidationError("anonymous visual request requires a non-empty frame sequence")
    allowed = {"frame_id", "relative_seconds"}
    ordered: list[dict[str, Any]] = []
    previous_time: float | None = None
    identifiers: set[str] = set()
    for item in frames:
        if not isinstance(item, Mapping) or set(item) != allowed:
            raise IntakeValidationError("visual request frames may contain only frame_id and relative_seconds")
        frame_id = item.get("frame_id")
        relative_seconds = item.get("relative_seconds")
        if not _is_anonymous_frame_id(frame_id) or frame_id in identifiers:
            raise IntakeValidationError("visual request frame IDs must be unique opaque frame-<sha256> tokens")
        if not isinstance(relative_seconds, (int, float)) or isinstance(relative_seconds, bool):
            raise IntakeValidationError("visual request relative_seconds must be numeric")
        relative = float(relative_seconds)
        if previous_time is not None and relative <= previous_time:
            raise IntakeValidationError("visual request frames must be strictly ordered by relative_seconds")
        identifiers.add(frame_id)
        previous_time = relative
        ordered.append({"frame_id": frame_id, "relative_seconds": relative})
    output = {
        "schema_version": "soccertrack-v2-anonymous-visual-request-v1",
        "ordered_frames": ordered,
        "input_contract": {
            "labels_used": False,
            "annotations_used": False,
            "source_identity_used": False,
            "source_paths_used": False,
            "transport_implemented": False,
            "model_calls_made": 0,
        },
    }
    _ensure_no_annotation_content(output, context="anonymous visual request")
    return output


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntakeValidationError(f"expected JSON object for {name}")
    return value


def _require_file_hash(record: Mapping[str, Any], key: str, root: Path, path_key: str) -> None:
    relative = record.get(path_key)
    expected = record.get(key)
    if not isinstance(relative, str) or not _is_hash(expected):
        raise IntakeValidationError(f"manifest record lacks {path_key} or valid {key}")
    path = _assert_contained_regular_file(root, root / relative)
    actual = sha256_file(path)
    if actual != expected:
        raise IntakeValidationError(f"hash mismatch for {relative}")


def verify_intake(dataset_root: Path, artifact_root: Path) -> dict[str, Any]:
    """Recompute every source/artifact hash and re-enforce downstream secrecy."""

    root = assert_public_dataset_root(dataset_root)
    output_root = artifact_root.resolve()
    files = {
        "video_manifest": output_root / "video-manifest.json",
        "source_split": output_root / "source-split.json",
        "anonymous_visual_manifest": output_root / "anonymous-visual-manifest.json",
        "label_free_retrieval_catalog": output_root / "label-free-retrieval-catalog.json",
    }
    loaded = {name: _require_mapping(_read_json_object(path), name) for name, path in files.items()}
    video_manifest = loaded["video_manifest"]
    if video_manifest.get("schema_version") != VIDEO_MANIFEST_SCHEMA_VERSION:
        raise IntakeValidationError("unexpected video manifest schema")
    if video_manifest.get("source_scope") != "open_licensed_soccertrack_v2_only":
        raise IntakeValidationError("video manifest source scope is not public SoccerTrack only")
    if video_manifest.get("private_source_paths_allowed") is not False:
        raise IntakeValidationError("video manifest must forbid private source paths")
    provenance = _require_mapping(video_manifest.get("provenance"), "provenance")
    provenance_path = _assert_contained_regular_file(root, root / str(provenance.get("provenance_relative_path", "")))
    if sha256_file(provenance_path) != provenance.get("provenance_sha256"):
        raise IntakeValidationError("source provenance hash mismatch")
    for record in video_manifest.get("media", []):
        _require_file_hash(_require_mapping(record, "media record"), "media_sha256", root, "media_relative_path")
    for record in video_manifest.get("bas_containers", []):
        _require_file_hash(_require_mapping(record, "BAS record"), "bas_sha256", root, "bas_relative_path")
    # Recreate the structural discovery record and compare its canonical form.
    # This catches added/missing matches and any changed BAS container layout
    # without ever copying action values into downstream artifacts.
    recreated = build_video_manifest(root)
    if canonical_json(recreated | {"created_at": video_manifest.get("created_at")}) != canonical_json(video_manifest):
        raise IntakeValidationError("video manifest no longer matches the public dataset structure")
    manifest_hash = sha256_bytes(canonical_json(video_manifest))
    split = loaded["source_split"]
    if split.get("schema_version") != SOURCE_SPLIT_SCHEMA_VERSION or split.get("source_manifest_sha256") != manifest_hash:
        raise IntakeValidationError("source split is not bound to the video manifest")
    if canonical_json(build_source_split(video_manifest)) != canonical_json(split):
        raise IntakeValidationError("source split does not match deterministic game-level assignment")
    visual = loaded["anonymous_visual_manifest"]
    if visual.get("schema_version") != VISUAL_MANIFEST_SCHEMA_VERSION or visual.get("source_manifest_sha256") != manifest_hash:
        raise IntakeValidationError("anonymous visual manifest is not bound to the video manifest")
    _ensure_no_annotation_content(visual, context="anonymous visual manifest")
    if canonical_json(build_anonymous_visual_manifest(video_manifest)) != canonical_json(visual):
        raise IntakeValidationError("anonymous visual manifest is not the deterministic label-free projection")
    retrieval = loaded["label_free_retrieval_catalog"]
    if retrieval.get("schema_version") != RETRIEVAL_CATALOG_SCHEMA_VERSION or retrieval.get("source_manifest_sha256") != manifest_hash:
        raise IntakeValidationError("retrieval catalog is not bound to the video manifest")
    _ensure_no_annotation_content(retrieval, context="label-free retrieval catalog")
    if canonical_json(build_label_free_retrieval_catalog(video_manifest)) != canonical_json(retrieval):
        raise IntakeValidationError("retrieval catalog is not the deterministic label-free projection")
    split_games = split.get("games")
    heldout_count = sum(
        isinstance(item, dict) and item.get("research_partition") == "heldout" for item in split_games if isinstance(split_games, list)
    )
    development_count = sum(
        isinstance(item, dict) and item.get("research_partition") == "development" for item in split_games if isinstance(split_games, list)
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "pass",
        "dataset_scope": "open_licensed_soccertrack_v2_only",
        "source_manifest_sha256": manifest_hash,
        "artifact_sha256": {name: sha256_file(path) for name, path in files.items()},
        "media_hashes_verified": len(video_manifest.get("media", [])),
        "bas_hashes_verified": len(video_manifest.get("bas_containers", [])),
        "game_level_split": {"development": development_count, "heldout": heldout_count, "status": split.get("status")},
        "evidence_gated_eligible": (
            split.get("status") == "official_split_ready_for_separate_review" and development_count >= 1 and heldout_count >= 2
        ),
        "annotations_or_labels_in_visual_input": False,
        "annotations_or_labels_in_query_retrieval": False,
        "model_calls_made": 0,
        "pixel_or_event_inference_performed": False,
        "claim_boundary": "This verifies public-source integrity and data separation only; it is not a VLM result, event-detection result, or coach-utility result.",
    }
    return receipt


def build_intake(dataset_root: Path, artifact_root: Path) -> dict[str, Any]:
    """Write a fresh, deterministic public intake bundle and verify it."""

    root = assert_public_dataset_root(dataset_root)
    output_root = artifact_root.resolve()
    if _is_relative_to(output_root, root):
        raise IntakeValidationError("intake artifacts must be outside the public media tree")
    video_manifest = build_video_manifest(root)
    split = build_source_split(video_manifest)
    visual = build_anonymous_visual_manifest(video_manifest)
    retrieval = build_label_free_retrieval_catalog(video_manifest)
    _write_json(output_root / "video-manifest.json", video_manifest)
    _write_json(output_root / "source-split.json", split)
    _write_json(output_root / "anonymous-visual-manifest.json", visual)
    _write_json(output_root / "label-free-retrieval-catalog.json", retrieval)
    receipt = verify_intake(root, output_root)
    _write_json(output_root / "validation-receipt.json", receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    value.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    subparsers = value.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="build and verify public, label-free intake artifacts")
    subparsers.add_parser("verify", help="verify a previously built intake artifact set")
    return value


def _resolve(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    dataset_root = _resolve(project_root, args.dataset_root)
    artifact_root = _resolve(project_root, args.artifact_root)
    if args.command == "build":
        result = build_intake(dataset_root, artifact_root)
    elif args.command == "verify":
        result = verify_intake(dataset_root, artifact_root)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
