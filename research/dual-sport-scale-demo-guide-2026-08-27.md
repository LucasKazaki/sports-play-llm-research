# Dual-sport scale demo guide: what is verified, what failed, and what comes next

**Evidence snapshot:** August 28, 2026, 1:22 AM EDT  
**Audience:** Archit (computer-science PhD) and the presenter who needs the terminology translated into plain English  
**Scope:** independently verified corpus, isolation, the SoccerMaster candidate and complete-match VLM lanes, FootballMaster long-form v2, the DVIDS external series probe, and the shared evidence-review demo. Systems and semantic verdicts are kept separate.

## Technical summary

The defensible project today is an evidence-first research system, not a finished whole-game coaching product.

- **The data scale is real.** The soccer corpus contains eight SoccerNet game IDs, both halves of each game, 16 decoded videos, and 44,720 seconds (12.4222 hours). The complete-match soccer run uses both full 45-minute halves of one newly acquired authorized test game. The American-football work includes six distinct long programs totaling 20,265.7455 seconds (5.6294 hours) plus one externally held-out, correlated 19-part DVIDS series totaling 11,657.29 seconds. These are separate evidence units with separate rights and completeness limits.
- **The sport implementations are genuinely separated.** `footballmaster/` has no Soccer, SoccerNet, SoccerMaster, or multisport application dependency. A shared UI adapter can call both packages, but that adapter is outside the isolated FootballMaster boundary.
- **Among the completed scale artifacts in this guide, only one model actually trained parameters.** The soccer baseline froze MobileNetV2 image descriptors and trained a 14-class softmax head with 3,598 learned parameters. It reached 167/389 = 42.93% exact candidate-window accuracy on two untouched test games. This is candidate classification, not full-match action spotting.
- **The new complete-match soccer VLM lane is systems GO and semantic NO-GO.** A frozen local Gemma VLM returned valid reports on 96/96 test calls: 90 contiguous 60-second windows cover both full halves, with six additional 30/60/120-second stress windows. After the 1,874-file visual seal was closed, a restricted non-one-to-one ±6-second evaluator corroborated only 3/166 mapped annotations and 3/54 mapped predictions. Direct review found 0/6 reports fully supported, and the anonymization audit found readable lower-third team-name pixels in at least one sampled frame.
- **The earlier 50-window soccer VLM lane remains a separate bounded negative result.** On label-centered silent windows it was correct on 3/50, abstained on 24/50, and underperformed the 4/50 subset-majority rule. It is historical evidence about candidate-window semantics, not the complete-match index.
- **The completed FootballMaster long-form experiment is also a semantic NO-GO.** The protocol made 108 development calls and 36 frozen test calls. The selected VLM abstained on 36/36 test windows, contradicted that abstention with asserted events on 27/36, and made 126 unsupported `scoring` assignments across 21 windows. With no human event labels, event accuracy remains unmeasured.
- **The football sampling is sparse, not whole-game indexing.** The six-program source pool is 20,265.7455 seconds (5.6294 hours), but the 69 overlapping windows cover 4,830 nominal seconds and 2,760 unique seconds. The searchable held-out index covers 1,440 unique seconds from two source programs totaling 6,438.9325 seconds.
- **The external DVIDS result is another systems GO / semantic NO-GO result.** All 57 sparse fixed windows produced schema-valid reports over 3,420 unique sampled seconds, but 56/57 reports abstained, the model still emitted 277 unverified events and 82 `scoring` labels, and there are no human event labels or retrieval judgments. The 19 source-numbered parts are one correlated event and are not proven uncut, every-play, or broadcast-complete.
- **The live UI now prefers the verified SoccerMaster complete-match package in Soccer mode and FootballMaster v2 in Football mode.** At query time, a local language model translates only the coach's sentence into a strict retrieval plan; a clearly labeled literal fallback works when it is offline. Ordinary code searches sealed reports and opens exact source evidence. Historical packages are visibly labeled fallback-only.

The strongest presentation is therefore: **real data, leakage-aware protocols, independent reproduction, useful retrieval infrastructure, and a measured semantic failure that defines the next experiment.**

## Status at a glance

| Surface | Status | What may be said |
|---|---:|---|
| SoccerNet scale corpus | **GO** | Eight game IDs, 16 halves, 12.4222 hours, authentic footage, whole-game-ID splits |
| Soccer trained baseline | **GO, bounded** | 14-class label-centered candidate classifier; 167/389 exact and 294/389 top-3 on two held-out games |
| Soccer complete-match VLM | **SYSTEMS GO / SEMANTIC NO-GO** | 96/96 valid calls; 90 contiguous dense minutes cover both halves; restricted corroboration 3/166 annotations and 3/54 predictions; direct review 0/6 fully supported |
| Soccer complete-match shared GUI | **GO, diagnostic only** | Seal-verified 96-window index, deterministic retrieval, playable private evidence, visible semantic/anonymization warnings, and explicit legacy fallback |
| Soccer 50-window VLM predecessor | **NO-GO for semantics** | The separate label-centered pipeline completed 50/50 valid responses, but exact correctness was 3/50 and detailed coach-search claims are unsafe |
| FootballMaster v2 corpus | **GO** | Six authentic long programs, 5.6294 hours, source metadata and local files hash-bound, 3/1/2 game-held-out split |
| Football whole-game claim | **NO-GO** | Long single-game programs are not source-proven uncut, every-play recordings |
| Standalone `footballmaster/` | **GO** | Static and runtime isolation from all soccer and multisport application code |
| Football long-form experiment | **NO-GO for semantics** | 35/36 valid JSON, 36/36 abstain, 27/36 contradictions, and 126 unsupported scoring events across 21 windows; no event-accuracy claim |
| FootballMaster v2 in shared GUI | **GO, bounded** | v2 is preferred and searchable; semantic failure and sparse-coverage warnings stay visible; legacy is labeled fallback-only |
| DVIDS external series probe | **SYSTEMS GO / SEMANTIC NO-GO** | 57/57 valid sparse windows over 3,420 of 11,657.29 seconds; 56 abstentions, 277 emitted events, 82 scoring labels, and no event gold |
| Entire-match search | **SOCCER INFRASTRUCTURE ONLY** | Soccer has dense complete-match coverage and retrieval, but its event semantics failed; both football lanes remain sparse and none is coach-ready |

## Architecture: separate sport engines, adapter-only integration

```text
SoccerNet media + labels                               Football media
          │                                                 │
          ▼                                                 ▼
prototype/soccermaster_scale/                         footballmaster/
  candidate baseline + 50-window VLM                   football-only schemas,
prototype/soccermaster_longform/                       v2 + DVIDS experiments
  full-match visual VLM, seal, evaluator                     │
          │                                                 │
          ▼                                                 ▼
prototype/soccer_longform_adapter.py              football-owned adapters
          └────────────── saved reports/indexes ────────────┘
                                    │
                                    ▼
                   prototype/multisport_search_demo_server.py
                     shared UI, query planning, retrieval,
                     evidence playback, transparent fallback
```

