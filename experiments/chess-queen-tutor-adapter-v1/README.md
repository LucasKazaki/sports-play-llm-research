# Disabled tuned Queen tutor entrypoint v1

Current eligibility: the once-only fresh comparison closed at its unchanged
commit reserve before any trained-panel call. It provides no matched quality
result. This fixed step-64 integration remains disabled; its source-test pass
does not authorize activation or an identical held-test retry.

This adds an inference-only path for the fixed development-selected step-64
adapter. It does **not** change the running tutor, its default model, launcher,
frontend, current experiment, or any training/evaluation data. The new UI
qualification record ships with `availability:false`; ordinary runner admission
fails until its separate evidence and explicit decision are complete.

The development output already contains five false claims among twelve
recognized narrow facts, as reported by the root. Other prose is unscored.
A development-selected checkpoint is not a reliable coach, expert-reviewed
explanation, or automatic UI replacement. Closed training/held audit, an explicit
optional-demo decision and actual entrypoint qualification remain required.

The new child uses only frozen `Runtime.load`, `load_adapter`, `infer`, inactive
memory cleanup and storage verification. It never imports the trainer or scorer,
opens corpus rows/references, computes a loss, updates weights, discovers a latest
checkpoint or substitutes baseline weights. Every generation uses the exact
step-64 adapter before its first inference. The fixed adapter, selection, training
protocol, runtime and dependencies are pinned in [the protocol](protocol.json).
Current FEN, legally consecutive prior FENs and an optional legal selected move
are the only input fields. Black/White and free/selected requests have CPU tests.
Engine scores, PVs, future boards, solution labels and audit repairs are rejected.

The returned runtime dictionary is written unchanged to `response.raw.json` and
kept under `raw_response` in a separate envelope. The input bytes are read and
hashed once; the intent, parsing snapshot and outer metadata retain that same
hash even if cancellation produces no raw response. Entrypoint/profile provenance,
resource samples, failure phase and storage verification live outside it. The
raw `adapter_sha256` still identifies frozen Runtime v2; it is never relabelled
as the new entrypoint. Errors and partial/illegal model output remain visible.
No repair, engine fallback or automatic retry is added. Intent, events, raw and
envelope files are create-only per owned request; cancellation uses only its
`response.CANCEL`.

Frozen generation stays at 1,024 tokens, 180 seconds, deterministic no-cache/math
attention and the existing 4/4/1 GiB running reserves. The unchanged worker adds
30 seconds, giving a 210-second outer limit. Cold load and storage hashing must
be measured; the generation cap does not promise a full 180 seconds before that
outer deadline. Do not lower reserves or silently extend time to pass a smoke.

After independent full-source review, only the root may run authored
preactivation qualification under the existing exclusive worker. Use absolute
paths consistently; the later qualification checks the worker's exact argument
hash against input/output/protocol paths:

```powershell
python experiments/chess-queen-v1/gpu_worker.py --receipt <new-worker.json> `
  --maximum-seconds 180 -- <absolute-new-entrypoint.py> `
  --protocol <absolute-protocol.json> --protocol-sha256 <reviewed-exact-hash> `
  --input <absolute-authored-input.json> --out <absolute-new-response.json>
```

The input and output directory must already exist. Cancel by writing only that
request's `response.CANCEL`; wait for its closed worker before lease reuse. No
held case may be used for entrypoint or UI qualification. This local CLI does
not authenticate an OS user as the root agent; reviewed dispatch and exclusive
GPU ownership remain the parent's responsibility. It exposes no HTTP endpoint.

Future ordinary UI admission requires all exact bindings: closed training and
held-quality audit wrappers that point to original reports, an explicit root
optional-local-demo eligibility record, and completed/cancelled authored
entrypoint plus exact input/worker receipts, and an independent actual-entrypoint
audit wrapper linked to its original report. That audit binds both request trios
and source/protocol, with observed load, inference-entry, EOS and owned-shutdown
phases. Eligibility must cite its exact hash. Wrappers are metadata declarations
about independently reviewed reports, not a substitute for missing evidence or
human gold labels. `expert_human_semantic_validation` remains false. Every worker
must run this exact input/protocol/entrypoint and close before lease release.
Runner/source hash, raw response identity, settings and frozen storage are checked.
The caller must supply the exact complete qualification hash; no shipped
availability or favorable score can silently enable it.

The [software receipt](software-tests.json) records 47 CPU-only cases and the real
metadata-only binding check. Fake runtime/weight fixtures test provenance,
ordering, failure retention, cancellation, stale context and closed admission;
they are not model demonstrations. Actual model/engine/GPU/HTTP/browser calls in
this implementation lane: zero. Source bundles are retained in the current chat
under `work/tuned-tutor-source-review/`, each below 30 KB. UI integration and model
activation are separate later decisions and are not part of this change.

The first metadata preflight rejected four declared upstream source files because
their pinned checkout sits outside the repo. That failed check and exact draft
are retained in `metadata-preflight-first.json` and `preflight-draft-1/`. A second
metadata failure exposed the official formatter, pinned by the diagnostic but
absent from the earlier inference manifest; it is preserved in
`metadata-preflight-second.json` and `preflight-draft-2/`. The repaired binder
requires exact manifest-listed files inside the fixed source checkout. The
[supplemental formatter manifest](upstream-formatter-manifest.json) binds the
one formatter file to its fixed digest, original source manifest and diagnostic
protocol. Unlisted files, lexical traversal, symlink substitutions and unrelated
outside paths fail. `preflight-draft-3/` preserves the earlier metadata-pass draft
before this path hardening. No model was called while diagnosing or repairing
these metadata boundaries.

`work/tuned-tutor-source-review/prequalification-draft-4/` in the current chat
preserves the exact previous unexecuted draft, tests, receipt and qualification
design. The repair adds input-byte and independent actual-audit admission
bindings. It does not alter the frozen runtime or returned inference fields.
