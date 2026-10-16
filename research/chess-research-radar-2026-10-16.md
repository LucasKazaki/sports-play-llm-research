# Chess research radar: October 16, 2026

This refresh supports the user's repeated research, plan, implement, test and
debug cycle. Two paper-index searches cover July–October 2026 explanation work
and 2025–2026 state tracking, evaluation and brittleness. The retained JSON
records the queries, returned papers and reading depth. Queen, ACT-Eval and the
faithfulness study were checked through selected full-text passages; other
entries below use abstracts or metadata. This is a bounded review, not an
exhaustive survey. Reported paper results are not local project results, and
arXiv availability alone does not establish peer review.

## Findings that change the work

| Primary source | Evidence and implication for this project |
| --- | --- |
| [Queen](https://arxiv.org/abs/2610.03695), updated October 5 | An expert board encoder, staged grounding curriculum and iterative explanation distillation address different weaknesses. The local NF4 port and narrow LoRA pilot are separate experiments, not reproductions of the paper's training or strength. Keep the encoder benefit, but test generated claims and alternatives independently. |
| [ACT-Eval](https://arxiv.org/abs/2608.04240), updated August 6 | Commentary evaluation separates factual correctness, expert-concept coverage and move-quality judgment. It checks claims against the appropriate replayed board. Next evaluation work should bind each claim to its actual branch and state, retain unsupported claims, and report coverage alongside factual precision. Its fallible judge and limited human calibration do not certify every claim. |
| [Explanation faithfulness](https://arxiv.org/abs/2609.22245), updated September 22 | Move recoverability changes when explicit hints are masked and when the decoder changes. A supplied-move explanation is not independent move prediction, and a plausible narrative does not establish faithful reasoning. Keep these modes and scores separate; later faithfulness tests need predeclared controls. |
| [ChessQA](https://arxiv.org/abs/2510.23948) | Structural knowledge, motifs, short tactics, position judgment and semantic descriptions require different tests. The current direct-check head and tactical puzzle panel cover only part of that spectrum. Add fresh diagnostics by category before claiming general understanding. |
| [Brittleness testing / GAMBIT](https://arxiv.org/abs/2605.17565) | Puzzle scores can conceal fragile pattern matching. Compare legal distribution shifts and counterfactual positions under a separate protocol. Verifier-assisted gains must stay distinct from raw model behavior. |
| [Chess-World-Model](https://arxiv.org/abs/2605.30100), updated May 29 | Exact state tracking over real games and random legal play tests rule generalization. Add long-history and out-of-distribution state probes rather than extrapolating from one-step check recognition. The paper's architecture comparison does not justify swapping this project's backbone without a matched local experiment. |
| [Strategy verbalization](https://arxiv.org/abs/2607.11486) | Main-line play and concept labels alone do not cover strategic explanations. A later research panel should include alternatives and qualified human usefulness judgments. No copyrighted commentary corpus is acquired from this discovery. |

## Official release check

The official Queen repository HEAD still matches local source revision
`c372da22ca75e95c3c79bee8a83c220fc54d0dcb`. The public PAWN-8 model API still
reports `5027687fac08b64b2403b13aca5b198e68294fe9`, last modified October 4.
These were read directly on October 16; no new source or weight download was
needed. Keep those pins during the experiment. A newer software release is not
automatically a compatible or better experimental condition.
[Official code](https://github.com/queen-project/queen),
[official model](https://huggingface.co/princeton-nlp/queen_pawn-8).

The standing [SoccerMaster watch](soccermaster-watch-2026-10-16.md) also records
an unchanged visible paper/checkpoint and an additional direct metadata check
confirming the prior code HEAD. This preserves the sports research radar;
chess remains the only active capability domain and no sports result follows.

## Current cycle and next experiments

The first coaching pilot completes 20 confirmed optimizer updates and 160
confirmed backward passes, then stops at the unchanged 4 GiB Windows commit
reserve. A following microbatch has a persisted start intent but an unknown
backward outcome. There is no saved post-training checkpoint, selection or
held-out inference. Eight baseline development answers and 64 loss calculations
are retained. This is a resource/debugging result, not a model improvement.

1. **Backend reliability:** test a separately versioned memory-lifetime change
   with process-private and CUDA allocated/reserved observations, a spent long
   development request, and a fixed multi-update training qualification. Release
   only inactive cache; preserve live weights, gradients and all reserves. The
   optional demo CPU classifier is temporarily disabled to reduce owned memory.
   Do not close unrelated applications or silently resume the failed attempt.
2. **Learning:** only after qualification and independent review, start a
   separately identified full pilot from the original base with the same frozen
   train/development data and untouched held references. Save development-only
   selection before matched evaluation. All original failures remain visible.
3. **Factuality:** extend evaluation beyond the present exact check/capture
   grammar to branch-bound occupation, material and protection assertions, with
   explicit abstention for unresolved references. Reuse the existing evaluator
   kernels where sound; do not treat a keyword match or legal main line as full
   prose verification. Begin with known authored failures, not held-out answers.
4. **Coverage and teaching:** plan fresh quiet/positional, defensive and endgame
   cases and later expert review. The current 16-game tactical-source panel
   includes useful move types but cannot establish broad coaching competence.

The [UMD research-fit note](chess-umd-research-readiness-2026-10-16.md) records
official guidance, source dates and unresolved institutional questions. Current
work can support research review; neither institutional approval nor the
repository's commentary/shareable-candidate gate has been granted.

## Rule for the next iteration

Record the question, measured failure, primary source and version, bounded
hypothesis, frozen data and plan, exact implementation, actual execution,
debugging evidence, independent verdict and next decision. A useful iteration
may reject a model change or confirm no material literature update. It must not
turn more calls, lower loss, fluent prose or a passing software test into a
capability claim. Keep the live UI clear, accessible and explicit about what
Stockfish, deterministic rules and each learned model actually supplied.

Refresh official paper/project/release surfaces before choosing a new method
or updating a dependency. Preserve pinned versions during a run, log material
deltas, and verify rights and compatibility before acquisition or execution.
Hourly follow-ups retain the existing October 16, 09:00 Eastern cutoff; this
steering adds no new scheduler or indefinite extension.
