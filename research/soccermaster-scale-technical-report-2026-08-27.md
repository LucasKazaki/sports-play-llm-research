# SoccerMaster scale experiment: 12.42-hour SoccerNet pilot

**Status:** completed feasibility experiment; semantic deployment **NO-GO**  
**Date:** 2026-08-27  
**Implementation:** `prototype/soccermaster_scale/`  
**Primary receipts:** `artifacts/soccermaster-scale-v1/`

## Answer first

The soccer workstream now runs on **eight complete, authentic SoccerNet matches (16 halves, 12.4222 decoded hours)** rather than a handful of short or artificial clips. Train, validation, and test are disjoint by whole game: four train games, two validation games, and two frozen test games.

Two separate experiments were completed:

1. A **non-VLM visual baseline** trained on 810 unambiguous candidate windows and evaluated on 389 windows from two held-out games. It reached 42.93% exact accuracy versus a 23.91% train-majority baseline. This verifies the scaled data/training/evaluation path but is not the project's intended VLM contribution.
2. A **local Gemma-4-E4B VLM probe** on a separately frozen, label-sealed, class-stratified subset of 50 silent held-out windows. It returned schema-valid output for all 50, but abstained on 24 and classified only 3/50 correctly: **6.0% exact accuracy**, below the subset's 8.0% majority baseline. This is a semantic no-go result.

The experiments do **not** establish dense whole-match spotting, player identification, long-ball recognition, formation analysis, tactical inference, report factuality, or coaching utility. Public artifacts set `performance_claim_allowed` to false.

## Corpus and rights

The user provided evidence of completed SoccerNet NDA authorization. The existing downloader OCR'd the access credential in memory and cleared it after each request. The credential was never printed, written to a receipt, placed in a command line, or included in this report.

| Property | Verified value |
|---|---:|
| Complete games | 8 |
| Video halves | 16 |
| Decoded duration | 44,720 s / 12.4222 h |
| Video bytes | 3,019,689,368 |
| Split by whole game | 4 train / 2 valid / 2 test |
| Total event/background candidates | 1,749 |
| Single-label-eligible candidates | 1,555 |
| Raw media redistribution | Not allowed |
| Permitted use | Local non-commercial research |

Raw video, features, contact sheets, raw VLM responses, and sealed labels remain under `data/private/soccermaster-scale-v1`. The public-safe corpus receipt contains hashes and aggregates but no credential or raw-media path.

The manifest independently verified every downloaded half against its acquisition receipt, decoded a first frame, checked duration and dimensions, and rejected duplicate media bytes, example IDs, or game IDs across splits. Corpus receipt SHA-256:

`27240a28254bb02a94574b1c09ea4c5d788bb96147df21257c448aa56fd1ebdf`

## Task definition

This pilot evaluates **event-centered candidate classification**, not dense action spotting.

- Positive windows are 12 seconds centered on visible SoccerNet-v2 event annotations.
- Background windows are deterministic candidates at least 12 seconds from every visible event.
- A positive window is modeling-eligible only when no *different* mapped event class occurs within four seconds of its center.
- Labels choose candidate centers and are then withheld from visual model inputs.
- Test labels remain frozen. For the VLM experiment they are physically separated from the label-free inference manifest and opened only by the scorer after all raw responses are persisted.

This boundary matters: a model that classifies a known candidate has not yet learned to find the event within a full match.

## Soccer-only taxonomy

The package owns a 14-class taxonomy and imports neither `footballmaster` nor the multi-sport demo:

`background`, `ball_out_of_play`, `card`, `clearance`, `corner_kick`, `foul`, `free_kick`, `goal`, `kick_off`, `offside`, `penalty_kick`, `shot`, `substitution`, `throw_in`.

Three SoccerNet distinctions are collapsed for this pilot: on/off-target shots become `shot`; direct/indirect free kicks become `free_kick`; card colors become `card`. Long balls, player identities, formations, pressing triggers, run types, and tactical intent are not SoccerNet-v2 action labels and have no supervision here.

Single-label-eligible support was 810 train / 356 validation / 389 test windows. Test support was:

| Class | Test n |
|---|---:|
| background | 96 |
| ball out of play | 93 |
| card | 6 |
| clearance | 14 |
| corner kick | 12 |
| foul | 45 |
| free kick | 21 |
| goal | 2 |
| kick off | 7 |
| offside | 14 |
| penalty kick | 0 |
| shot | 21 |
| substitution | 10 |
| throw in | 48 |

Penalty-kick performance is therefore not estimable. Goal performance has only two test examples.

