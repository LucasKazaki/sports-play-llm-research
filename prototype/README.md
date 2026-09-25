# Prototype

`SportsPlayLLMLab` is a deliberately small, model-agnostic evaluation scaffold.

## Current verified path: real video, VLM-only classification

1. Acquire an explicitly authorized SoccerNet match half into `data/private` and write a credential-free hash receipt.
2. Prove the match identity against SoccerDB's immutable public mapping.
3. Extract hash-bound 10-second event windows twice: physically silent VLM inputs and local-review copies with commentary.
4. Uniformly sample 12 full-resolution frames. This is evidence packaging, not a hand-engineered play classifier.
5. Send only those frames to a loopback `google/gemma-4-e4b` VLM under a strict 17-class SoccerNet taxonomy plus background and abstention.
6. Fail closed on malformed output or serving failure; every requested clip remains in the accuracy denominator.
7. Seal the visual summary before opening aligned SoccerNet-Echoes ASR.
8. Run a separate text-only commentary classifier and record only `supports`, `contradicts`, or `uninformative`; it cannot change the visual output.
9. Render the frozen results in an offline private demo with silent-first playback, separate commentary, and hidden ground truth.

The exact commands, immutable hashes, failure history, and presentation sequence are recorded in `research/soccernet-real-footage-pilot-2026-08-27.md`.

## Important limitation

The real pilot contains only 11 clips from two matches and only 6 clips in one held-out match. It is descriptive systems evidence, not a benchmark estimate. The old synthetic harness remains a regression fixture only and is not part of the live demo or reported model results.

## Real-video LLM-only path

`real_clip_vlm.py` is the separate path for a locally authorized real soccer clip. It performs no hand-engineered play classification: it uniformly samples and hashes frames, builds chronological contact sheets, sends them to a loopback-only VLM, validates the returned play type against a fixed taxonomy, and writes an input manifest, raw response, normalized prediction, and receipt.

```bash
python prototype/real_clip_vlm.py \
  --video PATH_TO_AUTHORIZED_CLIP \
  --clip-id CANONICAL_CLIP_ID \
  --source-reference PROVIDER_REFERENCE \
  --source-manifest PATH_TO_NON_SECRET_MANIFEST \
  --out artifacts/real-clip-vlm-run
```

For SoccerDB, `PATH_TO_AUTHORIZED_CLIP` and its manifest may be supplied only after the provider's credential, terms, acquisition-method, and clip-processing gates have been verified. The runner never authenticates, downloads media, or treats one unadjudicated response as a performance result.

## Next implementation steps

- Add more match-grouped SoccerDB/SoccerNet overlap games before any performance comparison.
- Compare the already installed, vision-capable Qwen3.5-9B under a separate frozen receipt after deliberately stopping only the owned Gemma runtime; do not disturb the unrelated second-GPU service.
- Evaluate native temporal video input against the current 12-frame evidence package.
- Double-annotate event-window visibility and temporal evidence; SoccerNet-v2 point labels alone do not adjudicate everything visible in a 10-second window.
- Add separately scored natural-language QA, retrieval, and pitch-coordinate/trajectory evidence rather than claiming they already exist.
- Consider soccer parameter-efficient weight adaptation only after the baseline data and evaluation protocol are large enough; the present soccer path performs no weight training.

## American-football trained pilot

`footballmaster_pilot.py` is a separate, rights-gated American-football path. Unlike the soccer VLM evaluation path, it does persist fitted parameters: frozen ONNX MobileNetV2 frame scores feed fixed temporal pooling, train-only PCA, and an eight-parameter binary softmax head for `is_touchdown`. Fine event tags remain weak source metadata, not model outputs.

The final nine-clip source-held-out run, checkpoint, search index, metrics, hashes, failure case, commands, and claim boundary are documented in `research/footballmaster-pilot-model-2026-08-27.md`. This is a tiny descriptive pilot—not SoccerMaster-scale pretraining, a foundation model, calibrated confidence, fine-grained football understanding, or coach validation.

## Dual-sport coach-search server

`multisport_search_demo_server.py` packages the seal-verified SoccerMaster full-match index and the hash-verified FootballMaster package behind one loopback-only UI. Soccer is loaded through the independent `soccer_longform_adapter.py`; the shared server does not import football logic into the soccer engine. The interface has sport-specific query ontologies, safe byte-range media routes, receipt checks, and explicit per-field attribution. The query LLM receives only the coach sentence and selected sport ontology; it never receives video, audio, labels, saved predictions, or post-hoc evaluation data.

The primary soccer package contains 90 contiguous 60-second windows spanning both complete halves plus six fixed 30/60/120-second stress windows. It is **SYSTEMS GO / SEMANTIC NO-GO**: all 96 test calls produced valid structured output, but post-seal restricted corroboration was only 3/166 mapped annotations and 3/54 mapped predictions, while direct visual review found 0/6 fully supported sampled reports. The server displays those limits. If the verified package fails closed, the historical SQLite demo is exposed only as an explicit legacy fallback.

```powershell
& .\.venv-soccernet\Scripts\python.exe .\prototype\multisport_search_demo_server.py --port 8771
```

Then open `http://127.0.0.1:8771/`, or double-click `START_DUAL_SPORT_DEMO.cmd` from the project root. The API exposes `GET /api/sports`, `GET /api/status?sport=soccer|football`, and `POST /api/search` with `{"sport":"football","query":"Show the SMU Louisville touchdown pass"}`.

For deterministic UI QA without a query-model request, add `--literal-query-fallback`, or run `scripts/start-coach-search-ui.ps1 -LiteralQueryFallback`. Literal mode changes query parsing only; it does not change the sealed VLM reports or ranking corpus.

## Hosted-video benchmark harness (offline-first)

`hosted_video_benchmark.py` adds the bounded P0 experiment requested for a substantially stronger Gemini video model. It does not weaken the current local-only SoccerNet policy: a hosted run fails before provider invocation unless every input clip explicitly permits third-party processing by `google_gemini`, the video is physically silent, a Gemini credential is present only in the runtime environment, the manifest says `zero_spend_only`, and the caller deliberately supplies both `--execute-remote` and `--confirm-zero-spend` after verifying the current account/model route cannot incur paid usage.

The frozen contract is split into `coach-event-report.prompt.txt` and `coach-event-report.schema.json`. The report can contain multiple detailed events with actor evidence, ball action, possession, pitch regions, ordered action sequence, tactical intent, coach relevance, timestamped observations, replay state, alternatives, uncertainty, and abstention. Raw replies, parse failures, model/version, latency, input hashes, and deterministic resume state remain under `data/private`.

Use `--dry-run` to validate media, hashes, rights declarations, prompt/schema hashes, and the credential-presence gate without inference. Use `--provider mock --mock-responses PATH` to exercise the full parser/seal/resume path locally. Held-out labels and commentary are opened only with `--open-held-out`, after `primary-seal.json` exists; commentary remains auxiliary and cannot revise the sealed visual result.

See `research/gemini-video-benchmark-protocol-2026-08-27.md` for the exact manifest contract and safe commands. No Gemini result has been produced by adding this harness; the presentation boundary remains **SYSTEMS GO / SEMANTIC NO-GO**.
