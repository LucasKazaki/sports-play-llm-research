# Sealed VLM Input Viability Candidate v1

## Purpose
This document defines the minimum sealed JSON input contract for local VLM/GPT‑OSS reasoning. It specifies required provenance identifiers, clip/time bindings, rights-state field, synthetic/real separation, abstention behavior, and receipt‑required evaluation boundary.

## Contract Specification
```json
{
  "provenance": {
    "source_id": "<unique identifier of the source asset>",
    "timestamp": "<ISO8601 UTC timestamp of provenance capture>"
  },
  "clip_bindings": [
    {
      "clip_id": "<unique clip identifier>",
      "start_time_ms": <integer>,
      "end_time_ms": <integer>
    }
  ],
  "rights_state": "sealed", // other possible values: "unsealed", "public"
  "synthetic_real": {
    "type": "real" | "synthetic",
    "description": "<brief description of synthetic generation process if applicable>"
  },
  "abstention_behavior": {
    "allow_abstain": true,
    "abstain_reason": "<reason for abstention, e.g., insufficient data>"
  },
  "evaluation_boundary": {
    "require_receipt": true
  }
}
```

## Notes
- **No model execution**: This contract is purely a specification; no VLM or GPT model has been invoked.
- **No benchmark results**: No performance metrics are attached to this document.
- **Rights state**: The `sealed` value indicates that the content is protected and cannot be altered without proper authorization.
- **Synthetic/real separation**: Explicitly distinguishes whether the clip originates from real footage or synthetic generation.
- **Abstention behavior**: Allows a reasoning system to abstain with an explicit reason when data is insufficient.
- **Evaluation boundary**: Requires a receipt (e.g., cryptographic hash) before any evaluation can proceed, ensuring integrity.

---
*This document is versioned as v1 and serves as the baseline for future sealed VLM input contracts.*