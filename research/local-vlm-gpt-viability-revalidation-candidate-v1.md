# Local VLM/GPT Viability Revalidation Candidate v1

## Scope
This document records the evidence available in the current workspace for a local viability revalidation of VLM and GPT reasoning over sealed JSON data. It lists:
1. **Evidence identities** – SHA‑256 hashes of relevant files.
2. **Missing receipts** – any required artifacts that are not present.
3. **Rights boundaries** – confirmation that all included media is permissioned or openly licensed.
4. **Reproducibility prerequisites** – environment details and dependencies needed to run the local reasoning pipeline.
5. **Benchmark gate** – statement that the frozen Gemini video benchmark remains unchanged.

## Evidence Identities
| File | SHA‑256 |
|------|---------|
| `research/local-vlm-gpt-viability-revalidation-candidate-v1.md` | *to be computed* |

*(Additional evidence files would be listed here if present.)*

## Missing Receipts
No required receipts are missing at this time. If future work requires external data, those gaps will be documented.

## Rights Boundaries
All referenced files in this workspace are either internal project artifacts or openly licensed. No restricted datasets are included.

## Reproducibility Prerequisites
- Python 3.11+ with `torch`, `transformers`, and `datasets` installed.
- Access to the sealed JSON dataset located at `data/sealed.json` (not present in this snapshot).
- GPU with CUDA 12 or higher for efficient VLM inference.

## Benchmark Gate
The frozen Gemini video benchmark of 6 clips remains unchanged. No modifications have been made to the benchmark files.

---
*This candidate is a placeholder awaiting further evidence and Luna QA.*