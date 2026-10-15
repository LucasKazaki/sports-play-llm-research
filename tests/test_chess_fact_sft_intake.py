"""Small synthetic intake fixtures; never select from the real pinned shard."""
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import sys

import chess
import chess.pgn
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import chess_fact_sft_intake as intake


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def toy_rows(count=120):
    rng = random.Random(84311)
    board = chess.Board()
    result = []
    for n in range(count):
        if board.is_game_over():
            board = chess.Board()
        for _ in range(3):
            if board.is_game_over():
                board = chess.Board()
            board.push(rng.choice(list(board.legal_moves)))
        move = rng.choice(list(board.legal_moves))
        result.append({"PuzzleId": f"toy{n}", "GameId": f"{n:08d}/black#42", "FEN": board.fen(),
                       "Moves": move.uci() + " ANSWER_TAIL_IS_NOT_A_MOVE", "Rating": "FORBIDDEN",
                       "Themes": ["FORBIDDEN"], "expected": "FORBIDDEN"})
        board.push(move)
    return result


def located(rows):
    for n, row in enumerate(rows):
        yield {"source_ordinal": n, "row_group": 0, "row_in_group": n}, row


@pytest.mark.parametrize("raw,game", [("787zsVup/black#48", "787zsVup"), ("F8M8OS71#53", "F8M8OS71"),
    ("EwHRkfas", "EwHRkfas"), ("AbCd1234/white", "AbCd1234"), ("AbCd1234/white#0", "AbCd1234")])
def test_native_game_id_suffix_is_not_part_of_identity(raw, game):
    assert intake.canonical_game_id(raw) == game


@pytest.mark.parametrize("raw", [None, 12345678, "", "https://lichess.org/AbCd1234", "AbCd1234/green#2",
    "AbCd1234#-1", "AbCd1234#", "AbCd1234/black#2/garbage", "ébcD1234", " AbCd1234", "AbCd1234\n"])
def test_native_game_id_rejects_malformed_without_inference(raw):
    with pytest.raises(ValueError, match="GameId"):
        intake.canonical_game_id(raw)


def test_frozen_protocol_core_is_checked_and_changed_bytes_fail(tmp_path):
    protocol = intake.ROOT / "experiments/chess-fact-sft-v1/protocol.json"
    assert intake.load_protocol(protocol)["intake"]["seed"] == 4082031
    copied = tmp_path / "protocol.json"
    copied.write_bytes(protocol.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="protocol changed"):
        intake.load_protocol(copied)


def test_board_key_ignores_clocks_and_nonlegal_ep_but_keeps_side_and_rights():
    start = chess.STARTING_FEN
    assert intake.board_key(start) == intake.board_key(start.rsplit(" ", 2)[0] + " 77 99")
    assert intake.board_key(start) != intake.board_key(start.replace(" w ", " b "))
    board = chess.Board(); board.push_uci("e2e4")
    assert intake.board_key(board.fen(en_passant="fen")) == intake.board_key(board.fen())
    castle = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    assert intake.board_key(castle) != intake.board_key(castle.replace("KQkq", "-"))


def test_source_order_split_move_hash_labels_and_input_boundary_are_deterministic():
    rows = toy_rows()
    a = intake.select_rows(located(rows), dict(train=2, dev=2, holdout=2), 4082031, set(), set())
    assert a == intake.select_rows(located(rows), dict(train=2, dev=2, holdout=2), 4082031, set(), set())
    seen_games, seen_keys = set(), set()
    for split in intake.SPLITS:
        assert len(a["inputs"][split]) == 2
        assert all(sum(c.values()) == 2 for c in a["coverage"][split].values())
        for meta, packet, label in zip(a["metadata"][split], a["inputs"][split], a["labels"][split], strict=True):
            game = meta["game_id"]
            bucket = int(hashlib.sha256(f"4082031:{game}".encode()).hexdigest(), 16) % 10
            assert split == ("train" if bucket < 8 else "dev" if bucket == 8 else "holdout")
            board = chess.Board(meta["source_before_fen"]); board.push_uci(meta["setup_uci"])
            assert board.fen() == packet["fen"]
            legal = sorted(move.uci() for move in board.legal_moves)
            index = int(hashlib.sha256(f"move:4082031:{game}".encode()).hexdigest(), 16) % len(legal)
            assert packet["selected_uci"] == legal[index]
            assert label["expected"] == intake.core.expected_facts(packet["fen"], packet["selected_uci"])
            assert label["expected"] == intake.core.independent_facts(packet["fen"], packet["selected_uci"])
            assert set(packet) == {"case_id", "fen", "selected_uci"}
            assert "FORBIDDEN" not in intake.core.build_prompt({**packet, "expected": "FORBIDDEN"}, "fen_uci_piece_map")
            keys = {intake.board_key(meta["source_before_fen"]), intake.board_key(meta["fen"])}
            assert game not in seen_games and not (keys & seen_keys)
            seen_games.add(game); seen_keys.update(keys)
    assert a["rejections"]["bucket_full"] > 0


