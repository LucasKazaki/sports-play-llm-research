# FootballMaster long-form v2: sealed experiment report

**Status:** primary football semantics **NO-GO**; infrastructure and retrieval demo **GO for research review only**  
**Experiment completed:** 2026-08-28 UTC  
**Prediction seal:** `7a8260cc109e6cf60433c186d5000030fdf38aa905382460aae1dbd0960ec8f1`  
**Core verification:** pass (`artifacts/footballmaster/longform-v2/verification-receipt.json`)

## Answer first

The scale experiment did what it was supposed to do operationally and exposed a decisive semantic failure. A local `google/gemma-4-e4b` VLM processed real American-football programs in deterministic 30, 60, and 120 second windows using eight silent frames per window. Development used three games, prompt selection used one validation game, and the frozen test used 36 windows from two untouched games. Every request and response is hash-bound, all 36 test windows are searchable, and the football runtime has no dependency on the soccer runtime. This is sparse sampling over a 5.629-hour corpus—not a dense entire-game index: the 69 unique windows cover 2,760 seconds (0.7667 hours) after overlapping durations are merged.

The primary result is not a play-detection success. The selected prompt returned valid JSON for 35/36 held-out windows, but it set `abstain=true` for all 36. In 27 of those windows it simultaneously asserted one or more events. It also assigned `scoring` to generic action without explicit scoring evidence 126 times across 21 windows. Because there are no human-adjudicated event labels, this experiment measures delivery, abstention consistency, unsupported-claim behavior, and searchability—not event accuracy. The correct research conclusion is **semantic NO-GO**.

The live UI deliberately makes that failure visible. It is safe to show as a systems-and-methodology demo: natural-language query expansion, deterministic search over sealed reports, exact source-video playback, and explicit failure gates. It is not safe to pitch as a coach-ready detector.

## Research question

Can a free local VLM turn long American-football video into detailed, searchable event reports without using commentary, filenames, team metadata, rosters, or labels as shortcuts?

The experiment tests three narrower questions:

1. Can the model reliably deliver the requested structured report at 30/60/120 second horizons?
2. Do its saved reports remain internally consistent and visually conservative on whole-game-held-out video?
3. Can a coach-style text query retrieve the saved reports and jump back to the exact video evidence without adding new semantic claims?

## Corpus and split

The verified corpus contains six real single-game broadcast programs from Berkeley Community Media/Internet Archive, totaling **20,265.7455 seconds = 5.62937375 hours** and **2,095,093,021 bytes**. Every file has one H.264 video stream and one AAC-LC 44.1 kHz stereo audio stream. The source manifest file SHA-256 is `da0e58d2ef1a0780a54dfa82d03c0a936f08c8dc61d24cb3a505fdc776713b68`; the verification binding SHA-256 is `a4826cdad27d374ece413ceb0a0a691441183a7d6c8949ee82b53443c9456bab`.

| Split | Programs | Duration | Experimental use |
|---|---:|---:|---|
| Train | Pittsburg–Berkeley JV; Logan–Berkeley JV; Castro Valley–Berkeley varsity | 9,886.877 s | prompt development and secondary pseudo-label baseline |
| Validation | Bishop O’Dowd–Berkeley varsity | 3,939.936 s | locked label-free prompt selection |
| Test | San Leandro–Berkeley; Encinal–Berkeley JV | 6,438.9325 s | frozen primary evaluation and search index |

The split unit is `game_id`; no game crosses splits. It is not team-held-out or broadcaster-held-out—Berkeley and the same source collection recur—so source-style generalization is unmeasured. The source metadata establishes long single-game programs, not guaranteed uncut every-play completeness. Accordingly, the project must say “long game programs” or “whole-game-held-out split,” not “complete games” or “every play.”

### Temporal coverage boundary

