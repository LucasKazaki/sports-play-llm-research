# Independent data validation — real-footage soccer pilot

**As of:** 27 August 2026, 08:07 UTC  
**Audience:** Archit demo and technical review  
**Overall assessment:** **GO for the local demo, with explicit caveats. NO-GO for a benchmark, model-quality, or generalization claim.**

## Question answered

Are the quantitative results, provenance chain, isolated-runtime claims, commentary cross-check, and offline demo internally consistent and safe to present as a small real-footage feasibility study?

Yes. Every headline count and rate recomputes from the clip-level records; the final demo matches its hash-bound inputs; and the live runtime passes its ownership, binary-hash, port, health, receipt-hash, and single-model checks. The scientific result is negative but useful: isolating the server fixed completion reliability, while the six-clip recovery rerun achieved 0/6 allowed-window accuracy. That is a systems/failure-analysis result, not evidence of soccer understanding.

## Methodology review

The source-to-output chain was independently traced as:

1. SoccerDB's public mapping was checked at commit `ac9c9c50d14b683b8eca464f55a700cffb95b629`; its SHA-256 is `53c445988019ee4b50ed408fae949f903a90afbe02158c62296559a769493b02`. Each chosen match half has exactly one matching row.
2. Both authorized acquisition-receipt hashes, both clip-manifest hashes, the source video/label/Echoes hashes, and all 11 sets of silent-video, review-video, and aligned-commentary derivative hashes were recomputed. They match.
3. The five development clips and six validation clips are match- and ID-disjoint. Each clip is 10 seconds. The manifests declare zero audio streams for every VLM copy and at least one audio stream for every local-review copy.
4. Frozen v1 and recovery-v2 configs bind the correct development summary and both manifests. V2 also binds the isolated runtime receipt. Prompt, taxonomy/schema hash, sampler, 12-frame/12-image sampling, and 1,600-token budget agree across v1 and v2.
5. Every saved prediction/receipt hash was matched back to the public summary. Failure records were retained rather than dropped.
6. Strict commentary relations were recomputed from the already sealed visual predictions. Commentary never changed a visual answer.
7. The final demo receipt, six-card HTML, 12 copied videos, and every input hash were reconciled. The HTML contains no absolute/private path, credential-shaped string, external asset URL, or ASR payload field.

The precise data claim is **SoccerDB-mapped SoccerNet footage**. The evaluated annotations are SoccerNet-v2 point labels, not SoccerDB event segments.

## Calculation spot-checks

### Frozen primary visual v1

| Metric | Independent recomputation | Saved value | Result |
|---|---:|---:|---|
| Requested | 6 | 6 | Verified |
| Completed / failed | 3 / 3 | 3 / 3 | Verified |
| First-pass schema-valid rate | 3/6 = 50.0% | 50.0% | Verified |
| Allowed-window accuracy | 1/6 = 16.7% | 16.7% | Verified |
| Single-label exact accuracy | 0/2 = 0.0% | 0.0% | Verified |
| Median completed latency | 110.624 s | 110.624 s | Verified |

The three `TimeoutError` records remain in all applicable requested-set denominators. There is no survivorship exclusion.

### Post-hoc visual recovery v2

| Metric | Independent recomputation | Saved value | Result |
|---|---:|---:|---|
| Requested | 6 | 6 | Verified |
| Completed / failed | 6 / 0 | 6 / 0 | Verified |
| First-pass schema-valid rate | 6/6 = 100.0% | 100.0% | Verified |
| Allowed-window accuracy | 0/6 = 0.0% | 0.0% | Verified |
| Single-label exact accuracy | 0/2 = 0.0% | 0.0% | Verified |
| Median completed latency | 9.306 s | 9.306 s | Verified |

V2 uses exactly the same six validation clip IDs as v1. The report and UI correctly call it a **post-hoc serving-recovery rerun on the same clips**, not untouched or independent validation. Completion improved from 3/6 to 6/6, but semantic correctness did not improve.

### Strict commentary recovery v3

| Metric | Independent recomputation | Saved value | Result |
|---|---:|---:|---|
| Queried / schema-valid | 6 / 6 | 6 / 6 | Verified |
| Support / contradict / uninformative | 2 / 2 / 2 | 2 / 2 / 2 | Verified |
| Support among informative relations | 2/4 = 50.0% | 50.0% | Verified |
| Median text-model latency | 5.792 s | 5.792 s | Verified |

