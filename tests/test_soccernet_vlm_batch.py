import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import run_soccernet_vlm_batch as batch_module
from freeze_visual_config import create_frozen_config
from real_clip_vlm import prompt, sha256_file
from run_soccernet_vlm_batch import macro_f1, require_private_output, run_batch, safe_rate, summarize
from runtime_receipt_fixtures import write_isolated_runtime_receipt


def test_rates_are_explicit_for_empty_denominator() -> None:
    assert safe_rate(1, 2) == 0.5
    assert safe_rate(0, 0) is None


def test_macro_f1_recomputes_from_clip_pairs() -> None:
    records = [
        {"truth": "goal", "prediction": "goal"},
        {"truth": "foul", "prediction": "goal"},
    ]
    assert macro_f1(records) == pytest.approx(1 / 3)


def test_raw_outputs_must_remain_private(tmp_path: Path) -> None:
    private = tmp_path / "data" / "private" / "runs"
    assert require_private_output(private) == private.resolve()
    with pytest.raises(ValueError, match="data/private"):
        require_private_output(tmp_path / "artifacts" / "runs")


def test_requested_set_metrics_count_failed_clips_as_failures(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    manifest = {
        "split": "train",
        "clips": [
            {"clip_id": "clip-1", "ground_truth": {"single_label_eligible": True}},
            {"clip_id": "clip-2", "ground_truth": {"single_label_eligible": True}},
        ],
    }
    completed = [{
        "clip_id": "clip-1",
        "truth": "goal",
        "prediction": "goal",
        "allowed_play_types": ["goal"],
        "single_label_eligible": True,
        "elapsed_ms": 10,
    }]
    summary = summarize(
        manifest=manifest,
        completed=completed,
        failures=[{"clip_id": "clip-2", "error_code": "TimeoutError"}],
        model="test-model",
        manifest_path=manifest_path,
        sample_count=4,
        sheets=1,
        max_tokens=100,
        frozen_config_receipt={
            "schema_version": "playground-frozen-visual-config-v1",
            "sha256": "a" * 64,
        },
    )
    assert summary["counts"]["single_label_eligible_requested"] == 2
    assert summary["counts"]["single_label_eligible_completed"] == 1
    assert summary["metrics"]["primary_requested_set"] == {
        "single_label_exact_accuracy": 0.5,
        "allowed_label_accuracy_all_clips": 0.5,
        "schema_valid_first_pass_rate": 0.5,
    }
    assert summary["metrics"]["secondary_completed_only"]["single_label_exact_accuracy"] == 1.0
    assert summary["metrics"]["secondary_completed_only"]["allowed_label_accuracy_all_clips"] == 1.0
    assert summary["frozen_config"] == {
        "enforced": True,
        "schema_version": "playground-frozen-visual-config-v1",
        "sha256": "a" * 64,
    }


def test_summary_rejects_missing_requested_set_accounting(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    manifest = {
        "split": "train",
        "clips": [{"clip_id": "clip-1", "ground_truth": {"single_label_eligible": True}}],
    }
    with pytest.raises(ValueError, match="account for the requested set exactly"):
        summarize(
            manifest=manifest,
            completed=[],
            failures=[],
            model="test-model",
            manifest_path=manifest_path,
            sample_count=4,
            sheets=1,
            max_tokens=100,
        )


def test_batch_rejects_frozen_config_drift_before_inference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    train = tmp_path / "train.json"
    valid = tmp_path / "valid.json"
    train.write_text(json.dumps({
        "split": "train", "clips": [{"clip_id": "train-one", "split": "train"}],
    }), encoding="utf-8")
    valid.write_text(json.dumps({
        "split": "valid",
        "clips": [{"clip_id": "valid-one", "split": "valid", "ground_truth": {"single_label_eligible": True}}],
    }), encoding="utf-8")
    development_summary = tmp_path / "development-summary.json"
    development_summary.write_text(json.dumps({
        "schema_version": "playground-soccernet-vlm-pilot-summary-v1",
        "split": "train",
        "model": "frozen/model",
        "sampling": {"sample_count": 12, "contact_sheets": 12, "max_tokens": 1600},
        "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
        "private_manifest_sha256": sha256_file(train),
        "counts": {"requested": 1, "completed": 1, "failed": 0},
        "clips": [{"clip_id": "train-one"}],
        "failures": [],
    }), encoding="utf-8")
    frozen = tmp_path / "frozen.json"
    create_frozen_config(
        train_manifest_path=train,
        validation_manifest_path=valid,
        development_summary_path=development_summary,
        out_path=frozen,
        endpoint="http://127.0.0.1:1234/v1",
        model="frozen/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
    )
    called = False

    def forbidden_run(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("inference must not run")

    monkeypatch.setattr(batch_module, "run", forbidden_run)
    with pytest.raises(ValueError, match="model"):
        run_batch(
            manifest_path=valid,
            private_out=tmp_path / "data" / "private" / "runs",
            public_summary=tmp_path / "summary.json",
            endpoint="http://127.0.0.1:1234/v1",
            model="drifted/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
            frozen_config_path=frozen,
        )
    assert called is False
    assert not (tmp_path / "summary.json").exists()


def test_summary_records_runtime_receipt_hash_for_v2_freeze(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    manifest = {
        "split": "valid",
        "clips": [{"clip_id": "clip-1", "ground_truth": {"single_label_eligible": True}}],
    }
    summary = summarize(
        manifest=manifest,
        completed=[{
            "clip_id": "clip-1",
            "truth": "goal",
            "prediction": "goal",
            "allowed_play_types": ["goal"],
            "single_label_eligible": True,
            "elapsed_ms": 10,
        }],
        failures=[],
        model="test/model",
        manifest_path=manifest_path,
        sample_count=12,
        sheets=12,
        max_tokens=1600,
        frozen_config_receipt={
            "schema_version": "playground-frozen-visual-config-v2",
            "sha256": "a" * 64,
            "runtime_receipt_sha256": "b" * 64,
        },
    )
    assert summary["frozen_config"] == {
        "enforced": True,
        "schema_version": "playground-frozen-visual-config-v2",
        "sha256": "a" * 64,
        "runtime_receipt_sha256": "b" * 64,
    }


def test_batch_requires_v2_runtime_receipt_before_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    train = tmp_path / "train.json"
    valid = tmp_path / "valid.json"
    train.write_text(json.dumps({
        "split": "train", "clips": [{"clip_id": "train-one", "split": "train"}],
    }), encoding="utf-8")
    valid.write_text(json.dumps({
        "split": "valid",
        "clips": [{"clip_id": "valid-one", "split": "valid", "ground_truth": {"single_label_eligible": True}}],
    }), encoding="utf-8")
    development_summary = tmp_path / "development-summary.json"
    development_summary.write_text(json.dumps({
        "schema_version": "playground-soccernet-vlm-pilot-summary-v1",
        "split": "train",
        "model": "test/model",
        "sampling": {"sample_count": 12, "contact_sheets": 12, "max_tokens": 1600},
        "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
        "private_manifest_sha256": sha256_file(train),
        "counts": {"requested": 1, "completed": 1, "failed": 0},
        "clips": [{"clip_id": "train-one"}],
        "failures": [],
    }), encoding="utf-8")
    runtime_receipt = tmp_path / "runtime-receipt.json"
    write_isolated_runtime_receipt(runtime_receipt, model="test/model")
    frozen = tmp_path / "frozen-v2.json"
    create_frozen_config(
        train_manifest_path=train,
        validation_manifest_path=valid,
        development_summary_path=development_summary,
        out_path=frozen,
        endpoint="http://127.0.0.1:1240/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
        runtime_receipt_path=runtime_receipt,
    )
    called = False

    def forbidden_run(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("inference must not run")

    monkeypatch.setattr(batch_module, "run", forbidden_run)
    with pytest.raises(ValueError, match="runtime_receipt_required"):
        run_batch(
            manifest_path=valid,
            private_out=tmp_path / "data" / "private" / "runs",
            public_summary=tmp_path / "summary.json",
            endpoint="http://127.0.0.1:1240/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
            frozen_config_path=frozen,
        )
    assert called is False
    assert not (tmp_path / "summary.json").exists()
