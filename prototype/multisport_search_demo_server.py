"""Loopback-only dual-sport search over sealed soccer and FootballMaster indexes.

The query LLM is only a language-to-retrieval-plan translator.  It receives the
coach query and the selected sport's public ontology; it never receives video,
audio, source labels, held-out annotations, model predictions, or audit results.
Validated deterministic code ranks already-saved reports afterward.

Soccer retains the original private, receipt-sealed VLM index and its visibly
separate post-hoc SoccerNet audit. American football prefers the independently
sealed FootballMaster long-form package: silent-frame VLM reports over two
held-out games at 30/60/120 seconds. A legacy tiny pilot remains an explicitly
labeled fallback only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sqlite3
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import query_capabilities as query_caps
import search_demo_server as soccer_server
import soccer_longform_adapter as soccer_adapter
import football_longform_adapter as football_adapter


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = Path(__file__).resolve().parent / "search_demo_ui"
DEFAULT_SOCCER_INDEX_ROOT = soccer_server.DEFAULT_INDEX_ROOT
DEFAULT_SOCCER_LONGFORM_ARTIFACT_ROOT = ROOT / "artifacts" / "soccermaster-longform-v1"
DEFAULT_SOCCER_LONGFORM_PRIVATE_ROOT = ROOT / "data" / "private" / "soccermaster-longform-v1"
DEFAULT_ENDPOINT = soccer_server.DEFAULT_ENDPOINT
DEFAULT_MODEL = soccer_server.DEFAULT_MODEL
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8771
QUERY_PLAN_SCHEMA_VERSION = "playground-multisport-coach-query-plan-v1"

FOOTBALL_EVENT_TYPES = (
    "touchdown_pass",
    "rushing_touchdown",
    "kickoff_return",
    "field_goal_attempt",
    "interception_practice",
    *tuple(item for item in football_adapter.EVENT_TYPES if item not in {
        "touchdown_pass", "rushing_touchdown", "kickoff_return", "field_goal_attempt", "interception_practice"
    }),
)
FOOTBALL_PHASES = (
    "pre_snap",
    "dropback",
    "pass_play",
    "run_play",
    "special_teams",
    "turnover",
    "dead_ball",
    "unknown",
)
FOOTBALL_FIELD_AREAS = (
    "own_end_zone",
    "own_red_zone",
    "own_territory",
    "midfield",
    "opponent_territory",
    "opponent_red_zone",
    "opponent_end_zone",
    "sideline",
    "unknown",
)


@dataclass(frozen=True)
class SportSpec:
    key: str
    name: str
    query_noun: str
    event_types: tuple[str, ...]
    phases: tuple[str, ...]
    field_areas: tuple[str, ...]


SPORT_SPECS: Mapping[str, SportSpec] = {
    "soccer": SportSpec(
        key="soccer",
        name="Soccer",
        query_noun="soccer",
        event_types=tuple(soccer_adapter.EVENT_TYPES),
        phases=tuple(soccer_adapter.PHASES),
        field_areas=tuple(soccer_adapter.FIELD_AREAS),
    ),
    "football": SportSpec(
        key="football",
        name="American football",
        query_noun="American football",
        event_types=FOOTBALL_EVENT_TYPES,
        phases=FOOTBALL_PHASES,
        field_areas=FOOTBALL_FIELD_AREAS,
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_project_path(project_root: Path, relative: str, allowed_root: Path) -> Path:
    """Resolve one manifest path and prove it remains under the exact media root."""
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("media_path must be non-empty project-relative text")
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("football media paths must be project-relative")
    resolved = (project_root / raw).resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise ValueError("football media path escaped the allowlisted public media root") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _clock(seconds: float) -> str:
    return soccer_server._clock(seconds)


@dataclass(frozen=True)
class MediaClip:
    clip_id: str
    route: str
    path: Path
    index_time_origin_s: float
    source_window_start_s: float
    duration_s: float
    source_id: str
    sha256: str
    license_spdxish: str | None = None
    source_page_url: str | None = None


@dataclass(frozen=True)
class SportContext:
    sport: str
    spec: SportSpec
    available: bool
    endpoint: str
    model: str
    demo_status: str
    warning: str
    unavailable_reason: str | None = None
    index_root: Path | None = None
    database: Path | None = None
    receipt: Mapping[str, Any] = field(default_factory=dict)
    index_plan: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    model_card: Mapping[str, Any] = field(default_factory=dict)
    media_by_window: Mapping[str, MediaClip] = field(default_factory=dict)
    media_routes: Mapping[str, MediaClip] = field(default_factory=dict)
    audit: tuple[Mapping[str, Any], ...] = ()
    discovery_errors: tuple[str, ...] = ()
    backend: str = "legacy_sqlite"
    soccer_longform: soccer_adapter.SoccerContext | None = None
    football_longform: football_adapter.FootballContext | None = None

    @classmethod
    def unavailable(
        cls,
        sport: str,
        *,
        endpoint: str,
        model: str,
        reason: str,
        errors: Iterable[str] = (),
    ) -> "SportContext":
        spec = SPORT_SPECS[sport]
        return cls(
            sport=sport,
            spec=spec,
            available=False,
            endpoint=endpoint,
            model=model,
            demo_status="UNAVAILABLE",
            warning=reason,
            unavailable_reason=reason,
            discovery_errors=tuple(errors),
        )


@dataclass(frozen=True)
class MultiSportContext:
    sports: Mapping[str, SportContext]
    ui_root: Path = UI_ROOT
    query_llm_enabled: bool = True


def query_plan_response_format(spec: SportSpec) -> dict[str, Any]:
    """Strict plan schema whose ontology is selected before any LLM request."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{spec.key}_coach_search_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "intent_summary",
                    "event_types",
                    "search_terms",
                    "participant_terms",
                    "phases",
                    "field_areas",
                    "explanation",
                ],
                "properties": {
                    "intent_summary": {"type": "string", "minLength": 1},
                    "event_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(spec.event_types)},
                        "maxItems": 6,
                        "uniqueItems": True,
                    },
                    "search_terms": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                        "maxItems": 10,
                        "uniqueItems": True,
                    },
                    "participant_terms": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "maxItems": 6,
                        "uniqueItems": True,
                    },
                    "phases": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(spec.phases)},
                        "maxItems": 4,
                        "uniqueItems": True,
                    },
                    "field_areas": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(spec.field_areas)},
                        "maxItems": 5,
                        "uniqueItems": True,
                    },
                    "explanation": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def query_interpreter_prompt(query: str, spec: SportSpec) -> tuple[str, str]:
    """Build a sport-specific prompt from query plus ontology, and nothing else."""
    system = (
        f"You are a query planner for a private {spec.query_noun} coaching-report search index. "
        "You do not watch or classify video and must not claim that an event exists. "
        "Translate only the coach's words into a compact retrieval plan. Event filters use the supplied ontology. "
        "search_terms should be concrete words or short phrases likely to occur in a detailed saved report. "
        "participant_terms capture role, kit or uniform description, or jersey-number requests. "
        "Empty filter arrays are valid. Deterministic local code performs ranking. Return only strict JSON."
    )
    user = (
        f"Coach query: {query}\n\n"
        f"Selected sport: {spec.name}\n"
        f"Allowed event types: {', '.join(spec.event_types)}\n"
        f"Allowed phases: {', '.join(spec.phases)}\n"
        f"Allowed field areas: {', '.join(spec.field_areas)}\n"
        "Build the retrieval plan without asserting that matching footage is present."
    )
    return system, user


