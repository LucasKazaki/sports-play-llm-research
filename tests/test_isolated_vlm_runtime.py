import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

import isolated_vlm_runtime as runtime
from prepare_local_vlm_runtime import CommandResult, prepare_runtime, sha256_file


PINNED_BINARY = {"release": "0.2.0-dev", "build": 10566, "commit": "bb4caa754"}


def test_binary_identity_parses_actual_windows_llama_cpp_version(monkeypatch, tmp_path: Path) -> None:
    observed = "version: 0.2.0-dev (build 10566, commit bb4caa754)\n"

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=observed, stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    assert runtime._default_binary_identity(tmp_path / "llama-server.exe") == PINNED_BINARY


class FakeLms:
    def __init__(self) -> None:
        self.server_running = True
        self.server_port = 1234
        self.models = ["google/gemma-4-e4b", "openai/gpt-oss-20b"]
        self.calls: list[list[str]] = []

    def __call__(self, _executable: Path, arguments, _timeout_s: float) -> CommandResult:
        args = list(arguments)
        self.calls.append(args)
        if args == ["--version"]:
            return CommandResult(0, "CLI commit: 71bd99c\n", "")
        if args == ["server", "status", "--json"]:
            return CommandResult(0, json.dumps({
                "running": self.server_running,
                "port": self.server_port if self.server_running else None,
            }), "")
        if args == ["ps", "--json"]:
            return CommandResult(0, json.dumps([
                {"identifier": identifier} for identifier in self.models
            ]), "")
        if args == ["server", "stop"]:
            self.server_running = False
            return CommandResult(0, "stopped", "")
        if args == ["unload", "--all"]:
            self.models = []
            return CommandResult(0, "unloaded", "")
        if args[:3] == ["server", "start", "--port"]:
            self.server_running = True
            self.server_port = int(args[3])
            return CommandResult(0, "started", "")
        raise AssertionError(f"unexpected fake LMS call: {args}")


def _prepare(tmp_path: Path, fake: FakeLms) -> Path:
    state = tmp_path / ".agent" / "isolated-state.json"
    runtime.prepare_isolation(
        state_path=state,
        lms_executable=tmp_path / "lms.exe",
        lms_locator="test_locator",
        model="google/gemma-4-e4b",
        host="127.0.0.1",
        port=1240,
        context_length=8192,
        gpu_layers="all",
        parallel=1,
        runner=fake,
    )
    return state


def test_shared_bionic_prepare_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="shared Bionic preparation is disabled"):
        prepare_runtime(
            executable=tmp_path / "lms.exe",
            locator="test",
            endpoint="http://127.0.0.1:1234/v1",
            model="google/gemma-4-e4b",
            context_length=8192,
            parallel=1,
            gpu_offload="max",
            ttl_seconds=3600,
        )


def test_prepare_closes_api_before_unloading_and_persists_no_paths(tmp_path: Path) -> None:
    fake = FakeLms()
    state_path = _prepare(tmp_path, fake)
    assert fake.calls.index(["server", "stop"]) < fake.calls.index(["unload", "--all"])
    state_text = state_path.read_text(encoding="utf-8")
    state = json.loads(state_text)
    assert state["lifecycle_status"] == "bionic_suspended"
    assert state["bionic"]["prior_model_identifiers"] == [
        "google/gemma-4-e4b", "openai/gpt-oss-20b",
    ]
    assert state["bionic"]["loaded_model_count_after_suspend"] == 0
    assert str(tmp_path) not in state_text
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        runtime.prepare_isolation(
            state_path=state_path,
            lms_executable=tmp_path / "lms.exe",
            lms_locator="test_locator",
            model="google/gemma-4-e4b",
            host="127.0.0.1",
            port=1240,
            context_length=8192,
            gpu_layers="all",
            parallel=1,
            runner=fake,
        )


