import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))
from hosted_video_label_conversion import CONFIG_SCHEMA, ConversionError, convert_annotations
from hosted_video_benchmark import FixtureVideoProvider, run_benchmark, sha256_file
from hosted_video_scoring import score_run
from test_hosted_video_benchmark import write_manifest, valid_report, silent_probe, private_out


def source_annotation(*, half=1, seconds=62, label="Foul", visibility="visible", extra_ms=0):
    return {"gameTime": f"{half} - {seconds//60:02d}:{seconds%60:02d}",
            "position": str(seconds*1000+extra_ms), "label": label, "visibility": visibility, "team": "home"}


def config_for(source_sha, *, clip_id="clip-01", media_sha="a"*64):
    return {
        "schema_version": CONFIG_SCHEMA, "source_annotations_sha256": source_sha,
        "source_match_id": "synthetic_league/2026/fixture-match", "half": 1, "half_duration_s": 3000,
        "clip": {"clip_id": clip_id, "source_sha256": media_sha, "offset_s": 60, "duration_s": 5},
        "annotation_origin": "synthetic_fixture", "independence_evidence_sha256": None,
        "mapping": {"Foul": "foul", "Offside": "offside", "Ignore": None},
        "policy": {"input_position_unit": "milliseconds", "input_game_time_basis": "half_relative_mm:ss",
                   "output_time_unit": "seconds", "game_time_consistency": "floor_position_to_whole_second",
                   "point_membership": "start_inclusive_end_exclusive", "interval_before_s": 1,
                   "interval_after_s": 1, "boundary_policy": "clip_to_window", "visibility_policy": "visible_only"},
    }


def inputs(tmp_path, *, annotations=None, config_mutation=None, source_mutation=None):
    source = {"UrlLocal": "synthetic_league/2026/fixture-match",
              "annotations": [source_annotation()] if annotations is None else annotations}
    if source_mutation:
        source_mutation(source)
    source_path = tmp_path / "synthetic-Labels-v2.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    config = config_for(sha256_file(source_path))
    if config_mutation:
        config_mutation(config)
    config_path = tmp_path / "conversion-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return source_path, config_path, tmp_path / "data" / "private" / "converted"


def convert(paths):
    return convert_annotations(annotations_path=paths[0], config_path=paths[1], output_dir=paths[2])


def test_explicit_mapping_half_clip_and_policy_bind_conversion_without_media_access(tmp_path):
    rows = [source_annotation(), source_annotation(half=2),
            source_annotation(seconds=59), source_annotation(seconds=65),
            source_annotation(seconds=63, visibility="not shown"),
            source_annotation(seconds=64, label="Ignore")]
    paths = inputs(tmp_path, annotations=rows)
    hashes = [sha256_file(path) for path in paths[:2]]
    receipt = convert(paths)
    labels = json.loads((paths[2] / "labels.json").read_text())
    assert labels["events"] == [{"label_id": "g0001", "event_type": "foul",
                                  "start_s": 1.0, "peak_s": 2.0, "end_s": 3.0}]
    assert receipt["selected_half"] == 1
    assert receipt["source_annotations_sha256"] == hashes[0]
    assert receipt["configuration_sha256"] == hashes[1]
    assert hashes == [sha256_file(path) for path in paths[:2]]
    assert receipt["labels_sha256"] == sha256_file(paths[2] / "labels.json")
    assert len(receipt["excluded"]) == 5
    assert receipt["annotation_independence_verified"] is False
    assert receipt["clip_media_hash_verified"] is False
    assert receipt["scientific_validation"] is False
    assert not list(tmp_path.rglob("*.mp4"))


