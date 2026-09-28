# Paper Outline

## 2026-09-22 internal software-control evidence

The development claim experiment in research/chess-factuality-experiment-2026-09-22.md is a bounded software/provenance control using8 real boards and deliberately mutated claims. It is not a model benchmark, human explanation-quality result or sports-transfer evidence. The reference-only comparison is intentionally weak; no independent statistical-sample claim is justified. Preserve all broader evaluation gates.

## September 17 chess explanation foundation (internal companion track)

Chess is being added as a fully observable, controlled companion testbed for
the explanation contract—not as evidence for the PlayGround paper's soccer or
football claims. The companion asks whether a local generator can tie a move
explanation to legal board transitions, structured engine evidence, named
concepts, alternatives, confidence, and abstention. It is documented in
`chess-concept-model-delivery-plan-2026-09-17.md` and its selected research and
rights receipt.

Any later methodological appendix may compare three blinded explanation sources:
raw engine/PV, labelled deterministic template, and the concept-guided model.
It must report legal-board fidelity, claim-reference validity, factual and
concept correctness, causal/teaching usefulness, calibration/selective risk,
and non-template diversity. FIDE-level language is prohibited before the
separate game-disjoint evaluation with two independent named FIDE-rated
reviewers and adjudication. This companion's success cannot establish sports
understanding; it can at most validate an architecture for later sport-specific,
rights-cleared, evidence-linked evaluation.

## Working title
**PlayGround: Evidence-Grounded and Selective Question Answering for Short Soccer Plays**

## Current research design — 2026-09-07 UTC

September 8 execution note: the runtime now supports the full local development/test/model cycle and has completed eight actual local query-planner calls. Its eight invented selection cases expose constraint failures and are engineering diagnostics only. Keep them out of empirical soccer result tables. [The retained experiment](../artifacts/project-capability-20260908/local-model-experiment-findings.md) prioritizes action eligibility, typed constraints and query-supported filters before new inference or learning. Native tool access and a passing test suite do not establish scientific novelty or frontier reasoning parity.

The latest internal market/technical extension is [model-improvement-loop-2026-09-07.md](model-improvement-loop-2026-09-07.md), informed by [college sports discovery](college-sports-market-research-2026-09-07.md). Existing video capture, tagging, synchronized analysis and play search constrain product and novelty claims. A proposed doctoral contribution must externally score question-linked temporal/pitch evidence, faithful abstention and utility under incomplete observations against strong equal-budget baselines. Treat export/camera constraints as measured experimental conditions. Market discovery and the new 398-test software validation are not novel scientific results. Keep the separate football pilot's tiny test and ontology out of soccer comparisons.

The exact reviewed governance and proposed evaluation contract is indexed by [project-loop-info.md](project-loop-info.md). It is a plan for research, not evidence of novelty or successful soccer understanding. Existing frozen protocols and historical results below remain unchanged.

The next paper should test distinct questions: whether valid temporal/pitch evidence improves joint answer-and-evidence correctness; whether abstention reduces risk at useful coverage; whether predictions depend on the relevant visual cues; and whether coaches verify correct evidence faster. Use equal-budget direct, tool-assisted, temporal/field ablation and repeat-inference comparisons. Null/repeated events, close distractors, calibration validity and human-labeled corruption answerability are required controls, not optional favorable examples.

Before untouched test access, freeze outcome eligibility, accepted-answer/evidence scoring, full failure taxonomy and denominators, numeric effect/coverage criteria, budget ceilings and clustered uncertainty. Group halves, overlaps, replays and encodes by original match; use development-only power/precision work for test sizing. Require independent blinded human annotation and adjudication. Coach time comparisons need masked conditions, randomized/counterbalanced order and equal training. Report disagreement, failures, exclusion counts and compute costs alongside results.

The new terminal-outcome validator has synthetic accounting tests and separate annotation/prediction hash bindings. Those tests are infrastructure evidence and must not enter a soccer accuracy table. Current primary-source snapshots inform an expanded internal agenda, which has not received a full model review; broader novelty review and real held-out evaluation remain open.

