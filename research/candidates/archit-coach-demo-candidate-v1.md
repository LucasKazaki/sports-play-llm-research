# Archit Coach‑Demo Candidate v1

## Demo States (receipt‑supported)

- **Event‑card creation** – Demonstrated using the current event‑card UI. The action was captured via a screenshot stored in `assets/event-card-demo.png` and a JSON log of the API call (`logs/event-card-create.json`).
- **SQL search** – Executed against the local SQLite database containing match metadata. Query results were exported to `data/sql-search-results.csv` and logged in `logs/sql-search.log`.
- **Exact video playback** – Played a 30‑second clip from the licensed dataset using the built‑in player. Playback was recorded with a timestamped log (`logs/video-playback.log`) and a frame capture (`assets/video-frame.png`).

## Missing Evidence / Hard Gates

1. **Clip licensing confirmation** – No formal license verification for the 30‑second clip; requires NDA clearance.
2. **Performance metrics** – No latency or throughput measurements collected.
3. **User interaction data** – No analytics on coach usage of the demo features.
4. **Full dataset access** – Only a subset of clips is available; full benchmark cannot be run yet.

## Luna‑Review Handoff

- Submit this candidate to the Luna QA team for review of evidence links and compliance with the *Use permissioned or openly licensed media* gate.
- Await approval before promotion to the next stage.
