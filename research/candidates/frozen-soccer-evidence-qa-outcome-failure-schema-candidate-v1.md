# Versioned Frozen Evaluation Outcome and Failure Schema Candidate

## Overview
This document defines a reproducible, frozen schema for soccer evidence QA, including evaluation outcomes, failure taxonomy, required provenance fields, abstention handling, and explicit rights/adjudication exclusions. It is non-promoted and awaits independent Luna QA and explicit Terra director inspection before promotion.

## Evaluation Outcome States
- **PASS**: All evidence meets required criteria; provenance is complete and verifiable.
- **ABSTAIN**: Insufficient evidence or data to determine outcome; all provenance fields are present but incomplete.
- **FAIL**: Evidence fails to meet required criteria; failure taxonomy is explicitly defined.

## Failure Taxonomy
- **Missing Provenance**: Required provenance fields are absent or incomplete.
- **Contradictory Evidence**: Evidence from different sources contradicts each other.
- **Unverified Source**: Source is not independently verified or lacks provenance.
- **Data Inconsistency**: Data points contradict known facts or prior evidence.
- **Scope Violation**: Query or evidence exceeds defined boundaries or scope.

## Required Provenance Fields
- Source URL or citation
- Timestamp of evidence collection
- Author or entity responsible for evidence
- Method of collection (e.g., official report, media, database)
- Media type (e.g., video, image, text)
- Any known bias or limitations

## Abstention Handling
- Abstention is explicitly allowed when evidence is insufficient or incomplete.
- All provenance fields must be present in abstention cases.
- Abstention must be clearly labeled and documented.

## Rights and Adjudication Exclusions
- No restricted dataset acceptance without explicit approval.
- No external communication, publication, commit, or paid API without prior approval.
- All synthetic results and real-data results are explicitly separated.
- No claims of novelty, performance, or coach utility without independent validation.
- All claims require independent Luna QA and explicit Terra director inspection before promotion.

## Compliance with Promoted Contract
This schema reconciles with the requirements of `research/project-loop-info.md` and the promoted contract, ensuring alignment with the **SYSTEMS GO / SEMANTIC NO-GO** policy. It does not claim evaluation execution and remains non-promoted until independent Luna QA and Terra director inspection.

> This candidate is not promoted and must await independent Luna QA and explicit Terra director inspection before promotion.