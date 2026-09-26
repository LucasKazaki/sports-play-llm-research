# Sealed‑JSON Local Reasoning Viability Candidate

## Purpose
This document defines the design for a **sealed JSON local‑model viability candidate**. It specifies:

1. **Admissible sealed VLM/SoccerMaster‑derived JSON inputs** – the structure, required fields, and provenance constraints.
2. **Fail‑closed provenance and rights gates** – conditions under which the candidate must abort or flag unresolved permissions.
3. **Non‑claiming local GPT‑OSS/GPT reasoning checks** – how to perform reasoning without asserting benchmark results or model performance claims.
4. **Explicit missing evidence requirements** – what evidence is needed before any benchmark result can be reported.

The goal is to produce a versioned, receipt‑backed design that can be reviewed by Luna QA and the director without executing models or fabricating data.

---

## 1. Admissible Sealed VLM/SoccerMaster‑Derived JSON Inputs

| Field | Type | Description | Provenance Requirement |
|-------|------|-------------|------------------------|
| `metadata` | object | High‑level description of the dataset (e.g., sport, season). | Must reference a public or licensed source with a verifiable URL.
| `events` | array | List of event objects. | Each event must include a unique identifier and timestamp.
| `event_type` | string | Type of event (e.g., pass, shot, tackle). | Must be one of the enumerated types defined in SoccerMaster schema.
| `player_ids` | array | IDs of players involved. | Each ID must map to a public player profile with a verifiable source.
| `location` | object | Spatial coordinates (x,y) on the pitch. | Coordinates must be within valid pitch bounds.
| `confidence_score` | number | Model confidence for event detection. | Must be between 0 and 1 inclusive.

**Sealing Rules**
- The JSON file must be signed with a SHA‑256 hash that is stored in an accompanying `.sig` file (not created here but required for future validation).
- No sensitive personal data may be included; all identifiers must be pseudonymized unless publicly available.

## 2. Fail‑Closed Provenance and Rights Gates

| Gate | Condition | Action |
|------|-----------|--------|
| `public_source` | All referenced URLs are from open licenses (e.g., CC0, MIT) or public domain. | Pass |
| `non_exclusive_use` | No exclusive rights granted that would restrict downstream use. | Pass |
| `no_confidential_data` | No PII or proprietary data present. | Pass |
| `verified_hash` | SHA‑256 hash matches the signed `.sig`. | Pass |

If any gate fails, the candidate must **abort** and record the failure reason in a separate log (not created here). The document should include a section titled *Unresolved Gates* listing any failures.

## 3. Non‑Claiming Local GPT‑OSS/GPT Reasoning Checks

- Reasoning steps are described textually; no model inference is executed.
- Each reasoning step references the relevant JSON field and explains how it would be used by a local VLM.
- No performance metrics, accuracy claims, or benchmark results are included.

Example:
> *Reasoning Step 1:* The `confidence_score` of 0.87 indicates high confidence that the event is a pass. A local VLM could use this threshold to filter events for further analysis.

## 4. Explicit Missing Evidence Requirements

Before any benchmark result can be reported, the following evidence must be collected:
1. **Source Receipt** – A verifiable link or DOI to the original dataset.
2. **License Confirmation** – Documentation that the data is licensed under an open license permitting research use.
3. **Hash Verification** – The SHA‑256 hash of the JSON file and its corresponding `.sig` file.
4. **Pseudonymization Proof** – Evidence that all player IDs are pseudonymized or publicly available.

These items should be stored in a separate evidence repository (not created here). Until they are present, the candidate remains *unverified*.

---

## Versioning
- **Version:** 1.0.0
- **Date:** 2026‑09‑04
- **Author:** sports-play-llm-workspace-writer

---

## Next Steps
- Submit this document to Luna QA for review.
- Await confirmation of missing evidence before proceeding to benchmark execution.
