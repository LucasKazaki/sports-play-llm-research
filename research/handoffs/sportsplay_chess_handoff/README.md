# SportsPlay chess-phase agent handoff

This is an authoring and planning package, not a completed chess application. It contains a private research plan, a 32-task dependency graph, proposed evaluation settings, and evidence templates. No model benchmark or learner result has been run by this bundle.

## Start here

Read `FIRST_AGENT_PROMPT.md`, then `project-context.json` and `CHESS_PHASE_HANDOFF.md`. Start task C00 before claiming that the local agents have access. The workspace path and active agent roster must be discovered on the AI PC. Translate the task graph into the existing Company Runtime; do not create a second scheduler.

## Canonical working documents

[SportsPlay Internal Research Hub](https://docs.google.com/document/d/1YtB0K7W4aT5NE4c7N6738kxu6V0cUoMuhpDvzm8JsH8/edit) is the living record of decisions, evidence, and blockers.

[Chess-phase implementation, evaluation, and presentation handoff](https://docs.google.com/document/d/1_w_YCoTMQtP1Ni9Sj_m1bkLCp77Cf0HPPjhxUyCam3M/edit) is the versioned technical protocol.

Both were created as restricted, owner-only Google Docs. A private Google Doc does not automatically become readable by local agents. C00 must verify the authorized Drive route or install the included read-only mirror in the actual project context. Do not change sharing to make access work.

The [Archit update](https://docs.google.com/document/d/1uUdenRhHnkKJQSQVH4ppDhSdTbrlLJafrAuiZMzKEjk/edit) is separate and collaborator-facing. Its existing permissions were not changed. Do not insert internal document links or copy private logs into it.

## Package contents

- `CHESS_PHASE_HANDOFF.md`: full report, including architecture, tools, state/evidence contracts, data splits, tests, 32 work packets, final deliverables, and a 12-slide presentation plan.
- `tasks.json`: proposed dependency graph, with all tasks initially NOT_STARTED.
- `benchmark-config.proposed.json`: proposed starting settings, not measured performance.
- `project-context.json`: canonical IDs, source revisions, local mirror hashes, and private-access policy.
- `INTERNAL_HUB_SNAPSHOT.md`: readable initial hub snapshot; refresh from the canonical document before work when authorized access exists.
- `FIRST_AGENT_PROMPT.md`: copy-ready coordinator instruction.
- `templates/`: read-access, work-evidence, Chess.com comparison, and result templates. Null fields mean not measured or not verified, not zero.
- `sources.json`: primary reference links and their source IDs.
- `MANIFEST.sha256`: hashes of the delivered files, excluding itself.

## Completion and maintenance

Implement a local, completed-game chess review assistant using existing chess tooling. Evaluate exact state separately from generated images and replay. Use rules/tablebases, bounded engine references, platform comparisons, and human judgments as distinct evidence types. Keep general engine estimates and Chess.com classifications separate from exact truth claims.

An owner-authorized daily connected-evidence review has been scheduled for the private hub. It does not execute local Agent Studio work or see unpublished AI-PC changes. Local agents should submit receipts and update proposals after accepted work so the documentation can reflect real progress.

## Privacy and reproducibility

Keep this package in the private project workspace. Do not commit it to a public repository merely because GitHub is available. Do not include secrets, proprietary platform assets, restricted footage, or hidden final-test answers in shared agent context. Claim completion only against the handoff's relevant acceptance gate and retained artifacts.
