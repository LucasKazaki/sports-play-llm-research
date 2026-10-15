# Four-case development scoring worksheet v1 — 6 October 2026

**Internal preparation only; every quality judgment below is unscored.** These are four known plies from one previously inspected Chess.com game, not blind cases. This worksheet neither records new model answers nor establishes whether any capture has run. Populate attempt fields only from exact retained capture receipts. It is evaluator-only and must never be added to a no-forward generator request.

## Source and denominator

The [practice plan](chesscom-breadth-practice-plan-2026-10-06.md) fixes plies **33, 46, 57 and 93**: four scheduled development cases. Keep every malformed, rejected, empty, timed-out, interrupted and not-run case. A later version retains this original denominator and its evidence.

Source: [local PGN](../artifacts/chess-user-reviews/chesscom-184866057876/source.pgn), SHA-256 `684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`. Use only the source-bound legal mainline for case identity; its annotations and side variation are not generator inputs. Redistribution rights have not been established.

The [baseline](chesscom-breadth-baseline-2026-10-06.md) contains evaluator-only engine observations. Its sampled alternative is not automatically the model-named alternative or evidence for that model's contrast. The [v9 note](chess-no-forward-teaching-v9-2026-10-06.md) records packet/projection hashes and checker limits. The [capture implementation](../scripts/chess_no_forward_teaching_capture_v9.py) defines exact attempt retention. The [comparison rubric](chess-explanation-comparison-rubric-2026-10-06.md) and [human judgment proposal](chess-teaching-judgment-protocol-2026-10-06.md) control scoring; software admission is not teaching quality.

The [Chess.com observations](chesscom-review-breadth-observations-2026-10-06.md) are dated paraphrases, not immutable comparator answers: screenshots were not saved. Do not use those labels or paraphrases as a ground-truth answer key, an invented paired answer, or generator context. No blind paired preference can be assigned from this worksheet alone.

## Recording rules

Keep capture accounting separate from quality. Bind each completed record to the exact frozen request, raw response, evaluation, model identity, latency, attempt count and failure status with paths and hashes. Record the model's actual named alternative and mechanism without filling a missing answer from the baseline or analyst knowledge. Do not edit the initial answer after evaluator feedback.

For each case, retain atomic claims and legal/evaluator evidence; record conditional examples as conditional. A bound, mate score or missing paired evidence cannot be turned into a centipawn ordering. Record the comparative outcome as **answered with verified contrast / useful mechanism but ranking unresolved / unanswered / factual fail** only after evidence review. Until then it stays **unscored**. Keep teaching score, critical error, abstention, each judge's first rating and adjudication separate. A score of 2+ does not establish why every inferior move was bad or Chess.com parity.

The learner questions below are evaluator questions fixed for this worksheet, not new model prompt content. If an existing capture asked a different question, retain that mismatch and do not claim matched-question comparison.

## Ply 33 — 17.Qc2

- Selected move: `d1c2`; source-bound FEN: see the exact row in the practice plan.
- Learner question: **What does Qc2 change, and why should I choose it or a different legal move while my queen is attacked?**
- Retained baseline: [ply 33 review](../artifacts/chesscom-breadth-baseline-20261006/ply33/review.json), SHA-256 `28ccb3384d34b9027ececae67933ed18fbf8cb9f15a732aefc4c4d3de701f006`.
- V9 source packet SHA-256 from the retained integration: `68a93644e372d4df7058fdae2866c6bc1ceee56e27b9240801842c2ca1bb0fae`. This reference does not prove a model capture exists.

| Record field | Initial value |
| --- | --- |
| Capture version; frozen request path/hash; raw response path/hash | Pending receipt binding |
| Attempt count; model identity; latency; transport/failure status | Pending receipt inspection; do not infer not-run or success |
| No-forward input audit and evaluator report path/hash | Pending receipt inspection |
| Model's stated mechanism; atomic claims | Unscored; no answer entered |
| Model-named alternative or refutation | Unscored; no answer entered |
| Model-named conditional consequence; legal replay/evaluator evidence | Unscored; no answer entered |
| Critical error and factual/admission decision | Unscored |
| Full/partial abstention and unresolved part | Unscored |
| Comparative question outcome and concrete reason | Unscored |
| Teaching score (0–3), judge identity/qualification, initial rating | Unscored |
| Second initial rating; adjudication and reason | Unscored |
| Paired product preference | Unscored; preserved comparator answer unavailable |

## Ply 46 — 23...Qxd4+