## Non-VLM baseline

This component is deliberately named a baseline, not a VLM.

1. Sample 12 silent uniform frames per 12-second candidate.
2. Run each frame through a frozen ONNX Model Zoo MobileNetV2 trained on ImageNet.
3. Aggregate its 1,000 output scores with mean, standard deviation, maximum, last-minus-first, and center-minus-edges statistics: 5,000 values.
4. Apply train-fitted standardization and a fixed seeded random projection to 256 dimensions.
5. Fit a class-balanced 14-way multinomial softmax head.
6. Train five hyperparameter candidates for 350 epochs each; select by validation macro-F1 and balanced accuracy; touch test only after selection.
7. Select the abstention threshold on validation only.

Feature extraction covered 18,660 decoded frames and took 432.2404 seconds on CPU. The learned head has 3,598 fitted weights/biases. Frozen generation: `fde62ed3925bb8c9353661bb`.

| Frozen test metric | Result |
|---|---:|
| Candidate windows | 389 |
| Exact accuracy | 0.4293 |
| Wilson 95% accuracy interval | [0.3810, 0.4789] |
| Top-3 accuracy | 0.7558 |
| Macro-F1 over 13 test-supported classes | 0.3589 |
| Balanced accuracy over supported classes | 0.3725 |
| Train-majority baseline accuracy | 0.2391 |
| Validation-selected threshold | 0.90 |
| Selective test coverage | 0.4884 |
| Selective test accuracy | 0.5579 |

The test confusion matrix shows serious class-specific gaps: goal recall 0/2, free-kick recall 1/21, offside recall 2/14, and shot recall 5/21. Clearance was strongest at 12/14 recall, but its support is small. These are feasibility diagnostics, not generalization claims.

The model package recomputes all 389 predictions and metrics, checks six artifact hashes, and validates all 389 detailed reports. A clean reproduction under `.agent/soccermaster-scale-reproduction` produced the identical generation and exact accuracy.

## Local VLM experiment

Before the first request, the evaluator froze 50 test windows across the two held-out games, taking up to four examples per supported class. Goal had only two eligible examples and penalty had none. This produces a deliberately class-stratified diagnostic subset, not a prevalence-weighted sample.

The inference manifest contained no ground-truth fields. A separate sealed-label file and its SHA-256 were recorded before inference. Gemma received:

- eight chronological frames as two contact sheets;
- no audio;
- no team, game, score, or source metadata;
- a fixed 14-class taxonomy plus `insufficient_visual_evidence`;
- a strict JSON schema requiring confidence, evidence frames, observable summary, coarse field region, and explicit abstention.

The runtime served only `google/gemma-4-e4b` on loopback. Every example persisted its contact sheets, label-free input manifest, exact request, raw response, validated prediction, latency, and receipt. A raw-response index binds all 50 terminal records.

| VLM metric | Result |
|---|---:|
| Frozen denominator | 50 |
| Schema-valid responses | 50 / 50 |
| Runtime failures | 0 / 50 |
| Accumulated model request time | 584.56 s |
| Median / mean / maximum latency | 8.056 / 11.691 / 33.714 s |
| Abstentions | 24 / 50 (48%) |
| Exact correct, abstentions counted wrong | 3 / 50 (6.0%) |
| Wilson 95% interval | [2.06%, 16.22%] |
| Subset majority baseline | 4 / 50 (8.0%) |
| Non-abstained exact accuracy | 3 / 26 (11.54%) |

Prediction collapse was severe: 24 abstentions, 13 `background`, 9 `shot`, 2 `card`, 1 `foul`, and 1 `kick_off`. The VLM never predicted eight supported classes in the frozen subset.

The 389-example baseline result and 50-example VLM result are **not a controlled model comparison**: their denominators and sampling distributions differ. No post-hoc prompt, threshold, or taxonomy tuning was performed after test labels were revealed.

## Direct false-positive audit

One preselected result was directly inspected after sealed scoring:

- Example: `soc-f9467523960ecb187648`
- Ground truth: `foul`
- Gemma output: `shot`, confidence 0.90
- Gemma prose claimed that the ball passed the goalkeeper and entered the net.
- The eight frames instead show midfield/touchline play, a close challenge, players going down, and a referee gesture; they do not visibly establish a shot or goal-line crossing.

This is an illustrative audit, not a statistically sampled prose-factuality estimate. It demonstrates why non-empty detailed prose cannot be treated as grounded detail. Observable-summary and trajectory factuality were **not** annotated or scored, so VLM prose is not safe for coach search.

## Detailed report contract

