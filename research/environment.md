# Local Prototype Environment (observed 2026-08-06)

Command-derived state from Lucas's current Windows host:

- OS: Microsoft Windows 11 Pro, build 26200, x64
- Python: 3.11.15
- FFmpeg: 8.1.2 full build
- RAM: 64,681 MB total; 34,326 MB available at check time
- GPUs:
  - NVIDIA GeForce RTX 3070 — 8,192 MiB
  - NVIDIA GeForce GTX 1080 — 8,192 MiB
  - driver 560.94
- Python packages present: OpenCV (`cv2`), NumPy, pytest, requests, Pydantic
- Ollama: no executable found / no service responding on `127.0.0.1:11434`

## Practical consequence
The machine is suitable for video preprocessing, classical CV/tracking, evaluation, and many 7B-class quantized/open VLM experiments with careful memory management. It is not suitable for naïve full-precision training of large video VLMs. Prefer parameter-efficient tuning, short clips/frame sampling, offloading, or lab/cloud GPUs. Do not assume the two GPUs can be pooled transparently.

## Verified local VLM runtime — 2026-08-27

The real-footage pilot uses a directly owned, loopback-only `llama.cpp` server rather than the shared model-manager API. The public-safe runtime receipt is `artifacts/soccernet-pilot-v1/isolated-vlm-runtime-receipt-v1.json`.

- backend: `llama.cpp` 0.2.0-dev, build 10566, commit `bb4caa754`;
- model: `google/gemma-4-e4b`, Q4_K_M GGUF with the matching BF16 multimodal projector;
- device: RTX 3070 (`CUDA0`), all model layers offloaded, no GPU split;
- context: 8,192 tokens; one parallel slot; fixed batch/KV/reasoning settings;
- web UI disabled, no API key configured, environment `LLAMA_*` overrides removed;
- lifecycle checks: Bionic server suspended, other Bionic models unloaded, PID/port/process-image hashes matched, `/health` passed, and `/v1/models` exposed exactly one expected model.

The untouched primary pass ran before this isolation and suffered three timeouts. After isolation, the same six-clip serving-recovery rerun completed 6/6 at a 9.306 s median latency. Because it reuses the same validation clips after a runtime diagnosis, it is a post-hoc reliability result, not a second independent estimate of model accuracy.

## Prepared second-VLM comparison

A complete local `qwen/qwen3.5-9b` Q4_K_M vision model and matching BF16 multimodal projector were verified on disk. Their combined static size is 6.099 GiB, and the pinned llama.cpp build exposes the required Qwen3.5/Qwen3-VL multimodal support. It is the strongest credible second model for one 8 GiB card on this host.

It was deliberately not launched during the final demo handoff: CUDA0 is occupied by the verified Gemma runtime, while CUDA1 belongs to an unrelated live service. A concurrent run would either invalidate the isolated-runtime guarantee or disturb out-of-scope work. The next comparison should deliberately stop only the owned Gemma process, start Qwen on CUDA0 with a new receipt and frozen configuration, run the identical silent clips and scoring contract, then restore the Archit demo runtime. The Qwen run would be a post-hoc model comparison on the same clips, not another independent estimate.
