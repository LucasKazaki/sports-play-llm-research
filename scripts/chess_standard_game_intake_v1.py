"""Bounded, offline intake of a decompressed standard-game PGN prefix.

This module accepts caller-pinned PGN bytes. It does not fetch or decompress the
source archive, inspect protected cohorts, run an engine, or make generator
inputs. Its whole-game replay is evaluator-only: later plies must never be
copied into a no-forward commentary packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import chess


SCHEMA = "chess-standard-game-intake/v1"
MAX_PGN_BYTES = 16 * 1024 * 1024
MIN_PLIES = 16
MIN_INITIAL_SECONDS = 300
SITE = re.compile(r"https://lichess\.org/([A-Za-z0-9]{8})\Z")
HEADER = re.compile(r'^\[([A-Za-z][A-Za-z0-9]*) "((?:[^"\\]|\\.)*)"\]$')
TIME_CONTROL = re.compile(r"([0-9]+)\+([0-9]+)\Z")
RESULTS = frozenset(("1-0", "0-1", "1/2-1/2"))
MOVE_NUMBER = re.compile(r"([1-9][0-9]*)\.(\.\.)?")
NAG = re.compile(r"\$[1-9][0-9]*\Z")
BOUNDARY = re.compile(r"\r?\n(?:[ \t]*\r?\n)+(?=\[)")
FINAL_DELIMITER = re.compile(r"\r?\n[ \t]*\r?\n\Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _comment_depth(text: str, start: int, end: int, depth: int, semicolon: bool) -> tuple[int, bool]:
    """Track PGN comments so a header-looking line inside one is not a split."""
    for char in text[start:end]:
        if char == "\n":
            semicolon = False
        elif semicolon:
            continue
        elif char == ";" and depth == 0:
            semicolon = True
        elif char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
    return depth, semicolon


def _segments(text: str) -> tuple[list[str], bool]:
    """Only an observed next header or final blank line closes a PGN record."""
    parts: list[str] = []
    start = 0
    scanned = 0
    depth = 0
    semicolon = False
    for match in BOUNDARY.finditer(text):
        depth, semicolon = _comment_depth(text, scanned, match.end(), depth, semicolon)
        scanned = match.end()
        if depth == 0 and not semicolon:
            parts.append(text[start:match.start()])
            start = match.end()
    tail = text[start:]
    if FINAL_DELIMITER.search(tail):
        parts.append(tail)
        return parts, False
    return parts, bool(tail.strip())


def _mainline_tokens(movetext: str) -> list[str] | None:
    """Tokenize every mainline character without joining across annotations."""
    tokens: list[str] = []
    current: list[str] = []
    brace_depth = 0
    variation_depth = 0
    semicolon = False

    def flush() -> None:
        if current:
            tokens.append("".join(current))
            current.clear()

    for char in movetext:
        if semicolon:
            if char == "\n":
                semicolon = False
            continue
        if brace_depth:
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
            continue
        if char == "{":
            if not variation_depth:
                flush()
            brace_depth = 1
            continue
        if char == ";":
            if not variation_depth:
                flush()
            semicolon = True
            continue
        if variation_depth:
            if char == "(":
                variation_depth += 1
            elif char == ")":
                variation_depth -= 1
            continue
        if char == "(":
            flush()
            variation_depth = 1
            continue
        if char in "})":
            return None
        if char.isspace():
            flush()
            continue
        current.append(char)
    if brace_depth or variation_depth:
        return None
    flush()
    return tokens


def _replay_mainline(tokens: list[str], result: str) -> tuple[list[dict] | None, str | None]:
    """Consume every visible token and replay only legal SAN from the start."""
    board = chess.Board()
    moves: list[dict] = []
    pending_number = False
    result_seen = False
    for original in tokens:
        token = original
        if token in RESULTS or token == "*":
            if result_seen or token != result or pending_number:
                return None, "invalid_result"
            result_seen = True
            continue
        if result_seen or any(marker in token for marker in (*RESULTS, "*")):
            return None, "invalid_result"
        if NAG.fullmatch(token):
            if not moves or pending_number:
                return None, "malformed_movetext"
            continue
        number = MOVE_NUMBER.match(token)
        if number:
            if pending_number or int(number[1]) != board.fullmove_number \
                    or (number[2] is not None) != (board.turn == chess.BLACK):
                return None, "malformed_move_number"
            token = token[number.end():]
            pending_number = True
            if not token:
                continue
        elif token[0].isdigit():
            return None, "malformed_move_number"
        san = re.sub(r"[!?]{1,2}\Z", "", token)
        try:
            move = board.parse_san(san)
        except ValueError:
            return None, "illegal_move"
        if move not in board.legal_moves:
            return None, "illegal_move"
        canonical_san = board.san(move)
        if san != canonical_san:
            return None, "noncanonical_san"
        moves.append({"ply": len(moves) + 1, "pre_move_fen": board.fen(),
                      "played_uci": move.uci(), "played_san": canonical_san})
        board.push(move)
        pending_number = False
    if not result_seen:
        return None, "invalid_result"
    if len(moves) < MIN_PLIES:
        return None, "short_game"
    return moves, None


def _parse_record(record: str, ordinal: int) -> tuple[dict | None, str | None]:
    normalized = record.replace("\r\n", "\n")
    sections = normalized.split("\n\n", 1)
    if len(sections) != 2:
        return None, "malformed_record"
    header_lines = sections[0].split("\n")
    headers: dict[str, str] = {}
    for line in header_lines:
        match = HEADER.fullmatch(line)
        if not match or match[1] in headers:
            return None, "malformed_header"
        headers[match[1]] = match[2]
    if not headers:
        return None, "malformed_header"
    if headers.get("Variant", "Standard") != "Standard" or "SetUp" in headers or "FEN" in headers:
        return None, "nonstandard_start"
    site = SITE.fullmatch(headers.get("Site", ""))
    if site is None:
        return None, "invalid_site"
    result = headers.get("Result")
    tokens = _mainline_tokens(sections[1])
    if result not in RESULTS or tokens is None:
        return None, "invalid_result"
    time_control = TIME_CONTROL.fullmatch(headers.get("TimeControl", ""))
    if time_control is None:
        return None, "invalid_time_control"
    if int(time_control[1]) < MIN_INITIAL_SECONDS:
        return None, "short_time_control"
    moves, reason = _replay_mainline(tokens, result)
    if reason:
        return None, reason
    assert moves is not None
    trajectory = "\n".join(move["played_uci"] for move in moves).encode("ascii")
    return {
        "source_ordinal": ordinal,
        "source_record_sha256": sha256(record.encode("utf-8")),
        "game_id": f"lichess:{site[1]}",
        "result": result,
        "time_control": headers["TimeControl"],
        "trajectory_sha256": sha256(trajectory),
        "plies": moves,
    }, None


def parse_decompressed_prefix(raw: bytes, expected_sha256: str) -> dict:
    """Parse a caller-pinned byte prefix; return an evaluator-only manifest.

    The hash covers these decompressed bytes, not the compressed archive. A
    subsequent broker integration must independently bind the decompression to
    its retained compressed-prefix receipt.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PGN_BYTES:
        raise ValueError("invalid_pgn_byte_count")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid_expected_sha256")
    if sha256(raw) != expected_sha256:
        raise ValueError("pgn_source_hash_mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("invalid_utf8_pgn") from error
    if "\x00" in text or "\r" in text.replace("\r\n", ""):
        raise ValueError("invalid_pgn_encoding")
    records, trailing = _segments(text)
    rejected: Counter[str] = Counter()
    games: list[dict] = []
    seen_ids: set[str] = set()
    seen_trajectories: set[str] = set()
    for ordinal, record in enumerate(records, start=1):
        game, reason = _parse_record(record, ordinal)
        if reason:
            rejected[reason] += 1
            continue
        assert game is not None
        if game["game_id"] in seen_ids:
            rejected["duplicate_game_id"] += 1
            continue
        seen_ids.add(game["game_id"])
        if game["trajectory_sha256"] in seen_trajectories:
            rejected["duplicate_trajectory"] += 1
            continue
        seen_trajectories.add(game["trajectory_sha256"])
        games.append(game)
    return {
        "schema": SCHEMA,
        "evaluator_only": True,
        "source": {"content_kind": "decompressed_pgn_prefix", "bytes": len(raw),
                   "sha256": expected_sha256,
                   "assurance": "caller-pinned decompressed bytes; compressed broker binding pending"},
        "counts": {"complete_records": len(records), "trailing_incomplete_records": int(trailing),
                   "rejected_by_reason": dict(sorted(rejected.items())),
                   "accepted_games": len(games)},
        "games": games,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decompressed-pgn", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.decompressed_pgn.open("rb") as source:
        raw = source.read(MAX_PGN_BYTES + 1)
    manifest = parse_decompressed_prefix(raw, args.sha256)
    encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False) + "\n").encode("utf-8")
    with args.output.open("xb") as destination:
        destination.write(encoded)


if __name__ == "__main__":
    main()
