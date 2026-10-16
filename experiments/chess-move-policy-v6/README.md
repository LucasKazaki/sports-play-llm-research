# Learning legal moves without masking predictions

V5 improved same-panel teacher agreement slightly, but its selected checkpoint produced more illegal raw forecast sequences. V6 tests a direct training change: keep Stockfish move supervision and also penalize probability assigned to illegal action classes. The classifier still chooses from all 1,968 classes at inference.

For a batch, the new loss is full-class cross-entropy plus `logsumexp(all logits) - logsumexp(legal logits)`, with coefficient 1.0. The second term is the negative logarithm of total softmax probability on deterministically legal moves. It changes gradients during training; it does not filter, repair or replace a prediction. The calculation uses the installed PyTorch 2.8 contracts for [cross-entropy](https://docs.pytorch.org/docs/2.8/generated/torch.nn.CrossEntropyLoss.html) and numerically stable [log-sum-exp](https://docs.pytorch.org/docs/2.8/generated/torch.logsumexp.html).

## Frozen experiment

Continue the actual V5 selected step-2048 ROOK-CLF-9m weights. Reuse exactly 32,768 V5 training rows and targets, then add 32,768 fresh training roots. Select 512 fresh development roots, 512 fresh held-out roots and a separate 512-root forecast-candidate reservoir. All fresh roots must have distinct original game IDs and avoid the full historical registry, matched-check and balanced-check cohorts, and every V5 training or evaluation root's before/current board. Reused V5 training examples are the explicit exception; V5 evaluation examples never enter training.

Use the existing pinned Lichess CC0 Parquet shard. Consume only the source's first opponent setup move; never use source solution tails or puzzle themes. CPU teachers use one thread, 32 MB hash and 50,000 nodes per root. Keep every requested teacher record, including failures and incomplete evidence. Existing V5 labels are reused exactly and are never relabeled.

The forecast panel deliberately fixes V5's incomplete teacher support. Before any learned call, choose the earliest 128 source ordinals from the fixed 512-candidate reservoir whose Stockfish PV contains three legally replayable plies without an automatic terminal state before the third ply. Keep all candidate outcomes and exclusion reasons. If fewer than 128 qualify, stop without expanding the reservoir. This panel excludes short-PV and immediate-terminal cases and cannot be described as a general-play estimate.

Train 4,096 AdamW updates, batch 128, learning rate 0.000005, saving steps 0, 256, 512, 1024, 2048 and 4096. First prefer checkpoints with at least 99.5% raw development legality. Among those, choose highest teacher agreement, then legality, then earliest checkpoint. If none qualifies, use the predeclared fallback of teacher agreement, legality and earliest checkpoint. Save selection before opening the new held-out panels.

Compare the starting checkpoint and new selection on the same fresh 512-root holdout and the same 128 supported forecast roots. Forecast both sides for three plies using the model's own previous legal prediction. The model receives no PV, future board, answer label or legal mask. Retain exact one-, two- and three-ply teacher-prefix agreement, legality, terminal/illegal outcomes, backend failures and all not-run roots. A backend failure is latched; raw and score files are saved before the run stops.

## Review and resource handling

The original `protocol.json` is preserved. Before source intake, independent review identified a reference-eligibility edge: python-chess can enumerate individually legal moves after an automatic draw, even though the game is over. The final `protocol-v2.json` pins the added terminal-state check and regression. No data or engine call occurred before that correction.

The CPU phase uses at most six teachers. It starts six only when available physical memory and commit headroom both exceed 10 GiB, otherwise three when both exceed 6 GiB, and stops before calls below those reserves. It does not change system settings or other processes. The root coordinator owns all CUDA execution. Training retains the existing per-64-update cancellation, deadline and read-only resource checks.

Create-only teacher attempts, durable per-row chunk journals, source snapshots and failure-inclusive aggregates reuse the reviewed V5 implementation. Interrupted calls are not blindly replayed. Fatal execution records remain separate from research outcomes.

## Current checkpoint

Before source intake, **46 CPU software checks pass**: 17 V6 objective, selector, reservoir and resource checks, plus 29 retained V5/evaluator checks. The gradient test is a software fixture showing that this objective reduces illegal probability on synthetic logits; it is not evidence that the chess model improved.

Final pre-intake source SHA-256: `22612791d18dcc81257ba3ec7a120215b4050c159b75768ef43c4bfe3284d670`.

Final protocol SHA-256: `b2eda0acf707b475cab8968991afc53fb46de426fced8e8e0084b4c38f7edfc4`.

CPU intake and teacher labeling are complete. Intake selected all 34,304 planned fresh roots and retained exactly 32,768 V5 training rows. Independent review checked every fresh root's source reconstruction, game identity, split and historical exclusions, with no overlap. All 34,304 new teacher requests completed without failure in 422.35 seconds using three workers. The fixed 512-root forecast reservoir contained 329 eligible three-ply references; the first 128 were selected, 201 remained unused, and all 183 short references remain in the candidate ledger.

Final labels contain 65,536 training, 512 development, 512 held-out and 128 forecast rows. Dataset SHA-256: `7891cb1fbbc175085310428eceff453cca88b3a24a79fa03c5ac8cce1582cf06`. Labels SHA-256: `2cf5f1f6efd1bd89d70df80a954ac2efb0aece0047caa9441b21b9b45d5eff90`. The compact `pretraining-receipt.json` binds these identities and all candidate outcomes.

Learned training and fresh evaluation are NOT RUN at this writing checkpoint. Subsequent private receipts provide actual execution status. No Elo, coaching, commentary or broad chess-understanding claim follows from this move-only experiment.

```powershell
.venv-soccernet/Scripts/python.exe scripts/chess_move_policy_v6.py intake
.venv-soccernet/Scripts/python.exe scripts/chess_move_policy_v6.py label
# Root coordinator only, after completed labels and independent source review:
.venv-soccernet/Scripts/python.exe scripts/chess_move_policy_v6.py train
```
