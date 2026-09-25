# DeepSport vs. PlayGround: active frame retrieval and evidence contract

**Iteration:** 28  
**Accessed:** 2026-08-06  
**Primary source:** Junbo Zou, Haotian Xia, Zhen Ye, Shengjie Zhang, Christopher Lai, Vicente Ordonez, Weining Shen, and Hanjie Chen, *DeepSport: A Multimodal Large Language Model for Comprehensive Sports Video Reasoning via Agentic Reinforcement Learning*, arXiv:2511.12908v2, revised 2026-03-11.  
**Immutable paper:** https://arxiv.org/abs/2511.12908v2  
**Working interpretation:** DeepSport is a research-system preprint and a direct near-neighbor for sports video reasoning with active temporal frame retrieval. It is not evidence of deployment, and this review found no author-linked runnable implementation in the paper HTML.

## Claim-level comparison

| Dimension | DeepSport v2 (paper-supported fact) | PlayGround target | Implication |
|---|---|---|---|
| Scope | Multi-task, multi-sport video understanding across recognition, rules, coaching/assessment, and commentary; its curated sources include SoccerBench, SoccerReplay-1988, X-VARS, and other sports datasets. | Fine-grained QA about bounded 5–10 second soccer plays. | Soccer/sports VideoQA is not novel; short-play scope must earn value through resolution, evidence, and uncertainty evaluation. |
| Active temporal tool | Starts from uniformly sampled frames tagged with `frame_index`; the model can iteratively call `frame_extraction_tool(idx_start, idx_end)` to request frames from a temporal window. | Direct, retrieval, tool, oracle, and noisy-tool baselines under one output schema. | **Closes novelty for active, iterative frame-window retrieval in sports MLLMs.** DeepSport is a required conceptual baseline. |
| Tool policy | GRPO reward classifies samples by whether the base model succeeds on initial frames and rewards useful tool use for initially failed items or no tool use for initially successful items. | Decide whether available evidence is sufficient, then answer or abstain. | Selective tool invocation is prior art, but it is not selective prediction: DeepSport still terminates in an answer and does not define answer abstention. |
| Submitted evidence | Tool calls expose queried frame-index windows inside the reasoning trajectory; final output is `<answer>...</answer>`. The checked evaluation reports answer scores and average frames, not a required answer-linked evidence payload or frame-grounding metric. | Every answer submits externally scored frame/time and pitch/trajectory evidence. | A tool-use trace can be candidate provenance, but must be converted into an explicit, answer-linked, externally scored artifact rather than treated as faithful by default. |
| Spatial grounding | The checked full text has no occurrence of `coordinate`; `trajectory` predominantly means a reasoning trajectory. | Pitch regions/trajectories with validity masks and independent scoring. | Answer-linked soccer-coordinate evidence remains outside this source's demonstrated contract. |
| Confidence/abstention | The checked text has zero occurrences of `abstain` and `confidence`; “selective” refers to tool invocation. | Confidence, explicit insufficient-evidence abstention, calibration, and selective risk. | Do not conflate deciding whether to retrieve with deciding whether to answer. Validity-aware abstention remains a narrower axis. |
| Data/training | Authors report DeepSport-CoT-14K with 14,599 retained Q&A/CoT pairs, DeepSport-RL-63K, a held-out 6.7K test benchmark, and 796 H20 GPU-hours. | Rights-governed pilot and reproducible evaluation, with no training implied before approval. | Numbers are scale/context only; they were not reproduced and do not authorize acquiring source media or datasets. |
| Main result | Claude 4.5 Sonnet is used as LLM judge; Table 2 reports overall 37.67 for DeepSport versus 16.98 for its Qwen2.5-VL-7B backbone, with 9.81 versus 16 average frames. | Separate answer, grounding, calibration, selective-risk, and intervention metrics. | The author-reported result motivates the retrieval baseline but is not directly comparable to future PlayGround scores. |
| Failure evidence | Manual inspection of 70 sampled failures assigns 42.9% to tool-grounding failure (retrieved window missed the event) and 37.1% to visual hallucination despite correct frames. | Measure false citation, evidence corruption, tool validity, and abstention under failed retrieval/reconstruction. | Strongly motivates answer-linked grounding and fail-closed abstention: tool use alone neither localizes reliably nor prevents hallucination. |
| Reproducibility status | Full v2 paper and parameters are inspectable. No GitHub/project/code URL was found in the paper HTML; a GitHub repository search produced no clearly author-linked implementation. | Public schema, evaluator, tests, prompts/configs, and hash-bound receipts. | Classify as a research preprint, not working open source. Search non-discovery is not proof that code is unavailable. |

## Decision

DeepSport narrows the thesis but strengthens its motivation. PlayGround must **not** claim active frame extraction, multi-turn video interrogation, selective tool invocation, sports-specific SFT/RL, or sports VideoQA as novel. Treat active frame-window retrieval as a baseline family.

The defensible research question is now sharper: does requiring an externally submitted answer-linked temporal and pitch-evidence payload, validity-aware confidence/abstention, and intervention-based scoring expose and reduce the exact failure modes that an answer-only active-retrieval system leaves unresolved? DeepSport's manual error analysis is supporting motivation, not proof that PlayGround solves those failures.

## Evidence limitations and integrity

- All model scores, data sizes, GPU-hours, and failure percentages are author-reported and unreproduced.
- The 70-case error analysis is small, manually classified, and reports percentages in one-decimal increments; the paper does not state inter-rater reliability in the checked passage.
- Zero term occurrences can miss synonyms. Tool calls are visible in a generated reasoning trajectory, but the checked benchmark does not externally score them as answer evidence.
- No dataset, media, checkpoint, model, or restricted material was acquired.
- Archived HTML SHA-256: `ef3d0c216aa86083b79378dd331eed8799b785fc0b634822e19ef78cd48ea4d2`.
- Archived API XML SHA-256: `c2dbf2ecd2cbd95b264ca6452bb26b3a601dd22a324ad667e434877aa25aab56`.
- Extracted convenience text SHA-256: `f2409662660ee72e093da4210b3a1dd9a2a2183d18a19cedbc4975197d54d790`; HTML is canonical.
