# Move-only local chess pilot v3

**Candidate result: higher agreement with the bounded teacher, with two newly illegal raw predictions. No automatic promotion.**

The previous two language-model fine-tuning pilots reduced agreement. This experiment changes the task to move-only classification, using the small public ROOK-CLF-9m specialist. It does not train natural-language commentary or establish chess understanding in a broader sense.

## Frozen experiment and execution

The model is pinned to `jrahn/ROOK-CLF-9m@a02db44faf1c495a85f9dd725584d197c58294a1`. Its native 78-token FEN representation and 1,968 move classes were checked against pinned upstream source and local metadata. No remote Python module was executed. A differential check on 261 finite FENs matched the reviewed upstream preprocessing and tokenizer IDs. Legitimate positions exceeding the native counter widths are explicitly unsupported; they must remain in evaluation denominators.

The [protocol](../research/chess-classifier-protocol-v3.json) was frozen before selection and model measurement. The exact retained CC0 Lichess prefix supplied 8,192 training games, 256 development games and 256 held-out games. All prior project games and both before/after setup board roles were excluded. Independent reconstruction verified 8,704 unique new games and 17,408 distinct board-role keys with no prior or cross-split overlap. Unknown overlap with upstream pretraining remains possible.

Eight one-thread Stockfish 19 workers labeled the positions in 32.97 seconds using 32 MiB hash per worker, hash clear per position and a 20,000-node budget. The target is the actual completed UCI bestmove, not a natural-language rationale or an assumed optimal move. Score observations retain the last individual score event and its bound flags; they are never model inputs or training targets. Bound events occur in 2,210 training, 59 development and 65 holdout records. All completed bestmoves are legal.

The RTX 5080 ran 512 real AdamW updates, batch size 32, learning rate 0.00001, with 16,384 example presentations. All 8,192 training positions encoded successfully. Checkpoints at steps 0, 128, 256 and 512 were compared on development data only. The declared raw-agreement, raw-legality, earliest-step rule selected step 512. Selection was saved before opening the holdout, and rejected checkpoints were not evaluated there. Training plus development checks took 21.44 seconds; peak CUDA allocation was 702,262,272 bytes.

## Retained results

| Metric | Base development | Selected development | Base holdout | Selected holdout |
|---|---:|---:|---:|---:|
| Raw legal moves | 254/256 | 253/256 | 256/256 | 254/256 |
| Raw teacher matches | 169/256 | 194/256 | 142/256 | 167/256 |
| Raw top-three teacher coverage | 225/256 | 227/256 | 202/256 | 226/256 |
| Legal-mask teacher matches | 171/256 | 196/256 | 142/256 | 168/256 |
| Cross-entropy | 1.1763 | 0.8502 | 1.5032 | 1.1104 |
| Failed/unsupported cases | 0/256 | 0/256 | 0/256 | 0/256 |

On this holdout, raw agreement rose from 55.47% to 65.23%, a descriptive gain of 9.77 percentage points. Thirty cases changed from wrong to matching and five changed from matching to wrong. Raw legality fell by two cases. Legal masking is rule-assisted selection and remains separate; it cannot hide the raw errors.

This is a tactical-prefix convenience sample and one training run with development checkpoint selection. It does not establish Elo, general playing strength, statistical significance, commentary faithfulness, teaching value or sports transfer. The games, model architecture and teacher budget also differ from v1/v2, so their percentages are not a matched cross-pilot model comparison. The selected weights remain an experimental candidate.

## Debugging and independent checks

An independent source/artifact review reconstructed the exact selection, checked hash bindings and no-answer-input boundaries, and recomputed all 1,536 retained logit rows across four development and two holdout conditions. Rankings, legality, teacher matches and cross-entropy agree. The original frozen receipt and execution snapshots are preserved; a separate immutable verification manifest binds them to tokenizer metadata, the optimizer log, model files and later packaging evidence.

Root integration caught a packaging omission: saved checkpoints lacked native tokenizer metadata. A separate helper now packages the selected checkpoint, verifies identical weight hashes before/after and rejects mapping mismatches or conflicting metadata. Live base and selected-policy commands both ran on the initial board. Those smoke calls did not reopen the evaluation set.

The frozen run completed every case. A future-run robustness issue was also repaired: model exceptions or malformed logit shapes now record failures for the affected batch and mark remaining rows not run, instead of abandoning the planned denominator or repeatedly calling a failed backend. Synthetic regression checks exercise that path. No frozen training, selected weights or holdout logits were regenerated for this repair.

## Explicit local use

`chess_classifier_policy.py` requires an explicit local model directory. Raw mode abstains on an illegal prediction. `--legal-mask` opts into rule-assisted selection while retaining the raw result. Logits are rankings, not engine scores or calibrated probabilities. For an existing selected checkpoint, package its metadata first:

```powershell
& .\.venv-soccernet\Scripts\python.exe .\scripts\chess_classifier_package.py --base-dir .\data\private\chess-classifier-v3\base-model --checkpoint-dir .\data\private\chess-classifier-v3\checkpoints\step-512
& .\.venv-soccernet\Scripts\python.exe .\scripts\chess_classifier_policy.py --fen 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' --model-dir .\data\private\chess-classifier-v3\checkpoints\step-512
```

Full receipts, source bytes, logits and weights remain private local artifacts. Portable aggregate evidence is in `experiments/chess-classifier-v3/summary.json`. The next research question is how to retain or improve raw legality while preserving agreement gains on new games. Commentary remains a separate unmet capability gate. Implementation and candidate notes were prepared with Codex assistance.
