# Archit Coach‑Demo Candidate v1 (2026‑09‑04)

## Demo Script Overview
1. **Event‑Card Creation** – Show how to generate an event card from a JSON snippet using the VLM interface.
2. **SQL Search** – Demonstrate querying the event database for specific play types and retrieving matching clips.
3. **Exact Video Playback** – Play back a clip at frame‑accurate timestamps, highlighting the requested segment.

## Evidence‑Link Schema
| Step | Action | Required Receipt | Notes |
|------|--------|------------------|-------|
| 1 | Create event card from JSON | `create_event_card_receipt.md` | Must include SHA256 of input JSON and output card ID |
| 2 | Execute SQL query | `sql_query_receipt.md` | Include query string, result row count, and a checksum of the returned rows |
| 3 | Play video segment | `video_playback_receipt.md` | Provide clip identifier, start/end timestamps, and frame‑level checksum |

All receipts are stored in the `receipts/` directory and referenced by relative paths.

## Constraints & NO‑GO
- No private footage or credentials are used.
- All media is publicly licensed or synthetic.
- Performance claims are omitted; only functional evidence is provided.

---
**Prepared for:** UMD Coaches
**Prepared by:** Archit Team
