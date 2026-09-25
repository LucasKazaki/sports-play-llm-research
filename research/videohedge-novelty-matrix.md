# VideoHEDGE overlap and novelty matrix

**Checked:** 2026-08-06  
**Primary paper:** Gautam, Midoglu, Thambawita, Riegler, and Halvorsen, *VideoHEDGE: Entropy-Based Hallucination Detection for Video-VLMs via Semantic Clustering and Spatiotemporal Perturbations*, arXiv:2601.08557v1, submitted 2026-01-13. <https://arxiv.org/abs/2601.08557v1>  
**Author-linked resources:** <https://github.com/Simula/HEDGE#videohedge>; <https://pypi.org/project/hedge-bench/>  
**Status:** research-paper result with a released base HEDGE package, but **VideoHEDGE implementation unavailable at the checked repository head**. This is not deployed-system evidence and is not currently a reproducible VideoHEDGE reference implementation.

## What the immutable v1 paper establishes

VideoHEDGE is direct prior art for SoccerChat-specific hallucination detection using sampled-answer semantic clustering and clean/noisy visual perturbations. The paper randomly selects 490 SoccerChat clips with one annotated event, yielding 1,460 video/question/answer instances across EventClassification and VideoQA. It evaluates Qwen2-VL-7B, Qwen2.5-VL-7B, and SoccerChat-qwen2-vl-7B. Qwen3-30B-A3B judges whether a generated answer matches a reference answer; VideoHEDGE then evaluates Semantic Entropy, RadFlag, and perturbation-aware VASE by ROC-AUC against those binary labels.

At the default 24-frame, 100,352-max-pixel setting, the author-reported embedding-clustering VASE ROC-AUC is `0.654` for EventClassification and `0.623` for VideoQA on SoccerChat-qwen2-vl. These are reported hallucination-detection discrimination values, not grounding, calibration-error, selective-risk, or abstention results. The authors explicitly characterize absolute ROC-AUC as moderate and list human adjudication on a subset as future work.

## Comparison to PlayGround

| Capability / contract | VideoHEDGE v1 | PlayGround implication |
|---|---|---|
| Soccer short-clip evaluation | Yes: SoccerChat clips stated as 3–6 seconds | Short duration and SoccerChat-domain reliability are not novel. |
| Reliability signal | Semantic cluster dispersion from high-temperature clean/noisy answer samples | Semantic entropy and sampled-answer consistency must be baselines, not contributions. |
| Evidence intervention | Brightness, contrast, saturation, hue shift, and additive spatiotemporal noise; compares clean/noisy semantic distributions | Generic visual perturbation-aware hallucination scoring is prior art. PlayGround interventions must target submitted evidence and soccer structure (frame/region/trajectory swaps, shifts, or validity failures). |
| Correctness label | Qwen3-30B-A3B compares generated answer with gold answer; no video is supplied to the judging prompt described in the paper | Do not call this external visual grounding verification. PlayGround should separately score answer correctness, answer-linked evidence, and unsupported citations. |
| Submitted temporal evidence | No required timestamp/frame citation; checked full text has zero `timestamp` occurrences | Retained novelty boundary. |
| Submitted pitch/trajectory evidence | No required pitch coordinate, region, or trajectory payload; checked full text has zero `coordinate`, `trajectory`, and `pitch` occurrences | Retained novelty boundary. |
| Abstention/selective prediction | No operational abstention or selective-risk evaluation; checked full text has zero `abstain` and `selective risk` occurrences | Retained novelty boundary, but VideoHEDGE/VASE should be a candidate confidence score in selective-risk comparisons. |
| Calibration claim | Uses “calibration” broadly for reliability discrimination, reported through ROC-AUC | Do not equate ROC-AUC with probability calibration. PlayGround should report proper calibration/selective metrics with clustered intervals. |
| Human validation | LLM-as-judge labels; human adjudication listed as future work | Human item review/adjudication and transparent judge error analysis remain necessary. |
| Reproducibility | Paper says code/resources are available. Checked GitHub head `71130bef4c1b07266c39a69e894f8a60ae1beee8` has only `README.md` and a four-byte `VideoHedge.md` containing `WIP`. PyPI `hedge-bench` 0.1.2 sdist contains base `algorithms.py`/`utils.py` but no VideoHEDGE-named path. | Treat reported results as unreproduced and do not claim a runnable VideoHEDGE baseline until exact code/configuration is released or independently implemented and validated. |

## Evidence-quality caveats

1. **Internal class-count contradiction:** the v1 prose says SoccerChat-qwen2-vl has 1,885 hallucinated and 1,035 supported outputs (2,920 total), but Table 3's 24-frame row has 1,381 label-0 and 1,539 label-1 outputs (also 2,920). The direction reverses. The checked sources do not resolve which values are correct.
2. **Judge wording is stronger than its input:** the prompt asks whether answers are “supported” but receives task type, question, description, gold answer, and generated answer—not the video. It primarily checks semantic agreement with the reference, not direct support in pixels.
3. **Sampling ambiguity:** 1,460 instances are reported, while aggregate count rows total 2,920 across the two tasks. This likely reflects two task outputs per instance, but the exact unit should be clarified before power or cost calculations.
4. **Metrics unreproduced:** no model, dataset, or experiment was run here. The artifact verifier only checks the archived paper/repository/PyPI snapshots.
5. **Rights remain blocked:** VideoHEDGE uses SoccerChat/SoccerNet media. This verification acquired no media and crossed no dataset gate.

## Decision

Treat VideoHEDGE as the closest uncertainty/hallucination comparator to PlayGround. Do **not** claim semantic-entropy reliability, clean/noisy perturbation gaps, scalable embedding clustering, or SoccerChat-specific hallucination detection as novel. Preserve the contribution around externally scored answer-linked temporal and pitch/trajectory evidence, explicit provenance/visual-inferability, fail-closed unsupported-citation behavior, structured evidence corruptions, and true selective prediction/abstention. Include SE, RadFlag, and VASE-like confidence baselines if lawful media and compute become available, while clearly separating ROC-AUC discrimination from calibration and selective risk.