def test_exclusions_cover_both_roles_counters_and_native_suffix_aliases():
    rows = toy_rows()
    initial = intake.select_rows(located(rows), dict(train=1, dev=1, holdout=1), 4082031, set(), set())
    meta = initial["metadata"]["train"][0]
    # A game exclusion must apply despite a different colour/ply suffix.
    rejected = intake.select_rows(located(rows), dict(train=1, dev=1, holdout=1), 4082031, {meta["game_id"]}, set())
    assert meta["game_id"] not in {r["game_id"] for s in rejected["metadata"].values() for r in s}
    for role in ("source_before_fen", "fen"):
        bad_key = intake.board_key(meta[role])
        result = intake.select_rows(located(rows), dict(train=1, dev=1, holdout=1), 4082031, set(), {bad_key})
        assert all(bad_key not in {intake.board_key(r["source_before_fen"]), intake.board_key(r["fen"])}
                   for s in result["metadata"].values() for r in s)


def test_invalid_setup_and_identity_are_counted_but_answer_tail_is_ignored():
    rows = toy_rows()
    bads = [dict(rows[0], GameId="bad"), dict(rows[0], Moves="e2e5 nonsense"), dict(rows[0], FEN="bad")]
    result = intake.select_rows(located([*bads, *rows]), dict(train=1, dev=1, holdout=1), 4082031, set(), set())
    assert result["rejections"]["invalid"] == 3


def test_exhaustion_fails_instead_of_substituting_or_dropping_split():
    with pytest.raises(ValueError, match="quotas"):
        intake.select_rows(located(toy_rows(1)), dict(train=2, dev=2, holdout=2), 4082031, set(), set())


def test_oracle_disagreement_stops_without_selecting_replacement(monkeypatch):
    monkeypatch.setattr(intake.core, "independent_facts", lambda *args: {})
    with pytest.raises(ValueError, match="oracles disagree"):
        intake.select_rows(located(toy_rows()), dict(train=1, dev=1, holdout=1), 4082031, set(), set())


def test_zero_positive_coverage_is_explicit():
    truth = intake.core.expected_facts(chess.STARTING_FEN, "e2e4")
    coverage = intake.class_coverage([{"expected": truth}])
    assert coverage["is_en_passant"] == {"false": 1, "true": 0, "unknown": 0}
    assert coverage["promotion_piece"]["null"] == 1 and coverage["promotion_piece"]["queen"] == 0


@pytest.fixture
def registry_fixture(tmp_path, monkeypatch):
    rows = toy_rows(16)
    facts = []
    for row in rows:
        board = chess.Board(row["FEN"]); move = row["Moves"].split()[0]; board.push_uci(move)
        facts.append({"game_id": intake.canonical_game_id(row["GameId"]), "source_before_fen": row["FEN"],
                      "setup_uci": move, "fen": board.fen()})
    write(tmp_path / intake.FACT_DATA, {"rows": facts})
    pgn = tmp_path / intake.ROLLOUT; pgn.parent.mkdir(parents=True)
    pgn.write_text((' [Event "fixture"]\n\n1. e4 e5 *\n\n'.lstrip()) * 64)
    write(tmp_path / intake.VIDEO, {"positions": [{"pre_move_fen": r["FEN"]} for r in rows[:3]]})
    prefix = tmp_path / intake.PRIOR_SOURCE; prefix.parent.mkdir(parents=True); prefix.write_bytes(b"fixture")
    names = (intake.FACT_DATA, intake.ROLLOUT, intake.VIDEO, intake.PRIOR_SOURCE)
    required = {name: intake.sha(tmp_path / name) for name in names}
    base_games, base_boards = {"legacy01"}, {intake.board_key(chess.STARTING_FEN)}
    monkeypatch.setattr(intake.historical, "prior_exclusions", lambda *args: (set(base_games), set(base_boards), {}))
    policy = {"intake": {"prior_exclusions": {"required_files_sha256": required,
              "expected_prior_base_crosscheck": {"games": 1, "board_keys": 1}}}}
    return tmp_path, policy


def test_registry_replays_all_games_and_pins_exact_union(registry_fixture):
    repo, protocol = registry_fixture
    games, boards, registry = intake.exclusion_registry(repo, protocol)
    assert len(games) == 17 and registry["rollout_games"] == 64 and registry["rollout_plies"] == 128
    assert registry["stages"]["all_spent_union"] == {"games": len(games), "board_keys": len(boards)}
    assert set(registry["games"]) == games and set(registry["board_keys"]) == boards
    board = chess.Board(); board.push_uci("e2e4"); board.push_uci("e7e5")
    assert intake.board_key(board.fen()) in boards


