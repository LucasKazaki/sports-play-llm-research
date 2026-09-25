from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from footballmaster.dvids_external import (
    ANCHOR_FRACTIONS,
    EXTERNAL_SPLIT,
    EXTERNAL_UNIT_ID,
    EXPECTED_ENDPOINT,
    EXPECTED_MAX_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_ID,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_REQUEST_POLICY_ID,
    FRAMES_PER_WINDOW,
    PLANNED_WINDOW_DENOMINATOR,
    WINDOW_SECONDS,
    ExternalWindow,
    bind_prompt,
    build_results,
    build_external_windows,
    build_sentinel_packet,
    prepare,
    query_packet,
    run_all,
    run_external_one,
    seal_predictions,
    sha256_bytes,
    sha256_file,
    unique_sampled_seconds,
    validate_clearance,
    validate_frozen_preflight,
    validate_frozen_protocol_bindings,
    validate_terminal_artifacts,
    validate_window_design,
    verify_protocol,
    verify_prediction_seal,
)
from footballmaster.longform import _failure_report, build_request, canonical_json, scan_package_isolation


def _source_receipts(tmp_path: Path) -> tuple[Path, Path, dict, dict]:
    project_root = tmp_path
    dataset = project_root / "data" / "external"
    items = []
    observed = []
    for part in range(1, 20):
        name = f"part_{part:02d}.mp4"
        digest = f"{part:064x}"
        items.append(
            {
                "part_number": part,
                "video_id": 10000 + part,
                "local_media": {
                    "local_path": f"media/{name}",
                    "bytes": part * 100,
                    "sha256": digest,
                },
            }
        )
        observed.append(
            {
                "part_number": part,
                "duration_seconds": 600.0 + part,
                "bytes": part * 100,
                "sha256": digest,
                "full_decode": {"status": "passed"},
            }
        )
    return project_root, dataset, {"items": items}, {"media": {"items": observed}}


def test_external_windows_are_one_unit_and_exactly_three_per_part(tmp_path: Path) -> None:
    project_root, dataset, manifest, offline = _source_receipts(tmp_path)
    windows = build_external_windows(project_root, dataset, manifest, offline)
    assert len(windows) == PLANNED_WINDOW_DENOMINATOR == 57
    assert {window.external_unit_id for window in windows} == {EXTERNAL_UNIT_ID}
    assert {window.split for window in windows} == {EXTERNAL_SPLIT}
    assert {window.duration_seconds for window in windows} == {WINDOW_SECONDS}
    assert {window.frames_per_window for window in windows} == {FRAMES_PER_WINDOW}
    assert all(sum(window.part_number == part for window in windows) == 3 for part in range(1, 20))
    assert [window.anchor_fraction for window in windows[:3]] == list(ANCHOR_FRACTIONS)


def test_part_level_subdivision_is_rejected(tmp_path: Path) -> None:
    project_root, dataset, manifest, offline = _source_receipts(tmp_path)
    windows = build_external_windows(project_root, dataset, manifest, offline)
    windows[0] = replace(windows[0], split="train")
    with pytest.raises(ValueError, match="train/test"):
        validate_window_design(windows)


def test_nine_non_play_sentinels_are_private_and_not_accuracy_gold(tmp_path: Path) -> None:
    project_root, dataset, manifest, offline = _source_receipts(tmp_path)
    windows = build_external_windows(project_root, dataset, manifest, offline)
    packet = build_sentinel_packet(windows, "a" * 64)
    assert packet["case_count"] == 9
    assert packet["model_input"] is False
    assert packet["dense_event_ground_truth"] is False
    assert packet["accuracy_metric_allowed"] is False
    assert {case["part_number_private_analysis"] for case in packet["cases"]} == {1, 10, 19}


def test_external_request_has_eight_frames_and_no_private_identifiers() -> None:
    window = ExternalWindow(
        window_id="fmdv-test",
        external_unit_id="private-unit",
        split=EXTERNAL_SPLIT,
        part_number=7,
        source_video_id_private_receipt=12345,
        media_path_private_receipt="private/path/part_07.mp4",
        media_sha256="a" * 64,
        start_seconds=100.0,
        duration_seconds=60,
        anchor_index=1,
        anchor_fraction=0.5,
    )
    frames = [
        {
            "frame_id": f"F{index:02d}",
            "relative_seconds": (index + 0.5) * 60 / 8,
            "sha256": f"{index:064x}",
            "bytes": 3,
            "data": b"abc",
        }
        for index in range(8)
    ]
    payload, receipt = build_request(
        "model", "Analyze only the ordered football frames.", window.as_core_window(), frames
    )
    encoded = json.dumps(payload).lower()
    for private in ("private-unit", "private/path/part_07.mp4", "dvids-part-07", "12345"):
        assert private not in encoded
    assert len(receipt["frames"]) == 8
    assert receipt["audio_used"] is False
    assert receipt["metadata_fields_used"] == []
    assert receipt["input_modalities"] == ["text_protocol", "silent_jpeg_frames"]


