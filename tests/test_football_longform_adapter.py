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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _load_with_other_engine_blocked(monkeypatch: pytest.MonkeyPatch):
    blocked = "search_" + "demo_server"
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == blocked:
            raise ImportError("blocked by isolation test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.syspath_prepend(str(PROTOTYPE))
    sys.modules.pop("football_longform_adapter", None)
    return importlib.import_module("football_longform_adapter")


def _fixture(project: Path) -> Path:
    dataset = project / "data" / "public" / "footballmaster-v2"
    media = dataset / "media" / "fixture-game.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"football video fixture")
    media_sha = _sha(media)
    assets = [
        {
            "asset_id": "fixture-game",
            "downloaded_sha256": media_sha,
            "observed_duration_seconds": 3600.0,
            "license_spdxish": "CC-BY-SA-3.0",
            "canonical_page_url": "https://example.invalid/fixture",
        }
    ]
    _write_json(dataset / "source-manifest.json", {"assets": assets})
    _write_json(dataset / "verification-receipt.json", {"checks": {"five_hour_duration_gate": "pass"}})

    output = project / "artifacts" / "footballmaster" / "longform-v2"
    output.mkdir(parents=True)
    report = {
        "schema_version": "footballmaster-visual-report-v2",
        "visual_only": True,
        "abstain": False,
        "abstention_reason": "",
        "confidence": "medium",
        "window_summary": "A forward pass is visible near the sideline.",
        "events": [
            {
                "event_type": "pass_play",
                "action": "forward pass",
                "outcome": "unknown",
                "actors_visible": ["passer; identity unknown"],
                "field_context": "sideline",
                "evidence_frame_ids": ["F03"],
                "uncertainties": ["completion unknown"],
            }
        ],
        "formations_and_tactics": [],
        "coach_search_terms": ["forward pass", "sideline"],
    }
    index = output / "football-search-index.jsonl"
    rows = []
    for index_number in range(36):
        duration = (30, 60, 120)[index_number % 3]
        rows.append(
            {
                "window_id": f"w-{index_number:02d}",
                "game_id": f"game-{index_number % 2}",
                "split": "test",
                "start_seconds": float(index_number * 30),
                "duration_seconds": duration,
                "media_path": "data/public/footballmaster-v2/media/fixture-game.mp4",
                "media_sha256": media_sha,
                "abstain": False,
                "confidence": "medium",
                "search_text": "forward pass sideline",
                "report": report,
            }
        )
    index.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    window_manifest = output / "window-manifest.jsonl"
    window_manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    required = {
        "protocol.json": {
            "dataset_duration_hours": 5.62937375,
            "files": {"window_manifest_sha256": _sha(window_manifest)},
        },
        "frozen-test-config.json": {},
        "report-metrics.json": {"performance_claim_allowed": False},
        "football-search-index-receipt.json": {"entry_count": 36, "index_sha256": _sha(index)},
        "frozen-query-results.json": {},
        "weak-visual-probe-receipt.json": {},
    }
    for name, value in required.items():
        _write_json(output / name, value)
    sealed_names = [*required, "football-search-index.jsonl"]
    files = {name: _sha(output / name) for name in sealed_names}
    root_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    _write_json(output / "prediction-seal.json", {"files": files, "root_hash": root_hash})
    _write_json(output / "verification-receipt.json", {"status": "pass"})
    return output


def test_adapter_loads_and_searches_when_other_engine_import_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_with_other_engine_blocked(monkeypatch)
    output = _fixture(tmp_path)
    context = module.load_context(output, project_root=tmp_path)
    payload = module.search_context(context, "forward pass near the sideline", use_query_llm=False)
    assert payload["result_count"] == 12
    assert payload["results"][0]["event_types"] == ["pass_play"]
    assert payload["results"][0]["clip_url"] == "/media/football/fixture-game"
    assert payload["results"][0]["attribution"]["audio_fields"] == []
    assert context.coverage["corpus_duration_seconds"] == 20265.7455
    assert context.coverage["all_window_count"] == 36
    assert context.coverage["all_nominal_window_seconds"] == 2520.0
    assert context.coverage["by_split"]["test"]["window_count"] == 36
    assert context.coverage["dense_entire_game_index"] is False


def test_endpoint_must_be_literal_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_with_other_engine_blocked(monkeypatch)
    module.ensure_loopback_endpoint("http://127.0.0.1:1240/v1")
    with pytest.raises(ValueError):
        module.ensure_loopback_endpoint("https://api.example.com/v1")


def test_adapter_source_has_no_other_engine_import() -> None:
    source = (PROTOTYPE / "football_longform_adapter.py").read_text(encoding="utf-8")
    assert "search_" + "demo_server" not in source
