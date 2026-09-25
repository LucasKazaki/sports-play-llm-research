# SoccerMaster / PlayGround evaluation protocol v1

Internal proposed protocol, 13 September 2026. **SYSTEMS GO / SEMANTIC NO-GO.** No experiment is registered or executed by this document. The existing six-clip frozen scorer remains unchanged.

## Cohort and freeze

Use at least six rights-safe real clips, targeting 10–15, for Archit's stronger-video-model feasibility request. This small study is descriptive. Select a broader source-group sample and justify its precision using development-only information before a later effectiveness study. Do not call 40 windows or repeated generations 40 independent matches.

Assign the original match to one split. Both halves, overlapping windows, replays, edited highlights, alternative encodes and derived frames inherit that group. A human history audit must map prior prompts, retrieval indexes, labels and tuning exposure to those groups. Record team/season/competition overlap as a remaining generalization limit. Enrollment must contain genuine negative and unanswerable cases, multiple events and close distractors; neither sparse event annotations nor absence of a label proves a negative.

Freeze clip/source hashes, group map, inclusion/exclusion reasons, model IDs/revisions, exact input method and frame/media settings, prompt/schema, seed if supported, retries, time budget, ontology and point-to-interval policy. Freeze labels separately with two blinded independent annotators and an adjudicator before primary prediction access. Keep pre-adjudication judgments and disagreement; the second reviewer must not see the first review or model output. The current intake slots are empty.

The advisory CLI `prototype/evaluation_design_gate.py --manifest DESIGN.json --output NEW_CHECK.json` checks declared groups, duplicate bytes, development exposure and bound evidence documents. Its output is always scientifically unvalidated and unauthorizing. It does not inspect annotation contents or discover renamed/edited duplicate matches. Provider execution still uses its own rights/processor/spend gates.

## Annotation and failure record

One row per item: sample/group/source ID, question, answerability, accepted answer(s), event class and definition, time interval or point plus tolerance, visible evidence spans, calibrated pitch validity if relevant, supported/contradicted/insufficient claim judgments, annotator ID, blinded condition, confidence and reason. Preserve each raw annotation and the adjudicator's change/reason. Do not infer field coordinates from normalized image coordinates.

| Failure family | Observable record | Scoring boundary |
| --- | --- | --- |
| Enrollment / provenance | Missing rights/scope, bad hash, unknown group, prior exposure | Exclude before frozen enrollment with reason; never silently replace after seeing results |
| Provider / transport | Timeout, nonresponse, cleanup error, immutable attempt number | Keep every requested item and terminal failure |
| Schema / parsing | Invalid JSON, duplicate key, invalid time, unsupported fields | Requested-set failure; conditional parse rate separately |
| Event / temporal | Missed reference, unmatched prediction, duplicate, wrong interval/peak | Existing deterministic one-to-one scorer; review completeness before calling hallucination |
| Broadcast state | Replay-as-live, wrong replay origin, cutaway or missing live event | Independently annotated state and event time; unimplemented semantic endpoint |
| Grounding | Citation resolves but is irrelevant, contradicts claim, or lacks visible support | Human claim-level evidence judgment, distinct from file/link integrity |
| Identity / spatial | Wrong player, unreadable jersey, invalid calibration, occluded/off-screen entity | Abstain when required evidence unavailable; no tactical inference from absent visibility |
| Query / retrieval | Added event, dropped constraint, wrong order, irrelevant hit, missed relevant clip | Frozen relevance/constraint judgments; schema acceptance is insufficient |
| Selectivity | Wrong confident answer, unjustified abstention, answer during insufficient evidence | Joint correctness and coverage with independently labeled answerability |
| Coach workflow | Incorrect result accepted, task not completed, excessive review time | Separate human study after discovery and authorization |

## Endpoints and denominators

Report enrolled, attempted, complete, parseable and label-eligible counts, plus every exclusion, terminal error and abstention. Existing event precision is matches/predictions and recall is matches/references within eligible labels; list missing-label items separately. Requested-set exact recovery includes provider failures. Present n/N for each endpoint.

