# Agent Studio semantic correction receipt

## What happened

Agent Studio task `805ebdba-c15e-4689-95ea-e33469244b6d` successfully exercised the workspace-write lane and produced `research/archit-coach-ready-next-steps-2026-09-03.md`. The server verified the write, but the drafted content contained unsupported claims. A valid write receipt therefore did not imply semantic correctness.

Unsupported claims in the first draft included:

- a completed Gemini demo and target accuracy;
- 82.3% primary and 79.1% recovery accuracy;
- public licensing for the SoccerNet clips;
- a verified SoccerMaster checkpoint load and comparable accuracy;
- a Docker/GitHub deliverable that does not exist.

The first-draft server artifact hash was `04b6b889beeb9bea9bcf4550ce589f80a470f03d8801e6695eb9d36425e32110`.

## Correction

The artifact was replaced with a source-grounded version whose SHA-256 is `268e2aa77ac72c6de97bcedf0f4f917a409d950d4f17a9e6ef321e823c144b26`. A negative scan found no remaining matches for the invented metrics or completion claims.

The corrected file restores the canonical boundary:

- primary run: 3/6 completed, 3/6 schema-valid, 1/6 allowed-window correct, median completed latency 110.624 seconds;
- isolated recovery: 6/6 completed and schema-valid, 0/6 allowed-window correct, median latency 9.306 seconds;
- current state: **SYSTEMS GO / SEMANTIC NO-GO**;
- no verified Gemini 3 run, SoccerMaster checkpoint execution, fine-tuning result, coach validation, or benchmark win.

Focused verification after correction: `60 passed in 2.92s` across `test_hosted_video_benchmark.py`, `test_soccermaster_evidence_gated.py`, `test_soccermaster_scale.py`, and `test_soccermaster_longform.py`. This verifies the existing harness/scaffold code paths, not model accuracy.

## Monitoring implication

Overnight checks must inspect artifact meaning against the canonical evidence, not count task completion or a server-owned file receipt as research progress by itself.
