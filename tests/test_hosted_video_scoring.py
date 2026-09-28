import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from hosted_video_benchmark import BenchmarkGateError, FixtureVideoProvider, run_benchmark, sha256_file
from hosted_video_scoring import LABEL_SCHEMA, match_events, score_run
from test_hosted_video_benchmark import write_manifest, valid_report, silent_probe, private_out


def label_document(clip_id, source_sha):
    return {"schema_version": LABEL_SCHEMA, "clip_id": clip_id, "source_sha256": source_sha,
            "duration_s": 5.0, "time_unit": "seconds", "annotation_origin": "synthetic_fixture",
            "events": [{"label_id": "g01", "event_type": "progressive_pass",
                        "start_s": 1.0, "peak_s": 2.0, "end_s": 3.0}]}


def make_run(tmp_path, *, count=6, mutation=None, frozen=True, responses=None):
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[],
                                   phase="benchmark" if count >= 6 else "development", clip_count=count)
    data = json.loads(manifest.read_text())
    for clip in data["clips"]:
        labels_path = tmp_path / clip["held_out"]["labels_path"]
        labels = label_document(clip["clip_id"], clip["sha256"])
        if mutation:
            mutation(labels)
        labels_path.write_text(json.dumps(labels), encoding="utf-8")
        if frozen:
            clip["held_out"]["labels_sha256"] = sha256_file(labels_path)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    provider = FixtureVideoProvider(responses or {key: valid_report(key) for key in ids})
    out = private_out(tmp_path)
    run_benchmark(manifest_path=manifest, private_out=out, provider=provider,
                  model="offline-fixture", environment={}, media_probe=silent_probe, open_held_out=True)
    return out, manifest, ids


def test_six_clip_scoring_is_hash_bound_and_preserves_primary_and_labels(tmp_path):
    out, manifest, _ = make_run(tmp_path)
    paths = [manifest, out / "primary-seal.json", out / "posthoc-audit.json",
             *tmp_path.glob("*-labels.json")]
    before = {path: sha256_file(path) for path in paths}
    result = score_run(out)
    assert result["counts"]["requested"] == 6
    assert result["counts"]["true_positive"] == 6
    assert result["metrics"]["event_f1_labeled_cohort"] == 1
    assert result["study_size"] == {"minimum": 6, "target": [10, 15], "observed": 6,
                                     "meets_minimum": True, "meets_target": False}
    assert result["annotation_origin"] == "synthetic_fixture"
    assert result["scientific_validation"] is False
    assert result["annotation_independence_verified"] is False
    assert before == {path: sha256_file(path) for path in paths}


def test_duplicate_predictions_do_not_inflate_recall(tmp_path):
    reports = {f"clip-{i:02d}": valid_report(f"clip-{i:02d}") for i in range(1, 7)}
    duplicate = copy.deepcopy(reports["clip-01"]["events"][0])
    duplicate["event_id"] = "e02"
    reports["clip-01"]["events"].append(duplicate)
    out, _, _ = make_run(tmp_path, responses=reports)
    result = score_run(out)
    assert result["counts"]["true_positive"] == 6
    assert result["counts"]["false_positive"] == 1
    assert result["metrics"]["event_recall_labeled_cohort"] == 1


def test_matching_uses_maximum_cardinality_and_is_order_invariant():
    pred = [{"event_id": "e01", "event_type": "pass", "start_s": .5, "peak_s": 1.5, "end_s": 2.5},
            {"event_id": "e02", "event_type": "pass", "start_s": 0., "peak_s": 1., "end_s": 2.}]
    gold = [{"label_id": "g01", "event_type": "pass", "start_s": 0., "peak_s": 1., "end_s": 2.},
            {"label_id": "g02", "event_type": "pass", "start_s": 1., "peak_s": 2., "end_s": 3.}]
    result = match_events(pred, gold)
    assert len(result) == 2
    assert result == match_events(list(reversed(pred)), list(reversed(gold)))


