"""Create a private six-clip synthetic harness/scoring receipt, with zero model calls.

The videos are generated color screens. Event reports and labels are invented
software fixtures and demonstrate no soccer accuracy, human labels or semantics.
Output directory must not exist; reruns require a distinct output directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from hosted_video_benchmark import (
    FixtureVideoProvider, run_benchmark, require_private_output,
    resolve_ffmpeg_executable, sha256_file, write_json_atomic,
)
from hosted_video_scoring import LABEL_SCHEMA, score_run


def fixture_report(clip_id: str) -> dict:
    actor = {"reference": "invented fixture actor", "team_side": "left_attacking",
             "role": "ball carrier", "visible_jersey_number": None,
             "identity_basis": "appearance_only", "action": "invented fixture action", "confidence": .7}
    event = {
        "event_id": "e01", "event_type": "progressive_pass", "event_subtype": "ground_pass",
        "start_s": 1.0, "peak_s": 2.0, "end_s": 3.0, "phase_of_play": "progression",
        "restart_context": None, "team_side": "left_attacking", "primary_actor": actor,
        "secondary_participants": [], "ball_action": "invented pass",
        "possession": {"team_side": "left_attacking", "state": "controlled", "confidence": .7,
                       "visibility_limit": "synthetic fixture with no soccer content"},
        "origin_pitch_region": "invented origin", "destination_pitch_region": "invented destination",
        "movement_direction": "invented direction", "action_sequence": ["invented pass"],
        "tactical_intent": "synthetic fixture", "outcome": "synthetic fixture",
        "coach_relevance": "software testing only",
        "evidence": [{"timestamp_s": 2.0, "visible_support": "invented software fixture, not a visual claim"}],
        "replay_status": "uncertain", "alternatives": ["no soccer exists in this color screen"],
        "uncertainties": ["all content is synthetic"], "confidence": .7,
        "abstain": False, "abstention_reason": None,
    }
    return {"schema_version": "playground-coach-event-report-v1", "clip_id": clip_id,
            "video_condition": "physically_silent_video_only",
            "window_summary": "Invented software fixture; color screens contain no soccer.",
            "dominant_phase": "progression", "events": [event], "report_abstained": False,
            "abstention_reason": None, "overall_uncertainty": "synthetic fixture",
            "coverage_limit": "software test only; no model, human annotation, or soccer performance"}


def reproduce(output: Path) -> dict:
    output = require_private_output(output)
    if output.exists():
        raise ValueError("output directory already exists; use a fresh private directory")
    output.mkdir(parents=True)
    ffmpeg = resolve_ffmpeg_executable()
    clips, responses = [], {}
    for index, color in enumerate(["black", "blue", "red", "green", "yellow", "white"], 1):
        clip_id = f"clip-{index:02d}"
        video = output / f"{clip_id}-synthetic-color.mp4"
        cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               f"color=c={color}:s=64x64:r=5:d=5", "-an", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", str(video)]
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if process.returncode:
            raise RuntimeError("synthetic video generation failed: " + process.stderr)
        labels = {
            "schema_version": LABEL_SCHEMA, "clip_id": clip_id, "source_sha256": sha256_file(video),
            "duration_s": 5.0, "time_unit": "seconds", "annotation_origin": "synthetic_fixture",
            "events": [{"label_id": "g01", "event_type": "shot" if index == 6 else "progressive_pass",
                        "start_s": 1.0, "peak_s": 2.0, "end_s": 3.0}],
        }
        label_path = output / f"{clip_id}-synthetic-labels.json"
        write_json_atomic(label_path, labels)
        clips.append({"clip_id": clip_id, "video_path": video.name, "sha256": sha256_file(video),
                      "mime_type": "video/mp4",
                      "rights": {"third_party_processing_permitted": False, "approved_processors": [],
                                 "rights_record_id": "local-generated-color-software-fixture",
                                 "decision_date": "2026-09-13"},
                      "held_out": {"labels_path": label_path.name, "labels_sha256": sha256_file(label_path),
                                   "commentary_path": None}})
        responses[clip_id] = fixture_report(clip_id)
    responses["clip-01"] = {"response_text": "intentionally malformed synthetic response",
                            "raw_response": {"synthetic": True}}
    responses["clip-02"].update(events=[], report_abstained=True,
                                abstention_reason="synthetic abstention fixture")
    manifest = output / "input-manifest.json"
    write_json_atomic(manifest, {
        "schema_version": "playground-hosted-video-benchmark-input-v1",
        "study_id": "six-color-screen-software-fixture", "protocol_phase": "benchmark",
        "video_condition": "physically_silent_video_only", "cost_policy": "zero_spend_only", "clips": clips,
    })
    response_path = output / "synthetic-responses.json"
    write_json_atomic(response_path, responses)
    out = output / "run"
    run_benchmark(manifest_path=manifest, private_out=out,
                  provider=FixtureVideoProvider(responses), model="offline-synthetic-event-fixture",
                  environment={}, open_held_out=True)
    hashes = {name: sha256_file(out / name) for name in ["primary-seal.json", "posthoc-audit.json"]}
    class ResumeMustNotInfer:
        provider_id = "local_fixture"
        remote = False
        def infer(self, **kwargs):
            raise AssertionError("pure resume unexpectedly called provider")
    run_benchmark(manifest_path=manifest, private_out=out, provider=ResumeMustNotInfer(),
                  model="offline-synthetic-event-fixture", environment={}, open_held_out=True)
    assert hashes == {name: sha256_file(out / name) for name in hashes}
    scored = score_run(out)
    assert scored["counts"]["requested"] == 6
    assert scored["counts"]["failed"] == 1
    assert scored["counts"]["abstained"] == 1
    assert scored["counts"]["true_positive"] == 3
    assert scored["counts"]["false_positive"] == 1
    assert scored["counts"]["false_negative"] == 3
    scoring_path = output / "scoring.json"
    write_json_atomic(scoring_path, scored)
    receipt = {
        "schema_version": "playground-hosted-video-synthetic-reproduction-v1", "synthetic": True,
        "real_model_calls": 0, "real_soccer_clips": 0, "external_requests": 0,
        "truth_boundary": "SYSTEMS GO / SEMANTIC NO-GO", "scientific_validation": False,
        "scope": "six generated silent color screens, invented labels/reports, parser/failure/scoring/resume checks",
        "script_sha256": sha256_file(Path(__file__)),
        "runner_sha256": sha256_file(ROOT / "prototype" / "hosted_video_benchmark.py"),
        "scorer_sha256": sha256_file(ROOT / "prototype" / "hosted_video_scoring.py"),
        "input_manifest_sha256": sha256_file(manifest), "scoring_sha256": sha256_file(scoring_path),
        "primary_seal_sha256": hashes["primary-seal.json"], "posthoc_audit_sha256": hashes["posthoc-audit.json"],
        "pure_resume_preserved_seals": True, "counts": scored["counts"],
        "output": str(output), "protected_gates_changed": False,
    }
    write_json_atomic(output / "reproduction-receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.private_out), indent=2, sort_keys=True))