The isolation claim applies to the two sport engines, not to the shared adapter.

“SoccerMaster scale” is the project experiment name, not a claim that the official SoccerMaster architecture, training recipe, or reported paper result was reproduced. The completed soccer models here are the explicitly documented MobileNetV2-plus-softmax baseline and prompt-only local Gemma evaluations.

Final independent checks found no case-insensitive reference to `soccer`, `soccernet`, `soccermaster`, `multisport_search_demo_server`, or `search_demo_server` anywhere under `footballmaster/`. The package scanner returned no violations. A runtime blocker rejected the other sport engine while the football-owned adapter still loaded and searched FootballMaster v2. The frozen-package focused suites and the full repository suite passed at their recorded verification points; use the immutable receipts for exact historical denominators instead of quoting a moving repository-wide test count.

The shared server intentionally integrates both sport engines and is therefore outside either standalone isolation claim. Its football route now uses a football-owned validator, loader, query interpreter, and search implementation; it prefers the sealed v2 package and falls back to the older pilot only with an explicit legacy label.

## The two verified corpora and their rights boundaries

| Property | Soccer scale corpus | FootballMaster v2 public corpus |
|---|---:|---:|
| Source unit | SoccerNet game ID with two half files | Berkeley Community Media single-game program on Internet Archive |
| Units | 8 games; 16 video halves | 6 games; 6 program files |
| Decoded duration | 44,720 s = 12.4222 h | 20,265.7455 s = 5.6294 h |
| Bytes | 3,019,689,368 | 2,095,093,021 |
| Split | 4 train / 2 validation / 2 test games | 3 train / 1 validation / 2 test games |
| Model-input audio | Excluded | Excluded |
| Rights basis | User-authorized SoccerNet NDA access; local, non-commercial research | Institutional uploader metadata names CC BY-SA 3.0; admitted for local, non-commercial research |
| Redistribution | Raw media must not be redistributed | License conditions apply; model-weight release remains on institutional-review hold |
| Important limit | Two admitted halves establish structural completeness of each corpus game, not an external every-play audit | Long single-game programs are not proven uncut or every-play complete |

### Soccer corpus details

The eight game IDs are pairwise disjoint across train, validation, and test. All windows from one game inherit that game's split. The corpus generated 1,749 unique candidate windows. The single-label ambiguity rule retained 1,555 examples: 810 train, 356 validation, and 389 test.

Each retained example is a 12-second, silent window represented by 12 sampled frames. Event-centered windows come from SoccerNet annotations; deterministic background windows are placed away from those annotations. This design evaluates **classification after a candidate is supplied**. It does not ask the system to discover all events in untrimmed video.

The public receipt contains no credentials, raw media, or raw-media paths. SoccerNet media remains subject to its access agreement and must not be shown or redistributed outside the authorized setting.

### Football corpus details

The exact split durations are:

| Split | Games | Seconds | Hours |
|---|---:|---:|---:|
| Train | 3 | 9,886.877 | 2.7464 |
| Validation | 1 | 3,939.936 | 1.0944 |
| Test | 2 | 6,438.9325 | 1.7886 |
| **Total** | **6** | **20,265.7455** | **5.6294** |

All six local byte counts, MD5, SHA-1, and SHA-256 values matched both the manifest and cached Internet Archive metadata. Independent full video-only decoding passed for 6/6 files. A separate bounded audio decode confirmed that all six contain audio while the primary visual path can exclude it. Representative 12-frame contact sheets visibly show real American-football fields, officials, pre-snap formations, live plays, tackles, stoppages, sidelines, and bands.

All games include Berkeley, so this is **game-held-out, not team-held-out**. The source license does not by itself resolve player publicity, school-mark, venue, endorsement, or model-weight questions. External model-provider upload is outside the admitted local-use policy.

## What was actually trained—and what was only frozen or selected

The word “training” can hide three very different operations. Keep them separate.

| Component | Weight update? | What changed | Selection data | Test role |
|---|---:|---|---|---|
| Soccer MobileNetV2 backbone | No | Nothing; pretrained image descriptor is frozen | None | Produces per-frame descriptors |
| Soccer random projection | No learned update | Fixed 5,000×256 matrix generated from seed `20260827` | None | Compresses the aggregated descriptor deterministically |
| Soccer softmax head | **Yes** | 3,584 class weights + 14 biases = **3,598 learned parameters** | Five candidate hyperparameter trials compared on 356 validation examples | Frozen head scored once on 389 test examples |
| Soccer candidate-window VLM | No | One prompt and response schema were frozen and hash-sealed before inference | No test-label access | 50 silent label-centered test windows; labels joined only afterward |
| Soccer complete-match VLM | No | Validation-only structural prompt selection froze the number-disabled evidence-first contract | Six validation windows; no test-label semantics | 96 silent test calls over 90 dense and six stress windows; labels joined only after the 1,874-file seal |
| Football long-form v2 VLM | No | Three prompt candidates were compared structurally; no model weights were updated | Train windows for development, one validation game for prompt choice | Frozen candidate A ran on 36 sparse test windows |
| Football DVIDS external VLM | No | A pre-frozen visual-only prompt was applied without selection on the external series | None; one correlated external-held-out unit | 57 fixed sparse windows; no human event labels exist |
| Live query LLM | No project training | Turns a coach sentence into a validated search plan | Runtime prompt only | Searches already saved reports; it does not watch the video |

### Why the soccer checkpoint stores more than 3,598 values

The model package reports 14,110 persisted train-fit values:

- 10,000 raw-feature means/scales: 5,000 means + 5,000 scales;
- 512 projected-feature means/scales: 256 means + 256 scales;
- 3,584 learned softmax weights: 256 features × 14 classes;
- 14 learned class biases.

Only the last two lines are optimized class parameters. The normalization statistics are fitted from the training set, and the projection is deterministic rather than learned.

The selected soccer head ran 350 epochs with learning rate 0.03 and L2 regularization 0.001. Selection used validation supported-class macro-F1 and then balanced accuracy. The 0.90 abstention threshold was also selected on validation data, subject to at least 20% coverage. Test labels did not choose any of these values.

### What “frozen prompt selection” means

A VLM prompt is an instruction template, not a trained neural-network checkpoint. Comparing prompt candidates on development/validation inputs is experimental design, but it is not fine-tuning. Once the prompt is selected and hashed, it must remain unchanged for test inference. Otherwise the test set becomes another development set.

## Leakage controls and remaining confounds

### Controls that passed

