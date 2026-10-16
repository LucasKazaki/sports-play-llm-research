# Limited draft checks v1: source-review handoff

The seven approved files are frozen at the hashes in manifest.json. Actual
validation: 100 CPU/UI checks passed, with one real-engine check intentionally
deselected. Fixtures are authored software data, not chess-quality measurements.
The suite runs the actual full frontend module with DOM/API fixtures, checking
stale selected moves, return, evidence export eligibility and disclosure caching.

The pure API is draft_checks_v1.audit_bytes(response_bytes, input_bytes,
original_input_sha256, packet, context, undecorated_base_result, qualified=bool).
It writes no file and calls no model or engine. The controller retains the
original request hash after writing its unchanged input and computes a sibling
verification record only after the worker closes. It never edits raw files,
raw_text, decoded_text or parsed fields. The optional metadata record is
create-only. Binding/retention failures leave the raw response available.

Only a completed EOS response from the original qualified manual profile can
receive checks in production. Interface fixtures, cancelled/partial/failed
results, unqualified profiles and the unavailable trained profile do not.
The separate rendering fixture proposed for root browser QA deliberately uses
authored records and must retain a persistent no-model/fixture banner.

Board observations concern the legal structured BEST_MOVE. Selected identity
compares that reported move with the supplied move. Canonical ANALYSIS facts
use their own explicitly named legal move, never BEST_MOVE as a replacement.
The matcher requires ANALYSIS first, no substantive external prefix, one legal
BEST_MOVE and the entire two-sentence check/capture grammar. Unknown framing,
conditional text, duplicate/invalid fields and other prose abstain. Zero matched
statements is expected with ordinary original-model prose. No broad factuality
badge or quality percentage is shown. Check is true even on checkmate; mate is
the stronger specific predicate. Every span indexes exact response.raw_text in
Unicode code points, not file bytes or translated display text.

For a later root-only compatibility check on already-spent real authored/UI
receipts, first require the original output byte hash from its closed ledger
and the original saved input byte hash from its frozen packet binding. Do not
invent an expected input hash from a newly serialized response.input. Verify
the original QueenRunner source/settings/provenance and closed worker metadata
without launching its command. Its decorate_result may be used as a separate
in-memory view to check original_profile; pass the untouched raw dictionary as
the base result. Derive context only from the actual saved request/current FEN
and selected move. Missing original bindings mean unassessed, not reconstructed
substitute input. Save any checker result in a new derived receipt; leave all
original files unchanged. This establishes schema/processing compatibility,
not learned accuracy, prose quality, checkpoint admission or a fresh comparison.

All generator adapters, workers, trainers, scorers, protocols, inputs, references,
launcher, server and model eligibility files remain unchanged. See the boundary
verification for exact retained source pins. The running tutor was not restarted
or called in this lane. Root retains runtime, browser QA, Git and documentation
ownership. No actual Queen smoke is needed unless root finds material wiring
uncertainty after CPU checks and saved-response compatibility.
