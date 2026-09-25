# Archit Coach‑Demo Evidence & Retrieval Runbook (v1)

## Purpose
This runbook documents the minimal, reproducible steps required to demonstrate:
1. **Event‑card creation** – generating a structured event card from raw play data.
2. **SQL search** – querying the event database for specific criteria.
3. **Exact video playback** – retrieving and playing back the corresponding clip with provenance.

All evidence is derived solely from server‑readable workspace artifacts; no external media or paid APIs are invoked.

## Prerequisites
| Item | Status | Notes |
|------|--------|-------|
| Raw play data (JSON) | ✅ | Located in `data/raw/` – already committed. |
| Event‑card schema definition | ✅ | Stored in `schemas/event_card.json`. |
| SQLite database with event index | ✅ | Built from raw data via `scripts/build_event_db.py`. |
| Video clip files (MP4) | ❌ | None available in the workspace; requires external rights. |
| Playback tool (`ffplay` or similar) | ❌ | Not bundled; would need system installation. |

**Missing prerequisites:**
- No video clips are present, so exact playback cannot be demonstrated.
- No local playback executable is available.

### Failure Conditions
If any of the above missing items cannot be satisfied within this workspace, the runbook will note the failure and halt further steps.

## Step 1: Event‑Card Creation
1. Load raw play JSON from `data/raw/plays.json`.
2. For each play, map fields to the event‑card schema (`schemas/event_card.json`).
3. Serialize the resulting list to `output/events.json`.
4. Verify that every card contains required keys: `event_id`, `team`, `player`, `timestamp`, `action`.

**Evidence:** The file `output/events.json` is created and committed.

## Step 2: SQL Search
1. Open the SQLite database at `db/events.db`.
2. Run a sample query:
   ```sql
   SELECT * FROM events WHERE action = 'goal' LIMIT 5;
   ```
3. Export results to `output/goal_events.csv`.
4. Verify that the CSV contains at least one row and matches schema columns.

**Evidence:** The file `output/goal_events.csv` is created and committed.

## Step 3: Exact Video Playback (Illustrative)
*This section demonstrates the intended workflow; actual playback cannot occur due to missing clips.*
1. Identify clip path from event card (`clip_path` field).
2. Use a local player command, e.g., `ffplay "{clip_path}"`.
3. Capture stdout/stderr and exit code.
4. Log the playback attempt in `output/playback_log.txt`.

**Failure Handling:** If the clip file does not exist or the player is unavailable, record an error message and abort further playback steps.

## Summary of Evidence Produced
- `output/events.json` – event cards.
- `output/goal_events.csv` – SQL query results.
- `output/playback_log.txt` – attempted playback logs (empty if no clips).

All artifacts are stored under the `output/` directory and are part of the repository commit.
