# SportMV-Bench / SportMV-Agent novelty boundary for PlayGround

**Iteration:** 29  
**Accessed:** 2026-08-06  
**Primary source read:** Kerui Chen, Jinglu Wang, Xiaoyi Zhang, and Yan Lu, *Beyond the Single Camera: Agentic Multi-View Reasoning in Sports Video Understanding*, arXiv:2607.11844v1, submitted 2026-07-13, https://arxiv.org/abs/2607.11844v1  
**Evidence class:** primary author preprint, immutable v1 full HTML read; dataset and results are author-reported and were not reproduced.  
**Status:** research benchmark/system; no author code or benchmark-release link was found in the checked v1 HTML.

## Working interpretation

SportMV-Bench is a near-boundary benchmark for sports QA over several views of the same event. SportMV-Agent is a direct precedent for active view selection, perception-tool execution, accumulated textual evidence, and confidence-conditioned stopping. It is not an exact PlayGround match because its scored output is a multiple-choice answer rather than a required, externally scored answer-linked timestamp/frame plus pitch-region/trajectory evidence payload, and the checked paper does not evaluate answer abstention or calibration.

## Claim-level comparison

| Dimension | SportMV v1 (source-supported fact) | PlayGround target | Defensible implication |
|---|---|---|---|
| Task and scope | 787 multi-view bundles and 2,592 multiple-choice QA pairs from basketball and soccer, divided into PAR, REI, and ADR. | Fine-grained open-ended or structured QA over bounded 5–10 s soccer plays. | Do not claim sports QA, referee-style questions, or event-level reasoning as novel. The short-play scope must earn value through finer externally scored grounding and abstention. |
| Source | Basketball is taken from the NBA official replay archive; soccer is taken from SoccerNet's multi-view organization; paired official referee reports provide answer sources. The views for an event are not necessarily synchronized. | Rights-governed source chosen and approved before acquisition. | SportMV's use of public/official sources is precedent, not authorization for this project. Keep the rights gate. Unsynchronized views are a useful future validity field, not a reason to expand the initial single/broadcast-view pilot. |
| QA construction | Four stages: source/report collection, report-grounded LLM multiple-choice proposal, repeated MLLM filtering, and human filtering. Candidate failures include deviation from the referee report, commonsense-only answerability, misalignment with video, insufficient visual evidence, and hallucinated events. | Human-authored/verified answer and evidence records with leakage controls. | Add SportMV's documented support, play-specificity, visual-inferability, and hallucinated-event checks to pilot item review. Answer-leakage control remains a separate existing design requirement, not a SportMV finding. |
| Multi-view baseline | All views are concatenated with view identifiers; the model must implicitly select and fuse evidence. | Direct video-VLM baseline over the approved clip input. | If a lawful multi-view extension becomes available, compare random/all/best/guided view conditions rather than assuming more views help. This is not required for the initial pilot. |
| Agent architecture | An orchestrator iterates over active view selection and action/contact/contact-part perception tools, accumulating evidence until it considers confidence sufficient. | Direct, retrieval, structured-tool, oracle, and noisy-tool variants under one output schema. | Active view selection, confidence-conditioned evidence collection, tool routing, and textual evidence accumulation are prior art—not headline novelty. |
| Evidence object | Internal state contains accumulated textual evidence and tool outputs; qualitative examples show view switching/tool invocation. | Every answer must submit timestamp/frame evidence and pitch-region/trajectory evidence when applicable. | Calling reasoning “evidence-grounded” does not establish external evidence faithfulness. Score submitted evidence independently and intervene on it. |
| Uncertainty/abstention | “Sufficient confidence” controls whether the agent continues or emits an answer; action/tool confidence values are also used. Full-text inspection found no `abstain`, `uncertainty`, or `calibration`. | Calibrated answer confidence, explicit insufficient-evidence abstention, selective risk/coverage, ECE/Brier. | Confidence-conditioned stopping is prior art, but answer calibration and abstention remain open in this source. Do not conflate tool confidence with answer confidence. |
| Spatial/trajectory grounding | Full-text inspection found no `trajectory` or `pitch`; `coordinate` occurs in general localization/reference contexts, not a required answer-linked pitch-coordinate score. | Answer-linked pitch regions or trajectories, with GSR validity masks. | The externally scored soccer-coordinate/trajectory axis remains distinct in this checked source. |
| Reported results | GPT-4.1 baseline: 59.68% overall; SportMV-Agent: 68.31%, an author-reported 14.46% relative gain. Removing active view selection yields 61.03% overall (7.28 points below the full agent). | Report answer, grounding, calibration, and intervention outcomes separately. | Treat these as author-reported motivation only; task/output differences prevent direct performance comparison. |
| Controlled findings | For Qwen3-VL-30B, all-view overall accuracy is 44.89%, best-view 47.57%, and guided multi-view 50.75%. Ground-truth perception tools raise GPT-4.1 from 59.68% to 76.15% (+16.47 points). | Oracle/noisy tools and validity-aware failure propagation. | Supports oracle/noisy-tool controls and view-quality controls, but does not demonstrate PlayGround benefit. |
| Reproducibility | v1 states model/tool roles and reports tables/ablations, but the checked HTML exposes no author project/code/dataset-release link. | Public schema, deterministic evaluator, tests, prompts/configs, and hash-bound receipts. | Label SportMV as a research system, not working open source. Reproducibility remains a possible advantage for PlayGround. |

## Decision

Retain the north-star but narrow its architecture claim. PlayGround must not claim novelty for multi-view sports QA, active view selection, confidence-conditioned evidence collection, specialist perception tools, or “evidence-grounded” agent orchestration. SportMV-Agent becomes a near-boundary comparator/design precedent if authorized multi-view data is later available. The defensible contribution remains the **externally scored evidence-and-uncertainty contract**: answer-linked time/frame and soccer-coordinate evidence, upstream-validity-aware abstention, calibration/selective risk, and answer-preserving evidence/tool interventions.

The initial 50-clip rights-governed pilot should not expand to multi-view merely because this paper exists. Instead, incorporate its source-consistency, play-specificity, visual-inferability, and hallucinated-event checks into item review and preserve a future multi-view extension as a preregistered optional axis.

## Version and integrity caveats

- All numeric claims above are from immutable **v1**, not the current latest version.
- The unversioned arXiv API returned `2607.11844v2`, whose abstract reports 1,022 bundles, 3,015 QA pairs, and 15.61% relative improvement. These values were deliberately not merged with v1 claims. The versioned v1 API snapshot returned `2607.11844v1`.
- The paper's visible `CC BY 4.0` label applies to the paper. It does not establish authorization to acquire or redistribute NBA/SoccerNet videos or the benchmark media.
- Dataset sizes, model accuracy, and ablations are author-reported and unreproduced. Full-text term absence can miss synonyms.
- No media, dataset, model, checkpoint, code repository, or restricted asset was acquired in this iteration.

## Local source anchors

- `artifacts/multiview-sports-verification-2026-08-06/arxiv-2607.11844v1.html`
- `artifacts/multiview-sports-verification-2026-08-06/arxiv-2607.11844v1-api.xml`
- `artifacts/multiview-sports-verification-2026-08-06/arxiv-2607.11844-api.xml` (latest-version metadata snapshot; used only to document version drift)
- `artifacts/multiview-sports-verification-2026-08-06/arxiv-2607.11844v1.txt` (derived convenience text; HTML is canonical)
