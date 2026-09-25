# Coach discovery master v2 — 13 September 2026

Internal, unpromoted candidate for independent review. No coach interview, coach validation, sharing, or promotion is claimed. This packet consolidates existing local evidence; its creation is not a new model run or live demo rehearsal.

## 1. What can be shown honestly

**SYSTEMS GO / SEMANTIC NO-GO.** The system can search sealed model reports and open their local source spans. A search hit is an untrusted report, not a verified play, player identity, tactical judgment, or coaching recommendation. Hashes identify and protect files; they are not semantic embeddings. Commentary is post-hoc auxiliary evidence, not ground truth. Model confidence is not a calibrated probability.

The historical SoccerMaster-named long-form package is a local VLM report/index experiment. Its name does not establish execution of the official SoccerMaster encoder/checkpoint. Its 96 windows are 90 dense windows covering two complete 45-minute halves plus six stress windows; 96/96 schema-valid outputs prove formatting and execution only. The direct six-window audit recorded 0 supported, 2 partially supported, and 4 unsupported reports. The sampled anonymization audit found readable team-name pixels outside the scoreboard mask. Preserve these limits when explaining the demo.

Evidence: [report metrics](C:/AI/projects/SportsPlayLLMResearch/artifacts/soccermaster-longform-v1/report-metrics.json), [direct frame audit](C:/AI/projects/SportsPlayLLMResearch/artifacts/soccermaster-longform-v1/spot-check-adjudication.json), [technical report](C:/AI/projects/SportsPlayLLMResearch/research/soccermaster-longform-technical-report-2026-08-27.md).

## 2. Five clip-category hypotheses

These are exactly five discovery hypotheses from the existing next-steps brief, not a validated taxonomy or a claim that the current model detects them. Ask coaches to rank their usefulness using real tasks and their own examples.

| Category hypothesis | Concrete moments to discuss | Evidence needed before a system could assert it |
| --- | --- | --- |
| 1. Goal-mouth sequences | Saves, rebounds, second balls, cutbacks, follow-up shots | Visible ball and goal interaction with ordered before/after frames; direct goal-line evidence for a goal; human review of outcome |
| 2. Set pieces | Corner, free-kick or penalty setup, delivery, first contact, outcome | Restart context and ball location; continuous or sufficiently dense evidence linking setup to delivery and outcome |
| 3. Transitions | Turnovers, counterattacks, counter-presses, recovery runs | Possession change and subsequent player/ball movement; explicit uncertainty when possession or off-screen players cannot be resolved |
| 4. Possession progression | Overloads, switches, line breaks, final-third entries, exits under pressure | Pitch calibration, verified tracks and trajectories, visibility of relevant defenders; operational coach definitions for a line break and pressure |
| 5. Defensive shape | Compactness, press triggers, off-ball runs, tracking failures, breakdowns | Enough camera coverage for all relevant players, stable tracks, field coordinates, and coach-reviewed definitions; head-up decisions cannot be inferred from low-detail footage |

Source: [category and interaction brief](C:/AI/projects/SportsPlayLLMResearch/research/archit-coach-ready-next-steps-2026-09-03.md). No verified player-tracking, gaze, pitch-trajectory retrieval, or tactical-quality result is supplied by this packet.

## 3. Five interaction modes and honest status

| Mode | Sample query or action | Implemented versus design status |
| --- | --- | --- |
| 1. Natural-language search | “Show shots on goal.” Discovery extension: “Show every left-side cutback that led to a shot.” | Implemented text search over saved reports with deterministic ranking and optional local query-language translation. The exact shots query has a historical literal-mode receipt. The cutback/causal constraint is a discovery example, not a verified exhaustive or sequence-aware search. |
| 2. Structured filters | “Corners in the final third after 60 minutes for our team.” | Partial internal query-plan fields exist for event, phase, area and participant terms; the current UI is text search with a displayed plan, not a complete filter menu. Team, score-state, time and event constraints are not established as enforceable filters in the sealed long-form path. Full filter interaction remains design. |
| 3. Query by example | Select a coach-approved clip: “Find sequences like this one.” | Design only. No demonstrated clip embedding or similarity retrieval. SHA-256 file hashes cannot provide this function. |
| 4. Sketch/touch query | Draw a left-wing run and cutback on a tablet: “Find this path.” | Design only. Requires verified pitch coordinates, trajectories, camera calibration and a matching contract; none is demonstrated here. |
| 5. Conversational refine/compare | “Keep only the second-half examples; compare these two; show the evidence and mark this claim wrong.” | Manual new text searches and evidence playback are implemented. Persistent conversation, guaranteed exclusions, side-by-side semantic comparison, and a validated correction workflow remain design. Unsupported recognized “without [action]” requests fail explicitly; this is a bounded lexical safeguard, not full constraint understanding. |

