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

## Update at 04:47 UTC

The focused V10 suite now has **35 passing synthetic checks**. The new case sends a relative `v9_run_dir`, expects the exact `v10_run_dir_must_be_absolute` error, and confirms that search was never called. This closes one test-coverage gap without changing the V10 source or establishing model quality.

The reviewer bottleneck is still real. V9 `build_request` r2 (`a70009da`), V9 capture-entry r3 (`cba23d82`), V9 `_source_packet` r3 (`43b8301d`), and V10 input-path r5 (`594cee2c`) each received a complete, task-bound source/test/result read, but their summaries used broad or mistaken citations and were independently marked **changes required for the reviewer result**. In the source slices inspected, those audits identified no new code defect. Narrower V8 reply-choice r8, V9 `build_request` r3b, and V10 outside-artifacts r6 reviews are queued or running. Their native command receipts prove only that the requested bundles were produced; they are not source verdicts. The four-case model practice remains on hold.

The open Chess.com review was rechecked on 47.Rb8. It still displayed **best**, while its visible score changed from the 6 October note's −6.67 to −6.69. The [dated observation](chesscom-review-breadth-observations-2026-10-06.md) records this as interface evidence, separate from the frozen source game and any model answer.

## Update at 04:50 UTC

The V9 `_source_packet` review exposed a specific test gap: the existing capture test changed the whole helper but did not isolate its wrong-ply, packet-digest, and projection-digest guards. Three new direct negative cases now assert the exact errors and confirm that projection is never built after either early packet failure. They passed alone: **3 passed, 30 deselected**. The clean GitHub checkout intentionally lacks the local game PGN and baseline, so its first full-file attempt failed on those absent assets; the fixture now explicitly skips only when those files are absent. The changed full-file run was **3 passed, 30 skipped**. Those skips are not integration passes, and the canonical local asset-backed suite has not been rerun with this new test file.

## Update at 04:59 UTC

The narrow V10 outside-artifacts reviewer also read its complete 1,376-byte bundle but returned an instruction echo instead of the actual error name and test result. Independent audit marked that **review result** changes required; it found no new defect in the shown source guard. A small offline checker now catches these missing or disconnected citations against a human-authored scope and a verified full-read receipt. Its 12 focused checks passed, including two misleading reviews rejected and one accurately scoped protocol review accepted as text. It does not judge chess correctness or replace independent source review. V8 reply-choice is running and V9 `build_request` remains queued; the four-case practice run is still waiting.

## Route check at 05:02 UTC

A read-only check resolved a misleading configuration comparison. The **running** Studio worktree and live Sports developer profile both select `loops-cpu-gpt-oss-20b`, matching the model recorded in the failed source reviews. The earlier Qwen setting came from a different checkout; its endpoint was not serving, and that file does not satisfy the live one-model route policy. This explains the apparent model-name mismatch, not the reviewer's inaccurate prose. No model route or active review was changed.

## Update at 05:19 UTC

V8's narrow reply-choice reviewer read the complete source/test bundle, but its PASS gave line ranges without describing the `>1` legal-reply condition, the rejection reason, or the five-reply test assertions. The independent verdict is **changes required for the review result**; no source defect was identified in that slice. V9's revised `build_request` review is running.

One changed-instruction V10 review is now queued. The previous V10 reviewer had copied its answer-shaped instructions almost verbatim; this request asks for observed values under plain labels. Its native command completed once and produced the exact audited 1,376-byte bundle, but the developer has not yet produced a signed read or source verdict. It remains an experiment in review wording, with the four-case practice still gated.

## Update at 05:24 UTC

The V9 `build_request` reviewer reached its 900-second deadline before making a source read. Its parent had already passed six inline software negatives; the child produced no source verdict. The changed-instruction V10 reviewer has started.

After the V9 attempt settled, I copied the exact new V9 test file from the draft branch into the local asset-backed checkout. The V9 capture source bytes were unchanged. The focused capture test file now passes **33/33** with the local game and baseline present, so the three direct packet-pin negatives have been checked in the actual practice environment as well as the portable checkout. This does not resolve the reviewer timeout or authorize the four-case model run.

## Update at 05:32 UTC

