from pathlib import Path
import sys
import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chess_classifier_adapter import expected_action_space
from chess_classifier_policy import policy_result


def contract_and_logits():
    actions = expected_action_space()
    logits = [0.0]*len(actions)
    logits[actions.index("a1a8")] = 10.0
    logits[actions.index("e2e4")] = 9.0
    return {"id2label": actions}, logits


def test_raw_illegal_action_abstains_without_silent_masking():
    contract, logits = contract_and_logits()
    result = policy_result(chess.STARTING_FEN, logits, contract)
    assert not result["accepted"] and result["move_uci"] is None
    assert result["raw_choice_uci"] == "a1a8"
    assert result["legal_choice_uci"] == "e2e4"
    assert result["selection_mode"] == "raw"


def test_explicit_mask_returns_legal_choice_but_keeps_raw_illegal():
    contract, logits = contract_and_logits()
    result = policy_result(chess.STARTING_FEN, logits, contract, use_legal_mask=True)
    assert result["accepted"] and result["move_uci"] == "e2e4"
    assert result["raw_choice_is_legal"] is False
    assert result["raw_choice_uci"] == "a1a8"
    assert result["selection_mode"] == "legal_mask"