- Selected move: `d5d4`; source-bound FEN: see the exact row in the practice plan.
- Learner question: **What does Qxd4+ accomplish, what reply could challenge the explanation, and why choose it over a named alternative?**
- Retained baseline: [ply 46 review](../artifacts/chesscom-breadth-baseline-20261006/ply46/review.json), SHA-256 `2e246ed59ab9bbf494a7b2ae888b8dea8745dbb74ede68325846e8404b24ec28`.
- V9 source packet SHA-256 from the retained integration: `2d377b2e0223a9fb9c4d01ba060c15078dc788aef233eb68fe52a861a5f735aa`. This reference does not prove a model capture exists.

| Record field | Initial value |
| --- | --- |
| Capture version; frozen request path/hash; raw response path/hash | Pending receipt binding |
| Attempt count; model identity; latency; transport/failure status | Pending receipt inspection; do not infer not-run or success |
| No-forward input audit and evaluator report path/hash | Pending receipt inspection |
| Model's stated mechanism; atomic claims | Unscored; no answer entered |
| Model-named alternative or refutation | Unscored; no answer entered |
| Model-named conditional consequence; legal replay/evaluator evidence | Unscored; no answer entered |
| Critical error and factual/admission decision | Unscored |
| Full/partial abstention and unresolved part | Unscored |
| Comparative question outcome and concrete reason | Unscored |
| Teaching score (0–3), judge identity/qualification, initial rating | Unscored |
| Second initial rating; adjudication and reason | Unscored |
| Paired product preference | Unscored; preserved comparator answer unavailable |

## Ply 57 — 29.Rac1

- Selected move: `a1c1`; source-bound FEN: see the exact row in the practice plan.
- Learner question: **Why choose Rac1 or a different rook move, and what concrete consequence would make one choice weaker?**
- Retained baseline: [ply 57 review](../artifacts/chesscom-breadth-baseline-20261006/ply57/review.json), SHA-256 `8a4bd9724386ab26389a796da4fd4bbea3d690862efadd5acd3c6cdfff8f61ba`.
- V9 source packet SHA-256 from the retained integration: `76d906526abaed37760bea838cec7671b9a093e607895f057f61c35cad767597`. This reference does not prove a model capture exists.

| Record field | Initial value |
| --- | --- |
| Capture version; frozen request path/hash; raw response path/hash | Pending receipt binding |
| Attempt count; model identity; latency; transport/failure status | Pending receipt inspection; do not infer not-run or success |
| No-forward input audit and evaluator report path/hash | Pending receipt inspection |
| Model's stated mechanism; atomic claims | Unscored; no answer entered |
| Model-named alternative or refutation | Unscored; no answer entered |
| Model-named conditional consequence; legal replay/evaluator evidence | Unscored; no answer entered |
| Critical error and factual/admission decision | Unscored |
| Full/partial abstention and unresolved part | Unscored |
| Comparative question outcome and concrete reason | Unscored |
| Teaching score (0–3), judge identity/qualification, initial rating | Unscored |
| Second initial rating; adjudication and reason | Unscored |
| Paired product preference | Unscored; preserved comparator answer unavailable |

## Ply 93 — 47.Rb8

- Selected move: `h8b8`; source-bound FEN: see the exact row in the practice plan.
- Learner question: **How does Rb8 affect the passed pawn, what reply limits that idea, and why choose it over a named alternative?**
- Retained baseline: [ply 93 review](../artifacts/chesscom-breadth-baseline-20261006/ply93/review.json), SHA-256 `5c7b26287d401cca861b17641742a64e9bcb97c508bfe76525935eebfa929fd3`.
- V9 source packet SHA-256 from the retained integration: `3219c8c925997a9b02d4446f9ff04dd62a88a8bf6f815b43a141f4669b4c24eb`. This reference does not prove a model capture exists.

| Record field | Initial value |
| --- | --- |
| Capture version; frozen request path/hash; raw response path/hash | Pending receipt binding |
| Attempt count; model identity; latency; transport/failure status | Pending receipt inspection; do not infer not-run or success |
| No-forward input audit and evaluator report path/hash | Pending receipt inspection |
| Model's stated mechanism; atomic claims | Unscored; no answer entered |
| Model-named alternative or refutation | Unscored; no answer entered |
| Model-named conditional consequence; legal replay/evaluator evidence | Unscored; no answer entered |
| Critical error and factual/admission decision | Unscored |
| Full/partial abstention and unresolved part | Unscored |
| Comparative question outcome and concrete reason | Unscored |
| Teaching score (0–3), judge identity/qualification, initial rating | Unscored |
| Second initial rating; adjudication and reason | Unscored |
| Paired product preference | Unscored; preserved comparator answer unavailable |

## Completion boundary

Readiness means all four case records exist with evidence references and honest pending fields. It is not a model-quality result or formal review. After an authorized capture, fill evidence and accounting first, then obtain the separate judgments required by the project. Report comparative outcomes over all four scheduled cases and disclose pending records. Never treat four cases from this known game as game-disjoint evidence, all-moves coverage, or permission to expand to other games.
