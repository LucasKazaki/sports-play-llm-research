# Active Wake Public‑Source Frontier

**Date:** 2026‑08‑31

## Objective
Create a research memo defining a provider‑neutral, rights‑failing benchmark or evaluation improvement for Sports Play LLM. The memo must include:
1. Observed‑versus‑proposed labels.
2. Three measurable acceptance criteria.
3. One exact implementation handoff.
4. One stop condition.

## Benchmark Concept
**Provider‑Neutral, Rights‑Failing Video Evaluation**
- **Observed Labels:** Current model outputs for a set of 10 publicly licensed soccer clips (e.g., from the public domain or Creative Commons). These are the *observed* predictions.
- **Proposed Labels:** A new labeling schema that annotates each clip with *event density* (number of distinct events per minute) and *action complexity* (binary high/low). The proposed labels are derived from a lightweight rule‑based extractor that does not require proprietary data.

## Acceptance Criteria
1. **Label Agreement Rate** – ≥ 85 % agreement between observed and proposed event density counts across the 10 clips.
2. **Complexity Accuracy** – ≥ 90 % accuracy of high/low action complexity classification compared to a human‑verified gold standard (publicly available annotations).
3. **Runtime Efficiency** – The rule‑based extractor must run in ≤ 5 s per clip on a single CPU core.

## Implementation Handoff
- **Tool:** `sports-play-llm-evaluator` CLI.
- **Command Template:**
  ```bash
  sports-play-llm-evaluator \
    --input-clips /path/to/public_clips/ \
    --output-metrics /tmp/eval_metrics.json \
    --rule‑extractor public_event_extractor.py
  ```
- **Artifact:** `public_event_extractor.py` (to be placed in the project’s `scripts/` directory). It implements the rule‑based labeling logic.

## Stop Condition
If any of the acceptance criteria fall below their thresholds, halt further benchmarking and flag a review task for manual inspection.

---
**Prepared by:** Sports Play LLM Research Team
