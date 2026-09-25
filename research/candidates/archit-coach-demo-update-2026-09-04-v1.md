# Archit Coach‑Demo Update (v1)

## Overview
This document provides a concise update on the Archit project and outlines a short demo script for coaches. The demo covers:
1. **Event‑card creation** – how to generate event cards from raw data.
2. **SQL search** – querying the event database for specific play types.
3. **Exact video playback** – retrieving and playing back clip segments tied to events.

All functionality is derived solely from repository‑local evidence; no external media or licenses are referenced.

## Event‑Card Creation
- Use the `event_card_generator.py` script (see `src/event_card_generator.py`).
- Input: JSON payloads from SoccerMaster.
- Output: Markdown cards stored in `data/event_cards/`.

## SQL Search
- The SQLite database `data/events.db` contains tables `events`, `plays`, and `videos`.
- Example query:
```sql
SELECT * FROM events WHERE play_type = 'corner_kick' LIMIT 10;
```
- Results are exported to CSV via the `export_sql.py` utility.

## Exact Video Playback
- Clips are referenced by UUID in the database.
- Use the `playback_tool.py` (see `src/playback_tool.py`) with the clip ID to launch the local player.
- No external streaming; all media is locally stored and permissioned.

## Unsupported / Unavailable Features
| Feature | Status |
|---------|--------|
| Third‑party video analytics | Unavailable – no licensed data |
| Real‑time live feed integration | Unavailable – requires external API |

## Conclusion
This versioned candidate is ready for Luna QA. All paths referenced are within the repository and comply with policy.
