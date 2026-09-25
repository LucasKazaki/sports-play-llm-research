"""Verified adapter for the private SoccerMaster long-form search package.

The adapter is deliberately soccer-only.  It verifies the frozen visual
prediction chain, loads the private 96-window search index, exposes opaque
whole-half media bindings, and performs deterministic BM25 ranking over saved
VLM prose.  The optional query LLM sees only the coach query and a public
soccer ontology; it never receives video, labels, annotations, source identity,
or saved predictions.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import time
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import query_capabilities as query_caps


DEFAULT_ARTIFACT_ROOT = Path("artifacts/soccermaster-longform-v1")
DEFAULT_PRIVATE_ROOT = Path("data/private/soccermaster-longform-v1")
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
EVENT_TYPES = (
    "aerial_duel",
    "ball_out_of_play",
    "ball_recovery",
    "card",
    "clearance",
    "corner_kick",
    "counterpress",
    "cross",
    "dribble",
    "foul",
    "free_kick",
    "goal",
    "goal_kick",
    "ground_duel",
    "header",
    "interception",
    "long_ball",
    "offside",
    "other",
    "penalty_kick",
    "press",
    "replay",
    "save",
    "set_piece",
    "short_pass",
    "shot_off_target",
    "shot_on_target",
    "stoppage",
    "substitution",
    "switch_of_play",
    "tackle",
    "through_ball",
    "throw_in",
    "transition",
    "turnover",
    "unknown",
)
PHASES = (
    "build_up",
    "progression",
    "sustained_attack",
    "transition_to_attack",
    "transition_to_defense",
    "defensive_phase",
    "set_piece",
    "restart",
    "stoppage",
    "unknown",
)
FIELD_AREAS = (
    "defensive_third",
    "middle_third",
    "attacking_third",
    "left_flank",
    "right_flank",
    "central_channel",
    "penalty_area",
    "goal_area",
    "touchline",
    "unknown",
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "find",
    "for",
    "from",
    "in",
    "into",
    "me",
    "near",
    "of",
    "please",
    "show",
    "the",
    "to",
    "with",
}
FRAME_COUNTS = {30: 8, 60: 12, 120: 16}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ensure_loopback_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("model endpoint must be a local HTTP URL")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        raise ValueError("model endpoint hostname must be a literal loopback address") from error
    if not address.is_loopback:
        raise ValueError("model endpoint must remain on loopback")


def model_health(endpoint: str, timeout_seconds: float = 2.0) -> dict[str, Any]:
    try:
        ensure_loopback_endpoint(endpoint)
        request = urllib.request.Request(endpoint.rstrip("/") + "/models", headers={"accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            value = json.loads(response.read())
        models = value.get("data", value.get("models", []))
        return {"reachable": True, "models": [item.get("id") or item.get("model") for item in models]}
    except Exception as error:
        return {"reachable": False, "error": f"{type(error).__name__}: {error}"}


@dataclass(frozen=True)
class MediaBinding:
    half: int
    asset_id: str
    route: str
    path: Path
    sha256: str
    duration_seconds: float
    source_media_sha256: str
    browser_compatible_derivative: bool


@dataclass(frozen=True)
class SoccerContext:
    artifact_root: Path
    private_root: Path
    entries: tuple[Mapping[str, Any], ...]
    media_by_window: Mapping[str, MediaBinding]
    media_routes: Mapping[str, MediaBinding]
    verification: Mapping[str, Any]
    metrics: Mapping[str, Any]
    evaluation: Mapping[str, Any]
    spot_check: Mapping[str, Any]
    coverage: Mapping[str, Any]
    model: str
    endpoint: str
    spot_by_window: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


def _safe_inside(path: Path, allowed_root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} escaped its private allowlisted root") from error
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _verify_required_seal(
    artifact_root: Path,
    private_root: Path,
    required_public: Sequence[str],
    required_private: Sequence[str],
) -> Mapping[str, Any]:
    seal_path = artifact_root / "prediction-seal.json"
    if not seal_path.is_file():
        raise FileNotFoundError(seal_path)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    files = seal.get("files", {})
    if not isinstance(files, dict) or canonical_hash(files) != seal.get("root_hash"):
        raise ValueError("soccer prediction seal root hash mismatch")
    for relative in required_public:
        key = f"public/{relative}"
        expected = files.get(key)
        path = artifact_root / relative
        if not isinstance(expected, str) or not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"sealed soccer artifact mismatch: {key}")
    private_map = {
        "soccer-search-index.jsonl": private_root / "experiment" / "soccer-search-index.jsonl",
        "source-lock.json": private_root / "experiment" / "source-lock.json",
        "window-manifest.jsonl": private_root / "experiment" / "window-manifest.jsonl",
    }
    for relative in required_private:
        key = f"private/{relative}"
        expected = files.get(key)
        path = private_map[relative]
        if not isinstance(expected, str) or not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"sealed soccer artifact mismatch: {key}")
    return seal


def _load_package_bound_postseal(artifact_root: Path) -> dict[str, Mapping[str, Any]]:
    package_path = artifact_root / "package-receipt.json"
    if not package_path.is_file():
        raise FileNotFoundError(package_path)
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if package.get("status") not in {
        "implementation_verified_independent_review_pending",
        "verified",
        "pass",
    } or package.get("performance_claim_allowed") is not False:
        raise ValueError("soccer package receipt lost its verification or no-performance-claim boundary")
    bound = {
        Path(str(item.get("name", ""))).name: item
        for item in package.get("artifacts", [])
        if isinstance(item, dict)
    }
    required = (
        "annotation-evaluation.json",
        "spot-check-adjudication.json",
        "verification-receipt.json",
        "prediction-seal.json",
    )
    values: dict[str, Mapping[str, Any]] = {}
    for name in required:
        item = bound.get(name)
        path = artifact_root / name
        if not isinstance(item, dict) or item.get("sha256") != sha256_file(path):
            raise ValueError(f"post-seal soccer artifact is not package-bound: {name}")
        values[name] = json.loads(path.read_text(encoding="utf-8"))
    return values


def _load_review_receipt(private_root: Path) -> Mapping[str, Any] | None:
    path = private_root / "review" / "review-derivative-receipt.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "soccermaster-longform-browser-review-v1":
        raise ValueError("soccer review derivative receipt has an unknown schema")
    return value


def load_context(
    artifact_root: Path,
    *,
    private_root: Path,
    project_root: Path,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
) -> SoccerContext:
    ensure_loopback_endpoint(endpoint)
    project_root = project_root.resolve()
    artifact_root = artifact_root.resolve()
    private_root = private_root.resolve()
    try:
        artifact_root.relative_to(project_root)
        private_root.relative_to((project_root / "data" / "private").resolve())
    except ValueError as error:
        raise ValueError("soccer package roots must remain inside the project and its private data root") from error

    required_public = (
        "protocol-receipt.json",
        "frozen-test-config.json",
        "report-metrics.json",
        "search-index-receipt.json",
        "frozen-query-results.json",
        "test-run-receipt.json",
    )
    required_private = ("soccer-search-index.jsonl", "source-lock.json", "window-manifest.jsonl")
    for name in (*required_public, "prediction-seal.json", "package-receipt.json"):
        if not (artifact_root / name).is_file():
            raise FileNotFoundError(artifact_root / name)
    seal = _verify_required_seal(artifact_root, private_root, required_public, required_private)
    postseal = _load_package_bound_postseal(artifact_root)
    verification = postseal["verification-receipt.json"]
    checks = verification.get("checks", {})
    if verification.get("status") != "pass" or verification.get("visual_prediction_seal_root_hash") != seal.get("root_hash"):
        raise ValueError("soccer verification receipt does not bind the passing prediction seal")
    expected_checks = {
        "dense_window_count": 90,
        "stress_window_count": 6,
        "test_window_denominator": 96,
        "test_valid_response_count": 96,
        "test_failure_count": 0,
        "labels_opened_only_post_seal": True,
        "input_anonymization_audit_status": "failed_in_at_least_one_sampled_frame",
        "team_name_pixels_fully_unavailable": False,
    }
    for key, expected in expected_checks.items():
        actual = checks.get(key, verification.get(key))
        if actual != expected:
            raise ValueError(f"soccer verification boundary mismatch: {key}")

    index_path = private_root / "experiment" / "soccer-search-index.jsonl"
    index_receipt = json.loads((artifact_root / "search-index-receipt.json").read_text(encoding="utf-8"))
    if index_receipt.get("index_sha256") != sha256_file(index_path):
        raise ValueError("soccer search index hash mismatch")
    entries = tuple(json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if len(entries) != 96 or index_receipt.get("entry_count") != 96:
        raise ValueError("soccer demo index must contain exactly 96 frozen test windows")
    if sum(entry.get("window_role") == "test_dense" for entry in entries) != 90:
        raise ValueError("soccer demo index lost its 90 dense windows")
    if sum(entry.get("window_role") == "test_stress" for entry in entries) != 6:
        raise ValueError("soccer demo index lost its six stress windows")
    if {int(entry.get("source_half", 0)) for entry in entries} != {1, 2}:
        raise ValueError("soccer demo index must cover both held-out halves")
    if {int(entry.get("duration_seconds", 0)) for entry in entries} != {30, 60, 120}:
        raise ValueError("soccer demo index lost a frozen duration")

    manifest_path = private_root / "experiment" / "window-manifest.jsonl"
    manifest_rows = tuple(
        json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    manifest_by_id = {str(row.get("window_id")): row for row in manifest_rows if str(row.get("role", "")).startswith("test_")}
    if set(manifest_by_id) != {str(entry.get("window_id")) for entry in entries}:
        raise ValueError("soccer private index and frozen test manifest do not match")
    for entry in entries:
        duration = int(entry["duration_seconds"])
        manifest = manifest_by_id[str(entry["window_id"])]
        if int(manifest.get("frame_count", 0)) != FRAME_COUNTS[duration]:
            raise ValueError("soccer test window lost its ordered-frame denominator")

    source_lock = json.loads((private_root / "experiment" / "source-lock.json").read_text(encoding="utf-8"))
    source_halves = source_lock.get("test", {}).get("halves", [])
    if len(source_halves) != 2:
        raise ValueError("soccer private source lock must contain two test halves")
    raw_root = private_root / "raw"
    review_receipt = _load_review_receipt(private_root)
    review_by_half = {
        int(item["half"]): item
        for item in (review_receipt or {}).get("halves", [])
        if isinstance(item, dict) and isinstance(item.get("half"), int)
    }
    media_by_half: dict[int, MediaBinding] = {}
    for item in source_halves:
        half = int(item.get("half", 0))
        source_path = _safe_inside(Path(str(item.get("media_path", ""))), raw_root, "soccer source media")
        source_sha = sha256_file(source_path)
        if source_sha != item.get("media_sha256"):
            raise ValueError(f"soccer source media hash mismatch for opaque half {half}")
        selected_path = source_path
        selected_sha = source_sha
        derivative = review_by_half.get(half)
        browser_compatible = False
        if derivative is not None:
            if derivative.get("source_media_sha256") != source_sha or derivative.get("audio_streams") != 0:
                raise ValueError(f"soccer review derivative provenance mismatch for opaque half {half}")
            selected_path = _safe_inside(
                private_root / "review" / str(derivative.get("filename", "")),
                private_root / "review",
                "soccer review derivative",
            )
            selected_sha = sha256_file(selected_path)
            if selected_sha != derivative.get("sha256"):
                raise ValueError(f"soccer review derivative hash mismatch for opaque half {half}")
            browser_compatible = True
        route = f"/media/soccer/longform/half-{half}"
        media_by_half[half] = MediaBinding(
            half=half,
            asset_id=f"soccer-test-half-{half}",
            route=route,
            path=selected_path,
            sha256=selected_sha,
            duration_seconds=float(item.get("duration_seconds", 0.0)),
            source_media_sha256=source_sha,
            browser_compatible_derivative=browser_compatible,
        )
    media_by_window = {str(entry["window_id"]): media_by_half[int(entry["source_half"])] for entry in entries}
    media_routes = {binding.route: binding for binding in media_by_half.values()}

    metrics = json.loads((artifact_root / "report-metrics.json").read_text(encoding="utf-8"))
    evaluation = postseal["annotation-evaluation.json"]
    spot_check = postseal["spot-check-adjudication.json"]
    spot_by_window = {
        str(row["window_id"]): row for row in spot_check.get("rows", []) if isinstance(row, dict)
    }
    if spot_check.get("judgment_counts") != {
        "supported": 0,
        "partially_supported": 2,
        "unsupported": 4,
        "abstention_appropriate": 0,
    }:
        raise ValueError("soccer direct spot-check result changed from the verified no-go receipt")
    if evaluation.get("performance_claim_allowed") is not False or evaluation.get(
        "labels_opened_only_after_visual_prediction_seal_verified"
    ) is not True:
        raise ValueError("soccer post-seal evaluation lost its leakage or claim boundary")
    coverage = {
        "source_halves": 2,
        "source_seconds": 5400.0,
        "source_hours": 1.5,
        "dense_entire_game_index": True,
        "dense_window_count": 90,
        "dense_windows_per_half": {"1": 45, "2": 45},
        "dense_window_seconds": 60,
        "dense_stride_seconds": 60,
        "stress_window_count": 6,
        "stress_durations_seconds": [30, 60, 120],
        "minimum_ordered_frames": 8,
        "browser_compatible_review_media": all(item.browser_compatible_derivative for item in media_by_half.values()),
    }
    return SoccerContext(
        artifact_root=artifact_root,
        private_root=private_root,
        entries=entries,
        media_by_window=media_by_window,
        media_routes=media_routes,
        verification=verification,
        metrics=metrics,
        evaluation=evaluation,
        spot_check=spot_check,
        coverage=coverage,
        model=model,
        endpoint=endpoint,
        spot_by_window=spot_by_window,
    )


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())


def _query_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(token for token in _tokens(text) if token not in QUERY_STOPWORDS))


def _bm25(entries: Sequence[Mapping[str, Any]], query: str, limit: int) -> list[tuple[float, Mapping[str, Any]]]:
    documents = [_tokens(str(entry.get("search_text", ""))) for entry in entries]
    query_terms = _query_tokens(query)
    if not documents or not query_terms:
        return []
    document_frequency = Counter(term for document in documents for term in set(document))
    average_length = sum(len(document) for document in documents) / len(documents)
    scored: list[tuple[float, Mapping[str, Any]]] = []
    for entry, document in zip(entries, documents):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            df = document_frequency.get(term, 0)
            if not df:
                continue
            inverse = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
            frequency = frequencies[term]
            denominator = frequency + 1.5 * (0.25 + 0.75 * len(document) / max(1.0, average_length))
            score += inverse * frequency * 2.5 / denominator
        if score > 0:
            scored.append((score, entry))
    return sorted(scored, key=lambda item: (-item[0], str(item[1].get("window_id"))))[:limit]


def interpret_query(
    query: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1-500 characters")
    query_caps.check_query(query, "soccer")
    ensure_loopback_endpoint(endpoint)
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "soccer_longform_search_terms",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "search_terms": {"type": "array", "maxItems": 12, "items": {"type": "string"}},
                    "event_types": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "enum": list(EVENT_TYPES)},
                    },
                },
                "required": ["search_terms", "event_types"],
            },
        },
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Translate a coach's soccer-film search request into short visual-report search terms. "
                    "Do not answer the query or assert that an event exists. Do not invent a player, team, game, score, or result."
                ),
            },
            {"role": "user", "content": query.strip()},
        ],
        "response_format": schema,
        "temperature": 0,
        "max_tokens": 500,
    }
    raw_content = None
    started = time.perf_counter()
    try:
        request = urllib.request.Request(
            endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            envelope = json.loads(response.read())
        raw_content = envelope["choices"][0]["message"]["content"]
        parsed = json.loads(raw_content)
        search_terms = [str(item).strip() for item in parsed.get("search_terms", []) if str(item).strip()][:12]
        event_types = [str(item) for item in parsed.get("event_types", []) if item in EVENT_TYPES][:6]
        query_caps.validate_participant_terms(query, search_terms, "soccer")
        if not search_terms and not event_types:
            raise ValueError("query model returned no usable terms")
        return {
            "source": "local_query_llm",
            "requested_model": model,
            "reported_model": envelope.get("model") or model,
            "search_terms": search_terms,
            "event_types": event_types,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "raw_interpretation": raw_content,
            "error": None,
        }
    except (OSError, TimeoutError, urllib.error.URLError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        return {
            "source": "deterministic_literal_fallback",
            "requested_model": model,
            "reported_model": model,
            "search_terms": [query.strip()],
            "event_types": [],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "raw_interpretation": raw_content,
            "error": f"{type(error).__name__}: {error}",
        }


def _frame_relative(frame_id: str, duration_seconds: int) -> float | None:
    match = re.fullmatch(r"F(\d{2})", frame_id)
    if not match or duration_seconds not in FRAME_COUNTS:
        return None
    index = int(match.group(1))
    count = FRAME_COUNTS[duration_seconds]
    if index < 0 or index >= count:
        return None
    return (index + 0.5) * duration_seconds / count


def _clock(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _unique_text(values: Sequence[Any]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def search_context(
    context: SoccerContext,
    query: str,
    *,
    limit: int = 12,
    use_query_llm: bool = True,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1-500 characters")
    query_caps.check_query(query, "soccer")
    interpretation = (
        interpret_query(query, endpoint=context.endpoint, model=context.model)
        if use_query_llm
        else {
            "source": "deterministic_literal_fallback",
            "requested_model": context.model,
            "latency_ms": 0,
            "reported_model": context.model,
            "search_terms": [query.strip()],
            "event_types": [],
            "raw_interpretation": None,
            "error": "query LLM disabled for this server session",
        }
    )
    expanded = " ".join([query, *interpretation["search_terms"], *interpretation["event_types"]])
    requested_event_types = set(interpretation["event_types"])
    ranked_candidates = _bm25(context.entries, expanded, len(context.entries))
    if requested_event_types:
        filtered: list[tuple[float, Mapping[str, Any]]] = []
        for score, candidate in ranked_candidates:
            candidate_types = {
                str(event.get("event_type"))
                for event in candidate.get("report", {}).get("events", [])
                if isinstance(event, dict)
            }
            overlap = requested_event_types & candidate_types
            if overlap:
                filtered.append((score + 6.0 * len(overlap), candidate))
        ranked = sorted(filtered, key=lambda item: (-item[0], str(item[1].get("window_id"))))[:limit]
    else:
        ranked = ranked_candidates[:limit]
    results = []
    for score, entry in ranked:
        report = entry["report"]
        window_id = str(entry["window_id"])
        binding = context.media_by_window[window_id]
        half = int(entry["source_half"])
        start = float(entry["start_seconds"])
        duration = int(entry["duration_seconds"])
        events = [item for item in report.get("events", []) if isinstance(item, dict)]
        event_types = _unique_text([event.get("event_type") for event in events])
        participants = [
            participant
            for event in events
            for participant in event.get("participants", [])
            if isinstance(participant, dict)
        ]
        evidence: list[dict[str, Any]] = []
        seen_evidence: set[tuple[str, float]] = set()
        for event in events:
            observations = str(event.get("sequence_detail") or event.get("primary_action") or "Model-cited sampled frame")
            for frame_id in event.get("evidence_frame_ids", []):
                relative = _frame_relative(str(frame_id), duration)
                if relative is None:
                    continue
                source_time = round(start + relative, 3)
                key = (str(frame_id), source_time)
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                evidence.append(
                    {
                        "frame_id": str(frame_id),
                        "relative_s": source_time,
                        "source_timestamp_s": source_time,
                        "clock": f"H{half} {_clock(source_time)}",
                        "observation": observations,
                    }
                )
        uncertainty_items = _unique_text(
            [*report.get("overall_uncertainties", []), *(item for event in events for item in event.get("uncertainties", []))]
        )
        confidence_values = [float(event["confidence"]) for event in events if isinstance(event.get("confidence"), (int, float))]
        spot = context.spot_by_window.get(window_id)
        results.append(
            {
                "event_id": window_id,
                "window_id": window_id,
                "window_role": entry["window_role"],
                "match_id": "private-held-out-soccer-match",
                "clip_id": binding.asset_id,
                "source_id": binding.asset_id,
                "split": "test",
                "source_half": half,
                "start_s": start,
                "end_s": start + duration,
                "duration_s": duration,
                "relative_start_s": start,
                "relative_end_s": start + duration,
                "source_start_s": start,
                "source_end_s": start + duration,
                "match_clock": f"Half {half} · {_clock(start)}–{_clock(start + duration)}",
                "clip_url": binding.route,
                "confidence": max(confidence_values) if confidence_values else None,
                "score": score,
                "matched_on": [{"kind": "BM25", "value": term, "weight": 0} for term in _query_tokens(expanded)[:12]],
                "event_types": event_types,
                "primary_action": events[0].get("primary_action") if events else "model abstention",
                "participants": participants,
                "evidence_frames": evidence,
                "phase_of_play": " · ".join(_unique_text([event.get("phase_of_play") for event in events])) or "unknown",
                "field_areas": _unique_text([area for event in events for area in event.get("field_areas", [])]),
                "outcome": "; ".join(_unique_text([event.get("outcome") for event in events])) or "unknown",
                "detailed_description": report.get("window_summary"),
                "coaching_relevance": "; ".join(
                    _unique_text([event.get("coaching_relevance") for event in events])
                ),
                "coaching_tags": _unique_text(
                    [*report.get("coach_search_terms", []), *(tag for event in events for tag in event.get("search_terms", []))]
                ),
                "uncertainty": "; ".join(uncertainty_items)
                or "Uncalibrated sparse-frame VLM report; human video review required.",
                "abstain": bool(report.get("abstain")),
                "abstention_reason": report.get("abstention_reason"),
                "spot_check": (
                    {
                        "overall_judgment": spot.get("overall_judgment"),
                        "visual_observations": spot.get("visual_observations"),
                    }
                    if spot
                    else None
                ),
                "attribution": {
                    "report_origin": "sealed_silent_frame_vlm_report",
                    "optional_vlm_fields": sorted(report.keys()),
                    "deterministic_fields": ["query_expansion_validation", "BM25_ranking", "time_projection"],
                    "audio_fields": [],
                    "source_label_fields": [],
                    "boundary": (
                        "All event semantics are untrusted sealed silent-frame VLM output; deterministic ranking and "
                        "time projection do not validate what happened."
                    ),
                },
            }
        )
    return {
        "query": query,
        "interpretation": interpretation,
        "results": results,
        "result_count": len(results),
        "ranking_note": (
            "Optional local query-LM expansion plus deterministic BM25 over 96 sealed, untrusted silent-frame VLM "
            "reports. Retrieval does not validate event claims; labels and source identity never enter query planning."
        ),
    }


def build_browser_review_media(
    private_root: Path,
    *,
    ffmpeg: Path,
) -> Mapping[str, Any]:
    """Remux both private H.264 halves to silent MP4 for local browser review."""
    private_root = private_root.resolve()
    source_lock_path = private_root / "experiment" / "source-lock.json"
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    output_dir = private_root / "review"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in source_lock.get("test", {}).get("halves", []):
        half = int(item["half"])
        source = _safe_inside(Path(item["media_path"]), private_root / "raw", "soccer source media")
        source_sha = sha256_file(source)
        if source_sha != item.get("media_sha256"):
            raise ValueError(f"source hash mismatch before review-media build for opaque half {half}")
        output = output_dir / f"half-{half}-silent.mp4"
        temporary = output_dir / f"half-{half}-silent.partial.mp4"
        command = [
            str(ffmpeg.resolve()),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        subprocess.run(command, check=True)
        temporary.replace(output)
        rows.append(
            {
                "half": half,
                "filename": output.name,
                "source_media_sha256": source_sha,
                "sha256": sha256_file(output),
                "duration_seconds": float(item["duration_seconds"]),
                "audio_streams": 0,
                "video_codec": "copy_of_source_h264",
            }
        )
    receipt = {
        "schema_version": "soccermaster-longform-browser-review-v1",
        "privacy": "Private loopback-only review derivatives; do not redistribute.",
        "halves": rows,
    }
    (output_dir / "review-derivative-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt
