# PlayGround selective-prediction protocol v1

**Frozen:** 2026-08-06  
**Scope:** primary evaluation protocol for answer and evidence-aware abstention on 5–10 second soccer-play QA. This protocol fixes endpoints; it does not report real-data performance.

## Primary prediction contract

Each item emits one payload containing the answer or explicit abstention, one confidence in `[0,1]`, discovered temporal evidence, any required pitch-region/trajectory evidence, and provenance. The primary track supplies no oracle support timestamps or coordinates. Oracle-time and oracle-coordinate variants are diagnostic ablations only.

A system may abstain explicitly. For threshold sweeps, all non-explicitly-abstained items with confidence at least the threshold are covered. Equal-confidence items enter or leave together; dataset order must never break a tie.

## Two separately reported correctness targets

1. **Answer correctness** (`A_i`): the frozen answer scorer marks the response correct.
2. **Joint-grounded correctness** (`J_i`): `A_i=1` and every gold-required evidence channel passes its frozen threshold. Required temporal evidence uses the registered overlap rule; required pitch regions use set F1; required trajectories use normalized ADE. Missing required evidence fails. Items with unusable gold spatial evidence are evaluated through answerability/failure-reason and false-citation outcomes, not silently counted as trajectory-grounded.

Neither target substitutes for the other. Answer-only selective results cannot support a grounded-reliability claim.

## Frozen selective endpoints

At a threshold, coverage is the covered-item count divided by all evaluation items. Selective risk is the mean `1-correctness` among covered items and is undefined when none are covered.

For each of `A_i` and `J_i`, report:

- the complete tie-grouped risk–coverage curve, including the zero-coverage origin;
- maximum attainable non-abstained coverage;
- `C@1%`, `C@5%`, and `C@10%`: maximum **attained** coverage at an observed selective risk no greater than the target;
- AURC as the right-step integral of risk over attained coverage, normalized by attained maximum coverage; report maximum coverage alongside AURC so a low AURC cannot hide universal abstention;
- overall correctness, operational coverage, and operational selective risk at the preregistered deployment threshold.

The pre-eligible-data interface operating point is confidence `>= 0.5` for non-explicitly-abstained predictions. It is fixed for pipeline validation, not presented as optimized, calibrated, or deployment-ready. The exact machine-readable thresholds, bins, grouping, seed, and eligibility rules are frozen in `evaluation-preregistration-v1.json`.

Do not interpolate between unattained thresholds or split a confidence tie. All-abstained resamples contribute zero to C@risk but are excluded from AURC/risk intervals as undefined; valid-replicate counts must be reported.

## Uncertainty and leakage unit

Use a 95% percentile bootstrap over the preregistered independent sampling unit, preferably `match_id`; retain every clip/question belonging to a sampled group. The immutable pilot manifest must declare the grouping field before model evaluation. Report group count, replicate count, seed, interval limits, and valid-replicate count. Item-wise bootstrap intervals are not acceptable when multiple items share a match/source.

## Calibration and evidence sensitivity

Report calibration separately from selective risk (ECE plus a reliability diagram for both correctness targets). ECE is descriptive and is not a guarantee of epistemic sensitivity. The controlled evidence-degradation precedent shows confidence may remain stable when frames are removed.

Primary intervention analysis is paired on the same frozen items: clean versus answer-preserving evidence swap, noisy tool output, invalid calibration, and evidence removal. Report answer-correctness and joint-grounded-correctness deltas with grouped intervals. A method supports the PlayGround hypothesis only if it improves joint-grounded selective performance without masking failures through collapsed coverage, and if its confidence/abstention reacts appropriately to evidence invalidity.

## Primary precedents and novelty boundary

- Whitehead et al., *Reliable Visual Question Answering: Abstain Rather Than Answer Incorrectly*, ECCV 2022 / arXiv:2204.13631v3: selective VQA, learned selection, C@risk, risk–coverage AUC, and Effective Reliability are prior art. https://arxiv.org/abs/2204.13631v3
- Ortiz, *Explicit Abstention Knobs for Predictable Reliability in Video Question Answering*, arXiv:2601.00138v2: confidence-thresholded VideoQA risk–coverage and controlled frame reduction are prior art. https://arxiv.org/abs/2601.00138v2

PlayGround must not claim abstention, selective multimodal QA, C@risk/AURC, or frame-reduction diagnostics as novel. The remaining testable hypothesis is evidence-aware selective prediction on a single, non-oracle answer-linked soccer payload with externally scored time/pitch/trajectory evidence and controlled evidence/tool interventions.

## Executable status

The current scorer implements tie grouping, answer and joint-grounded curves, C@1/5/10%, attained-coverage AURC, explicit maximum coverage, the fixed operational point, grouped percentile intervals, and separate answered-item ECE/reliability-diagram records for answer and joint-grounded correctness. This protocol is verified only against deterministic synthetic fixtures; real-data calibration, utility, and threshold optimality remain unmeasured.
