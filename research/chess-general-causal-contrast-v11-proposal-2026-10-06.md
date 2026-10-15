# Proposed two-branch check for chess move explanations

**Proposed follow-up hypothesis, 6 October 2026.** This is a research and software proposal, not an implemented V11 path, a model result, a source-review verdict, or a teaching-quality finding. Decide whether to build it only after inspecting the signed V8/V9/V10 source reviews and the retained four-case development trial. The [no-forward commentary gate](chess-commentary-capability-gate-v1.md) remains open.

## The gap

The [V9 checker](../scripts/chess_no_forward_teaching_v9.py) can verify a model's named squares, legal moves and conditional examples. It deliberately avoids ranking the moves. The [V10 sidecar](../scripts/chess_post_generation_comparison_v10.py) can compare an accepted model-named pair in a bounded, post-generation Stockfish search, but a score difference does not identify the board consequence responsible for it. The existing [model-named comparison plan](chess-model-named-contrast-next-step-2026-10-06.md) addresses the score side. This proposal addresses a different question: **does the proposed mechanism distinguish the played move from the named alternative?** A fact that holds after both moves may be useful instruction, but it cannot explain their difference.

## Candidate contract

Keep the generator's source-bound, nine-field **pre-move** projection. A new, separately versioned output may either abstain or name one distinct legal alternative and one typed, checkable claim about a board consequence. The model must supply the exact moves, squares, pieces and branch; the checker must not discover a substitute alternative or repair the raw answer. Start with a small vocabulary such as check, legal capture, attack or defense of a named piece, and control of a named square. Each added predicate needs its own negative controls.

After the raw response is sealed, an **offline two-branch checker** reconstructs the same source-pinned pre-move board, plays both root moves legally, and applies one predicate definition to both successor positions. It returns `shared_reason` if the proposed property holds in both; `verified_board_difference` only if it differs as claimed; and `unverified_difference`, `rejected` or `abstain` when the evidence does not support display. A model-named conditional reply may be replayed as one possible line, with its own witness. It must never become a claim that the opponent must choose that reply. Fixed wording displays only verified facts and states what remains unresolved.

Any engine comparison happens **after** generation under a separately frozen evaluator protocol, using exactly the accepted model-named pair. PVs, later boards, alternative scores and evaluator witnesses remain outside the generator request. Keep `verified_board_difference`, finite score ordering and the strategic hypothesis as separate fields. A qualified score may support a bounded statement about that search; it cannot prove Stockfish's intent or establish that the board difference caused its preference. Missing, bounded, mate, unstable or source-mismatched observations leave the ranking unresolved.

## First bounded implementation and checks

Implement the generic two-branch predicate checker first, with synthetic boards and **zero model or engine calls**. Test a true shared-property claim, a genuine branch-specific consequence, an illegal alternative or reply, a false piece/square relation, malformed or duplicate-key JSON, and an attempted forced-line assertion. Verify exact source and raw-response hashes, unchanged generator request bytes, and rejection of prohibited nested input fields before dispatch. Preserve rejected, abstained, failed and not-run cases in the original trial denominator. Only after a finite function-level source review should a newly frozen model attempt use the new output version; the original V9 answers and V10 receipts remain sealed.

This check can reject a weak comparative explanation and admit a narrow, legally supported contrast. Whether the result teaches a player well requires separate chess judgment and a fresh, game-disjoint evaluation. It makes no Game Review parity or general board-game claim.
