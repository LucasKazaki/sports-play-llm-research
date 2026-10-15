# Matched move diagnostic: the selected adapter misses every check

The completed retained-artifact audit and root publication review pass. This report uses the single retained run; no additional inference was used to prepare it.

The fixed selected fact adapter detects **0/32 checking moves** and correctly reports no check on **32/32 matched nonchecking moves**. It predicts `gives_check: false` for all 64 supplied moves. **No matched board has both check labels correct: 0/32 pairs.** All 64 responses meet the strict eight-field schema. The failure is therefore visible even when output formatting succeeds. Check confusion is **TP 0, FN 32, FP 0, TN 32**, with zero unknown, schema-failed, runtime-error, truncated or not-run outcomes.

| Measure | Result |
| --- | ---: |
| Checking moves correctly identified | 0/32 |
| Nonchecking moves correctly rejected | 32/32 |
| Matched pairs with both check labels correct | 0/32 |
| Responses predicting check | 0/64 |
| Strict-schema-valid responses | 64/64 |
| All eight immediate facts correct | 32/64 |
| Runtime error / truncation / not run | 0 / 0 / 0 |

The 32 all-eight successes are the nonchecking cases. The other seven fields are correct on all 64 inputs, including six pawn captures. This panel contains no positive promotion, castling or en-passant case and no moving-king case. Correct negative answers in those fields do not assess their positive classes. The balanced panel is a diagnostic construction; its all-eight proportion is not an estimate of natural chess accuracy.

## What was tested

Each of 32 new pre-move boards supplies two legal moves from the same origin square, matched on moving piece/colour, capture flag and captured-piece type. Exactly one move gives check. Promotions, castling and en passant are excluded from pairing. Inputs contain only the full pre-move FEN, supplied UCI and a piece map derived from that same board. The model is being asked for facts about a given move, not to choose a move or explain strategy.

The source is the already retained CC0 Lichess Parquet shard at revision `461725966ea46898ec6481372a6326de3281bfbd`, SHA256 `5352e3bff4d6163851c07a0cc922b1ff72875cc6f75d994bdfc3272a37ca9e87`. Intake reconstructs the complete known registry of 30,280 games and 71,463 canonical board keys. It scans 23,463 source rows in physical order, accepts the first 32 eligible new games and chooses each eligible move pair by the frozen hash ranking. Both source roles and both selected successors are excluded against known and newly accepted states. Source answer tails, ratings, themes and future moves do not select pairs or enter prompts.

Independent intake review reconstructs the exact source order, all pair candidates/ranks, exclusions, rule-derived labels and all 64 native token boundaries. This establishes disjointness from known retained games and boards. Original Gotham game identities/full histories and upstream model-pretraining overlap remain unknown; no artificial game ID fills those gaps.

## One fixed selected-only run

The already selected primary fact adapter at step 512 is the only condition. It was selected under the earlier development rule, before this diagnostic; there is no new checkpoint selection, baseline pass, prompt search, training update, teacher search or response retry. The selected checkpoint saw 4,096 primary training presentations. This diagnostic does not compare its balanced result percentage to the earlier convenience-source panel.

The protocol was committed before intake; reviewed source/tests followed. Commit `2739917c014aa0294d80a55186b174acabf9be00` freezes the reviewed runtime, input-only records and execution extension before the single actual run. The generator never opens label or dataset files. It loads the selected adapter once, records the raw token sequences/text and seals all 64 outcomes before a separate owned CPU process opens labels. Unknown/schema-invalid/missing outcomes would receive zero correctness while remaining separate from false predictions; none occurs in this actual run.

The actual job completes in 204.453 seconds, within the frozen 600-second total covering preflight, load, generation, sealing, evaluation and final checks. There is no resource cancellation or forced termination. Its loaded tied BF16 base has 596,049,920 unique parameters; the F32 adapter has 392 tensors and 5,046,272 scalars. The content digests before/after are identical: base `e3af872d3dca520ddbcc6ebd78caf41dccb84203a7835efa7022545db713c008` and adapter `a37d6d6dca148d0bf1089991374b0f9cd2723e080bc84d0cddc09d89b7002a43`. The base digest explicitly excludes LoRA names in the primary parameter order; package file hashes alone are not offered as loaded-base proof.

## Failures and verification remain visible

The intake software review records 104 passes. The final separate runtime review records 51 passes, including harmless actual CPU interpreter/PID/ownership/cleanup and evaluator probes. Earlier software evidence remains preserved: four fixture failures from calling the existing rule helper with the wrong signature; one output-path fixture that correctly collided with the protected source folder; and the independently reproduced partial-seal failure-accounting gap. The narrow final repair writes a separate create-only full-64 failure ledger while preserving any partial raw bytes and refusing evaluator launch. That repair does not alter model loading, prompts, decoding or scoring.

The mandatory historical intake compatibility run separately records 9 failures, 5 passes and 89 errors from unavailable private source/replay fixtures. No full-suite pass or historical gate restoration is claimed. Earlier primary SFT launch attempts also remain separately documented: an interpreter-ownership stop before model loading, then 16 baseline-development responses before a local progress-file replacement failure, both with zero optimizer updates. Those are earlier primary runs, not additional attempts at this diagnostic.

The public evidence inventory maps every original cohort/run file and retained review/failure artifact to an exact-byte public alias, with a complete before/after path/hash inventory. Weights, optimizer state, the source shard and copyrighted media stay private. Archival host paths identify the actual execution; inert source snapshots are not claimed to have executed after relocation.

This result supports the narrow statement that the fixed adapter consistently reports no check on this matched panel. It does not identify the cause, establish natural-distribution accuracy, demonstrate chess strategy or playing strength, or authorize promotion. Practical engineering audits remain distinct from the repository's formal research-promotion gate. This is Codex-assisted research engineering.

[Full counts and all field/class support](../experiments/chess-matched-check-v1/summary.json), [completed independent audit](../experiments/chess-matched-check-v1/completed-evidence/reviews/chess-matched-check-completed-independent-audit.json), [audit source and finite checks](../experiments/chess-matched-check-v1/completed-evidence/reviews/chess-matched-check-completed-audit-evidence.json), [root publication review](../experiments/chess-matched-check-v1/completed-evidence/reviews/chess-matched-check-root-completed-publication-review.json), [exact public aliases](../experiments/chess-matched-check-v1/public-manifest.json), and [completed evidence guide](../experiments/chess-matched-check-v1/RESULTS.md).
