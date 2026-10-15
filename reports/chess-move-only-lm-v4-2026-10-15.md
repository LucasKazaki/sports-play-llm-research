# Move-only language-policy pilot v4

**A modest held-out agreement gain came with six newly illegal predictions. The trained weights remain experimental.** Raw matches to the bounded Stockfish teacher rose from 58/256 to 65/256; raw legal actions fell from 256/256 to 250/256. This does not establish stronger play, reliable chess rules, faithful commentary or sports competence.

## Question and frozen execution

The earlier v1/v2 language-model pilots trained move lists and numeric scores and reduced action agreement. This [separately frozen protocol](../research/stockfish-move-only-lm-protocol-v4.json), committed as `5b9b413` before selection or calls, trains only the completed Stockfish bestmove string plus EOS. The original `jrahn/ROOK-LM-124m@c16158d399a61847cbcb616ecf2e36e6c96e16ca` base is used; no earlier trained weights initialize v4.

The input is the native `P:` FEN padded to 90 characters followed by `M:`. Joint tokenization masks the exact inference prefix and rejects a token crossing into supervision. Candidates, score tokens, PVs, future boards, themes and annotations never enter the input. Both conditions generate greedily for at most 16 tokens. The first whitespace-delimited token, after an optional initial `M:` marker, must match UCI syntax and be legal. The policy never searches later text for a rescue, selects `B:` output or silently masks illegal actions. Full continuations and token IDs remain retained; a completion can still contain trailing candidate text.

This first-M task deliberately differs from v2's full-native B-first policy. The dataset, teacher budget and training schedule also differ. Cross-pilot percentages therefore do not isolate a cause or rank model strength.

The exact retained 4 MiB CC0 Lichess prefix supplied 8,192 new training games, 128 development games and 256 held-out games. All 13,112 historical/v1/v2/v3 games and 26,322 prior source-before/setup-after/historical board keys were excluded. An independent reconstruction reproduced the source-order selection and every rejection. The new 8,576 games and 17,152 board-role keys are distinct, with no prior or cross-split overlap. Unknown upstream pretraining overlap remains possible.

Eight one-thread Stockfish 19 workers generated legal completed-bestmove labels with 32 MiB hash, hash clear per position and 50,000 nodes each, in 50.07 seconds. Retained score events are observations only and are never training targets; bound observations occur in 1,838 training, 35 development and 53 held-out records. The teacher is a bounded search, not perfect chess truth or a source of invented natural-language rationales.

The RTX 5080 executed 2,048 AdamW updates, batch size 32, learning rate 0.000002, with 65,536 example presentations. Parameters remained float32 with bfloat16 autocast. Training and the intervening development checks took 167.20 seconds; peak CUDA allocation was 6,075,981,824 bytes. Observed utilization snapshots reached 92–95%, with system-memory headroom retained.

## Selection and retained results

| Checkpoint | Development teacher matches | Development legal moves |
| --- | ---: | ---: |
| Base, step 0 | 32/128 | 128/128 |
| Step 256 | 32/128 | 128/128 |
| Step 512 | 30/128 | 128/128 |
| Step 1024 | 33/128 | 127/128 |
| Step 2048 | 34/128 | 124/128 |

The predeclared agreement/legality/earliest-step rule selected step 2048. Its weight identity was saved before opening the holdout; only the base and selected weights were evaluated there.

| Metric | Base development | Selected development | Base holdout | Selected holdout |
| --- | ---: | ---: | ---: | ---: |
| Accounted / planned | 128/128 | 128/128 | 256/256 | 256/256 |
| Parsed first UCI token | 128/128 | 128/128 | 256/256 | 256/256 |
| Raw legal actions | 128/128 | 124/128 | 256/256 | 250/256 |
| Raw teacher matches | 32/128 | 34/128 | 58/256 | 65/256 |
| Backend/not-run failures | 0 | 0 | 0 | 0 |

Held-out raw agreement rose from 22.66% to 25.39%, a descriptive gain of 2.73 percentage points. Twenty-five cases changed from wrong to matching and eighteen from matching to wrong. Six formerly legal cases became illegal; none recovered legality. Development completion-token NLL fell from 3.9543 to 3.0321. Lower training-objective loss does not erase action errors or establish understanding. This is one convenience-sample run with checkpoint selection, without a significance or Elo claim.

## Checks and explicit use

Independent preflight review passed 26 checks and verified exact native tokenization/masking on all 8,320 training/development rows. Independent intake review reconstructed all exclusions and all 8,576 legal labels and provenance bindings. After execution, independent review decoded and reaccounted all 1,152 retained rows across five development and two holdout conditions, verified selection/order and hashes, and checked all 148 selected-weight tensors on CPU for finite float32 values. Review made no additional model or engine call.

A separate explicit-use command requires a local model directory, retains the raw text/token IDs and abstains on an illegal first action. Three additional policy checks pass; the combined focused set is 29. Live base and selected commands both ran on the standard initial board and selected `e2e4`. Those two post-run smoke calls did not reopen the holdout. The frozen training script, protocol, receipts and weights were unchanged.

```powershell
& .\.venv-soccernet\Scripts\python.exe .\scripts\chess_move_only_lm_policy.py --fen 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' --model-dir .\data\private\chess-move-only-lm-v4\checkpoints\step-2048
```

The [compact evidence](../experiments/chess-move-only-lm-v4/summary.json), independent source review, intake audit and retained-output audit are committed. Full source bytes, generated tokens, weights and immutable bindings remain private locally. Historical missing-evidence compatibility failures remain separate; a green full-repository suite is not claimed. The next question is whether training can retain raw rule compliance while improving move choice. Commentary remains a separate unmet capability gate. Codex assistance is recorded; this is a review candidate, not formal research promotion.
