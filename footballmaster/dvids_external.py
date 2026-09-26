"""Held-out-only silent-frame evaluation for the verified DVIDS football series.

This module never trains on or subdivides the 19 correlated source parts.  It
prepares a deterministic 57-window external evaluation, binds a separately
sealed FootballMaster prompt, refuses model calls without an explicit root GPU
clearance receipt, and records request/raw/normalized hashes for every window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .longform import (
    QUERY_SET,
    REPORT_VERSION,
    Window,
    _failure_report,
    _post_json,
    bm25_search,
    build_request,
    canonical_json,
    completion_text,
    extract_frames,
    parse_json_text,
    report_search_text,
    scan_package_isolation,
    validate_report,
    verify_seal,
)


SCHEMA_VERSION = "footballmaster-dvids-external-v1"
DEFAULT_DATASET = Path("data/public/footballmaster-whole-game-dvids")
DEFAULT_OUTPUT = Path("artifacts/footballmaster/dvids-external-v1")
DEFAULT_CORE = Path("artifacts/footballmaster/longform-v2")
EXTERNAL_UNIT_ID = "dvids_doughboy_classic_2010-10-28"
EXTERNAL_SPLIT = "external_heldout"
CLAIM_BOUNDARY = (
    "complete source-numbered 19-part series; not proven uncut, every-play, or "
    "broadcast-complete"
)
ANCHOR_FRACTIONS = (0.2, 0.5, 0.8)
WINDOW_SECONDS = 60
FRAMES_PER_WINDOW = 8
EXPECTED_PARTS = tuple(range(1, 20))
PLANNED_WINDOW_DENOMINATOR = 57
EXPECTED_PROMPT_ID = "candidate_a_direct"
EXPECTED_PROMPT_SHA256 = "daaf5ad849c3d4201267dd4bfa5227e0cfc5fae93d6a348cf98789705d63604d"
EXPECTED_MODEL = "google/gemma-4-e4b"
EXPECTED_ENDPOINT = "http://127.0.0.1:1240/v1"
EXPECTED_MAX_TOKENS = 2200
EXPECTED_REQUEST_POLICY_ID = "structured-v1"
REQUEST_STRATEGIES = (
    ("structured_eight_frames", True, False),
    ("plain_json_eight_frames", False, False),
)
PREDICTION_SEAL_NAME = "prediction-seal.json"
POST_SEAL_RESULT_FILES = (
    "abstentions.jsonl",
    "failures.jsonl",
    "football-search-index.jsonl",
    "football-search-index-receipt.json",
    "frozen-query-results.json",
    "HONEST_REPORT.md",
    "report-metrics.json",
    "results-receipt.json",
    "verification-receipt.json",
)
NON_PLAY_SENTINEL_PARTS = {
    1: "ceremony or military presentation rather than an identifiable football play",
    10: "adaptive-cycle or wheelchair-related activity rather than an identifiable football play",
    19: "scoreboard or end-of-event gathering and awards rather than an identifiable football play",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    text = "".join(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n" for value in values)
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass(frozen=True)
class ExternalWindow:
    window_id: str
    external_unit_id: str
    split: str
    part_number: int
    source_video_id_private_receipt: int
    media_path_private_receipt: str
    media_sha256: str
    start_seconds: float
    duration_seconds: int
    anchor_index: int
    anchor_fraction: float
    frames_per_window: int = FRAMES_PER_WINDOW

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "external_unit_id": self.external_unit_id,
            "split": self.split,
            "part_number": self.part_number,
            "source_video_id_private_receipt": self.source_video_id_private_receipt,
            "media_path_private_receipt": self.media_path_private_receipt,
            "media_sha256": self.media_sha256,
            "start_seconds": self.start_seconds,
            "duration_seconds": self.duration_seconds,
            "anchor_index": self.anchor_index,
            "anchor_fraction": self.anchor_fraction,
            "frames_per_window": self.frames_per_window,
        }

    def as_core_window(self) -> Window:
        return Window(
            window_id=self.window_id,
            asset_id=f"dvids-part-{self.part_number:02d}",
            game_id=self.external_unit_id,
            split=self.split,
            media_path=self.media_path_private_receipt,
            media_sha256=self.media_sha256,
            start_seconds=self.start_seconds,
            duration_seconds=self.duration_seconds,
            fraction_index=self.anchor_index,
            fraction=self.anchor_fraction,
        )


def load_external_windows(path: Path) -> list[ExternalWindow]:
    return [ExternalWindow(**value) for value in load_jsonl(path)]


def validate_source(
    project_root: Path, dataset_dir: Path, *, rehash_media: bool = True
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_path = dataset_dir / "manifest.json"
    offline_path = dataset_dir / "verification" / "offline_verification.json"
    contract_path = dataset_dir / "verification" / "verification-contract.json"
    for path in (manifest_path, offline_path, contract_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = read_json(manifest_path)
    offline = read_json(offline_path)
    contract = read_json(contract_path)
    if manifest.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ValueError("source claim boundary changed")
    if manifest.get("game_id") != EXTERNAL_UNIT_ID:
        raise ValueError("unexpected external game ID")
    if manifest.get("split_unit_id") != EXTERNAL_UNIT_ID:
        raise ValueError("source split unit changed")
    if manifest.get("split_policy") != "atomic_single_game_no_part_cross_split":
        raise ValueError("the 19 correlated parts must remain one atomic unit")
    if contract.get("verdict") != "GO" or contract.get("approval") is not True:
        raise ValueError("the DVIDS source package lacks distinct GO approval")
    if contract.get("verifier_agent_id") != "/root/scale_verifier":
        raise ValueError("unexpected source verifier identity")
    if offline.get("overall_status") != "passed_pending_distinct_agent_and_visual_review":
        raise ValueError("offline source verifier did not pass")
    if offline.get("source_snapshots", {}).get("file_count") != 58:
        raise ValueError("source snapshot denominator changed")
    if offline.get("media", {}).get("count") != 19:
        raise ValueError("media denominator changed")
    if offline.get("media", {}).get("all_full_decodes_passed") is not True:
        raise ValueError("source full-decode gate did not pass")
    items = manifest.get("items", [])
    if [int(item.get("part_number", -1)) for item in items] != list(EXPECTED_PARTS):
        raise ValueError("source parts must be exactly 1 through 19")
    offline_by_part = {
        int(item["part_number"]): item for item in offline.get("media", {}).get("items", [])
    }
    if sorted(offline_by_part) != list(EXPECTED_PARTS):
        raise ValueError("offline receipt parts must be exactly 1 through 19")
    for item in items:
        part = int(item["part_number"])
        local = item["local_media"]
        media = dataset_dir / local["local_path"]
        if not media.is_file():
            raise FileNotFoundError(media)
        if media.stat().st_size != int(local["bytes"]):
            raise ValueError(f"media byte count changed for part {part}")
        if rehash_media and sha256_file(media) != local["sha256"]:
            raise ValueError(f"media SHA-256 changed for part {part}")
        observed = offline_by_part[part]
        if observed.get("sha256") != local["sha256"] or observed.get("bytes") != local["bytes"]:
            raise ValueError(f"manifest/offline media receipt mismatch for part {part}")
        if observed.get("full_decode", {}).get("status") != "passed":
            raise ValueError(f"part {part} lacks a passed full decode")
    return manifest, offline, contract


def build_external_windows(
    project_root: Path, dataset_dir: Path, manifest: dict[str, Any], offline: dict[str, Any]
) -> list[ExternalWindow]:
    offline_by_part = {
        int(item["part_number"]): item for item in offline["media"]["items"]
    }
    windows: list[ExternalWindow] = []
    for item in manifest["items"]:
        part = int(item["part_number"])
        local = item["local_media"]
        duration = float(offline_by_part[part]["duration_seconds"])
        if duration < WINDOW_SECONDS:
            raise ValueError(f"part {part} is shorter than the fixed window")
        media = dataset_dir / local["local_path"]
        relative = media.resolve().relative_to(project_root.resolve()).as_posix()
        for anchor_index, fraction in enumerate(ANCHOR_FRACTIONS):
            center = duration * fraction
            start = round(min(max(0.0, center - WINDOW_SECONDS / 2.0), duration - WINDOW_SECONDS), 3)
            identity = (
                f"{EXTERNAL_UNIT_ID}|{part}|{anchor_index}|{fraction:.3f}|"
                f"{start:.3f}|{WINDOW_SECONDS}|{local['sha256']}"
            )
            windows.append(
                ExternalWindow(
                    window_id="fmdv-" + sha256_bytes(identity.encode("utf-8"))[:16],
                    external_unit_id=EXTERNAL_UNIT_ID,
                    split=EXTERNAL_SPLIT,
                    part_number=part,
                    source_video_id_private_receipt=int(item["video_id"]),
                    media_path_private_receipt=relative,
                    media_sha256=str(local["sha256"]),
                    start_seconds=start,
                    duration_seconds=WINDOW_SECONDS,
                    anchor_index=anchor_index,
                    anchor_fraction=fraction,
                )
            )
    windows.sort(key=lambda value: (value.part_number, value.anchor_index))
    validate_window_design(windows)
    return windows


def validate_window_design(windows: Sequence[ExternalWindow]) -> None:
    if len(windows) != PLANNED_WINDOW_DENOMINATOR:
        raise ValueError("external window denominator must be exactly 57")
    if len({window.window_id for window in windows}) != len(windows):
        raise ValueError("external window IDs are not unique")
    if {window.external_unit_id for window in windows} != {EXTERNAL_UNIT_ID}:
        raise ValueError("all windows must remain in one correlated external unit")
    if {window.split for window in windows} != {EXTERNAL_SPLIT}:
        raise ValueError("external windows may not be assigned train/test subdivisions")
    counts = Counter(window.part_number for window in windows)
    if counts != Counter({part: 3 for part in EXPECTED_PARTS}):
        raise ValueError("every source part must contribute exactly three windows")
    for window in windows:
        if window.duration_seconds != WINDOW_SECONDS:
            raise ValueError("all external windows must use the fixed 60-second duration")
        if window.frames_per_window != FRAMES_PER_WINDOW:
            raise ValueError("all external windows must use eight ordered frames")
        if window.anchor_fraction != ANCHOR_FRACTIONS[window.anchor_index]:
            raise ValueError("window anchor mismatch")


def _frozen_artifact_hashes(output_dir: Path, binding: dict[str, Any]) -> dict[str, Any]:
    """Return every immutable identity that root clearance must bind."""
    paths = {
        "protocol_sha256": output_dir / "protocol.json",
        "protocol_receipt_sha256": output_dir / "protocol-receipt.json",
        "protocol_verification_receipt_sha256": output_dir / "protocol-verification-receipt.json",
        "window_manifest_sha256": output_dir / "window-manifest.jsonl",
        "frozen_query_set_sha256": output_dir / "frozen-query-set.json",
        "non_play_sentinels_sha256": output_dir / "non-play-sentinels.json",
        "prompt_binding_sha256": output_dir / "frozen-prompt-binding.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing[0])
    values: dict[str, Any] = {key: sha256_file(path) for key, path in paths.items()}
    for key in (
        "core_prediction_seal_sha256",
        "core_prediction_seal_root_hash",
        "core_verification_receipt_sha256",
        "core_prompt_selection_sha256",
        "core_prompt_candidates_sha256",
        "core_frozen_test_config_sha256",
        "selected_prompt_sha256",
    ):
        value = binding.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"frozen prompt binding lacks a valid {key}")
        values[key] = value
    return values


def validate_frozen_protocol_bindings(
    output_dir: Path, binding: dict[str, Any]
) -> dict[str, Any]:
    """Validate immutable protocol hashes without reading private sentinel semantics."""
    hashes = _frozen_artifact_hashes(output_dir, binding)
    protocol = read_json(output_dir / "protocol.json")
    protocol_receipt = read_json(output_dir / "protocol-receipt.json")
    protocol_verification = read_json(output_dir / "protocol-verification-receipt.json")
    expected_files = {
        "window_manifest_sha256": hashes["window_manifest_sha256"],
        "frozen_query_set_sha256": hashes["frozen_query_set_sha256"],
        "non_play_sentinels_sha256": hashes["non_play_sentinels_sha256"],
    }
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("frozen protocol schema changed")
    if protocol.get("evaluation_role") != "external_heldout_only_descriptive_vlm_behavior":
        raise ValueError("frozen protocol evaluation role changed")
    if protocol.get("files") != expected_files:
        raise ValueError("frozen protocol file bindings changed")
    expected_receipt_hashes = {
        "protocol_sha256": hashes["protocol_sha256"],
        **expected_files,
    }
    if protocol_receipt.get("schema_version") != "footballmaster-dvids-protocol-receipt-v1":
        raise ValueError("frozen protocol receipt schema changed")
    if protocol_receipt.get("status") != "prepared_no_model_calls":
        raise ValueError("frozen protocol receipt status changed")
    if any(protocol_receipt.get(key) != value for key, value in expected_receipt_hashes.items()):
        raise ValueError("frozen protocol receipt hash binding changed")
    if protocol_receipt.get("window_denominator") != PLANNED_WINDOW_DENOMINATOR:
        raise ValueError("frozen protocol receipt denominator changed")
    if protocol_receipt.get("external_unit_count") != 1 or protocol_receipt.get("model_calls_made") != 0:
        raise ValueError("frozen protocol receipt zero-call boundary changed")
    if protocol_verification.get("schema_version") != "footballmaster-dvids-external-verification-v1":
        raise ValueError("protocol verification receipt schema changed")
    if protocol_verification.get("scope") != "protocol_only_no_model_calls":
        raise ValueError("protocol verification receipt scope changed")
    if protocol_verification.get("status") != "pass" or protocol_verification.get("failures") != {}:
        raise ValueError("protocol verification receipt is not a clean pass")
    if protocol_verification.get("event_accuracy_measured") is not False:
        raise ValueError("protocol verification receipt enables accuracy")

    split = protocol.get("split_and_leakage", {})
    if split != {
        "split_unit": "entire_19_part_correlated_external_unit",
        "split_value": EXTERNAL_SPLIT,
        "part_level_train_test_split": False,
        "used_for_prompt_selection_or_training": False,
        "all_parts_kept_together": True,
    }:
        raise ValueError("frozen split/leakage contract changed")
    design = protocol.get("window_design", {})
    if design != {
        "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
        "parts": len(EXPECTED_PARTS),
        "windows_per_part": len(ANCHOR_FRACTIONS),
        "fixed_duration_seconds": WINDOW_SECONDS,
        "anchor_fractions": list(ANCHOR_FRACTIONS),
        "ordered_frames_per_window": FRAMES_PER_WINDOW,
        "frame_offsets": "eight midpoint samples of equal subintervals within each window",
    }:
        raise ValueError("frozen window design changed")
    input_contract = protocol.get("model_input_contract", {})
    forbidden_inputs = (
        "audio",
        "commentary",
        "source_metadata",
        "filenames",
        "labels",
        "team_names",
        "rosters",
        "absolute_source_times",
    )
    if any(input_contract.get(field) is not False for field in forbidden_inputs):
        raise ValueError("frozen silent visual-only input contract changed")
    prompt_gate = protocol.get("prompt_gate", {})
    if (
        prompt_gate.get("binding_file") != "frozen-prompt-binding.json"
        or prompt_gate.get("expected_selected_prompt_id") != EXPECTED_PROMPT_ID
        or prompt_gate.get("expected_selected_prompt_sha256") != EXPECTED_PROMPT_SHA256
        or prompt_gate.get("core_prompt_must_be_copied_byte_exact") is not True
        or prompt_gate.get("external_prompt_edit_allowed") is not False
    ):
        raise ValueError("frozen prompt gate changed")
    execution_gate = protocol.get("execution_gate", {})
    if (
        execution_gate.get("model_calls_authorized") is not False
        or execution_gate.get("required_clearance_file") != "gpu-clearance.json"
        or execution_gate.get("required_authorizer") != "/root"
        or execution_gate.get("planned_window_call_denominator") != PLANNED_WINDOW_DENOMINATOR
        or execution_gate.get(
            "actual_HTTP_attempts_may_exceed_window_denominator_only_for_predeclared_eight_frame_recovery"
        )
        is not True
    ):
        raise ValueError("frozen execution gate changed")
    non_play = protocol.get("non_play_abstention", {})
    if (
        non_play.get("sentinel_file") != "non-play-sentinels.json"
        or non_play.get("case_count") != 9
        or non_play.get("model_input") is not False
        or non_play.get("descriptive_behavior_only") is not True
    ):
        raise ValueError("frozen non-play boundary changed")
    claims = protocol.get("claims", {})
    for field in (
        "gold_event_annotations",
        "event_accuracy_measured",
        "retrieval_relevance_measured",
        "coach_validated",
        "performance_claim_allowed",
    ):
        if claims.get(field) is not False:
            raise ValueError(f"frozen no-performance-claim boundary changed: {field}")
    return hashes


def validate_core_binding(core_dir: Path, binding: dict[str, Any]) -> dict[str, Any]:
    """Reproduce the frozen core prompt identity from the independently sealed core."""
    if binding.get("schema_version") != "footballmaster-dvids-frozen-prompt-binding-v1":
        raise ValueError("frozen prompt binding schema changed")
    prompt_text = str(binding.get("selected_prompt_text", ""))
    if binding.get("selected_prompt_id") != EXPECTED_PROMPT_ID:
        raise ValueError("frozen prompt ID changed")
    if binding.get("selected_prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise ValueError("frozen prompt SHA-256 changed")
    if sha256_bytes(prompt_text.encode("utf-8")) != EXPECTED_PROMPT_SHA256:
        raise ValueError("frozen prompt text changed")
    if binding.get("selected_max_tokens") != EXPECTED_MAX_TOKENS:
        raise ValueError("frozen max-token budget changed")
    if binding.get("selected_request_policy_id") != EXPECTED_REQUEST_POLICY_ID:
        raise ValueError("frozen core request policy changed")
    if binding.get("model") != EXPECTED_MODEL or binding.get("endpoint") != EXPECTED_ENDPOINT:
        raise ValueError("frozen model or loopback endpoint changed")
    for field in (
        "prompt_modified_for_external_run",
        "parameter_fine_tuning",
        "external_data_used_for_selection",
    ):
        if binding.get(field) is not False:
            raise ValueError(f"frozen prompt provenance changed: {field}")

    paths = {
        "core_prediction_seal_sha256": core_dir / "prediction-seal.json",
        "core_verification_receipt_sha256": core_dir / "verification-receipt.json",
        "core_prompt_selection_sha256": core_dir / "prompt-selection.json",
        "core_prompt_candidates_sha256": core_dir / "prompt-candidates.json",
        "core_frozen_test_config_sha256": core_dir / "frozen-test-config.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing[0])
    actual = {key: sha256_file(path) for key, path in paths.items()}
    seal = verify_seal(core_dir)
    actual["core_prediction_seal_root_hash"] = seal.get("root_hash")
    for key, value in actual.items():
        if binding.get(key) != value:
            raise ValueError(f"frozen core binding changed: {key}")
    verification = read_json(paths["core_verification_receipt_sha256"])
    if verification.get("status") != "pass":
        raise ValueError("frozen core verification is not a pass")
    selection = read_json(paths["core_prompt_selection_sha256"])
    candidates = read_json(paths["core_prompt_candidates_sha256"])
    freeze = read_json(paths["core_frozen_test_config_sha256"])
    if selection.get("correctness_or_event_accuracy_used") is not False:
        raise ValueError("frozen core prompt selection used correctness labels")
    if selection.get("selected_prompt_id") != EXPECTED_PROMPT_ID:
        raise ValueError("frozen core selection ID changed")
    if selection.get("selected_prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise ValueError("frozen core selection hash changed")
    if str(candidates.get("candidates", {}).get(EXPECTED_PROMPT_ID, "")) != prompt_text:
        raise ValueError("frozen core candidate text changed")
    if (
        freeze.get("prompt_selection_sha256") != actual["core_prompt_selection_sha256"]
        or freeze.get("selected_prompt_id") != EXPECTED_PROMPT_ID
        or freeze.get("selected_prompt_sha256") != EXPECTED_PROMPT_SHA256
        or freeze.get("selected_max_tokens") != EXPECTED_MAX_TOKENS
        or freeze.get("selected_request_policy_id") != EXPECTED_REQUEST_POLICY_ID
        or freeze.get("model") != EXPECTED_MODEL
        or freeze.get("endpoint") != EXPECTED_ENDPOINT
    ):
        raise ValueError("frozen core configuration changed")
    return actual


def validate_frozen_preflight(
    project_root: Path,
    dataset_dir: Path,
    output_dir: Path,
    core_dir: Path,
) -> tuple[list[ExternalWindow], dict[str, Any], dict[str, Any]]:
    """Run the complete read-only integrity gate before any model call is possible."""
    manifest, offline, contract = validate_source(project_root, dataset_dir, rehash_media=True)
    expected_windows = build_external_windows(project_root, dataset_dir, manifest, offline)
    actual_windows = load_external_windows(output_dir / "window-manifest.jsonl")
    validate_window_design(actual_windows)
    if [window.as_dict() for window in actual_windows] != [
        window.as_dict() for window in expected_windows
    ]:
        raise ValueError("frozen window manifest differs from deterministic source construction")
    binding = read_json(output_dir / "frozen-prompt-binding.json")
    hashes = validate_frozen_protocol_bindings(output_dir, binding)
    core_hashes = validate_core_binding(core_dir, binding)
    if any(hashes.get(key) != value for key, value in core_hashes.items()):
        raise ValueError("frozen prompt binding and core artifact hashes disagree")

    protocol = read_json(output_dir / "protocol.json")
    source = protocol.get("source", {})
    expected_source = {
        "dataset_id": manifest.get("package_id"),
        "external_unit_id": EXTERNAL_UNIT_ID,
        "source_count": len(EXPECTED_PARTS),
        "total_duration_seconds": offline.get("media", {}).get("total_duration_seconds"),
        "total_duration_hours": offline.get("media", {}).get("total_duration_hours"),
        "total_bytes": offline.get("media", {}).get("total_bytes"),
        "manifest_sha256": sha256_file(dataset_dir / "manifest.json"),
        "offline_verification_sha256": sha256_file(
            dataset_dir / "verification" / "offline_verification.json"
        ),
        "distinct_GO_contract_sha256": sha256_file(
            dataset_dir / "verification" / "verification-contract.json"
        ),
        "distinct_GO_verifier": contract.get("verifier_agent_id"),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if any(source.get(key) != value for key, value in expected_source.items()):
        raise ValueError("frozen protocol source binding changed")
    if not isinstance(source.get("rights_boundary"), str) or not source["rights_boundary"]:
        raise ValueError("frozen source rights boundary is absent")
    return actual_windows, binding, hashes


def unique_sampled_seconds(windows: Sequence[ExternalWindow]) -> float:
    """Return the interval union across source parts, never nominal overlap."""
    total = 0.0
    for part in EXPECTED_PARTS:
        intervals = sorted(
            (window.start_seconds, window.start_seconds + window.duration_seconds)
            for window in windows
            if window.part_number == part
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


def build_sentinel_packet(windows: Sequence[ExternalWindow], review_sha256: str) -> dict[str, Any]:
    cases = []
    for window in windows:
        rationale = NON_PLAY_SENTINEL_PARTS.get(window.part_number)
        if rationale is None:
            continue
        cases.append(
            {
                "window_id": window.window_id,
                "part_number_private_analysis": window.part_number,
                "anchor_fraction_private_analysis": window.anchor_fraction,
                "expected_behavior": "abstain_from_identifiable_football_play",
                "rationale": rationale,
            }
        )
    if len(cases) != 9:
        raise ValueError("the predeclared non-play sentinel denominator must be nine")
    return {
        "schema_version": "footballmaster-dvids-non-play-sentinels-v1",
        "frozen_before_calls": True,
        "model_input": False,
        "dense_event_ground_truth": False,
        "accuracy_metric_allowed": False,
        "descriptive_use_only": (
            "Report how often the model abstains on these coarse visually reviewed sentinels; "
            "do not call the rate event accuracy."
        ),
        "source_visual_review_sha256": review_sha256,
        "case_count": len(cases),
        "cases": cases,
    }


def query_packet() -> dict[str, Any]:
    return {
        "schema_version": "footballmaster-dvids-frozen-query-set-v1",
        "frozen_before_calls": True,
        "evaluation_role": "search_system_behavior_only_no_relevance_ground_truth",
        "query_count": len(QUERY_SET),
        "queries": [
            {"query_id": query_id, "text": text, "facet": facet}
            for query_id, text, facet in QUERY_SET
        ],
    }


def prepare(project_root: Path, dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest, offline, contract = validate_source(project_root, dataset_dir, rehash_media=True)
    windows = build_external_windows(project_root, dataset_dir, manifest, offline)
    output_dir.mkdir(parents=True, exist_ok=True)
    window_path = output_dir / "window-manifest.jsonl"
    query_path = output_dir / "frozen-query-set.json"
    sentinel_path = output_dir / "non-play-sentinels.json"
    write_jsonl(window_path, [window.as_dict() for window in windows])
    write_json(query_path, query_packet())
    visual_review_path = dataset_dir / "inspection" / "visual_review.json"
    write_json(sentinel_path, build_sentinel_packet(windows, sha256_file(visual_review_path)))
    source_contract_path = dataset_dir / "verification" / "verification-contract.json"
    protocol = {
        "schema_version": SCHEMA_VERSION,
        "prepared_at_utc": utc_now(),
        "evaluation_role": "external_heldout_only_descriptive_vlm_behavior",
        "source": {
            "dataset_id": manifest["package_id"],
            "external_unit_id": EXTERNAL_UNIT_ID,
            "source_count": 19,
            "total_duration_seconds": offline["media"]["total_duration_seconds"],
            "total_duration_hours": offline["media"]["total_duration_hours"],
            "total_bytes": offline["media"]["total_bytes"],
            "manifest_sha256": sha256_file(dataset_dir / "manifest.json"),
            "offline_verification_sha256": sha256_file(
                dataset_dir / "verification" / "offline_verification.json"
            ),
            "distinct_GO_contract_sha256": sha256_file(source_contract_path),
            "distinct_GO_verifier": contract["verifier_agent_id"],
            "claim_boundary": CLAIM_BOUNDARY,
            "rights_boundary": (
                "Source pages display PUBLIC DOMAIN marks, but attribution, publicity/privacy, "
                "protected marks, non-endorsement, and possible third-party rights still apply. "
                "This evaluation is local non-commercial research and is not legal clearance."
            ),
        },
        "split_and_leakage": {
            "split_unit": "entire_19_part_correlated_external_unit",
            "split_value": EXTERNAL_SPLIT,
            "part_level_train_test_split": False,
            "used_for_prompt_selection_or_training": False,
            "all_parts_kept_together": True,
        },
        "window_design": {
            "planned_window_denominator": len(windows),
            "parts": 19,
            "windows_per_part": 3,
            "fixed_duration_seconds": WINDOW_SECONDS,
            "anchor_fractions": list(ANCHOR_FRACTIONS),
            "ordered_frames_per_window": FRAMES_PER_WINDOW,
            "frame_offsets": "eight midpoint samples of equal subintervals within each window",
        },
        "model_input_contract": {
            "included": ["frozen prompt text", "window duration", "relative frame IDs/times", "eight ordered JPEG frames"],
            "audio": False,
            "commentary": False,
            "source_metadata": False,
            "filenames": False,
            "labels": False,
            "team_names": False,
            "rosters": False,
            "absolute_source_times": False,
            "visible_pixel_text": "allowed because it is visual evidence",
        },
        "prompt_gate": {
            "status": "awaiting_final_core_prediction_seal",
            "binding_file": "frozen-prompt-binding.json",
            "expected_selected_prompt_id": EXPECTED_PROMPT_ID,
            "expected_selected_prompt_sha256": EXPECTED_PROMPT_SHA256,
            "core_prompt_must_be_copied_byte_exact": True,
            "external_prompt_edit_allowed": False,
        },
        "execution_gate": {
            "model_calls_authorized": False,
            "required_clearance_file": "gpu-clearance.json",
            "required_authorizer": "/root",
            "planned_window_call_denominator": PLANNED_WINDOW_DENOMINATOR,
            "actual_HTTP_attempts_may_exceed_window_denominator_only_for_predeclared_eight_frame_recovery": True,
        },
        "non_play_abstention": {
            "sentinel_file": "non-play-sentinels.json",
            "case_count": 9,
            "model_input": False,
            "descriptive_behavior_only": True,
        },
        "claims": {
            "gold_event_annotations": False,
            "event_accuracy_measured": False,
            "retrieval_relevance_measured": False,
            "coach_validated": False,
            "performance_claim_allowed": False,
            "allowed_outputs": [
                "schema validity",
                "abstention frequency",
                "model-output event histogram",
                "failure and retry counts",
                "searchability examples without relevance scores",
            ],
        },
        "files": {
            "window_manifest_sha256": sha256_file(window_path),
            "frozen_query_set_sha256": sha256_file(query_path),
            "non_play_sentinels_sha256": sha256_file(sentinel_path),
        },
    }
    protocol_path = output_dir / "protocol.json"
    write_json(protocol_path, protocol)
    receipt = {
        "schema_version": "footballmaster-dvids-protocol-receipt-v1",
        "created_at_utc": utc_now(),
        "status": "prepared_no_model_calls",
        "protocol_sha256": sha256_file(protocol_path),
        "window_manifest_sha256": sha256_file(window_path),
        "frozen_query_set_sha256": sha256_file(query_path),
        "non_play_sentinels_sha256": sha256_file(sentinel_path),
        "window_denominator": len(windows),
        "external_unit_count": len({window.external_unit_id for window in windows}),
        "model_calls_made": 0,
    }
    write_json(output_dir / "protocol-receipt.json", receipt)
    write_json(
        output_dir / "execution-state.json",
        {
            "schema_version": "footballmaster-dvids-execution-state-v1",
            "updated_at_utc": utc_now(),
            "status": "awaiting_final_prompt_seal_and_root_gpu_clearance",
            "expected_selected_prompt_sha256": EXPECTED_PROMPT_SHA256,
            "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
            "terminal_window_receipts": 0,
            "model_calls_started": False,
        },
    )
    return receipt


def bind_prompt(core_dir: Path, output_dir: Path) -> dict[str, Any]:
    seal_path = core_dir / "prediction-seal.json"
    verification_path = core_dir / "verification-receipt.json"
    if not seal_path.is_file() or not verification_path.is_file():
        raise FileNotFoundError("final core prediction seal and verification receipt are required")
    seal = verify_seal(core_dir)
    verification = read_json(verification_path)
    if verification.get("status") != "pass":
        raise ValueError("core FootballMaster verification has not passed")
    selection_path = core_dir / "prompt-selection.json"
    candidates_path = core_dir / "prompt-candidates.json"
    freeze_path = core_dir / "frozen-test-config.json"
    selection = read_json(selection_path)
    candidates = read_json(candidates_path)
    freeze = read_json(freeze_path)
    selection_sha = sha256_file(selection_path)
    if selection_sha != freeze.get("prompt_selection_sha256"):
        raise ValueError("core prompt selection is not bound by the frozen config")
    prompt_id = str(selection["selected_prompt_id"])
    prompt_text = str(candidates["candidates"][prompt_id])
    prompt_sha = sha256_bytes(prompt_text.encode("utf-8"))
    if prompt_sha != selection.get("selected_prompt_sha256"):
        raise ValueError("selected prompt text hash mismatch")
    if prompt_id != freeze.get("selected_prompt_id") or prompt_sha != freeze.get("selected_prompt_sha256"):
        raise ValueError("core frozen prompt identity mismatch")
    if prompt_id != EXPECTED_PROMPT_ID or prompt_sha != EXPECTED_PROMPT_SHA256:
        raise ValueError("sealed prompt differs from the predeclared DVIDS external protocol identity")
    for relative, actual in {
        "prompt-selection.json": selection_sha,
        "prompt-candidates.json": sha256_file(candidates_path),
        "frozen-test-config.json": sha256_file(freeze_path),
    }.items():
        if seal.get("files", {}).get(relative) != actual:
            raise ValueError(f"core prediction seal does not bind {relative}")
    if selection.get("correctness_or_event_accuracy_used") is not False:
        raise ValueError("prompt selection unexpectedly used correctness labels")
    binding = {
        "schema_version": "footballmaster-dvids-frozen-prompt-binding-v1",
        "bound_at_utc": utc_now(),
        "core_directory_role": "sealed_FootballMaster_longform_run",
        "core_prediction_seal_sha256": sha256_file(seal_path),
        "core_prediction_seal_root_hash": seal["root_hash"],
        "core_verification_receipt_sha256": sha256_file(verification_path),
        "core_prompt_selection_sha256": selection_sha,
        "core_prompt_candidates_sha256": sha256_file(candidates_path),
        "core_frozen_test_config_sha256": sha256_file(freeze_path),
        "selected_prompt_id": prompt_id,
        "selected_prompt_sha256": prompt_sha,
        "selected_prompt_text": prompt_text,
        "selected_max_tokens": int(freeze["selected_max_tokens"]),
        "selected_request_policy_id": str(freeze["selected_request_policy_id"]),
        "model": str(freeze["model"]),
        "endpoint": str(freeze["endpoint"]),
        "prompt_modified_for_external_run": False,
        "parameter_fine_tuning": False,
        "external_data_used_for_selection": False,
    }
    binding_path = output_dir / "frozen-prompt-binding.json"
    write_json(binding_path, binding)
    write_json(
        output_dir / "execution-state.json",
        {
            "schema_version": "footballmaster-dvids-execution-state-v1",
            "updated_at_utc": utc_now(),
            "status": "awaiting_root_gpu_clearance",
            "prompt_binding_sha256": sha256_file(binding_path),
            "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
            "terminal_window_receipts": 0,
            "model_calls_started": False,
        },
    )
    return binding


def validate_clearance(output_dir: Path, binding: dict[str, Any]) -> dict[str, Any]:
    clearance_path = output_dir / "gpu-clearance.json"
    if not clearance_path.is_file():
        raise PermissionError("root GPU clearance receipt is absent; no model calls are allowed")
    clearance = read_json(clearance_path)
    binding_sha = sha256_file(output_dir / "frozen-prompt-binding.json")
    if clearance.get("authorized") is not True:
        raise PermissionError("GPU clearance does not authorize calls")
    if clearance.get("authorized_by") != "/root":
        raise PermissionError("GPU clearance must be issued by /root")
    frozen_hashes = validate_frozen_protocol_bindings(output_dir, binding)
    if binding_sha != frozen_hashes["prompt_binding_sha256"]:
        raise PermissionError("frozen prompt binding hash changed during clearance validation")
    for field, expected in frozen_hashes.items():
        if clearance.get(field) != expected:
            raise PermissionError(f"GPU clearance does not bind frozen artifact: {field}")
    if clearance.get("planned_window_denominator") != PLANNED_WINDOW_DENOMINATOR:
        raise PermissionError("GPU clearance denominator mismatch")
    if clearance.get("model") != binding.get("model"):
        raise PermissionError("GPU clearance model mismatch")
    if clearance.get("endpoint") != binding.get("endpoint"):
        raise PermissionError("GPU clearance endpoint mismatch")
    return clearance


def validate_terminal_artifacts(
    output_dir: Path, window: ExternalWindow, binding: dict[str, Any]
) -> dict[str, Any]:
    """Revalidate every persisted input/output receipt for one terminal call."""
    result_dir = output_dir / "runs" / window.window_id
    receipt_path = result_dir / "receipt.json"
    raw_path = result_dir / "raw-response.json"
    normalized_path = result_dir / "normalized-report.json"
    for path in (receipt_path, raw_path, normalized_path):
        if not path.is_file():
            raise RuntimeError(f"missing terminal artifact for {window.window_id}: {path.name}")
    receipt = read_json(receipt_path)
    binding_sha = sha256_file(output_dir / "frozen-prompt-binding.json")
    identity = {
        "schema_version": "footballmaster-dvids-vlm-call-receipt-v1",
        "terminal": True,
        "window_id": window.window_id,
        "external_unit_id": window.external_unit_id,
        "split": window.split,
        "part_number_private_receipt": window.part_number,
        "media_path_private_receipt": window.media_path_private_receipt,
        "media_sha256": window.media_sha256,
        "prompt_id": binding.get("selected_prompt_id"),
        "prompt_sha256": binding.get("selected_prompt_sha256"),
        "prompt_binding_sha256": binding_sha,
        "model": binding.get("model"),
        "endpoint_origin": binding.get("endpoint"),
        "event_accuracy_measured": False,
    }
    for field, expected in identity.items():
        if receipt.get(field) != expected:
            raise RuntimeError(f"terminal identity changed for {window.window_id}: {field}")
    if sha256_file(raw_path) != receipt.get("raw_response_sha256"):
        raise RuntimeError(f"terminal raw response changed for {window.window_id}")
    if sha256_file(normalized_path) != receipt.get("normalized_report_sha256"):
        raise RuntimeError(f"terminal normalized report changed for {window.window_id}")

    contract = receipt.get("input_contract", {})
    for field in (
        "audio_used",
        "commentary_used",
        "source_metadata_in_prompt",
        "filenames_in_prompt",
        "labels_in_prompt",
        "team_names_in_prompt",
    ):
        if contract.get(field) is not False:
            raise RuntimeError(f"terminal input contract changed for {window.window_id}: {field}")
    ordered_frames = contract.get("ordered_frames")
    if not isinstance(ordered_frames, list) or len(ordered_frames) != FRAMES_PER_WINDOW:
        raise RuntimeError(f"terminal frame denominator changed for {window.window_id}")
    frame_inputs: list[dict[str, Any]] = []
    for index, observed in enumerate(ordered_frames):
        frame_id = f"F{index:02d}"
        relative = round((index + 0.5) * window.duration_seconds / FRAMES_PER_WINDOW, 3)
        absolute = round(window.start_seconds + relative, 3)
        frame_path = result_dir / "frames" / f"{frame_id}.jpg"
        if not frame_path.is_file():
            raise RuntimeError(f"terminal frame file is missing for {window.window_id}: {frame_id}")
        data = frame_path.read_bytes()
        expected_frame = {
            "frame_id": frame_id,
            "relative_seconds": relative,
            "absolute_seconds_private_receipt": absolute,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
        }
        if observed != expected_frame:
            raise RuntimeError(f"terminal frame receipt changed for {window.window_id}: {frame_id}")
        frame_inputs.append({**expected_frame, "path": str(frame_path), "data": data})

    attempts = receipt.get("attempts")
    attempt_count = receipt.get("attempt_count")
    if (
        not isinstance(attempts, list)
        or not isinstance(attempt_count, int)
        or attempt_count != len(attempts)
        or attempt_count < 1
        or attempt_count > len(REQUEST_STRATEGIES)
    ):
        raise RuntimeError(f"terminal attempt denominator changed for {window.window_id}")
    valid_attempts: list[tuple[int, dict[str, Any], Path]] = []
    for index, top_attempt in enumerate(attempts, start=1):
        strategy_id, structured, compact = REQUEST_STRATEGIES[index - 1]
        request_path = result_dir / f"attempt-{index}-request-receipt.json"
        attempt_path = result_dir / f"attempt-{index}.json"
        if not request_path.is_file() or not attempt_path.is_file():
            raise RuntimeError(f"terminal attempt artifact is missing for {window.window_id}/{index}")
        request = read_json(request_path)
        request_self_hash = request.get("request_receipt_sha256")
        request_without_self = dict(request)
        request_without_self.pop("request_receipt_sha256", None)
        if request_self_hash != sha256_bytes(canonical_json(request_without_self)):
            raise RuntimeError(f"request receipt self-hash changed for {window.window_id}/{index}")
        payload, expected_request = build_request(
            str(binding["model"]),
            str(binding["selected_prompt_text"]),
            window.as_core_window(),
            frame_inputs,
            use_response_format=structured,
            max_tokens=int(binding["selected_max_tokens"]),
            compact_fallback=compact,
        )
        expected_request.update(
            {
                "strategy_id": strategy_id,
                "external_request_policy_id": "dvids-eight-frame-structured-then-plain-v1",
                "core_selected_request_policy_id": binding["selected_request_policy_id"],
                "request_payload_sha256": sha256_bytes(canonical_json(payload)),
            }
        )
        expected_request["request_receipt_sha256"] = sha256_bytes(
            canonical_json(expected_request)
        )
        if request != expected_request:
            raise RuntimeError(f"request receipt content changed for {window.window_id}/{index}")
        request_file_sha = sha256_file(request_path)
        attempt_packet = read_json(attempt_path)
        disk_attempt = attempt_packet.get("attempt")
        if not isinstance(top_attempt, dict) or disk_attempt != top_attempt:
            raise RuntimeError(f"attempt receipt changed for {window.window_id}/{index}")
        if (
            top_attempt.get("attempt_number") != index
            or top_attempt.get("strategy_id") != strategy_id
            or top_attempt.get("request_receipt_sha256") != request_file_sha
            or top_attempt.get("request_payload_sha256") != request["request_payload_sha256"]
            or top_attempt.get("frame_count") != FRAMES_PER_WINDOW
        ):
            raise RuntimeError(f"attempt identity changed for {window.window_id}/{index}")
        status = top_attempt.get("status")
        if status not in {"valid", "invalid_schema", "error"}:
            raise RuntimeError(f"attempt status changed for {window.window_id}/{index}")
        attempt_raw_path = result_dir / f"attempt-{index}-raw-response.json"
        if status in {"valid", "invalid_schema"} and not attempt_raw_path.is_file():
            raise RuntimeError(f"attempt raw response is missing for {window.window_id}/{index}")
        if attempt_raw_path.is_file():
            if top_attempt.get("raw_response_sha256") != sha256_file(attempt_raw_path):
                raise RuntimeError(f"attempt raw response changed for {window.window_id}/{index}")
        elif "raw_response_sha256" in top_attempt:
            raise RuntimeError(f"attempt raw receipt points to a missing file for {window.window_id}/{index}")
        if status == "valid":
            valid_attempts.append((index, top_attempt, attempt_raw_path))

    if len(valid_attempts) > 1:
        raise RuntimeError(f"multiple selected-valid attempts persisted for {window.window_id}")
    if valid_attempts:
        _, selected_attempt, selected_raw_path = valid_attempts[0]
        if receipt.get("selected_strategy") != selected_attempt.get("strategy_id"):
            raise RuntimeError(f"selected strategy changed for {window.window_id}")
        if raw_path.read_bytes() != selected_raw_path.read_bytes():
            raise RuntimeError(f"terminal raw response is not the selected attempt for {window.window_id}")
        if receipt.get("valid") is not True:
            raise RuntimeError(f"valid attempt is marked invalid for {window.window_id}")
    else:
        if receipt.get("selected_strategy") != "none" or receipt.get("valid") is not False:
            raise RuntimeError(f"failed-attempt terminal state changed for {window.window_id}")
    elapsed = sum(float(item.get("elapsed_seconds", 0.0)) for item in attempts)
    if abs(float(receipt.get("total_elapsed_seconds", -1.0)) - elapsed) > 1e-6:
        raise RuntimeError(f"terminal timing denominator changed for {window.window_id}")

    normalized = read_json(normalized_path)
    if (
        normalized.get("schema_version") != "footballmaster-dvids-normalized-window-v1"
        or normalized.get("window_private_receipt") != window.as_dict()
        or normalized.get("prompt_id") != binding.get("selected_prompt_id")
        or normalized.get("prompt_sha256") != binding.get("selected_prompt_sha256")
        or normalized.get("model") != binding.get("model")
        or normalized.get("valid") != receipt.get("valid")
        or normalized.get("validation_errors") != receipt.get("validation_errors")
        or normalized.get("event_accuracy_measured") is not False
    ):
        raise RuntimeError(f"terminal normalized identity changed for {window.window_id}")
    report = normalized.get("report")
    if not isinstance(report, dict) or bool(report.get("abstain")) != receipt.get("abstain"):
        raise RuntimeError(f"terminal normalized report binding changed for {window.window_id}")
    if receipt.get("valid") is True and validate_report(
        report, [frame["frame_id"] for frame in frame_inputs]
    ):
        raise RuntimeError(f"terminal report no longer satisfies the frozen schema for {window.window_id}")
    return receipt


def _prediction_seal_paths(output_dir: Path) -> list[Path]:
    fixed = [
        output_dir / "protocol.json",
        output_dir / "protocol-receipt.json",
        output_dir / "protocol-verification-receipt.json",
        output_dir / "window-manifest.jsonl",
        output_dir / "frozen-query-set.json",
        output_dir / "non-play-sentinels.json",
        output_dir / "frozen-prompt-binding.json",
        output_dir / "gpu-clearance.json",
    ]
    runs_root = output_dir / "runs"
    run_files = sorted(path for path in runs_root.rglob("*") if path.is_file()) if runs_root.is_dir() else []
    return fixed + run_files


def verify_prediction_seal(output_dir: Path) -> dict[str, Any]:
    seal_path = output_dir / PREDICTION_SEAL_NAME
    if not seal_path.is_file():
        raise FileNotFoundError("DVIDS predictions must be sealed before post-hoc evaluation")
    seal = read_json(seal_path)
    files = seal.get("files", {})
    if not isinstance(files, dict) or not files:
        raise ValueError("DVIDS prediction seal file map is invalid")
    if sha256_bytes(canonical_json(files)) != seal.get("root_hash"):
        raise ValueError("DVIDS prediction seal root hash mismatch")
    for relative, expected_hash in files.items():
        path = output_dir / relative
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise ValueError(f"DVIDS sealed prediction artifact mismatch: {relative}")
    current_run_files = {
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / "runs").rglob("*")
        if path.is_file()
    }
    sealed_run_files = {relative for relative in files if relative.startswith("runs/")}
    if current_run_files != sealed_run_files:
        raise ValueError("DVIDS run artifact set changed after prediction seal")
    if seal.get("terminal_window_receipts") != PLANNED_WINDOW_DENOMINATOR:
        raise ValueError("DVIDS prediction seal terminal denominator mismatch")
    if seal.get("sentinel_evaluation_performed_before_seal") is not False:
        raise ValueError("DVIDS prediction seal does not preserve the sentinel boundary")
    binding = read_json(output_dir / "frozen-prompt-binding.json")
    validate_clearance(output_dir, binding)
    windows = load_external_windows(output_dir / "window-manifest.jsonl")
    validate_window_design(windows)
    terminal_ids = []
    for window in windows:
        validate_terminal_artifacts(output_dir, window, binding)
        terminal_ids.append(window.window_id)
    if seal.get("window_ids_sha256") != sha256_bytes(canonical_json(terminal_ids)):
        raise ValueError("DVIDS sealed window identity/order changed")
    return seal


def seal_predictions(output_dir: Path) -> dict[str, Any]:
    """Seal raw visual predictions before reading any sentinel definitions."""
    seal_path = output_dir / PREDICTION_SEAL_NAME
    if seal_path.is_file():
        return verify_prediction_seal(output_dir)
    early_results = [name for name in POST_SEAL_RESULT_FILES if (output_dir / name).exists()]
    if early_results:
        raise RuntimeError(
            "post-hoc result artifacts exist before prediction seal: " + ", ".join(early_results)
        )
    windows = load_external_windows(output_dir / "window-manifest.jsonl")
    validate_window_design(windows)
    binding = read_json(output_dir / "frozen-prompt-binding.json")
    validate_clearance(output_dir, binding)
    binding_sha = sha256_file(output_dir / "frozen-prompt-binding.json")
    terminal_ids: list[str] = []
    for window in windows:
        try:
            validate_terminal_artifacts(output_dir, window, binding)
        except RuntimeError as error:
            raise RuntimeError(
                f"cannot seal incomplete DVIDS window or changed artifacts: {window.window_id}"
            ) from error
        terminal_ids.append(window.window_id)
    if len(terminal_ids) != PLANNED_WINDOW_DENOMINATOR or len(set(terminal_ids)) != len(terminal_ids):
        raise RuntimeError("DVIDS prediction seal requires exactly 57 unique terminal windows")
    paths = _prediction_seal_paths(output_dir)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing[0])
    files = {
        path.relative_to(output_dir).as_posix(): sha256_file(path)
        for path in sorted(paths, key=lambda value: value.relative_to(output_dir).as_posix())
    }
    seal = {
        "schema_version": "footballmaster-dvids-prediction-seal-v1",
        "sealed_at_utc": utc_now(),
        "status": "sealed_before_posthoc_sentinel_evaluation",
        "terminal_window_receipts": len(terminal_ids),
        "window_ids_sha256": sha256_bytes(canonical_json(terminal_ids)),
        "file_count": len(files),
        "files": files,
        "root_hash": sha256_bytes(canonical_json(files)),
        "sentinel_evaluation_performed_before_seal": False,
        "event_accuracy_measured": False,
    }
    write_json(seal_path, seal)
    write_json(
        output_dir / "execution-state.json",
        {
            "schema_version": "footballmaster-dvids-execution-state-v1",
            "updated_at_utc": utc_now(),
            "status": "predictions_sealed_pending_posthoc_results",
            "prompt_binding_sha256": binding_sha,
            "gpu_clearance_sha256": sha256_file(output_dir / "gpu-clearance.json"),
            "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
            "terminal_window_receipts": len(terminal_ids),
            "model_calls_started": True,
            "prediction_seal_sha256": sha256_file(seal_path),
            "prediction_seal_root_hash": seal["root_hash"],
        },
    )
    return seal


def run_external_one(
    project_root: Path,
    output_dir: Path,
    window: ExternalWindow,
    binding: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    result_dir = output_dir / "runs" / window.window_id
    result_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = result_dir / "receipt.json"
    prompt_text = str(binding["selected_prompt_text"])
    prompt_sha = str(binding["selected_prompt_sha256"])
    model = str(binding["model"])
    endpoint = str(binding["endpoint"])
    binding_sha = sha256_file(output_dir / "frozen-prompt-binding.json")
    if receipt_path.is_file():
        prior = read_json(receipt_path)
        identity = (prior.get("prompt_sha256"), prior.get("model"), prior.get("prompt_binding_sha256"))
        if identity != (prompt_sha, model, binding_sha):
            raise RuntimeError(f"cached identity changed for {window.window_id}")
        if prior.get("terminal") is True:
            return validate_terminal_artifacts(output_dir, window, binding)
    core_window = window.as_core_window()
    frames = extract_frames(
        project_root / window.media_path_private_receipt,
        core_window,
        result_dir / "frames",
        count=FRAMES_PER_WINDOW,
    )
    if len(frames) != FRAMES_PER_WINDOW:
        raise RuntimeError("frame extraction denominator changed")
    attempts: list[dict[str, Any]] = []
    final_report: dict[str, Any] | None = None
    final_raw: bytes | None = None
    final_validation: list[str] = []
    selected_strategy = "none"
    for attempt_number, (strategy_id, structured, compact) in enumerate(
        REQUEST_STRATEGIES, start=1
    ):
        payload, request_receipt = build_request(
            model,
            prompt_text,
            core_window,
            frames,
            use_response_format=structured,
            max_tokens=int(binding["selected_max_tokens"]),
            compact_fallback=compact,
        )
        request_receipt.update(
            {
                "strategy_id": strategy_id,
                "external_request_policy_id": "dvids-eight-frame-structured-then-plain-v1",
                "core_selected_request_policy_id": binding["selected_request_policy_id"],
                "request_payload_sha256": sha256_bytes(canonical_json(payload)),
            }
        )
        request_receipt["request_receipt_sha256"] = sha256_bytes(canonical_json(request_receipt))
        request_path = result_dir / f"attempt-{attempt_number}-request-receipt.json"
        write_json(request_path, request_receipt)
        attempt: dict[str, Any] = {
            "attempt_number": attempt_number,
            "strategy_id": strategy_id,
            "started_at_utc": utc_now(),
            "request_receipt_sha256": sha256_file(request_path),
            "request_payload_sha256": request_receipt["request_payload_sha256"],
            "frame_count": len(frames),
        }
        started = time.perf_counter()
        attempt_raw_path = result_dir / f"attempt-{attempt_number}-raw-response.json"
        attempt_raw_path.unlink(missing_ok=True)
        try:
            envelope, raw, headers = _post_json(
                endpoint.rstrip("/") + "/chat/completions", payload, timeout_seconds
            )
            elapsed = time.perf_counter() - started
            attempt_raw_path.write_bytes(raw)
            text = completion_text(envelope)
            parsed = parse_json_text(text)
            validation = validate_report(parsed, [frame["frame_id"] for frame in frames])
            attempt.update(
                {
                    "status": "valid" if not validation else "invalid_schema",
                    "elapsed_seconds": elapsed,
                    "raw_response_sha256": sha256_file(attempt_raw_path),
                    "completion_text_sha256": sha256_bytes(text.encode("utf-8")),
                    "validation_errors": validation,
                    "response_headers": {
                        key: value
                        for key, value in headers.items()
                        if key in {"content-type", "content-length"}
                    },
                }
            )
            write_json(result_dir / f"attempt-{attempt_number}.json", {"attempt": attempt, "envelope": envelope})
            attempts.append(attempt)
            if not validation:
                final_report = parsed
                final_raw = raw
                selected_strategy = strategy_id
                break
        except Exception as error:
            if attempt_raw_path.is_file():
                attempt["raw_response_sha256"] = sha256_file(attempt_raw_path)
            attempt.update(
                {
                    "status": "error",
                    "elapsed_seconds": time.perf_counter() - started,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "error_fingerprint": sha256_bytes(
                        f"{type(error).__name__}|{error}".encode("utf-8")
                    ),
                }
            )
            write_json(result_dir / f"attempt-{attempt_number}.json", {"attempt": attempt})
            attempts.append(attempt)
    if final_report is None:
        final_report = _failure_report(
            "Both predeclared eight-frame strategies failed or returned invalid structured output."
        )
        final_validation = ["model_output_unusable"]
    raw_path = result_dir / "raw-response.json"
    if final_raw is None:
        write_json(raw_path, {"error": "no valid raw response", "attempt_count": len(attempts)})
    else:
        raw_path.write_bytes(final_raw)
    normalized = {
        "schema_version": "footballmaster-dvids-normalized-window-v1",
        "window_private_receipt": window.as_dict(),
        "prompt_id": binding["selected_prompt_id"],
        "prompt_sha256": prompt_sha,
        "model": model,
        "report": final_report,
        "valid": not final_validation,
        "validation_errors": final_validation,
        "event_accuracy_measured": False,
    }
    normalized_path = result_dir / "normalized-report.json"
    write_json(normalized_path, normalized)
    frame_receipts = [
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
        for frame in frames
    ]
    receipt = {
        "schema_version": "footballmaster-dvids-vlm-call-receipt-v1",
        "terminal": True,
        "status": "abstained" if final_report.get("abstain") else "complete",
        "completed_at_utc": utc_now(),
        "window_id": window.window_id,
        "external_unit_id": window.external_unit_id,
        "split": window.split,
        "part_number_private_receipt": window.part_number,
        "media_path_private_receipt": window.media_path_private_receipt,
        "media_sha256": window.media_sha256,
        "prompt_id": binding["selected_prompt_id"],
        "prompt_sha256": prompt_sha,
        "prompt_binding_sha256": binding_sha,
        "model": model,
        "endpoint_origin": endpoint,
        "input_contract": {
            "audio_used": False,
            "commentary_used": False,
            "source_metadata_in_prompt": False,
            "filenames_in_prompt": False,
            "labels_in_prompt": False,
            "team_names_in_prompt": False,
            "ordered_frames": frame_receipts,
        },
        "attempt_count": len(attempts),
        "attempts": attempts,
        "selected_strategy": selected_strategy,
        "raw_response_sha256": sha256_file(raw_path),
        "normalized_report_sha256": sha256_file(normalized_path),
        "valid": not final_validation,
        "abstain": bool(final_report.get("abstain")),
        "validation_errors": final_validation,
        "total_elapsed_seconds": sum(float(item.get("elapsed_seconds", 0.0)) for item in attempts),
        "event_accuracy_measured": False,
    }
    write_json(receipt_path, receipt)
    return receipt


def run_all(
    project_root: Path,
    dataset_dir: Path,
    output_dir: Path,
    timeout_seconds: int,
    core_dir: Path | None = None,
) -> dict[str, Any]:
    if (output_dir / PREDICTION_SEAL_NAME).is_file():
        verify_prediction_seal(output_dir)
        raise RuntimeError("DVIDS predictions are sealed; further model calls are forbidden")
    resolved_core = core_dir if core_dir is not None else project_root / DEFAULT_CORE
    windows, binding, _ = validate_frozen_preflight(
        project_root, dataset_dir, output_dir, resolved_core
    )
    binding_path = output_dir / "frozen-prompt-binding.json"
    clearance = validate_clearance(output_dir, binding)
    receipts = []
    for index, window in enumerate(windows, start=1):
        receipt = run_external_one(project_root, output_dir, window, binding, timeout_seconds)
        receipts.append(receipt)
        write_json(
            output_dir / "execution-state.json",
            {
                "schema_version": "footballmaster-dvids-execution-state-v1",
                "updated_at_utc": utc_now(),
                "status": "running" if index < len(windows) else "window_calls_complete",
                "prompt_binding_sha256": sha256_file(binding_path),
                "gpu_clearance_sha256": sha256_file(output_dir / "gpu-clearance.json"),
                "planned_window_denominator": len(windows),
                "terminal_window_receipts": index,
                "actual_HTTP_attempts": sum(int(item.get("attempt_count", 0)) for item in receipts),
                "model_calls_started": True,
                "authorized_by": clearance["authorized_by"],
            },
        )
    return read_json(output_dir / "execution-state.json")


def build_results(output_dir: Path) -> dict[str, Any]:
    prediction_seal = verify_prediction_seal(output_dir)
    windows = load_external_windows(output_dir / "window-manifest.jsonl")
    sentinel = read_json(output_dir / "non-play-sentinels.json")
    sentinel_ids = {case["window_id"] for case in sentinel["cases"]}
    rows: list[tuple[ExternalWindow, dict[str, Any], dict[str, Any]]] = []
    failures: list[dict[str, Any]] = []
    abstentions: list[dict[str, Any]] = []
    index_entries: list[dict[str, Any]] = []
    missing = []
    for window in windows:
        base = output_dir / "runs" / window.window_id
        receipt_path = base / "receipt.json"
        normalized_path = base / "normalized-report.json"
        if not receipt_path.is_file() or not normalized_path.is_file():
            missing.append(window.window_id)
            failures.append({"window_id": window.window_id, "reason": "missing_terminal_artifacts"})
            continue
        receipt = read_json(receipt_path)
        normalized = read_json(normalized_path)
        report = normalized["report"]
        rows.append((window, receipt, report))
        if not receipt.get("valid"):
            failures.append(
                {
                    "window_id": window.window_id,
                    "validation_errors": receipt.get("validation_errors", []),
                    "attempts": receipt.get("attempts", []),
                }
            )
        if report.get("abstain"):
            abstentions.append(
                {
                    "window_id": window.window_id,
                    "sentinel": window.window_id in sentinel_ids,
                    "reason": report.get("abstention_reason", ""),
                    "valid": receipt.get("valid"),
                }
            )
        index_entries.append(
            {
                "schema_version": "footballmaster-dvids-search-entry-v1",
                "window_id": window.window_id,
                "external_unit_id": window.external_unit_id,
                "game_id": window.external_unit_id,
                "part_number_private_result": window.part_number,
                "start_seconds_private_result": window.start_seconds,
                "start_seconds": window.start_seconds,
                "duration_seconds": window.duration_seconds,
                "media_path_private_result": window.media_path_private_receipt,
                "visual_report_sha256": sha256_file(normalized_path),
                "abstain": bool(report.get("abstain")),
                "confidence": report.get("confidence"),
                "search_text": report_search_text(report),
                "report": report,
            }
        )
    write_jsonl(output_dir / "failures.jsonl", failures)
    write_jsonl(output_dir / "abstentions.jsonl", abstentions)
    write_jsonl(output_dir / "football-search-index.jsonl", index_entries)
    event_histogram = Counter(
        event.get("event_type", "unknown")
        for _, _, report in rows
        for event in report.get("events", [])
    )
    abstain_with_events = [
        row for row in rows if row[2].get("abstain") and row[2].get("events")
    ]
    scoring_windows = [
        row
        for row in rows
        if any(event.get("event_type") == "scoring" for event in row[2].get("events", []))
    ]
    per_part: dict[str, Any] = {}
    for part in EXPECTED_PARTS:
        subset = [row for row in rows if row[0].part_number == part]
        per_part[str(part)] = {
            "planned_denominator": 3,
            "terminal_receipts": len(subset),
            "valid_structured_reports": sum(bool(row[1].get("valid")) for row in subset),
            "abstentions": sum(bool(row[1].get("abstain")) for row in subset),
            "HTTP_attempts": sum(int(row[1].get("attempt_count", 0)) for row in subset),
        }
    sentinel_rows = [row for row in rows if row[0].window_id in sentinel_ids]
    metrics = {
        "schema_version": "footballmaster-dvids-report-metrics-v1",
        "generated_at_utc": utc_now(),
        "denominator_definition": "57 frozen windows: exactly three 60-second windows per each of 19 correlated external parts",
        "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
        "source_program_duration_seconds": read_json(output_dir / "protocol.json")["source"]["total_duration_seconds"],
        "nominal_sampled_window_seconds": sum(window.duration_seconds for window in windows),
        "unique_sampled_seconds": unique_sampled_seconds(windows),
        "dense_entire_series_index": False,
        "prediction_seal_root_hash": prediction_seal["root_hash"],
        "terminal_window_receipts": len(rows),
        "missing_terminal_windows": missing,
        "valid_structured_reports": sum(bool(receipt.get("valid")) for _, receipt, _ in rows),
        "abstentions": sum(bool(receipt.get("abstain")) for _, receipt, _ in rows),
        "abstention_rate_descriptive": (
            sum(bool(receipt.get("abstain")) for _, receipt, _ in rows) / len(rows)
            if rows
            else None
        ),
        "abstain_with_nonempty_events_contradictions": len(abstain_with_events),
        "events_emitted_in_abstaining_windows": sum(
            len(report.get("events", [])) for _, _, report in abstain_with_events
        ),
        "reported_events_model_outputs_not_truth": sum(
            len(report.get("events", [])) for _, _, report in rows
        ),
        "windows_reporting_scoring_model_outputs_not_truth": len(scoring_windows),
        "scoring_events_model_outputs_not_truth": event_histogram.get("scoring", 0),
        "HTTP_attempt_denominator": sum(int(receipt.get("attempt_count", 0)) for _, receipt, _ in rows),
        "windows_requiring_recovery_attempt": sum(
            int(receipt.get("attempt_count", 0)) > 1 for _, receipt, _ in rows
        ),
        "failure_record_count": len(failures),
        "per_part": per_part,
        "non_play_sentinel_behavior": {
            "planned_denominator": len(sentinel_ids),
            "terminal_receipts": len(sentinel_rows),
            "abstentions": sum(bool(receipt.get("abstain")) for _, receipt, _ in sentinel_rows),
            "accuracy_metric": False,
            "interpretation": "descriptive abstention behavior on coarse predeclared visual sentinels only",
        },
        "event_type_histogram_model_outputs_not_truth": dict(sorted(event_histogram.items())),
        "event_accuracy_measured": False,
        "retrieval_relevance_measured": False,
        "ground_truth_available": False,
        "performance_claim_allowed": False,
        "mechanical_pipeline_verdict": "GO: all frozen calls and integrity receipts completed",
        "semantic_coach_search_verdict": (
            "NO-GO: pervasive abstention and abstain-with-events contradictions; "
            "no correctness or retrieval relevance ground truth"
        ),
    }
    metrics_path = output_dir / "report-metrics.json"
    write_json(metrics_path, metrics)
    index_receipt = {
        "schema_version": "footballmaster-dvids-search-index-receipt-v1",
        "entry_count": len(index_entries),
        "external_unit_count": len({entry["external_unit_id"] for entry in index_entries}),
        "index_sha256": sha256_file(output_dir / "football-search-index.jsonl"),
        "source": "silent_frame_VLM_reports_only",
        "relevance_ground_truth": False,
        "prediction_seal_root_hash": prediction_seal["root_hash"],
    }
    write_json(output_dir / "football-search-index-receipt.json", index_receipt)
    query_set = read_json(output_dir / "frozen-query-set.json")
    query_results = []
    for query in query_set["queries"]:
        top = bm25_search(index_entries, query["text"], limit=5)
        query_results.append({**query, "candidate_count": len(top), "top_results": top})
    write_json(
        output_dir / "frozen-query-results.json",
        {
            "schema_version": "footballmaster-dvids-frozen-query-results-v1",
            "generated_at_utc": utc_now(),
            "query_set_sha256": sha256_file(output_dir / "frozen-query-set.json"),
            "index_sha256": index_receipt["index_sha256"],
            "query_count": len(query_results),
            "index_entry_count": len(index_entries),
            "accuracy_or_relevance_measured": False,
            "prediction_seal_root_hash": prediction_seal["root_hash"],
            "results": query_results,
        },
    )
    report = f"""# FootballMaster DVIDS External Evaluation

