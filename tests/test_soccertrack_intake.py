import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import soccertrack_intake.adapter as module


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _dataset_root(tmp_path: Path) -> Path:
    return tmp_path / "data" / "open" / "soccertrack-v2"


def _add_game(root: Path, game_id: str, *, annotation_match_id: str | None = None) -> None:
    media = root / "media" / game_id / f"{game_id}_panorama_1st_half.mp4"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(("public-soccertrack-video-" + game_id).encode("utf-8"))
    annotation = root / "annotations" / "bas" / f"{game_id}_12_class_events.json"
    _write_json(
        annotation,
        {
            "match_id": annotation_match_id or game_id,
            "fps": 25,
            "actions": [
                {
                    "gameTime": "1 - 0:01",
                    "label": "INTENTIONALLY_NOT_EXPORTED",
                    "position": "1000",
                    "team": "left",
                    "player_id": "42",
                }
            ],
        },
    )


def _make_dataset(tmp_path: Path, game_ids: tuple[str, ...] = ("117092",)) -> Path:
    root = _dataset_root(tmp_path)
    _write_json(
        root / "source-provenance.json",
        {
            "schema_version": module.PROVENANCE_SCHEMA_VERSION,
            "dataset_id": module.EXPECTED_DATASET_ID,
            "data_license": module.EXPECTED_LICENSE,
            "source_url": "https://github.com/AtomScott/SoccerTrack-v2",
            "license_url": "https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA",
            "source_revision": "fixture-revision",
        },
    )
    for game_id in game_ids:
        _add_game(root, game_id)
    return root


def test_build_and_verify_public_intake_keeps_labels_out_of_downstream_artifacts(tmp_path: Path) -> None:
    dataset_root = _make_dataset(tmp_path)
    artifacts = tmp_path / "artifacts" / "soccertrack-v2-intake"
    receipt = module.build_intake(dataset_root, artifacts)
    assert receipt["status"] == "pass"
    assert receipt["media_hashes_verified"] == 1
    assert receipt["bas_hashes_verified"] == 1
    assert receipt["evidence_gated_eligible"] is False
    split = json.loads((artifacts / "source-split.json").read_text(encoding="utf-8"))
    assert split["status"] == "blocked_missing_official_test_games"
    assert split["games"] == [
        {
            "official_partition": "train",
            "research_partition": "development",
            "source_game_id": "117092",
            "split": "official_train_development_only",
        }
    ]
    assert split["official_split_config_sha256"] == module.sha256_bytes(module.canonical_json(module.official_split_config()))
    assert split["provenance_split_binding_sha256"]
    assert receipt["annotations_or_labels_in_visual_input"] is False
    assert receipt["annotations_or_labels_in_query_retrieval"] is False
    assert receipt["model_calls_made"] == 0
    for name in ("anonymous-visual-manifest.json", "label-free-retrieval-catalog.json"):
        encoded = (artifacts / name).read_text(encoding="utf-8")
        assert "INTENTIONALLY_NOT_EXPORTED" not in encoded
        assert "player_id" not in encoded
        assert "gameTime" not in encoded
        assert "media_relative_path" not in encoded
    visual = json.loads((artifacts / "anonymous-visual-manifest.json").read_text(encoding="utf-8"))
    retrieval = json.loads((artifacts / "label-free-retrieval-catalog.json").read_text(encoding="utf-8"))
    assert visual["model_input_contract"]["annotations_or_labels_used"] is False
    assert retrieval["query_contract"]["semantic_entries_present"] is False
    assert retrieval["retrieval_status"] == "disabled_pending_sealed_vlm_authored_reports"
    assert module.verify_intake(dataset_root, artifacts)["status"] == "pass"


def test_match_id_must_link_both_bas_container_and_video_directory(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path)
    _add_game(root, "117093", annotation_match_id="missing-game")
    with pytest.raises(module.IntakeValidationError, match="matching public video directory"):
        module.build_intake(root, tmp_path / "artifacts")


def test_private_or_lookalike_roots_are_rejected(tmp_path: Path) -> None:
    private_root = tmp_path / "data" / "private" / "soccertrack-v2"
    private_root.mkdir(parents=True)
    with pytest.raises(module.IntakeValidationError, match="data/open/soccertrack-v2"):
        module.assert_public_dataset_root(private_root)


def test_symlinked_media_is_rejected_before_intake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_dataset(tmp_path)
    media = root / "media" / "117092" / "117092_panorama_1st_half.mp4"
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"must-not-be-admitted-through-a-symlink")
    media.unlink()
    try:
        media.symlink_to(outside)
    except OSError:  # Windows can deny symlink creation even for ordinary test paths.
        # Preserve branch coverage of the adapter's fail-closed symlink check
        # when the host filesystem itself cannot create a symlink.
        media.write_bytes(b"synthetic-media-for-symlink-branch-test")
        original_is_symlink = Path.is_symlink

        def simulated_is_symlink(candidate: Path) -> bool:
            return candidate == media or original_is_symlink(candidate)

        monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)
    with pytest.raises(module.IntakeValidationError, match="symlinks are not permitted"):
        module.build_intake(root, tmp_path / "artifacts")


