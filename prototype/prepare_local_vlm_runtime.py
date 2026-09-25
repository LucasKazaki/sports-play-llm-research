"""Diagnose the shared LM Studio/Bionic local VLM runtime without mutating it.

This module intentionally refuses its former ``--prepare`` path.  Evidence from
the overnight run showed that another client can make Bionic auto-load an
unrelated model after a seemingly clean preparation.  The shared service is
therefore diagnostic-only; use ``isolated_vlm_runtime.py`` for a freeze-grade,
single-model backend with an owned process and port.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


RUNTIME_RECEIPT_SCHEMA_VERSION = "playground-local-vlm-runtime-receipt-v1"
DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_CONTEXT_LENGTH = 4096
DEFAULT_PARALLEL = 1
DEFAULT_GPU_OFFLOAD = "max"
DEFAULT_TTL_SECONDS = 3600
DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1"

_CLI_COMMIT = re.compile(r"CLI commit:\s*([0-9a-f]{7,40})", re.IGNORECASE)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_SECRET_KEYS = {
    "password", "passwd", "api_key", "apikey", "access_token",
    "refresh_token", "secret", "authorization", "authorization_header",
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise HTTPError(req.full_url, code, "redirect refused", headers, fp)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[Path, Sequence[str], float], CommandResult]
ApiReader = Callable[[str, float], dict[str, Any]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_runner(executable: Path, arguments: Sequence[str], timeout_s: float) -> CommandResult:
    try:
        result = subprocess.run(
            [str(executable), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"LM Studio operation timed out after {timeout_s:g} seconds") from exc
    return CommandResult(result.returncode, result.stdout, result.stderr)


def _default_api_reader(url: str, timeout_s: float) -> dict[str, Any]:
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout_s) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("LM Studio loopback model inspection failed") from exc
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("LM Studio loopback model response must be a JSON object")
    return value


def _run_json(
    executable: Path,
    arguments: Sequence[str],
    *,
    runner: CommandRunner,
    operation: str,
    timeout_s: float = 15.0,
) -> Any:
    result = runner(executable, arguments, timeout_s)
    if result.returncode != 0:
        raise RuntimeError(f"{operation} failed with exit code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} returned malformed JSON") from exc


def _run_required(
    executable: Path,
    arguments: Sequence[str],
    *,
    runner: CommandRunner,
    operation: str,
    timeout_s: float,
) -> CommandResult:
    result = runner(executable, arguments, timeout_s)
    if result.returncode != 0:
        raise RuntimeError(f"{operation} failed with exit code {result.returncode}")
    return result


def locate_lms(
    explicit_path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, str]:
    """Locate lms.exe only through PATH or a small set of documented install roots."""
    env = os.environ if environ is None else environ
    if explicit_path is not None:
        resolved = explicit_path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError("the explicitly selected LM Studio CLI does not exist")
        return resolved, "explicit"

    on_path = shutil.which("lms", path=env.get("PATH"))
    if on_path:
        resolved = Path(on_path).resolve()
        if resolved.is_file():
            return resolved, "environment_path"

    candidates: list[tuple[str, Path]] = []
    user_profile = env.get("USERPROFILE")
    local_app_data = env.get("LOCALAPPDATA")
    program_files = env.get("ProgramFiles") or env.get("PROGRAMFILES")
    if user_profile:
        candidates.append(("user_profile_lmstudio_bin", Path(user_profile) / ".lmstudio/bin/lms.exe"))
    if local_app_data:
        candidates.extend([
            ("local_app_data_lmstudio_bin", Path(local_app_data) / "LM Studio/bin/lms.exe"),
            ("local_app_data_programs_lmstudio", Path(local_app_data) / "Programs/LM Studio/lms.exe"),
        ])
    if program_files:
        candidates.append(("program_files_lmstudio", Path(program_files) / "LM Studio/lms.exe"))
    for locator, candidate in candidates:
        if candidate.is_file():
            return candidate.resolve(), locator
    raise FileNotFoundError("LM Studio CLI was not found on PATH or in a known installation location")


def _normalize_loopback_endpoint(endpoint: str) -> tuple[str, int, str]:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the runtime endpoint must be an HTTP loopback endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("the runtime endpoint must not contain credentials, query parameters, or fragments")
    if not parsed.port:
        raise ValueError("the runtime endpoint must use an explicit port")
    path = parsed.path.rstrip("/")
    if path not in {"", "/v1"}:
        raise ValueError("the runtime endpoint path must be empty or /v1")
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    server_base = f"http://{host}:{parsed.port}"
    return server_base + "/v1", parsed.port, server_base + "/api/v0/models"


def _safe_quantization(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return name if isinstance(name, str) else None
    return value if isinstance(value, str) else None


def _safe_model_record(record: dict[str, Any]) -> dict[str, Any]:
    """Select only reproducibility fields; intentionally omit filesystem paths."""
    return {
        "model_key": record.get("modelKey"),
        "identifier": record.get("identifier"),
        "format": record.get("format"),
        "architecture": record.get("architecture"),
        "quantization": _safe_quantization(record.get("quantization")),
        "selected_variant": record.get("selectedVariant"),
        "size_bytes": record.get("sizeBytes"),
        "vision": record.get("vision"),
        "parallel": record.get("parallel"),
        "ttl_ms": record.get("ttlMs"),
        "status": record.get("status"),
        "reported_context_length": record.get("contextLength"),
        "reported_max_context_length": record.get("maxContextLength"),
    }


def _safe_api_model_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": record.get("id"),
        "state": record.get("state"),
        "reported_loaded_context_length": record.get("loaded_context_length"),
        "reported_max_context_length": record.get("max_context_length"),
    }


def inspect_runtime(
    *,
    executable: Path,
    locator: str,
    endpoint: str,
    runner: CommandRunner = _default_runner,
    api_reader: ApiReader = _default_api_reader,
) -> dict[str, Any]:
    normalized_endpoint, expected_port, api_url = _normalize_loopback_endpoint(endpoint)
    version = _run_required(
        executable, ["--version"], runner=runner,
        operation="LM Studio version inspection", timeout_s=15,
    )
    commit_match = _CLI_COMMIT.search(version.stdout)
    if not commit_match:
        raise ValueError("LM Studio version output did not contain a CLI commit")
    server = _run_json(
        executable, ["server", "status", "--json"], runner=runner,
        operation="LM Studio server inspection",
    )
    models = _run_json(
        executable, ["ps", "--json"], runner=runner,
        operation="LM Studio loaded-model inspection",
    )
    if not isinstance(server, dict):
        raise ValueError("LM Studio server status must be a JSON object")
    if not isinstance(models, list) or any(not isinstance(item, dict) for item in models):
        raise ValueError("LM Studio loaded-model status must be a JSON array of objects")
    api_payload = api_reader(api_url, 15.0)
    api_models = api_payload.get("data")
    if not isinstance(api_models, list) or any(not isinstance(item, dict) for item in api_models):
        raise ValueError("LM Studio loopback model response data must be an array of objects")
    api_loaded = [item for item in api_models if item.get("state") == "loaded"]
    return {
        "cli_commit": commit_match.group(1).lower(),
        "cli_locator": locator,
        "endpoint": normalized_endpoint,
        "server": {
            "running": server.get("running"),
            "port": server.get("port"),
            "expected_port": expected_port,
        },
        "loaded_model_count": len(models),
        "loaded_models": [_safe_model_record(item) for item in models],
        "api_loaded_model_count": len(api_loaded),
        "api_loaded_models": [_safe_api_model_record(item) for item in api_loaded],
    }


def observable_drift(
    observation: dict[str, Any],
    *,
    model: str,
    parallel: int,
    ttl_seconds: int,
) -> list[str]:
    """Return only drift that LM Studio exposes after loading."""
    drift: list[str] = []
    server = observation.get("server")
    if not isinstance(server, dict) or server.get("running") is not True:
        drift.append("server_not_running")
    elif server.get("port") != server.get("expected_port"):
        drift.append("server_port")
    models = observation.get("loaded_models")
    if observation.get("loaded_model_count") != 1 or not isinstance(models, list) or len(models) != 1:
        drift.append("loaded_model_count")
    else:
        loaded = models[0]
        if loaded.get("model_key") != model:
            drift.append("model_key")
        if loaded.get("identifier") != model:
            drift.append("identifier")
        if loaded.get("parallel") != parallel:
            drift.append("parallel")
        if loaded.get("ttl_ms") != ttl_seconds * 1000:
            drift.append("ttl")
        if loaded.get("vision") is not True:
            drift.append("vision_capability")
        if not isinstance(loaded.get("size_bytes"), int) or loaded["size_bytes"] <= 0:
            drift.append("model_size")
        if loaded.get("status") not in {"idle", "loaded"}:
            drift.append("model_status")
        reported_context = loaded.get("reported_context_length")
        if not isinstance(reported_context, int) or reported_context <= 0:
            drift.append("reported_context_length")
    api_models = observation.get("api_loaded_models")
    if observation.get("api_loaded_model_count") != 1 or not isinstance(api_models, list) or len(api_models) != 1:
        drift.append("api_loaded_model_count")
    else:
        api_model = api_models[0]
        if api_model.get("model_id") != model:
            drift.append("api_model_id")
        if api_model.get("state") != "loaded":
            drift.append("api_model_state")
        if isinstance(models, list) and len(models) == 1:
            if api_model.get("reported_loaded_context_length") != models[0].get("reported_context_length"):
                drift.append("reported_context_disagreement")
    return sorted(set(drift))


def _assert_public_safe(value: Any) -> None:
    def walk(child: Any, key: str | None = None) -> None:
        if key is not None and key.lower().replace("-", "_") in _SECRET_KEYS:
            raise ValueError("runtime receipt contains a secret-shaped key")
        if isinstance(child, dict):
            for item_key, item_value in child.items():
                walk(item_value, str(item_key))
        elif isinstance(child, list):
            for item in child:
                walk(item)
        elif isinstance(child, str):
            normalized = child.replace("\\", "/").lower()
            if (
                _WINDOWS_ABSOLUTE_PATH.match(child)
                or child.startswith("\\\\")
                or "/data/private/" in "/" + normalized.strip("/") + "/"
            ):
                raise ValueError("runtime receipt contains an absolute or private path")

    walk(value)


def _model_observation(observation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    models = observation["loaded_models"]
    api_models = observation["api_loaded_models"]
    if len(models) != 1 or len(api_models) != 1:
        raise ValueError("a freeze-grade receipt requires one loaded CLI model and one loaded API model")
    return models[0], api_models[0]


def build_runtime_receipt(
    *,
    observation: dict[str, Any],
    model: str,
    context_length: int,
    parallel: int,
    gpu_offload: str,
    ttl_seconds: int,
    unload_exit_code: int,
    load_exit_code: int,
) -> dict[str, Any]:
    drift = observable_drift(
        observation, model=model, parallel=parallel, ttl_seconds=ttl_seconds,
    )
    if drift:
        raise ValueError("prepared runtime has observable drift: " + ",".join(drift))
    loaded, api_loaded = _model_observation(observation)
    receipt = {
        "schema_version": RUNTIME_RECEIPT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "prepared_and_verified",
        "target": {
            "model_key": model,
            "identifier": model,
        },
        "requested_settings": {
            "context_length": context_length,
            "parallel": parallel,
            "gpu_offload": gpu_offload,
            "ttl_seconds": ttl_seconds,
            "speculative_draft_mtp": False,
        },
        "observed_runtime": {
            "cli_commit": observation["cli_commit"],
            "cli_locator": observation["cli_locator"],
            "endpoint": observation["endpoint"],
            "server": {
                "running": observation["server"]["running"],
                "port": observation["server"]["port"],
            },
            "loaded_model_count": observation["loaded_model_count"],
            "model": loaded,
            "api_loaded_model_count": observation["api_loaded_model_count"],
            "api_model": api_loaded,
        },
        "preparation": {
            "mode": "explicit_unload_all_then_load_one",
            "unload_all_exit_code": unload_exit_code,
            "load_exit_code": load_exit_code,
            "exact_settings_submitted": True,
        },
        "verification": {
            "status": "pass",
            "observable_drift": [],
            "observable_checks": [
                "loopback_server_port",
                "single_loaded_model",
                "model_key_and_identifier",
                "vision_capability",
                "parallel",
                "ttl",
                "cli_api_model_agreement",
                "reported_context_recorded",
            ],
            "attestation_boundary": (
                "The exact context, GPU-max, parallel, TTL, identifier, and no-speculative-MTP settings were "
                "submitted to a successful load operation. LM Studio does not expose GPU offload, requested "
                "context allocation, or speculative-decoding state in `lms ps --json`; its reported model "
                "context is recorded separately and is not treated as the requested allocation."
            ),
        },
        "safety": {
            "public_safe": True,
            "contains_credentials": False,
            "contains_process_command_line": False,
            "contains_executable_path": False,
            "contains_private_media_path": False,
        },
    }
    _assert_public_safe(receipt)
    return receipt


def validate_runtime_receipt(
    receipt: dict[str, Any],
    *,
    model: str,
    context_length: int,
    parallel: int,
    gpu_offload: str,
    ttl_seconds: int,
    endpoint: str,
) -> None:
    """Validate the strict freeze-grade receipt schema and expected settings."""
    _assert_public_safe(receipt)
    required_top = {
        "schema_version", "generated_at", "status", "target", "requested_settings",
        "observed_runtime", "preparation", "verification", "safety",
    }
    mismatches: list[str] = []
    if not isinstance(receipt, dict) or set(receipt) != required_top:
        raise ValueError("runtime receipt has an unexpected schema")
    if receipt.get("schema_version") != RUNTIME_RECEIPT_SCHEMA_VERSION:
        mismatches.append("schema_version")
    if receipt.get("status") != "prepared_and_verified":
        mismatches.append("status")
    if receipt.get("target") != {"model_key": model, "identifier": model}:
        mismatches.append("target")
    expected_settings = {
        "context_length": context_length,
        "parallel": parallel,
        "gpu_offload": gpu_offload,
        "ttl_seconds": ttl_seconds,
        "speculative_draft_mtp": False,
    }
    if receipt.get("requested_settings") != expected_settings:
        mismatches.append("requested_settings")
    normalized_endpoint, expected_port, _api_url = _normalize_loopback_endpoint(endpoint)
    observed = receipt.get("observed_runtime")
    if not isinstance(observed, dict) or set(observed) != {
        "cli_commit", "cli_locator", "endpoint", "server", "loaded_model_count",
        "model", "api_loaded_model_count", "api_model",
    }:
        mismatches.append("observed_runtime_schema")
    else:
        if observed.get("endpoint") != normalized_endpoint:
            mismatches.append("endpoint")
        if observed.get("server") != {"running": True, "port": expected_port}:
            mismatches.append("server")
        model_record = observed.get("model")
        api_record = observed.get("api_model")
        if observed.get("loaded_model_count") != 1 or not isinstance(model_record, dict):
            mismatches.append("single_loaded_model")
        else:
            if model_record.get("model_key") != model or model_record.get("identifier") != model:
                mismatches.append("model_identity")
            if model_record.get("parallel") != parallel:
                mismatches.append("parallel")
            if model_record.get("ttl_ms") != ttl_seconds * 1000:
                mismatches.append("ttl")
            if model_record.get("vision") is not True:
                mismatches.append("vision_capability")
            if model_record.get("status") not in {"idle", "loaded"}:
                mismatches.append("model_status")
            if not isinstance(model_record.get("reported_context_length"), int):
                mismatches.append("reported_context_length")
        if observed.get("api_loaded_model_count") != 1 or not isinstance(api_record, dict):
            mismatches.append("single_api_model")
        elif api_record.get("model_id") != model or api_record.get("state") != "loaded":
            mismatches.append("api_model_identity")
        elif isinstance(model_record, dict) and (
            api_record.get("reported_loaded_context_length") != model_record.get("reported_context_length")
        ):
            mismatches.append("reported_context_disagreement")
        if not isinstance(observed.get("cli_commit"), str) or not re.fullmatch(r"[0-9a-f]{7,40}", observed["cli_commit"]):
            mismatches.append("cli_commit")
        if not isinstance(observed.get("cli_locator"), str) or not observed["cli_locator"]:
            mismatches.append("cli_locator")
    preparation = receipt.get("preparation")
    if preparation != {
        "mode": "explicit_unload_all_then_load_one",
        "unload_all_exit_code": 0,
        "load_exit_code": 0,
        "exact_settings_submitted": True,
    }:
        mismatches.append("preparation")
    verification = receipt.get("verification")
    if (
        not isinstance(verification, dict)
        or verification.get("status") != "pass"
        or verification.get("observable_drift") != []
        or not isinstance(verification.get("attestation_boundary"), str)
    ):
        mismatches.append("verification")
    safety = receipt.get("safety")
    if safety != {
        "public_safe": True,
        "contains_credentials": False,
        "contains_process_command_line": False,
        "contains_executable_path": False,
        "contains_private_media_path": False,
    }:
        mismatches.append("safety")
    if mismatches:
        raise ValueError("runtime receipt does not match expected settings: " + ",".join(sorted(set(mismatches))))


def write_receipt_exclusive(path: Path, receipt: dict[str, Any]) -> None:
    _assert_public_safe(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as sink:
            sink.write(payload)
    except FileExistsError as exc:
        raise FileExistsError("refusing to overwrite an existing runtime receipt") from exc


def prepare_runtime(
    *,
    executable: Path,
    locator: str,
    endpoint: str,
    model: str,
    context_length: int,
    parallel: int,
    gpu_offload: str,
    ttl_seconds: int,
    runner: CommandRunner = _default_runner,
    api_reader: ApiReader = _default_api_reader,
) -> dict[str, Any]:
    raise RuntimeError(
        "shared Bionic preparation is disabled because external auto-load can invalidate the runtime; "
        "use isolated_vlm_runtime.py"
    )
    # Retain the implementation below as a record of the rejected strategy.  It
    # is unreachable by design so imports cannot accidentally mutate Bionic.
    if not model.strip():
        raise ValueError("model must be non-empty")
    if context_length < 1 or parallel < 1 or ttl_seconds < 1 or gpu_offload != "max":
        raise ValueError("runtime settings require positive context/parallel/TTL and gpu_offload=max")
    unload = _run_required(
        executable, ["unload", "--all"], runner=runner,
        operation="LM Studio unload-all", timeout_s=60,
    )
    load_arguments = [
        "load", model,
        "--identifier", model,
        "--context-length", str(context_length),
        "--parallel", str(parallel),
        "--gpu", gpu_offload,
        "--ttl", str(ttl_seconds),
        "--no-speculative-draft-mtp",
        "-y",
    ]
    load = _run_required(
        executable, load_arguments, runner=runner,
        operation="LM Studio target-model load", timeout_s=180,
    )

    observation: dict[str, Any] | None = None
    drift: list[str] = ["post_load_state_unavailable"]
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        try:
            observation = inspect_runtime(
                executable=executable, locator=locator, endpoint=endpoint,
                runner=runner, api_reader=api_reader,
            )
            drift = observable_drift(
                observation, model=model, parallel=parallel, ttl_seconds=ttl_seconds,
            )
            if not drift:
                break
        except (RuntimeError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    if observation is None or drift:
        raise RuntimeError("LM Studio post-load verification failed: " + ",".join(drift))
    return build_runtime_receipt(
        observation=observation,
        model=model,
        context_length=context_length,
        parallel=parallel,
        gpu_offload=gpu_offload,
        ttl_seconds=ttl_seconds,
        unload_exit_code=unload.returncode,
        load_exit_code=load.returncode,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Explicitly unload all models and load the target.")
    parser.add_argument("--output", type=Path, help="Write-once public runtime receipt; requires --prepare.")
    parser.add_argument("--lms", type=Path, help="Explicit LM Studio CLI executable.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    parser.add_argument("--gpu", choices=["max"], default=DEFAULT_GPU_OFFLOAD)
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    args = parser.parse_args()
    if args.prepare or args.output is not None:
        parser.error(
            "shared Bionic preparation is disabled because its auto-load surface cannot be isolated; "
            "use isolated_vlm_runtime.py"
        )
    executable, locator = locate_lms(args.lms)
    observation = inspect_runtime(
        executable=executable, locator=locator, endpoint=args.endpoint,
    )
    drift = observable_drift(
        observation, model=args.model, parallel=args.parallel, ttl_seconds=args.ttl,
    )
    print(json.dumps({
        "status": "observable_pass" if not drift else "observable_drift",
        "mutated": False,
        "freeze_grade_receipt": False,
        "model": args.model,
        "loaded_model_count": observation["loaded_model_count"],
        "reported_context_length": (
            observation["loaded_models"][0].get("reported_context_length")
            if observation["loaded_model_count"] == 1 else None
        ),
        "observable_drift": drift,
        "attestation_boundary": (
            "Read-only inspection cannot attest GPU offload, requested context allocation, or "
            "speculative-decoding state; use --prepare for a freeze-grade receipt."
        ),
    }, indent=2))
    return 0 if not drift else 2


if __name__ == "__main__":
    raise SystemExit(main())
