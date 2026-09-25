# Local VLM Viability Evidence‑Gap Candidate (v1)

## Sealed VLM/SoccerMaster‑Derived JSON Evidence Present
| File | Description |
|------|-------------|
| `.agent/soccermaster-scale-reproduction/test-event-reports.jsonl` | Sample event reports used for local reasoning checks.
| `.agent/soccermaster-scale-reproduction/test-predictions.jsonl` | Corresponding predictions from the local VLM model.

## Reproducible Local‑Model Viability Checks
- **Local inference**: The `test-event-reports.jsonl` can be parsed and matched against `test-predictions.jsonl` without external dependencies. No GPU or proprietary software required.
- **GPT reasoning viability**: GPT‑style prompts can be constructed from the JSON fields (e.g., event description, player actions) using only open‑source tooling.

## Unsupported Claims / Blocked Prerequisites
- **Model performance metrics**: No benchmark scores are available locally; external evaluation is blocked by data licensing.
- **Video processing**: Private footage cannot be processed; no local video evidence exists.
- **Third‑party API calls**: Not permitted without explicit approval.

## Summary
This candidate lists all admissible sealed JSON evidence, outlines reproducible checks that can run locally, and flags every claim that cannot yet be verified due to data or policy constraints.