Implementation evidence: [current UI](C:/AI/projects/SportsPlayLLMResearch/prototype/search_demo_ui/index.html), [sport-specific server](C:/AI/projects/SportsPlayLLMResearch/prototype/multisport_search_demo_server.py), [sealed soccer adapter](C:/AI/projects/SportsPlayLLMResearch/prototype/soccer_longform_adapter.py), [bounded query safeguards](C:/AI/projects/SportsPlayLLMResearch/prototype/query_capabilities.py), [saved shots query](C:/AI/projects/SportsPlayLLMResearch/artifacts/demo-readiness-2026-09-06-v1/search-1.json). Internal schema fields and successful query translation do not prove semantic retrieval correctness.

## 4. Workflow discovery questions and record sheet

The Maryland film walkthrough remains a future input. Do not describe Maryland's tools, staffing, tagging practices or priorities as known. No contact is authorized by this packet.

Use a 45-minute proposed interview: 5 minutes for role and decisions, 15 for a walkthrough of one recent film task, 10 for five to twelve actual queries, 10 for errors/verification, and 5 for scope and ownership.

| Topic | Questions to ask | Observable record to retain after authorized discovery |
| --- | --- | --- |
| Current task | Who prepares clips, who reviews them, and what decision follows? Walk through a recent request from start to finish. | Owner role, steps, existing tool names supplied by the participant, observed baseline time, deliverable and decision |
| Real queries | What five to twelve questions recur? Which of the five categories saves the most effort? Show one useful example and one confusing near-match. | Verbatim queries, ranked categories, examples and ambiguity notes; no invented coach quotations |
| Camera and rights | What views exist and what is off-screen? Who can approve local processing, retention, human annotation and any third-party processing? | Named approval owner, explicit scope/retention limits, approval receipt reference; unknown remains unknown |
| Error cost | Which false hit, missed hit or wrong identity is unacceptable? When should the system say it cannot tell? | Error classes, coach-specified maximum tolerance and examples requiring abstention |
| Verification | How much time can a reviewer spend per result? What visible evidence makes a result usable? | Agreed time budget, evidence requirement and manual comparison task |
| Scope and next step | Is one soccer workflow enough? Is there a concrete football need? Who would own each evaluation and correction? | Sport choice, separate owners/rights, agreed read-only shadow task or decision to defer |

After discovery, freeze the coach-authored queries, acceptance thresholds, human reviewers and group-disjoint evaluation plan before running a new scored test. Capture corrections as human judgments with provenance. The project still needs independent human annotation and adjudication; this document supplies neither.

## 5. Observable sport-scope decision rubric

This is a proposed decision rule for the interview and subsequent shadow study, not a decision coaches have made. “Football” means American football. A split demo means two separately labeled examples; multisport means an ongoing shared product scope.

First apply mandatory gates to every sport: a named workflow owner, explicit rights for the proposed processing, an observable task and reviewer, and a frozen evaluation/verification budget. If any gate is unknown, keep that sport at internal systems discovery only. If both sports fail, defer coach deployment rather than infer readiness.

| Candidate scope | Evidence that would support choosing it | Evidence that should stop or narrow it |
| --- | --- | --- |
| Soccer only | A soccer owner supplies recurring high-priority queries and rights-safe examples; a bounded soccer workflow has a measurable manual baseline and an agreed review budget. | Missing owner or rights; essential off-ball/identity evidence is not visible; no independently reviewed evaluation set |
| Football only | A football owner supplies the same concrete records and soccer has no ready task; separate football ontology and evaluation are accepted. | Mistaking the current 36 sparse held-out reports for whole-game coverage or relying on their event claims without labels |
| Split demo | Both owners want a short comparison of two separately labeled search/playback examples and understand that this tests interface fit only. | Pressure to pool scores, transfer soccer labels to football, or imply that the switch proves cross-sport semantic generalization |
| Multisport program | Both single-sport shadow tasks first meet their separately frozen error, abstention and review-time thresholds; there are owners and rights per sport; repeated shared workflow needs justify common UI work. | Either sport fails its own threshold, loses provenance/isolation, or has no capacity for ongoing review |

