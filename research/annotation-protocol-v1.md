# PlayGround annotation and evaluation protocol v1

**Status:** pilot-ready draft; model- and dataset-agnostic.  
**Scope:** 5–10 second soccer-play QA items. This protocol does not authorize acquisition or redistribution of footage.

## 1. Annotation unit and frozen inputs

One item is `(clip_id, clip SHA-256, exact clip bounds, question_id, question text)`. Before annotation, freeze the clip bytes, frame rate/time base, and question wording. Annotators may scrub frame-by-frame but must not see model outputs, captions generated from the answer, or split membership.

Each primary pilot item receives two independent annotations. An adjudicator sees both only after they are locked. Keep original annotations and adjudication; never overwrite disagreement. Exploratory items outside the frozen primary set may be single-annotated, but they cannot enter confirmatory reliability or model-comparison endpoints.

## 2. Required labels

1. **Answerability:** `answerable`, `insufficient_visual_evidence`, or `invalid_question`.
2. **Canonical answer:** non-empty only for answerable items. Use a closed label where the question type permits it; otherwise preserve a normalized free-text answer plus accepted aliases.
3. **Minimum temporal evidence:** one or more half-open intervals `[start_s, end_s)` sufficient to justify the answer. Annotators should mark the smallest sufficient span, not the whole clip by default.
4. **Spatial evidence:** zero or more controlled pitch regions from the rubric JSON. Empty spatial evidence is allowed only when the question is genuinely non-spatial and the adjudicator records that rationale.
5. **Trajectory evidence:** optional ordered points `(timestamp_s, x_norm, y_norm)` in broadcast-image coordinates. It is required for progression/trajectory question types unless the evidence cannot be localized reliably; that case must be marked `trajectory_unavailable` and cannot count as trajectory-grounded correctness.
6. **Evidence entities:** optional stable roles such as `ball`, `possessor`, `receiver`, `defender`, or `goalkeeper`; do not infer identity when it is not visible.
7. **Rationale note:** one sentence stating why the cited evidence is sufficient. This is annotation-audit metadata, not a model target.

For unanswerable/invalid items, canonical answer, intervals, regions, and trajectories must be empty. Record one reason code from the machine-readable rubric.

## 3. Independent annotation and adjudication

- Randomize item order and hide the paired annotator's work.
- Double-annotate all frozen primary items in the 50-clip pilot, including every unanswerable control and every new question type. The earlier 20% minimum applies only to an interface dry run that is explicitly excluded from confirmatory reliability and model-comparison endpoints.
- Adjudicate answerability disagreement, answer mismatch, temporal IoU below 0.5, region-set F1 below 0.5, or any required-trajectory availability disagreement.
- The adjudicator selects or creates a gold label and records `adjudication_reason`; both pre-adjudication labels remain immutable.
- Report pre-adjudication agreement separately: answerability Cohen's kappa, exact/alias answer agreement, temporal IoU distribution, region F1 distribution, and trajectory-availability agreement. Do not present adjudicated agreement as inter-annotator reliability.

## 4. Fail-closed validation rules

The pilot export is rejected if any rule fails:

- IDs are unique and clip hashes are 64 lowercase hexadecimal characters.
- Clip duration is positive; every interval and point lies within `[0, duration_s]`; interval end is greater than start.
- Temporal intervals are ordered and non-overlapping.
- Normalized coordinates are finite and in `[0,1]`; trajectory timestamps strictly increase.
- Pitch regions and reason codes belong to `annotation-rubric-v1.json`.
- Answerable items have an answer and at least one temporal interval; progression/trajectory items have a trajectory or an explicit unavailable marker.
- Unanswerable/invalid items contain no positive answer/evidence and include a reason code.
- The clip/question IDs and clip hash used for evaluation exactly match the frozen manifest.

## 5. Primary metrics

Metrics are computed per question type and macro-averaged across types; bootstrap confidence intervals resample clips (not individual questions) to preserve within-clip dependence.

- **Answer score (`A`)**: exact/alias accuracy for closed answers; a preregistered semantic rubric is required before scoring open answers.
- **Temporal evidence score (`T`)**: maximum IoU between any predicted interval and any gold sufficient interval. Also report thresholded hit rates at 0.3, 0.5, and 0.7.
- **Region evidence score (`R`)**: set F1 over controlled pitch regions. Mark non-spatial items separately rather than awarding an empty/empty 1.0.
- **Trajectory score (`D`)**: resample predicted and gold trajectories at shared timestamps over their overlap, then report normalized average displacement error and final displacement error. No temporal overlap or a missing required trajectory is a miss, not zero error.
- **Joint grounded correctness (`J`)**: item-level indicator `A=1 AND T>=0.5 AND (R>=0.5 when spatial evidence is required) AND (trajectory ADE<=tau when trajectory evidence is required)`. Freeze `tau` from annotation disagreement on the pilot before model comparison; do not tune it on test predictions.
- **Abstention correctness**: binary correctness on answerability controls, with unanswerable recall and answerable false-abstention rate.
- **Calibration:** Brier score for joint correctness and reliability plots; ECE is secondary and must state binning.
- **Selective prediction:** risk (1 − joint accuracy among answered items) versus coverage, plus AURC. Count malformed outputs as abstentions for coverage and as contract failures in a separate rate; do not silently repair semantic content.

## 6. Robustness and leakage controls

- Group splits by source match/broadcast; near-duplicate clips from one play cannot cross splits.
- Record whether commentary, scoreboard text, ASR, or metadata exposes the answer. Report baselines with each channel disabled where applicable.
- Include at least 20% controls across visually insufficient, evidence-swap, temporal-shift, and question/clip mismatch cases.
- Evaluate direct VLM, retrieval-augmented, and tool-augmented systems against the identical frozen manifest and output contract.
- Evidence corruption/noisy-tool tests are reported separately from clean-test accuracy.

## 7. Pilot acceptance gate

The protocol advances beyond 50 clips only if: (a) zero fail-closed export errors; (b) all flagged disagreements adjudicated; (c) answerability kappa and evidence-disagreement distributions are reported; (d) trajectory threshold `tau`, semantic-answer rubric, prompts, model versions, and split grouping are frozen; and (e) footage rights and publication constraints are documented by the lab.

## Claim boundary

This document defines a proposed annotation/evaluation protocol. It reports no human-agreement value, model result, SoccerNet result, or coach-utility result. Those require authorized data and direct experiments.