@pytest.mark.parametrize("mutation,message", [
    (lambda c: c.update(half=True), "half must"),
    (lambda c: c.update(half=3), "half must"),
    (lambda c: c.update(source_match_id="wrong-match"), "match grouping"),
    (lambda c: c.update(source_match_id="../fixture"), "non-traversing"),
    (lambda c: c.update(source_annotations_sha256="0"*64), "bytes/hash"),
    (lambda c: c["clip"].update(source_sha256="not-a-hash"), "SHA-256"),
    (lambda c: c["clip"].update(offset_s=-1), "bounds"),
    (lambda c: c["clip"].update(duration_s=0), "bounds"),
    (lambda c: c["clip"].update(offset_s=2999), "bounds"),
    (lambda c: c["clip"].update(duration_s=float("inf")), "non-finite"),
    (lambda c: c["policy"].update(input_position_unit="seconds"), "milliseconds"),
    (lambda c: c["policy"].pop("point_membership"), "policy keys"),
    (lambda c: c["policy"].update(interval_before_s=0, interval_after_s=0), "extent"),
    (lambda c: c["policy"].update(boundary_policy="guess"), "boundary_policy"),
    (lambda c: c.update(mapping={"Offside": "offside"}), "no explicit ontology mapping"),
    (lambda c: c.update(mapping={}), "ontology mapping"),
    (lambda c: c.update(annotation_origin="independent_annotation"), "independence_evidence"),
])
def test_invalid_explicit_config_fails_before_output_creation(tmp_path, mutation, message):
    paths = inputs(tmp_path, config_mutation=mutation)
    with pytest.raises((ConversionError, ValueError), match=message):
        convert(paths)
    assert not paths[2].exists()


@pytest.mark.parametrize("row,message", [
    ({**source_annotation(), "gameTime": "2 - 01:03"}, "disagree"),
    ({**source_annotation(), "gameTime": "01:02"}, "explicit half"),
    ({**source_annotation(), "position": 62.0}, "integer milliseconds"),
    ({**source_annotation(), "position": "62"}, "disagree"),
    ({**source_annotation(), "position": "-62000"}, "integer milliseconds"),
    ({**source_annotation(), "half": 2}, "grouping"),
    ({**source_annotation(), "match_id": "another-match"}, "grouping"),
    ({**source_annotation(), "visibility": "guessed"}, "visibility"),
    (source_annotation(seconds=3001), "half duration"),
])
def test_invalid_source_annotations_fail_closed(tmp_path, row, message):
    paths = inputs(tmp_path, annotations=[row])
    with pytest.raises(ConversionError, match=message):
        convert(paths)
    assert not paths[2].exists()


def test_exact_duplicate_annotations_are_rejected(tmp_path):
    row = source_annotation()
    with pytest.raises(ConversionError, match="duplicate half"):
        convert(inputs(tmp_path, annotations=[row, copy.deepcopy(row)]))


def test_mapping_cannot_collapse_distinct_source_labels_into_duplicate_events(tmp_path):
    paths = inputs(tmp_path, annotations=[source_annotation(), source_annotation(label="Offside")],
                   config_mutation=lambda c: c["mapping"].update(Offside="foul"))
    with pytest.raises(ConversionError, match="collapses duplicate"):
        convert(paths)


def test_changed_source_bytes_refused_and_existing_outputs_never_overwritten(tmp_path):
    paths = inputs(tmp_path)
    original = paths[0].read_bytes()
    paths[0].write_bytes(original+b" ")
    with pytest.raises(ConversionError, match="bytes/hash"):
        convert(paths)
    paths[0].write_bytes(original)
    convert(paths)
    label_bytes = (paths[2] / "labels.json").read_bytes()
    with pytest.raises(ConversionError, match="already exists"):
        convert(paths)
    assert (paths[2] / "labels.json").read_bytes() == label_bytes


def test_start_is_included_end_excluded_and_clipping_is_explicit(tmp_path):
    paths = inputs(tmp_path, annotations=[source_annotation(seconds=60),
                                        source_annotation(seconds=65)])
    convert(paths)
    events = json.loads((paths[2] / "labels.json").read_text())["events"]
    assert len(events) == 1
    assert (events[0]["start_s"], events[0]["peak_s"], events[0]["end_s"]) == (0, 0, 1)


