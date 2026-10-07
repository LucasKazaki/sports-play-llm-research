# 17.Qc2 and 17.Qb3: an offline two-branch contrast

**Proposed evaluator note, 6 October 2026. No model response, new engine search, or teaching-quality verdict.** This is one known development position from the user's completed game. Keep every fact below outside a no-forward generator packet. The source PGN is local only; redistribution rights are unestablished.

## Fixed position and evidence

- Local-only source PGN (untracked; no movetext reproduced here), SHA-256 `684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`. A read-only `python-chess` replay of its 121-ply mainline reported zero parse errors and reached the same pre-ply-33 FEN recorded in the [practice plan](chesscom-breadth-practice-plan-2026-10-06.md): `2kr3r/pppq3p/3bpp2/6p1/1P1P4/P1n1PBBP/5PP1/R2Q1RK1 w - - 1 17`.
- Locally retained ply-33 paired JSON baseline (see the [tracked baseline summary](chesscom-breadth-baseline-2026-10-06.md)), SHA-256 `28ccb3384d34b9027ececae67933ed18fbf8cb9f15a732aefc4c4d3de701f006`, contains the played `d1c2` and sampled alternative `d1b3` in one Stockfish 19 root-restricted MultiPV-2 search. One thread, 16 MB hash, 10,000 requested nodes; both recorded observations show 10,003 nodes and depth 10 for that search. The separate discovery call selected Qb3; its score is not the paired comparison. The baseline's own `comparison.status` is `abstain` with `delta_cp: null`.
- I legally replayed the same pre-move board for `17.Qc2` and `17.Qb3`, then held Black's candidate reply fixed at `17...Nd5`. These are legal-board checks, not Stockfish judgments. The observed score and PV below are evaluator-only. [Stockfish's UCI documentation](https://official-stockfish.github.io/docs/stockfish-wiki/UCI-Protocol-and-Stockfish-Commands.html) distinguishes root restrictions, MultiPV search output, centipawn and mate scores, and bound flags.

## The contrast, with the same Black reply in both branches

| Check | `17.Qc2` branch | `17.Qb3` branch |
| --- | --- | --- |
| Immediate shared facts | Legal queen retreat from attacked d1 to c2; Black has no immediate attack on the queen there. White queen attacks Black's knight on c3. | Legal queen retreat from attacked d1 to b3; Black has no immediate attack on the queen there. White queen also attacks the knight on c3. |
| Is `17...Nd5` legal? | Yes. It is one of eight legal knight moves from c3. | Yes. The same eight knight moves are legal. |
| After `17...Nd5`, does the queen attack the knight on d5? | **No.** `18.Qxd5` is not a legal queen move from c2. | **Yes.** `18.Qxd5` is legal from b3, along b3–c4–d5. |
| Does that extra attack win the knight outright? | No such capture exists from c2. | **No claim of a free knight.** The pawn on e6 protects d5; after the legal illustrative `18.Qxd5`, `18...exd5` is legal and captures White's queen. |

The differing consequence is narrow but real: Qb3 covers the knight's d5 landing square and Qc2 does not. This follows directly from the queen's new square while the opponent reply is held constant. It does **not** show that `...Nd5` is unsound after Qb3, that `Qxd5` is a good move, or that Qb3 is strategically best. The immediately tempting sentence “Qb3 attacks the knight on c3 while Qc2 does not” is false: **both** moves attack c3. Nor does “the queen escapes attack” distinguish them. In the initial post-move positions, Qc2 also attacks Black's h7 pawn and Qb3 attacks e6; those are geometric targets, not proven gains.

## Where the engine evidence stops

The retained paired event reports `17.Qc2` as **+120 cp upper bound** and `17.Qb3` as **+141 cp unbounded**, both from White's perspective at the stated finite search. The stored comparison deliberately abstains on `mate_or_bounded_score`. Therefore this note makes **no numeric centipawn gap, move-quality label, or “Stockfish prefers Qb3 because it eyes d5” claim**. The two saved principal variations differ (`Qc2 ...Nd5` versus `Qb3 ...Bxg3`), but they are sampled search continuations, not a controlled proof of why either move is stronger. A legal conditional line also does not prove that Black must play it.

## Proposed use after a model answer exists

Split the answer into atomic claims. Give credit for the shared escape and c3 attack as board facts, but not as a reason *between* Qc2 and Qb3. If the model names Qb3 and claims d5 coverage, replay its exact conditional branch and the e6-pawn recapture before rating the claim; do not patch the original answer after seeing these facts. If it asserts a numeric loss, a forced knight win, or a Stockfish motive from this bounded receipt, mark that assertion unsupported. This single same-game case can test contrastive specificity and honest restraint; it is not a game-disjoint holdout, a Chess.com comparator result, or evidence for professional commentary. The [project's no-forward gate](chess-commentary-capability-gate-v1.md) still applies.
