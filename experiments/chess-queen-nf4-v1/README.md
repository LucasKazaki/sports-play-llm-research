# Queen decoder NF4 candidate

The local candidate now completes real chess-language requests on the RTX 5080. Its four authored qualification examples produce legal structured moves and legal main lines. The explanations still contain false claims, so this is a research runtime and tutor-feedback candidate. It has no accepted coaching-quality or playing-strength result.

The model uses Princeton's Queen PAWN-8 with a separately versioned compressed decoder. Its 252 attention and MLP linear layers use nested NF4 with BF16 compute. The full tied 128,333-token vocabulary, frozen LC0 board encoder and 16 cross-attention bridges remain BF16 on CUDA 0. Every actual registered tensor must be on that device. Inference uses the deterministic no-cache path with math attention and full-precision reductions; cached inference remains disabled after its earlier numerical failure.

## Actual qualification results

- The two tiny CUDA kernel diagnostics pass their frozen limits. The second reports a maximum forward error of 0.015625, relative L2 error of 0.00384652, and zero input-gradient error against the same dequantized weights.
- The first complete-model parity attempt fails before any forward because Transformers 5 omits optional device-map metadata. Its source and failed receipt are retained. The separately named v2 adapter requires the actual tensor inventory, tolerates absent optional metadata, and rejects any present offloading or malformed map.
- The second complete-model parity attempt passes all six comparisons: two complete prefixes over the full, original and added vocabulary partitions. Maximum and mean logit errors are zero; minimum cosine similarity is 0.99999988 and top choices match. Peak allocation is 3,471,615,488 bytes. This compares two calculations using the same quantized weights; it establishes no equivalence to the original BF16 weights or chess strength.
- All four predeclared authored generation cases complete to EOS. Their structured raw choices are legal, with main lines of one, three, ten and eleven legal plies. The fourth case supplies c3 for explanation, so following it is not an independent prediction. The mate case chooses Qd8#, but also gives an illegal side variation and a false protection claim. Other responses include false material and bishop-pair claims.

The exact raw responses, closed workers and resource journals are under `evidence/`, including the failed first parity attempt. Their byte hashes are in `evidence-manifest.json`. Independent readback reproduces the token decoding, prompt/input scopes, structured parsing, full main-line legal replay and closed-worker state. These are software integration examples, not a fresh accuracy benchmark.

## Reproducibility and limits

The original BF16 adapter, every executed source generation and each frozen protocol remain intact. The current software sources and tests bind their exact dependencies. No random legal fallback, engine replacement, automatic retry, CPU/disk offload or reduction of the 4 GiB commit reserve is used. The root alone dispatches GPU calls through the shared lease and owned Windows worker. The current v2 software set passes 40 CPU contracts; both retained source generations together pass 74.

The official bitsandbytes 0.50.2 Windows wheel has SHA256 `c697963c8fda3dcd0d7ebd9b5211ae4067feef7cd06e0350d4e816a434fe683d`; all 65 installed wheel files were verified. No other package was changed. Its MIT notice and Queen component notices remain private with acquisition receipts. No weights or creator media are redistributed. See the [official installation documentation](https://huggingface.co/docs/bitsandbytes/v0.50.2/en/installation) and [Transformers configuration](https://huggingface.co/docs/transformers/v5.19.0/quantization/bitsandbytes).

A separate coaching fine-tune follows under `chess-queen-coach-sft-training-v1`. This qualification does not promote its eventual weights automatically.
