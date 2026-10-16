# Cached decoding: source investigation

This folder preserves a source review of Queen's retained cached-decoding failure and a small standard-library arithmetic and dispatch demonstration. The three research files are exact copies of the original frozen artifacts; `copy-manifest.json` records their hashes and byte counts.

The investigation proposes tests. It does **not** implement a cache repair, reproduce BF16 or NF4 numerical behavior, measure speed, or establish chess strength or coaching quality. Existing qualified runtimes remain unchanged.

- `findings-and-prospective-plan.json` distinguishes the retained BF16 cache failure from successful NF4 **no-cache** parity. Shape-dependent arithmetic is a hypothesis; the first divergent operation remains unmeasured.
- `source_math_probe.py` checks mathematical mask geometry and evaluates the installed bitsandbytes dispatch function using authored device properties. It does not import Torch, Transformers or bitsandbytes, query hardware, or execute a model or kernel.
- `source-math-result.json` contains only those limited demonstrations. Its device properties are authored inputs, not observations of the machine.

The script retains the original local paths and requires the pinned local environment. It is a research snapshot, not a portable benchmark. No runtime implementation, model weights, training data or fresh held-out responses are included.
