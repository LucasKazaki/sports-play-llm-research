# Versioned Sealed‑JSON Local Reasoning Viability Candidate

## Purpose
This document defines a **fail‑closed, non‑executing protocol** for reasoning over sealed VLM/SoccerMaster‑derived JSON. It distinguishes design from evidence, prohibits private‑footage upload and benchmark execution absent rights/spend receipts, and lists exact missing receipts.

## Protocol Overview
1. **Input Specification** – The only accepted input is a *sealed* JSON file produced by the SoccerMaster pipeline (e.g., `soccer_master_output.json`).  The JSON must be signed or otherwise cryptographically verified to ensure integrity.
2. **Local Reasoning Engine** – A lightweight GPT‑style model runs locally on the provided JSON, generating natural‑language explanations and high‑level summaries *without* executing any video benchmarks.
3. **Fail‑Closed Behavior** – If the input is malformed, missing required fields, or if any step fails, the system aborts immediately and returns an error message without performing further computation.
4. **Evidence Separation** – All generated text is tagged as *design* (the protocol description) versus *evidence* (any logged outputs). No evidence of private‑footage processing is produced.
5. **Rights & Receipts** – The protocol explicitly requires a `rights_receipt.json` and a `spend_receipt.txt`.  If either is missing, the process halts and lists the missing receipts in the output.

## Missing Receipts Checklist
- `rights_receipt.json` – Proof of permission to use SoccerMaster data.
- `spend_receipt.txt` – Documentation that no paid API calls were made during this run.

If any receipt is absent, the system will report:
```
ERROR: Missing required receipts: [list]
``` 
and terminate.

## Usage Notes
- This document is *not* executable code; it serves as a specification for future implementation.
- No private footage or benchmark execution occurs under this protocol.
- All outputs are purely textual and can be stored locally without external dependencies.

---
**End of Document**
