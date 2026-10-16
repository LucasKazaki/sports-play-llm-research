# Closed held evaluation failure — 16 October 2026

The planned matched evaluation stopped during the baseline condition when global
commit headroom crossed its running reserve. The selected trained checkpoint was
not loaded or called. The failure accounting passed independent local-agent
audit; the quality evaluation is incomplete and supplies no comparative result.

| Planned condition | Completed EOS | Partial | Failed | Not run | Planned |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 28 | 2 | 1 | 1 | 32 |
| Selected trained checkpoint | 0 | 0 | 0 | 32 | 32 |
| Total | 28 | 2 | 1 | 33 | 64 |

“Completed” describes generation termination, not accurate chess or coaching.
There were 31 retained raw receipts and no unresolved interrupted request. No
held reference content was opened or scored by the failure auditor. No accuracy,
move quality, explanation quality or model-strength metric is published here.

The 2,270 resource samples include a final commit-headroom observation of
3,964,276,736 bytes, below the unchanged 4,294,967,296-byte floor. Physical and GPU
free memory remained above their respective observed floors. This is a recorded
commit-reserve stop, rather than a reported CUDA out-of-memory event. The worker
exited nonzero; its receipt records child exit before lease release. The root
then observed that child absent and the lease free.

Process private usage increased by 1,197,563,904 bytes between the reported
post-cleanup observations; global commit increased by substantially more. The
last such process observation preceded failure by about 108 seconds. These are
different counters with incomplete attribution. Stable live CUDA allocations
across each cleanup do not identify the exclusive cause of the growth, prove a
leak, or guarantee that a fresh-worker design would repair it. No final
post-run frozen-storage verification was produced, and none is inferred.

The audit also retains an exposure disclosure: an overly broad diagnostic
display showed an earlier baseline decoded response and the failed response's
empty text field and token IDs. The auditor did not assess that prose, open held
references or score content. Later reads used a positive metadata allowlist.
The root reports seeing no decoded prose. This phase therefore must not be
described as having zero held-raw exposure. No displayed content is reproduced
in this package.

The successor counterfactual source and data design had been frozen before that
exposure and exclude all 512 games in the prior held reservoir. Any successor
corpus and experiment still require their own closed audit and reviewed plan.
No retry on the same held cases is authorized. The trained tutor profile remains
ineligible; this failure does not change the live tutor or its default model.

[The summary](summary.json) is a positive aggregate projection of the exact bound
private audit. [The evidence manifest](evidence-manifest.json) verifies exact
copies of the failed worker, failure, owner-closure and execution-snapshot
metadata, plus six code/test source files frozen before execution. The two other
execution snapshots—training protocol and selection—are verified by hash only
in this package because their contents include development identities or
selection metrics. Existing frozen training copies were not rewritten. No raw
held responses, case identities, inputs, references, prose, tokens or weights
are included. This is engineering failure evidence, not expert validation or a
completed coaching assessment.
