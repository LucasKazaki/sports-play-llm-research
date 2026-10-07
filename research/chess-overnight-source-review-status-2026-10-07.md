# Chess development checkpoint — 7 October 2026

*Status snapshot: 03:38 UTC. Internal development checkpoint; no chess capability or teaching-quality claim.*

## What has been built

- The [v8 typed checker](chess-no-forward-teaching-v8-2026-10-06.md) handles four distinct move-explanation problems from one known practice game. It accepts a narrow pre-move projection, legally checks model-named facts and conditional moves, and renders cautious fixed text. Its 16 focused software checks and four synthetic integration cases passed; no v8 model attempt was made.
- [V9](chess-no-forward-teaching-v9-2026-10-06.md) adds typed alternatives and conditional consequences. Its capture runner freezes source packets, nine-field generator projections, exact requests and a four-case denominator before use. A create-only request marker precedes each single local model call; raw responses, model identity, latency and failures have explicit records. The retained runner suite passed 101 offline tests with fake transport. These tests establish software behavior, not live explanation quality.
- The staged workflow freezes the Stockfish and source protocol before a model response. The [v10 post-generation sidecar](chess-post-generation-comparison-v10.md) later checks its bytes and hashes, then permits a separate paired search only for an eligible, legally checked alternative the model actually named. Missing, bounded, mate or inconsistent observations abstain. Its 34 tests use fake paired results and make no model or engine call.

The no-forward boundary keeps later positions, engine continuations, alternative scores, Game Review labels and evaluator results out of the generator request. The [capability gate](chess-commentary-capability-gate-v1.md) remains open.

## Independent source review

A passing native command or synthetic test is separate from an accepted source review. The registered review requires a complete signed read of the selected source, tests and result, followed by a concrete function-level verdict with limits.

| Area | Status at this snapshot |
| --- | --- |
| V8 | Full source acceptance is open. The r7 reviewer timed out after 900 seconds with no signed read or verdict. A materially narrower r8 review emitted a 2,036-byte bundle for one reply-choice guard; its developer callback is pending. The r8 native success is execution evidence only. |
| V9 | An initial `build_request` reviewer read its complete bundle but gave a generic test-pass summary, so it was not accepted. A narrower review hit a model loaded-state readback failure before reading the source and returned to the queue without consuming an attempt; capture-entry and source-packet reviews are also waiting. The 101-test result does not close those reviews. |
| V10 | One signed, independently audited PASS covers **two protocol-byte guards only** (review task `7c204768-5dae-413c-b0cf-df26a92a8608`). The later input reviewer timed out after 900 seconds without a signed read or verdict. Upstream and paired-result slices remain staged. This is not whole-v10 acceptance. |

No reviewer has accepted the complete v8/v9/v10 path or the first live four-case trial.

Two developer callbacks in a row timed out without reading their source bundles. New review starts are temporarily paused while a bounded runtime timing diagnostic is tested. A V9 callback that was active as the pause began subsequently failed at the loaded-model readback step; the timing alone does not establish why. These are review-throughput problems, not evidence about move-explanation quality.

## Practice sequence and claim boundary

A [four-case practice plan](chesscom-breadth-practice-plan-2026-10-06.md) and [scoring worksheet](chesscom-four-case-scoring-worksheet-v1-2026-10-06.md) are staged for four already inspected positions from the same game: freeze protocol and requests, retain one attempt per case, check responses offline, then run any eligible v10 comparison after the answer is sealed. Failed, interrupted and unattempted cases stay in the original denominator. The worksheet is unscored and keeps factual admission, a verified contrast or unresolved ranking, abstention, teaching value and judge records separate. The generator supplies typed claims rather than a free-form lesson; any later teaching rating must bind the exact checker-rendered text to the raw claim. Dated Game Review paraphrases are not preserved comparator answers.

This work does not establish why every move was good or bad, Chess.com parity, professional commentary, a game-disjoint holdout result, or competence in other board games or sports.

## Next steps

1. Resolve the pending finite reviews using each callback's signed full-read receipt and line-cited verdict. Preserve timeouts and nonconforming responses; do not count them as passes.
2. When source review is accepted and the serial local-model lane is free, recheck frozen hashes and vacant create-only paths, then run the staged four-case capture once. Inspect all raw attempts and failure rows before offline evaluation.
3. Run v10 only after the v9 responses and checker records are sealed. Score factual claims and teaching value separately, retaining qualified human judgment and unresolved cases. A fresh, preregistered, game-disjoint study is still required for the commentary capability gate.

