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


# Async controller fixtures run only a short standard-library child process.
import copy
import sys
import time
from types import SimpleNamespace
import coaching_jobs as jobs_module
import queen_runtime as queen_runtime

FIXTURE_WORKER = '"""CPU-only interface fixture. Never imports a model, engine or GPU library."""\nimport argparse\nimport json\nfrom pathlib import Path\nimport time\n\n\ndef main():\n    parser=argparse.ArgumentParser()\n    for name in (\'input\',\'out\',\'cancel\',\'receipt\'):parser.add_argument(\'--\'+name,type=Path,required=True)\n    parser.add_argument(\'--scenario\',required=True);parser.add_argument(\'--delay\',type=float,default=.25)\n    args=parser.parse_args()\n    if args.scenario==\'busy\':args.receipt.write_text(\'{"status":"busy","child_pid":null}\');return\n    args.receipt.write_text(\'{"status":"running"}\')\n    finish=time.monotonic()+min(5,max(0,args.delay))\n    while time.monotonic()<finish:\n        if args.cancel.exists():\n            args.out.write_text(\'{"status":"failed","error":"owned cancellation","raw_text":"CPU interface fixture stopped."}\')\n            args.receipt.write_text(\'{"status":"failed","child_exited_before_lease_release":true}\');return\n        time.sleep(.02)\n    packet=json.loads(args.input.read_text())\n    result={\'status\':\'partial\' if args.scenario==\'partial\' else \'failed\' if args.scenario==\'resource\' else \'completed\',\n        \'finish_reason\':\'token_limit\' if args.scenario==\'partial\' else \'error\' if args.scenario==\'resource\' else \'eos\',\n        \'input\':packet,\'model_id\':\'CPU interface fixture; no model inference\',\n        \'raw_text\':\'ANALYSIS: Interface fixture only. <script>This is inert text.</script>\',\n        \'decoded_text\':\'ANALYSIS: This is a CPU interface fixture, not a model response. It tests the reading layout and status behavior.\',\n        \'settings\':{\'backend\':\'CPU interface fixture\',\'generation_mode\':\'fixture\',\'precision_profile\':\'fixture\',\'quantization\':\'fixture\'},\n        \'parsed\':{\'raw_choice_uci\':\'e2e5\' if args.scenario==\'illegal\' else None,\'raw_choice_is_legal\':False,\n            \'accepted_move_uci\':None,\'move_rejection\':\'illegal_move\' if args.scenario==\'illegal\' else \'missing_or_ambiguous_best_move\',\n            \'critical_line\':{\'legal_prefix_plies\':0,\'steps\':[],\'failure\':{\'reason\':\'fixture\'}}},\n        \'generation_timing\':{\'decode_seconds\':args.delay,\'tokens_per_decode_second\':0},\'generated_tokens\':[]}\n    if args.scenario==\'resource\':result[\'error\']=\'RuntimeError: resource reserve: commit_headroom_bytes_below_reserve\'\n    args.out.write_text(json.dumps(result),encoding=\'utf-8\')\n    args.receipt.write_text(\'{"status":"completed","child_exited_before_lease_release":true}\')\n\n\nif __name__==\'__main__\':main()\n'


class UIFixtureRunner:
    fixture=True
    label='CPU interface fixture'
    def __init__(self,scenario='completed',delay=.25):
        self.scenario=scenario;self.delay=delay;self.maximum_seconds=5
    def verify(self):pass
    def command(self,job):
        script=job['input'].with_name('cpu-fixture.py');script.write_text(FIXTURE_WORKER,encoding='utf-8')
        return [sys.executable,str(script),'--scenario',self.scenario,'--delay',str(self.delay),
            '--input',str(job['input']),'--out',str(job['out']),'--cancel',str(job['cancel']),
            '--receipt',str(job['worker'])]


class CoachEngineFixture:
    path=Path(__file__)
    def analyze(self,board):
        return {'status':'test_fixture','alternatives':[]}


server=SimpleNamespace(app=app,coach_packet=app.coach_packet,handler_for=app.handler_for,
    EngineFixture=CoachEngineFixture,ThreadingHTTPServer=app.ThreadingHTTPServer)

def payload():return {'position':{'fen':chess.STARTING_FEN,'moves':['e2e4','e7e5']}}


def completed(jobs,identifier):
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        result=jobs.get(identifier)
        if result['status'] not in jobs_module.ACTIVE:return result
        time.sleep(.02)
    pytest.fail('CPU fixture did not reach a terminal state.')


