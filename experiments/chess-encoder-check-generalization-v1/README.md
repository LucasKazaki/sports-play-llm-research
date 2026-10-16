# Check-head coverage diagnostic

The previously selected encoder check head scored 458/512 on its fresh matched panel, but that panel contained no pawn moves, king moves, discovered checks or double checks. This separate diagnostic targets those missing cases. It compares the saved epoch 4 head with its original epoch 0 head; it does not train, tune or select either model.

Request 16 pairs in each of four allocations: king moves, pawn moves, double checks and remaining discovered checks. A checking move may have several flags. Allocate it to king first, then pawn, double check and remaining discovered check; retain every flag in evaluator metadata. Each source game supplies at most one pair. The source is the already retained, hash-pinned CC0 Lichess Parquet, limited to its first 500,000 rows and first setup token. No source answer tails, themes, additional plies or new downloads are used.

Both moves in a pair share the current board, moved piece type and capture/victim category. King and pawn pairs also share the exact source square. Double and remaining discovered pairs instead require a different same-type piece instance for the nonchecking move. This contrast change was declared before intake: an ordinary knight uncovering a rook check cannot supply a same-origin nonchecking alternative. A legal authored fixture demonstrates both a discovered check and double check, zero nonchecking moves by that knight, and a valid nonchecking move by another knight. These categories must not be described as matched-origin evidence.

The reservation audit binds 109,032 old games and 250,895 canonical board keys, including all 512 reserved coach holdout games. It checks the earlier registries, every old head root and selected successor, all 96 Queen pool roots and every coach source root using metadata only. Coach held references and teacher contents remain unopened. Every new before/current/checking-successor/nonchecking-successor path must be novel. Future generated boards and unknown encoder pretraining overlap are outside this claim.

The complete plan has 64 pair slots and 128 move slots. If the fixed source scope cannot supply a category, retain its shortage and matching constraints. Do not invent examples or count unavailable source slots as model errors. Report requested coverage, constructed examples and actual prediction outcomes separately. This deliberately targeted small tactical panel cannot establish general chess, move strength, Elo or coaching quality.

The implementation is CPU intake only. It contains no model, feature extraction, engine or GPU calls. Fourteen authored software checks and the metadata reservation preflight pass; independent review precedes actual intake. The current protocol-v2 checks host reserves before even accessing the source iterator; the unexecuted earlier source, tests and protocol remain in archive/draft-v1. Future inference requires an independently audited actual cohort and a separately frozen root-owned plan, using only current FEN and selected legal UCI with the original feature pipeline and raw zero threshold.

The authorized CPU intake is now closed and independently audited. It filled all 64 pairs and 128 moves, exactly 16 pairs in each allocation, with no source shortages. The 64 original games and 256 path board keys are distinct and novel against the frozen registry. Selected source ordinals range from 108,209 to 172,642. Dataset SHA-256 is 50a2046969610c94e42d87a6e70c2689016c78b620134800cfc5fa8bf28b9dbb. The audit verified every original Parquet location, setup token, legal label, matching category and deterministic pair choice. No model or engine calls occurred.

The separate inference-only candidate retains both raw condition ledgers and all requested source slots before backend setup. Its new cache contains only the original 3,072 current-board features and native move indices, bound to input, encoder and source hashes. It opens labels and the case-to-stratum mapping after both saved epoch 0 and epoch 4 conditions complete. There is no optimizer, new checkpoint choice or rule-based replacement. Twenty-six combined CPU checks pass; source and final inference-plan review are required before root dispatch. Actual check-generalization results remain unavailable until that run closes.

Before any inference, a second version strengthened the GPU running reserve
from 512 MiB to 1 GiB, matching the current overnight policy. Other reserves,
scientific functions, cohort, saved heads, raw threshold and label embargo are
unchanged. The earlier inference v1 remains unexecuted and preserved. Use
`chess_encoder_check_generalization_eval_v2.py` with `inference-protocol-v2.json`.
Independent review reproduced all 36 CPU checks, verified the exact source and
protocol bindings, and confirmed that the earlier scientific function bodies
match after normalizing the guard call. The exact review is retained in
`inference-source-review-v2.json`. This is source readiness; no new inference
or quality result is claimed here.
