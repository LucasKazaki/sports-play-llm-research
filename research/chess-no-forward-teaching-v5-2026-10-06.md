# Let the model name a move, then check the example

The saved Chess.com game is still a practice case, not a quality benchmark. On
the played 20.Qc3 position, the first two v3 calls produced no admitted lesson
(0/2). The one v4 call also produced no admitted lesson (0/1). Its response was
complete and proposed `c2b3`, but the model wrote its own phrase where v4
required a fixed `hypothesis` token. The checker rejected the whole response as
`unsupported_hypothesis` before looking for a legal example. The v4 request and
raw response are retained with hashes in
[the v4 note](chess-no-forward-teaching-v4-2026-10-06.md); neither result is a
rating of the model's chess teaching. These are three visible development
attempts under two different schemas, not one frozen experiment.

V5 changes the question rather than repairing that response. It asks for only
an exact JSON abstention, or the selected move and one other legal move by the
same piece from the same square. It no longer asks the model to fill in
`hypothesis`, `modality`, or `uncertainty` labels. The checker rejects extra
fields, a changed selected move, an illegal alternative, and a move from
another square. If the model abstains, the result says so directly.

The model still receives exactly nine pre-move fields: schema, source packet
hash, source identity, pre-move FEN, side to move, selected move, immediate
transition facts, one typed engine observation, and allowed assertion kinds.
No alternative menu, opponent reply, later move, post-move position, engine
line, alternative score, or review label goes into the request. The source
packet must be replayed from the pinned PGN and review bytes before a request
can be frozen or sent. The capture folder is create-only: an interrupted POST
spends its one attempt, and a response cut off at its token limit is retained
but cannot be admitted as an answer.

After generation, the offline checker can search common legal replies and a
later option for the moved piece. It records counts and at most one deterministic
legal witness, or abstains when there is no such witness. A witness means only
that a particular option exists after one proposed move and one named reply.
It does not show that the alternative is better, that the reply is likely, or
why Stockfish assigned its score. The example sentence is an evaluator-written
template; it is not a model explanation or a human teaching judgment.

V5 is presently a software candidate with **zero v5 model calls** and no
evaluated quality. Synthetic checks cover the known `Qc3`/`Qe4` legal example,
illegal or relabelled alternatives, extra fields, source binding, prohibited
future material, an interrupted attempt, and a complete-looking answer with
`finish_reason=length`. Native test evidence and independent source review
must be attached before a v5 practice call. The separately drafted explanation
protocol still needs a numbered freeze and a fresh game-disjoint holdout
before the project can claim strong commentary, Chess.com Game Review parity,
or readiness for another board game.