Decision record template: date; participating owner(s); chosen scope or deferred; supplied query IDs; rights receipt(s); baseline task/time; frozen acceptance thresholds; reviewer/adjudicator; observed result and denominator; unresolved issues; next review date. Thresholds are deliberately unfilled until an authorized owner sets them. Current recommendation for internal discussion: use soccer as the main systems example and football only as a separately labeled optional interface example. No sport is approved for autonomous coaching decisions.

Football evidence boundary: [demo verification](C:/AI/projects/SportsPlayLLMResearch/artifacts/footballmaster/longform-v2-demo/demo-verification-receipt.json) records 36 sparse held-out reports, 1,440 unique sampled seconds, and semantic NO-GO. It does not establish full-game indexing, event accuracy or coach utility.

## 6. Evidence-linked five-minute demo script

This is a timed plan grounded in historical receipts, not a claim that a fresh five-minute rehearsal occurred on September 13. Keep the demo private and local. Existing private-media rights do not authorize external sharing, new acquisition or upload.

For a future authorized local rehearsal, use [the existing launcher](C:/AI/projects/SportsPlayLLMResearch/scripts/start-coach-search-ui.ps1) with explicit literal mode when a query-model lane has not been reserved. Run [the readiness checker](C:/AI/projects/SportsPlayLLMResearch/prototype/demo_readiness.py) through the project-native executor into a fresh receipt directory. Inspect the actual session mode; a model listing is not a successful inference. Do not claim live readiness from the historical receipt.

| Time | Show and say | Exact evidence or fallback |
| --- | --- | --- |
| 0:00–0:40 | Show the system/semantic banner and the source window context. Say: “This searches saved reports and lets us check footage. The event descriptions can be wrong.” | [Historical readiness receipt](C:/AI/projects/SportsPlayLLMResearch/artifacts/demo-readiness-2026-09-06-v1/receipt.json): 23 passed checks, literal mode, zero visual-model calls. Use receipts if the live server is unavailable. |
| 0:40–1:25 | Enter “Show shots on goal.” Show the query-plan trace and literal-mode label. Say: “The words rank saved text; a match does not prove a shot.” | [Exact saved query/result](C:/AI/projects/SportsPlayLLMResearch/artifacts/demo-readiness-2026-09-06-v1/search-1.json): first result smw-d87c5fd11593378a4c, half 1, 1800–1860 seconds. Do not promise the present order before a fresh check. |
| 1:25–2:15 | Select Play evidence; point out the time binding and a report claim. Explain that the seal binds the report to the source. | [Historical browser observation](C:/AI/projects/SportsPlayLLMResearch/artifacts/demo-readiness-2026-09-06-v1/browser-observation.json): 12 results, selected 30:00–31:00, readyState 4, no decoder error. This observation explicitly is not a server-owned receipt or human event adjudication. |
| 2:15–3:20 | Open the direct audit. Use window smw-bc6e9ec80d42a2703d as the failure example: a replay graphic was described as a dribble; a referee frame as a shot; a free-kick delivery as a save. Say: “The evidence can contradict a fluent report.” | [Audit rows and limitations](C:/AI/projects/SportsPlayLLMResearch/artifacts/soccermaster-longform-v1/spot-check-adjudication.json). These are historical recorded observations, not newly performed visual review. Do not silently relabel the report. |
| 3:20–4:15 | Show the five category hypotheses and interaction menu above. Ask participants in the planned interview to choose one real task and define acceptable evidence/error cost. | Sections 2–4. Sketch and example search are design concepts. Optional football screenshot: [separate sport example](C:/AI/projects/SportsPlayLLMResearch/artifacts/footballmaster/longform-v2-demo/ui-search-results-1365x768.png), under its sparse-coverage/NO-GO boundary. |
| 4:15–5:00 | Close with the sport-scope rubric and exact next decision: a bounded, rights-approved, read-only workflow study with human review. State “SYSTEMS GO / SEMANTIC NO-GO” again. | Section 5. No request to rely on automated tactical advice, no new media transfer, no spending or publication commitment. |

