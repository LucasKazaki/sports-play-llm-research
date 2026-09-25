# Archit Coach‑Demo Status Candidate (v1)

## Overview
This document records the current status of the **Archit coach‑demo** effort. It is a *candidate* version, not yet promoted to a final deliverable.

### Receipt‑Supported Capabilities
- **Event‑Card Generation** – Demonstrated ability to produce event cards from the sealed SoccerMaster JSON dataset (see evidence in `research/evidence/event-card-demo.md`).
- **SQL Search Prototype** – A working SQL query interface that retrieves relevant clips based on coach‑specified criteria (evidence: `research/evidence/sql-search-demo.sql`).
- **Exact Video Playback Demo** – Proof of concept for playing back a specific frame from a clip using the local VLM pipeline (see `research/evidence/video-playback-demo.md`).

### Missing Evidence / Pending Work
- Full end‑to‑end demo video showing all three components together.
- User testing feedback from UMD coaches.
- Performance metrics for the SQL search against the full dataset.

### Rights/Adjudication & P0 Gates
- All media used is permissioned or openly licensed; no restricted datasets are included.
- The P0 gate (Gemini video benchmark) remains **frozen** until third‑party processing rights and zero‑spend evidence are secured.

## Next Steps for Demo Evidence
1. **Event‑Card** – Capture a short clip demonstrating the card generation pipeline, annotate with coach notes.
2. **SQL Search** – Record a screen capture of the search UI querying for a specific play type.
3. **Exact Video Playback** – Log a playback session showing frame‑accurate retrieval from a clip.

These artifacts will be stored in `research/evidence/` and referenced here upon completion.