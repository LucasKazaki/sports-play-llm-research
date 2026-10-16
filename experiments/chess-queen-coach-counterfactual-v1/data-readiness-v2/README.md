# Counterfactual recovery v2: closed corpus readiness

The single changed-context CPU recovery completed. The independent closed-corpus
audit passed with no blocking findings. All 3,168 planned Stockfish teacher
requests completed; failed, unknown and not-run counts are zero. The operational
sequence took 604.328 seconds, verified owned-engine exit before export and
cleanup, and released its resource-context lease. It made no learned model or
GPU calls.

The corpus contains 512 training roots with 1,536 examples, 32 development roots
with 96 examples, and a fixed 512-root reservoir. Its 16 selected held roots yield
48 input-only records. All reservoir games and board paths remain reserved.
This folder publishes none of those individual records or their references.

The independent auditor checked all 1,056 retained source locations and seeded
candidate choices, historical and cross-split exclusions, 3,168 intent/outcome
pairs, 223,662 incoming UCI lines, legal teacher paths and all six exact exports.
It checked 4,224 distinct board-role keys. It did not rerun selection over every
rejected source-prefix row; that coverage also relies on the frozen source and
retained scan/rejection accounting. No king candidates occurred in this cohort.
Outgoing search commands were not directly logged; their constrained behavior
is supported by the pinned executed source, rather than an outgoing wire trace.

The actual CPU tokenizer preflight passed for all 1,536 training and 96
development examples, including exact integer prefix masks, EOS and no
truncation. No model weights were loaded, CUDA was not initialized, and no
learned forward ran. The corpus reviewer validated that exact receipt and its
bindings without repeating tokenization.

`independent-corpus-main-result.json` is the exact aggregate projection approved
for this folder. The full private audit and its 98-entry sealed index remain
private. The two operational receipts are byte-identical exact copies. The
root-owner closure records the earlier operational closure; its then-pending
scientific audit is resolved by the later independent main result. Every exact
copy has a source, byte count and SHA-256 in `copies-manifest.json`.

These are node-limited engine targets, not human gold labels or perfect chess.
Selected candidates are forced moves, not global best-move claims or
independent first-move predictions. Independent review here was by a local
agent, with no human chess-expert validation. This is corpus and software
readiness only: it establishes no learned quality, coaching correctness, Elo,
trained-profile eligibility or UI activation. Exact training authorization and
any later evaluation remain separate decisions.
