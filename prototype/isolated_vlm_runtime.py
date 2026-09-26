"""Own an isolated, hash-pinned llama-server lifecycle for VLM experiments.

The lifecycle is intentionally explicit:

``prepare`` closes the shared Bionic API and unloads its models; ``start``
launches one direct llama-server process on a dedicated loopback port; ``status``
checks the process image, PID/port ownership, health, and model API; ``stop``
terminates only the verified owned process; and ``restore`` returns the Bionic
server to its prior on/off state.  No API key is configured, and neither the
public receipt nor the lifecycle state persists executable/model paths or a
process command line.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from prepare_local_vlm_runtime import (
    CommandResult,
    CommandRunner,
    _default_runner,
    _run_json,
    _run_required,
    locate_lms,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
STATE_SCHEMA_VERSION = "playground-isolated-vlm-runtime-state-v1"
RECEIPT_SCHEMA_VERSION = "playground-isolated-vlm-runtime-receipt-v1"
DEFAULT_STATE = ROOT / ".agent/isolated-vlm-runtime-state.json"
DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1240
DEFAULT_CONTEXT_LENGTH = 8192
DEFAULT_GPU_LAYERS = "all"
DEFAULT_PARALLEL = 1
EXPECTED_BINARY_RELEASE = "0.2.0-dev"
EXPECTED_BINARY_BUILD = 10566
EXPECTED_BINARY_COMMIT = "bb4caa754"
DEFAULT_REASONING_BUDGET_MESSAGE = "I have to answer now."

_CLI_COMMIT = re.compile(r"CLI commit:\s*([0-9a-f]{7,40})", re.IGNORECASE)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_SECRET_KEYS = {
    "password", "passwd", "api_key", "apikey", "access_token", "refresh_token",
    "secret", "authorization", "authorization_header", "api_key_file",
}

HttpReader = Callable[[str, float], dict[str, Any]]
PortOwnerReader = Callable[[int], int | None]
ProcessHashReader = Callable[[int], str | None]
ProcessAliveReader = Callable[[int], bool]
ProcessStopper = Callable[[int, float], None]
ProcessLauncher = Callable[[Path, Sequence[str], Path, Mapping[str, str]], int]
BinaryIdentityReader = Callable[[Path], dict[str, Any]]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_public_safe(value: Any) -> None:
    def walk(child: Any, key: str | None = None) -> None:
        if key is not None and key.lower().replace("-", "_") in _SECRET_KEYS:
            raise ValueError("runtime metadata contains a secret-shaped key")
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
                raise ValueError("runtime metadata contains an absolute or private path")

    walk(value)


def _require_state_path(path: Path) -> Path:
    resolved = path.resolve()
    if ".agent" not in {part.lower() for part in resolved.parts}:
        raise ValueError("isolated runtime state must remain under a .agent directory")
    return resolved


def _atomic_write_state(path: Path, state: dict[str, Any], *, exclusive: bool = False) -> None:
    _assert_public_safe(state)
    resolved = _require_state_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if exclusive:
        try:
            with resolved.open("x", encoding="utf-8", newline="\n") as sink:
                sink.write(payload)
        except FileExistsError as exc:
            raise FileExistsError("refusing to overwrite an existing isolated-runtime lifecycle") from exc
        return
    temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as sink:
            sink.write(payload)
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_state(path: Path) -> dict[str, Any]:
    resolved = _require_state_path(path)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("unsupported isolated-runtime lifecycle state")
    _assert_public_safe(value)
    return value


def write_receipt_exclusive(path: Path, receipt: dict[str, Any]) -> None:
    _assert_public_safe(receipt)
    resolved = path.resolve()
    if any(part.lower() == "private" for part in resolved.parts):
        raise ValueError("the public runtime receipt must not be written under a private directory")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with resolved.open("x", encoding="utf-8", newline="\n") as sink:
            sink.write(payload)
    except FileExistsError as exc:
        raise FileExistsError("refusing to overwrite an existing isolated-runtime receipt") from exc


def _read_http_json(url: str, timeout_s: float) -> dict[str, Any]:
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("isolated backend inspection is restricted to HTTP loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("isolated backend URL must not contain credentials, query parameters, or fragments")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout_s) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("isolated backend loopback inspection failed") from exc
    if not isinstance(value, dict):
        raise ValueError("isolated backend response must be a JSON object")
    return value


def _bionic_snapshot(executable: Path, runner: CommandRunner) -> dict[str, Any]:
    version = _run_required(
        executable, ["--version"], runner=runner,
        operation="LM Studio version inspection", timeout_s=15,
    )
    match = _CLI_COMMIT.search(version.stdout)
    if not match:
        raise ValueError("LM Studio version output did not contain a CLI commit")
    server = _run_json(
        executable, ["server", "status", "--json"], runner=runner,
        operation="LM Studio server inspection",
    )
    models = _run_json(
        executable, ["ps", "--json"], runner=runner,
        operation="LM Studio loaded-model inspection",
    )
    if not isinstance(server, dict) or not isinstance(models, list):
        raise ValueError("LM Studio runtime inspection returned an unexpected schema")
    identifiers: list[str] = []
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("identifier"), str):
            raise ValueError("LM Studio loaded-model inspection contains an invalid identifier")
        identifiers.append(model["identifier"])
    return {
        "cli_commit": match.group(1).lower(),
        "server_running": server.get("running"),
        "server_port": server.get("port"),
        "loaded_model_identifiers": sorted(identifiers),
    }


def prepare_isolation(
    *,
    state_path: Path,
    lms_executable: Path,
    lms_locator: str,
    model: str,
    host: str,
    port: int,
    context_length: int,
    gpu_layers: str,
    parallel: int,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    if state_path.exists():
        raise FileExistsError("refusing to overwrite an existing isolated-runtime lifecycle")
    if host != DEFAULT_HOST or not (1024 <= port <= 65535):
        raise ValueError("the isolated backend must use 127.0.0.1 and a non-privileged port")
    if (
        not model.strip()
        or context_length != DEFAULT_CONTEXT_LENGTH
        or gpu_layers != DEFAULT_GPU_LAYERS
        or parallel != DEFAULT_PARALLEL
    ):
        raise ValueError("invalid isolated backend settings")
    before = _bionic_snapshot(lms_executable, runner)
    if before["server_running"] is True:
        _run_required(
            lms_executable, ["server", "stop"], runner=runner,
            operation="LM Studio server stop", timeout_s=60,
        )
    if before["loaded_model_identifiers"]:
        _run_required(
            lms_executable, ["unload", "--all"], runner=runner,
            operation="LM Studio unload-all", timeout_s=60,
        )
    after = _bionic_snapshot(lms_executable, runner)
    if after["server_running"] is not False or after["loaded_model_identifiers"] != []:
        raise RuntimeError("Bionic isolation failed: server or loaded models remain active")
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "lifecycle_status": "bionic_suspended",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "configuration": {
            "backend": "llama.cpp-direct",
            "model": model,
            "host": host,
            "port": port,
            "endpoint": f"http://{host}:{port}/v1",
            "context_length": context_length,
            "gpu_offload": "max",
            "gpu_layers": gpu_layers,
            "parallel": parallel,
            "device": "CUDA0",
            "split_mode": "none",
            "fit_enabled": True,
            "fit_target": 256,
            "fit_context": 8192,
            "batch_size": 2048,
            "micro_batch_size": 512,
            "threads": 4,
            "kv_key_type": "f16",
            "kv_value_type": "f16",
            "flash_attention": "auto",
            "kv_offload": True,
            "kv_unified": True,
            "device_io_disabled": True,
            "memory_lock": True,
            "metrics_enabled": True,
            "reasoning_format": "deepseek",
            "reasoning_budget": 256,
            "reasoning_budget_message": DEFAULT_REASONING_BUDGET_MESSAGE,
            "mmproj_required": True,
            "webui_enabled": False,
            "api_key_configured": False,
        },
        "bionic": {
            "cli_commit": before["cli_commit"],
            "cli_locator": lms_locator,
            "prior_server_running": before["server_running"],
            "prior_server_port": before["server_port"],
            "prior_model_identifiers": before["loaded_model_identifiers"],
            "server_suspended": True,
            "loaded_model_count_after_suspend": 0,
        },
        "backend_process": None,
        "runtime_receipt_sha256": None,
        "restoration": None,
    }
    _atomic_write_state(state_path, state, exclusive=True)
    return state


def _default_port_owner(port: int) -> int | None:
    if os.name == "nt":
        result = subprocess.run(
            ["netstat.exe", "-ano", "-p", "TCP"], check=False,
            capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError("TCP port ownership inspection failed")
        owners: set[int] = set()
        suffix = f":{port}"
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[1].endswith(suffix):
                if fields[3].upper() == "LISTENING" and fields[4].isdigit():
                    owners.add(int(fields[4]))
        if len(owners) > 1:
            raise RuntimeError("multiple processes claim the isolated backend port")
        return next(iter(owners), None)
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("port ownership inspection requires psutil on this platform") from exc
    owners = {
        item.pid for item in psutil.net_connections(kind="tcp")
        if item.status == psutil.CONN_LISTEN and item.laddr and item.laddr.port == port and item.pid
    }
    if len(owners) > 1:
        raise RuntimeError("multiple processes claim the isolated backend port")
    return next(iter(owners), None)


def _process_image_path(pid: int) -> Path | None:
    if pid < 1:
        return None
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_uint32(len(buffer))
            kernel32.QueryFullProcessImageNameW.argtypes = [
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return None
            return Path(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
    proc_link = Path(f"/proc/{pid}/exe")
    try:
        return proc_link.resolve(strict=True)
    except OSError:
        return None


def _default_process_hash(pid: int) -> str | None:
    image = _process_image_path(pid)
    return sha256_file(image) if image is not None and image.is_file() else None


def _default_process_alive(pid: int) -> bool:
    if _process_image_path(pid) is not None:
        return True
    try:
        os.kill(pid, 0)
    # Windows can expose a failed zero-signal probe as ``SystemError`` with an
    # underlying WinError after the process has just exited.  Both exceptions
    # mean the process is not alive once its image path is also absent.
    except (OSError, SystemError):
        return False
    return True


def _sanitized_backend_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    return {key: value for key, value in source.items() if not key.upper().startswith("LLAMA_")}


def _default_binary_identity(executable: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(executable), "--version"],
        cwd=executable.parent,
        env=_sanitized_backend_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError("llama-server version inspection failed")
    combined = result.stdout + "\n" + result.stderr
    release_match = re.search(r"\bversion\s*:\s*([^\s(]+)", combined, re.IGNORECASE)
    build_match = re.search(
        r"\bbuild\s+(\d{4,})\s*,\s*commit\s+([0-9a-f]{7,40})\b",
        combined,
        re.IGNORECASE,
    )
    if not release_match or not build_match:
        raise ValueError("llama-server version output did not contain its build and commit")
    return {
        "release": release_match.group(1),
        "build": int(build_match.group(1)),
        "commit": build_match.group(2).lower(),
    }


def _default_launcher(
    executable: Path, arguments: Sequence[str], working_directory: Path,
    environment: Mapping[str, str],
) -> int:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        [str(executable), *arguments],
        cwd=working_directory,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=creationflags,
    )
    return process.pid


def _default_stopper(pid: int, timeout_s: float) -> None:
    if not _default_process_alive(pid):
        return
    gentle_signal = signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM
    try:
        os.kill(pid, gentle_signal)
    # On Windows, ``os.kill(pid, CTRL_BREAK_EVENT)`` can terminate a process
    # successfully while CPython surfaces WinError 87 as ``SystemError``
    # instead of ``OSError``.  Treat both as a failed gentle-send attempt and
    # let the verified liveness/port loop decide whether escalation is needed.
    except (OSError, SystemError):
        pass
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _default_process_alive(pid):
            return
        time.sleep(0.1)
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x0001, 0, pid)  # PROCESS_TERMINATE
        if not handle:
            raise RuntimeError("verified isolated backend could not be opened for termination")
        try:
            if not kernel32.TerminateProcess(handle, 1):
                raise RuntimeError("verified isolated backend termination failed")
        finally:
            kernel32.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGKILL)


def _backend_arguments(config: dict[str, Any], model_name: str, mmproj_name: str) -> list[str]:
    return [
        "-m", model_name,
        "--mmproj", mmproj_name,
        "-c", str(config["context_length"]),
        "-np", str(config["parallel"]),
        "-dev", config["device"],
        "-sm", config["split_mode"],
        "-ngl", str(config["gpu_layers"]),
        "-fit", "on",
        "-fitt", str(config["fit_target"]),
        "-fitc", str(config["fit_context"]),
        "-b", str(config["batch_size"]),
        "-ub", str(config["micro_batch_size"]),
        "-t", str(config["threads"]),
        "-ctk", config["kv_key_type"],
        "-ctv", config["kv_value_type"],
        "-fa", config["flash_attention"],
        "-kvo",
        "-kvu",
        "-ndio",
        "--mlock",
        "--metrics",
        "--reasoning-format", config["reasoning_format"],
        "--reasoning-budget", str(config["reasoning_budget"]),
        "--reasoning-budget-message", config["reasoning_budget_message"],
        "-a", config["model"],
        "--host", config["host"],
        "--port", str(config["port"]),
        "--no-webui",
    ]


def _wait_for_backend(
    *,
    pid: int,
    config: dict[str, Any],
    binary_sha256: str,
    http_reader: HttpReader,
    port_owner_reader: PortOwnerReader,
    process_hash_reader: ProcessHashReader,
    process_alive_reader: ProcessAliveReader,
    timeout_s: float,
) -> dict[str, Any]:
    base = f"http://{config['host']}:{config['port']}"
    deadline = time.monotonic() + timeout_s
    last_issue = "backend_not_ready"
    while time.monotonic() < deadline:
        if not process_alive_reader(pid):
            raise RuntimeError("isolated backend exited before becoming ready")
        try:
            owner = port_owner_reader(config["port"])
            if owner != pid:
                last_issue = "port_owner"
                time.sleep(0.25)
                continue
            process_hash = process_hash_reader(pid)
            if process_hash != binary_sha256:
                raise RuntimeError("isolated backend process image hash mismatch")
            health = http_reader(base + "/health", 5.0)
            models = http_reader(base + "/v1/models", 5.0)
            data = models.get("data")
            model_ids = sorted(
                item.get("id") for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ) if isinstance(data, list) else []
            health_status = health.get("status")
            if health_status not in {"ok", "ready"}:
                last_issue = "health"
                time.sleep(0.25)
                continue
            if model_ids != [config["model"]]:
                last_issue = "models_api"
                time.sleep(0.25)
                continue
            return {
                "pid": pid,
                "port_owner_pid": owner,
                "process_image_sha256": process_hash,
                "health_status": health_status,
                "served_model_ids": model_ids,
            }
        except RuntimeError as exc:
            last_issue = str(exc)
        time.sleep(0.25)
    raise RuntimeError("isolated backend readiness timed out: " + last_issue)


def _runtime_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError("isolated runtime input file does not exist")
    return {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def start_isolated(
    *,
    state_path: Path,
    receipt_path: Path,
    binary_path: Path,
    model_path: Path,
    mmproj_path: Path,
    lms_executable: Path | None = None,
    runner: CommandRunner = _default_runner,
    http_reader: HttpReader = _read_http_json,
    port_owner_reader: PortOwnerReader = _default_port_owner,
    process_hash_reader: ProcessHashReader = _default_process_hash,
    process_alive_reader: ProcessAliveReader = _default_process_alive,
    process_stopper: ProcessStopper = _default_stopper,
    launcher: ProcessLauncher = _default_launcher,
    binary_identity_reader: BinaryIdentityReader = _default_binary_identity,
    environ: Mapping[str, str] | None = None,
    readiness_timeout_s: float = 180.0,
) -> dict[str, Any]:
    state = _load_state(state_path)
    if state.get("lifecycle_status") != "bionic_suspended":
        raise ValueError("isolated backend can start only from bionic_suspended state")
    if receipt_path.exists():
        raise FileExistsError("refusing to overwrite an existing isolated-runtime receipt")
    config = state["configuration"]
    # A prepare-only state may have been created immediately before the proven
    # --no-webui correction.  Normalize that not-yet-started setting in memory;
    # it is persisted only after a successful owned-server start.
    if config.get("webui_enabled") is True:
        config = dict(config)
        config["webui_enabled"] = False
        state["configuration"] = config
    if config.get("reasoning_budget_message") is True:
        config = dict(config)
        config["reasoning_budget_message"] = DEFAULT_REASONING_BUDGET_MESSAGE
        state["configuration"] = config
    if config.get("webui_enabled") is not False:
        raise ValueError("isolated runtime state has an invalid web UI setting")
    if config.get("reasoning_budget_message") != DEFAULT_REASONING_BUDGET_MESSAGE:
        raise ValueError("isolated runtime state has an invalid reasoning budget message")
    if lms_executable is None:
        lms_executable, _locator = locate_lms()
    bionic_now = _bionic_snapshot(lms_executable, runner)
    if bionic_now["server_running"] is not False or bionic_now["loaded_model_identifiers"] != []:
        raise RuntimeError("Bionic drifted after isolation preparation; refusing to launch the direct backend")
    if port_owner_reader(config["port"]) is not None:
        raise RuntimeError("isolated backend port is already owned")
    binary = binary_path.resolve()
    model_file = model_path.resolve()
    mmproj_file = mmproj_path.resolve()
    if model_file.parent != mmproj_file.parent:
        raise ValueError("model and mmproj files must share a directory so only relative paths enter the process arguments")
    binary_artifact = _runtime_artifact(binary)
    binary_identity = binary_identity_reader(binary)
    if binary_identity != {
        "release": EXPECTED_BINARY_RELEASE,
        "build": EXPECTED_BINARY_BUILD,
        "commit": EXPECTED_BINARY_COMMIT,
    }:
        raise ValueError("isolated backend binary is not the pinned llama.cpp b10566 build")
    model_artifact = _runtime_artifact(model_file)
    mmproj_artifact = _runtime_artifact(mmproj_file)
    arguments = _backend_arguments(config, model_file.name, mmproj_file.name)
    forbidden = {"--api-key", "--api-key-file", "--model-url", "--hf-repo"}
    if forbidden & set(arguments):
        raise ValueError("isolated backend arguments contain a forbidden remote or credential option")
    environment = _sanitized_backend_environment(environ)
    pid = launcher(binary, arguments, model_file.parent, environment)
    try:
        live = _wait_for_backend(
            pid=pid,
            config=config,
            binary_sha256=binary_artifact["sha256"],
            http_reader=http_reader,
            port_owner_reader=port_owner_reader,
            process_hash_reader=process_hash_reader,
            process_alive_reader=process_alive_reader,
            timeout_s=readiness_timeout_s,
        )
    except Exception:
        if process_hash_reader(pid) == binary_artifact["sha256"]:
            process_stopper(pid, 5.0)
        raise
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "isolated_started_and_verified",
        "backend": {
            "kind": "llama.cpp-direct",
            "release": binary_identity["release"],
            "build": binary_identity["build"],
            "commit": binary_identity["commit"],
            "binary_sha256": binary_artifact["sha256"],
            "binary_size_bytes": binary_artifact["size_bytes"],
        },
        "model": {
            "identifier": config["model"],
            "gguf_sha256": model_artifact["sha256"],
            "gguf_size_bytes": model_artifact["size_bytes"],
            "mmproj_sha256": mmproj_artifact["sha256"],
            "mmproj_size_bytes": mmproj_artifact["size_bytes"],
        },
        "requested_settings": {
            "host": config["host"],
            "port": config["port"],
            "endpoint": config["endpoint"],
            "context_length": config["context_length"],
            "gpu_offload": config["gpu_offload"],
            "gpu_layers": config["gpu_layers"],
            "parallel": config["parallel"],
            "device": config["device"],
            "split_mode": config["split_mode"],
            "fit_enabled": config["fit_enabled"],
            "fit_target": config["fit_target"],
            "fit_context": config["fit_context"],
            "batch_size": config["batch_size"],
            "micro_batch_size": config["micro_batch_size"],
            "threads": config["threads"],
            "kv_key_type": config["kv_key_type"],
            "kv_value_type": config["kv_value_type"],
            "flash_attention": config["flash_attention"],
            "kv_offload": config["kv_offload"],
            "kv_unified": config["kv_unified"],
            "device_io_disabled": config["device_io_disabled"],
            "memory_lock": config["memory_lock"],
            "metrics_enabled": config["metrics_enabled"],
            "reasoning_format": config["reasoning_format"],
            "reasoning_budget": config["reasoning_budget"],
            "reasoning_budget_message": config["reasoning_budget_message"],
            "mmproj_enabled": True,
            "webui_enabled": config["webui_enabled"],
            "api_key_configured": False,
        },
        "isolation_verification": {
            "bionic_server_suspended": state["bionic"]["server_suspended"],
            "bionic_loaded_model_count": state["bionic"]["loaded_model_count_after_suspend"],
            "bionic_cli_commit": state["bionic"]["cli_commit"],
            "bionic_cli_locator": state["bionic"]["cli_locator"],
            "owned_pid": live["pid"],
            "port_owner_pid": live["port_owner_pid"],
            "pid_port_owner_match": live["pid"] == live["port_owner_pid"],
            "process_image_sha256": live["process_image_sha256"],
            "process_image_hash_match": live["process_image_sha256"] == binary_artifact["sha256"],
            "health_status": live["health_status"],
            "served_model_ids": live["served_model_ids"],
            "status": "pass",
        },
        "attestation_boundary": (
            "The owned direct backend was launched with one hash-pinned GGUF and mmproj, exact structured "
            "settings, a sanitized environment with all LLAMA_* overrides removed, loopback-only networking, "
            "and no API key. Paths and the process command line are intentionally omitted."
        ),
        "safety": {
            "public_safe": True,
            "contains_credentials": False,
            "contains_process_command_line": False,
            "contains_executable_path": False,
            "contains_model_path": False,
            "contains_private_media_path": False,
        },
    }
    validate_runtime_receipt(
        receipt,
        model=config["model"], endpoint=config["endpoint"],
        context_length=config["context_length"], parallel=config["parallel"],
        gpu_offload=config["gpu_offload"], gpu_layers=config["gpu_layers"],
    )
    write_receipt_exclusive(receipt_path, receipt)
    state["lifecycle_status"] = "isolated_running"
    state["updated_at"] = _utc_now()
    state["backend_process"] = {
        "pid": pid,
        "binary_sha256": binary_artifact["sha256"],
        "model_sha256": model_artifact["sha256"],
        "mmproj_sha256": mmproj_artifact["sha256"],
        "port_owner_verified": True,
        "process_image_verified": True,
        "health_verified": True,
        "models_api_verified": True,
        "started_at": receipt["generated_at"],
    }
    state["runtime_receipt_sha256"] = sha256_file(receipt_path)
    _atomic_write_state(state_path, state)
    return receipt


def validate_runtime_receipt(
    receipt: dict[str, Any],
    *,
    model: str,
    endpoint: str,
    context_length: int = DEFAULT_CONTEXT_LENGTH,
    parallel: int = DEFAULT_PARALLEL,
    gpu_offload: str = "max",
    gpu_layers: str = DEFAULT_GPU_LAYERS,
) -> None:
    _assert_public_safe(receipt)
    required = {
        "schema_version", "generated_at", "status", "backend", "model",
        "requested_settings", "isolation_verification", "attestation_boundary", "safety",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ValueError("isolated runtime receipt has an unexpected schema")
    mismatches: list[str] = []
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        mismatches.append("schema_version")
    if receipt.get("status") != "isolated_started_and_verified":
        mismatches.append("status")
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname != DEFAULT_HOST or not parsed.port or parsed.path.rstrip("/") != "/v1":
        raise ValueError("isolated runtime endpoint must be an explicit 127.0.0.1 /v1 URL")
    expected_settings = {
        "host": DEFAULT_HOST,
        "port": parsed.port,
        "endpoint": endpoint.rstrip("/"),
        "context_length": context_length,
        "gpu_offload": gpu_offload,
        "gpu_layers": gpu_layers,
        "parallel": parallel,
        "device": "CUDA0",
        "split_mode": "none",
        "fit_enabled": True,
        "fit_target": 256,
        "fit_context": 8192,
        "batch_size": 2048,
        "micro_batch_size": 512,
        "threads": 4,
        "kv_key_type": "f16",
        "kv_value_type": "f16",
        "flash_attention": "auto",
        "kv_offload": True,
        "kv_unified": True,
        "device_io_disabled": True,
        "memory_lock": True,
        "metrics_enabled": True,
        "reasoning_format": "deepseek",
        "reasoning_budget": 256,
        "reasoning_budget_message": DEFAULT_REASONING_BUDGET_MESSAGE,
        "mmproj_enabled": True,
        "webui_enabled": False,
        "api_key_configured": False,
    }
    if receipt.get("requested_settings") != expected_settings:
        mismatches.append("requested_settings")
    backend = receipt.get("backend")
    if not isinstance(backend, dict) or set(backend) != {
        "kind", "release", "build", "commit", "binary_sha256", "binary_size_bytes",
    }:
        mismatches.append("backend_schema")
    elif (
        backend.get("kind") != "llama.cpp-direct"
        or backend.get("release") != EXPECTED_BINARY_RELEASE
        or backend.get("build") != EXPECTED_BINARY_BUILD
        or backend.get("commit") != EXPECTED_BINARY_COMMIT
        or not isinstance(backend.get("binary_sha256"), str)
        or not _SHA256.fullmatch(backend["binary_sha256"])
        or not isinstance(backend.get("binary_size_bytes"), int)
        or backend["binary_size_bytes"] <= 0
    ):
        mismatches.append("backend")
    model_record = receipt.get("model")
    if not isinstance(model_record, dict) or set(model_record) != {
        "identifier", "gguf_sha256", "gguf_size_bytes", "mmproj_sha256", "mmproj_size_bytes",
    }:
        mismatches.append("model_schema")
    elif (
        model_record.get("identifier") != model
        or any(not isinstance(model_record.get(key), str) or not _SHA256.fullmatch(model_record[key])
               for key in ("gguf_sha256", "mmproj_sha256"))
        or any(not isinstance(model_record.get(key), int) or model_record[key] <= 0
               for key in ("gguf_size_bytes", "mmproj_size_bytes"))
    ):
        mismatches.append("model")
    verification = receipt.get("isolation_verification")
    if not isinstance(verification, dict) or set(verification) != {
        "bionic_server_suspended", "bionic_loaded_model_count", "bionic_cli_commit",
        "bionic_cli_locator", "owned_pid", "port_owner_pid",
        "pid_port_owner_match", "process_image_sha256", "process_image_hash_match",
        "health_status", "served_model_ids", "status",
    }:
        mismatches.append("isolation_schema")
    elif (
        verification.get("bionic_server_suspended") is not True
        or verification.get("bionic_loaded_model_count") != 0
        or not isinstance(verification.get("bionic_cli_commit"), str)
        or not re.fullmatch(r"[0-9a-f]{7,40}", verification["bionic_cli_commit"])
        or not isinstance(verification.get("bionic_cli_locator"), str)
        or not verification["bionic_cli_locator"]
        or not isinstance(verification.get("owned_pid"), int)
        or verification.get("owned_pid") != verification.get("port_owner_pid")
        or verification.get("pid_port_owner_match") is not True
        or not isinstance(backend, dict)
        or verification.get("process_image_sha256") != backend.get("binary_sha256")
        or verification.get("process_image_hash_match") is not True
        or verification.get("health_status") not in {"ok", "ready"}
        or verification.get("served_model_ids") != [model]
        or verification.get("status") != "pass"
    ):
        mismatches.append("isolation_verification")
    if receipt.get("safety") != {
        "public_safe": True,
        "contains_credentials": False,
        "contains_process_command_line": False,
        "contains_executable_path": False,
        "contains_model_path": False,
        "contains_private_media_path": False,
    }:
        mismatches.append("safety")
    if not isinstance(receipt.get("attestation_boundary"), str) or not receipt["attestation_boundary"]:
        mismatches.append("attestation_boundary")
    if mismatches:
        raise ValueError("isolated runtime receipt does not match expected settings: " + ",".join(sorted(set(mismatches))))


def status_isolated(
    *,
    state_path: Path,
    receipt_path: Path | None = None,
    lms_executable: Path | None = None,
    runner: CommandRunner = _default_runner,
    http_reader: HttpReader = _read_http_json,
    port_owner_reader: PortOwnerReader = _default_port_owner,
    process_hash_reader: ProcessHashReader = _default_process_hash,
    process_alive_reader: ProcessAliveReader = _default_process_alive,
) -> dict[str, Any]:
    state = _load_state(state_path)
    if state.get("lifecycle_status") != "isolated_running":
        return {"status": state.get("lifecycle_status"), "running": False, "checks": {}}
    process = state.get("backend_process")
    if not isinstance(process, dict) or not isinstance(process.get("pid"), int):
        raise ValueError("isolated runtime state is missing its backend process")
    pid = process["pid"]
    config = state["configuration"]
    if lms_executable is None:
        lms_executable, _locator = locate_lms()
    bionic_now = _bionic_snapshot(lms_executable, runner)
    checks = {
        "bionic_server_suspended": bionic_now["server_running"] is False,
        "bionic_models_unloaded": bionic_now["loaded_model_identifiers"] == [],
        "bionic_cli_commit_match": bionic_now["cli_commit"] == state["bionic"]["cli_commit"],
        "process_alive": process_alive_reader(pid),
        "process_image_hash_match": process_hash_reader(pid) == process.get("binary_sha256"),
        "port_owner_match": port_owner_reader(config["port"]) == pid,
        "receipt_hash_match": True,
    }
    if receipt_path is not None:
        checks["receipt_hash_match"] = (
            receipt_path.is_file() and sha256_file(receipt_path) == state.get("runtime_receipt_sha256")
        )
    try:
        health = http_reader(f"http://{config['host']}:{config['port']}/health", 5.0)
        models = http_reader(f"http://{config['host']}:{config['port']}/v1/models", 5.0)
        data = models.get("data")
        served = sorted(
            item.get("id") for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ) if isinstance(data, list) else []
        checks["health"] = health.get("status") in {"ok", "ready"}
        checks["single_expected_model"] = served == [config["model"]]
    except RuntimeError:
        checks["health"] = False
        checks["single_expected_model"] = False
    return {
        "status": "pass" if all(checks.values()) else "drift",
        "running": all(checks.values()),
        "model": config["model"],
        "endpoint": config["endpoint"],
        "checks": checks,
    }


def verify_live_runtime_receipt(
    *,
    receipt_path: Path,
    model: str,
    endpoint: str,
    lms_executable: Path | None = None,
    runner: CommandRunner = _default_runner,
    http_reader: HttpReader = _read_http_json,
    port_owner_reader: PortOwnerReader = _default_port_owner,
    process_hash_reader: ProcessHashReader = _default_process_hash,
    process_alive_reader: ProcessAliveReader = _default_process_alive,
) -> dict[str, Any]:
    """Fail closed if the live owned runtime has drifted since receipt creation."""
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("isolated runtime receipt must be a JSON object")
    validate_runtime_receipt(receipt, model=model, endpoint=endpoint)
    if lms_executable is None:
        lms_executable, _locator = locate_lms()
    bionic_now = _bionic_snapshot(lms_executable, runner)
    verification = receipt["isolation_verification"]
    settings = receipt["requested_settings"]
    backend = receipt["backend"]
    pid = verification["owned_pid"]
    checks = {
        "bionic_server_suspended": bionic_now["server_running"] is False,
        "bionic_models_unloaded": bionic_now["loaded_model_identifiers"] == [],
        "bionic_cli_commit_match": bionic_now["cli_commit"] == verification["bionic_cli_commit"],
        "process_alive": process_alive_reader(pid),
        "process_image_hash_match": process_hash_reader(pid) == backend["binary_sha256"],
        "port_owner_match": port_owner_reader(settings["port"]) == pid,
    }
    try:
        health = http_reader(f"http://{settings['host']}:{settings['port']}/health", 5.0)
        models = http_reader(f"http://{settings['host']}:{settings['port']}/v1/models", 5.0)
        data = models.get("data")
        served = sorted(
            item.get("id") for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ) if isinstance(data, list) else []
        checks["health"] = health.get("status") in {"ok", "ready"}
        checks["single_expected_model"] = served == [model]
    except RuntimeError:
        checks["health"] = False
        checks["single_expected_model"] = False
    drift = sorted(key for key, passed in checks.items() if not passed)
    if drift:
        raise RuntimeError("live isolated runtime drift: " + ",".join(drift))
    return {
        "status": "pass",
        "receipt_sha256": sha256_file(receipt_path),
        "model": model,
        "endpoint": endpoint.rstrip("/"),
        "checks": checks,
    }


def stop_isolated(
    *,
    state_path: Path,
    port_owner_reader: PortOwnerReader = _default_port_owner,
    process_hash_reader: ProcessHashReader = _default_process_hash,
    process_alive_reader: ProcessAliveReader = _default_process_alive,
    process_stopper: ProcessStopper = _default_stopper,
) -> dict[str, Any]:
    state = _load_state(state_path)
    if state.get("lifecycle_status") != "isolated_running":
        raise ValueError("isolated backend can stop only from isolated_running state")
    process = state["backend_process"]
    pid = process["pid"]
    if process_hash_reader(pid) != process["binary_sha256"]:
        raise RuntimeError("refusing to stop a PID whose process image hash is not owned")
    owner = port_owner_reader(state["configuration"]["port"])
    if owner not in {None, pid}:
        raise RuntimeError("refusing to stop because another PID owns the isolated backend port")
    process_stopper(pid, 10.0)
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if not process_alive_reader(pid) and port_owner_reader(state["configuration"]["port"]) is None:
            break
        time.sleep(0.1)
    if process_alive_reader(pid) or port_owner_reader(state["configuration"]["port"]) is not None:
        raise RuntimeError("isolated backend did not stop cleanly")
    state["lifecycle_status"] = "isolated_stopped"
    state["updated_at"] = _utc_now()
    process["stopped_at"] = _utc_now()
    process["stop_verified"] = True
    _atomic_write_state(state_path, state)
    return {"status": "isolated_stopped", "pid": pid, "port_released": True}


def restore_bionic(
    *,
    state_path: Path,
    lms_executable: Path,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    state = _load_state(state_path)
    if state.get("lifecycle_status") not in {"bionic_suspended", "isolated_stopped"}:
        raise ValueError("Bionic can be restored only after suspension or an isolated stop")
    prior_running = state["bionic"]["prior_server_running"]
    prior_port = state["bionic"]["prior_server_port"]
    if prior_running is True:
        if not isinstance(prior_port, int):
            raise ValueError("prior Bionic server port is invalid")
        _run_required(
            lms_executable, ["server", "start", "--port", str(prior_port)], runner=runner,
            operation="LM Studio server restore", timeout_s=60,
        )
    after = _bionic_snapshot(lms_executable, runner)
    if after["server_running"] is not prior_running:
        raise RuntimeError("Bionic server on/off state was not restored")
    if prior_running is True and after["server_port"] != prior_port:
        raise RuntimeError("Bionic server port was not restored")
    state["lifecycle_status"] = "restored"
    state["updated_at"] = _utc_now()
    state["restoration"] = {
        "restored_at": _utc_now(),
        "server_running": after["server_running"],
        "server_port": after["server_port"],
        "models_restored": False,
        "model_restoration_policy": (
            "Prior model identifiers are recorded for audit only; models are not auto-restored because "
            "their prior GPU/context settings were not trustworthy."
        ),
    }
    _atomic_write_state(state_path, state)
    return {"status": "restored", "server_running": after["server_running"], "models_restored": False}


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare = subparsers.add_parser("prepare", help="Stop Bionic's API and unload its models.")
    prepare.add_argument("--state", type=Path, default=DEFAULT_STATE)
    prepare.add_argument("--lms", type=Path)
    prepare.add_argument("--model", default=DEFAULT_MODEL)
    prepare.add_argument("--host", default=DEFAULT_HOST)
    prepare.add_argument("--port", type=int, default=DEFAULT_PORT)
    prepare.add_argument("--context-length", type=int, choices=[DEFAULT_CONTEXT_LENGTH], default=DEFAULT_CONTEXT_LENGTH)
    prepare.add_argument("--gpu-layers", choices=[DEFAULT_GPU_LAYERS], default=DEFAULT_GPU_LAYERS)
    prepare.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)

    start = subparsers.add_parser("start", help="Launch and verify the owned direct llama-server.")
    start.add_argument("--state", type=Path, default=DEFAULT_STATE)
    start.add_argument("--receipt", type=Path, required=True)
    start.add_argument("--binary", type=Path, required=True)
    start.add_argument("--model-file", type=Path, required=True)
    start.add_argument("--mmproj-file", type=Path, required=True)

    status = subparsers.add_parser("status", help="Check PID, port, image hash, health, and model identity.")
    status.add_argument("--state", type=Path, default=DEFAULT_STATE)
    status.add_argument("--receipt", type=Path)

    stop = subparsers.add_parser("stop", help="Stop only the hash-verified owned backend.")
    stop.add_argument("--state", type=Path, default=DEFAULT_STATE)

    restore = subparsers.add_parser("restore", help="Restore Bionic's prior server on/off state.")
    restore.add_argument("--state", type=Path, default=DEFAULT_STATE)
    restore.add_argument("--lms", type=Path)
    return parser


def main() -> int:
    parser = _cli()
    args = parser.parse_args()
    if args.action == "prepare":
        lms, locator = locate_lms(args.lms)
        result = prepare_isolation(
            state_path=args.state, lms_executable=lms, lms_locator=locator,
            model=args.model, host=args.host, port=args.port,
            context_length=args.context_length, gpu_layers=args.gpu_layers,
            parallel=args.parallel,
        )
        output = {"status": result["lifecycle_status"], "configuration": result["configuration"]}
    elif args.action == "start":
        lms, _locator = locate_lms()
        receipt = start_isolated(
            state_path=args.state, receipt_path=args.receipt,
            binary_path=args.binary, model_path=args.model_file, mmproj_path=args.mmproj_file,
            lms_executable=lms,
        )
        output = {
            "status": receipt["status"],
            "model": receipt["model"]["identifier"],
            "endpoint": receipt["requested_settings"]["endpoint"],
            "receipt_sha256": sha256_file(args.receipt),
        }
    elif args.action == "status":
        lms, _locator = locate_lms()
        output = status_isolated(
            state_path=args.state, receipt_path=args.receipt, lms_executable=lms,
        )
        if output["status"] == "drift":
            print(json.dumps(output, indent=2))
            return 2
    elif args.action == "stop":
        output = stop_isolated(state_path=args.state)
    else:
        lms, _locator = locate_lms(args.lms)
        output = restore_bionic(state_path=args.state, lms_executable=lms)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
