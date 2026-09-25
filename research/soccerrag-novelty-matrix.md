# SoccerRAG novelty boundary for PlayGround

**Iteration:** 30  
**Accessed:** 2026-08-06  
**Primary source read:** Aleksander Theo Strand, Sushant Gautam, Cise Midoglu, and Pål Halvorsen, *SoccerRAG: Multimodal Soccer Information Retrieval via Natural Queries*, arXiv:2406.01273v2, revised 2024-07-22, https://arxiv.org/abs/2406.01273v2  
**Evidence class:** primary author paper plus author-linked repository/README; reported evaluation was not reproduced.  
**Status:** working-open-source research implementation at [`simula/soccer-rag`](https://github.com/simula/soccer-rag), with inspectable code and setup instructions. The checked `main` head was `6ba49c4ca8c8248ff5c44ee51418901f204f59c8`; execution was not attempted because it requires OpenAI credentials and SoccerNet data that are not included in the repository.

## Working interpretation

SoccerRAG is a direct precedent for natural-language retrieval over structured soccer metadata, few-shot SQL retrieval, and an extractor-validator chain that repairs entity names before database querying. Its word “validator” refers to validating extracted query properties against database entries—not validating whether an answer is supported by submitted video evidence. Although the framework links event metadata to video timestamps, the reported 20-question evaluation concerns database membership, aggregate statistics, lineups, events, and commentary. Clip retrieval and visual analysis are described as future applications, so SoccerRAG is adjacent infrastructure rather than a short-play video-QA benchmark.

## Claim-level comparison

| Dimension | SoccerRAG v2 (source-supported fact) | PlayGround target | Defensible implication |
|---|---|---|---|
| Task | Natural-language retrieval from an augmented SoccerNet-derived SQL database. The 20 sample questions ask about database entities, season/match statistics, event times, lineups, and commentary. | Fine-grained questions about the visible content of bounded 5–10 s plays. | Do not claim natural-language soccer retrieval or database-grounded soccer QA as novel. Keep play-level visual inference distinct from archive/statistics retrieval. |
| Data representation | The paper describes 550 SoccerNet games, with ASR commentary, event annotations, caption/general-game metadata, and links between related entities in SQLite. | Rights-governed clips plus answer-linked temporal and pitch/trajectory annotations. | Structured metadata and commentary are candidate retrieval baselines, not sufficient evidence for visible play claims. Paper use of SoccerNet is not authorization for this project. |
| Architecture | Four components: database, feature extractor, feature validator, and SQL agent. The SQL agent retrieves semantically similar human-written SQL examples from a FAISS store. | Direct VLM, retrieval, structured-tool, oracle, and noisy-tool variants under one output contract. | Extractor → validator → SQL-RAG is prior art for soccer query/tool workflows and should inform a metadata-RAG baseline. |
| Meaning of validation | Extracted team/player/league/season values are matched to database tables; aliases and spelling errors are repaired using auxiliary tables, Levenshtein distance, thresholds, and possible user clarification. | Externally score whether cited frames/times and pitch regions/trajectories support the answer. | Do not describe entity normalization as evidence validation. PlayGround must validate answer support, not just query entities. |
| Video and timestamps | The database links event metadata with video timestamps. The paper places retrieval of event-associated clips, object detection, action recognition, scene understanding, highlights, and summaries in **future work**. | Video is the primary item input and timestamp/frame evidence is required output. | Timestamp-bearing metadata retrieval is prior art, but reported short-play visual QA is not established by this source. Compare metadata/event retrieval where lawful, while testing whether answers survive evidence interventions. |
| Evaluation | The extractor-validator chain is subjectively scored on 20 questions. The six pipeline configurations are tested on 10 questions with binary correct/incorrect grading; the full pipeline passes 9/10 for GPT-3.5-Turbo and 8/10 for GPT-4.0-Turbo from Table I. | Answer, temporal evidence, spatial/trajectory evidence, calibration/selective risk, and corruption effects. | SoccerRAG's small author-reported evaluation motivates a baseline but is not directly comparable to PlayGround and is not a benchmark-quality grounding result. |
| Known failures | The paper reports partial-list responses, model laziness, complex-query/large-volume limitations, and non-deterministic outputs. | Explicit insufficient-evidence/tool-failure abstention and calibrated confidence. | These are useful failure classes for retrieval baselines. The checked full text contains no `confidence`, `abstain`, `uncertainty`, or `calibration`, so it does not establish selective prediction. |
| Spatial grounding | The checked full text contains no `pitch`, `coordinate`, or `trajectory` occurrences. | Answer-linked pitch regions or trajectories with reconstruction-validity masks. | SoccerRAG does not close the external soccer-coordinate evidence axis. |
| Reproducibility | The paper links an MIT-licensed repository with source and setup instructions. The README requires Python 3.12, OpenAI environment fields, and SoccerNet files not included in the repository. | Public evaluator/schema/tests with rights-safe inputs and hash-bound receipts. | Classify it as working-open-source rather than deployed. Reproduction remains unverified here and would require a separate credentials/data authorization decision. |

## Decision

Retain the north-star while narrowing retrieval claims. PlayGround must not claim natural-language soccer archive retrieval, SQL-RAG over soccer metadata, entity extractor-validation, or timestamp-linked event retrieval as novel. SoccerRAG should be cited as the principal metadata-RAG/database-query predecessor and should inform a future lawful baseline.

The defensible distinction is that PlayGround requires a model to submit answer-linked visual and soccer-coordinate evidence, scores that support externally, measures calibrated abstention when visual/tool evidence is invalid, and applies answer-preserving evidence/tool perturbations. SoccerRAG's automatic feature validation and database query success cannot be presented as evidence faithfulness.

## Version, rights, and integrity caveats

- All paper claims are bound to immutable arXiv **v2** (`2406.01273v2`).
- The reported evaluation uses only 20 authored sample questions (10 for pipeline ablation); binary correctness and extractor-validator judgments are author-reported and unreproduced.
- “Multimodal” describes the augmented data design and timestamp links, but the checked source treats clip retrieval and visual-analysis applications as future work.
- Full-text absence checks can miss synonyms.
- The repository's MIT code license does not grant rights to SoccerNet media/data or OpenAI services. No code clone, dependency installation, API call, dataset, video, model, or checkpoint acquisition occurred.

## Local source anchors

- `artifacts/soccerrag-verification-2026-08-06/arxiv-2406.01273v2.html`
- `artifacts/soccerrag-verification-2026-08-06/arxiv-2406.01273v2-api.xml`
- `artifacts/soccerrag-verification-2026-08-06/arxiv-2406.01273v2.txt` (derived convenience text; HTML is canonical)
- `artifacts/soccerrag-verification-2026-08-06/github-repository-api.json`
- `artifacts/soccerrag-verification-2026-08-06/github-main-commit-api.json`
- `artifacts/soccerrag-verification-2026-08-06/github-readme.md`
