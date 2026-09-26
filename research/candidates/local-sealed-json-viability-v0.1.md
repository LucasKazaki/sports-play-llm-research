# Local Sealed JSON Viability Candidate v0.1

This document defines the **sealed event‑card JSON contract** for local VLM/GPT reasoning admission.

## Contract Overview

An *event card* is a self‑contained JSON object that describes a single sports event.  The card must be **synthetic only** – no real footage or proprietary data may appear.

### Required Fields
| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the card (UUID v4). |
| `sport` | string | Name of the sport (e.g., "soccer"). |
| `description` | string | Human‑readable description of the event. |
| `provenance` | object | Metadata about data origin.
| `rights` | string | License or rights statement (must be open or synthetic). |
| `abstention` | boolean | Indicates if the card is a placeholder for missing video. |

### Optional Fields
| Field | Type | Description |
|-------|------|-------------|
| `videoBinding` | object | If present, contains `{"url": string}` pointing to an external video (must be publicly available). |

## Fail‑Closed Handling
If a card references a missing or inaccessible `videoBinding`, the verifier must flag the card as **invalid** and provide an error message.

---

For more details, see the accompanying JSON fixture and verifier script.
