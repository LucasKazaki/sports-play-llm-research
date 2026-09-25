# PlayGround annotation and evaluation protocol v2

**Status:** pilot-ready draft; model- and dataset-agnostic.  
**Scope:** 5–10 second soccer-play QA items. This protocol does not authorize acquisition or redistribution of footage.

Version 2 retains v1's frozen item, double-annotation, evidence, adjudication, metric, split, and rights requirements. It adds a required `spatial_validity` record so missing or invalid game-state evidence cannot be silently treated as an empty citation.

## Spatial-validity contract

Every item records `spatial_evidence_usable`, camera visibility, calibration validity, ball-localization support, identity resolution, and controlled failure reasons from `annotation-rubric-v2.json`.

Fail closed: positive pitch regions or trajectory points require `spatial_evidence_usable=true`, `camera_visibility=in_view`, `calibration_validity=valid`, and no failure reason. Conversely, unusable spatial evidence requires at least one failure reason and forbids positive regions/trajectory. Explicit camera-out, insufficient-lines, airborne-ball-3D, and unresolved-identity states require their matching reason codes. Unknown states cannot support positive spatial citations.

For progression/trajectory questions, invalid spatial evidence is represented by an empty trajectory plus `trajectory_unavailable=true`; it is not trajectory-grounded. If the failure also makes the question visually unanswerable, select its matching unanswerable reason and retain the structured validity record.

## Required annotation fields and validation

Exports use `playground-annotations-v2` and are structurally specified by `playground-annotations-v2.schema.json`. The executable validator additionally binds each item to the frozen manifest and enforces ordering, duration, rubric membership, answerability, evidence, trajectory, and cross-field spatial-validity rules.

## Frame-review and metric-eligibility gate

A real-media pilot item also requires a `playground-frame-review-v1` worksheet bound to its annotation export and frozen manifest. The worksheet records nominal rational FPS, sequentially decoded frame count, decoded presentation timestamps (PTS), reviewed frame indices/timestamps/hashes, independent-review identity, selected half-open temporal boundary positions, calibration evidence, the six item-quality checks, and annotation/adjudication roles. Never infer PTS as `frame_index/fps`: variable-frame-rate media or dropped timestamps can make that mapping false.

`validate-frame-review` derives metric eligibility rather than trusting a declaration. Eligibility is true only when: (1) the reviewer is named and differs from the draft author; (2) tight half-open boundaries are confirmed and their timestamps exactly match the annotation's single temporal interval; (3) calibration is `valid` with a named method, reviewed supporting frames, at least four correspondences, finite non-negative mean/max reprojection errors, and a hash-bound evidence artifact; (4) all six quality checks pass; and (5) a second annotator and adjudicator are named. The start boundary names the first included decoded frame. The end boundary names the first excluded frame position, so it may equal the decoded-frame count when the last frame is included; the frame immediately before that boundary must be present in `reviewed_frames`. Both worksheet and frozen manifest must equal the derived result. Missing evidence therefore remains a valid pending worksheet but cannot be promoted to metrics.

Decoded-pixel hashes are audit aids tied to the decoding implementation, not replacements for the source-file SHA-256 or human visual review.

## Item-quality review addition

Before freezing an item, a reviewer who did not draft it must reject or revise it if: (1) the answer deviates from the approved clip or permitted source record; (2) the item is answerable from commonsense alone or is not specific to the play; (3) the item is unrelated to the video or lacks sufficient visual evidence; (4) it introduces an event absent from the clip; (5) the wording leaks the answer; or (6) the question/options are ambiguous, weakly grounded, ill-posed, or lack a unique supported answer. Record the review outcome without treating model-based filtering as human verification. Checks (1)–(4) and the ambiguous/non-visual/weakly-grounded review categories operationalize QA-generation failures documented by SportMV-Bench v1; answer-leakage control is retained separately and is not attributed to SportMV. These checks do not imply access to or reproduction of that benchmark.

## Evaluation addition

Report prevalence by validity/failure state. Score upstream camera/calibration/localization/identity validity separately from answer-linked grounding. Joint spatial/trajectory metrics apply only where gold spatial evidence is usable; failures are evaluated through answerability, failure-reason accuracy, false-citation rate, and selective risk. Oracle-coordinate, noisy-coordinate, and invalid-calibration conditions remain separate ablations.

## Claim boundary

This proposed contract is exercised only on deterministic synthetic fixtures in iteration 26. It reports no human reliability, model performance, reconstruction quality, or real-soccer result.