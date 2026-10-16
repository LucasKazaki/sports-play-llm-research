# ChessQA source audit — 16 October 2026

ChessQA is useful for a future diagnostic of skills beyond immediate check and
capture. Its released commentary is **not yet cleared here for training or
redistribution**, and selecting a source comment is a different measurement from
writing accurate coaching. This audit changes no experiment or admission decision.

1. **Pin code and data separately.** The official code is at
   `7b656c3316b5266acc596124610fa084f58ee717` (3 August 2026); the official dataset
   is at `18c5a789c6b358db1191642d31414a8bac540809` (1 November 2025).
   Both were read through unauthenticated metadata APIs at 10:08 UTC today. Treat
   this version gap as a reproducibility issue until exact files are compared.
   [Code revision](https://github.com/CSSLab/chessqa-benchmark/commit/7b656c3316b5266acc596124610fa084f58ee717),
   [dataset revision](https://huggingface.co/datasets/wieeii/ChessQA-Benchmark/commit/18c5a789c6b358db1191642d31414a8bac540809).

2. **Use its categories to design separate tests.** The benchmark spans
   Structural, Motifs, Short Tactics, Position Judgment and Semantic questions.
   Report task accuracy and answer-format failures separately; retain the
   distinction between geometric attacks and legal moves. This is a proposed
   future diagnostic, with no current model result.
   [Current official README](https://github.com/CSSLab/chessqa-benchmark/blob/7b656c3316b5266acc596124610fa084f58ee717/README.md).

3. **Keep commentary matching separate from coaching.** Semantic asks for one of
   four comments given a position and move. The paper describes ChessBase17
   comments cleaned and relevance-filtered with Qwen; these steps do not establish
   expert validation of every explanation claim. A high choice score would not
   establish faithful free-form teaching. A later coaching test still needs fresh
   explanations, claim checks and actual tutor feedback.
   [Paper, Appendix C.5](https://arxiv.org/html/2510.23948).

4. **Do not infer data rights from MIT code.** The current repository explicitly
   limits MIT to code and preserves source terms for benchmark data. The older
   dataset card labels the release MIT and expert-generated, but the purchased
   ChessBase commentary's applicable training and redistribution grant is not
   established by the inspected sources. Record that as unresolved, not as proof
   of either permission or prohibition. Lichess separately permits reuse of its
   CC0 database exports; that does not clear ChessBase text.
   [Repository provenance](https://github.com/CSSLab/chessqa-benchmark/blob/7b656c3316b5266acc596124610fa084f58ee717/README.md#licensing-and-provenance),
   [dataset card](https://huggingface.co/datasets/wieeii/ChessQA-Benchmark/blob/main/README.md),
   [Lichess source rights](https://database.lichess.org/).

5. **Freeze an evaluation set before any future training.** The current code
   reuses 100 semantic position–move–comment examples across four variants.
   Separate all variants of a base example, source games, repeated boards and
   duplicate comments together. Do not train on released answers and then claim
   an independent benchmark gain. Prior exposure in model pretraining remains
   unknown; a public benchmark score cannot prove its absence.
   [Official grouping/audit description](https://github.com/CSSLab/chessqa-benchmark/blob/7b656c3316b5266acc596124610fa084f58ee717/README.md#audit-benchmark-structure).

6. **Begin a later proposal with fresh, rights-verified positions.** Reuse the
   MIT construction ideas with preserved notices, pin the exact operational
   definitions, and create a small diagnostic from approved CC0 sources. Keep
   answers, correct commentary, after-positions and engine metadata outside the
   model packet. The current semantic builder stores both correct text and an
   after-FEN in metadata, so passing whole rows would leak evaluator material.
   Any selected-move condition must remain explicitly labelled. No new corpus,
   generation, training or evaluation is authorized or performed by this note.
   [Pinned builder](https://github.com/CSSLab/chessqa-benchmark/blob/7b656c3316b5266acc596124610fa084f58ee717/dataset/05_semantic.py#L201).

This is a source and research-design assessment, not legal clearance, university
approval, expert annotation validation, a systematic review or a coaching claim.
The adjacent ledger records observation versus inference and remaining gaps.
