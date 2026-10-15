# What the local model actually said about the Chess.com practice move

On 6 October, I finally ran the two frozen, separate model requests for the game already open in Chess.com Game Review: the played **20.Qc3** and the suggested **20.Qe4**. Each request had the same pre-move position but contained only its own selected move, deterministic transition facts and typed Stockfish observation. It did not include the other move, a principal variation, a later board, Chess.com's label or the game's later moves. The exported game remains a development practice case, not a blind test.

The local `loops-cpu-gpt-oss-20b` route returned one matched HTTP 200 response for each request, with no automatic retry. Qc3 took 9.31 seconds and Qe4 took 5.56 seconds. The Qc3 answer copied the move and score, then added a vague queen-activity hypothesis. It also put extra fields into an engine-observation assertion whose accepted shape is just the exact score. The offline checker rejected the **whole Qc3 answer** as an unsupported or uncheckable typed assertion. I would not show that answer as coaching.

The Qe4 answer passed the typed checker, but it only repeated “Qe4” and the retained score. It gave no reason the move might be better. A structurally admitted answer is therefore still short of the Chess.com comparison, let alone a better explanation. Neither capture establishes Stockfish's intent, a forced line, an exact move loss or lesson quality.

## Exact local evidence

| Item | Qc3 played | Qe4 alternative |
| --- | --- | --- |
| Frozen directory | `artifacts/chess-user-game-generation-v1/chesscom-184866057876/played-frozen-v2-20261006/` | `artifacts/chess-user-game-generation-v1/chesscom-184866057876/alternative-frozen-v2-20261006/` |
| Native capture task / job | `4b832499-c167-4018-8ee9-a75246cc5072` / `2d6445bd-9d6e-48a6-bcdb-efe6fa25a931` | `ef5087a9-5207-4978-823f-bcd37d839dd6` / `14337aa8-77c8-423d-910f-b07956437bb1` |
| Original capture receipt SHA-256 | `12c1929f59b86bdd007ece01df43cc05c082a5e57ed15d1a675c0463eb9d888c` | `22970945d49853fe953d2e8ce55ba4e9deae109955c9a90c3b1f9dbaf4385c11` |
| Raw response SHA-256 | `057d0cd6d83f75e6139001037e7cc785f4fe9e6210a6a2f2eb038f119ba1230f` | `4d444178157d90da6c96f465bff3e02d55a3580a5a1cdbf3801355628d50bcca` |
| Captured result SHA-256 | `8fa6dbf8ba7ff674abfc8c8b2670ed3c16228c661ffda8b55a05c3efc8957448` | `73056e0ef5513f4d736493fc40ea6702f0485e22b16dbe55dc3757c48cf40fa5` |
| Offline checker task | `a09e0e07-0608-4136-a9ed-819ad7b163d8` | `95a99e96-26c3-458e-bf11-6427507b4300` |
| Original checker receipt SHA-256 | `1b565627772961dba2da92af29c50ac601880540f9a468a86cf0eada59eb3bb5` | `81034b1d139778c45b97b13ba2ec33c584c3c76f4611b2e549791634a21128e5` |
| Checked report SHA-256 | `0317f958ee3ba3141641ceff42d3e4c65f8b93e5e164654af9bff8cc5b75903b` | `90e2df3d26b86aa1976673d529f73ab658075c6b0d2cbf0098933cfc73761ef6` |
| Checker decision | `abstain`, reason `unsupported_or_uncheckable_typed_assertion` | `admissible_typed_assertions`, kinds `legal_board_fact`, `retained_engine_observation` |

Both checker tasks ran after capture and made **zero new model or engine calls**. Their saved reports account for one attempt each. The original runtime receipts are under `C:/AI/projects/LucasAgentStudio/data/company-runtime/project-execution/`; the project job directories are inspection copies.

The next version should ask for a narrow, conditional and checkable teaching claim. One candidate is whether a proposed alternative leaves a legal checking option after a named reply. The model must propose that idea without seeing the evaluator's continuation; an offline chess-rules check should then reject it when the moves or claim are false. That would explain one concrete difference, not the whole reason behind an engine score. Fresh game-disjoint tests and independent chess judgment still decide whether the explanations are useful.
