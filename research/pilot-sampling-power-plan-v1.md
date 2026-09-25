# PlayGround 50-clip pilot sampling and sensitivity plan v1

**Prepared:** 2026-08-06  
**Status:** metadata-only design; no footage selected or acquired.  
**Purpose:** turn the rights packet into a reviewable candidate-manifest and a feasibility-oriented 50-clip sampling design. This is not a claim that 50 clips provide confirmatory model-comparison power.

## 1. Gate and population

The eligible population is only 5–10 second soccer clips covered by one written rights record that permits the intended processing. Populate `pilot-manifest-template-v1.json` with metadata only, review it, and satisfy every gate in `rights-and-source-decision-packet.md` before copying, downloading, extracting, hashing, annotating, uploading, or running a model on footage.

Every screened candidate receives a stable non-semantic ID and an eligibility or exclusion record. The team must not screen with model outputs or silently replace difficult clips. `sha256_after_acquisition`, custody fields, and annotation status remain null/not-started in the metadata-only phase.

## 2. Sampling contract

Use 50 clips only as a maximum, not a quota that overrides rights or quality.

1. Target at least **10 independent matches**, no more than **5 clips per match**, and as many distinct source/broadcast groups as rights permit. If fewer than 10 match groups are available, label all uncertainty descriptive/feasibility-only.
2. Keep source, match, and near-duplicate `play_group_id` units wholly within one split. Assign groups before annotation or model evaluation.
3. After rights/privacy eligibility, sample for phase-of-play, viewpoint, occlusion, and difficulty diversity. Do not claim population representativeness from convenience footage.
4. Assign one primary QA item per clip for the initial reliability analysis. Provisional question-type targets sum to 50: progression/trajectory 10; each of restart, temporal order, player role, causal evidence, and counterfactual control 8. If a type is infeasible, record the shortfall rather than relabeling a clip post hoc.
5. Include at least **10/50 intentionally unanswerable or invalid primary controls** (20%), stratified across question types where meaningful. Freeze control identities before model runs.
6. Double-annotate **all 50 primary items** independently, then adjudicate flagged disagreement while preserving both originals. Extra exploratory questions may be single-annotated but cannot enter confirmatory reliability or model-comparison endpoints.

## 3. Estimands and analysis unit

The pilot's primary outputs are feasibility rates, pre-adjudication agreement distributions, exclusion reasons, annotation time, model contract-failure rates, and paired clean/corrupt effect estimates with match-grouped uncertainty. Questions are not independent when they share a clip or match. Resample the highest available independent source/match unit; never treat 50 clips as 50 independent observations when match clustering exists.

Do not use a significance threshold as the pilot acceptance gate. Advance decisions should consider rights completion, zero fail-closed export errors, annotation feasibility, agreement distributions, effect direction/uncertainty, and whether the observed number of independent groups supports a preregistered larger study.

## 4. Precomputed sensitivity, not achieved power

The following values are deterministic design calculations, not observed results.

### Proportion precision

For 50 independent Bernoulli items, the normal-approximation worst-case 95% margin of error is **13.9 percentage points**. With five clips per match and an assumed intraclass correlation (ICC), the design-effect sensitivity is:

| Assumed ICC | Design effect `1 + (5-1)ICC` | Approx. effective n | Worst-case 95% margin |
|---:|---:|---:|---:|
| 0.0 | 1.0 | 50.0 | 13.9 pp |
| 0.1 | 1.4 | 35.7 | 16.4 pp |
| 0.3 | 2.2 | 22.7 | 20.6 pp |

If zero of 50 independent items exhibit a failure, the exact one-sided 95% upper bound is **5.8%** (`1 - 0.05^(1/50)`); clustering makes that optimistic.

### Paired clean/corrupt comparison

An exact two-sided McNemar calculation with 50 independent pairs has only the following illustrative power under three preregistered-style discordance scenarios:

| `P(clean correct, corrupt wrong)` | `P(clean wrong, corrupt correct)` | Net paired difference | Exact power at alpha .05 |
|---:|---:|---:|---:|
| 0.15 | 0.05 | 0.10 | 24.1% |
| 0.20 | 0.05 | 0.15 | 47.8% |
| 0.25 | 0.05 | 0.20 | 69.9% |

These calculations assume independent pairs and therefore overstate sensitivity when clips cluster by match. Even under a large 20-point net effect, 50 independent pairs do not reach 80% power in the displayed scenario. The 50-clip run is consequently a feasibility/effect-estimation pilot, not a definitive hypothesis test.

## 5. Freeze-after-pilot decisions

Before a larger model comparison, use the locked pilot—not test predictions—to freeze:

- the actual source/match/play grouping hierarchy and split assignment;
- eligible question taxonomy and any infeasible strata;
- trajectory tolerance `tau` from pre-adjudication displacement disagreement;
- semantic-answer aliases/rubric and abstention-control mix;
- primary effect size and variance/discordance assumptions for a cluster-aware sample-size calculation;
- model prompts, tool versions, corruption severities, and stopping/exclusion rules.

## 6. Stop rules and claim boundary

Stop acquisition/annotation if rights scope changes, privacy review fails, clip boundaries violate approval, a group crosses splits, candidate replacements are model-informed, or the manifest cannot preserve immutable originals. A populated metadata manifest is not an acquisition authorization. This plan contains no real clips, annotations, agreement values, model outputs, or soccer performance results.