## Iteration 58 dual-sport extension — FootballMaster-Pilot

The current presentation adds an American-football feasibility branch without changing the soccer paper's scientific claims. It should be described as a trained, source-held-out binary visual probe and evidence/search scaffold—not as a SoccerMaster reproduction or football VLM. Nine openly licensed clips from eight source groups exercise rights audit, whole-source splitting, frozen frame descriptors, train-only PCA, a learned `is_touchdown` head, immutable packaging, deterministic retrieval, per-field provenance, and playable source evidence. The three-clip test (2/3 correct; Wilson 95% accuracy interval 0.208–0.939) is a systems result and failure-analysis case only.

For a future dual-sport paper, keep three layers separable: sport-specific perception, language/query/report generation, and human verification. Soccer and football may share the retrieval and provenance interface, but not their evidence contracts: soccer is continuous and phase/pitch oriented; football is play-bounded and situation/personnel/formation oriented. The next publishable unit requires coach-authored questions, source/game-held-out adjudicated data, semantically close negatives, explicit abstention, and a controlled comparison of direct VLM, sport-specific representation augmentation, and frozen-probe baselines. Canonical evidence: `research/footballmaster-dual-sport-technical-report-2026-08-27.md`.

## 1. Motivation
Direct video-VLM answers may be plausible without exposing the moments or field evidence that support them. Short soccer plays provide a constrained setting for testing answer faithfulness, temporal/spatial attribution, confidence, and abstention.

## 2. Related work
### 2.1 Soccer video understanding
- SoccerNet-v2: untrimmed broadcast corpus with action spotting, camera-shot segmentation, and replay grounding.
- SoccerNet-Caption: timestamp-localized soccer captioning, but not QA or verified spatial evidence.
- SoccerNet-MVFoul/VARS: multi-view foul-property classification with displayed confidence, but not answer-linked evidence or verified calibration/abstention.
- SoccerAgent/SoccerBench: broad text/image/video soccer multiple-choice QA and 18 specialist tools; treat answer accuracy and internal image-plane boxes as predecessors, not externally scored pitch/trajectory evidence or selective prediction. Preserve the paper/README 13-vs-14-task discrepancy and repository-license caveat.
- SoccerNet-GSR: direct precedent for reconstructing visible-athlete identity and per-frame 2D pitch position on a centered 105 × 68 m field. Treat it as candidate upstream tool/oracle infrastructure, not QA or answer-linked grounding; retain invalid-calibration and airborne-ball limitations as explicit validity/abstention conditions.
- TrajSV: direct precedent for deriving player/ball field-coordinate trajectories from broadcast video and using their representations for retrieval, action spotting, and temporally localized sports captioning. Treat trajectories as internal model inputs—not answer-linked evidence outputs—and retain the absence of verified QA, calibration, abstention, and official code as boundaries.
- SoccerLens: direct precedent for soccer event-class attribution grounding with per-frame image-plane cue boxes, Energy/Pointing/S-IoU, and cue-frame T-IoU. It closes generic soccer attribution-grounding novelty but not QA-linked pitch trajectories, calibration, or abstention. Preserve the paper-vs-repository lineage/cue-semantic/license discrepancies and the 502 no-ROI sentinel reconciliation.
- *Grounding Video Reasoning in Physical Signals*: direct precedent for a single scored `a_what`/`a_when`/`a_where` VideoQA output, normalized image-plane box trajectories, temporal/spatial IoU, and shuffled/ablated/frame-masked diagnostics. It closes generic structured box-trajectory grounding and perturbation novelty, but not sports-field coordinates, calibration, or abstention; retain its automatically generated annotation caveat.
- SVI-Bench: direct precedent for five-choice Action QA on 10-second basketball/hockey/soccer clips and corpus-scale tool-assisted sports reasoning. Its T2 evaluates answer accuracy without answer-linked temporal/spatial evidence; T5 separately reports calibration error; T7 evaluates image-plane trajectory-conditioned video generation rather than QA grounding. Retain the gated-data/code-license boundary.
- X-VARS / SoccerNet-XFoul: near-neighbor for soccer refereeing video-QA with semantic answers, detailed explanations, and multiple answers per action. The inspected paper evaluates explanation-derived foul/severity predictions, but does not establish a separately submitted answer-linked pitch-coordinate/trajectory payload with external field scoring; preserve the bounded single-paper result class `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- TreeSoc: near-neighbor for soccer VQA, tool-routed intermediate evidence, visual grounding/temporal localization, and SoccerBench answer accuracy. The inspected paper describes pitch geometry and player boxes as internal/tool-derived context, but does not establish a separately submitted answer-linked pitch-coordinate/trajectory payload with external field scoring; preserve the bounded single-paper result class `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- SoccerChat: near-neighbor for short soccer-video question-answering, referee decision making, event classification, and response generation. The inspected paper does not establish a separately submitted answer-linked soccer-field coordinate/region/trajectory payload with external field scoring; preserve the independently QA-verified bounded single-paper result class `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR` and do not cite rejected QA v1 as accepted evidence.
- To verify next: benchmarks that output and externally score answer-conditioned **sports-field** coordinates or trajectories.

