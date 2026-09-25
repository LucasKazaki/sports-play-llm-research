# SoccerChat novelty boundary for PlayGround

**Iteration:** 31  
**Accessed:** 2026-08-06  
**Primary source read:** Sushant Gautam, Cise Midoglu, Vajira Thambawita, Michael A. Riegler, Pål Halvorsen, and Mubarak Shah, *SoccerChat: Integrating Multimodal Data for Enhanced Soccer Game Understanding*, arXiv:2505.16630v1, 2025-05-22, https://arxiv.org/abs/2505.16630v1  
**Official project sources:** https://github.com/simula/SoccerChat, https://huggingface.co/SimulaMet/SoccerChat-qwen2-vl-7b, and https://huggingface.co/datasets/SimulaMet/SoccerChat  
**Evidence class:** primary author preprint plus author-linked repository/model/dataset metadata; all paper results are author-reported and were not reproduced.  
**Status:** working-open-source research model/demo, not deployed evidence. The public repository's checked `main` head (`330b26ed797e985dbb8f5baeaffe0ef91da0906e`) contains a README and two runnable-example notebooks; the public ungated Hugging Face model card provides inference instructions. The SoccerNet-derived dataset is gated and was not accessed.

## Working interpretation

SoccerChat is a close precedent for the *short-clip soccer VideoQA* part of PlayGround. Its paper reports event-centered clips no longer than 10 seconds, a multimodal instruction dataset, and a Qwen2-VL-7B model fine-tuned for conversational soccer understanding. Therefore, PlayGround cannot claim novelty from combining short soccer clips and free-form questions/answers.

It does **not** close the proposed evidence-faithfulness contract. The checked v1 evaluation scores referee-decision answers with a separate LLM and action classification with label metrics; it does not require models to submit answer-linked timestamps/frames, pitch regions/trajectories, confidence, or abstentions. More importantly, the QA-generation prompt supplies commentary/captions and explicitly instructs the generator to act as though the information came from the video. That is direct motivation for PlayGround's source-provenance, visual-inferability, and intervention checks—not proof that every SoccerChat answer is visually unsupported.

## Claim-level comparison

| Dimension | SoccerChat v1 (source-supported fact) | PlayGround target | Defensible implication |
|---|---|---|---|
| Clip/task granularity | Event clips are extracted from SoccerNet and capped at 10 seconds. The paper reports 90,834 event clips before QA filtering and 49,120 retained QA pairs. | Questions about rights-governed 5–10 second soccer plays. | Short soccer clips and free-form soccer VideoQA are prior art, not novelty. |
| Inputs and model | Qwen2-VL-7B-Instruct is LoRA fine-tuned on 24 sampled frames per clip (reported as 2.4 fps) and a textual query. The paper says audio is not incorporated in the current model architecture. | Direct VLM, retrieval, structured-tool, oracle, and noisy-tool variants under a common contract. | SoccerChat is a direct video-VLM baseline family; commentary-derived supervision should be tracked separately from runtime modalities. |
| Instruction construction | GPT-3.5 Turbo fuses event metadata, jersey colors, supporting captions, and commentary into descriptions/QAs. A displayed prompt says to use supporting commentary/caption while “faking as though” the information came from the video itself. | Each claim must be visually inferable from the clip or explicitly marked as metadata/commentary support; corruption tests probe dependence on submitted evidence. | Add provenance labels and reject hidden-source leakage. The prompt is evidence of a generation risk, not evidence that all generated items fail visual-inferability review. |
| Dialogue/QA evaluation | On XFoul, an LLM scorer (QwQ-32B) assigns 0–10 scores to model responses against reference answers. The paper also evaluates six- and sixteen-class action classification. | Answer correctness plus temporal evidence, spatial/trajectory evidence, confidence/abstention, calibration, and paired evidence interventions. | LLM-judged answer similarity and classification metrics do not establish faithful evidence or selective reliability. |
| Reported classification result | Table 1 reports SoccerChat six-class weighted precision/recall/F1 of 0.59/0.57/0.57, Cohen’s κ 0.48, MCC 0.49, and Hamming loss 0.43. | Multiple baseline families evaluated under externally scored joint endpoints. | Treat the values as author-reported baseline context only; they were not reproduced and are not comparable to PlayGround's proposed joint metric. |
| Temporal evidence | The checked full text has zero `timestamp` and `evidence` occurrences and defines no required supporting-frame payload. | Submitted timestamps/frame IDs scored against answer-linked references. | Short duration does not substitute for temporal localization. |
| Spatial evidence | The checked full text has zero `pitch`, `coordinate`, and `trajectory` occurrences. Jersey colors are used in generated descriptions. | Submitted pitch region or trajectory plus geometry-validity state. | Jersey-color reasoning is not coordinate grounding; the spatial axis remains open. |
| Selective reliability | The checked full text has zero `confidence`, `abstain`, and `uncertainty` occurrences. Two `calibration` mentions concern camera calibration in related work, not predictive calibration. | Calibrated confidence, abstention, failure reasons, selective-risk curves, and false-citation rate. | SoccerChat does not establish answer-level selective prediction under the checked terms/protocol. |
| Reproducibility/status | The author-linked repository exposes README plus usage/WebUI notebooks. A public ungated Apache-2.0 model card gives inference instructions. GitHub's API detects no repository-level license file. | Public evaluator/schema/tests and hash-bound, rights-safe receipts. | Classify as working-open-source research model/demo, not deployment. Do not infer a repository code license from the model card. |
| Rights and release drift | Current Hugging Face API metadata marks the dataset `gated: auto`, `license: other`, and requires an active SoccerNet NDA for video access. It reports 85,220 train and 4,625 validation examples, which does not match the paper's 49,120-pair snapshot. | Explicit source approval, immutable hashes, custody fields, and frozen splits before empirical work. | Do not request access or acquire media without Lucas/Archit approval. Bind any future comparison to exact dataset revision/splits rather than mixing paper and live-hub counts. |

