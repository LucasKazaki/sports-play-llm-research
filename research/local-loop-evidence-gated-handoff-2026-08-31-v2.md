# Purpose
The purpose of this document is to provide a corrected pre‑inference handoff for the local evidence‑gated SoccerMaster v1 protocol. It distinguishes the current state from the future protocol and specifies the exact artifacts that must be preserved by any executor.

## Verified Current Baseline
- The authorized private soccer corpus audit verified **9 opaque game groups**, **18 halves**, **50,120 seconds** (13.9222 h), and **3.407 GB** of video data. This corpus is development‑only and may be used for protocol engineering or rehearsal but never as a held‑out test set.
- Historical long‑form soccer VLM results are systems evidence only; post‑seal corroboration found only 3 of 166 annotations and 3 of 54 predictions corroborated, with no fully supported examples in direct review. No claim of accuracy or retrieval readiness is made.

## Frozen Evaluation Protocol
The frozen protocol resides at `research/soccermaster-evidence-gated-v1-protocol-2026-08-30.md` and is pre‑registered under hash `d0bf9809cb87491a088dc6abc85eef104c4950f773a2367d1de5239978fbc720`. It specifies:
- 40‑window held‑out design: 4 goal, 8 offside, 8 foul, 8 corner, 12 background windows.
- 13 frames per window, 30‑second context plus jitter.
- Two blinded proposals and a VLM evidence audit.

## Current Cohort Status
The fresh official held‑out cohort is **currently empty** because the official provider refuses TCP 443 before authentication. Therefore no new evidence‑gated score/run is authorized today. Once the provider becomes reachable, a bounded acquisition can create and freeze the fresh held‑out cohort under the pre‑registered manifest.

## Pre‑Inference Checklist
1. Verify that the frozen protocol file exists and its hash matches the registered value.
2. Confirm access to the development corpus (9 game groups, 18 halves).
3. Ensure no media from the private corpus is uploaded to third‑party models.
4. Prepare deterministic code for sampling, windowing, schema validation, and evidence ranking **without** assigning sports semantics.
5. Document any proposed changes to the protocol in a separate change log.

## Evaluation Boundaries
- Deterministic code may sample, window, validate schemas, and rank evidence but must never assign sports semantics.
- Commentary/ASR is post‑hoc only and cannot enter the primary visual inference condition.
- Restricted media must never be uploaded to third‑party models.

## Required Output Record
Any executor must preserve the following artifacts:
1. Frozen cohort manifest (once created).
2. Raw model responses.
3. Model/version configuration.
4. Prompt/schema hashes.
5. Timestamps/latency logs.
6. Evaluator proposal records.
7. Privacy audit report.
8. Append‑only result manifest.

## Stop Conditions
- If the official provider remains unreachable after a reasonable timeout, halt execution and log the status.
- If any attempt to upload restricted media to a third‑party model is detected, abort immediately and notify the director.
- If deterministic code attempts to assign sports semantics, terminate and record the violation.

---
**Note:** This handoff distinguishes verified facts from future checks. The private corpus remains development‑only; acquisition of a fresh held‑out cohort is permitted once the provider becomes reachable.
