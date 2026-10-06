# Chess evidence review v1

This is an offline, local study page for the eight real **development** positions
in the CC0 Lichess seed. It shows the source game, the board before and after a
selected legal move, a second searched move, typed Stockfish observations,
checkable board facts, and the saved local model's validation result. It makes
no model, engine, or network calls when opened.

Open [the generated page](../artifacts/chess-evidence-review-v1/index.html) in
a local browser. Select a case in the left navigation. The original player is
at the bottom of both boards. Open the source-game link to inspect Lichess.
The engine line is collapsed and clearly marked as evaluator-only material.

From the repository root, rebuild to a **new** path with the installed Python
environment:

```text
.venv-soccernet/Scripts/python.exe scripts/chess_real_evidence_interface.py build --output artifacts/chess-evidence-review-v1/my-rebuild.html
.venv-soccernet/Scripts/python.exe scripts/chess_real_evidence_interface.py verify --output artifacts/chess-evidence-review-v1/my-rebuild.html
```

`build` refuses to overwrite an existing file. `verify` rechecks the frozen
source receipt, development projection, typed evidence, saved model capture,
output-validation report, and exact page bytes. Run the focused checks with:

```text
.venv-soccernet/Scripts/python.exe -m pytest -q tests/test_chess_real_evidence_interface.py tests/test_chess_typed_position_evidence.py tests/test_chess_no_forward_output_validator.py
```

The page is useful for evidence inspection. It is **not** a validated chess
commentator: the saved eight model calls produced six untyped prose replies
and two transport failures, so zero model claim sets were admitted. The
sample is small and selected, there is no fresh game-disjoint heldout
commentary result, and no qualified chess reviewer has approved teaching
quality. Board facts are deterministic, while engine scores are bounded-search
observations rather than proofs. See
[the capability gate](../research/chess-commentary-capability-gate-v1.md)
before using this page as research or release evidence.

Implementation: [page builder](../scripts/chess_real_evidence_interface.py),
[styles](chess_evidence_review.css), and
[checks](../tests/test_chess_real_evidence_interface.py). The page was built
from saved data; no live-game assistance is provided.

## Review one move from your own completed game

Save a **completed standard-chess game** as a UTF-8 PGN with one game and a
declared result. The local tool rejects unfinished games, variants, parse
errors, and files over 2 MiB. It does not use a model or send the PGN online.
To see the output first, open the
[saved checkmate demonstration](../artifacts/chess-completed-game-review-v2/synthetic-demo/index.html).
Its four-move game is synthetic and demonstrates the software only; the
eight-case page above contains the real development positions.

List numbered moves, then choose a ply from the first column:

```text
.venv-soccernet/Scripts/python.exe scripts/chess_review_completed_game.py doctor
.venv-soccernet/Scripts/python.exe scripts/chess_review_completed_game.py moves --pgn C:/path/to/completed-game.pgn
.venv-soccernet/Scripts/python.exe scripts/chess_review_completed_game.py review --pgn C:/path/to/completed-game.pgn --ply 27 --output-dir artifacts/chess-user-reviews/my-first-review
.venv-soccernet/Scripts/python.exe scripts/chess_review_completed_game.py verify --pgn C:/path/to/completed-game.pgn --output-dir artifacts/chess-user-reviews/my-first-review
```

Open the new `index.html` in that output directory. The page includes the
played move, before/after boards, one separately searched alternative when
available, exact rule facts, the full move list, and a downloadable annotated
PGN. The v2 JSON receipt retains every PGN header, the source PGN hash, engine identity, search
settings, scores with perspective and bound, observed node counts, and legal
engine lines. Each search requests 10,000 nodes by default; `--nodes` accepts
1,000–100,000. The output directory is create-only to preserve earlier reviews.

The actual played move is searched with its root move restricted; the other
move comes from a separate unrestricted search. Their scores are estimates
under different searches and are shown without a superiority claim. The
annotated PGN marks the engine evidence as a trace rather than a human lesson.
The user's PGN result is a completion declaration; the tool cannot independently
establish whether an external game is over. Use it only after a game has ended.

Implementation and checks:
[post-game review tool](../scripts/chess_review_completed_game.py) and
[post-game tests](../tests/test_chess_review_completed_game.py). The local
Stockfish 19 binary is pinned by SHA-256; its GPL notices must be preserved
if the tool is distributed.
