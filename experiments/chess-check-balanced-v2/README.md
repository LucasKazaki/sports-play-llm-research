# Balanced check learning, October 16

The earlier eight-field adapter missed every checking move in its balanced
diagnostic. This experiment trains a new Qwen3-0.6B adapter specifically to
distinguish a checking move from a nonchecking move made by the same piece.

The first run stopped on its Windows commit-memory reserve after **1,004 actual
optimizer updates**; 992 was the last periodic progress counter. It did not
encounter a recorded out-of-memory exception. The best completed development
checkpoint scored 137/256 individual moves and 21/128 complete matched pairs.
No held-out generation occurred, no checkpoint was finally selected, and all
2,304 planned evaluation outcomes remain recorded, including not-run cases.

A separately frozen [warm retry](training-protocol-run-2-v2.json) continues the
saved update-512 adapter with a fresh optimizer for 4,096 new updates. This is
not an exact optimizer resume. Its selector retains the unchanged warm adapter,
the disabled base, and new checkpoints. The retry requires 6 GiB of available
physical memory and 6 GiB of commit headroom during execution, compared with
the first run's 4/8 GiB reserves. GPU work is serialized with the move-policy
experiment. Original source, protocols and interruption evidence are preserved.

The retained CC0 Lichess shard supplies 8,192 training games, 128 development
games and 256 held-out games. Each contributes two legal moves, with exactly
one giving check. Known earlier games and before/current/successor positions
are excluded. The model sees only the current FEN, candidate UCI move and
occupied-square map. It never sees a SAN check suffix or future position.

The original intake [protocol](protocol.json) was frozen before selection.
The [training amendment](training-protocol.json), frozen before any model call,
adds durable interrupted-outcome accounting without changing the cohort or
the learning task. Exact original intake source and plan are archived.
An independent full-cohort audit verifies all 17,152 examples and zero known
historical or cross-split game/position overlap. Eleven software tests pass.
Those checks establish dataset and implementation integrity, not learning.

The initial training plan uses fresh rank-16 LoRA weights, 2,048 updates and native
full-vocabulary cross entropy for one `true` or `false` next token. Evaluation
scores unrestricted token choices; another token is invalid. Conditional
binary probabilities are retained separately and never rescue a raw answer.
Development selects a checkpoint before the held-out comparison is opened.
The warm retry keeps the same task and cohort with its explicit changes above.

Actual checkpoints, journals and complete outcomes stay in ignored local
storage at `data/private/chess-check-balanced-v2/`. Public summaries will report
class recall and completely correct matched pairs, including failures.
This is a check-discrimination experiment. It does not establish strategic
understanding, move strength, Elo or teaching quality.

The source is [Lichess's CC0 database](https://database.lichess.org/); the pinned
Qwen base declares Apache-2.0. Creator videos are not used for training.
Code and research notes were prepared with Codex assistance.
