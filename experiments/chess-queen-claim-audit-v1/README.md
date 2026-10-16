# Queen claim audit v1

The [closed result](RESULTS.md) now records four completed audits and an
independent replay. The premeasurement instructions below are retained; their
exact reviewed bytes are saved with the closed evidence.

This is a small offline evaluator for claims manually annotated by Codex in four
already spent Queen demonstration responses. It checks the exact statement's assigned
board and variation. It does not judge a whole explanation, interpret prose, call
a model or engine, repair a response, or change the live app or training data.
No actual authored claim measurement has run yet. Independent source review and
root and independent local-agent review of each text-to-predicate/branch mapping
are required first. These are agent-authored annotations, not human gold labels.
No human chess expert or tutor has validated their semantic interpretation.
This package is an engineering diagnostic, not expert factuality validation.

The research basis is [ACT-Eval v1, submitted August 4, 2026](https://arxiv.org/abs/2608.04240v1):
checking atomic claims against their appropriate states is distinct from judging
concept coverage or move quality. This implementation uses Codex mappings and a
small deterministic rule subset; it is not an ACT-Eval reproduction or judge.

The [frozen protocol](protocol.json) binds the implementation, tests, contract and
four original response hashes. The first software draft and 37-pass receipt are
retained separately. The second premeasurement draft also preserves the earlier
source/tests/protocol/receipt/README with inaccurate human-review wording; this
version corrects that wording and records the actual annotation/reviewer origin.
Self-review added CLI enforcement of the declared
response pool; the current [software receipt](software-tests.json) records 38
passing authored CPU tests. No saved learned response or held-reference content
is used by those tests. Two full review bundles remain under the current chat's
`work/research-loop-quality/claim-audit-review/`; each is below 30 KB.

## Bind the text before checking it

An annotation envelope has exactly `schema`, `response_sha256`,
`raw_text_sha256`, and `claims`. Each claim has exactly `claim_id`, `span`,
`context`, and `claim`. `schema` is `chess.queen-claim-annotations.v1`.

`response_sha256` binds the exact original JSON bytes, including whitespace.
`raw_text_sha256` binds the UTF-8 encoding of the decoded `raw_text` field.
`span` contains `start`, `end`, and `sha256`: offsets are zero-based Python
Unicode code points with an exclusive end, and the hash is over the exact UTF-8
substring. They are not UTF-8 byte offsets or JavaScript UTF-16 offsets. Native
chess tokens and punctuation remain exactly as emitted; do not substitute the
UI's translated text. Every row's binding is checked before any verdict. A bad
response/text/span hash, duplicate JSON key or malformed envelope rejects the
audit, even if another claim would have been supported.

Hashes establish identity. They do **not** prove that an annotation correctly
interprets the prose, its hypothetical branch, side, or intended time. The root
and an independent local agent inspect that correspondence separately. This
agent review does not substitute for human chess-expert validation. The output always says
`semantic_mapping_automatically_verified:false`.

## State and supported claims

The root is only `response.input.fen`. An annotator cannot replace it with a FEN.
The response's `selected_uci` is not silently played. `context` contains exactly
`resolution`, `branch_uci` and `expected_turn`. Only `resolution:"explicit"`
can be assessed. `branch_uci` lists 0–64 actual coordinate moves from that root;
`expected_turn` is `white` or `black` at the resulting board. Replay never skips
an illegal ply. An ambiguous branch, illegal earlier prefix, changed turn or
extra context field makes the later claim **unassessed**. An independently false
looking predicate is not evaluated on an invented replacement board.

| Kind | Required claim fields beyond `kind` | What is measured |
| --- | --- | --- |
| `piece_count` | `color`, `piece_type`, integer `expected` | Literal count of pawns, knights, bishops, rooks, queens or kings for one side. |
| `material_count` | `color`, `expected` dictionary with all five non-king piece names | Literal pawn/knight/bishop/rook/queen counts. No piece points, advantage or position judgment. |
| `geometric_attacks_square` | `piece:{color,type}`, `from_square`, `target_square`, boolean `expected` | Occupancy-aware attack geometry of that actual piece. Includes pinned pieces and a friendly occupied target; reports pin state. Never legal capture, recapture, successful defense or king safety. |
| `legal_variation` | `moves_uci`, boolean `expected` | Whether this explicit 1–64-ply line legally replays from its valid context; retains the first failed ply and legal prefix. No engine attribution, forcedness or whole-prose inference. |

Colors are `white`/`black`; piece names are singular lowercase. Coordinate moves
include promotion suffixes. Replay handles en passant, promotion and castling.
It checks terminal conditions available from the current FEN and explicit branch;
it does not reconstruct earlier repetition from `input.history` or claim optional
draws. Unsupported kinds, malformed predicates or absent attacker identity remain
unassessed. A syntactically valid but illegal *claimed variation* can contradict
that bound legality assertion; an illegal *context prefix* cannot establish a
later assertion. A legal main line never validates an illegal prose alternative.

## Execution and reporting

After both reviews, use the repository Python environment:

```powershell
./.venv-soccernet/Scripts/python.exe scripts/chess_queen_claim_audit_v1.py `
  --protocol experiments/chess-queen-claim-audit-v1/protocol.json `
  --protocol-sha256 <reviewed-exact-protocol-SHA256> `
  --response <original-private-response.json> `
  --annotations <reviewed-private-annotations.json> `
  --out <new-private-audit.json>
```

The CLI rejects response bytes outside the protocol's closed four-response pool,
checks the exact implementation/contract, caps each JSON input at 2 MiB and
annotations at 256 claims, and creates output only if it does not already exist.
Keep every attempt and review receipt. Do not replay over an existing output.
The CLI cannot certify that an independent review actually occurred; dispatch
remains with the root after the retained independent verdict and mapping check.

Report supported, contradicted and unassessed annotation counts together. The
assessed-annotation fraction and supported fraction among assessed annotations
describe only this manual inventory, which is not a random sample or automatic
coverage of the prose. Empty inventory yields undefined fractions, not a perfect
score. Keep ambiguous/unsupported entries visible. These four spent authored
responses cannot establish chess strength, teaching quality or a heldout gain.
All output, branch FENs and corrections are evaluator-only; never pass them into
the generator, current training corpus or active heldout evaluation.