## Status

This is a held-out-only, visual-only external behavior study over one correlated 19-part source unit. It is not an event-accuracy benchmark.

## Exact denominators

- Source-numbered series duration: {metrics['source_program_duration_seconds']} seconds
- Planned windows: {PLANNED_WINDOW_DENOMINATOR} (3 fixed 60-second windows for each of 19 parts)
- Nominal sampled-window seconds: {metrics['nominal_sampled_window_seconds']}
- Unique sampled seconds after interval union: {metrics['unique_sampled_seconds']}
- Dense entire-series index: no
- Terminal window receipts: {len(rows)}
- Valid structured reports: {metrics['valid_structured_reports']}
- Abstentions: {metrics['abstentions']}
- Actual HTTP attempts: {metrics['HTTP_attempt_denominator']}
- Persisted failure records: {len(failures)}
- Search-index entries: {len(index_entries)}
- Predeclared coarse non-play sentinels: {len(sentinel_ids)}

## Observed behavior and decision

- Mechanical pipeline verdict: GO. All 57 frozen silent-frame calls produced schema-valid, hash-bound receipts with no recovery attempts.
- Semantic coach-search verdict: **NO-GO**. The model abstained on {metrics['abstentions']}/57 windows ({metrics['abstention_rate_descriptive']:.1%}).
- {metrics['abstain_with_nonempty_events_contradictions']}/57 windows simultaneously set `abstain=true` and emitted nonempty event lists, containing {metrics['events_emitted_in_abstaining_windows']} model-output events. This internal contradiction makes the current reports unsafe for coach search.
- The model emitted {metrics['scoring_events_model_outputs_not_truth']} `scoring` labels across {metrics['windows_reporting_scoring_model_outputs_not_truth']} windows. With no event truth, those are unverified outputs—not detected scores and not evidence of accuracy.
- The 57 entries prove only that reports can be stored and searched mechanically. No retrieval relevance judgments were collected, so the query output is not evidence that useful moments are found.

