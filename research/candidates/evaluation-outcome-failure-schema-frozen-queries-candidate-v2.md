# Versioned Evaluation Outcome and Frozen-Query Contract Candidate

## Overview
This document defines the versioned evaluation outcome and frozen-query protocol for the Sports Play LLM Research project. It is aligned with the requirements in `research/project-loop-info.md` and maintains the **SYSTEMS GO / SEMANTIC NO-GO** principle.

## Evaluation Outcome Schema

### Success Criteria
- All inputs are explicitly defined with hash, source, and provenance.
- Output matches expected format and structure as defined in the frozen query protocol.
- No model-generated content is used without explicit source attribution and provenance.
- All outputs are evaluated against a fixed, pre-defined set of inputs and expected outputs.

### Failure Criteria
- Missing or incomplete input definitions (e.g., missing hash, source, or provenance).
- Output format or structure does not match the defined schema.
- Answer-level provenance, rights, annotation, or adjudication evidence is absent.
- Model-generated content is used without explicit source attribution or provenance.
- Any evaluation result lacks a verifiable, server-owned mutation receipt.

## Frozen-Query Protocol

### Definition
A frozen query is a pre-defined, fixed input with a known expected output. It is used to validate the system's behavior under controlled conditions without running inference or retrieval.

### Requirements
- Each frozen query must include:
  - A unique identifier (UUID)
  - A clear description of the input
  - The expected output structure
  - The source of the input (if applicable)
  - The provenance of the input
  - The expected output format
- The query must be immutable and cannot be modified after creation.

### Usage
- Frozen queries are used to validate the system's behavior under controlled conditions.
- They are not used for scoring or performance evaluation.
- They remain unreviewed and unfrozen until independently verified by Luna QA and then Terra inspection.

## Absent Evidence Marking

Any evaluation that lacks answer-level provenance, rights, annotation, or adjudication evidence is explicitly marked as **non-evaluable**. This is in strict compliance with the project's governance and human gates.

## Governance and Human Gates

- All Archit-, coach-, publication-, or final-deliverable candidates must pass independent Luna QA and then explicit Terra director inspection before promotion.
- No restricted dataset acceptance, external communication, publication, commit, or paid API without approval.
- Unchanged-source checks are activity, not progress.

## Status
This candidate remains **unpromoted** and is pending independent Luna QA and later Terra inspection.

> **Note**: This document is a versioned candidate and does not constitute final deliverables. It is subject to independent review and validation before any promotion or publication.