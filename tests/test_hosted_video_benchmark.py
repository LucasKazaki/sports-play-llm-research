import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from hosted_video_benchmark import (
    BenchmarkGateError,
    FixtureVideoProvider,
    GeminiVideoProvider,
    MediaProbe,
    ProviderResult,
    ReportValidationError,
    default_media_probe,
    resolve_ffmpeg_executable,
    run_benchmark,
    validate_event_report,
)


def _participant() -> dict:
    return {
        "reference": "attacker in dark kit",
        "team_side": "left_attacking",
        "role": "ball carrier",
        "visible_jersey_number": None,
        "identity_basis": "appearance_only",
        "action": "plays a forward pass",
        "confidence": 0.7,
    }


def valid_report(clip_id: str) -> dict:
    return {
        "schema_version": "playground-coach-event-report-v1",
        "clip_id": clip_id,
        "video_condition": "physically_silent_video_only",
        "window_summary": "A player advances possession with a forward pass.",
        "dominant_phase": "progression",
        "events": [{
            "event_id": "e01",
            "event_type": "progressive_pass",
            "event_subtype": "ground_pass",
            "start_s": 1.0,
            "peak_s": 2.0,
            "end_s": 3.0,
            "phase_of_play": "progression",
            "restart_context": None,
            "team_side": "left_attacking",
            "primary_actor": _participant(),
            "secondary_participants": [],
            "ball_action": "forward ground pass",
            "possession": {
                "team_side": "left_attacking",
                "state": "controlled",
                "confidence": 0.7,
                "visibility_limit": "receiver leaves the frame",
            },
            "origin_pitch_region": "middle third, left half-space",
            "destination_pitch_region": "middle third, central channel",
            "movement_direction": "left to right",
            "action_sequence": ["controls the ball", "plays forward"],
            "tactical_intent": "progress possession",
            "outcome": "receiver contact is not visible",
            "coach_relevance": "review the passing option under light pressure",
            "evidence": [{"timestamp_s": 2.0, "visible_support": "foot-to-ball contact and forward ball motion"}],
            "replay_status": "live_main_camera",
            "alternatives": ["the pass may be lateral due to camera perspective"],
            "uncertainties": ["receiver and completion are not visible"],
            "confidence": 0.7,
            "abstain": False,
            "abstention_reason": None,
        }],
        "report_abstained": False,
        "abstention_reason": None,
        "overall_uncertainty": "Player identity and pass completion are unresolved.",
        "coverage_limit": "Only actions visible in the five-second clip are described.",
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(
    tmp_path: Path,
    *,
    permitted: bool,
    processors: list[str],
    phase: str = "development",
    clip_count: int = 1,
) -> tuple[Path, list[str]]:
    clips = []
    clip_ids = []
    for index in range(clip_count):
        clip_id = f"clip-{index + 1:02d}"
        clip_ids.append(clip_id)
        video = tmp_path / f"{clip_id}.mp4"
        video.write_bytes(b"software-fixture-video-" + str(index).encode("ascii"))
        labels = tmp_path / f"{clip_id}-labels.json"
        commentary = tmp_path / f"{clip_id}-commentary.json"
        labels.write_text(json.dumps({"held_out_event": "secret-label"}), encoding="utf-8")
        commentary.write_text(json.dumps({"auxiliary_text": "commentator words"}), encoding="utf-8")
        clips.append({
            "clip_id": clip_id,
            "video_path": video.name,
            "sha256": _sha(video),
            "mime_type": "video/mp4",
            "rights": {
                "third_party_processing_permitted": permitted,
                "approved_processors": processors,
                "rights_record_id": f"rights-{index + 1:02d}",
                "decision_date": "2026-08-27",
            },
            "held_out": {
                "labels_path": labels.name,
                "commentary_path": commentary.name,
            },
        })
    manifest = {
        "schema_version": "playground-hosted-video-benchmark-input-v1",
        "study_id": "gemini-dev-fixture",
        "protocol_phase": phase,
        "video_condition": "physically_silent_video_only",
        "cost_policy": "zero_spend_only",
        "clips": clips,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, clip_ids


def silent_probe(_path: Path) -> MediaProbe:
    return MediaProbe(video_streams=1, audio_streams=0, duration_s=5.0, probe_tool="test-probe")


class SpyProvider:
    provider_id = "google_gemini"
    remote = True

    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def infer(self, **kwargs) -> ProviderResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return ProviderResult(
            response_text=json.dumps(self.response),
            raw_response={"candidate": self.response},
            model_reported="gemini-test-version",
            provider_metadata={"transport": "spy"},
        )


def private_out(tmp_path: Path) -> Path:
    return tmp_path / "data" / "private" / "gemini-run"


def test_remote_rights_gate_fails_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    provider = SpyProvider(valid_report(clip_ids[0]))
    with pytest.raises(BenchmarkGateError, match="hosted upload refused"):
        run_benchmark(
            manifest_path=manifest,
            private_out=private_out(tmp_path),
            provider=provider,
            model="gemini-test",
            execute_remote=True,
            zero_spend_confirmed=True,
            environment={"GEMINI_API_KEY": "not-written-anywhere"},
            media_probe=silent_probe,
        )
    assert provider.calls == []


def test_remote_credential_gate_fails_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    provider = SpyProvider(valid_report(clip_ids[0]))
    with pytest.raises(BenchmarkGateError, match="credential is absent"):
        run_benchmark(
            manifest_path=manifest,
            private_out=private_out(tmp_path),
            provider=provider,
            model="gemini-test",
            execute_remote=True,
            zero_spend_confirmed=True,
            environment={},
            media_probe=silent_probe,
        )
    assert provider.calls == []


def test_physical_audio_gate_fails_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    provider = SpyProvider(valid_report(clip_ids[0]))
    with pytest.raises(BenchmarkGateError, match="physical silent-video"):
        run_benchmark(
            manifest_path=manifest,
            private_out=private_out(tmp_path),
            provider=provider,
            model="gemini-test",
            execute_remote=True,
            zero_spend_confirmed=True,
            environment={"GEMINI_API_KEY": "runtime-only-value"},
            media_probe=lambda _path: MediaProbe(1, 1, 5.0, "test-probe"),
        )
    assert provider.calls == []


def test_mock_run_seals_primary_before_posthoc_and_preserves_receipts(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    provider = FixtureVideoProvider({clip_id: valid_report(clip_id)})
    out = private_out(tmp_path)
    summary = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=provider,
        model="offline-rich-report-fixture",
        open_held_out=True,
        environment={},
        media_probe=silent_probe,
    )
    assert summary["status"] == "complete_with_posthoc_audit"
    assert summary["runner_sha256"] == hashlib.sha256(
        (PROTOTYPE / "hosted_video_benchmark.py").read_bytes()
    ).hexdigest()
    assert (out / "primary-seal.json").is_file()
    assert (out / "posthoc-audit.json").is_file()
    result = json.loads((out / clip_id / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "complete"
    assert result["model_reported"] == "offline-rich-report-fixture"
    assert result["input_sha256"]
    assert isinstance(result["latency_ms"], int)
    receipt = json.loads((out / clip_id / "request-receipt.json").read_text(encoding="utf-8"))
    assert receipt["held_out_opened_before_request"] is False
    assert receipt["credential_persisted"] is False
    audit = json.loads((out / "posthoc-audit.json").read_text(encoding="utf-8"))
    assert audit["records"][0]["evidence"]["held_out_labels"]["content"]["held_out_event"] == "secret-label"
    assert "not ground truth" in audit["policy"]
    raw = (out / clip_id / "raw-response.json").read_text(encoding="utf-8")
    assert "secret-label" not in raw
    assert "commentator words" not in raw


def test_parse_failure_is_raw_preserved_and_resumable_without_reinvocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    invalid = FixtureVideoProvider({clip_id: {"response_text": "not-json", "raw_response": {"text": "not-json"}}})
    first = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=invalid,
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    assert first["clips"][0]["status"] == "parse_failed"
    assert (out / clip_id / "raw-response.json").is_file()
    assert (out / clip_id / "parse-failure.json").is_file()
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    second = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=replacement,
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    assert second["run_fingerprint"] == first["run_fingerprint"]
    assert second["clips"][0]["status"] == "parse_failed"
    assert replacement.calls == []


def test_runtime_credential_is_redacted_from_provider_failures_and_run_receipts(tmp_path: Path) -> None:
    manifest, _ = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    secret = "runtime-secret-value-that-must-never-appear"
    provider = SpyProvider(error=RuntimeError(f"transport rejected api_key={secret}"))
    out = private_out(tmp_path)
    summary = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=provider,
        model="gemini-test",
        execute_remote=True,
        zero_spend_confirmed=True,
        environment={"GEMINI_API_KEY": secret},
        media_probe=silent_probe,
    )
    assert summary["clips"][0]["status"] == "provider_failed"
    persisted = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*.json"))
    assert secret not in persisted
    assert "[REDACTED]" in persisted
    assert summary["credential"] == {"present": True, "environment_variable": "GEMINI_API_KEY"}


def test_remote_zero_spend_gate_fails_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    provider = SpyProvider(valid_report(clip_ids[0]))
    with pytest.raises(BenchmarkGateError, match="cannot incur spend"):
        run_benchmark(
            manifest_path=manifest,
            private_out=private_out(tmp_path),
            provider=provider,
            model="gemini-test",
            execute_remote=True,
            environment={"GEMINI_API_KEY": "runtime-only-value"},
            media_probe=silent_probe,
        )
    assert provider.calls == []


def test_remote_dry_run_reports_both_gates_without_calling_provider(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    provider = SpyProvider(valid_report(clip_ids[0]))
    result = run_benchmark(
        manifest_path=manifest,
        private_out=private_out(tmp_path),
        provider=provider,
        model="gemini-test",
        dry_run=True,
        environment={},
        media_probe=silent_probe,
    )
    assert result["status"] == "validated_no_inference"
    assert result["rights_ready_for_selected_provider"] is False
    assert result["credential"] == {"present": False, "environment_variable": None}
    assert provider.calls == []


def test_benchmark_phase_enforces_archit_minimum_of_six(tmp_path: Path) -> None:
    manifest, _ = write_manifest(
        tmp_path,
        permitted=False,
        processors=[],
        phase="benchmark",
        clip_count=5,
    )
    with pytest.raises(BenchmarkGateError, match="at least six clips"):
        run_benchmark(
            manifest_path=manifest,
            private_out=private_out(tmp_path),
            provider=FixtureVideoProvider({}),
            model="offline-fixture",
            dry_run=True,
            environment={},
            media_probe=silent_probe,
        )


def test_resume_refuses_mutated_raw_receipt_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    first_provider = FixtureVideoProvider({clip_id: valid_report(clip_id)})
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=first_provider,
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    raw_path = out / clip_id / "raw-response.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["provider_metadata"]["tampered"] = True
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    with pytest.raises(BenchmarkGateError, match="primary seal hash mismatch"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=replacement,
            model="offline-fixture",
            environment={},
            media_probe=silent_probe,
        )
    assert replacement.calls == []


def test_resume_refuses_mutated_request_receipt_before_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=FixtureVideoProvider({clip_id: valid_report(clip_id)}),
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    receipt_path = out / clip_id / "request-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["credential_persisted"] = True
    receipt["rights_record_id"] = "tampered-rights-record"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    # Simulate interruption before the batch-level seal was created; the clip result must still bind the request.
    (out / "primary-seal.json").unlink()
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    with pytest.raises(BenchmarkGateError, match="request receipt hash changed"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=replacement,
            model="offline-fixture",
            environment={},
            media_probe=silent_probe,
        )
    assert replacement.calls == []


def test_resume_refuses_result_mutation_against_existing_primary_seal(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=FixtureVideoProvider({clip_id: valid_report(clip_id)}),
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    result_path = out / clip_id / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["model_reported"] = "tampered-model-version"
    result["latency_ms"] = 999999
    result_path.write_text(json.dumps(result), encoding="utf-8")
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    with pytest.raises(BenchmarkGateError, match="primary seal hash mismatch"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=replacement,
            model="offline-fixture",
            environment={},
            media_probe=silent_probe,
        )
    assert replacement.calls == []


def test_provider_failure_cannot_open_held_out_until_retry_succeeds(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    failing = SpyProvider(error=RuntimeError("fixture transport failure"))
    failing.provider_id = "local_fixture"
    failing.remote = False
    with pytest.raises(BenchmarkGateError, match="provider failures remain retryable"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=failing,
            model="offline-fixture",
            open_held_out=True,
            environment={},
            media_probe=silent_probe,
        )
    assert not (out / "posthoc-audit.json").exists()
    succeeding = SpyProvider(valid_report(clip_id))
    succeeding.provider_id = "local_fixture"
    succeeding.remote = False
    result = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=succeeding,
        model="offline-fixture",
        open_held_out=True,
        environment={},
        media_probe=silent_probe,
    )
    assert len(succeeding.calls) == 1
    assert result["status"] == "complete_with_posthoc_audit"


def test_existing_posthoc_refuses_any_future_provider_invocation(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    failing = SpyProvider(error=RuntimeError("fixture transport failure"))
    failing.provider_id = "local_fixture"
    failing.remote = False
    first = run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=failing,
        model="offline-fixture",
        open_held_out=False,
        environment={},
        media_probe=silent_probe,
    )
    # Simulate a legacy contaminated run that opened held-out evidence despite a retryable failure.
    audit = {
        "schema_version": "playground-hosted-video-posthoc-audit-v1",
        "opened_at": "2026-08-27T00:00:00Z",
        "primary_seal_sha256": first["primary_seal_sha256"],
        "policy": "legacy fixture",
        "records": [],
    }
    audit_path = out / "posthoc-audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_path = out / "run-manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["posthoc_audit_sha256"] = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    succeeding = SpyProvider(valid_report(clip_id))
    succeeding.provider_id = "local_fixture"
    succeeding.remote = False
    with pytest.raises(BenchmarkGateError, match="held-out evidence was already opened"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=succeeding,
            model="offline-fixture",
            environment={},
            media_probe=silent_probe,
        )
    assert succeeding.calls == []


def test_pure_resume_preserves_existing_primary_and_posthoc_seals(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=FixtureVideoProvider({clip_id: valid_report(clip_id)}),
        model="offline-fixture",
        open_held_out=True,
        environment={},
        media_probe=silent_probe,
    )
    seal_hash = hashlib.sha256((out / "primary-seal.json").read_bytes()).hexdigest()
    audit_hash = hashlib.sha256((out / "posthoc-audit.json").read_bytes()).hexdigest()
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=replacement,
        model="offline-fixture",
        open_held_out=True,
        environment={},
        media_probe=silent_probe,
    )
    assert replacement.calls == []
    assert hashlib.sha256((out / "primary-seal.json").read_bytes()).hexdigest() == seal_hash
    assert hashlib.sha256((out / "posthoc-audit.json").read_bytes()).hexdigest() == audit_hash


def test_pure_resume_refuses_mutated_run_manifest_summaries(tmp_path: Path) -> None:
    manifest, clip_ids = write_manifest(tmp_path, permitted=False, processors=[])
    clip_id = clip_ids[0]
    out = private_out(tmp_path)
    run_benchmark(
        manifest_path=manifest,
        private_out=out,
        provider=FixtureVideoProvider({clip_id: valid_report(clip_id)}),
        model="offline-fixture",
        environment={},
        media_probe=silent_probe,
    )
    run_path = out / "run-manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["clips"][0]["latency_ms"] = 999999
    run["counts"]["complete"] = 0
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    replacement = SpyProvider(valid_report(clip_id))
    replacement.provider_id = "local_fixture"
    replacement.remote = False
    with pytest.raises(BenchmarkGateError, match="cached clip summaries changed"):
        run_benchmark(
            manifest_path=manifest,
            private_out=out,
            provider=replacement,
            model="offline-fixture",
            environment={},
            media_probe=silent_probe,
        )
    assert replacement.calls == []


def test_report_validator_rejects_temporally_reversed_event() -> None:
    report = valid_report("clip-01")
    report["events"][0]["start_s"] = 3.0
    report["events"][0]["end_s"] = 1.0
    with pytest.raises(ReportValidationError, match="start_s"):
        validate_event_report(report, clip_id="clip-01", duration_s=5.0)


def test_gemini_adapter_uses_native_video_and_deletes_remote_file() -> None:
    report = valid_report("clip-01")
    uploaded = SimpleNamespace(name="files/test", state=SimpleNamespace(name="ACTIVE"))

    class Files:
        def __init__(self) -> None:
            self.uploads = []
            self.deletes = []

        def upload(self, **kwargs):
            self.uploads.append(kwargs)
            return uploaded

        def get(self, **_kwargs):
            return uploaded

        def delete(self, **kwargs):
            self.deletes.append(kwargs)

    class Response:
        text = json.dumps(report)
        model_version = "gemini-test-001"

        def model_dump(self, **_kwargs):
            return {"model_version": self.model_version, "text": self.text}

    class Models:
        def __init__(self) -> None:
            self.calls = []

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            return Response()

    client = SimpleNamespace(files=Files(), models=Models())
    adapter = GeminiVideoProvider(client_factory=lambda key: client)
    result = adapter.infer(
        clip_id="clip-01",
        video_path=Path("silent.mp4"),
        mime_type="video/mp4",
        prompt="frozen prompt",
        response_schema={"type": "object"},
        model="gemini-test",
        credential="runtime-only",
    )
    assert result.model_reported == "gemini-test-001"
    assert client.files.uploads == [{"file": "silent.mp4", "config": {"mime_type": "video/mp4"}}]
    assert client.files.deletes == [{"name": "files/test"}]
    assert client.models.calls[0]["contents"][0] is uploaded
    assert client.models.calls[0]["config"]["response_mime_type"] == "application/json"


def test_default_media_probe_detects_a_real_physically_silent_fixture(tmp_path: Path) -> None:
    import subprocess

    ffmpeg = str(resolve_ffmpeg_executable())
    target = tmp_path / "silent.mp4"
    completed = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "color=c=black:s=64x64:r=5:d=1", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    probe = default_media_probe(target)
    assert probe.video_streams == 1
    assert probe.audio_streams == 0
    assert probe.duration_s == pytest.approx(1.0, abs=0.05)


@pytest.mark.parametrize("count,accepted", [(5, False), (6, True), (10, True), (15, True), (16, False)])
def test_benchmark_size_boundaries(tmp_path: Path, count, accepted) -> None:
    manifest, _ = write_manifest(tmp_path, permitted=False, processors=[], phase="benchmark", clip_count=count)
    kwargs = dict(manifest_path=manifest, private_out=private_out(tmp_path), provider=FixtureVideoProvider({}),
                  model="offline-fixture", dry_run=True, environment={}, media_probe=silent_probe)
    if accepted:
        assert run_benchmark(**kwargs)["status"] == "validated_no_inference"
    else:
        with pytest.raises(BenchmarkGateError):
            run_benchmark(**kwargs)


def test_retry_history_preserves_repeated_failures_and_success(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[])
    out = private_out(tmp_path)
    provider = SpyProvider(error=RuntimeError("first failure"))
    provider.provider_id = "local_fixture"
    provider.remote = False
    kwargs = dict(manifest_path=manifest, private_out=out, provider=provider,
                  model="offline-fixture", environment={}, media_probe=silent_probe)
    run_benchmark(**kwargs)
    first = (out / ids[0] / "attempts" / "0001" / "provider-failure.json").read_bytes()
    provider.error = RuntimeError("second failure")
    run_benchmark(**kwargs)
    provider.error = None
    provider.response = valid_report(ids[0])
    run_benchmark(**kwargs)
    history = json.loads((out / ids[0] / "attempts-manifest.json").read_text())
    assert [a["status"] for a in history["attempts"]] == ["provider_failed", "provider_failed", "complete"]
    assert (out / ids[0] / "attempts" / "0001" / "provider-failure.json").read_bytes() == first
    assert len(provider.calls) == 3
    run_benchmark(**kwargs)
    assert len(provider.calls) == 3


def test_resume_refuses_tampered_attempt_archive(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[])
    out = private_out(tmp_path)
    kwargs = dict(manifest_path=manifest, private_out=out,
                  provider=FixtureVideoProvider({ids[0]: valid_report(ids[0])}),
                  model="offline-fixture", environment={}, media_probe=silent_probe)
    run_benchmark(**kwargs)
    (out / ids[0] / "attempts" / "0001" / "raw-response.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BenchmarkGateError, match="attempt history hash"):
        run_benchmark(**kwargs)


def test_duplicate_json_keys_are_parse_failures(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[])
    text = json.dumps(valid_report(ids[0]))
    text = text[:-1] + ', "clip_id": "' + ids[0] + '"}'
    result = run_benchmark(manifest_path=manifest, private_out=private_out(tmp_path),
                          provider=FixtureVideoProvider({ids[0]: {"response_text": text, "raw_response": {}}}),
                          model="offline-fixture", environment={}, media_probe=silent_probe)
    assert result["clips"][0]["status"] == "parse_failed"
    assert "duplicate JSON key" in result["clips"][0]["parse_failure"]["error"]


def test_changed_frozen_labels_refused_after_primary_seal(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[])
    data = json.loads(manifest.read_text())
    label = tmp_path / data["clips"][0]["held_out"]["labels_path"]
    data["clips"][0]["held_out"]["labels_sha256"] = _sha(label)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    label.write_text('{"changed": true}', encoding="utf-8")
    out = private_out(tmp_path)
    with pytest.raises(BenchmarkGateError, match="labels changed after freeze"):
        run_benchmark(manifest_path=manifest, private_out=out,
                      provider=FixtureVideoProvider({ids[0]: valid_report(ids[0])}),
                      model="offline-fixture", environment={}, media_probe=silent_probe, open_held_out=True)
    assert (out / "primary-seal.json").exists()
    assert not (out / "posthoc-audit.json").exists()


def test_full_long_raw_and_parsed_responses_are_preserved_after_secret_redaction(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    secret = "sensitive-runtime-fixture-value"
    report = valid_report(ids[0])
    long_text = "start-" + "a" * 3000 + secret + "z" * 3000 + "-end"
    report["overall_uncertainty"] = long_text
    provider = SpyProvider(report)
    out = private_out(tmp_path)
    summary = run_benchmark(
        manifest_path=manifest, private_out=out, provider=provider, model="spy-only-no-network",
        execute_remote=True, zero_spend_confirmed=True, environment={"GEMINI_API_KEY": secret},
        media_probe=silent_probe)
    assert summary["clips"][0]["status"] == "complete"
    raw = json.loads((out / ids[0] / "raw-response.json").read_text(encoding="utf-8"))
    expected_text = json.dumps(report).replace(secret, "[REDACTED]")
    assert len(raw["response_text"]) > 6000
    assert raw["response_text"] == expected_text
    assert json.loads(raw["response_text"])["overall_uncertainty"] == long_text.replace(secret, "[REDACTED]")
    assert raw["provider_response"]["candidate"]["overall_uncertainty"] == long_text.replace(secret, "[REDACTED]")
    normalized = json.loads((out / ids[0] / "event-report.json").read_text(encoding="utf-8"))
    assert normalized["overall_uncertainty"] == long_text.replace(secret, "[REDACTED]")
    for path in out.rglob("*.json"):
        assert secret not in path.read_text(encoding="utf-8")


def _cleanup_fixture_client(report, *, generate_error=None, delete_error=None):
    calls = {"generate": 0, "delete": 0}
    uploaded = SimpleNamespace(name="files/private-fixture-identifier", state=SimpleNamespace(name="ACTIVE"))
    class Files:
        def upload(self, **kwargs):
            return uploaded
        def delete(self, **kwargs):
            calls["delete"] += 1
            if delete_error is not None:
                raise delete_error
    class Models:
        def generate_content(self, **kwargs):
            calls["generate"] += 1
            if generate_error is not None:
                raise generate_error
            return SimpleNamespace(text=json.dumps(report), model_version="mock-reported-version",
                                   model_dump=lambda **kwargs: {"text": json.dumps(report)})
    return SimpleNamespace(files=Files(), models=Models()), calls


def test_successful_generation_survives_cleanup_failure_and_resumes_without_regeneration(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    secret = "cleanup-runtime-test-secret"
    client, calls = _cleanup_fixture_client(
        valid_report(ids[0]), delete_error=RuntimeError("cleanup failed " + secret))
    provider = GeminiVideoProvider(client_factory=lambda key: client)
    out = private_out(tmp_path)
    kwargs = dict(manifest_path=manifest, private_out=out, provider=provider,
                  model="mock-only-no-network", execute_remote=True, zero_spend_confirmed=True,
                  environment={"GEMINI_API_KEY": secret}, media_probe=silent_probe)
    result = run_benchmark(**kwargs)
    assert result["clips"][0]["status"] == "complete"
    raw = json.loads((out / ids[0] / "raw-response.json").read_text(encoding="utf-8"))
    cleanup = raw["provider_metadata"]["remote_file_cleanup"]
    assert cleanup["status"] == "failed"
    assert cleanup["file_name"] == "files/private-fixture-identifier"
    assert cleanup["error_type"] == "RuntimeError"
    assert cleanup["error"] == "cleanup failed [REDACTED]"
    assert json.loads(raw["response_text"]) == valid_report(ids[0])
    assert (out / ids[0] / "event-report.json").exists()
    run_benchmark(**kwargs)
    assert calls == {"generate": 1, "delete": 1}
    assert all(secret not in path.read_text(encoding="utf-8") for path in out.rglob("*.json"))


def test_generation_failure_retains_original_error_and_cleanup_failure(tmp_path: Path) -> None:
    manifest, ids = write_manifest(tmp_path, permitted=True, processors=["google_gemini"])
    client, calls = _cleanup_fixture_client(
        valid_report(ids[0]), generate_error=ValueError("original generation failed"),
        delete_error=RuntimeError("subsequent cleanup failed"))
    out = private_out(tmp_path)
    result = run_benchmark(
        manifest_path=manifest, private_out=out, provider=GeminiVideoProvider(client_factory=lambda key: client),
        model="mock-only-no-network", execute_remote=True, zero_spend_confirmed=True,
        environment={"GEMINI_API_KEY": "fixture-secret"}, media_probe=silent_probe)
    assert result["clips"][0]["status"] == "provider_failed"
    failure = json.loads((out / ids[0] / "provider-failure.json").read_text(encoding="utf-8"))
    assert failure["error_type"] == "ValueError"
    assert failure["error"] == "original generation failed"
    assert failure["provider_metadata"]["remote_file_cleanup"]["status"] == "failed"
    assert failure["provider_metadata"]["remote_file_cleanup"]["error"] == "subsequent cleanup failed"
    assert calls == {"generate": 1, "delete": 1}
