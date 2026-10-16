"""Software checks for an engine-assisted study candidate, not chess quality."""
import importlib.util
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import chess
import chess.engine
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chess_tutor_v1_server", ROOT / "prototype/chess_tutor_v1/server.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def test_fen_and_legal_move_replay():
    board, history, ply, source = app.parse_position({"fen": chess.STARTING_FEN, "moves": ["e2e4", "e7e5"]})
    expected = chess.Board()
    expected.push_uci("e2e4")
    expected.push_uci("e7e5")
    assert board.fen() == expected.fen()
    assert ply == 2
    assert [item["san"] for item in history] == ["Start", "e4", "e5"]
    assert source["kind"] == "user_position"


def test_pgn_mainline_selected_ply_and_branch():
    pgn = '[Event "<script>inert</script>"]\n\n1. e4 (1. d4 d5) e5 2. Nf3 Nc6 *'
    board, history, ply, source = app.parse_position({"pgn": pgn, "ply": 1})
    assert ply == 1 and board.piece_at(chess.E4).symbol() == "P"
    assert len(history) == 5
    assert source["headers"]["Event"] == "<script>inert</script>"
    board, history, ply, _ = app.parse_position({"pgn": pgn, "ply": 1, "moves": ["c7c5"]})
    assert ply == 2 and history[-1]["san"] == "c5" and len(history) == 3


