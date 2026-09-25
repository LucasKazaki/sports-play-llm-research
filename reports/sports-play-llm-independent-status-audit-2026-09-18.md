# Independent status audit — Sports Play LLM Research

**Observed:** 2026-09-18, local read-first audit  
**Scope:** durable project files, current Company Runtime receipts, local listeners and read-only loopback health. No source code, data, dependency, service, scheduler, or external state was changed.

## Runtime and active work

- Company Runtime is listening locally at `127.0.0.1:4174` (PID 16132 at observation). Its current durable project jobs are under [`.agent-runtime/jobs/`](../.agent-runtime/jobs/).
- The Chess Concept preview is the only observed project preview listener: `127.0.0.1:8782` (PID 25372). `GET /health` returned `{"status":"ok","scope":"loopback-only"}`; `GET /api/review` returned an intentional abstention, not a chess explanation.
- No listener was observed on the shared searchable-demo port 8771. This means the SoccerMaster/FootballMaster interface is **not currently running**, not that it is unavailable or failed. No new listener was started.
- The preview's fixed local packet currently fails closed with `legal_board_not_verified`, `unverified_source_rights`, and `engine_candidate_comparison_required`. That is the correct current behavior.

## What is complete versus active

| Lane | Durable completed evidence | Current status and boundary |
| --- | --- | --- |
| SoccerMaster | [Long-form technical report](../research/soccermaster-longform-technical-report-2026-08-27.md) and [package receipt](../artifacts/soccermaster-longform-v1/package-receipt.json): 96/96 structurally valid reports; restricted corroboration 3/166 annotations and 3/54 mapped predictions; direct audit 0/6 fully supported. | **SYSTEMS GO / SEMANTIC NO-GO.** The old package is locally reviewable, but it does not establish factual reports, tactics, coach utility, or deployment readiness. The later [publication-readiness report](soccermaster-archit-publication-readiness-2026-09-13.md) remains internal and unpromoted; no real Gemini study or official model import is evidenced. |
| FootballMaster | [Long-form v2 report](../research/footballmaster-longform-v2-technical-report-2026-08-28.md) and its cited `artifacts/footballmaster/longform-v2/verification-receipt.json`: 35/36 valid JSON reports on held-out windows, but 36/36 abstentions, 27/36 abstention/event contradictions, and 126 unsupported scoring assignments. | **Infrastructure/retrieval review path only; semantic NO-GO.** No human-adjudicated event truth, accuracy, calibration, or coach-usefulness evidence exists. |
| Searchable demo | [Prototype README](../prototype/README.md), [SoccerMaster report](../research/soccermaster-longform-technical-report-2026-08-27.md), and [FootballMaster report](../research/footballmaster-longform-v2-technical-report-2026-08-28.md) identify sealed searchable packages and a loopback-only shared adapter. | Sealed artifacts and launch paths exist, but no 8771 listener was observed. Search proves retrieval over saved VLM text, not correctness or relevance. |
| Chess Concept extension | [State](../state/loop-state.json), [plan](../research/chess-concept-model-delivery-plan-2026-09-17.md), [rights decision](../research/chess-dependency-rights-decision-2026-09-17.md), and current jobs: [738e913a receipt](../.agent-runtime/jobs/738e913a-629a-429c-9f43-39dff0f131d7/receipt.json), [64bebafe receipt](../.agent-runtime/jobs/64bebafe-a421-4597-acf1-5918ea537774/receipt.json), and [efe23a receipt](../.agent-runtime/jobs/efe23a7a-fc3c-456a-87aa-db0be59f4ca1/receipt.json). The latest suite passed 30 focused tests and a finite loopback readiness check. | **Local, evidence-only preview; fail closed.** The environment now detects a local `chess` module but no Stockfish executable, so no engine-backed comparison is available. A contract-fixture explanation emitted by job 4e69bfed is synthetic and explicitly not engine evidence. No legal replay, rights-approved source intake, real commentary ingest, model training, expert evaluation, or FIDE-level explanation has been established. |

## Current gates

1. **SoccerMaster:** independent annotated multi-game evaluation, privacy/anonymization repair, coach relevance judgments, and candidate review/promotion remain open.
2. **FootballMaster:** human temporal/event annotation and a corrected abstention/event contract are prerequisites to semantic evaluation; more unlabelled prompting is not an adequate substitute.
3. **Searchable demo:** its runtime is not active; reopening it would be a presentation action, not new semantic evidence.
4. **Chess:** approved rules/engine provenance and dependency rights are required before legal replay or engine-backed candidate comparison. Rights-recorded source material and independently annotated/expert explanation evaluation are still required before any human-quality or FIDE-level statement.

## Recommended next packet

No new cross-lane packet is recommended from this audit. The safe non-duplicative work remains the Chess Concept lane's existing dependency-free contract/parity work and the separately controlled rights decision for a rules library/engine. Do not start a second listener, rerun retained jobs, ingest public creator commentary, or launch new SoccerMaster/FootballMaster model experiments merely to create activity.

## Audit conclusion

The project has real, inspectable local systems and documented failure evidence. SoccerMaster and FootballMaster are not semantically validated; the shared search UI is presently stopped; and Chess is a deliberately abstaining prototype with a live loopback preview. The honest umbrella status is **infrastructure and provenance work progressing; semantic coaching and FIDE-quality understanding remain unproven**.
