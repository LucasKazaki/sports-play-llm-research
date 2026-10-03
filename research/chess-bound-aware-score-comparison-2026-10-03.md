# C02 R13: bound-aware typed score comparison

Date: 2026-10-03. Cloud reference checked; native implementation not run.

Base chain: R11 typed score -> R12 matched root comparison -> R13 comparison semantics.

Current project source already preserves typed cp/mate and exact/lower/upper score qualification in `scripts/chess_score_bounds.py`. Existing research explicitly says comparative-superiority claims remain unsupported until a validated comparison layer exists.

R13 rule:
- compare only observations normalized to the same pre-move side-to-move POV;
- preserve engine Score order: received mate-zero < losing mates < finite cp < winning mates < delivered mate-zero;
- later forced loss is better; faster forced win is better;
- treat lower/upper as one-sided bounds in engine-score order, not confidence intervals;
- emit numeric candidate-minus-reference cp delta only for exact cp vs exact cp;
- apply the frozen 25 cp near-equivalence heuristic only to exact cp vs exact cp;
- any bound-qualified, mate, mixed-type, or exact-cp difference beyond 25 cp remains an adjudication input, not a final move-quality label;
- never convert mate to synthetic cp;
- bind comparisons to exact matched R12 root receipts and reject position/config/search mismatches.

Primary semantics checked 2026-10-03:
- UCI protocol: `lowerbound` and `upperbound` qualify engine score observations.
- python-chess Score defines a total order across Cp/Mate/MateGiven and warns that mate-zero direction can be lost if reduced to a scalar.

Cloud standard-library reference: 15/15 focused tests passed on Python 3.13.5 with `-S`; py_compile exit 0. Tests cover exact cp near-equivalence, both >25 cp directions, non-overlap and overlap bounds, mate/cp order without numeric delta, mate ordering, mate-zero direction, invalid booleans and POV mismatch.

Native next step after genuine C00 and R11/R12 adoption: extend the single authoritative comparison path, add fail-first tests before source edits, then return one exact-cp accepted comparison, one bound-overlap abstention and one mate/mixed-type adjudication with real Runtime receipts.

Typed stops: `SLM-C02-R13-C00`, `SLM-C02-R13-R11`, `SLM-C02-R13-R12`, `SLM-C02-R13-PATHS`, `SLM-C02-R13-RECEIPT-BINDING`.

No heldout scoring, model call, publication, main merge, board-game expansion or professional-commentary claim.