@pytest.mark.parametrize("payload", [
    {"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}, {"fen": "bad"},
    {"fen": chess.STARTING_FEN, "moves": ["e2e5"]},
    {"fen": chess.STARTING_FEN, "moves": ["0000"]},
    {"pgn": "this is not a game"}, {"pgn": "1. e4 e5 2. Ke3 *"},
    {"pgn": "1. e4 *\n\n1. d4 *"},
    {"pgn": '[Variant "Atomic"]\n\n1. e4 *'},
    {"pgn": "1. e4 *", "ply": True}, {"pgn": "1. e4 *", "ply": 2},
    {"fen": chess.STARTING_FEN, "pgn": "1. e4 *"}, {"model": "false"},
    {"fen": chess.STARTING_FEN, "moves": ["e2e4"]*513}, {"pgn": "x"*24_001},
    {"unknown": "ignored"}, [],
])
def test_rejects_invalid_or_unbounded_inputs(payload):
    with pytest.raises(app.InputError):
        app.parse_position(payload)


def test_verified_facts_capture_checkmate_castle_promotion_and_en_passant():
    board = chess.Board("6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1")
    facts = app.move_facts(board, chess.Move.from_uci("g5d8"))
    assert any(fact["kind"] == "checkmate" for fact in facts)
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")
    facts = app.move_facts(board, chess.Move.from_uci("e5d6"))
    assert any(fact["kind"] == "capture" and "d5 en passant" in fact["text"] for fact in facts)
    board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    assert any(fact["kind"] == "promotion" for fact in app.move_facts(board, chess.Move.from_uci("a7a8n")))
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert any(fact["kind"] == "castling" for fact in app.move_facts(board, chess.Move.from_uci("e1g1")))


def test_score_types_bounds_and_black_perspective_are_explicit():
    info = {"score": chess.engine.PovScore(chess.engine.Cp(121), chess.BLACK), "upperbound": True}
    assert app.score_record(info, chess.BLACK) == {"type": "engine_observation", "kind": "centipawn", "value": 121, "perspective": "black", "bound": "upper", "qualification": "Bounded search estimate; not a guarantee of perfect play or a teaching judgment."}
    mate = app.score_record({"score": chess.engine.PovScore(chess.engine.Mate(-3), chess.WHITE)}, chess.WHITE)
    assert mate["kind"] == "mate" and mate["value"] == -3 and mate["bound"] == "exact"


def test_immediate_attacks_are_verified_and_pinned_movers_abstain():
    board = chess.Board()
    for move in ("e2e4", "e7e5", "g1f3", "b8c6"):
        board.push_uci(move)
    facts = app.move_facts(board, chess.Move.from_uci("f1b5"))
    attack = next(fact for fact in facts if fact["kind"] == "attack")
    assert attack["squares"] == ["b5", "c6"] and "black knight" in attack["text"]
    assert "does not establish" in attack["qualification"]
    pinned = chess.Board("4r2k/8/8/8/8/q7/4R3/4K3 w - - 0 1")
    facts = app.move_facts(pinned, chess.Move.from_uci("e2e3"))
    assert not any(fact["kind"] == "attack" for fact in facts)


def test_automatic_draw_overrides_check_but_checkmate_takes_priority():
    board = chess.Board("7k/8/8/8/8/8/R7/K7 w - - 149 76")
    facts = app.move_facts(board, chess.Move.from_uci("a2a8"))
    assert any(fact["kind"] == "draw" and "75-move rule" in fact["text"] for fact in facts)
    assert not any(fact["kind"] == "check" for fact in facts)
    board = chess.Board("6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 149 76")
    facts = app.move_facts(board, chess.Move.from_uci("g5d8"))
    assert any(fact["kind"] == "checkmate" for fact in facts)
    assert not any(fact["kind"] == "draw" for fact in facts)


def test_fivefold_history_is_preserved_in_pgn_played_line_model_and_cache():
    cycle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    board, _, _, _ = app.parse_position({"fen": chess.STARTING_FEN, "moves": cycle*4})
    assert board.is_fivefold_repetition()
    assert app.board_record(board)["terminal"] is True
    assert app.board_record(board)["termination"] == "fivefold_repetition"
    assert app.board_record(board)["legal_moves"] == []
    pgn = "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 5. Nf3 Nf6 6. Ng1 Ng8 7. Nf3 Nf6 8. Ng1 Ng8 1/2-1/2"
    imported, _, _, _ = app.parse_position({"pgn": pgn})
    assert imported.is_fivefold_repetition()
    model = app.Classifier(Path("test-placeholder"))
    model.rank = lambda _: pytest.fail("automatic draw must not call model")
    assert model.rollout(imported)["stop_reason"] == "game_over"
    engine = app.Engine(Path("does-not-exist"))
    assert engine.analyze(imported)["status"] == "terminal"
    class RecordingEngine:
        calls = []
        def analyze(self, candidate):
            self.calls.append(candidate.is_fivefold_repetition())
            return {"status": "terminal" if candidate.is_game_over() else "test", "alternatives": []}
    engine = RecordingEngine()
    tutor = app.Tutor(engine, app.Classifier())
    tutor.analyze({"fen": imported.fen(), "model": False})
    tutor.analyze({"fen": chess.STARTING_FEN, "moves": cycle*4, "model": False})
    assert engine.calls == [False, True]
    with pytest.raises(app.InputError, match="already over"):
        app.parse_position({"fen": chess.STARTING_FEN, "moves": cycle*4 + ["e2e4"]})
    with pytest.raises(app.InputError, match="automatic game-ending"):
        app.parse_position({"pgn": pgn.replace("1/2-1/2", "9. e4 *")})


def ranking(raw="e2e4", legal=True, filtered="e2e4"):
    return {"raw_choice_uci": raw, "raw_choice_is_legal": legal, "legal_choice_uci": filtered,
            "raw_topk": [{"move_uci": raw, "logit": 1.2, "legal": legal}],
            "legal_topk": [{"move_uci": filtered, "logit": 1.1, "legal": True}]}


def test_illegal_raw_model_choice_stops_without_rule_or_engine_replacement():
    model = app.Classifier(Path("explicit-test-placeholder"))
    calls = []
    model.rank = lambda fen: (calls.append(fen) or ranking("a1a8", False, "e2e4"))
    result = model.rollout(chess.Board())
    assert len(calls) == 1 and calls[0] == chess.STARTING_FEN
    assert result["stop_reason"] == "raw_illegal_move"
    assert result["interventions"] == 0
    assert result["predictions"][0]["raw_choice_uci"] == "a1a8"
    assert result["predictions"][0]["accepted"] is False


def test_model_rollout_receives_only_each_current_fen():
    model = app.Classifier(Path("explicit-test-placeholder"))
    calls, moves = [], iter(["e2e4", "e7e5", "g1f3"])
    def rank(fen):
        calls.append(fen)
        move = next(moves)
        return ranking(move, True, move)
    model.rank = rank
    result = model.rollout(chess.Board())
    assert result["stop_reason"] == "three_plies_complete"
    assert len(calls) == 3
    assert calls[1] == result["predictions"][0]["fen_after"]
    assert calls[2] == result["predictions"][1]["fen_after"]
    assert result["predictions"][2]["san"] == "Nf3"


def test_partial_model_failure_retains_prior_predictions():
    model = app.Classifier(Path("explicit-test-placeholder"))
    def rank(fen):
        if fen == chess.STARTING_FEN:
            return ranking()
        raise RuntimeError("test inference failure")
    model.rank = rank
    result = model.rollout(chess.Board())
    assert result["status"] == "error" and len(result["predictions"]) == 1
    assert result["stop_reason"] == "model_error"


class StubEngine:
    path = app.DEFAULT_ENGINE
    def analyze(self, board):
        moves = ["e2e4", "e7e5", "g1f3"]
        replay, pv = board.copy(), []
        for text in moves:
            move = chess.Move.from_uci(text)
            san = replay.san(move)
            replay.push(move)
            pv.append({"uci": text, "san": san, "fen": replay.fen()})
        return {"status": "ok", "name": "test fixture", "alternatives": [{"move_uci": moves[0], "pv": pv}]}


def test_model_runs_before_engine_and_divergence_never_matches_later_plies():
    events = []
    class Model:
        path = Path("test-placeholder")
        def rollout(self, board):
            events.append("model")
            return {"status": "ok", "predictions": [dict(ranking("d2d4", True, "d2d4"), accepted=True), dict(ranking("e7e5", True, "e7e5"), accepted=True)], "interventions": 0}
    class Engine(StubEngine):
        def analyze(self, board):
            events.append("engine")
            return super().analyze(board)
    result = app.Tutor(Engine(), Model()).analyze({"fen": chess.STARTING_FEN})
    assert events == ["model", "engine"]
    assert result["model"]["root_raw_matches_engine"] is False
    assert result["model"]["exact_root_pv_prefix_plies"] == 0
    assert "No per-ply teacher search" in result["model"]["comparison_scope"]


def test_transient_errors_are_retained_but_not_cached():
    class RecoveringEngine(StubEngine):
        calls = 0
        def analyze(self, board):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient engine failure")
            return super().analyze(board)
    engine = RecoveringEngine()
    tutor = app.Tutor(engine, app.Classifier())
    assert tutor.analyze({"fen": chess.STARTING_FEN})["engine"]["status"] == "error"
    assert tutor.analyze({"fen": chess.STARTING_FEN})["engine"]["status"] == "ok"
    assert engine.calls == 2
    class RecoveringModel:
        path = Path("test-placeholder")
        calls = 0
        def rollout(self, board):
            self.calls += 1
            return {"status": "error" if self.calls == 1 else "ok", "predictions": [], "interventions": 0}
    model = RecoveringModel()
    tutor = app.Tutor(StubEngine(), model)
    assert tutor.analyze({"fen": chess.STARTING_FEN})["model"]["status"] == "error"
    assert tutor.analyze({"fen": chess.STARTING_FEN})["model"]["status"] == "ok"
    assert model.calls == 2


def test_terminal_board_skips_engine_and_model_inference():
    board = chess.Board("7k/6Q1/5K2/8/8/8/8/8 b - - 0 1")
    assert board.is_checkmate()
    assert app.Engine(Path("does-not-exist")).analyze(board)["status"] == "terminal"
    model = app.Classifier(Path("test-placeholder"))
    model.rank = lambda _: pytest.fail("terminal board must not call model")
    assert model.rollout(board)["stop_reason"] == "game_over"
    assert app.board_record(board)["terminal"] is True


@pytest.fixture
def local_server():
    tutor = app.Tutor(StubEngine(), app.Classifier())
    server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.handler_for(tutor))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_http_validation_origin_host_and_static_allowlist(local_server):
    url = f"http://127.0.0.1:{local_server.server_port}"
    with urlopen(url + "/api/health") as response:
        assert json.load(response)["schema_version"] == app.SCHEMA
    with urlopen(url + "/") as response:
        assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
        assert b"Chess study" in response.read()
    for suffix in ["/server.py", "/../../AGENTS.md", "/%2e%2e/server.py"]:
        with pytest.raises(HTTPError) as exc:
            urlopen(url + suffix)
        assert exc.value.code == 404
    for headers in [{"Origin": "https://example.com"}, {"Host": "evil.example"}]:
        request = Request(url+"/api/analyze", data=b"{}", headers={"Content-Type": "application/json", **headers})
        with pytest.raises(HTTPError) as exc:
            urlopen(request)
        assert exc.value.code == 403
    request = Request(url+"/api/analyze", data=b"{}", headers={"Content-Type": "text/plain"})
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 415