def test_start_hashes_inputs_uses_relative_model_args_and_writes_public_receipt(tmp_path: Path) -> None:
    fake = FakeLms()
    state_path = _prepare(tmp_path, fake)
    backend = tmp_path / "runtime" / "llama-server.exe"
    model_dir = tmp_path / "models" / "gemma"
    model = model_dir / "model.gguf"
    mmproj = model_dir / "mmproj.gguf"
    backend.parent.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    backend.write_bytes(b"backend-binary")
    model.write_bytes(b"model-weights")
    mmproj.write_bytes(b"vision-projector")
    receipt_path = tmp_path / "artifacts" / "runtime-receipt.json"
    pid = 4242
    launch: dict[str, object] = {}
    port_calls = 0

    def launcher(executable: Path, arguments, cwd: Path, environment) -> int:
        launch.update(executable=executable, arguments=list(arguments), cwd=cwd, environment=dict(environment))
        return pid

    def port_owner(_port: int) -> int | None:
        nonlocal port_calls
        port_calls += 1
        return None if port_calls == 1 else pid

    def http_reader(url: str, _timeout: float):
        if url.endswith("/health"):
            return {"status": "ok"}
        return {"data": [{"id": "google/gemma-4-e4b", "object": "model"}]}

    receipt = runtime.start_isolated(
        state_path=state_path,
        receipt_path=receipt_path,
        binary_path=backend,
        model_path=model,
        mmproj_path=mmproj,
        lms_executable=tmp_path / "lms.exe",
        runner=fake,
        http_reader=http_reader,
        port_owner_reader=port_owner,
        process_hash_reader=lambda _pid: sha256_file(backend),
        process_alive_reader=lambda _pid: True,
        process_stopper=lambda _pid, _timeout: None,
        launcher=launcher,
        binary_identity_reader=lambda _path: PINNED_BINARY,
        environ={"PATH": "safe", "LLAMA_API_KEY": "must-not-propagate", "LLAMA_ARG_CTX_SIZE": "99999"},
        readiness_timeout_s=1,
    )
    args = launch["arguments"]
    assert str(model) not in args
    assert str(mmproj) not in args
    assert args == [
        "-m", "model.gguf", "--mmproj", "mmproj.gguf",
        "-c", "8192", "-np", "1", "-dev", "CUDA0", "-sm", "none", "-ngl", "all",
        "-fit", "on", "-fitt", "256", "-fitc", "8192", "-b", "2048", "-ub", "512",
        "-t", "4", "-ctk", "f16", "-ctv", "f16", "-fa", "auto", "-kvo", "-kvu",
        "-ndio", "--mlock", "--metrics", "--reasoning-format", "deepseek",
        "--reasoning-budget", "256", "--reasoning-budget-message", "I have to answer now.",
        "-a", "google/gemma-4-e4b", "--host", "127.0.0.1",
        "--port", "1240", "--no-webui",
    ]
    assert all(not key.startswith("LLAMA_") for key in launch["environment"])
    assert receipt["backend"]["binary_sha256"] == sha256_file(backend)
    assert receipt["model"]["gguf_sha256"] == sha256_file(model)
    assert receipt["model"]["mmproj_sha256"] == sha256_file(mmproj)
    assert receipt["requested_settings"] == {
        "host": "127.0.0.1",
        "port": 1240,
        "endpoint": "http://127.0.0.1:1240/v1",
        "context_length": 8192,
        "gpu_offload": "max",
        "gpu_layers": "all",
        "parallel": 1,
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
        "reasoning_budget_message": "I have to answer now.",
        "mmproj_enabled": True,
        "webui_enabled": False,
        "api_key_configured": False,
    }
    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in receipt_text
    assert "must-not-propagate" not in receipt_text
    assert '"process_command_line"' not in receipt_text
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["lifecycle_status"] == "isolated_running"
    assert state["configuration"]["webui_enabled"] is False
    assert state["runtime_receipt_sha256"] == sha256_file(receipt_path)


