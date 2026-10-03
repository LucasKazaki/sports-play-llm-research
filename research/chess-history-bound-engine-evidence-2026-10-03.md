# Chess history-bound engine evidence — 2026-10-03

Packet: `SLM-C02-R14-HISTORY-BOUND-ENGINE-EVIDENCE-v1`.

Current mirror: `156780d1370363ab83f64589c8bb319dde63cc9f`.

Current source inspection found a history-boundary gap:
- `scripts/chess_counterfactual_evidence.py@7dccf3525049c60a72f0a2883709012d86d6adfb` creates each development board from the Lichess puzzle source FEN and then pushes one setup move.
- `tests/test_chess_counterfactual_evidence.py@1db2b5d6592c51af4a4cc693984da9d6a3ec1cd5` and `tests/test_chess_counterfactual_streaming.py@7a540cc201f82ea59b05ab42c1fe8cfe1eca79ba` explicitly expect engine-bound boards to have `move_stack` length 1.
- The accepted v3 review already records that earlier game history is unavailable.

Decision: preserve historical v3 unchanged and classify its repetition scope as `unknown_prior_history`. Future exact-state engine receipts should bind an ordered move-history digest in addition to final FEN, observation, engine identity and search settings.

Two history modes are sufficient for the first implementation:
- `complete_from_start`: legally replayed from the standard initial position; eligible for a native repetition check.
- `partial_from_fen`: earlier history unknown; ordinary position analysis remains usable, but repetition-dependent claims abstain.

A six-field FEN is not a substitute for the prior position sequence. Same final FEN with a different history must produce a different engine-analysis identity.

Native acceptance remains gated by C00/N+1 consumption. The local implementation should add one focused history-binding helper and tests, including a real python-chess repetition fixture that changes when the move stack is discarded. This cloud pass ran only standard-library contract tests; it did not run Stockfish, python-chess, Company Runtime, Windows, a model, or heldout evaluation.

Cloud reference: 15/15 focused tests passed on Python 3.13.5; `py_compile` passed. Full artifact packet is retained outside this repository handoff.