def test_http_real_analysis_contract_and_invalid_move(local_server):
    url = f"http://127.0.0.1:{local_server.server_port}/api/analyze"
    request = Request(url, data=json.dumps({"fen": chess.STARTING_FEN, "model": False}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        data = json.load(response)
    assert data["board"]["turn"] == "white" and len(data["board"]["legal_moves"]) == 20
    assert data["model"]["status"] == "disabled"
    request = Request(url, data=json.dumps({"fen": chess.STARTING_FEN, "moves": ["e2e5"]}).encode(), headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 400


@pytest.mark.skipif(not app.DEFAULT_ENGINE.is_file(), reason="Local engine binary is not installed in a portable checkout")
def test_real_engine_legally_replays_every_returned_variation():
    board = chess.Board("6k1/5ppp/8/6Q1/8/8/5PPP/6K1 w - - 0 1")
    result = app.Engine(nodes=5_000).analyze(board)
    assert "Stockfish" in result["name"]
    assert result["budget"]["threads"] <= 2
    assert result["alternatives"]
    for row in result["alternatives"]:
        replay = board.copy()
        assert row["score"]["type"] == "engine_observation"
        assert row["score"]["perspective"] == "white"
        assert row["score"]["bound"] in {"exact", "lower", "upper"}
        for step in row["pv"]:
            move = chess.Move.from_uci(step["uci"])
            assert move in replay.legal_moves
            assert replay.san(move) == step["san"]
            replay.push(move)
            assert replay.fen() == step["fen"]
        assert all(fact["type"] == "board_fact" for fact in row["facts"])
