# Strong hosted-video VLM protocol — Gemini-ready, no run claimed

**Status:** executor and receipt path implemented; actual hosted inference remains gated.  
**Truth boundary:** **SYSTEMS GO / SEMANTIC NO-GO.**  
**Primary condition:** physically silent video only.  
**Cost policy:** zero spend only.

## What now exists

`prototype/hosted_video_benchmark.py` is a provider-neutral runner with two adapters:

- `FixtureVideoProvider` exercises the entire request-receipt, raw-response, strict-parse, primary-seal, resume, and post-hoc path locally.
- `GeminiVideoProvider` uses native video through the Google Gen AI SDK only after the runner completes every pre-upload gate. The requested and provider-reported model versions are both retained.

The frozen model contract is:

- `prototype/coach-event-report.prompt.txt`
- `prototype/coach-event-report.schema.json`

The schema returns zero or more detailed event cards rather than one class. Each card records event type/subtype, start/peak/end, phase and restart context, evidence-qualified participants, ball action, inferred possession with visibility limits, pitch origin/destination, movement direction, ordered action sequence, tactical intent, outcome, coaching relevance, timestamped visible evidence, broadcast/replay state, alternatives, uncertainty, confidence, and event-level abstention.

## Manifest contract

The runner accepts one immutable JSON manifest. A development manifest may contain 1–15 clips; a benchmark manifest must contain 6–15, preserving Archit's six-minimum and 10–15-target protocol.

```json
{
  "schema_version": "playground-hosted-video-benchmark-input-v1",
  "study_id": "opaque-study-id",
  "protocol_phase": "development",
  "video_condition": "physically_silent_video_only",
  "cost_policy": "zero_spend_only",
  "clips": [
    {
      "clip_id": "opaque-clip-01",
      "video_path": "relative/or/absolute/silent.mp4",
      "sha256": "64-lowercase-hex-characters",
      "mime_type": "video/mp4",
      "rights": {
        "third_party_processing_permitted": false,
        "approved_processors": [],
        "rights_record_id": "durable-rights-record-id",
        "decision_date": "YYYY-MM-DD"
      },
      "held_out": {
        "labels_path": "held-out-labels.json",
        "commentary_path": "auxiliary-commentary.json"
      }
    }
  ]
}
```

Credentials are forbidden in this file. For a Gemini run, every clip must instead set `third_party_processing_permitted` to `true` and include `google_gemini` in `approved_processors`, backed by the named rights record. Private SoccerNet/NDA footage does not meet that gate and must remain local.

## Safe execution sequence

1. Validate a candidate manifest without inference:

   ```powershell
   .venv-soccernet\Scripts\python.exe prototype\hosted_video_benchmark.py `
     --manifest PATH_TO_RIGHTS_MANIFEST.json `
     --private-out data\private\gemini-benchmark\preflight `
     --provider gemini --model gemini-3.7-flash --dry-run
   ```

2. Exercise the full software path with local frozen responses:

   ```powershell
   .venv-soccernet\Scripts\python.exe prototype\hosted_video_benchmark.py `
     --manifest PATH_TO_DEVELOPMENT_MANIFEST.json `
     --private-out data\private\gemini-benchmark\mock-run `
     --provider mock --model offline-rich-report-fixture `
     --mock-responses PATH_TO_MOCK_RESPONSES.json --open-held-out
   ```

3. Only after a rights-safe 6–15-clip manifest exists, the exact Gemini endpoint is confirmed free for the account, and a runtime credential is present, use `--provider gemini --execute-remote --confirm-zero-spend`. The runner reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` only at runtime and stores only the environment-variable name and a boolean presence flag. It never stores the value. The extra confirmation is a fail-closed guard; it is not evidence by itself that a provider account is on a free route.

The default model name is the current candidate recorded in the 2026-08-27 technical brief. Because hosted catalogs change, the actual run must preserve the requested ID, returned model version, SDK version, date, and terminal error; a renamed/unavailable endpoint is an explicit result, not permission to silently substitute a model.

## Receipt and separation guarantees

Before any provider call, the runner validates the complete batch:

1. manifest schema and absence of secret-shaped keys;
2. source-file SHA-256;
3. a real ffmpeg stream probe showing at least one video stream and exactly zero audio streams;
4. `zero_spend_only` policy;
5. explicit per-clip third-party rights and selected-processor approval;
6. runtime credential presence and deliberate remote-execution opt-in.

The private run tree contains:

- `run-manifest.json` — deterministic run fingerprint, sorted clip order, runner/prompt/schema hashes, terminal clip states, and resume pointers;
- per clip: `request-receipt.json`, `raw-response.json`, `event-report.json` or `parse-failure.json`/`provider-failure.json`, and `result.json`;
- `primary-seal.json` — hashes every primary artifact before held-out material opens;
- optional `posthoc-audit.json` — hash-bound labels plus commentary, clearly marked auxiliary and unable to modify the primary record.

Malformed JSON is never repaired silently. Parse failures retain the redacted raw response and are terminal/resumable. Provider failures retain a credential-scrubbed error receipt and may be retried. The primary seal includes every requested clip, including failures.

## Claims this does not support

- No Gemini request or performance result was produced while implementing or testing the harness.
- No private SoccerNet video is approved for Gemini upload.
- A valid JSON report is not evidence of correct soccer semantics.
- Model confidence remains an uncalibrated self-report.
- Commentary is not ground truth.
- Six to fifteen clips are protocol debugging and failure discovery, not a population estimate.
