# Active Wake Public‑Source Frontier

## Context
The Sports Play LLM Research team is exploring provider‑neutral, rights‑failing benchmarks that can be executed without accessing proprietary media or invoking external inference services. This memo defines a benchmark concept, acceptance criteria, implementation handoff, and stop condition.

## Benchmark Concept
**Provider‑Neutral Rights‑Failing Video Retrieval Benchmark (PRR‑VRB)**
- **Goal:** Measure the ability of a retrieval model to locate short video clips that *do not* contain any copyrighted content, using only publicly available metadata and open‑source datasets. The benchmark deliberately fails when a clip is found to contain protected material.
- **Observed vs Proposed Labels:** 
  - *Observed*: Current model returns a set of candidate clips with associated confidence scores.
  - *Proposed*: A curated list of public‑domain or Creative‑Commons‑licensed clips that the model should retrieve. The benchmark flags any deviation as a failure.

## Acceptance Criteria (Three Measurable)
1. **Recall@5** – At least 70 % of the proposed public‑domain clips must appear in the top‑5 retrieval results for each query.
2. **Rights‑Fail Rate** – Zero instances where a retrieved clip is identified as containing copyrighted content by an automated rights‑check (e.g., metadata flag).
3. **Latency** – Average query latency ≤ 200 ms on a single CPU core, measured with the provided lightweight harness.

## Implementation Handoff
- **Repository:** `sports-play-llm/benchmarks/prr-vrb`
- **Key Files to Implement:"
  - `benchmark.yaml` – defines queries and expected public‑domain clips.
  - `rights_check.py` – simple metadata checker that flags non‑CC licenses.
  - `harness.py` – runs the retrieval model, measures latency, and aggregates metrics.
- **Instructions:** Clone the repository, install dependencies listed in `requirements.txt`, and run `python harness.py --config benchmark.yaml`. The script will output a JSON report with recall, rights‑fail rate, and latency.

## Stop Condition
If any of the acceptance criteria fail on two consecutive runs (e.g., recall drops below 70 % or a rights‑fail is detected), halt further benchmarking and flag the model for retraining or dataset curation.

---
*Prepared by the Sports Play LLM Research team – Active Wake Task e9953cde-9d87-4cca-92f9-b518d0f3a1e8*