- Game/source IDs, not random clips, define train/validation/test membership.
- Soccer test games were frozen before fitting; the 50-window VLM subset and its labels were separately hash-sealed before inference.
- The soccer VLM loaded no labels during inference. Labels were joined after raw responses had been stored.
- The complete-match soccer prompt, schema, query set, 90 dense windows, six duration-stress windows, and six direct spot checks were frozen before test inference. SoccerNet annotations were opened only after the 1,874-file visual seal.
- The football protocol excludes audio, commentary, filenames, titles, team names, rosters, and split labels from model input.
- Audio/commentary may be examined only after the silent visual prediction and its hash are sealed. That audit is weak, post-hoc evidence—not ground truth.
- Source receipts bind media identity, duration, and provenance. Hash mismatches fail closed.

### Confounds that remain

- The soccer candidate label chooses where to look, so candidate classification is easier and different from dense spotting.
- The 50-window VLM sample is stratified, not a natural match-frequency sample.
- The soccer baseline and VLM use different denominators (389 versus 50) and representations; their percentages are not a controlled head-to-head comparison.
- The complete-match soccer label evaluator is a restricted, non-one-to-one ±6-second corroboration, not mAP, dense action-spotting accuracy, or a score of the generated prose.
- A sampled complete-match soccer frame retained readable lower-third team-name pixels outside the fixed top mask. Model inputs therefore cannot be claimed fully identity-free even though the model output did not repeat that name.
- Berkeley appears in every football split, so the football design cannot test transfer to an unseen team.
- Broadcast pixels can reveal scoreboard, replay graphics, uniforms, and venue shortcuts.
- Eight sparse frames from a 120-second football window may miss the decisive moment; long context duration does not equal temporal coverage.
- The DVIDS lane samples 3,420 of 11,657.29 seconds from one correlated 19-part series. It is neither dense coverage nor 19 independent games.
- Neither corpus currently supplies human atomic annotations for player identity, trajectory, tactical intent, or the factuality of generated prose.

## Soccer result: the trained baseline is usable only as a bounded diagnostic

The baseline was independently reimplemented from saved features without importing the project trainer. The reproduced weights, bias, raw normalization, and projected normalization matched the saved checkpoint with maximum absolute difference 0.0.

| Metric | Verified result | Interpretation |
|---|---:|---|
| Test examples | 389 from 2 games | Single-label eligible event/background candidates only |
| Exact accuracy | 167/389 = **42.93%** | Better than the train-majority rule, but not high enough for autonomous tagging |
| Train-majority baseline | 93/389 = **23.91%** | Always predicts `ball_out_of_play` |
| Top-3 accuracy | 294/389 = **75.58%** | True class appears among three guesses; not equivalent to a correct single answer |
| Macro-F1, all 14 taxonomy slots | **0.3333** | Includes the unsupported penalty-kick slot |
| Macro-F1, 13 test-supported classes | **0.3589** | Gives equal weight to each supported class |
| Balanced accuracy, supported classes | **0.3725** | Mean recall across supported classes |
| 95% Wilson interval for exact accuracy | **38.10%–47.89%** | Sampling uncertainty for these 389 candidates, not domain-shift uncertainty |
| Selective result at threshold 0.90 | 106/190 = **55.79%** at **48.84% coverage** | Accuracy improves by declining to answer on 199/389 cases |

Penalty kick has zero eligible examples in train, validation, and test, and goal has only two eligible test examples. Do not use aggregate accuracy to imply reliable rare-event performance.

The learned output is only a 14-way event/background probability. Timestamps and report prose are deterministic templates. Player identity, team identity, field location, ball trajectory, long-ball type, formation, and tactical intent are not learned.

## Soccer VLM result: pipeline GO, semantics NO-GO

The local model `google/gemma-4-e4b` processed all 50 frozen silent windows with zero runtime failures. The response format was reliable; the soccer interpretation was not.

| Metric | Verified result |
|---|---:|
| Frozen denominator | 50 windows from 2 held-out games |
| Valid structured responses | 50/50 |
| Exact correct, counting abstentions as wrong | **3/50 = 6.0%** |
| 95% Wilson interval | **2.06%–16.22%** |
| Abstentions | **24/50 = 48.0%** |
| Non-abstained accuracy | **3/26 = 11.54%** |
| Stratified-subset majority rule | **4/50 = 8.0%** |
| Candidate discovery evaluated | No |
| Detailed factuality evaluated | No |
| Detailed reports safe for coach search | **No** |

The output distribution collapsed to six values: 24 `insufficient_visual_evidence`, 13 `background`, 9 `shot`, 2 `card`, 1 `foul`, and 1 `kick_off`. In a preselected false-positive audit, the frames showed midfield/touchline play, a challenge, players down, and a referee gesture. The VLM predicted `shot` with high confidence and stated that the ball passed the goalkeeper into the net—an event not visible in the supplied frames.

This negative result is scientifically useful: JSON validity and fluent detail are not semantic accuracy. It motivates atomic evidence scoring, temporal coverage tests, and more cautious report generation.

<!-- SOCCER_COMPLETE_MATCH_RESULT_BLOCK_START: independently verified final block -->
## SoccerMaster complete-match result — indexing GO, semantics NO-GO

**Status:** the complete visual run, prediction seal, post-seal annotation join, direct spot checks, soccer-only adapter, shared UI surface, browser evidence, and lifecycle gates are frozen and independently verified. Full-match retrieval infrastructure is GO; event semantics, detailed-report factuality, anonymization, and coach readiness are NO-GO.

### Exact completed protocol

- Source unit: both complete 2,700-second halves of one newly acquired authorized SoccerNet test game. Raw footage remains private and non-redistributable.
- Dense test: 90 contiguous 60-second windows at 60-second stride, 45 per half, covering all 5,400 seconds with eight ordered silent frames per window.
- Stress test: six fixed windows, one each at 30/60/120 seconds per half, using 8/12/16 ordered silent frames.
- Development: 12 terminal v2 validation windows required 20 actual requests; the final number-disabled v3 delivery check completed 6/6 on the first request. All development used validation footage only.
- Frozen test: 96/96 reports were schema-valid on the first request, with zero retries, failures, or abstentions. This is a delivery result, not soccer correctness.
- Request construction excluded audio, commentary, labels, filenames, paths, source metadata, textual team/score/game identity, and absolute match clock. It did **not** remove every identity-bearing pixel: the later anonymization audit found a readable lower third. The VLM alone authored event semantics; ordinary code sampled/hashed frames, validated schema, sealed outputs, joined labels after sealing, and ranked text.
- Weight update: none. This is prompt selection plus inference, not fine-tuning or a reproduction of the official SoccerMaster model.

### Frozen and post-seal result

