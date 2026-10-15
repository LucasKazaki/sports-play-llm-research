# A smaller question for the chess explainer

The first two model attempts on the saved 20.Qc3 position did not produce a
checked lesson. The 512-token attempt spent almost its entire allowance on
reasoning and returned an empty answer. The 1024-token attempt returned the
requested JSON, but it put Black's knight on e5 and suggested `e5d7` as a reply.
The source position has that knight on e3. The checker rejected the reply as
illegal. Both attempts stay in the development record: **two requests, two
model calls, zero admitted lessons**. Their raw bytes and separate evaluations
are retained under `artifacts/chess-no-forward-teaching-capture-v3/`.

The v3 prompt asked one model response to name a legal alternative, a reply
legal after either move, and a later option for the moved piece. That is a lot
of chess geometry for one short answer. Merely giving the model more tokens
solved the empty-output problem, but not the invented square. We should not
turn the rejected reply into a passing answer by replacing it afterward.

The separately versioned v4 checker asks the model for a smaller hypothesis:
one other legal move by the same piece from the same square, or an explicit
abstention. It sends the same **nine kinds of pre-move information** as v3:
source binding, the position before the move, the selected move, immediate
transition facts, one typed score observation, and assertion kinds. The model
does not see an alternative menu, a reply menu, a post-move board, engine line,
alternative score, or Chess.com label. A menu of legal replies would be a
future-move feature, even if generated deterministically, and would cross the
current no-forward boundary.

Only after the model responds does an offline checker search for a conditional
example. It intersects the legal opponent replies after both moves, keeps only
replies with the same SAN and a comparable moved piece, and tests the piece's
follow-on captures or checks. It reports the first witness under a fixed
ordering and saves how many replies and options it examined. If none qualifies,
it withholds a lesson and records an **evaluator abstention**. That remains
different from a model abstention or a rejected illegal proposal. No engine or
model is called by the checker.

A verified witness would mean only that a particular option is legal after one
proposed move and one named reply, but not after the played move and that same
reply. It would not mean the proposed move is stronger, that the reply is best
or likely, or that Stockfish valued the option. For this practice game, the
known `20.Qe4 Qxd4 21.Qxb7+` line is a useful legal regression. It is not a
blind case or a label to place in the model input. The model's earlier `Qc4`
proposal, if made again, must stay `Qc4`; a legal illustration for it cannot
be relabelled as a reason 20.Qe4 was preferred.

The v4 capture runner retains one create-only request, raw response, exact
route and source hashes, and an offline evaluation. An interrupted or malformed
attempt still spends its place in the denominator; it is never retried in the
same frozen folder. The two v3 attempts remain a separate 0/2 result. A future
v4 practice call starts its own declared denominator, not a rewrite of v3.

One frozen v4 call has now run. It returned HTTP 200 from the matched local
model with `finish_reason=stop`, one attempt, one model call, and zero automatic
retries. Its request SHA-256 is
`dbcb08291ade74836a1ef1245fe665488cb824d80562478ba6726ca85d22dea2`;
the raw response SHA-256 is
`3180c0051848a4c62c2f7d9f7b89d840bf773f6a79c336e88bd4aea565a699ce`.
The model proposed `c2b3` as an alternative, but wrote a free-form value in
the required `hypothesis` field. The offline checker rejected it with
`unsupported_hypothesis` before searching for a witness. There is **no admitted
v4 lesson in one attempted call (0/1)** and no teaching-quality rating. The
raw response, request, and separate evaluation remain in
`artifacts/chess-no-forward-teaching-capture-v4/chesscom-184866057876/played-frozen-20261006/`.
The v3 attempts remain 0/2 under their earlier schema; the three calls are
all visible but are not a single frozen quality experiment.
Native evaluation task `882ac5ed-9d6d-4067-b98b-45bf2b72665d` checked the
saved response and verified the run's integrity. Its authoritative receipt is
`C:\AI\projects\LucasAgentStudio\data\company-runtime\project-execution\35fc2d789ba6f2679b8923ca442f12f478109f37cdea1c0b5239b93972d1de6a\b2e09a28cd769daa70fd3cf17a7784d3ce4948e2787a45e628fa7719a7eac927\receipt.json`
(SHA-256 `b3bb18de80ad8f0d81f5261a630b80ea8ab713725418602367b793685314eb58`).
The earlier native capture receipt has SHA-256
`02124f17b40eee0724b739c8860c357fd8a9e178c9e434293f4f9b53c4710752`.

The focused native check of the final v4 source passed **12 tests** and Python
syntax compilation. It included a promoted-pawn wording case and a complete-looking
JSON response cut off with `finish_reason=length`; that response keeps its raw
envelope and is rejected. Native task
`0bb9d528-6072-43ac-b32c-c89059cc23fd`, job
`50626baf-4af1-4bc5-b0d3-d6dca0057234`, has an authoritative receipt at
`C:\AI\projects\LucasAgentStudio\data\company-runtime\project-execution\35fc2d789ba6f2679b8923ca442f12f478109f37cdea1c0b5239b93972d1de6a\00299fe01479b43d4eb12f30e7ca6c16f986ce7b1ed274871eb2aca9f41bb773\receipt.json`
(SHA-256 `6409cf354f483f0184a458dc5a4bd2815c82b75d72049a47d69951c00c178811`).
An independent source reviewer passed the revised five-file implementation
for this narrow software scope. The review did not judge a model lesson or
validate the project's chess-commentary capability.

The [draft explanation-quality protocol](chess-explanation-quality-protocol-draft-2026-10-06.md)
still needs a numbered freeze and a fresh game-disjoint holdout before any
capability claim. A synthetic legal-witness test and one Chess.com practice
position show that the software can check a conditional example; they cannot
show that a human would find the explanation helpful or that this project
matches Game Review.