def test_clearance_gate_blocks_calls_when_receipt_is_absent(tmp_path: Path) -> None:
    binding = {"model": "model"}
    (tmp_path / "frozen-prompt-binding.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="no model calls"):
        validate_clearance(tmp_path, binding)


def test_queries_are_frozen_behavior_probes_and_package_is_isolated() -> None:
    packet = query_packet()
    assert packet["frozen_before_calls"] is True
    assert packet["query_count"] == 30
    assert "no_relevance_ground_truth" in packet["evaluation_role"]
    assert EXPECTED_PROMPT_ID == "candidate_a_direct"
    assert EXPECTED_PROMPT_SHA256 == "daaf5ad849c3d4201267dd4bfa5227e0cfc5fae93d6a348cf98789705d63604d"
    project_root = Path(__file__).resolve().parents[1]
    assert scan_package_isolation(project_root) == []


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


PROMPT_TEXT = (
    "Analyze only the ordered American-football broadcast frames supplied below. "
    "Describe every distinct visible play or broadcast state. Never use commentary, "
    "filenames, team metadata, rosters, or outside knowledge. Return the required JSON."
)


def _binding_stub() -> dict:
    return {
        "schema_version": "footballmaster-dvids-frozen-prompt-binding-v1",
        "selected_prompt_text": PROMPT_TEXT,
        "selected_prompt_sha256": EXPECTED_PROMPT_SHA256,
        "selected_prompt_id": EXPECTED_PROMPT_ID,
        "selected_max_tokens": EXPECTED_MAX_TOKENS,
        "selected_request_policy_id": EXPECTED_REQUEST_POLICY_ID,
        "model": EXPECTED_MODEL,
        "endpoint": EXPECTED_ENDPOINT,
        "core_prediction_seal_sha256": "1" * 64,
        "core_prediction_seal_root_hash": "2" * 64,
        "core_verification_receipt_sha256": "3" * 64,
        "core_prompt_selection_sha256": "4" * 64,
        "core_prompt_candidates_sha256": "5" * 64,
        "core_frozen_test_config_sha256": "6" * 64,
        "prompt_modified_for_external_run": False,
        "parameter_fine_tuning": False,
        "external_data_used_for_selection": False,
    }


def _write_source_package(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path
    dataset = project_root / "data" / "external"
    items = []
    observed = []
    total_bytes = 0
    total_duration = 0.0
    for part in range(1, 20):
        media = dataset / "media" / f"part_{part:02d}.mp4"
        media.parent.mkdir(parents=True, exist_ok=True)
        data = (f"fixture-part-{part:02d}-" * 4).encode("utf-8")
        media.write_bytes(data)
        digest = sha256_bytes(data)
        duration = 600.0 + part
        total_bytes += len(data)
        total_duration += duration
        items.append(
            {
                "part_number": part,
                "video_id": 10000 + part,
                "local_media": {
                    "local_path": f"media/part_{part:02d}.mp4",
                    "bytes": len(data),
                    "sha256": digest,
                },
            }
        )
        observed.append(
            {
                "part_number": part,
                "duration_seconds": duration,
                "bytes": len(data),
                "sha256": digest,
                "full_decode": {"status": "passed"},
            }
        )
    _write_json(
        dataset / "manifest.json",
        {
            "package_id": "fixture-dvids-v1",
            "claim_boundary": (
                "complete source-numbered 19-part series; not proven uncut, every-play, or "
                "broadcast-complete"
            ),
            "game_id": EXTERNAL_UNIT_ID,
            "split_unit_id": EXTERNAL_UNIT_ID,
            "split_policy": "atomic_single_game_no_part_cross_split",
            "items": items,
        },
    )
    _write_json(
        dataset / "verification" / "offline_verification.json",
        {
            "overall_status": "passed_pending_distinct_agent_and_visual_review",
            "source_snapshots": {"file_count": 58},
            "media": {
                "count": 19,
                "all_full_decodes_passed": True,
                "total_duration_seconds": total_duration,
                "total_duration_hours": total_duration / 3600.0,
                "total_bytes": total_bytes,
                "items": observed,
            },
        },
    )
    _write_json(
        dataset / "verification" / "verification-contract.json",
        {"verdict": "GO", "approval": True, "verifier_agent_id": "/root/scale_verifier"},
    )
    _write_json(dataset / "inspection" / "visual_review.json", {"status": "fixture-only"})
    return project_root, dataset


def _write_core_fixture(project_root: Path) -> Path:
    core = project_root / "core"
    candidates = {"candidates": {EXPECTED_PROMPT_ID: PROMPT_TEXT}}
    _write_json(core / "prompt-candidates.json", candidates)
    selection = {
        "selected_prompt_id": EXPECTED_PROMPT_ID,
        "selected_prompt_sha256": EXPECTED_PROMPT_SHA256,
        "correctness_or_event_accuracy_used": False,
    }
    _write_json(core / "prompt-selection.json", selection)
    freeze = {
        "prompt_selection_sha256": sha256_file(core / "prompt-selection.json"),
        "selected_prompt_id": EXPECTED_PROMPT_ID,
        "selected_prompt_sha256": EXPECTED_PROMPT_SHA256,
        "selected_max_tokens": EXPECTED_MAX_TOKENS,
        "selected_request_policy_id": EXPECTED_REQUEST_POLICY_ID,
        "model": EXPECTED_MODEL,
        "endpoint": EXPECTED_ENDPOINT,
    }
    _write_json(core / "frozen-test-config.json", freeze)
    _write_json(core / "verification-receipt.json", {"status": "pass"})
    files = {
        name: sha256_file(core / name)
        for name in (
            "prompt-selection.json",
            "prompt-candidates.json",
            "frozen-test-config.json",
        )
    }
    _write_json(
        core / "prediction-seal.json",
        {"files": files, "root_hash": sha256_bytes(canonical_json(files))},
    )
    return core


def _prepared_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, list[ExternalWindow], dict]:
    project_root, dataset = _write_source_package(tmp_path)
    output = project_root / "output"
    core = _write_core_fixture(project_root)
    prepare(project_root, dataset, output)
    binding = bind_prompt(core, output)
    verify_protocol(project_root, dataset, output, require_results=False)
    windows = [
        ExternalWindow(**json.loads(line))
        for line in (output / "window-manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return project_root, dataset, core, output, windows, binding


def _authorize(output: Path, binding: dict) -> dict:
    frozen = validate_frozen_protocol_bindings(output, binding)
    clearance = {
        "schema_version": "footballmaster-dvids-gpu-clearance-v2",
        "authorized": True,
        "authorized_by": "/root",
        "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
        "model": binding["model"],
        "endpoint": binding["endpoint"],
        **frozen,
    }
    _write_json(output / "gpu-clearance.json", clearance)
    return clearance


def _write_terminal_fixture(output: Path, window: ExternalWindow, binding: dict) -> dict:
    base = output / "runs" / window.window_id
    frames = []
    frame_receipts = []
    for index in range(FRAMES_PER_WINDOW):
        frame_id = f"F{index:02d}"
        relative = round((index + 0.5) * window.duration_seconds / FRAMES_PER_WINDOW, 3)
        absolute = round(window.start_seconds + relative, 3)
        data = f"{window.window_id}|{frame_id}|silent-fixture".encode("utf-8")
        frame_path = base / "frames" / f"{frame_id}.jpg"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        frame_path.write_bytes(data)
        frame = {
            "frame_id": frame_id,
            "relative_seconds": relative,
            "absolute_seconds_private_receipt": absolute,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
            "path": str(frame_path),
            "data": data,
        }
        frames.append(frame)
        frame_receipts.append(
            {
                key: frame[key]
                for key in (
                    "frame_id",
                    "relative_seconds",
                    "absolute_seconds_private_receipt",
                    "sha256",
                    "bytes",
                )
            }
        )
    payload, request = build_request(
        binding["model"],
        binding["selected_prompt_text"],
        window.as_core_window(),
        frames,
        use_response_format=True,
        max_tokens=binding["selected_max_tokens"],
        compact_fallback=False,
    )
    request.update(
        {
            "strategy_id": "structured_eight_frames",
            "external_request_policy_id": "dvids-eight-frame-structured-then-plain-v1",
            "core_selected_request_policy_id": binding["selected_request_policy_id"],
            "request_payload_sha256": sha256_bytes(canonical_json(payload)),
        }
    )
    request["request_receipt_sha256"] = sha256_bytes(canonical_json(request))
    request_path = base / "attempt-1-request-receipt.json"
    _write_json(request_path, request)
    attempt = {
        "attempt_number": 1,
        "strategy_id": "structured_eight_frames",
        "started_at_utc": "2026-01-01T00:00:00Z",
        "request_receipt_sha256": sha256_file(request_path),
        "request_payload_sha256": request["request_payload_sha256"],
        "frame_count": FRAMES_PER_WINDOW,
        "status": "error",
        "elapsed_seconds": 0.125,
        "error_type": "FixtureError",
        "error": "fixture terminal failure",
        "error_fingerprint": "7" * 64,
    }
    _write_json(base / "attempt-1.json", {"attempt": attempt})
    report = _failure_report("Fixture produced no usable model output.")
    raw_path = base / "raw-response.json"
    _write_json(raw_path, {"error": "no valid raw response", "attempt_count": 1})
    normalized = {
        "schema_version": "footballmaster-dvids-normalized-window-v1",
        "window_private_receipt": window.as_dict(),
        "prompt_id": binding["selected_prompt_id"],
        "prompt_sha256": binding["selected_prompt_sha256"],
        "model": binding["model"],
        "report": report,
        "valid": False,
        "validation_errors": ["model_output_unusable"],
        "event_accuracy_measured": False,
    }
    normalized_path = base / "normalized-report.json"
    _write_json(normalized_path, normalized)
    receipt = {
        "schema_version": "footballmaster-dvids-vlm-call-receipt-v1",
        "terminal": True,
        "status": "abstained",
        "completed_at_utc": "2026-01-01T00:00:01Z",
        "window_id": window.window_id,
        "external_unit_id": window.external_unit_id,
        "split": window.split,
        "part_number_private_receipt": window.part_number,
        "media_path_private_receipt": window.media_path_private_receipt,
        "media_sha256": window.media_sha256,
        "prompt_id": binding["selected_prompt_id"],
        "prompt_sha256": binding["selected_prompt_sha256"],
        "prompt_binding_sha256": sha256_file(output / "frozen-prompt-binding.json"),
        "model": binding["model"],
        "endpoint_origin": binding["endpoint"],
        "input_contract": {
            "audio_used": False,
            "commentary_used": False,
            "source_metadata_in_prompt": False,
            "filenames_in_prompt": False,
            "labels_in_prompt": False,
            "team_names_in_prompt": False,
            "ordered_frames": frame_receipts,
        },
        "attempt_count": 1,
        "attempts": [attempt],
        "selected_strategy": "none",
        "raw_response_sha256": sha256_file(raw_path),
        "normalized_report_sha256": sha256_file(normalized_path),
        "valid": False,
        "abstain": bool(report["abstain"]),
        "validation_errors": ["model_output_unusable"],
        "total_elapsed_seconds": 0.125,
        "event_accuracy_measured": False,
    }
    _write_json(base / "receipt.json", receipt)
    return receipt


def test_unique_coverage_does_not_double_count_overlapping_windows(tmp_path: Path) -> None:
    project_root, dataset, manifest, offline = _source_receipts(tmp_path)
    windows = build_external_windows(project_root, dataset, manifest, offline)
    assert unique_sampled_seconds(windows) <= PLANNED_WINDOW_DENOMINATOR * WINDOW_SECONDS
    overlapping = [
        replace(windows[0], start_seconds=10.0),
        replace(windows[1], start_seconds=30.0),
    ]
    assert unique_sampled_seconds(overlapping) == 80.0


def test_terminal_receipt_is_resumed_without_frame_extraction_or_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding = _binding_stub()
    output = tmp_path / "output"
    binding_path = output / "frozen-prompt-binding.json"
    _write_json(binding_path, binding)
    window = ExternalWindow(
        window_id="fmdv-resume",
        external_unit_id=EXTERNAL_UNIT_ID,
        split=EXTERNAL_SPLIT,
        part_number=1,
        source_video_id_private_receipt=123,
        media_path_private_receipt="private/part.mp4",
        media_sha256="a" * 64,
        start_seconds=10.0,
        duration_seconds=60,
        anchor_index=0,
        anchor_fraction=0.2,
    )
    cached = _write_terminal_fixture(output, window, binding)
    monkeypatch.setattr(
        "footballmaster.dvids_external.extract_frames",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("resume extracted frames")),
    )
    monkeypatch.setattr(
        "footballmaster.dvids_external._post_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("resume called HTTP")),
    )
    resumed = run_external_one(tmp_path, output, window, binding, timeout_seconds=1)
    assert resumed == cached


@pytest.mark.parametrize("artifact", ["frame", "request"])
def test_terminal_resume_rejects_tampered_input_receipts_before_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    binding = _binding_stub()
    output = tmp_path / "output"
    _write_json(output / "frozen-prompt-binding.json", binding)
    window = ExternalWindow(
        window_id="fmdv-resume-tamper",
        external_unit_id=EXTERNAL_UNIT_ID,
        split=EXTERNAL_SPLIT,
        part_number=1,
        source_video_id_private_receipt=123,
        media_path_private_receipt="private/part.mp4",
        media_sha256="a" * 64,
        start_seconds=10.0,
        duration_seconds=60,
        anchor_index=0,
        anchor_fraction=0.2,
    )
    _write_terminal_fixture(output, window, binding)
    base = output / "runs" / window.window_id
    if artifact == "frame":
        (base / "frames" / "F03.jpg").write_bytes(b"tampered-frame")
        expected = "frame receipt changed"
    else:
        request_path = base / "attempt-1-request-receipt.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["audio_used"] = True
        _write_json(request_path, request)
        expected = "request receipt self-hash changed"
    monkeypatch.setattr(
        "footballmaster.dvids_external.extract_frames",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tampered resume extracted")),
    )
    monkeypatch.setattr(
        "footballmaster.dvids_external._post_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tampered resume called HTTP")),
    )
    with pytest.raises(RuntimeError, match=expected):
        run_external_one(tmp_path, output, window, binding, timeout_seconds=1)


