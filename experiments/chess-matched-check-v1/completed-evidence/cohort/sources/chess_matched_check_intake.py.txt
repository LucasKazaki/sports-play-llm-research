"""Create-only, known-history-disjoint matched-check intake; no learned calls.

The CLI owns one bounded CPU child. Merely importing this module reads no data.
Actual source intake requires the separately reviewed source hash on the CLI.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import chess
import chess_board_fact_core as core
import chess_fact_sft_intake as prior

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "experiments/chess-matched-check-v1/protocol.json"
PROTOCOL_SHA = "c9c22898e14772744e83c6e68f62bfef845cb3b6ba62f0e1c8005f6caf0f63dd"
FREEZE_SHA = "22278fc0fa502218ce121af5984fe92c384d41a40e7c0af0e9046b2b9fbabdef"
REGISTRY = "experiments/chess-matched-check-v1/archive/v2/known-history-exclusions-v2.json"
REGISTRY_SHA = "a11640f88970296a42f0a6d82f134fa4bca5b9f202b1eaa405cf586377f9bcfb"
PRIVATE = "data/private/gothamchess/constructed-middlegame-eval-v1"
FORBIDDEN_ENV = ("PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__")


class IntakeStopped(RuntimeError):
    pass


def check_stop(cancel, deadline):
    if time.monotonic() >= deadline or (cancel is not None and cancel.exists()):
        raise IntakeStopped("owned intake cancellation or deadline")


def sha(path, check=lambda: None):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            check()
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def confined(root, relative):
    if (type(relative) is not str or "\0" in relative or Path(relative).is_absolute()
            or re.match(r"^[A-Za-z]:", relative) or ".." in Path(relative).parts):
        raise ValueError("relative evidence path required")
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("evidence path escapes root")
    return path


def new_output(repo, out):
    repo, out = Path(repo).resolve(), Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("refusing existing cohort or attempt")
    target = out.resolve()
    if not target.is_relative_to(repo) or target == repo:
        raise ValueError("output must stay inside repository")
    return target


def load_protocol(repo, path):
    if sha(path) != PROTOCOL_SHA:
        raise ValueError("frozen matched-check protocol changed")
    freeze = confined(repo, "experiments/chess-matched-check-v1/protocol-freeze.json")
    if sha(freeze) != FREEZE_SHA or read(freeze)["protocol_sha256"] != PROTOCOL_SHA:
        raise ValueError("protocol-first freeze changed")
    protocol = read(path)
    if (protocol["schema"] != "chess.matched-check.diagnostic.protocol-proposal.v2"
            or protocol["fixed_scope"] != {
                "alternative_checkpoints": 0, "conditions": ["primary_v3_selected_step512_only"],
                "engine_calls": 0, "games": 32, "moves_each": 2, "optimizer_updates": 0,
                "pre_move_boards": 32, "prompt_variants": 0, "repeat_generations": 0,
                "seed": 4082032, "source_row_cap": 200000, "total_planned_responses": 64,
                "true_checking_cases": 32, "true_nonchecking_cases": 32}):
        raise ValueError("unsupported frozen scope")
    return protocol


def verify_bindings(repo, workspace, protocol, check=lambda: None):
    evidence = protocol["evidence_before_new_work"]
    for module, name in ((core,"chess_board_fact_core.py"),(prior,"chess_fact_sft_intake.py"),
                         (prior.historical,"chess_board_fact_diagnostic.py")):
        expected = evidence["all_frozen_existing_inputs_sha256"]["scripts/"+name]["sha256"]
        if sha(Path(module.__file__),check) != expected:
            raise ValueError("actually imported source changed: "+name)
    found = {}
    for root, bindings, prefix in (
        (repo, evidence["all_frozen_existing_inputs_sha256"], "repo/"),
        (workspace, evidence["additional_workspace_bindings"], "workspace/"),
    ):
        for name, expected in bindings.items():
            check()
            path = confined(root, name)
            actual = {"bytes": path.stat().st_size, "sha256": sha(path, check)}
            if actual != expected:
                raise ValueError("bound input changed: " + name)
            found[prefix + name] = actual
    metadata_path = confined(repo, "experiments/chess-matched-check-v1/archive/v1/source-and-exclusion-metadata.json")
    if sha(metadata_path) != "3c54efc59492de364f8f3d9159b7f014e877c3a98977b5585121092f79c0df52":
        raise ValueError("runtime metadata changed")
    import chess.pgn
    runtime = read(metadata_path)["runtime"]
    if (chess.__version__ != runtime["chess"]
            or sha(Path(chess.__file__)) != runtime["chess_source"]["sha256"]
            or sha(Path(chess.pgn.__file__)) != runtime["pgn_source"]["sha256"]):
        raise ValueError("board-rule runtime changed")
    return found


def add_fact_roles(row, games, boards):
    board = prior.valid_board(row["source_before_fen"])
    setup = chess.Move.from_uci(row["setup_uci"])
    if setup not in board.legal_moves:
        raise ValueError("illegal retained fact setup")
    boards.add(prior.board_key(board.fen()))
    board.push(setup)
    if board.fen() != row["fen"]:
        raise ValueError("retained fact source roles differ")
    games.add(prior.canonical_game_id(row["game_id"]))
    boards.add(prior.board_key(board.fen()))
    move = chess.Move.from_uci(row["selected_uci"])
    if move not in board.legal_moves:
        raise ValueError("illegal retained supplied fact move")
    board.push(move)
    boards.add(prior.board_key(board.fen()))


def spent_move_successors(repo, check=lambda: None):
    """Read only completed sealed choices; never generate or evaluate a model."""
    import numpy as np
    directory = confined(repo, PRIVATE)
    seal = read(directory / "raw-seal.json")
    if seal["planned"] != 6 or seal["evaluator_opened"] is not False:
        raise ValueError("unexpected retained illustration seal")
    for name, expected in seal["files_sha256"].items():
        if sha(confined(directory, name), check) != expected:
            raise ValueError("retained illustration seal mismatch")
    closed = read(directory / "move-raw-closed.json")
    rows = read(directory / "raw-results.json")["rows"][:4]
    if (rows != closed["rows"] or len(rows) != 4
            or closed["forbid_further_move_calls"] is not True
            or [r["condition"] for r in rows] != seal["conditions"][:4]):
        raise ValueError("retained move closure mismatch")
    positions = read(directory / "move-input.json")["positions"]
    if len(positions) != 1:
        raise ValueError("expected one constructed board")
    board = prior.valid_board(positions[0]["fen"])
    legal = {move.uci() for move in board.legal_moves}
    choices = set()
    for row in rows:
        check()
        if row["status"] != "completed":
            raise ValueError("incomplete retained move choice")
        if "classifier" not in row["condition"]:
            if row["parsed"] is not True or row["raw_legal"] is not True:
                raise ValueError("unverified retained first move")
            choices.add(row["raw_uci"])
            continue
        artifact, labels = row["logit_artifact"], row["id2label"]
        vector_path = confined(directory, artifact["path"])
        if sha(vector_path) != artifact["sha256"]:
            raise ValueError("retained vector mismatch")
        vector = np.load(vector_path, allow_pickle=False)
        if (vector.shape != (1968,) or vector.dtype != np.float32 or type(labels) is not list
                or not np.isfinite(vector).all() or len(labels) != len(set(labels))
                or len(labels) != len(vector)):
            raise ValueError("retained classifier domain differs")
        ranked = sorted(range(len(vector)), key=lambda i: (-float(vector[i]), i))
        masked = [i for i in ranked if labels[i] in legal]
        result = row["raw"]
        if result["raw_choice_uci"] != labels[ranked[0]] or result["legal_choice_uci"] != labels[masked[0]]:
            raise ValueError("retained first classifier choice differs")
        if (result["raw_choice_is_legal"] != (labels[ranked[0]] in legal)
                or result["legal_move_count"] != len(legal)):
            raise ValueError("retained classifier legality accounting differs")
        choices.update((result["raw_choice_uci"], result["legal_choice_uci"]))
        for name, indices in (("raw_topk", ranked[:5]), ("legal_topk", masked[:5])):
            if [item["class_id"] for item in result[name]] != indices:
                raise ValueError("retained classifier ranking differs")
            for item, index in zip(result[name], indices, strict=True):
                if (item["move_uci"] != labels[index] or item["logit"] != float(vector[index])
                        or item["legal"] != (labels[index] in legal)):
                    raise ValueError("retained classifier top-five differs")
                choices.add(item["move_uci"])
    keys = set()
    for uci in choices:
        move = chess.Move.from_uci(uci)
        if move in board.legal_moves:
            after = board.copy(stack=False)
            after.push(move)
            keys.add(prior.board_key(after.fen()))
    return keys


def reconstruct_exclusions(repo, check=lambda: None):
    """Rebuild all known roles and compare full sets, not just their counts."""
    old_protocol = prior.load_protocol(confined(repo, "experiments/chess-fact-sft-v1/protocol.json"))
    games, boards, _ = prior.exclusion_registry(repo, old_protocol)
    for row in read(confined(repo, "data/open/chess/autonomy-broker-derived-20260919-v1/manifest.json"))["items"]:
        games.add(prior.canonical_game_id(row["game_id"]))
        boards.add(prior.board_key(row["fen"]))
        for ply in row.get("legal_replay", []):
            boards.update((prior.board_key(ply["before"]), prior.board_key(ply["after"])))
    rows = list(read(confined(repo, prior.FACT_DATA))["rows"])
    primary = read(confined(repo, "data/private/chess-fact-sft-v1/cohort/dataset.json"))
    for split in ("train", "dev", "holdout"):
        check()
        selected = primary["splits"][split]
        actual = read(confined(repo, "data/private/chess-fact-sft-v1/cohort/" + split + "-inputs.json"))["rows"]
        if [{k:r[k] for k in ("case_id", "fen", "selected_uci")} for r in selected] != actual:
            raise ValueError("retained primary input rows differ")
        for row in selected:
            if prior.canonical_game_id(row["native_game_id"]) != row["game_id"]:
                raise ValueError("retained native GameId differs")
        rows.extend(selected)
    for row in rows:
        check()
        add_fact_roles(row, games, boards)
    for scene in read(confined(repo, "experiments/gotham-illustrative-v1/source-ledger.json"))["scenes"]:
        board = chess.Board()
        boards.add(prior.board_key(board.fen()))
        for san in scene["history_san"].split():
            board.push_san(san)
            boards.add(prior.board_key(board.fen()))
        if board.fen() != scene["pre_move_fen"]:
            raise ValueError("retained illustrative history differs")
        move = chess.Move.from_uci(scene["next_displayed_move_evaluator_only"]["next_displayed_move_uci"])
        if move not in board.legal_moves:
            raise ValueError("illegal retained displayed move")
        board.push(move)
        boards.add(prior.board_key(board.fen()))
    constructed = "experiments/gotham-constructed-middlegame-v1/"
    for row in read(confined(repo, constructed + "move-inputs.json"))["positions"]:
        boards.add(prior.board_key(prior.valid_board(row["fen"]).fen()))
    for row in read(confined(repo, constructed + "fact-inputs.json"))["positions"]:
        board, move = core.board_and_move(row["fen"], row["selected_uci"])
        boards.add(prior.board_key(board.fen()))
        board.push(move)
        boards.add(prior.board_key(board.fen()))
    boards.update(spent_move_successors(repo, check))
    registry_path = confined(repo, REGISTRY)
    if sha(registry_path) != REGISTRY_SHA:
        raise ValueError("frozen known-history registry changed")
    registry = read(registry_path)
    if sorted(games) != registry["games"] or sorted(boards) != registry["board_keys"]:
        raise ValueError("reconstructed known-history union differs")
    return games, boards


def digest(domain, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(domain.encode("ascii") + bytes([10]) + encoded).hexdigest()


def candidate_pairs(board, game_id, puzzle_id, seed, used_boards, source_key):
    """Exhaust eligible pairs before deterministic ranking; no answer-tail use."""
    moves, rejected = [], Counter()
    pre_key = prior.board_key(board.fen())
    for move in sorted(board.legal_moves, key=lambda m:m.uci()):
        if move.promotion or board.is_castling(move) or board.is_en_passant(move):
            rejected["special_move"] += 1
            continue
        after = board.copy(stack=False)
        after.push(move)
        next_key = prior.board_key(after.fen())
        if not after.is_valid() or next_key in used_boards or next_key in (source_key, pre_key):
            rejected["successor_overlap"] += 1
            continue
        moving, victim = board.piece_at(move.from_square), board.piece_at(move.to_square)
        attribute = (move.from_square, moving.piece_type, moving.color, board.is_capture(move), victim.piece_type if victim else None)
        moves.append({"uci":move.uci(), "match":attribute, "check":board.gives_check(move),
                      "successor_key":next_key})
    pairs = []
    for index, first in enumerate(moves):
        for second in moves[index+1:]:
            if first["match"] != second["match"] or first["check"] == second["check"]:
                rejected["unmatched_pair"] += 1
                continue
            if first["successor_key"] == second["successor_key"]:
                rejected["successor_pair_collision"] += 1
                continue
            ucis = [first["uci"], second["uci"]]
            rank = digest("matched-check-pair-v1", {"seed":seed,"game_id":game_id,
                "puzzle_id":puzzle_id,"fen":board.fen(),"moves":ucis})
            pairs.append({"moves":ucis,"pair_sha256":rank,
                          "successor_keys":[first["successor_key"],second["successor_key"]],
                          "matching_attributes":list(first["match"])})
    return sorted(pairs, key=lambda p:(p["pair_sha256"], *p["moves"])), dict(rejected)


def select_rows(rows, games, boards, *, count=32, cap=200000, seed=4082032,
                trace=lambda event: None, check=lambda: None):
    if type(count) is not int or type(cap) is not int or not 0 < count <= 32 or cap < count:
        raise ValueError("positive bounded pair count and source cap required")
    used_games, used_boards = set(games), set(boards)
    accepted, inputs, labels, seen = [], [], {}, set()
    rejections, pair_filters = Counter(), Counter()
    scanned = 0
    for location, row in islice(rows, cap):
        check()
        scanned += 1
        outcome = None
        try:
            game = prior.canonical_game_id(row["GameId"])
            puzzle = row["PuzzleId"]
            if type(puzzle) is not str or re.fullmatch(r"[A-Za-z0-9]+", puzzle) is None:
                raise ValueError("malformed puzzle identity")
            board = prior.valid_board(row["FEN"])
            if type(row["Moves"]) is not str:
                raise ValueError("nonstring source setup")
            setup = chess.Move.from_uci(row["Moves"].split(maxsplit=1)[0])
            if setup not in board.legal_moves:
                raise ValueError("illegal source setup")
            before, before_key = board.fen(), prior.board_key(board.fen())
            board.push(setup)
            if not board.is_valid() or board.is_game_over():
                raise ValueError("invalid or terminal setup-after")
            pre_key = prior.board_key(board.fen())
        except (ValueError, TypeError, KeyError, IndexError):
            outcome = "invalid"
        if outcome is None:
            if game in used_games:
                outcome = "known_or_new_game_overlap"
            elif before_key in used_boards or pre_key in used_boards or before_key == pre_key:
                outcome = "source_role_board_overlap"
            elif puzzle in seen:
                trace({**location,"outcome":"repeated_accepted_puzzle_identity"})
                raise ValueError("accepted puzzle identity repeated")
        if outcome is None:
            pairs, filters = candidate_pairs(board, game, puzzle, seed, used_boards, before_key)
            pair_filters.update(filters)
            if not pairs:
                outcome = "no_legal_matched_pair_after_all_filters"
            else:
                chosen = pairs[0]
                pair_id = "mc-pair-" + format(len(accepted), "02d")
                row_ids = []
                for index, uci in enumerate(chosen["moves"]):
                    case_id = pair_id + "-" + str(index)
                    expected = core.expected_facts(board.fen(), uci)
                    if expected != core.independent_facts(board.fen(), uci):
                        trace({**location,"outcome":"oracle_disagreement"})
                        raise ValueError("fact oracles disagree")
                    core.parse_facts(json.dumps(expected))
                    inputs.append({"case_id":case_id,"fen":board.fen(),"selected_uci":uci})
                    labels[case_id] = {"case_id":case_id,"expected":expected}
                    row_ids.append(case_id)
                if {labels[c]["expected"]["gives_check"] for c in row_ids} != {False, True}:
                    raise ValueError("matched class support differs")
                accepted.append({"pair_id":pair_id,"case_ids":row_ids,"game_id":game,
                    "native_game_id":row["GameId"],"puzzle_id":puzzle,"source_url":"https://lichess.org/"+game,
                    **location,"source_before_fen":before,"setup_uci":setup.uci(),"fen":board.fen(),
                    "legal_move_count":board.legal_moves.count(),"eligible_pair_count":len(pairs),**chosen})
                used_games.add(game)
                used_boards.update((before_key,pre_key,*chosen["successor_keys"]))
                seen.add(puzzle)
                outcome = "accepted"
        rejections[outcome] += 1
        trace({**location,"outcome":outcome})
        if len(accepted) == count:
            break
    if len(accepted) != count:
        raise ValueError(f"fixed source cap shortfall: {len(accepted)}/{count} pairs after {scanned} rows")
    ordered = sorted(inputs, key=lambda r:(digest("matched-check-order-v1", {"seed":seed,"case_id":r["case_id"]}),r["case_id"]))
    return {"pairs":accepted,"inputs":ordered,"labels":[labels[r["case_id"]] for r in ordered],
            "source_rows_scanned":scanned,"terminal_outcomes":dict(rejections),"candidate_filters":dict(pair_filters)}


def freeze(repo, workspace, protocol_path, out, expected_source_sha256, *, cancel=None, deadline=None):
    deadline = time.monotonic()+600 if deadline is None else deadline
    check = lambda: check_stop(cancel, deadline)
    repo, workspace = Path(repo).resolve(), Path(workspace).resolve()
    out = new_output(repo, out)
    if sha(Path(__file__), check) != expected_source_sha256:
        raise ValueError("reviewed intake source changed")
    out.mkdir(parents=True)
    try:
        check()
        protocol = load_protocol(repo, protocol_path)
        before = verify_bindings(repo, workspace, protocol, check)
        games, boards = reconstruct_exclusions(repo, check)
        snapshot = out / "sources"
        snapshot.mkdir()
        sources = [Path(__file__),Path(core.__file__),Path(prior.__file__),Path(prior.historical.__file__),
                   ROOT/"tests/test_chess_matched_check_intake.py",
                   ROOT/"tests/test_chess_matched_check_exclusions.py"]
        for path in sources:
            shutil.copyfile(path, snapshot/path.name)
        source_hashes = {p.name:sha(p,check) for p in snapshot.iterdir()}
        shutil.copyfile(protocol_path,out/"protocol.json")
        save_new(out/"before-selection.json",{"schema":"chess.matched-check.before-selection.v1",
            "protocol_sha256":PROTOCOL_SHA,"sources":source_hashes,"bound_inputs":before,
            "known_games":len(games),"known_board_keys":len(boards),"pid":os.getpid(),"model_calls":0})
        source = confined(repo,protocol["source"]["source_path"])
        with (out/"selection-trace.jsonl").open("x",encoding="utf-8",newline="\n") as stream:
            selected = select_rows(prior.parquet_rows(source), games, boards,
                trace=lambda event:stream.write(json.dumps(event,sort_keys=True)+"\n"),check=check)
        if before != verify_bindings(repo,workspace,protocol,check):
            raise ValueError("bound input changed during selection")
        if (sha(protocol_path,check) != PROTOCOL_SHA
                or sha(Path(__file__),check) != expected_source_sha256
                or any(sha(snapshot/n,check)!=h for n,h in source_hashes.items())
                or any(sha(p,check)!=source_hashes[p.name] for p in sources)):
            raise ValueError("protocol or executed source changed during selection")
        save_new(out/"inputs.json",{"schema":"chess.matched-check.inputs.v1","rows":selected.pop("inputs")})
        labels = selected.pop("labels")
        save_new(out/"labels.json",{"schema":"chess.matched-check.labels.v1","rows":labels})
        selected.update(schema="chess.matched-check.dataset.v1",protocol_sha256=PROTOCOL_SHA,
            known_games=len(games),known_board_keys=len(boards),coverage=prior.class_coverage(labels),model_calls=0,
            limits=["Known-history disjointness only; original video games and upstream pretraining unknown.",
                    "Rule-selected diagnostic of supplied moves; no strength or natural-prevalence estimate."])
        save_new(out/"dataset.json",selected)
        check()
        files = {p.relative_to(out).as_posix():sha(p,check) for p in sorted(out.rglob("*")) if p.is_file()}
        save_new(out/"frozen-data.json",{"schema":"chess.matched-check.frozen-data.v1",
            "files_sha256":files,"protocol_sha256":PROTOCOL_SHA,"pairs":32,"planned":64,"model_calls":0})
        check()
        return {"pairs":32,"planned":64,"frozen_sha256":sha(out/"frozen-data.json",check),"model_calls":0}
    except BaseException as error:
        save_new(out/"selection-failed.json",{"type":type(error).__name__,"error":str(error),
            "model_calls":0,"retry_permitted":False})
        raise


def launch_identity():
    """Avoid the Windows venv-launcher PID indirection; environment is child-only."""
    if any(os.environ.get(name) for name in FORBIDDEN_ENV):
        raise ValueError("conflicting Python path environment")
    executable = Path(sys.executable).resolve()
    base = Path(sys._base_executable).resolve()
    environment = os.environ.copy()
    if os.name == "nt":
        environment["__PYVENV_LAUNCHER__"] = str(executable)
    else:
        base = executable
    return str(base), environment, {"parent_pid":os.getpid(),"base_executable":str(base),
        "base_executable_sha256":sha(base),"venv_executable":str(executable),
        "venv_executable_sha256":sha(executable),"venv_prefix":str(Path(sys.prefix).resolve())}


def run_owned(command, attempt, *, environment=None, seconds=600, grace=30, started=None):
    """Generic owned-process primitive; tests use only harmless CPU fixtures."""
    started = time.monotonic() if started is None else started
    attempt = Path(attempt)
    if attempt.exists() or attempt.is_symlink():
        raise ValueError("refusing existing supervision attempt")
    attempt.mkdir(parents=True)
    save_new(attempt/"intent.json",{"command":list(command),"parent_pid":os.getpid(),
        "budget_seconds":seconds,"grace_seconds":grace,"model_calls":0})
    process, timed_out, forced, exit_code, failure = None, False, False, None, None
    try:
        with (attempt/"stdout.txt").open("xb") as stdout, (attempt/"stderr.txt").open("xb") as stderr:
            if time.monotonic()-started >= seconds:
                timed_out = True
                raise IntakeStopped("owned CPU deadline before launch")
            process = subprocess.Popen(command,stdout=stdout,stderr=stderr,env=environment)
            save_new(attempt/"owned-process.json",{"pid":process.pid,"parent_pid":os.getpid()})
            remaining = max(0,seconds-(time.monotonic()-started))
            try:
                exit_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                timed_out = True
                save_new(attempt/"cancel.json",{"reason":"CPU intake wall deadline"})
                try:
                    exit_code = process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.terminate()
                    exit_code = process.wait(timeout=10)
    except BaseException as error:
        failure = {"type":type(error).__name__,"error":str(error)}
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            exit_code = process.wait(timeout=10)
            forced = True
        receipt = {"schema":"chess.matched-check.owned-CPU.v1","pid":process.pid if process else None,
            "exit_code":exit_code,"timed_out":timed_out,"forced":forced,
            "elapsed_seconds":time.monotonic()-started,"model_calls":0,
            "failure":failure,
            "status":"PASS" if exit_code==0 and not timed_out and failure is None else "FAILED"}
        save_new(attempt/"receipt.json",receipt)
    return receipt


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,default=ROOT)
    parser.add_argument("--workspace-root",type=Path,required=True)
    parser.add_argument("--protocol",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--expected-source-sha256",required=True)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--parent-pid",type=int,help=argparse.SUPPRESS)
    parser.add_argument("--cancel",type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    protocol = args.protocol or args.repo/PROTOCOL
    if args.worker:
        if args.parent_pid != os.getppid() or args.cancel is None:
            raise ValueError("owned CPU worker parent identity missing")
        result = freeze(args.repo,args.workspace_root,protocol,args.out,args.expected_source_sha256,
                        cancel=args.cancel,deadline=started+600)
        print(json.dumps(result))
        return 0
    out = new_output(args.repo,args.out)
    attempt = out.with_name(out.name+"-supervision")
    if attempt.exists() or attempt.is_symlink():
        raise ValueError("refusing existing supervision attempt")
    try:
        if sha(Path(__file__)) != args.expected_source_sha256:
            raise ValueError("reviewed intake source changed")
        load_protocol(args.repo,protocol)
        executable,environment,identity = launch_identity()
    except BaseException as error:
        attempt.mkdir(parents=True)
        failure = {"stage":"parent_preflight","type":type(error).__name__,"error":str(error),
                   "model_calls":0,"worker_started":False,"retry_permitted":False}
        save_new(attempt/"preflight-failed.json",failure)
        print(json.dumps(failure))
        return 2
    command = [executable,"-B",str(Path(__file__).resolve()),"--worker","--repo",str(args.repo.resolve()),
        "--workspace-root",str(args.workspace_root.resolve()),"--protocol",str(protocol.resolve()),
        "--out",str(out),"--expected-source-sha256",args.expected_source_sha256,
        "--parent-pid",str(os.getpid()),"--cancel",str(attempt/"cancel.json")]
    receipt = run_owned(command,attempt,environment=environment,started=started)
    save_new(attempt/"launch-identity.json",identity)
    print(json.dumps(receipt))
    return 0 if receipt["status"]=="PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
