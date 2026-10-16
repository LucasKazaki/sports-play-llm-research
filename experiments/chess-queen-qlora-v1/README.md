# Authored Queen QLoRA diagnostic

A real local gradient update now succeeds on the compressed Queen decoder. This establishes training feasibility on this machine; it says nothing about unseen-game understanding or coaching quality. The one-update diagnostic adapter is discarded before the separate corpus pilot.

PEFT injects rank-8 q/v LoRA with 1,916,928 FP32 trainable parameters. The original decoder object runs through Queen's official manual Flamingo implementation. Nonreentrant checkpoints include the frozen BF16 cross-attention bridges, allowing gradients to pass through them. Only the frozen current-position encoder runs without gradient recording. The full tied BF16 vocabulary remains intact. The generic PEFT preparation helper is avoided because it would upcast large frozen parameters.

Training supervises the complete assistant response and closing token with full 128,333-vocabulary cross entropy, the pinned official chat template, and chunked loss. The model input contains the current board and native question. It receives no engine continuation, future board or target facts.

## Actual attempts

The first attempt fails before any forward or update because Transformers 5's default chat-template return value differs from the expected token-ID list. Its executed source, protocol and failure receipt remain unchanged. Separately named v2 forces token-ID output through a compatibility proxy while retaining the official formatter, and hashes raw tensor subclasses without invoking their relocation override.

The second attempt passes all eight checks and completes one optimizer update. Loss is 1.813796877861023. All 144 adapter gradients are finite, 72 are nonzero, and adapter storage changes. All 2,268 frozen tensors, totaling 3,393,484,936 bytes, hash identically before and after, including nested quantization scales and codebooks. Peak allocation is 3,529,801,216 bytes and total runtime is 27.25 seconds. The owned worker closes before releasing the GPU lease.

Independent readback verifies source/protocol bindings, phase and resource journals, gradient counts and the hash receipts. No diagnostic checkpoint was retained for a second independent tensor rehash; this remains a software feasibility result. Unmodified receipts and resource journals for both attempts are under `evidence/`, with hashes in `evidence-manifest.json`.

The fresh corpus and separate pilot live under `chess-queen-coach-sft-v1` and `chess-queen-coach-sft-training-v1`. The root alone dispatches GPU work under the unchanged resource reserves and shared lease.
