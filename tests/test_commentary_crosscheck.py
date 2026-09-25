from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import socket
import sys
from threading import Thread
from typing import Any
from urllib.error import URLError

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))

from run_commentary_crosscheck import (
    COMMENTARY_ABSTENTION,
    assert_public_summary_redacted,
    commentary_config,
    commentary_response_format,
    load_bound_inputs,
    normalize_commentary_output,
    post_json,
    private_clip_output,
    relation_to_visual,
    require_private_output,
    require_public_summary_output,
    run_crosscheck,
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(tmp_path: Path, *, visual_failure: bool = False, no_segments: bool = False) -> tuple[Path, Path, Path, Path]:
    private = tmp_path / "data" / "private"
    transcript_path = private / "aligned" / "opaque-001-commentary.json"
    segments = [] if no_segments else [{
        "segment_id": "s1",
        "clip_relative_start_s": 1.0,
        "clip_relative_end_s": 3.0,
        "start_s": 101.0,
        "end_s": 103.0,
        "text": "The corner is swung into the penalty area.",
    }]
    transcript = {
        "schema_version": "playground-commentary-evidence-v1",
        "source": "SoccerNet-Echoes",
        "source_half": 1,
        "source_transcript_sha256": "a" * 64,
        "clip_id": "opaque-001",
        "clip_duration_s": 10.0,
        "segments": segments,
    }
    write_json(transcript_path, transcript)
    manifest_path = private / "manifest.json"
    manifest = {
        "schema_version": "playground-soccernet-clips-manifest-v1",
        "split": "train",
        "clips": [{
            "clip_id": "opaque-001",
            "source_half": 1,
            "clip_duration_s": 10.0,
            "ground_truth": {"play_type": "PRIVATE_TRUTH_SENTINEL"},
            "commentary": {
                "path": str(transcript_path),
                "sha256": sha(transcript_path),
                "segment_count": len(segments),
            },
        }],
    }
    write_json(manifest_path, manifest)
    summary_path = tmp_path / "artifacts" / "visual-summary.json"
    completed = [] if visual_failure else [{
        "clip_id": "opaque-001", "prediction": "corner_kick", "abstained": False,
        "private_visual_note": "PRIVATE_VISUAL_SENTINEL",
    }]
    failures = [{"clip_id": "opaque-001", "error_code": "RuntimeError"}] if visual_failure else []
    visual = {
        "schema_version": "playground-soccernet-vlm-pilot-summary-v1",
        "split": "train",
        "model": "vision-model",
        "prompt_sha256": "b" * 64,
        "private_manifest_sha256": sha(manifest_path),
        "counts": {"requested": 1, "completed": len(completed), "failed": len(failures)},
        "clips": completed,
        "failures": failures,
    }
    write_json(summary_path, visual)
    return manifest_path, summary_path, private / "runs", tmp_path / "artifacts" / "commentary-summary.json"


def model_response(label: str = "corner_kick") -> dict[str, Any]:
    return {
        "model": "text-model",
        "choices": [{"message": {"content": json.dumps({
            "play_type": label,
            "confidence": 0.8,
            "abstained": False,
            "evidence_segment_ids": ["s1"],
            "reason": "The call explicitly describes the restart.",
        })}}],
    }


def test_strict_commentary_contract_accepts_supported_and_abstained_outputs() -> None:
    supported = normalize_commentary_output(
        json.loads(model_response()["choices"][0]["message"]["content"]),
        allowed_segment_ids={"s1"},
    )
    assert supported["play_type"] == "corner_kick"
    abstained = normalize_commentary_output({
        "play_type": COMMENTARY_ABSTENTION,
        "confidence": 0,
        "abstained": True,
        "evidence_segment_ids": [],
        "reason": "The words do not identify a play.",
    }, allowed_segment_ids={"s1"})
    assert abstained["abstained"] is True


@pytest.mark.parametrize("mutator", [
    lambda value: value.update(extra="leak"),
    lambda value: value.update(play_type="not_a_label"),
    lambda value: value.update(evidence_segment_ids=["unknown"]),
    lambda value: value.update(abstained="false"),
])
def test_strict_commentary_contract_rejects_malformed_outputs(mutator) -> None:
    value = json.loads(model_response()["choices"][0]["message"]["content"])
    mutator(value)
    with pytest.raises(ValueError):
        normalize_commentary_output(value, allowed_segment_ids={"s1"})


def test_commentary_response_format_constrains_labels_and_segment_ids() -> None:
    response_format = commentary_response_format({"s2", "s1"})
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    abstention, prediction = response_format["json_schema"]["schema"]["oneOf"]
    assert abstention["properties"]["play_type"]["const"] == COMMENTARY_ABSTENTION
    assert prediction["properties"]["evidence_segment_ids"]["items"]["enum"] == ["s1", "s2"]
    assert "direct_free_kick" in prediction["properties"]["play_type"]["enum"]


def test_relations_never_override_visual_prediction() -> None:
    assert relation_to_visual(
        visual_prediction="corner_kick", visual_abstained=False,
        commentary_prediction="corner_kick", commentary_abstained=False,
    ) == ("supports", "same_non_abstained_label")
    assert relation_to_visual(
        visual_prediction="goal", visual_abstained=False,
        commentary_prediction="corner_kick", commentary_abstained=False,
    ) == ("contradicts", "different_non_abstained_labels")
    assert relation_to_visual(
        visual_prediction="insufficient_visual_evidence", visual_abstained=True,
        commentary_prediction="corner_kick", commentary_abstained=False,
    )[0] == "uninformative"


def test_run_seals_before_transcript_request_and_redacts_public_summary(tmp_path: Path) -> None:
    manifest, visual, private_out, public_out = make_fixture(tmp_path)
    captured: dict[str, Any] = {}

    def fake_request(endpoint: str, payload: dict[str, Any], timeout_s: int) -> dict[str, Any]:
        assert (private_out / "visual-seal.json").is_file()
        captured["payload"] = payload
        return model_response()

    summary = run_crosscheck(
        manifest_path=manifest,
        visual_summary_path=visual,
        private_out=private_out,
        public_summary_path=public_out,
        endpoint="http://127.0.0.1:1234/v1",
        model="text-model",
        request_fn=fake_request,
    )
    assert summary["counts"] == {
        "requested": 1,
        "visual_predictions_sealed": 1,
        "crosschecks_completed": 1,
        "text_model_queried": 1,
        "text_model_completed": 1,
        "no_aligned_commentary": 0,
        "failed_or_not_evaluated": 0,
        "supports": 1,
        "contradicts": 0,
        "uninformative": 0,
    }
    assert summary["clips"][0]["visual_prediction"] == "corner_kick"
    assert summary["clips"][0]["relation"] == "supports"
    assert summary["primary_visual_predictions_unchanged"] is True
    run_receipt = json.loads((private_out / "run-receipt.json").read_text(encoding="utf-8"))
    assert run_receipt["public_summary_sha256"] == sha(public_out)
    assert run_receipt["config_sha256"] == summary["commentary_config_sha256"]
    config_path = private_out / "commentary-config.json"
    assert config_path.is_file()
    assert run_receipt["config_file_sha256"] == sha(config_path)
    clip_receipt = json.loads((private_out / "opaque-001" / "receipt.json").read_text(encoding="utf-8"))
    assert clip_receipt["config_file_sha256"] == sha(config_path)
    public_text = public_out.read_text(encoding="utf-8")
    assert "The corner is swung" not in public_text
    assert "data/private" not in public_text.replace("\\", "/")
    user_payload = json.loads(captured["payload"]["messages"][1]["content"])
    assert set(user_payload) == {
        "aligned_asr_segments", "clip_duration_s", "target_relative_s", "evidence_policy",
    }
    assert user_payload["clip_duration_s"] == 10.0
    assert user_payload["target_relative_s"] == 5.0
    assert set(user_payload["aligned_asr_segments"][0]) == {
        "segment_id", "relative_start_s", "relative_end_s", "text",
    }
    serialized_request = json.dumps(captured["payload"])
    assert "PRIVATE_TRUTH_SENTINEL" not in serialized_request
    assert "PRIVATE_VISUAL_SENTINEL" not in serialized_request
    assert captured["payload"]["response_format"]["type"] == "json_schema"


def test_visual_failure_is_explicit_in_requested_set_and_skips_text_model(tmp_path: Path) -> None:
    manifest, visual, private_out, public_out = make_fixture(tmp_path, visual_failure=True)
    called = False

    def should_not_run(endpoint: str, payload: dict[str, Any], timeout_s: int) -> dict[str, Any]:
        nonlocal called
        called = True
        return model_response()

    with pytest.raises(RuntimeError, match="not evaluated"):
        run_crosscheck(
            manifest_path=manifest, visual_summary_path=visual,
            private_out=private_out, public_summary_path=public_out,
            endpoint="http://localhost:1234/v1", model="text-model", request_fn=should_not_run,
        )
    assert called is False
    summary = json.loads(public_out.read_text(encoding="utf-8"))
    assert summary["counts"]["requested"] == 1
    assert summary["counts"]["crosschecks_completed"] == 0
    assert summary["counts"]["failed_or_not_evaluated"] == 1
    assert summary["metrics"]["crosscheck_completion_rate_requested_set"] == 0
    assert summary["failures"] == [{
        "clip_id": "opaque-001", "error_code": "VisualPredictionUnavailable", "stage": "visual_seal",
    }]


def test_no_aligned_segments_yields_deterministic_uninformative_result(tmp_path: Path) -> None:
    manifest, visual, private_out, public_out = make_fixture(tmp_path, no_segments=True)
    summary = run_crosscheck(
        manifest_path=manifest, visual_summary_path=visual,
        private_out=private_out, public_summary_path=public_out,
        endpoint="http://127.0.0.1:1234/v1", model="text-model",
        request_fn=lambda *_: pytest.fail("model must not be called without aligned commentary"),
    )
    assert summary["counts"]["no_aligned_commentary"] == 1
    assert summary["counts"]["text_model_queried"] == 0
    assert summary["clips"][0]["relation"] == "uninformative"


def test_mismatched_manifest_binding_is_rejected_before_crosscheck(tmp_path: Path) -> None:
    manifest, visual, _, _ = make_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["split"] = "valid"
    write_json(manifest, payload)
    with pytest.raises(ValueError, match="not bound"):
        load_bound_inputs(manifest, visual)


@pytest.mark.parametrize("duration", [4.9, 10.1, float("inf"), "10"])
def test_manifest_rejects_clip_outside_five_to_ten_second_contract(tmp_path: Path, duration: Any) -> None:
    manifest, visual, _, _ = make_fixture(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["clips"][0]["clip_duration_s"] = duration
    write_json(manifest, manifest_payload)
    visual_payload = json.loads(visual.read_text(encoding="utf-8"))
    visual_payload["private_manifest_sha256"] = sha(manifest)
    write_json(visual, visual_payload)
    with pytest.raises(ValueError, match="between 5 and 10 seconds"):
        load_bound_inputs(manifest, visual)


def test_manifest_rejects_empty_requested_set(tmp_path: Path) -> None:
    manifest, visual, _, _ = make_fixture(tmp_path)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["clips"] = []
    write_json(manifest, manifest_payload)
    visual_payload = json.loads(visual.read_text(encoding="utf-8"))
    visual_payload["private_manifest_sha256"] = sha(manifest)
    visual_payload["clips"] = []
    visual_payload["failures"] = []
    visual_payload["counts"] = {"requested": 0, "completed": 0, "failed": 0}
    write_json(visual, visual_payload)
    with pytest.raises(ValueError, match="at least one clip"):
        load_bound_inputs(manifest, visual)


def test_private_boundary_and_public_redaction_are_fail_closed(tmp_path: Path) -> None:
    private = tmp_path / "data" / "private" / "runs"
    assert require_private_output(private) == private.resolve()
    with pytest.raises(ValueError, match="data/private"):
        require_private_output(tmp_path / "artifacts" / "runs")
    assert require_public_summary_output(tmp_path / "artifacts" / "summary.json") == (
        tmp_path / "artifacts" / "summary.json"
    ).resolve()
    with pytest.raises(ValueError, match="must not be written under data/private"):
        require_public_summary_output(tmp_path / "data" / "private" / "summary.json")
    with pytest.raises(ValueError, match="private or absolute path"):
        assert_public_summary_redacted({"clips": [{"value": str(private)}]})
    for leaked in (
        "data/private/transcript.json",
        "../data/private/transcript.json",
        "/var/data/private/transcript.json",
        r"\\server\share\data\private\transcript.json",
        r"C:\data\private\transcript.json",
        r"C:data\private\transcript.json",
        "data/private",
    ):
        with pytest.raises(ValueError, match="private or absolute path"):
            assert_public_summary_redacted({"value": leaked})
    with pytest.raises(ValueError, match="forbidden private field"):
        assert_public_summary_redacted({"transcript_path": "opaque-relative-name.json"})


def test_text_model_endpoint_must_be_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        commentary_config(endpoint="https://example.com/v1", model="text-model", max_tokens=100, timeout_s=30)


@pytest.mark.parametrize(("max_tokens", "timeout_s"), [(0, 30), (100, 0), (True, 30), (100, False)])
def test_text_model_config_requires_positive_integer_limits(max_tokens: Any, timeout_s: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        commentary_config(
            endpoint="http://127.0.0.1:1234/v1",
            model="text-model",
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )


def test_manifest_with_private_paths_cannot_be_loaded_from_public_artifacts(tmp_path: Path) -> None:
    manifest, visual, _, _ = make_fixture(tmp_path)
    public_manifest = tmp_path / "artifacts" / "manifest.json"
    write_json(public_manifest, json.loads(manifest.read_text(encoding="utf-8")))
    visual_payload = json.loads(visual.read_text(encoding="utf-8"))
    visual_payload["private_manifest_sha256"] = sha(public_manifest)
    write_json(visual, visual_payload)
    with pytest.raises(ValueError, match="data/private"):
        load_bound_inputs(public_manifest, visual)


def test_clip_id_cannot_escape_private_output_root(tmp_path: Path) -> None:
    private_out = tmp_path / "data" / "private" / "runs"
    with pytest.raises(ValueError, match="opaque single path component"):
        private_clip_output(private_out, r"..\..\..\artifacts\escaped")
    with pytest.raises(ValueError, match="opaque single path component"):
        private_clip_output(private_out, "../escaped")
    assert private_clip_output(private_out, "valid-6007fdf7-h1-001") == (
        private_out / "valid-6007fdf7-h1-001"
    ).resolve()


def test_reported_model_mismatch_fails_attribution_and_requested_set(tmp_path: Path) -> None:
    manifest, visual, private_out, public_out = make_fixture(tmp_path)
    response = model_response()
    response["model"] = "different-model"
    with pytest.raises(RuntimeError, match="failed or were not evaluated"):
        run_crosscheck(
            manifest_path=manifest,
            visual_summary_path=visual,
            private_out=private_out,
            public_summary_path=public_out,
            endpoint="http://127.0.0.1:1234/v1",
            model="text-model",
            request_fn=lambda *_: response,
        )
    summary = json.loads(public_out.read_text(encoding="utf-8"))
    assert summary["counts"]["requested"] == 1
    assert summary["counts"]["text_model_queried"] == 1
    assert summary["counts"]["text_model_completed"] == 0
    assert summary["counts"]["failed_or_not_evaluated"] == 1
    assert summary["failures"][0]["error_code"] == "ValueError"
    assert (private_out / "opaque-001" / "raw-response.json").is_file()


def test_public_summary_cannot_overwrite_sealed_visual_input(tmp_path: Path) -> None:
    manifest, visual, private_out, _ = make_fixture(tmp_path)
    original_visual_sha = sha(visual)
    with pytest.raises(ValueError, match="must not overwrite"):
        run_crosscheck(
            manifest_path=manifest,
            visual_summary_path=visual,
            private_out=private_out,
            public_summary_path=visual,
            endpoint="http://127.0.0.1:1234/v1",
            model="text-model",
            request_fn=lambda *_: model_response(),
        )
    assert sha(visual) == original_visual_sha


@pytest.mark.parametrize("bound_input", ["manifest", "visual"])
def test_public_summary_hardlink_cannot_alias_bound_input(tmp_path: Path, bound_input: str) -> None:
    manifest, visual, private_out, public_out = make_fixture(tmp_path)
    source = manifest if bound_input == "manifest" else visual
    public_out.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, public_out)
    original_sha = sha(source)
    assert os.path.samefile(source, public_out)
    with pytest.raises(ValueError, match="must not overwrite"):
        run_crosscheck(
            manifest_path=manifest,
            visual_summary_path=visual,
            private_out=private_out,
            public_summary_path=public_out,
            endpoint="http://127.0.0.1:1234/v1",
            model="text-model",
            request_fn=lambda *_: model_response(),
        )
    assert sha(source) == original_sha


def test_post_json_rejects_redirect_without_contacting_target() -> None:
    target_hits: list[str] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            target_hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, format: str, *args: Any) -> None:
            pass

    target = HTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    target_url = f"http://127.0.0.1:{target.server_port}/redirect-target"

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(302)
            self.send_header("Location", target_url)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    source = HTTPServer(("127.0.0.1", 0), RedirectHandler)
    source_thread = Thread(target=source.serve_forever, daemon=True)
    source_thread.start()
    try:
        with pytest.raises(RuntimeError, match="HTTP 302"):
            post_json(
                f"http://127.0.0.1:{source.server_port}/v1",
                {"model": "text-model", "secret": "asr"},
                5,
            )
        assert target_hits == []
    finally:
        source.shutdown()
        target.shutdown()
        source.server_close()
        target.server_close()
        source_thread.join(timeout=2)
        target_thread.join(timeout=2)


def test_post_json_ignores_environment_proxy_for_asr_request(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy_hits: list[str] = []

    class ProxyHandlerProbe(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            proxy_hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"model":"text-model","choices":[]}')

        def log_message(self, format: str, *args: Any) -> None:
            pass

    proxy = HTTPServer(("127.0.0.1", 0), ProxyHandlerProbe)
    proxy_thread = Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        unavailable_port = reservation.getsockname()[1]
    proxy_url = f"http://127.0.0.1:{proxy.server_port}"
    monkeypatch.setenv("HTTP_PROXY", proxy_url)
    monkeypatch.setenv("HTTPS_PROXY", proxy_url)
    monkeypatch.setenv("NO_PROXY", "")
    try:
        with pytest.raises(URLError):
            post_json(
                f"http://127.0.0.1:{unavailable_port}/v1",
                {"model": "text-model", "secret": "asr"},
                1,
            )
        assert proxy_hits == []
    finally:
        proxy.shutdown()
        proxy.server_close()
        proxy_thread.join(timeout=2)
