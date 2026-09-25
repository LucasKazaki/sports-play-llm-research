# Citation-neighborhood review: sports temporal grounding × soccer QA × pitch state

**Iteration:** 27  
**Accessed:** 2026-08-06  
**Working interpretation:** A direct PlayGround neighbor must jointly answer play-level questions, expose answer-linked temporal and soccer-coordinate evidence for external scoring, and evaluate confidence/abstention. Internal attention, generic soccer QA, attribution maps, and game-state reconstruction are near-boundary components rather than exact matches.

## Discovery method and coverage

Semantic Scholar citation/reference endpoints were queried for four verified anchors: SoccerNet-GSR (`2404.11335`), SoccerAgent (`2505.03735`), SoccerLens (`2605.09598`), and TreeSoc (`2607.10990`). Raw snapshots preserve 58/100, 20/68, 0/34, and 0/22 citation/reference edges respectively (302 records total; the GSR reference endpoint was capped at 100). Per-paper detail requests returned HTTP 429 and were not silently reconstructed. Semantic Scholar is a discovery index, not proof of paper contents.

The highest-value newly discovered near-neighbor was then verified from its immutable arXiv v1 full HTML and API metadata:

- Arushi Rai and Adriana Kovashka, *Learning Consistent Temporal Grounding between Related Tasks in Sports Coaching*, arXiv:2603.18453v1, submitted 2026-03-19: https://arxiv.org/abs/2603.18453v1

## Classified candidates

| Candidate | Status/evidence | What it establishes | Missing from the verified source | PlayGround implication |
|---|---|---|---|---|
| **Learning Consistent Temporal Grounding…** — Rai & Kovashka | Research-system preprint; full immutable v1 read; no author code link found in the paper HTML | Dual-pathway generation/verification training aligns selected internal visual-attention maps without new frame labels. Ground-truth VidDiffBench keyframes are used for diagnosis/proof-of-concept, and three sports-coaching tasks evaluate answer/feedback quality. | It does not require submitted timestamp/frame citations; its temporal-grounding diagnostic is internal-attention AUROC, not an externally scored answer evidence payload. No pitch-coordinate region/trajectory, abstention, calibration, or selective-risk evaluation was found. | **Closes novelty for internal temporal-attention consistency training in sports.** Add it as a training baseline/ablation, but preserve explicit external evidence and uncertainty as the contribution boundary. |
| **SoccerAgent / SoccerBench** | ACM MM 2025 research system; previously full-paper verified | Broad multimodal soccer QA and 18 specialist tools | No externally scored answer-linked pitch trajectory or selective prediction in the checked paper | Required QA/tool baseline; not headline novelty. |
| **SoccerLens** | Preprint benchmark; previously full-paper verified | Per-frame soccer cue boxes and spatial/temporal attribution metrics | Event-classifier attribution rather than answer evidence; no selective prediction | Required grounding comparator. |
| **SoccerNet-GSR** | CVPRW 2024 dataset/baseline and inspectable official code; previously verified | Visible-athlete identity plus 2D pitch-state reconstruction | No QA, answer-linked evidence, or selective prediction | Tool/oracle infrastructure with explicit validity masks. |
| **TreeSoc** | Preprint/reference claim; repository was announcement-level at prior check | Dynamic tool-augmented soccer QA | No external answer-linked pitch/trajectory score or selective evaluation | Required agentic comparator; not working-open-source evidence. |
| SoccerChat, SoccerRAG, MSUE, multi-view sports reasoning, DeepSport, SportR | **Discovery leads only** from indexed citation/reference metadata | Adjacent soccer dialogue/retrieval or sports reasoning by title/index metadata | Full claims not verified in this iteration | Prioritize only if rights gate remains blocked; do not use their indexed metadata for novelty claims. |

## Claim-level verification of arXiv:2603.18453v1

1. The method trains a shared video-language model with generation and verification pathways and applies a KL self-consistency objective between selected internal visual-attention maps, plus entropy and answer losses.
2. On the EgoExo4D split of VidDiffBench, the paper measures keyframe overlap using AUROC against ground-truth keyframe indicators. The selected layer's reported AUROC is 0.62. In a ground-truth-keyframe attention-redistribution proof-of-concept, Table 1 reports accuracy 65.8 with no redistribution, 68.4 with uniform redistribution, 71.8 with proportional redistribution over keyframes, and 73.4 with adaptive non-sink head selection plus keyframes.
3. Across Exact, FitnessQA, and ExpertAF, Table 2 reports the finetuned PerceptionLM-8B baseline at 84.5, 74.1, and 37.5 and the proposed method at 87.5, 88.2, and 38.4, corresponding to author-reported gains of +3.0 and +14.1 accuracy and +0.9 BERTScore.
4. Exact includes physical skills ranging from soccer to dance; ExpertAF includes a qualitative soccer example. This is sports-coaching work, not a soccer-play QA benchmark.
5. Searches of the full extracted v1 text found zero occurrences for `abstain`, `calibration`, `trajectory`, and `coordinate`; `confidence` occurred only in discussion of another spatial-attention intervention. The paper's timestamp hit was bibliographic/contextual, not a required timestamp submission protocol.

## Decision

This review changes the novelty boundary but not the north-star recommendation. Do **not** claim that improving temporal grounding in sports through attention training is new. PlayGround should compare or ablate internal temporal-attention consistency while insisting on externally inspectable answer-linked frame/time and pitch evidence, reconstruction-validity-aware abstention, and joint-grounded selective risk. No exact joint contract was found in this bounded citation neighborhood, but that is not an absence proof and cannot support a categorical “first” claim.

## Integrity anchors and limitations

- arXiv v1 HTML: `artifacts/citation-neighborhood-2026-08-06/arxiv-2603.18453v1.html`, SHA-256 `787fd84d351bf8a64d57e39a7e7359211bb4d3be9ed9cc49402c893a7fed63f2`.
- arXiv API metadata: `artifacts/citation-neighborhood-2026-08-06/arxiv-2603.18453-api.xml`, SHA-256 `5def81c8eeb9d2ff7e42ef3e8612f42a6e46ea0d6e57e0a4ac249a844a8b54e5`.
- Extracted text: `artifacts/citation-neighborhood-2026-08-06/arxiv-2603.18453v1.txt` (derived convenience artifact; HTML is canonical).
- Indexed citation counts are mutable and were not used to rank technical quality. Reported model results are author-reported and were not reproduced. Term absence can miss synonyms. Citation endpoints can omit papers and the GSR references were capped at 100.
