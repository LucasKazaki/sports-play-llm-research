# Learning check detection from an expert board representation

This experiment tests whether a small learned head can distinguish checking and nonchecking selected moves from LC0's current-board representation. The earlier text-only Qwen check experiments remain separate. Changing the representation is a hypothesis; software tests do not establish that the new model understands chess.

The frozen encoder is Queen PAWN-8's BT5-1024x15 network, from model revision `5027687fac08b64b2403b13aca5b198e68294fe9`. Its local encoder weights have SHA-256 `a72807f43a9b7e89b143bd6e25067315a0a4312a1340c865141ae763f393862e`. The pinned encoder, FEN-plane module and reviewed target-only loading helper execute. The Queen language decoder, cross-attention bridges, engine references and LC0 policy/value outputs never enter this classifier.

## Inputs and learning

The complete inference packet contains the current six-field FEN and one selected legal UCI move. Extra fields, including previous/future boards, history, SAN, check labels, solutions and PVs, are rejected. Empty history uses the pinned upstream FEN-only synthesis of missing history planes. It cannot recover the actual game history.

The frozen encoder returns 64 current-board square states of width 1,024. The head receives the mean state, the selected source square's state and the selected target square's state. These 3,072 values are concatenated with separately learned source and target embeddings of width 32 and a promotion embedding of width 8. Black squares use LC0's native rank mirror, square XOR 56. A fresh `3144 → 512 → 128 → 1` ReLU MLP learns binary check detection; all 1,680,169 head parameters are trained. The encoder remains frozen.

Predictions use the raw logit threshold zero, equivalent to sigmoid probability at least 0.5. There is no class mask, rule replacement or check calculation in inference. Deterministic chess rules validate that the selected move is a legal input; check truth is confined to supervision and scoring.

## Data and frozen selection

Reuse exactly the balanced-v2 training inputs and labels: 8,192 original-game pairs, or 16,384 moves. Reuse its 128 development pairs, or 256 moves, for checkpoint selection. Its old heldout examples never enter training or selection. This reuse is declared; the development set is not fresh evidence.

After the Queen benchmark dataset exists, freeze its exact identity in this experiment's protocol. Then select 256 fresh original games, each providing a matched pair of legal moves from the same piece and capture category, with one checking and one nonchecking move. The single heldout panel therefore contains 512 moves. Use deterministic source order and pair tie-breaking, consuming only the pinned CC0 Parquet's first opponent setup token. Never consume puzzle solution tails or themes.

Fresh intake excludes the historical registry, latest matched-check diagnostic, every balanced-v2 game and before/current/selected-successor board, every V5 root, every V6 fresh root including unused forecast candidates, and every Queen benchmark split. Original pretraining overlap is unknown. The matched tactical pairs exclude promotion, castling and en passant; the promotion input contract is software-tested but this panel cannot establish special-move competence.

Exact canonical current FENs are deduplicated for encoder work. Each requested move still has its own input hash, cached 3,072-value vector and source/target/promotion indices. Cache manifests contain input identities and feature bindings, without labels or evaluator features. Extraction of new heldout features cannot begin until development selection has been saved.

Train eight epochs with FP32 AdamW, learning rate 0.001, weight decay 0.01, batch 256, binary cross-entropy with logits and gradient norm at most one. This is 512 planned optimizer updates. Save epochs 0, 1, 2, 4 and 8. Select highest development correctness, then most complete pairs correct, then earliest checkpoint including the untrained baseline. Save selection before any heldout learned calls.

On the same 512 new moves, report majority-false and saved untrained-head baselines alongside the selected head. Retain TP/TN/FP/FN, checking and nonchecking recall, complete-pair correctness, invalid predictions, failures and all not-run requests. The first backend failure stops later calls and conditions. Feature attempts are journaled before calls and completed shards are saved durably. Head evaluation journals batch intent and completion and updates its full condition ledger after each event. An interrupted started batch remains unknown, while later requests remain not run; interrupted work is not silently replayed. Each computational phase is create-only.

