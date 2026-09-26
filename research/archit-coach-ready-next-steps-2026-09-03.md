# Archit coach-ready next steps

## Goal

The final goal is a coach-ready, evidence-linked retrieval system that can extend across UMD sports and support publication-quality research. The midterm goal is narrower: give Archit a short, honest demo and a clear view of what works, what does not, and what we will test next.

## What is working now

- Private-local clip ingestion and short-window frame sampling.
- SHA-256 hashes for clip/frame identity and integrity. These are not semantic embeddings.
- Structured event cards with validation, SQLite/FTS storage, deterministic ranking, and exact evidence playback.
- A coach-facing search/demo path that is useful for testing system plumbing.

Current boundary: **SYSTEMS GO / SEMANTIC NO-GO**. The storage/search/playback chain works; soccer-event understanding is not reliable enough for a coach or publication claim.

## Current six-clip evidence

- Primary run: 3/6 requests completed, 3 timed out, 3/6 were schema-valid, 1/6 matched the allowed time window, and median latency among completed requests was 110.624 seconds.
- Isolated recovery run: 6/6 completed and were schema-valid, 0/6 matched the allowed time window, and median latency was 9.306 seconds.
- Commentary cross-check: 2 supported, 2 contradicted, and 2 uninformative. Commentary is post-hoc auxiliary evidence, not ground truth.
- Model self-confidence is not treated as calibrated probability.

No Gemini 3 run, SoccerMaster checkpoint execution, fine-tuning result, coach validation, real-time performance, or benchmark win has been verified yet.

## Five coach clip concepts

1. Goal-mouth sequences: saves, rebounds, second balls, cutbacks, and follow-up shots.
2. Set pieces: corner/free-kick/penalty setup, delivery, first contact, and outcome.
3. Transitions: turnovers, counterattacks, counter-presses, and recovery runs.
4. Possession progression: overloads, switches, line breaks, final-third entries, and exits under pressure.
5. Defensive shape: compactness, press triggers, off-ball runs, tracking failures, and breakdowns.

These are hypotheses to take to coaches, not validated requirements.

## Five retrieval interactions

1. Natural-language search: “show every left-side cutback that led to a shot.”
2. Structured filters for event type, team, phase, field zone, score state, and time.
3. Query by example: start from one clip and retrieve similar sequences.
4. Sketch/touch query: draw a run or ball path on an iPad and match it in pitch coordinates.
5. Conversational refine/compare: narrow results, compare examples, expose evidence, and allow correction or abstention.

## Five-minute Archit demo

1. Ingest one rights-safe clip and show the sampled evidence.
2. Create an event card and show timestamps, claim origin, validation status, and hashes.
3. Show the SQLite row and generated search plan.
4. Run a coach-style query and play the exact supporting span.
5. Show one plumbing success and one model failure/abstention so the boundary is visible.

## Gemini comparison gate

Freeze one event-card schema, prompt, held-out clip manifest, and scoring sheet. Target at least 6 and ideally 10-15 rights-reviewed clips, and preserve the exact model/version, raw output, latency, failures, and hashes. Run remote inference only after both third-party-processing rights and a zero-spend credential path are verified. Until then, the deliverable is the runnable provider-neutral harness plus the exact gate; private SoccerNet footage stays local.

## SoccerMaster feasibility gate

Treat SoccerMaster as an encoder/task-head foundation model, not a conversational VLM. Before any checkpoint experiment, verify the official source/commit, checkpoint and code/data licenses, SoccerNet split overlap, input contract, and 8 GB VRAM fit. Do not bulk-download SoccerFactory or claim a checkpoint result before a real run receipt exists.

## Next three bounded tasks

1. Freeze the benchmark contract and build the fail-closed Gemini harness with tests and a 6-15 clip rights manifest.
2. Finish the no-download SoccerMaster feasibility audit and define the smallest reversible adapter/dry run.
3. Package and rehearse the Archit demo with the retrieval menu, evidence table, limitations, and coach interview questions.

## What to ask Archit and coaches

- Five to twelve real queries they would want during or after a match.
- Which errors are tolerable, when the system should abstain, and how much verification time is acceptable.
- Who owns the workflow and who can approve media, API, and compliance decisions.
- Whether the first coach-facing scope should stay soccer-only or include one carefully separated second-sport example.

## Publication path

Compare the same held-out clips under three conditions: a strong direct VLM, a VLM with declared soccer evidence/tools, and SoccerMaster-assisted reranking. Score report correctness, timestamp/region accuracy, top-k retrieval, abstention quality, latency, and human verification time. Keep sports, datasets, and splits separate.

## Consolidation note

- The complete 14-file legacy Agent Studio soccer-research workspace is archived in the current project with matching SHA-256 hashes.
- The old SSD contributed 11,427 accessible source-only files without overwriting current files; a post-copy dry run found zero accessible source-only files left.
- Twenty-one old-SSD directories still deny read access. Matching current-project directories exist, but their contents could not be byte-compared. Permissions and private media were left untouched.
