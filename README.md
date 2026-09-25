# Sports Play LLM Research

**Status:** active, local-first research and engineering. This repository is the intended project handbook and versioned collaboration point; this page is operational documentation, not a reviewed research deliverable or scientific claim.

## Where work happens

The working project is on the Windows Agent Studio computer at:

`C:\AI\projects\SportsPlayLLMResearch`

Implementation, tests, approved local inference, and evidence collection use the existing local Agent Studio/Company Runtime workflow. Company Runtime is the sole scheduler; do not create a parallel scheduler or replay retained jobs. Keep the local workspace authoritative for active experiments until their files have been reviewed and safely synchronized here.

**Current sync setup blocker (2026-09-25):** native `git fetch --prune origin` from the local checkout returns HTTP 403, and this repository had no Git branches before this handbook was created. Restore the intended repository-scoped native Git access before claiming that local agents and this repository are synchronized. Do not upload the dirty local checkout wholesale or initialize its history over this repository.

## Current research direction

Work is **chess-first** under `research/chess-autonomous-research-program-2026-09-18.md`. Historical soccer and football research stays available as separate evidence; it does not establish chess results or current sports competence.

The no-forward commentary capability gate in `research/chess-commentary-capability-gate-v1.md` remains **unpassed**. The next documented implementation requirement is a separately versioned local generation runner using the validated no-forward input boundary, with fake-transport tests and durable raw-result/failure retention before any live model request. Never give a generator engine PV tails, post-move boards, future moves/features, puzzle solutions/themes, annotations, or evaluator-only material. Do not claim professional commentary quality or board-game generalization until the gate is independently satisfied.

## Evidence and promotion

- Freeze inputs, protocol, denominators, and budgets before measurement; preserve failed and not-run cases.
- Separate software tests, model/engine observations, scientific acceptance, and release readiness.
- Preserve source, rights, and provenance records. Synthetic fixtures are software tests, not empirical results.
- For a shareable research candidate, follow the project gate: versioned candidate → independent Luna review → resolve defects → Terra director inspection and exact promotion.
- Keep restricted/private data, credentials, runtime databases and logs, vendor/dependency trees, model weights, and unreviewed generated artifacts out of routine Git synchronization. Verify rights and scope for each proposed file.

## Collaboration and synchronization

Use this repository for the maintained project index, approved source/docs, decisions, and reviewable evidence. Each sync must identify exact commits and paths, exclude protected/generated/private material, run the smallest applicable verification, and read back the exact remote commit. Do not rewrite history, merge over active local work, or treat a successful command as research validation.

Until native Git access is restored, GitHub-side documentation may be visible here while local agents cannot fetch it; that is not real-time synchronization. See [issue #1](https://github.com/LucasKazaki/sports-play-llm-research/issues/1) for the access blocker.

## Current GitHub mirror status

This repository is still being bootstrapped. As of 2026-09-25, its GitHub branch contains this operational README only; the local research sources and engineering workspace have not been mirrored here. The Agent Studio workspace remains the active local project while native Git access is repaired. Do not describe this repository as a real-time mirror yet, and do not copy the dirty local tree through ad hoc file writes. Once repository-scoped native Git access is restored, synchronize approved paths through the existing review process and verify the exact remote commit.