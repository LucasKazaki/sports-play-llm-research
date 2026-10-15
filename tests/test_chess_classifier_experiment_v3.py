from pathlib import Path
from types import SimpleNamespace
import json
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chess_classifier_experiment_v3 as experiment
from chess_classifier_adapter import expected_action_space


def test_checkpoint_selection_uses_raw_quality_then_legality_then_earliest():
    results = {0: {"raw_top1_match_count": 8, "raw_legal_count": 10},
               128: {"raw_top1_match_count": 8, "raw_legal_count": 10},
               256: {"raw_top1_match_count": 7, "raw_legal_count": 12},
               512: {"raw_top1_match_count": 9, "raw_legal_count": 9}}
    assert max(results, key=lambda step: experiment.selection_key(step, results[step])) == 512
    del results[512]
    assert max(results, key=lambda step: experiment.selection_key(step, results[step])) == 0


def test_unsupported_encoding_stays_in_original_evaluation_denominator(tmp_path):
    torch = pytest.importorskip("torch")
    labels = expected_action_space()
    contract = {"vocab": {char: i for i, char in enumerate([
        "-", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "B", "K", "N", "P", "Q", "R",
        "a", "b", "c", "d", "e", "f", "g", "h", "k", "n", "p", "q", "r", "w", "[SEP]", "[PAD]", "[CLS]", "[MASK]"])},
                "id2label": labels, "label2id": {move: i for i, move in enumerate(labels)}}
    class FixedModel:
        def eval(self):
            return self

        def __call__(self, input_ids, attention_mask):
            logits = torch.zeros((len(input_ids), len(labels)))
            logits[:, labels.index("a1a8")] = 10  # Raw illegal rook move must stay visible.
            logits[:, labels.index("e2e4")] = 9
            return SimpleNamespace(logits=logits)
    rows = [{"id": "supported", "game_id": "abcdefgh", "fen": chess.STARTING_FEN, "teacher_move_uci": "e2e4"},
            {"id": "unsupported", "game_id": "ijklmnop", "fen": chess.STARTING_FEN.replace(" 0 1", " 100 1000"),
             "teacher_move_uci": "e2e4"}]
    result = experiment.evaluate(FixedModel(), rows, contract, "cpu", "synthetic", tmp_path, 64)
    assert result["count"] == 2 and result["encoded_count"] == 1
    assert result["raw_legal_count"] == 0 and result["failure_count"] == 1
    assert result["raw_top1_match_count"] == 0 and result["masked_top1_match_count"] == 1
    assert result["raw_top3_match_count"] == 1
    assert result["records"][0]["raw_move_uci"] == "a1a8"
    assert result["records"][0]["masked_move_uci"] == "e2e4"
    assert "error" in result["records"][1]
    assert result["cross_entropy_count"] == 1


def test_frozen_protocol_selects_without_opening_rejected_checkpoint_holdouts():
    path = Path(__file__).resolve().parents[1] / "research/chess-classifier-protocol-v3.json"
    protocol = json.loads(path.read_text())
    assert protocol["training"]["checkpoint_steps"] == [0, 128, 256, 512]
    assert protocol["selection"]["data"] == "development only"
    assert "rejected" in protocol["selection"]["holdout"]
    assert protocol["teacher"]["workers"] == 8


@pytest.mark.parametrize("failure", ["exception", "shape"])
def test_model_failure_stops_more_calls_and_preserves_complete_denominator(tmp_path, failure):
    torch = pytest.importorskip("torch")
    from chess_classifier_adapter import native_vocab
    actions = expected_action_space()
    # Reuse the verified constant vocabulary; this is a software fixture, not model evidence.
    contract = {"vocab": native_vocab(), "id2label": actions,
                "label2id": {move: i for i, move in enumerate(actions)}}
    class BrokenModel:
        calls = 0

        def eval(self):
            return self

        def __call__(self, **kwargs):
            self.calls += 1
            if failure == "exception":
                raise RuntimeError("synthetic backend failure")
            return SimpleNamespace(logits=torch.zeros((1, 3)))
    model = BrokenModel()
    rows = [{"id": str(i), "game_id": f"game{i:04d}", "fen": chess.STARTING_FEN,
             "teacher_move_uci": "e2e4"} for i in range(3)]
    result = experiment.evaluate(model, rows, contract, "cpu", "failed", tmp_path, batch_size=1)
    assert model.calls == 1
    assert result["count"] == result["failure_count"] == 3
    assert result["raw_top1_match_count"] == result["raw_legal_count"] == 0
    assert result["cross_entropy_count"] == 0 and result["cross_entropy"] is None
    assert result["records"][0]["error"].startswith("model_call_failed:")
    assert all(r["error"] == "not_run_after_model_failure" for r in result["records"][1:])
