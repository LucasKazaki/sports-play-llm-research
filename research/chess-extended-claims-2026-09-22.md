# Extended chess claim validator — 22 September 2026, 18:28 UTC repair

## Implemented and tested; wider acceptance remains open

The source-bound evaluator now checks exact piece occupation before/after the selected legal move and replays every ply of an explicit variation. An asserted legal variation is not an engine recommendation. Exact full-PV equality is required for retained-engine attribution; a legal prefix cannot impersonate the full recorded PV. Unsupported strategic/teaching claims abstain. Integrity is checked before any verdict. The module is evaluator-only and performs no model or engine calls.

Source: scripts/chess_extended_claims.py, SHA256 003d2b621dabc4b7741732c85df3737035c589b4ba95976e5a1c49b3e24e313f. Tests: tests/test_chess_extended_claims.py, SHA256 9ced7e75255417b046474e48ddfdc98d9e6f9325f9002dea999e73cac8c63b0b.

The 41 new tests include 64 occupation assertions over all 16 retained development candidates, false occupation, legal/misattributed PVs, illegal subsequent plies, unknown/foreign references, changed sources and unsupported claims. Castling, en passant, promotion and post-checkmate probes are explicitly synthetic software fixtures with literal expected outcomes. No real matches, ratings or human labels were invented. Existing CC0 Lichess acquisition/projection/typed receipts and 8/8/8 split remain unchanged; no heldout outcome was scored.

## Exact native evidence

Fail-first task bb3ec06e-9cef-48b0-a5f8-2504d3f3956e; job 333520ce-8f2c-4072-90c0-9778847902da; receipt 262c87cf065ad006b25401674e870824ed84ae5ec6520893a85444559636c250: meaningful new tests could not import the absent module.

Implementation task af5e4268-6421-44af-890e-6ff71fa10de9; run 8f9263d5-bab8-46ed-aea5-f87a2109433e; job 44571d89-40c4-43ad-82b6-799b06ea9243; receipt 22896d6517a3279881dd79bc5aa73d3a6e356bb75e2060b384269304f1945f33: 70 focused tests passed in 36.88 seconds, including the 29 original adapter controls.

Full verification task 0ed007fe-9087-4d99-b366-9b6a3b6adf2a; run 634004e0-8786-4475-8ba6-72431fe2cd6d; job c476ec3c-0b9a-4178-8365-051e0b375c7a; receipt 63088bf742d92bcdf37e69389b552cb88bf8b231570e459720a434604951850a: all nine commands passed, frozen before/after source bindings matched, doctor/reproduction/log collection/full verification/synthetic smoke/reset preview passed. Full suite: 1325 pass, one existing Windows symlink-permission skip, zero failures.

Retained focused streams and implementation receipt are in artifacts/chess-extended-claims-v1/. The exact 30390-byte review bundle has SHA256 d26b151f30f9571a0821c315f7a8485ae771dbab48b7f607b6554d1064f5598c. Initial review 29886ec9-f9a4-4759-9c61-67b6b2ecab72 exhausted its three-tool phase before logs. Bundle reviews bb5e2d98-e62f-4b9c-9e44-4ced27c4c6c9 and fb275746-8087-4373-86c3-3a437cf0471c were unverified because a generic developer task was classified as implementation intent despite read-only scope. Generic goal-worker reader 71d64627-e07c-4bf0-a5d6-86fde7f72151 lacked its specialized binding. All failures remain retained; none is an accepted review.

The established native-result route succeeded. Native task c5155f42-99a0-4ceb-bb4b-b03f985059cc, job 3a117756-bce1-45d1-8b66-864705045aa0, bound the unchanged tested candidate; receipt SHA256 699f4bd1c874e296c8217dae3d3d418eda0f9a86b6899b74b591c3b2561967dc. Its independent local callback 1f3233d7-4336-4ff6-ab59-bd0ae3220ee4, run 5cd65694-295f-4779-8de9-c566323de444, completed at 18:57:06.913 UTC with verification_status=passed. It read the exact native result and full source/tests, with all three hashes independently checked, and returned no follow-ups. Read receipt defcd729a729b71050705681f8da936200c93cfeefa6d1d793c09cd332bcbce7 and runtime verifier receipt 38df05f467d4ed678b6e523dbd86bb114ba14ce8f6ca83982e21fd45ed6a9070 bind this finite review. The local reviewer did not execute tests or produce a Company goal-acceptance verdict. Inspect artifacts/chess-extended-claims-v1/independent-review.json for exact scope and evidence.

The first autonomous successor goal-99010926b6fe26858b41f3132abf9873a51391096ed4c233 blocked on the absent experiment instead of proposing it; the second goal-4b4795646ca021b80e641beca666b802c1b42a585d056768 settled unverified. Their histories and consumed budgets remain. Missing source is the implementation requirement, not new external authority. Do not count either attempt as product progress or replay its unchanged packet.

## Next useful prerequisite

Keep the same factuality item open. Implement a separately versioned frozen extended-claim experiment with complete requested/accepted/abstained/failed/not-run accounting, provenance and independent replay. Reuse the validator; do not rerun existing tests or recreate files as progress. New source files need an actual create-only edit plus meaningful tests, not a missing-file test command. Before commentary generation, implement the no-forward allowlist from research/chess-commentary-capability-gate-v1.md. The legacy generator remains incompatible with that gate. Professional commentary quality, a fresh game-disjoint heldout evaluation and board-game expansion remain unachieved.

Prior exact agenda bytes are retained in research/history/GOAL_WORK-before-20260922T1828Z.json. Existing original task/run/job/session identities, spent budgets, local 131072-context routing and the single scheduler are preserved. No unrelated project is changed.
