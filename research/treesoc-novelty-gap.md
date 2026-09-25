# TreeSoc vs. PlayGround: claim-level novelty comparison

**Accessed:** 2026-08-06  
**Primary paper:** Thanh-Nhan Vo, Thanh-Khoi Nguyen, Trong-Thuan Nguyen, Trung-Hoang Le, and Minh-Triet Tran, “TreeSoc: Tree-Structured Dynamic Reasoning and Tool Synergy for Soccer Video Understanding,” arXiv:2607.10990v1, submitted 2026-07-13.  
**Paper URL:** https://arxiv.org/abs/2607.10990v1  
**Author-linked repository:** https://github.com/thanhnhan29/TreeSoc

## Working interpretation

TreeSoc is a **research prototype / claimed reference implementation**, not a publicly evidenced deployment. It is a direct near-neighbor for tool-augmented soccer VQA, but not for PlayGround’s proposed benchmark contract: externally scored timestamp/frame evidence, pitch-region/trajectory evidence, calibrated confidence, and abstention.

## Comparison matrix

| Dimension | TreeSoc (paper-supported fact) | PlayGround target | Novelty implication |
|---|---|---|---|
| Core task | SoccerBench TextQA, ImageQA, and VideoQA plus zero-shot NExT-QA; SoccerBench is described as 500 public-test samples across 14 task types. | Fine-grained questions about bounded 5–10 s soccer plays. | Short-play scope is narrower; it must be justified through evidence resolution and coach utility, not “soccer VQA” alone. |
| Reasoning architecture | Qwen3.5-9B coordinator decomposes queries into a hierarchical task tree, traverses with dynamic DFS, accumulates intermediate state, and routes to specialist tools/retrieval. | Compare direct VLM, retrieval-augmented, and structured tool-augmented game-state reasoning. | Generic tool orchestration/tree search is **not** a defensible novelty claim after TreeSoc. Treat it as a baseline/design precedent. |
| Perception/tools | Paper describes YOLO26, PRTReID, face recognition, jersey-region extraction, OCR, replay retrieval, UniSoccer, camera/foul modules, and external databases. | Minimal tools sufficient for timestamp/frame and pitch/trajectory evidence. | Prefer a controlled, inspectable tool set and ablations over a broad task-specific stack. |
| Temporal evidence | Intermediate context can include timestamps; paper describes temporal localization and replay retrieval. | Every answer must return and be scored against timestamp/frame evidence. | “Uses temporal evidence internally” is insufficient novelty. The differentiator is a required, externally scored evidence payload. |
| Spatial evidence | Tactical mapping uses pitch geometry/spatial distribution for role assignment; no reported benchmark metric for answer-linked pitch regions or trajectories. | Every spatially answerable item returns pitch-region/trajectory evidence and is scored for grounding. | External answer-linked spatial provenance remains an open gap in this source. |
| Answer evidence/provenance | Intermediate tool outputs are injected as compact semantic evidence; final outputs are multiple-choice or formatted open-ended answers. No answer-level citation/evidence score is reported. | Answer plus explicit evidence spans/regions, with evidence quality scored separately from correctness. | This is the clearest novelty boundary: faithful provenance as an evaluation target rather than hidden reasoning context. |
| Confidence/abstention | The only explicit confidence value is an object-detector threshold. The conclusion lists uncertainty-aware replanning as future work; no abstention metric or selective-risk curve is reported. | Calibrated confidence, explicit insufficient-evidence abstention, coverage-risk/ECE/Brier evaluation. | Uncertainty and abstention remain a defensible contribution axis. |
| Reported results | Authors report 85.2% TextQA, 87.4% ImageQA, 82.2% VideoQA on SoccerBench and 74.16% NExT-QA overall. | Report answer, grounding, calibration, and selective-risk metrics, with real-data claims separated from synthetic harness tests. | Do not compare future PlayGround numbers directly unless task set and evaluation protocol are aligned. |
| Baselines | Table 1 compares commercial APIs, open-source models, and SoccerAgent. | Direct VLM, retrieval-augmented, tool-augmented structured state, and oracle/tool-noise controls. | Match TreeSoc’s direct/agentic comparison breadth, then add grounding and uncertainty controls. |
| Ablations | Section 5.2 calls an NExT-QA category breakdown an “ablation analysis,” but Table 2 reports only TreeSoc scores by question category; no remove-tree/remove-tool/remove-replanning component variants are shown. | Remove retrieval, temporal evidence, spatial evidence, confidence gate, and tool components; test evidence corruption/tool noise. | A preregistered component and tool-noise ablation suite is a concrete rigor advantage. |
| Failure analysis | Qualitative failures include distraction by salient secondary actions and propagation from incorrect player grounding. | Quantify answer–evidence consistency, error propagation, and abstention under insufficient/corrupted evidence. | Convert TreeSoc’s qualitative failure modes into measurable benchmark perturbations. |
| Reproducibility status | Paper provides core model, seed, and some generation/tool parameters. On 2026-08-06 the author-linked GitHub repository API reported repository size 0, and raw `README.md` contained only `# TreeSoc`; no runnable code was inspectable. | Public schema, deterministic evaluator, tests, baseline prompts/configs, and hash-bound receipts. | Reproducibility can be a meaningful advantage. Do not label TreeSoc “working open source” based only on the paper’s code-available sentence. |

## Decision

**Retain the north-star, but tighten the novelty claim.** PlayGround should not claim novelty from using tools, retrieval, specialist modules, or dynamic reasoning for soccer VQA. Its contribution should be framed as an **evidence-and-uncertainty evaluation contract** for short plays, plus controlled evidence/tool ablations:

1. answer correctness is separated from timestamp/frame and pitch/trajectory grounding;
2. confidence and abstention are mandatory and evaluated with calibration/selective-risk metrics;
3. direct, retrieval, structured-tool, and oracle/noisy-tool variants are compared under the same schema;
4. evidence corruption and wrong-grounding propagation are measured explicitly.

## Evidence limitations

- All performance values are author-reported in arXiv v1 and were not independently reproduced here.
- SoccerBench’s paper-reported 500-sample public test is not equivalent to the proposed 5–10 s short-play corpus.
- The HTML conversion duplicates some decimal strings (for example, `0.30.3`); parameter values should be checked against the PDF/source before reproduction.
- Repository state is mutable. The API/README snapshot and hashes in `experiments/2026-08-06-iteration-002-treesoc-verification.md` preserve what was observed on the access date.
