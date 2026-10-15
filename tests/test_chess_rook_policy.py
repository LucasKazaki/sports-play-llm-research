from pathlib import Path
import sys
import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chess_rook_policy import checked_result


@pytest.mark.parametrize("raw,accepted,move", [
    (" e2e4 d2d4 E: 0.2 B: e2e4", True, "e2e4"),
    (" e2e4 d2d4 E: 0.2", True, "e2e4"),
    (" a7a7 E: 0.2 B: a7a7", False, None),
    (" a1a8 E: 0.2 B: a1a8", False, None),
    (" unparseable", False, None),
])
def test_policy_rejects_bad_actions_without_hiding_raw_output(raw, accepted, move):
    result = checked_result(chess.STARTING_FEN, raw)
    assert result["accepted"] is accepted
    assert result["move_uci"] == move
    assert result["raw_output"] == raw