The sorted latencies are 5.441, 5.594, 5.759, 5.825, 5.928, and 5.974 seconds. As an auditor-only descriptive cross-tab, commentary's proposed label matched an allowed window label in 3/6 cases, but neither of the two `supports` relations supported a correct visual answer. That is strong case-level evidence that **agreement is not correctness**; it is not a commentary benchmark.

## Runtime and source review

The live Windows server reports the pinned llama.cpp identity: release `0.2.0-dev`, build `10566`, commit `bb4caa754`. The parser accepts the live Windows version format and rejects non-pinned identity. The launch contract contains:

- one model and multimodal projector;
- 8,192-token context and parallelism 1;
- reasoning budget 256;
- exact reasoning-budget message `I have to answer now.`;
- `--no-webui` and a receipt value of `webui_enabled=false`;
- loopback-only networking and no API key.

The recovery batch verifies the frozen-v2 receipt before the batch and again before every clip. The current live status passes all nine checks: Bionic suspended, Bionic models unloaded, CLI commit matched, process alive, process-image hash matched, port owner matched, receipt hash matched, health passed, and exactly the expected model served.

The focused runtime, UI, frozen-config, batch, commentary, and overlap suites passed **84/84 tests in 4.12 seconds**.

## Live-demo integrity

The final offline bundle renders six silent-first cards and six separately gated commentary videos. Its visible metrics are exactly the recovery-v2 values: 6/6 complete, 100.0% schema valid, 0.0% allowed-label accuracy, and 0.0% single-label exact accuracy. It shows 2 support, 2 contradiction, and 2 uninformative commentary relations.

The UI visibly says:

- `Post-hoc serving-recovery rerun`;
- the same clips were reused;
- the original failed pass is preserved;
- this is a systems result, not a benchmark;
- the media is private and non-redistributable.

All 12 copied-media hashes match both the demo receipt and the source manifest. The HTML hash matches its receipt. There are no external scripts, fonts, trackers, network assets, AI-generated images, absolute filesystem paths, persisted credentials, or exposed ASR text fields.

## Issues found

### P1 — blocking

None.

### P2 — non-blocking but should be fixed

1. **Stale real-data doctor.** The public doctor artifact predates the overlap build, names the earlier E2B model, and does not carry the final manifest hashes. Do not cite it for the final demo. Rerun it against the overlap manifests and E4B runtime or omit it from the handoff.
2. **UI runtime-receipt binding is not fail-closed in the generator.** The actual demo's runtime hash is correct, and inference was enforced correctly. However, the UI builder will project any supplied runtime receipt without comparing its hash with the frozen-v2 and visual-summary bindings. Add that equality check and a negative test for future builds.
3. **Recovery context is not intrinsic to the summary schema.** The report and UI are clear, but the immutable recovery summary retains the generic v1 summary schema and has no explicit `post_hoc` field. Keep it paired with the recovery filename, frozen-v2 config, and disclosure; add explicit recovery metadata only in a future schema.

## Required caveats for Archit

- This is 5 development clips plus 6 validation clips from two match halves. It cannot estimate generalization across matches, leagues, broadcasts, or models.
- Recovery v2 reuses clips already inspected in v1. It establishes non-reproduction of the serving timeouts, not an independent performance estimate.
- SoccerNet-v2 provides point labels. Ten-second event-centered windows can contain multiple mapped actions, lead-up, aftermath, and replay cuts.
- Only two validation windows are single-label eligible, and the windows were not independently adjudicated for answerability from the 12 sampled frames.
- Commentary is noisy secondary evidence, may lag or describe context, and never overrides the sealed visual answer.
- No model weights were trained or fine-tuned. “Training/development” means model, prompt, schema, sampling, and runtime selection.
- The pilot has no calibrated spatial grounding, player tracking, or trajectory score.
- The authorized media is private, non-commercial, and non-redistributable.

## Verdict

**GO for the local Archit demo as an honest real-footage systems prototype and negative feasibility result.** Present v1 and recovery v2 together. Lead with the correct claim: isolation repaired serving completeness, while the model still failed all six allowed-window decisions in the post-hoc rerun. Do not frame these numbers as a benchmark or as evidence that the model understands soccer plays reliably.

The machine-readable companion is [`data-validation-2026-08-27.json`](../artifacts/soccernet-pilot-v1/data-validation-2026-08-27.json).