def test_packet_has_only_current_fen_prior_history_and_explicit_selected_move():
    packet,context,terminal=server.coach_packet({**payload(),'selected_uci':'g1f3','selected_move_origin':'stockfish_selection'})
    assert set(packet)=={'fen','history','selected_uci'} and len(packet['history'])==2
    board=chess.Board();assert packet['history'][0]==board.fen();board.push_uci('e2e4')
    assert packet['history'][1]==board.fen();board.push_uci('e7e5');assert packet['fen']==board.fen()
    assert context['position']==payload()['position'] and context['selected_move_origin']=='stockfish_selection'
    assert terminal is False


@pytest.mark.parametrize('bad',[
    {**payload(),'pv':['g1f3']}, {'position':{'fen':chess.STARTING_FEN,'engine':{}}},
    {'position':{'pgn':'1.e4 e5 *','ply':0}}, {**payload(),'selected_uci':'e2e5'},
    {**payload(),'selected_move_origin':'stockfish_selection'},
    {**payload(),'selected_uci':'g1f3','selected_move_origin':[]},
    {'position':{'fen':chess.STARTING_FEN,'moves':['0000']}},
])
def test_rejects_future_evaluator_unknown_or_illegal_data_before_process_launch(tmp_path,bad):
    jobs=jobs_module.CoachingJobs(tmp_path/'jobs',server.coach_packet,UIFixtureRunner())
    with pytest.raises((ValueError,server.app.InputError)):jobs.start(bad)
    assert not (tmp_path/'jobs').exists()


@pytest.mark.parametrize('scenario,status',[('completed','completed'),('partial','partial'),('illegal','completed'),('busy','busy')])
def test_async_mock_outputs_preserve_actual_mode_raw_failure_and_busy(tmp_path,scenario,status):
    jobs=jobs_module.CoachingJobs(tmp_path,server.coach_packet,UIFixtureRunner(scenario))
    first=jobs.start(payload());assert first['status']=='starting'
    result=completed(jobs,first['request_id']);assert result['status']==status and result['fixture'] is True
    assert not any(key in result for key in ('process','input','out','worker','log'))
    if status=='busy':assert result['result'] is None
    else:
        assert '<script>' in result['result']['raw_text']
        assert result['result']['settings']['generation_mode']=='fixture'
        if scenario=='illegal':assert result['result']['parsed']['accepted_move_uci'] is None
    jobs.close()


def test_one_owned_request_cancel_waits_for_process_exit_and_does_not_cancel_unknown_ids(tmp_path):
    jobs=jobs_module.CoachingJobs(tmp_path,server.coach_packet,UIFixtureRunner(delay=2))
    first=jobs.start(payload())
    with pytest.raises(jobs_module.JobBusy):jobs.start(payload())
    with pytest.raises(KeyError):jobs.cancel('0'*32)
    deadline=time.monotonic()+3
    while jobs.get(first['request_id'])['status']=='starting' and time.monotonic()<deadline:time.sleep(.02)
    assert jobs.cancel(first['request_id'])['status']=='stopping'
    result=completed(jobs,first['request_id']);assert result['status']=='cancelled'
    assert jobs.jobs[first['request_id']]['process'].poll() is not None
    second=jobs.start(payload());assert second['request_id']!=first['request_id']
    jobs.cancel(second['request_id']);completed(jobs,second['request_id']);jobs.close()


def test_resource_failure_retains_partial_raw_and_blocks_automatic_or_manual_relaunch(tmp_path):
    jobs=jobs_module.CoachingJobs(tmp_path,server.coach_packet,UIFixtureRunner('resource'))
    first=jobs.start(payload());result=completed(jobs,first['request_id'])
    assert result['status']=='failed' and result['result']['raw_text']
    assert jobs.health()['status']=='blocked'
    with pytest.raises(jobs_module.Unavailable):jobs.start(payload())
    assert len(list(tmp_path.iterdir()))==1


def test_automatic_fivefold_terminal_never_starts_fixture_process(tmp_path):
    jobs=jobs_module.CoachingJobs(tmp_path,server.coach_packet,UIFixtureRunner())
    result=jobs.start({'position':{'fen':chess.STARTING_FEN,'moves':['g1f3','g8f6','f3g1','f6g8']*4}})
    assert result['status']=='terminal' and result['result']['finish_reason']=='game_over'
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_worker_record_waits_for_partial_json_but_rejects_nonfinite_or_wrong_shape(tmp_path):
    path=tmp_path/'response.json';path.write_text('{"status":')
    assert jobs_module.read_record(path) is None
    path.write_text('{"value":NaN}')
    with pytest.raises(ValueError):jobs_module.read_record(path)
    path.write_text('[]')
    with pytest.raises(ValueError):jobs_module.read_record(path)


