"""Offline official SoccerMaster feasibility and adapter contracts.

This module never downloads, imports official source, deserializes checkpoints,
or invokes a model. A completed preflight may be BLOCKED. Existing MobileNet and
Gemma experiments are not official SoccerMaster checkpoint executions.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "research/fixtures/soccermaster-official-preflight-v1.json"
SCHEMA = "playground-official-soccermaster-preflight-v1"
SHA = re.compile(r"^[a-f0-9]{64}$")
REV = re.compile(r"^[a-f0-9]{40}$")
CLIP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
FRAME_COUNT, WIDTH, HEIGHT = 30, 512, 512
GIB = 1024 ** 3
APPROVAL_KINDS = ("rights", "license", "computation")

class PreflightError(ValueError):
    pass

def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()

def file_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise PreflightError(name + " must be an exact SHA-256")
    return value

def _exact(value: Any, keys: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise PreflightError(name + " keys do not match the frozen contract")
    return value

def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise PreflightError(name + " must be positive and finite")
    return float(value)

def _local(root: Path, supplied: str) -> Path:
    # Deny network paths before resolve/stat can touch them, including Windows UNC.
    if not isinstance(supplied, str) or not supplied or supplied.startswith(("//", "\\\\")) or "://" in supplied:
        raise PreflightError("only explicitly supplied local project paths are allowed")
    if any(part.lower() in {"credentials", "secrets", ".ssh", ".aws"} for part in supplied.replace("\\", "/").split("/")):
        raise PreflightError("reserved private path")
    candidate = Path(supplied)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PreflightError("path escapes the project root") from exc
    return resolved

def _bound_file(root: Path, spec: Mapping[str, Any]) -> tuple[Path, str]:
    _exact(spec, {"path", "sha256"}, "file binding")
    expected = _digest(spec["sha256"], "file binding")
    path = _local(root, spec["path"])
    if not path.is_file():
        raise PreflightError("bound file is missing: " + spec["path"])
    if file_hash(path) != expected:
        raise PreflightError("bound file hash mismatch: " + spec["path"])
    return path, expected

def validate_scope(scope: dict) -> dict:
    _exact(scope, {"component", "source_revision", "checkpoint_hashes", "media_sha256",
                   "input_contract_sha256", "max_gpu_memory_bytes", "max_model_calls",
                   "remote_processing", "spend_usd"}, "scope")
    if scope["component"] != "encoder_event_head":
        raise PreflightError("only the bounded encoder/event-head scope is supported")
    if not isinstance(scope["source_revision"], str) or not REV.fullmatch(scope["source_revision"]):
        raise PreflightError("source revision is not pinned")
    _exact(scope["checkpoint_hashes"], {"backbone", "event_head"}, "checkpoint hashes")
    for role, value in scope["checkpoint_hashes"].items():
        _digest(value, role)
    _digest(scope["media_sha256"], "media")
    _digest(scope["input_contract_sha256"], "input contract")
    if type(scope["max_gpu_memory_bytes"]) is not int or not 0 < scope["max_gpu_memory_bytes"] <= 8 * GIB:
        raise PreflightError("GPU budget must be at most 8 GiB")
    if type(scope["max_model_calls"]) is not int or scope["max_model_calls"] != 1:
        raise PreflightError("preflight scope is one development clip")
    if scope["remote_processing"] is not False or type(scope["spend_usd"]) not in (int, float) or scope["spend_usd"] != 0:
        raise PreflightError("this path is offline and zero-spend only")
    return scope

def verify_approval(root: Path, kind: str, binding: dict, scope: dict) -> dict:
    if kind not in APPROVAL_KINDS:
        raise PreflightError("unknown approval kind")
    validate_scope(scope)
    path, digest = _bound_file(root, binding)
    data = json.loads(path.read_text(encoding="utf-8"))
    _exact(data, {"schema_version", "kind", "decision", "issuer", "approved_at",
                  "scope_sha256"}, "approval")
    if data["schema_version"] != "playground-soccermaster-approval-v1" or data["kind"] != kind or data["decision"] != "approved":
        raise PreflightError(kind + " approval does not match")
    if any(not isinstance(data[key], str) or not data[key].strip() for key in ("issuer", "approved_at")):
        raise PreflightError("approval issuer and time are required")
    try:
        approved_at = datetime.fromisoformat(data["approved_at"].replace("Z", "+00:00"))
        if approved_at.utcoffset() is None or approved_at > datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise PreflightError("approval time must be a past timezone-aware ISO timestamp") from exc
    if data["scope_sha256"] != canonical_hash(scope):
        raise PreflightError(kind + " approval is for a different experiment scope")
    return {"kind": kind, "evidence_sha256": digest, "scope_sha256": data["scope_sha256"],
            "validation": "content_binding_only_not_independent_issuer_authentication"}

def frame_plan(clip_id: str, duration_s: float, media_sha256: str) -> dict:
    if not isinstance(clip_id, str) or not CLIP.fullmatch(clip_id):
        raise PreflightError("clip ID must be anonymous and path-safe")
    duration = _positive(duration_s, "duration")
    _digest(media_sha256, "media")
    frames = [{"frame_id": "F%02d" % i, "offset_s": duration * i / FRAME_COUNT}
              for i in range(FRAME_COUNT)]
    return {"schema_version": "playground-soccermaster-frame-plan-v1", "clip_id": clip_id,
            "media_sha256": media_sha256, "duration_s": duration,
            "sampling": "uniform_endpoint_exclusive", "frames": frames,
            "shape": [FRAME_COUNT, HEIGHT, WIDTH, 3], "dtype": "uint8",
            "layout": "THWC", "color": "RGB", "normalization": "none",
            "official_tensor_normalization": "unverified",
            "contract_origin": "project_adapter_not_verified_official_callable",
            "audio_included": False, "labels_included": False}

def adapt_rgb_frames(plan: dict, frames: Sequence[bytes]) -> dict:
    """Hash caller-supplied RGB bytes; no pixel semantics, media read or model call.

    Caller must decode/redact rights-approved media first. This function cannot
    attest that pixels are redacted or came from the declared source.
    """
    expected = frame_plan(plan.get("clip_id"), plan.get("duration_s"), plan.get("media_sha256"))
    if plan != expected:
        raise PreflightError("frame plan changed")
    if len(frames) != FRAME_COUNT:
        raise PreflightError("exactly 30 decoded frames required")
    digests = []
    for raw in frames:
        if not isinstance(raw, bytes) or len(raw) != HEIGHT * WIDTH * 3:
            raise PreflightError("each frame must be exact 512x512 RGB uint8 bytes")
        digests.append(hashlib.sha256(raw).hexdigest())
    return {"schema_version": "playground-soccermaster-rgb-adapter-v1",
            "frame_plan_sha256": canonical_hash(plan), "frame_sha256": digests,
            "input_sha256": canonical_hash({"plan": plan, "frame_sha256": digests}),
            "shape": [FRAME_COUNT, HEIGHT, WIDTH, 3], "dtype": "uint8", "layout": "THWC",
            "total_raw_bytes": FRAME_COUNT * HEIGHT * WIDTH * 3,
            "official_callable_compatible": False, "normalization_status": "unverified",
            "source_and_redaction_verified": False, "model_calls": 0,
            "performance_claim_allowed": False}

PROVENANCE_KEYS = {"source_revision", "backbone_sha256", "head_sha256",
                   "input_manifest_sha256", "ontology_sha256", "run_receipt_sha256"}

def validate_model_output(payload: dict, *, expected_provenance: dict, ontology: dict) -> dict:
    """Validate a raw caller-supplied envelope, never synthesize coach reports.

    Hash equality checks provenance bindings; it does not authenticate the run,
    adjudicate the prediction, or establish official-checkpoint execution.
    """
    _exact(ontology, {"class_names", "mapping_status", "source_sha256"}, "ontology")
    _digest(ontology["source_sha256"], "ontology source")
    names = ontology["class_names"]
    if ontology["mapping_status"] != "verified" or not isinstance(names, list) or not names:
        raise PreflightError("event-class mapping is unresolved")
    if any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != len(names):
        raise PreflightError("class names must be distinct nonempty strings")
    _exact(expected_provenance, PROVENANCE_KEYS, "expected provenance")
    if not isinstance(expected_provenance["source_revision"], str) or not REV.fullmatch(expected_provenance["source_revision"]):
        raise PreflightError("exact source revision required")
    for key in PROVENANCE_KEYS - {"source_revision"}:
        _digest(expected_provenance[key], key)
    if expected_provenance["ontology_sha256"] != canonical_hash(ontology):
        raise PreflightError("ontology hash mismatch")
    _exact(payload, {"schema_version", "origin", "provenance", "event_logits",
                     "semantic_embedding"}, "model output")
    if payload["schema_version"] != "playground-soccermaster-raw-output-v1":
        raise PreflightError("model output schema mismatch")
    if payload["origin"] not in {"declared_official_checkpoint", "synthetic_contract_fixture"}:
        raise PreflightError("output origin must be explicit")
    if payload["provenance"] != expected_provenance:
        raise PreflightError("output provenance differs from pinned expected provenance")
    logits, embedding = payload["event_logits"], payload["semantic_embedding"]
    if not isinstance(logits, list) or len(logits) != len(names):
        raise PreflightError("logit count differs from the pinned class order")
    if not isinstance(embedding, list) or not 1 <= len(embedding) <= 65536:
        raise PreflightError("embedding is empty or exceeds the contract limit")
    for value in logits + embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise PreflightError("raw outputs must contain finite real numbers")
    return {"schema_version": "playground-soccermaster-validated-output-v1",
            "raw_output_sha256": canonical_hash(payload), "origin": payload["origin"],
            "provenance": dict(expected_provenance), "embedding_dimensions": len(embedding),
            "event_class_count": len(logits), "ontology_resolved_by_supplied_evidence": True,
            "official_execution_verified": False, "semantic_status": "UNADJUDICATED",
            "performance_claim_allowed": False, "coach_report_generated": False}

def machine_inventory() -> dict:
    packages = {}
    for name in ("torch", "torchvision", "torchaudio", "transformers", "accelerate",
                 "qwen-vl-utils", "flash-attn", "numpy", "Pillow"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    gpu = {"status": "unavailable", "devices": [], "error": None}
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            result = subprocess.run([executable, "--query-gpu=name,memory.total,driver_version",
                                     "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                for row in result.stdout.strip().splitlines():
                    name, mib, driver = [cell.strip() for cell in row.split(",")]
                    gpu["devices"].append({"name": name, "total_memory_bytes": int(mib) * 1024 ** 2,
                                           "driver_version": driver})
                gpu["status"] = "observed" if gpu["devices"] else "unavailable"
            else:
                gpu["error"] = "nvidia-smi exit " + str(result.returncode)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            gpu["error"] = type(exc).__name__
    ram = None
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page",
                 "avail_page", "total_virtual", "avail_virtual", "extended")]
        state = MemoryStatus()
        state.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            ram = state.total_phys
    elif hasattr(os, "sysconf"):
        try:
            ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError):
            pass
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": packages, "gpu": gpu, "ram_bytes": ram,
            "disk_free_bytes": shutil.disk_usage(ROOT).free,
            "package_inspection": "metadata_only_no_module_import",
            "peak_gpu_allocated_bytes": None, "peak_gpu_reserved_bytes": None,
            "cold_latency_s": None, "warm_latency_s": None}

def preflight(config: dict, *, root: Path = ROOT, inventory: dict | None = None) -> dict:
    _exact(config, {"schema_version", "sources", "scope", "approvals", "assets",
                    "official_entrypoint", "normalization", "ontology"}, "preflight config")
    if config["schema_version"] != "playground-soccermaster-preflight-config-v1":
        raise PreflightError("config schema mismatch")
    _exact(config["approvals"], set(APPROVAL_KINDS), "approvals")
    _exact(config["assets"], {"source_code", "backbone", "event_head", "siglip_config"}, "assets")
    blockers, sources, assets, approvals = [], [], {}, {}
    for item in config["sources"]:
        _exact(item, {"snapshot", "receipt"}, "source entry")
        try:
            snapshot, digest = _bound_file(root, item["snapshot"])
            receipt_path, receipt_digest = _bound_file(root, item["receipt"])
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if str(receipt.get("sha256", "")).lower() != digest or receipt.get("httpStatus") != 200:
                raise PreflightError("snapshot capture receipt does not match")
            if receipt.get("bytes") != snapshot.stat().st_size:
                raise PreflightError("snapshot byte count differs")
            sources.append({"snapshot_path": item["snapshot"]["path"], "snapshot_sha256": digest,
                            "receipt_sha256": receipt_digest, "url": receipt.get("url"),
                            "captured_at": receipt.get("capturedAtUtc"),
                            "server_owned_runtime_receipt": receipt.get("serverOwnedRuntimeReceipt", False),
                            "freshness": "historical_snapshot_not_a_current_remote_check"})
        except (PreflightError, ValueError, OSError) as exc:
            blockers.append("source_evidence: " + str(exc))
    if not sources:
        blockers.append("no_verified_official_source_snapshot")
    scope = config["scope"]
    try:
        validate_scope(scope)
    except PreflightError as exc:
        blockers.append("scope_unresolved: " + str(exc))
    for kind in APPROVAL_KINDS:
        binding = config["approvals"][kind]
        if binding is None:
            blockers.append(kind + "_approval_absent")
        else:
            try:
                approvals[kind] = verify_approval(root, kind, binding, scope)
            except (PreflightError, ValueError, OSError) as exc:
                blockers.append(kind + "_approval_invalid: " + str(exc))
    # Metadata/hashes only. No deserialization or imports, regardless of approvals.
    for role, spec in config["assets"].items():
        if spec is None:
            assets[role] = {"status": "not_supplied"}
            blockers.append(role + "_not_supplied")
        else:
            try:
                path, digest = _bound_file(root, spec)
                if role in ("backbone", "event_head") and scope["checkpoint_hashes"].get(role) != digest:
                    raise PreflightError("asset differs from approved scope")
                assets[role] = {"status": "hash_verified_only", "sha256": digest,
                                "bytes": path.stat().st_size, "deserialized": False}
            except (PreflightError, ValueError, OSError, KeyError, TypeError) as exc:
                blockers.append(role + "_invalid: " + str(exc))
    # These are deliberately unresolved until source-level contract inspection.
    if config["official_entrypoint"] is None:
        blockers.append("official_callable_not_verified")
    if config["normalization"] is None:
        blockers.append("official_normalization_not_verified")
    ontology = config["ontology"]
    if ontology.get("mapping_status") != "verified":
        blockers.append("ontology_unresolved_paper24_loader23_no_background")
    machine = inventory if inventory is not None else machine_inventory()
    if machine["packages"].get("torch") is None:
        blockers.append("pytorch_not_installed")
    if machine["packages"].get("transformers") is None:
        blockers.append("transformers_not_installed")
    blockers.append("runtime_import_and_peak_memory_unmeasured")
    blockers.append("official_inference_transport_not_implemented")
    return {"schema_version": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED" if blockers else "PREFLIGHT_COMPLETE",
            "config_sha256": canonical_hash(config), "scope_sha256": canonical_hash(scope),
            "sources": sources, "assets": assets, "approvals": approvals, "machine": machine,
            "blockers": blockers, "adapter_contract": {"frames": FRAME_COUNT, "width": WIDTH,
              "height": HEIGHT, "raw_rgb_bytes": FRAME_COUNT * HEIGHT * WIDTH * 3,
              "fp32_input_bytes_only": FRAME_COUNT * HEIGHT * WIDTH * 3 * 4,
              "gpu_fit_claim_allowed": False},
            "model_calls": 0, "network_calls": 0, "checkpoint_deserializations": 0,
            "official_code_imports": 0, "performance_claim_allowed": False,
            "current_semantic_boundary": "SYSTEMS GO / SEMANTIC NO-GO"}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config_path = _local(ROOT, str(args.config))
    result = preflight(json.loads(config_path.read_text(encoding="utf-8")))
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        path = _local(ROOT, str(args.output))
        path.parent.mkdir(parents=True, exist_ok=True)
        # Receipts are create-only; a fresh run needs a fresh output path.
        with path.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded)
    return 0  # Successful inventory execution does not mean gates passed.

if __name__ == "__main__":
    raise SystemExit(main())