The changed-instruction V10 outside-artifacts reviewer completed a full signed read of its 1,376-byte bundle. It improved on the earlier instruction echo by naming the actual error and prior test count, but omitted the path predicate, the injected-search handoff and several exact test assertions. The independent result audit therefore marked **changes required for the reviewer artifact**. It found no defect in the bounded source slice. The four-case practice is still waiting for accepted source reviews.

A read-only trace of the V9 timeout located the delay in the first required file-read model step: the local model was asked for high reasoning without an output cap, generated about 15,000 tokens and hit the 900-second deadline before calling the file tool. Two earlier reviewer timeouts showed the same pattern. A narrow Studio-side adjustment to that first read is being prepared offline; the trace supports a repair hypothesis, not a verified cure.

After V10 R7 settled, I moved the already committed relative-path negative test into the local checkout that has the practice assets. The unchanged V10 source and updated focused test file now pass **35/35** there. This verifies the path guard in both checkouts; it does not establish model, engine or teaching performance.

## Update at 05:34 UTC

The R7 audit also identified an uncovered equality case: the V9 run directory must not be the `artifacts` directory itself. A direct negative test now supplies that exact directory, checks the literal rejection label, and confirms that no search callback runs. The V10 source did not change. The complete focused V10 file passes **36/36** in both the clean GitHub checkout and the local checkout with practice assets. These are fake-search software checks, not a live explanation result.

## Update at 05:44 UTC

A revised V9 `_source_packet` review packet passed an independent submission check and ran once through the project's native executor. Its server result contains the complete bounded guard function, the three direct negative cases, and a fresh **33/33** focused software result. The reviewer child is still queued, so this is transport and test evidence only; no V9 source verdict has been accepted.

The proposed Studio fix for the first-file-read timeout is isolated from the running service. Its targeted test failed before the edit and passed afterward; the focused module suite passed **60/60**, and static and contract checks passed. One additional schema test fails the same way against the copied baseline. The full Studio gate and a live read have not been verified, so the proposal has not been activated.

## Update at 05:57 UTC

An independent check found that the proposed low-reasoning first read needed a matching correction when it produced no answer. That exact case now has a failing-before, passing-after test, and the isolated Studio module suite passes **61/61**. The narrow patch and audits are saved on the companion Studio evidence branch as an **offline, unactivated** candidate. Full Studio verification and a live fenced read remain open.

The next V10 path-guard review is prepared with the new 36-test file and a bounded source/test/result packet. Its original reviewer instruction still looked like a fill-in answer, so it was replaced with bare section headings before submission. The revised request passed a separate predispatch check but remains unsubmitted while the V9 child waits for the shared local model lane. Neither packet is a source verdict.

## Handoff at 06:09 UTC

The V9 reviewer child is still waiting for the shared local model lane. A read-only check corrected a misleading top-level zero counter: the active Sports goal worker's durable session advanced to **9 model requests and 7 tool calls**, and the local model log showed continuing generation. It is making progress, so I left it running. When the V9 child gets the lane, its full signed read and exact source/test findings must be audited before the four-case practice can start. The V10 request remains staged behind it. The hourly overnight continuation has these task IDs and evidence paths.

## Update at 07:16 UTC

The earlier goal worker later hit its durable inactivity deadline. Its saved session resumed and finished with a proposal and an existing **36/36** V10 test run, but no new explanation or capability result. The following verifier is blocked by an exact recovery mismatch: eight required reads versus eleven retained reads, including optional reads. A bounded Studio-side repair is being tested offline; no live runtime change has been made.

The V9 reviewer eventually read the entire signed 3,201-byte bundle, but its summary misplaced the selected-ply source line, called three direct cases “33 parameterized tests,” and omitted the test-line citations and key limits. Independent audit marked **changes required for the reviewer artifact**, with no source defect identified in the shown guard. I narrowed a new V9 review to one wrong-ply case; its request was independently checked and submitted once through the native executor. It has no reviewer verdict yet.

The prepared V10 path-guard review also ran once through the native executor. Its signed 8,074-byte bundle contains the current source/test slices and a fresh **36/36** fake-search result; its developer reviewer is queued behind the local model lane. Native transport and software tests do not open the four-case practice gate. The Chess.com comparison worksheet remains unscored.