The corpus duration is a data-availability denominator, not the amount of unique video submitted to the VLM. The frozen manifest contains 69 windows totaling 4,830 nominal seconds; because the 30/60/120-second windows are nested around the same anchors, their interval union is 2,760 seconds (0.7667 hours, 13.6% of the 20,265.7455-second corpus). By split, unique coverage is 1,080 seconds train, 240 seconds validation, and 1,440 seconds test. The test index’s 36 overlapping windows total 2,520 nominal window-seconds while covering 1,440 unique seconds from held-out source programs totaling 6,438.9325 seconds. It therefore searches sampled intervals—not every moment in either held-out program. Building a truly entire-game searchable index remains planned work.

## Frozen input protocol

- Window durations: 30, 60, and 120 seconds.
- Frames: eight ordered JPEG samples centered in eight equal temporal bins.
- Test windows: six deterministic fractional positions per duration per game, yielding `2 games × 3 durations × 6 positions = 36`.
- Model input: prompt text plus silent JPEG frames only.
- Explicitly excluded: audio, commentary, source title, filename, team name, roster, split label, and event label.
- Visible pixels such as a scoreboard remain available because they are genuinely in the video image.
- Temperature: 0.
- Primary maximum output: 2,200 tokens.
- Primary request policy: strict structured JSON, with bounded recovery receipts.

The frozen window manifest SHA-256 is `cd8447348a2c2df779518728be359365623ffe1052db46bb531c5c49826c1ee9`. The 30-query set SHA-256 is `964dcb285ca5f67edb6950ba6f834d2d35c601ab9fbb385d6ee549b8a2d86aaa`.

## Model and hardware identity

The loopback endpoint exposed `google/gemma-4-e4b` through a llama.cpp-compatible API. The captured model metadata reports:

- 7,518,069,290 parameters;
- GGUF `Q4_K - Medium` quantization;
- 5,319,465,128-byte model payload;
- 8,192-token runtime context;
- multimodal and completion capabilities.

The model-identity receipt SHA-256 is `13cae81e0dc7e04232e0930d4e0f6b82005a617d0a4cc1e3b76e486f3f7c9bc8`. The host exposes an NVIDIA RTX 3070 8 GB and GTX 1080 8 GB with driver 560.94; primary inference used the loopback service on GPU 0. This is a runtime identity, not a claim that the underlying model weights were trained in this project.

## Prompt development and freeze history

Prompt development is not VLM fine-tuning. No VLM weights were updated.

The initial candidates were a direct report prompt (A) and an evidence-first prompt (B). Development inspection found B could call generic action `scoring`, so an append-only, zero-test amendment added a guarded semantic prompt (C). The original C with a 2,200-token budget failed JSON delivery in 6/9 inspected calls. That failure condition is preserved. A second append-only amendment kept the same semantic prompt but raised the bounded generation budget to 3,200 tokens and added structured-four-frame and compact-JSON recovery modes. This C3200 condition achieved 33/33 valid development reports.

Terminal development calls:

| Candidate | Calls | Valid | Invalid | Attempts | Elapsed |
|---|---:|---:|---:|---:|---:|
| A direct | 33 | 33 | 0 | 33 | 822.516 s |
| B evidence-first | 33 | 31 | 2 | 37 | 909.550 s |
| C guarded, 2,200 tokens | 9 | 3 | 6 | 21 | 497.524 s |
| C guarded, 3,200 tokens | 33 | 33 | 0 | 40 | 1,231.961 s |

The locked validation proxy prioritized schema validity, frame citations, lower unsupported-claim risk, lower frame fragmentation, and then latency. It did not use correctness or labels. Scores were A `607.9769`, C3200 `605.9444`, and B `584.9755`; A was selected and frozen before any test call. The result is instructive: the proxy favored A, but the held-out semantic consistency audit later showed A was unusable. The proxy therefore needs a hard abstention-consistency gate in the next protocol.

Frozen configuration hashes:

- protocol: `111aff29c06fa16de0c4686896cd9d31964b3a464c7a4ac86fa379facb458f0a`
- prompt candidates: `0e5033f6b951c34e83111eae34d8a26cba9bbf64ea7d89855b129e2288cba2f8`
- prompt selection: `89c11cedeb83e22700e8498b87bb6e7601f14378313c14186df0189386853ce7`
- selected prompt A: `daaf5ad849c3d4201267dd4bfa5227e0cfc5fae93d6a348cf98789705d63604d`
- append-only amendments: `9600028d367ce16ead54f9922f028f02cba0419bc149f5cfc5a6fad42f8cdee9`