### 2.2 Grounded video QA
- NExT-GQA directly precedes PlayGround on answer-linked temporal localization: models answer and identify relevant video moments.
- TVQA+ directly precedes generic spatio-temporally grounded VideoQA: question/correct-answer concepts are linked to sampled image-plane boxes, and Answer-Span Accuracy jointly requires answer correctness and temporal IoU >= 0.5.
- Remaining survey: answer-conditioned coordinate/trajectory outputs, evidence sufficiency, selective prediction, and abstention in sports QA.
- Novelty guardrail: do not claim short sports Action QA, corpus-scale tool-assisted sports reasoning, temporal grounding, generic spatio-temporal answer grounding, broad soccer QA/tool routing, pitch-coordinate reconstruction, trajectory-informed sports captioning, structured what/when/where boxes, box trajectories, or visual perturbation diagnostics alone are new; test the combined answer-linked soccer-field-coordinate, calibrated, selective evidence contract.

## 3. PlayGround task
Input: a 5–10 second soccer clip plus a fine-grained question.

Required output:
1. answer or abstention;
2. supporting timestamp/frame interval;
3. pitch-region, object trajectory, or player relation evidence;
4. confidence and insufficiency reason.

## 4. Benchmark construction
- Rights-cleared clip manifest.
- Current feasibility asset: one hash-bound CC BY 2.0 Wikimedia clip for interface testing only; excluded from benchmark-scale claims until independent groups and annotation governance exist.
- Annotation protocol and adjudication.
- Question families and hard negatives.
- Leakage-resistant splits.

## 5. Systems
- Direct video-VLM baseline.
- Tool-augmented VLM with frame retrieval and spatial/trajectory tools.
- Ablations for temporal-only, spatial-only, and abstention components.

## 6. Evaluation
- Answer correctness.
- Temporal evidence overlap/pointing accuracy.
- Spatial evidence accuracy.
- Joint answer-and-evidence faithfulness.
- Calibration, coverage, and selective risk.
- Separate reliability diagrams and ECE for answer correctness and joint-grounded correctness, excluding explicit abstentions from probability calibration.
- Frozen pre-eligible-data protocol: temporal IoU and pitch-region F1 thresholds `0.5`, normalized trajectory ADE threshold `0.1`, five equal-width calibration bins, fixed interface confidence threshold `0.5`, and 1,000-replicate `match_id`-grouped percentile bootstrap (`research/evaluation-preregistration-v1.json`). These are preregistered pipeline choices, not empirically validated operating characteristics.

## 7. Experiments and limitations
Explicitly separate synthetic harness checks, openly licensed real-video results, and restricted-data experiments (if ever approved). Discuss broadcast cuts, replay ambiguity, camera calibration error, annotation uncertainty, and data rights.

