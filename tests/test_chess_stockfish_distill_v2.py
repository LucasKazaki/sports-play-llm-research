import json
from pathlib import Path
import sys
import chess
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import chess_stockfish_distill_v2 as v2


def row():
    return {"id": "fixture", "fen": chess.STARTING_FEN, "teacher_move_uci": "e2e4", "candidates": [
        {"move_uci": "e2e4", "score_cp": 30, "mate": None},
        {"move_uci": "d2d4", "score_cp": 20, "mate": None},
        {"move_uci": "g1f3", "score_cp": 10, "mate": None},
        {"move_uci": "c2c4", "score_cp": 5, "mate": None},
        {"move_uci": "g2g3", "score_cp": -10, "mate": None}]}


def test_native_prefix_and_target_pairing():
    fixture = row()
    assert v2.prompt_for(fixture) == f"P: {chess.STARTING_FEN:90}M:"
    target = v2.target_for(fixture)
    assert target == v2.target_for(fixture)
    moves, rest = target.split("E: ")
    scores, best = rest.split("B: ")
    assert dict(zip(moves.split(), map(float, scores.split()))) == {
        c["move_uci"]: c["score_cp"]/100 for c in fixture["candidates"]}
    assert best.strip() == "e2e4"


def test_input_is_independent_of_teacher_answer():
    a = row()
    b = {**a, "teacher_move_uci": "HIDDEN", "candidates": ["SECRET"]}
    assert v2.prompt_for(a) == v2.prompt_for(b)


def test_parser_recovers_candidate_when_m_marker_is_in_prompt():
    assert v2.parse_action(" e2e4 d2d4 E: 0.3") == ("e2e4", True)
    assert v2.parse_action(" e2e4 d2d4 E: 0.3 B: d2d4") == ("d2d4", False)
    assert v2.parse_action(" nonsense E: 0.3") == (None, False)
    assert v2.parse_action(" M: e2e4 d2d4 E: 0.3") == ("e2e4", True)


def test_real_tokenizer_train_and_inference_prefix_match():
    transformers = pytest.importorskip("transformers")
    path = SCRIPTS.parent / "data/private/chess-distill-v1/base-model"
    if not path.exists():
        pytest.skip("optional locally acquired tokenizer absent")
    tokenizer = transformers.AutoTokenizer.from_pretrained(path, local_files_only=True)
    fixture = row()
    ids, labels = v2.make_example(fixture, tokenizer)
    prefix = tokenizer.encode(v2.prompt_for(fixture), add_special_tokens=False)
    assert ids[:len(prefix)] == prefix
    assert labels[:len(prefix)] == [-100]*len(prefix)
    assert ids == tokenizer.encode(v2.prompt_for(fixture)+v2.target_for(fixture)+tokenizer.eos_token, add_special_tokens=False)


def test_v2_has_fresh_splits_and_smaller_fixed_learning_rate():
    protocol = json.loads((SCRIPTS.parent / "research/stockfish-distillation-protocol-v2.json").read_text())
    assert protocol["splits"]["seed"] != 4082026
    assert protocol["training"]["learning_rate"] == 0.000002
    assert protocol["training"]["steps"] == 800
    assert protocol["teacher"]["multipv"] == 5


def test_recount_preserves_raw_text_original_receipt_and_checkpoint(tmp_path):
    checkpoint = tmp_path / "checkpoint/model.safetensors"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"synthetic checkpoint identity")
    raw = " e2e4 d2d4 E: 0.3"
    receipt = {"schema": "chess.stockfish-distillation.v2",
               "model": {"checkpoint_sha256": v2.core.digest(checkpoint)},
               "evaluation": {"baseline": {"development": {"count": 1, "records": [
                   {"fen": chess.STARTING_FEN, "raw_output": raw, "teacher_move_uci": "e2e4"}]}}}}
    v2.core.save(tmp_path / "receipt.json", receipt)
    original_bytes = (tmp_path / "receipt.json").read_bytes()
    result = v2.reaccount(tmp_path)
    assert (tmp_path / "receipt-before-action-parser-repair.json").read_bytes() == original_bytes
    assert checkpoint.read_bytes() == b"synthetic checkpoint identity"
    row = result["evaluation"]["baseline"]["development"]["records"][0]
    assert row["raw_output"] == raw
    assert row["move_uci"] == "e2e4" and row["legal"] and row["match"]
    assert result["accounting_repair"]["model_calls"] == 0
    with pytest.raises(ValueError, match="already preserved"):
        v2.reaccount(tmp_path)