def test_split_preserves_official_game_assignments_and_requires_both_official_test_groups(tmp_path: Path) -> None:
    assert module.official_split_config() == {
        "schema_version": "soccertrack-v2-official-game-split-v1",
        "train": ["117092", "117093", "118575", "118576", "118577", "128058", "132877"],
        "validation": ["118578"],
        "test": ["128057", "132831"],
    }
    root = _make_dataset(tmp_path, ("117092", "128057", "132831"))
    artifacts = tmp_path / "artifacts"
    receipt = module.build_intake(root, artifacts)
    split = json.loads((artifacts / "source-split.json").read_text(encoding="utf-8"))
    roles = {item["source_game_id"]: item["split"] for item in split["games"]}
    assert split["status"] == "official_split_ready_for_separate_review"
    assert roles == {
        "117092": "official_train_development_only",
        "128057": "official_test_heldout",
        "132831": "official_test_heldout",
    }
    assert receipt["evidence_gated_eligible"] is True
    assert split["leakage_controls"]["event_or_annotation_values_used"] is False
    assert split["leakage_controls"]["official_test_games_never_reassigned"] is True
    assert module.build_source_split(json.loads((artifacts / "video-manifest.json").read_text(encoding="utf-8"))) == split


def test_unpinned_soccertrack_game_is_rejected_instead_of_reassigned(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path, ("117092", "999999"))
    with pytest.raises(module.IntakeValidationError, match="pinned official split"):
        module.build_intake(root, tmp_path / "artifacts")


def test_anonymous_request_rejects_annotation_injection_and_paths() -> None:
    first_frame = "frame-" + ("a" * 64)
    second_frame = "frame-" + ("b" * 64)
    allowed = module.build_anonymous_visual_request(
        [{"frame_id": first_frame, "relative_seconds": -1.0}, {"frame_id": second_frame, "relative_seconds": 1.0}]
    )
    assert allowed["input_contract"]["labels_used"] is False
    assert allowed["ordered_frames"] == [
        {"frame_id": first_frame, "relative_seconds": -1.0},
        {"frame_id": second_frame, "relative_seconds": 1.0},
    ]
    with pytest.raises(module.IntakeValidationError, match="only frame_id and relative_seconds"):
        module.build_anonymous_visual_request(
            [{"frame_id": first_frame, "relative_seconds": 0, "label": "must-never-enter-a-request"}]
        )
    with pytest.raises(module.IntakeValidationError, match="only frame_id and relative_seconds"):
        module.build_anonymous_visual_request(
            [{"frame_id": first_frame, "relative_seconds": 0, "media_path": "data/private/forbidden.mp4"}]
        )
    with pytest.raises(module.IntakeValidationError, match="opaque frame-<sha256>"):
        module.build_anonymous_visual_request(
            [{"frame_id": "data/open/soccertrack-v2/media/117092/goal_label_frame", "relative_seconds": 0}]
        )


def test_verify_detects_media_tampering_after_hash_seal(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path)
    artifacts = tmp_path / "artifacts"
    module.build_intake(root, artifacts)
    media = root / "media" / "117092" / "117092_panorama_1st_half.mp4"
    media.write_bytes(b"tampered-public-video")
    with pytest.raises(module.IntakeValidationError, match="hash mismatch"):
        module.verify_intake(root, artifacts)


def test_verify_detects_provenance_tampering_after_split_binding(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path)
    artifacts = tmp_path / "artifacts"
    module.build_intake(root, artifacts)
    provenance = root / "source-provenance.json"
    value = json.loads(provenance.read_text(encoding="utf-8"))
    value["source_revision"] = "tampered-revision"
    _write_json(provenance, value)
    with pytest.raises(module.IntakeValidationError, match="source provenance hash mismatch"):
        module.verify_intake(root, artifacts)


def test_verify_rejects_annotation_label_tampering_in_visual_artifact(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path)
    artifacts = tmp_path / "artifacts"
    module.build_intake(root, artifacts)
    visual_path = artifacts / "anonymous-visual-manifest.json"
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    visual["label"] = "tampered-label-must-not-enter-vlm-input"
    _write_json(visual_path, visual)
    with pytest.raises(module.IntakeValidationError, match="forbidden annotation-derived keys"):
        module.verify_intake(root, artifacts)


def test_adapter_has_no_model_transport_or_pixel_event_inference_dependency() -> None:
    source = (ROOT / "prototype" / "soccertrack_intake" / "adapter.py").read_text(encoding="utf-8")
    forbidden = ("urllib", "requests", "openai", "cv2", "onnxruntime", "torch", "VideoCapture", "_post_json")
    assert not [term for term in forbidden if term in source]


def test_artifact_write_retries_a_transient_windows_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "artifact.json"
    original_replace = module.os.replace
    attempts = 0

    def flaky_replace(source: Path | str, destination: Path | str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("simulated transient artifact-reader lock")
        original_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", flaky_replace)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    module._write_json(target, {"status": "sealed"})
    assert attempts == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "sealed"}
