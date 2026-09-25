# Post-hoc commentary cross-check protocol

This stage asks a text-only local LLM what soccer play is directly supported at the stated target midpoint by the SoccerNet-Echoes ASR segments aligned to each 5–10 second clip. The request includes only those segments, their clip-relative times, the clip duration, and the target-relative time. It runs only after a visual-only VLM summary has been written and hash-sealed. The visual label, SoccerNet annotation, match identity, media path, and audio are not included in the text-model request.

The output is an audit relation, not a corrected prediction:

- `supports`: the separately inferred commentary label equals the non-abstained visual label.
- `contradicts`: both inferences are non-abstained and their labels differ.
- `uninformative`: the commentary model abstains, no aligned ASR exists, or the primary visual model abstained.

Commentary never changes the primary visual prediction. The hash seal makes this stage causally non-intervening; it does **not** make the two signals statistically independent. Both describe the same broadcast event, use the same action taxonomy, and may share temporal or semantic shortcuts. SoccerNet-Echoes ASR is also noisy: speech can lag the visible action, describe surrounding context, contain recognition errors, or be absent. Agreement is therefore only label equality, not proof of visual correctness, and disagreement is not ground truth.

Privacy and provenance controls:

- aligned transcript text, text-model requests, raw responses, normalized private predictions, error detail, and per-clip receipts remain under `data/private`;
- the HTTP client accepts only a prevalidated loopback endpoint, disables environment proxies, and rejects redirects instead of forwarding ASR-bearing requests;
- clip IDs must be opaque single path components, and every resolved per-clip directory is checked to remain inside the private output root;
- the public summary contains opaque clip IDs, normalized labels, relations, counts, metrics, and hashes, but no transcript text or private/absolute paths;
- the redacted public summary is refused if its target is inside `data/private` or is the same file—including a hard-link alias—as either bound input; the bound-input hashes are checked again after output writes;
- a pre-commentary seal binds the exact clip manifest and exact visual-summary bytes before any transcript is opened, and both files are re-hashed after the run;
- every requested manifest clip is accounted for. Missing visual predictions and text-model failures are reported as not evaluated, rather than excluded from the requested-set denominator;
- the requested set must be non-empty and every bound clip must have a finite duration from 5 through 10 seconds;
- the exact text-model configuration is persisted privately so its canonical and file hashes can be independently recomputed;
- a response is rejected if the loopback server's reported model identity does not exactly match the requested model;
- per-clip receipts bind the model, prompt, persisted configuration, visual entry, aligned transcript, projected segment evidence, request, response, and normalized prediction by SHA-256.

Example command after a visual result is frozen:

```powershell
.\.venv-soccernet\Scripts\python.exe prototype\run_commentary_crosscheck.py `
  --manifest data\private\soccernet-derived\<split>-game-000-v2-manifest.json `
  --visual-summary artifacts\soccernet-pilot-v1\<sealed-visual-summary>.json `
  --private-out data\private\commentary-runs\<run-id> `
  --summary artifacts\soccernet-pilot-v1\<run-id>-commentary-summary.json `
  --model <loaded-text-model-id>
```

Do not run the validation split until the visual model, prompt, frame-sampling configuration, and output contract are frozen. The commentary stage is always downstream of that frozen visual run.
