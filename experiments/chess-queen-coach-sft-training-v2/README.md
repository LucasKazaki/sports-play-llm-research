# Queen coach memory repair and full pilot v2

The new full pilot is running after a successful, independently audited memory qualification. No trained chess-quality result is claimed yet. The first pilot remains a failed attempt: 20 confirmed updates, 160 confirmed backward passes and one unknown following microbatch, with no selected post-training checkpoint or held-out inference.

The v2 runtime keeps the original loss calculation unchanged. After a completed call returns, the caller synchronizes, collects unreachable Python objects and releases only inactive CUDA allocator cache. It records this process's private memory and CUDA allocated/reserved memory before and after. Live weights and accumulated gradients remain intact. The owned tutor was also restarted with its optional CPU classifier disabled to release that context. No unrelated application was stopped, and the memory reserves were not reduced.

## Actual qualification

The fixed test replayed one already-spent development request through all 1,024 tokens, then completed 32 updates and 256 training presentations. All 12 checks passed. Two cleanup boundaries preserved all 144 adapter tensors and their 144 gradients exactly. All 2,268 frozen tensors, totaling 3,393,484,936 bytes, hashed identically before and after; adapter storage changed. All planned call outcomes were retained, with no unknown or missing call.

The final eight update boundaries had a private-memory range of 5,959,680 bytes, with zero range in CUDA allocated and reserved memory. Minimum observed global commit headroom was 8,253,722,624 bytes, above the unchanged 4 GiB floor. The owned worker closed successfully before releasing its lease. This qualifies that bounded combined operating condition; it does not guarantee stability for 256 updates or establish a chess skill. The diagnostic adapter is discarded.

Exact raw qualification, call/memory/resource journals and closed worker are under `memory-evidence/`, with hashes in `memory-evidence-manifest.json`. Independent review and source bindings are retained alongside the compact `memory-result.json`. The operational-condition addendum clarifies an imprecise phrase in the frozen full protocol without changing its executed bytes.

## Fresh full attempt

Protocol `5364c4c9a4b744770c5f0c9c617d6edc09730a0aa0dee2e3c0f55e6a80df6168` restarts from the original publisher/NF4 base, seeded zero-B LoRA and a fresh optimizer. Failed and diagnostic learning are discarded. Training data, order, targets, 256-update budget, development-only selector, matched held-out panel and generation limits remain the same as v1. Repeated training/development exposure is explicit; held-reference content remains closed.

Independent review passed the complete final source/plan and all 36 recursive bindings without importing the backend. The repaired trainer's combined CPU checks passed 32 tests. Every planned training case is retained, with actual completions, unknown calls and never-run cases distinguished; a torn final journal suffix is preserved rather than hiding the denominator. The three-hour training phase, 90-minute held-out phase and absolute October 16 cutoff of 13:00 UTC remain enforced. Root alone dispatches GPU calls under the shared lease. No checkpoint enters the tutor UI automatically.
