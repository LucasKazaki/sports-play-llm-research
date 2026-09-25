"""Loopback-only browser demo for LLM-planned search over saved VLM reports.

The query LLM translates a coach's natural-language request into a transparent,
strict search plan.  Deterministic code validates that plan and ranks already
saved VLM event reports.  It never infers a soccer event from pixels.  Held-out
SoccerNet annotations are loaded only for the visibly separate post-hoc audit
panel and are never sent to the query LLM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from real_clip_vlm import parse_json_content
from searchable_match_vlm import EVENT_TYPES, FIELD_AREAS, PHASES


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = Path(__file__).resolve().parent / "search_demo_ui"
DEFAULT_INDEX_ROOT = ROOT / "data" / "private" / "searchable-coaching-index-barca-bate-goal-30s-v2"
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8770
QUERY_PLAN_SCHEMA_VERSION = "playground-coach-query-plan-v1"
QUERY_ACTION_GUARD_VERSION = "coach-action-coverage-v1"
RETRIEVAL_LIMITATIONS = [
    "Search ranks saved model reports; matching footage has not been verified.",
    "Ranking does not enforce negation, event order, or every requested constraint.",
]
DEMO_STATUS = "SYSTEMS GO / SEMANTIC NO-GO"
AUDIT_WARNING = (
    "UNADJUDICATED MODEL OUTPUT — this saved Gemma report is factually wrong against held-out "
    "SoccerNet annotations. The 30-second window contains a visible penalty, shot on target, and goal; "
    "the model instead described a saved shot/clearance plus invented corner and build-up sequences."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_loopback_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("query LLM endpoint must be loopback-only")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Make a redirect an ordinary HTTP error instead of leaving loopback."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _build_loopback_opener():
    """Return an opener that ignores environment proxies and never follows redirects."""
    return build_opener(ProxyHandler({}), _NoRedirectHandler())


def _loopback_urlopen(target: Request | str, *, timeout: float):
    """Open only a directly addressed loopback URL with no proxy or redirect path."""
    url = target.full_url if isinstance(target, Request) else str(target)
    ensure_loopback_endpoint(url)
    return _build_loopback_opener().open(target, timeout=timeout)


def query_plan_response_format() -> dict[str, Any]:
    """Strict response schema for the query interpreter, not the video analyst."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "coach_search_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "intent_summary", "event_types", "search_terms", "participant_terms",
                    "phases", "field_areas", "explanation",
                ],
                "properties": {
                    "intent_summary": {"type": "string", "minLength": 1},
                    "event_types": {
                        "type": "array", "items": {"type": "string", "enum": list(EVENT_TYPES)},
                        "maxItems": 6, "uniqueItems": True,
                    },
                    "search_terms": {
                        "type": "array", "items": {"type": "string", "minLength": 1},
                        "minItems": 1, "maxItems": 10, "uniqueItems": True,
                    },
                    "participant_terms": {
                        "type": "array", "items": {"type": "string", "minLength": 1},
                        "maxItems": 6, "uniqueItems": True,
                    },
                    "phases": {
                        "type": "array", "items": {"type": "string", "enum": list(PHASES)},
                        "maxItems": 4, "uniqueItems": True,
                    },
                    "field_areas": {
                        "type": "array", "items": {"type": "string", "enum": list(FIELD_AREAS)},
                        "maxItems": 5, "uniqueItems": True,
                    },
                    "explanation": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def query_interpreter_prompt(query: str) -> tuple[str, str]:
    """Return prompts deliberately isolated from video and held-out annotations."""
    system = (
        "You are a query planner for a private soccer coaching-report search index. "
        "You do not watch or classify video and must not claim that an event exists. "
        "Translate only the coach's words into a compact retrieval plan. Event filters use the supplied ontology. "
        "search_terms should contain concrete words or short phrases likely to appear in a detailed VLM report. "
        "Preserve every requested action in search_terms or event_types; mentioning it only in prose is insufficient. "
        "participant_terms capture role, kit description, or jersey number requests. Empty filter arrays are valid. "
        "The downstream system performs deterministic local ranking. Return only strict JSON."
    )
    user = (
        f"Coach query: {query}\n\n"
        f"Allowed event types: {', '.join(EVENT_TYPES)}\n"
        f"Allowed phases: {', '.join(PHASES)}\n"
        f"Allowed field areas: {', '.join(FIELD_AREAS)}\n"
        "Build the retrieval plan without asserting that matching footage is present."
    )
    return system, user


def _unique_strings(value: Any, field: str, *, allowed: Iterable[str] | None = None, max_items: int) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise ValueError(f"{field} must be a list with at most {max_items} items")
    result: list[str] = []
    allowed_set = None if allowed is None else set(allowed)
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field} items must be non-empty strings")
        normalized = item.strip().casefold()
        if allowed_set is not None and normalized not in allowed_set:
            raise ValueError(f"{field} contains a value outside the ontology")
        if normalized not in result:
            result.append(normalized)
    return result