def test_start_refuses_occupied_port_before_launch(tmp_path: Path) -> None:
    fake = FakeLms()
    state_path = _prepare(tmp_path, fake)
    file_path = tmp_path / "same" / "file.gguf"
    file_path.parent.mkdir()
    file_path.write_bytes(b"x")
    called = False

    def launcher(*_args):
        nonlocal called
        called = True
        return 1

    with pytest.raises(RuntimeError, match="port is already owned"):
        runtime.start_isolated(
            state_path=state_path,
            receipt_path=tmp_path / "artifacts" / "receipt.json",
            binary_path=file_path,
            model_path=file_path,
            mmproj_path=file_path,
            lms_executable=tmp_path / "lms.exe",
            runner=fake,
            port_owner_reader=lambda _port: 999,
            launcher=launcher,
            binary_identity_reader=lambda _path: PINNED_BINARY,
        )
    assert called is False


def test_receipt_validation_rejects_settings_or_hash_tampering(tmp_path: Path) -> None:
    fake = FakeLms()
    state_path = _prepare(tmp_path, fake)
    files = tmp_path / "files"
    files.mkdir()
    backend = files / "backend.exe"
    model = files / "model.gguf"
    mmproj = files / "mmproj.gguf"
    for path, payload in ((backend, b"b"), (model, b"m"), (mmproj, b"v")):
        path.write_bytes(payload)
    calls = 0

    def owner(_port: int):
        nonlocal calls
        calls += 1
        return None if calls == 1 else 11

    receipt = runtime.start_isolated(
        state_path=state_path,
        receipt_path=tmp_path / "artifacts" / "receipt.json",
        binary_path=backend,
        model_path=model,
        mmproj_path=mmproj,
        lms_executable=tmp_path / "lms.exe",
        runner=fake,
        http_reader=lambda url, _timeout: (
            {"status": "ready"} if url.endswith("health")
            else {"data": [{"id": "google/gemma-4-e4b"}]}
        ),
        port_owner_reader=owner,
        process_hash_reader=lambda _pid: sha256_file(backend),
        process_alive_reader=lambda _pid: True,
        launcher=lambda *_args: 11,
        binary_identity_reader=lambda _path: PINNED_BINARY,
        readiness_timeout_s=1,
    )
    receipt["requested_settings"]["context_length"] = 4096
    with pytest.raises(ValueError, match="requested_settings"):
        runtime.validate_runtime_receipt(
            receipt,
            model="google/gemma-4-e4b",
            endpoint="http://127.0.0.1:1240/v1",
        )
    receipt["requested_settings"]["context_length"] = 8192
    receipt["backend"]["binary_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="isolation_verification"):
        runtime.validate_runtime_receipt(
            receipt,
            model="google/gemma-4-e4b",
            endpoint="http://127.0.0.1:1240/v1",
        )


def test_status_stop_and_restore_enforce_owned_pid_and_do_not_restore_models(tmp_path: Path) -> None:
    fake = FakeLms()
    state_path = _prepare(tmp_path, fake)
    files = tmp_path / "files"
    files.mkdir()
    backend = files / "backend.exe"
    model = files / "model.gguf"
    mmproj = files / "mmproj.gguf"
    for path in (backend, model, mmproj):
        path.write_bytes(path.name.encode())
    start_owner_calls = 0

    def start_owner(_port: int):
        nonlocal start_owner_calls
        start_owner_calls += 1
        return None if start_owner_calls == 1 else 77

    receipt_path = tmp_path / "artifacts" / "receipt.json"
    runtime.start_isolated(
        state_path=state_path,
        receipt_path=receipt_path,
        binary_path=backend,
        model_path=model,
        mmproj_path=mmproj,
        lms_executable=tmp_path / "lms.exe",
        runner=fake,
        http_reader=lambda url, _timeout: (
            {"status": "ok"} if url.endswith("health")
            else {"data": [{"id": "google/gemma-4-e4b"}]}
        ),
        port_owner_reader=start_owner,
        process_hash_reader=lambda _pid: sha256_file(backend),
        process_alive_reader=lambda _pid: True,
        launcher=lambda *_args: 77,
        binary_identity_reader=lambda _path: PINNED_BINARY,
        readiness_timeout_s=1,
    )
    status = runtime.status_isolated(
        state_path=state_path,
        receipt_path=receipt_path,
        lms_executable=tmp_path / "lms.exe",
        runner=fake,
        http_reader=lambda url, _timeout: (
            {"status": "ok"} if url.endswith("health")
            else {"data": [{"id": "google/gemma-4-e4b"}]}
        ),
        port_owner_reader=lambda _port: 77,
        process_hash_reader=lambda _pid: sha256_file(backend),
        process_alive_reader=lambda _pid: True,
    )
    assert status["status"] == "pass"
    alive = True
    owner = 77

    def stopper(_pid: int, _timeout: float):
        nonlocal alive, owner
        alive = False
        owner = None

    stopped = runtime.stop_isolated(
        state_path=state_path,
        port_owner_reader=lambda _port: owner,
        process_hash_reader=lambda _pid: sha256_file(backend),
        process_alive_reader=lambda _pid: alive,
        process_stopper=stopper,
    )
    assert stopped == {"status": "isolated_stopped", "pid": 77, "port_released": True}
    restored = runtime.restore_bionic(
        state_path=state_path,
        lms_executable=tmp_path / "lms.exe",
        runner=fake,
    )
    assert restored == {"status": "restored", "server_running": True, "models_restored": False}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["lifecycle_status"] == "restored"
    assert state["restoration"]["models_restored"] is False
    assert fake.models == []


def test_stop_refuses_process_image_hash_mismatch(tmp_path: Path) -> None:
    state_path = tmp_path / ".agent" / "state.json"
    state_path.parent.mkdir()
    state = {
        "schema_version": runtime.STATE_SCHEMA_VERSION,
        "lifecycle_status": "isolated_running",
        "created_at": "2026-08-27T00:00:00+00:00",
        "updated_at": "2026-08-27T00:00:00+00:00",
        "configuration": {"port": 1240},
        "bionic": {},
        "backend_process": {"pid": 55, "binary_sha256": "a" * 64},
        "runtime_receipt_sha256": "b" * 64,
        "restoration": None,
    }
    runtime._atomic_write_state(state_path, state, exclusive=True)
    with pytest.raises(RuntimeError, match="process image hash is not owned"):
        runtime.stop_isolated(
            state_path=state_path,
            port_owner_reader=lambda _port: 55,
            process_hash_reader=lambda _pid: "c" * 64,
            process_alive_reader=lambda _pid: True,
            process_stopper=lambda _pid, _timeout: pytest.fail("must not stop unowned process"),
        )


def test_default_stopper_tolerates_windows_ctrl_break_systemerror(monkeypatch: pytest.MonkeyPatch) -> None:
    alive = iter([True, False])

    monkeypatch.setattr(runtime.os, "name", "nt")
    monkeypatch.setattr(runtime, "_default_process_alive", lambda _pid: next(alive))

    def raise_system_error(_pid: int, _signal: int) -> None:
        raise SystemError("CTRL_BREAK_EVENT surfaced WinError 87")

    monkeypatch.setattr(runtime.os, "kill", raise_system_error)

    runtime._default_stopper(77, 1.0)


def test_default_process_alive_treats_windows_zero_signal_systemerror_as_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_process_image_path", lambda _pid: None)

    def raise_system_error(_pid: int, _signal: int) -> None:
        raise SystemError("zero-signal probe surfaced WinError 87")

    monkeypatch.setattr(runtime.os, "kill", raise_system_error)

    assert runtime._default_process_alive(77) is False