## Decision

Retain the north-star but narrow the novelty claim again. PlayGround must not claim short-clip soccer dialogue, soccer-domain video instruction tuning, jersey/commentary fusion, referee-decision QA, or action-classification benchmarking as new. SoccerChat should be included as the closest direct short-clip soccer-VLM baseline/precedent.

The defensible distinction is an **externally scored evidence contract**: answer-linked frame/time plus pitch-region/trajectory support, provenance of visual versus metadata/commentary evidence, validity-aware calibrated abstention, and answer-preserving evidence/tool perturbations. SoccerChat's generation procedure makes visual-inferability auditing especially important.

## Version, rights, and integrity caveats

- Paper claims are bound to immutable arXiv **v1** (`2505.16630v1`). Metrics and dataset counts are author-reported and unreproduced.
- The current mutable Hugging Face dataset metadata differs from the paper snapshot and is therefore preserved separately at revision `eb86ef97533511a1d49efe29b92b2af00843edf8`.
- Full-text term absence can miss synonyms. The two `calibration` matches refer to camera calibration, not confidence calibration.
- The public model's Apache-2.0 metadata does not authorize SoccerNet-derived video. The dataset requires an active SoccerNet NDA; no access request, license acceptance, media, model weight, repository clone, dependency, or checkpoint acquisition occurred.
- The QA-generation prompt demonstrates a leakage/provenance risk but cannot establish that every final QA answer is unsupported by pixels; item-level review would be required.

## Local source anchors

- `artifacts/soccerchat-verification-2026-08-06/arxiv-2505.16630v1-api.xml`
- `artifacts/soccerchat-verification-2026-08-06/arxiv-2505.16630v1.html`
- `artifacts/soccerchat-verification-2026-08-06/paper-text.txt` (derived convenience text; HTML is canonical)
- `artifacts/soccerchat-verification-2026-08-06/github-repository-api.json`
- `artifacts/soccerchat-verification-2026-08-06/github-main-commit-api.json`
- `artifacts/soccerchat-verification-2026-08-06/github-tree-api.json`
- `artifacts/soccerchat-verification-2026-08-06/github-readme.md`
- `artifacts/soccerchat-verification-2026-08-06/hf-model-api.json`
- `artifacts/soccerchat-verification-2026-08-06/hf-model-card.md`
- `artifacts/soccerchat-verification-2026-08-06/hf-dataset-api.json` (metadata only; no gated files acquired)
- `artifacts/soccerchat-verification-2026-08-06/verification-summary.json`
