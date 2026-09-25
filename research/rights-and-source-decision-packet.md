# PlayGround Pilot — Rights and Source Decision Packet

**Prepared:** 2026-08-06  
**Decision owner:** Lucas, with Archit/lab confirmation  
**Scope:** authorization for a small 5–10 second soccer-clip pilot only. This packet does not authorize acquisition, license acceptance, publication, model training, or sharing.

## Superseding authorization record — 2026-08-27

Lucas explicitly instructed this project to use the SoccerNet access email supplied in the current Codex task to download a bounded part of the database for local training/development and testing. The attached SoccerNet email states that Lucas completed the NDA, grants access to the original videos, identifies the official SoccerNet API/package, limits use to non-commercial purposes, makes the recipient responsible for copyright, and prohibits sharing the data with collaborators who have not independently completed the access process.

Decision: **GO for this bounded local-only SoccerNet/SoccerDB-overlap pilot**, with the following controls:

- credentials are used only in memory and are never copied into code, manifests, receipts, logs, reports, slides, or source control;
- source media, derived clips, commentary, and the live demo remain under `data/private` and are not redistributed;
- inference is loopback-only; no footage or transcript is uploaded to a hosted model provider;
- only public-safe hashes, aggregate metrics, opaque clip IDs, and public SoccerDB mapping metadata leave the private data tree;
- the presentation is a private research presentation and carries a non-redistribution notice;
- this approval does not extend to arbitrary publicly viewable TV broadcasts or social-media uploads, which still require a specific compatible license or owner permission.

Credential-free acquisition receipts and the SoccerDB mapping binding are stored under `artifacts/soccernet-private-receipt/` and `artifacts/soccernet-pilot-v1/`. The private authorization screenshot itself remains user-provided task evidence; its secret is intentionally omitted from project files.

## Decision requested

Select exactly one source path for a **metadata-first, 50-clip maximum pilot**, or select **defer**. Before any clip is copied or downloaded, provide the source-specific evidence in the gate below and freeze an immutable manifest.

### Recommended path: A — lab-controlled clips

Use clips already lawfully held by Archit's lab only if the lab/data owner confirms the permitted uses in writing. This best matches the stated coach-recorded 10-second clip use case and reduces the domain mismatch of panoramic university datasets.

Required confirmation:

- source/owner and the person authorized to grant research use;
- whether the lab already possesses the files lawfully;
- permission for local research processing, derived annotations, model/API processing, paper evaluation, publication of aggregate results, and retention/deletion;
- whether any frames, screenshots, clip IDs, or derived trajectories may be released;
- whether faces, jersey numbers, audio, minors, teams, or partner-confidential material impose privacy/contract restrictions;
- whether third-party API upload is permitted, or local-only inference is required.

**Current status:** not authorized. Internal lab notes describe coach-recorded 10-second clips and a Huddle partnership, but they do not establish ownership or any of the permissions above.

### Conditional path: B — SoccerNet material already authorized to the lab

Use only if Archit identifies the exact SoccerNet task, release/version, files already obtained by the lab, and applicable terms. Do not create an account, accept terms, or download data under this packet.

Required confirmation:

- exact task/release and canonical URL;
- identity of the lab member who obtained access and date;
- license/terms text or durable local copy, including derivative-annotation and publication restrictions;
- whether Lucas is an authorized user under those terms;
- whether short clips may be extracted and whether data may be sent to hosted model APIs;
- a local inventory showing that the intended files are already present and authorized.

**Current status:** unresolved. The internal action items say to review SoccerNet Challenge data, but do not show which task is held or that Lucas is covered by its terms.

### Not recommended now: C — SoccerTrack v2

Primary sources report aligned per-frame pitch state and 12-class ball-action labels, which are technically relevant. However, the linked Hugging Face dataset API returned HTTP 401 without authentication on 2026-08-06; comprehensive boxes are not reported in the main release; and panoramic university footage has a domain gap from professional broadcast/coach clips.

**Current status:** metadata-only. Reconsider only after Lucas explicitly authorizes an access investigation and a non-gated rights path is verified. Do not accept a license or authenticate automatically.

### Reject by default: D — arbitrary web/broadcast/social clips

Do not use clips merely because they are publicly viewable. A public URL does not establish permission to download, extract, annotate, upload to model APIs, redistribute, or publish frames. Consider only a specifically identified source with explicit compatible licensing or owner permission.

### Safe fallback: E — synthetic-only continuation