| Measure | Verified result | Meaning |
|---|---:|---|
| Valid test reports | 96/96 | structural delivery worked on every frozen test call |
| Dense coverage | 90 × 60 s = 5,400 s | both complete halves are searchable at 60-second granularity |
| Stress coverage | 6 windows at 30/60/120 s | fixed duration stress, not extra independent games |
| VLM-emitted events | 361 | unverified model outputs, not match-event prevalence |
| Restricted mapped-annotation corroboration | 3/166 = 1.81% | non-one-to-one ±6-second type/time match; not mAP or event accuracy |
| Restricted mapped-prediction corroboration | 3/54 = 5.56% | same restricted evaluator; actor, outcome, tactics, and prose unscored |
| Mapped offside / foul predictions | 0 / 0 | compared descriptively with 3 offside and 19 foul annotations |
| Direct visual spot checks | 0 supported, 2 partial, 4 unsupported | six predeclared windows; semantic coach-readiness failure |
| Input anonymization audit | failed sampled frame | readable lower-third team-name pixels remained outside the top mask |

The restricted label join is an evaluator, never an event detector: it ran only after the 1,874-file visual seal closed, and it could not change a prediction. Its many-to-many ±6-second matches must not be reported as benchmark action-spotting accuracy. The direct visual spot checks are the stronger warning for detailed reports: none of the six sampled reports was fully supported.

### Reproducibility and demo evidence

- Prediction-seal root: `5a8ffad71312528c01faad4f0f261de1421f1e13910fb79e0da846d594ba10e4` over 1,874 files.
- Technical report SHA-256: `7e573a6c73f27ce6618f029f437658aadf3a5c5a745651b35bf18c23a15f64b8`.
- Immutable-core independent QA SHA-256: `b06ae62fc7ac02506f983f54e8006a800d20f212e554ae42706fb62c7ed296cf`.
- Frozen 21-file demo-surface receipt SHA-256: `c5b6338b24bbcd2d11b450f25e33766eb891e4f148755db8ca284888ee104fe4`.
- Mutable-surface independent QA SHA-256: `61b4e210ba2608b8089cd4151d88a4bf182c24c3ea43ab390166fe2c83ff5470`.
- Supplemental six-screenshot receipt SHA-256: `a8e745b916fbdcc1c339b16caf81f49677b2e1ebdd1cbf89da2e8fb5c80f75c3`; it includes the live local-query-LLM start state and binds the runtime handoff receipt.
- Independent mutable QA reproduced 21/21 surface hashes, the core seal/root, focused tests, full tests, launch/API/media-range behavior, desktop/mobile layouts, sport switching, the honest offside-zero state, accessibility semantics, and zero browser-console warnings/errors.
- Exactly one live query-model smoke translated a through-ball query and returned 12 ranked candidates in 6.128 client-observed seconds. It verifies query planning, retrieval, and routing only—not any saved VLM claim.

The defensible demo is: “I can search a hash-sealed complete-match report index, open the actual authorized silent evidence, and expose the model’s failure.” It is not: “The system reliably finds soccer events for coaches.”
<!-- SOCCER_COMPLETE_MATCH_RESULT_BLOCK_END -->

<!-- FOOTBALL_LONGFORM_RESULT_BLOCK_START: independently verified final block -->
## FootballMaster long-form result — systems GO, semantic NO-GO

**Status:** the primary predictions, report, adapter, UI, and lifecycle package are frozen and independently verified. Packaging/reproducibility and research-demo mechanics are GO; event semantics, dense whole-game search, accuracy, and coach readiness are NO-GO.

### Exact completed protocol

- Corpus source pool: six long single-game programs, 20,265.7455 seconds = 5.62937375 hours, split 3 train / 1 validation / 2 test by game ID.
- Windows: 27 train, 6 validation, 36 test = 69; test contains 12 each at 30, 60, and 120 seconds.
- Coverage: 4,830 nominal overlapping window-seconds but only 2,760 unique seconds. The searchable test index has 2,520 nominal and 1,440 unique seconds from 6,438.9325 seconds of held-out source programs.
- Visual input: eight ordered silent frames per window plus protocol text; audio, commentary, filenames, titles, team names, rosters, split labels, and event labels excluded.
- Development: 108 terminal calls across A, B, original C, and C3200; 36 frozen test calls; 144 terminal calls and 169 bounded HTTP attempts total.
- Selected prompt: `candidate_a_direct`, SHA-256 `daaf5ad849c3d4201267dd4bfa5227e0cfc5fae93d6a348cf98789705d63604d`.
- Weight update: none. This is prompt selection and inference, not VLM fine-tuning.
- Ground-truth event annotations: none. Event accuracy cannot be computed.

### Frozen held-out result

| Measure | Result | Meaning |
|---|---:|---|
| Valid normalized JSON | 35/36 | delivery mostly worked; one terminal failure remains |
| `abstain=true` | 36/36 | the selected prompt abstained everywhere |
| Abstain plus asserted events | 27/36 | direct logical contradiction |
| Unsupported `scoring` | 126 events / 21 windows | generic action received a high-stakes scoring type without explicit score evidence |
| Output histogram | 137 scoring, 60 pre-snap, 4 run-play, 1 stoppage | model outputs, not event prevalence |
| Human event truth | 0 windows | accuracy and calibration are unmeasured |

A direct independent audit opened all eight frames for `fmw-2998f9d573461887`. They show a run, stopped group, officials, reset, and pre-snap formation near a 10-yard marker; none shows an explicit score or scoring signal. The report nevertheless labels every frame-level event `scoring` while also abstaining.

### Reproducibility and UI evidence

- Prediction-seal root: `7a8260cc109e6cf60433c186d5000030fdf38aa905382460aae1dbd0960ec8f1` over 1,797 files; audio/commentary excluded.
- Corrected technical report SHA-256: `14b2e1070ace410b7bdd12a44f9ca04c1047bc563242985b2a5ff9d157810b1b`.
- Corrected demo receipt SHA-256: `028cf4c957bbff302aee9c5401a675f3b923a63318078d57cf1d2408124e017d`.
- Independent QA SHA-256: `d29edee3ef8b6b407f424d4bdbfdcfbae814fda1804efba3f612badc5d97e27d`.
- Focused frozen-package tests: 33/33. The full repository suite passed at final verification; use the immutable QA receipt for its historical denominator rather than quoting a moving project-wide count.
- Fresh browser audit: three searches, 12 results each through the labeled literal fallback, exact local playback, HTTP 206 media range, no mobile overflow, and zero console warnings/errors.
- Four post-seal audio clips reproduced byte-for-byte; ASR remains weak, unverified, post hoc, and never truth.

The defensible result is that a leakage-aware pipeline ran and made its semantic failure inspectable. It is not a play detector, accuracy result, entire-game index, or coach-ready tool.
<!-- FOOTBALL_LONGFORM_RESULT_BLOCK_END -->

### Non-primary C3200 diagnostic — still semantic NO-GO

After both primary predictions and the six-window diagnostic plan were frozen, candidate C3200 was run on the same six predeclared FootballMaster v2 windows. It produced 6/6 valid terminal reports in eight HTTP attempts. All nine of its `scoring` labels explicitly negated their own scoring claim—for example, assigning the scoring type while saying there was no scoring evidence. Independent review rehashed all 76 diagnostic-seal files, reproduced the exact primary-A/C comparison, and inspected all 25 cited frames. Verdict: reproducibility GO; semantics and coach-search readiness NO-GO.

