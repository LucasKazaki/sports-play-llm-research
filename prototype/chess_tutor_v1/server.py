"""Local chess study candidate. Engine facts and raw model output stay separate.

This server neither trains models nor sends inputs to a remote service. The move
classifier sees FEN tokens only. Its rollout completes before engine evaluation.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import sys
import threading
import time

import chess
import chess.engine
import chess.pgn

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_ENGINE = ROOT / "data/private/chess-distill-v1/tools/stockfish/stockfish-windows-x86-64-universal.exe"
MAX_BODY = 32_768
MAX_PLIES = 512
SCHEMA = "chess.tutor-candidate.v1"


class InputError(ValueError):
    pass


def checked_board(fen):
    if type(fen) is not str or len(fen) > 256 or len(fen.split()) != 6:
        raise InputError("Paste a complete six-field FEN position.")
    try:
        board = chess.Board(fen, chess960=False)
    except ValueError as exc:
        raise InputError("The FEN could not be read. Check the pieces, turn, and move counters.") from exc
    if not board.is_valid():
        raise InputError("This is not a valid standard chess position. Check both kings and the side to move.")
    if board.fullmove_number > 999_999 or board.halfmove_clock > 999_999:
        raise InputError("The FEN move counters exceed the study limit.")
    return board


class StrictGameBuilder(chess.pgn.GameBuilder):
    def begin_game(self):
        self.move_count = 0
        return super().begin_game()

    def visit_move(self, board, move):
        self.move_count += 1
        if self.move_count > MAX_PLIES:
            raise InputError("This game exceeds the 512-ply study limit.")
        return super().visit_move(board, move)

    def handle_error(self, error):
        raise InputError("The PGN contains an illegal or unreadable move. Use standard chess PGN.") from error

    def begin_variation(self):
        # The explorer imports the main line only. Skip rather than allocate
        # arbitrary nested variation trees from untrusted pasted input.
        return chess.pgn.SKIP

    def end_variation(self):
        pass


def parse_position(payload):
    if type(payload) is not dict or set(payload) - {"fen", "pgn", "ply", "moves", "model"}:
        raise InputError("Use a FEN or PGN, with an optional move index and legal moves.")
    if "fen" in payload and "pgn" in payload:
        raise InputError("Load either FEN or PGN at one time.")
    history = []
    source = {"kind": "user_position", "label": "Supplied position", "provenance": "User input; no game origin is verified."}
    if "pgn" in payload:
        text = payload["pgn"]
        if type(text) is not str or not text.strip() or len(text.encode("utf-8")) > 24_000:
            raise InputError("Paste one PGN game, up to 24 KB.")
        stream = io.StringIO(text)
        try:
            game = chess.pgn.read_game(stream, Visitor=StrictGameBuilder)
            if game is None:
                raise InputError("No PGN game was found.")
            if not game.variations and not re.search(r'^\s*\[\w+\s+"', text, re.MULTILINE):
                raise InputError("No chess moves or PGN headers were found. Paste a complete FEN or standard PGN.")
            if game.headers.get("Variant", "Standard").lower() not in ("standard", "chess"):
                raise InputError("Only standard chess PGN is supported.")
            board = checked_board(game.board().fen())
            history.append({"fen": board.fen(), "san": "Start", "uci": None})
            for move in game.mainline_moves():
                if len(history) > MAX_PLIES:
                    raise InputError("This game exceeds the 512-ply study limit.")
                if move not in board.legal_moves:
                    raise InputError("The PGN contains an illegal move.")
                if board.is_game_over(claim_draw=False):
                    raise InputError("The PGN continues after an automatic game-ending position.")
                san = board.san(move)
                board.push(move)
                history.append({"fen": board.fen(), "san": san, "uci": move.uci()})
            if chess.pgn.read_game(stream, Visitor=StrictGameBuilder) is not None:
                raise InputError("Load one PGN game at a time.")
        except InputError:
            raise
        except (ValueError, KeyError, IndexError) as exc:
            raise InputError("The PGN could not be read. Check its headers and move text.") from exc
        source.update(kind="user_pgn", label="Supplied PGN", headers={key: str(game.headers.get(key, ""))[:160] for key in ("White", "Black", "Event", "Date", "Result")})
    else:
        board = checked_board(payload.get("fen", chess.STARTING_FEN))
        history.append({"fen": board.fen(), "san": "Start", "uci": None})
    ply = payload.get("ply", len(history)-1)
    if type(ply) is not int or not 0 <= ply < len(history):
        raise InputError("Choose a move within this game.")
    # Rebuild from the root rather than a selected FEN: a FEN cannot encode
    # repetition history, and automatic fivefold draws depend on that history.
    board = checked_board(history[0]["fen"])
    for step in history[1:ply+1]:
        board.push_uci(step["uci"])
    moves = payload.get("moves", [])
    if type(moves) is not list or len(moves) + ply > MAX_PLIES:
        raise InputError("Study at most 512 plies in one line.")
    if moves:
        history = history[:ply+1]
    for text in moves:
        if type(text) is not str or not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", text):
            raise InputError("Use coordinate moves such as e2e4 or a7a8q.")
        move = chess.Move.from_uci(text)
        if board.is_game_over(claim_draw=False):
            raise InputError("The game is already over. Return to an earlier move to explore another line.")
        if move not in board.legal_moves:
            raise InputError(f"{text} is not legal in this position.")
        san = board.san(move)
        board.push(move)
        history.append({"fen": board.fen(), "san": san, "uci": text})
        ply += 1
    if "model" in payload and type(payload["model"]) is not bool:
        raise InputError("The model option must be true or false.")
    return board, history, ply, source


def board_record(board):
    outcome = board.outcome(claim_draw=False)
    status = "Checkmate" if board.is_checkmate() else "Stalemate" if board.is_stalemate() else "Game over" if outcome else "Check" if board.is_check() else "Ready"
    return {"fen": board.fen(), "turn": "white" if board.turn else "black", "status": status,
            "terminal": outcome is not None, "result": outcome.result() if outcome else None,
            "termination": outcome.termination.name.lower() if outcome else None,
            "pieces": {chess.square_name(square): piece.symbol() for square, piece in board.piece_map().items()},
            "legal_moves": [] if outcome else [{"uci": move.uci(), "san": board.san(move)} for move in board.legal_moves]}


def move_facts(board, move):
    if move not in board.legal_moves:
        raise InputError("Cannot explain an illegal move.")
    piece = board.piece_at(move.from_square)
    colour = "White" if board.turn else "Black"
    origin, target = chess.square_name(move.from_square), chess.square_name(move.to_square)
    facts = [{"type": "board_fact", "kind": "movement", "text": f"{colour} moves the {chess.piece_name(piece.piece_type)} from {origin} to {target}.", "squares": [origin, target]}]
    if board.is_capture(move):
        capture_square = move.to_square + (-8 if board.turn else 8) if board.is_en_passant(move) else move.to_square
        captured = board.piece_at(capture_square)
        facts.append({"type": "board_fact", "kind": "capture", "text": f"The move captures the {chess.piece_name(captured.piece_type)} on {chess.square_name(capture_square)}" + (" en passant." if board.is_en_passant(move) else "."), "squares": [chess.square_name(capture_square)]})
    if board.is_castling(move):
        facts.append({"type": "board_fact", "kind": "castling", "text": f"{colour} castles {'kingside' if board.is_kingside_castling(move) else 'queenside'}.", "squares": []})
    if move.promotion:
        facts.append({"type": "board_fact", "kind": "promotion", "text": f"The pawn promotes to a {chess.piece_name(move.promotion)}.", "squares": [target]})
    after = board.copy()
    after.push(move)
    # A static attack is evidence of pressure, not proof of a material win.
    # Omit pinned movers, whose geometric targets can be illegal captures.
    if not after.is_pinned(board.turn, move.to_square):
        targets = []
        for square in after.attacks(move.to_square):
            victim = after.piece_at(square)
            if victim and victim.color != board.turn and victim.piece_type != chess.KING:
                targets.append((victim.piece_type, square, victim))
        targets.sort(key=lambda item: (-item[0], item[1]))
        for _, square, victim in targets[:2]:
            moved = after.piece_at(move.to_square)
            enemy = "black" if victim.color == chess.BLACK else "white"
            facts.append({"type": "board_fact", "kind": "attack", "text": f"From {target}, the {chess.piece_name(moved.piece_type)} attacks the {enemy} {chess.piece_name(victim.piece_type)} on {chess.square_name(square)}.", "squares": [target, chess.square_name(square)], "qualification": "Immediate attack only; this does not establish that material can be won."})
    if after.is_checkmate():
        facts.append({"type": "board_fact", "kind": "checkmate", "text": "This move is checkmate: the opposing king is in check and has no legal reply.", "squares": [chess.square_name(after.king(after.turn))]})
    elif after.is_stalemate():
        facts.append({"type": "board_fact", "kind": "stalemate", "text": "This move leaves stalemate: the opponent has no legal move and is not in check.", "squares": []})
    elif after.is_game_over(claim_draw=False):
        reason = {"SEVENTYFIVE_MOVES": "75-move rule", "FIVEFOLD_REPETITION": "fivefold repetition", "INSUFFICIENT_MATERIAL": "insufficient material"}.get(after.outcome().termination.name, "automatic draw rule")
        facts.append({"type": "board_fact", "kind": "draw", "text": f"This move ends the game in a draw ({reason}).", "squares": []})
    elif after.is_check():
        facts.append({"type": "board_fact", "kind": "check", "text": "This move gives check. The opponent must answer the check.", "squares": [chess.square_name(after.king(after.turn))]})
    else:
        facts.append({"type": "board_fact", "kind": "reply_count", "text": f"After this move, the opponent has {after.legal_moves.count()} legal replies.", "squares": []})
    return facts


def score_record(info, turn):
    score = info.get("score")
    if score is None:
        return None
    point = score.pov(turn)
    return {"type": "engine_observation", "kind": "mate" if point.is_mate() else "centipawn", "value": point.mate() if point.is_mate() else point.score(),
            "perspective": "white" if turn else "black", "bound": "lower" if info.get("lowerbound") else "upper" if info.get("upperbound") else "exact",
            "qualification": "Bounded search estimate; not a guarantee of perfect play or a teaching judgment."}


class Engine:
    def __init__(self, path=DEFAULT_ENGINE, nodes=30_000):
        self.path = Path(path)
        self.nodes = max(1_000, min(int(nodes), 50_000))
        self.identity = None

    def analyze(self, board, alternatives=3):
        if board.is_game_over(claim_draw=False):
            return {"status": "terminal", "name": "Stockfish", "alternatives": []}
        started = time.monotonic()
        latest = {}
        # Per-request process avoids mixing concurrent games or stale bounds.
        with chess.engine.SimpleEngine.popen_uci(str(self.path), timeout=5.0) as engine:
            self.identity = dict(engine.id)
            engine.configure({"Threads": 2, "Hash": 32})
            with engine.analysis(board, chess.engine.Limit(nodes=self.nodes, time=1.5), multipv=min(alternatives, board.legal_moves.count())) as search:
                for info in search:
                    # Keep score/bounds/PV from one real info event, never merge
                    # a stale bound flag from an earlier search iteration.
                    if "score" in info and info.get("pv"):
                        latest[info.get("multipv", 1)] = dict(info)
        rows = []
        for rank in sorted(latest):
            info = latest[rank]
            replay = board.copy()
            pv = []
            for move in info["pv"][:6]:
                if move not in replay.legal_moves:
                    raise RuntimeError("Engine returned a continuation that failed legal replay.")
                san = replay.san(move)
                replay.push(move)
                pv.append({"uci": move.uci(), "san": san, "fen": replay.fen()})
            first = chess.Move.from_uci(pv[0]["uci"])
            rows.append({"rank": rank, "move_uci": first.uci(), "san": pv[0]["san"], "score": score_record(info, board.turn),
                         "depth": info.get("depth"), "nodes": info.get("nodes"), "pv": pv, "facts": move_facts(board, first)})
        if not rows:
            raise RuntimeError("Engine completed without a scored legal move.")
        return {"status": "ok", "name": self.identity.get("name", "Stockfish"), "budget": {"max_nodes": self.nodes, "max_seconds": 1.5, "threads": 2, "hash_mb": 32},
                "score_perspective": "white" if board.turn else "black", "elapsed_seconds": round(time.monotonic()-started, 3), "alternatives": rows,
                "assistance": "Every continuation below is Stockfish-assisted and legally replayed. It is not a model prediction."}


class Classifier:
    """Explicit, local CPU-only model; FEN is the sole inference input."""
    def __init__(self, path=None):
        self.path = Path(path).resolve() if path else None
        self.model = self.contract = self.torch = None
        self.identity = None

    def _load(self):
        if self.model is not None:
            return
        import torch
        from transformers import LlamaForSequenceClassification
        sys.path.insert(0, str(ROOT / "scripts"))
        from chess_classifier_adapter import load_native_contract
        self.contract = load_native_contract(self.path)
        torch.set_num_threads(2)
        self.model = LlamaForSequenceClassification.from_pretrained(str(self.path), local_files_only=True, trust_remote_code=False, attn_implementation="sdpa").float().to("cpu").eval()
        self.torch = torch
        self.identity = {"name": "ROOK-CLF-9m · local checkpoint", "directory": str(self.path), "weight_sha256": hashlib.sha256((self.path / "model.safetensors").read_bytes()).hexdigest(), "device": "cpu", "input": "Current pre-move FEN only; no engine move, PV, or post-move board."}

    def rank(self, fen):
        self._load()
        from chess_classifier_adapter import encode_fen, rank_logits
        encoded = encode_fen(fen, self.contract)
        inputs = {key: self.torch.tensor([value], dtype=self.torch.long, device="cpu") for key, value in encoded.items()}
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits[0].float().cpu().tolist()
        return rank_logits(fen, logits, self.contract["id2label"], top_k=3)

    def rollout(self, board):
        if not self.path:
            return {"status": "disabled", "reason": "No local classifier was configured at launch.", "predictions": [], "interventions": 0}
        start = time.monotonic()
        replay = board.copy()
        steps = []
        result = {"status": "ok", "predictions": steps, "interventions": 0, "assistance": "Raw model choices only. An illegal choice stops the line; no engine fallback or legal-mask replacement."}
        try:
            for ply in range(3):
                if replay.is_game_over(claim_draw=False):
                    result["stop_reason"] = "game_over"
                    break
                before = replay.fen()
                ranking = self.rank(before)
                accepted = ranking["raw_choice_is_legal"]
                step = {"ply": ply+1, "fen_before": before, **ranking, "accepted": accepted, "san": None}
                steps.append(step)
                if not accepted:
                    result["stop_reason"] = "raw_illegal_move"
                    break
                move = chess.Move.from_uci(ranking["raw_choice_uci"])
                step["san"] = replay.san(move)
                replay.push(move)
                step["fen_after"] = replay.fen()
            result.setdefault("stop_reason", "three_plies_complete")
        except Exception as exc:
            # Preserve earlier predictions and the failed case; never replace
            # failure with an engine-selected move or silently drop the ply.
            result.update(status="error", stop_reason="model_error", error=f"{type(exc).__name__}: {str(exc)[:240]}")
        result["identity"] = self.identity
        result["elapsed_seconds"] = round(time.monotonic()-start, 3)
        return result


class Tutor:
    def __init__(self, engine=None, classifier=None):
        self.engine = engine or Engine()
        self.classifier = classifier or Classifier()
        self.lock = threading.Lock()
        self.cache = OrderedDict()

    def analyze(self, payload):
        board, history, ply, source = parse_position(payload)
        use_model = payload.get("model", True)
        key = (board.root().fen(), tuple(move.uci() for move in board.move_stack), board.fen(), use_model)
        with self.lock:
            if key in self.cache:
                engine, model = self.cache[key]
                self.cache.move_to_end(key)
            else:
                model = self.classifier.rollout(board) if use_model else {"status": "disabled", "reason": "Model predictions are turned off.", "predictions": [], "interventions": 0}
                try:
                    engine = self.engine.analyze(board)
                except Exception as exc:
                    engine = {"status": "error", "name": "Stockfish", "error": f"{type(exc).__name__}: {str(exc)[:240]}", "alternatives": []}
                if model.get("status") == "ok" and model["predictions"] and engine.get("alternatives"):
                    top = engine["alternatives"][0]
                    model = dict(model)
                    model["root_raw_matches_engine"] = model["predictions"][0]["raw_choice_uci"] == top["move_uci"]
                    model["root_legal_filtered_matches_engine"] = model["predictions"][0]["legal_choice_uci"] == top["move_uci"]
                    prefix = 0
                    for prediction, step in zip(model["predictions"], top["pv"]):
                        if not prediction["accepted"] or prediction["raw_choice_uci"] != step["uci"]:
                            break
                        prefix += 1
                    model["exact_root_pv_prefix_plies"] = prefix
                    model["comparison_scope"] = "Exact prefix of this bounded root engine PV only. After a divergence, model-visited boards differ; later moves are not compared as if the positions matched. No per-ply teacher search is run."
                # A retry must be able to recover from a transient failure.
                if engine.get("status") != "error" and model.get("status") != "error":
                    self.cache[key] = (engine, model)
                    if len(self.cache) > 32:
                        self.cache.popitem(last=False)
        return {"schema_version": SCHEMA, "board": board_record(board), "history": history, "selected_ply": ply, "source": source,
                "engine": engine, "model": model, "limitations": ["Research candidate for chess tutor feedback; teaching quality has not been established.", "Explanations below are deterministic board facts and bounded engine observations. They do not establish a local model's strategic understanding.", "The move model is a classifier, not a prose coach. Three plies mean three individual half-moves, not three full turns.", "Loading or playing positions here is exploration, not held-out evaluation or training."]}


def handler_for(tutor):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ChessStudy/1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10.0)

        def _local(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                self._send(403, {"error": "This study is available on localhost only."})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed}:
                self._send(403, {"error": "Cross-site requests are not allowed."})
                return False
            return True

        def _send(self, status, value, kind="application/json; charset=utf-8"):
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8") if type(value) is dict else value
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._local():
                return
            path = self.path.split("?", 1)[0]
            if path == "/api/health":
                self._send(200, {"schema_version": SCHEMA, "status": "ready", "model_configured": tutor.classifier.path is not None, "engine_available": tutor.engine.path.is_file()})
                return
            files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if path not in files:
                self._send(404, {"error": "Page not found."})
                return
            name, mime = files[path]
            self._send(200, (STATIC / name).read_bytes(), mime+"; charset=utf-8")

        def do_POST(self):
            if not self._local():
                return
            if self.path != "/api/analyze":
                self._send(404, {"error": "Page not found."})
                return
            if self.headers.get_content_type() != "application/json":
                self._send(415, {"error": "Send the position as JSON."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    self._send(413, {"error": "The position exceeds the 32 KB request limit."})
                    return
                payload = json.loads(self.rfile.read(size))
                self._send(200, tutor.analyze(payload))
            except (InputError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                self._send(400, {"error": str(exc)[:280]})

        def log_message(self, fmt, *args):
            # Do not log user-supplied PGN or position bodies.
            sys.stderr.write("chess-tutor: " + fmt % args + "\n")
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8793)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--model-dir", type=Path, help="Explicit local native classifier checkpoint. Omit to keep inference off.")
    parser.add_argument("--nodes", type=int, default=30_000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535.")
    if not args.engine.is_file():
        parser.error("The local Stockfish executable was not found. Supply --engine.")
    tutor = Tutor(Engine(args.engine, args.nodes), Classifier(args.model_dir))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(tutor))
    server.daemon_threads = True
    print(f"Chess study candidate: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
