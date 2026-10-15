# Local chess execution — October 15, 2026

**Candidate engineering and experiment report. Both fine-tuned checkpoints remain unpromoted.**

The local research path now runs on Windows with the RTX 5080. It acquires bounded CC0 Lichess data, produces Stockfish labels, updates actual model weights, retains full outputs and measures results against a fixed teacher. A source-matched input format makes the small base specialist usable; the two training pilots did not improve move agreement.

## Observations

ROOK-LM-124m is pinned to `c16158d399a61847cbcb616ecf2e36e6c96e16ca`. Stockfish 19 used one thread, 64 MiB hash, a 10,000-node budget and a hash clear per position. All labels use the side-to-move score perspective. The source is a retained 4 MiB prefix of the [Lichess CC0 puzzle database](https://database.lichess.org/), a tactical convenience sample.

| Pilot and split | Base legal | Trained legal | Base teacher matches | Trained teacher matches |
|---|---:|---:|---:|---:|
| v1 development | 34/64 | 3/64 | 2/64 | 1/64 |
| v1 holdout | 40/64 | 3/64 | 6/64 | 0/64 |
| v2 development | 128/128 | 127/128 | 24/128 | 21/128 |
| v2 holdout | 127/128 | 127/128 | 33/128 | 27/128 |

V1 trained on 800 positions for 200 optimizer updates, with 1,600 example presentations. Its development completion-token NLL fell from 4.299 to 1.838 while action quality collapsed. Inspection found a missing native `P:` prefix, a training/inference token boundary mismatch and changed field formatting. The first evaluation also raised on the malformed action `a7a7`; its log and checkpoint were preserved, and evaluation was completed with fixed failure accounting, without retraining. The original first-run source was not separately snapshotted, so its evidence binding is weaker than v2.

V2 used 3,200 new training games and 128 new games per evaluation split, excluding every historical seed and v1 game/board. It uses native `P:/M:/E:/B:` field padding, paired candidate order and joint tokenization with an exact inference-prefix assertion. It trained from the unchanged base for 800 updates, 6,400 presentations, at learning rate 0.000002. Development NLL fell from 1.0333 to 0.9706; teacher agreement still declined. The optimizer phase took 55.321 seconds. The original receipt's 81.507-second field includes later evaluation/loading and must not be described as optimizer time.

A reviewer caught a candidate-fallback parser issue because v2 supplies `M:` in the prompt. A deterministic recount used the retained completions, preserved the original receipt and execution snapshots, and made zero model calls or optimizer updates. No retained result needed that fallback, so its aggregate counts were unchanged. A later repeated-marker parser edge was fixed for future calls without rerunning holdout generation.

The corrected base produced 255 legal actions out of the 256 v2 evaluation positions and 57 teacher matches. This is a descriptive source-bound pilot result, not a representative strength estimate. Several v2 changes were made together; the comparison does not isolate the effect of the `P:` prefix.

## Installed larger-model control

The installed Ollama alias `qwen3.8-27b-local-q2k:latest` was actually called on four development positions. Its backend metadata reports family `qwen35`, 27.3B parameters and Q2_K; the alias alone is not an independent model-version attestation. FEN-only input yielded 0/4 legal actions and 0/4 teacher matches. Explicit piece maps and legal-move lists yielded 4/4 legal actions and 1/4 matches. These are separate raw and tool-assisted conditions. No Qwen weights were changed and no engine answer entered either prompt.

## Limits and review decision

- Keep the pinned base specialist as the executable default. Both trained checkpoints are completed negative experiments, not improvements.
- Candidate lists correctly contain up to five legal moves. Stockfish top-ranked results carry bounds in 200 training, 7 development and 8 holdout cases. Training targets retain CP versus mate types but omit bound qualifiers; generated score faithfulness is unmeasured. Do not display predicted scores as engine evidence.
- New source games are disjoint across splits and from prior project samples. Unknown overlap with the base model's pretraining remains possible. Both local holdouts are now spent; future selection needs new frozen games.
- No Elo, calibrated playing strength, faithful commentary, human teaching quality, proprietary-model equivalence or sports transfer was established. The no-forward commentary gate remains open.
- Three recent GothamChess videos are retained privately with verified audio/video and file hashes. No full video/transcript is committed or used for training. Zero video-derived positions are accepted yet; no direct PGN link was found in their descriptions.
- Focused changed-area checks and independent practical source/receipt review were performed. The repository's formal runtime/research-promotion sequence was not claimed. Older compatibility checks require ignored source/evidence fixtures missing from this fresh clone; their failures are retained separately, not reported as a green full suite.
- Implementation and candidate notes were produced with Codex assistance. Lucas should review the interpretation and his supervisor's requirements before sharing.

## Local use

The new chess-only environment uses installed Python 3.12.2, torch 2.8.0+cu128 and transformers 5.19.0. The historical soccer Python 3.11 lock remains untouched. Acquire the pinned public model using Hugging Face's `snapshot_download` with the revision above and files `*.json`, `*.txt`, `model.safetensors`, excluding `onnx/*`. Preserve the model-card license notice. `requirements-chess-distill.txt` lists the new chess dependencies; install the CUDA torch wheel from PyTorch's cu128 index before the remaining packages.

```powershell
& .\.venv-soccernet\Scripts\python.exe .\scripts\chess_rook_policy.py --fen 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
```

The command uses the local pinned base model, emits the raw output and accepts only a legal move. An illegal output returns an abstention and exit code 2. [The inspector instructions](../prototype/chess_demo_ui/README.md) explain local viewing and JSON import. Full receipts, checkpoints, source bytes and videos remain under ignored `data/private/`; portable aggregate records are under `experiments/`.

## Next experiment

Treat move selection and numerical score prediction as separate objectives. Compare a small move-classification specialist and a legal candidate scorer on new game-disjoint development data, with immutable inputs, bound-qualified teacher labels and a fresh final holdout. Add a matched-representation larger-model control before claiming that specialization improves the full task. Separately verify video game histories and legal positions before creating a fixed observational challenge set.

Primary serialization source: [pinned upstream ROOK generator](https://github.com/jorahn/RookWorld/blob/4e2d5b3a949670c98f45258cb9ba6a8eea08495f/dev/data/rook/generate_lichess.py). Only its field convention is adopted; the local teacher takes Stockfish's first side-to-move candidate rather than copying the upstream black-move selection expression. [Writing and interface source review](../research/writing-and-interface-method-2026-10-15.md) records the bounded use of StoryScope and the design guidance.
