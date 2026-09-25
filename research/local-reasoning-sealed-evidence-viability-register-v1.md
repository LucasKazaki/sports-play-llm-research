# Versioned Sealed-Evidence Local Reasoning Viability Register

## Overview
This document inventories all server‑readable sealed VLM/SoccerMaster‑derived JSON evidence currently available in the admitted workspace. It distinguishes observed evidence from inferred data, records missing provenance/rights/configuration/receipt fields, and states fail‑closed admission criteria for local VLM and GPT reasoning.

## Sealed Evidence Inventory
| File | Observed / Inferred | Provenance | Rights | Configuration | Receipt |
|------|---------------------|------------|--------|---------------|---------|
| `data/soccer_master_2023.json` | Observed | *Missing* | *Missing* | *Missing* | *Missing* |
| `data/vlm_output_01.json` | Observed | *Missing* | *Missing* | *Missing* | *Missing* |

*(Add additional rows as evidence becomes available.)*

## Missing Fields Summary
- **Provenance**: Source of the data (e.g., SoccerMaster API, internal scrape). 
- **Rights**: Licensing or usage restrictions. 
- **Configuration**: Parameters used to generate the JSON (model version, prompt, etc.). 
- **Receipt**: Server‑generated receipt confirming integrity and authenticity.

## Fail‑Closed Admission Criteria
1. **No inferred evidence** is allowed; only directly observed sealed JSON files may be considered. 
2. All fields listed above must be present for an evidence file to be admitted for local VLM or GPT reasoning. 
3. If any field is missing, the evidence is marked as *unadmitted* and cannot be used until the missing information is supplied.

## System Status
- **SYSTEMS GO**: Unchanged. 
- **SEMANTIC NO‑GO**: Unchanged. 

## Next Steps
This register will be updated incrementally as new sealed evidence files are added to the workspace. Once all required fields are populated, a Luna QA review will be requested.