def test_registry_hash_tamper_and_wrong_reconstruction_counts_fail(registry_fixture):
    repo, protocol = registry_fixture
    wrong = copy.deepcopy(protocol)
    wrong["intake"]["prior_exclusions"]["expected_prior_base_crosscheck"]["games"] = 2
    with pytest.raises(ValueError, match="counts disagree"):
        intake.exclusion_registry(repo, wrong)
    (repo / intake.VIDEO).write_text("changed")
    with pytest.raises(ValueError, match="artifact changed"):
        intake.exclusion_registry(repo, protocol)


@pytest.fixture
def freeze_fixture(tmp_path, monkeypatch):
    repo = tmp_path / "repo"; repo.mkdir()
    protocol = intake.read(intake.ROOT / "experiments/chess-fact-sft-v1/protocol.json")
    protocol["intake"]["split_counts"] = dict(train=1, dev=1, holdout=1)
    source = repo / "source.parquet"
    pq.write_table(pa.Table.from_pylist(toy_rows()), source, row_group_size=17)
    write(repo / "acquisition.json", {"fixture": True})
    protocol["acquisition"].update(source_path="source.parquet", source_bytes=source.stat().st_size,
        source_sha256=intake.sha(source), amendment="acquisition.json", amendment_sha256=intake.sha(repo / "acquisition.json"))
    path = repo / "protocol.json"; write(path, protocol)
    monkeypatch.setattr(intake, "PROTOCOL_SHA256", intake.sha(path))
    monkeypatch.setattr(intake, "exclusion_registry", lambda *args: (set(), set(), {"fixture": True, "required_files_sha256": {}}))
    return repo, path, tmp_path / "cohort"


def test_freeze_writes_separate_inputs_labels_and_hashes_before_any_model(freeze_fixture):
    repo, protocol, out = freeze_fixture
    frozen = intake.freeze(repo, protocol, out)
    assert frozen["model_calls"] == 0 and (out / "before-selection.json").is_file()
    trace = [json.loads(line) for line in (out / "selection-trace.jsonl").read_text().splitlines()]
    dataset = intake.read(out / "dataset.json")
    assert len(trace) == dataset["source_rows_scanned"]
    assert [r["source_ordinal"] for r in trace] == list(range(len(trace)))
    assert sum(r["outcome"] == "accepted" for r in trace) == 3
    for name, expected in frozen["files_sha256"].items():
        assert intake.sha(out / name) == expected
    for split in intake.SPLITS:
        packet = intake.read(out / (split + "-inputs.json"))["rows"][0]
        label = intake.read(out / (split + "-labels.json"))["rows"][0]
        assert set(packet) == {"case_id", "fen", "selected_uci"} and set(label) == {"case_id", "expected"}
        assert packet["case_id"] == label["case_id"]
    before = {p.relative_to(out).as_posix(): intake.sha(p) for p in out.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="overwrite"):
        intake.freeze(repo, protocol, out)
    assert before == {p.relative_to(out).as_posix(): intake.sha(p) for p in out.rglob("*") if p.is_file()}


def test_changed_parquet_blocks_before_attempt(freeze_fixture):
    repo, protocol, out = freeze_fixture
    with (repo / "source.parquet").open("ab") as stream: stream.write(b"changed")
    with pytest.raises(ValueError, match="Parquet source changed"):
        intake.freeze(repo, protocol, out)
    assert not out.exists()


def test_failed_selection_is_retained_and_cannot_be_repeated(freeze_fixture, monkeypatch):
    repo, protocol, out = freeze_fixture
    monkeypatch.setattr(intake, "parquet_rows", lambda *args: iter(()))
    with pytest.raises(ValueError, match="quotas"):
        intake.freeze(repo, protocol, out)
    assert intake.read(out / "selection-failed.json")["retry_permitted"] is False
    assert not (out / "frozen-data.json").exists()
    with pytest.raises(ValueError, match="overwrite"):
        intake.freeze(repo, protocol, out)


def test_parquet_reader_uses_only_four_columns_in_physical_group_order(freeze_fixture):
    repo, _, _ = freeze_fixture
    rows = list(intake.parquet_rows(repo / "source.parquet"))
    assert len(rows) == 120
    assert all(set(row) == {"PuzzleId", "GameId", "FEN", "Moves"} for _, row in rows)
    assert rows[17][0] == {"source_ordinal": 17, "row_group": 1, "row_in_group": 0}
