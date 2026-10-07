# V8: four typed chess explanations from one practice game

The [four-case plan](chesscom-breadth-practice-plan-2026-10-06.md) asks a
different question from the move-20 queen-defense experiment: can one narrow
no-forward format express a defensive move, a checking capture, rook
coordination, and a rook's attack on a passed pawn? This v8 checker supplies
four **software claim types** for the four named plies of the already reviewed
Chess.com game. It has made no model call and offers no result about the local
model's ability to produce the claims. The game remains a known development
case, not a fresh holdout.

The generator projection has the same **nine pre-move fields** as v7: schema,
source packet hash, source identity, FEN, side to move, selected move,
deterministic transition, qualified engine observation, and assertion kinds.
The verified source packet excludes review labels, later moves, engine lines,
post-move FENs, alternative scores, and evaluator witnesses. The checker
requires the local source PGN digest and one exact selected ply/FEN/move pair
from the plan before building an input. The PGN itself remains in ignored local
artifacts because redistribution rights have not been established. The
[paired Stockfish baseline](chesscom-breadth-baseline-2026-10-06.md) is a
separate evaluator record; its lines are never placed in the generator
projection. Chess.com's [visible review observations](chesscom-review-breadth-observations-2026-10-06.md)
remain outside the generator as well.

## What a model would have to supply

The response is one exact JSON object. It can abstain, or name one typed
mechanism with its selected UCI move and fixed uncertainty scope. No free-form
lesson, ranking, score comparison, review label, or engine-rationale field is
accepted. The model supplies every square or conditional move used by its
claim; the checker does not search for a substitute after generation.

| Ply and typed claim | Offline check | Bounded explanation |
| --- | --- | --- |
| 33, queen escape | The model names the knight that attacks the queen's old square and the knight the moved queen attacks. Both must be the same actual knight. | `Qc2` leaves an attacked square and counterattacks that knight. This does not establish a forced win or move quality. |
| 46, checking capture | The queen must capture a pawn with check and attack the opposing queen. The model's named queen capture and rook recapture must both be legal. The checked side has more than one legal reply. | `Qxd4+` checks and attacks the queen; `Qxd4 Rxd4` is one conditional trade, not forced play or proof of a material outcome. |
| 57, rook coordination | The moved rook must support the other rook, which attacks the named pawn. The model must choose a different legal rook move that lands on a file with no pawns of either color. | `Rac1` connects the rooks; the named open-file move is a legal geometric option. The checker ranks neither move and does not assert a pawn win. |
| 93, passed pawn | The rook must attack a passed pawn from behind. The model may omit a line or name an opponent reply, pawn capture, and immediate rook recapture, all legally replayed. | `Rb8` attacks the b2 passer. The optional `Ra2 Rxb2 Rxb2` line illustrates why attack does not prove a safe capture. |

This intentionally narrow shape avoids treating a plausible sentence as
verified. Exact board replay supports geometric and conditional facts, but
does not measure whether the words teach a player well or why Stockfish
preferred a move. A typed claim may still abstain when the model cannot
verify its own fields.

## Local verification

The focused synthetic suite passed **16/16 tests** with the project Python
interpreter. It covers the four admitted claim types, both forms of the
passed-pawn claim, wrong squares and conditional moves, a false case kind,
unsupported ranking/prose fields, abstention, changed source binding, a
prohibited future field, duplicate keys, `NaN`, exponent overflow, and deeply
nested JSON. The parser rejects all numbers because no v8 claim field needs
one; this prevents `1e999` from becoming an infinite float. A malformed
response retains its raw-byte digest in the evaluator result.

A separate **read-only local integration check** rebuilt one source-bound
no-forward packet from each retained paired-review receipt and called the
offline checker with synthetic typed claims. All four projections were built
and all four synthetic claims were accepted, with **zero model and zero engine
calls in this check**. The packet SHA-256 values in ply order were
`68a93644e372d4df7058fdae2866c6bc1ceee56e27b9240801842c2ca1bb0fae`,
`2d377b2e0223a9fb9c4d01ba060c15078dc788aef233eb68fe52a861a5f735aa`,
`76d906526abaed37760bea838cec7671b9a093e607895f057f61c35cad767597`,
and `3219c8c925997a9b02d4446f9ff04dd62a88a8bf6f815b43a141f4669b4c24eb`.
The respective generator projection digests were
`323d2802f42a6ace08ed7f0347b1dadb1e318229b03add542de347a025305cae`,
`f45a69dfd59842fb5dc0f0a6b318fb3fd27f4d8021e0a378e82c4be73a1e7894`,
`65267a4ba706606b60d13eb65b58e364eee52f57ce92246f7805844e271d476b`,
and `349d80d043a762e6a4bba30254d5de870297f518f77fd4021e9fd105046ecb2f`.
Those hashes bind local packet bytes, not independent commentary quality.

The direct run is **not** the project's formal native source review. Before
any model attempt, the exact new checker and meaningful tests need the
project's bounded source-review route, a frozen create-only capture request,
and raw-response retention. The [commentary capability gate](chess-commentary-capability-gate-v1.md)
still requires a game-disjoint stratified holdout, full factuality and
failure denominators, independent evidence review, and qualified human
teaching judgment. V8's four known plies cannot support Chess.com parity,
all-Stockfish-moves coverage, or expansion to another board game.
