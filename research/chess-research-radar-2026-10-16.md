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
| [Queen](https://arxiv.org/abs/2610.03695v1), v1 October 2 | An expert board encoder, staged grounding curriculum and iterative explanation distillation address different weaknesses. The local NF4 port and narrow LoRA pilot are separate experiments, not reproductions of the paper's training or strength. Keep the encoder benefit, but test generated claims and alternatives independently. |
| [ACT-Eval](https://arxiv.org/abs/2608.04240v1), v1 August 4 | Commentary evaluation separates factual correctness, expert-concept coverage and move-quality judgment. It checks claims against the appropriate replayed board. Next evaluation work should bind each claim to its actual branch and state, retain unsupported claims, and report coverage alongside factual precision. Its fallible judge and limited human calibration do not certify every claim. |
| [Explanation faithfulness](https://arxiv.org/abs/2609.22245v1), v1 September 5 | Move recoverability changes when explicit hints are masked and when the decoder changes. A supplied-move explanation is not independent move prediction, and a plausible narrative does not establish faithful reasoning. Keep these modes and scores separate; later faithfulness tests need predeclared controls. |
| [ChessQA](https://arxiv.org/abs/2510.23948) | Structural knowledge, motifs, short tactics, position judgment and semantic descriptions require different tests. The current direct-check head and tactical puzzle panel cover only part of that spectrum. Add fresh diagnostics by category before claiming general understanding. |
| [Brittleness testing / GAMBIT](https://arxiv.org/abs/2605.17565) | Puzzle scores can conceal fragile pattern matching. Compare legal distribution shifts and counterfactual positions under a separate protocol. Verifier-assisted gains must stay distinct from raw model behavior. |
| [Chess-World-Model](https://arxiv.org/abs/2605.30100v1), v1 May 28 | Exact state tracking over real games and random legal play tests rule generalization. Add long-history and out-of-distribution state probes rather than extrapolating from one-step check recognition. The paper's architecture comparison does not justify swapping this project's backbone without a matched local experiment. |
| [Strategy verbalization](https://arxiv.org/abs/2607.11486) | Main-line play and concept labels alone do not cover strategic explanations. A later research panel should include alternatives and qualified human usefulness judgments. No copyrighted commentary corpus is acquired from this discovery. |

## Source-date correction

Direct arXiv submission-history checks on October 16 show only v1 for Queen
(October 2), ACT-Eval (August 4), the faithfulness study (September 5) and
Chess-World-Model (May 28). Earlier notes incorrectly used the paper index's
`updateDate` values as revision dates. The ledger preserves those values as
index observations; the table now links to the checked paper versions. This
metadata correction changes no frozen experiment or result.

## Official release check

The official Queen repository HEAD still matches local source revision
`c372da22ca75e95c3c79bee8a83c220fc54d0dcb`. The public PAWN-8 model API still
reports `5027687fac08b64b2403b13aca5b198e68294fe9`, last modified October 4.
These were read directly on October 16; no new source or weight download was
needed. Keep those pins during the experiment. A newer software release is not
automatically a compatible or better experimental condition.
[Official code](https://github.com/queen-project/queen),
[official model](https://huggingface.co/princeton-nlp/queen_pawn-8).

The October 16 release check also identifies Stockfish 19 as the latest stable
release, tagged `sf_19` and announced on September 5, 2026. The recorded local
engine uses that version. This checks the version label, not the binary's byte
identity; all experimental binary pins remain in force. No engine was acquired
or upgraded. [Official release](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19),
[official release date](https://stockfishchess.org/blog/).

## Current cycle and next experiments

The full coaching v2 pilot completed 256 updates and 2,048 backward passes.
Independent review verified its frozen storage and development-only step-64
selection. Five of twelve recognized development claims were false. Its fresh
comparison then stopped at the unchanged commit reserve: 28 completed,
two partial, one failed and 33 unrun responses out of 64, including zero calls
to the trained panel. There is no matched quality result or trained UI admission.

The move-conditioned check/capture curriculum completed 3,168 engine requests
over 1,056 retained positions. Independent corpus review and complete CPU
tokenization passed for 1,536 training and 96 development examples. No new
counterfactual training ran: the strict 11:00 UTC admission expired during
Windows process-controller debugging. The retained curriculum has no selected
king moves and cannot establish broad chess coverage.

After three preserved monitor failures, a separately versioned cold controller
passed two spent-development requests and independent software audit. Three
initially live, image-unverified handles later signalled EXIT during a bounded
wait. Their identities remain unknown. This qualifies the original SFT runtime
profile on two used requests, not a new counterfactual-trained model, chess
quality or 96-request stability. The proposed fixed old trained checkpoint-256
versus checkpoint-64 comparison was not admitted before 11:30 UTC; all 96
responses remain unrun, with its reservation retained and no score.

The fixed encoder-head generalization attempt stopped at its unchanged commit
reserve after two frozen-encoder forwards and before any head prediction.
Concurrent CPU analysis is recorded as unquantified context; no exclusive cause
is assigned. No broader generalization result or same-cohort retry follows.
Whole-prose factuality, quiet and positional coverage, endgames and qualified
tutor usefulness remain open. The next independent work improves transparent
UI verification and retains the tested source, data and failure evidence.

The [UMD research-fit note](chess-umd-research-readiness-2026-10-16.md) records official
guidance and unresolved institutional questions. No institutional approval or
repository commentary/shareable-candidate promotion is claimed.

## ChessQA source and rights check

The October 16 official-source check pins code `7b656c3` and dataset `18c5a789`
separately. The Semantic task selects one source comment from four choices;
its 100 base examples recur across four variants. It cannot establish accurate
free-form coaching, and variants must remain grouped in any later evaluation.
The repository scopes MIT to code and preserves data-source terms. The older
dataset card does not resolve training or redistribution rights for purchased
ChessBase commentary. That text stays outside this project's training; the
current experiment continues with the recorded CC0 source. This is an unresolved
rights assessment, not legal clearance or a finding of prohibition.
[Pinned official provenance and audit notes](https://github.com/CSSLab/chessqa-benchmark/blob/7b656c3316b5266acc596124610fa084f58ee717/README.md),
[paper](https://arxiv.org/html/2510.23948).

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


## 11:44 UTC freshness and reading-depth supplement

Fresh public API responses still report the same Queen code and model revisions;
Stockfish 19 remains marked latest. The new receipt retains response hashes and
locally saved public metadata bodies. No dependency, weight or running source
changed. The bounded search is not an exhaustive field survey.

Selected full-text review of the [strategic-reasoning map](https://arxiv.org/html/2609.18286v1)
adds an evaluation caution: engine agreement, explanation faithfulness and human
assistance answer different questions. The preprint reports 84 core study
families and lacks complete independent duplicate coding. Our later tutor work
should keep its baselines explicit; no new model-quality or institutional claim
follows from this reading. It was already in the discovery ledger, so this
updates reading depth rather than inflating the paper count.

## Descriptive coverage cycle and scope correction — October 16, 12:27 UTC

A prospective, source-reviewed CPU audit inspected only the frozen TRAIN and
development exports. Fifteen authored software checks passed in both owner and
independent review. The single actual pass closed in 0.438 seconds; independent
recomputation matched every split aggregate and separately recounted board facts.
All 1,536 TRAIN and 96 development presentations passed the narrow schema/group
checks, and all five cross-split overlap counts were zero. These are 512 and 32
distinct source roots, each repeated in FREE and two selected-move presentations.
No model, framework, engine, GPU, held-reference or reserve-content access was
part of this audit. Process completion is not a general data-quality certificate.

Scope correction: earlier 2,112-candidate piece counts concerned supplied-move
pairs across the prepared corpus. They must not be read as all FREE targets.
TRAIN contains four FREE king targets (4/512 FREE; 4/1,536 overall), zero selected
king targets (0/1,024), and development has none (0/96). All 544 audited roots
start outside check. Selected TRAIN targets are queens or rooks in 828/1,024
presentations, while 130 of 132 selected captures take pawns. There are no
castling or en-passant targets; the one TRAIN promotion and one double-check
target are FREE. The intended selected checking/nonchecking contrast is exactly
50%; it does not establish ordinary-play representativeness or learned ability.

The frozen corpus and reservations remain unchanged. A future broader-coaching
design should predeclare separate coverage for in-check inputs, king and pawn
selected moves, varied capture victims and rare rules, record source shortages,
and retain a separately fixed generalization evaluation. This is a future design
decision, not authority to alter current held panels or restart expired phases.
Counterfactual TRAIN192 and the fresh comparison96 remain unrun. No coaching,
institutional approval or formal commentary/shareable-candidate claim follows.

Evidence: research/chess-counterfactual-train-dev-coverage-2026-10-16/.
Actual aggregate SHA256 e6730fb8d0d373236c0b53b1bfa7cd99b2a0d4cd40374f9d211e512abbec22a6;
independent closed-result review e18211457ebbf319c09ed4c2535259867c7bc97fd43a42021b41e6499cd57dcd.
