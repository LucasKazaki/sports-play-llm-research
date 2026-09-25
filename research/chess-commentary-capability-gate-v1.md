# Chess no-forward-commentary capability gate v1

## Status

**Planned acceptance contract — not achieved.** The project must not describe
itself as a professional chess commentator, nor begin a general board-game
rollout, from the present Stockfish move-match baseline.

## Why this gate exists

The current `prototype/chess_concept_model.py` prompt receives the retained
`engine_evidence` object wholesale. That object contains `pv_uci` and a final
FEN, so the current prototype can see a Stockfish continuation while producing
an explanation. Its own files also say explanation quality is unmeasured.
Matching a puzzle solution or passing a board-fact validator is useful plumbing,
but it is not an explanation of why a move is good.

## Required no-forward mode

Implement a new, separately versioned commentator path rather than silently
changing historic receipts. For one selected move, the generator may receive:

- the source-bound pre-move FEN and side to move;
- the selected legal UCI/SAN move, deterministic transition facts, and an
  explicitly typed engine observation for that move; and
- source and engine identity, score perspective, score type/bound, plus the
  declared concept vocabulary.

It must not receive a Stockfish principal variation, post-move FEN, reply
sequence, puzzle solution/theme, future-board feature, human annotation, or
any hidden continuation-derived label. The input packet, field allowlist,
canonical hash, model/version/seed, and raw response must be retained. A
machine check must reject prohibited fields before the local generator is
called. The engine may be used **after generation** by a separate evaluator;
that evaluator must not feed its continuation back into the generated output.

Every assertion in output must be typed as one of:

1. a legally replayed board fact;
2. an exact retained engine observation, with perspective and qualification;
3. a bounded strategic hypothesis with explicit evidence and uncertainty; or
4. an abstention.

Do not attribute an inferred strategic rationale to Stockfish. Do not turn an
engine score or PV into a claim of forced play, best human teaching, or a
professional commentary judgment.

## Evidence required before a capability claim

The experiment protocol must be frozen before use and must use a fresh,
game-disjoint holdout whose solutions, themes, and engine continuations were
not supplied to the generator. The existing eight historical test puzzles are
not sufficient because their labels have entered prior review context.

At minimum, the retained evaluation needs all of the following:

- a predeclared stratified corpus covering tactical, quiet/positional,
  defensive, and endgame positions, with complete denominators and source
  provenance;
- 100% legality and deterministic board-fact accuracy for every asserted
  checkable fact, with malformed/unsupported claims rejected or abstained;
- a no-forward input audit for every generation and a negative-control test
  proving prohibited PV/post-move fields cause rejection;
- separate scoring of factuality, engine-reference validity, strategic-claim
  evidence coverage, abstention, latency, and failure rate;
- an independent receipt-based review that checks the frozen protocol and raw
  outputs without treating a passing command as teaching quality; and
- an independent qualified chess reviewer or a documented, explicitly limited
  substitute rubric before calling the result professional-level. Without that
  evidence, report at most a local, evidence-grounded commentary candidate.

The precise sample size, thresholds, reviewers, and confidence bounds must be
preregistered in the new experiment rather than retrofitted after a favorable
run. A local model's confident prose is not a substitute for this gate.

## General board-game expansion gate

Only after the no-forward gate is independently accepted and the professional
quality claim is actually supported may the director create a board-game
generalization packet. That packet must be game-specific: obtain authoritative
rules and permitted strategy/commentary sources, define a legal-state adapter
and evaluator, preserve source/rights records, and abstain when the requested
game lacks sufficient evidence. The project must never claim that a chess
result proves competence in every board game.