Continue harness, schema, and scorer work with generated fixtures. This supports software verification but cannot support real-soccer performance, annotation reliability, coach utility, or model-comparison claims.

## Mandatory acquisition gate

All boxes must be satisfied before touching real video:

- [ ] Lucas selects A, B, or a specifically documented alternative in writing.
- [ ] Rights evidence is saved locally with URL/owner, effective date, access date, and exact permitted/prohibited uses.
- [ ] Archit/lab confirms privacy, partner-contract, and hosted-API constraints.
- [ ] The intended clip count is at most 50 and each clip is 5–10 seconds unless a revised pilot is explicitly approved.
- [ ] A metadata-only candidate manifest is reviewed before file acquisition.
- [ ] Acquisition method requires no new license acceptance, form submission, payment, or credential use by this loop.
- [ ] Storage location, access list, retention period, and deletion procedure are named.
- [ ] Two independent annotators and an adjudicator are named or the pilot is explicitly limited to interface testing.

If any item is unresolved, the result is **NO-GO for acquisition**.

## Immutable pilot manifest contract

Freeze the approved manifest before baseline runs. Use one row per clip with at least:

| Field | Purpose |
|---|---|
| `clip_id` | Non-semantic stable identifier |
| `source_id`, `match_id` | Source/match-grouped splitting and resampling |
| `source_owner`, `rights_record_id` | Traceability to authorization evidence |
| `source_uri` | Canonical origin; may be redacted in public artifacts |
| `start_time_s`, `end_time_s` | Exact extraction boundary |
| `sha256` | Immutable clip identity after authorized acquisition |
| `acquired_at`, `acquired_by` | Custody record |
| `privacy_flags` | Faces, minors, audio, jersey/identity, confidential partner data |
| `api_policy` | `local_only` or named permitted processors |
| `release_policy` | What may be shared: none, metadata, annotations, frames, or clip |
| `split_group` | Group key assigned before evaluation; never randomize clips across one match/source |
| `annotation_status` | pending, double-annotated, adjudicated, excluded |
| `exclusion_reason` | Auditable removal without silent cherry-picking |

After files are lawfully acquired, hash each clip and the canonical manifest. Any content, boundary, or rights change creates a new manifest version; do not overwrite the prior one.

## Minimal written approval template

> I authorize the PlayGround team to proceed with source path **[A/B/other]** for a pilot of at most **[N ≤ 50]** clips of **[duration]**. The rights record is **[path/URL/owner/date]**. Permitted processing is **[local only / named APIs]**. Permitted outputs are **[aggregate metrics / annotations / frames / clips]**. Storage is **[location]**, access is limited to **[people]**, and retention/deletion is **[rule]**. Source/match-grouped splits and two-annotator adjudication are **[required/waived for interface-only testing]**.

This approval authorizes only the stated pilot. It does not authorize publication, public release, expanded acquisition, fine-tuning, or paid services.

## Evidence basis and caveats

1. Internal project transcript, *Summer Research* email thread, Archit Ramanasai Kambhamettu and Lucas Tao, messages dated 2026-05-03 to 2026-05-31, captured 2026-08-06: `source/archit-lab-emails-transcript.md`. It requests tests on “a couple” of 5–10 second soccer clips but contains no rights grant.
2. Internal lab notes dated 2026-04-15: `source/Kambhamettu lab-2.md`. They describe coach-recorded 10-second clips, a Huddle partnership, and SoccerNet review as project context; they do not establish data ownership, license scope, privacy clearance, or API-upload permission.
3. Atom Scott et al., *SoccerTrack v2: A Full-Pitch Multi-View Soccer Dataset for Game State Reconstruction*, arXiv:2508.01802v1, submitted 2025-08-03, accessed 2026-08-06: https://arxiv.org/abs/2508.01802v1; official README pinned at commit `3ee38e481aab9de0f1d099c1cdde15302eb63f49`. Verified claim/access caveats are recorded in `experiments/2026-08-06-iteration-008-soccertrack-v2-verification.md`. (Evidence-ledger E-003 concerns SoccerNet-Caption and is not a SoccerTrack v2 source.)

Internal notes are project-context evidence, not legal advice or proof of rights. Final terms must come from the data owner/license and the lab's applicable institutional process.

## Current decision

**GO for the completed bounded local-only SoccerNet/SoccerDB-overlap pilot under the 2026-08-27 controls above. NO-GO for redistribution, hosted-model upload, public deployment, expansion to unlicensed broadcast footage, or sharing source media with collaborators who lack their own SoccerNet authorization.**