# A deliberately bounded lexical guard, not a semantic accuracy scorer. Keep the
# vocabulary explicit so unsupported concepts do not acquire a false guarantee.
_ACTION_CONCEPTS = {
    "shot": r"shots?|shoot(?:s|ing)?",
    "cutback": r"cutbacks?|cut backs?",
    "pass": r"pass(?:es|ing)?",
    "cross": r"cross(?:es|ing)?",
    "goal": r"goals?",
    "save": r"saves?",
    "tackle": r"tackles?|tackling",
    "interception": r"interceptions?|intercept(?:s|ed|ing)?",
    "turnover": r"turnovers?",
    "dribble": r"dribbles?|dribbling",
    "corner": r"corners?",
    "penalty": r"penalt(?:y|ies)",
    "offside": r"offsides?",
    "free kick": r"free kicks?",
    "throw in": r"throw ins?",
}


def _action_concepts(text: str) -> list[str]:
    normalized = re.sub(r"[_\s-]+", " ", text.casefold())
    return [name for name, pattern in _ACTION_CONCEPTS.items()
            if re.search(rf"(?<!\w)(?:{pattern})(?!\w)", normalized)]


# Only these explicit lexical attributes are bound to query evidence. This is
# not role/name recognition, visual identity verification, or filter execution.
_JERSEY_ATTRIBUTE = re.compile(
    r"(?<!\w)(?:(?:(?:jersey|shirt)(?:\s+(?:number|no\.?))?|"
    r"player(?:\s+(?:number|no\.?))?|number|no\.?)\s*#?\s*|#\s*)"
    r"([0-9]{1,3})(?!\w|[.:][0-9])"
)
_KIT_COLOURS = r"red|blue|green|white|black|yellow|orange|purple|pink|maroon|navy|gr[ae]y|gold|silver"
_KIT_ATTRIBUTE = re.compile(
    rf"(?<!\w)(?:wearing\s+(?:(?:a|the)\s+)?({_KIT_COLOURS})(?!\w)|"
    rf"({_KIT_COLOURS})\s+(?:kits?|shirts?|jerseys?|uniforms?)(?!\w))"
)


def _explicit_participant_attributes(text: str) -> set[str]:
    normalized = re.sub(r"[_\s-]+", " ", text.casefold())
    attributes = {"jersey:" + str(int(match.group(1)))
                  for match in _JERSEY_ATTRIBUTE.finditer(normalized)}
    for match in _KIT_ATTRIBUTE.finditer(normalized):
        colour = (match.group(1) or match.group(2)).replace("grey", "gray")
        attributes.add("kit:" + colour)
    return attributes


