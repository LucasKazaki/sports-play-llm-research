# C02 R20 provenance-safe evidence evolution

Date: 2026-10-03. Packet: `SLM-C02-R20-PROVENANCE-SAFE-EVIDENCE-EVOLUTION-v1`.

Fresh source inspection found a dependency that must be resolved before R11-R19 production edits.

Current `scripts/chess_counterfactual_evidence.py` blob
`7dccf3525049c60a72f0a2883709012d86d6adfb` verifies historical v3 receipts by
recomputing SHA-256 values from the current mutable collector/projection/intake/
score-bound files and comparing them with the receipt's `implementation_sha256`.

Current `scripts/chess_typed_position_evidence.py` blob
`396d4777701bcdc9772c68a1080140d3b6cfc4f4` pins the v3 source receipt SHA but
then calls that current collector verifier and re-derives the packet using the
current typed-adapter source hash.

Therefore editing those accepted modules in place can make the independently
accepted historical artifacts fail verification even when the artifact bytes and
original production evidence are unchanged.

Reviewed immutable identities already exist:
- v3 receipt SHA-256 `a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6`;
- v3 review blob `8e10e0f2af35e3863dfc59838042260fbd9be0d4`;
- accepted collector SHA-256 `ee3a58965c700774a7a14ab3f77eb715b5ebfa33b28469e17b97b6b98456ea93`;
- typed packet SHA-256 `7743b9fac58695a99cee8f5918e0ca6225909c1750658fc60e34c57f42a9bd0c`;
- typed review blob `50f5cf1dfbe212b9d13e62275bfaca9427f914de`;
- accepted typed-adapter SHA-256 `69d9f30a389986e3f55da46f427aaf27c2baf5b81338c08279a088be572c7c6f`.

Architecture decision: keep accepted v3 and typed-v1 source as provenance-frozen
interfaces until an explicit successor is admitted. Add a reviewed historical
lock sourced from actual artifact readback + independent-review values, then put
future R11-R19 behavior in a v4/successor collector. Current rules replay is a new
verification observation, not a rewrite of which code produced the old engine
receipt. A receipt may not self-authorize a new implementation-hash allowlist.

Native first steps after genuine C00 N/N+1 consumption:
1. Hash the actual local v3 and typed artifacts and accepted source files.
2. Run existing v3 + typed verifiers before edits.
3. Add fail-first showing current-source substitution breaks the old strategy.
4. Add the historical lock and negative substitution tests.
5. Keep old collector/typed adapter and both frozen artifact bodies byte-stable.
6. Optionally create only a v4 successor skeleton if source ownership is clear.
7. Return Runtime task/run/read/result IDs plus before/after old-source hashes.

Cloud standard-library reference: fail-first exits 1 as expected; 17 focused tests
pass; py_compile passes on Python 3.13.5. No local frozen artifact, python-chess,
Stockfish, Windows, Company Runtime, model or heldout run was performed.

Research basis: SLSA provenance separates an artifact from the exact resolved
dependencies that produced it; in-toto likewise records materials/products for
later provenance verification. This is design guidance, not a SLSA/in-toto
certification.

Full cloud task SHA-256:
`38e2ac581977cabf5d6f6ff22911424d6832ce2f4c6bf92425edb372b80a02c5`.

Typed stops:
`SLM-C02-R20-C00`, `-FROZEN-ARTIFACT`, `-SOURCE-LOCK`, `-TYPED-LOCK`,
`-PATHS`, `-CONSUMER-BRIDGE`.

Do not rewrite historical receipts, force-push, merge main, or create a second
engine/runtime path.