# SoccerMaster evidence-gated VLM diagnostic v1

**Status:** pre-registered, zero model calls; private held-out data binding pending

## Why this next experiment exists

The sealed complete-match SoccerMaster run proved the infrastructure could
process a complete 90-minute game, but it did not prove soccer understanding.
It produced 361 VLM-authored events across 96 windows; the restricted post-seal
time/type check corroborated only 3/166 mapped annotations and 3/54 mapped
predictions, and a six-window visual audit found 0 fully supported reports.
The observed failure modes were frame-as-event output, unsupported goal-like
claims, invented continuity, and weak temporal evidence. This protocol targets
those failures directly without changing or reinterpreting any frozen result.

## Pre-registered task

The future test is a private 40-window, labeled diagnostic drawn from at least
two **new** game-held-out groups: four `goal`, eight `offside`, eight `foul`, eight
`corner_kick`, and twelve background windows. Each window is 30 seconds and
its evaluator-selected action time is deterministically jittered by up to six
seconds. Thus the VLM sees a short anonymous sequence but is not told which
event is expected or that it should occur at the center.

SoccerNet-v2 labels are used only to construct the private test lock and to
evaluate after predictions are sealed. The visual request contains only 13
ordered silent, scoreboard-redacted frames with anonymous IDs and relative
offsets. It excludes audio, commentary, labels, file/source identity, teams,
scores, and absolute match time. Raw SoccerNet data stays private and is not
redistributable.

Before a future call, a private full-frame overlay audit must pass. This is
stronger than the earlier fixed top-strip policy, which left a readable
lower-third in a sampled frame. The redaction check is a privacy/provenance
gate; it does not classify soccer events.

The current local pool cannot satisfy this fresh-evaluation condition because
its groups have already served train, validation, legacy test, or the frozen
complete-match VLM lane. Before a model call, the private binding must include
new-source acquisition receipts and prove zero held-out-media overlap against a
hash lock covering every historic VLM input. Until then this is deliberately a
zero-call, data-binding-pending protocol.

The source-role conclusion is independently auditable from the metadata-only
current-pool manifest at
`artifacts/soccer-data-expansion-audit-2026-08-30/local-asr-overlay-manifest.json`
(SHA-256 `24d4cac323a439835a8dcea2e0813302c6610666c400b2be25fb1d8ed9af348d`;
91/91 audit checks). It contains opaque group/half identifiers and hashes only,
not raw media, source names, or transcripts.

## VLM-only event semantics

For every window, a local VLM will make three separately persisted calls:

1. **Proposal A**: exactly one event claim or abstention, with distinct
   pre/anchor/post frames.
2. **Proposal B**: the same atomic task, without Proposal A, labels, or any
   external metadata.
3. **Evidence audit**: receives Proposal A and the frames, but not Proposal B
   or labels; it answers supported, insufficient, or contradicted and cites a
   visual chain.

The same local model in differently prompted calls is procedural redundancy,
not statistical model independence. Every event interpretation, including the
goal-specific visual-evidence category, comes from a VLM response. Deterministic
code only validates IDs/ordering, requires agreement, gates admission, records
an abstention reason, hashes artifacts, retrieves accepted text, and performs
post-seal matching. It does not inspect pixels or infer / repair an event.

For a `goal`, the VLM evidence audit must state direct visual evidence of either
`ball_crosses_goal_line` or `ball_visibly_in_goal`. A celebration, replay,
score graphic, or later restart alone must fail the gate. If any gate fails,
the index stores abstention rather than a deterministic substitute.

## Outcomes and claim boundary

Primary results will report raw versus accepted claim counts, raw versus
accepted goal claims, gate-reason and abstention rates, VLM-anchor error versus
the private label time, and restricted coarse type/time corroboration. The
protocol will also report atomic output multiplicity: every window is allowed
one candidate, so a result cannot hide frame-per-event behavior under a long
multi-event paragraph.

These are diagnostic measures. Coarse SoccerNet labels do not validate actors,
outcomes, detailed prose, tactics, or coach usefulness. No accuracy,
generalization, coaching, or improvement claim is permitted until a new
held-out run is frozen, evaluated, and independently blinded human visual
adjudication supports the relevant claim.

## Safe preflight and authorization boundary

The executable package is [prototype/soccermaster_evidence_gated](../prototype/soccermaster_evidence_gated/README.md).
It intentionally contains no HTTP/model transport and therefore cannot run
inference. Its dry run uses synthetic anonymous hashes only; preflight verifies
the strict private binding contract without reading media or labels. A later
executor needs an explicit root authorization receipt binding the frozen
protocol hash, private data-lock hash, and local model-identity hash. No
inference has been authorized or performed under this protocol.

## Reproducibility anchors

- Canonical protocol SHA-256: `d0bf9809cb87491a088dc6abc85eef104c4950f773a2367d1de5239978fbc720`
- Public preregistration file SHA-256: `c26c68454509d9843af7c238265526911a9bdbcfdd3dfafa5ce3d81fd70df79e`
- Public private-binding-schema SHA-256: `e0ab1380d551af4ee2687f7a4a0db2953d59e6e9ddbbf18ccaa93710c9abeaf2`
- Focused validator tests: 11/11 passed; latest full repository suite: 313/313 passed.
