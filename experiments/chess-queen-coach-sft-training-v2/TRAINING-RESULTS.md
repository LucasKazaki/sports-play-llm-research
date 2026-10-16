# Full local coaching training result

The fresh v2 pilot completed **256 optimizer updates and 2,048 backward passes**
over 1,024 training games. Independent closed-file review verified the seeded
order, all planned training outcomes, four complete development conditions,
saved optimizer/adapter contents and unchanged frozen storage. No training
presentation is unknown or never run. The discarded diagnostic and failed v1
attempt remain separate.

Each development condition includes 64 response-token loss calculations and
eight raw requests from four games, with free and supplied-move modes. These
are development results, not a fresh test or a representative chess estimate.

| Saved step | Response-token loss | Free three-ply teacher match | Complete EOS requests | False / recognized narrow fact claims |
| --- | ---: | ---: | ---: | ---: |
| 0 | 2.1122 | 1/4 | 6/8 | 0/0: no recognized claims |
| 64 | 0.1234 | 3/4 | 8/8 | 5/12 |
| 128 | 0.0427 | 1/4 | 8/8 | 2/16 |
| 256 | 0.0362 | 1/4 | 8/8 | 2/16 |

The frozen development rule selected **step 64**, representing 512 training
presentations. It prioritizes accepted legal best moves, then free three-ply
teacher agreement, then free best-move agreement, loss and earliest step. It
does not select on explanation factuality. Lower later loss did not preserve
the same forecast result, so the final training step does not replace the saved
selection. All four checkpoints remain private and retained.

The selected adapter contains 144 finite FP32 tensors and 1,916,928 parameters;
all 144 differ from initialization. The recorded frozen-storage digest covers
2,268 tensors and 3,393,484,936 bytes before and after. An independent reviewer
verified the receipts and executing hash code; no separate post-exit frozen
tensor snapshot was retained. All 1,920 observed resource samples pass the fixed
floors, with minimum Windows commit headroom 8,116,699,136 bytes.

The once-only fresh test is now running: 32 responses from the starting
checkpoint and 32 from step 64 on the same 16 fresh game groups. Reference
content stays sealed until both raw panels close. The UI continues to use its
qualified original model; no tuned model has been promoted.

Step 64 still makes five false claims among twelve recognized narrow claims.
The starting model's zero recognized claims does not mean zero factual errors.
All whole prose remains unscored. Neither these small development counts nor
training completion establish broad chess understanding, Elo or teaching
quality. The next data hypothesis concerns balanced legal selected-move
counterfactuals; it is not a demonstrated explanation repair.

The [compact result](training-result.json), [exact evidence manifest](training-evidence-manifest.json)
and [independent closed review](training-evidence/queen-coach-sft-training-v2-closed-review.json)
retain source and result identities. Raw development records, source-game data,
targets and weights remain private. The review explicitly records that the five
source snapshots had no manifest frozen before dispatch; exact source bytes,
protocol pins and the post-extracted original dispatch record remain available.