def qualified_response_fixture():
    runner=queen_runtime.QueenRunner.__new__(queen_runtime.QueenRunner)
    names=('adapter','kernel_protocol','kernel_receipt','base_adapter','asset_manifest','source_manifest','parity_protocol','parity_receipt')
    runner.plan={'candidate_id':'fixture-only','bindings':{name:{'sha256':str(i)*64} for i,name in enumerate(names,1)}}
    bindings=runner.plan['bindings'];packet={'fen':chess.STARTING_FEN,'history':[]}
    response={'status':'completed','raw_text':'<script>retained raw fixture</script>','decoded_text':'Unverified fixture prose.',
        'input':packet,'candidate_id':'fixture-only','adapter_sha256':bindings['adapter']['sha256'],
        'nf4_protocol_sha256':bindings['kernel_protocol']['sha256'],
        'diagnostic_receipt_sha256':bindings['kernel_receipt']['sha256'],
        'base_adapter_sha256':bindings['base_adapter']['sha256'],
        'asset_manifest_sha256':bindings['asset_manifest']['sha256'],
        'source_manifest_sha256':bindings['source_manifest']['sha256'],
        'settings':{**queen_runtime.EXPECTED_SETTINGS,'use_kv_cache':False,'backend':'CPU metadata fixture'},
        'no_forward_input_audit':{'passed':True,'engine_evaluation_or_pv_input':False,'selected_move_supplied':False},
        'quantization':{'status':'loaded_and_verified','actual_decoder_inventory':{'linear4bit_count':252}},
        'resource_policy':dict(queen_runtime.RESOURCE_FLOORS)}
    return runner,packet,response


@pytest.mark.parametrize('field,value',[
    ('candidate_id','other-model'),('nf4_protocol_sha256','wrong'),
    ('input',{'fen':'another position'}),('settings',{'generation_mode':'cached'}),
    ('no_forward_input_audit',{'passed':True,'engine_evaluation_or_pv_input':True}),
    ('quantization',{'status':'not_loaded'}),('resource_policy',{}),
])
def test_unqualified_worker_output_keeps_raw_but_never_receives_verified_ui_provenance(tmp_path,field,value):
    runner,packet,response=qualified_response_fixture();response[field]=value
    source=tmp_path/'input.json';source.write_text(json.dumps(packet))
    decorated=runner.decorate_result({'input':source},response)
    assert decorated['status']=='failed' and decorated['ui_validation_error']
    assert decorated['raw_text']==response['raw_text']
    assert decorated['execution']['canonical_provenance']['response_binding_verified'] is False


def test_selected_move_origin_stays_metadata_and_verified_execution_is_a_separate_view(tmp_path):
    runner,packet,response=qualified_response_fixture()
    packet['selected_uci']='e2e4';response['no_forward_input_audit']['selected_move_supplied']=True
    source=tmp_path/'input.json';source.write_text(json.dumps(packet))
    before=copy.deepcopy(response);decorated=runner.decorate_result({'input':source},response)
    assert response==before and 'execution' not in response
    assert decorated['execution']['canonical_provenance']['response_binding_verified'] is True
    assert decorated['execution']['generation_mode']=='no_cache'
    assert 'selected_move_origin' not in packet


def test_changed_qualification_source_fails_before_any_process_or_candidate_import(tmp_path,monkeypatch):
    child=tmp_path/'child.py';child.write_text('raise AssertionError("must not execute")')
    plan={'status':'approved_for_authored_ui','bindings':{'adapter':{'path':'child.py','sha256':jobs_module.sha(child)}}}
    qualification=tmp_path/'qualification.json';qualification.write_text(json.dumps(plan))
    monkeypatch.setattr(queen_runtime,'QUALIFICATION_SHA256',jobs_module.sha(qualification))
    child.write_text('changed after qualification')
    runner=queen_runtime.QueenRunner.__new__(queen_runtime.QueenRunner)
    runner.repo=tmp_path;runner.qualification_path=qualification
    monkeypatch.setattr(jobs_module.subprocess,'Popen',lambda *a,**k:pytest.fail('No process may start.'))
    with pytest.raises(jobs_module.Unavailable,match='qualified runtime file changed'):runner.verify()


