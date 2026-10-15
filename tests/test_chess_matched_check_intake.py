"""Synthetic intake software checks; never select from the real Parquet shard."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import chess
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import chess_matched_check_intake as intake


def synthetic_rows(count=32):
    squares = [sq for sq in range(32) if sq != chess.C1]
    for index in range(count):
        board = chess.Board.empty()
        board.set_piece_at(squares[index % len(squares)],chess.Piece(chess.KING,chess.WHITE))
        board.set_piece_at(chess.C1,chess.Piece(chess.ROOK,chess.WHITE))
        board.set_piece_at(chess.H8,chess.Piece(chess.KING,chess.BLACK))
        # A thirty-second distinct fixture uses a fifth-rank king.
        if index == 31:
            board.remove_piece_at(squares[0])
            board.set_piece_at(chess.A5,chess.Piece(chess.KING,chess.WHITE))
        board.turn = chess.BLACK
        assert board.is_valid()
        yield ({"source_ordinal":index,"row_group":0,"row_in_group":index},
               {"PuzzleId":"P"+str(index),"GameId":"G"+format(index,"07d"),
                "FEN":board.fen(),"Moves":"h8g8 NEVER_PARSE_THIS_ANSWER_TAIL"})


def preboard(row):
    board = chess.Board(row["FEN"])
    board.push_uci("h8g8")
    return board


def independent_digest(domain,payload):
    return hashlib.sha256(domain.encode("ascii")+b"\x0a"+
        json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def test_manual_pair_set_and_hash_ranking():
    _,row = next(synthetic_rows(1))
    board = preboard(row)
    pairs,_ = intake.candidate_pairs(board,row["GameId"],row["PuzzleId"],4082032,set(),intake.prior.board_key(row["FEN"]))
    checks = {"c1g1","c1c8"}
    quiet = {"c1b1","c1d1","c1e1","c1f1","c1h1",*("c1c"+str(r) for r in range(2,8))}
    expected = [sorted((c,q)) for c in checks for q in quiet]
    assert len(pairs)==22
    assert {tuple(p["moves"]) for p in pairs}=={tuple(p) for p in expected}
    ranked = sorted(expected,key=lambda moves:(independent_digest("matched-check-pair-v1",{
        "seed":4082032,"game_id":row["GameId"],"puzzle_id":row["PuzzleId"],
        "fen":board.fen(),"moves":moves}),*moves))
    assert [p["moves"] for p in pairs]==ranked


def test_poisoned_answer_tail_and_annotations_have_no_role():
    rows = list(synthetic_rows(2))
    baseline = intake.select_rows(iter(rows),set(),set(),count=2)
    poisoned = [(loc,{**row,"Moves":"h8g8 false gives_check true [MODEL ANSWER]", "Rating":1,
                       "Themes":["check"],"OpeningTags":["answer"]}) for loc,row in rows]
    assert intake.select_rows(iter(poisoned),set(),set(),count=2)==baseline
    for model_row in baseline["inputs"]:
        assert set(model_row)=={"case_id","fen","selected_uci"}
        prompt=intake.core.build_prompt(model_row,"fen_uci_piece_map")
        assert model_row["case_id"] not in prompt
        assert "MODEL ANSWER" not in prompt


def test_game_suffix_identity_and_source_order_precedence():
    rows=list(synthetic_rows(4)); events=[]
    rows[0]=(rows[0][0],{**rows[0][1],"GameId":"not-an-id"})
    rows[1]=(rows[1][0],{**rows[1][1],"GameId":rows[1][1]["GameId"]+"/black#38"})
    out=intake.select_rows(iter(rows),{"G0000002"},set(),count=2,trace=events.append)
    assert [p["source_ordinal"] for p in out["pairs"]]==[1,3]
    assert out["pairs"][0]["game_id"]=="G0000001"
    assert out["pairs"][0]["native_game_id"].endswith("/black#38")
    assert [e["outcome"] for e in events]==["invalid","accepted","known_or_new_game_overlap","accepted"]


@pytest.mark.parametrize("role",["source","setup_after"])
def test_both_source_board_roles_excluded(role):
    rows=list(synthetic_rows(2)); row=rows[0][1]
    fen=row["FEN"] if role=="source" else preboard(row).fen()
    # Clocks never evade the four-field board-key exclusion.
    fen=" ".join(fen.split()[:4])+" 77 99"
    out=intake.select_rows(iter(rows),set(),{intake.prior.board_key(fen)},count=1)
    assert out["pairs"][0]["source_ordinal"]==1
    assert out["terminal_outcomes"]["source_role_board_overlap"]==1


def test_each_successor_is_excluded_before_pair_rank():
    _,row=next(synthetic_rows(1)); board=preboard(row)
    forbidden=board.copy();forbidden.push_uci("c1g1")
    pairs,_=intake.candidate_pairs(board,row["GameId"],row["PuzzleId"],4082032,
        {intake.prior.board_key(forbidden.fen())},intake.prior.board_key(row["FEN"]))
    assert len(pairs)==11
    assert all("c1g1" not in p["moves"] for p in pairs)
    assert all("c1c8" in p["moves"] for p in pairs)


@pytest.mark.parametrize("fen,forbidden",[
    ("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1",{"e1g1","e1c1"}),
    ("7k/8/8/3pP3/8/8/8/K1R5 w - d6 0 1",{"e5d6"}),
    ("7k/P7/8/8/8/8/8/K1R5 w - - 0 1",{"a7a8q","a7a8r","a7a8b","a7a8n"}),
])
def test_special_moves_never_enter_pairs(fen,forbidden):
    board=chess.Board(fen)
    assert any(uci in {m.uci() for m in board.legal_moves} for uci in forbidden)
    pairs,filters=intake.candidate_pairs(board,"G0000000","P",4082032,set(),"not-a-board-key")
    assert filters["special_move"]>0
    assert all(not (set(p["moves"]) & forbidden) for p in pairs)


def test_cap_does_not_request_an_extra_row_or_relax_matching():
    rows=list(synthetic_rows(2)); consumed=[]
    def source():
        for item in rows:
            consumed.append(item[0]["source_ordinal"])
            yield item
        raise AssertionError("source read beyond fixed cap")
    with pytest.raises(ValueError,match="shortfall"):
        intake.select_rows(source(),{rows[0][1]["GameId"],rows[1][1]["GameId"]},set(),count=1,cap=2)
    assert consumed==[0,1]


def test_duplicate_accepted_game_is_rejected_and_new_puzzle_collision_is_fatal():
    rows=list(synthetic_rows(3))
    duplicate=(rows[1][0],{**rows[1][1],"GameId":rows[0][1]["GameId"]})
    out=intake.select_rows(iter([rows[0],duplicate,rows[2]]),set(),set(),count=2)
    assert out["terminal_outcomes"]["known_or_new_game_overlap"]==1
    collision=(rows[1][0],{**rows[1][1],"PuzzleId":rows[0][1]["PuzzleId"]})
    with pytest.raises(ValueError,match="puzzle identity"):
        intake.select_rows(iter([rows[0],collision]),set(),set(),count=2)


def test_full_synthetic_denominator_order_and_disjoint_roles():
    out=intake.select_rows(synthetic_rows(),set(),set())
    assert len(out["pairs"])==32 and len(out["inputs"])==len(out["labels"])==64
    assert sum(row["expected"]["gives_check"] for row in out["labels"])==32
    assert [r["case_id"] for r in out["inputs"]]==[r["case_id"] for r in out["labels"]]
    assert [r["case_id"] for r in out["inputs"]]==[r["case_id"] for r in sorted(out["inputs"],
        key=lambda r:(independent_digest("matched-check-order-v1",{"seed":4082032,"case_id":r["case_id"]}),r["case_id"]))]
    keys=set()
    for pair in out["pairs"]:
        roles={intake.prior.board_key(pair["source_before_fen"]),intake.prior.board_key(pair["fen"]),*pair["successor_keys"]}
        assert len(roles)==4 and not keys.intersection(roles)
        keys.update(roles)


def test_oracle_disagreement_is_fatal(monkeypatch):
    monkeypatch.setattr(intake.core,"independent_facts",lambda *_:{"wrong":True})
    with pytest.raises(ValueError,match="oracles disagree"):
        intake.select_rows(synthetic_rows(1),set(),set(),count=1)


@pytest.mark.parametrize("row",[
    {"GameId":"G0000000","PuzzleId":"P0","FEN":"bad","Moves":"h8g8"},
    {"GameId":"G0000000","PuzzleId":"bad/id","FEN":chess.STARTING_FEN,"Moves":"e2e4"},
    {"GameId":"G0000000","PuzzleId":"P0","FEN":chess.STARTING_FEN,"Moves":"e7e5"},
    {"GameId":"G0000000","PuzzleId":"P0","FEN":chess.STARTING_FEN,"Moves":None},
])
def test_invalid_source_fields_are_rejected_without_answer_recovery(row):
    events=[]
    with pytest.raises(ValueError,match="shortfall"):
        intake.select_rows(iter([({"source_ordinal":0},row)]),set(),set(),count=1,trace=events.append)
    assert events==[{"source_ordinal":0,"outcome":"invalid"}]


def test_fact_roles_include_supplied_successor_and_validate_setup():
    _,source=next(synthetic_rows(1)); board=preboard(source)
    row={"game_id":source["GameId"],"source_before_fen":source["FEN"],"setup_uci":"h8g8",
         "fen":board.fen(),"selected_uci":"c1g1"}
    games,boards=set(),set();intake.add_fact_roles(row,games,boards)
    board.push_uci("c1g1")
    assert games=={"G0000000"} and len(boards)==3
    assert intake.prior.board_key(board.fen()) in boards
    with pytest.raises(ValueError,match="illegal retained fact setup"):
        intake.add_fact_roles({**row,"setup_uci":"h8h1"},set(),set())


@pytest.mark.parametrize("name",["../escape","C:/escape","/escape","x\0y"])
def test_evidence_paths_cannot_escape(tmp_path,name):
    with pytest.raises(ValueError): intake.confined(tmp_path,name)


def test_protocol_bytes_and_freeze_are_pinned(tmp_path):
    repo=Path(__file__).resolve().parents[1]
    assert intake.load_protocol(repo,repo/intake.PROTOCOL)["fixed_scope"]["total_planned_responses"]==64
    target=tmp_path/"protocol.json";target.write_bytes((repo/intake.PROTOCOL).read_bytes()+b" ")
    with pytest.raises(ValueError,match="protocol changed"):intake.load_protocol(repo,target)


@pytest.fixture
def fake_freeze(tmp_path,monkeypatch):
    repo=tmp_path/"repo";repo.mkdir();workspace=tmp_path
    protocol=tmp_path/"protocol.json"
    original=Path(__file__).resolve().parents[1]/intake.PROTOCOL
    shutil.copyfile(original,protocol)
    monkeypatch.setattr(intake,"load_protocol",lambda *_:{"source":{"source_path":"synthetic-only.parquet"}})
    monkeypatch.setattr(intake,"verify_bindings",lambda *_:{"fixture":"fixed"})
    monkeypatch.setattr(intake,"reconstruct_exclusions",lambda *_:(set(),set()))
    def rows(path):
        assert path==repo/"synthetic-only.parquet"
        return synthetic_rows()
    monkeypatch.setattr(intake.prior,"parquet_rows",rows)
    return repo,workspace,protocol,repo/"cohort",intake.sha(Path(intake.__file__))


def test_create_only_full_freeze_uses_synthetic_rows_only(fake_freeze):
    repo,workspace,protocol,out,source=fake_freeze
    result=intake.freeze(repo,workspace,protocol,out,source)
    assert result["planned"]==64 and result["model_calls"]==0
    frozen=intake.read(out/"frozen-data.json")
    assert "frozen-data.json" not in frozen["files_sha256"]
    assert len(intake.read(out/"inputs.json")["rows"])==64
    for name,expected in frozen["files_sha256"].items(): assert intake.sha(out/name)==expected
    with pytest.raises(ValueError,match="existing"):intake.freeze(repo,workspace,protocol,out,source)


def test_failed_shortfall_keeps_trace_and_refuses_overwrite(fake_freeze,monkeypatch):
    repo,workspace,protocol,out,source=fake_freeze
    monkeypatch.setattr(intake.prior,"parquet_rows",lambda _ :synthetic_rows(1))
    with pytest.raises(ValueError,match="shortfall"):intake.freeze(repo,workspace,protocol,out,source)
    assert intake.read(out/"selection-failed.json")["model_calls"]==0
    assert len((out/"selection-trace.jsonl").read_text().splitlines())==1
    assert not (out/"frozen-data.json").exists()
    with pytest.raises(ValueError,match="existing"):intake.freeze(repo,workspace,protocol,out,source)


def test_postselection_binding_drift_fails_without_success_manifest(fake_freeze,monkeypatch):
    repo,workspace,protocol,out,source=fake_freeze
    calls=[]
    def binding(*_):
        calls.append(1);return {"fixture":len(calls)}
    monkeypatch.setattr(intake,"verify_bindings",binding)
    with pytest.raises(ValueError,match="changed during selection"):
        intake.freeze(repo,workspace,protocol,out,source)
    assert (out/"selection-failed.json").exists() and not (out/"frozen-data.json").exists()


def test_source_hash_mismatch_and_outside_output_are_rejected(fake_freeze):
    repo,workspace,protocol,out,source=fake_freeze
    with pytest.raises(ValueError,match="source changed"):
        intake.freeze(repo,workspace,protocol,out,"0"*64)
    assert not out.exists()
    with pytest.raises(ValueError,match="inside repository"):
        intake.freeze(repo,workspace,protocol,workspace/"outside",source)


def test_actual_CPU_identity_child_matches_owned_PID(tmp_path):
    executable,environment,identity=intake.launch_identity()
    marker=tmp_path/"identity.json"
    code="import os,sys,json,pathlib; pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid(),'prefix':sys.prefix,'executable':sys.executable}))"
    result=intake.run_owned([executable,"-c",code,str(marker)],tmp_path/"owned",environment=environment,seconds=5)
    actual=json.loads(marker.read_text())
    assert result["status"]=="PASS" and actual["pid"]==result["pid"]
    assert Path(actual["prefix"]).resolve()==Path(identity["venv_prefix"])
    assert Path(actual["executable"]).resolve()==Path(identity["venv_executable"])


def test_actual_CPU_timeout_stops_only_owned_child_and_retains_failure(tmp_path):
    executable,environment,_=intake.launch_identity()
    control=subprocess.Popen([executable,"-c","import time;time.sleep(15)"],env=environment,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        result=intake.run_owned([executable,"-c","import time;time.sleep(15)"],tmp_path/"timeout",
            environment=environment,seconds=.15,grace=.05)
        assert result["status"]=="FAILED" and result["timed_out"] and result["forced"]
        assert control.poll() is None
        assert intake.read(tmp_path/"timeout/receipt.json")["pid"]==result["pid"]
        assert (tmp_path/"timeout/cancel.json").exists()
        with pytest.raises(ValueError,match="existing"):
            intake.run_owned([executable,"-c","pass"],tmp_path/"timeout")
    finally:
        control.terminate();control.wait(timeout=5)


def test_expired_budget_never_launches_child(tmp_path,monkeypatch):
    monkeypatch.setattr(intake.subprocess,"Popen",lambda *_a,**_k:pytest.fail("expired launch"))
    with pytest.raises(intake.IntakeStopped,match="before launch"):
        intake.run_owned([sys.executable,"-c","pass"],tmp_path/"expired",seconds=.1,started=time.monotonic()-1)
    assert intake.read(tmp_path/"expired/receipt.json")["timed_out"]


def test_cancellation_stops_before_synthetic_row_consumption(tmp_path):
    marker=tmp_path/"cancel.json";marker.write_text("{}")
    with pytest.raises(intake.IntakeStopped): intake.check_stop(marker,time.monotonic()+10)
    with pytest.raises(intake.IntakeStopped): intake.check_stop(None,time.monotonic()-1)


def test_conflicting_child_python_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("PYTHONPATH","unreviewed")
    with pytest.raises(ValueError,match="conflicting"):intake.launch_identity()


def test_parent_preflight_failure_retained_without_starting_worker(tmp_path,monkeypatch):
    repo=tmp_path/"repo";repo.mkdir();out=repo/"cohort"
    monkeypatch.setattr(intake.subprocess,"Popen",lambda *_a,**_k:pytest.fail("preflight launched"))
    argv=["--repo",str(repo),"--workspace-root",str(tmp_path),"--out",str(out),
          "--expected-source-sha256","0"*64]
    assert intake.main(argv)==2
    assert not out.exists()
    failed=intake.read(repo/"cohort-supervision/preflight-failed.json")
    assert failed["stage"]=="parent_preflight" and not failed["worker_started"]
    with pytest.raises(ValueError,match="existing"):intake.main(argv)


def test_worker_parent_guard_fails_before_any_intake(tmp_path,monkeypatch):
    monkeypatch.setattr(intake,"freeze",lambda *_a,**_k:pytest.fail("unowned intake"))
    with pytest.raises(ValueError,match="parent identity"):
        intake.main(["--repo",str(tmp_path),"--workspace-root",str(tmp_path),"--out",str(tmp_path/"cohort"),
            "--expected-source-sha256","0"*64,"--worker","--parent-pid","0","--cancel",str(tmp_path/"cancel")])