## Exact call denominator and timing

The frozen plan contains **144 terminal VLM calls**: 108 development calls and 36 primary test calls. Across all candidates, those calls required 169 bounded attempts. There were 135 valid terminal reports and nine invalid terminal reports. Total receipt-measured call time was **4,257.730 seconds**; mean terminal-call time was 29.568 seconds and median was 28.289 seconds.

Candidate A has 69 total calls: 27 train, six validation, and 36 test. Its total elapsed time was 1,618.696 seconds. The frozen test alone took 796.180 seconds across 38 attempts: mean 22.116 seconds per terminal window and observed receipt p95 28.884 seconds.

Failed calls remain in the denominator. Recovery attempts and their raw model envelopes are retained rather than silently overwritten.

## Frozen held-out result

| Measure | Result | Interpretation |
|---|---:|---|
| Test denominator | 36 windows | two games; 12 each at 30/60/120 s |
| Valid normalized JSON | 35/36 | format delivery mostly worked |
| Terminal schema/recovery failures | 1/36 | `fmw-9155b25178e07957` |
| `abstain=true` | 36/36 | selected prompt abstained everywhere |
| Abstain plus nonempty events | 27/36 | direct logical contradiction |
| Unsupported `scoring` assignments | 126 events in 21 windows | generic action labeled high-stakes scoring without explicit score evidence |
| Human-adjudicated event truth | 0 windows | event accuracy cannot be computed |

The saved output histogram contains 137 `scoring`, 60 `pre_snap`, four `run_play`, and one `stoppage` assignments. Those counts are model outputs, not real-event prevalence. The unsupported-scoring check is deliberately narrower: it flags a `scoring` event only when its saved action, outcome, and field-context text contain no explicit scoring-evidence term.

The primary semantic verdict is **NO-GO** for three independent reasons:

1. abstention is logically inconsistent with asserted events;
2. generic or unknown action is repeatedly assigned the high-stakes scoring type;
3. no human-adjudicated truth exists for event accuracy or calibration.

## Search index and live demo

All 36 frozen test reports are stored in a football-only JSONL index covering both held-out games and all three durations. Thirty coach-style queries are frozen and materialized. A football-owned adapter:

- verifies the prediction seal and core verification receipt;
- checks the search-index hash and the source-video hashes;
- serves only project-contained, rights-manifest-bound media;
- optionally uses the local LLM to expand the coach’s text query;
- falls back to literal text when the query LLM is offline;
- uses deterministic BM25 over already-saved report text;
- projects result and cited-frame times back to the source video;
- never sends video, audio, labels, model reports, or audit results to the query LLM.

The shared UI now prefers long-form v2 and labels the older nine-window touchdown probe as a legacy fallback. The football route uses the football-owned loopback validator, loader, query interpreter, and search code. A focused test blocks the soccer engine import and still loads and searches FootballMaster. Another integration test makes every soccer helper raise and proves that the long-form football load/search path still succeeds.

The demo is intentionally framed as an evidence-review surface. Its top-level warning shows the 27/36 contradiction count; the evaluation panel shows 35/36 schema validity, 27/36 contradictions, 126 unsupported-scoring events across 21 windows, and the weak-probe 1/5 validation result. Search cards expose abstention reasons and model-cited sampled frames. This makes a failure easy to inspect instead of hiding it behind a polished search box.

Visual QA evidence:

- `artifacts/footballmaster/longform-v2-demo/ui-desktop-1365x768.png`
- `artifacts/footballmaster/longform-v2-demo/ui-search-results-1365x768.png`
- `artifacts/footballmaster/longform-v2-demo/ui-mobile-390x844.png`

The desktop and mobile layouts were exercised in a real browser, the literal-fallback search returned 12 playable results, and the browser console contained no warnings or errors. The source-video byte-range route was also exercised.

## Secondary visual-probe baseline

The only actual parameter fitting in this work is a deliberately secondary baseline: frozen ImageNet MobileNetV2 logits averaged over frames, followed by a fitted ridge head. It used guarded-C development pseudo-labels—not human truth.

