from pathlib import Path
import sys
import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chess_move_only_lm_policy import policy_result


def test_policy_abstains_on_illegal_first_move_without_searching_later_legal_answer():
    result = policy_result(chess.STARTING_FEN, " a1a8 B: e2e4", [1, 2, 3])
    assert not result["accepted"] and result["move_uci"] is None
    assert result["raw_move_uci"] == "a1a8" and result["generated_token_ids"] == [1, 2, 3]


def test_policy_keeps_complete_raw_text_and_uses_legal_first_token_only():
    result = policy_result(chess.STARTING_FEN, " e2e4 d2d4 E: 0.3 B: d2d4", [1, 2])
    assert result["accepted"] and result["move_uci"] == "e2e4"
    assert result["raw_output"].endswith("B: d2d4")


def test_malformed_first_token_cannot_be_rescued_by_later_answer():
    result = policy_result(chess.STARTING_FEN, " BAD e2e4", [])
    assert not result["accepted"] and result["raw_move_uci"] is None