The non-VLM path emits one report per test candidate with explicit origins:

- learned: candidate class probability;
- deterministic: window/candidate timestamps, abstention decision, and prose template;
- unavailable: actor, team, field location, trajectory, tactical context, and outcome beyond the predicted class.

The VLM path preserves richer raw fields, but those fields are marked unverified and unsafe for retrieval. A future coach-facing system must score each atomic claim against human annotations or evidence—not just require a well-formed paragraph.

## What this result means

The scale-up succeeded as infrastructure and failed as a semantic VLM system.

- **Succeeded:** authentic footage acquisition, 12.42-hour corpus, complete games, source-held-out splits, resumable feature/VLM processing, label sealing, 50/50 schema reliability, raw-response provenance, deterministic metric reproduction, and standalone soccer code.
- **Failed/no-go:** the tested zero-shot local VLM did not reliably distinguish fine soccer events from sparse silent frames; its 6% exact accuracy was below the subset majority baseline and its prose could invent outcomes.
- **Still unknown:** whether a soccer-specialized temporal VLM, denser frame/video tokens, parameter-efficient fine-tuning, tracking/field tools, or audio-aware cross-checking improves performance.

## Next research steps

1. **Separate spotting from classification.** Add dense one-second candidate generation over full halves and score SoccerNet action-spotting mAP before connecting natural-language search.
2. **Train a temporal soccer model.** Use substantially more SoccerNet train games, a video backbone rather than independent image scores, and class-balanced episodic sampling. Keep game/source groups disjoint.
3. **Evaluate actual video tokens.** Compare sparse contact sheets with a local model/runtime that truly consumes video or many temporally ordered frames. Freeze the prompt and subset before test.
4. **Add player/action annotations.** Long balls, player identity, formation, pressure, run type, and tactical intent require a new annotation schema or a rights-compatible linked dataset. Do not infer them from SoccerNet-v2 event names.
5. **Score atomic report claims.** Annotate actor, action, object, field region, trajectory, outcome, evidence interval, and abstention. Measure entailment and unsupported-claim rate separately from event accuracy.
6. **Use commentary only as a sealed post-hoc check.** Audio/ASR must never leak into the video-only prediction. Measure agreement and disagreement after visual inference.
7. **Keep the coach interface behind a semantic gate.** Until player/action detail is annotated and validated, the UI should expose only candidate clips, confidence, evidence frames, and a prominent research/no-go warning.

## Reproducibility and verification

- Corpus receipt: `artifacts/soccermaster-scale-v1/corpus-receipt.json`
- Baseline package: `artifacts/soccermaster-scale-v1/pilot-v1/`
- VLM subset receipt: `artifacts/soccermaster-scale-v1/vlm-subset-receipt.json`
- VLM evaluation package: `artifacts/soccermaster-scale-v1/vlm-eval-v1/`
- Private raw run: `data/private/soccermaster-scale-v1/vlm-eval/run-v1/`
- Package guide: `prototype/soccermaster_scale/README.md`
- Focused tests: `tests/test_soccermaster_scale.py`

Receipt SHA-256 values:

- corpus receipt: `27240a28254bb02a94574b1c09ea4c5d788bb96147df21257c448aa56fd1ebdf`
- baseline package receipt: `6924980785ecdd54e905df4757b8c6efd577942d65f527617f3f8a72f89abdb6`
- frozen VLM subset receipt: `2b06a3748374ec600aa371b6ab2e743b0ce585e1eb4b76ee2c328064c7d21c17`
- VLM run receipt: `97581a7f12a2d05052fd47a0b1892dd16c22923b84ca2ad1f3a40f0b529c48c4`
- VLM evaluation package receipt: `3494dd229c3e3a37df98cac49dd80e663deabe312278f98832c5eb018a5df86b`

Verification completed before this report:

- manifest: 12/12 checks passed;
- soccer-focused tests: 12/12 passed;
- integrated repository verify: 253 tests passed after the football lane corrected its concurrent import-isolation regression;
- baseline package: all hashes, 389 predictions, metrics, and reports reproduced;
- clean baseline retrain: identical generation and test accuracy;
- VLM package: label sealing, prompt/schema hashes, 50 raw-response hashes, denominator, and exact accuracy reproduced;
- lifecycle: doctor, reproduce, log collection, smoke test, and preview-only safe reset passed.

Primary source links: [SoccerNet data portal](https://www.soccer-net.org/data), [SoccerNet-v2 paper](https://arxiv.org/abs/2011.13367), [ONNX Model Zoo MobileNet documentation](https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet).