## Execution and rights

The root coordinator owns all pretrained extraction and actual head learning. CPU tests use authored boards, synthetic states and a randomly initialized head. Read-only resource checks, the owned `CANCEL` file and a bounded phase deadline apply before model loading and throughout execution. The stable `chess_queen_materialize.py` helper initializes on the meta device, establishes BF16 floating-buffer dtype, allocates target storage and strictly copies pinned weights; integer policy indices stay int64. This avoids a temporary CPU FP32 model. Its function body is exactly the reviewed decoder adapter's loader, isolated so decoder changes cannot alter this experiment's dependency. The encoder is released before cached-feature training.

The [Queen source](https://github.com/queen-project/queen/tree/c372da22ca75e95c3c79bee8a83c220fc54d0dcb) is Apache-2.0. The [publisher model card](https://huggingface.co/princeton-nlp/queen_pawn-8) identifies the LC0 component and states that upstream component terms apply, without asserting a blanket license for the combined weights. Retain notices and local acquisition evidence; make no permissive redistribution claim. The existing user authority permits private local experimentation. This experiment does not download new data, publish weights or contact anyone.

Current status: **41 CPU software checks passed and source intake is complete.** Final protocol `a72ffa9df05d1622688bfba2b9a749db2dfc157ea618c803e0f7a3800fff567a` passed independent review before intake. The final `protocol-v2.json` binds the actual 96-game Queen pool and stable loader. The original `protocol.json` is preserved unexecuted; this pre-intake amendment changes only dependency isolation and the default protocol path.

The dataset contains exactly 16,384 training moves, 256 development moves and 512 fresh heldout moves from 256 distinct games. Reused train/dev input and label files are byte-identical to balanced-v2. All 256 new pairs have one checking and one nonchecking move; their source ordinals range from 104,377 to 107,180. The intake excluded 107,208 historical games and 242,535 board keys. Dataset SHA-256: `59de14730e88647c58d08b5089f1d5998a76f04e31bc2560ae948f12d52ee71f`. Independent actual-cohort review passed: all source rows, setup tokens, deterministic pairs, exclusions and 15 source snapshots verified, with zero historical or cross-game board overlap. The root-owned run is complete. It extracted current-board features, trained all 512 updates over 131,072 example presentations and selected epoch 4 using development data before heldout extraction. The selected head scored **458/512 (89.45%)** and **203/256 complete pairs (79.30%)**, compared with 235/512 and 24 pairs for the untrained head on exactly the same new panel. Majority-false scored 256/512 with zero complete pairs. Selected confusion: TP230, TN228, FP28, FN26. All outcomes completed, with no invalid or missing predictions. Independent closed-file review recomputed every score, checked all finite checkpoint tensors and training updates, verified all 8,576 feature shards and sealed 8,700 files. Public raw logits, inputs, labels, selection, losses and audit are in evidence/. Weights and feature tensors stay private. This narrow result leaves 54 mistakes and does not establish language understanding or coaching quality.

From the repository root, after the final protocol and review exist:

```powershell
.venv-soccernet/Scripts/python.exe scripts/chess_encoder_check_v1.py intake
# Root coordinator only, after independent review:
.venv-soccernet/Scripts/python.exe scripts/chess_encoder_check_v1.py run
```

The optional phases `features --scope training`, `train`, `features --scope holdout` and `evaluate` permit separate root-owned processes. `run` follows that same order. The `recover` phase only finalizes saved head-evaluation journals and makes no model calls. Check detection alone establishes neither explanation factuality nor move strength, Elo or chess tutor readiness.

Post-hoc coverage audit: all 256 positive heldout moves are direct checks; there are no discovered or double checks. The 512 moves cover queens (268), rooks (156), knights (64) and bishops (24), with no pawn or king moves. Correctness on this restricted panel does not establish those missing skills. Queens account for 31 of the 54 errors. The independently recounted details are in posthoc-coverage.json; this spent-panel analysis generates future hypotheses and is not new acceptance evidence.
