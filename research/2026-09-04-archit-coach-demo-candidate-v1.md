# Coach Demo Candidate v1

## Event‑Card Creation
Demonstrated ability to generate event cards from raw play data. The system parses the JSON feed, extracts key events (goals, fouls, substitutions), and renders them in a structured card format.

## SQL Search
Implemented a lightweight SQLite interface that allows coaches to query historical match statistics by team, player, or date range. Sample queries are included in the documentation.

## Exact Video Playback
Showcases frame‑accurate playback of annotated clips using the provided video index. The demo links to a publicly licensed clip and demonstrates synchronized event markers.

---

### Evidence Gaps
- No live playback integration with proprietary footage (restricted by NDA).
- Full end‑to‑end test harness pending.

### Luna Review Checklist
1. Verify event‑card rendering against sample data.
2. Confirm SQL queries return expected results.
3. Ensure video playback aligns with markers in the public clip.
4. Document any remaining gaps for future work.