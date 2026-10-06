# Project Guide — Sports Play LLM Research

Historical repair: [frozen intake restoration and false cohort acceptance](research/chess-intake-restoration-2026-09-22.md). The original v1 importer was restored. Preserve the erroneous September 22 acceptance and exact counter-evidence. A separately versioned 24-position cohort was assembled from the retained CC0 prefix on October 5; its source binding and limitations are in [the current readiness receipt](research/chess-product-readiness-2026-10-05.md). This does not pass the commentary gate.

Current acceptance authority: read `research/chess-commentary-capability-gate-v1.md` before planning commentary work. The latest finite implementation/evidence handoff is `research/chess-no-forward-input-2026-09-22.md`; it links the earlier extended-claim validator and the next generation-runner requirement. Chess remains the only active domain; local execution continues while the gate is unpassed.

Current local review entrypoint: `prototype/CHESS_EVIDENCE_REVIEW.md` documents the
real-development evidence page and the offline completed-game PGN review tool.
They expose board facts and bounded engine observations; the commentary gate
above remains unpassed.


## Purpose

Build a reproducible, evidence-grounded research program, starting with real chess positions and grounded move explanations, then testing what transfers to sports. The current user correction is continuous chess-first improvement. Preserve historical soccer/football evidence and require separate evidence before claiming sports competence.

## Read in this order

1. `AGENTS.md` — research-loop contract, lanes, quality gates, and protected actions.
2. `research/chess-autonomous-research-program-2026-09-18.md` and `README.md` — current chess-first authority, real data and honest outcome boundaries.
3. `GOAL_WORK.json`, `state/loop-state.json`, and `research/action-plan.md` — current work and replenished frontier. The dated sports coverage ledger remains historical context for separate sports claims.
4. The narrow experiment, dataset, prototype, or deliverable named by the task.

## Map

| Location | Use |
| --- | --- |
| `research/` | Decision log, action plan, paper outline, source/evidence notes, and radar |
| `state/` | Durable loop and document-sync state |
| `experiments/` | Versioned experiment work and receipts |
| `prototype/` | Demo/prototype implementations; each subproject has a README |
| `data/` | Open/public data; read the dataset-specific README and rights boundary first |
| `footballmaster/` | FootballMaster-specific materials |
| `scripts/` | Doctor, reproduce, verify, smoke, data validation, local VLM, and demo commands |
| `tests/` | Deterministic project checks |
| `deliverables/`, `presentation/`, `demo/` | Candidate/shareable outputs; subject to the review-promotion gate |
| `artifacts/`, `logs/`, `source/` | Generated evidence/logs/source inputs; inspect only for a named chain |

## Working rules

Keep a maximum of the authorized independent execution lanes, record claim-level primary-source evidence, and never call synthetic output real soccer evidence. Shareable work must follow the candidate → independent Luna review → defect resolution → Terra director promotion sequence. Public sharing, commits/pushes, restricted data, forms, licenses, purchases, and contact remain human gates.

## Token-saving rules

Start with the current state files and the one named lane. Do not crawl dated frontier logs, all experiments, or whole dataset trees. Use an existing dataset/prototype README to locate the exact file or command.

## Portable Windows checkout

For a new Windows computer, install Python 3.11 and run `scripts/bootstrap.ps1` from the repository root. `requirements-windows-py311.lock.txt` pins the checked project environment; `scripts/resolve-python.ps1` resolves the project-local interpreter without depending on a fixed Agent Studio installation path. Run `scripts/portable-doctor.ps1` for source/dependency readiness, then `scripts/reproduce.ps1` for the bounded public software reproduction. `scripts/doctor.ps1` and `scripts/verify.ps1` also inspect local evidence and data packages that are deliberately not in the Git mirror; their missing-data results on a fresh checkout are expected until authorized assets are made available locally.
