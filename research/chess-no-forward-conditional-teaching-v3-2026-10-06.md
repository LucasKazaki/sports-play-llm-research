# A checkable conditional chess lesson, v3

**Status: software candidate for development practice.** This adds no model
response, engine search, quality score or acceptance result. The existing
no-forward input, typed v2 prompt and its receipts remain frozen.

## The small change

`scripts/chess_no_forward_teaching_v3.py` rechecks a pinned original Lichess or
completed-game packet through its owning source encoder. It projects only the
pre-move board, selected move, deterministic transition, qualified score and
source identity into a v3 generator input. The old assertion declaration is
replaced by v3's two output choices: a conditional option difference or an
abstention. The proposed alternative, reply, option, future board, saved line
and review label never enter that input. `generator_messages` prepares text for
a future separately frozen runner; it does not contact a model.

For a claim, the model must name a legal alternative by the **same piece from
the same square**, a single opponent reply legal after either move, and a
destination for the moved piece. After generation, the evaluator replays both
branches. It requires the reply to have the same SAN in both, the moved piece
to survive, the option to be legal only after the alternative, and any claimed
capture, check or mate to occur. Source failures stop evaluation. Malformed,
false, ambiguous, forced or engine-intent claims yield no teaching text. An
admitted claim receives one sentence assembled from replayed SAN and fixed
words; the model's prose is never rendered.

The source-bound Chess.com development position supplies a concrete check:
after Qc3 or Qe4, ...Qxd4 is legal, but Qxb7+ is available from e4 and not
from c3. The same queen exchange is possible after both moves, so that exchange
alone does not explain their difference. This checked option is conditional on
...Qxd4; it does not prove why Stockfish scored either move as it did. The game
is practice, never heldout evidence.

## Verification and limits

Run `.venv-soccernet/Scripts/python.exe -m pytest tests/test_chess_no_forward_teaching_v3.py -q`.
The local run passed 18 tests. The focused suite covers the checked Qc3 sentence and actual local source
binding, no-forward projection, abstention, illegal and ambiguous replies,
false options and events, wrong piece/square, duplicate JSON keys, unsupported
wording, and packet/source tampering. The actual source-bound test skips when
the ignored local PGN and review assets are absent on a clean clone.
It pins packet SHA-256 `02c5f3955bf1649534e62b505659e6915ef98800b76938b9a6c00d44d82c7eec`,
PGN `684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`,
review receipt `b76e4746eadf4b85775468df0ee7324272dcb677673efe58dd8d4a8b40a3b730`
and page `ed6ddf506897c76fce2856fb4e82e3c2a2a9ae6a8f48bfd93efb3c31b4b27a5b`.
An independent review caught a false generic label for a pawn that promoted:
the first sentence called it a moved queen. A synthetic promotion case now
checks that the fixed sentence says "promoted queen" instead.

This is a one-reply option checker, not a full variation or move-quality
grader. It cannot determine which reply is likely, whether an option is wise,
or Stockfish's intention. A future runner must freeze model identity, request,
raw output, module hashes and all attempt outcomes before a live test. Any
teaching-quality claim still needs the game-disjoint protocol and independent
chess review in `research/chess-commentary-capability-gate-v1.md`. Board-game
expansion remains gated there.
