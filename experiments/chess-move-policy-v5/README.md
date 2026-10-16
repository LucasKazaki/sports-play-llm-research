# Larger chess move-policy experiment

This experiment continues the existing ROOK-CLF-9m step-512 checkpoint on 32,768 new source-game roots. Its purpose is to measure raw move choice and short continuation prediction on fresh positions. This classifier does not write chess explanations.

## Completed result

The RTX 5080 completed all 4,096 updates and 262,144 example presentations.
Development selected update 2048. An independent file-only audit reconstructed
all held-out rankings and forecasts from retained outputs and verified the
checkpoint selection and weights. The result is a small agreement improvement
with worse raw legality; it does not justify replacing the default model.

| Fresh panel | Starting checkpoint | Selected checkpoint |
| --- | ---: | ---: |
| Holdout: raw Stockfish move agreement | 384/512 (75.00%) | 389/512 (75.98%) |
| Holdout: raw legal moves | 510/512 | 509/512 |
| Forecast: exact first ply | 92/128 | 97/128 |
| Forecast: exact first two plies | 47/128 | 48/128 |
| Forecast: exact first three plies | 30/128 | 32/128 |
| Forecast: three legal plies completed | 104/128 | 100/128 |
| Forecast: illegal-choice stops | 3/128 | 7/128 |

Both forecast conditions stop at a game ending on 21 roots. The teacher has
one-ply support on 128 roots, two-ply support on 102 and three-ply support on 72;
short references remain in the 128-root headline denominator. A legal divergent
line is not necessarily a bad line, and this agreement panel is not an Elo test.
Training and evaluation took 113.06 seconds; the six CPU teachers previously
took 233.03 seconds. These are different stages, not a sustained GPU-use claim.

[Summary](summary.json), [retained raw outcomes](evidence/), and
[evidence manifest](evidence-manifest.json) preserve the results. Full logits,
checkpoints and source data stay local. The next experiment targets legality
directly and uses a separately frozen, fully supported three-ply panel.

The frozen intake selected 32,768 training roots, 512 development roots, 512 held-out roots and a separate 128-root three-ply forecast panel. All 33,920 roots have different original game IDs. Selection inspected 73,058 source rows after excluding 38,888 known games and 105,895 before/current/successor board identities. It rejected 29 further duplicate/terminal boards and skipped 221 rows whose split was already full.

The source is the existing 294,920,084-byte Lichess CC0 Parquet shard. Intake consumes only the opponent's first setup move. Source solution tails and themes are neither selected nor supplied to a model. The new split also excludes the balanced-check cohort selected earlier in this work period, including both successors of every checking/nonchecking pair.

## Freeze and execution identity

The initial `protocol.json` was frozen before source selection. Root source review arrived after the CPU-only intake finished and before any teacher or model call. The explicit `protocol-amendment-v2.json` preserves that selected cohort and original snapshots. It repairs UCI score-event coherence, journals completed teacher calls, stops after failed model evaluation and adds cancellation/resource checks. It changes no data-selection or evaluation rule.

| Artifact | SHA-256 |
| --- | --- |
| Initial protocol | `666b1d484d21410715b160438ea85d7d6fdba56741cd2f787cc0f6ea084b7709` |
| Pre-label amended protocol | `a1ab33e7d324d048bd185aaf7f64ea08ba7b459965d8b5fb2eb0b0bf80d55dcd` |
| Implementation used for all teacher calls | `75b8190d71d92a937dff06cf342a4670b65208c2db8213a7374a3cfc71f62bac` |
| Final pre-training protocol | `7cba8468e2220c998fe099048cb5e3d049123b2fcd474fb4ec9ab532028c91ac` |
| Final pre-training implementation | `17ce1bbf1f31d750c13709def6a88e2de43a014ad849dc0304c9bbdd7bf55193` |
| Frozen dataset | `be5c1b051fb6c0153e683816af51d9c2d190d8f56189ffc363724463cd38a6a8` |
| Completed teacher labels | `04ccf7e0161b047318b1c905762f4e078df2c95517e4480534bc29e6b0e5dfc1` |
| Starting step-512 weights | `2643e51526335e5a33a67370bf1fa70ddf3c6b2e64b31550ad6ca033f9430a22` |
| Stockfish binary | `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0` |

Private data and weights stay under `data/private/chess-move-policy-v5/`. The original intake snapshot and later pre-label snapshot remain separate. Teacher jobs use at most six Stockfish processes with one thread, 32 MB hash and a 50,000-node budget per root. Each root starts a new UCI game; the final legal bestmove must agree with the last individual score event's PV. Score bounds come only from that same event. Every completed or failed row is flushed to a create-only chunk journal before aggregate labels are written. An existing label-attempt marker prevents replay after interruption.

## Training and measurement

The root coordinator owns CUDA execution. Continue all nine-million parameters from the existing selected checkpoint using AdamW, learning rate 0.00001, batch size 64 and 4,096 updates. Save checkpoints 0, 256, 512, 1024, 2048 and 4096. Choose by development raw teacher agreement, then raw legality, then earliest checkpoint. Save that decision before model scoring on either held-out panel.

Compare the starting checkpoint with the new selection on the same fresh 512-root holdout. The forecast panel makes three raw predictions in sequence, updating the board with the model's own move after each legal choice. Neither side receives a legal mask, teacher continuation, solution or future board. Save the complete raw forecast before scoring exact one-, two- and three-ply agreement with the fixed root Stockfish PV. Report legality and all terminal, illegal, failed and short-reference outcomes. All 128 planned roots remain in the denominator; available teacher support is reported separately.

The raw classifier still has 1,968 unrestricted move classes. Legality cannot be rescued and presented as learned understanding. A failed backend evaluation stops further backend calls. Training checks the owned cancellation file, deadline and read-only memory reserves every 64 updates. Fatal setup or execution errors retain `failure.json` and existing journals/checkpoints.

## Verification and current status

`software-tests-v3.txt` records **29 passing checks**, including 24 new checks for selection/exclusion boundaries, ignored solution tails, individual score-event bounds, final-PV coherence, durable recovery, illegal forecasts, failed backend accounting, terminal boards and selection order. Five existing v3 evaluation checks also pass. These are software fixtures, not model-performance measurements. The earlier 26-check pre-label run remains in `software-tests.txt`.

CPU source intake and all **33,920 Stockfish labels completed**, with zero recorded failures, in 233 seconds. Independent review then found that a forecast backend failure could cause later roots to call the failed backend again. After the teacher process exited and before any learned model call, `protocol-amendment-v3.json` froze a repair that latches the first such failure, retains remaining IDs as not run, saves raw and score files, and stops before another condition. It binds the exact completed labels and teacher-source snapshot; no engine call was replayed.

GPU training and both final evaluation panels are complete. The independent
audit verifies 75 closed files, all 4,096 finite-loss/gradient updates, unchanged
starting tensors, development-only selection and both final checkpoint hashes.
The table above reports the observed tradeoff without a broad strength claim.

The root coordinator uses the final amended protocol for training:

```powershell
.venv-soccernet/Scripts/python.exe scripts/chess_move_policy_v5.py train --protocol experiments/chess-move-policy-v5/protocol-amendment-v3.json
```

The training and label commands are create-only and must not be rerun against
this completed attempt. These development, holdout and forecast observations
are now spent. A successor needs its own protocol and fresh evaluation games.

Stockfish agreement measures agreement with one bounded teacher configuration. It is not a mathematical chess proof, Elo, a measure of coaching quality or evidence that the model understands soccer. The tactical convenience source and unknown original-pretraining overlap remain limitations even if the fresh evaluation improves.
