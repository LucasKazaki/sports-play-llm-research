# V7: let the model choose the line, then check every causal step

The Chess.com practice game remains a useful place to find mistakes in our
explanations. At move 20, White played `Qc3`; Game Review suggested `Qe4`.
The narrow line we can replay is `20.Qc3 Qxd4 21.Qxc7+ Kxc7`, compared with
`20.Qe4 Qxd4 21.Qxb7+`. In the latter line the bishop on f3 protects b7,
so the Black king cannot take the queen. This is a conditional board fact,
not a proof that the bishop caused Stockfish's score gap. `Qe4` does not
prevent `...Qxd4`; both queen-trade lines can reach the same board. Black
has other replies. The source and finite Stockfish evidence are recorded in
[the queen-defense replay](chesscom-queen-capture-defense-2026-10-06.md).

Chess.com's [Game Review description](https://support.chess.com/en/articles/8584089-how-does-game-review-work)
describes move classifications, Coach explanations, suggested computer lines,
visual ideas such as a lost piece or fork, and feedback after Retry. Those
are useful benchmark dimensions, not features established by this experiment.
We need to score whether a learner can understand a move and correct a bad
one separately from whether a sentence is legal and factual. No parity or
superiority claim follows from replaying one motif.

## What changed from v5 and v6

V5 asked the model for one same-origin alternative and let the evaluator pick
a legal illustration. V6 added an offline queen-defense proof but needed a
caller-supplied reply focus; an unscoped search in this position found many
qualified pairs. V7 asks the model itself to name the alternative, the same
opponent reply in both branches, each checking queen capture, which branch is
protected, the bishop's square, a typed mechanism, and a short lesson draft.
The output is a single exact JSON shape or an exact abstention. It cannot
inherit a convenient evaluator-selected reply, capture, or defender.

The generator still sees **exactly nine pre-move fields**: schema, packet hash,
source identity, FEN, side to move, selected move, deterministic transition,
typed engine observation, and assertion kinds. Its projection contains no
future move, engine PV, post-move FEN, alternative score, review label, legal
reply menu, or evaluator witness. The route builder checks all top-level and
nested fields and scalar leaf types before it constructs a request. A separate
v7 capture runner pins the source packet, projection, prompt, local route,
attestation, implementation hashes, and request. It writes a create-only
request sentinel before one local POST; a crash spends the attempt. No v7
model POST has been made for this candidate.

After generation, the checker replays only the model's named moves on both
boards. The common reply must be legal with the same SAN. Each follow-up must
be a legal capture with check by the moved queen, of the same piece type.
The unprotected capture must have no friendly defender and permit an immediate
legal king capture. The protected capture must have exactly one friendly
defender, a bishop, and forbid that king capture. Removing that bishop on a
copy must make the king capture legal. The model's `protected_branch` and
`defender_square` must match the observed direction and square. The result
keeps the model's selected and alternative labels even when the selected
move is the protected one.

The lesson is model-authored in the raw response, but v7 admits it as
`teaching_text` only when it exactly matches a bounded, board-populated
conditional sentence pattern. That sentence says which capture permits the
king recapture, which bishop protects the other capture, and that other
replies and move quality remain unchecked. A claim such as “Qe4 prevents
Qxd4” is rejected. Free-form coaching would require a broader claim parser
and independent human teaching review; accepting plausible prose on this
one board would be unwarranted. An otherwise well-shaped response with no
verified contrast abstains. Malformed or illegal claims are rejected. Both
outcomes keep their raw response in a future capture receipt.

## Software evidence and limits

The v7 checker test was written before its module existed and first failed
at import. The final focused run of v5, v6, and v7 tests passed **48 tests**
with the project Python interpreter; both v7 sources also passed Python
compilation. The v7 cases cover `Qc3 → Qe4` and `Qe4 → Qc3`, the exact
`...Qxd4` defender-removal counterfactual, the false claim that `Qe4`
prevents that reply, a different reply or capture, an extra bishop defender,
abstention, bad output shape, prohibited future input fields, source binding,
the fake one-call capture, interrupted attempts, incomplete envelopes, and
no automatic retry. These are synthetic software checks around the real
practice FEN, not a new model result, fresh holdout, or a teaching evaluation.
The tests do not measure whether the local model can produce the strict v7
format. The exact source hashes belong with the next native source-review
receipt; a direct run alone is not formal project acceptance.

The governing [no-forward commentary capability gate](chess-commentary-capability-gate-v1.md)
is still open. It calls for source-bound no-forward input audits, legal and
factual checks of every asserted fact, a game-disjoint stratified holdout,
separate factuality, engine-reference, claim-support, abstention, latency and
failure measures, and independent review of both evidence and teaching
quality. V7 exercises one legal motif and one rigid lesson pattern. It does
not explain every Stockfish move, every bad move, quiet or positional play,
endgames, or why Stockfish chose a move.

## Next experiments

1. Obtain a concrete function-level native source review of the v7 checker
   and capture runner. Freeze a new v7 request before one bounded local model
   call; retain the raw response even if it is empty, malformed, or wrong.
   Inspect the exact denominator and cause of every rejection before changing
   the format or prompt.
2. Build a game-disjoint move-category cohort with tactical, defensive, quiet,
   positional, endgame, and clearly bad decisions. Keep source rights, game
   exclusions, legal replay, and engine settings fixed before scoring.
3. Add claim-bound explanation types beyond this bishop motif. For each,
   separate pre-move model hypotheses from evaluator-only legal continuations
   and Stockfish observations. An engine line can establish a bounded
   consequence after evaluation; it cannot, by itself, prove Stockfish's
   underlying reason or the best teaching explanation.
4. Compare factuality, legal coverage, alternative and reply selection,
   abstention, latency, and failure against the frozen categories. Ask a
   qualified chess reviewer to rate clarity, usefulness, and whether the
   explanation helps a player avoid the same error. Only a measured broader
   protocol can support a Game Review comparison. A different board game
   waits for the separate expansion gate, and human sports needs its own
   rules and evidence rather than a chess analogy.
