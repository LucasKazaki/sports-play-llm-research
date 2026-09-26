# PlayGround Paired Evidence-Corruption Protocol v1

**Status:** frozen dataset-independent protocol; execution on real clips remains blocked until an authorized immutable pilot manifest fixes source/match groups.  
**Purpose:** distinguish answer correctness from warrant validity and test whether confidence/abstention responds when answer-linked evidence is removed, swapped, or corrupted. This protocol does not make a causal claim from the existing synthetic fixture.

## 1. Prerequisites and preregistration boundary

Before inspecting model outcomes, freeze and hash:

1. the rights-approved pilot manifest, with `clip_id`, immutable media hash, source/match/group IDs, duration, split, and permitted-use record;
2. adjudicated `annotation-protocol-v1` references and aliases;
3. model/checkpoint or API version, decoding parameters, prompt, frame sampler, tool versions, and `playground-output-v1` parser;
4. condition generator version, seed, corruption magnitudes, validity bounds, and pairing table;
5. primary metrics, exclusions, clustering hierarchy, and bootstrap/permutation seeds.

No item may cross train/development/test boundaries through its source, match, near-duplicate play, or swapped evidence donor. A malformed output is scored fail-closed; it is not silently repaired.

## 2. Experimental units and pairing

- **Unit:** one question attached to one 5–10 second clip.
- **Pair:** the same unit under clean and exactly one corrupted condition.
- **Blocking:** question type, answerability, evidence modality required, and source/match group.
- **Donor selection for swaps:** deterministic seeded derangement within the same question/evidence-modality stratum, but from a different clip and, where the manifest permits, a different match. Donor answers are never exposed to the recipient.
- **Repeated questions per clip:** retained, with inference clustered at the highest shared source/match/clip level specified by the manifest.

The pairing table is generated once and hashed before model execution. Failed donor construction is reported as an unexecuted pair, never replaced after outcomes are seen.

## 3. Two non-interchangeable experiment families

### A. Submission counterfactual (scorer diagnostic)

Freeze each model's `answer`, `abstain`, and `confidence`; mutate only its submitted evidence fields. This asks whether external scoring catches unsupported warrants while answer accuracy is mechanically unchanged. It is an evaluator-sensitivity check, **not** evidence that the model used or ignored the evidence.

### B. Model/tool intervention (behavioral robustness)

Hold question, base video, prompt template, decoder settings, and random seed fixed; alter only the designated retrieved/tool evidence before rerunning the model. Answers and confidence are allowed to change and every transition is reported. Calling the intervention "answer-preserving" describes the intended semantic manipulation, not a post-hoc inclusion rule; pairs must not be filtered because the answer changed.

Direct video-only systems receive applicable temporal/frame interventions, not fabricated tool inputs. Oracle/noisy-tool comparisons use the same model and prompt surface, differing only in the supplied structured state.

## 4. Frozen corruption conditions

| ID | Condition | Mutation | Applicability | Required validity check |
|---|---|---|---|---|
| C0 | clean | unmodified evidence/input | all | frozen contract valid |
| C1 | complete evidence swap | rotate temporal span, pitch regions, and trajectory together using preregistered donor | submissions; retrieval/tool inputs | donor differs; schema valid; no split leakage |
| C2 | temporal removal | remove question-relevant temporal support while preserving clip duration/interface | frame/retrieval conditions | removed span overlaps adjudicated support; remaining frames logged |
| C3 | matched-count temporal swap | replace relevant frames with equal-count irrelevant frames from the same permissible clip window | frame conditions | frame count and timestamps logged; no target-support overlap |
| C4 | temporal reversal | reverse evidence order without changing the evidence set | order-sensitive questions | identical frame/time set; order hash differs |
| C5 | pitch/trajectory shift | apply preregistered normalized-coordinate displacement and clip to field bounds | structured-tool conditions | displacement, clipping rate, and out-of-support rate logged |
| C6 | missing tool channel | replace exactly one required tool channel with an explicit unavailable sentinel | tool conditions | no hidden fallback; missing channel named |
| C7 | oracle evidence | use adjudicated temporal and soccer-coordinate evidence | oracle upper-control | reference hash matches frozen annotations |

