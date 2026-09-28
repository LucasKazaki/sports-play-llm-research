# SoccerMaster long-form VLM/search scale experiment

**Status:** completed single-game held-out systems experiment; deployment and coach-utility **NO-GO**

## Answer first

The pipeline densely indexed both halves of one newly acquired, untouched authorized SoccerNet test game (1.500 h) with 90 contiguous 60-second windows at a 60-second stride, plus six locked 30/60/120-second stress windows. The selected local Gemma prompt produced 96/96 schema-valid test reports (100.0%); 0/96 reports abstained (0.0%).

This is a larger real-footage VLM/search experiment, not evidence that the prose is correct or useful to coaches. SoccerNet labels were opened only after every visual output and query result was hash-sealed. The post-hoc evaluator covers selected SoccerNet-v2 actions, not long balls, most passes, duels, pressing, player identity, or tactics.

## Frozen protocol

| Property | Frozen value |
|---|---:|
| New official SoccerNet test games | 1 |
| Complete halves | 2 |
| Dense visual test calls | 90 |
| Duration-stress test calls | 6 |
| Total test denominator | 96 |
| v2 structural-selection window/candidate pairs | 12 |
| v2 actual requests including recovery | 20 |
| v3 number-disabled delivery checks / requests | 6 / 6 |
| Final frozen development + test window denominator | 114 |
| Final frozen development + test actual requests | 122 |
| Preserved pre-amendment diagnostic requests | 3 |
| Minimum ordered frames | 8 |
| Selected prompt | `candidate_b_evidence_first_v3_number_disabled` |

Prompt selection used only schema validity, strict first-attempt success, attempts, and latency on a pre-existing validation game. It used no correctness labels and is prompt selection—not parameter fine-tuning. The selected evidence-first v2 prompt was conservatively adapted to a number-disabled v3 contract after low-resolution validation exposed unsupported numeral claims; v3 then passed 6/6 fresh structural delivery checks before test freeze.

## Leakage and privacy controls

- No audio, commentary, labels, filenames, scores, game identity, source metadata, or absolute match clock was deliberately supplied as nonvisual request data.
- The prompt prohibited player/team names and the v3 schema prohibited all jersey-number claims.
- The top 16% of every frame was blacked out before inference to remove the broadcast score/clock overlay.
- **Post-seal anonymization failure:** one of six predeclared checks contained a readable lower-third team-name graphic outside that top mask. The model report did not repeat the name, but the experiment is not fully identity-leakage-free and no leakage-free performance claim is allowed.
- Requests used only anonymous relative frame IDs and offsets.
- Raw media, redacted frames, raw responses, source names, labels, and the full search index remain under `data/private` and are not redistributable.
- A visual prediction seal binds the prompt, all requests/responses/reports, index, and frozen query results before annotations were parsed.

## Structural and latency results

- Valid reports: 96/96.
- Runtime failures: 0/96.
- Strict first-attempt successes: 96/96.
- VLM-authored events: 361 (unverified before annotation join).
- Median/mean/max per-window request time: 33.014 / 32.042 / 38.858 seconds.

## Post-seal SoccerNet evaluator

Mapped visible SoccerNet annotations: 166. Tolerance-based restricted annotation recall was 1.807% (3/166).
Restricted precision among VLM predictions whose types exist in the SoccerNet mapping was 5.556% (3/54).

These restricted numbers are not dense action-spotting mAP and do not score detailed prose. Matching a coarse event type near an annotation does not validate actor, outcome, trajectory, tactical interpretation, or coaching relevance.

## Search behavior and direct inspection

The frozen BM25 query suite returned at least one VLM-authored candidate for 20/20 queries. No human relevance set exists, so this measures only whether the reports are searchable.
A predeclared six-window first/middle/last visual audit judged 0/6 reports fully supported, 2/6 partially supported, and 4/6 unsupported. These six windows are illustrative rather than a factuality-rate estimate, but they independently demonstrate major event and continuity hallucinations despite 100% schema validity.

## Safe claims

- The system can reproducibly window and process a complete two-half SoccerNet game with a silent local VLM and build a searchable private index.
- Protocol, model inputs, recoveries, outputs, retrieval queries, and the post-seal annotation join are receipt-bound and resumable.
- The experiment directly measures schema reliability, latency, abstention, coarse annotation corroboration, and deterministic retrieval behavior on one game.

## Unsafe claims / no-go boundary

- Do not claim full-match event detection performance, generalization, player identification, detailed report factuality, tactical understanding, or coach utility.
- Do not claim that all identity-bearing pixels were removed; the direct audit found a lower-third team-name overlay outside the fixed mask.
- Do not call SoccerNet annotation matching an event detector; it is an evaluator applied after visual outputs were sealed.
- Do not expose or redistribute SoccerNet video, frames, labels, raw responses, or private source paths.

## Local demo integration

The shared loopback demo now prefers this verified 96-window package and labels the older SQLite soccer pilot as an explicit fallback. A standalone soccer adapter verifies the visual prediction seal, package-bound post-seal evaluator and spot-check receipts, the private index hash and denominator, both source-half hashes, and private media allowlists before serving results. It does not import FootballMaster, and the shared server remains outside both sport-engine boundaries.

The presentation UI exposes two separate verdicts: systems/provenance **GO** and soccer semantics/coach readiness **NO-GO**. It shows the 90-minute dense coverage, 96/96 structural delivery, restricted 3/166 annotation corroboration, restricted 3/54 prediction corroboration, 0/6 fully supported direct spot checks, and the sampled-frame anonymization failure. Each result is labeled as a VLM claim and opens an opaque half-relative timestamp in a private, silent H.264 MP4 review derivative. These derivatives were remuxed without re-encoding and contain zero audio streams; they remain under `data/private` and are not redistributable.

Browser QA used a clearly labeled deterministic literal-query mode so it could not interfere with concurrent model evaluation. Desktop and 390×844 mobile checks covered initial rendering, 12-result search, an honest zero-result offside query, soccer/football switching, 44-pixel mobile evidence controls, range-backed video readiness and time seeking, responsive overflow, labels/live regions, and the browser console. One separately authorized live query-model smoke used `google/gemma-4-e4b`: it translated “Find through balls into the attacking third” into `through_ball`, `cross`, and `shot_on_target` filters in 6.128 seconds and returned 12 playable candidates. This validates integration only—not the candidates’ event semantics.

## Next experiment

Freeze a multi-game dense test set, add independent atomic human annotations for actor/action/outcome/tactics, compare sparse frames against true video-token models, report SoccerNet action-spotting mAP where applicable, and measure retrieval precision with coach-authored queries and blinded relevance judgments.

## Reproducibility anchors

- Protocol receipt SHA-256: `ba2cc8daafa60de5c93bfca5c8f6c0fe4a263c7de7314a9f5dc6589ca41b6946`
- Frozen test config SHA-256: `aa4a9ee4b981a0dcaa6255e894a0d12175fab282a41405dfd1c90465563c3630`
- Visual prediction seal root: `5a8ffad71312528c01faad4f0f261de1421f1e13910fb79e0da846d594ba10e4`
- Annotation evaluation SHA-256: `0d03e1269ca43d980bf33ee15be396ca4665544afbe9a3c655644ea3035acda8`
