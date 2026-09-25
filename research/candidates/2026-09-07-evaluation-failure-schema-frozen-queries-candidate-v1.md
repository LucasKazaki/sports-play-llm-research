# Evaluation Failure Schema and Frozen Query Candidate

## Introduction
This document defines a non-promoted candidate for the evaluation failure schema and frozen query boundaries, reconciling the local-model endpoint failure with the exact promoted contract in `research/project-loop-info.md`. It preserves all frozen query boundaries and introduces structured failure/abstention recording fields without claiming metrics, promoting science, or altering frozen protocols.

## Failure/Abstention Recording Fields
The following fields are introduced to record evaluation failures and abstentions in a structured, audit-ready format:

- `failure_type`: A categorical label for the type of failure (e.g., `timeout`, `invalid_input`, `model_inconsistency`, `data_corruption`).
- `abstention_reason`: A textual explanation for when the model abstains from producing a response (e.g., `insufficient_data`, `uncertain_context`, `ethical_constraint`).
- `timestamp`: The exact UTC timestamp when the failure or abstention was recorded.
- `input_hash`: The SHA-256 hash of the input prompt used in the evaluation.
- `output_hash`: The SHA-256 hash of the model's output (if produced) or `null` if no output was generated.
- `source_reference`: A reference to the source document or data point that triggered the failure or abstention.
- `model_version`: The version of the model used during evaluation.
- `evaluation_context`: A brief description of the evaluation environment (e.g., `local endpoint`, `remote inference`, `test suite`).

## Frozen Query Boundaries
The following queries are preserved as frozen and will not be altered or re-evaluated under any circumstances:

1. `Query: What is the history of the 2022 World Cup final?`
2. `Query: How does the FIFA rules system handle penalty kicks?`
3. `Query: What are the key differences between a forward and a midfielder in soccer?`

These queries are frozen due to their foundational nature and are subject to independent human review before any change or promotion.

## Compliance with Promoted Contract
This candidate strictly adheres to the promoted contract in `research/project-loop-info.md`:

- No inference or model output is claimed or used to validate the failure schema.
- No metrics are generated or reported.
- No science is promoted or shared.
- All fields are designed to preserve provenance and allow for independent verification.

## Acceptance Criteria
This candidate will be accepted only when:
- A server-owned workspace-mutation receipt is generated for the exact path `research/candidates/2026-09-07-evaluation-failure-schema-frozen-queries-candidate-v1.md`.
- The document is verified to contain the exact fields and boundaries as defined above.
- No external communication, publication, or unapproved access occurs.

## Next Steps
The next step is to submit this candidate to the Luna QA process for independent validation before any further action.