This is a small, nonrandom, overlapping, post-hoc diagnostic with no event gold or retrieval judgments. It cannot support accuracy, prompt selection, model improvement, held-out performance, or replacement of the 36-window primary result. Two malformed first-attempt response envelopes were not retained, although their sealed requests, error fingerprints, and attempt counts were preserved. Final diagnostic receipt root: `1a4cb8281cab6d98c247adad0172a83edd73e5a0e065db0471ebdd3ce86fcab7`; independent QA SHA-256: `295b6767d8de170d459d8b2ae059b1c32494f5bec7118f423b445f30813d4e53`.

<!-- DVIDS_EXTERNAL_RESULT_BLOCK_START: independently verified final block -->
## FootballMaster DVIDS external result — reproducible sparse probe, semantic NO-GO

**Status:** the external package, 57 visual requests, prediction seal, post-seal result/index/query packet, source bindings, and final report are frozen and independently verified. Systems/reproducibility is GO; semantics, retrieval relevance, whole-game search, and coach readiness are NO-GO.

- Source boundary: one correlated, externally held-out, source-numbered 19-part series totaling 11,657.29 seconds. It must not be counted as 19 independent games and is not proven uncut, every-play, or broadcast-complete.
- Sampling: 57 fixed 60-second windows, exactly three per part, for 3,420 nominal and unique sampled seconds. Eight ordered silent frames per window; this is sparse sampling, not dense coverage.
- Delivery: 57/57 terminal reports were schema-valid on the first HTTP attempt, with 456/456 frame hashes reproduced.
- Semantics: 56/57 reports abstained; 43 abstaining reports still emitted events; 269 events appeared inside abstaining windows; all reports emitted 277 unverified events, including 82 `scoring` labels across 21 windows.
- Evaluation boundary: there are no human event labels and no retrieval-relevance judgments. Event accuracy, calibration, recall, precision, and search quality are unmeasured.
- Direct failure evidence: an on-field ceremony/canopy sequence was labeled as a pre-snap formation; a non-football wheeled-cycle sequence still emitted pre-snap events; an ordinary formation/stoppage window ranked first for a touchdown/celebration query.
- Search packet: 57 sealed entries and 30 deterministic query packets reproduce mechanically, but every query's five candidates are unjudged.

Independent QA reproduced the 806-file prediction seal, 57 receipts/attempts, 456 frames, search/index hashes, source-media bindings, and metric counts. Final package receipt SHA-256: `8df48037d0e64c70c44ba87111a2047fad6d04f4965c6a9dcff2239432cf88ab`; prediction-seal root: `a96876090f3f822243a430f976655832371c3a16cb0fd0f2c318ef777c592fd9`; independent final QA SHA-256: `d02368538d28dcb075c904b257b05a1f94186f9fbc34b191448dafa07d36f059`.

Safe sentence: “The external runner reproducibly made 57 visual-only calls over a fixed sparse sample and built a deterministic search packet.” Unsafe sentence: “The model searched or understood the whole game.”
<!-- DVIDS_EXTERNAL_RESULT_BLOCK_END -->

## How the backend and demo work

### Offline analysis path

1. **Admit and verify media.** The acquisition layer checks source metadata, rights state, file hashes, duration, and full decodability.
2. **Assign a source-held-out split.** Every window derived from one game stays in that game's split.
3. **Sample silent visual evidence.** Audio is not decoded into the visual-model request.
4. **Run the sport-specific analyst.** The candidate soccer baseline returns class probabilities; each VLM lane returns schema-constrained event/report fields. Raw response, model, prompt, and input hashes are stored.
5. **Seal before scoring.** Predictions exist before held-out labels or commentary are joined.
6. **Validate and index.** Deterministic code checks the schema and stores searchable text, fields, timestamps, evidence references, provenance, and uncertainty.

### Live query path

1. The UI sends `{sport, query}` to `POST /api/search`.
2. A separate loopback-only query LLM sees the coach's sentence and the retrieval ontology. It does **not** see or re-analyze the video.
3. Its strict plan is validated: requested event filters, search phrases, player/participant terms, field/context constraints, confidence requirements, and abstention behavior.
4. Deterministic ranking searches the saved reports and metadata.
5. The UI displays ranked evidence cards, timestamps, match reasons, model boundary, source attribution, and playable local media.

This separation matters: the video model decides what its saved report says; the query LLM decides how to search those saved words; ordinary code makes the process repeatable and inspectable.

### Transparent fallbacks

- **Query LLM offline:** the server uses a deterministic literal-term plan and labels the source `deterministic_literal_fallback`. The demo remains searchable, but synonyms and structured interpretation may be weaker.
- **Video model offline:** use already sealed reports. A live demo is not a valid reason to generate new test predictions or change prompts.
- **Media playback issue:** open the verified contact sheet and receipt, then show the report timestamp/evidence IDs. Do not substitute an unrelated clip.
- **SoccerMaster long-form unavailable:** the server fails closed on the new package and exposes the historical SQLite demonstration only as `legacy_sqlite_fallback`. Do not call it the complete-match result.
- **FootballMaster v2 unavailable:** the server tries the verified v2 package first. If it cannot verify or load it, any older pilot is shown only as an explicit legacy fallback. Do not hide or relabel that fallback.
- **Any semantic mismatch:** show it. The safe claim is that the infrastructure retrieved the saved report; the unsafe claim is that the saved report is true.

## A six-minute live-demo script

### 0:00–0:45 — State the boundary

Say:

> “This is a research prototype for evidence-linked video search. I can show that the media, splits, model calls, report store, and retrieval path are real. I cannot yet show that a VLM reliably understands a whole match.”

### 0:45–1:45 — Show the data receipts

Open the SoccerMaster complete-match source/protocol receipts and the FootballMaster v2 or DVIDS source manifest. Point to source-held-out units, decoded duration, rights state, and audio exclusion. Emphasize that real footage replaced synthetic fixtures and that SoccerNet raw media remains private.

### 1:45–3:00 — Show the search mechanics

For the current handoff, open the already-running live-query server at `http://127.0.0.1:8774/?sport=soccer`; a fresh launcher normally uses `http://127.0.0.1:8771/`. Submit one soccer query, switch to American football, and submit one football query. Point to:

- the selected sport;
- whether the plan came from the local query LLM or literal fallback;
- the strict search plan;
- matched terms/fields and timestamps;
- playable evidence and attribution.
- the soccer banner showing 96 sealed windows, 90 dense minutes, both halves, and semantic NO-GO;
- the soccer evaluator/spot-check warning: 3/166, 3/54, and 0/6 fully supported;
- the football banner separating 1,440 unique indexed seconds from the 5.629-hour source pool;
- the 27/36 contradiction and 126-event unsupported-scoring failure counters.

