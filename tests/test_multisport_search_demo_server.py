import hashlib
import json
import sqlite3
import sys
import threading
from types import SimpleNamespace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import multisport_search_demo_server as module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _raw_plan(sport: str) -> dict:
    if sport == "football":
        return {
            "intent_summary": "Find touchdown pass clips.",
            "event_types": ["touchdown_pass"],
            "search_terms": ["touchdown"],
            "participant_terms": [],
            "phases": ["unknown"],
            "field_areas": ["unknown"],
            "explanation": "Match the requested source event tag and saved report text.",
        }
    return {
        "intent_summary": "Find shots.",
        "event_types": ["shot_on_target"],
        "search_terms": ["shot"],
        "participant_terms": [],
        "phases": [],
        "field_areas": [],
        "explanation": "Match the requested saved soccer report text.",
    }


def _football_package(project: Path) -> Path:
    media = project / "data" / "public" / "footballmaster" / "media" / "fixture-touchdown.webm"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"0123456789abcdef")
    source_manifest = {
        "schema_version": "fixture",
        "assets": [
            {
                "asset_id": "fixture-touchdown",
                "license_spdxish": "CC-BY-4.0",
                "canonical_page_url": "https://commons.wikimedia.org/wiki/File:Fixture.webm",
            }
        ],
    }
    _write_json(project / "data" / "public" / "footballmaster" / "source-manifest.json", source_manifest)

    package = project / "artifacts" / "footballmaster-fixture"
    package.mkdir(parents=True)
    database = package / "search-index.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE windows(
          window_id TEXT PRIMARY KEY,ordinal INTEGER,match_id TEXT,start_s REAL,end_s REAL,status TEXT,
          report_json TEXT,error_type TEXT,error_message TEXT,elapsed_ms INTEGER,updated_at TEXT,
          sport TEXT,clip_id TEXT,source_id TEXT,split TEXT,media_path TEXT
        );
        CREATE TABLE events(
          event_id TEXT PRIMARY KEY,window_id TEXT,event_types_json TEXT,primary_action TEXT,
          start_s REAL,end_s REAL,confidence REAL,report_json TEXT
        );
        INSERT INTO metadata VALUES('sport','american_football');
        """
    )
    event = {
        "event_id": "football-fixture-w:e01",
        "sport": "american_football",
        "event_types": ["touchdown_pass"],
        "primary_action": "touchdown pass",
        "phase_of_play": "unknown",
        "field_areas": ["unknown"],
        "outcome": "Source description marks a touchdown.",
        "detailed_description": "Source tag: touchdown pass. Learned probe predicts touchdown.",
        "coaching_relevance": "Human review required.",
        "coaching_tags": ["touchdown_pass", "footballmaster_touchdown"],
        "retrieval_keywords": ["touchdown pass", "touchdown"],
        "uncertainty": "Tiny weakly labeled pilot.",
        "participants": [],
        "evidence_frames": [],
        "report_origin": "deterministic_projection_of_source_metadata_and_learned_binary_prediction",
        "learned_fields": ["predicted_label", "probabilities", "confidence", "learned_embedding"],
        "source_metadata_fields": ["event_types", "primary_action", "source target"],
        "vlm_generated_fields": [],
        "predicted_label": "touchdown",
        "probabilities": {"not_touchdown": 0.2, "touchdown": 0.8},
        "split": "test",
    }
    connection.execute(
        "INSERT INTO windows VALUES(?,?,?,?,?,'complete',?,NULL,NULL,0,?,?,?,?,?,?)",
        (
            "football-fixture-w",
            0,
            "fixture-source",
            0.0,
            4.0,
            json.dumps({"events": [event]}),
            "2026-08-27T00:00:00Z",
            "american_football",
            "fixture-touchdown",
            "fixture-source",
            "test",
            "data/public/footballmaster/media/fixture-touchdown.webm",
        ),
    )
    connection.execute(
        "INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",
        (
            "football-fixture-w:e01",
            "football-fixture-w",
            json.dumps(["touchdown_pass"]),
            "touchdown pass",
            1.0,
            3.0,
            0.8,
            json.dumps(event),
        ),
    )
    connection.commit()
    connection.close()

    plan = {
        "schema_version": "footballmaster-search-index-v1",
        "sport": "american_football",
        "windows": [
            {
                "window_id": "football-fixture-w",
                "clip_id": "fixture-touchdown",
                "source_id": "fixture-source",
                "split": "test",
                "media_path": "data/public/footballmaster/media/fixture-touchdown.webm",
                "media_sha256": _sha(media),
                "local_window_s": [0.0, 4.0],
                "source_window_s": [10.0, 14.0],
            }
        ],
        "semantic_boundary": {
            "learned": "binary is_touchdown probability only",
            "source_metadata": "fine event tags",
            "deterministic": "prose projection and retrieval",
            "vlm": "none in this index",
        },
    }
    metrics = {
        "schema_version": "footballmaster-pilot-metrics-v1",
        "performance_claim_allowed": False,
        "claim_boundary": "Fixture tiny-pilot boundary.",
        "test": {"accuracy": 0.5},
    }
    model_card = {
        "schema_version": "footballmaster-pilot-model-card-v1",
        "actual_trained_parameters": True,
        "architecture_scope": "football_only",
        "evaluated_target": "is_touchdown",
    }
    _write_json(package / "index-plan.json", plan)
    _write_json(package / "metrics.json", metrics)
    _write_json(package / "model-card.json", model_card)
    (package / "footballmaster-pilot-v1.npz").write_bytes(b"fixture checkpoint")
    _write_json(package / "model-config.json", {"schema_version": "fixture"})
    (package / "predictions.jsonl").write_text('{"clip_id":"fixture-touchdown"}\n', encoding="utf-8")
    (package / "training-log.jsonl").write_text('{"epoch":1}\n', encoding="utf-8")
    _write_json(package / "feature-receipts.json", {"schema_version": "fixture"})
    receipt = {
        "status": "pass",
        "sport": "american_football",
        "database_sha256": _sha(database),
        "index_plan_sha256": _sha(package / "index-plan.json"),
        "metrics_sha256": _sha(package / "metrics.json"),
        "model_card_sha256": _sha(package / "model-card.json"),
        "checkpoint_sha256": _sha(package / "footballmaster-pilot-v1.npz"),
        "model_config_sha256": _sha(package / "model-config.json"),
        "predictions_sha256": _sha(package / "predictions.jsonl"),
        "training_log_sha256": _sha(package / "training-log.jsonl"),
        "feature_receipts_sha256": _sha(package / "feature-receipts.json"),
        "source_manifest_sha256": _sha(project / "data" / "public" / "footballmaster" / "source-manifest.json"),
        "source_held_out_test": True,
        "performance_claim_allowed": False,
    }
    _write_json(package / "run-receipt.json", receipt)
    return package


def test_sport_specific_query_contracts_and_prompt_isolation() -> None:
    football = module.validate_query_plan(_raw_plan("football"), module.SPORT_SPECS["football"])
    soccer = module.validate_query_plan(_raw_plan("soccer"), module.SPORT_SPECS["soccer"])
    assert football["sport"] == "football" and football["event_types"] == ["touchdown_pass"]
    assert soccer["sport"] == "soccer" and soccer["event_types"] == ["shot_on_target"]
    with pytest.raises(ValueError, match="ontology"):
        module.validate_query_plan(_raw_plan("football"), module.SPORT_SPECS["soccer"])

    system, user = module.query_interpreter_prompt("find passes by number 8", module.SPORT_SPECS["football"])
    prompt = (system + user).casefold()
    assert "american football" in prompt and "touchdown_pass" in prompt
    for forbidden in ("labels-v2", "factually wrong", "post-hoc", "audit", "commentary transcript"):
        assert forbidden not in prompt


def test_literal_fallback_is_sport_scoped_and_does_not_invent_filters() -> None:
    plan = module.fallback_query_plan("Show touchdown passes by number 8", "offline", module.SPORT_SPECS["football"])
    assert plan["sport"] == "football"
    assert plan["event_types"] == []
    assert "touchdown" in plan["search_terms"] and "8" in plan["search_terms"]


def test_missing_football_package_is_an_explicit_nonfatal_state(tmp_path: Path) -> None:
    context = module.load_football_context(project_root=tmp_path)
    assert not context.available
    assert context.demo_status == "UNAVAILABLE"
    assert "no verified package" in context.unavailable_reason


def test_longform_v2_is_preferred_and_football_path_avoids_soccer_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "artifacts" / "footballmaster" / "longform-v2"
    output.mkdir(parents=True)
    (output / "football-search-index.jsonl").write_text("{}\n", encoding="utf-8")
    media = tmp_path / "fixture.mp4"
    media.write_bytes(b"football-only fixture")
    binding = module.football_adapter.MediaBinding(
        asset_id="held-out-game",
        route="/media/football/held-out-game",
        path=media,
        sha256=_sha(media),
        duration_seconds=3600.0,
        license_spdxish="CC-BY-4.0",
        source_page_url="https://example.invalid/held-out-game",
    )
    entries = tuple(
        {
            "window_id": f"w-{index:02d}",
            "report": {"events": [{"event_type": "pass_play"}]},
        }
        for index in range(36)
    )
    standalone = module.football_adapter.FootballContext(
        output_root=output,
        entries=entries,
        media_by_window={entry["window_id"]: binding for entry in entries},
        media_routes={binding.route: binding},
        verification={"status": "pass"},
        metrics={
            "test_semantic_contract": {
                "status": "NO-GO",
                "denominator": 36,
                "abstain_with_nonempty_events_count": 27,
            }
        },
        model=module.DEFAULT_MODEL,
        endpoint=module.DEFAULT_ENDPOINT,
        coverage={
            "corpus_duration_seconds": 20265.7455,
            "corpus_duration_hours": 5.62937375,
            "all_window_count": 69,
            "all_nominal_window_seconds": 4830.0,
            "all_unique_sampled_seconds": 2760.0,
            "test_source_program_seconds": 6438.9325,
            "by_split": {
                "train": {"window_count": 27, "nominal_window_seconds": 1890.0, "unique_sampled_seconds": 1080.0},
                "valid": {"window_count": 6, "nominal_window_seconds": 420.0, "unique_sampled_seconds": 240.0},
                "test": {"window_count": 36, "nominal_window_seconds": 2520.0, "unique_sampled_seconds": 1440.0},
            },
            "dense_entire_game_index": False,
        },
    )
    monkeypatch.setattr(module.football_adapter, "load_context", lambda *_args, **_kwargs: standalone)
    monkeypatch.setattr(
        module.soccer_server,
        "ensure_loopback_endpoint",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("soccer helper called")),
    )
    context = module.load_football_context(project_root=tmp_path)
    assert context.available and context.backend == "longform_v2"
    assert context.index_root == output
    status = module.status_payload(context)
    assert status["coverage"]["corpus_duration_seconds"] == 20265.7455
    assert status["coverage"]["all_unique_sampled_seconds"] == 2760.0
    assert status["coverage"]["by_split"]["test"]["unique_sampled_seconds"] == 1440.0
    assert "2,520 nominal overlapping test-window seconds" in status["warning"]
    assert "6,438.9325 seconds" in status["warning"]
    assert "20,265.7455 seconds" in status["warning"]
    assert "1,440 unique test seconds" in status["pipeline"][1]

    monkeypatch.setattr(
        module.football_adapter,
        "search_context",
        lambda *_args, **_kwargs: {
            "query": "forward pass",
            "interpretation": {
                "source": "deterministic_literal_fallback",
                "requested_model": module.DEFAULT_MODEL,
                "search_terms": ["forward pass"],
                "event_types": ["pass_play"],
                "error": "query model disabled in fixture",
            },
            "results": [{"event_id": "w-00", "clip_url": binding.route}],
            "result_count": 1,
            "ranking_note": "fixture ranking",
        },
    )
    payload = module.search_football_longform(context, "forward pass")
    assert payload["results"][0]["clip_url"] == binding.route
    assert payload["interpretation"]["plan"]["event_types"] == ["pass_play"]


def test_verified_full_game_soccer_is_preferred_and_literal_mode_never_calls_query_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "artifacts" / "soccermaster-longform-v1"
    private = tmp_path / "data" / "private" / "soccermaster-longform-v1"
    artifact.mkdir(parents=True)
    private.mkdir(parents=True)
    media = private / "half-1-silent.mp4"
    media.write_bytes(b"private full-game soccer fixture")
    binding = module.soccer_adapter.MediaBinding(
        half=1,
        asset_id="soccer-test-half-1",
        route="/media/soccer/longform/half-1",
        path=media,
        sha256=_sha(media),
        duration_seconds=2700.0,
        source_media_sha256="0" * 64,
        browser_compatible_derivative=True,
    )
    entries = tuple(
        {
            "window_id": f"smw-{index:03d}",
            "report": {"events": [{"event_type": "long_ball"}]},
        }
        for index in range(96)
    )
    standalone = module.soccer_adapter.SoccerContext(
        artifact_root=artifact,
        private_root=private,
        entries=entries,
        media_by_window={entry["window_id"]: binding for entry in entries},
        media_routes={binding.route: binding},
        verification={
            "status": "pass",
            "checks": {"input_anonymization_audit_status": "failed_in_at_least_one_sampled_frame"},
        },
        metrics={"window_denominator": 96, "valid_response_count": 96, "failure_count": 0},
        evaluation={
            "temporally_corroborated_annotation_count": 3,
            "mapped_visible_annotation_denominator": 166,
            "restricted_mapped_annotation_recall": 3 / 166,
            "temporally_corroborated_prediction_count": 3,
            "mapped_vlm_prediction_denominator": 54,
            "restricted_mapped_prediction_precision": 3 / 54,
        },
        spot_check={
            "judgment_counts": {
                "supported": 0,
                "partially_supported": 2,
                "unsupported": 4,
                "abstention_appropriate": 0,
            }
        },
        coverage={
            "source_seconds": 5400.0,
            "dense_entire_game_index": True,
            "dense_window_count": 90,
            "stress_window_count": 6,
        },
        model=module.DEFAULT_MODEL,
        endpoint=module.DEFAULT_ENDPOINT,
    )
    monkeypatch.setattr(module.soccer_adapter, "load_context", lambda *_args, **_kwargs: standalone)
    monkeypatch.setattr(
        module.soccer_server,
        "load_demo_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy soccer fallback used")),
    )
    context = module.load_soccer_context(project_root=tmp_path)
    assert context.available and context.backend == "soccermaster_longform_v1"
    status = module.status_payload(context, query_llm_enabled=False)
    assert status["coverage"]["dense_entire_game_index"] is True
    assert status["semantic_contract"]["mapped_annotation_recall_count"] == 3
    assert status["semantic_contract"]["spot_check_judgment_counts"]["supported"] == 0
    assert status["query_mode"] == "deterministic_literal_fallback"
    assert status["model_health"]["skipped"] is True

    calls = []
    monkeypatch.setattr(
        module.soccer_adapter,
        "search_context",
        lambda *_args, **kwargs: calls.append(kwargs) or {
            "query": "long ball",
            "interpretation": {
                "source": "deterministic_literal_fallback",
                "requested_model": module.DEFAULT_MODEL,
                "reported_model": module.DEFAULT_MODEL,
                "search_terms": ["long ball"],
                "event_types": [],
                "raw_interpretation": None,
                "error": "query LLM disabled for this server session",
            },
            "results": [{"window_id": "smw-000", "clip_url": binding.route}],
            "result_count": 1,
            "ranking_note": "fixture BM25",
        },
    )
    payload = module.search_soccer_longform(context, "long ball", use_query_llm=False)
    assert payload["results"][0]["clip_url"] == binding.route
    assert calls == [{"limit": 12, "use_query_llm": False}]


def test_soccer_legacy_fallback_is_explicit_when_full_game_verification_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE windows(window_id TEXT,start_s REAL,status TEXT);"
        "INSERT INTO windows VALUES('legacy-window',0.0,'complete');"
        "CREATE TABLE events(event_id TEXT);"
    )
    connection.close()
    review = tmp_path / "legacy-review.mp4"
    review.write_bytes(b"legacy soccer review fixture")
    sealed = SimpleNamespace(
        database=database,
        review_clip=review,
        window_start_s=10.0,
        window_end_s=20.0,
        index_plan={"configuration": {"match_id": "opaque-legacy"}},
        receipt={"status": "pass"},
        audit=(),
        index_root=tmp_path,
    )
    monkeypatch.setattr(
        module.soccer_adapter,
        "load_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("fixture seal mismatch")),
    )
    monkeypatch.setattr(module.soccer_server, "load_demo_context", lambda *_args, **_kwargs: sealed)
    context = module.load_soccer_context(project_root=tmp_path)
    assert context.available and context.backend == "legacy_sqlite_fallback"
    assert context.warning.startswith("LEGACY FALLBACK")
    assert any("fixture seal mismatch" in error for error in context.discovery_errors)


def test_verified_football_package_search_and_attribution(tmp_path: Path) -> None:
    package = _football_package(tmp_path)
    context = module.load_football_context(package, project_root=tmp_path)
    assert context.available
    clip = context.media_routes["/media/football/fixture-touchdown"]
    assert clip.license_spdxish == "CC-BY-4.0"
    assert clip.source_page_url == "https://commons.wikimedia.org/wiki/File:Fixture.webm"
    plan = module.validate_query_plan(_raw_plan("football"), module.SPORT_SPECS["football"])
    results = module.rank_saved_events(context, plan)
    assert len(results) == 1 and results[0]["score"] == 13.5
    payload = module._result_payload(results[0], context)
    assert payload["clip_url"] == "/media/football/fixture-touchdown"
    assert payload["relative_start_s"] == 1.0 and payload["relative_end_s"] == 3.0
    assert payload["source_start_s"] == 11.0 and payload["source_end_s"] == 13.0
    assert payload["attribution"]["learned_probe_fields"] == [
        "predicted_label",
        "probabilities",
        "confidence",
        "learned_embedding",
    ]
    assert payload["attribution"]["optional_vlm_fields"] == []

    source_plan = {
        **plan,
        "event_types": [],
        "search_terms": ["fixture source"],
        "participant_terms": [],
        "phases": [],
        "field_areas": [],
    }
    source_results = module.rank_saved_events(context, source_plan)
    assert len(source_results) == 1 and source_results[0]["score"] == 1.5


def test_legacy_football_scope_key_is_accepted_only_by_the_shared_adapter(tmp_path: Path) -> None:
    package = _football_package(tmp_path)
    card_path = package / "model-card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card.pop("architecture_scope")
    card["soccer_master_replication"] = False
    _write_json(card_path, card)
    receipt_path = package / "run-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["model_card_sha256"] = _sha(card_path)
    _write_json(receipt_path, receipt)

    context = module.load_football_context(package, project_root=tmp_path)
    assert context.available
    assert context.model_card.get("architecture_scope") is None


def test_football_loader_rejects_source_manifest_tamper(tmp_path: Path) -> None:
    package = _football_package(tmp_path)
    manifest_path = tmp_path / "data" / "public" / "footballmaster" / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["assets"][0]["license_spdxish"] = "PROVENANCE-TAMPER"
    _write_json(manifest_path, manifest)

    context = module.load_football_context(package, project_root=tmp_path)
    assert not context.available
    assert any("source manifest does not match" in error for error in context.discovery_errors)


@pytest.mark.parametrize(
    ("filename", "expected_error"),
    [
        ("footballmaster-pilot-v1.npz", "checkpoint"),
        ("model-config.json", "model config"),
        ("predictions.jsonl", "predictions"),
        ("training-log.jsonl", "training log"),
        ("feature-receipts.json", "feature receipts"),
    ],
)
def test_football_loader_rejects_missing_or_tampered_trained_package_file(
    tmp_path: Path, filename: str, expected_error: str
) -> None:
    package = _football_package(tmp_path)
    target = package / filename
    if filename == "footballmaster-pilot-v1.npz":
        target.unlink()
        expected_error = "missing checkpoint"
    else:
        target.write_bytes(target.read_bytes() + b"tamper")

    context = module.load_football_context(package, project_root=tmp_path)
    assert not context.available
    assert any(expected_error in error for error in context.discovery_errors)


def test_ui_initial_media_load_does_not_scroll_past_claim_boundary() -> None:
    app_js = (ROOT / "prototype" / "search_demo_ui" / "app.js").read_text(encoding="utf-8")
    assert "if (scroll) video.scrollIntoView" in app_js
    # Full-game soccer, legacy soccer, and football each initialize media
    # without pulling the viewport past the visible claim boundary.
    assert app_js.count("{ scroll: false }") == 3


def test_football_loader_rejects_media_path_escape(tmp_path: Path) -> None:
    package = _football_package(tmp_path)
    plan_path = package / "index-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["windows"][0]["media_path"] = "data/public/footballmaster/media/../not-allowlisted.webm"
    escaped = tmp_path / "data" / "public" / "footballmaster" / "not-allowlisted.webm"
    escaped.write_bytes(b"outside exact media root")
    plan["windows"][0]["media_sha256"] = _sha(escaped)
    _write_json(plan_path, plan)
    receipt_path = package / "run-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["index_plan_sha256"] = _sha(plan_path)
    _write_json(receipt_path, receipt)

    context = module.load_football_context(package, project_root=tmp_path)
    assert not context.available
    assert any("escaped the allowlisted" in error for error in context.discovery_errors)


def test_byte_range_parser_handles_suffix_and_rejects_multiple_ranges() -> None:
    assert module.parse_byte_range(None, 16) == (0, 15, False)
    assert module.parse_byte_range("bytes=4-7", 16) == (4, 7, True)
    assert module.parse_byte_range("bytes=-4", 16) == (12, 15, True)
    with pytest.raises(ValueError):
        module.parse_byte_range("bytes=0-1,4-5", 16)


@pytest.mark.parametrize("disconnect", [BrokenPipeError, ConnectionResetError])
def test_media_stream_treats_browser_disconnect_as_normal(
    tmp_path: Path, disconnect: type[OSError]
) -> None:
    media = tmp_path / "clip.webm"
    media.write_bytes(b"0123456789abcdef")
    clip = module.MediaClip(
        clip_id="fixture-clip",
        route="/media/football/fixture-clip",
        path=media,
        index_time_origin_s=0.0,
        source_window_start_s=0.0,
        duration_s=1.0,
        source_id="fixture-source",
        sha256=_sha(media),
    )

    class DisconnectingWriter:
        def write(self, _data: bytes) -> None:
            raise disconnect("browser aborted range fetch")

    handler = object.__new__(module.MultiSportHandler)
    handler.headers = {"Range": "bytes=0-15"}
    handler.wfile = DisconnectingWriter()
    handler.send_response = lambda *_args, **_kwargs: None
    handler.send_header = lambda *_args, **_kwargs: None
    handler.end_headers = lambda: None

    handler._serve_media(clip)


def test_http_api_exposes_sports_search_and_exact_range_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _football_package(tmp_path)
    football = module.load_football_context(package, project_root=tmp_path)
    soccer = module.SportContext.unavailable(
        "soccer", endpoint=module.DEFAULT_ENDPOINT, model=module.DEFAULT_MODEL, reason="fixture unavailable"
    )
    context = module.MultiSportContext(sports={"soccer": soccer, "football": football}, ui_root=tmp_path)
    monkeypatch.setattr(module.soccer_server, "_model_health", lambda *_args, **_kwargs: {"online": False})

    plan = module.validate_query_plan(_raw_plan("football"), module.SPORT_SPECS["football"])
    monkeypatch.setattr(
        module,
        "interpret_coach_query",
        lambda *_args, **_kwargs: {
            "plan": plan,
            "source": "fixture",
            "requested_model": "fixture",
            "reported_model": "fixture",
            "endpoint": module.DEFAULT_ENDPOINT,
            "latency_ms": 0,
            "raw_interpretation": None,
            "error": None,
        },
    )
    server = module.build_server(context, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sports = json.loads(urlopen(base + "/api/sports", timeout=3).read().decode("utf-8"))
        assert [item["key"] for item in sports["sports"]] == ["soccer", "football"]
        assert not sports["sports"][0]["available"] and sports["sports"][1]["available"]

        status = json.loads(urlopen(base + "/api/status?sport=football", timeout=3).read().decode("utf-8"))
        assert status["actual_trained_parameters"] is True
        assert status["learned_target"] == "is_touchdown"
        assert status["audit"] == []

        search_request = Request(
            base + "/api/search",
            data=json.dumps({"sport": "football", "query": "find touchdown passes"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        search = json.loads(urlopen(search_request, timeout=3).read().decode("utf-8"))
        assert search["result_count"] == 1
        assert search["results"][0]["clip_url"] == "/media/football/fixture-touchdown"

        media_request = Request(base + "/media/football/fixture-touchdown", headers={"Range": "bytes=-4"})
        with urlopen(media_request, timeout=3) as response:
            assert response.status == 206
            assert response.headers["content-range"] == "bytes 12-15/16"
            assert response.read() == b"cdef"

        with pytest.raises(HTTPError) as blocked:
            urlopen(base + "/media/football/%2e%2e/not-allowlisted.webm", timeout=3)
        assert blocked.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_remote_bind_is_rejected(tmp_path: Path) -> None:
    context = module.MultiSportContext(
        sports={
            key: module.SportContext.unavailable(
                key, endpoint=module.DEFAULT_ENDPOINT, model=module.DEFAULT_MODEL, reason="fixture"
            )
            for key in module.SPORT_SPECS
        },
        ui_root=tmp_path,
    )
    with pytest.raises(ValueError, match="loopback"):
        module.build_server(context, host="0.0.0.0", port=0)
