# Candidate update for Archit's project document

Internal candidate only. The prose below has not passed the project's independent Luna review and later Terra promotion gate. It reports one Chess.com practice game and a repaired local review, not a measured commentary result.

## Suggested document edit

Replace the current sections **“What the first version would do”** and **“How I'd test it”** with the following. Keep the personal reason for starting with chess and the later sports sections around them. Refresh any new model result before promotion.

### What I've built and what I still need to prove

I can now load a finished chess game, replay it move by move, and inspect the move played beside another legal option. The tool saves the board, the engine's bounded checks, and an annotated game file. That gives me something concrete to inspect when I ask why a move was strong or weak.

The first evidence page covers eight positions from real Lichess games. It shows legal moves, links back to the games, and engine scores with the scoring side made clear. The page helps me check the analysis, but it does not yet give the kind of explanation I'd want from a good coach.

The first local language-model run exposed the main gap. Six answers came back as loose prose and two calls failed; none became a checked set of claims. A fluent answer is not enough. I want each explanation to say which board fact or engine observation supports it, and to admit when the evidence does not settle a question.

I've prepared 24 more positions from public Lichess games, split so the same game does not appear on both sides of the test. The final eight are held back. Before I use them, I need to decide exactly how to count factual errors, unsupported reasons, useful abstentions, response time, and failed calls.

I've also built a reader for ordinary, completed chess games so the next set can include quiet decisions and mistakes, not just puzzles. It checks each recorded move on the board and rejects incomplete or malformed games. I haven't brought that new set in yet, so it does not add any measured examples today.

I tried this on the completed game already open in Chess.com Game Review. At move 20, its review called **Qc3** a mistake and pointed to **Qe4**. I exported the game and ran our local review on 20.Qc3. That exposed a saved-file mismatch, which I fixed and checked against the same game. My first explanation was too neat: Black can take a pawn and trade queens after Qc3, but the same trade is possible after Qe4. I built a page where I can step through each move and see what changes on the board. Qe4 creates a checking idea on b7; one Black reply leaves it open, while the saved alternative reply blocks the queen's route. Those legal examples make the position easier to understand, but they are not a complete account of Stockfish's score.

I started a repeatable comparison for any legal move, and the first runs exposed two faults in the local checks. After I fixed them, two saved Stockfish searches placed Qe4 well ahead of Qc3. Qc3's scores were bounds, so I can say the saved readings were far apart; I cannot claim an exact loss or explain the difference from those numbers. A separate comparison stopped because its searches reached different depths.

I also tested a local model without handing it future moves. Its first Qc3 answer made a claim I could not check, while the Qe4 answer only repeated the move and score. In two more Qc3 tries, one produced no answer and the other suggested a move Black could not legally play. I narrowed the question again to one alternative move. The model proposed one but used an answer format the checker could not accept, so this separate trial yielded no accepted lesson in one attempt. I've prepared a simpler version that asks for an alternative or an honest "I don't know," but have not tried it with the model. These are practice attempts on one saved game; I still cannot say the system teaches why a move is better.

I'll work through quiet moves and mistakes as well as obvious tactics. The goal is to explain a chosen move and its alternatives in plain language, including why a tempting move is worse, while showing the board evidence behind the answer. I still need a language model that gives checkable reasons, fresh-game tests, and an independent chess reviewer to judge whether those reasons teach well. Only after those checks and the separate chess capability review would I try another board game. Sports will need their own video evidence and coach testing.

## Evidence and review notes

The detailed source and receipt ledger for this draft is in [the evidence notes](archit-overnight-update-evidence-2026-10-06.md). Keep those notes out of the live document; send their full text to the independent reviewer.
