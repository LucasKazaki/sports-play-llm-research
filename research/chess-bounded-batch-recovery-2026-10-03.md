# C02 R18: bounded batch recovery after engine-session failure

Research date: 2026-10-03.

Packet: `SLM-C02-R18-BOUNDED-BATCH-RECOVERY-v1`.
Cloud task SHA-256: `b4d49bac995e2f60b3e1581df543ec2ed9774123b384b54227c7a8167e05c5c1`.

Current mirror baseline: `156780d1370363ab83f64589c8bb319dde63cc9f`.
Current collector blob: `7dccf3525049c60a72f0a2883709012d86d6adfb`.
Current collector-test blob: `1db2b5d6592c51af4a4cc693984da9d6a3ec1cd5`.
Current streaming-test blob: `7a540cc201f82ea59b05ab42c1fe8cfe1eca79ba`.

## Concrete finding

The existing regression `test_failure_keeps_all_requested_cases_and_cannot_report_completion` freezes 8 requested positions and fails engine call 3. It proves only 3 engine calls occurred and 2 rows succeeded, but the current receipt encodes all 6 remaining rows as failed. Therefore 5 untouched rows are labeled as engine failures even though they were never attempted.

The collector correctly closes the uncertain engine session and never reuses it. What is missing is batch-level accounting and bounded continuation on a fresh process generation.

## Architecture decision

Layer R18 on the existing R6 process/search lifecycle. Do not create another engine adapter.

For future receipts:
- `failed` means the exact row was actually attempted and has typed failure evidence;
- `not_run` means no engine attempt occurred and carries an explicit reason;
- preserve the frozen requested denominator and order;
- never retry the failed position inside the evidence batch;
- after a fatal generation failure, retire that R6 generation;
- permit at most one preregistered fresh generation in v1, and only for later untouched positions;
- the fresh generation must re-establish R9/R15 effective configuration/provenance;
- if recovery fails or is unavailable, mark the remaining untouched rows `not_run`;
- caller cancellation ends the batch and never spawns a replacement.

Stockfish 19 terminates immediately after a CRITICAL ERROR caused by invalid command/position input, so replaying the same request automatically is especially unsafe. python-chess 1.11.2 represents unexpected engine process loss as `EngineTerminatedError`; a terminated process is not a reusable transport.

## Cloud reference check

Standard-library-only reference:
- fail-first current-source observation: expected exit 1;
- focused tests: 19 passed, 0 failed;
- `py_compile`: exit 0.

Reference source SHA-256:
`ca4ed64702a516788ec5fad0e2a4bf499e30179cc4b046f6d8fa975e98f3f8b7`.

Reference test SHA-256:
`30f122ea49bc55637ddf004070864d28166294d5377cc077751b84d94428f5c5`.

These are cloud control-contract checks only. No Stockfish, python-chess native engine path, Company Runtime, Windows recovery, or AI-PC execution is claimed.

## Native next action

After genuine C00 N/N+1 consumption, add a fail-first assertion that rows 4-8 in the existing crash fixture were unattempted. Then integrate bounded recovery into the single current collector or its already-adopted R6 equivalent.

Return `WORKER_UPDATE SLM-C02-R18-BOUNDED-BATCH-RECOVERY-v1` with genuine Runtime task/run/read/result receipts, per-row attempted/status/generation evidence, one healthy fresh-generation continuation, one exhausted-recovery case, proof the failed row was never replayed, and historical receipt hashes unchanged.

Typed stops: `SLM-C02-R18-C00`, `-PATHS`, `-R6`, `-PROVENANCE`, `-RECOVERY-FACTORY`.

Sources checked 2026-10-03: Stockfish 19 release notes; python-chess 1.11.2 engine docs/source. Stockfish is GPL-3.0; python-chess is GPL-3.0-or-later. No upstream implementation code is copied here.
