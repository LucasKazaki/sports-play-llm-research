# PhD-CS methodology audit for the Archit presentation

**Audit date:** 27 August 2026  
**Decision:** **Needs P0 wording corrections before presentation; otherwise suitable for a private systems/failure-analysis demo.** No current result supports a benchmark, generalization, calibrated-confidence, grounding-quality, action-spotting, or overall model-quality claim.

## Technical summary

The strongest contribution is the evaluation plumbing: authorized real footage, silent visual inputs, hash-bound artifacts, a frozen primary pass, failures retained in the denominator, and visual outputs sealed before commentary. The saved numbers recompute correctly. The weakest part is the scientific estimand. This is not SoccerNet action spotting and not naturalistic “play detection.” It is a hand-selected, event-centered, closed-set classification probe over six clips from one match, with a generous any-label-in-window score and no negative/background windows.

The most defensible result is:

> Under a frozen prompt, Gemma 4 E4B completed 3/6 requests in the primary system pass and matched a mapped SoccerNet-v2 label occurring somewhere in 1/6 ten-second windows. After a post-hoc serving-stack change, all six requests completed, but 0/6 matched an allowed window label. These are case-level feasibility and failure observations on one match, not estimates of soccer understanding.

Commentary is **sealed and modality-separated**, but it is not independent and does not validate correctness. The ASR describes the same broadcast event, the same Gemma weights perform the text classification, and `supports` means only that two saved labels are equal. The strict commentary-v3 schema was also introduced after a validation taxonomy failure, so its 6/6 completion is a post-hoc systems-recovery result.

## Exact task that actually ran

For each chosen class, the clip builder selected the **first SoccerNet-v2 annotation marked `visible`** in a match half and cut five seconds before and after that point. Development contains five selected center classes; validation contains six. The visual input is 12 uniformly spaced, timestamp-labeled still images. The prompt asks for the primary observable action near the midpoint from 17 SoccerNet classes plus `background_or_other`, or the separate abstention response `insufficient_visual_evidence`. See the [clip builder](../prototype/build_soccernet_clips.py), [visual prompt and sampler](../prototype/real_clip_vlm.py), [frozen v1 configuration](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-v1.json), and [public-safe overlap binding](../artifacts/soccernet-pilot-v1/soccerdb-overlap-binding-v1.json).

Let `x_i` be the 12-image input, `y_i` the centered annotation, and `A_i` the set of all mapped `visible` annotation labels whose timestamps fall anywhere in the ten-second window. The main descriptive metric is

\[
\frac{1}{N}\sum_{i=1}^{N} \mathbf{1}[\text{request completed and }\hat y_i\in A_i],
\]

with timeouts and malformed outputs scored incorrect. This is **allowed-window classification accuracy**, not SoccerNet's full-match temporal spotting metric. SoccerNet action spotting predicts action timestamps in untrimmed matches and evaluates average precision across temporal tolerances; SoccerNet-v2 provides point annotations rather than event intervals. [Official SoccerNet task definition](https://www.soccer-net.org/tasks/action-spotting), [SoccerNet-v2 paper](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/papers/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.pdf)

Important consequences:

- There are no sampled no-action windows, so the pilot cannot estimate false-positive rate, specificity, event prevalence, or spotting performance.
- Accepting any member of `A_i` can reward a nearby context event instead of the intended midpoint event. Only two validation windows contain a single mapped label.
- The six center labels were deliberately chosen and use occurrence zero. They are not a random or prevalence-weighted sample of the 17-class task.
- The emitted temporal interval and free-text spatial regions are not compared with human evidence. `trajectory` is forced empty. The run tests structured emission, not grounding validity.

## Prioritized findings

### P0 — Correct before presenting

#### P0-1. Frame the task as curated event-window classification, not soccer-play detection or action spotting

**Evidence.** Slides 1 and 3 ask whether the VLM can identify a soccer play from video; slide 4 calls six clips “held-out”; slide 10 uses “held-out label.” In fact, the six clips were label-selected event windows, the label classes largely repeat development classes, and there are no negative windows. The primary v1 clips were unseen at prediction time; the recovery clips were not.