# Bind only one complete positive participant request. A colour/number elsewhere
# in a query is not permission to attach it to the requested participant.
_KIT_WORD = r"(?:kits?|shirts?|jerseys?|uniforms?)"
_ARTICLE = r"(?:(?:a|the)\s+)?"
_NUMBERED_PARTICIPANT = (
    r"(?:(?:player\s+with\s+)?(?:jersey|shirt)(?:\s+(?:number|no\.?))?|"
    r"player(?:\s+(?:number|no\.?))?|number|no\.?)\s*#?\s*[0-9]{1,3}|#\s*[0-9]{1,3}"
)
_WEARING_KIT = rf"wearing\s+{_ARTICLE}(?:{_KIT_COLOURS})(?:\s+{_KIT_WORD})?"
_COLOUR_KIT = rf"(?:{_KIT_COLOURS})\s+{_KIT_WORD}"
_PARTICIPANT_DESCRIPTION = (
    rf"{_ARTICLE}(?:(?:{_NUMBERED_PARTICIPANT})"
    rf"(?:\s+(?:{_WEARING_KIT}|in\s+{_ARTICLE}{_COLOUR_KIT}))?|"
    rf"(?:players?\s+)?{_WEARING_KIT}|{_COLOUR_KIT})"
)
_POSITIVE_PARTICIPANT_DESCRIPTION = re.compile(rf"{_PARTICIPANT_DESCRIPTION}[.!?]?")
_POSITIVE_PARTICIPANT_QUERY = re.compile(
    rf"(?:find|show)(?:\s+me)?\s+(?:the\s+)?"
    rf"(?:shots?(?:\s+on\s+(?:goal|target)|\s+off\s+target)?|pass(?:es)?|cutbacks?|"
    rf"cross(?:es)?|corners?|goals?|saves?|tackles?|interceptions?|dribbles?|"
    rf"free\s+kicks?|throw\s+ins?|long\s+balls?)\s+by\s+"
    rf"(?P<participant>{_PARTICIPANT_DESCRIPTION})[.!?]?"
)


def _validate_explicit_participant_binding(query: str, plan: dict[str, Any]) -> None:
    normalized_query = re.sub(r"[_\s-]+", " ", query.casefold()).strip()
    request = _POSITIVE_PARTICIPANT_QUERY.fullmatch(normalized_query)
    # No global bag of attributes: a match supplies exactly one positive actor.
    requested = (_explicit_participant_attributes(request.group("participant"))
                 if request is not None else None)
    unsupported: set[str] = set()
    for field in ("participant_terms", "search_terms"):
        for term in plan[field]:
            proposed = _explicit_participant_attributes(term)
            if not proposed:
                continue
            normalized_term = re.sub(r"[_\s-]+", " ", term.casefold()).strip()
            if (requested is None or not _POSITIVE_PARTICIPANT_DESCRIPTION.fullmatch(normalized_term)
                    or not proposed.issubset(requested)):
                unsupported.update(proposed)
    if unsupported:
        raise ValueError(
            "query plan has unsupported participant attributes without a bounded positive "
            "single-participant binding: " + ", ".join(sorted(unsupported))
            + ". Literal fallback does not enforce participant or exclusion constraints."
        )


