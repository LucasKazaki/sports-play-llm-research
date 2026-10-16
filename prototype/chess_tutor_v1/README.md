# Chess study candidate v1

A working local board for tutor feedback. Load a standard FEN or one PGN, play
legal moves, navigate the game, inspect Stockfish alternatives, and preview a
legally replayed engine continuation. Ask Queen for a separate local explanation
draft, with its raw move and legally replayed line kept visible. Queen's prose is
unverified and can include incorrect moves and false board claims. The Stockfish
panel contains deterministic facts and bounded engine observations; its checks
do not verify Queen's prose. Strategic coaching quality is unmeasured. This
candidate has not passed the repository's independent
shareable-candidate promotion or no-forward commentary gates.

From the repository root, run `./scripts/start-chess-tutor.ps1`, then open
<http://127.0.0.1:8793/>. Ctrl+C stops its owned processes. `-NoModel` disables the
CPU move classifier; `-NoCoaching` disables Queen. Use both switches for only the
engine-assisted view. `-ModelDir` chooses an explicit local native classifier
checkpoint. The default is the historical v3 step-512 experimental candidate,
selected on development before its holdout was opened. No automatic checkpoint
promotion, downloads, Ollama calls, or training occurs. Queen uses the GPU only
after the manual explanation action. Running `server.py` directly requires
`--queen` to enable it; it otherwise remains off.

Queen is the separately versioned `queen-pawn-8/native-nf4-v2` candidate. Every
request starts a short-lived process through the existing shared GPU lease.
The frozen settings are deterministic no-cache/math attention, 1,024 new tokens
and 240 seconds of generation, with 4 GiB physical/commit and 1 GiB GPU running
reserves. The wrapper has a 270-second deadline. A busy lease starts no model;
there is no queue, automatic retry or fallback. Cancellation writes only this
request's `response.CANCEL` and stays stopping until the process exits.

`queen-runtime.json` binds the actual matching kernel/protocol, no-cache
canonical parity/protocol, four complete authored EOS responses, closed worker
receipts, source and publisher manifests. Metadata/source verification runs
before each launch without importing a model. These are runtime software checks,
not proof of playing strength or teaching value. The actual authored mate draft
already includes a false pawn-protection claim and an illegal prose alternative.
The first structured move is legal; that does not validate its explanation.

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

`POST /api/coach` accepts `{"position":{"fen":"root FEN","moves":[]}}` and
optional `selected_uci` plus `selected_move_origin` metadata. The server legally
replays only the line to the selected board and creates a model packet with
current FEN, actual prior FENs and the optional legal selected move. No engine
evaluation, PV, future board, annotations or labels enter that packet. The
selected-move UI explicitly says when Stockfish's chosen move was supplied.
`GET /api/coach/<opaque request ID>` polls; `POST /api/coach/<ID>/cancel` takes
`{}`. The board and engine remain usable while Queen runs. Earlier answers stay
attached to their original line with an explicit return action. Response/raw
tokens, errors, truncation and actual backend metadata remain retained under
ignored `data/private/chess-tutor-v1/coaching/`. A resource or provenance failure
blocks new coaching requests until reviewed. Only 32 public job records remain
in memory; their private receipts are not automatically deleted. Export includes
coaching only when its original line matches the current analyzed position.

Safety bounds: loopback bind, Host/Origin checks, same-origin policy, a fixed
static file allowlist, no arbitrary file access, 32 KB HTTP/24 KB PGN input limits,
512 total mainline/played plies, standard chess only. PGN variations are
skipped. Each engine request uses at most two CPU threads, 32 MB hash, and a
target limit of at most 50,000 nodes or 1.5 seconds of search. Stockfish can
slightly overshoot a node target; the actual candidate node counts are retained.
Board analyses are serialized; 32 analyses are cached in memory only. User PGN bodies
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