def _unique_strings(
    value: Any,
    field_name: str,
    *,
    allowed: Iterable[str] | None = None,
    max_items: int,
) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"{field_name} must be a list with at most {max_items} items")
    allowed_values = None if allowed is None else {item.casefold() for item in allowed}
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} items must be non-empty strings")
        normalized = item.strip().casefold()
        if allowed_values is not None and normalized not in allowed_values:
            raise ValueError(f"{field_name} contains a value outside the {field_name} ontology")
        if normalized not in result:
            result.append(normalized)
    return result


def validate_query_plan(raw: Any, spec: SportSpec, *, query: str | None = None) -> dict[str, Any]:
    expected = {
        "intent_summary",
        "event_types",
        "search_terms",
        "participant_terms",
        "phases",
        "field_areas",
        "explanation",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("query plan keys do not match the strict contract")
    for field_name in ("intent_summary", "explanation"):
        if not isinstance(raw[field_name], str) or not raw[field_name].strip():
            raise ValueError(f"{field_name} must be non-empty text")
    plan = {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "sport": spec.key,
        "intent_summary": raw["intent_summary"].strip(),
        "event_types": _unique_strings(
            raw["event_types"], "event_types", allowed=spec.event_types, max_items=6
        ),
        "search_terms": _unique_strings(raw["search_terms"], "search_terms", max_items=10),
        "participant_terms": _unique_strings(raw["participant_terms"], "participant_terms", max_items=6),
        "phases": _unique_strings(raw["phases"], "phases", allowed=spec.phases, max_items=4),
        "field_areas": _unique_strings(
            raw["field_areas"], "field_areas", allowed=spec.field_areas, max_items=5
        ),
        "explanation": raw["explanation"].strip(),
    }
    if not plan["search_terms"]:
        raise ValueError("search_terms must contain at least one term")
    if query is not None:
        query_caps.check_query(query, spec.key)
        query_caps.validate_participant_terms(query, [*plan["search_terms"], *plan["participant_terms"]], spec.key)
    return plan


_FALLBACK_STOPWORDS = {
    "a",
    "an",
    "and",
    "around",
    "can",
    "clip",
    "clips",
    "find",
    "for",
    "from",
    "in",
    "involving",
    "later",
    "me",
    "of",
    "please",
    "show",
    "that",
    "the",
    "to",
    "video",
    "with",
}


def fallback_query_plan(query: str, error: str, spec: SportSpec) -> dict[str, Any]:
    query_caps.check_query(query, spec.key)
    tokens = [token for token in re.findall(r"[\w#]+", query.casefold()) if token not in _FALLBACK_STOPWORDS]
    terms = list(dict.fromkeys(tokens))[:10] or [spec.query_noun.casefold()]
    return {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "sport": spec.key,
        "intent_summary": "Literal local keyword search because the query LLM was unavailable or invalid.",
        "event_types": [],
        "search_terms": terms,
        "participant_terms": [],
        "phases": [],
        "field_areas": [],
        "explanation": f"Fallback preserved literal query terms only. Query-LLM error: {error}",
    }


def interpret_coach_query(
    query: str,
    *,
    spec: SportSpec,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 25,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1–500 characters")
    query_caps.check_query(query, spec.key)
    soccer_server.ensure_loopback_endpoint(endpoint)
    system, user = query_interpreter_prompt(query.strip(), spec)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": query_plan_response_format(spec),
        "temperature": 0,
        "max_tokens": 900,
    }
    started = time.perf_counter()
    raw_content: str | None = None
    try:
        request = Request(
            endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with soccer_server._loopback_urlopen(request, timeout=timeout_s) as response:
            response_json = json.loads(response.read().decode("utf-8"))
        raw_content = response_json.get("choices", [{}])[0].get("message", {}).get("content")
        plan = validate_query_plan(soccer_server.parse_json_content(raw_content), spec, query=query)
        reported_model = response_json.get("model") or model
        source = "local_query_llm"
        error = None
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        error = f"{type(exc).__name__}: {exc}"
        plan = fallback_query_plan(query, error, spec)
        reported_model = model
        source = "deterministic_literal_fallback"
    return {
        "plan": plan,
        "source": source,
        "requested_model": model,
        "reported_model": reported_model,
        "endpoint": endpoint,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "raw_interpretation": raw_content,
        "error": error,
    }


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def rank_saved_events(context: SportContext, plan: Mapping[str, Any], *, limit: int = 12) -> list[dict[str, Any]]:
    """Rank saved text only; this function performs no video or event inference."""
    if not context.available or context.database is None:
        raise RuntimeError(context.unavailable_reason or f"{context.sport} is unavailable")
    if plan.get("sport") != context.sport:
        raise ValueError("retrieval plan sport does not match the selected index")
    connection = sqlite3.connect(context.database)
    connection.row_factory = sqlite3.Row
    try:
        window_columns = _table_columns(connection, "windows")
        if not {"window_id", "match_id", "status"}.issubset(window_columns):
            raise RuntimeError("search index windows table is missing required common keys")
        optional = {
            "clip_id": "w.clip_id" if "clip_id" in window_columns else "NULL",
            "source_id": "w.source_id" if "source_id" in window_columns else "NULL",
            "split": "w.split" if "split" in window_columns else "NULL",
        }
        rows = connection.execute(
            "SELECT e.event_id,e.window_id,e.start_s,e.end_s,e.confidence,e.report_json,w.match_id,"
            f"{optional['clip_id']} AS clip_id,{optional['source_id']} AS source_id,"
            f"{optional['split']} AS split "
            "FROM events e JOIN windows w ON w.window_id=e.window_id WHERE w.status='complete'"
        ).fetchall()
    finally:
        connection.close()
    ranked: list[dict[str, Any]] = []
    for row in rows:
        event = json.loads(row["report_json"])
        # Source and clip identifiers are explicit index metadata, not visual
        # predictions. Including their readable tokens lets a coach narrow a
        # tiny research index by team/game wording without changing event
        # semantics or exposing labels to the query LLM.
        text = " ".join(
            (
                soccer_server._flatten_event(event),
                str(row["source_id"] or "").replace("-", " "),
                str(row["clip_id"] or "").replace("-", " "),
            )
        )
        matched: list[dict[str, Any]] = []
        score = 0.0
        normalized_event_types = {str(value).casefold() for value in event.get("event_types", [])}
        for event_type in plan["event_types"]:
            if event_type in normalized_event_types:
                score += 6.0
                matched.append({"kind": "event_type", "value": event_type, "weight": 6.0})
        for term in plan["search_terms"]:
            if soccer_server._contains_phrase(text, term):
                score += 1.5
                matched.append({"kind": "search_term", "value": term, "weight": 1.5})
        participant_text = soccer_server._flatten_event({"participants": event.get("participants", [])})
        for term in plan["participant_terms"]:
            if soccer_server._contains_phrase(participant_text, term):
                score += 2.5
                matched.append({"kind": "participant", "value": term, "weight": 2.5})
        if str(event.get("phase_of_play", "")).casefold() in plan["phases"]:
            score += 3.0
            matched.append({"kind": "phase", "value": event["phase_of_play"], "weight": 3.0})
        normalized_areas = {str(value).casefold() for value in event.get("field_areas", [])}
        for area in plan["field_areas"]:
            if area in normalized_areas:
                score += 3.0
                matched.append({"kind": "field_area", "value": area, "weight": 3.0})
        if score <= 0:
            continue
        ranked.append(
            {
                "event_id": row["event_id"],
                "window_id": row["window_id"],
                "match_id": row["match_id"],
                "clip_id": row["clip_id"],
                "source_id": row["source_id"],
                "split": row["split"],
                "start_s": float(row["start_s"]),
                "end_s": float(row["end_s"]),
                "confidence": float(row["confidence"]),
                "score": score,
                "matched_on": matched,
                "report": event,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], -item["confidence"], item["start_s"], item["event_id"]))
    return ranked[:limit]


def _event_attribution(event: Mapping[str, Any], sport: str) -> dict[str, Any]:
    deterministic = ["query_plan_validation", "saved_text_matching", "ranking", "relative_time_projection"]
    if sport == "soccer":
        vlm_fields = sorted(key for key in event if key not in {"event_id"})
        return {
            "report_origin": event.get("report_origin", "saved_local_vlm_report"),
            "learned_probe_fields": [],
            "source_metadata_fields": [],
            "deterministic_fields": deterministic,
            "optional_vlm_fields": vlm_fields,
            "boundary": "Soccer event semantics come from the saved VLM report; ranking and time projection are deterministic.",
        }
    origin = event.get("report_origin")
    if origin == "deterministic_projection_of_source_metadata_and_learned_binary_prediction":
        deterministic.append("metadata_report_projection")
    return {
        "report_origin": origin,
        "learned_probe_fields": list(event.get("learned_fields", [])),
        "source_metadata_fields": list(event.get("source_metadata_fields", [])),
        "deterministic_fields": deterministic,
        "optional_vlm_fields": list(event.get("vlm_generated_fields", [])),
        "boundary": "The pilot learns only its declared probe fields; fine tags are source metadata and the report prose is deterministic.",
    }


def _result_payload(result: Mapping[str, Any], context: SportContext) -> dict[str, Any]:
    clip = context.media_by_window.get(str(result["window_id"]))
    if clip is None:
        raise RuntimeError("saved result has no allowlisted media binding")
    relative_start = max(0.0, float(result["start_s"]) - clip.index_time_origin_s)
    relative_end = max(relative_start, float(result["end_s"]) - clip.index_time_origin_s)
    relative_start = round(min(clip.duration_s, relative_start), 3)
    relative_end = round(min(clip.duration_s, relative_end), 3)
    event = result["report"]

    evidence_frames: list[dict[str, Any]] = []
    for frame in event.get("evidence_frames", []):
        if not isinstance(frame, dict) or not isinstance(frame.get("timestamp_s"), (int, float)):
            continue
        relative = round(float(frame["timestamp_s"]) - clip.index_time_origin_s, 3)
        evidence_frames.append({**frame, "clock": _clock(float(frame["timestamp_s"])), "relative_s": relative})

    return {
        **result,
        "clip_id": clip.clip_id,
        "clip_url": clip.route,
        "relative_start_s": relative_start,
        "relative_end_s": relative_end,
        "source_start_s": round(clip.source_window_start_s + relative_start, 3),
        "source_end_s": round(clip.source_window_start_s + relative_end, 3),
        "match_clock": f"{_clock(float(result['start_s']))}–{_clock(float(result['end_s']))}",
        "event_types": event.get("event_types", []),
        "primary_action": event.get("primary_action"),
        "participants": event.get("participants", []),
        "evidence_frames": evidence_frames,
        "phase_of_play": event.get("phase_of_play"),
        "field_areas": event.get("field_areas", []),
        "outcome": event.get("outcome"),
        "detailed_description": event.get("detailed_description"),
        "coaching_relevance": event.get("coaching_relevance"),
        "coaching_tags": event.get("coaching_tags", []),
        "uncertainty": event.get("uncertainty"),
        "attribution": _event_attribution(event, context.sport),
    }


def _database_counts(database: Path) -> tuple[int, int]:
    connection = sqlite3.connect(database)
    try:
        event_count = int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        window_count = int(connection.execute("SELECT COUNT(*) FROM windows WHERE status='complete'").fetchone()[0])
    finally:
        connection.close()
    return event_count, window_count


def load_soccer_context(
    index_root: Path = DEFAULT_SOCCER_INDEX_ROOT,
    *,
    project_root: Path = ROOT,
    longform_artifact_root: Path | None = None,
    longform_private_root: Path | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
) -> SportContext:
    """Prefer the verified full-game package; retain legacy as explicit fallback."""
    project_root = project_root.resolve()
    artifact_root = (
        longform_artifact_root.resolve()
        if longform_artifact_root is not None
        else project_root / "artifacts" / "soccermaster-longform-v1"
    )
    private_root = (
        longform_private_root.resolve()
        if longform_private_root is not None
        else project_root / "data" / "private" / "soccermaster-longform-v1"
    )
    errors: list[str] = []
    try:
        standalone = soccer_adapter.load_context(
            artifact_root,
            private_root=private_root,
            project_root=project_root,
            endpoint=endpoint,
            model=model,
        )
        media_routes = {
            route: MediaClip(
                clip_id=binding.asset_id,
                route=route,
                path=binding.path,
                index_time_origin_s=0.0,
                source_window_start_s=0.0,
                duration_s=binding.duration_seconds,
                source_id=binding.asset_id,
                sha256=binding.sha256,
            )
            for route, binding in standalone.media_routes.items()
        }
        media_by_half = {clip.clip_id: clip for clip in media_routes.values()}
        media_by_window = {
            window_id: media_by_half[binding.asset_id]
            for window_id, binding in standalone.media_by_window.items()
        }
        evaluation = standalone.evaluation
        spot = standalone.spot_check.get("judgment_counts", {})
        warning = (
            "Verified complete-match retrieval index; semantic status NO-GO. "
            f"Only {evaluation.get('temporally_corroborated_annotation_count', 0)}/"
            f"{evaluation.get('mapped_visible_annotation_denominator', 0)} mapped held-out annotations and "
            f"{evaluation.get('temporally_corroborated_prediction_count', 0)}/"
            f"{evaluation.get('mapped_vlm_prediction_denominator', 0)} mapped VLM predictions were temporally/type "
            "corroborated under a non-one-to-one ±6-second evaluator. "
            f"Direct review found {spot.get('supported', 0)}/6 reports fully supported; "
            f"{spot.get('partially_supported', 0)} partial and {spot.get('unsupported', 0)} unsupported. "
            "Detailed prose is unscored, and a sampled frame retained a readable team-name lower third. "
            "Treat every result as an untrusted review candidate."
        )
        return SportContext(
            sport="soccer",
            spec=SPORT_SPECS["soccer"],
            available=True,
            endpoint=endpoint,
            model=model,
            demo_status="FULL-GAME VLM INDEX / SEMANTIC NO-GO",
            warning=warning,
            index_root=artifact_root,
            receipt=standalone.verification,
            metrics=standalone.metrics,
            model_card={
                "architecture_scope": "soccer_only",
                "evaluated_target": "silent_frame_detailed_event_report",
                "actual_trained_parameters": False,
            },
            media_by_window=media_by_window,
            media_routes=media_routes,
            audit=(),
            discovery_errors=(),
            backend="soccermaster_longform_v1",
            soccer_longform=standalone,
        )
    except Exception as exc:
        errors.append(f"soccermaster-longform-v1: {type(exc).__name__}: {exc}")
    try:
        sealed = soccer_server.load_demo_context(index_root, endpoint=endpoint, model=model)
        connection = sqlite3.connect(sealed.database)
        try:
            window_ids = [str(row[0]) for row in connection.execute(
                "SELECT window_id FROM windows WHERE status='complete' ORDER BY start_s"
            ).fetchall()]
        finally:
            connection.close()
        clip = MediaClip(
            clip_id="sealed-soccernet-review",
            route="/media/soccer/review.mp4",
            path=sealed.review_clip.resolve(),
            index_time_origin_s=sealed.window_start_s,
            source_window_start_s=sealed.window_start_s,
            duration_s=sealed.window_end_s - sealed.window_start_s,
            source_id=str(sealed.index_plan["configuration"]["match_id"]),
            sha256=_sha256(sealed.review_clip),
        )
        legacy = SportContext(
            sport="soccer",
            spec=SPORT_SPECS["soccer"],
            available=True,
            endpoint=endpoint,
            model=model,
            demo_status=soccer_server.DEMO_STATUS,
            warning=(
                "LEGACY FALLBACK — the verified full-game SoccerMaster package failed discovery or verification. "
                + soccer_server.AUDIT_WARNING
            ),
            index_root=sealed.index_root,
            database=sealed.database,
            receipt=sealed.receipt,
            index_plan=sealed.index_plan,
            media_by_window={window_id: clip for window_id in window_ids},
            media_routes={clip.route: clip},
            audit=tuple(sealed.audit),
            discovery_errors=tuple(errors),
            backend="legacy_sqlite_fallback",
        )
        return legacy
    except Exception as exc:
        errors.append(f"legacy-soccer-index: {type(exc).__name__}: {exc}")
        return SportContext.unavailable(
            "soccer",
            endpoint=endpoint,
            model=model,
            reason="Soccer index unavailable: verified long-form and explicit legacy fallback both failed.",
            errors=errors,
        )


def discover_football_index_roots(project_root: Path = ROOT) -> list[Path]:
    """Return v2-first candidates; the legacy pilot is fallback-only."""
    project_root = project_root.resolve()
    candidates: set[Path] = set()
    artifact_root = project_root / "artifacts"
    if artifact_root.is_dir():
        for index in artifact_root.rglob("football-search-index.jsonl"):
            lowered = {part.casefold() for part in index.parts}
            if any("staging" in part or "backup" in part for part in lowered):
                continue
            candidates.add(index.parent.resolve())
        for top in artifact_root.glob("footballmaster*"):
            if not top.is_dir():
                continue
            for database in top.rglob("search-index.sqlite3"):
                lowered = {part.casefold() for part in database.parts}
                if any("staging" in part or "backup" in part for part in lowered):
                    continue
                candidates.add(database.parent.resolve())
    public_root = project_root / "data" / "public" / "footballmaster"
    if public_root.is_dir():
        for database in public_root.rglob("search-index.sqlite3"):
            candidates.add(database.parent.resolve())
    return sorted(
        candidates,
        key=lambda path: (
            int((path / "football-search-index.jsonl").is_file()),
            max(
                ((path / name).stat().st_mtime for name in ("verification-receipt.json", "run-receipt.json") if (path / name).is_file()),
                default=0,
            ),
            str(path),
        ),
        reverse=True,
    )


def _load_football_package(
    package_root: Path,
    *,
    project_root: Path,
    endpoint: str,
    model: str,
) -> SportContext:
    package_root = package_root.resolve()
    project_root = project_root.resolve()
    try:
        package_root.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("football package must remain inside the project") from exc
    required = {
        "database": package_root / "search-index.sqlite3",
        "receipt": package_root / "run-receipt.json",
        "plan": package_root / "index-plan.json",
        "metrics": package_root / "metrics.json",
        "model_card": package_root / "model-card.json",
        "checkpoint": package_root / "footballmaster-pilot-v1.npz",
        "model_config": package_root / "model-config.json",
        "predictions": package_root / "predictions.jsonl",
        "training_log": package_root / "training-log.jsonl",
        "feature_receipts": package_root / "feature-receipts.json",
    }
    for name, path in required.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing {name}: {path.name}")
    receipt = json.loads(required["receipt"].read_text(encoding="utf-8"))
    plan = json.loads(required["plan"].read_text(encoding="utf-8"))
    metrics = json.loads(required["metrics"].read_text(encoding="utf-8"))
    model_card = json.loads(required["model_card"].read_text(encoding="utf-8"))
    if receipt.get("status") != "pass" or receipt.get("sport") != "american_football":
        raise RuntimeError("football run receipt is not a passing American-football package")
    if receipt.get("database_sha256") != _sha256(required["database"]):
        raise RuntimeError("football search database does not match its run receipt")
    if receipt.get("index_plan_sha256") != _sha256(required["plan"]):
        raise RuntimeError("football index plan does not match its run receipt")
    if receipt.get("metrics_sha256") != _sha256(required["metrics"]):
        raise RuntimeError("football metrics do not match their run receipt")
    if receipt.get("model_card_sha256") != _sha256(required["model_card"]):
        raise RuntimeError("football model card does not match its run receipt")
    if receipt.get("checkpoint_sha256") != _sha256(required["checkpoint"]):
        raise RuntimeError("football checkpoint does not match its run receipt")
    if receipt.get("model_config_sha256") != _sha256(required["model_config"]):
        raise RuntimeError("football model config does not match its run receipt")
    if receipt.get("predictions_sha256") != _sha256(required["predictions"]):
        raise RuntimeError("football predictions do not match their run receipt")
    if receipt.get("training_log_sha256") != _sha256(required["training_log"]):
        raise RuntimeError("football training log does not match its run receipt")
    if receipt.get("feature_receipts_sha256") != _sha256(required["feature_receipts"]):
        raise RuntimeError("football feature receipts do not match their run receipt")
    if receipt.get("source_held_out_test") is not True or receipt.get("performance_claim_allowed") is not False:
        raise RuntimeError("football run receipt lost its source-holdout or no-performance-claim boundary")
    if metrics.get("performance_claim_allowed") is not False:
        raise RuntimeError("football metrics lost the tiny-pilot claim boundary")
    # New FootballMaster packages declare their own architecture boundary.
    # The legacy key is interpreted only here so existing sealed pilot artifacts
    # remain demo-compatible; it is not part of the standalone package contract.
    architecture_scope = model_card.get("architecture_scope")
    legacy_scope = architecture_scope is None and model_card.get("soccer_master_replication") is False
    if model_card.get("actual_trained_parameters") is not True or (
        architecture_scope != "football_only" and not legacy_scope
    ):
        raise RuntimeError("football model card does not preserve its football-only trained-pilot boundary")
    if plan.get("sport") != "american_football":
        raise RuntimeError("football index plan has the wrong sport")
    semantic = plan.get("semantic_boundary", {})
    if semantic.get("vlm") not in {"none in this index", "none", None}:
        raise RuntimeError("football index unexpectedly attributes its report to a VLM")

    connection = sqlite3.connect(required["database"])
    try:
        window_columns = _table_columns(connection, "windows")
        required_window_columns = {"window_id", "clip_id", "source_id", "split", "media_path", "status"}
        if not required_window_columns.issubset(window_columns):
            raise RuntimeError("football windows table is missing media/source attribution keys")
        database_windows = {
            str(row[0])
            for row in connection.execute("SELECT window_id FROM windows WHERE status='complete'").fetchall()
        }
        metadata_columns = _table_columns(connection, "metadata")
        if metadata_columns:
            sport_row = connection.execute("SELECT value FROM metadata WHERE key='sport'").fetchone()
            if sport_row is not None and sport_row[0] != "american_football":
                raise RuntimeError("football database metadata has the wrong sport")
    finally:
        connection.close()

    source_manifest_path = project_root / "data" / "public" / "footballmaster" / "source-manifest.json"
    source_manifest: dict[str, Mapping[str, Any]] = {}
    if not source_manifest_path.is_file():
        raise FileNotFoundError("football source manifest is missing")
    if receipt.get("source_manifest_sha256") != _sha256(source_manifest_path):
        raise RuntimeError("football source manifest does not match its run receipt")
    source_data = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    # The canonical rights manifest calls these records ``assets``.  The
    # ``sources`` fallback keeps the loader compatible with early fixtures,
    # but never relaxes any package or media hash gate.
    manifest_items = source_data.get("assets", source_data.get("sources", []))
    for item in manifest_items:
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str):
            source_manifest[item["asset_id"]] = item

    allowed_media_root = project_root / "data" / "public" / "footballmaster" / "media"
    media_by_window: dict[str, MediaClip] = {}
    media_routes: dict[str, MediaClip] = {}
    plan_window_ids: set[str] = set()
    for item in plan.get("windows", []):
        if not isinstance(item, dict):
            raise RuntimeError("football index plan windows must be objects")
        window_id = str(item.get("window_id", ""))
        clip_id = str(item.get("clip_id", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,119}", clip_id):
            raise RuntimeError("football clip_id is not a safe opaque identifier")
        if not window_id or window_id in plan_window_ids:
            raise RuntimeError("football index plan window identifiers are missing or duplicated")
        plan_window_ids.add(window_id)
        local_window = item.get("local_window_s")
        source_window = item.get("source_window_s")
        if (
            not isinstance(local_window, list)
            or len(local_window) != 2
            or not all(isinstance(value, (int, float)) for value in local_window)
            or float(local_window[1]) <= float(local_window[0])
        ):
            raise RuntimeError("football local window is invalid")
        if (
            not isinstance(source_window, list)
            or len(source_window) != 2
            or not all(isinstance(value, (int, float)) for value in source_window)
        ):
            raise RuntimeError("football source window is invalid")
        media_path = _safe_project_path(project_root, item.get("media_path"), allowed_media_root)
        expected_hash = str(item.get("media_sha256", ""))
        actual_hash = _sha256(media_path)
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or actual_hash != expected_hash:
            raise RuntimeError(f"football media hash mismatch for {clip_id}")
        source = source_manifest.get(clip_id, {})
        route = f"/media/football/{clip_id}"
        clip = MediaClip(
            clip_id=clip_id,
            route=route,
            path=media_path,
            index_time_origin_s=float(local_window[0]),
            source_window_start_s=float(source_window[0]),
            duration_s=float(local_window[1]) - float(local_window[0]),
            source_id=str(item.get("source_id", "")),
            sha256=actual_hash,
            license_spdxish=source.get("license_spdxish") if isinstance(source, dict) else None,
            source_page_url=source.get("canonical_page_url") if isinstance(source, dict) else None,
        )
        if route in media_routes:
            raise RuntimeError("football media route collision")
        media_by_window[window_id] = clip
        media_routes[route] = clip
    if plan_window_ids != database_windows:
        raise RuntimeError("football index-plan windows do not exactly match complete database windows")
    if not media_by_window:
        raise RuntimeError("football package contains no playable indexed windows")

    warning = str(
        metrics.get("claim_boundary")
        or "Tiny source-held-out pilot only; human review is required and no coaching-performance claim is allowed."
    )
    return SportContext(
        sport="football",
        spec=SPORT_SPECS["football"],
        available=True,
        endpoint=endpoint,
        model=model,
        demo_status="TRAINED PILOT / COACHING CLAIMS NO-GO",
        warning=warning,
        index_root=package_root,
        database=required["database"],
        receipt=receipt,
        index_plan=plan,
        metrics=metrics,
        model_card=model_card,
        media_by_window=media_by_window,
        media_routes=media_routes,
        audit=(),
        backend="legacy_sqlite",
    )


def _load_football_longform_package(
    package_root: Path,
    *,
    project_root: Path,
    endpoint: str,
    model: str,
) -> SportContext:
    """Adapt the standalone football engine without routing through soccer code."""
    standalone = football_adapter.load_context(
        package_root,
        project_root=project_root,
        endpoint=endpoint,
        model=model,
    )
    media_routes = {
        route: MediaClip(
            clip_id=binding.asset_id,
            route=route,
            path=binding.path,
            index_time_origin_s=0.0,
            source_window_start_s=0.0,
            duration_s=binding.duration_seconds,
            source_id=binding.asset_id,
            sha256=binding.sha256,
            license_spdxish=binding.license_spdxish,
            source_page_url=binding.source_page_url,
        )
        for route, binding in standalone.media_routes.items()
    }
    media_by_asset = {clip.clip_id: clip for clip in media_routes.values()}
    media_by_window = {
        window_id: media_by_asset[binding.asset_id]
        for window_id, binding in standalone.media_by_window.items()
    }
    semantic = standalone.metrics.get("test_semantic_contract", {})
    test_coverage = standalone.coverage.get("by_split", {}).get("test", {})
    warning = (
        f"Primary semantic status {semantic.get('status', 'UNKNOWN')}: "
        f"{semantic.get('abstain_with_nonempty_events_count', 0)}/{semantic.get('denominator', 0)} "
        "reports contradict abstention. "
        f"This sparse index covers {test_coverage.get('unique_sampled_seconds', 0):,.0f} unique test seconds "
        f"({test_coverage.get('nominal_window_seconds', 0):,.0f} nominal overlapping test-window seconds) "
        f"from held-out source programs totaling {standalone.coverage.get('test_source_program_seconds', 0):,.4f} seconds; "
        f"the verified corpus source pool contains {standalone.coverage.get('corpus_duration_seconds', 0):,.4f} seconds. "
        "Treat every result as an untrusted review candidate."
    )
    return SportContext(
        sport="football",
        spec=SPORT_SPECS["football"],
        available=True,
        endpoint=endpoint,
        model=model,
        demo_status="LONG-FORM VLM / SEMANTIC NO-GO",
        warning=warning,
        index_root=standalone.output_root,
        receipt=standalone.verification,
        metrics=standalone.metrics,
        model_card={
            "architecture_scope": "football_only",
            "evaluated_target": "silent_frame_detailed_event_report",
            "actual_trained_parameters": False,
        },
        media_by_window=media_by_window,
        media_routes=media_routes,
        backend="longform_v2",
        football_longform=standalone,
    )


def load_football_context(
    index_root: Path | None = None,
    *,
    project_root: Path = ROOT,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
) -> SportContext:
    football_adapter.ensure_loopback_endpoint(endpoint)
    candidates = [index_root.resolve()] if index_root is not None else discover_football_index_roots(project_root)
    errors: list[str] = []
    for candidate in candidates:
        try:
            if (candidate / "football-search-index.jsonl").is_file():
                return _load_football_longform_package(
                    candidate,
                    project_root=project_root,
                    endpoint=endpoint,
                    model=model,
                )
            return _load_football_package(
                candidate,
                project_root=project_root,
                endpoint=endpoint,
                model=model,
            )
        except Exception as exc:
            errors.append(f"{candidate.name}: {type(exc).__name__}: {exc}")
    reason = (
        "FootballMaster index unavailable: no verified package (long-form v2 or legacy) was discovered under "
        "artifacts/footballmaster* or data/public/footballmaster."
        if not candidates
        else "FootballMaster index unavailable: every discovered package failed verification."
    )
    return SportContext.unavailable(
        "football",
        endpoint=endpoint,
        model=model,
        reason=reason,
        errors=errors,
    )


def load_multisport_context(
    *,
    soccer_index_root: Path = DEFAULT_SOCCER_INDEX_ROOT,
    soccer_longform_artifact_root: Path | None = None,
    soccer_longform_private_root: Path | None = None,
    football_index_root: Path | None = None,
    project_root: Path = ROOT,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
    ui_root: Path = UI_ROOT,
    query_llm_enabled: bool = True,
) -> MultiSportContext:
    soccer_server.ensure_loopback_endpoint(endpoint)
    return MultiSportContext(
        sports={
            "soccer": load_soccer_context(
                soccer_index_root,
                project_root=project_root,
                longform_artifact_root=soccer_longform_artifact_root,
                longform_private_root=soccer_longform_private_root,
                endpoint=endpoint,
                model=model,
            ),
            "football": load_football_context(
                football_index_root,
                project_root=project_root,
                endpoint=endpoint,
                model=model,
            ),
        },
        ui_root=ui_root,
        query_llm_enabled=query_llm_enabled,
    )


def sport_summary(context: SportContext) -> dict[str, Any]:
    event_count = 0
    window_count = 0
    if context.available and context.soccer_longform is not None:
        window_count = len(context.soccer_longform.entries)
        event_count = sum(
            len(entry.get("report", {}).get("events", []))
            for entry in context.soccer_longform.entries
        )
    elif context.available and context.football_longform is not None:
        window_count = len(context.football_longform.entries)
        event_count = sum(
            len(entry.get("report", {}).get("events", []))
            for entry in context.football_longform.entries
        )
    elif context.available and context.database is not None:
        event_count, window_count = _database_counts(context.database)
    return {
        "key": context.sport,
        "name": context.spec.name,
        "available": context.available,
        "demo_status": context.demo_status,
        "warning": context.warning,
        "unavailable_reason": context.unavailable_reason,
        "event_count": event_count,
        "window_count": window_count,
        "event_types": list(context.spec.event_types),
        "phases": list(context.spec.phases),
        "field_areas": list(context.spec.field_areas),
        "backend": context.backend,
    }


def _query_model_health(context: SportContext, query_llm_enabled: bool) -> dict[str, Any]:
    if not query_llm_enabled:
        return {
            "reachable": False,
            "online": False,
            "skipped": True,
            "reason": "Query LLM intentionally disabled; deterministic literal search is active.",
        }
    return (
        football_adapter.model_health(context.endpoint)
        if context.sport == "football"
        else soccer_adapter.model_health(context.endpoint)
    )


def status_payload(context: SportContext, *, query_llm_enabled: bool = True) -> dict[str, Any]:
    summary = sport_summary(context)
    if not context.available:
        return {
            **summary,
            "discovery_errors": list(context.discovery_errors),
            "query_model": context.model,
            "model_health": _query_model_health(context, query_llm_enabled),
            "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
            "performance_claim_allowed": False,
        }
    if context.soccer_longform is not None:
        standalone = context.soccer_longform
        evaluation = standalone.evaluation
        spot_counts = standalone.spot_check.get("judgment_counts", {})
        return {
            **summary,
            "query_model": context.model,
            "model_health": _query_model_health(context, query_llm_enabled),
            "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
            "performance_claim_allowed": False,
            "source_held_out_test": True,
            "actual_trained_parameters": False,
            "architecture_scope": "soccer_only",
            "learned_target": "none; frozen prompt inference over silent ordered frames",
            "metrics": context.metrics,
            "coverage": standalone.coverage,
            "semantic_contract": {
                "status": "NO-GO",
                "evaluator": "non-one-to-one event-type/temporal corroboration within ±6 seconds",
                "not_action_spotting_map": True,
                "detailed_claim_factuality_measured": False,
                "mapped_annotation_recall": evaluation.get("restricted_mapped_annotation_recall"),
                "mapped_annotation_recall_count": evaluation.get("temporally_corroborated_annotation_count"),
                "mapped_annotation_denominator": evaluation.get("mapped_visible_annotation_denominator"),
                "mapped_prediction_precision": evaluation.get("restricted_mapped_prediction_precision"),
                "mapped_prediction_precision_count": evaluation.get("temporally_corroborated_prediction_count"),
                "mapped_prediction_denominator": evaluation.get("mapped_vlm_prediction_denominator"),
                "spot_check_judgment_counts": spot_counts,
                "input_anonymization_audit_status": standalone.verification.get("checks", {}).get(
                    "input_anonymization_audit_status"
                ),
            },
            "audio_supplied_to_vlm": False,
            "metadata_supplied_to_vlm": False,
            "labels_supplied_to_vlm": False,
            "audit": [],
            "clips": [
                {
                    "clip_id": clip.asset_id,
                    "clip_url": clip.route,
                    "half": clip.half,
                    "duration_s": clip.duration_seconds,
                    "browser_compatible_derivative": clip.browser_compatible_derivative,
                    "rights": "private SoccerNet research access; do not redistribute",
                }
                for clip in standalone.media_routes.values()
            ],
            "attribution_boundary": {
                "vlm": "sealed ordered silent scoreboard-redacted frames; saved event text is untrusted model output",
                "deterministic": "hash verification, optional query expansion validation, BM25 ranking, and time projection",
                "excluded": "audio, commentary, labels, source metadata, filenames, team names, scores, and absolute clock",
                "post_seal_only": "SoccerNet annotations and direct visual spot-check judgments",
                "known_input_limitation": (
                    "A predeclared sampled frame retained readable team-name lower-third pixels outside the fixed mask."
                ),
            },
            "pipeline": [
                "Coach language → optional local query expansion (literal fallback is explicitly labeled)",
                "Deterministic BM25 → 96 sealed visual reports across both complete held-out halves",
                "Playable silent 30/60/120-second source window → human review",
                "Post-seal labels + six direct spot-checks → visible semantic NO-GO gate",
            ],
        }
    if context.football_longform is not None:
        semantic = context.metrics.get("test_semantic_contract", {})
        probe_path = context.index_root / "weak-visual-probe-receipt.json" if context.index_root else None
        probe = json.loads(probe_path.read_text(encoding="utf-8")) if probe_path and probe_path.is_file() else {}
        return {
            **summary,
            "query_model": context.model,
            "model_health": _query_model_health(context, query_llm_enabled),
            "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
            "performance_claim_allowed": False,
            "source_held_out_test": True,
            "actual_trained_parameters": bool(probe.get("fitted_parameter_count")),
            "architecture_scope": "football_only",
            "learned_target": "weak visual-probe agreement with unverified development pseudo-labels",
            "metrics": context.metrics,
            "semantic_contract": semantic,
            "weak_probe": probe,
            "coverage": context.football_longform.coverage,
            "audio_supplied_to_vlm": False,
            "metadata_supplied_to_vlm": False,
            "audit": [],
            "clips": [
                {
                    "clip_id": clip.clip_id,
                    "clip_url": clip.route,
                    "duration_s": clip.duration_s,
                    "source_id": clip.source_id,
                    "license_spdxish": clip.license_spdxish,
                    "source_page_url": clip.source_page_url,
                }
                for clip in context.media_routes.values()
            ],
            "attribution_boundary": {
                "vlm": "sealed silent frames only; event text is untrusted model output",
                "deterministic": "hash verification, BM25 ranking, and time projection",
                "excluded": "audio, commentary, source titles, rosters, and labels",
                "weak_probe": "secondary fitted baseline; not used for primary reports or retrieval",
            },
            "pipeline": [
                "Coach language → football-owned local query expansion",
                "Deterministic BM25 → 36 sealed sampled reports covering 1,440 unique test seconds",
                "Playable 30/60/120-second source window → human review",
                "Semantic failure counters remain visible; no coaching claim",
            ],
        }
    if context.database is None:
        return {
            **summary,
            "discovery_errors": list(context.discovery_errors),
            "query_model": context.model,
            "model_health": _query_model_health(context, query_llm_enabled),
            "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
            "performance_claim_allowed": False,
        }
    event_count, window_count = _database_counts(context.database)
    if context.sport == "soccer":
        configuration = context.index_plan.get("configuration", {})
        clips = list(context.media_routes.values())
        return {
            **summary,
            "query_model": context.model,
            "model_health": _query_model_health(context, query_llm_enabled),
            "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
            "event_count": event_count,
            "window_count": window_count,
            "window_duration_s": clips[0].duration_s if clips else None,
            "match_id": configuration.get("match_id"),
            "source_reference": configuration.get("source_reference"),
            "audio_supplied_to_vlm": False,
            "review_clip_audio": False,
            "performance_claim_allowed": False,
            "audit": list(context.audit),
            "attribution_boundary": {
                "learned_probe": "none",
                "deterministic": "query planning validation, saved-text ranking, and time projection",
                "optional_vlm": "all saved soccer event semantics",
                "held_out": "SoccerNet annotations appear only in this post-hoc audit response",
            },
            "pipeline": [
                "Coach language → local query LLM → strict soccer retrieval plan",
                "Validated plan → deterministic ranking over saved VLM reports",
                "Playable clip + evidence timestamps → human review",
                "Held-out SoccerNet annotations → separate post-hoc audit only",
            ],
        }
    return {
        **summary,
        "query_model": context.model,
        "model_health": _query_model_health(context, query_llm_enabled),
        "query_mode": "local_query_llm" if query_llm_enabled else "deterministic_literal_fallback",
        "event_count": event_count,
        "window_count": window_count,
        "performance_claim_allowed": False,
        "source_held_out_test": context.receipt.get("source_held_out_test") is True,
        "actual_trained_parameters": context.model_card.get("actual_trained_parameters") is True,
        "architecture_scope": context.model_card.get("architecture_scope", "football_only_legacy_adapter"),
        "learned_target": context.model_card.get("evaluated_target"),
        "metrics": context.metrics,
        "audit": [],
        "clips": [
            {
                "clip_id": clip.clip_id,
                "clip_url": clip.route,
                "duration_s": clip.duration_s,
                "source_id": clip.source_id,
                "license_spdxish": clip.license_spdxish,
                "source_page_url": clip.source_page_url,
            }
            for clip in context.media_routes.values()
        ],
        "attribution_boundary": context.index_plan.get("semantic_boundary", {}),
        "pipeline": [
            "Coach language → local query LLM → strict American-football retrieval plan",
            "Validated plan → deterministic ranking over saved package reports",
            "Fine event tag → source-description metadata (not a learned prediction)",
            "Touchdown/not-touchdown probability → learned pilot probe",
            "Detailed report prose → deterministic projection; no VLM attached",
            "Playable rights-audited clip → human review",
        ],
    }


def search_soccer_longform(
    context: SportContext,
    query: str,
    *,
    use_query_llm: bool = True,
) -> dict[str, Any]:
    """Search the verified soccer-owned full-game index and adapt its UI shape."""
    if context.soccer_longform is None:
        raise ValueError("soccer long-form backend is not loaded")
    searched = soccer_adapter.search_context(
        context.soccer_longform,
        query,
        limit=12,
        use_query_llm=use_query_llm,
    )
    compact = searched["interpretation"]
    plan = {
        "sport": "soccer",
        "intent_summary": query.strip(),
        "event_types": list(compact.get("event_types", [])),
        "search_terms": list(compact.get("search_terms", [])),
        "participant_terms": [],
        "phases": [],
        "field_areas": [],
        "explanation": (
            "The local query model expands only the coach's words; deterministic BM25 ranks sealed, untrusted "
            "silent-frame VLM reports."
            if compact.get("source") == "local_query_llm"
            else "Literal query terms are used directly; deterministic BM25 ranks sealed, untrusted VLM reports."
        ),
    }
    interpretation = {
        "plan": plan,
        "source": compact.get("source"),
        "requested_model": compact.get("requested_model"),
        "reported_model": compact.get("reported_model") or compact.get("requested_model"),
        "endpoint": context.endpoint,
        "latency_ms": compact.get("latency_ms"),
        "raw_interpretation": compact.get("raw_interpretation"),
        "error": compact.get("error"),
    }
    return {
        "sport": "soccer",
        "query": query,
        "interpretation": interpretation,
        "results": searched["results"],
        "result_count": searched["result_count"],
        "demo_status": context.demo_status,
        "warning": context.warning,
        "audit": [],
        "ranking_note": searched["ranking_note"],
    }


def search_football_longform(
    context: SportContext,
    query: str,
    *,
    use_query_llm: bool = True,
) -> dict[str, Any]:
    """Search v2 through the football-owned engine and adapt only its UI shape."""
    if context.football_longform is None:
        raise ValueError("football long-form backend is not loaded")
    searched = football_adapter.search_context(
        context.football_longform,
        query,
        limit=12,
        use_query_llm=use_query_llm,
    )
    compact = searched["interpretation"]
    plan = {
        "sport": "football",
        "intent_summary": query.strip(),
        "event_types": list(compact.get("event_types", [])),
        "search_terms": list(compact.get("search_terms", [])),
        "participant_terms": [],
        "phases": [],
        "field_areas": [],
        "explanation": "Search terms are expanded locally, then BM25 ranks sealed silent-frame reports.",
    }
    interpretation = {
        "plan": plan,
        "source": compact.get("source"),
        "requested_model": compact.get("requested_model"),
        "reported_model": compact.get("requested_model"),
        "endpoint": context.endpoint,
        "latency_ms": compact.get("latency_ms"),
        "raw_interpretation": compact,
        "error": compact.get("error"),
    }
    return {
        "sport": "football",
        "query": query,
        "interpretation": interpretation,
        "results": searched["results"],
        "result_count": searched["result_count"],
        "demo_status": context.demo_status,
        "warning": context.warning,
        "audit": [],
        "ranking_note": searched["ranking_note"],
    }


def parse_byte_range(value: str | None, size: int) -> tuple[int, int, bool]:
    """Parse one RFC 7233 byte range, including suffix ranges."""
    if size <= 0:
        raise ValueError("cannot range an empty file")
    if value is None:
        return 0, size - 1, False
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or (not match.group(1) and not match.group(2)):
        raise ValueError("unsupported byte range")
    if not match.group(1):
        suffix = int(match.group(2))
        if suffix <= 0:
            raise ValueError("invalid suffix byte range")
        return max(0, size - suffix), size - 1, True
    start = int(match.group(1))
    end = size - 1 if not match.group(2) else min(int(match.group(2)), size - 1)
    if start >= size or start > end:
        raise ValueError("byte range is outside the file")
    return start, end, True


class MultiSportHandler(BaseHTTPRequestHandler):
    server_version = "PlayGroundMultiSportDemo/1.0"

    @property
    def context(self) -> MultiSportContext:
        return self.server.multisport_context  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _security_headers(self) -> None:
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("referrer-policy", "no-referrer")
        self.send_header("x-frame-options", "DENY")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("content-length", str(len(data)))
        self.send_header("cache-control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _find_media(self, route: str) -> MediaClip | None:
        for sport in self.context.sports.values():
            clip = sport.media_routes.get(route)
            if clip is not None:
                return clip
        return None

    def _serve_media(self, clip: MediaClip) -> None:
        try:
            start, end, partial = parse_byte_range(self.headers.get("Range"), clip.path.stat().st_size)
        except (OSError, ValueError):
            size = clip.path.stat().st_size if clip.path.is_file() else 0
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("content-range", f"bytes */{size}")
            self.send_header("content-length", "0")
            self._security_headers()
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("content-type", mimetypes.guess_type(clip.path.name)[0] or "application/octet-stream")
        self.send_header("accept-ranges", "bytes")
        self.send_header("content-length", str(length))
        if partial:
            self.send_header("content-range", f"bytes {start}-{end}/{clip.path.stat().st_size}")
        self.send_header("cache-control", "private, no-store")
        self._security_headers()
        self.end_headers()
        try:
            with clip.path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Browsers routinely abort an earlier range fetch when the user
            # switches clips or seeks.  That is a normal client disconnect,
            # not a server failure worth dumping into the live-demo console.
            return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file(self.context.ui_root / "index.html", "text/html; charset=utf-8")
        elif path == "/app.css":
            self._serve_file(self.context.ui_root / "app.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(self.context.ui_root / "app.js", "text/javascript; charset=utf-8")
        elif path == "/api/sports":
            self._send_json({"sports": [sport_summary(self.context.sports[key]) for key in SPORT_SPECS]})
        elif path == "/api/status":
            requested = parse_qs(parsed.query).get("sport", ["soccer"])[0]
            context = self.context.sports.get(requested)
            if context is None:
                self._send_json({"error": "sport must be soccer or football"}, status=400)
            else:
                self._send_json(
                    status_payload(
                        context,
                        query_llm_enabled=self.context.query_llm_enabled,
                    )
                )
        elif path == "/healthz":
            self._send_json(
                {
                    "ok": any(item.available for item in self.context.sports.values()),
                    "sports": {key: item.available for key, item in self.context.sports.items()},
                }
            )
        else:
            clip = self._find_media(path)
            if clip is None:
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._serve_media(clip)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/search":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            if length < 1 or length > 8_192:
                raise ValueError("request body must be 1–8192 bytes")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("request body must be a JSON object")
            sport = body.get("sport")
            if sport not in SPORT_SPECS:
                raise ValueError("sport must be soccer or football")
            context = self.context.sports[sport]
            if not context.available:
                self._send_json(
                    {
                        "error": context.unavailable_reason,
                        "sport": sport,
                        "available": False,
                        "demo_status": context.demo_status,
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            query = body.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 500:
                raise ValueError("query must contain 1–500 characters")
            query_caps.check_query(query, sport)
            if sport == "soccer" and context.soccer_longform is not None:
                self._send_json(
                    search_soccer_longform(
                        context,
                        query,
                        use_query_llm=self.context.query_llm_enabled,
                    )
                )
                return
            if sport == "football" and context.football_longform is not None:
                self._send_json(
                    search_football_longform(
                        context,
                        query,
                        use_query_llm=self.context.query_llm_enabled,
                    )
                )
                return
            interpretation = (
                interpret_coach_query(
                    query,
                    spec=context.spec,
                    endpoint=context.endpoint,
                    model=context.model,
                )
                if self.context.query_llm_enabled
                else {
                    "plan": fallback_query_plan(query, "query LLM disabled for this server session", context.spec),
                    "source": "deterministic_literal_fallback",
                    "requested_model": context.model,
                    "reported_model": context.model,
                    "endpoint": context.endpoint,
                    "latency_ms": 0,
                    "raw_interpretation": None,
                    "error": "query LLM disabled for this server session",
                }
            )
            results = rank_saved_events(context, interpretation["plan"], limit=12)
            self._send_json(
                {
                    "sport": sport,
                    "query": query,
                    "interpretation": interpretation,
                    "results": [_result_payload(result, context) for result in results],
                    "result_count": len(results),
                    "demo_status": context.demo_status,
                    "warning": context.warning,
                    "audit": list(context.audit) if sport == "soccer" else [],
                    "ranking_note": (
                        "Scores are deterministic text matches over saved reports. They do not validate event claims, "
                        "and the query LLM never receives video, audio, labels, predictions, or audit data."
                    ),
                }
            )
        except (query_caps.UnsupportedNegationConstraint, query_caps.UnsupportedTemporalOrderConstraint,
                query_caps.UnsupportedParticipantConstraint) as exc:
            self._send_json({"error": str(exc), "code": exc.code, "error_code": exc.code}, status=422)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)


def build_server(
    context: MultiSportContext,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("multisport search demo must bind to loopback")
    server = ThreadingHTTPServer((host, port), MultiSportHandler)
    server.multisport_context = context  # type: ignore[attr-defined]
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soccer-index-root", type=Path, default=DEFAULT_SOCCER_INDEX_ROOT)
    parser.add_argument("--soccer-longform-artifact-root", type=Path)
    parser.add_argument("--soccer-longform-private-root", type=Path)
    parser.add_argument("--football-index-root", type=Path)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument(
        "--literal-query-fallback",
        action="store_true",
        help="Skip query-model calls and visibly use deterministic literal BM25 terms.",
    )
    args = parser.parse_args()
    context = load_multisport_context(
        soccer_index_root=args.soccer_index_root,
        soccer_longform_artifact_root=args.soccer_longform_artifact_root,
        soccer_longform_private_root=args.soccer_longform_private_root,
        football_index_root=args.football_index_root,
        endpoint=args.endpoint,
        model=args.model,
        query_llm_enabled=not args.literal_query_fallback,
    )
    server = build_server(context, args.host, args.port)
    url = f"http://{args.host}:{server.server_address[1]}/"
    print(f"PlayGround dual-sport coach-search demo: {url}")
    for key, item in context.sports.items():
        print(f"{item.spec.name}: {item.demo_status} ({'available' if item.available else item.unavailable_reason})")
    print("All footage remains on this machine. Press Ctrl+C to stop.")
    if args.open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
