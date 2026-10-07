# Candidate update for Archit's project document (v13)

Internal candidate only. The prose below has not passed the project's independent Luna review and later Terra promotion gate. It reports one Chess.com practice game, a repaired local review, four more practice positions, and software checks. It is not a measured commentary-quality result.

## Suggested document edit

Replace the current sections **“What the first version would do”** and **“How I'd test it”** with the following. Keep the personal reason for starting with chess and the later sports sections around them. Refresh any new model result before promotion.

### What I've built and what I still need to prove

I can now replay a completed chess game move by move, compare a move with a legal alternative, and check both against short Stockfish searches. The tool saves the board and an annotated game so I can check my work. An earlier page shows eight real Lichess positions, but these pages still show evidence better than they explain it. In our first eight-position model run, six replies were loose prose and two calls failed; none gave us a checked set of claims.

I have prepared 24 more Lichess positions, eight each for training, development, and a reserved test group. They come from 24 different games, but I put every game ID, including the reserved eight, in the draft record. I need a fresh, separately sealed set from different games before I can make a chess capability claim. I also built a reader that checks the moves in ordinary completed games; I have not added any of those games to a new test set yet.

I used the Chess.com Game Review already open for one practice case. It called 20.Qc3 a mistake and suggested 20.Qe4. I fixed a saved-file mismatch in our local review and then corrected my first explanation: Black can take the d4 pawn and trade queens after either move. After one Black reply to Qe4, White can take on b7 with check; another saved reply blocks that route. Those legal examples help me ask a better question, but the live Chess.com label is only a practice reference, and the examples do not tell me Stockfish's full reason.

Two saved, paired Stockfish searches put Qe4 ahead of Qc3, even though Qc3's score was only a bound. I cannot call that an exact cost for Qc3 or a causal explanation. Another comparison stopped because the two moves had not been searched to the same depth. The first runs also exposed two faults in our local checks, which I repaired and verified.

I asked the local model about Qc3 and Qe4 without showing it later moves. Its first Qc3 reply made a claim I could not check; its Qe4 reply mostly copied the move and score. Two more Qc3 calls gave no accepted lesson: one returned no answer, and the other named an illegal reply. One later call also produced no accepted lesson because its answer format failed the check. Two simpler designs are ready but have made no model calls. These were practice attempts on one known game, not a test of teaching quality.

I checked four more moves from that same game against the live review cards. Three score comparisons were too limited for a numeric difference; the fourth rests on one short paired search. A new checker passed 16 software tests and accepted four hand-written test claims about the board, with no model call. Its independent source review is still open. My next step is to finish that review, try one saved model response per move, count every failure, and test on fresh games with independent chess judgment. I cannot yet say our explanations match Chess.com, let alone improve on it. I will try another board game only after the separate chess capability review; sports will need their own video evidence and coach testing.

## Evidence and review notes

The detailed source and receipt ledger for this draft is in [the evidence notes](archit-overnight-update-evidence-2026-10-06.md). Keep those notes out of the live document; send their full text to the independent reviewer.
