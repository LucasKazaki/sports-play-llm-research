"""Synthetic software fixtures for decompressed standard-game PGN intake."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import chess
import chess.pgn
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "chess_standard_game_intake_v1", ROOT / "scripts/chess_standard_game_intake_v1.py")
assert SPEC and SPEC.loader
intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intake)

LINE = ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6",
        "O-O", "Be7", "Re1", "b5", "Bb3", "d6", "c3", "O-O")


def pgn(game_id: str = "Ab12Cd34", moves: tuple[str, ...] = LINE,
        *, result: str = "1-0", time_control: str = "300+0",
        extra_headers: dict[str, str] | None = None, annotation: bool = False) -> str:
    game = chess.pgn.Game()
    game.headers.update({"Event": "Synthetic fixture", "Site": f"https://lichess.org/{game_id}",
                         "Date": "2025.09.01", "Round": "-", "White": "Test White",
                         "Black": "Test Black", "Result": result,
                         "TimeControl": time_control})
    game.headers.update(extra_headers or {})
    board = chess.Board()
    node = game
    for san in moves:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)
    if annotation:
        node.comment = "[%eval 4.20] forbidden future annotation"
    return game.accept(chess.pgn.StringExporter(headers=True, variations=False,
                                                comments=True)) + "\n\n"


def parse(text: str) -> dict:
    raw = text.encode("utf-8")
    return intake.parse_decompressed_prefix(raw, intake.sha256(raw))


def test_pinned_bytes_and_legal_pre_move_projection_are_evaluator_only():
    text = pgn(annotation=True)
    manifest = parse(text)
    assert manifest["schema"] == intake.SCHEMA
    assert manifest["evaluator_only"] is True
    assert manifest["source"]["bytes"] == len(text.encode("utf-8"))
    assert manifest["counts"] == {"complete_records": 1, "trailing_incomplete_records": 0,
                                  "rejected_by_reason": {}, "accepted_games": 1}
    game = manifest["games"][0]
    assert game["game_id"] == "lichess:Ab12Cd34"
    assert game["plies"][0] == {"ply": 1, "pre_move_fen": chess.STARTING_FEN,
                                "played_uci": "e2e4", "played_san": "e4"}
    assert len(game["plies"]) == 16
    board = chess.Board()
    for projected in game["plies"]:
        assert projected["pre_move_fen"] == board.fen()
        move = chess.Move.from_uci(projected["played_uci"])
        assert projected["played_san"] == board.san(move)
        board.push(move)
    output = json.dumps(manifest)
    assert "forbidden future annotation" not in output
    assert "[%eval" not in output
    assert "generator_packet" not in output
    assert "pv_uci" not in output
    assert "post_move_fen" not in output


def test_trailing_partial_game_is_counted_and_not_projected():
    full = pgn()
    cut = pgn("Bc12De34").split(" 1-0", 1)[0]
    manifest = parse(full + cut)
    assert manifest["counts"]["complete_records"] == 1
    assert manifest["counts"]["trailing_incomplete_records"] == 1
    assert manifest["counts"]["accepted_games"] == 1
    assert [game["game_id"] for game in manifest["games"]] == ["lichess:Ab12Cd34"]


@pytest.mark.parametrize("suffix", [
    " GARBAGE 1-0\n\n",
    ' [Event "hidden"] 1-0\n\n',
    " 1. d4 d5 1-0\n\n",
    " 1-0\n\n",
    " EXTRA\n\n",
    " ;ignored on this line\n EXTRA 1-0\n\n",
    "GARBAGE 1-0\n\n",
    "1. d4 d5 1-0\n\n",
    "{x}GARBAGE 1-0\n\n",
    '[Event "hidden"] 1-0\n\n',
])
def test_text_after_first_mainline_result_is_rejected(suffix):
    manifest = parse(pgn().rstrip() + suffix)
    assert manifest["counts"]["complete_records"] == 1
    assert manifest["counts"]["accepted_games"] == 0
    assert manifest["counts"]["rejected_by_reason"] == {"invalid_result": 1}


@pytest.mark.parametrize("injected", [" GARBAGE 1-0", " Qz9 1-0", " 1. d4 1-0"])
def test_every_token_before_sole_result_must_parse_as_legal_mainline(injected):
    source = pgn().replace(" 1-0\n\n", injected + "\n\n")
    manifest = parse(source)
    assert manifest["counts"]["complete_records"] == 1
    assert manifest["counts"]["accepted_games"] == 0
    assert sum(manifest["counts"]["rejected_by_reason"].values()) == 1


def test_python_chess_null_move_san_is_not_a_legal_game_ply():
    source = pgn().replace(" 1-0\n\n", " 9. -- 1-0\n\n")
    manifest = parse(source)
    assert manifest["counts"]["accepted_games"] == 0
    assert manifest["counts"]["rejected_by_reason"] == {"illegal_move": 1}


@pytest.mark.parametrize("source_san", ["e4#", "e4+", "e2e4", "e2-e4"])
def test_noncanonical_source_san_and_false_check_claims_are_rejected(source_san):
    source = pgn().replace("1. e4 e5", f"1. {source_san} e5")
    manifest = parse(source)
    assert manifest["counts"]["accepted_games"] == 0
    assert sum(manifest["counts"]["rejected_by_reason"].values()) == 1


def test_genuine_check_and_mate_san_remain_accepted():
    checked = parse(pgn(moves=LINE + ("Bxf7+",)))
    assert checked["counts"]["accepted_games"] == 1
    assert checked["games"][0]["plies"][-1]["played_san"] == "Bxf7+"
    waiting = ("Nf3", "Nf6", "Ng1", "Ng8") * 3
    mated = parse(pgn(moves=waiting + ("f3", "e5", "g4", "Qh4#"), result="0-1"))
    assert mated["counts"]["accepted_games"] == 1
    assert mated["games"][0]["plies"][-1]["played_san"] == "Qh4#"


def test_trailing_comments_and_variations_do_not_create_second_mainline_result():
    source = pgn().rstrip() + " {an annotation containing 0-1} (8... Bb7) ; tail 1-0\n\n"
    manifest = parse(source)
    assert manifest["counts"]["accepted_games"] == 1
    assert manifest["counts"]["rejected_by_reason"] == {}


def test_even_result_token_without_final_delimiter_is_not_a_complete_prefix_record():
    manifest = parse(pgn().rstrip())
    assert manifest["counts"]["complete_records"] == 0
    assert manifest["counts"]["trailing_incomplete_records"] == 1
    assert not manifest["games"]


def test_variant_custom_start_illegal_move_and_bad_headers_are_separate_rejections():
    variant = pgn("Va12Ri34", extra_headers={"Variant": "Chess960"})
    custom = pgn("Cu12St34", extra_headers={"SetUp": "1", "FEN": chess.STARTING_FEN})
    illegal = pgn("Il12Lg34").replace("3. Bb5", "3. Qa9")
    malformed = pgn("Ma12Lf34").replace('[Site "https://lichess.org/Ma12Lf34"]',
                                       '[Site https://lichess.org/Ma12Lf34]')
    result = parse(variant + custom + illegal + malformed)
    assert result["counts"]["complete_records"] == 4
    assert result["counts"]["accepted_games"] == 0
    assert result["counts"]["rejected_by_reason"] == {
        "illegal_move": 1, "malformed_header": 1, "nonstandard_start": 2}


def test_game_and_trajectory_duplicates_have_distinct_denominators():
    manifest = parse(pgn() + pgn() + pgn("Ef56Gh78"))
    assert manifest["counts"]["complete_records"] == 3
    assert manifest["counts"]["accepted_games"] == 1
    assert manifest["counts"]["rejected_by_reason"] == {
        "duplicate_game_id": 1, "duplicate_trajectory": 1}


@pytest.mark.parametrize("changed,reason", [
    (lambda s: s.replace("https://lichess.org/Ab12Cd34", "https://other.org/Ab12Cd34"),
     "invalid_site"),
    (lambda s: s.replace('[Result "1-0"]', '[Result "0-1"]'), "invalid_result"),
    (lambda s: s.replace('[TimeControl "300+0"]', '[TimeControl "60+0"]'),
     "short_time_control"),
    (lambda s: s.replace('[TimeControl "300+0"]', '[TimeControl "-"]'),
     "invalid_time_control"),
    (lambda s: s.replace("3. Bb5", "3. Bc4"), "illegal_move"),
])
def test_rejects_nonconforming_complete_records(changed, reason):
    manifest = parse(changed(pgn()))
    assert manifest["counts"]["complete_records"] == 1
    assert manifest["counts"]["accepted_games"] == 0
    assert manifest["counts"]["rejected_by_reason"] == {reason: 1}


def test_short_game_and_comment_header_like_text_do_not_hide_records():
    short = pgn("Sh12Or34", moves=LINE[:14])
    with_header_looking_comment = pgn(annotation=True).replace(
        "forbidden future annotation", "forbidden future annotation\n\n[Event Fake]")
    manifest = parse(short + with_header_looking_comment)
    assert manifest["counts"]["complete_records"] == 2
    assert manifest["counts"]["accepted_games"] == 1
    assert manifest["counts"]["rejected_by_reason"] == {"short_game": 1}


def test_hash_and_byte_bounds_fail_closed():
    raw = pgn().encode("utf-8")
    with pytest.raises(ValueError, match="hash_mismatch"):
        intake.parse_decompressed_prefix(raw, "0" * 64)
    with pytest.raises(ValueError, match="invalid_expected_sha256"):
        intake.parse_decompressed_prefix(raw, "bad")
    with pytest.raises(ValueError, match="invalid_pgn_byte_count"):
        intake.parse_decompressed_prefix(b"x" * (intake.MAX_PGN_BYTES + 1),
                                         intake.sha256(raw))


def test_cli_writes_new_canonical_manifest_only_once(tmp_path, monkeypatch):
    source = tmp_path / "prefix.pgn"
    output = tmp_path / "intake.json"
    source.write_bytes(pgn().encode("utf-8"))
    monkeypatch.setattr(sys, "argv", ["intake", "--decompressed-pgn", str(source),
                                      "--sha256", intake.sha256(source.read_bytes()),
                                      "--output", str(output)])
    intake.main()
    encoded = output.read_bytes()
    assert json.loads(encoded)["counts"]["accepted_games"] == 1
    assert encoded.endswith(b"\n")
    with pytest.raises(FileExistsError):
        intake.main()
    assert output.read_bytes() == encoded
