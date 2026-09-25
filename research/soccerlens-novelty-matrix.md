# SoccerLens novelty boundary for PlayGround

**Iteration:** 1  
**Accessed:** 2026-08-06  
**Primary source read:** Elsharkawi, Sait, Giancola, Ghanem, Sharara, and Eldesokey, *SoccerLens: Grounded Soccer Video Understanding Beyond Accuracy*, arXiv:2605.09598v1 (2026-05-10), https://arxiv.org/abs/2605.09598v1  
**Evidence class:** author preprint, full HTML read; reported results are not independently replicated.

## Claim-level comparison

| Dimension | SoccerLens (source-supported fact) | PlayGround working proposal | Defensible separation / required test |
|---|---|---|---|
| Primary task | Event classification grounding over 13 common event classes. | Fine-grained QA/retrieval over 5–10 s plays. | Do not claim generic “grounded soccer understanding”; test answer-conditioned evidence on questions requiring temporal order, entities, regions, and trajectories. |
| Unit and source | 200 clips selected from one MatchTime broadcast source; evaluation uses 30 s clips sampled at 1 fps. | Proposed 50-clip pilot of 5–10 s plays; source not yet approved. | Shorter/high-frame-rate evidence may target rapid actions SoccerLens's stated protocol cannot resolve, but this is a hypothesis until real data and frame rates are fixed. |
| Annotation target | Professional annotators label per-frame bounding boxes for primary (event-essential), secondary (supporting), and common (correlated/contextual) cues. | Answer plus timestamp/frame, pitch-region or trajectory evidence, confidence, and abstention reason. | Preserve SoccerLens-style cue hierarchy as a shortcut-control baseline; add answer-specific evidence and explicit unanswerability. |
| Explanation object | Post-hoc attribution maps from Chefer/Chefer-T over classifier predictions. | Model-produced evidence references plus tool traces/structured game state. | Compare cited/tool evidence against post-hoc attribution rather than treating either as faithful by definition; add evidence-swap tests. |
| Metrics | Energy inside boxes, Pointing, spatial IoU, and temporal IoU. T-IoU thresholds frames whose mean attribution exceeds 50% of the clip maximum. | Answer accuracy/F1, temporal IoU/hit, region/trajectory agreement, ECE/Brier, selective risk/coverage, retrieval, latency/cost. | Reuse overlap metrics where compatible, but separately report answer correctness, evidence correctness, calibration, and abstention. |
| Evaluated systems | SigLIP, MatchVision, SoccerMaster; fixed-weight, training-free evaluation. | Direct VLM, retrieval-augmented, tool-augmented structured reasoning; fine-tuning only as an experiment. | The contribution must be a controlled system/evaluation comparison, not simply adding tools. |
| Reported finding | No evaluated model exceeds 50% grounding at any cue level across the reported metrics; specialized temporal models underperform non-temporal SigLIP on T-IoU. | Unknown; no real-data result yet. | Treat the result as motivation, never as a PlayGround result. Test whether explicit evidence/tool supervision improves grounded correctness without sacrificing calibration. |
| Scope caveat | Single broadcast source; attribution-only evaluation; authors call for more sources, VLMs, and explanation methods. | Data rights/source and coach questions remain unresolved. | Cross-source claims are blocked until an authorized source exists; avoid claiming attribution-method superiority from a QA pilot. |

## Decision from this comparison

SoccerLens occupies **soccer event-classification attribution grounding** and already supplies a useful cue hierarchy plus spatial/temporal overlap metrics. PlayGround remains potentially distinct only if it evaluates **answer-conditioned, explicit temporal + pitch/trajectory evidence and selective abstention** for short-play QA/retrieval, and compares direct, retrieval, and tool-structured systems. This is a narrowed novelty hypothesis—not a settled novelty claim.

## Reproducibility anchors

- Version actually read: `2605.09598v1` HTML.
- HTML SHA-256: `006fe5df00f74e91c4169a98fe7a30dded7d0452637feb083252ace4bb5aa502`.
- API metadata snapshot (returned latest `v2`): SHA-256 `20254997537b5851b58fbb0791e33f7bc86c2c22470e8b02acf80a359d4dae66`.
- Local source paths: `artifacts/arxiv-2605.09598v1.html`, `artifacts/arxiv-2605.09598.xml`.