Stop the live path if a seal fails, source playback is unavailable, mode differs from what is shown, or a semantic warning disappears. Use the named receipts to explain what was previously observed, and record a new rehearsal failure rather than pretend the current session passed.

Review handoff: independent Luna review must inspect this exact version, its source hashes, implementation/status distinctions and historical receipt scopes; resolve material defects in a new version; Terra must then inspect the version and verdict before any exact promotion edit. This packet remains unpromoted. Rights, credentials, spend, external contact/sharing, publication, commit/push and human-annotation gates remain in force.

### Source existence and SHA-256 receipt

Generated by the native candidate-creation command on 2026-09-13. These hashes bind the source files read for this packet; historical receipt dates remain unchanged. No media or checkpoint was downloaded, and no model or browser was called.

| Source path (relative to project) | SHA-256 |
| --- | --- |
| artifacts/demo-readiness-2026-09-06-v1/browser-observation.json | 4b8216854cffc396cea807fe8a4c3417d8a42f55293c059a732a575deb244521 |
| artifacts/demo-readiness-2026-09-06-v1/receipt.json | d8de671b02349696393f71c2cabb428109d4d3d9258ecdd356c10c18625e3770 |
| artifacts/demo-readiness-2026-09-06-v1/search-1.json | 0da3baee37f39fe4a566a85598060c84eb85a62fd4431ea38df27bb20a84f0c5 |
| artifacts/footballmaster/longform-v2-demo/demo-verification-receipt.json | 028cf4c957bbff302aee9c5401a675f3b923a63318078d57cf1d2408124e017d |
| artifacts/footballmaster/longform-v2-demo/ui-search-results-1365x768.png | 4fed18e2a08304850aecad179c2dc57747e8755201da0af0997ad0a92687f247 |
| artifacts/soccermaster-longform-v1/report-metrics.json | a29d230a343c81cad15df8df26a5d27df45bd14bf32a992344ec29dab9ab2dbc |
| artifacts/soccermaster-longform-v1/spot-check-adjudication.json | 620711e22f1ff403c4e543320e1b1f6d271294eac43343a2d717cff4071b4526 |
| prototype/demo_readiness.py | 664affa15d073e2cb2051980f7eff046c9699e56f23c6dd4e57909859218a6d1 |
| prototype/multisport_search_demo_server.py | 59c9e7ec47201172a4593d01d50663912e3abf9c2deacc67f9b29389839fef44 |
| prototype/query_capabilities.py | 58552319fa89acbb1e7eb10ab535290f64838ff2adcf90e46e9bfef16333db96 |
| prototype/search_demo_ui/index.html | 409e183ecd99cb2111a0a2a67bdd15f2a618006daeb45410b50439569155f528 |
| prototype/soccer_longform_adapter.py | f13e55cc578ef9c36102c5cf7efa4663e9b268545fa345c25912c52620b8a6b2 |
| research/archit-coach-ready-next-steps-2026-09-03.md | 268e2aa77ac72c6de97bcedf0f4f917a409d950d4f17a9e6ef321e823c144b26 |
| research/soccermaster-longform-technical-report-2026-08-27.md | 7e573a6c73f27ce6618f029f437658aadf3a5c5a745651b35bf18c23a15f64b8 |
| scripts/start-coach-search-ui.ps1 | 6dd3f72d006d7b906b2ece5bf7170b57ec9f715f152326317c89ea46eed86bdc |

## September 13 systems rehearsal supplement

This v2 preserves the v1 historical source table as creation-time evidence and adds fresh internal systems observations. The [literal rehearsal](../../artifacts/master-package-20260913/demo-v1/demo/receipt.json) and [local query-model rehearsal](../../artifacts/master-package-20260913/model-demo-v1/receipt.json) each passed 23 checks. Both finite servers shut down. No browser decoding observation was repeated on September 13; media byte ranges and timestamp bindings were checked.

The query model completed two text/ontology calls, but its [shot-query plan](../../artifacts/master-package-20260913/model-demo-v1/search-1.json) added stoppage, transition and offside, while its [cross-query plan](../../artifacts/master-package-20260913/model-demo-v1/search-2.json) added ball recovery and other unrelated types. A schema-valid plan and passing systems check are not faithful interpretation. Query latency is not measured by the current long-form wrappers (their field is hard-coded zero). Keep the literal-mode presentation available and inspect each returned claim against footage. This supplement is not coach validation or promotion.
