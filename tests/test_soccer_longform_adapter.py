from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest


PROJECT = Path(__file__).resolve().parents[1]
PROTOTYPE = PROJECT / "prototype"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_with_football_blocked(monkeypatch: pytest.MonkeyPatch):
    blocked = "football_" + "longform_adapter"
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == blocked:
            raise ImportError("blocked by soccer isolation test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.syspath_prepend(str(PROTOTYPE))
    sys.modules.pop("soccer_longform_adapter", None)
    return importlib.import_module("soccer_longform_adapter")


def _fixture(project: Path) -> tuple[Path, Path]:
    artifact = project / "artifacts" / "soccermaster-longform-v1"
    private = project / "data" / "private" / "soccermaster-longform-v1"
    experiment = private / "experiment"
    raw = private / "raw" / "opaque-game"
    artifact.mkdir(parents=True)
    experiment.mkdir(parents=True)
    raw.mkdir(parents=True)
    media = {}
    for half in (1, 2):
        path = raw / f"half-{half}.mp4"
        path.write_bytes(f"private soccer half {half}".encode())
        media[half] = path
    source_lock = {
        "schema_version": "fixture",
        "test": {
            "source_scope_id": "opaque-test-game",
            "halves": [
                {
                    "half": half,
                    "duration_seconds": 2700.0,
                    "media_path": str(media[half].resolve()),
                    "media_sha256": _sha(media[half]),
                }
                for half in (1, 2)
            ],
        },
    }
    _write_json(experiment / "source-lock.json", source_lock)

    report = {
        "schema_version": "soccermaster-longform-visual-report-v2-number-disabled",
        "visual_only": True,
        "abstain": False,
        "abstention_reason": "",
        "window_summary": "A long ball and transition are asserted near the attacking third.",
        "tactics_observed": ["direct progression"],
        "coach_search_terms": ["long ball", "transition"],
        "overall_uncertainties": ["Sparse frames do not establish continuity."],
        "events": [
            {
                "event_type": "long_ball",
                "primary_action": "Forward long pass",
                "sequence_detail": "A direct pass is asserted from two sampled frames.",
                "outcome": "unknown",
                "phase_of_play": "progression",
                "field_areas": ["middle_third", "attacking_third"],
                "confidence": 0.7,
                "evidence_frame_ids": ["F01", "F03"],
                "coaching_relevance": "Review direct progression.",
                "search_terms": ["long pass"],
                "uncertainties": ["Receiver is unclear."],
                "participants": [
                    {
                        "player_reference": "attacking player",
                        "visible_jersey_number": None,
                        "identity_basis": "role_only",
                        "role_in_event": "passer",
                        "team_reference": "unknown",
                        "observable_action": "kicks the ball",
                    }
                ],
            }
        ],
    }
    index_rows = []
    manifest_rows = []
    for half in (1, 2):
        for ordinal in range(45):
            window_id = f"dense-h{half}-{ordinal:02d}"
            entry = {
                "schema_version": "soccermaster-longform-search-entry-v1",
                "window_id": window_id,
                "window_role": "test_dense",
                "source_half": half,
                "start_seconds": float(ordinal * 60),
                "duration_seconds": 60,
                "abstain": False,
                "report": report,
                "search_text": "long ball direct progression transition attacking third",
                "visual_report_sha256": "0" * 64,
            }
            index_rows.append(entry)
            manifest_rows.append(
                {
                    "window_id": window_id,
                    "role": "test_dense",
                    "source_half": half,
                    "start_seconds": float(ordinal * 60),
                    "duration_seconds": 60,
                    "frame_count": 12,
                }
            )
        for stress, duration in enumerate((30, 60, 120)):
            window_id = f"stress-h{half}-{duration}"
            entry = {
                "schema_version": "soccermaster-longform-search-entry-v1",
                "window_id": window_id,
                "window_role": "test_stress",
                "source_half": half,
                "start_seconds": float(300 + stress * 300),
                "duration_seconds": duration,
                "abstain": False,
                "report": report,
                "search_text": "long ball direct progression transition attacking third",
                "visual_report_sha256": "0" * 64,
            }
            index_rows.append(entry)
            manifest_rows.append(
                {
                    "window_id": window_id,
                    "role": "test_stress",
                    "source_half": half,
                    "start_seconds": float(300 + stress * 300),
                    "duration_seconds": duration,
                    "frame_count": {30: 8, 60: 12, 120: 16}[duration],
                }
            )
    index_path = experiment / "soccer-search-index.jsonl"
    index_path.write_text("".join(json.dumps(row) + "\n" for row in index_rows), encoding="utf-8")
    manifest_path = experiment / "window-manifest.jsonl"
    manifest_path.write_text("".join(json.dumps(row) + "\n" for row in manifest_rows), encoding="utf-8")

    public_values = {
        "protocol-receipt.json": {"claims": {"performance_claim_allowed": False}},
        "frozen-test-config.json": {"model": "google/gemma-4-e4b", "test_window_denominator": 96},
        "report-metrics.json": {"window_denominator": 96, "valid_response_count": 96, "failure_count": 0},
        "search-index-receipt.json": {"entry_count": 96, "index_sha256": _sha(index_path)},
        "frozen-query-results.json": {"query_count": 20},
        "test-run-receipt.json": {"status": "complete", "window_denominator": 96},
    }
    for name, value in public_values.items():
        _write_json(artifact / name, value)
    files = {f"public/{name}": _sha(artifact / name) for name in public_values}
    files.update(
        {
            "private/soccer-search-index.jsonl": _sha(index_path),
            "private/source-lock.json": _sha(experiment / "source-lock.json"),
            "private/window-manifest.jsonl": _sha(manifest_path),
        }
    )
    seal = {"files": files, "root_hash": _canonical(files)}
    _write_json(artifact / "prediction-seal.json", seal)

    evaluation = {
        "performance_claim_allowed": False,
        "labels_opened_only_after_visual_prediction_seal_verified": True,
        "mapped_visible_annotation_denominator": 166,
        "mapped_vlm_prediction_denominator": 54,
        "temporally_corroborated_annotation_count": 3,
        "temporally_corroborated_prediction_count": 3,
    }
    spot = {
        "judgment_counts": {
            "supported": 0,
            "partially_supported": 2,
            "unsupported": 4,
            "abstention_appropriate": 0,
        },
        "rows": [
            {
                "window_id": "dense-h1-00",
                "overall_judgment": "unsupported",
                "visual_observations": "The asserted pass is not established.",
            }
        ],
    }
    verification = {
        "status": "pass",
        "visual_prediction_seal_root_hash": seal["root_hash"],
        "checks": {
            "dense_window_count": 90,
            "stress_window_count": 6,
            "test_window_denominator": 96,
            "test_valid_response_count": 96,
            "test_failure_count": 0,
            "labels_opened_only_post_seal": True,
            "input_anonymization_audit_status": "failed_in_at_least_one_sampled_frame",
            "team_name_pixels_fully_unavailable": False,
        },
    }
    _write_json(artifact / "annotation-evaluation.json", evaluation)
    _write_json(artifact / "spot-check-adjudication.json", spot)
    _write_json(artifact / "verification-receipt.json", verification)
    package_names = (
        "annotation-evaluation.json",
        "spot-check-adjudication.json",
        "verification-receipt.json",
        "prediction-seal.json",
    )
    _write_json(
        artifact / "package-receipt.json",
        {
            "status": "implementation_verified_independent_review_pending",
            "performance_claim_allowed": False,
            "artifacts": [{"name": name, "sha256": _sha(artifact / name)} for name in package_names],
        },
    )
    return artifact, private


def test_adapter_loads_and_searches_without_football_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_with_football_blocked(monkeypatch)
    artifact, private = _fixture(tmp_path)
    context = module.load_context(artifact, private_root=private, project_root=tmp_path)
    assert len(context.entries) == 96
    assert context.coverage["dense_entire_game_index"] is True
    assert context.coverage["dense_window_count"] == 90
    assert context.coverage["stress_durations_seconds"] == [30, 60, 120]
    assert set(context.media_routes) == {
        "/media/soccer/longform/half-1",
        "/media/soccer/longform/half-2",
    }

    payload = module.search_context(context, "long ball into the attacking third", use_query_llm=False)
    assert payload["result_count"] == 12
    result = payload["results"][0]
    assert result["event_types"] == ["long_ball"]
    assert result["clip_url"].startswith("/media/soccer/longform/half-")
    assert result["match_id"] == "private-held-out-soccer-match"
    assert "opaque-game" not in json.dumps(payload)
    assert result["attribution"]["audio_fields"] == []
    assert "untrusted" in result["attribution"]["boundary"]

    monkeypatch.setattr(
        module,
        "interpret_query",
        lambda *_args, **_kwargs: {
            "source": "local_query_llm",
            "requested_model": module.DEFAULT_MODEL,
            "reported_model": module.DEFAULT_MODEL,
            "search_terms": ["offside"],
            "event_types": ["offside"],
            "raw_interpretation": "{}",
            "error": None,
        },
    )
    assert module.search_context(context, "find offsides", use_query_llm=True)["result_count"] == 0


def test_adapter_rejects_postseal_semantic_boundary_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_with_football_blocked(monkeypatch)
    artifact, private = _fixture(tmp_path)
    evaluation_path = artifact / "annotation-evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["performance_claim_allowed"] = True
    _write_json(evaluation_path, evaluation)
    package_path = artifact / "package-receipt.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    for item in package["artifacts"]:
        if item["name"] == "annotation-evaluation.json":
            item["sha256"] = _sha(evaluation_path)
    _write_json(package_path, package)
    with pytest.raises(ValueError, match="claim boundary"):
        module.load_context(artifact, private_root=private, project_root=tmp_path)


def test_adapter_rejects_source_path_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_with_football_blocked(monkeypatch)
    artifact, private = _fixture(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"not private soccer media")
    source_lock_path = private / "experiment" / "source-lock.json"
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    source_lock["test"]["halves"][0]["media_path"] = str(outside.resolve())
    source_lock["test"]["halves"][0]["media_sha256"] = _sha(outside)
    _write_json(source_lock_path, source_lock)
    seal_path = artifact / "prediction-seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["files"]["private/source-lock.json"] = _sha(source_lock_path)
    seal["root_hash"] = _canonical(seal["files"])
    _write_json(seal_path, seal)
    verification_path = artifact / "verification-receipt.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["visual_prediction_seal_root_hash"] = seal["root_hash"]
    _write_json(verification_path, verification)
    package_path = artifact / "package-receipt.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    for item in package["artifacts"]:
        if item["name"] == "prediction-seal.json":
            item["sha256"] = _sha(seal_path)
        if item["name"] == "verification-receipt.json":
            item["sha256"] = _sha(verification_path)
    _write_json(package_path, package)
    with pytest.raises(ValueError, match="escaped"):
        module.load_context(artifact, private_root=private, project_root=tmp_path)


def test_endpoint_must_be_literal_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_with_football_blocked(monkeypatch)
    module.ensure_loopback_endpoint("http://127.0.0.1:1240/v1")
    with pytest.raises(ValueError):
        module.ensure_loopback_endpoint("https://api.example.com/v1")


def test_adapter_source_has_no_football_import() -> None:
    source = (PROTOTYPE / "soccer_longform_adapter.py").read_text(encoding="utf-8")
    assert "football_" + "longform_adapter" not in source
