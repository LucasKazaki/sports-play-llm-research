from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chess_move_only_lm_v4 as experiment


@pytest.mark.parametrize("raw,expected", [
    (" e2e4", "e2e4"), (" M: e2e4 d2d4 E: 0.3 B: d2d4", "e2e4"),
    ("M:e2e4", "e2e4"), (" a7a8q", "a7a8q"),
    ("BAD e2e4", None), ("B: e2e4", None), ("e2e4oops d2d4", None),
    ("M: M: e2e4", None), ("", None), ("e2e5", "e2e5")])
def test_parser_uses_only_first_token_without_late_answer_rescue(raw, expected):
    assert experiment.parse_action(raw) == expected


def row(fen=chess.STARTING_FEN, move="e2e4"):
    return {"id": "fixture", "game_id": "abcdefgh", "fen": fen, "teacher_move_uci": move}


def test_generator_prefix_ignores_hidden_teacher_and_evaluator_material():
    sample = row()
    leaked = {**sample, "teacher_move_uci": "SECRET", "candidates": ["SECRET"], "pv": "SECRET", "themes": "SECRET"}
    assert experiment.prompt_for(sample) == experiment.prompt_for(leaked) == f"P: {chess.STARTING_FEN:90}M:"


def test_illegal_supervision_is_rejected_before_tokenizer():
    class NeverTokenizer:
        def __call__(self, *args, **kwargs):
            raise AssertionError("illegal label reached tokenizer")
    with pytest.raises(ValueError, match="illegal completion"):
        experiment.make_example(row(move="a1a8"), NeverTokenizer())


def test_joint_token_crossing_supervision_boundary_is_rejected():
    boundary = len(experiment.prompt_for(row()))
    class CrossingTokenizer:
        eos_token = "<eos>"
        def __call__(self, *args, **kwargs):
            return {"input_ids": [1], "offset_mapping": [(boundary-1, boundary+1)]}
    with pytest.raises(ValueError, match="crosses supervision"):
        experiment.make_example(row(), CrossingTokenizer())


@pytest.mark.parametrize("sample", [row(), row("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q")])
def test_actual_tokenizer_has_exact_masked_prefix_and_only_move_eos_targets(sample):
    from transformers import AutoTokenizer
    base = Path(__file__).resolve().parents[1] / "data/private/chess-distill-v1/base-model"
    if not base.exists():
        pytest.skip("locally acquired pinned tokenizer absent")
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    ids, labels = experiment.make_example(sample, tokenizer)
    prefix = tokenizer.encode(experiment.prompt_for(sample), add_special_tokens=False)
    assert ids[:len(prefix)] == prefix and labels[:len(prefix)] == [-100]*len(prefix)
    assert labels[len(prefix):] == ids[len(prefix):]
    assert tokenizer.decode(ids[len(prefix):], skip_special_tokens=True).strip() == sample["teacher_move_uci"]
    assert ids[-1] == tokenizer.eos_token_id


class FakeInputs(dict):
    def to(self, _): return self


class FakeTokenizer:
    pad_token_id = eos_token_id = 0
    def __init__(self, outputs): self.outputs = outputs
    def __call__(self, texts, **kwargs):
        import torch
        self.inputs = list(texts)
        return FakeInputs(input_ids=torch.ones((len(texts), 2), dtype=torch.long),
                          attention_mask=torch.ones((len(texts), 2), dtype=torch.long))
    def batch_decode(self, tokens, **kwargs):
        return self.outputs[:len(tokens)]


def test_evaluation_retains_raw_illegal_parse_failure_and_token_ids(tmp_path):
    import torch
    class FixedModel:
        def eval(self): return self
        def generate(self, input_ids, **kwargs):
            return torch.cat((input_ids, torch.ones((len(input_ids), 2), dtype=torch.long)), dim=1)
    tokenizer = FakeTokenizer([" a1a8 later e2e4", " e2e4", "BAD e2e4"])
    rows = [{**row(), "id": str(i)} for i in range(3)]
    result = experiment.evaluate(FixedModel(), tokenizer, rows,
        {"generation": {"batch_size": 3, "max_new_tokens": 16}}, "cpu", tmp_path, "fixture")
    assert result["count"] == result["accounted"] == 3
    assert result["raw_parse_count"] == 2
    assert result["raw_legal_count"] == result["raw_match_count"] == 1
    assert result["records"][0]["move_uci"] == "a1a8"
    assert result["records"][2]["move_uci"] is None
    assert all(r["generated_token_ids"] == [1, 1] for r in result["records"])
    assert all("teacher_move_uci" not in text and "e2e4" not in text for text in tokenizer.inputs)


