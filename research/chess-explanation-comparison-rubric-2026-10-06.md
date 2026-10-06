# Chess explanation comparison rubric — working note

**Design only, 6 October 2026; no quality or parity result.** The [no-forward commentary gate](chess-commentary-capability-gate-v1.md) remains controlling. The [draft quality protocol](chess-explanation-quality-protocol-draft-2026-10-06.md) still needs frozen sample sizes and thresholds before a fresh holdout.

## What to compare

[Chess.com describes Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work) as giving move classifications, short coach feedback, computer move predictions and a chance to retry a decision. Its [current classification guide](https://support.chess.com/en/articles/8572705-how-are-moves-classified-what-is-a-blunder-or-brilliant-etc) bases ordinary labels on expected-points change, not a simple centipawn cutoff. Chess.com also says [deeper analysis and different engine settings can change classifications](https://support.chess.com/en/articles/11845102-why-did-my-move-classification-change-in-game-review). Do not equate those labels or UI numbers with our Stockfish centipawns. The target is an accurate, useful explanation and checkable alternative, not a matching label.

The [open-game practice](chesscom-game-review-practice-2026-10-06.md) exposed the gap at 20.Qc3 versus 20.Qe4: the same pawn-and-queen exchange is legal after either move, so the pawn capture alone does not explain the difference. The [two model attempts](chesscom-no-forward-model-practice-2026-10-06.md) yielded one rejected Qc3 answer and one admitted Qe4 answer with no reason. The [four-position baseline](chesscom-breadth-baseline-2026-10-06.md) made zero model calls; three paired comparisons abstained on bounds, while one gave a finite 283 cp event difference. All are known same-game practice, not teaching-quality evidence.

## Hard factual gate, then teaching score

Bind each output to its source game, ply, pre-move board, legal move, generator packet and raw response. Reject post-move boards, future play, PVs, answer labels and evaluator lines in generator input. Legally replay each claimed capture, attack, check, mate, alternative and reply. Require engine identity, score perspective, type, bound and search receipt. A numeric comparison needs the played move and **model-named** alternative in one pinned root-restricted search, with two unbounded centipawn observations from the same perspective; otherwise abstain. [Stockfish's UCI guide](https://official-stockfish.github.io/docs/stockfish-wiki/UCI-Protocol-and-Stockfish-Commands.html) documents `searchmoves`, `MultiPV`, node limits and `upperbound`; its [evaluation FAQ](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html) describes scores as engine evaluations, not prose rationales.

An invented fact, false score attribution, unsupported forced claim or missing no-forward receipt **fails the factual gate**. Reject it for coaching, mark `F-fail` and retain it in the denominator. A legal line is an example unless forcedness is checked. Factual passage allows a teaching rating; it does not prove usefulness.

| Teaching score | Reader-facing criterion after the factual gate |
| --- | --- |
| **0** | No usable reason: empty, full abstention on an answerable case, or vague praise/criticism. For summary arithmetic, an `F-fail` also contributes 0 but remains separately flagged. |
| **1** | Correct move, board fact or qualified score, but no concrete consequence or choice a learner can use. |
| **2** | A specific, verified conditional mechanism and a relevant legal choice, with the untested part stated plainly. The reader can identify what to look for, although the move ranking or full reason remains unresolved. |
| **3** | A verified contrast between the played move and a model-named alternative, with the resulting practical decision explained in plain language and limits retained. The contrast must survive legal replay and evaluator checks; a finite score alone cannot earn 3. |

Report `F-fail`, correct restraint on insufficient-evidence controls, full abstention on answerable cases, valid scores, latency and transport failures separately. Two blinded readers, including a qualified chess reviewer before a professional claim, should rate the same positions and learner question and retain initial ratings and adjudication. A Chess.com head-to-head test needs lawful source and review access, game-disjoint positions, randomized source-hidden paired answers and predeclared analysis including failures. Do not copy Chess.com coaching text into a dataset or use its labels as hidden answers. This one practice game cannot establish parity or superiority.

## Comparative question outcome

Record this outcome separately from the teaching score for each initial answer and each judge. Use the same question and evidence standard for both products. Do not infer the outcome from a teaching score or engine number.

| Outcome | Required evidence |
| --- | --- |
| **Answered with verified contrast** | The answer explains the practical difference between the selected move and a named alternative or refutation. Its mechanism, conditional consequence and comparison survive legal replay and the separate evaluator checks. A finite score difference alone is insufficient. |
| **Useful mechanism but ranking unresolved** | The answer teaches a checked mechanism or conditional choice, but the evidence does not establish why the selected move is stronger or weaker than the relevant alternative. |
| **Unanswered** | The answer does not supply a usable comparative reason, including a full abstention, missing answer or transport failure. Keep the precise failure or abstention status separately. |
| **Factual fail** | The answer fails the factual gate; retain its critical error or admission failure and count it in the original denominator. Do not reclassify rejection as a successful abstention. |

Leave the outcome **unscored** until the exact initial answer and evaluator evidence have been inspected. An unscored record is pending, not a fifth outcome or a successful answer. Retain initial judgments and any adjudication. Report all four outcome counts over the original scheduled denominator, with unscored cases disclosed separately; never drop failed or unresolved cases.

A teaching score of 2 or higher can include a useful mechanism with an unresolved ranking. The proposed 2+ teaching threshold does not establish why every inferior move was bad or Chess.com parity. No new comparative acceptance threshold is set here; any future decision rule must be frozen before holdout scoring. The [four-case worksheet](chesscom-four-case-scoring-worksheet-v1-2026-10-06.md) applies this distinction only to the known development game.

## Next discriminating experiment

Keep the v9 generator's pre-move packet unchanged. After saving a one-attempt raw answer, replay the **model-named alternative** and run a separately versioned, fixed-budget paired Stockfish search restricted to that move and the played move. Pin source, engine, settings, root position, moves, command and full output; abstain on missing, bounded or mate scores. This post-generation result must never enter the same answer. Blind human ratings then ask whether the verified contrast teaches *why* the move was weaker or stronger. Fresh game-disjoint testing, independent source review and qualified chess judgment remain required before the chess gate or board-game expansion.