def test_posthoc_results_are_blocked_until_all_predictions_are_sealed(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="sealed before post-hoc"):
        build_results(tmp_path)


@pytest.mark.parametrize("mutation", ["start", "window_id"])
def test_run_preflight_rejects_structurally_valid_manifest_mutation_before_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    project_root, dataset, core, output, _windows, _binding = _prepared_fixture(tmp_path)
    rows = [
        json.loads(line)
        for line in (output / "window-manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if mutation == "start":
        rows[0]["start_seconds"] = round(float(rows[0]["start_seconds"]) + 1.0, 3)
    else:
        rows[0]["window_id"] = "fmdv-ffffffffffffffff"
    (output / "window-manifest.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(
        "footballmaster.dvids_external.run_external_one",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("preflight reached call")),
    )
    with pytest.raises(ValueError, match="deterministic source construction"):
        run_all(project_root, dataset, output, timeout_seconds=1, core_dir=core)
    assert not (output / "runs").exists()


def test_run_preflight_rejects_protocol_mutation_before_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, dataset, core, output, _windows, _binding = _prepared_fixture(tmp_path)
    protocol_path = output / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["claims"]["performance_claim_allowed"] = True
    _write_json(protocol_path, protocol)
    monkeypatch.setattr(
        "footballmaster.dvids_external.run_external_one",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("preflight reached call")),
    )
    with pytest.raises(ValueError, match="protocol receipt hash binding changed"):
        run_all(project_root, dataset, output, timeout_seconds=1, core_dir=core)
    assert not (output / "runs").exists()


