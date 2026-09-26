# SoccerMaster evidence-gated VLM diagnostic protocol

`soccermaster_evidence_gated` is a separate, pre-registered next experiment
for the semantic failures found in the complete-match SoccerMaster run. It is
not a replacement for that frozen experiment and does not yet contain model
outputs.

## What changes

Each 30-second diagnostic window admits at most one VLM-authored event claim.
The future local-only run will use three calls on the same ordered silent,
scoreboard-redacted frames. A private full-frame overlay audit must pass first;
the prior experiment's fixed top strip did not reliably remove lower-thirds:

1. Proposal A returns one claim or abstention with distinct pre/anchor/post
   frames.
2. Proposal B independently performs the same task without seeing Proposal A.
3. An evidence auditor sees Proposal A's claim and the frames, but not labels
   or Proposal B, and returns `supported`, `insufficient`, or `contradicted`.

The deterministic gate does not recognize soccer events. It only validates
VLM-authored schemas/evidence IDs and admits Proposal A verbatim when the VLM
calls agree, the evidence is chronological and spans at least two seconds, and
the audit supports it. A `goal` additionally needs a VLM-authored direct visual
evidence category (`ball_crosses_goal_line` or `ball_visibly_in_goal`). A
failed gate becomes abstention; code never invents a replacement event.

The test contract is a 40-window private, labeled, game-held-out diagnostic:
four goals, eight offsides, eight fouls, eight corners, and twelve background
windows across at least two **new** held-out game groups. Their media hashes
must have zero overlap with every historic VLM input before a run can be
authorized. Windows are event-jittered so the model is not told that an action
occurs at the center. Labels select and
evaluate the subset but never enter a model request.

## Safe commands

From the repository root:

```powershell
.venv-soccernet\Scripts\python -m prototype.soccermaster_evidence_gated write-preregistration
.venv-soccernet\Scripts\python -m prototype.soccermaster_evidence_gated write-private-binding-schema
.venv-soccernet\Scripts\python -m prototype.soccermaster_evidence_gated dry-run
.venv-soccernet\Scripts\python -m prototype.soccermaster_evidence_gated preflight
```

`dry-run` uses anonymous synthetic hashes only. `preflight` without a private
binding validates the public contract but intentionally reports
`heldout_binding_ready: false`; it never reads video, labels, or a model.

A future executor must bind an actual private label lock, an anonymous visual
window manifest, media hashes, disjoint game-group hashes, a local model
identity, and an explicit post-review root authorization receipt. The exact
private-lock fields are in the public
`artifacts/soccermaster-evidence-gated-v1/private-binding.schema.json` schema.
This package has no network or model-execution path, so it cannot accidentally
make a VLM call.

## Limits

Separate role-conditioned calls using the same local model are not statistically
independent. SoccerNet-v2 labels provide coarse time/type evaluation, not
actor/outcome/tactics ground truth. Any coach-utility or detailed-report claim
still requires blinded human visual adjudication on the new held-out windows.
