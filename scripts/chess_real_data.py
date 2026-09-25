"""Bounded public Lichess intake and reproducible, local chess baselines.

No model calls, service, scheduler, full corpus download, or synthetic fallback.
Puzzle solution/theme fields are targets, never engine inputs. Test split stays sealed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import stat
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import chess
import chess.engine
import chess.svg

SOURCE_PAGE = "https://database.lichess.org/"
SOURCE_PREFIX = SOURCE_PAGE + "lichess_db_puzzle.csv.zst"
MAX_COMPRESSED = 262144
MAX_DECOMPRESSED = 8 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def derive_row(row):
    """Replay every published move; preserve the opponent setup/solution distinction."""
    game_match = re.fullmatch(r"https://lichess.org/([A-Za-z0-9]{8})(?:/[^#]+)?(?:#\d+)?", row["GameUrl"])
    if not game_match:
        raise ValueError("invalid_game_source")
    board = chess.Board(row["FEN"])
    if not board.is_valid():
        raise ValueError("invalid_board")
    moves = row["Moves"].split()
    if len(moves) < 2:
        raise ValueError("missing_setup_or_solution")
    trace = []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError("illegal_source_move:" + uci)
        before = board.fen()
        san = board.san(move)
        board.push(move)
        trace.append({"before": before, "uci": uci, "san": san, "after": board.fen()})
    return {
        "position_id": "lichess-puzzle-" + row["PuzzleId"],
        "puzzle_id": row["PuzzleId"], "game_id": game_match[1],
        "game_url": row["GameUrl"], "source_fen": row["FEN"],
        "fen": trace[0]["after"], "setup_move": moves[0],
        "target_move": moves[1], "solution_uci": moves[1:],
        "rating": int(row["Rating"]), "themes": row["Themes"].split(),
        "legal_replay": trace, "legal_replay_sha256": sha(json_bytes(trace)),
        "provenance_kind": "real_public_game_derived_puzzle",
        "label_origin": "Lichess engine generated puzzle and automatic themes; not human commentary",
    }


def select_rows(csv_text, count=24, min_rating=None):
    if count != 24:
        raise ValueError("this_frozen_seed_requires_24_items")
    selected, games, seen = [], set(), set()
    for row in csv.DictReader(io.StringIO(csv_text)):
        derived = derive_row(row)
        if min_rating is not None and derived["rating"] < min_rating:
            continue
        if derived["game_id"] in games or derived["fen"] in seen:
            continue
        selected.append((row, derived))
        games.add(derived["game_id"])
        seen.add(derived["fen"])
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError("insufficient_unique_real_games")
    ranked = sorted(games, key=lambda value: sha(("lichess-seed-v1:" + value).encode()))
    splits = {game:["train","dev","test"][i // 8] for i, game in enumerate(ranked)}
    for _, derived in selected:
        derived["split"] = splits[derived["game_id"]]
    return selected

    if count != 24:
        raise ValueError("this_frozen_seed_requires_24_items")
    selected, games, seen = [], set(), set()
    for row in csv.DictReader(io.StringIO(csv_text)):
        derived = derive_row(row)
        if derived["game_id"] in games or derived["fen"] in seen:
            continue
        selected.append((row, derived))
        games.add(derived["game_id"])
        seen.add(derived["fen"])
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError("insufficient_unique_real_games")
    ranked = sorted(games, key=lambda value: sha(("lichess-seed-v1:" + value).encode()))
    splits = {game: ["train", "dev", "test"][i // 8] for i, game in enumerate(ranked)}
    for _, derived in selected:
        derived["split"] = splits[derived["game_id"]]
    return selected


def _local_broker_path(file):
    if os.fspath(file).replace("/", "\\").startswith("\\\\"):
        raise ValueError("broker_local_path_required_no_unc_or_device_paths")
    return Path(file).absolute()


def _broker_file_bytes(file, max_bytes):
    """Read one bounded regular file without following links or reparse points."""
    file = _local_broker_path(file)
    if ".." in file.parts:
        raise ValueError("broker_path_parent_escape")
    try:
        for part in [*reversed(file.parents), file]:
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("broker_symlink_or_reparse_path")
        before = file.stat()
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= max_bytes:
            raise ValueError("broker_file_bytes_outside_bound")
        descriptor = os.open(file, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
        final = file.lstat()
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(opened) or identity(opened) != identity(after) or identity(after) != identity(final):
            raise ValueError("broker_file_changed_during_read")
        if len(data) != before.st_size:
            raise ValueError("broker_file_bytes_changed")
        return data
    except OSError as error:
        raise ValueError("broker_file_unavailable:" + file.name) from error


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("broker_receipt_duplicate_key")
        value[key] = item
    return value


def _broker_inputs(receipt_path):
    """Validate retained bytes. Authentic fetch provenance comes from the native job, not JSON alone."""
    receipt_path = _local_broker_path(receipt_path)
    raw = _broker_file_bytes(receipt_path, 128 * 1024)
    receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(receipt, dict) or receipt.get("schema") != "project-public-data-acquisition/v1" \
            or receipt.get("source") != "lichess-puzzle-prefix" \
            or receipt.get("synthetic") is not False or receipt.get("fullArchive") is not False:
        raise ValueError("invalid_broker_receipt_contract")
    target = receipt.get("target", "")
    if not isinstance(target, str) or not re.fullmatch(r"data/open/chess/[A-Za-z0-9][A-Za-z0-9._-]{0,100}", target) \
            or tuple(part.casefold() for part in receipt_path.parent.parts[-4:]) != tuple(part.casefold() for part in target.split("/")):
        raise ValueError("broker_target_path_mismatch")
    license_info, page_meta, prefix_meta = [receipt.get(key) for key in ("license", "page", "prefix")]
    if not all(isinstance(value, dict) for value in (license_info, page_meta, prefix_meta)):
        raise ValueError("invalid_broker_source_contract")
    if license_info.get("spdx") != "CC0-1.0" or license_info.get("evidenceFile") != "source-page.html":
        raise ValueError("broker_rights_contract_missing")
    try:
        retrieved_at = datetime.fromisoformat(receipt["retrievedAt"].replace("Z", "+00:00"))
        if retrieved_at.tzinfo is None:
            raise ValueError("timezone required")
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("broker_retrieval_time_invalid") from error
    if type(receipt.get("timeoutMs")) is not int or not 0 < receipt["timeoutMs"] <= 60000:
        raise ValueError("broker_timeout_invalid")
    retained = []
    for metadata, expected_file, expected_url, budget in (
            (page_meta, "source-page.html", SOURCE_PAGE, 2 * 1024 * 1024),
            (prefix_meta, "puzzles.csv.zst.part", SOURCE_PREFIX, MAX_COMPRESSED)):
        if metadata.get("file") != expected_file or metadata.get("url") != expected_url:
            raise ValueError("broker_source_path_or_url_mismatch")
        headers = metadata.get("headers")
        if not isinstance(headers, dict) or any(headers.get(key) is not None and
                (not isinstance(headers[key], str) or len(headers[key]) > 8192)
                for key in ("etag", "lastModified", "contentType", "contentRange", "contentLength")):
            raise ValueError("broker_headers_invalid")
        data = _broker_file_bytes(receipt_path.parent / expected_file, budget)
        if type(metadata.get("bytes")) is not int or metadata["bytes"] != len(data) \
                or metadata.get("sha256") != sha(data):
            raise ValueError("broker_artifact_hash_or_bytes_mismatch:" + expected_file)
        retained.append(data)
    page, compressed = retained
    if page_meta.get("status") != 200 or prefix_meta.get("status") not in (200, 206):
        raise ValueError("broker_http_status_invalid")
    maximum = prefix_meta.get("requestedMaxBytes")
    if type(maximum) is not int or not 65536 <= maximum <= MAX_COMPRESSED or len(compressed) != maximum:
        raise ValueError("broker_prefix_bytes_outside_frozen_bound")
    content_range = prefix_meta["headers"].get("contentRange")
    content_length = prefix_meta["headers"].get("contentLength")
    if prefix_meta["status"] == 200 and (not isinstance(content_length, str)
            or not re.fullmatch(r"[0-9]+", content_length) or int(content_length) <= len(compressed)):
        raise ValueError("broker_content_length_does_not_prove_remaining_archive_bytes")
    if prefix_meta["status"] == 206 or content_range:
        match = re.fullmatch(r"bytes 0-(\d+)/(\d+)", str(content_range or ""))
        if not match or int(match[1]) != len(compressed) - 1 or int(match[2]) <= len(compressed):
            raise ValueError("broker_prefix_content_range_invalid")
    page_text = page.decode("utf-8")
    marker = license_info.get("marker")
    if not isinstance(marker, str) or not marker or len(marker) > 512 or marker not in page_text \
            or not ("CC0" in page_text or "https://creativecommons.org/publicdomain/zero/1.0/" in page_text):
        raise ValueError("broker_source_rights_declaration_missing")
    links = re.findall(r'href=["\']([^"\']*lichess_db_puzzle\.csv\.zst)["\']', page_text)
    if not any(urljoin(SOURCE_PAGE, html.unescape(link)) == SOURCE_PREFIX for link in links):
        raise ValueError("broker_official_puzzle_download_link_missing")
    response_meta = {"status": prefix_meta["status"], "url": SOURCE_PREFIX,
        "etag": prefix_meta["headers"].get("etag"), "last_modified": prefix_meta["headers"].get("lastModified"),
        "content_range": content_range,
        "broker": {"schema": receipt["schema"], "source": receipt["source"], "target": target,
            "retrieved_at": receipt["retrievedAt"], "receipt_file": "broker-receipt.json", "receipt_sha256": sha(raw),
            "hash_scope": "retained compressed prefix only; not the full upstream archive",
            "assurance": "Local consistency checks do not authenticate arbitrary receipt JSON; the retained native broker stdout and job receipt supply fetch provenance."}}
    return page, compressed, page_meta["status"], response_meta, raw


def acquire(out, from_broker=None, count=24, min_rating=None):
    import zstandard
    if from_broker is not None:
        _local_broker_path(from_broker)
        _local_broker_path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("intake_directory_not_empty_use_a_new_version")
    broker_receipt = None
    if from_broker is not None:
        page, compressed, page_status, response_meta, broker_receipt = _broker_inputs(from_broker)
        source_url = SOURCE_PREFIX
    else:
        headers = {"User-Agent": "PlayGroundResearch/1.0 (bounded CC0 research intake)"}
        with urlopen(Request(SOURCE_PAGE, headers=headers), timeout=30) as response:
            page = response.read(1024 * 1024)
            page_status = response.status
        page_text = page.decode("utf-8")
        if "CC0" not in page_text:
            raise ValueError("source_rights_declaration_missing")
        matches = re.findall(r'href=["\']([^"\']*lichess_db_puzzle\.csv\.zst)["\']', page_text)
        if not matches:
            raise ValueError("official_puzzle_download_link_missing")
        source_url = urljoin(SOURCE_PAGE, html.unescape(matches[0]))
        if urlparse(source_url).hostname != "database.lichess.org":
            raise ValueError("unexpected_download_host")
        headers["Range"] = f"bytes=0-{MAX_COMPRESSED - 1}"
        with urlopen(Request(source_url, headers=headers), timeout=45) as response:
            compressed = response.read(MAX_COMPRESSED)
            response_meta = {"status": response.status, "url": response.url,
                             "etag": response.headers.get("ETag"),
                             "last_modified": response.headers.get("Last-Modified"),
                             "content_range": response.headers.get("Content-Range")}
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(compressed)) as reader:
        decoded = reader.read(MAX_DECOMPRESSED + 1)
    if len(decoded) > MAX_DECOMPRESSED:
        raise ValueError("decompressed_prefix_exceeds_budget")
    # The compressed prefix may end mid-record. Ignore only that incomplete last line.
    text = decoded[:decoded.rfind(b"\n") + 1].decode("utf-8")
    selected = select_rows(text)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(selected[0][0]))
    writer.writeheader()
    writer.writerows(row for row, _ in selected)
    sample = buffer.getvalue().encode()
    files = {"source-page.html": page, "source-prefix.csv.zst.part": compressed, "sample.csv": sample}
    if broker_receipt is not None:
        files["broker-receipt.json"] = broker_receipt
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    manifest = {
        "schema": "chess-real-seed/v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url, "source_page": SOURCE_PAGE, "source_page_status": page_status,
        "license": "CC0-1.0", "license_source": SOURCE_PAGE,
        "acquisition": response_meta, "compressed_bytes_retained": len(compressed),
        "full_database_downloaded": False, "hash_scope": "retained prefix and selected CSV, not full upstream archive",
        "selection": "First 24 distinct game IDs and positions in complete prefix rows; convenience sample, not representative",
        "split_rule": "Sort SHA256('lichess-seed-v1:'+game_id), assign exactly 8 train / 8 dev / 8 test",
        "test_policy": "Legality/integrity inspection only; no engine, model, tuning or outcome scoring on test",
        "files": {name: {"sha256": sha(data), "bytes": len(data)} for name, data in files.items()},
        "items": [derived for _, derived in selected],
    }
    save(out / "manifest.json", manifest)
    return verify(out)


def verify(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "chess-real-seed/v1" or manifest.get("license") != "CC0-1.0":
        raise ValueError("invalid_manifest_contract")
    for name in ("source-page.html", "source-prefix.csv.zst.part", "sample.csv"):
        data = (directory / name).read_bytes()
        if manifest["files"].get(name) != {"sha256": sha(data), "bytes": len(data)}:
            raise ValueError("source_hash_mismatch:" + name)
    if "broker" in manifest.get("acquisition", {}):
        raw = _broker_file_bytes(directory / "broker-receipt.json", 128 * 1024)
        if manifest["files"].get("broker-receipt.json") != {"sha256": sha(raw), "bytes": len(raw)} \
                or manifest["acquisition"]["broker"].get("receipt_sha256") != sha(raw):
            raise ValueError("broker_receipt_hash_mismatch")
    source_rows = select_rows((directory / "sample.csv").read_text(encoding="utf-8"))
    if [derived for _, derived in source_rows] != manifest["items"]:
        raise ValueError("manifest_does_not_match_legal_source_replay")
    # Recover the selected rows from retained original bytes, not only the derived CSV.
    import zstandard
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO((directory / "source-prefix.csv.zst.part").read_bytes())) as reader:
        decoded = reader.read(MAX_DECOMPRESSED + 1)
    if len(decoded) > MAX_DECOMPRESSED:
        raise ValueError("decompressed_prefix_exceeds_budget")
    original = select_rows(decoded[:decoded.rfind(b"\n") + 1].decode())
    if original != source_rows:
        raise ValueError("selected_sample_not_bound_to_original_prefix")
    return {"passed": True, "real_games": len(source_rows),
            "replayed_plies": sum(len(item["legal_replay"]) for _, item in source_rows),
            "split_counts": dict(Counter(item["split"] for _, item in source_rows)),
            "manifest_sha256": sha((directory / "manifest.json").read_bytes()),
            "synthetic_items": 0, "test_outcomes_scored": 0}


def transition_facts(fen, uci):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("invalid_board")
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise ValueError("illegal_candidate_move")
    piece = board.piece_at(move.from_square)
    facts = {"piece": chess.piece_name(piece.piece_type), "from": chess.square_name(move.from_square),
             "to": chess.square_name(move.to_square), "san": board.san(move),
             "capture": board.is_capture(move), "en_passant": board.is_en_passant(move),
             "castling": board.is_castling(move), "promotion": chess.piece_name(move.promotion) if move.promotion else None}
    board.push(move)
    facts.update({"gives_check": board.is_check(), "checkmate": board.is_checkmate(), "fen_after": board.fen()})
    facts["template"] = (f"{facts['san']}: {facts['piece']} from {facts['from']} to {facts['to']}. "
                         f"Capture: {facts['capture']}. Check: {facts['gives_check']}. Checkmate: {facts['checkmate']}.")
    facts["claim_boundary"] = "Deterministic board facts only; strategic rationale and teaching usefulness not assessed"
    return facts


def engine_result(engine, board, nodes, game_token):
    info = engine.analyse(board, chess.engine.Limit(nodes=nodes), game=game_token)
    pv = info.get("pv", [])
    if not pv:
        raise ValueError("engine_returned_no_line")
    replay = board.copy(stack=True)
    for move in pv:
        if move not in replay.legal_moves:
            raise ValueError("engine_returned_illegal_line")
        replay.push(move)
    score = info["score"].pov(board.turn)
    return {"move_uci": pv[0].uci(), "pv_uci": [move.uci() for move in pv],
            "score_perspective": "side_to_move", "score_cp": score.score(), "mate_in": score.mate(),
            "nodes_requested": nodes, "nodes_observed": info.get("nodes"),
            "depth": info.get("depth"), "time_seconds": info.get("time"),
            "facts": transition_facts(board.fen(), pv[0].uci())}


def baseline(directory, engine_path, output):
    verification = verify(directory)
    if output.exists():
        raise ValueError("baseline_output_exists_use_a_new_version")
    manifest = json.loads((directory / "manifest.json").read_text())
    rows, cases = [], [item for item in manifest["items"] if item["split"] == "dev"]
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(engine_path), timeout=30)
    except Exception as e:
        raise ValueError("invalid_engine_binary: " + str(e))
    identity = dict(engine.id)
    disabled_reason = None
    try:
        engine.configure({"Threads": 1, "Hash": 16})
        for case in cases:
            row = {"position_id": case["position_id"], "split": "dev", "fen": case["fen"],
                   "target_move": case["target_move"], "source_url": case["game_url"], "runs": {}}
            for nodes in (10000, 100000):
                if disabled_reason:
                    row["runs"][str(nodes)] = {"not_run": True, "reason": disabled_reason}
                    continue
                try:
                    # Only the legal position and setup history reach the engine, never target/theme labels.
                    board = chess.Board(case["source_fen"])
                    board.push_uci(case["setup_move"])
                    result = engine_result(engine, board, nodes, object())
                    result["matches_published_solution"] = result["move_uci"] == case["target_move"]
                    result["accepted_solution"] = result["matches_published_solution"] or (
                        "mateIn1" in case["themes"] and result["facts"]["checkmate"])
                    row["runs"][str(nodes)] = result
                except Exception as error:
                    row["runs"][str(nodes)] = {"failed": True, "error_type": type(error).__name__, "error": str(error)}
                    disabled_reason = "Engine packet stopped after " + type(error).__name__ + "; diagnose before a distinct repair run"
            rows.append(row)
    finally:
        try:
            engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
    summary = {}
    for nodes in (10000, 100000):
        runs = [row["runs"][str(nodes)] for row in rows]
        summary[str(nodes)] = {"requested": len(cases), "completed": sum("move_uci" in r for r in runs),
                               "accepted_solution": sum(r.get("accepted_solution", False) for r in runs),
                               "exact_solution_match": sum(r.get("matches_published_solution", False) for r in runs)}
    result = {"schema": "chess-real-baseline/v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "intake_verification": verification, "script_sha256": sha(Path(__file__).read_bytes()),
              "engine": {"id": identity, "binary_sha256": sha(engine_path.read_bytes()),
                         "python_chess_version": chess.__version__, "threads": 1, "hash_mb": 16,
                         "local_path": str(engine_path), "source": "https://github.com/official-stockfish/Stockfish"},
              "summary": summary, "cases": rows, "test_outcomes_scored": 0, "model_calls": 0,
              "limitations": ["Eight development puzzles from a convenience sample; not a general chess benchmark.",
                              "Published solution matching is a source agreement measure, not human teaching usefulness.",
                              "Themes are machine labels; no claim of trained concept quality or sports transfer.",
                              "Historical game state before the puzzle FEN is unavailable; repetition claims are excluded."]}
    save(output, result)
    return {"output": str(output), "summary": summary, "test_outcomes_scored": 0}


def report(baseline_path, output):
    data = json.loads(baseline_path.read_text())
    cards = []
    for case in data["cases"]:
        runs = html.escape(json.dumps(case["runs"], indent=2))
        cards.append(f"<article><h2>{html.escape(case['position_id'])}</h2>"
                     + chess.svg.board(chess.Board(case["fen"]), size=300)
                     + f"<p><a href='{html.escape(case['source_url'], quote=True)}'>Original game</a></p><pre>{runs}</pre></article>")
    output.write_text("<!doctype html><meta charset='utf-8'><title>Real chess development baseline</title>"
                      "<style>body{font:16px system-ui;background:#fafafa;color:#17202a;max-width:1100px;margin:2rem auto}"
                      "article{background:white;border:1px solid #ddd;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap}"
                      "svg{float:left;margin-right:2rem}article:after{content:'';display:block;clear:both}</style>"
                      "<h1>Real chess development baseline</h1><p>24 real CC0 Lichess puzzles; eight development positions scored. "
                      "Test positions remain unscored. Local Stockfish only; board descriptions are deterministic facts.</p>"
                      + "<pre>" + html.escape(json.dumps(data["summary"], indent=2)) + "</pre>"
                      + "".join(cards), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    intake = subs.add_parser("acquire")
    intake.add_argument("--data", type=Path, required=True)
    intake.add_argument("--from-broker", type=Path, help="Import retained broker receipt and bytes without any network access")
    subs.add_parser("verify").add_argument("--data", type=Path, required=True)
    run = subs.add_parser("baseline")
    run.add_argument("--data", type=Path, required=True)
    run.add_argument("--engine", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    render = subs.add_parser("report")
    render.add_argument("--baseline", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire": result = acquire(args.data, from_broker=args.from_broker)
    elif args.command == "verify": result = verify(args.data)
    elif args.command == "baseline": result = baseline(args.data, args.engine.resolve(), args.output)
    else:
        report(args.baseline, args.output)
        result = {"report": str(args.output)}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
