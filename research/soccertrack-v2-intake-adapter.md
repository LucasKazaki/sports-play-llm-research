# SoccerTrack v2 public-data intake adapter (2026-08-31)

## Purpose

The project now has a deterministic intake boundary for a separately licensed
public SoccerTrack v2 subset. It is intentionally isolated from the private
SoccerNet corpus: accepted paths are only `data/open/soccertrack-v2`, output
artifacts live under `artifacts/soccertrack-v2-intake`, and all source files
must be regular files within that root.

## Evidence and separation contract

The adapter checks a local acquisition-owned provenance record, video byte
hashes, BAS-container byte hashes, and opaque match-ID linkage. It records
container count and hash but never exports BAS action rows or values. This
means label text, player IDs, teams, positions, and action timestamps cannot
flow into either of the two downstream artifacts:

- `anonymous-visual-manifest.json` contains only non-reversible asset tokens
  and a future frame-input contract.
- `label-free-retrieval-catalog.json` is deliberately non-semantic and
  disabled. Only a later, separately authorized, sealed VLM report could add
  semantic retrieval entries; BAS annotations and deterministic event logic
  are prohibited.

The model-request-shaped helper accepts only opaque `frame-<sha256>` IDs and
relative-time fields. It has no image decoder or model transport. The BAS source is
therefore post-hoc provenance/evaluation material, not a source of candidate
events, prompt content, or query answers.

## Split logic

Assignments are at the opaque source-game level and preserve the released,
pinned SoccerTrack v2 partition: train `117092, 117093, 118575, 118576,
118577, 128058, 132877`; validation `118578`; test `128057, 132831`. The
adapter never rebalances by a local hash or annotation values. The local public
intake now has development game `117092` and one official test game, `128057`.
It labels the latter `official_test_heldout`, keeps it sealed and unscored, and
still writes `blocked_missing_official_test_games` because `132831` is absent.
It therefore does not manufacture a held-out result. The split configuration
hash is explicitly bound to the local provenance hash. Even an official split
marked ready still needs the evidence-gated protocol's fresh-media/history-
overlap, redaction, private binding, and explicit authorization gates.

## How to interpret a receipt

`validation-receipt.json` gives byte-level integrity counts and the number of
development/held-out game groups. The current receipt has one development and
one held-out group, but still reports incomplete official test coverage and is
not evidence-gated eligible. A passing receipt is only a data-readiness fact.
It is not an experiment result, a model-quality estimate, an event detection
result, a valid search system, or evidence for coach utility.