Say: “This call searches saved model reports; it does not send the clip back through the video model.”

### 3:00–4:15 — Lead with the negative result

Open the complete-match soccer evaluation. Say:

> “The VLM returned valid structured reports on all 96 frozen calls, and 90 dense minutes cover both full halves. But the post-seal restricted evaluator corroborated only 3 of 166 mapped annotations and 3 of 54 mapped predictions, while direct review found zero of six reports fully supported. Complete indexing is a software result, not proof of soccer understanding.”

Explain that the ±6-second label join is non-one-to-one corroboration, not mAP or full event accuracy, and that generated actor/outcome/tactical prose remains unscored. If the older 50-window result comes up, do not compare its 3/50 directly to the baseline's 167/389 as though only the model changed; samples and representations differ.

### 4:15–5:15 — Explain what really trained

Show the soccer model config. Say:

> “The learned scale result is a small 3,598-parameter softmax head on frozen image descriptors. The VLM runs are prompt-only; no VLM weights were updated. Prompt selection is not fine-tuning.”

### 5:15–6:00 — Show football honestly and make the ask

Switch to the FootballMaster v2 view and search for a pre-snap or sideline phrase. Say:

> “The football pipeline and five-hour source pool are isolated and verified, but only 0.77 unique hours were sampled. The frozen v2 VLM result abstained on every test window, contradicted itself on 27 of 36, and made 126 unsupported scoring assignments. The external DVIDS probe also stayed sparse: 57 valid reports over 3,420 seconds, 56 abstentions, 277 unverified events, and 82 scoring labels with no event gold. The UI is useful for inspecting these failures, not for trusting their play labels.”

Ask Archit to help choose the next falsifiable experiment: dense candidate generation, atomic report factuality, or coach retrieval utility.

## Safe and unsafe claims

| Safe now | Unsafe now |
|---|---|
| “The project uses authentic, rights-audited local footage.” | “Any public broadcast is legal training data.” |
| “The soccer corpus is 8 game IDs / 16 halves / 12.4222 hours.” | “We validated every play of eight complete broadcasts.” |
| “The football corpus is 6 long programs / 5.6294 hours.” | “The football corpus contains a proven uncut full game.” |
| “Splits are game-held-out.” | “Football is team-held-out.” |
| “The soccer baseline trained 3,598 parameters and scored 167/389 on supplied candidates.” | “The baseline finds 42.93% of events in a whole match.” |
| “SoccerMaster is research context for this experiment.” | “We reproduced or trained the official SoccerMaster model.” |
| “The complete-match soccer VLM produced 96/96 structured reports; 90 dense windows cover both full halves.” | “Schema validity or complete temporal coverage proves the reports are correct.” |
| “The restricted post-seal soccer evaluator corroborated 3/166 mapped annotations and 3/54 mapped predictions; direct review fully supported 0/6 reports.” | “Those counts are mAP, full event accuracy, or a score of player/action/tactics prose.” |
| “The sampled soccer anonymization audit failed because a readable lower third remained.” | “The fixed top mask removed every identity cue.” |
| “The earlier label-centered soccer VLM completed 50/50 responses but was correct on 3/50.” | “The earlier and complete-match soccer denominators are interchangeable.” |
| “The football VLM used silent 30/60/120-second windows and failed its semantic consistency gates.” | “Football long-form accuracy is X%.” No human event truth exists. |
| “The 5.629-hour corpus was sampled over 2,760 unique seconds; the test UI indexes 1,440 unique seconds.” | “The entire 5.629 hours or every play is searchable.” |
| “The DVIDS runner completed 57/57 fixed sparse calls over 3,420 unique seconds.” | “The 19-part DVIDS series is 19 independent games or a dense whole-game index.” |
| “The DVIDS model emitted 277 unverified events and 82 scoring labels while abstaining on 56/57 reports.” | “Those output counts measure event prevalence or accuracy.” |
| “Audio is separated and excluded from primary inference.” | “Commentary verifies the visual answer.” |
| “The query LLM translates language into a search plan.” | “The query LLM watches or validates the clip.” |
| “The standalone FootballMaster package is soccer-free.” | “The current shared GUI has no soccer dependency.” |
| “The UI prefers verified FootballMaster v2 and visibly labels any legacy fallback.” | “A retrieved football report is a verified real event.” |
| “Detailed factuality remains unevaluated.” | “Player, formation, trajectory, intent, or outcome fields are correct because they are fluent.” |

## Next research: falsifiable hypotheses for Archit and UMD coaches

These are proposed studies, not claims about UMD's current workflow.

| Hypothesis | Minimal experiment | Success/failure measure |
|---|---|---|
| Coarse-to-fine temporal sampling improves whole-match event recall under a fixed frame budget | Compare fixed 30/60/120-second sampling against coarse scan plus dense refinement on untouched games | Event proposal recall, timestamp error, compute per match; fail if gains disappear on new games |
| Evidence-first prompting reduces unsupported football detail | Select between the direct and evidence-first prompt on validation, freeze it, then audit atomic claims on test | Unsupported claims per report and abstention; no test-driven prompt editing |
| Atomic field scoring is more informative than one event label | Human annotators mark actor, action, location, outcome, time span, and visible evidence separately | Per-field precision/recall and entailment; report missing/unknown fields instead of a single average |
| Search helps coaches only if it saves review time without hiding relevant clips | Coaches write and freeze queries, then compare prototype versus their current manual cutup process | Top-5 relevance, held-out event recall, median task time, correction burden |
| Explicit unknown-player behavior improves trust | Compare forced identity against roster-assisted identity with an `unknown_player` option | Identity precision, abstention, and high-confidence hallucination count |
| Football-specific schemas matter more than reusing soccer logic | Compare FootballMaster fields with a deliberately generic sports schema on the same plays | Coach-rated field usefulness and factuality; hold the visual model/input fixed |
| Post-hoc commentary agreement is a weak diagnostic, not truth | Seal visual outputs, then compare them with independently processed ASR | Agreement versus human labels; reject any design that treats commentary as the label oracle |
| Coach-controlled camera views support more tactical queries than broadcast video | Evaluate the same schema on approved wide/end-zone views versus broadcast views | Formation/coverage/player-field factuality by view; abstain when evidence leaves frame |

### Initial coach questions worth testing

For soccer:

- “Show long balls followed by a second-ball contest.”
- “Find offside or foul sequences where the restart changes possession.”
- “Show a specific player's forward receptions under pressure, but return unknown identity when the jersey is unreadable.”

For American football:

- “Show third-and-medium plays with visible pre-snap motion.”
- “Find pass plays where pressure is visible before the throw.”
- “Group punts, kickoffs, and field-goal attempts, separating live play from replay or stoppage.”

