# Local chess rollout software stress test

**The classifier's single-position agreement gain did not establish strong play. Every completed game in this designed panel was lost to the bounded Stockfish opponent.** Four raw-policy games stopped on illegal model predictions; those remain unfinished games, not recorded chess losses.

The [protocol](../research/chess-rollout-stress-protocol-v1.json) was frozen before calls. Eight authored opening fixtures were legally replayed from the standard initial board. Each was played with the model on both colours, using both the base and the already selected v3 checkpoint, under raw-abstain and explicit legal-mask modes: 64 planned games. These are synthetic software stress fixtures, not acquired human games, a new held-out cohort or video-derived positions. No weights, hyperparameters or checkpoint selection changed.

The model received only its native current-FEN tokens. Stockfish 19 received the legal move history, used one thread, 32 MiB hash and 10,000 nodes per move, with hash cleared each move. The maximum additional length was 200 plies. Rules-based terminal outcomes and immediately claimable draws took precedence over the cap; capped/failed games would remain `*`, never synthetic draws. The panel finished in 36.91 seconds on the RTX 5080.

| Condition | Planned games | Opponent checkmates | Raw-illegal stops (`*`) | Raw legal decisions | Mask interventions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base, raw | 16 | 15 | 1 | 589/590 | 0 |
| Selected step 512, raw | 16 | 13 | 3 | 524/527 | 0 |
| Base, legal mask | 16 | 16 | 0 | 589/590 | 1 |
| Selected step 512, legal mask | 16 | 16 | 0 | 541/545 | 4 |

There were no model/adapter/opponent exceptions, no draw and no ply-cap stop. All 60 checkmates were wins for Stockfish, regardless of model colour. The remaining four games stopped before applying the illegal move. The selected raw-policy condition therefore cannot be described as having fewer chess losses: more games failed to finish legally.

Twenty-eight of the 32 paired raw/masked games stayed identical throughout. Four pairs diverged at the raw-illegal prediction; one selected-policy continuation needed a second intervention. Legal masking uses deterministic rules and must stay visible as assistance.

Before execution, independent source review caught missing metadata bindings, unlinked malformed-output rows and an opponent-configuration error path. Those were repaired and tested before model calls. Twelve focused tests include legal history, cap/outcome precedence, claimed repetition, raw-versus-mask behavior, malformed logits and injected model/opponent startup/configuration failures. Independent finite CPU mocks checked complete-run sequencing and failed-logit row linkage.

After execution, an independent reviewer legally replayed all 64 retained PGNs, checked all 4,528 applied moves and independently ranked all 2,252 retained logit rows. Every row is finite and linked exactly once. Raw choices, top-three values, legality, masks, terminal facts, final boards and aggregate counts agree. Twenty-four source, protocol, metadata, weight, engine and artifact hashes match. Shared paired positions have identical retained logits. No model or engine output was regenerated during review.

The [aggregate evidence](../experiments/chess-rollout-stress-v1/summary.json), [independent audit](../experiments/chess-rollout-stress-v1/independent-audit.json) and [64 PGNs](../experiments/chess-rollout-stress-v1/games.pgn) are available for review. Raw logits, complete decision traces and execution snapshots remain private local artifacts. The original classifier v3 experiment remains unchanged.

This bounded stress panel exposes concrete rule-compliance and sequential-play failures. It provides no Elo, calibrated strength comparison, commentary quality or sports-transfer result. It supports retaining the v3 weights as an experimental move-only candidate. The next training question is whether direct move-only supervision can improve the language policy without teaching noisy score tokens or concealing raw illegality. Codex assistance and independent agent review are recorded; a qualified chess review remains separate.
