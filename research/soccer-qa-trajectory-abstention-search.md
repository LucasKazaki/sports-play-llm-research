# Targeted novelty search — soccer QA × field trajectories × abstention

**Iteration:** 23  
**Accessed:** 2026-08-06  
**Working interpretation:** The relevant category is a soccer video/language system or benchmark that jointly (1) answers play-level questions, (2) submits answer-linked pitch-coordinate regions or trajectories for external scoring, and (3) exposes calibrated abstention/selective-risk evaluation. Generic image-plane localization, internal tool coordinates, trajectory forecasting without QA, and camera calibration are near-boundary rather than exact matches.

## Search coverage and classification

Four arXiv API searches created candidate pools for soccer QA, soccer trajectory + language, sports VideoQA + abstention/calibration, and the three-way soccer trajectory + abstention intersection. The API reported 74, 17, 275, and 62 total matches respectively; 30, 17, 30, and 50 ranked entries were archived. The broad Boolean searches have substantial false positives: in the three-way pool, `calibration` usually means camera calibration and `uncertainty` appears in trajectory forecasting, not selective QA. Manual title/abstract screening of the 50 archived three-way entries found no exact joint match; this is a scoped negative result, not proof of global absence.

| Candidate | Status | Primary task and strongest evidence | Answer-linked pitch/trajectory evidence | Confidence/abstention | PlayGround implication |
|---|---|---|---|---|---|
| **SoccerAgent / SoccerBench** — Rao et al. | Published ACM MM 2025 paper / research system; no runnable implementation was established in this iteration | Around 10K multiple-choice QA pairs across 13 text/image/video tasks; SoccerAgent routes questions through 18 specialist tools. The paper evaluates answer accuracy and reports SoccerAgent category results. | **No external answer-linked pitch/trajectory metric found.** A segmentation tool returns image bounding-box coordinates and detector confidence; this is internal generic image-plane output. | Full-text searches found no `abstain`, `calibration`, or `uncertainty`; `confidence` appears only in a tool description, not selective QA evaluation. | Closes novelty of broad soccer multimodal QA, SoccerWiki retrieval, and multi-agent specialist-tool routing. SoccerAgent is a required near-neighbor baseline/precedent. |
| **Domain Adaptation of VLM for Soccer Video Understanding** — Jiang et al. | Author preprint / training study; no deployment evidence | Multi-stage LoRA adaptation of LLaVA-NeXT-Video on 20K curated 2-second clips. Authors report 37.5% relative VQA improvement and action-classification accuracy from 11.8% to 63.5%. | None reported; full-text searches found no `trajectory`, `coordinate`, `pitch`, or `spatial`. | No `confidence`, `abstain`, `calibration`, or `uncertainty` occurrences found. | Closes novelty of short-clip soccer VLM adaptation and synthetic instruction tuning. Fine-tuning is a baseline/ablation, not the PlayGround contribution. |
| **TreeSoc** — Vo et al. | Preprint / announcement-level repository at prior access | Dynamic DFS and specialist-tool soccer QA; author-reported SoccerBench/NExT-QA accuracy. | Internal context may include timestamps/coordinates, but no external answer-linked pitch/trajectory score was reported. | Uncertainty-aware replanning is future work; no selective evaluation. | Already closes generic dynamic tool orchestration; complements SoccerAgent. |
| **SoccerLens** — Elsharkawi et al. | Benchmark preprint | Event-classifier attribution grounding with per-frame cue boxes. | Image-plane cue boxes and temporal attribution, not QA-linked pitch trajectories. | Not reported. | Closes generic grounded soccer understanding, not the joint contract. |
| **Trajectory candidate pool** (for example TacticGen, FOOTPASS, Sports-Traj, SoccerNet Game State Reconstruction) | Mixed preprints/datasets/models; near-boundary | Tactical generation, action spotting, trajectory generation, or minimap reconstruction rather than externally grounded QA plus selective prediction. | Yes for some candidates, but not jointly with answer-linked QA evidence and abstention in the screened metadata. | No matching selective-QA contract in the screened metadata. | Useful future tool/data precedents; they do not independently establish the proposed joint benchmark contract. |

## Transparent ranking by relevance

1. **SoccerAgent / SoccerBench** — closest verified predecessor for broad soccer QA and specialist-tool routing.
2. **TreeSoc** — closest predecessor for dynamic tool-augmented soccer video QA.
3. **SoccerLens** — strongest soccer grounding benchmark predecessor.
4. **Domain Adaptation of VLM for Soccer Video Understanding** — strongest verified short-clip adaptation precedent in this iteration.
5. **Trajectory candidate pool** — technically relevant to pitch-state tooling, but not exact QA/selective-prediction matches from metadata screening.

## Decision

The targeted search **does not establish novelty by absence**. It does, however, further narrow safe language:

- Do not claim novelty for soccer QA, multimodal soccer benchmarks, SoccerWiki-style retrieval, multi-agent/specialist-tool routing, short-clip soccer VLM adaptation, synthetic soccer instruction tuning, generic soccer grounding, or trajectory/game-state modeling separately.
- Retain only a combination hypothesis: short-play QA with externally scored **answer-linked soccer-coordinate regions/trajectories**, calibrated abstention, joint-grounded selective risk, grouping/leakage controls, and answer-preserving evidence/tool perturbations.
- The next evidence gate remains a rights-cleared real-data pilot. A larger database/venue search is still required before any categorical “first” claim.

## Primary sources and integrity anchors

- Rao et al., *Multi-Agent System for Comprehensive Soccer Understanding*, arXiv:2505.03735v2, published 2025-05-06, revised 2025-09-02: https://arxiv.org/abs/2505.03735v2
  - PDF SHA-256: `108a22caa39a15349a059fb802dcaefc2fb69ef9c7dc59a004fe8616e7d31243`
  - Extracted text SHA-256: `f5be60b6fa31790b930de6dfa6e13880a9a03532ad98545f12cff1e15f2d18ad`
  - API SHA-256: `3d5a45385544b7484ece94de90ffa272fa3504b436e78b34c66b2342bdd503d2`
- Jiang et al., *Domain Adaptation of VLM for Soccer Video Understanding*, arXiv:2505.13860v2, published 2025-05-20, revised 2025-07-07: https://arxiv.org/abs/2505.13860v2
  - HTML SHA-256: `5a15110868fbab184b69e935969fd8acc75e2235759d765945abbf1c56144812`
  - API SHA-256: `3c0612eb14fdc06d3c44dce3b92d05e140d4f9dfce0c5ef781f97d8df4114dfd`
- Search snapshot hashes and query/return counts are recorded in `experiments/2026-08-06-iteration-023-targeted-novelty-search.md`.

## Caveats

All paper metrics are author-reported and were not reproduced. Full-text term absence is weaker than an explicit author statement. ArXiv ranking and indexing are not exhaustive; queries can miss synonyms and include false positives. The adaptation paper used SoccerNet and proprietary subscription-based WyScout source data; no dataset or video was downloaded or licensed here. “Published/research system” does not mean deployed or working open source.
