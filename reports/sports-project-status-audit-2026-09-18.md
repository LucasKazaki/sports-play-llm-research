# Sports project status audit — 2026-09-18

**Method:** read-first local audit of the required project context, current loopback listeners, and durable runtime receipts.  
**Scope:** internal status only. No source, dependency, media, service, scheduler, or external state was changed.

## Runtime state

- Company Runtime is live on `127.0.0.1:4174` (PID 16132 at audit time).
- Chess Concept preview is live only on `127.0.0.1:8782` (PID 25372). Its current fixed packet returns a safe abstention with `invalid_position_evidence`; it does not generate a chess explanation.
- No listener was observed on 8771, so the shared SoccerMaster/FootballMaster searchable interface is not currently running. This is an observed stopped presentation surface, not a product failure.
- The state record says the project is `working`; its `runtimeObservation` is historical (2026-09-08) and should not be read as a fresh liveness test.

## Completed, inspectable artifacts

| Area | Evidence | Current claim boundary |
| --- | --- | --- |
| SoccerMaster | [Long-form report](../research/soccermaster-longform-technical-report-2026-08-27.md); [package receipt](../artifacts/soccermaster-longform-v1/package-receipt.json); [publication-readiness report](soccermaster-archit-publication-readiness-2026-09-13.md). | 96/96 structured reports are infrastructure evidence only; 3/166 restricted annotation corroboration and 0/6 fully supported spot checks keep soccer **SEMANTIC NO-GO**. |
| FootballMaster | [Long-form v2 report](../research/footballmaster-longform-v2-technical-report-2026-08-28.md); cited `artifacts/footballmaster/longform-v2/verification-receipt.json`. | Sealed retrieval path exists, but 36/36 abstentions, 27/36 contradictions, and 126 unsupported scoring assignments leave football **SEMANTIC NO-GO**. |
| Searchable demo | [Prototype README](../prototype/README.md); soccer and football reports above. | Adapter/launch paths and sealed indices exist; no active 8771 UI was observed. Retrieval of saved VLM text does not prove event correctness or coach relevance. |
| Chess Concept | [State](../state/loop-state.json); [evaluation/transfer map](../research/chess-concept-evaluation-and-transfer-map-v1.md); [latest focused suite receipt](../.agent-runtime/jobs/efe23a7a-fc3c-456a-87aa-db0be59f4ca1/receipt.json); [local preview handoff receipt](../.agent-runtime/jobs/4e69bfed-6bdb-4f5b-b288-6eae2edd2ee5/receipt.json). | 30 focused tests and loopback readiness passed. The preview deliberately abstains. A synthetic contract output is not engine evidence, commentary, or expert explanation. |
| Chess planning | [Evaluation/transfer-map creation receipt](../.agent-runtime/jobs/82ac34e5-6d2b-48cb-82b1-a2c98be24b60/receipt.json). | Internal plan only; it explicitly blocks claims of sport understanding or tactical transfer from chess. |

## Open gates

1. **SoccerMaster:** multi-game independent annotations, privacy/anonymization resolution, coach relevance judgments, and candidate review/promotion.
2. **FootballMaster:** human event/temporal labels, a repaired abstention/event contract, calibration, and coach-usefulness evaluation.
3. **Chess:** rights-recorded position provenance, legal replay, Stockfish or another approved engine receipt, independently annotated/expert explanation evaluation, and calibration. The latest environment receipt [64bebafe](../.agent-runtime/jobs/64bebafe-a421-4597-acf1-5918ea537774/receipt.json) detects `chess` locally but no Stockfish executable; this is not permission to acquire software or data.
4. **Across all lanes:** no semantic coaching, human-quality, or FIDE-level claim is justified by current test or interface evidence.

## Current active lanes and recommended disposition

The only observed active project presentation lane is the fail-closed Chess loopback preview. Company Runtime is healthy and recent jobs completed, including the 30-test Chess suite and the internal evaluation/transfer map. SoccerMaster and FootballMaster have durable completed packages but no observed live demo process.

No new non-duplicative execution packet is recommended by this audit. Continue only the existing Chess evidence/rights gate work when its required authority is recorded; do not restart a listener, replay retained jobs, ingest creator commentary, or start fresh sports model experiments solely for status activity.
