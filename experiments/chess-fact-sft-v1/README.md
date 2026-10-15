# Local move-fact adapter: completed engineering candidate

The selected Qwen3-0.6B adapter reports all eight immediate move facts correctly on 242 of 256 held-out positions. It misses **all 13 checks and the only promotion**. Its 256 responses satisfy the exact schema; the frozen base satisfies it on zero positions. This comparison combines response-format/task conformance with factual correctness. It does not isolate a gain in chess knowledge or establish playing strength.

This is a Codex-assisted, development-selected candidate, with no default-model, commentary, or formal research promotion. [Summary](summary.json), [independent completed review](evidence/independent-completed-review.json), [publication byte bindings](evidence/reviews/chess-fact-sft-publication-bindings.json), and [report](../../reports/chess-fact-sft-v1-2026-10-15.md) retain the evidence and limits.

| Held-out measure | Frozen base | Selected step 512 |
| --- | ---: | ---: |
| Exact-schema responses | 0/256 | 256/256 |
| All eight facts correct under the frozen rule | 0/256 | 242/256 |
| Capture-positive cases correct | 0/17 (schema failure) | 17/17 |
| Check-positive cases correct | 0/13 (schema failure) | 0/13 |
| Rook promotion correct | 0/1 (schema failure) | 0/1 |

There are no positive castling or en-passant cases in development or held-out data. The base score does not establish absence of factual content or necessarily invalid JSON syntax. No extraction, format repair, retry or answer selection rescues a response.

## Method

Qwen/Qwen3-0.6B is pinned to `c1899de289a04d12100db370d81485cdf75e47ca`. Its native chat template receives a pre-move FEN, selected legal move and board-derived piece map. Eight immediate rule facts supervise training. Generator inputs contain no post-move board, future moves, engine continuation, theme, annotation or expected answer. This is rule-labelled fact supervision, distinct from earlier Stockfish-supervised move models.

The run consumes 8,192 training examples once in 1,024 updates, with 5,046,272 trainable adapter parameters and 596,049,920 unique frozen base parameters. The base digest is unchanged. Five fixed development passes each contain 128 positions. All-eight counts at steps 0/128/256/512/1024 are 0/111/115/118/118; the predeclared earliest-tie rule selects 512 before the held-out comparison. Both 256-response held-out batches are sealed before truth is opened. All 1,152 planned development/held-out generations complete without runtime errors, truncation or missing outcomes.

The game-disjoint cohort comes from a pinned CC0 Lichess puzzle shard. Source selection, prior-game/board exclusions, independent oracle and native token checks are retained in `evidence/cohort/` and the intake review. Unknown upstream pretraining overlap and convenience-source bias remain.

## Failures and verification

Attempt v1 stops on Windows process identity before importing/loading the model: 1,152 not run. Attempt v2 stops after 16 baseline-development responses and one progress-file artifact error, with zero optimizer updates and 1,135 not run. The exact lock holder was not captured. Separate amendments are frozen before each repair. The third attempt repeats those baseline prompts under unchanged settings and never pools or selects interrupted outputs. Failed attempts and executed sources remain separate.

Launch/persistence repair review records 83 passing focused software/CPU checks and one explicit deselection. Required historical compatibility tests separately record 9 failures, 5 passes and 89 errors from unavailable historical private fixtures. **The full repository suite is not green and historical acceptance is not restored.** The actual log is retained in `evidence/reviews/`.

The completed retained-file audit verifies raw seals, all 1,152 outcomes, native prompt/token replay, independent move facts, selection, source identity, unchanged base weights and resource reserves. A separately identified file-only re-audit binds exact publication inputs between identical complete inventories, with no new model/engine calls. The public manifest records 137 exact-byte files and hashes 19 private adapter/optimizer/journal artifacts. Base weights, source Parquet and GothamChess media stay local.

One publication-tooling attempt stops before output creation because Windows path sorting and string sorting order mixed-case filenames differently. Membership and file bytes are unchanged. The helper now compares canonical sorted names and rejects duplicates; the original helper is preserved in the workspace. This packaging issue is separate from training/evaluation.

## Inspect without new inference

Read `summary.json`, then full field supports/confusions in the retained held-out score files. `evidence/manifest.json` hashes public files relative to `evidence/`; the companion binds original local inputs. Implementations are under `scripts/`; exact executed copies are inert `.py.txt` evidence.

The existing environment is `.venv-soccernet\Scripts\python.exe`. A new training run requires pinned private base/source files, a new output directory, frozen protocol/amendments and resource-aware supervision. Do not rerun or overwrite a retained attempt as a reproduction shortcut. The current result requires only file inspection.
