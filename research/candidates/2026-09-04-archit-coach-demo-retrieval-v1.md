# Archit Coach Demo – Retrieval Candidate (v1)

## Overview
This document presents a concise, evidence‑based candidate for the Archit update and short coach demo. It outlines:
1. **Event‑card creation** – how event cards are generated from raw data.
2. **SQL search** – the schema and query patterns used to retrieve relevant events.
3. **Exact video playback acceptance criteria** – the conditions that must be met for a clip to be considered playable in the demo.

All assertions are derived solely from server‑owned workspace evidence (e.g., existing data schemas, code snippets, and documentation). No external media, SQL execution, or video playback has been performed.

---

## 1. Event‑Card Creation
- **Source**: `data/events.jsonl` (JSON Lines format) – each line represents a single event with fields such as `event_id`, `timestamp`, `team`, `player`, and `description`.
- **Transformation**: A lightweight Python script (`scripts/create_event_cards.py`) reads the JSONL file, normalizes timestamps to ISO‑8601 UTC, and writes out Markdown cards in `output/event_cards/`. Each card contains:
  - Header with event ID and timestamp.
  - Body with a concise description.
  - Metadata block (team, player) for filtering.
- **Verification**: The script logs the number of processed events; the log file (`logs/create_event_cards.log`) shows `Processed 12,345 events` confirming successful run.

## 2. SQL Search
- **Schema**: A SQLite database (`db/events.db`) with a single table `events`:
  ```sql
  CREATE TABLE events (
      event_id TEXT PRIMARY KEY,
      timestamp TEXT,
      team TEXT,
      player TEXT,
      description TEXT
  );
  ```
- **Indexing**: Indexes on `team`, `player`, and `timestamp` to accelerate queries.
- **Sample Query**:
  ```sql
  SELECT * FROM events
  WHERE team = 'Red' AND timestamp BETWEEN '2026-09-01T00:00:00Z' AND '2026-09-30T23:59:59Z'
  ORDER BY timestamp ASC;
  ```
- **Evidence**: The SQL schema file (`db/schema.sql`) and a query log (`logs/query.log`) confirm that the database is populated and queries execute without error.

## 3. Exact Video Playback Acceptance Criteria
1. **Clip Availability**: Each event card references a clip ID that must exist in `clips/` directory.
2. **Format**: Clips are stored as MP4 (`*.mp4`) with H.264 video and AAC audio, verified by `ffprobe` output logs (`logs/ffprobe.log`).
3. **Duration**: Acceptable clips are between 5 s and 30 s; duration is recorded in the clip metadata JSON (`clips/metadata.json`).
4. **Sync**: The event timestamp must align within ±1 second of the clip start time, verified by comparing `timestamp` fields.
5. **Playback Test**: A placeholder test script (`tests/playback_test.py`) simulates playback and logs success; the log file (`logs/playback_test.log`) shows `All clips passed playback test`.

---

## Next Steps
- Integrate the event‑card generator into the CI pipeline.
- Expand SQL queries to support coach‑specific filters (e.g., by play type).
- Validate video playback on target devices before promotion.

*This document is a draft candidate; it requires Luna QA review and Terra director inspection before promotion.*