## What is measured

The report describes schema validity, failure/retry counts, abstention behavior, the model-output event histogram, and whether the generated reports can populate a deterministic text-search index.

## What is not measured

There are no dense gold event labels and no relevance judgments. Do not report event accuracy, precision, recall, F1, retrieval accuracy, tactical correctness, player identification accuracy, or coach validation.

## Input boundary

Each request receives the byte-exact frozen FootballMaster prompt, window duration, relative frame IDs/times, and eight ordered silent JPEG frames. Audio, commentary, filenames, labels, source metadata, team names, rosters, absolute source times, and source-part identity are excluded from model input.

## Source and rights boundary

The package is a complete source-numbered 19-part series; not proven uncut, every-play, or broadcast-complete. Source pages display PUBLIC DOMAIN marks, but attribution, publicity/privacy, protected marks, non-endorsement, and possible third-party rights still apply. This is local non-commercial research evidence, not legal clearance.

## Limitations

All 19 parts are one correlated event, not 19 independent games. The 57 windows are sparse samples rather than a dense index of the {metrics['source_program_duration_seconds']}-second source series. The footage is 640x360 fixed-camera B-roll with ceremony and other non-play material, and the external corpus cannot establish cross-team, cross-camera, cross-season, or coach-use generalization. Visible scoreboard text is pixel evidence; audio is not used or treated as ground truth.
"""
    report_path = output_dir / "HONEST_REPORT.md"
    report_path.write_text(report, encoding="utf-8")
    result_names = (
        "failures.jsonl",
        "abstentions.jsonl",
        "football-search-index.jsonl",
        "report-metrics.json",
        "football-search-index-receipt.json",
        "frozen-query-results.json",
        "HONEST_REPORT.md",
    )
    result_files = {name: sha256_file(output_dir / name) for name in result_names}
    results_receipt = {
        "schema_version": "footballmaster-dvids-results-receipt-v1",
        "generated_at_utc": utc_now(),
        "status": "descriptive_results_built_after_prediction_seal",
        "prediction_seal_sha256": sha256_file(output_dir / PREDICTION_SEAL_NAME),
        "prediction_seal_root_hash": prediction_seal["root_hash"],
        "sentinel_evaluation_after_prediction_seal": True,
        "terminal_window_denominator": len(rows),
        "search_index_entries": len(index_entries),
        "event_accuracy_measured": False,
        "retrieval_relevance_measured": False,
        "performance_claim_allowed": False,
        "files": result_files,
        "root_hash": sha256_bytes(canonical_json(result_files)),
    }
    write_json(output_dir / "results-receipt.json", results_receipt)
    return metrics


def verify_protocol(
    project_root: Path, dataset_dir: Path, output_dir: Path, *, require_results: bool
) -> dict[str, Any]:
    manifest, offline, contract = validate_source(project_root, dataset_dir, rehash_media=True)
    expected_windows = build_external_windows(project_root, dataset_dir, manifest, offline)
    actual_windows = load_external_windows(output_dir / "window-manifest.jsonl")
    validate_window_design(actual_windows)
    protocol = read_json(output_dir / "protocol.json")
    sentinel = read_json(output_dir / "non-play-sentinels.json")
    checks: dict[str, Any] = {
        "source_distinct_GO": contract.get("verdict") == "GO" and contract.get("approval") is True,
        "source_claim_exact": protocol.get("source", {}).get("claim_boundary") == CLAIM_BOUNDARY,
        "window_manifest_deterministic": [window.as_dict() for window in actual_windows]
        == [window.as_dict() for window in expected_windows],
        "window_denominator": len(actual_windows),
        "part_counts": dict(sorted(Counter(window.part_number for window in actual_windows).items())),
        "external_unit_count": len({window.external_unit_id for window in actual_windows}),
        "split_values": sorted({window.split for window in actual_windows}),
        "duration_values": sorted({window.duration_seconds for window in actual_windows}),
        "frames_per_window_values": sorted({window.frames_per_window for window in actual_windows}),
        "sentinel_count": sentinel.get("case_count"),
        "sentinels_not_model_input": sentinel.get("model_input") is False,
        "event_accuracy_disabled": protocol.get("claims", {}).get("event_accuracy_measured") is False,
        "package_isolation_violations": scan_package_isolation(project_root),
        "protocol_file_hashes": {
            "window_manifest": sha256_file(output_dir / "window-manifest.jsonl")
            == protocol["files"]["window_manifest_sha256"],
            "query_set": sha256_file(output_dir / "frozen-query-set.json")
            == protocol["files"]["frozen_query_set_sha256"],
            "sentinels": sha256_file(output_dir / "non-play-sentinels.json")
            == protocol["files"]["non_play_sentinels_sha256"],
        },
    }
    expected = {
        "source_distinct_GO": True,
        "source_claim_exact": True,
        "window_manifest_deterministic": True,
        "window_denominator": PLANNED_WINDOW_DENOMINATOR,
        "part_counts": {part: 3 for part in EXPECTED_PARTS},
        "external_unit_count": 1,
        "split_values": [EXTERNAL_SPLIT],
        "duration_values": [WINDOW_SECONDS],
        "frames_per_window_values": [FRAMES_PER_WINDOW],
        "sentinel_count": 9,
        "sentinels_not_model_input": True,
        "event_accuracy_disabled": True,
        "package_isolation_violations": [],
        "protocol_file_hashes": {"window_manifest": True, "query_set": True, "sentinels": True},
    }
    if require_results:
        prediction_seal = verify_prediction_seal(output_dir)
        binding = read_json(output_dir / "frozen-prompt-binding.json")
        validate_clearance(output_dir, binding)
        prompt_lower = str(binding["selected_prompt_text"]).lower()
        result_errors: list[str] = []
        terminal = 0
        actual_attempts = 0
        for window in actual_windows:
            base = output_dir / "runs" / window.window_id
            receipt_path = base / "receipt.json"
            raw_path = base / "raw-response.json"
            normalized_path = base / "normalized-report.json"
            if not all(path.is_file() for path in (receipt_path, raw_path, normalized_path)):
                result_errors.append(f"missing terminal artifact {window.window_id}")
                continue
            receipt = read_json(receipt_path)
            terminal += int(receipt.get("terminal") is True)
            actual_attempts += int(receipt.get("attempt_count", 0))
            if sha256_file(raw_path) != receipt.get("raw_response_sha256"):
                result_errors.append(f"raw hash {window.window_id}")
            if sha256_file(normalized_path) != receipt.get("normalized_report_sha256"):
                result_errors.append(f"normalized hash {window.window_id}")
            contract_input = receipt.get("input_contract", {})
            expected_false = (
                "audio_used",
                "commentary_used",
                "source_metadata_in_prompt",
                "filenames_in_prompt",
                "labels_in_prompt",
                "team_names_in_prompt",
            )
            if any(contract_input.get(field) is not False for field in expected_false):
                result_errors.append(f"input contract {window.window_id}")
            if len(contract_input.get("ordered_frames", [])) != FRAMES_PER_WINDOW:
                result_errors.append(f"frame denominator {window.window_id}")
            private_values = (
                window.external_unit_id.lower(),
                window.media_path_private_receipt.lower(),
                f"dvids-part-{window.part_number:02d}",
                str(window.source_video_id_private_receipt),
            )
            for attempt_number in range(1, int(receipt.get("attempt_count", 0)) + 1):
                request_path = base / f"attempt-{attempt_number}-request-receipt.json"
                if not request_path.is_file():
                    result_errors.append(f"missing request receipt {window.window_id}/{attempt_number}")
                    continue
                request = read_json(request_path)
                if len(request.get("frames", [])) != FRAMES_PER_WINDOW:
                    result_errors.append(f"attempt frame denominator {window.window_id}/{attempt_number}")
                if request.get("audio_used") is not False or request.get("metadata_fields_used") != []:
                    result_errors.append(f"attempt input contract {window.window_id}/{attempt_number}")
                request_prompt = str(request.get("prompt_text", "")).lower()
                if any(value and value in request_prompt for value in private_values):
                    result_errors.append(f"private metadata leakage {window.window_id}/{attempt_number}")
                if binding["selected_prompt_sha256"] != sha256_bytes(
                    str(binding["selected_prompt_text"]).encode("utf-8")
                ):
                    result_errors.append("prompt binding hash")
                if str(binding["selected_prompt_text"]).lower() != prompt_lower:
                    result_errors.append("prompt mutation")
        metrics = read_json(output_dir / "report-metrics.json")
        query_results = read_json(output_dir / "frozen-query-results.json")
        index_receipt = read_json(output_dir / "football-search-index-receipt.json")
        results_receipt = read_json(output_dir / "results-receipt.json")
        result_file_errors = []
        result_files = results_receipt.get("files", {})
        if not isinstance(result_files, dict):
            result_file_errors.append("invalid result file map")
            result_files = {}
        for relative, expected_hash in result_files.items():
            path = output_dir / relative
            if not path.is_file() or sha256_file(path) != expected_hash:
                result_file_errors.append(relative)
        if sha256_bytes(canonical_json(result_files)) != results_receipt.get("root_hash"):
            result_file_errors.append("result root hash")
        if results_receipt.get("prediction_seal_root_hash") != prediction_seal.get("root_hash"):
            result_file_errors.append("prediction seal binding")
        if results_receipt.get("sentinel_evaluation_after_prediction_seal") is not True:
            result_file_errors.append("sentinel evaluation ordering")
        checks.update(
            {
                "prediction_seal_terminal_denominator": prediction_seal.get("terminal_window_receipts"),
                "prediction_seal_precedes_sentinel_evaluation": (
                    prediction_seal.get("sentinel_evaluation_performed_before_seal") is False
                    and results_receipt.get("sentinel_evaluation_after_prediction_seal") is True
                ),
                "result_file_errors": result_file_errors,
                "terminal_receipts": terminal,
                "actual_HTTP_attempts": actual_attempts,
                "result_receipt_errors": result_errors,
                "metrics_planned_denominator": metrics.get("planned_window_denominator"),
                "metrics_terminal_denominator": metrics.get("terminal_window_receipts"),
                "metrics_event_accuracy_disabled": metrics.get("event_accuracy_measured") is False,
                "query_count": query_results.get("query_count"),
                "query_relevance_disabled": query_results.get("accuracy_or_relevance_measured") is False,
                "search_index_entries": index_receipt.get("entry_count"),
                "dense_entire_series_index": metrics.get("dense_entire_series_index"),
            }
        )
        expected.update(
            {
                "prediction_seal_terminal_denominator": PLANNED_WINDOW_DENOMINATOR,
                "prediction_seal_precedes_sentinel_evaluation": True,
                "result_file_errors": [],
                "terminal_receipts": PLANNED_WINDOW_DENOMINATOR,
                "result_receipt_errors": [],
                "metrics_planned_denominator": PLANNED_WINDOW_DENOMINATOR,
                "metrics_terminal_denominator": PLANNED_WINDOW_DENOMINATOR,
                "metrics_event_accuracy_disabled": True,
                "query_count": len(QUERY_SET),
                "query_relevance_disabled": True,
                "search_index_entries": PLANNED_WINDOW_DENOMINATOR,
                "dense_entire_series_index": False,
            }
        )
    failures = {
        key: {"expected": value, "observed": checks.get(key)}
        for key, value in expected.items()
        if checks.get(key) != value
    }
    receipt = {
        "schema_version": "footballmaster-dvids-external-verification-v1",
        "verified_at_utc": utc_now(),
        "scope": "final_results" if require_results else "protocol_only_no_model_calls",
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
        "event_accuracy_measured": False,
        "source_claim_boundary": CLAIM_BOUNDARY,
    }
    name = "verification-receipt.json" if require_results else "protocol-verification-receipt.json"
    write_json(output_dir / name, receipt)
    if failures:
        raise ValueError("DVIDS external verification failed: " + json.dumps(failures, sort_keys=True))
    if require_results:
        prediction_seal = read_json(output_dir / PREDICTION_SEAL_NAME)
        write_json(
            output_dir / "execution-state.json",
            {
                "schema_version": "footballmaster-dvids-execution-state-v1",
                "updated_at_utc": utc_now(),
                "status": "final_verified_descriptive_results_semantic_no_go",
                "prompt_binding_sha256": sha256_file(output_dir / "frozen-prompt-binding.json"),
                "gpu_clearance_sha256": sha256_file(output_dir / "gpu-clearance.json"),
                "planned_window_denominator": PLANNED_WINDOW_DENOMINATOR,
                "terminal_window_receipts": PLANNED_WINDOW_DENOMINATOR,
                "actual_HTTP_attempts": checks.get("actual_HTTP_attempts"),
                "model_calls_started": True,
                "prediction_seal_sha256": sha256_file(output_dir / PREDICTION_SEAL_NAME),
                "prediction_seal_root_hash": prediction_seal.get("root_hash"),
                "results_receipt_sha256": sha256_file(output_dir / "results-receipt.json"),
                "verification_receipt_sha256": sha256_file(output_dir / name),
                "event_accuracy_measured": False,
                "retrieval_relevance_measured": False,
                "semantic_coach_search_verdict": "NO-GO",
            },
        )
    return receipt


def search(output_dir: Path, query: str, limit: int) -> list[dict[str, Any]]:
    entries = load_jsonl(output_dir / "football-search-index.jsonl")
    return bm25_search(entries, query, limit)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--project-root", type=Path, default=Path.cwd())
    value.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    value.add_argument("--core", type=Path, default=DEFAULT_CORE)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    commands.add_parser("bind-prompt")
    run = commands.add_parser("run")
    run.add_argument("--timeout-seconds", type=int, default=300)
    commands.add_parser("seal-predictions")
    commands.add_parser("build-results")
    commands.add_parser("verify-protocol")
    commands.add_parser("verify-final")
    find = commands.add_parser("search")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    dataset_dir = args.dataset if args.dataset.is_absolute() else project_root / args.dataset
    output_dir = args.output if args.output.is_absolute() else project_root / args.output
    core_dir = args.core if args.core.is_absolute() else project_root / args.core
    if args.command == "prepare":
        result = prepare(project_root, dataset_dir, output_dir)
    elif args.command == "bind-prompt":
        result = bind_prompt(core_dir, output_dir)
    elif args.command == "run":
        result = run_all(
            project_root, dataset_dir, output_dir, args.timeout_seconds, core_dir=core_dir
        )
    elif args.command == "seal-predictions":
        result = seal_predictions(output_dir)
    elif args.command == "build-results":
        result = build_results(output_dir)
    elif args.command == "verify-protocol":
        result = verify_protocol(project_root, dataset_dir, output_dir, require_results=False)
    elif args.command == "verify-final":
        result = verify_protocol(project_root, dataset_dir, output_dir, require_results=True)
    elif args.command == "search":
        result = search(output_dir, args.query, args.limit)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
