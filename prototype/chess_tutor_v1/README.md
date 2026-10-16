# Chess study candidate v1

A working local board for tutor feedback. Load a standard FEN or one PGN, play
legal moves, navigate the game, inspect Stockfish alternatives, and preview a
legally replayed engine continuation. All explanations are deterministic board
facts and typed, bounded engine observations. Strategic coaching quality is
unmeasured. This candidate has not passed the repository's independent
shareable-candidate promotion or no-forward commentary gates.

From the repository root, run `./scripts/start-chess-tutor.ps1`, then open
<http://127.0.0.1:8793/>. Ctrl+C stops its owned process. `-NoModel` starts only the
engine-assisted study view. `-ModelDir` chooses an explicit local native classifier
checkpoint. The default is the historical v3 step-512 experimental candidate,
selected on development before its holdout was opened. No automatic checkpoint
promotion, downloads, GPU use, Ollama calls, or training occurs.

The move classifier is loaded lazily on CPU with two threads and only audited
native FEN encoding. Its three-ply rollout completes **before** engine analysis.
Every call receives only its current pre-move FEN. Raw illegal output stops the
line; legal filtering is reported separately and never replaces the raw choice.
The UI shows the exact shared prefix of this bounded root engine PV. After a
divergence it does not compare later moves as if the positions still matched.
No per-ply teacher search is performed. Logits are neither probabilities nor
engine evaluations. Three plies are three half-moves.

`POST /api/analyze` accepts `{"fen":"...","moves":["e2e4"],"model":true}` or
`{"pgn":"1. e4 e5 *","ply":1,"model":false}`. A response has schema
`chess.tutor-candidate.v1`, `board`, `history`, `selected_ply`, `source`, `engine`,
`model`, and `limitations`. Engine alternatives carry score type, perspective,
same-info-event bounds, legal PV replay, and typed immediate board facts.
Terminal boards and model/engine errors stay visible. User game origins are
unverified. Exploration is never reported as held-out evaluation.

Safety bounds: loopback bind, Host/Origin checks, same-origin policy, a fixed
static file allowlist, no dynamic file reads, 32 KB HTTP/24 KB PGN input limits,
512 total mainline/played plies, standard chess only. PGN variations are
skipped. Each engine request uses at most two CPU threads, 32 MB hash, and a
target limit of at most 50,000 nodes or 1.5 seconds of search. Stockfish can
slightly overshoot a node target; the actual candidate node counts are retained.
Requests are serialized; 32 analyses are cached in memory only. User PGN bodies
are not logged. The save action creates a local evidence JSON in the browser.
Python-chess and Stockfish remain subject to their existing GPL notices; this
local candidate redistributes neither engine binaries nor model weights.

PGN and played-line history is retained for automatic fivefold-repetition and
75-move draws. Claimable threefold/50-move draws are not claimed automatically.
A standalone FEN has no repetition history. Immediate attack facts are checked
on the resulting board and omit pinned movers; they do not claim a material win.

Verification uses `.venv-soccernet/Scripts/python.exe -m pytest
tests/test_chess_tutor_v1.py -q`. Software tests and browser QA demonstrate this
interface's behavior, not chess expertise, model calibration, or teaching value.
