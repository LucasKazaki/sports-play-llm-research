# Private GothamChess benchmark intake — October 15, 2026

Three recent videos are now downloaded locally. They are source material for
choosing observational test positions. No position, game score, model comparison,
or training example has been accepted from them yet.

The current source record is
`gothamchess-private-benchmark-2026-10-15.json`. It records three successful
downloads, hashes, sizes, public metadata and media inspection. The older
October 14 discovery index remains intact. Fresh channel/detail extraction
returned different titles and October 14/12/10 upload dates; the older index
listed October 14/11/7. Retain both observations rather than silently correcting
historical evidence. The channel scan observed the first 40 uploads and selected
its first three AI-title candidates. This is a bounded latest-upload check.

## Reproduce acquisition

Install `requirements-gothamchess.txt` into the existing project environment;
the retained run used yt-dlp 2026.08.19 and an installed FFmpeg. From the
repository root:

```powershell
& '.venv-soccernet\Scripts\python.exe' scripts/collect_gothamchess_media.py discover --scan-limit 40
& '.venv-soccernet\Scripts\python.exe' scripts/collect_gothamchess_media.py collect --manifest research/gothamchess-source-selection-2026-10-15.json --download
```

Without `--download`, the second command only validates source metadata. The
collector checks video identity, the known GothamChess channel ID and public
availability before requesting bytes. It records per-video failures and hashes
completed files. Videos, temporary streams, and receipts remain under ignored
`data/private/gothamchess/`; no cookies, login, subtitle collection, or access
workarounds are supplied. Existing completed media is reused by yt-dlp and
hashed again. A rerun refreshes the private receipt, so retain or version its
previous hash before replacing provenance used by a frozen experiment.

The local copies are for private review. User authorization to download is not
a training or redistribution license. Do not commit the videos, full
transcripts, or copied creator analysis. Use separately permitted sources for
Stockfish training and teacher data. Titles and on-screen labels are creator
claims; they do not authenticate model versions, prompts, budgets, or Elo.

## Accept a position

Copy `gothamchess-position-intake-v1.template.json` for each candidate. Leave
the template unfilled in version control until an actual observation exists.

1. Prefer a creator-provided original game PGN with source URL and applicable
   rights. No direct `.pgn` link appeared in the three extracted descriptions.
   Shortened links and comments have not been exhaustively investigated. If
   transcribing video manually, record the actual mainline and mark every
   uncertainty. A displayed board may be an illustrative variation.
2. Bind the candidate to the video hash and timestamp, plus a private frame.
   Reconstruct the full legal state from the starting position and moves.
   Piece placement alone cannot establish castling rights, en passant,
   move counters, side to move, or which game/variation the creator showed.
3. Replay every preceding move with a declared chess-library version. Record
   the resulting full FEN and the observed played move. Check that the move
   is legal. A human reviewer must check the board, move and mainline against
   the source, with a retained name, date and short notes. Never populate a
   reviewer or passed flag from this template or from a successful download.
4. Assign the entire original game to the observational holdout. Check its
   game fingerprint and each candidate position against the frozen training
   and development manifests, including transpositions. Exclude the whole
   game from Stockfish distillation, prompt examples and tuning. Keep exact
   exclusion receipts, not just a stored completion boolean.
5. Freeze the evaluation protocol before running a local model. For move
   selection, expose only the pre-move FEN and side to move. Keep the observed
   played move, creator comments, future moves, engine continuations and all
   evaluator labels sealed. A separate selected-move explanation task must
   follow the existing no-forward commentary gate and record its own allowed
   input packet.
6. Report raw legality, board-state accuracy, engine-relative move quality,
   evidence-supported rationale, abstention, latency and failures separately.
   Retain every selected case in the denominator. Compare identical prompts,
   representations and compute budgets where possible. A similar move in a
   creator-edited game is neither calibrated Elo nor validated teaching skill.

The source videos can help identify useful failure cases. Their edited format
does not establish a controlled frontier-model baseline, and successful local
acquisition does not satisfy the commentary capability gate.
