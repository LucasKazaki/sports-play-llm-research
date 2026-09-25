# Local Evidence-Gated Execution Handoff

## Purpose
This document provides a concise, evidence-backed handoff for the local execution of the SoccerMaster v1 protocol. It specifies verified facts, future checks, stop conditions, and required artifacts to ensure compliance with the project’s privacy and inference constraints.

## Verified Current Baseline
- Private soccer corpus audit: 9 opaque game groups, 18 halves, 50,120 s (13.9222 h), 3.407 GB. Development-only unless a new held‑out cohort is acquired.
- Historical long‑form VLM results are systems evidence only; post‑seal corroboration found 3/166 annotations and 3/54 predictions supported. Direct review: 0/6 fully supported, 2 partial, 4 unsupported. No accuracy or retrieval readiness claims.

## Frozen Evaluation Protocol
The protocol is defined in `research/soccermaster-evidence-gated-v1-protocol-2026-08-30.md` (hash d0bf9809cb87491a088dc6abc85eef104c4950f773a2367d1de5239978fbc720). It prescribes:
- 40‑window held‑out design: 4 goal, 8 offside, 8 foul, 8 corner, 12 background.
- 13 frames per window, 30‑second context + jitter.
- Two blinded proposals and a VLM evidence audit.

## Pre-Inference Checklist
1. Verify that the frozen cohort manifest matches the protocol hash.
2. Ensure no fresh official‑cohort data is present (blocked due to TCP 443 refusal).
3. Confirm deterministic code samples, windows, validates schemas, and ranks evidence without assigning sports semantics.
4. Validate that commentary/ASR is post‑hoc only and not part of primary visual inference.
5. Verify restricted media has not been uploaded to third‑party models.

## Evaluation Boundaries
- Only the frozen cohort may be used; no new data acquisition.
- No sports semantics are assigned during deterministic processing.
- Commentary/ASR is excluded from primary inference.
- Restricted media must remain local and never be sent externally.

## Required Output Record
Future executors must preserve:
1. Frozen cohort manifest (protocol‑aligned).
2. Raw model responses.
3. Model/version configuration.
4. Prompt/schema hashes.
5. Timestamps/latency logs.
6. Evaluator proposal records.
7. Privacy audit report.
8. Append‑only result manifest.

## Stop Conditions
- Encounter of any non‑compliant data (e.g., external media, unauthorized inference).
- Failure to match protocol hash or frozen cohort structure.
- Detection of sports semantics assignment in deterministic code.
- Any attempt to upload restricted media to third‑party services.
- Breach of privacy audit requirements.

---
*Prepared for the local evidence‑gated SoccerMaster v1 execution.*