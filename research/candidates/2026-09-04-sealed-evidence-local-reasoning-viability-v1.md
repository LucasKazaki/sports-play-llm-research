# Versioned Sealed‑Evidence Local Reasoning Viability Candidate (v1)

## 1. Purpose
This document defines the admissible sealed JSON inputs, required provenance fields, abstention/fail‑closed behavior, and the exact evidence still needed before any local VLM/GPT performance claim can be made.

## 2. Version
- **Version:** 1.0
- **Date:** 2026‑09‑04
- **Author:** sports-play-llm-workspace-writer

## 3. Admissible Sealed JSON Inputs
| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | Unique identifier for the sporting event.
| `video_segment` | object | `{"start":<seconds>, "end":<seconds>}` defining the clip bounds.
| `metadata` | object | Immutable, signed metadata (e.g., source, timestamp).

All fields must be JSON‑encoded and cryptographically sealed using the project’s public key infrastructure. No additional keys or signatures are accepted.

## 4. Required Provenance Fields
The sealed payload must include:
1. `source_url` – URL of the original video (must be publicly licensed or internal).
2. `license_type` – SPDX identifier of the license.
3. `checksum_sha256` – SHA‑256 hash of the raw video segment.
4. `timestamp_utc` – ISO 8601 UTC timestamp when the clip was extracted.
5. `extractor_id` – Identifier of the tool that performed extraction.

All provenance must be verifiable against a trusted registry maintained by the project.

## 5. Abstention / Fail‑Closed Behavior
- If any required field is missing or malformed, the system must **abstain** from processing and return an error code `E_MISSING_FIELD`.
- If provenance verification fails (e.g., checksum mismatch), the system must **fail closed** with error code `E_PROVENANCE_FAIL` and log the incident for audit.
- No partial processing is allowed; the entire payload is treated atomically.

## 6. Evidence Still Needed
Before claiming local VLM/GPT performance:
1. **Benchmark Results:** Quantitative metrics (e.g., accuracy, F1) from a controlled test set of at least 10 sealed clips.
2. **Model Versioning Proof:** Signed hash of the exact model weights used for inference.
3. **Runtime Environment Snapshot:** Docker image digest or VM configuration that reproduces the inference environment.
4. **Human Review Log:** Record of a human annotator confirming correct extraction and provenance for 5 random samples.

These artifacts must be stored in the project’s evidence repository with immutable timestamps.

---
*Prepared by the Sports Play LLM Research Workspace Writer.*