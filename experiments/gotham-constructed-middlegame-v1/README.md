# Constructed-counter middlegame illustration — frozen before calls

This package freezes one source-visible board with explicitly constructed halfmove/fullmove counters of **0/1**. The original game's counters, complete history and mainline remain unresolved. It contains **zero accepted holdout positions** and supports no playing-strength, strategic-idea or commentary claim.

No illustration model or engine call has occurred. Root must verify this commit and final extension before granting a separate execution GO. The final extension is `execution-extension.json`, SHA256 `9df1a3fe206f7c2b5d356d4fbf73815d10b7ec9c34fa619b897f56c05f5627bb`.

The six planned outcomes form three family pairs:

| Family | Base condition | Existing selected condition | Task |
| --- | --- | --- | --- |
| 9M classifier | Fixed base | Step 512 from classifier v3 | Choose a move from the constructed FEN |
| 124M move language policy | Fixed base | Step 2048 from move-only v4 | First-M move from the constructed FEN |
| Qwen3-0.6B fact language model | Adapter disabled | Dev-selected native fact-SFT step 512 | Eight immediate facts for the given legal move |

The move conditions receive only the pre-move FEN. Their four raw outcomes close immutably before the fact-input file is hashed or opened. The fact conditions receive the same FEN, the selected legal move and a piece map derived only from that preboard. All six raw outcomes seal before a separate CPU evaluator reads the displayed move and expected facts. Raw classifier choices and legal-mask diagnostics remain separate. Move-choice and given-move fact results are never pooled.

`protocol.json` is the unchanged six-condition workspace plan, SHA256 `8c5313c2088ebbce8acbbd23df195b108f69c341237cc1f6305fd9875c66ba75`. The three input/evaluator copies preserve their original byte hashes. Runtime still uses the original workspace paths bound in that plan; these package copies are evidence.

`archive/reviewed-workspace-sources/` contains inert, byte-exact source and test snapshots. **The reviewed execution entrypoint is** `C:\Users\lucas\Documents\Codex\2026-10-15\go\work\gotham-constructed-middlegame-runner-v1\illustration_run.py`. No relocated or post-run adapted copy has executed. `freeze-manifest.json` maps copied evidence to the original paths and hashes; `execution-command.json` records the proposed command without running it.

The practical source review independently passed 45 checks: fake inference/resource/accounting cases and a real CPU-only exact-process/virtual-environment/timeout probe. No pretrained load, forward, GPU query or engine was used for these checks. This is practical engineering review, not a formal research-promotion receipt. Earlier proposals, the test-discovery correction, and the failing whole-job deadline regression are retained. The repaired 600-second budget includes setup and preflight; cooperative cancellation permits a separately bounded 30-second owned-process cleanup grace.

Only hashes and references identify the private source ledger and media. No video, frame, audio or transcript is copied. Original experiments, failed native SFT attempts and their disclosures remain intact. Codex-assisted engineering is explicitly attributed.
