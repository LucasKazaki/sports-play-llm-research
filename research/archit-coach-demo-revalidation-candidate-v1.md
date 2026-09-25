# Archit Coach‑Demo Revalidation Candidate (v1)

This document reconciles the current status of the Archit/coach outcomes required for a coach‑ready demo. It is **not** a promotion candidate; it merely records what has been achieved, what remains missing or stale, and the provenance of each outcome.

## 1. Event‑Card Creation
- **Status:** *Implemented* – event cards can be generated from the JSON metadata extracted by SoccerMaster.  
- **Gap:** None.

## 2. SQL Search
- **Status:** *Partial* – basic keyword search over event titles is functional, but advanced filtering (date range, player, team) is not yet available.  
- **Gap:** Missing SQL schema for full‑text indexing and query templates.

## 3. Exact Video Playback
- **Status:** *Implemented* – the playback component can stream a clip given its exact timestamp bounds.  
- **Gap:** No automated verification that the clip matches the event metadata; manual check required.

## 4. Clip Categories & Retrieval Provenance
- **Status:** *Stale* – categories exist but are not linked to provenance records in the database.  
- **Gap:** Need to attach a provenance URI for each category assignment.

## 5. Concise Update Readiness
- **Status:** *Pending* – a concise update (bullet‑point summary) can be generated, but it is not yet integrated into the coach dashboard UI.  
- **Gap:** UI integration and user testing pending.

---

### Evidence & Gap Summary
| Outcome | Status | Gap | Next Steps |
|---------|--------|-----|------------|
| Event‑Card Creation | Implemented | None | N/A |
| SQL Search | Partial | Full schema & templates | Draft schema |
| Exact Video Playback | Implemented | Provenance check | Add automated test |
| Clip Categories | Stale | Provenance linkage | Update DB schema |
| Concise Update | Pending | UI integration | Design mockup |

---

This file is versioned as `v1` and does **not** modify the human‑gated gap register (`archit-coach-demo-evidence-gap-register-v1.md`).  Further iterations will be created as new evidence becomes available.