C2 and C3 must be reported separately: reducing frame count is not equivalent to removing question-relevant evidence. C3 is the preferred control for semantic evidence removal at fixed visual-input count. Corruption severity values are fixed from geometry/rubric considerations or a development split, never tuned on test outcomes.

## 5. Invariants and contamination guards

Each execution receipt must assert:

- unchanged unit/question IDs and pair cardinality;
- unchanged clean media hash for structured-tool interventions;
- exactly one intended condition delta per pair, except C1's explicitly bundled swap;
- stable model/prompt/decoder/tool versions;
- no donor from the recipient clip, forbidden split, or prohibited source group;
- normalized times and coordinates remain within contract bounds;
- answers/confidence are byte-identical only for family A, never forcibly copied for family B;
- all failures, truncations, retries, and API nondeterminism are retained and counted.

## 6. Outcomes and primary estimands

Report clean and paired-condition values for:

1. answer accuracy and abstention coverage;
2. temporal IoU, pitch-region F1, trajectory ADE/FDE, and joint-grounded accuracy;
3. answer risk-coverage/AURC and joint-grounded risk-coverage/AURC;
4. tie-safe C@1%, C@5%, and C@10% for both answer and joint-grounded risk;
5. calibration on answered items, with the frozen binning rule;
6. paired deltas in confidence, abstention, answer correctness, and joint-grounded correctness;
7. answer transition counts: correct→incorrect, incorrect→correct, answer→abstain, abstain→answer, and unchanged;
8. corruption validity/failure rates and clipping/missing-channel rates.

**Primary behavioral estimand:** paired change in joint-grounded error among all preregistered units under C3 or the applicable structured-tool corruption, alongside coverage.  
**Primary scorer diagnostic:** family-A change in joint-grounded accuracy with answer accuracy fixed by construction.  
A confidence drop without improved selective risk is not counted as successful abstention behavior.

## 7. Statistical analysis

- Preserve all preregistered pairs; use paired differences rather than independent condition averages.
- Resample at the highest independent source/match cluster fixed by the authorized manifest; nested clip/question sampling is used only if preregistered and supported by enough clusters.
- Report point estimates and deterministic 95% intervals with seed and replicate count.
- For binary paired endpoints, report discordant counts and an exact paired test when sample size permits; for continuous paired deltas, report the full empirical distribution and a cluster-aware randomization or bootstrap interval.
- Apply the frozen multiple-comparison rule to secondary conditions; do not promote a favorable secondary corruption to primary after observing results.
- If too few independent clusters make intervals uninformative, report that limitation rather than treating questions as independent.

The exact clustering hierarchy and minimum detectable effect remain intentionally unset until the authorized manifest establishes the number and nesting of sources/matches/clips.

## 8. Required artifacts per run

1. immutable manifest, annotation, model/prompt, and tool hashes;
2. condition-generation config, seed, pairing table, and donor audit;
3. raw model outputs and contract-validation errors for every pair;
4. per-item clean/corrupt scores and transition table;
5. aggregate metrics, paired intervals/tests, and failure accounting;
6. environment/package receipt and exact commands;
7. explicit labels separating prior-work reports, synthetic controls, pilot results, and confirmatory test results.

## 9. Stop/fail-closed rules

Stop before inference if authorization, hashes, split isolation, donor constraints, or grouping IDs are missing. Mark a condition invalid if its intended semantic effect cannot be verified. Do not replace invalid pairs using outcome knowledge. Any prompt/model/tool change after clean execution requires rerunning all paired conditions under a new protocol receipt.

## 10. Current executable scope

`python prototype/sports_play_lab.py evidence-perturbation-fixture --out artifacts/evidence-perturbation-fixture-v2` currently exercises only family A on synthetic records (C0, a bundled C1 swap, and a C5 x-shift). It emits aligned per-pair deltas, answer-transition counts, exact paired binary tests, and deterministic group-resampled percentile intervals. This verifies scorer and paired-analysis plumbing only; it does not execute family B, real video, model inference, causal reliance, empirical calibration, or adequately powered inference.
