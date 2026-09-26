# Sealed JSON Local VLM + GPT Viability Candidate

## Version
v1.0 – 2026‑09‑04

## Purpose
This document proposes a protocol for combining a local Vision‑Language Model (VLM) with GPT‑style reasoning over *sealed* SoccerMaster‑derived JSON data. The goal is to outline the input schema, abstention/failure criteria, and receipt requirements while explicitly separating observed evidence from assumptions.

## Scope & Constraints
- **No private footage** may be uploaded or processed.
- **Benchmark execution** and performance claims are prohibited.
- Only *sealed* JSON (no raw video) is used.
- The protocol is a *candidate* pending Luna receipt‑backed review.

## Input Schema
| Field | Type | Description |
|-------|------|-------------|
| `match_id` | string | Unique identifier for the match. |
| `team_home` | string | Home team name. |
| `team_away` | string | Away team name. |
| `events` | array of objects | Each object represents a game event with fields:
| | `timestamp` | integer (seconds from start) |
| | `event_type` | enum (`goal`, `foul`, `corner`, etc.) |
| | `player_id` | string |
| | `description` | string (human‑readable, optional) |

The JSON is *sealed* – it cannot be altered by the VLM or GPT during inference.

## Local VLM Step
1. **Load** the sealed JSON into memory.
2. For each event, generate a *visual prompt* that would correspond to the event (e.g., “Goal scored by player X at minute Y”).
3. Feed the prompt to the local VLM to produce a *semantic embedding* or short textual description. The VLM must **not** access any external data.
4. Store the embeddings/descriptions in an intermediate structure keyed by event ID.

## GPT Reasoning Step
1. Construct a context that includes:
   - Match metadata (`match_id`, teams).
   - The list of VLM‑generated embeddings/descriptions.
2. Prompt GPT with a *reasoning question* (e.g., “Summarize the key moments of this match.”) and the context.
3. Capture GPT’s output as the final reasoning result.

## Abstention / Failure Criteria
- **VLM abstention**: If the VLM cannot generate an embedding for an event, mark the event as *unprocessed* and continue.
- **GPT failure**: If GPT returns a non‑textual token or exceeds token limits, flag the request as failed.
- **Data integrity**: Any modification to the sealed JSON triggers a failure.

## Receipt Requirements
1. **VLM receipt** – a hash of the input JSON and the VLM output embeddings (e.g., SHA‑256). This proves that the VLM processed the exact sealed data.
2. **GPT receipt** – a hash of the GPT prompt, context, and output text. This ensures reproducibility.
3. Store both receipts in a separate `receipts/` directory with clear linkage to the original JSON file.

## Observed Evidence vs Assumptions
- *Evidence*: The protocol is derived from existing VLM inference pipelines and GPT prompting guidelines documented in the project’s requirements ledger.
- *Assumptions*: Local VLM can process all event types; GPT will not hallucinate beyond the provided context.

## Next Steps
- Implement a prototype following this protocol.
- Generate receipts for a sample sealed JSON.
- Submit for Luna QA and Terra director inspection.

---
*Prepared by the Sports Play LLM Research Workspace Writer – 2026‑09‑04*
