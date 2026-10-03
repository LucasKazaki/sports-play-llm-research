# SLM-C02-R11-TYPED-COMPARISON-SCORE-v1

Status: cloud reference checked; native Stockfish execution not run.

Base mirror: main@156780d1370363ab83f64589c8bb319dde63cc9f.

Current scripts/chess_stockfish_compare.py blob:
b324c3659d33607eeb60cfe90f0e168ecc04dd27.

Finding: the legacy comparison receipt calls
PovScore.pov(board.turn).score(mate_score=100000) and stores the result as score_cp.
python-chess documents that score(mate_score=...) converts mate scores into synthetic
centipawn-like integers; Stockfish UCI emits cp and mate as distinct score forms. This
violates the Sports LM requirement to keep cp/mate identity, perspective and bound
qualification separate.

Repair:
1. Reuse scripts/chess_score_bounds.py typed_score_bound(info, board.turn).
2. Replace candidate score_cp with typed score {type,value,perspective,side_to_move,bound,order[,mate_zero]}.
3. Bump only this comparison receipt to stockfish-comparison-receipt/v2. Do not relabel old v1 receipts.
4. Retain actual returned depth/nodes/time/seldepth when present and reject boolean/negative accounting.
5. Record engine.id, python-chess version, requested depth and requested MultiPV.
6. Refuse to overwrite an existing output path.
7. Preserve comparison semantics: proposed move rank is still based on exact UCI move identity.

Fail-first:
- current source contains mate_score=100000 and score_cp;
- synthetic Mate(+5) must remain {type:mate,value:5};
- Mate(0) versus MateGiven must remain distinguishable through mate_zero;
- a perspective flip must flip score sign and lower/upper bound direction;
- invalid accounting and missing PV fail closed.

Cloud reference result: 7/7 focused tests pass after the repair; py_compile passes.
The fail-first static control fails against the current blob as expected.

Native worker:
Inspect installed python-chess and Stockfish first. Apply the smallest compatible
production repair, run the focused comparison tests plus existing score-bound and
counterfactual tests, then run one native comparison containing a mate score if a
dependency-ready fixture exists. Return exact engine/library versions, binary hash,
effective engine options/settings already required by the C02 provenance packets,
commands/exits, receipt hash, and any not-run checks.

No professional-commentary, heldout-quality, C00-access, migration, merge, or publication
claim follows from this repair. Do not expand to checkers/Catan until chess acceptance gates
are actually measured.

Return WORKER_UPDATE SLM-C02-R11-TYPED-COMPARISON-SCORE-v1.