def validate_query_plan(raw: Any, *, query: str | None = None) -> dict[str, Any]:
    expected = {
        "intent_summary", "event_types", "search_terms", "participant_terms",
        "phases", "field_areas", "explanation",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("query plan keys do not match the strict contract")
    for field in ("intent_summary", "explanation"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ValueError(f"{field} must be non-empty text")
    plan = {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "intent_summary": raw["intent_summary"].strip(),
        "event_types": _unique_strings(raw["event_types"], "event_types", allowed=EVENT_TYPES, max_items=6),
        "search_terms": _unique_strings(raw["search_terms"], "search_terms", max_items=10),
        "participant_terms": _unique_strings(raw["participant_terms"], "participant_terms", max_items=6),
        "phases": _unique_strings(raw["phases"], "phases", allowed=PHASES, max_items=4),
        "field_areas": _unique_strings(raw["field_areas"], "field_areas", allowed=FIELD_AREAS, max_items=5),
        "explanation": raw["explanation"].strip(),
    }
    if not plan["search_terms"]:
        raise ValueError("search_terms must contain at least one term")
    if query is not None:
        executable = " ".join(term for field in ("event_types", "search_terms") for term in plan[field])
        covered = set(_action_concepts(executable))
        missing = [concept for concept in _action_concepts(query) if concept not in covered]
        if missing:
            raise ValueError("query plan omitted requested action concepts: " + ", ".join(missing))
        _validate_explicit_participant_binding(query, plan)
    return plan


_FALLBACK_STOPWORDS = {
    "a", "an", "and", "around", "can", "clips", "find", "for", "from", "in", "involving",
    "later", "me", "of", "please", "show", "that", "the", "to", "video", "with",
}


def fallback_query_plan(query: str, error: str) -> dict[str, Any]:
    tokens = [token for token in re.findall(r"[\w#]+", query.casefold()) if token not in _FALLBACK_STOPWORDS]
    # Prioritize recognized requested actions within the ten-term plan budget.
    # The explanation discloses truncation; this is not full intent preservation.
    all_terms = list(dict.fromkeys([*_action_concepts(query), *tokens]))
    terms = all_terms[:10] or [query.strip().casefold() or "soccer"]
    truncation = " Some terms were omitted by the ten-term limit." if len(all_terms) > 10 else ""
    return {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "intent_summary": "Literal local keyword search because the query LLM was unavailable or invalid.",
        "event_types": [], "search_terms": terms, "participant_terms": [], "phases": [], "field_areas": [],
        "explanation": f"Fallback uses query words and normalized action terms.{truncation} Query-LLM error: {error}",
    }


class UnsupportedOrdinalConstraint(ValueError):
    """A recognized occurrence constraint cannot be executed by this ranker."""

    code = "unsupported_ordinal_constraint"


class UnsupportedTemporalOrderConstraint(ValueError):
    """A recognized action order cannot be executed by this ranker."""

    code = "unsupported_temporal_order_constraint"


class UnsupportedNegationConstraint(ValueError):
    """The saved-report ranker cannot execute a recognized action exclusion."""

    code = "unsupported_negation_constraint"


def _reject_unsupported_negation_query(query: str) -> None:
    # Bounded adjacent English exclusion only, not a general negation parser.
    # Keep non-action phrases such as 'without hesitation' on their existing path.
    normalized = re.sub(r"[_\s-]+", " ", query.casefold())
    actions = "|".join(f"(?:{pattern})" for pattern in [*_ACTION_CONCEPTS.values(), r"fouls?"])
    if re.search(rf"(?<!\w)without\s+(?:(?:a|an|any|the)\s+)?(?:{actions})(?!\w)", normalized):
        raise UnsupportedNegationConstraint(
            "Queries that exclude an action (for example, 'cutbacks without a shot') "
            "are not supported yet. Saved-report search cannot enforce that exclusion."
        )


def _reject_unsupported_temporal_order_query(query: str) -> None:
    # Bounded adjacent action-order guard, not a general temporal parser.
    # A phase phrase such as 'shots after halftime' remains on its existing path.
    normalized = re.sub(r"[_\s-]+", " ", query.casefold())
    actions = "|".join(f"(?:{pattern})" for pattern in _ACTION_CONCEPTS.values())
    relation = r"(?:leading\s+to|followed\s+by|that\s+follow(?:s|ed)?|before|after)"
    if re.search(rf"(?<!\w)(?:{actions})\s+{relation}\s+(?:(?:a|an|the)\s+)?(?:{actions})(?!\w)", normalized):
        raise UnsupportedTemporalOrderConstraint(
            "Queries that require one action before or after another are not supported yet. "
            "Saved-report search cannot enforce temporal event order."
        )


def _reject_unsupported_ordinal_query(query: str) -> None:
    # Bounded English capability guard, not a complete query-semantics parser.
    # Require an adjacent event phrase, preserving second half/striker/jerseys.
    normalized = re.sub(r"[_\s-]+", " ", query.casefold())
    ordinal = r"(?:first|second|third|[1-9]\d*(?:st|nd|rd|th))"
    actions = "|".join(f"(?:{pattern})" for pattern in _ACTION_CONCEPTS.values())
    if re.search(rf"(?<!\w){ordinal}\s+(?:{actions})(?!\w)", normalized):
        raise UnsupportedOrdinalConstraint(
            "Queries for a specific event occurrence (for example, 'second corner') "
            "are not supported yet. Ask for events without an occurrence number."
        )


def interpret_coach_query(
    query: str, *, endpoint: str = DEFAULT_ENDPOINT, model: str = DEFAULT_MODEL, timeout_s: float = 25,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1–500 characters")
    _reject_unsupported_ordinal_query(query)
    _reject_unsupported_temporal_order_query(query)
    _reject_unsupported_negation_query(query)
    ensure_loopback_endpoint(endpoint)
    system, user = query_interpreter_prompt(query.strip())
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": query_plan_response_format(),
        "temperature": 0,
        "max_tokens": 900,
    }
    started = time.perf_counter()
    raw_content: str | None = None
    reported_model: str | None = None
    try:
        request = Request(
            endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"}, method="POST",
        )
        with _loopback_urlopen(request, timeout=timeout_s) as response:
            response_json = json.loads(response.read().decode("utf-8"))
        identity = response_json.get("model")
        reported_model = identity.strip() if isinstance(identity, str) and identity.strip() else None
        raw_content = response_json.get("choices", [{}])[0].get("message", {}).get("content")
        plan = validate_query_plan(parse_json_content(raw_content), query=query)
        source = "local_query_llm"
        error = None
    except (HTTPError, URLError, TimeoutError, OSError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        plan = fallback_query_plan(query, error)
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
        "action_guard_version": QUERY_ACTION_GUARD_VERSION,
        "limitations": list(RETRIEVAL_LIMITATIONS),
    }


def _flatten_event(event: dict[str, Any]) -> str:
    participants = " ".join(
        " ".join(str(value) for value in participant.values() if value is not None)
        for participant in event.get("participants", [])
    )
    parts: list[Any] = [
        event.get("event_types", []), event.get("primary_action"), event.get("phase_of_play"),
        event.get("field_areas", []), event.get("outcome"), event.get("detailed_description"),
        event.get("coaching_relevance"), event.get("coaching_tags", []),
        event.get("retrieval_keywords", []), event.get("uncertainty"), participants,
    ]
    text = " ".join(" ".join(item) if isinstance(item, list) else str(item or "") for item in parts)
    return re.sub(r"[_\s]+", " ", text.casefold()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized = re.sub(r"[_\s]+", " ", phrase.casefold()).strip()
    if not normalized:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None


def rank_saved_events(database: Path, plan: dict[str, Any], *, limit: int = 12) -> list[dict[str, Any]]:
    """Deterministically rank saved model reports; no pixel/event inference occurs here."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT e.event_id,e.window_id,e.start_s,e.end_s,e.confidence,e.report_json,w.match_id "
            "FROM events e JOIN windows w ON w.window_id=e.window_id WHERE w.status='complete'"
        ).fetchall()
    finally:
        connection.close()
    ranked: list[dict[str, Any]] = []
    for row in rows:
        event = json.loads(row["report_json"])
        # Explicit event filters constrain eligibility; alternatives use OR.
        required_types = set(plan["event_types"])
        if required_types and not required_types.intersection(event.get("event_types", [])):
            continue
        text = _flatten_event(event)
        matched: list[dict[str, Any]] = []
        score = 0.0
        for event_type in plan["event_types"]:
            if event_type in event.get("event_types", []):
                score += 6.0
                matched.append({"kind": "event_type", "value": event_type, "weight": 6.0})
        for term in plan["search_terms"]:
            if _contains_phrase(text, term):
                score += 1.5
                matched.append({"kind": "search_term", "value": term, "weight": 1.5})
        participant_text = _flatten_event({"participants": event.get("participants", [])})
        for term in plan["participant_terms"]:
            if _contains_phrase(participant_text, term):
                score += 2.5
                matched.append({"kind": "participant", "value": term, "weight": 2.5})
        if event.get("phase_of_play") in plan["phases"]:
            score += 3.0
            matched.append({"kind": "phase", "value": event["phase_of_play"], "weight": 3.0})
        for area in plan["field_areas"]:
            if area in event.get("field_areas", []):
                score += 3.0
                matched.append({"kind": "field_area", "value": area, "weight": 3.0})
        if score <= 0:
            continue
        ranked.append({
            "event_id": row["event_id"], "window_id": row["window_id"], "match_id": row["match_id"],
            "start_s": row["start_s"], "end_s": row["end_s"], "confidence": row["confidence"],
            "score": score, "matched_on": matched, "report": event,
        })
    ranked.sort(key=lambda item: (-item["score"], -item["confidence"], item["start_s"], item["event_id"]))
    return ranked[:limit]


def _clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = int(round(seconds - minutes * 60))
    if remainder == 60:
        minutes += 1
        remainder = 0
    return f"{minutes:02d}:{remainder:02d}"


@dataclass(frozen=True)
class DemoContext:
    index_root: Path
    database: Path
    receipt: dict[str, Any]
    index_plan: dict[str, Any]
    review_clip: Path
    audit: list[dict[str, Any]]
    endpoint: str
    model: str

    @property
    def window_start_s(self) -> float:
        return float(self.index_plan["windows"][0]["start_s"])

    @property
    def window_end_s(self) -> float:
        return float(self.index_plan["windows"][0]["end_s"])


def _load_heldout_audit(plan: dict[str, Any]) -> list[dict[str, Any]]:
    video = Path(plan["configuration"]["video"]["path"])
    labels_path = video.parent / "Labels-v2.json"
    if not labels_path.is_file():
        return []
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    start_s = float(plan["windows"][0]["start_s"])
    end_s = float(plan["windows"][0]["end_s"])
    audit: list[dict[str, Any]] = []
    for item in labels.get("annotations", []):
        if not str(item.get("gameTime", "")).startswith("1 -"):
            continue
        timestamp_s = float(item["position"]) / 1000.0
        if start_s <= timestamp_s <= end_s:
            audit.append({
                "label": item["label"], "timestamp_s": timestamp_s,
                "relative_s": round(timestamp_s - start_s, 3), "clock": _clock(timestamp_s),
                "team": item.get("team"), "visibility": item.get("visibility"),
            })
    return audit


def ensure_review_clip(index_root: Path, plan: dict[str, Any]) -> Path:
    target = index_root / "browser-review-30s-silent.mp4"
    if target.is_file() and target.stat().st_size > 100_000:
        return target
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("imageio-ffmpeg is required to create the browser review clip") from exc
    source = Path(plan["configuration"]["video"]["path"])
    start_s = float(plan["windows"][0]["start_s"])
    duration_s = float(plan["windows"][0]["end_s"]) - start_s
    if not source.is_file():
        raise FileNotFoundError(source)
    temporary = target.with_name(target.stem + ".building.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start_s:.3f}", "-i", str(source), "-t", f"{duration_s:.3f}", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(temporary),
    ]
    subprocess.run(command, check=True, timeout=120)
    os.replace(temporary, target)
    return target


def load_demo_context(
    index_root: Path = DEFAULT_INDEX_ROOT, *, endpoint: str = DEFAULT_ENDPOINT, model: str = DEFAULT_MODEL,
) -> DemoContext:
    ensure_loopback_endpoint(endpoint)
    index_root = index_root.resolve()
    if "data" not in [part.casefold() for part in index_root.parts] or "private" not in [part.casefold() for part in index_root.parts]:
        raise ValueError("demo index must remain under data/private")
    database = index_root / "search-index.sqlite3"
    receipt_path = index_root / "run-receipt.json"
    plan_path = index_root / "index-plan.json"
    for path in (database, receipt_path, plan_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("database_sha256") != _sha256(database):
        raise RuntimeError("search database does not match the sealed run receipt")
    if receipt.get("performance_claim_allowed") is not False or receipt.get("audio_supplied_to_vlm") is not False:
        raise RuntimeError("demo receipt does not preserve the research safety boundary")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    review_clip = ensure_review_clip(index_root, plan)
    return DemoContext(
        index_root=index_root, database=database, receipt=receipt, index_plan=plan,
        review_clip=review_clip, audit=_load_heldout_audit(plan), endpoint=endpoint, model=model,
    )


def _model_health(endpoint: str, timeout_s: float = 1.5) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with _loopback_urlopen(endpoint.rstrip("/") + "/models", timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
        ids = [item.get("id") or item.get("name") for item in body.get("data", body.get("models", []))]
        return {"online": True, "models": ids, "latency_ms": round((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        return {"online": False, "models": [], "latency_ms": round((time.perf_counter() - started) * 1000), "error": str(exc)}


def _result_payload(result: dict[str, Any], context: DemoContext) -> dict[str, Any]:
    event = result["report"]
    return {
        **result,
        "match_clock": f"{_clock(result['start_s'])}–{_clock(result['end_s'])}",
        "relative_start_s": round(max(0.0, result["start_s"] - context.window_start_s), 3),
        "relative_end_s": round(min(context.window_end_s, result["end_s"]) - context.window_start_s, 3),
        "event_types": event.get("event_types", []), "primary_action": event.get("primary_action"),
        "participants": event.get("participants", []), "evidence_frames": [
            {**frame, "clock": _clock(frame["timestamp_s"]), "relative_s": round(frame["timestamp_s"] - context.window_start_s, 3)}
            for frame in event.get("evidence_frames", [])
        ],
        "phase_of_play": event.get("phase_of_play"), "field_areas": event.get("field_areas", []),
        "outcome": event.get("outcome"), "detailed_description": event.get("detailed_description"),
        "coaching_relevance": event.get("coaching_relevance"), "coaching_tags": event.get("coaching_tags", []),
        "uncertainty": event.get("uncertainty"),
    }


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "PlayGroundSearchDemo/1.0"

    @property
    def context(self) -> DemoContext:
        return self.server.demo_context  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
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
        self.end_headers()
        self.wfile.write(data)

    def _serve_video(self) -> None:
        path = self.context.review_clip
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range")
        partial = False
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            if match.group(1):
                start = int(match.group(1))
            if match.group(2):
                end = min(int(match.group(2)), size - 1)
            if start > end or start >= size:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            partial = True
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("content-type", "video/mp4")
        self.send_header("accept-ranges", "bytes")
        self.send_header("content-length", str(length))
        if partial:
            self.send_header("content-range", f"bytes {start}-{end}/{size}")
        self.send_header("cache-control", "private, no-store")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._serve_file(UI_ROOT / "index.html", "text/html; charset=utf-8")
        elif path == "/app.css":
            self._serve_file(UI_ROOT / "app.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(UI_ROOT / "app.js", "text/javascript; charset=utf-8")
        elif path == "/media/review.mp4":
            self._serve_video()
        elif path == "/api/status":
            connection = sqlite3.connect(self.context.database)
            try:
                event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                window_count = connection.execute("SELECT COUNT(*) FROM windows WHERE status='complete'").fetchone()[0]
            finally:
                connection.close()
            self._send_json({
                "demo_status": DEMO_STATUS, "warning": AUDIT_WARNING,
                "query_model": self.context.model, "model_health": _model_health(self.context.endpoint),
                "event_count": event_count, "window_count": window_count,
                "window_duration_s": round(self.context.window_end_s - self.context.window_start_s, 3),
                "match_id": self.context.index_plan["configuration"]["match_id"],
                "source_reference": self.context.index_plan["configuration"]["source_reference"],
                "audio_supplied_to_vlm": False, "review_clip_audio": False,
                "performance_claim_allowed": False, "audit": self.context.audit,
                "pipeline": [
                    "Coach language → local query LLM → strict retrieval plan",
                    "Validated plan → deterministic ranking over saved VLM reports",
                    "Playable frames + evidence timestamps → human review",
                    "Held-out labels → separate post-hoc audit only",
                ],
            })
        elif path == "/healthz":
            self._send_json({"ok": True, "status": DEMO_STATUS})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/search":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            if length < 1 or length > 8_192:
                raise ValueError("request body must be 1–8192 bytes")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            query = body.get("query") if isinstance(body, dict) else None
            interpretation = interpret_coach_query(query, endpoint=self.context.endpoint, model=self.context.model)
            results = rank_saved_events(self.context.database, interpretation["plan"], limit=12)
            self._send_json({
                "query": query, "interpretation": interpretation,
                "results": [_result_payload(result, self.context) for result in results],
                "result_count": len(results), "demo_status": DEMO_STATUS, "warning": AUDIT_WARNING,
                "audit": self.context.audit, "clip_url": "/media/review.mp4",
                "ranking_note": "Scores are transparent deterministic matches over saved VLM text; they do not validate the soccer claims.",
            })
        except (UnsupportedOrdinalConstraint, UnsupportedTemporalOrderConstraint, UnsupportedNegationConstraint) as exc:
            self._send_json({"error": str(exc), "error_code": exc.code}, status=HTTPStatus.UNPROCESSABLE_ENTITY)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:  # Keep the live demo responsive but expose exact evidence.
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)


def build_server(context: DemoContext, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("search demo must bind to loopback")
    server = ThreadingHTTPServer((host, port), DemoHandler)
    server.demo_context = context  # type: ignore[attr-defined]
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", type=Path, default=DEFAULT_INDEX_ROOT)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    context = load_demo_context(args.index_root, endpoint=args.endpoint, model=args.model)
    server = build_server(context, args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    print(f"PlayGround coach-search demo: {url}")
    print(f"{DEMO_STATUS}: {AUDIT_WARNING}")
    print("Private real footage remains on this machine. Press Ctrl+C to stop.")
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