The first UMD ask should be a workflow interview and a small approved shadow evaluation—not access to an entire archive and not a promise of automated grading. Coaches should define the vocabulary, five to twelve high-value queries, the error cost, and the current manual baseline.

## Plain-language glossary

| Term | Plain-English meaning |
|---|---|
| **VLM** | Vision-language model: a language model that can inspect images/video frames and write text or structured fields about them. |
| **LLM** | Large language model: here, the separate query interpreter that turns a coach's sentence into a search plan. |
| **ASR** | Automatic speech recognition: software that converts commentary audio to text. It is kept out of visual inference and used only in a later weak comparison. |
| **Baseline** | A deliberately simpler reference system. The soccer baseline is frozen image features plus a trained softmax classifier. |
| **Backbone** | The feature-producing neural network. MobileNetV2 is frozen here, so its weights never change. |
| **Feature/descriptor** | A numeric summary of visual content. It is useful to a classifier but is not itself an event label. |
| **Softmax head** | The small trained layer that turns features into probabilities across the 14 soccer classes. |
| **Parameter** | A numeric model value adjusted by optimization. The soccer head learned 3,598; the VLM runs learned none. |
| **Hyperparameter** | A setting chosen around training—such as learning rate, regularization, or threshold—rather than learned as a weight. |
| **Frozen** | Locked before the next stage. Frozen weights, prompts, queries, or test sets cannot be changed after seeing test results. |
| **Fine-tuning** | Updating pretrained model weights on project data. No completed VLM experiment here performs fine-tuning. |
| **Prompt selection** | Choosing an instruction template using development/validation behavior. It is not weight training. |
| **Train / validation / test** | Train fits parameters; validation chooses settings; test is opened once for the final estimate. |
| **Game-held-out** | No windows from a test game appear in training or validation. It does not guarantee the teams are new. |
| **Leakage** | Test-only information accidentally influencing training, prompt design, model selection, or inputs. |
| **Seal** | A saved cryptographic commitment—usually a SHA-256 hash—showing that an input or prediction existed unchanged before labels were joined. |
| **Hash** | A content fingerprint. If one byte changes, the SHA-256 value should change. |
| **Post-hoc** | Done after the primary prediction is fixed. The ASR comparison is post-hoc. |
| **Same-clip comparison** | Two systems see the same source clip. This controls footage, but it is not a clean model comparison if sampling, prompt, or preprocessing also differ. |
| **Candidate window** | A short interval supplied to a classifier because an annotation or sampler already chose where to look. |
| **Dense action spotting** | Searching an untrimmed match to discover every event and timestamp. The complete-match lane densely scans time, but its semantic evaluation failed, so it has not demonstrated valid action spotting. |
| **Abstention** | The system explicitly says evidence is insufficient instead of forcing a guess. |
| **Macro-F1** | Compute F1 separately for every class and average them equally, so frequent classes do not dominate. |
| **Balanced accuracy** | Average recall across supported classes, again reducing domination by frequent classes. |
| **Top-3 accuracy** | The true label appears among the model's three highest-scored classes. It is not three independent correct answers. |
| **Wilson interval** | A statistically stable uncertainty interval for a binomial proportion such as correct/total. It does not cover dataset or domain shift. |
| **Schema** | The required JSON field contract for a model response. Valid schema means the shape is correct, not that the content is true. |
| **Ground truth** | Human- or dataset-provided reference labels used for evaluation. Commentary is not ground truth. |
| **Retrieval** | Searching and ranking saved reports for a query. Good retrieval cannot repair an incorrect saved report. |
| **Adapter** | Thin integration code that connects independent sport packages to the shared UI. |

## Verified artifact map

### Independent QA

- `.agent/dual-scale-independent-qa-stage1.md` — independent corpus/isolation/Soccer audit; SHA-256 `8e08fbe7cb4ffffe38a4a311044e3493db96e5229a99a9587877b4bed169983d`
- `.agent/soccermaster-longform-immutable-core-qa.md` — complete-match visual seal/protocol/evaluator reproduction; SHA-256 `b06ae62fc7ac02506f983f54e8006a800d20f212e554ae42706fb62c7ed296cf`
- `.agent/soccermaster-longform-mutable-surface-qa.md` — adapter/UI/browser/claim-boundary verification; SHA-256 `61b4e210ba2608b8089cd4151d88a4bf182c24c3ea43ab390166fe2c83ff5470`
- `.agent/dvids-external-v1-independent-final-qa.md` — frozen DVIDS package and semantic-failure reproduction; SHA-256 `d02368538d28dcb075c904b257b05a1f94186f9fbc34b191448dafa07d36f059`
- `.agent/footballmaster-c3200-independent-final-qa.md` — six-window post-hoc diagnostic reproduction and visual audit; SHA-256 `295b6767d8de170d459d8b2ae059b1c32494f5bec7118f423b445f30813d4e53`

### Soccer

- `artifacts/soccermaster-scale-v1/corpus-receipt.json` — corpus, split, rights, and leakage receipt; SHA-256 `27240a28254bb02a94574b1c09ea4c5d788bb96147df21257c448aa56fd1ebdf`
- `artifacts/soccermaster-scale-v1/pilot-v1/model-config.json` — architecture, learned-parameter count, and selected settings
- `artifacts/soccermaster-scale-v1/pilot-v1/metrics.json` — baseline test metrics and claim boundary
- `artifacts/soccermaster-scale-v1/pilot-v1/package-receipt.json` — verified baseline package; SHA-256 `6924980785ecdd54e905df4757b8c6efd577942d65f527617f3f8a72f89abdb6`
- `artifacts/soccermaster-scale-v1/vlm-subset-receipt.json` — frozen 50-window VLM subset; SHA-256 `2b06a3748374ec600aa371b6ab2e743b0ce585e1eb4b76ee2c328064c7d21c17`
- `artifacts/soccermaster-scale-v1/vlm-eval-v1/evaluation.json` — scored 50-window semantic result
- `artifacts/soccermaster-scale-v1/vlm-eval-v1/package-receipt.json` — VLM package; SHA-256 `3494dd229c3e3a37df98cac49dd80e663deabe312278f98832c5eb018a5df86b`
- `research/soccermaster-scale-technical-report-2026-08-27.md` — full technical interpretation
- `prototype/soccermaster_scale/` — standalone soccer-scale implementation
- `artifacts/soccermaster-longform-v1/prediction-seal.json` — complete-match 1,874-file visual prediction seal; root `5a8ffad71312528c01faad4f0f261de1421f1e13910fb79e0da846d594ba10e4`
- `artifacts/soccermaster-longform-v1/annotation-evaluation.json` — post-seal restricted annotation corroboration, explicitly not an event detector
- `artifacts/soccermaster-longform-v1/spot-check-adjudication.json` — six direct visual judgments; 0 supported, 2 partial, 4 unsupported
- `artifacts/soccermaster-longform-v1/demo-surface-receipt.json` — frozen 21-file demo surface; SHA-256 `c5b6338b24bbcd2d11b450f25e33766eb891e4f148755db8ca284888ee104fe4`
- `artifacts/soccermaster-longform-v1/browser-evidence/screenshot-receipt.json` — six presentation screenshots including the live-LLM state; SHA-256 `a8e745b916fbdcc1c339b16caf81f49677b2e1ebdd1cbf89da2e8fb5c80f75c3`
- `research/soccermaster-longform-technical-report-2026-08-27.md` — complete-match technical report; SHA-256 `7e573a6c73f27ce6618f029f437658aadf3a5c5a745651b35bf18c23a15f64b8`
- `prototype/soccermaster_longform/` and `prototype/soccer_longform_adapter.py` — soccer-only full-match runner and sealed-package search adapter

