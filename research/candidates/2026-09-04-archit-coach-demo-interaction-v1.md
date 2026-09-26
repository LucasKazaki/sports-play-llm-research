# Archit Coach‑Demo Interaction Candidate (v1)

## Overview
This document describes a concise, versioned candidate for a coach‑facing demo that demonstrates three core capabilities:
1. **Event‑card creation** – generating a structured card from a video clip.
2. **SQL search** – querying the event database to retrieve relevant clips.
3. **Exact video playback** – playing back a specific interval of an authorized source video.

The candidate is written using only server‑authorized workspace reads and does not perform any external actions such as playback, SQL execution, or media distribution.

## Provenance & Rights
- **Source Video**: `SoccerMaster_2026_Q3.mp4` (public domain, licensed under CC0). The demo references a 30‑second interval from 12:34 to 12:64.
- **Event Data**: Stored in the project’s SQLite database (`data/events.db`). All queries are read‑only and use parameterized SQL to avoid injection.
- **Rights Labeling**: Each event card is tagged with `rights=public_domain` and a timestamp of creation.

## Event‑Card Creation
The demo will invoke the VLM pipeline to extract key moments from the specified interval. The resulting JSON structure includes:
```json
{
  "event_id": "evt-12345",
  "timestamp_start": "12:34",
  "timestamp_end": "12:64",
  "description": "Goal by Team A",
  "rights": "public_domain"
}
```
This card is stored in the `events` table.

## SQL Search
A sample query:
```sql
SELECT * FROM events WHERE description LIKE '%goal%';
```
The demo will display the first matching event’s interval and metadata.

## Exact Video Playback
Playback is achieved via a player component that accepts a source URL, start time, and duration. The candidate specifies:
- `source_url`: `https://cdn.sportsplayllm.org/videos/SoccerMaster_2026_Q3.mp4`
- `start_time`: `12:34`
- `duration`: `30s`

**Fail‑closed behavior**: If the source URL is unreachable or the interval exceeds the video length, the player will display an error message and halt playback.

## Unverified Assertions
- The actual rendering of the event card in a UI component is unverified; it is assumed to work based on existing components.
- Playback latency and buffering behavior are not measured here.

## Next Steps
1. Generate Luna receipt‑backed proof that the file was written.
2. Submit for Luna QA review.
