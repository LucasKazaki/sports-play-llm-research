# Independent v2 memory qualification review

Verdict: GO for the bounded root-only memory qualification, not a full pilot or chess capability claim. Complete source, meaningful tests and protocol were read in two finite bundles below 30,000 bytes each. No model, GPU or real engine calls were performed by this reviewer.

- Runtime v2: `7f28693ae26c82575539c603783fc37c0a35a6fcf43e281b99fe02dc6d105349`
- Qualification v1: `8da53d0f3efa64659324c23a284bdfaa9d919542269ea17a4327a0d1a13402c1`
- Memory protocol: `418e4b13fed39d821b30ebc7b44a4b1ccc1da4661eb4e5b202688d975ec2fc69`
- Runtime tests: `d5fce78a9fc7ed58db393e44338c0d943687520ef0226635504b9862c328c99d`
- Qualification tests: `6c2ff599844a0ff8d807ff58eef4b9a213b440233b55e51bb8adb0f334dc352a`

Independent 29 CPU checks passed in 0.30 seconds across the new runtime/qualification and retained trainer/evaluator test files. The owner's 31-check total additionally includes two previous-runtime tests. Actual metadata-only `verify_plan` passes without Torch, bitsandbytes or PEFT import. The current-process Windows PrivateUsage API works in the CPU test. An AST comparison confirms the numerical loss/backward body equals executed v1.

The additive runtime exposes cleanup only after returned work, with synchronization, fsynced before/after memory records, Python collection and CUDA inactive-cache release. It never explicitly changes live tensors, accumulated gradients, optimizer parameters, conditioning or objective. Actual qualification must prove live preservation by hashing all trainable tensors and all 144 gradients immediately before/after cleanup at two specified boundaries, rather than relying on the stub sequencing test alone. Complete frozen storage must still hash identically.

The predeclared qualification reuses one already-spent development request and requires an actual 1,024-token prefix, then exactly 32 optimizer updates/256 TRAIN micros using the original order, accumulation and learning-rate schedule. All future micro/optimizer rows and the generation row are retained before model setup. Inflight failures become active unknown; remaining calls stay not-run. Failure stops further calls. Original 4 GiB physical/commit and 1 GiB GPU floors, 900-second qualification budget and 13:00 UTC cutoff remain. The failed v1 bytes and its step21/micro0 unknown are explicitly bound; no hidden resume is performed.

Acceptance requires the fixed budget, finite gradients, changed LoRA, full frozen equality, live preservation, resource guards and the declared last-eight-boundary spans. The 512 MiB process / 256 MiB CUDA span criterion is a bounded stability observation; it cannot guarantee the full 256-update pilot or establish a causal diagnosis. The root's owned CPU-server maintenance is part of the combined operational condition. Qualification adapter weights are discarded, held references remain unopened, and a full v2 trainer requires a separate protocol/review after actual qualification.

No remaining blocking source/protocol defect found.