- SoccerRAG: retrieval/database natural-query soccer QA near-neighbor; retrieved text, database outputs, and timestamps are not separately submitted answer-linked soccer-field coordinates/trajectories or externally scored field evidence.

- SoccerMaster / Soccer Factory, MatchTime, and UniSoccer / SoccerReplay-1988: QA-accepted selected citation neighbors for soccer understanding, field-state infrastructure, commentary/temporal alignment, and replay-adjacent context; none establishes the required separate answer-linked soccer-field payload with external scoring. Preserve `BOUNDED_NEGATIVE_WITH_CITATION_NEIGHBORS`.

## Iteration 56 outline update — excluded exploratory evidence

- Related work: E-VQA / ST-Evidence closes generic dense answer-plus-temporal-plus-tracked-evidence claims; SportsTime / CoTR closes sports QA with stepwise temporal evidence; TimeLens2 supplies multi-interval question-form temporal grounding; GroundFormer motivates same-clip PIoU and GT-Pred-correlation-style question-discrimination tests.
- Systems: the OpenAI-compatible adapter has one hash-bound, loopback-only structured-output smoke on the open-license pilot.
- Evaluation: add same-clip, multiple-question evidence-discrimination and causal evidence-corruption tests alongside joint answer/evidence and selective-risk metrics.
- Results boundary: the 2026-08-21 smoke is excluded from reported model results because the sole clip and source-assisted draft are unadjudicated and metric-ineligible. It supports only interface feasibility and a documented failure taxonomy.

## Iteration 57 outline update — excluded exploratory evidence

- Related work: Soccer-GMR precedes null-set/single-/multi-moment soccer retrieval; GOAL and SoccerNet-Echoes precede commentary-conditioned retrieval; NA-VMR precedes explicit negative-query rejection; MVMR precedes multiple-distractor hard-negative retrieval; MCAD establishes soccer commentary as retrieved generation context, not a scored commentary-to-visual alignment benchmark. Coaching-document and tactical-geometry sources contribute components but not the full source-video-cited document-QA contract.
- Evaluation design: add in-domain/out-of-domain null queries, semantically close distractor clips, and commentary-span versus visual-moment agreement as separate checks.
- Excluded results: the corrupted-evidence and same-clip hard-negative/null-query outputs are unadjudicated structural observations and must not enter accuracy, grounding, calibration, latency, robustness, abstention, or tool-benefit tables.
- Methodology provenance: the legacy soccer-project fixtures are preserved as a synthetic annotation/prompt-design reference only; they contribute no empirical result.


## 6 September 2026 — operational demo recovery

The real soccer demo now has an executable rehearsal and a versioned candidate backed by exact paths and SHA-256 bindings. Literal-mode rehearsal passed 23 checks, including both private source halves and valid result time bindings; browser playback was observed at readyState 4 without a decoder error. This is systems evidence only. See `research/loop-recovery-handoff-2026-09-06.md` and `artifacts/demo-readiness-2026-09-06-v1/candidate-evidence-index.json`. Independent Luna review and subsequent Terra promotion remain required; no shareable candidate was promoted.

## September 13 master implementation and audit handoff

Internal candidate: research/candidates/soccermaster-master-implementation-v1-2026-09-13.md. Exact source/native log identities: artifacts/master-package-20260913/master-evidence-index.json and native-evidence-verified.json. Full native validation: 891 tests, six required scripts successful, preview-only reset, 20 named pilot files unchanged. Fresh finite literal and local query-model demos each passed 23 systems checks; query expansion remains semantically unreliable and latency reporting is unmeasured. Official preflight is BLOCKED with 15 exact reasons, no inference/downloads. Six generated color-screen clips exercise frozen label hashing, raw/resume/seals and descriptive scoring; no actual Gemini or official-checkpoint result is claimed.

Next: independent audit and substantiated repairs; then exact Luna/Terra promotion sequence for shareable material. Acquire nothing and contact nobody without existing gates. Actual clip enrollment, rights/processor/spend evidence, compatible official assets/dependencies, adoption of a frozen point-label policy, match isolation, independent annotation/adjudication and coach workflow remain open. Company Runtime recovered retained native execution following coordinator maintenance; invalid autonomous planner envelopes and source-path matching remain distinct unresolved evidence. No scheduler, job replay, commit/push, public sharing, cloud video call or trained-weight improvement occurred.


