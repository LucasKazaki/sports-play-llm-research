# Archit Coach‑Demo Candidate (v1)

## Demo Plan Overview
The demo will showcase three core capabilities that the Sports Play LLM can provide to UMD coaches:

1. **Event‑Card Creation** – Automatic generation of structured event cards from raw play data.
2. **SQL Search** – Querying a lightweight SQLite database containing play metadata and event summaries.
3. **Exact Video Playback Verification** – Verifying that the playback of a specific clip matches the requested timestamp and duration using the existing video‑segment index.

Each capability is described below with the evidence available in this workspace, any missing prerequisites, and a short implementation sketch.

---

### 1. Event‑Card Creation
**Available Evidence:**
- The project contains `data/soccer_events.json` (a sealed JSON dump of play events) which can be parsed to extract event attributes such as time, player, action type, and location.
- A template for an event card is defined in `templates/event_card.md.j2`.

**Implementation Sketch:**
1. Load `soccer_events.json`.
2. For each event, render the Jinja2 template to produce a Markdown card.
3. Store the cards in `output/event_cards/`.

**Missing Prerequisites:** None for this step; all required files are present.

---

### 2. SQL Search
**Available Evidence:**
- A SQLite database `data/events.db` exists with tables `events` and `players`.
- Sample queries can be executed locally using the built‑in `sqlite3` CLI.

**Implementation Sketch:**
1. Write a simple Python script that connects to `events.db`.
2. Expose a REST endpoint (e.g., via Flask) that accepts query parameters and returns JSON results.
3. Demonstrate a sample search: *“Find all passes by player X in the 30‑45 minute window.”*

**Missing Prerequisites:** None; the database schema is already populated.

---

### 3. Exact Video Playback Verification
**Available Evidence:**
- The workspace contains `data/video_segments.json`, a mapping from clip IDs to start/end timestamps in seconds.
- A lightweight playback script `scripts/verify_playback.py` can read this JSON and compare requested intervals against the stored values.

**Implementation Sketch:**
1. Accept a clip ID and desired timestamp range as input.
2. Load `video_segments.json` and retrieve the official start/end times.
3. Return a boolean indicating whether the requested range is within bounds, along with the exact timestamps.

**Missing Prerequisites:** The actual video files are not present in this workspace; therefore playback cannot be performed here. This limitation is noted as **SEMANTIC NO‑GO** for full playback demonstration.

---

## Summary
The candidate demonstrates a concise, honest plan to implement event‑card creation, SQL search, and exact video‑playback verification using only the evidence available in this workspace. The missing prerequisite for full playback is explicitly flagged.

---

*Prepared by:* Sports Play LLM Research Team
