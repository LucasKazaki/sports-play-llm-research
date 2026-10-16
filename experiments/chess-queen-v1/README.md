# Queen native Windows candidate

Current runtime status: full-prefix native/manual parity is exact on the authored
fixture, but the first completed cache comparison failed the frozen numerical
limits. Cached generation is unqualified. The separately recorded v5 precision
probe and canonical uncached prefix check are prepared; their future receipts,
then a complete authored response with measured latency, determine usability.

This lane investigates a chess encoder plus language decoder, which directly
addresses the project's need for stronger chess explanations. The authors of
[Queen](https://arxiv.org/abs/2610.03695) report a 4B chess-language model, trained
with LC0 board representations and iterative explanation distillation. Their
reported playing strength and language-model-based coherence scores are external
results, not measurements of this local candidate or evidence of tutor quality.

The official [PAWN-8 model card](https://huggingface.co/princeton-nlp/queen_pawn-8)
uses Linux, CUDA 13 and vLLM and validates an H100 80GB. It explicitly leaves smaller
GPUs unvalidated. The pinned project code also includes pure Torch cross-attention
and encoder implementations. That makes a native Windows port plausible without
upgrading the existing environment. The validation below was prepared before
pretrained or GPU execution; later versioned receipts establish actual runs.

Pinned identities:

- Model: `princeton-nlp/queen_pawn-8` at
  `5027687fac08b64b2403b13aca5b198e68294fe9`.
- Source: [queen-project/queen](https://github.com/queen-project/queen) at
  `c372da22ca75e95c3c79bee8a83c220fc54d0dcb`.
- Local weight root: `data/private/chess-queen-v1/pawn-8`.
- Acquisition receipt: `data/private/chess-queen-v1/acquisition.json`.
- `asset-manifest.json` binds 30 publisher files, totaling 9,001,130,570 bytes.
  `source-manifest.json` binds the exact local modules that may execute.

The native adapter keeps the full merged SmolLM3 vocabulary and injects the
pinned `DenseXAttn` modules before layers 0, 2, …, 30. Stock Transformers handles
causal masking and positional embeddings. Generation explicitly selects cached
continuation or canonical full-prefix recomputation with no cache. Each
request's encoder states are closed over by temporary hooks, removed in
`finally`. No prefix cache is shared between boards. The decoder alone would
omit the chess expert; that path is never presented as Queen.

Approximate parameter storage is 6.15 GB for the BF16 decoder, 0.94 GB for BF16 bridges
and 0.48 GB for the BF16 encoder. A 16 GB GPU is therefore plausible for one request,
but actual peak memory, compatibility and latency must be measured. CPU import,
parsing and preflight do not load models. Full CPU inference is an experimental
option, not an upstream-supported fast path.

Only current FEN, legally consecutive prior FENs and an optional selected legal
move enter the adapter. Extra fields such as PV, solution, future boards, engine
evidence and annotations are rejected before model loading. Missing game history
is disclosed: the upstream encoder synthesizes missing history planes from the
current FEN. Fixed prompts contain no continuation or answer labels.

Raw structured `BEST_MOVE` and `CRITICAL_LINE` are retained. Move legality and
capture/piece description validity are distinct. The adapter neither defaults an
unspecified promotion to a queen nor uses the publisher's random-legal fallback.
Illegal, malformed and missing moves remain visible. Generated prose is
unverified model output; a legal continuation alone does not validate its claims.

Private local acquisition is authorized. Queen's source is Apache-2.0 and its
SmolLM3 base declares Apache-2.0. The publisher explicitly gives no blanket license
for the combined release and says upstream LC0 component terms apply. The
[LC0 engine source](https://github.com/LeelaChessZero/lc0) is GPL-3.0-or-later; that
does not establish an independent permissive license for the converted network.
Retain component notices and make no permissive-license or redistribution claim
for the combined weights. No account, payment, access gate or terms acceptance
was used.

Validation completed before pretrained execution:

- 33 CPU contract tests pass: no-forward field rejection, real prior-state replay,
  black POV mapping, special moves, raw illegality, first-error stopping, file
  hashes, hook placement and hook cleanup, duplicate-section rejection, process
  lease exclusion, owned-child timeout cleanup, interrupted-parent startup-gate
  cleanup, throttled resource sampling, meta-only module construction, exact
  target-dtype weight copies and integer-buffer preservation.
- `cpu-parity.json`: a tiny random CPU SmolLM3 matches the upstream manual
  Flamingo path exactly; its cached and uncached next logits agree within
  approximately 1e-7. This test uses no pretrained weights or CUDA.
- Full file preflight verifies every model asset and executed source module.

The first actual `parity_pretrained_v2.py` attempt stopped before any forward
when the unchanged commit reserve guard fired after decoder and bridge loading.
That failed attempt and its resource samples remain retained. The observed
headroom was about 5.52 GB against the required 6 GiB; no GPU out-of-memory
exception occurred. This was a loading failure, not a chess result.

The memory repair constructs bridge and encoder tensors on the meta device,
sets the target floating dtype there, then allocates only target storage and
strictly copies the pinned mapped weights. It avoids a full CPU FP32 random
bridge allocation. The audited LC0 class stores its weights as buffers; a tiny
local CPU check found that this Transformers release's dtype argument alone
leaves those buffers FP32. Its direct strict safetensors copy now preserves
integer buffers and allocates floating buffers in the requested format.
`cpu-parity-memory-v2.json` verifies the repaired bridge loader against the
upstream manual path with tiny random CPU weights: maximum error zero and
cached versus uncached error approximately 2.1e-7. No pretrained or GPU forward
was used for that check. Actual resource improvement still requires measurement.

The second actual attempt loaded the decoder, bridges and encoder, then stopped
before any forward with 6,440,951,808 bytes commit headroom, only 1,499,136 bytes
below the former 6 GiB reserve. The separately versioned
`parity_pretrained_v3.py` records both failed receipts by hash and the authorized
5 GiB running commit reserve. Start reserves and the 4 GiB physical/1 GiB GPU
running reserves are unchanged. The short-lived Queen inference child uses the
same 5 GiB running commit reserve and records its full policy. The worker's
process lease and startup/cleanup behavior are unchanged. This amendment uses
the observed loading footprint; activation and cache pressure still need to be
measured. Any actual memory-pressure failure requires investigation before a
new attempt.

The third actual attempt completed the encoder and both decoder paths: finite
conditioning shape `[1,16,64,1024]`, manual/native hook maximum error zero, cosine
one and identical top token. This establishes one numerical path comparison,
not chess ability. The reserve guard then stopped the run before the three cache
comparisons. Post-forward headroom was 5,168,066,560 bytes (about 4.81 GiB), with
10.89 GB physical and 6.92 GB GPU free; no OOM occurred.

`parity_pretrained_v4.py` records all three failed receipts, the observed exact
hook match and the final authorized 4 GiB inference-only commit floor. All
numerical checks and other resource limits remain unchanged, and the short-lived
Queen child uses the same floor. This leaves about 0.81 GiB beyond that observed
post-forward footprint. A real OOM or more than 1 GiB of further kernel growth
requires a memory or quantization fix, with no further reserve reduction. The
probe uses no optimizer and only three cache steps.

The fourth actual attempt fit memory and completed all three cache steps, but
failed the unchanged numerical limits. Cache step one had maximum error 0.546875,
mean error 0.086814 and cosine 0.999259; all three top tokens agreed. Full-prefix
native/manual logits remained exactly equal. This is a failed cache check.

A possible cause is shape-dependent BF16 arithmetic and automatic attention
kernel selection, not a demonstrated cache-index bug. PyTorch documents
[differences between attention backends](https://docs.pytorch.org/docs/2.8/generated/torch.nn.functional.scaled_dot_product_attention.html)
and [BF16 reduction and batched-computation effects](https://docs.pytorch.org/docs/2.8/notes/numerical_accuracy.html).
This is a diagnosis to test, not an established explanation for this model.

`parity_pretrained_v5.py` applies one scoped math-SDPA profile with BF16 reduced
GEMM reductions, TF32 and reduced-precision math-SDPA intermediates disabled.
It uses the same profile for encoder, upstream manual, native full-prefix and
cache paths, then restores settings on exit. All numerical limits and the final
4 GiB reserve are unchanged. It separately predeclares three native/manual
full-prefix comparisons. A canonical uncached component can pass while cache
parity remains failed; overall cache validation is never rescued by that result.
An optional root-only `precision_probe_gpu.py` uses tiny random BF16 weights to
test the two execution profiles without loading pretrained Queen. Neither probe
was run by the implementation lane.

The adapter's default candidate is explicit `no_cache` with the math profile.
Its recorded backend, cache flag, raw tokens, finish reason and measured token
latency describe that mode. Production use still requires the corresponding
actual numerical and authored-output checks. Selected-move provenance says that
a move was supplied, without incorrectly asserting that no engine-selected move
could have been given by an evaluator.

The next required check is `parity_pretrained_v5.py` on one authored board fixture.
It compares native hook execution with upstream manual Flamingo and compares
cached with uncached next-token logits over three steps, including a synthetic
Queen-vocabulary suffix in the compared prefix. Its tolerances are saved before
execution. Every attempted preflight retains a receipt, including setup errors.
The older v1 probe remains preserved but is not the selected first test.

`gpu_worker.py` holds the shared `data/private/chess-gpu-owner.lock` through a
short-lived child process's exit. On Windows an owned job object kills the child
tree if its wrapper dies. The same wrapper can serialize existing project
trainers without editing their frozen source. A busy lease starts no model.
The child waits for an exact start signal on its parent-owned stdin pipe before
importing the target. The parent sends that signal only after job assignment;
parent death before assignment closes the pipe and the child exits without
loading a model. The bootstrap preserves the target script's argument and
module-search entry points and runs it in the same protected process.
The Queen child checks cancellation every token and samples resource counters
at most once a second. Source-import preflight and CPU tests need no GPU lease.
Current training that started outside the lease must finish before the first
Queen worker is launched by the root.

The three FEN-only authored cases (mate opportunity, middle game, opening) and
one selected-move variant are frozen in `authored-smoke-protocol.json`. They use
1024 new tokens, greedy decoding and a 240-second budget. Raw output tokens,
failure and truncation stay visible. These cases are software demonstrations,
not a held-out capability set. A smaller token cap may end before the model's
`BEST_MOVE` section; a move-only prompt needs separate measurement.

Full retained component notices and their provenance are in
`data/private/chess-queen-v1/notices/`. The model card's missing combined license
is recorded without inventing a license for the converted network or weights.

Example commands from the repository root:

```powershell
& .\.venv-soccernet\Scripts\python.exe scripts/chess_queen_adapter.py --preflight
& .\.venv-soccernet\Scripts\python.exe -m pytest tests/test_chess_queen_adapter.py -q
# Run only when the root has granted exclusive GPU ownership:
& .\.venv-soccernet\Scripts\python.exe experiments/chess-queen-v1/gpu_worker.py --receipt data/private/chess-queen-v1/workers/parity-v5-worker-1.json --maximum-seconds 300 -- experiments/chess-queen-v1/parity_pretrained_v5.py --device cuda --out data/private/chess-queen-v1/parity-authored-v5-1.json
# After parity passes, one short-lived authored inference worker:
& .\.venv-soccernet\Scripts\python.exe experiments/chess-queen-v1/gpu_worker.py --input experiments/chess-queen-v1/authored-opening.json --out data/private/chess-queen-v1/authored-opening-1.json --max-tokens 1024 --maximum-seconds 240 --generation-mode no_cache --precision-profile math_sdpa_fp32_reduction
```

After parity passes, bounded authored examples can test output completeness,
raw legality and explanation failures. A predeclared fresh game-disjoint cohort
is still needed for capability measurement. Engine evaluation belongs after
generation and never enters the model's input. No public UI change, automatic
model promotion, professional-coaching claim or paper-strength reproduction is
implied by this integration candidate.
