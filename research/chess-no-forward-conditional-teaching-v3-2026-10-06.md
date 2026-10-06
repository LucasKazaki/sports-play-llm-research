# A checkable conditional chess lesson, v3

**Status: software candidate with one unsuccessful real-game model trial.** It
has no accepted teaching response, quality score or capability result. The
existing no-forward input, typed v2 prompt and its receipts remain frozen.

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
or Stockfish's intention. The first live attempt below retains model identity,
request, raw output, module hashes and its outcome, but yields no lesson. Any
teaching-quality claim still needs the game-disjoint protocol and independent
chess review in `research/chess-commentary-capability-gate-v1.md`. Board-game
expansion remains gated there.

## One real-game model trial

We tried the frozen v3 prompt once on the played 20.Qc3 from the exported
Chess.com game. The local endpoint returned HTTP 200 and the
expected model identity; there was one call and no automatic retry. It spent
509 of its 512 completion tokens on reasoning, stopped at the length limit,
and returned no answer text. The checker rejected the empty result as
`invalid_model_envelope` / `invalid_response_length`. It produced no teaching
sentence, and no chess teaching quality was evaluated. The separate integrity
check passed for the saved request, raw reply and evaluation; it does not make
the reply useful or pass the commentary gate.

The frozen request SHA-256 is
`6013644c4520b4d8ecfef4f191e7b52078955f748ebcca78331b3024bb4d3a37`;
the raw reply SHA-256 is
`2f74cd54ffcc172c0161f99a8a9976a3caee448765187d782c02f5c780db9cdd`.
The retained run is
`artifacts/chess-no-forward-teaching-capture-v3/chesscom-184866057876/played-frozen-20261006/`.
Native evaluation and verification are bound by
`C:/AI/projects/LucasAgentStudio/data/company-runtime/project-execution/35fc2d789ba6f2679b8923ca442f12f478109f37cdea1c0b5239b93972d1de6a/ba538a32e10dff7b846200ea6c89acbc8ed56ab5b7fb40196cb302cbcc3f03e6/receipt.json`.

The next distinct trial can freeze a new versioned route and request with
`max_tokens=1024` and a 60-second timeout. That tests whether the small answer
budget caused the empty reply; it must use a new run rather than replay or
overwrite this one. Even a
valid JSON reply would still need the separate board-fact checks, fresh-game
evaluation and independent chess review before a teaching claim.