@pytest.mark.parametrize("failure", ["exception", "shape"])
def test_backend_failure_stops_calls_and_keeps_complete_denominator(tmp_path, failure):
    import torch
    class FailedModel:
        calls = 0
        def eval(self): return self
        def generate(self, **kwargs):
            self.calls += 1
            if failure == "exception":
                raise RuntimeError("injected backend error")
            return torch.zeros((2, 1), dtype=torch.long)
    model = FailedModel()
    rows = [{**row(), "id": str(i)} for i in range(3)]
    result = experiment.evaluate(model, FakeTokenizer([]), rows,
        {"generation": {"batch_size": 1, "max_new_tokens": 16}}, "cpu", tmp_path, "failure")
    assert model.calls == 1
    assert result["count"] == result["accounted"] == result["backend_failure_count"] == 3
    assert result["raw_parse_count"] == result["raw_match_count"] == 0
    assert result["records"][0]["error"].startswith("backend_failure:")
    assert all(r["error"] == "not_run_after_backend_failure" for r in result["records"][1:])


def test_checkpoint_selection_respects_legality_then_earliest_only_after_match_count():
    results = {0: {"raw_match_count": 4, "raw_legal_count": 10},
               256: {"raw_match_count": 4, "raw_legal_count": 10},
               512: {"raw_match_count": 5, "raw_legal_count": 8}}
    assert max(results, key=lambda step: experiment.selection_key(step, results[step])) == 512
    del results[512]
    assert max(results, key=lambda step: experiment.selection_key(step, results[step])) == 0


@pytest.mark.parametrize("tamper", ["protocol", "dataset_hash", "teacher_budget", "row_fen", "row_game", "count", "illegal_label"])
def test_training_bindings_reject_changed_protocol_teacher_or_source_before_calls(tmp_path, tamper):
    import copy
    import json
    from chess_stockfish_distill import digest
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text("frozen fixture protocol bytes")
    protocol = {"teacher": {"sha256": "fixture-engine", "nodes": 50000},
                "splits": {"train": 1, "development": 1, "holdout": 1}}
    dataset = {"protocol_sha256": digest(protocol_path),
               "splits": {split: [row()] for split in protocol["splits"]}}
    (tmp_path / "dataset.json").write_text(json.dumps(dataset))
    labels = {"protocol_sha256": digest(protocol_path), "dataset_sha256": digest(tmp_path / "dataset.json"),
              "engine": {"sha256": "fixture-engine", "settings": copy.deepcopy(protocol["teacher"])},
              "splits": copy.deepcopy(dataset["splits"])}
    experiment.validate_training_bindings(protocol, protocol_path, dataset, labels, tmp_path)
    if tamper == "protocol": labels["protocol_sha256"] = "changed"
    elif tamper == "dataset_hash": labels["dataset_sha256"] = "changed"
    elif tamper == "teacher_budget": labels["engine"]["settings"]["nodes"] = 1
    elif tamper == "row_fen": labels["splits"]["holdout"][0]["fen"] = chess.STARTING_FEN.replace(" 0 1", " 1 1")
    elif tamper == "row_game": labels["splits"]["holdout"][0]["game_id"] = "foreign1"
    elif tamper == "count": labels["splits"]["holdout"] = []
    elif tamper == "illegal_label": labels["splits"]["holdout"][0]["teacher_move_uci"] = "a1a8"
    with pytest.raises(ValueError):
        experiment.validate_training_bindings(protocol, protocol_path, dataset, labels, tmp_path)