def test_canonical_parity_requires_each_finite_scope_and_both_frozen_prefixes():
    plan={'thresholds':{'max_absolute_error':.01,'mean_absolute_error':.001,'minimum_cosine_similarity':.9999}}
    value={'finite':True,'top1_equal':True,'max_absolute_error':0.,'mean_absolute_error':0.,'cosine_similarity':1.}
    receipt={'status':'passed','thresholds':dict(plan['thresholds']),'comparisons':[
        {'kind':kind,**{scope:dict(value) for scope in ('all_logits','original_vocab_logits','added_vocab_logits')}}
        for kind in ('base_prompt','synthetic_vocabulary_suffix')]}
    assert queen_runtime.parity_passed(receipt,plan)
    receipt['comparisons'][1]['added_vocab_logits']['mean_absolute_error']=.002
    assert not queen_runtime.parity_passed(receipt,plan)
    receipt['comparisons'][1]['added_vocab_logits']['mean_absolute_error']=float('nan')
    assert not queen_runtime.parity_passed(receipt,plan)
    receipt['comparisons'].pop()
    assert not queen_runtime.parity_passed(receipt,plan)


def test_http_origin_allowlist_and_async_endpoint_with_cpu_fixture(tmp_path):
    jobs=jobs_module.CoachingJobs(tmp_path,server.coach_packet,UIFixtureRunner())
    tutor=server.app.Tutor(server.EngineFixture(),server.app.Classifier(None))
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.handler_for(tutor,jobs))
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{http.server_port}'
    def request(path,body=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urlopen(Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=4)
    try:
        with pytest.raises(HTTPError) as error:request('/api/coach',payload(),'https://example.com')
        assert error.value.code==403
        with pytest.raises(HTTPError) as error:request('/data/private/model.safetensors')
        assert error.value.code==404
        response=request('/api/coach',payload());assert response.status==202
        job=json.load(response);result=completed(jobs,job['request_id'])
        response=request(job['poll_url']);assert json.load(response)['status']==result['status']=='completed'
        assert request('/coaching.js').headers['X-Content-Type-Options']=='nosniff'
    finally:jobs.close();http.shutdown();http.server_close();thread.join(timeout=3)


def test_actual_frontend_selected_move_matching_and_exact_saved_view_restore_without_fetch():
    import shutil
    import subprocess
    node=shutil.which('node')
    if node is None:pytest.skip('Node is unavailable for the bounded frontend regression.')
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const app=fs.readFileSync(process.argv[1],'utf8'),coach=fs.readFileSync(process.argv[2],'utf8');
const matching=coach.slice(coach.indexOf('function coachingContextMatches('),coach.indexOf('(() =>'));
const dom={'position-label':{textContent:'SOURCE POSITION'},'use-model':{checked:true},promotion:{hidden:false},'input-error':{hidden:false}};
const state={structuredClone,$:id=>dom[id],result:{board:{fen:'original'},engine:{alternatives:[{move_uci:'e2e4'},{move_uci:'d2d4'}]}},
  timeline:[{fen:'root',uci:null},{fen:'after',uci:'e2e4'}],index:1,candidate:1,busy:false,preview:null,selection:'e2',pendingPromotion:'a7a8',
  render(){},navigation(){},notice(){}};
vm.createContext(state);vm.runInContext(matching,state);
const position={fen:'root',moves:['e2e4']},study={position,selectedUci:'d2d4',preview:false};
const context={position,kind:'selected_move',selected_uci:'d2d4'};
assert.equal(state.coachingContextMatches(context,study),true);
assert.equal(state.coachingContextMatches(context,{...study,selectedUci:'e2e4'}),false);
assert.equal(state.coachingContextMatches(context,{...study,preview:true}),false);
assert.equal(state.coachingContextMatches(context,{...study,position:{fen:'root',moves:[]}}),false);
assert.equal(state.coachingContextMatches({...context,kind:'position'},{...study,selectedUci:'e2e4'}),true);
const restore=app.slice(app.indexOf('function captureCoachingStudy('),app.indexOf("$('flip').addEventListener"));
vm.runInContext(restore,state);const saved=state.captureCoachingStudy();
state.result.board.fen='later-board';state.result.engine.alternatives=[];state.candidate=0;state.timeline=[];
state.restoreCoachingStudy(saved);
assert.equal(state.result.board.fen,'original');assert.equal(state.candidate,1);
assert.equal(state.result.engine.alternatives[state.candidate].move_uci,'d2d4');assert.equal(state.timeline.length,2);
assert.equal(state.pendingPromotion,null);assert.equal(dom.promotion.hidden,true);
assert.equal(typeof state.fetch,'undefined');
'''
    result=subprocess.run([node,'-e',script,str(app.STATIC/'app.js'),str(app.STATIC/'coaching.js')],
        capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stdout+result.stderr


