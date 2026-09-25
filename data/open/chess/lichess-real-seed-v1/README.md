# Real Lichess chess seed, v1

24 genuine game-derived puzzles, CC0-1.0, downloaded from the provider's linked
open export on 2026-09-19 UTC. `manifest.json` records acquisition URL, response
metadata, source-page snapshot, exact byte hashes and each legal replay.
`source-prefix.csv.zst.part` is deliberately only the first 262,144 bytes of the
upstream archive, not a complete zstd archive. Its hash is a prefix hash, never
the full dataset's hash. `sample.csv` contains exactly the selected source rows.

The first published move is the opponent's setup move. The solution begins at
the second move, from the resulting position. Preserve this distinction.
Puzzle themes are machine labels. No creator commentary was acquired.

The sample takes the first 24 different game IDs and positions in the retained
prefix. It is not representative. Game hashes deterministically assign 8 train,
8 development and 8 test cases. Test outcomes have not been scored; legal replay
and file-integrity checks do not expose model/engine outcome measures.

From the project root, using the existing project Python environment:

```text
.venv-soccernet/Scripts/python.exe scripts/chess_real_data.py verify --data data/open/chess/lichess-real-seed-v1
.venv-soccernet/Scripts/python.exe -m pytest tests/test_chess_real_data.py -q
```

The paired local Stockfish baseline and board report are retained under
`artifacts/autonomy-audit-20260918/`. To conduct a materially changed experiment,
use `chess_real_data.py baseline` with a **new** output path and retain its
configuration. Do not rerun an unchanged successful experiment merely to keep a
loop busy. Move to the next experiment in `GOAL_WORK.json`.

Dependency versions actually used: Python 3.11.9, chess 1.10.0, zstandard 0.25.0,
existing Stockfish 19 universal Windows binary. Keep GPL notices with any future
distribution of chess/Stockfish; internal data/results are not a release approval.
Source: https://database.lichess.org/
