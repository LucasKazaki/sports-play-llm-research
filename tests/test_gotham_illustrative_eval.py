"""Finite fake backends only: never load model weights, torch or an engine."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import chess
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gotham_illustrative_eval as runner


@pytest.fixture
def fixture(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    actual_adapter = Path(__file__).resolve().parents[1] / "scripts/chess_classifier_adapter.py"
    shutil.copyfile(actual_adapter, repo / "scripts/chess_classifier_adapter.py")
    positions = [{"position_id": "scene" + str(i), "pre_move_fen": chess.STARTING_FEN, "side_to_move": "white"}
                 for i in range(3)]
    input_path, ledger_path = tmp_path / "fen-inputs.json", tmp_path / "evaluator-ledger.json"
    runner.save(input_path, {"positions": positions})
    runner.save(ledger_path, {"counts": {"accepted_holdout_positions": 0}, "scenes": [
        {**row, "next_displayed_move_evaluator_only": {"next_displayed_move_uci": move},
         "hidden_creator_commentary": "MUST NEVER REACH A MODEL"}
        for row, move in zip(positions, ("e2e4", "d2d4", "g1f3"))]})
    conditions = {}
    for name in runner.CONDITIONS:
        folder = repo / "models" / name
        folder.mkdir(parents=True)
        (folder / "model.safetensors").write_bytes(("FAKE NO MODEL:" + name).encode())
        runner.save(folder / "config.json", {"fake": True})
        conditions[name] = {"private_model_directory": folder.relative_to(repo).as_posix(),
                            "weights_sha256": runner.digest(folder / "model.safetensors"),
                            "metadata_sha256": {"config.json": runner.digest(folder / "config.json")}}
    plan = {"conditions": conditions, "planned_denominators": {"conditions": 3, "scenes_per_condition": 3,
            "total_policy_scene_outcomes": 9, "failure_retention": "all"},
            "source_binding": {"fen_only_input_path": str(input_path), "fen_only_input_sha256": runner.digest(input_path),
              "position_ids": [p["position_id"] for p in positions], "candidate_ledger_path": str(ledger_path),
              "candidate_ledger_sha256": runner.digest(ledger_path)},
            "language_policy": {"parser_source_ast_sha256": runner.parser_ast_sha256(runner.__file__)},
            "source_sha256": {"scripts/chess_classifier_adapter.py": runner.digest(repo / "scripts/chess_classifier_adapter.py")},
            "limitations": ["FAKE FIXTURE ONLY; zero accepted holdouts; no strength claim"]}
    plan_path = tmp_path / "plan.json"
    runner.save(plan_path, plan)
    return {"repo": repo, "plan": plan, "plan_path": plan_path, "ledger": ledger_path,
            "inputs": input_path, "out": tmp_path / "run"}


def prepare(fixture):
    return runner.prepare(fixture["plan_path"], fixture["repo"], fixture["out"], runner.digest(fixture["plan_path"]))


class FakeBackend:
    def __init__(self, condition, directory, adapter, runtime, events):
        self.condition, self.adapter, self.events = condition, adapter, events
        self.classifier = condition != "base_language_policy_124m"
        self.index = 0
        events.append(("load", condition))

    def encode(self, fen):
        assert fen == chess.STARTING_FEN
        if self.classifier:
            return self.adapter.encode_fen(fen, {"vocab": self.adapter.native_vocab()})
        prompt = f"P: {fen:90}M:"
        return {"input_ids": [ord(c) for c in prompt], "attention_mask": [1] * len(prompt), "prompt": prompt}

    def predict(self, encoded):
        self.events.append(("predict", self.condition, encoded.copy()))
        index = self.index
        self.index += 1
        if self.classifier:
            labels = self.adapter.expected_action_space()
            vector = np.zeros(1968, dtype=np.float32)
            vector[labels.index("a1a8")] = 10.
            vector[labels.index("e2e4")] = 9.
            return {"kind": "classifier", "logits": vector, "id2label": labels}
        return {"kind": "language", "generated_token_ids": [100 + index, 50256],
                "raw_output": ("BAD e2e4", " M: d2d4 trailing B: e2e4", " e2e5")[index]}

    def close(self):
        self.events.append(("close", self.condition))


def factory(events, backend_type=FakeBackend):
    return lambda condition, directory, adapter, runtime: backend_type(condition, directory, adapter, runtime, events)


def generate(fixture, events, backend_type=FakeBackend, custom_factory=None):
    return runner.generate(fixture["out"], backend_factory=custom_factory or factory(events, backend_type),
                           runtime_factory=lambda: {"device": "FAKE_CPU", "no_real_model_calls": True})


@pytest.mark.parametrize("text,move", [(" e2e4", "e2e4"), ("M:e2e4", "e2e4"),
    (" M: a7a8q extra E: 10", "a7a8q"), ("BAD e2e4", None), ("B: e2e4", None),
    ("M: M: e2e4", None), ("e2e4oops d2d4", None), ("", None), ("e2e5", "e2e5")])
def test_strict_first_token_parser_never_rescues_a_later_move(text, move):
    assert runner.parse_action(text) == move


def test_labels_are_unread_until_all_raw_outcomes_and_hashes_are_sealed(fixture, monkeypatch):
    opened = []
    original_open = Path.open
    def deny_evaluator_open(path, *args, **kwargs):
        if path.resolve() == fixture["ledger"].resolve():
            opened.append(str(path))
            raise AssertionError("evaluator labels opened before raw seal")
        return original_open(path, *args, **kwargs)
    events = []
    with monkeypatch.context() as context:
        context.setattr(Path, "open", deny_evaluator_open)
        prepare(fixture)
        raw = generate(fixture, events)
    assert opened == [] and raw["accounted"] == 9 and raw["evaluator_ledger_read"] is False
    assert [e[1] for e in events if e[0] == "load"] == list(runner.CONDITIONS)
    assert len([e for e in events if e[0] == "predict"]) == 9
    assert [e[1] for e in events if e[0] == "close"] == list(runner.CONDITIONS)
    assert all(set(e[2]) <= {"input_ids", "attention_mask", "prompt"} for e in events if e[0] == "predict")
    assert all("MUST NEVER" not in json.dumps(e[2]) and "scene" not in json.dumps(e[2]) for e in events if e[0] == "predict")
    reads = []
    def checked_loader(plan):
        seal, saved, _ = runner.load_verified_raw(fixture["out"])
        assert saved["accounted"] == 9 and len(saved["records"]) == 9
        assert seal["files_sha256"]["raw-results.json"] == runner.digest(fixture["out"] / "raw-results.json")
        reads.append("after_all_nine_sealed")
        return runner.evaluator_ledger(plan)
    joined = runner.evaluate(fixture["out"], ledger_loader=checked_loader)
    assert reads == ["after_all_nine_sealed"] and joined["accounted"] == 9 and joined["accepted_holdout_positions"] == 0
    # Classifier masking cannot hide its three illegal raw choices.
    for condition in runner.CONDITIONS[:2]:
        summary = joined["groups"][condition]
        assert (summary["planned"], summary["accounted"], summary["parsed"], summary["raw_legal"]) == (3, 3, 3, 0)
        rows = [r for r in raw["records"] if r["condition"] == condition]
        assert all(r["move_uci"] == "a1a8" and r["legal_mask_choice_diagnostic"] == "e2e4" for r in rows)
        assert all(r["raw_logit_artifact"]["shape"] == [1968] and r["mask_would_intervene"] for r in rows)
    lm = joined["groups"][runner.CONDITIONS[2]]
    assert (lm["planned"], lm["parsed"], lm["raw_legal"], lm["matches_displayed_move"]) == (3, 2, 1, 1)
    lm_rows = raw["records"][-3:]
    assert [r["status"] for r in lm_rows] == ["parse_failure", "ok", "raw_illegal"]
    assert all(r["generated_token_ids"][-1] == 50256 for r in lm_rows)
    assert lm_rows[1]["raw_output"].endswith("trailing B: e2e4")


@pytest.mark.parametrize("which", ["raw-results.json", "sources/chess_classifier_adapter.py", "raw/condition-0-scene-0.npy"])
def test_tampered_raw_or_source_hash_blocks_label_loading(fixture, which):
    prepare(fixture)
    generate(fixture, [])
    target = fixture["out"] / which
    target.write_bytes(target.read_bytes() + b"tamper")
    reads = []
    with pytest.raises(ValueError, match="sealed raw artifact changed"):
        runner.evaluate(fixture["out"], ledger_loader=lambda _: reads.append("LEAK"))
    assert reads == []


def test_missing_seal_or_required_binding_blocks_label_loading(fixture):
    prepare(fixture)
    reads = []
    with pytest.raises(FileNotFoundError):
        runner.evaluate(fixture["out"], ledger_loader=lambda _: reads.append("LEAK"))
    generate(fixture, [])
    seal = runner.read_json(fixture["out"] / "raw-seal.json")
    del seal["files_sha256"]["raw-results.json"]
    runner.save(fixture["out"] / "raw-seal.json", seal)
    with pytest.raises(ValueError, match="omits required"):
        runner.evaluate(fixture["out"], ledger_loader=lambda _: reads.append("LEAK"))
    assert reads == []


@pytest.mark.parametrize("mutation", ["omitted_npy", "wrong_row_sha", "omitted_prepared_source"])
def test_every_prepared_source_and_row_referenced_npy_is_required_before_labels(fixture, mutation):
    prepare(fixture)
    generate(fixture, [])
    seal_path = fixture["out"] / "raw-seal.json"
    seal = runner.read_json(seal_path)
    if mutation == "omitted_npy":
        del seal["files_sha256"]["raw/condition-0-scene-0.npy"]
    elif mutation == "wrong_row_sha":
        raw_path = fixture["out"] / "raw-results.json"
        raw = runner.read_json(raw_path)
        raw["records"][0]["raw_logit_artifact"]["sha256"] = "0" * 64
        runner.save(raw_path, raw)
        seal["files_sha256"]["raw-results.json"] = runner.digest(raw_path)
    else:
        del seal["files_sha256"]["sources/chess_classifier_adapter.py"]
    runner.save(seal_path, seal)
    reads = []
    with pytest.raises(ValueError, match="prepared source binding|row-referenced raw logit"):
        runner.evaluate(fixture["out"], ledger_loader=lambda _: reads.append("LEAK"))
    assert reads == []


def test_interrupted_attempt_cannot_replay_calls_or_overwrite_partial_bytes(fixture):
    prepare(fixture)
    marker = fixture["out"] / "before-model-calls.json"
    runner.save(marker, {"model_attempt_started": True})
    runner.save(fixture["out"] / "raw-progress.json", {"records": [{"status": "partial_preserved"}]})
    (fixture["out"] / "raw/partial.npy").write_bytes(b"retained partial artifact")
    previous = {p.relative_to(fixture["out"]): p.read_bytes() for p in fixture["out"].rglob("*") if p.is_file()}
    calls = []
    with pytest.raises(ValueError, match="retained generation attempt"):
        runner.generate(fixture["out"], backend_factory=lambda *a: calls.append("loader"),
                        runtime_factory=lambda: calls.append("runtime"))
    assert calls == []
    assert {p.relative_to(fixture["out"]): p.read_bytes() for p in fixture["out"].rglob("*") if p.is_file()} == previous


def test_load_failure_retains_all_three_failed_scenes_and_other_conditions(fixture):
    prepare(fixture)
    events = []
    def fail_first(condition, directory, adapter, runtime):
        if condition == runner.CONDITIONS[0]:
            raise OSError("injected loader failure")
        return FakeBackend(condition, directory, adapter, runtime, events)
    raw = generate(fixture, events, custom_factory=fail_first)
    assert raw["accounted"] == 9
    assert [r["status"] for r in raw["records"][:3]] == ["model_load_error"] * 3
    assert not any(r["model_call_attempted"] for r in raw["records"][:3])
    assert len([e for e in events if e[0] == "predict"]) == 6
    assert runner.evaluate(fixture["out"])["groups"][runner.CONDITIONS[0]]["accounted"] == 3


def test_backend_failure_stops_only_affected_condition_and_retains_nine(fixture):
    prepare(fixture)
    class FailingBackend(FakeBackend):
        def predict(self, encoded):
            if self.condition == runner.CONDITIONS[1]:
                self.events.append(("failed_call", self.condition))
                raise RuntimeError("injected backend failure")
            return super().predict(encoded)
    events = []
    raw = generate(fixture, events, FailingBackend)
    assert len(raw["records"]) == 9
    assert [r["status"] for r in raw["records"][3:6]] == ["model_call_error", "not_run_after_backend_failure", "not_run_after_backend_failure"]
    assert sum(e[0] == "failed_call" for e in events) == 1
    assert sum(r["model_call_attempted"] for r in raw["records"]) == 7
    assert runner.evaluate(fixture["out"])["groups"][runner.CONDITIONS[1]]["accounted"] == 3


def test_nonfinite_logits_are_retained_before_failure_accounting(fixture):
    prepare(fixture)
    class NonfiniteBackend(FakeBackend):
        def predict(self, encoded):
            result = super().predict(encoded)
            if self.classifier and self.condition == runner.CONDITIONS[0] and self.index == 1:
                result["logits"][0] = np.nan
            return result
    raw = generate(fixture, [], NonfiniteBackend)
    failed = raw["records"][0]
    assert failed["status"] == "model_output_error" and failed["model_call_attempted"]
    assert failed["raw_logit_artifact"]["sha256"] == runner.digest(fixture["out"] / failed["raw_logit_artifact"]["path"])
    assert np.isnan(np.load(fixture["out"] / failed["raw_logit_artifact"]["path"], allow_pickle=False)[0])
    assert len(runner.load_verified_raw(fixture["out"])[1]["records"]) == 9


def test_encoding_failure_has_no_call_and_next_actual_call_is_marked_cold(fixture):
    prepare(fixture)
    class EncodeFailure(FakeBackend):
        def encode(self, fen):
            if self.condition == runner.CONDITIONS[0] and not hasattr(self, "failed_encode"):
                self.failed_encode = True
                raise ValueError("injected encoding failure")
            return super().encode(fen)
    raw = generate(fixture, [], EncodeFailure)
    assert raw["records"][0]["status"] == "encoding_error" and not raw["records"][0]["model_call_attempted"]
    assert raw["records"][1]["first_call_after_load"] and not raw["records"][2]["first_call_after_load"]
    assert raw["models"][runner.CONDITIONS[0]]["call_attempts"] == 2


def test_runtime_failure_seals_all_nine_without_any_factory_call(fixture):
    prepare(fixture)
    def runtime_failure(): raise RuntimeError("no runtime")
    calls = []
    raw = runner.generate(fixture["out"], backend_factory=lambda *a: calls.append(a), runtime_factory=runtime_failure)
    assert calls == [] and len(raw["records"]) == 9
    assert all(r["status"] == "runtime_error" and not r["model_call_attempted"] for r in raw["records"])
    assert runner.evaluate(fixture["out"])["accounted"] == 9


def test_model_change_after_preparation_never_reaches_loader(fixture):
    prepare(fixture)
    first = fixture["repo"] / fixture["plan"]["conditions"][runner.CONDITIONS[0]]["private_model_directory"]
    (first / "model.safetensors").write_bytes(b"changed")
    events = []
    raw = generate(fixture, events)
    assert [e[1] for e in events if e[0] == "load"] == list(runner.CONDITIONS[1:])
    assert [r["status"] for r in raw["records"][:3]] == ["model_load_error"] * 3
    assert len(raw["records"]) == 9


def test_unknown_input_fields_are_rejected_even_when_hash_is_updated(fixture):
    inputs = runner.read_json(fixture["inputs"])
    inputs["positions"][0]["teacher_move_uci"] = "e2e4"
    runner.save(fixture["inputs"], inputs)
    fixture["plan"]["source_binding"]["fen_only_input_sha256"] = runner.digest(fixture["inputs"])
    runner.save(fixture["plan_path"], fixture["plan"])
    with pytest.raises(ValueError, match="evaluator material"):
        prepare(fixture)
    assert not fixture["out"].exists()


def test_completed_stages_refuse_repeated_calls_or_overwriting(fixture):
    prepare(fixture)
    with pytest.raises(ValueError, match="existing illustrative"):
        prepare(fixture)
    generate(fixture, [])
    with pytest.raises(ValueError, match="retained generation"):
        generate(fixture, [])
    runner.evaluate(fixture["out"])
    with pytest.raises(ValueError, match="retained evaluator"):
        runner.evaluate(fixture["out"])


def test_cli_generate_requires_parent_gpu_handoff_before_loading(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(runner, "generate", lambda *a: calls.append(a))
    with pytest.raises(SystemExit) as raised:
        runner.main(["generate", "--out", str(tmp_path)])
    assert raised.value.code == 2 and calls == []


def test_cli_prepare_keeps_original_frozen_plan_hash_as_default(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(runner, "prepare", lambda *args: calls.append(args))
    assert runner.main(["prepare", "--plan", str(tmp_path / "plan.json"),
                        "--repo", str(tmp_path), "--out", str(tmp_path / "run")]) == 0
    assert len(calls) == 1 and calls[0][3] == runner.FROZEN_PLAN_SHA256


def test_cli_prepare_rejects_a_different_plan_without_explicit_new_hash(fixture):
    with pytest.raises(ValueError, match="frozen plan identity mismatch"):
        runner.main(["prepare", "--plan", str(fixture["plan_path"]),
                     "--repo", str(fixture["repo"]), "--out", str(fixture["out"])])
    assert not fixture["out"].exists()


def test_cli_new_plan_preparation_from_other_cwd_binds_repository_tests(fixture, tmp_path):
    # Fake weight bytes only; this subprocess performs file preparation, never inference.
    result = subprocess.run([sys.executable, str(Path(runner.__file__).resolve()), "prepare",
                             "--plan", str(fixture["plan_path"]), "--repo", str(fixture["repo"]),
                             "--out", str(fixture["out"]), "--expected-plan-sha256",
                             runner.digest(fixture["plan_path"])],
                            cwd=tmp_path, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"phase": "prepared", "model_calls": 0, "evaluator_ledger_read": False}
    prepared = runner.read_json(fixture["out"] / "prepared.json")
    relative = "sources/test_gotham_illustrative_eval.py"
    assert prepared["source_sha256"][relative] == runner.digest(Path(__file__))
    assert prepared["source_roles"][relative] == "test_source_only"
    assert (fixture["out"] / "sources/test_gotham_illustrative_eval.py").read_bytes() == Path(__file__).read_bytes()
