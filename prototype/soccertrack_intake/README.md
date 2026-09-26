# SoccerTrack v2 public-media intake boundary

This package turns a locally acquired, openly licensed SoccerTrack v2 subset
into a small set of deterministic integrity artifacts. It is deliberately not
a visual model, event detector, trainer, or search index.

## What it verifies

- The only accepted source root is `data/open/soccertrack-v2`; private
  SoccerNet material and symlink escapes are rejected.
- `source-provenance.json` must declare the SoccerTrack v2 dataset, CC BY 4.0,
  canonical HTTPS source/license links, and an acquisition revision/status.
- Each `media/<match_id>/<match_id>_*.mp4` asset is SHA-256 hashed and matched
  by opaque `match_id` to at least one `annotations/bas/*.json` container.
- The official SoccerTrack v2 game split is pinned rather than rebalanced
  locally: train `117092, 117093, 118575, 118576, 118577, 128058, 132877`;
  validation `118578`; test `128057, 132831`. Action values never influence
  the assignment. Missing either official test game is explicitly blocked.

## What it refuses to do

The source manifest may record BAS *container hashes* and action counts for
post-hoc integrity work, but it never copies raw actions, labels, player IDs,
teams, positions, or timestamps. The separate anonymous visual manifest and
retrieval catalog reject those fields. The retrieval catalog is disabled until
a separate approved executor contributes sealed VLM-authored reports. This
package has no model transport, pixel decoder, event heuristic, or network
client.

Any future frame-request helper also requires an opaque
`frame-<sha256>` identifier rather than arbitrary caller text, so a media
path, match ID, or annotation wording cannot be smuggled into a
model-request-shaped object through a nominal frame ID.

## Required local provenance record

The acquisition lane owns `data/open/soccertrack-v2/source-provenance.json`.
It must include at least:

```json
{
  "schema_version": "soccertrack-v2-source-provenance-v1",
  "dataset_id": "SoccerTrack-v2",
  "data_license": "CC-BY-4.0",
  "source_url": "https://…",
  "license_url": "https://…",
  "source_revision": "documented-source-revision"
}
```

## Commands

From the repository root, after the public acquisition is complete:

```powershell
.venv-soccernet\Scripts\python -m prototype.soccertrack_intake build
.venv-soccernet\Scripts\python -m prototype.soccertrack_intake verify
```

The artifacts are written under `artifacts/soccertrack-v2-intake/`. A `pass`
means byte/provenance/data-separation checks passed. It does **not** mean that
a VLM was called, a play was detected, annotations were usable as retrieval
labels, or coaching claims are justified.
