"""Seal a trained visual-only VLM configuration before validation inference.

The resulting artifact contains hashes and runtime settings, never dataset paths,
labels, commentary, credentials, or validation predictions.  A batch run can use
the artifact as a fail-closed gate via ``--frozen-config``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from isolated_vlm_runtime import (
    DEFAULT_CONTEXT_LENGTH as ISOLATED_CONTEXT_LENGTH,
    DEFAULT_GPU_LAYERS as ISOLATED_GPU_LAYERS,
    DEFAULT_PARALLEL as ISOLATED_PARALLEL,
    RECEIPT_SCHEMA_VERSION as RUNTIME_RECEIPT_SCHEMA_VERSION,
    validate_runtime_receipt,
)
from real_clip_vlm import SAMPLER_VERSION, prompt, sha256_file, structured_response_format


FROZEN_CONFIG_SCHEMA_VERSION = "playground-frozen-visual-config-v1"
FROZEN_CONFIG_SCHEMA_VERSION_V2 = "playground-frozen-visual-config-v2"
DEVELOPMENT_SUMMARY_SCHEMA_VERSION = "playground-soccernet-vlm-pilot-summary-v1"
RESPONSE_FORMAT_PROBE_TIMESTAMPS_S = [0.0, 1.0, 2.0]
PURPOSE = "One-time visual-only SoccerNet validation after prompt development on the train split."
MODEL_INPUT_POLICY = "sampled visual frames from physically silent event clips only"
FREEZE_POLICY = (
    "Prompt and runtime settings were selected on the development split. "
    "Validation predictions must not be inspected before this artifact is enforced."
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prompt_sha256() -> str:
    return hashlib.sha256(prompt().encode("utf-8")).hexdigest()


def _write_json_exclusive(path: Path, value: Any) -> None:
    """Create canonical JSON without any overwrite race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as sink:
            sink.write(payload)
    except FileExistsError as exc:
        raise FileExistsError("refusing to overwrite an existing frozen configuration") from exc


def _response_format_contract_sha256() -> str:
    return _json_sha256(structured_response_format(RESPONSE_FORMAT_PROBE_TIMESTAMPS_S))


def _normalize_loopback_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the frozen endpoint must be an HTTP loopback endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("the frozen endpoint must not contain credentials, query parameters, or fragments")
    if not parsed.port:
        raise ValueError("the frozen endpoint must use an explicit port")
    return endpoint.rstrip("/")


