# Real-footage soccer event-window classification pilot

**Evidence report for the Archit demo — 27 August 2026**

## Technical summary

The project now runs end to end on **real, NDA-authorized broadcast footage** rather than generated soccer-like clips. The media was obtained from SoccerNet and matched to SoccerDB entries through SoccerDB's published match-name mapping; hashes integrity-bind the pinned mapping and selected SoccerNet files. The precise description is **SoccerDB-mapped SoccerNet footage** or **SoccerDB/SoccerNet overlap**. The evaluated labels remain SoccerNet-v2 point annotations; they are not SoccerDB's time-bounded event segments.

The current system is a local VLM pipeline, not a classical soccer detector. It decodes each roughly 10-second silent clip, uniformly selects 12 timestamped frames, and asks a local VLM for one structured action label, a generated self-score, and visual evidence fields. The frozen primary and serving-recovery paths use `google/gemma-4-e4b`; a later same-clip engineering comparison uses `qwen/qwen3.5-9b`. No tracker, optical-flow rule, color heuristic, or hand-engineered classifier determines the answer. Frame decoding, timestamping, hashing, and JSON validation are deterministic infrastructure around the VLM.

No model weights were fine-tuned. Here, **development/training split** means that the prompt, taxonomy, structured-output schema, frame sampling, model choice, and serving settings were selected on five clips from one match. A six-clip match-disjoint validation set was then run once under a frozen v1 configuration. That primary pass completed only three of six requests because of local serving timeouts. Under the fail-closed metric policy, the timeouts count as incorrect: first-pass schema validity was 3/6, allowed-window accuracy was 1/6, and strict exact accuracy on the two single-label clips was 0/2. This is an honest feasibility/failure-analysis result, not a benchmark estimate.

The serving failure was investigated separately. The same model and prompt later completed all five development clips under a dedicated single-model runtime, with median latency 9.586 seconds. A hash-bound recovery v2 then completed all six of the same validation clips with 100% schema-valid output and median latency 9.306 seconds, so the v1 timeout pattern did not reproduce. However, none of the six recovery predictions matched an allowed SoccerNet label timestamp in its window. Runtime reliability improved; the semantic score did not. Because those validation clips had already been inspected in v1, recovery v2 is explicitly post hoc and is reported beside, never instead of, the frozen primary pass.

Commentator audio is not given to the visual model. Only after the visual summary is hash-sealed does a text-only model inspect temporally aligned SoccerNet-Echoes ASR. Its output is reduced to `supports`, `contradicts`, or `uninformative`, and cannot change the visual answer. This matters empirically: in the v1 validation run, commentary supported both a correct visual `goal` and an incorrect visual `goal` on a `shot_off_target` window. Under the canonical strict recovery-v3 commentary configuration, all six cross-checks completed: two supported, two contradicted, and two were uninformative. Commentary agreement is therefore not correctness.

After the Gemma results were known, Qwen3.5-9B was developed and run over the same six clips. It completed 6/6 requests, matched an allowed mapped label in 3/6 windows, and was exact on 1/2 single-label windows, with median latency 9.9925 seconds. All 72 decoded frame records match Gemma byte-for-byte, but input packaging differs: Gemma received twelve one-frame 1280×720 sheets; Qwen received six two-frame 1280×360 sheets after the twelve-image request exceeded the fixed 8,192-token context. Qwen was selected post hoc and the representation changed with the model, so this is a hypothesis-generating engineering comparison—not an independent test estimate or causal model ranking.

The defensible demo claim is:

> A hash-auditable local pipeline now performs structured, visual-only event-window classification on real SoccerDB-mapped SoccerNet clips. In a post-hoc same-clip comparison, Qwen matched 3/6 allowed-window labels while Gemma recovery matched 0/6. Six curated windows from one match, adaptive model choice, different image grouping, and unvalidated grounding preclude any benchmark, causal, calibration, or generalization claim.

## What data was used

### Dataset identity and rights boundary

