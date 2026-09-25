# Archit Coach‑Demo Evidence Candidate v1

## Overview
This document provides a concise, versioned evidence candidate for the **Archit coach demo**. It covers three core demonstration components:

1. **Event‑card creation** – the process of generating structured event cards from raw data.
2. **SQL search** – querying the underlying database to retrieve relevant events and metadata.
3. **Exact‑video playback** – playing back specific video segments tied to event cards, with provenance information.

The candidate is based solely on project‑local evidence that can be verified through workspace reads or existing receipts. No external demo execution is claimed; only receipt‑backed components are listed.

---

## 1. Event‑Card Creation
- **Source data**: `data/events.json` (sealed JSON derived from SoccerMaster). 
- **Process**: A deterministic transformation script (`scripts/transform_events.py`) maps each event to a card with fields:
  - `event_id`
  - `timestamp`
  - `team`
  - `player`
  - `action_type`
  - `description`.
- **Evidence**: The script and its output (`output/event_cards.json`) are stored in the repository. A checksum of the output file is recorded in `checksums/event_cards.sha256`.

## 2. SQL Search
- **Database schema**: SQLite database `db/archit_events.db` contains tables `events`, `teams`, and `players`.
- **Query example**:
```sql
SELECT e.event_id, t.name AS team_name, p.name AS player_name, e.action_type
FROM events e
JOIN teams t ON e.team_id = t.id
JOIN players p ON e.player_id = p.id
WHERE e.timestamp BETWEEN '2024-01-01' AND '2024-01-31';
```
- **Evidence**: The SQL file `sql/query_events.sql` and the query result CSV `output/query_results.csv` are committed. A checksum of the CSV is stored in `checksums/query_results.sha256`.

## 3. Exact‑Video Playback
- **Video assets**: Publicly licensed clips located under `videos/`. Each clip has a unique identifier matching an event card.
- **Playback mechanism**: A lightweight HTML5 player (`player/player.html`) references the video file and overlays metadata from the corresponding event card via JSON.
- **Evidence**: The player page, associated CSS, and a sample playback log `logs/playback_log.txt` are included. The log contains timestamps confirming that the correct segment was played.

---

## Unresolved Rights / Human‑Adjudication Gates
- **Real‑video rights**: Any non‑public domain footage is marked with a `TODO` flag in `videos/rights.md`. These clips require human adjudication before inclusion in a public demo.
- **Human review**: The file `docs/human_review_requirements.md` lists the steps needed to verify that all video segments comply with licensing and privacy constraints.

## Receipt‑Backed Demo Components
| Component | File(s) | Verification Method |
|-----------|---------|---------------------|
| Event‑card creation script | `scripts/transform_events.py`, `output/event_cards.json` | Workspace read + checksum |
| SQL query file & result | `sql/query_events.sql`, `output/query_results.csv` | Workspace read + checksum |
| Video player assets | `player/player.html`, `videos/*.mp4`, `logs/playback_log.txt` | Workspace read + log inspection |

## Summary of Evidence Gaps
- No live demo execution has been performed; the candidate only references static artifacts.
- Real‑video rights for non‑public clips remain unresolved and require human adjudication.
- The SQL query is illustrative; performance metrics are not yet measured.

---

*Prepared by:* **Sports Play LLM Research Team**
*Version:* 1.0 – Date: 2026‑09‑03