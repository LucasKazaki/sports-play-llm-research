import importlib.util
import json
from pathlib import Path
import sys
import chess
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from chess_ollama_control import build_prompt


@pytest.mark.parametrize("condition", ["fen_only", "board_and_legal_moves"])
def test_generator_input_has_no_teacher_or_continuation(condition):
    row = {"fen": chess.STARTING_FEN, "teacher_move_uci": "ANSWER_SENTINEL",
           "candidates": [{"pv": "HIDDEN_SENTINEL"}], "solution": "SECRET_SENTINEL"}
    prompt = build_prompt(row, condition)
    assert not any(s in prompt for s in ("ANSWER_SENTINEL", "HIDDEN_SENTINEL", "SECRET_SENTINEL"))
    assert ("legal_moves" in prompt) == (condition == "board_and_legal_moves")


def test_legal_list_is_computed_from_current_board():
    packet = json.loads(build_prompt({"fen": chess.STARTING_FEN}, "board_and_legal_moves").split("\n", 1)[1])
    assert len(packet["legal_moves"]) == 20
    assert packet["pieces"]["e1"] == "K"
    assert packet["pieces"]["e8"] == "k"
    assert packet["side_to_move"] == "white"


def test_unsupported_representation_fails():
    with pytest.raises(ValueError):
        build_prompt({"fen": chess.STARTING_FEN}, "answers")
