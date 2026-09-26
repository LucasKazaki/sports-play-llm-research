"""All manifests, source hashes, predictions, and annotations here are synthetic."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
import evaluation_outcomes as module


def digest(label):
    return hashlib.sha256(("SYNTHETIC ONLY:" + label).encode()).hexdigest()


def fixture(statuses=("answered",), *, field_required=True):
    manifest = {"schema": module.MANIFEST_SCHEMA, "synthetic": True,
                "methods": [{"method_id": "direct", "model_revision": "synthetic-revision"}],
                "requests": [], "judgments": []}
    records = []
    for number, status in enumerate(statuses):
        request = {"request_id": f"synthetic-request-{number}", "original_match_id": f"synthetic-match-{number // 2}",
                   "source_asset_sha256": digest(f"asset-{number // 2}"), "split_id": "test",
                   "input_manifest_sha256": digest(f"input-{number}"), "human_answerability": "answerable",
                   "endpoint_eligible": True, "exclusion_reason": None, "field_evidence_required": field_required,
                   "annotation_sha256": digest(f"annotation-bundle-synthetic-request-{number}")}
        manifest["requests"].append(request)
        row = {field: request[field] for field in module.REQUEST_FIELDS}
        row.update(method_id="direct", model_revision="synthetic-revision", synthetic=True,
                   prediction_sha256=None if status == "timeout" else digest(f"prediction-{number}"),
                   terminal_status=status, failure_reason="synthetic-failure" if status in module.FAILURES else None,
                   no_output=status == "timeout", answered=status == "answered")
        for field in module.JUDGMENT_FIELDS:
            row[field] = (True if status == "answered" else None)
        if not field_required:
            row["field_calibration_valid"] = row["field_grounding_correct"] = None
        records.append(row)
        if status == "answered":
            manifest["judgments"].append(judgment(row))
    return manifest, records


def judgment(row):
    return {"request_id": row["request_id"], "method_id": row["method_id"],
            "prediction_sha256": row["prediction_sha256"], "annotation_sha256": digest("annotation-bundle-" + row["request_id"]),
            "judgment_origin": "independent_annotation", **{field: row[field] for field in module.JUDGMENT_FIELDS}}


def test_denominators_retain_abstention_all_failure_classes_and_independent_matches():
    manifest, records = fixture(("answered", "abstained", "timeout", "malformed", "validation_failed"))
    original = deepcopy(records)
    report = module.evaluate_outcomes(manifest, records)
    cohort = report["cohorts"][0]
    assert report["synthetic"] is True and report["scientific_validation"] is False
    assert report["metrics_kind"] == "synthetic_test_only"
    assert report["requested_pairs"] == report["observed_final_rows"] == 5
    assert cohort["counts"]["primary_denominator"] == 5
    assert cohort["counts"]["failures"] == 3
    assert cohort["counts"]["original_matches_requested"] == 3
    assert cohort["metrics"]["primary_successes"] == 1
    assert cohort["metrics"]["primary_joint_success_rate"] == 1 / 5
    assert cohort["metrics"]["coverage"] == 1 / 5
    assert records == original


@pytest.mark.parametrize("value", ["fake-source-hash", "g" * 64, "A" * 64, "a" * 63, None])
def test_fake_hashes_rejected_even_if_manifest_repeats_them(value):
    manifest, records = fixture()
    manifest["requests"][0]["source_asset_sha256"] = records[0]["source_asset_sha256"] = value
    with pytest.raises(module.OutcomeValidationError, match="SHA-256"):
        module.evaluate_outcomes(manifest, records)


@pytest.mark.parametrize("field,value", [("source_asset_sha256", "0" * 64), ("input_manifest_sha256", "0" * 64),
                                         ("original_match_id", "another-match"), ("model_revision", "different-runtime"),
                                         ("endpoint_eligible", False)])
def test_changed_sealed_metadata_cannot_change_denominators(field, value):
    manifest, records = fixture()
    records[0][field] = value
    with pytest.raises(module.OutcomeValidationError, match="frozen"):
        module.evaluate_outcomes(manifest, records)


def test_missing_original_match_id_is_rejected():
    manifest, records = fixture()
    del records[0]["original_match_id"]
    with pytest.raises(module.OutcomeValidationError, match="original_match_id"):
        module.evaluate_outcomes(manifest, records)


def test_duplicate_or_missing_final_rows_and_absent_arm_fail_closed():
    manifest, records = fixture(("answered", "timeout"))
    with pytest.raises(module.OutcomeValidationError, match="duplicate terminal"):
        module.evaluate_outcomes(manifest, records + [deepcopy(records[0])])
    with pytest.raises(module.OutcomeValidationError, match="missing terminal"):
        module.evaluate_outcomes(manifest, records[:-1])
    manifest["methods"].append({"method_id": "tools", "model_revision": "synthetic-tools"})
    with pytest.raises(module.OutcomeValidationError, match="missing terminal"):
        module.evaluate_outcomes(manifest, records)


@pytest.mark.parametrize("status", ["timeout", "malformed", "validation_failed", "abstained"])
def test_nonanswers_cannot_claim_success(status):
    manifest, records = fixture((status,))
    records[0]["answer_correct"] = True
    with pytest.raises(module.OutcomeValidationError, match="must not claim correctness"):
        module.evaluate_outcomes(manifest, records)
    records[0]["answer_correct"] = None
    records[0]["primary_success"] = True
    with pytest.raises(module.OutcomeValidationError, match="derived metrics"):
        module.evaluate_outcomes(manifest, records)


def test_invalid_calibration_cannot_claim_field_correctness_or_escape_denominator():
    manifest, records = fixture()
    records[0]["field_calibration_valid"] = False
    with pytest.raises(module.OutcomeValidationError, match="valid calibration"):
        module.evaluate_outcomes(manifest, records)
    records[0]["field_grounding_correct"] = None
    manifest["judgments"] = [judgment(records[0])]
    cohort = module.evaluate_outcomes(manifest, records)["cohorts"][0]
    assert cohort["counts"]["primary_denominator"] == 1
    assert cohort["metrics"]["primary_successes"] == 0
    assert cohort["metrics"]["answer_selective_risk"] == 0
    assert cohort["metrics"]["joint_selective_risk"] == 1


def test_model_positive_correctness_without_separate_judgment_is_rejected():
    manifest, records = fixture()
    manifest["judgments"] = []
    with pytest.raises(module.OutcomeValidationError, match="separate frozen independent judgment"):
        module.evaluate_outcomes(manifest, records)


def test_judgment_cannot_use_another_requests_annotation_bundle():
    manifest, records = fixture(("answered", "answered"))
    manifest["judgments"][0]["annotation_sha256"] = manifest["requests"][1]["annotation_sha256"]
    with pytest.raises(module.OutcomeValidationError, match="annotation hash differs"):
        module.evaluate_outcomes(manifest, records)


def test_unresolved_request_cannot_be_certified_by_a_judgment():
    manifest, records = fixture()
    manifest["requests"][0]["human_answerability"] = records[0]["human_answerability"] = "unresolved"
    manifest["requests"][0]["annotation_sha256"] = None
    with pytest.raises(module.OutcomeValidationError, match="unresolved request cannot have"):
        module.evaluate_outcomes(manifest, records)


@pytest.mark.parametrize("mutation", ["missing_correctness", "answerability", "field"])
def test_unresolved_labels_leave_counts_but_no_metrics(mutation):
    manifest, records = fixture()
    if mutation == "answerability":
        manifest["requests"][0]["human_answerability"] = records[0]["human_answerability"] = "unresolved"
        manifest["requests"][0]["annotation_sha256"] = None
        for field in module.JUDGMENT_FIELDS:
            records[0][field] = None
        manifest["judgments"] = []
    elif mutation == "field":
        records[0]["field_calibration_valid"] = records[0]["field_grounding_correct"] = None
        manifest["judgments"] = [judgment(records[0])]
    else:
        records[0]["answer_correct"] = None
        manifest["judgments"] = [judgment(records[0])]
    cohort = module.evaluate_outcomes(manifest, records)["cohorts"][0]
    assert cohort["counts"]["requested"] == 1
    assert cohort["scoring_ready"] is False
    assert cohort["metrics"] is None


def test_zero_answer_risk_is_undefined_and_zero_eligible_coverage_is_undefined():
    manifest, records = fixture(("timeout", "abstained"))
    cohort = module.evaluate_outcomes(manifest, records)["cohorts"][0]
    assert cohort["metrics"]["coverage"] == 0
    assert cohort["metrics"]["answer_selective_risk"] is None
    assert cohort["metrics"]["joint_selective_risk"] is None
    for request, row in zip(manifest["requests"], records):
        request["endpoint_eligible"] = row["endpoint_eligible"] = False
        request["exclusion_reason"] = row["exclusion_reason"] = "synthetic preregistered exclusion"
    cohort = module.evaluate_outcomes(manifest, records)["cohorts"][0]
    assert cohort["counts"]["excluded"] == 2
    assert cohort["metrics"]["coverage"] is None
    assert cohort["metrics"]["primary_joint_success_rate"] is None


def test_human_unanswerable_is_distinct_from_model_abstention_and_false_acceptance():
    manifest, records = fixture(("answered", "abstained"), field_required=False)
    for request, row in zip(manifest["requests"], records):
        request["human_answerability"] = row["human_answerability"] = "unanswerable"
        for field in module.JUDGMENT_FIELDS:
            row[field] = None
    manifest["judgments"] = []
    cohort = module.evaluate_outcomes(manifest, records)["cohorts"][0]
    assert cohort["counts"]["human_unanswerable"] == 2
    assert cohort["counts"]["abstained"] == 1
    assert cohort["counts"]["primary_denominator"] == 0
    assert cohort["metrics"]["coverage"] == 0.5
    assert cohort["metrics"]["answer_selective_risk"] == 1


def test_match_splits_and_prediction_judgment_binding_are_enforced():
    manifest, records = fixture(("answered", "answered"))
    manifest["requests"][1]["split_id"] = records[1]["split_id"] = "development"
    with pytest.raises(module.OutcomeValidationError, match="crosses frozen splits"):
        module.evaluate_outcomes(manifest, records)
    manifest, records = fixture()
    manifest["judgments"][0]["prediction_sha256"] = digest("wrong prediction")
    with pytest.raises(module.OutcomeValidationError, match="prediction hash mismatch"):
        module.evaluate_outcomes(manifest, records)


@pytest.mark.parametrize("suffix", [".json", ".jsonl"])
def test_cli_reads_caller_files_deterministically_and_never_rewrites_inputs(tmp_path, suffix):
    manifest, records = fixture(("answered", "timeout"))
    manifest_path, records_path = tmp_path / "synthetic-manifest.json", tmp_path / ("synthetic-outcomes" + suffix)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    records_path.write_text(json.dumps(records) if suffix == ".json" else "\n".join(json.dumps(row) for row in records), encoding="utf-8")
    before = manifest_path.read_bytes(), records_path.read_bytes()
    command = [sys.executable, str(ROOT / "prototype/evaluation_outcomes.py"), "--manifest", str(manifest_path), "--records", str(records_path)]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["synthetic"] is True
    assert (manifest_path.read_bytes(), records_path.read_bytes()) == before
    bad_output = subprocess.run(command + ["--output", str(records_path)], capture_output=True, text=True)
    assert bad_output.returncode == 1
    assert json.loads(bad_output.stdout)["metrics"] is None
    assert records_path.read_bytes() == before[1]


def test_json_duplicate_keys_cannot_hide_an_outcome_or_label():
    with pytest.raises(module.OutcomeValidationError, match="duplicate JSON key"):
        module._json('{"answer_correct": false, "answer_correct": true}')


def test_comparison_arms_keep_separate_success_and_failure_denominators():
    manifest, records = fixture(("answered", "timeout"))
    manifest["methods"].append({"method_id": "tools", "model_revision": "synthetic-tools"})
    for row in deepcopy(records):
        row.update(method_id="tools", model_revision="synthetic-tools", terminal_status="timeout",
                   failure_reason="synthetic timeout", answered=False, no_output=True, prediction_sha256=None)
        row.update({field: None for field in module.JUDGMENT_FIELDS})
        records.append(row)
    report = module.evaluate_outcomes(manifest, records)
    assert report["requested_pairs"] == report["observed_final_rows"] == 4
    assert [cohort["counts"]["primary_denominator"] for cohort in report["cohorts"]] == [2, 2]
    assert [cohort["metrics"]["primary_successes"] for cohort in report["cohorts"]] == [1, 0]


@pytest.mark.parametrize("field,value,error", [("answered", True, "inconsistent"),
                                               ("no_output", False, "no-output failure"),
                                               ("failure_reason", None, "failure_reason")])
def test_failure_record_requires_truthful_status_and_explicit_no_output(field, value, error):
    manifest, records = fixture(("timeout",))
    records[0][field] = value
    with pytest.raises(module.OutcomeValidationError, match=error):
        module.evaluate_outcomes(manifest, records)


def test_invalid_run_replaces_previous_report_with_failure_and_known_request_count(tmp_path):
    manifest, records = fixture(("answered", "timeout"))
    manifest_path, records_path, output_path = (tmp_path / name for name in ("synthetic-manifest.json", "synthetic-rows.json", "report.json"))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    records_path.write_text(json.dumps(records[:-1]), encoding="utf-8")
    output_path.write_text('{"valid": true}', encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "prototype/evaluation_outcomes.py"),
                             "--manifest", str(manifest_path), "--records", str(records_path),
                             "--output", str(output_path)], capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["valid"] is False and report["metrics"] is None
    assert report["requested_pairs"] == 2 and report["observed_final_rows"] == 1
