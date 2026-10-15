# Three GothamChess opening illustrations

**Nine recorded predictions were legal. Each of three fixed policies matched one of the three next displayed video moves. This is not an accepted benchmark.**

The [report](../../reports/gotham-illustrative-v1-2026-10-15.md) explains the nine rows and source limitations. [summary.json](summary.json) is the exact retained evaluator result. There are **zero accepted holdout positions**. The whole original games are unknown, human editorial/mainline validation is pending, and the third scene includes nearby hypothetical branches and rewinds. Displayed moves are observations, not certified best moves or authenticated frontier-model answers.

## Inspect the evidence

| File | Purpose |
| --- | --- |
| [fen-inputs.json](fen-inputs.json) | The exact three FEN-only records read by generation; position IDs are bookkeeping only |
| [source-ledger.json](source-ledger.json) | Separate evaluator-only source links, histories, displayed moves and private observation hashes |
| [summary.json](summary.json) | All nine joined outcomes and per-condition counts |
| [evidence/raw-results.json](evidence/raw-results.json) | Native input IDs, raw classifier rankings, LM continuation strings/token IDs, failures and runtime observations |
| [evidence/raw/](evidence/raw) | Six full 1,968-class logit arrays; NumPy files contain no pickled objects |
| [evidence/raw-seal.json](evidence/raw-seal.json) | Sixteen original bindings sealed before reading evaluator labels |
| [packaging-map.json](packaging-map.json) | Map from the original sealed names to the committed copies |
| [independent-results-audit.json](independent-results-audit.json) | The original independent file/token audit |
| [packaging-results-audit.json](packaging-results-audit.json) | A second check of every binding, all six rankings, three decoded continuations and nine native inputs; no inference |
| [software-checks.json](software-checks.json), [software-tests.xml](software-tests.xml) | Thirty passing fake-backend/CLI checks; software evidence only |
| [manifest.json](manifest.json) | Candidate file sizes/hashes and exact executed versus post-run source identities |

No videos, frames, transcripts, model weights or creator commentary are committed. Private artifact paths and media hashes are provenance metadata; those files are not distributed. Acquisition for authorized private viewing does not grant creator-media training or redistribution rights. No creator material was used for training here.

The third condition is the original **base ROOK-LM-124m**, not the trained move-only v4 checkpoint. The classifiers are the existing v3 base and the v3 development-selected step 512. None was tuned or selected on these scenes. There is no pooled model ranking, ideas/understanding comparison, Elo estimate or research promotion.

## Executed source versus the repository utility

The nine predictions used the exact [archived runner](archive/sources/gotham_illustrative_eval.py.txt), SHA-256 `f43f6beaed6ec8770b15967db0d14ab30827605cdcbe0a7aa55fa3034294c8a8`. The [archived tests](archive/sources/test_gotham_illustrative_eval.py.txt) preserve the original 27-check version. The other source snapshots retain their original prepared roles: the classifier adapter was executed; the v4 training and original distillation scripts were pinned references only.

The active [scripts/gotham_illustrative_eval.py](../../scripts/gotham_illustrative_eval.py) is a **post-run repository copy**, with only these packaging adaptations:

- Test imports and adapter fixtures use the repository layout.
- Preparation finds test source adjacent to the runner or in `../tests`.
- `prepare --expected-plan-sha256` permits the explicit hash of a separately frozen **new** plan. Omitting it still requires the original hash.

The [original plan](archive/frozen-plan.json) remains byte-for-byte archival, including host-specific absolute paths and its pre-call `not_executed` status. The ledger's `models_evaluated_on_scenes: 0` describes intake before inference. Current results are recorded separately in the raw/evaluator artifacts. Do not edit either snapshot to make its historical status appear current.

**The original plan is not a portable replay recipe.** A fresh checkout does not include private models, tokenizer/config files or the old host's paths. A future execution needs its own reviewed and frozen plan with accessible FEN/evaluator paths, exact model/source bindings, a new output directory and coordinated device availability. Do not alter the old plan or reuse its output directory. The CLI requires an explicit GPU handoff before generation, and any started generation attempt is retained rather than replayed.

## Software checks only

From the repository root, after the normal dependency bootstrap:

```powershell
& .\.venv-soccernet\Scripts\python.exe -m pytest tests\test_gotham_illustrative_eval.py -q
& .\.venv-soccernet\Scripts\python.exe scripts\gotham_illustrative_eval.py prepare --help
```

All 27 original cases and three added plan/portability cases pass. The suite exercises fake weights/backends only: no neural model, Torch runtime or Stockfish is loaded by the runner's generation path. It verifies FEN-only input, failure-inclusive denominators, source/NPY tamper rejection before label loading, interrupted-attempt preservation, parser behavior, raw versus masked accounting, and explicit CLI plan identity. The new subprocess check prepares a fake plan from another working directory and binds the repository test source.

The packaging audit used local pinned tokenizer/config files to reconstruct inputs and decode retained tokens; it made no model or engine call. Public evidence inspection is possible without inference, but private tokenizer/model availability is still required to reproduce that exact token audit or any new model run. Codex assistance is recorded. Formal commentary/research promotion remains separate and unmet.
