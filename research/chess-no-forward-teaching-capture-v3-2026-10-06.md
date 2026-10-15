# A frozen route for the next Chess.com teaching practice

The earlier local model answers did not explain why 20.Qc3 fell short of
20.Qe4. This new runner prepares one stricter experiment for the same reviewed
game. It has **not called the model**. Its job is to keep the next request
small, source-bound and replayable, then account for the sole attempt even if
the local call fails.

`scripts/chess_no_forward_teaching_capture_v3.py` accepts only the played
ply-39 Qc3 packet. It verifies the retained PGN, review receipt and page through
the packet's own encoder, checks the packet hash, and asks the v3 teaching
checker for its exact nine-field pre-move projection. That projection contains
the selected move and qualified score observation. It contains no proposed
Qe4, reply, later board, PV, Chess.com move label or checker result. The request
also freezes the v3 prompt, model, endpoint, sampling, seed and the local route
readiness files. A source or implementation change after freezing blocks the
call before the request is sent.

Capture writes the exact request with create-only semantics before its one
loopback POST. A saved request spends the attempt, including after a timeout
or interruption; there is no retry path. The raw HTTP body and result receipt
are retained. A separate offline command extracts one plain assistant message
and calls the v3 legal-option checker. A malformed envelope is retained as a
rejected claim with the raw response still available. Verification rereads the
source, request, raw body and optional checker receipt.

The focused software test first failed because the new module did not exist.
After implementation, ten runner tests passed; the runner and checker suites
passed 28 tests together. They include a fake one-call capture,
Qe4/Qxb7+ conditional lesson, source tamper before POST, spent timeout and
interrupted attempts, frozen CLI pins, duplicate response keys, malformed
assistant content, raw/evaluation tamper, and
an actual source-bound freeze of the retained Chess.com Qc3 packet. That real
freeze made zero model and engine calls. The test skips the last check when
the ignored local game and route evidence are absent from a fresh checkout.

This is still development practice. A legally checked conditional option is
not proof that Qe4 is better for that reason, that the named reply is likely,
or that Stockfish intended the line. We need a real one-attempt model capture,
inspection of its raw answer, and independent review before saying this
version helped the game explanation. The separate game-disjoint and chess
reviewer requirements in `chess-commentary-capability-gate-v1.md` remain open.