- The source media is SoccerNet broadcast video accessed under the user's existing NDA authorization. The credential was used only for bounded acquisition and was not persisted in project artifacts.
- SoccerNet states that its NDA prevents redistribution, that researchers may train their own models, that sourced screenshots/clips may appear in research papers or presentations, and that the data is non-commercial. This project displays sourced clips only as part of a local research presentation to authorized participants, names SoccerNet as the source, and keeps the media private; it does not infer blanket permission for a standalone public demo. [SoccerNet FAQ](https://www.soccer-net.org/faq)
- SoccerNet's data catalog describes 500 + 50 broadcast videos at 25 fps in 720p or 224p and requires the NDA before video download. The standard SoccerNet-v2 action-spotting task uses 500 games and 17 action classes, with each action annotated by one timestamp. [SoccerNet data catalog](https://www.soccer-net.org/data), [action-spotting task](https://www.soccer-net.org/tasks/action-spotting), [official devkit](https://github.com/SoccerNet/sn-spotting)
- SoccerDB reports 346 matches, 171,191 unique video segments, 37,709 time-bounded event labels, 702,096 video bounding boxes, and 17,115 highlight annotations, with 10 event classes plus background. The paper says 270 of its matches came from SoccerNet. Its abstract and tables differ slightly on total event/playback counts, so this report consistently uses the abstract values. [SoccerDB paper](https://arxiv.org/html/1912.04465), [official repository](https://github.com/newsdata/SoccerDB)
- SoccerDB publishes `SoccerDB2SoccerNet.csv`, mapping SoccerDB video names to SoccerNet match names. The project pinned that mapping to commit `ac9c9c50d14b683b8eca464f55a700cffb95b629`, verified its SHA-256, and matched both selected halves to exact rows. [Published mapping directory](https://github.com/newsdata/SoccerDB/tree/master/dataset/video_dataset), [pinned raw mapping](https://raw.githubusercontent.com/newsdata/SoccerDB/ac9c9c50d14b683b8eca464f55a700cffb95b629/dataset/video_dataset/SoccerDB2SoccerNet.csv), [local overlap binding](../artifacts/soccernet-pilot-v1/soccerdb-overlap-binding-v1.json)

This provenance does **not** mean the project downloaded a separate SoccerDB video release. It means the actual SoccerNet match halves are members of the overlap published by SoccerDB.

### Bounded split

| Role | Match half | Clips | Target play labels |
|---|---|---:|---|
| Prompt/schema/runtime development | Barcelona–Roma, 24 Nov 2015, first half | 5 | corner, shot off target, goal, foul, yellow card |
| Frozen primary-v1 set / post-hoc comparison set | Barcelona–BATE, 4 Nov 2015, first half | 6 | corner, shot off target, goal, foul, yellow card, direct free kick |

The matches, manifests, and opaque clip IDs are disjoint. They are not team-, competition-, season-, or broadcast-domain-disjoint: both matches are Barcelona first halves from the same 2015–16 UEFA Champions League season. Each event-centered clip is approximately 10 seconds. Every VLM copy has zero audio streams; a separate local-review copy retains the broadcast commentary. The clip builder verifies both conditions before admitting a clip.

The label source is SoccerNet-v2 `Labels-v2.json`. These are action spots—one timestamp per annotated action—not event intervals. A 10-second window can therefore contain more than one mapped SoccerNet label timestamp. Whether every annotated action is visually answerable in the 12 sampled frames is unknown because these windows were not independently adjudicated. The primary metric records the timestamp overlap without pretending every centered window is semantically pure. [SoccerNet action-spotting definition](https://www.soccer-net.org/tasks/action-spotting)

### Why arbitrary famous broadcasts were not added

Publicly viewable television footage is not automatically licensed for downloading, processing, or redistribution. No arbitrary YouTube, social-media, or famous-match broadcast was acquired. A future broadcast extension needs an explicit reusable license or owner permission plus a source manifest. The authorized SoccerNet path already supplies real television footage without silently expanding the rights scope.

## Backend: exact computation path

```text
NDA-authorized SoccerNet half + acquisition hashes
                         |
Pinned SoccerDB<->SoccerNet mapping row
                         |
               overlap-binding verifier
                         |
      SoccerNet-v2 point label selects a 10 s window
                         |
          +--------------+--------------+
          |                             |
silent visual-only MP4            review MP4 + Echoes ASR
          |                             |  (kept closed)
12 uniform timestamps                   |
          |                             |
12 timestamped stills                   |
          |                             |
Gemma: 12 one-frame sheets              |
Qwen: 6 two-frame sheets                |
local VLM + strict JSON schema          |
          |                             |
hash-sealed visual summary -------------+
                         |
        text-only commentary classification
                         |
supports / contradicts / uninformative only
```

### 1. Acquisition and identity binding

The acquisition stage uses a bounded allowlist: one video half, SoccerNet-v2 labels, and SoccerNet-Echoes ASR for each selected match. SHA-256 receipts bind every downloaded file. The overlap verifier independently checks the pinned public CSV hash, the exact SoccerDB-to-SoccerNet row, the source-video and label hashes, clip IDs, rights fields, and train/validation disjointness. Its public report contains no credential or private filesystem path.

### 2. Clip construction without answer leakage

The SoccerNet point label is used only to choose the temporal window and later to score the response. For every target, the builder creates:

- a physically silent MP4 for the VLM;
- an audio-bearing MP4 for local human review;
- a clip-local ASR file with opaque segment IDs and times;
- a manifest record with file hashes, media metadata, the centered target, and every mapped SoccerNet label timestamp in the window.

The model request contains none of the SoccerNet label, allowed-window labels, match identity, commentary, source path, or score context. The source video is not sent to a hosted API.

### 3. Visual model input and output contract

The runner decodes 12 frames at uniformly spaced timestamps. It hashes each decoded frame and makes 12 chronological, timestamp-labeled, single-frame image inputs on a 1280×720 canvas. The source halves are 398×224 at 25 fps, so the larger canvas standardizes the interface but does not create visual detail. Although the Gemma 4 family supports native multimodal/video input, this experiment deliberately uses ordered frames through a local OpenAI-compatible image interface; the model never decodes the MP4 container and never hears audio. [Official Gemma 4 overview](https://ai.google.dev/gemma/docs/core)

The prompt asks for the primary observable play near the midpoint from a fixed taxonomy derived from SoccerNet-v2 plus `background_or_other`. The model may instead return `insufficient_visual_evidence`. The strict schema requires:

- one normalized answer;
- one generated self-score in `[0,1]` (not calibrated confidence in this pilot);
- one evidence interval whose endpoints are valid sampled timestamps;
- non-empty coarse spatial evidence for non-abstentions;
- an empty trajectory list in this pilot;
- internally consistent abstention fields.

There is no semantic retry or post-hoc answer repair. A malformed response, timeout, stale cache, hash mismatch, or schema violation becomes an explicit failed clip.

### 4. Frozen evaluation and cache integrity

The v1 freeze hashes the development summary, train and validation manifests, model ID, loopback endpoint, prompt, response schema, sampler version, sample count, number of image inputs, and token budget. The batch runner refuses mismatches before inference. Cached predictions are reusable only if their request, input-manifest, clip, prompt, schema, sampler, endpoint, and source-manifest hashes all agree.

The recovery design adds a public-safe isolated-runtime receipt that binds the direct server binary, model and multimodal projector hashes, loopback model identity, context size, parallelism, GPU settings, and live process/port ownership. A recovery-v2 result is admissible only if that receipt is frozen and rechecked before each clip.

### 5. Scoring policy

Let `N` be every clip requested by the immutable manifest, including inference failures.

- **First-pass schema-valid rate:** number of completed schema-valid responses divided by `N`.
- **Allowed-window accuracy:** number of completed predictions matching any mapped SoccerNet label timestamp in the 10-second window divided by `N`. This is tolerant of overlapping point labels and is the main descriptive semantic metric; it does not certify that the event is visible in the sampled frames.
- **Single-label exact accuracy:** exact matches only among windows containing one mapped label timestamp; failed eligible requests remain in the denominator.
- **Completed-only metrics:** secondary diagnostics only. They cannot hide timeouts or malformed outputs.
- **Abstention:** valid but scored incorrect when an annotated allowed label is present. It is retained because calibrated refusal is a research target, not because it earns correctness here.

No confidence interval is reported. With one validation match and six clips, clip-level binomial intervals would falsely imply independent sampling, and match-level uncertainty is not estimable.

### 6. Commentary is a sealed post-hoc consistency probe

Before the commentary stage opens an ASR file, it saves a hash seal over the manifest, visual summary, visual prompt, model identity, and completed visual IDs. The text request contains only:

```json
{
  "aligned_asr_segments": [
    {"segment_id": "opaque", "relative_start_s": 0.0, "relative_end_s": 1.2, "text": "..."}
  ],
  "clip_duration_s": 10.0,
  "target_relative_s": 5.0
}
```

It does not contain the visual prediction, SoccerNet label, allowed labels, match name, absolute timestamp, file path, or video. After the text prediction is saved, deterministic code compares it with the already sealed visual answer. The comparison cannot modify the visual output.

SoccerNet-Echoes covers 1,100 halves from 550 games in 10 commentary languages and provides timestamped Whisper v1/v2/v3 transcriptions. The authors report that 70 halves have no commentary, note entity-name and hallucination failure modes, and report Whisper large-v2 WER of 0.458 on their 20-game verified subset. This supports treating commentary as noisy evidence, not truth. [SoccerNet-Echoes paper](https://arxiv.org/html/2405.07354), [official repository](https://github.com/SoccerNet/sn-echoes)

## Empirical evidence

### Development established a complete isolated serving path, not performance

Under the dedicated single-model runtime, all 5/5 development clips produced first-pass schema-valid outputs, 2/5 predictions matched an allowed label timestamp in their windows, and median latency was 9.586 seconds. Strict exact accuracy on the three single-label development windows was 1/3. These values were observed while selecting and hardening the system, so they are **not** held-out estimates. [Isolated development summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-train-development-gemma-e4b-isolated-v3-summary.json)

### Frozen primary validation v1: one correct window, two semantic non-successes, three serving failures

The exact frozen configuration is recorded in the [v1 freeze](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-v1.json); the immutable first pass is recorded in the [v1 validation summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-frozen-v1-summary.json).

| Clip | Center label | Allowed mapped labels in window | First-pass output | Outcome |
|---|---|---|---|---|
| V-001 | corner kick | corner kick, foul | abstained | incorrect |
| V-002 | shot off target | ball out, shot off target | goal, confidence 0.95 | incorrect |
| V-003 | goal | goal, penalty kick, shot on target | goal, confidence 1.00 | allowed-window correct |
| V-004 | foul | foul | timeout | incorrect; single-label eligible |
| V-005 | yellow card | yellow card | timeout | incorrect; single-label eligible |
| V-006 | direct free kick | ball out, direct free kick, shot off target | timeout | incorrect |

| Requested-set metric | Value | Denominator |
|---|---:|---:|
| First-pass schema-valid rate | 50.0% | 3 / 6 |
| Allowed-window accuracy | 16.7% | 1 / 6 |
| Single-label exact accuracy | 0.0% | 0 / 2 |
| Median latency, completed clips only | 110.624 s | 3 completed |

The result is descriptive. It does not distinguish model inability from temporal sampling loss, ambiguous point-label windows, or serving failure. The wrong `goal` with a generated self-score of 0.95 is a high-self-score error. Calibration cannot be assessed from this sample because there is no calibration set, reliability curve, ECE/Brier score, or risk–coverage analysis.

### Primary commentary v1: agreement can reinforce an incorrect answer

The [sealed v1 commentary summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-primary-v1-summary.json) completed 2/6 requested cross-checks. One queried clip emitted malformed/empty JSON and three clips lacked a visual prediction because of the v1 timeouts. Both completed checks `supported` the visual label:

- V-003: visual `goal`, commentary `goal`, and the window allowed `goal`.
- V-002: visual `goal`, commentary `goal`, but the window allowed only `shot_off_target` or `ball_out_of_play`.

Thus `supports` is an agreement relation, not an accuracy relation. The final strict development commentary check reinforces the same caution: all five cross-checks completed—four text-model queries plus one deterministic no-commentary case—but the relations were 0 support, 3 contradiction, and 2 uninformative. [Strict development commentary summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-train-commentary-isolated-strict-v4-summary.json)

### Recovery v2 fixed serving completion, not semantic correctness

Recovery v2 reran all six already inspected validation clips after moving the same model and prompt to a hash-bound, dedicated runtime. Its [frozen v2 configuration](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-recovery-v2.json) has SHA-256 `e636789282ecc01c713a10229bb4f88c7ae0bfd7aa9be0feda9b83544a25d68f` and binds the [isolated runtime receipt](../artifacts/soccernet-pilot-v1/isolated-vlm-runtime-receipt-v1.json) with SHA-256 `51efc870ebe63c5194401a52128167cab7b582da48c46c7f1e8e0640aba46b25`.

| Requested-set metric | Frozen primary v1 | Post-hoc recovery v2 |
|---|---:|---:|
| Completed / requested | 3 / 6 | 6 / 6 |
| First-pass schema-valid rate | 50.0% | 100.0% |
| Allowed-window accuracy | 1 / 6 (16.7%) | 0 / 6 (0.0%) |
| Single-label exact accuracy | 0 / 2 (0.0%) | 0 / 2 (0.0%) |
| Median latency, completed only | 110.624 s | 9.306 s |

The completion and latency changes are strong evidence that the v1 timeout failure did not reproduce under the isolated runtime. They are not evidence of better event-window classification. Recovery predictions were `background_or_other` on V-001, V-004, and V-006; `goal` on V-002; and abstentions on V-003 and V-005. None matched the mapped SoccerNet label timestamps accepted for its window. [Recovery-v2 visual summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-isolated-recovery-v2-summary.json)

The result must remain labeled **post-hoc serving recovery**. Reusing the same six validation clips after v1 was inspected means it is neither untouched nor an independent model-performance estimate. The sealed artifact itself sets `performance_claim_allowed=false`.

### Canonical strict commentary recovery v3 completed 6/6

The first commentary recovery attempt completed 5/6. On V-006 the text model produced `free_kick`, which is not in the frozen taxonomy, so the validator correctly rejected it. The commentary output contract was then tightened to a strict JSON schema, tested on all five development cross-checks, and applied to all six validation clips. This is a structural schema repair, not permission to alter the visual predictions.

The canonical [strict recovery-v3 commentary summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-isolated-strict-recovery-v3-summary.json) reports 6/6 completed and schema-valid text checks, with 2 `supports`, 2 `contradicts`, and 2 `uninformative`; median text-model latency was 5.792 seconds. The visual summary remained hash-sealed and unchanged. The earlier [non-strict recovery-v2 commentary artifact](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-isolated-recovery-v2-summary.json) is retained as failure evidence, not mixed with the canonical counts.

### Qwen3.5-9B same-clip comparison: 3/6 allowed-window matches

Qwen was chosen only after the Gemma validation results were known. It was developed on the existing five-clip development match and then frozen before its one complete pass over the existing six-clip comparison set. This prevents commentary leakage into Qwen's visual outputs, but it does not restore an untouched test estimate.

| Requested-set metric | Gemma recovery v2 | Qwen comparison |
|---|---:|---:|
| Completed / requested | 6 / 6 | 6 / 6 |
| Schema-valid rate | 100.0% | 100.0% |
| Allowed-window accuracy | 0 / 6 (0.0%) | 3 / 6 (50.0%) |
| Single-label exact accuracy | 0 / 2 (0.0%) | 1 / 2 (50.0%) |
| Median latency, completed only | 9.306 s | 9.9925 s |

Qwen predicted `corner_kick`, `goal`, `goal`, `shot_on_target`, `yellow_card`, and `penalty_kick`. The allowed-window matches were the corner, goal, and yellow-card cases. It returned a 0.90 or 0.95 self-score for every answer, including all three errors, and never abstained.

The exact source-video bytes and all 12 sampled frame timestamps, indices, ordinals, and decoded-frame SHA-256 values match the Gemma recovery inputs for every clip. The image representation is not held fixed: Gemma received twelve 1280×720 one-frame sheets, while Qwen received six 1280×360 two-frame sheets. The first Qwen smoke request with twelve images failed with HTTP 400 because the request occupied 11,629 prompt tokens against an 8,192-token context. The six-sheet fallback preserves the sampled frames but changes grouping and per-image geometry. Therefore the observed 3/6 versus 0/6 difference cannot be attributed solely to model identity. [Qwen summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-qwen35-comparison-v1-summary.json), [independent recomputation](../artifacts/soccernet-pilot-v1/qwen35-second-vlm-comparison-verification-v1.json)

Only after the Qwen visual summary was sealed did Gemma classify the aligned ASR text. The Qwen commentary run completed 6/6 with two label-equality `supports` relations and four `contradicts`. Both supports occurred on correct Qwen cases (`goal` and `yellow_card`), but the sample is too small and same-event dependence is too strong for this to validate visual correctness. [Qwen commentary summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-qwen35-comparison-commentary-v1-summary.json)

## What related work says about this design

### Dr. Tica Lin's work defines the downstream validity target

Archit specifically pointed to Dr. Tica Lin's sports research. The closest bridge is architectural, not a comparable benchmark result. [Sportify](https://arxiv.org/abs/2408.05123) detects basketball actions and tactics from structured player/ball data and then gives that context to a text-only LLM for narratives and embedded visualizations. [VIRD](https://arxiv.org/abs/2307.12539) turns real badminton match video into poses, trajectories, synchronized source video, and a match-to-rally-to-shot drill-down for expert analysis. [SportsBuddy](https://arxiv.org/abs/2502.08621) links tracking, timeline cues, in-video annotation, and captions in a deployed storytelling workflow.

Those systems do not establish raw-video VLM play-recognition performance. They expose the missing endpoint: a label becomes useful only when a chosen user can inspect the supporting moment and spatial relations and reconnect the claim to source video. That supports a three-layer PlayGround program: (1) validate visual perception, (2) ground explanations in externally scored evidence, and (3) present the result in an inspectable, correctable interface.

Lin and colleagues' 2026 soccer study [*Who's That Player?*](https://vcg.seas.harvard.edu/publications/who-s-that-player) makes the interface requirement unusually concrete. The authors identify referential, spatial, temporal, and metric query ambiguity. In their within-subject study (`N=16`), externalized interpretations were associated with higher inspectability on most measured dimensions, yet participants repaired only 38% of deliberately misaligned externalization trials. The direct implication is that PlayGround should expose its interpreted question, selected temporal scope, evidence, and uncertainty **and** provide low-cost correction controls; transparency alone is not an error-recovery mechanism. This is HCI/XR evidence, not perception evidence, and the authors acknowledge that their voice-only comparison does not isolate visual richness.

[The Ball is in Our Court](https://arxiv.org/abs/2211.07832) supplies the methodological bridge: sports data are spatial, highly temporal, user-specific, access-constrained, and best studied with domain experts around explicit tasks. Its simulated/Wizard-of-Oz examples isolate interface components; they must not be represented as recognition results. The genuine SoccerNet experiment here is complementary because it tests the actual perception layer before an expert-facing explanation workflow is built. A claim-level review and caveats are recorded in [the Dr. Lin research note](dr-tica-lin-and-soccer-vlm-research-2026-08-27.md).

### Evidence-grounded QA and tool-augmented soccer are already active research areas

[NExT-GQA](https://openaccess.thecvf.com/content/CVPR2024/html/Xiao_Can_I_Trust_Your_Answer_Visually_Grounded_Video_Question_Answering_CVPR_2024_paper.html) couples video-QA answers with manually checked temporal support, establishing a general-video precedent for joint answer/evidence evaluation. [SoccerAgent / SoccerBench](https://arxiv.org/abs/2505.03735) contributes around 10,000 multimodal multiple-choice pairs across 13 soccer tasks and an agent that decomposes questions and uses a soccer knowledge base and distributed toolbox. [SoccerNet game-state reconstruction](https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Somers_SoccerNet_Game_State_Reconstruction_End-to-End_Athlete_Tracking_and_Identification_on_CVPRW_2024_paper.html) supplies a potential pitch-relative state layer.

Therefore neither sports QA nor tool routing is claimed as new. The testable gap is narrower: compare a direct VLM with incrementally declared soccer-state tools on the same real clips, require answer-linked temporal/spatial evidence, and measure selective abstention. Any tracker or reconstruction model must remain an explicit ablation; it cannot become a hidden rule-based labeler.

### Commentary is powerful enough to be a confound

Chakraborty et al. use three prompted Llama 3.1 8B judges over sliding commentary windows and report action-spotting results without visual-frame processing. The system is few-shot prompted; no weight fine-tuning is reported. Its full-match mAP is not comparable to six-clip classification accuracy, but it shows why commentary cannot be treated casually as truth or given to the visual model before scoring. [ACL Anthology record and paper](https://aclanthology.org/2025.ijcnlp-srw.6/)

### Soccer-specific fine-tuning is a credible next stage, but it has not happened here

Jiang et al. adapt LLaVA-NeXT-Video through concept alignment, instruction tuning, and downstream LoRA fine-tuning on a curated 20k-clip mixture of SoccerNet and proprietary WyScout. Their preprocessing uses two-second clips represented by eight uniformly sampled frames. They report a 37.5% relative VQA improvement and action-classification accuracy rising from 11.8% to 63.5%. Those supervised, multi-dataset results are not comparable to this frozen-prompt pilot, but they make domain adaptation a concrete future experiment once sample size and rights permit it. [CVPRW 2025 paper](https://openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Jiang_Domain_Adaptation_of_VLM_for_Soccer_Video_Understanding_CVPRW_2025_paper.html)

### Accuracy without grounding is not enough

SoccerLens evaluates 13 soccer events with structured spatial and temporal cues. Its authors report that the tested soccer VLMs remain below 50% grounding even under the loosest cue definition and underuse temporal information. It is a recent, small preprint benchmark rather than a universal result, but it directly motivates this project's timestamp/evidence contract and the need to inspect whether a correct label was based on the play rather than a scoreboard, replay, or celebration. [SoccerLens preprint](https://arxiv.org/html/2605.09598)

## Model choice and next comparisons

| Model | Primary-source capability | Project status | Scientific use |
|---|---|---|---|
| Gemma 4 E4B | Open-weight local multimodal model; E4B supports image, video, and audio; Google's approximate E4B Q4_0 loading estimate is 4.5 GB and includes its stated 20% loading allowance, but excludes supporting software and context memory | Executed locally on the overlap pilot using ordered frames, not native video/audio | Current feasibility baseline |
| Qwen3.5-9B | Apache-2.0 local multimodal model; official card documents image-text use and an 8.8B-parameter dense architecture | Executed locally on the same 12 sampled frame records, grouped as six two-frame sheets | Post-hoc comparison; 3/6 allowed-window matches, not an independent test estimate |
| GLM-4.6V-Flash | Official repository describes the smaller Flash model as a local candidate and supports video/event understanding | Not a validated overlap result | Secondary local candidate after a hardware-fit probe |
| Domain-adapted LLaVA-NeXT-Video | Published soccer-specific LoRA curriculum and 20k instruction clips | Literature result only; no project weight training | Future supervised adaptation baseline |

Sources: [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4), [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B), [GLM-V official repository](https://github.com/zai-org/GLM-V), [CVPRW domain-adaptation paper](https://openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Jiang_Domain_Adaptation_of_VLM_for_Soccer_Video_Understanding_CVPRW_2025_paper.html).

Vendor model-card capability claims are selection evidence, not project performance evidence. A fair future comparison must declare the model and representation in advance, use new match groups, and hold clip hashes, sampled frames, visual-token budget, prompt/schema, requested-set denominator, and runtime attestation fixed or factor them explicitly.

## Limitations and robustness interpretation

- **One match per split.** Five development clips and six validation clips cannot estimate variation across leagues, camera operators, scoreboards, commentary languages, teams, or matches.
- **Point-label ambiguity.** Event-centered 10-second windows can include lead-up, aftermath, replay cuts, and multiple annotations. Allowed-window scoring is transparent but generous; strict single-label exact accuracy has only two eligible validation items.
- **No independent adjudication.** Labels are official SoccerNet points, but the particular windows were not double-annotated for what a human can see at the midpoint.
- **Sparse, low-resolution visual input.** Twelve still frames from 398×224 footage can miss the ball, contact, referee gestures, or line crossing. Upscaling the image canvas does not recover detail. The model family may support native video, but this interface evaluates ordered-frame reasoning.
- **No validated spatial grounding.** The schema records model-proposed coarse regions and an interval, but there are no human spatial boxes, pitch calibration, or grounding scores in this pilot. Do not claim tracking, player localization, or trajectory evidence.
- **No weight training.** Prompt/schema selection is not fine-tuning. The project has not demonstrated that learned soccer adaptation improves anything.
- **Serving and model errors are entangled in v1.** Requested-set scoring correctly penalizes both, but semantic ability should be analyzed only after the runtime is stable.
- **Commentary is neither independent truth nor temporally exact.** It can lag, anticipate, hallucinate, describe a replay, or agree with an incorrect visual prediction.
- **Recovery v2 is post hoc.** Reusing the same validation clips after seeing v1 cannot restore untouched-validation status.
- **Qwen is also post hoc and representation-confounded.** Qwen was chosen after Gemma results were known and received six two-frame sheets instead of twelve one-frame sheets. The comparison changes model and image grouping together.
- **No negative windows.** Every clip is centered on a selected annotated event, so this pilot cannot estimate false-positive rate, specificity, event prevalence, or full-match spotting performance.
- **Shortcut risk is untested.** Broadcast scoreboards, replay structure, score changes, camera style, teams, and celebrations remain in the pixels; pretraining contamination by recognizable broadcasts cannot be ruled out.
- **No redistribution.** Sourced clips are displayed only inside the local research presentation to authorized participants. That presentation use does not authorize a public standalone demo, and project media must remain private.

## Recommended next experiments

1. Preserve primary v1, Gemma recovery v2, and the Qwen comparison unchanged; label their different evidentiary roles instead of selecting the best run.
2. Freeze a new untouched, multi-match test before choosing another model, prompt, sampling density, or abstention policy. Group uncertainty by match, not clip.
3. Double-annotate the intended midpoint action, every action actually visible, replay/live status, cue interval, and evidence region; adjudicate disagreements.
4. Add background/no-action and hard-negative windows, including celebration-without-goal, goalmouth-without-goal, and overlay-masked pairs.
5. Pre-register a factorial model × representation × sampling-density experiment. Compare matched frames and official video processing within each model before ranking models.
6. Report the generated self-score as uncalibrated until a sufficiently large untouched set supports reliability, Brier/ECE, and coverage–risk analyses.
7. Score human temporal/spatial evidence separately from label accuracy. Keep event-window classification, full-match spotting, and open-ended QA as distinct tasks with distinct metrics.
8. Treat commentary as a separately scored modality: visual-only, commentary-only, and late fusion, with every branch frozen before comparison.
9. Only after the evaluation set is large and stable, test LoRA domain adaptation on development groups and preserve an untouched match-grouped test.

## Gated school-year program

### Fall 2026 — task and annotation validity

- Assemble a 50-clip feasibility set from at least ten match groups, with no more than five clips per match and at least 20% background, unanswerable, or semantically close hard-negative controls.
- Independently double-annotate intended answers, all visible actions, answerability, replay/live state, cue intervals, and cue regions; adjudicate disagreements.
- Freeze a genuinely untouched match-grouped test before another model, prompt, threshold, or adaptation choice.

**Gate:** stable taxonomy plus acceptable answerability/evidence agreement and a sealed test manifest.

### Winter 2027 — controlled VLM and modality study

- Fully cross model × image packaging × sampling density, holding clips, prompts, schemas, and denominators fixed.
- Add scoreboard masking, replay-logo perturbations, and semantically matched controls.
- Compare visual-only, commentary-only, and late-fusion branches, sealing each upstream output before comparison.
- Report requested-set reliability, strict answer correctness, joint answer/evidence correctness, match-grouped uncertainty, and selective coverage–risk.

**Gate:** reproducible estimates with explicit confounds and non-overlapping evidentiary roles.

### Spring 2027 — explicit tools and expert verification

- Compare direct VLM inference with declared game-state, trajectory, or retrieval augmentations inspired by SoccerNet-GSR and SoccerAgent.
- Choose one role—coach or analyst—and co-design the evidence display and correction controls.
- Measure verification time, correction rate, missed-error rate, and final decision correctness rather than preference alone.
- Consider domain adaptation only after the frozen evaluation protocol is stable.

**Gate:** experts verify or correct outputs faster without reducing correctness, and gains are attributable to declared components.

## Further questions for Archit

- Is the lab's intended target **action classification in event-centered clips**, **action spotting in full matches**, or **open-ended QA**? They require different sampling and metrics.
- Should the model identify the event at the exact SoccerNet timestamp or any salient event in the 10-second window?
- Which evidence is scientifically essential: timestamps, broadcast-image regions, calibrated pitch coordinates, player relations, or trajectories?
- Is a commentary-based consistency check useful to the lab, or should commentary become a separately scored baseline?
- What minimum match diversity and adjudication protocol would Archit consider sufficient for a workshop-quality feasibility study?

## Audit index

- [SoccerDB/SoccerNet overlap binding](../artifacts/soccernet-pilot-v1/soccerdb-overlap-binding-v1.json)
- [Frozen visual configuration v1](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-v1.json)
- [Frozen primary validation v1](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-frozen-v1-summary.json)
- [Primary commentary cross-check v1](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-primary-v1-summary.json)
- [Isolated development visual run](../artifacts/soccernet-pilot-v1/soccerdb-overlap-train-development-gemma-e4b-isolated-v3-summary.json)
- [Frozen visual configuration recovery v2](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-recovery-v2.json)
- [Isolated runtime receipt](../artifacts/soccernet-pilot-v1/isolated-vlm-runtime-receipt-v1.json)
- [Post-hoc visual recovery v2](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-gemma-e4b-isolated-recovery-v2-summary.json)
- [Non-strict commentary recovery-v2 failure record](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-isolated-recovery-v2-summary.json)
- [Canonical strict commentary recovery v3](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-commentary-isolated-strict-recovery-v3-summary.json)
- [Strict development commentary check v4](../artifacts/soccernet-pilot-v1/soccerdb-overlap-train-commentary-isolated-strict-v4-summary.json)
- [Qwen frozen comparison config](../artifacts/soccernet-pilot-v1/soccerdb-overlap-frozen-visual-config-qwen35-comparison-v1.json)
- [Qwen visual comparison summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-qwen35-comparison-v1-summary.json)
- [Qwen visual seal](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-qwen35-visual-seal-v1.json)
- [Independent second-model verification](../artifacts/soccernet-pilot-v1/qwen35-second-vlm-comparison-verification-v1.json)
- [Qwen commentary consistency summary](../artifacts/soccernet-pilot-v1/soccerdb-overlap-validation-qwen35-comparison-commentary-v1-summary.json)
- [Live-demo adversarial audit](live-demo-adversarial-audit-2026-08-27.md)
- [Commentary cross-check protocol](commentary-crosscheck-protocol.md)