## September 13 independent audit completion

Internal engineering audit: [completion report](C:/AI/projects/SportsPlayLLMResearch/reports/soccermaster-audit-and-completion-report-2026-09-13.md). Current source/evidence identities: artifacts/soccermaster-audit-20260913/audit-evidence-index.json. Six demonstrated query-timing failures are repaired; 35 focused tests and 897 full tests pass. All six required scripts and 23 finite literal-demo checks pass; reset remains preview-only and the 20 frozen pilot files are unchanged. All 323 handed-off artifact entries matched before edits. The original master/coach candidates and their historical latency statements remain unchanged; this audit supplement identifies the current code.

The six-clip result remains synthetic fixture arithmetic; independent rescoring matches exactly and preserves all 73 source files. Actual Gemini clip enrollment, official model execution (15 preflight blockers), independent semantic annotation/calibration and coach validation remain open. Query expansion still adds unrelated events. SYSTEMS GO / SEMANTIC NO-GO; no performance or trained-weight gain and no promotion. Existing Studio source already contains the recovery-path normalization fix; native execution success does not establish autonomous planner recovery. No audit runtime restart, job replay or new scheduler occurred. Next: exact candidate plus audit-delta review through Luna, then Terra inspection before any promotion; protected external actions retain their gates.


## September 13 publication-readiness packet

The current internal packet is [the publication-readiness report](C:/AI/projects/SportsPlayLLMResearch/reports/soccermaster-archit-publication-readiness-2026-09-13.md) and research/candidates/archit-soccermaster-briefing-v1-2026-09-13.md. Paths in this operational entry are project-relative. The 18-row matrix reconciles every standing requirement. Methods/report materials, replay-gate/hybrid-retrieval designs, coach v3 and executable gated runbook are prepared; no full manuscript promotion.

New evaluation_design_gate.py rejects declared cross-split groups, duplicate exact test-input bytes, development exposure and missing/tampered evidence bindings. Two actual failures preceded the duplicate-byte repair; 17 focused and 915 full tests passed, six required scripts passed, finite literal demo passed, 20 frozen pilot files unchanged and reset preview-only. The earlier 156 focused/913 full verification remains historical. All 88 audit-index entries matched; six master-index differences were evolving operational notes (317/323 matched). Exact current evidence is artifacts/soccermaster-publication-20260913/evidence-index-v1.json.

Bounded Luna reasoning review requested then accepted the duplicate-byte correction; it is not full source/manuscript review. Full Luna then Terra promotion remain pending. Real Gemini enrollment/inference, official checkpoint/dependencies/callable/ontology/transport (15 blockers), independent annotation/calibration, coach workflow/utility and protected release remain open. SYSTEMS GO / SEMANTIC NO-GO. No model calls, downloads, credentials, spending, external publication, contact, restart or replay added.

Runtime observation preserves goal-d71b7571e8c51d0eeddb09366df2b02563e4a61e7188b28b and event 235eddf1-2434-436a-8aec-fba11ab8408f waiting on local inference lane lmstudio:cpu-goal-workers:loops-cpu-qwen3.5-9b-text. Native success does not establish autonomous recovery. Architecture owner should inspect the existing lane/event without replacement. Next research decision: actual rights-safe stronger-model feasibility, official-model one-clip feasibility, then authorized coach discovery.


## September 15 engineering boundary
The bounded query safeguards, independent 1,029-test verification, actual Luna-v3 then Terra-v2 acceptance and direct v2 browser observations are internal software evidence only; see state/supervisor-final-milestone-2026-09-15.md. The accepted review covers the supplied participant delta, not a full-source or manuscript audit. This work adds no learned-weight, recognition-accuracy, cohort, annotation, coach-utility or publication-readiness result. Existing scientific methods and promotion requirements remain open.