Public background: [SoccerNet data portal](https://www.soccer-net.org/data), [SoccerNet-v2 paper](https://arxiv.org/abs/2011.13367), [SoccerMaster project](https://haolinyang-hlyang.github.io/SoccerMaster/), and [ONNX Model Zoo MobileNetV2](https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet).

### American football

- `data/public/footballmaster-v2/source-manifest.json` — admitted sources, rights, hashes, durations, and split; SHA-256 `da0e58d2ef1a0780a54dfa82d03c0a936f08c8dc61d24cb3a505fdc776713b68`
- `data/public/footballmaster-v2/verification-receipt.json` — offline corpus verifier receipt; SHA-256 `b9e0aa080b40b10003ff6d4abdf6e0f2bd872cb98931f56aadba8e83de3a66d2`
- `data/public/footballmaster-v2/visual-inspection-receipt.json` and `data/public/footballmaster-v2/contact-sheets/` — authentic-football frame evidence
- `footballmaster/` — isolated FootballMaster package
- `artifacts/footballmaster/longform-v2/prediction-seal.json` — 1,797-file primary prediction seal; root `7a8260cc109e6cf60433c186d5000030fdf38aa905382460aae1dbd0960ec8f1`
- `artifacts/footballmaster/longform-v2/verification-receipt.json` — passing core verification; SHA-256 `c35a5d3b9430c82e28df494fde76f3d94d2fa47a2bab12a1977f6e6855769736`
- `artifacts/footballmaster/longform-v2/protocol.json` — frozen completed protocol
- `artifacts/footballmaster/longform-v2/window-manifest.jsonl` — frozen 69-window design
- `artifacts/footballmaster/longform-v2/prompt-candidates.json` — three prompt candidates, explicitly not parameter training
- `artifacts/footballmaster/longform-v2/frozen-query-set.json` — 30 test queries frozen before test
- `artifacts/footballmaster/longform-v2/report-metrics.json` — exact completed call and semantic-failure denominators
- `research/footballmaster-longform-v2-technical-report-2026-08-28.md` — final technical report; SHA-256 `14b2e1070ace410b7bdd12a44f9ca04c1047bc563242985b2a5ff9d157810b1b`
- `.agent/footballmaster-v2-independent-final-qa.md` — independent final QA; SHA-256 `d29edee3ef8b6b407f424d4bdbfdcfbae814fda1804efba3f612badc5d97e27d`
- `artifacts/footballmaster/longform-v2-posthoc-c-diagnostic/FINAL_DIAGNOSTIC_RECEIPT.json` — non-primary C3200 diagnostic, SHA-256 `e8a60b9fa08718dec70e2433a0e7877308c1a02cb8d3861fba89cd655c702fd6`, final root `1a4cb8281cab6d98c247adad0172a83edd73e5a0e065db0471ebdd3ce86fcab7`
- `artifacts/footballmaster/dvids-external-v1/FINAL_PACKAGE_RECEIPT.json` — final external package; SHA-256 `8df48037d0e64c70c44ba87111a2047fad6d04f4965c6a9dcff2239432cf88ab`
- `artifacts/footballmaster/dvids-external-v1/prediction-seal.json` — 806-file sparse external prediction seal; root `a96876090f3f822243a430f976655832371c3a16cb0fd0f2c318ef777c592fd9`
- `artifacts/footballmaster/dvids-external-v1/HONEST_REPORT.md` — DVIDS systems/semantic result and claim boundaries

Public source pages: [Bishop O'Dowd–Berkeley](https://archive.org/details/betv-16559varsityfootball-bishopodowd-vs-berkeley), [Castro Valley–Berkeley](https://archive.org/details/betv-16556varsityfootball-castrovalley-vs-berkeley-11-8-13), [Berkeley–Pittsburg JV](https://archive.org/details/betv-16364bhs-jv-football---berkeley-vs-pittsburg), [Logan–Berkeley JV](https://archive.org/details/betv-16419bhs-jv-football---logan-vs-berkeley), [Encinal–Berkeley JV](https://archive.org/details/betv-16554jvfootball-enciminal-vs-berkeley-1028), [San Leandro–Berkeley](https://archive.org/details/betv-16546san-leandro-vs-berkeley-football), and [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).

### Demo adapter

- `prototype/multisport_search_demo_server.py` — shared loopback server, strict query planner, deterministic fallback/ranker, media routes; **outside the FootballMaster isolation boundary and wired to prefer verified v2**
- `prototype/soccer_longform_adapter.py` — soccer-only seal verifier, optional local query expansion, BM25 search, and private evidence binding; zero football imports/tokens
- `prototype/football_longform_adapter.py` — football-owned v2 validator, loader, query interpreter, search, coverage calculator, and media binder
- `prototype/search_demo_ui/` — shared browser UI
- `.agent/soccermaster-live-demo-runtime-handoff.json` — live local-query presentation server URL/PID/model/mode/health receipt
- `tests/test_footballmaster_isolation.py` — isolation and independent-package regression tests
- `tests/test_multisport_search_demo_server.py` — shared-adapter behavior tests

## Final presenter checklist

- Lead with the semantic NO-GO, not a polished UI screenshot.
- Say “candidate classification” every time the 42.93% baseline appears.
- Lead the current soccer result with “96/96 structured, 90 dense minutes, but 3/166, 3/54, and 0/6 fully supported.”
- If discussing the historical label-centered lane, say “3 of 50,” not merely “6%.”
- Keep the candidate baseline, 50-window VLM, and complete-match VLM denominators visibly separate.
- Say “prompt selection,” not “VLM training,” for both VLM protocols.
- Keep audio/commentary outside the visual path and never call it truth.
- Call the football footage “long single-game programs,” not verified full games.
- State that the GUI prefers verified FootballMaster v2, but that it searches only 36 sparsely sampled, semantically unreliable reports.
- Call DVIDS one correlated 19-part series, not 19 games; say 3,420 sparse sampled seconds, not whole-game coverage.
- If the live model fails, use the labeled literal fallback or sealed artifacts; do not improvise a new test.
- End with one falsifiable next experiment and a request for coach-defined queries/annotations.
