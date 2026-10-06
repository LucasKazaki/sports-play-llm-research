# Four-position Chess.com practice baseline — 6 October 2026

This is an **engine-only development baseline** for the four already chosen moves in [the breadth plan](chesscom-breadth-practice-plan-2026-10-06.md). It makes zero model calls and does not test teaching quality. All four positions come from the same known game; none is a game-disjoint holdout. The source PGN stays local because redistribution rights have not been established.

## Method and source

The source is the 1,602-byte local Chess.com export `artifacts/chess-user-reviews/chesscom-184866057876/source.pgn`, SHA-256 `684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`. The [practice note](chesscom-game-review-practice-2026-10-06.md) records its acquisition and legal mainline. The existing `scripts/chess_paired_review_v3.py` tool (SHA-256 `017198becb39ab2369c1ed126a1c469a4d92dc8536586bb3c7bc53f93daeb2ac`) replays the game and checks each selected move. For each position it first requests an unrestricted two-line search to select one alternative, then searches the played move and that alternative together in one root-restricted two-line call. Each call requests **10,000 nodes**; settings are one thread and 16 MB hash. The engine is pinned Stockfish 19, binary SHA-256 `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0`.

The native project-execution task `0415c263-ae32-4292-a821-eae799b20fe1` ran four create-only reviews and four offline verifications: **8/8 commands exited 0**, **8 engine calls**, **0 model calls**. Job `4202920b-b7a5-403a-92af-74620a9d6092` has the complete logs. The server-owned receipt is `C:\AI\projects\LucasAgentStudio\data\company-runtime\project-execution\35fc2d789ba6f2679b8923ca442f12f478109f37cdea1c0b5239b93972d1de6a\a8cddb66ad7e32f9c34d26bf95d1b70c95e9b49404ebd324a9125f59da92c3fd\receipt.json`, SHA-256 `d8d8f128310a28fab56a7615e7fab2c755cfced71421870e2ec863eca0a516c7`. Each `verify` command rechecked source binding, legal replay, record structure and rendered page bytes without an engine call.

## Observations

Scores are centipawns from the **side to move before the selected move**. “Unqualified” means that this search event did not carry a lower/upper-bound flag; it is still an engine estimate, not a proved game value. A bound prevents the existing comparison checker from reporting a numeric difference. The alternative was chosen by the earlier bounded discovery call, so it is a sampled candidate, not an established best move.

| Planned case | Played move: paired-search observation | Sampled alternative: paired-search observation | Valid paired comparison | Ignored evaluator receipt SHA-256 |
| --- | --- | --- | --- | --- |
| Ply 33, queen escape | `17.Qc2` **+120 upper bound**, White perspective | `17.Qb3` **+141 unqualified**, White perspective | Abstain: bounded score | `ply33/review.json` `28ccb3384d34b9027ececae67933ed18fbf8cb9f15a732aefc4c4d3de701f006` |
| Ply 46, checking capture | `23...Qxd4+` **+392 upper bound**, Black perspective | `23...g4` **+200 unqualified**, Black perspective | Abstain: bounded score | `ply46/review.json` `2e246ed59ab9bbf494a7b2ae888b8dea8745dbb74ede68325846e8404b24ec28` |
| Ply 57, rook coordination | `29.Rac1` **−235 unqualified**, White perspective | `29.Rb1` **−87 upper bound**, White perspective | Abstain: bounded score | `ply57/review.json` `8a4bd9724386ab26389a796da4fd4bbea3d690862efadd5acd3c6cdfff8f61ba` |
| Ply 93, rook and passed pawn | `47.Rb8` **−877 unqualified**, White perspective | `47.Rc8` **−1160 unqualified**, White perspective | Played scored 283 cp higher *in this paired search* | `ply93/review.json` `5c7b26287d401cca861b17641742a64e9bcb97c508bfe76525935eebfa929fd3` |

All four `review.json` files, their full legal engine lines, and matching HTML pages are under ignored `artifacts/chesscom-breadth-baseline-20261006/`. The four page SHA-256 values, in ply order, are `25f387bc6facd30fbc0e01ce4e497959ddce33e44d7c7290bf88d5950463338f`, `eac09f895913b44a1fd0ed9a4a17503c6a07088c6d2786eab9a7fd8c636912e6`, `3e86513b813bdac04e3ab6510b275ea8333d196301c2567093db9fe034f17b2c`, and `8c9f46f4705d04b27a7175e81e1e12d71b529426ebb56d923d63c3085b9aae5c`.

## What this does and does not establish

Legal replay supplies the useful questions: `Qc2` leaves the attacked queen's square; `Qxd4+` captures with check but White has legal replies besides moving its king; `Rac1` connects the rook on c1 behind the rook on c3; `Rb8` attacks the b2 pawn but does not make its capture automatically safe. These are board facts or bounded, conditional teaching prompts from the earlier plan. The engine scores do not establish the complete reason for any move, a forced continuation, or a Chess.com category. In particular, the 283 cp event difference for `Rb8` versus `Rc8` is neither a measured game outcome nor evidence that `Rb8` solves the passed-pawn problem. The saved principal variations are evaluator-only and must not enter a no-forward generator.

The next implementation question is whether a generalized typed commentator can express each of these four mechanisms, or abstain, using only its permitted pre-move packet. Freeze and review that software before any model call. Keep this **4/4 planned development denominator** separate from the fresh, stratified, game-disjoint commentary gate.