def _load_manifest(path: Path, *, expected_split: str) -> tuple[dict[str, Any], str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("split") != expected_split:
        raise ValueError(f"expected a {expected_split} manifest")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError(f"the {expected_split} manifest must contain clips")
    clip_ids: list[str] = []
    for clip in clips:
        if not isinstance(clip, dict) or clip.get("split") != expected_split:
            raise ValueError(f"every clip in the {expected_split} manifest must match its split")
        clip_id = clip.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id:
            raise ValueError(f"every clip in the {expected_split} manifest must have an opaque id")
        clip_ids.append(clip_id)
    if len(clip_ids) != len(set(clip_ids)):
        raise ValueError(f"clip ids in the {expected_split} manifest must be unique")
    return manifest, sha256_file(path)


def _validate_development_summary(
    path: Path, *, model: str, train_manifest_sha256: str,
    train_clip_ids: set[str], sample_count: int, sheets: int, max_tokens: int,
) -> str:
    summary = json.loads(path.read_text(encoding="utf-8"))
    expected_sampling = {
        "sample_count": sample_count,
        "contact_sheets": sheets,
        "max_tokens": max_tokens,
    }
    mismatches: list[str] = []
    if summary.get("schema_version") != DEVELOPMENT_SUMMARY_SCHEMA_VERSION:
        mismatches.append("schema_version")
    if summary.get("split") != "train":
        mismatches.append("split")
    if summary.get("model") != model:
        mismatches.append("model")
    if summary.get("sampling") != expected_sampling:
        mismatches.append("sampling")
    if summary.get("prompt_sha256") != _prompt_sha256():
        mismatches.append("prompt_sha256")
    if summary.get("private_manifest_sha256") != train_manifest_sha256:
        mismatches.append("private_manifest_sha256")
    counts = summary.get("counts")
    completed_records = summary.get("clips")
    completed_clip_ids = (
        [record.get("clip_id") for record in completed_records if isinstance(record, dict)]
        if isinstance(completed_records, list) else []
    )
    if (
        not isinstance(counts, dict)
        or counts.get("requested") != len(train_clip_ids)
        or counts.get("completed") != len(train_clip_ids)
        or counts.get("failed") != 0
    ):
        mismatches.append("complete_training_run")
    if (
        not isinstance(completed_records, list)
        or len(completed_clip_ids) != len(completed_records)
        or any(not isinstance(clip_id, str) or not clip_id for clip_id in completed_clip_ids)
        or len(completed_clip_ids) != len(set(completed_clip_ids))
        or set(completed_clip_ids) != train_clip_ids
    ):
        mismatches.append("completed_clip_ids")
    if summary.get("failures") != []:
        mismatches.append("empty_failure_records")
    if mismatches:
        raise ValueError("development summary does not match the configuration to freeze: " + ",".join(mismatches))
    return sha256_file(path)


def _runtime_receipt_binding(
    path: Path,
    *,
    model: str,
    endpoint: str,
) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("runtime receipt must be a JSON object")
    validate_runtime_receipt(
        receipt,
        model=model,
        endpoint=_normalize_loopback_endpoint(endpoint),
        context_length=ISOLATED_CONTEXT_LENGTH,
        parallel=ISOLATED_PARALLEL,
        gpu_offload="max",
        gpu_layers=ISOLATED_GPU_LAYERS,
    )
    backend = receipt["backend"]
    model_record = receipt["model"]
    return {
        "schema_version": RUNTIME_RECEIPT_SCHEMA_VERSION,
        "sha256": sha256_file(path),
        "backend": {
            "kind": backend["kind"],
            "release": backend["release"],
            "build": backend["build"],
            "commit": backend["commit"],
            "binary_sha256": backend["binary_sha256"],
        },
        "model": {
            "identifier": model_record["identifier"],
            "gguf_sha256": model_record["gguf_sha256"],
            "mmproj_sha256": model_record["mmproj_sha256"],
        },
        "expected_settings": {
            "endpoint": _normalize_loopback_endpoint(endpoint),
            "context_length": ISOLATED_CONTEXT_LENGTH,
            "parallel": ISOLATED_PARALLEL,
            "gpu_offload": "max",
            "gpu_layers": ISOLATED_GPU_LAYERS,
            "api_key_configured": False,
        },
    }


def create_frozen_config(
    *, train_manifest_path: Path, validation_manifest_path: Path,
    development_summary_path: Path, out_path: Path, endpoint: str, model: str,
    sample_count: int, sheets: int, max_tokens: int,
    runtime_receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Create a path-free, hash-sealed config artifact from a completed train run."""
    if not model.strip():
        raise ValueError("model must be non-empty")
    if sample_count < 1 or sheets < 1 or sheets > sample_count or max_tokens < 1:
        raise ValueError("sampling settings must be positive and sheets cannot exceed sample_count")
    normalized_endpoint = _normalize_loopback_endpoint(endpoint)
    train_manifest, train_sha256 = _load_manifest(train_manifest_path, expected_split="train")
    validation_manifest, validation_sha256 = _load_manifest(validation_manifest_path, expected_split="valid")
    train_ids = {clip["clip_id"] for clip in train_manifest["clips"]}
    validation_ids = {clip["clip_id"] for clip in validation_manifest["clips"]}
    if train_ids & validation_ids:
        raise ValueError("development and validation clip ids must be disjoint")
    if train_sha256 == validation_sha256:
        raise ValueError("development and validation manifests must be distinct")
    development_summary_sha256 = _validate_development_summary(
        development_summary_path,
        model=model,
        train_manifest_sha256=train_sha256,
        train_clip_ids={clip["clip_id"] for clip in train_manifest["clips"]},
        sample_count=sample_count,
        sheets=sheets,
        max_tokens=max_tokens,
    )
    runtime_binding = None
    if runtime_receipt_path is not None:
        runtime_binding = _runtime_receipt_binding(
            runtime_receipt_path,
            model=model,
            endpoint=normalized_endpoint,
        )
    artifact = {
        "schema_version": (
            FROZEN_CONFIG_SCHEMA_VERSION_V2 if runtime_binding is not None
            else FROZEN_CONFIG_SCHEMA_VERSION
        ),
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "purpose": PURPOSE,
        "model": model,
        "endpoint": normalized_endpoint,
        "sampling": {
            "sample_count": sample_count,
            "contact_sheets": sheets,
            "max_tokens": max_tokens,
        },
        "prompt_sha256": _prompt_sha256(),
        "sampler_version": SAMPLER_VERSION,
        "response_format_contract": {
            "probe_timestamps_s": RESPONSE_FORMAT_PROBE_TIMESTAMPS_S,
            "sha256": _response_format_contract_sha256(),
        },
        "manifests": {
            "development": {"split": "train", "sha256": train_sha256},
            "validation": {"split": "valid", "sha256": validation_sha256},
        },
        "development_summary_sha256": development_summary_sha256,
        "model_input": MODEL_INPUT_POLICY,
        "freeze_policy": FREEZE_POLICY,
        "performance_claim_allowed": False,
    }
    if runtime_binding is not None:
        artifact["runtime_receipt"] = runtime_binding
    _write_json_exclusive(out_path, artifact)
    return artifact


def verify_frozen_config(
    *, frozen_config_path: Path, manifest_path: Path, manifest: dict[str, Any],
    endpoint: str, model: str, sample_count: int, sheets: int, max_tokens: int,
    runtime_receipt_path: Path | None = None,
) -> dict[str, str]:
    """Fail closed on any config or split drift before a model request is made."""
    config = json.loads(frozen_config_path.read_text(encoding="utf-8"))
    required_keys = {
        "schema_version", "frozen_at", "purpose", "model", "endpoint", "sampling",
        "prompt_sha256", "sampler_version", "response_format_contract", "manifests",
        "development_summary_sha256", "model_input", "freeze_policy", "performance_claim_allowed",
    }
    schema_version = config.get("schema_version") if isinstance(config, dict) else None
    if schema_version == FROZEN_CONFIG_SCHEMA_VERSION_V2:
        required_keys = required_keys | {"runtime_receipt"}
    if not isinstance(config, dict) or set(config) != required_keys:
        raise ValueError("frozen configuration has an unexpected schema")
    if schema_version not in {FROZEN_CONFIG_SCHEMA_VERSION, FROZEN_CONFIG_SCHEMA_VERSION_V2}:
        raise ValueError("frozen configuration schema version is unsupported")
    expected_sampling = {
        "sample_count": sample_count,
        "contact_sheets": sheets,
        "max_tokens": max_tokens,
    }
    split = manifest.get("split")
    split_key = {"train": "development", "valid": "validation"}.get(split)
    if split_key is None:
        raise ValueError("a frozen configuration can only gate train or valid manifests")
    manifests = config.get("manifests")
    manifest_entry = manifests.get(split_key) if isinstance(manifests, dict) else None
    response_contract = config.get("response_format_contract")
    mismatches: list[str] = []
    if config.get("model") != model:
        mismatches.append("model")
    if config.get("endpoint") != _normalize_loopback_endpoint(endpoint):
        mismatches.append("endpoint")
    if config.get("sampling") != expected_sampling:
        mismatches.append("sampling")
    if config.get("prompt_sha256") != _prompt_sha256():
        mismatches.append("prompt_sha256")
    if config.get("sampler_version") != SAMPLER_VERSION:
        mismatches.append("sampler_version")
    if config.get("purpose") != PURPOSE or config.get("model_input") != MODEL_INPUT_POLICY:
        mismatches.append("input_policy")
    if config.get("freeze_policy") != FREEZE_POLICY:
        mismatches.append("freeze_policy")
    if response_contract != {
        "probe_timestamps_s": RESPONSE_FORMAT_PROBE_TIMESTAMPS_S,
        "sha256": _response_format_contract_sha256(),
    }:
        mismatches.append("response_format_contract")
    if not isinstance(manifests, dict) or set(manifests) != {"development", "validation"}:
        mismatches.append("manifest_schema")
    if not isinstance(manifest_entry, dict) or set(manifest_entry) != {"split", "sha256"} or manifest_entry.get("split") != split:
        mismatches.append("manifest_split")
    try:
        loaded_manifest, loaded_manifest_sha256 = _load_manifest(manifest_path, expected_split=split)
    except (OSError, ValueError, json.JSONDecodeError):
        mismatches.append("manifest_structure")
        loaded_manifest, loaded_manifest_sha256 = None, None
    if loaded_manifest != manifest:
        mismatches.append("manifest_content")
    if not isinstance(manifest_entry, dict) or manifest_entry.get("sha256") != loaded_manifest_sha256:
        mismatches.append("manifest_sha256")
    if config.get("performance_claim_allowed") is not False:
        mismatches.append("performance_claim_policy")
    runtime_receipt_sha256: str | None = None
    if schema_version == FROZEN_CONFIG_SCHEMA_VERSION_V2:
        if runtime_receipt_path is None:
            mismatches.append("runtime_receipt_required")
        else:
            try:
                live_binding = _runtime_receipt_binding(
                    runtime_receipt_path,
                    model=model,
                    endpoint=endpoint,
                )
            except (OSError, ValueError, json.JSONDecodeError):
                mismatches.append("runtime_receipt_invalid")
            else:
                runtime_receipt_sha256 = live_binding["sha256"]
                if config.get("runtime_receipt") != live_binding:
                    mismatches.append("runtime_receipt_binding")
    elif runtime_receipt_path is not None:
        mismatches.append("runtime_receipt_unbound_by_v1")
    for key in ("prompt_sha256", "development_summary_sha256"):
        if not isinstance(config.get(key), str) or not _SHA256.fullmatch(config[key]):
            mismatches.append(key + "_shape")
    if isinstance(manifests, dict):
        for key in ("development", "validation"):
            entry = manifests.get(key)
            if (
                not isinstance(entry, dict)
                or set(entry) != {"split", "sha256"}
                or entry.get("split") != {"development": "train", "validation": "valid"}[key]
                or not isinstance(entry.get("sha256"), str)
                or not _SHA256.fullmatch(entry["sha256"])
            ):
                mismatches.append("manifest_schema")
    if mismatches:
        raise ValueError("runtime does not match frozen visual configuration: " + ",".join(sorted(set(mismatches))))
    return {
        "schema_version": schema_version,
        "sha256": sha256_file(frozen_config_path),
        **({"runtime_receipt_sha256": runtime_receipt_sha256} if runtime_receipt_sha256 else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", type=Path, required=True)
    parser.add_argument("--validation-manifest", type=Path, required=True)
    parser.add_argument("--development-summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--sample-count", type=int, required=True)
    parser.add_argument("--sheets", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument(
        "--runtime-receipt", type=Path,
        help="Optional isolated-runtime receipt; when present, creates a v2 hash-bound freeze.",
    )
    args = parser.parse_args()
    artifact = create_frozen_config(
        train_manifest_path=args.train_manifest,
        validation_manifest_path=args.validation_manifest,
        development_summary_path=args.development_summary,
        out_path=args.out,
        endpoint=args.endpoint,
        model=args.model,
        sample_count=args.sample_count,
        sheets=args.sheets,
        max_tokens=args.max_tokens,
        runtime_receipt_path=args.runtime_receipt,
    )
    print(json.dumps({
        "status": "frozen",
        "schema_version": artifact["schema_version"],
        "artifact_sha256": sha256_file(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
