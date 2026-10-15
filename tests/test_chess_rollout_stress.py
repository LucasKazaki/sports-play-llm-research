import io
import json
from pathlib import Path
import sys

import chess
import chess.pgn
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chess_classifier_adapter import expected_action_space
from chess_rollout_stress import aggregate, apply_model, export_pgn, finish_if_needed, make_games, opening_board


def protocol():
    path = Path(__file__).resolve().parents[1] / "research/chess-rollout-stress-protocol-v1.json"
    return json.loads(path.read_text())


def logits():
    actions = expected_action_space()
    vector = [0.0] * len(actions)
    vector[actions.index("a1a8")] = 10.0
    vector[actions.index("e2e4")] = 9.0
    return {"id2label": actions}, vector


def game(mode="raw_abstain"):
    return next(g for g in make_games(protocol()) if g["opening"] == "initial" and g["mode"] == mode)


def test_all_planned_fixtures_legal_unique_and_retained():
    games = make_games(protocol())
    assert len(games) == len({g["id"] for g in games}) == 64
    assert all(g["board"].is_valid() for g in games)
    assert sum(v["planned_games"] for v in aggregate(games).values()) == 64
    assert all(v["terminations"] == {"not_run": 16} for v in aggregate(games).values())


def test_illegal_opening_rejected_before_any_model_call():
    with pytest.raises(ValueError, match="illegal opening"):
        opening_board({"id": "bad", "uci": ["e2e5"]})


def test_raw_illegal_stop_preserves_board_and_unfinished_chess_result():
    g = game()
    contract, vector = logits()
    apply_model(g, vector, contract, 7)
    assert g["termination"] == "raw_illegal" and g["result"] == "*"
    assert g["board"].fen() == chess.STARTING_FEN and g["additional_plies"] == 0
    assert g["decisions"][0]["logit_row"] == 7
    assert g["decisions"][0]["raw_uci"] == "a1a8"
    assert g["decisions"][0]["applied_uci"] is None
    assert not g["decisions"][0]["mask_intervened"]


def test_mask_intervention_retains_illegal_raw_and_pushes_only_legal_move():
    g = game("legal_mask")
    contract, vector = logits()
    apply_model(g, vector, contract, 0)
    assert g["termination"] is None and g["additional_plies"] == 1
    assert g["board"].peek().uci() == "e2e4"
    assert g["decisions"][0]["mask_intervened"]
    assert not g["decisions"][0]["raw_legal"]
    assert g["moves"][0]["fen"] == chess.STARTING_FEN


def test_cap_is_unfinished_and_terminal_outcome_takes_precedence():
    g = game()
    g["additional_plies"] = 200
    assert finish_if_needed(g, 200) and g["termination"] == "ply_cap" and g["result"] == "*"
    mate = game()
    for san in ("f3", "e5", "g4", "Qh4#"):
        mate["board"].push_san(san)
    mate["additional_plies"] = 200
    assert finish_if_needed(mate, 200)
    assert mate["termination"] == "checkmate" and mate["result"] == "0-1"


def test_claimable_draw_uses_retained_history():
    g = game()
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        g["board"].push_uci(uci)
    assert finish_if_needed(g, 200)
    assert g["termination"] == "threefold_repetition" and g["result"] == "1/2-1/2"


def test_pgn_keeps_opening_history_and_nonchess_stop_without_loss_label():
    g = next(g for g in make_games(protocol()) if g["opening"] == "exchange-centre")
    g["termination"] = "model_call_error"
    pgn = chess.pgn.read_game(io.StringIO(export_pgn(g)))
    assert pgn.errors == []
    assert pgn.headers["Result"] == "*" and pgn.headers["Termination"] == "model_call_error"
    assert len(list(pgn.mainline_moves())) == 6
    assert pgn.end().board().fen() == g["board"].fen()


def test_aggregate_never_hides_raw_illegality_in_mask_mode():
    g = game("legal_mask")
    contract, vector = logits()
    apply_model(g, vector, contract, 0)
    summary = aggregate([g])["base:legal_mask"]
    assert summary["model_decisions"] == 1 and summary["raw_legal_decisions"] == 0
    assert summary["mask_interventions"] == 1


def test_malformed_logits_do_not_change_board():
    g = game()
    contract, vector = logits()
    vector[0] = float("nan")
    with pytest.raises(ValueError):
        apply_model(g, vector, contract, 0)
    assert g["board"].fen() == chess.STARTING_FEN
    assert not g["moves"] and not g["decisions"]


@pytest.mark.parametrize("failure", ["model_load", "opponent_start", "opponent_configuration"])
def test_backend_start_failure_retains_all64_games_and_unfinished_pgn(tmp_path, monkeypatch, failure):
    import torch
    import transformers
    import chess_rollout_stress as runner
    from chess_stockfish_distill import digest

    frozen = protocol()
    directories = [tmp_path / "base", tmp_path / "selected"]
    for directory in directories:
        directory.mkdir()
        (directory / "model.safetensors").write_bytes(directory.name.encode())
    frozen["model_binding"]["base_weight_sha256"] = digest(directories[0] / "model.safetensors")
    frozen["model_binding"]["selected_weight_sha256"] = digest(directories[1] / "model.safetensors")
    engine = tmp_path / "engine.exe"
    engine.write_bytes(b"fixture-only-not-executed")
    frozen["opponent"]["sha256"] = digest(engine)
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(frozen))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(runner, "load_native_contract", lambda _: {"id2label": expected_action_space(),
                                                                 "source_sha256": {"fixture": "test-only"}})

    class FakeModel:
        def float(self): return self
        def to(self, _): return self
        def eval(self): return self

    def load(*args, **kwargs):
        if failure == "model_load":
            raise RuntimeError("injected model startup failure")
        return FakeModel()

    def start(*args, **kwargs):
        if failure == "opponent_configuration":
            return FakeEngine()
        raise OSError("injected opponent startup failure")

    class FakeEngine:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def configure(self, _):
            raise ValueError("injected opponent configuration failure")

    monkeypatch.setattr(transformers.LlamaForSequenceClassification, "from_pretrained", load)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start)
    out = tmp_path / "receipt"
    result = runner.run(protocol_path, out, directories[0], directories[1], engine)
    reason = {"model_load": "model_load_error", "opponent_start": "opponent_start_error",
              "opponent_configuration": "opponent_configuration_error"}[failure]
    assert result["planned_games"] == 64
    assert all(group["terminations"] == {reason: 16} for group in result["aggregate"].values())
    assert all(group["chess_results"] == {"*": 16} for group in result["aggregate"].values())
    assert len(json.loads((out / "games.json").read_text())) == 64
    pgns = io.StringIO((out / "games.pgn").read_text())
    parsed = []
    while (entry := chess.pgn.read_game(pgns)) is not None:
        parsed.append(entry)
    assert len(parsed) == 64 and all(not p.errors for p in parsed)