def test_clearance_must_bind_every_frozen_protocol_prompt_and_core_hash(tmp_path: Path) -> None:
    _project_root, _dataset, _core, output, _windows, binding = _prepared_fixture(tmp_path)
    clearance = _authorize(output, binding)
    assert validate_clearance(output, binding) == clearance
    clearance.pop("core_prompt_candidates_sha256")
    _write_json(output / "gpu-clearance.json", clearance)
    with pytest.raises(PermissionError, match="core_prompt_candidates_sha256"):
        validate_clearance(output, binding)


def test_prediction_seal_requires_all_57_terminal_windows_and_detects_mutation(
    tmp_path: Path,
) -> None:
    project_root, dataset, _core, output, windows, binding = _prepared_fixture(tmp_path)
    _authorize(output, binding)
    with pytest.raises(RuntimeError, match="incomplete DVIDS window"):
        seal_predictions(output)
    for window in windows:
        _write_terminal_fixture(output, window, binding)
    seal = seal_predictions(output)
    assert seal["terminal_window_receipts"] == 57
    assert seal["sentinel_evaluation_performed_before_seal"] is False
    assert verify_prediction_seal(output)["root_hash"] == seal["root_hash"]
    metrics = build_results(output)
    assert metrics["terminal_window_receipts"] == 57
    assert metrics["event_accuracy_measured"] is False
    assert metrics["abstain_with_nonempty_events_contradictions"] == 0
    assert metrics["semantic_coach_search_verdict"].startswith("NO-GO")
    assert verify_protocol(project_root, dataset, output, require_results=True)["status"] == "pass"
    state = json.loads((output / "execution-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "final_verified_descriptive_results_semantic_no_go"
    assert state["terminal_window_receipts"] == 57
    first_frame = output / "runs" / windows[0].window_id / "frames" / "F00.jpg"
    first_frame.write_bytes(b"mutated-frame-after-seal")
    with pytest.raises(ValueError, match="sealed prediction artifact mismatch"):
        verify_prediction_seal(output)
