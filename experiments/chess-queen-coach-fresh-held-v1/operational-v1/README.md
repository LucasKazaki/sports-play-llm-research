This is a prospective, one-attempt CPU operation over existing tables. It does
not acquire data, search with Stockfish, train or call a model. The actual latest
inventory, protocol and root dispatch are still required. Authored tests use
synthetic receipts and a deliberately fake selector for operation wiring; they
cannot prove that a real cohort is fresh.

`build_protocol.py --spec ABSOLUTE_SPEC --out NEW_PROTOCOL` reads only the small
root metadata spec and pinned source files. Its spec has exactly `data`,
`inventory_summary`, `corpus_attestations` and `admit_by_utc`. The eight data
roles are dataset, teachers, initial, reserved, corpus_manifest,
operational_provenance, inventory and latest_seal. Every file binding is
`{root: repo|task, path: relative_path, sha256: exact_byte_hash}`. Traversal,
symlinks and other roots fail closed. A draft or missing latest seal is not an
executable protocol. Source identities and Python/chess/filelock versions are
recorded without importing a framework.

The sealed inventory has schema `chess.fresh-held-exposure-inventory.v1`, status
`sealed`, and scopes in the protocol's exact order. Each scope carries scope_id,
slots, receipt attestations and, where applicable, no_learning=true with a typed
zero model-call receipt. Required scopes cover old cold attempts 1–4, first
failed daytime cold, direct cold, TRAIN development, failed HELD, manual9431,
repaired cold, preview192 qualification, optional preview UI, observer CPU3 and
warm scope. These names do not assert that any pending call ran or succeeded.
Root must close every scope and append intervening calls before sealing.

An attestation is `{kind, evidence, equals}`. Evidence has an exact binding,
format json|jsonl, locator list and line (null for JSON). The typed value must
match the closed receipt literally. Each exposure slot has a unique slot_id,
disposition, attestations, context and raw (binding or null). Context is an
original corpus_case with exact case_id/group_id, or anonymous_authored with
input_evidence. Current packets permit FEN and an optional original selected
move; history must be empty. Nonempty unexpected history stops the operation.

Dispositions distinguish retained_raw, unknown_no_raw, closed_raw_absent,
root_only_forward and explicitly proven not_run. Raw absence never establishes
zero forward calls. Known roots/groups remain excluded when output is unknown;
unretained successor paths stay an explicit limitation. Retained raw input and
bytes must match their bound receipts. Only the pinned native parser's legal
critical prefix and independent legal root BEST/given successors add keys.
The parser is not an ordinary-prose verifier.

Manual prose projections are separately bound in the root seal. The driver
verifies original raw bytes and Unicode spans, then independently replays the
included native atoms/UCI from response.input. It verifies every retained FEN
and key. No board after an illegal prefix is invented. These are exclusion
roles from AI-authored, independently agent-reviewed mappings, not human gold
labels, automatic language understanding or an explanation-quality metric.

The latest seal has schema `chess.latest-exposure-root-seal.v1`, status
`closed_for_selection`, inventory_sha256, exact scope_ids,
all_dispatches_closed_or_explicit_unrun=true, no_overlapped_gpu=true and
approved_manual_projections. Its exact hash is in the root-reviewed protocol.
It is a root operational assertion, not OS authentication. A later model phase
must re-attest that no intervening calls changed exposure.

Root alone may later dispatch run_once.py with an exact protocol/hash and new
output directory. It holds the existing chess-gpu-owner.lock through closure,
uses memory-only CPU guards (startup 8/4 GiB commit/physical; running 6/4), checks
a cooperative 90-second deadline and the fixed 22:00 UTC authority cutoff, and
creates no child processes. Checks occur at bounded reads and record/phase
boundaries; blocking filesystem calls and failure finalization are not a hard
preemptive 90-second timeout. Root must serialize heavy CPU/GPU work.

Full planned outcomes retain 512 reserve slots, 16 selected slots, 48 input/ref
pairs and every declared exposure slot. Durable intent/outcome prefixes recover
known work after ordinary failures. A fully unwritable disk can still prevent
the final receipt; no software receipt proves unwritable writes succeeded.
No retry, replacement, source edit, quota shrink or change to old reservations
is implemented. All original 16 games stay spent and all 512 reserves stay
excluded from training. Unknown foreign ownership remains foreign.

Success produces separate private heldout-inputs.jsonl and
heldout-references.jsonl, a private reservation and manifest.json with status
ready, selected_games=16, input_count=48, input_rows and grader_references
path/hash bindings. Inputs contain no response, score, PV or future facts.
Presence of a ready manifest alone is insufficient: the complete successful
closed ledger and an independent audit binding manifest_sha256 are required
before a separate model protocol can be admitted. No actual data/model claim
or UI admission follows from these source files or authored tests.
