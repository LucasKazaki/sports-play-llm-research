# Closed explanation debugging result

All four offline audits completed. Independent replay reproduced all 18
manually mapped verdicts: **9 supported, 4 contradicted and 5 unassessed**.
There were no failed, unknown or never-run audits, and no new model, engine or
GPU calls. These counts describe a purposive inventory of four spent authored
demonstrations. They are not a whole-prose accuracy estimate.

| Saved demonstration | Concrete contradiction |
| --- | --- |
| Mate in one | The main move Qd8# is legal, but a prose alternative later asserts Qd8xh5. A queen cannot make that move. |
| Middlegame | The short structured line is legal. A longer prose branch later asserts Ba2-e6 while a piece on c4 blocks that diagonal. |
| Opening, free choice | After the stated Bxe3, fxe3 branch, White has one bishop. The prose claims White has the bishop pair. |
| Opening, supplied c3 | After the stated Bxe6, fxe6 branch, Black has one bishop. The prose claims Black has the bishop pair. Supplying c3 does not test independent move choice. |

The mate example's later pawn-protection sentence is **unassessed** because its
context contains the earlier illegal Qd8xh5. The checker does not invent a board
to force a verdict. Four other retained assertions need unsupported evaluative
or comparative predicates. Legal main lines do not validate these prose claims.

Codex authored the annotations; a separate local AI agent reviewed the exact
text, side and branch mappings before execution. There is no human chess-expert
semantic validation or human gold annotation. This is evaluator engineering
evidence, not a claim about teaching usefulness, Elo or a fine-tuning gain.

The [result](result.json), [exact-copy manifest](evidence-manifest.json) and
[closed independent review](closed-evidence/claim-audit-closed-v1-review.json)
retain the complete count and provenance. The original premeasurement README
is [preserved byte for byte](closed-evidence/premeasurement-readme-final.md).
Review reports bind historical paths; the manifest identifies the corresponding
unchanged snapshots. The closed review observes all eight call journal events
and the CLI's output fsync. Outer journal fsync is attributed to the executed
operator tool-call record, rather than a dispatcher file frozen in advance.

No result, corrected sentence, branch FEN or evaluator feature is passed to the
active coaching trainer, generator or held-out score. The next factuality work
needs fresh predeclared cases and broader predicates; tutor review remains a
separate requirement.
