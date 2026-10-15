# One later-video board: move choices and immediate facts

All four local move policies chose legal alternatives to the displayed Rh3. The two 9M classifier outputs were c3d3 and d1d8; both 124M policies returned c3d3 as their first move token. This disagreement does not establish incorrect play. No engine assessed the choices, and the displayed move is not a verified best-move label.

The fact model received Rh3 as input. Its selected adapter returned the exact eight-field schema with all eight immediate facts correct; its base response failed that schema. This is a separate task from choosing a move. The tested rook move makes no capture, gives no check and has no promotion. The primary adapter's failures on checking moves (0/13 positives correct) and its only rook promotion (0/1) remain unresolved. One easy noncheck case supplies no evidence that those failures were repaired.

## Source and constructed input

The illustration comes from a later board in a retained [GothamChess video](https://www.youtube.com/watch?v=sskvj1_ehx4&t=620s). Private frames requested at 620 and 630 seconds show the preboard and Rh3. These are inspected seek instants, not frame-exact transition-onset certification. The media and frame hashes are retained; no video, frame, transcript or full source ledger is published. Creator model labels do not authenticate model identities, prompts, tools or compute.

Four visible FEN fields define the board. Computational halfmove/fullmove counters of **0/1** complete the encoders' required input and are never represented as observed source clocks. Original game identity, complete history and mainline remain unresolved. Clock tokens can affect model outputs. Source-game and upstream pretraining overlap are unknown. This is an explicitly constructed illustration with **zero accepted holdout positions**, not a recovered complete source game.

## Frozen tasks and execution

The pre-call commit freezes six outcomes in three existing base/selected pairs. Classifier v3 step 512 and move-only v4 step 2048 were already selected. Fact-SFT step 512 comes only from its prior development selection and completed independent audit. This illustration makes no new selection, training or tuning decision.

The four move-policy inputs contain only the pre-move FEN. Their immutable raw closure precedes even hashing or opening the fact-input file; no later move call is allowed. Fact inputs contain the same FEN, the given legal Rh3 and a piece map derived only from the preboard. No later moves, post-move position, engine line, annotation, theme, expected facts or commentary enters generation. All six final raw outcomes seal before the separate CPU evaluator opens labels.

| Family | Base result | Existing selected result | Interpretation |
| --- | --- | --- | --- |
| 9M move classifier | c3d3, legal | d1d8, legal | Both differ from displayed Rh3; raw/masked diagnostics retained separately |
| 124M move policy | c3d3, legal | c3d3, legal | Frozen first-M parsing; both generations reach the 16-token cap |
| Qwen3-0.6B facts for given Rh3 | Exact schema fails | Exact schema and eight facts correct | One immediate-fact illustration; schema/task conformance matters |

The owned job exits successfully after 29.797 seconds, with all six calls completed and no cancellation, forced termination, runtime error or missing outcome. Ten healthy preflight samples precede 17 running samples. Minimum sampled available physical memory, commit headroom and free GPU memory are 10,924,072,960, 17,195,888,640 and 13,404,995,584 bytes. The maximum interval between running samples is 1.047 seconds. These are sampled observations, not instantaneous peaks.

## Audit and retained limits

The practical source review independently passes 45 finite checks, including a real CPU-only owned-process identity/timeout probe. A separate post-run audit verifies all 37 raw-seal bindings, the full six-outcome ledger, four-move closure, original/worker source identities, classifier input and all 1,968 scores, native language/fact tokens, EOS handling, strict parsing, independent rule facts and exact evaluator recount. It makes no new model or engine calls. A retained tokenizer BPE cleanup warning is not an error.

The public evidence mapping preserves original bytes and seal paths. Inert `.py.txt` snapshots identify the actual workspace execution path; no post-run adapted or relocated runner is described as executed. All 60 files of the pre-call freeze remain unchanged. The five-condition proposal, later six-condition freeze, fake test-discovery correction and reproduced deadline repair remain visible. No model-generation retry occurred.

This case supplies a richer source-visible board than the earlier opening illustrations, but it does not measure strategic ideas, planning, commentary, playing strength, generalization or a common accuracy across different tasks. It leaves the primary rare-positive failures intact. The work is Codex-assisted research engineering, not human-only authorship or formal research promotion.

[Results](../experiments/gotham-constructed-middlegame-v1/results/README.md), [summary](../experiments/gotham-constructed-middlegame-v1/results/summary.json), [independent retained review](../experiments/gotham-constructed-middlegame-v1/evidence/reviews/independent-retained-review.json), [evidence manifest](../experiments/gotham-constructed-middlegame-v1/evidence/manifest.json), [primary fact experiment](chess-fact-sft-v1-2026-10-15.md).
