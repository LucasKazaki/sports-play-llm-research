import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
if str(PROTOTYPE) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from freeze_visual_config import (
    FROZEN_CONFIG_SCHEMA_VERSION_V2,
    create_frozen_config,
    verify_frozen_config,
)
from real_clip_vlm import prompt, sha256_file
from runtime_receipt_fixtures import write_isolated_runtime_receipt


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    train = tmp_path / "train.json"
    valid = tmp_path / "valid.json"
    _write_json(train, {"split": "train", "clips": [{"clip_id": "train-opaque", "split": "train"}]})
    _write_json(valid, {"split": "valid", "clips": [{"clip_id": "valid-opaque", "split": "valid"}]})
    import hashlib
    summary = tmp_path / "development-summary.json"
    _write_json(summary, {
        "schema_version": "playground-soccernet-vlm-pilot-summary-v1",
        "split": "train",
        "model": "test/model",
        "sampling": {"sample_count": 12, "contact_sheets": 12, "max_tokens": 1600},
        "prompt_sha256": hashlib.sha256(prompt().encode("utf-8")).hexdigest(),
        "private_manifest_sha256": sha256_file(train),
        "counts": {"requested": 1, "completed": 1, "failed": 0},
        "clips": [{"clip_id": "train-opaque"}],
        "failures": [],
    })
    return train, valid, summary


def _freeze(tmp_path: Path) -> tuple[Path, Path]:
    train, valid, summary = _fixtures(tmp_path)
    frozen = tmp_path / "frozen.json"
    create_frozen_config(
        train_manifest_path=train,
        validation_manifest_path=valid,
        development_summary_path=summary,
        out_path=frozen,
        endpoint="http://127.0.0.1:1234/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
    )
    return frozen, valid


def test_freeze_artifact_is_path_free_and_gates_validation(tmp_path: Path) -> None:
    frozen, valid = _freeze(tmp_path)
    config_text = frozen.read_text(encoding="utf-8")
    assert str(tmp_path) not in config_text
    manifest = json.loads(valid.read_text(encoding="utf-8"))
    receipt = verify_frozen_config(
        frozen_config_path=frozen,
        manifest_path=valid,
        manifest=manifest,
        endpoint="http://127.0.0.1:1234/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
    )
    assert receipt["sha256"] == sha256_file(frozen)


@pytest.mark.parametrize(
    ("field", "value"),
    [("model", "changed/model"), ("sample_count", 8), ("sheets", 3), ("max_tokens", 999)],
)
def test_gate_rejects_runtime_drift(tmp_path: Path, field: str, value: object) -> None:
    frozen, valid = _freeze(tmp_path)
    kwargs = {
        "frozen_config_path": frozen,
        "manifest_path": valid,
        "manifest": json.loads(valid.read_text(encoding="utf-8")),
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "test/model",
        "sample_count": 12,
        "sheets": 12,
        "max_tokens": 1600,
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match="runtime does not match frozen visual configuration"):
        verify_frozen_config(**kwargs)


def test_gate_rejects_manifest_tampering(tmp_path: Path) -> None:
    frozen, valid = _freeze(tmp_path)
    manifest = json.loads(valid.read_text(encoding="utf-8"))
    manifest["clips"].append({"clip_id": "valid-second", "split": "valid"})
    _write_json(valid, manifest)
    with pytest.raises(ValueError, match="manifest_sha256"):
        verify_frozen_config(
            frozen_config_path=frozen,
            manifest_path=valid,
            manifest=manifest,
            endpoint="http://127.0.0.1:1234/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
        )


