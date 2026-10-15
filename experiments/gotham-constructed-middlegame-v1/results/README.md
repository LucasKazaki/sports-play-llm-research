# Audited illustration outcome

The single frozen attempt completed all six planned raw outcomes in 29.797 seconds, including setup and preflight. A separate CPU evaluator ran after the raw seal. Independent retained-file review replayed native tokenization, both classifier rankings, generated text, legality and immediate rule facts without new model or engine calls.

| Move-policy condition | Raw move | Legal | Matches displayed Rh3 |
| --- | --- | --- | --- |
| Base 9M classifier | c3d3 | Yes | No |
| Selected 9M classifier, step 512 | d1d8 | Yes | No |
| Base 124M move language policy | c3d3 | Yes | No |
| Selected 124M move policy, step 2048 | c3d3 | Yes | No |

Different legal moves are not evidence of incorrect play. The displayed move is an observation, not an engine-derived best-move label. Raw classifier choices remain separate from legal-mask diagnostics; neither raw choice needs masking here. Both 124M generations reach their 16-token cap, and the frozen first-M policy evaluates only their first token.

The other two outcomes answer a different question: eight immediate facts for **given Rh3**. The base fact response does not satisfy the exact eight-field schema. The selected fact adapter returns that schema and gets all eight fields right. Rh3 here is a noncapture, noncheck, nonpromotion rook move. This single easy case does not repair the primary fact experiment's missed checks (0/13 positives correct) or its missed rook promotion (0/1).

The board uses constructed computational counters of 0/1. Original game identity, complete history and mainline remain unresolved; upstream pretraining overlap is unknown. There are zero accepted holdout positions. Move choice and given-move facts have separate inputs and results, with no pooled accuracy, ideas, strength or commentary claim.

[Summary](summary.json), [report](../../../reports/gotham-constructed-middlegame-v1-2026-10-15.md), [independent review](../evidence/reviews/independent-retained-review.json), [original raw seal](../evidence/raw-seal.json), and [original-to-public mapping](../evidence/publication-map.json) provide the evidence. All 37 sealed files are copied without byte changes. Python snapshots gain only an inert `.txt` suffix; the original seal is never rewritten. No private video, frame, transcript, full source ledger or weights are published.

The parent experiment README and all other files from commit `55fc2901142cd84c8a59785b7f0526f529eb074a` remain the immutable pre-call freeze. This results directory records the later outcome. Actual execution used the reviewed workspace entrypoint; published snapshots were not relocated and executed after the fact. The retained tokenizer BPE cleanup warning is not an execution error. Codex-assisted engineering remains explicitly attributed.