For the future semantic study, primary end-to-end joint success requires a correct answer AND valid supporting evidence on an independently answerable item. Failed requests count as unsuccessful. For unanswerable items, score correct abstention separately. Coverage is nonabstaining eligible outputs/eligible requests; selective error is incorrect answered outputs/answered outputs, undefined when none answer. Plot risk with coverage only after adjudicated labels exist. Freeze any calibration method/threshold on validation groups; model-written confidence alone is not a calibrated probability.

Retrieval: predeclare K=1,5,10, relevance grades 0/1/2 and a fixed candidate collection. Recall@K uses all known relevant items as denominator; nDCG uses the predeclared gain rule and ideal ranking. Report undefined/no-relevant queries and appropriate abstention separately. Judge a fixed complete small corpus where feasible; if using pooled judgments, disclose unjudged items and pool bias. Merge duplicate spans under a frozen event/group rule before evaluation. Do not add an embedding label to BM25.

## Controlled experiments and decisions

| Experiment | Frozen comparison | Endpoint and decision |
| --- | --- | --- |
| Stronger VLM feasibility | Same enrolled clips, prompt/schema and declared input budget; preserve provider-specific sampling differences | Report raw clip outcomes, timing and failures. No model ranking if representation/budget differences remain confounded |
| Official encoder feasibility | One permitted development clip, exact source/head/ontology, inference-only raw output | Require actual finite logits/embedding output, measured memory and provenance before any same-clip comparison |
| WP4 live/replay oracle gate | Fixed reporter/model and inputs; direct reporting versus independently annotated oracle state gate | Gate macro F1 requires predictions for a learned gate, so it is NOT a meaningful oracle score. For oracle intervention compare replay-as-live errors, live-event recovery, unsupported-event rate, coverage and full latency. Learn a gate only if a prespecified useful improvement survives coverage/cost checks |
| WP5 hybrid retrieval | BM25, real semantic vectors, and verified SoccerMaster evidence/reranking; same candidates and questions | Compare Recall@K/nDCG and correct evidence verification. Keep development-selected weights fixed. Abandon extra components if benefit does not justify measured costs |
| Grounding ablation | Same question/clip with relevant evidence removed, shuffled, contradicted or replaced by close distractor | Freeze expected abstention/correctness with blinded humans; same-clip question changes test whether evidence actually follows the question |
| Coach validation | Existing manual workflow versus prototype with equivalent task training and footage access | Randomized/counterbalanced order; independent outcome assessor; primary correct task completion and time, plus incorrect acceptance and error cost |

Freeze a numeric smallest worthwhile effect, risk ceiling, minimum coverage and cost/time ceiling with the study owner before test access. These values are intentionally undecided, not zero or implicit approval. The analysis plan must resolve them before a confirmatory run. Paired differences and uncertainty should cluster by original match (and by coach for repeated tasks); with few groups show cases and dispersion without unsupported population inference. Prespecify tolerance sensitivity separately from the immutable primary scorer; do not pick the best tolerance after seeing the test.

## Coach discovery and stopping

Use the five categories/interactions and discovery questions in [coach packet v3](coach-discovery-master-v3-2026-09-13.md). Discovery selects the task and error budget; it is not effectiveness evidence. Before recruitment, record owner, institutional review determination where applicable, participant information/consent, retention and access plan, permitted footage, compensation decision and stopping rule. No contact is authorized here.

Study record: participant pseudonym; role/experience; consent record; task/query IDs; condition and randomized order; start/end; correct completion; accepted incorrect claim; verification actions; uncertainty behavior; workload/comments; assessor; adjudication; withdrawal/exclusion reason. Keep identifiers and footage private. Stop a session for invalid provenance, unavailable footage or an undisclosed semantic warning. Scope remains soccer-first discovery unless separately evidenced football/multisport workflows justify expansion.

## Design-contract clarification after independent review

In the design manifest, source_sha256 identifies the exact model-input clip file bytes, after the declared extraction procedure; group_id identifies the original match and all its derivatives. Repeated input bytes in the test split fail, even under different clip/group IDs. Distinct encodes of the same moment still require the human derivative audit. Six clips can come from one test match only for descriptive feasibility, never six independent observations. Development/validation rows are optional in this feasibility checker; the future controlled study must supply the separately frozen development/validation design. One reviewed evidence packet may serve multiple roles if it explicitly addresses each role; hash equality alone proves neither adequacy nor independent authorship.