def test_freeze_requires_a_complete_development_run(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["counts"] = {"requested": 1, "completed": 0, "failed": 1}
    _write_json(summary, payload)
    with pytest.raises(ValueError, match="complete_training_run"):
        create_frozen_config(
            train_manifest_path=train,
            validation_manifest_path=valid,
            development_summary_path=summary,
            out_path=tmp_path / "frozen.json",
            endpoint="http://127.0.0.1:1234/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
        )


def test_freeze_rejects_zero_of_zero_summary_for_nonempty_train_manifest(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["counts"] = {"requested": 0, "completed": 0, "failed": 0}
    _write_json(summary, payload)
    with pytest.raises(ValueError, match="complete_training_run"):
        create_frozen_config(
            train_manifest_path=train,
            validation_manifest_path=valid,
            development_summary_path=summary,
            out_path=tmp_path / "frozen.json",
            endpoint="http://127.0.0.1:1234/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
        )


def test_freeze_rejects_wrong_development_summary_schema(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["schema_version"] = "unrelated-summary-v1"
    _write_json(summary, payload)
    with pytest.raises(ValueError, match="schema_version"):
        create_frozen_config(
            train_manifest_path=train,
            validation_manifest_path=valid,
            development_summary_path=summary,
            out_path=tmp_path / "frozen.json",
            endpoint="http://127.0.0.1:1234/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
        )


def test_freeze_requires_exact_completed_clip_ids_and_empty_failures(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["clips"] = [{"clip_id": "different-train-clip"}]
    payload["failures"] = [{"clip_id": "train-opaque", "error_code": "TimeoutError"}]
    _write_json(summary, payload)
    with pytest.raises(ValueError, match="completed_clip_ids|empty_failure_records"):
        create_frozen_config(
            train_manifest_path=train,
            validation_manifest_path=valid,
            development_summary_path=summary,
            out_path=tmp_path / "frozen.json",
            endpoint="http://127.0.0.1:1234/v1",
            model="test/model",
            sample_count=12,
            sheets=12,
            max_tokens=1600,
        )


def test_freeze_artifact_is_write_once(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    frozen = tmp_path / "frozen.json"
    kwargs = {
        "train_manifest_path": train,
        "validation_manifest_path": valid,
        "development_summary_path": summary,
        "out_path": frozen,
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "test/model",
        "sample_count": 12,
        "sheets": 12,
        "max_tokens": 1600,
    }
    create_frozen_config(**kwargs)
    original = frozen.read_bytes()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        create_frozen_config(**kwargs)
    assert frozen.read_bytes() == original


def test_concurrent_freeze_creators_have_exactly_one_winner(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    frozen = tmp_path / "frozen.json"
    kwargs = {
        "train_manifest_path": train,
        "validation_manifest_path": valid,
        "development_summary_path": summary,
        "out_path": frozen,
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "test/model",
        "sample_count": 12,
        "sheets": 12,
        "max_tokens": 1600,
    }

    def attempt() -> str:
        try:
            create_frozen_config(**kwargs)
            return "created"
        except FileExistsError:
            return "already-exists"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: attempt(), range(2)))
    assert sorted(outcomes) == ["already-exists", "created"]
    assert json.loads(frozen.read_text(encoding="utf-8"))["schema_version"] == (
        "playground-frozen-visual-config-v1"
    )


def test_v2_freeze_hash_binds_exact_isolated_runtime_receipt(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    runtime_receipt = tmp_path / "runtime-receipt.json"
    write_isolated_runtime_receipt(runtime_receipt, model="test/model")
    frozen = tmp_path / "frozen-v2.json"
    config = create_frozen_config(
        train_manifest_path=train,
        validation_manifest_path=valid,
        development_summary_path=summary,
        out_path=frozen,
        endpoint="http://127.0.0.1:1240/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
        runtime_receipt_path=runtime_receipt,
    )
    assert config["schema_version"] == FROZEN_CONFIG_SCHEMA_VERSION_V2
    assert config["runtime_receipt"]["sha256"] == sha256_file(runtime_receipt)
    assert config["runtime_receipt"]["expected_settings"] == {
        "endpoint": "http://127.0.0.1:1240/v1",
        "context_length": 8192,
        "parallel": 1,
        "gpu_offload": "max",
        "gpu_layers": "all",
        "api_key_configured": False,
    }
    assert str(tmp_path) not in frozen.read_text(encoding="utf-8")
    gate = verify_frozen_config(
        frozen_config_path=frozen,
        manifest_path=valid,
        manifest=json.loads(valid.read_text(encoding="utf-8")),
        endpoint="http://127.0.0.1:1240/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
        runtime_receipt_path=runtime_receipt,
    )
    assert gate == {
        "schema_version": FROZEN_CONFIG_SCHEMA_VERSION_V2,
        "sha256": sha256_file(frozen),
        "runtime_receipt_sha256": sha256_file(runtime_receipt),
    }


def test_v2_gate_requires_bound_receipt_and_rejects_receipt_tampering(tmp_path: Path) -> None:
    train, valid, summary = _fixtures(tmp_path)
    runtime_receipt = tmp_path / "runtime-receipt.json"
    receipt = write_isolated_runtime_receipt(runtime_receipt, model="test/model")
    frozen = tmp_path / "frozen-v2.json"
    create_frozen_config(
        train_manifest_path=train,
        validation_manifest_path=valid,
        development_summary_path=summary,
        out_path=frozen,
        endpoint="http://127.0.0.1:1240/v1",
        model="test/model",
        sample_count=12,
        sheets=12,
        max_tokens=1600,
        runtime_receipt_path=runtime_receipt,
    )
    kwargs = {
        "frozen_config_path": frozen,
        "manifest_path": valid,
        "manifest": json.loads(valid.read_text(encoding="utf-8")),
        "endpoint": "http://127.0.0.1:1240/v1",
        "model": "test/model",
        "sample_count": 12,
        "sheets": 12,
        "max_tokens": 1600,
    }
    with pytest.raises(ValueError, match="runtime_receipt_required"):
        verify_frozen_config(**kwargs)
    receipt["requested_settings"]["context_length"] = 4096
    _write_json(runtime_receipt, receipt)
    with pytest.raises(ValueError, match="runtime_receipt_invalid"):
        verify_frozen_config(**kwargs, runtime_receipt_path=runtime_receipt)


def test_v1_gate_rejects_unbound_runtime_receipt_but_remains_compatible_without_one(tmp_path: Path) -> None:
    frozen, valid = _freeze(tmp_path)
    runtime_receipt = tmp_path / "runtime-receipt.json"
    write_isolated_runtime_receipt(runtime_receipt, model="test/model")
    kwargs = {
        "frozen_config_path": frozen,
        "manifest_path": valid,
        "manifest": json.loads(valid.read_text(encoding="utf-8")),
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "test/model",
        "sample_count": 12,
        "sheets": 12,
        "max_tokens": 1600,
    }
    assert verify_frozen_config(**kwargs)["schema_version"] == "playground-frozen-visual-config-v1"
    with pytest.raises(ValueError, match="runtime_receipt_unbound_by_v1"):
        verify_frozen_config(**kwargs, runtime_receipt_path=runtime_receipt)