- training windows: 18;
- pseudo-label classes observed: `other`, `pass`, `run`;
- fitted values: 5,003, including 3,003 supervised head parameters;
- train agreement with pseudo-labels: 18/18;
- validation agreement with pseudo-labels: 1/5;
- test denominator: 0, because guarded C was never run across the frozen primary test;
- event accuracy: not measured;
- generalization claim: prohibited.

This baseline does not generate the primary reports, does not power search, and must not be described as FootballMaster performance.

## Post-seal commentary audit

Only after the prediction seal was written, a CPU-only `faster-whisper==1.2.1` / `tiny.en` audit transcribed four fixed 30-second test windows. The receipt is bound to the prediction-seal root; ASR was not VLM input, was not search input, is not ground truth, and has no human adjudication.

- two windows yielded short transcripts: “First down, jacks.” and “That’s down, Berkeley.”;
- two windows yielded empty transcripts;
- all four rows are labeled `unverified_side_by_side_only`.

The audit receipt SHA-256 is `84b6b95b30952b9e9e46118b4ccf33181680bc40f5f14165e53e16a71cd498d0`. It supports one conclusion only: commentary is technically available as a future weak cross-check. It does not establish that either ASR text or VLM output is correct.

## Seal and reproducibility

The prediction seal was written at `2026-08-28T03:11:51.250721Z`, covers 1,797 files, contains no audio or commentary artifact, and has root hash:

`7a8260cc109e6cf60433c186d5000030fdf38aa905382460aae1dbd0960ec8f1`

Core verification passed at `2026-08-28T03:14:02.775776Z`. It confirms the five-hour corpus gate, source-manifest binding, freeze hashes, prediction seal, 3/1/2 game split, 36 test windows over two games and three durations, zero call-receipt errors, 30 frozen queries, a two-game/three-duration index, and zero package-isolation violations.

## What to say in the meeting

Use this concise technical framing:

> We built a verified 5.63-hour football corpus, sparsely sampled 0.77 unique hours, and froze a game-held-out, silent-frame VLM evaluation at 30, 60, and 120 seconds. The infrastructure is reproducible and the 36 held-out windows are searchable, but the selected local model is not semantically reliable: it abstained on all 36 test windows, contradicted itself on 27, and made 126 unsupported scoring assignments. So the contribution today is a leakage-safe evaluation and evidence-search system that reveals model failure—not a coach-ready event detector or an entire-game index. The next experiment adds dense coverage and human temporal labels while keeping commentary strictly post-hoc.

Do not say:

- “FootballMaster detects plays accurately.”
- “We trained the VLM.”
- “The six files are guaranteed complete games.”
- “The entire 5.63 hours were indexed.”
- “Commentary proves the visual prediction.”
- “The search result is a real event label.”
- “The validation proxy measured correctness.”

## Next experiment

The highest-value next step is not more unlabelled prompting. It is a small human-adjudicated benchmark:

1. annotate start/end, event family, visible evidence, and `not_visible/ambiguous` for 150–300 windows;
2. keep games, teams when possible, and source programs disjoint;
3. replace free-form event-type generation with constrained detection plus a separate evidence-grounded description;
4. make `abstain=true` structurally require `events=[]`;
5. make high-stakes classes such as scoring and turnover require class-specific visual evidence fields;
6. report event precision/recall/F1, temporal IoU or tolerance-based localization, calibration/selective risk, retrieval Recall@K/MRR/nDCG, and latency by window duration;
7. compare eight sparse frames with denser sampling or short continuous clips under the same adjudicated test;
8. keep ASR/commentary sealed until visual predictions are final, then treat it as a noisy auditor rather than truth.

A six-window guarded-C diagnostic has been frozen after the primary seal only for error analysis. It is explicitly post-hoc and cannot change the primary denominator or claim. Its plan is `artifacts/footballmaster/longform-v2-posthoc-c-diagnostic/diagnostic-plan.json` with SHA-256 `ebb5b6e8bf91c1cbe38225d20e25dfc58cef451e4676abe265c2171fd87fd675`.
