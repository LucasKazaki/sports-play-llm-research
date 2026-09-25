"""Neutral adapter for the sealed FootballMaster long-form JSONL index.

This module has no dependency on another sport engine. It verifies the sealed
football artifacts, optionally asks a loopback language model to expand a coach
query, ranks only saved visual reports, and returns playable source bindings.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import query_capabilities as query_caps


DEFAULT_OUTPUT = Path("artifacts/footballmaster/longform-v2")
DEFAULT_ENDPOINT = "http://127.0.0.1:1240/v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
EVENT_TYPES = (
    "pass_play",
    "run_play",
    "kick_play",
    "penalty_or_officiating",
    "turnover",
    "scoring",
    "pre_snap",
    "post_play",
    "replay",
    "stoppage",
    "unknown",
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
    asset_id: str
    route: str
    path: Path
    sha256: str
    duration_seconds: float
    license_spdxish: str | None
    source_page_url: str | None


@dataclass(frozen=True)
class FootballContext:
    output_root: Path
    entries: tuple[Mapping[str, Any], ...]
    media_by_window: Mapping[str, MediaBinding]
    media_routes: Mapping[str, MediaBinding]
    verification: Mapping[str, Any]
    metrics: Mapping[str, Any]
    model: str
    endpoint: str
    coverage: Mapping[str, Any] = field(default_factory=dict)


def _union_seconds(rows: Sequence[Mapping[str, Any]]) -> float:
    total = 0.0
    for game_id in sorted({str(row.get("game_id")) for row in rows}):
        intervals = sorted(
            (
                float(row.get("start_seconds", 0.0)),
                float(row.get("start_seconds", 0.0)) + float(row.get("duration_seconds", 0.0)),
            )
            for row in rows
            if str(row.get("game_id")) == game_id
        )
        if not intervals:
            continue
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                total += end - start
                start, end = next_start, next_end
        total += end - start
    return round(total, 3)


def _safe_media(project_root: Path, relative: str, allowed_root: Path) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("media path must be project-relative")
    resolved = (project_root / raw).resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError as error:
        raise ValueError("media path escaped the football media root") from error
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _verify_required_seal(output_root: Path, required: Sequence[str]) -> Mapping[str, Any]:
    seal_path = output_root / "prediction-seal.json"
    if not seal_path.is_file():
        raise FileNotFoundError(seal_path)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    files = seal.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("prediction seal file map is invalid")
    for relative in required:
        expected = files.get(relative)
        path = output_root / relative
        if not isinstance(expected, str) or sha256_file(path) != expected:
            raise ValueError(f"sealed football artifact mismatch: {relative}")
    if canonical_hash(files) != seal.get("root_hash"):
        raise ValueError("prediction seal root hash mismatch")
    return seal


def load_context(
    output_root: Path,
    *,
    project_root: Path,
    endpoint: str = DEFAULT_ENDPOINT,
    model: str = DEFAULT_MODEL,
) -> FootballContext:
    ensure_loopback_endpoint(endpoint)
    output_root = output_root.resolve()
    project_root = project_root.resolve()
    try:
        output_root.relative_to(project_root)
    except ValueError as error:
        raise ValueError("football output root must remain inside the project") from error
    required = (
        "protocol.json",
        "frozen-test-config.json",
        "report-metrics.json",
        "football-search-index.jsonl",
        "football-search-index-receipt.json",
        "frozen-query-results.json",
        "weak-visual-probe-receipt.json",
    )
    for relative in (*required, "prediction-seal.json", "verification-receipt.json"):
        if not (output_root / relative).is_file():
            raise FileNotFoundError(output_root / relative)
    verification = json.loads((output_root / "verification-receipt.json").read_text(encoding="utf-8"))
    if verification.get("status") != "pass":
        raise ValueError("football long-form verification receipt is not passing")
    _verify_required_seal(output_root, required)
    index_path = output_root / "football-search-index.jsonl"
    index_receipt = json.loads((output_root / "football-search-index-receipt.json").read_text(encoding="utf-8"))
    if index_receipt.get("index_sha256") != sha256_file(index_path):
        raise ValueError("football search index hash mismatch")
    entries = tuple(json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if len(entries) != index_receipt.get("entry_count") or len(entries) != 36:
        raise ValueError("football search index must contain exactly 36 frozen test windows")
    if {entry.get("split") for entry in entries} != {"test"}:
        raise ValueError("football demo index contains non-test windows")
    if len({entry.get("game_id") for entry in entries}) != 2:
        raise ValueError("football demo index must cover two held-out games")
    if {entry.get("duration_seconds") for entry in entries} != {30, 60, 120}:
        raise ValueError("football demo index lost a frozen duration")

    dataset_root = project_root / "data" / "public" / "footballmaster-v2"
    dataset_receipt = json.loads((dataset_root / "verification-receipt.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((dataset_root / "source-manifest.json").read_text(encoding="utf-8"))
    if dataset_receipt.get("checks", {}).get("five_hour_duration_gate") != "pass":
        raise ValueError("football source corpus is not verified at five hours")
    assets = {item["asset_id"]: item for item in source_manifest.get("assets", [])}
    media_root = dataset_root / "media"
    bindings: dict[str, MediaBinding] = {}
    media_by_window: dict[str, MediaBinding] = {}
    media_routes: dict[str, MediaBinding] = {}
    for entry in entries:
        window_id = str(entry.get("window_id", ""))
        media_relative = str(entry.get("media_path", ""))
        asset_id = Path(media_relative).stem
        asset = assets.get(asset_id)
        if asset is None:
            raise ValueError(f"search entry has no rights manifest asset: {asset_id}")
        if asset_id not in bindings:
            media_path = _safe_media(project_root, media_relative, media_root)
            actual_hash = sha256_file(media_path)
            if actual_hash != entry.get("media_sha256") or actual_hash != asset.get("downloaded_sha256"):
                raise ValueError(f"football media hash mismatch: {asset_id}")
            route = f"/media/football/{asset_id}"
            bindings[asset_id] = MediaBinding(
                asset_id=asset_id,
                route=route,
                path=media_path,
                sha256=actual_hash,
                duration_seconds=float(asset["observed_duration_seconds"]),
                license_spdxish=asset.get("license_spdxish"),
                source_page_url=asset.get("canonical_page_url"),
            )
            media_routes[route] = bindings[asset_id]
        media_by_window[window_id] = bindings[asset_id]
    metrics = json.loads((output_root / "report-metrics.json").read_text(encoding="utf-8"))
    protocol = json.loads((output_root / "protocol.json").read_text(encoding="utf-8"))
    window_manifest_path = output_root / "window-manifest.jsonl"
    expected_window_hash = protocol.get("files", {}).get("window_manifest_sha256")
    if not window_manifest_path.is_file() or sha256_file(window_manifest_path) != expected_window_hash:
        raise ValueError("football window manifest does not match the sealed protocol")
    all_windows = tuple(
        json.loads(line) for line in window_manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    coverage_by_split = {}
    for split in ("train", "valid", "test"):
        split_rows = tuple(row for row in all_windows if row.get("split") == split)
        coverage_by_split[split] = {
            "window_count": len(split_rows),
            "nominal_window_seconds": round(sum(float(row["duration_seconds"]) for row in split_rows), 3),
            "unique_sampled_seconds": _union_seconds(split_rows),
        }
    test_assets = {Path(str(entry["media_path"])).stem for entry in entries}
    coverage = {
        "corpus_duration_seconds": round(float(protocol["dataset_duration_hours"]) * 3600.0, 4),
        "corpus_duration_hours": float(protocol["dataset_duration_hours"]),
        "all_window_count": len(all_windows),
        "all_nominal_window_seconds": round(sum(float(row["duration_seconds"]) for row in all_windows), 3),
        "all_unique_sampled_seconds": _union_seconds(all_windows),
        "test_source_program_seconds": round(
            sum(float(assets[asset_id]["observed_duration_seconds"]) for asset_id in test_assets), 4
        ),
        "by_split": coverage_by_split,
        "dense_entire_game_index": False,
    }
    return FootballContext(
        output_root=output_root,
        entries=entries,
        media_by_window=media_by_window,
        media_routes=media_routes,
        verification=verification,
        metrics=metrics,
        model=model,
        endpoint=endpoint,
        coverage=coverage,
    )


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _bm25(entries: Sequence[Mapping[str, Any]], query: str, limit: int) -> list[tuple[float, Mapping[str, Any]]]:
    documents = [_tokens(str(entry.get("search_text", ""))) for entry in entries]
    query_terms = _tokens(query)
    if not documents or not query_terms:
        return []
    document_frequency = Counter(term for document in documents for term in set(document))
    average_length = sum(len(document) for document in documents) / len(documents)
    scored = []
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
    query_caps.check_query(query, "football")
    ensure_loopback_endpoint(endpoint)
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "football_search_terms",
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
                    "Translate a coach's American-football film-search request into short visual-report search terms. "
                    "Do not answer the query and do not invent a player, team, game, or result."
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
        event_types = [item for item in parsed.get("event_types", []) if item in EVENT_TYPES][:6]
        query_caps.validate_participant_terms(query, search_terms, "football")
        if not search_terms and not event_types:
            raise ValueError("query model returned no usable terms")
        return {
            "source": "local_query_llm",
            "requested_model": model,
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
            "search_terms": [query.strip()],
            "event_types": [],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "raw_interpretation": raw_content,
            "error": f"{type(error).__name__}: {error}",
        }


def _frame_relative(frame_id: str, duration_seconds: float) -> float | None:
    match = re.fullmatch(r"F(\d{2})", frame_id)
    if not match:
        return None
    index = int(match.group(1))
    if index < 0 or index >= 8:
        return None
    return (index + 0.5) * duration_seconds / 8.0


def _clock(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def search_context(
    context: FootballContext,
    query: str,
    *,
    limit: int = 12,
    use_query_llm: bool = True,
) -> dict[str, Any]:
    query_caps.check_query(query, "football")
    interpretation = (
        interpret_query(query, endpoint=context.endpoint, model=context.model)
        if use_query_llm
        else {
            "source": "deterministic_literal_fallback",
            "requested_model": context.model,
            "latency_ms": 0,
            "search_terms": [query],
            "event_types": [],
            "error": "query LLM disabled",
        }
    )
    expanded = " ".join([query, *interpretation["search_terms"], *interpretation["event_types"]])
    ranked = _bm25(context.entries, expanded, limit)
    results = []
    for score, entry in ranked:
        report = entry["report"]
        window_id = str(entry["window_id"])
        binding = context.media_by_window[window_id]
        start = float(entry["start_seconds"])
        duration = float(entry["duration_seconds"])
        events = report.get("events", [])
        event_types = sorted({event.get("event_type") for event in events if isinstance(event, dict)})
        participants = sorted(
            {
                str(actor)
                for event in events
                if isinstance(event, dict)
                for actor in event.get("actors_visible", [])
            }
        )
        evidence = []
        for event in events:
            if not isinstance(event, dict):
                continue
            for frame_id in event.get("evidence_frame_ids", []):
                relative = _frame_relative(str(frame_id), duration)
                if relative is not None:
                    evidence.append(
                        {
                            "frame_id": frame_id,
                            "relative_s": round(start + relative, 3),
                            "source_timestamp_s": round(start + relative, 3),
                            "clock": _clock(start + relative),
                        }
                    )
        uncertainty_items = [
            str(item)
            for event in events
            if isinstance(event, dict)
            for item in event.get("uncertainties", [])
            if str(item).strip()
        ]
        if report.get("abstain"):
            uncertainty_text = "Model abstained"
            if report.get("abstention_reason"):
                uncertainty_text += f": {report['abstention_reason']}"
        elif uncertainty_items:
            uncertainty_text = "; ".join(dict.fromkeys(uncertainty_items))
        else:
            uncertainty_text = "Uncalibrated silent-frame report; human review required."
        results.append(
            {
                "event_id": window_id,
                "window_id": window_id,
                "match_id": entry["game_id"],
                "clip_id": binding.asset_id,
                "source_id": entry["game_id"],
                "split": "test",
                "start_s": start,
                "end_s": start + duration,
                "relative_start_s": start,
                "relative_end_s": start + duration,
                "source_start_s": start,
                "source_end_s": start + duration,
                "match_clock": f"{_clock(start)}–{_clock(start + duration)}",
                "clip_url": binding.route,
                "confidence": report.get("confidence"),
                "score": score,
                "event_types": event_types,
                "primary_action": events[0].get("action") if events else None,
                "participants": participants,
                "evidence_frames": evidence,
                "phase_of_play": event_types[0] if event_types else "unknown",
                "field_areas": sorted(
                    {event.get("field_context") for event in events if isinstance(event, dict) and event.get("field_context")}
                ),
                "outcome": "; ".join(
                    str(event.get("outcome")) for event in events if isinstance(event, dict) and event.get("outcome")
                ),
                "detailed_description": report.get("window_summary"),
                "coaching_relevance": ", ".join(report.get("coach_search_terms", [])),
                "coaching_tags": report.get("coach_search_terms", []),
                "uncertainty": uncertainty_text,
                "abstain": bool(report.get("abstain")),
                "abstention_reason": report.get("abstention_reason"),
                "attribution": {
                    "report_origin": "saved_silent_frame_vlm_report",
                    "optional_vlm_fields": sorted(report.keys()),
                    "deterministic_fields": ["query_expansion_validation", "BM25_ranking", "time_projection"],
                    "audio_fields": [],
                    "source_label_fields": [],
                    "boundary": "All event semantics come from the sealed silent-frame VLM report; ranking and time projection are deterministic.",
                },
                "license_spdxish": binding.license_spdxish,
                "source_page_url": binding.source_page_url,
            }
        )
    return {
        "query": query,
        "interpretation": interpretation,
        "results": results,
        "result_count": len(results),
        "ranking_note": "Local query-LM expansion plus deterministic BM25 over sealed silent-frame VLM reports; no audio, labels, or source metadata enter model inference.",
    }
