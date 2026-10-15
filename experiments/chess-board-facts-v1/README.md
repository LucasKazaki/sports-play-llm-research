# Failure-inclusive immediate-fact diagnostic

The [report](../../reports/chess-board-facts-v1-2026-10-15.md) explains the small result and the interrupted execution. [summary.json](summary.json) records the complete planned denominator: 32 outcomes, 31 generation requests, 30 strict completed responses, one incomplete backend response and one unattempted call. There were no retries or weight updates.

FEN plus a selected legal move yielded 2/16 fully correct eight-field responses. Adding a full pre-move piece map yielded 5/16. This is a reused-source development diagnostic, with three captures, one check and no selected castle, en-passant capture or promotion. It supports no strength, commentary or broad-understanding claim.

| Evidence | Role |
| --- | --- |
| [archive/board-fact-protocol-v1.json](archive/board-fact-protocol-v1.json) | Exact pre-call protocol; historical status is preserved |
| [dataset.json](dataset.json), [generator-inputs.json](generator-inputs.json) | Source/setup roles, game identities and the exact FEN/UCI-only input records |
| [evaluator-labels.json](evaluator-labels.json) | Separate expected immediate facts; never opened by generation |
| [frozen-data.json](frozen-data.json) | Exact data/source bindings before calls |
| [evidence/raw-results.json](evidence/raw-results.json), [evidence/raw/](evidence/raw/) | Recovered full ledger and all 31 saved HTTP bodies, including the incomplete response |
| [evidence/file-recovery.json](evidence/file-recovery.json) | Explicit post-failure reconstruction and original byte hashes; no additional requests |
| [evidence/raw-seal.json](evidence/raw-seal.json), [packaging-map.json](packaging-map.json) | Fifty original private bindings; 44 public copies and six expressly private inventory/system artifacts |
| [evidence/evaluation.json](evidence/evaluation.json) | Separate evaluator result after recovery sealing |
| [archive/board-fact-independent-output-audit.json](archive/board-fact-independent-output-audit.json) | Independent prompt/input/binding and full-denominator recount |
| [archive/board-fact-independent-intake-audit.json](archive/board-fact-independent-intake-audit.json) | Independent source-order/game/board-role reconstruction before actual inference |

The alias is `qwen3.8-27b-local-q2k:latest`; actual retained backend identity is `qwen35`, 27.3B, Q2_K. The precise installed digest is in the summary and original before-call receipt. An alias is not release authentication. Exact requests, raw completion fields and timing observations are retained. None of the responses contains a thinking trace.

The original attempt failed with Windows virtual-memory exhaustion, a model-server allocation error and a caller-side `MemoryError`. Original bytes were not replaced. The report distinguishes the original failed process from the later file-only recovery. Host-specific paths in receipts and archived protocols are historical provenance, not a portable replay recipe. Unrelated local-model/process inventories and the full Windows event remain private; the selected-model identity and failure observations are recorded publicly.

## Active code is a post-run copy

The exact executed [runner](archive/board_fact_diagnostic.py.txt), [core](archive/board_fact_core.py.txt) and [tests](archive/test_board_fact_diagnostic.py.txt) remain separate from [scripts/chess_board_fact_diagnostic.py](../../scripts/chess_board_fact_diagnostic.py) and its repository core/tests. The active copy adds repository paths and explicit interrupted-finalization handling. Independent review of that later code found and repaired a pre-call attempt-counter error. It was not used for the retained model predictions.

Software checks require the repository's Python environment with python-chess and pytest:

```powershell
& .\.venv-soccernet\Scripts\python.exe -m pytest tests\test_chess_board_fact_diagnostic.py -q
& .\.venv-soccernet\Scripts\python.exe scripts\chess_board_fact_diagnostic.py --help
```

The 39 focused checks use finite board fixtures and a fake client. No live model, GPU or engine is required. They exercise input isolation, strict parsing, backend errors, interruption, seal tampering and truthful attempted/not-run counts when saving metadata fails.

A new acquisition or inference needs its own reviewed protocol/data identity, accessible private prerequisites, a new output directory and a coordinated memory/device budget. All sixteen games and both source/setup board roles in this panel are now spent development evidence and must be excluded from later training, selection and independent evaluation. The historical freeze procedure reconstructs this cohort; it does not supply a new one. Historical source-prefix files, prior private datasets and installed weights are not included in a fresh checkout. Existing or partial attempt directories are refused. Do not rerun this diagnostic to replace its failed outcomes. The practical checks here do not satisfy the separate formal commentary/promotion gate.
