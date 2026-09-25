# Versioned Local Reasoning Viability Candidate (v1)

## Overview
This document reconciles the current requirements ledger with the sealed VLM/SoccerMaster‑derived JSON evidence available in the project workspace. It specifies:

1. **Viable local GPT‑OSS reasoning inputs** – the exact prompt structure and data format that can be processed by an open‑source LLM without external API calls.
2. **Required provenance fields** – metadata that must accompany each JSON record to satisfy audit and reproducibility requirements.
3. **Abstention / fail‑closed behavior** – how the system should respond when evidence is missing or ambiguous.
4. **Missing receipts or gates** – a checklist of any required artifacts or permissions that are not yet satisfied.

### 1. Viable Local GPT‑OSS Reasoning Inputs
- **Input format**: A JSON array where each element represents a single soccer event extracted by SoccerMaster. Each element must contain:
  - `event_id` (string)
  - `timestamp` (ISO8601 UTC)
  - `description` (short natural‑language summary)
  - `player_ids` (array of strings)
  - `location` (object with `x`, `y` coordinates in field units)
- **Prompt template**:
```
You are a sports analytics assistant. Given the following event data, answer the question below.

Event Data: {EVENT_JSON}

Question: {QUESTION}
``` 
The model should output a concise JSON object with keys `answer` and `confidence` (0–1).

### 2. Required Provenance Fields
Each event record must include:
- `source_id`: Identifier of the SoccerMaster extraction run.
- `extraction_timestamp`: UTC timestamp when the JSON was generated.
- `checksum`: SHA‑256 hash of the raw event data to ensure integrity.
- `license`: Explicit statement that the data is public domain or has a permissive license.

### 3. Abstention / Fail‑Closed Behavior
If any required field is missing or malformed, the system must:
1. Log an error with the offending `event_id`.
2. Return a JSON object `{"answer": null, "confidence": 0}` for that event.
3. Flag the entire batch as *incomplete* in the audit log.

### 4. Missing Receipts or Gates
- **Receipt**: No server‑owned receipt exists yet for the provenance fields; a future task must generate SHA‑256 checksums and store them.
- **Gate**: The license field is not verified against an external registry; manual review required.

---
*Prepared by:* sports-play-llm-workspace-writer
*Date:* 2026-09-03