@pytest.mark.parametrize("mutation,message", [
    (lambda d: d.update(source_sha256="0"*64), "source hash"),
    (lambda d: d.update(clip_id="wrong"), "clip mismatch"),
    (lambda d: d.update(time_unit="frames"), "time_unit"),
    (lambda d: d.update(duration_s=7), "duration mismatch"),
    (lambda d: d["events"][0].update(end_s=6), "within source"),
    (lambda d: d["events"].append(copy.deepcopy(d["events"][0])), "unique"),
    (lambda d: d.update(annotation_origin="model_guess"), "annotation origin"),
])
def test_scoring_refuses_invalid_labels(tmp_path, mutation, message):
    out, _, _ = make_run(tmp_path, mutation=mutation)
    with pytest.raises(BenchmarkGateError, match=message):
        score_run(out)


def test_missing_freeze_is_explicitly_unscorable(tmp_path):
    out, _, _ = make_run(tmp_path, frozen=False)
    result = score_run(out)
    assert result["counts"]["labels_ineligible"] == 6
    assert result["metrics"]["event_precision_labeled_cohort"] is None
    assert all("labels_not_frozen_before_inference" in row["failure_taxonomy"] for row in result["clips"])


def test_parse_failures_and_abstentions_stay_in_denominators(tmp_path):
    reports = {f"clip-{i:02d}": valid_report(f"clip-{i:02d}") for i in range(1, 7)}
    reports["clip-01"] = {"response_text": "not-json", "raw_response": {"text": "not-json"}}
    reports["clip-02"]["events"] = []
    reports["clip-02"]["report_abstained"] = True
    reports["clip-02"]["abstention_reason"] = "fixture visibility limit"
    out, _, _ = make_run(tmp_path, responses=reports)
    result = score_run(out)
    assert result["counts"]["requested"] == 6
    assert result["counts"]["failed"] == 1
    assert result["counts"]["abstained"] == 1
    assert result["counts"]["true_positive"] == 4
    assert result["counts"]["false_negative"] == 2
    assert result["metrics"]["nonabstained_coverage_all_requests"] == 4/6
    assert result["metrics"]["known_exact_success_rate_all_requests"] == 4/6


def test_tampered_primary_and_posthoc_refused(tmp_path):
    out, _, _ = make_run(tmp_path)
    path = out / "clip-01" / "event-report.json"
    data = json.loads(path.read_text())
    data["overall_uncertainty"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BenchmarkGateError, match="primary seal hash"):
        score_run(out)


def test_commentary_is_not_scoring_input(tmp_path):
    out, _, _ = make_run(tmp_path)
    scored = score_run(out)
    assert scored["counts"]["true_positive"] == 6
    assert "commentator words" not in json.dumps(scored)


def test_absent_posthoc_keeps_all_request_failures_visible(tmp_path):
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[], phase="benchmark", clip_count=6)
    out = private_out(tmp_path)
    run_benchmark(manifest_path=manifest, private_out=out,
                  provider=FixtureVideoProvider({}), model="offline-fixture",
                  environment={}, media_probe=silent_probe)
    result = score_run(out)
    assert result["counts"]["requested"] == 6
    assert result["counts"]["failed"] == 6
    assert result["counts"]["labels_ineligible"] == 6
    assert result["metrics"]["event_recall_labeled_cohort"] is None


@pytest.mark.parametrize("explicit_abstention", [True, False])
def test_empty_labels_do_not_turn_abstention_or_invalid_reports_into_background_success(tmp_path, explicit_abstention):
    reports = {f"clip-{i:02d}": valid_report(f"clip-{i:02d}") for i in range(1, 7)}
    for report in reports.values():
        report.update(events=[], report_abstained=explicit_abstention,
                      abstention_reason="synthetic insufficient evidence" if explicit_abstention else None)
    out, _, _ = make_run(tmp_path, mutation=lambda labels: labels.update(events=[]), responses=reports)
    result = score_run(out)
    assert result["counts"]["exact_event_set"] == 0
    assert result["counts"]["abstained"] == (6 if explicit_abstention else 0)
    assert result["counts"]["failed"] == (0 if explicit_abstention else 6)
    assert result["metrics"]["event_recall_labeled_cohort"] is None
