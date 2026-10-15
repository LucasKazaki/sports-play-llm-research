"""Software checks; these fixtures do not establish chess-model quality."""
import json
import random
from pathlib import Path

import chess
import pytest

from scripts.chess_stockfish_distill import (
    board_key, historical_exclusions, make_example, parse_action, legal_action,
    prompt_for, select_rows, split_for_game, target_for,
)


def source_rows(count=120):
    rng = random.Random(712)
    for i in range(count):
        board = chess.Board()
        for _ in range(8):
            if board.is_game_over():
                break
            board.push(rng.choice(list(board.legal_moves)))
        if board.is_game_over():
            continue
        setup = next(iter(board.legal_moves))
        yield {"PuzzleId": str(i), "GameUrl": f"https://lichess.org/game{i:04d}#17",
               "FEN": board.fen(), "Moves": setup.uci(), "Rating": "1600"}


def test_game_assignment_deterministic_and_all_splits_exist():
    values = [split_for_game(f"game{i:04d}", 4082026) for i in range(200)]
    assert set(values) == {"train", "development", "holdout"}
    assert values == [split_for_game(f"game{i:04d}", 4082026) for i in range(200)]


def test_selection_excludes_prior_games_and_boards_and_replays_setup():
    rows = list(source_rows())
    excluded = rows[0]["GameUrl"].split("/")[-1].split("#")[0]
    splits, rejected = select_rows(rows + rows, {"train": 6, "development": 3, "holdout": 3},
                                   4082026, {excluded}, {board_key(rows[1]["FEN"])})
    all_rows = sum(splits.values(), [])
    assert len(all_rows) == 12
    assert len({r["game_id"] for r in all_rows}) == 12
    assert excluded not in {r["game_id"] for r in all_rows}
    for split, selected in splits.items():
        for row in selected:
            assert split_for_game(row["game_id"], 4082026) == split
            assert chess.Board(row["fen"]).is_valid()
    assert rejected["duplicate_or_excluded"] >= 2


def test_missing_bucket_fails_instead_of_silently_shrinking_denominator():
    with pytest.raises(ValueError, match="did not fill"):
        select_rows([], {"train": 1, "development": 1, "holdout": 1}, 4082026)


def test_invalid_board_and_illegal_setup_are_skipped():
    rows = list(source_rows())
    bad = {**rows[0], "Moves": "a1a8"}
    _, rejected = select_rows([bad] + rows, {"train": 1, "development": 1, "holdout": 1}, 4082026)
    assert rejected["invalid"] == 1


@pytest.mark.parametrize("raw,expected,fallback", [
    ("M: e2e4 d2d4 E: 0.2 0.1 B: d2d4", "d2d4", False),
    ("M: e2e4 d2d4", "e2e4", True),
    ("B: a7a8q", "a7a8q", False),
    ("B: e2e9", None, False),
    ("e2e4", None, False),
])
def test_raw_action_parser(raw, expected, fallback):
    assert parse_action(raw) == (expected, fallback)


@pytest.mark.parametrize("move,expected", [("a7a7", False), (None, False), ("a1a8", False),
                                            ("nonsense", False), ("e2e4", True)])
def test_malformed_or_illegal_action_is_failure_not_crash(move, expected):
    assert legal_action(chess.STARTING_FEN, move) is expected


def test_generator_input_does_not_contain_supervision():
    row = {"fen": chess.STARTING_FEN, "teacher_move_uci": "e2e4",
           "candidates": [{"move_uci": "e2e4", "score_cp": 30, "mate": None}],
           "solution": "hidden", "pv_uci": ["e2e4", "e7e5"]}
    assert prompt_for(row) == chess.STARTING_FEN.ljust(90)
    assert "e2e4" not in prompt_for(row)
    assert target_for(row) == "M: e2e4 E: 0.30 B: e2e4"


def test_supervision_keeps_mate_distinct_from_centipawns():
    row = {"teacher_move_uci": "h7h8q", "candidates": [
        {"move_uci": "h7h8q", "score_cp": None, "mate": 2},
        {"move_uci": "h7h8r", "score_cp": -150, "mate": None}]}
    assert "E: #2 -1.50" in target_for(row)


def test_completion_loss_masks_every_input_token():
    class Tokenizer:
        eos_token = "!"

        def encode(self, text, add_special_tokens=False):
            return list(text.encode())
    row = {"fen": chess.STARTING_FEN, "teacher_move_uci": "e2e4",
           "candidates": [{"move_uci": "e2e4", "score_cp": 30, "mate": None}]}
    tokens, labels = make_example(row, Tokenizer())
    assert labels[:90] == [-100] * 90
    assert tokens[90:] == labels[90:]
    assert all(x != -100 for x in labels[90:])


def test_historical_exclusions_include_both_sides_of_setup(tmp_path):
    board = chess.Board()
    before = board.fen()
    board.push_uci("e2e4")
    after = board.fen()
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"items": [{"game_id": "abcdefgh", "fen": after,
                          "legal_replay": [{"before": before, "after": after}]}]}))
    games, positions = historical_exclusions(path)
    assert games == {"abcdefgh"}
    assert positions == {board_key(before), board_key(after)}


def test_protocol_is_frozen_and_explicit_about_claim_limits():
    path = Path(__file__).resolve().parents[1] / "research/stockfish-distillation-protocol-v1.json"
    protocol = json.loads(path.read_text())
    assert protocol["splits"] == {"train": 800, "development": 64, "holdout": 64,
                                  "seed": 4082026, "assignment": protocol["splits"]["assignment"]}
    assert protocol["training"]["steps"] == 200
    assert "no Elo" in protocol["evaluation"]["claim_boundary"]
