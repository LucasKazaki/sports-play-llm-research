# Archit Coach Demo Retrieval Candidate v1

## Versioned Candidate
This document records the current version of the coach demo and retrieval candidate. It is **not** promoted until Luna QA and Terra inspection are completed.

### Demo Evidence Plan
- **Event‑card creation**: Use the existing event‑card JSON contract (`research/event-card-schema.json`). The plan is to generate one card for a sample 10‑second clip from an openly licensed dataset. Provenance will be recorded by hashing the source video URL and noting the timestamp of generation.
- **SQL search**: Query the SQLite database (`data/coach_demo.db`) using the FTS5 index on event descriptions. The plan is to retrieve all cards matching a simple keyword query (“goal”) and record the SQL statement, execution time, and result set size.
- **Exact video playback**: Play back the retrieved clip in an embedded player (e.g., HTML5 `<video>`). The plan is to capture a short screenshot of the playback window and store it alongside the clip URL. No private footage is used; only openly licensed clips are referenced.

### Provenance & Retrieval Boundaries
- All source media referenced must be openly licensed or explicitly rights‑reviewed. URLs will be stored in `data/coach_demo_media.json` with accompanying license metadata.
- Retrieval boundaries are limited to the 10‑second clip segment defined in the event‑card. The SQL query is constrained to the `events` table and the FTS5 index.

### Visible Gaps
- No playback or search execution receipts have been captured yet; these will be added after a rehearsal run.
- The demo does not yet include user interaction logs or coach feedback.

## Next Steps
1. Perform a rehearsal run to generate actual receipts for event‑card creation, SQL search, and video playback.
2. Attach the receipts to this document as JSON blobs.
3. Submit for Luna QA.
