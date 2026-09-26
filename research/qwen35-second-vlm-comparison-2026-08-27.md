# Qwen3.5-9B second-VLM comparison

## Overall assessment: Share with caveats

The second local true-vision model is useful for the Archit demo as a hypothesis-generating comparison, but not as a publication-grade performance estimate. Qwen completed all six held-out silent clips and improved allowed-label accuracy from Gemma's 0/6 to 3/6. That improvement is real for these saved runs, but the sample is tiny, the second model was selected post hoc, and Qwen required different frame grouping to fit the fixed context.

## Method

- Model: Qwen3.5-9B Q4_K_M with its matching BF16 `qwen3vl_merger` projector.
- Runtime: the same hash-pinned llama.cpp build 10566 on CUDA0, context 8192, parallelism 1, no API key, and loopback-only serving.
- Evidence: the exact same source video hashes and 12 decoded frame records as the Gemma recovery run for every validation clip.
- Difference: Qwen received those 12 frames in six 1280×360 two-frame sheets. Twelve separate images required 11,629 prompt tokens and exceeded the 8,192-token context. Gemma had received 12 1280×720 one-frame sheets.
- Output: the same fixed SoccerNet-derived taxonomy, strict JSON schema, abstention contract, and requested-set scoring.
- Leakage control: the six visual outputs were hash-sealed before any Qwen validation commentary was opened. No commentary was subsequently processed for this comparison.

## Results

| Metric | Gemma E4B recovery | Qwen3.5-9B |
|---|---:|---:|
| Requested / completed | 6 / 6 | 6 / 6 |
| First-pass schema-valid | 100% | 100% |
| Allowed-label accuracy | 0 / 6 (0%) | 3 / 6 (50%) |
| Exact accuracy on single-label clips | 0 / 2 (0%) | 1 / 2 (50%) |
| Median completed latency | 9,306 ms | 9,992.5 ms |

Qwen correctly identified the corner, goal, and yellow-card clips. It misread a shot off target as a goal, a foul as a shot on target, and a direct free kick as a penalty kick. Every answer had confidence between 0.90 and 0.95, including all three errors, and the model never abstained. That is an important calibration failure, not merely a lower accuracy score.

## Calculation validation

The headline numbers were recomputed directly from each private prediction and the immutable validation manifest. Counts, denominators, schema validity, allowed-label accuracy, exact accuracy, and median latency all match the saved summary. Prediction, clip, manifest, model, and runtime hash bindings pass for all six clips.

A separate read-only verifier compared all 72 frame records field by field, reran the metric calculations, checked every receipt/config/summary/seal cross-link, confirmed Gemma's nine live checks and the protected GPU1 service, and ran the full repository suite: 162 tests passed.

## Required caveats for Archit

- This is six clips, not a benchmark-scale estimate.
- Qwen was selected after the Gemma validation result was known, so the comparison is post hoc.
- The decoded frames match exactly, but their image grouping differs because of Qwen's vision-token cost.
- High-confidence mistakes and zero abstentions show that reliability remains unsolved.
- No weights were trained or fine-tuned; this is local zero-shot inference over sampled video frames.

The strongest honest conclusion is: a second VLM can extract more soccer-event signal from the same real footage than this Gemma configuration did, but neither model is yet reliable enough for unattended play labeling.