def test_reject_crossing_policy_does_not_silently_clip(tmp_path):
    paths = inputs(tmp_path, annotations=[source_annotation(seconds=60)],
                   config_mutation=lambda c: c["policy"].update(boundary_policy="reject_crossing"))
    with pytest.raises(ConversionError, match="crosses clip"):
        convert(paths)


def test_millisecond_fraction_is_converted_only_under_declared_units(tmp_path):
    paths = inputs(tmp_path, annotations=[source_annotation(extra_ms=250)])
    convert(paths)
    event = json.loads((paths[2] / "labels.json").read_text())["events"][0]
    assert event["peak_s"] == 2.25
    assert event["start_s"] == 1.25


@pytest.mark.parametrize("empty", [False, True])
def test_raw_soccernet_to_frozen_label_hash_to_existing_scorer(tmp_path, empty):
    manifest, ids = write_manifest(tmp_path, permitted=False, processors=[])
    data = json.loads(manifest.read_text())
    source, config_path, out = inputs(tmp_path, annotations=[] if empty else [source_annotation()],
        config_mutation=lambda config: config["clip"].update(
            clip_id=ids[0], source_sha256=data["clips"][0]["sha256"]))
    receipt = convert((source, config_path, out))
    clip = data["clips"][0]
    clip["held_out"].update(labels_path=str(out / "labels.json"),
                            labels_sha256=receipt["labels_sha256"], commentary_path=None)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    response = valid_report(ids[0])
    response["events"][0]["event_type"] = "foul"
    if empty:
        response.update(events=[], report_abstained=True, abstention_reason="synthetic uncertainty")
    run_dir = private_out(tmp_path)
    before = source.read_bytes(), (out / "labels.json").read_bytes()
    run_benchmark(manifest_path=manifest, private_out=run_dir,
                  provider=FixtureVideoProvider({ids[0]: response}), model="offline-conversion-fixture",
                  environment={}, media_probe=silent_probe, open_held_out=True)
    result = score_run(run_dir)
    assert result["counts"]["labels_eligible"] == 1
    assert result["counts"]["true_positive"] == (0 if empty else 1)
    assert result["counts"]["exact_event_set"] == (0 if empty else 1)
    assert result["counts"]["abstained"] == (1 if empty else 0)
    assert result["metrics"]["event_recall_labeled_cohort"] == (None if empty else 1)
    assert result["scientific_validation"] is False
    assert before == (source.read_bytes(), (out / "labels.json").read_bytes())


def test_no_annotations_does_not_mean_verified_background(tmp_path):
    paths = inputs(tmp_path, annotations=[])
    receipt = convert(paths)
    assert receipt["converted_label_count"] == 0
    assert json.loads((paths[2] / "labels.json").read_text())["events"] == []
    assert any("not verified background" in limit for limit in receipt["limits"])


def test_observed_soccernet_match_metadata_is_accepted_without_model_label_leakage(tmp_path):
    metadata = {
        "gameAwayTeam": "fixture-away-private-name",
        "gameDate": "2026-09-13 fixture-only-date",
        "gameHomeTeam": "fixture-home-private-name",
        "gameScore": "fixture-private-score",
    }
    paths = inputs(tmp_path, source_mutation=lambda source: source.update(metadata))
    receipt = convert(paths)
    labels = json.loads((paths[2] / "labels.json").read_text(encoding="utf-8"))
    assert len(labels["events"]) == 1
    assert receipt["converted_label_count"] == 1
    encoded = json.dumps(labels)
    for key, value in metadata.items():
        assert key not in encoded
        assert value not in encoded


def test_unknown_soccernet_top_level_metadata_stays_rejected(tmp_path):
    paths = inputs(tmp_path, source_mutation=lambda source: source.update(unrecognizedPrivateField="fixture"))
    with pytest.raises(ConversionError, match="source grouping keys"):
        convert(paths)
    assert not paths[2].exists()
