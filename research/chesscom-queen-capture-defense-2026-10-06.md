# The protected capture after 20.Qe4: a bounded practice finding

The Chess.com practice game has a useful teaching detail that the saved score gap alone cannot explain. From the source game's position before move 20, both `Qc3 Qxd4 Qxd4 Rxd4` and `Qe4 Qxd4 Qxd4 Rxd4` legally reach the **same** board. So “Qe4 stops ...Qxd4” is false. The difference is an option White has *instead* of trading queens if Black takes on d4.

After `20.Qe4 Qxd4`, `21.Qxb7+` captures the b7 pawn with check. The queen on b7 is defended by White's bishop on f3 along `f3-e4-d5-c6-b7`, because the queen has vacated e4. In this exact position, the only legal Black reply is `21...Kd7`; `...Kxb7` is illegal. After `20.Qc3 Qxd4`, White has a superficially similar checking pawn capture, `21.Qxc7+`, but **no White piece defends c7**. The only legal reply is `21...Kxc7`, winning the queen. This is a concrete difference in piece coordination and in the safety of the checking capture. It also explains why a learner should inspect the defender of the destination square, rather than treat every capture with check as good.

This is a **legal-line fact, not a full explanation of Stockfish's choice**. The saved 100,000-node, five-PV probe after `20.Qe4 Qxd4` put `21.Qxb7+` first at a White-perspective **+78 centipawn upper bound**; an upper bound is not an exact advantage or proof of a forced result. Black can choose other move-20 replies: the saved paired line uses `20...Nd5`, which blocks the queen's route to b7. The 10,000-node paired root search observed `Qc3 -471` and `Qe4 -95` centipawns from White's perspective; the separate 30,000/100,000-node observations remain qualified search results, not a measured causal contribution for this motif. Nothing in this note should enter a no-forward generator packet. It is evaluator-side evidence for post-generation checking and for a carefully labelled practice lesson.

## Source and reproducibility

- Source PGN: `artifacts/chess-user-reviews/chesscom-184866057876/source.pgn`, SHA-256 `684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`. Its mainline legally replays to ply 38 FEN `2kr3r/pppq3p/4pp2/6p1/1P1P4/P3nBPP/2Q3P1/RR4K1 w - - 0 20`.
- Existing paired search: `artifacts/chess-user-reviews/chesscom-184866057876/review-v3-paired-explanation-20261006/review.json`. Existing reply probe: `artifacts/chess-user-reviews/chesscom-184866057876/qe4-qxd4-evaluator-probe-20261006.json`. Earlier legal replay: `artifacts/chess-user-reviews/chesscom-184866057876/qe4-qxd4-legal-replay-20261006.json`.
- I used the project-local `.venv-soccernet\Scripts\python.exe` with `python-chess`, verified the PGN hash, replayed its first 38 mainline moves, then replayed each three-move line with `Board.push_san`. For each resulting board I ran `Board.attackers(chess.WHITE, target_square)` and enumerated `Board.legal_moves`, rendering replies with `Board.san`. The exact checked lines and outputs were:

| Legal prefix | White defenders of captured square | All legal Black replies |
| --- | --- | --- |
| `20.Qc3 Qxd4 21.Qxc7+` | none on c7 | `21...Kxc7` |
| `20.Qe4 Qxd4 21.Qxb7+` | bishop on f3 protects b7 | `21...Kd7` |

This one game is a post-game development example. No new engine or model call, blind holdout, teaching rating, or claim of Chess.com parity came from this check. Chess.com's score and classification are an observed UI comparison, not inputs to the legal replay.