**Required edit.** Use “match-disjoint primary-v1 clips” rather than “held-out plays.” State the conditioning explicitly: “Given a label-selected ten-second window, classify the midpoint action from a closed taxonomy or abstain.” Do not use “action spotting,” “detect plays in a match,” or an 18-way performance claim.

#### P0-2. Commentary is a consistency probe, not an independent auditor

**Evidence.** Slide 11 is titled “Commentary is a noisy independent check.” The visual and commentary stages are causally isolated, which is good, but both concern the same event, use the same normalized taxonomy, and use `google/gemma-4-e4b`. SoccerNet-Echoes is automatically transcribed broadcast commentary, with documented missing commentary and substantial ASR error. A commentary-only study reports competitive spotting from 10-second ASR windows, confirming that commentary is an alternative predictive modality rather than external truth. [SoccerNet-Echoes paper](https://arxiv.org/abs/2405.07354), [Chakraborty et al., IJCNLP-AACL Student Research Workshop 2025](https://aclanthology.org/2025.ijcnlp-srw.6/)

The strict-v3 contract was introduced after the first validation recovery produced the out-of-taxonomy label `free_kick`; it was then checked on development and reapplied to the same six validation clips. That repairs schema reliability but cannot produce a fresh validation estimate. In the saved cross-tab, commentary matched an allowed window label in 3/6 cases, while neither of the two `supports` relations supported a correct visual label.

**Required edit.** Rename slide 11 to **“Commentary is a sealed cross-modal consistency probe—not ground truth.”** Say: “Sealing prevents commentary from changing the visual result; it does not make the two signals statistically independent.” Label strict v3 **post-hoc schema recovery**.

#### P0-3. Do not claim calibrated confidence or validated grounding

**Evidence.** `confidence` is a generated scalar constrained to `[0,1]`; it is not a class probability, log-probability, or score calibrated on held-out data. Abstention is a prompted JSON branch whose confidence is forced to zero, not a learned or thresholded selection function. The 0.95 wrong goal is a **high-self-score error**, not proof of population miscalibration. Calibration requires comparing stated confidence with empirical correctness over enough held-out cases; reliable abstention is normally evaluated through coverage–risk behavior. [Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a.html), [Whitehead et al., ECCV 2022](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136960146.pdf)

The output interval is restricted to adjacent sampled timestamps, but no human temporal interval or cue annotation is scored. SoccerLens specifically separates correct event labels from spatiotemporal cue grounding; its reported results are a recent preprint, not a universal benchmark conclusion. [SoccerLens preprint](https://arxiv.org/abs/2605.09598)

**Required edits.** Change slide 10's `Confidence` column to **“Model self-score (uncalibrated)”**. On slide 3 and in the talk track, say **“returns a self-reported evidence interval; grounding was not evaluated.”** In the report, replace “evidence of miscalibration on this case” with “a high-self-score error; calibration cannot be assessed from this sample.”

#### P0-4. Bound the bottom-line claim to this pilot

**Evidence.** Slide 15 says “The current local VLM is not yet good at the task” and “The pipeline is now real and reproducible.” Six curated clips cannot establish model-level competence, and exact external reproduction is limited by private media and an incompletely pinned primary-v1 serving stack.

**Required edit.** Use: **“The real, locally replayable pipeline is hash-auditable. Gemma failed all six allowed-window decisions in the post-hoc recovery rerun; this does not estimate performance beyond this pilot.”**

### P1 — Material caveats to surface in the talk and Q&A

#### P1-1. Match disjointness prevents exact-match reuse, not domain dependence

Development and primary validation use different matches and clip IDs, but both are Barcelona first halves from the same 2015–16 UEFA Champions League season. Thus the split is not team-, competition-, season-, or broadcast-domain-disjoint. Clips within a match are correlated, so `N=6` is not six independent match draws. The decision not to show a clip-level binomial interval is correct. Say “match-disjoint one-match pilot,” never “generalization set.”

#### P1-2. The development process is highly adaptive, even though primary v1 was frozen correctly

The artifact inventory contains 12 saved visual development batches before the v1 freeze, spanning GLM, Gemma E2B/E4B, prompt/schema/input variants, plus targeted probes—all on five clips. That is legitimate engineering development but makes development performance unusable and creates substantial configuration-overfitting risk. The v1 freeze timestamp precedes the primary predictions, which supports the one-pass claim; a hash cannot prove that no human had previously viewed the media or labels. Reusing a holdout after inspecting outcomes is adaptive analysis, which is why recovery v2 and commentary v3 must remain post hoc. [Dwork et al., Science 2015](https://www.science.org/doi/10.1126/science.aaa9375)

For any next model or prompt comparison, create a new untouched, match-grouped test set before looking at results. Do not use the current six clips to select Qwen, sampling density, prompt wording, or confidence policy and then report them as test performance.

#### P1-3. The input is sparse ordered imagery, not a controlled test of native temporal modeling

The source is 398×224 at 25 fps. Twelve frames are sampled about 0.9 seconds apart and resized to a 1280×720 single-image canvas; resizing does not restore detail. Slide 6's “12 full-resolution frames” is therefore misleading. Use **“12 uniformly sampled, upscaled stills from a 398×224 source; no native video/audio path.”**

Gemma's official video path also represents video through frame sequences, but processor, timestamp encoding, visual token budget, and sampling policy differ from this OpenAI-compatible multiple-image path. A “Gemma frames versus Qwen native video” comparison would change model and representation simultaneously. Use a preregistered factorial ablation: model × representation × sampling density, with clip hashes, prompt, output contract, and requested-set denominator fixed. [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4), [official Gemma video guide](https://ai.google.dev/gemma/docs/capabilities/vision/video), [Jiang et al., CVPRW 2025](https://openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Jiang_Domain_Adaptation_of_VLM_for_Soccer_Video_Understanding_CVPRW_2025_paper.html)

#### P1-4. The serving comparison is diagnostic, not a causal ablation

The primary and recovery runs share clip hashes, prompt, sampler, and model identifier, but recovery also changes endpoint ownership, process manager, backend/runtime receipt, and serving settings. Recovery v2 cryptographically binds model and projector files; the public v1 freeze binds only the model identifier, not equivalent binary/weight hashes. Therefore say **“the timeout pattern did not reproduce under the isolated stack”**, not “isolation caused the speedup.” Change slide 9's “accuracy fell” to **“Recovery removed timeouts; semantic score was 0/6 on the same post-hoc clips.”**

#### P1-5. Visual leakage and shortcut risks remain open

Audio, labels, paths, match identity, and commentary are correctly absent from the visual request. However, the pixels still contain broadcast overlays, score changes, replay structure, kits, camera style, and celebrations. Both selected matches feature Barcelona, and pretraining contamination by these recognizable broadcasts cannot be ruled out from the Gemma model card. SoccerLens motivates inspecting cue use rather than assuming label correctness implies play understanding.

A stronger evaluation should include overlay-masked pairs, replay/live-shot flags, celebration-without-goal hard negatives, goalmouth-without-goal hard negatives, and non-event windows. Report paired changes, not only aggregate label accuracy.

### P2 — Strengthening edits and next experiments

- **Literature wording.** On slide 13, replace “Top VLMs remain weak” with “SoccerLens reports <50% grounding for the models it tested.” Describe the commentary paper as one student-workshop study, not settled evidence. Keep the 20k-clip CVPRW adaptation result explicitly incomparable to this zero-weight-update pilot.
- **Separate three tasks.** Pre-register one of: event-centered classification, full-match action spotting, or open-ended QA. Give each its own inputs and metrics. Do not mix clip accuracy with SoccerNet mAP.
- **Adjudicate answerability.** Two annotators should label the intended midpoint action, all actions actually visible, replay/live status, cue interval, and evidence region; adjudicate disagreements and report agreement.
- **Add negatives and coverage.** Include no-action/background and hard-negative windows. For abstention, report answered coverage and selective risk on a future sufficiently large test set. Descriptively, recovery v2 answered 4/6, abstained on 2/6, and all four answered cases were wrong; this is not a curve or calibration estimate.
- **Use nested grouping.** Tune on multiple development matches, choose once on a validation group, and report one untouched test group. Group uncertainty by match; add team/competition/season diversity.
- **Factor the next experiment.** Compare matched frames and official video processing within each model before comparing models. Hold visual-token budget or report it explicitly.

## Exact slide and talk-track changes

| Location | Replace or add |
|---|---|
| Slide 1 subtitle | “Closed-set probe on six label-selected, 10-second clips from one match; visual-only model input.” |
| Slide 3 question | “Given a label-selected 10-second window, can 12 ordered stills support one normalized action label or abstention?” Add: “Evidence interval emitted, not externally scored.” |
| Slide 4 | Change “held-out clips” to “primary-v1 clips from a different match.” Add verbally: same team, competition, and season; one match only. |
| Slide 6 | Replace “12 full-resolution frames” with “12 uniformly sampled stills; 398×224 source upscaled for input.” |
| Slide 9 title | “Recovery removed timeouts; semantic score was 0/6 on the same post-hoc clips.” |
| Slide 10 | Change “Held-out label” to “Center label (hidden from model)” and “Confidence” to “Self-score (uncalibrated).” |
| Slide 11 title | “Commentary is a sealed cross-modal consistency probe—not ground truth.” Add: same event, same Gemma weights, and v3 is post-hoc schema recovery. |
| Slide 12 title | “Qualitative case: one sampled frame appears to show a card; the VLM abstained.” Do not present this as adjudicated grounding evidence. |
| Slide 15 | “This hash-auditable local pipeline ran on real footage. Gemma failed this six-clip post-hoc rerun; broader competence is unknown.” |
| Talk opening | “This is curated event-window classification, not full-match spotting: first visible occurrences of chosen labels, 12 stills per 10-second window, closed taxonomy, no negative windows.” |
| Talk on recovery | “Timeouts did not reproduce under a different isolated serving stack; this is diagnostic, not a controlled causal ablation or independent accuracy estimate.” |
| Talk on commentary | “Sealed means non-intervening, not independent. `Supports` means label equality only; it cannot validate correctness.” |
| Talk on confidence | “The numbers are generated self-scores. No calibration set, reliability curve, ECE/Brier score, or risk–coverage curve exists.” |

## Questions Archit is likely to ask

1. **What is the estimand?** Case-level success on selected event-centered windows; there is no population estimator yet.
2. **Why call it validation if you reran it?** Only primary v1 was the frozen first pass. Every recovery result is explicitly post hoc.
3. **Where are background/no-action clips?** They are absent; therefore this is classification conditioned on an annotated event, not spotting.
4. **Why should any label in ten seconds count?** It handles overlapping point annotations but is intentionally generous and can miss the midpoint target. Human answerability labels are needed.
5. **Is 0/6 evidence Gemma cannot understand soccer?** No. It is evidence that this quantized model/input/runtime/prompt combination failed these six cases.
6. **Is commentary independent?** No. It is only causally separated from the visual output and useful as a cross-modal consistency or commentary-only baseline.
7. **Is confidence calibrated?** No. It is an uncalibrated generated scalar; abstention is prompt-driven.
8. **Is the cited interval grounded?** Not yet. It is schema-valid but has no human temporal/spatial comparison.
9. **Could the model exploit the scoreboard or memorize the game?** Yes; those risks are untested and should become paired ablations.
10. **What is the next falsifiable experiment?** A preregistered, multi-match test with human answerability/evidence labels, negative windows, model × representation ablation, and match-grouped uncertainty.

## Evidence inspected

- [Current technical report](soccernet-real-footage-pilot-2026-08-27.md)
- [Current Archit talk track](archit-demo-talk-track.md)
- [Current 15-slide deck](../presentation/PlayGround-Real-Soccer-VLM-Results-2026-08-27.pptx)
- [Independent quantitative validation](data-validation-2026-08-27.md)
- [Frozen primary v1 summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-frozen-v1-summary.json)
- [Post-hoc visual recovery v2](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-isolated-recovery-v2-summary.json)
- [Strict commentary recovery v3](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-isolated-strict-recovery-v3-summary.json)

The quantitative records are internally consistent: primary v1 is 3/6 complete and 1/6 allowed-window correct; recovery v2 is 6/6 complete and 0/6 correct; strict commentary v3 is 6/6 complete with 2 supports, 2 contradictions, and 2 uninformative relations. Those verified counts do not remove the methodological limitations above.
