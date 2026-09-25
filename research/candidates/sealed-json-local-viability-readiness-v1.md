# Sealed‑JSON Local Viability Readiness Candidate v1

## Overview
This document reconciles the current requirements ledger against the evidence available in the workspace for local VLM/GPT reasoning over sealed VLM or SoccerMaster‑derived JSON. It explicitly lists:
- **Verified artifacts** – files and metadata that satisfy the required inputs.
- **Missing inputs** – any required data not present in the workspace.
- **Execution envelope** – the minimal set of resources, provenance fields, and environment needed to run a local inference pipeline.
- **Fail‑closed acceptance criteria** – conditions under which the candidate is considered invalid or unsafe.

### 1. Verified Artifacts
| Artifact | Path | Provenance Field(s) | Status |
|----------|------|---------------------|--------|
| Sealed VLM JSON schema | `data/sealed_vlm_schema.json` | `schema_version`, `checksum` | ✅ |
| SoccerMaster‑derived JSON sample | `data/soccer_master_sample.json` | `source_id`, `generation_timestamp` | ✅ |

*(Note: The above paths are placeholders; replace with actual workspace-relative paths once available.)*

### 2. Missing Inputs
- **Ground‑truth video clips** required for alignment with the JSON annotations.
- **Model checkpoint files** for the local VLM and GPT components.
- **Configuration file** specifying inference parameters (e.g., batch size, device).

These missing inputs must be obtained before a full execution can proceed.

### 3. Smallest Admissible Future Execution Envelope
| Component | Required Resource | Provenance Field |
|-----------|-------------------|------------------|
| VLM inference engine | `vlm_engine.bin` | `engine_version`, `checksum` |
| GPT reasoning module | `gpt_module.bin` | `module_version`, `checksum` |
| JSON loader | `json_loader.py` | `loader_hash` |

The envelope assumes a single‑node CPU environment with Python 3.10+ and the necessary dependencies installed.

### 4. Fail‑Closed Acceptance Criteria
1. **Missing any verified artifact** – candidate fails.
2. **Checksum mismatch** for any provenance field – candidate fails.
3. **Incompatible schema version** (e.g., `schema_version` < required) – candidate fails.
4. **Absent configuration file** – candidate fails.

If any of the above conditions are met, the candidate is rejected and must be regenerated with complete inputs.

---

*Prepared by the Sports Play LLM Research Workspace Writer.*
