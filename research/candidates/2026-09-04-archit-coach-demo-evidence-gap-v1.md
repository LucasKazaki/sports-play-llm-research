# Archit Coach Demo Evidence Gap Candidate (v1)

## Event‑Card, SQL Search, and Exact Video Playback Demo

This document outlines the evidence required to demonstrate the requested demo components for Archit. Each claim is linked to a verifiable receipt from the project workspace.

### 1. Event‑Card Creation
- **Claim**: An event‑card JSON contract exists that can be used to generate a playable video snippet.
- **Receipt**: `research/gemini-video-benchmark-protocol-2026-08-27.md` (contains the frozen schema and example event‑cards).
- **Status**: *Evidence present* – see ledger entry for “Gemini on 6 clips minimum”.

### 2. SQL Search Interface
- **Claim**: A SQLite/FTS database is available that supports structured queries over event‑card metadata.
- **Receipt**: `research/archit-coach-ready-next-steps-2026-09-03.md` (references the SQL schema and sample queries).
- **Status**: *Evidence present* – plumbing evidence exists as noted in the ledger.

### 3. Exact Video Playback
- **Claim**: A deterministic playback pipeline can render a video clip exactly from an event‑card without external inference.
- **Receipt**: `research/archit-coach-ready-next-steps-2026-09-03.md` (describes the playback artifacts and five‑minute demo sequence).
- **Status**: *Evidence present* – plumbing evidence exists; rehearsal remains to be performed.

## Unavailable / Human‑Gated Items
- **Live Demo Rehearsal**: Requires a rights‑safe clip set and a live environment. No receipt yet; will need human approval.
- **Coach Validation**: Feedback from UMD coaches on the demo is pending.

## Next Steps for Verification
1. Conduct a rehearsal of the event‑card → SQL search → playback pipeline using the existing artifacts.
2. Capture a server‑owned receipt (e.g., a log file or screenshot) of the successful run.
3. Submit the receipt to Luna QA and Terra inspection before promotion.

*This candidate is intentionally concise and evidence‑linked, awaiting the next verification step.*
