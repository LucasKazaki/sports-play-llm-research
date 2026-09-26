# Archit Coach Demo Candidate v0

## Concise Archit Update

This document provides a non‑promoted, evidence‑placeholder version of the Archit update and a short demo flow for coaches. It includes:

1. **Event‑card creation** – outline of how event cards are generated from raw data.
2. **SQL search** – example query template used to retrieve relevant clips.
3. **Exact video playback** – description of the playback mechanism and its dependency on rights, source binding, and receipt evidence.

---

### 1. Event‑Card Creation

- Input: JSON metadata extracted from a VLM or SoccerMaster pipeline.
- Process: Map fields to a standardized event‑card schema (e.g., `event_type`, `timestamp`, `player_id`).
- Output: Markdown/JSON card ready for coach review.

### 2. SQL Search Example

```sql
SELECT clip_id, start_time, end_time, description
FROM clips
WHERE sport = 'soccer'
  AND event_type = 'goal'
ORDER BY start_time ASC;
```

*This query is illustrative; actual schema may vary.*

### 3. Exact Video Playback

- Playback requires:
  - **Rights clearance** for the specific clip.
  - **Source binding** to a verified media repository.
  - **Receipt evidence** confirming that the clip has been authorized for use.
- Until such evidence is provided, playback claims are marked as *pending*.

---

## Evidence Placeholders

| Component | Placeholder | Notes |
|-----------|-------------|-------|
| Event‑card generation script | `{{script_sha256}}` | Replace with actual SHA‑256 after implementation |
| SQL query execution log | `{{sql_log_id}}` | Capture runtime logs for audit |
| Playback rights receipt | `{{rights_receipt_id}}` | Obtain from licensing authority |

---

### Non‑Promoted Status

This candidate is **not** promoted to production. It serves as a draft for review by the Luna QA team and subsequent Terra director inspection.

---

*Prepared on 2026-09-04.*