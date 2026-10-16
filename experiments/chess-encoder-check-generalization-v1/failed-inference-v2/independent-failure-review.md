# Fixed-head generalization v2: closed failure audit

Failure accounting passes. The evaluation stopped at the unchanged commit
reserve and produced no head predictions or generalization score.

| Retained denominator | Completed | Failed | Not run | Unknown |
| --- | ---: | ---: | ---: | ---: |
| Move-feature records, 128 planned | 4 | 2 | 122 | 0 |
| Original epoch-0 head, 128 planned | 0 | 0 | 128 | 0 |
| Selected epoch-4 head, 128 planned | 0 | 0 | 128 | 0 |

The initial “first feature” description is incorrect. Two current-board encoder
forwards completed, producing two feature shards for four requested moves. The
third callback failed at its first, pre-forward resource guard. Of 64 planned
unique boards, two encodings completed, one callback failed before its forward
and 61 were unattempted. No interrupted outcome remains unknown.

The two shard hashes and structural tensor metadata match the journals:
FP32 features of shape `[2, 3072]` and int64 indices of shape `[2, 3]` in each.
Numerical feature storage was not decoded. This audit imported no Torch or model
library and made no model, engine or GPU call.

The exact source, protocol, source-review receipt and worker arguments match
their frozen identities. All 23 execution snapshots match their originals and
manifest. Both complete 128-row prediction ledgers remain `not_run`, with no
logits or prediction-attempt journals. All 64 source-pair slots were constructed;
the failure was not a source shortage.

Three resource observations show commit headroom falling from 9,846,947,840 to
7,058,423,808 and then 6,088,839,168 bytes. The last observation breaches the
6,442,450,944-byte running floor. Physical and GPU free memory stay above their
observed floors. No CUDA out-of-memory event is recorded. These global counters
do not identify an exclusive process-level cause; no private-process memory
trajectory was retained here.

The worker exited with code 1 after 12.046 seconds and records child exit before
lease release. An independent read-only probe at 10:51:45 UTC confirms PID 52276
absent with `OpenProcess` error 87. The current shared lease was not probed,
because other root-owned work may now use it.

The executed verifier byte-hashed the fresh label file as planned. Its semantic
load occurs only after both prediction panels complete, a stage never reached.
No score or successful closed-result file exists. This conclusion uses frozen
control flow, the retained traceback and outcome ledgers, rather than an OS
file-read tracer. The auditor opened no input positions or fresh labels and did
not rehash the source input/label/reference files.

The adjacent JSON retains exact hashes, aggregate journals, resources and scope.
The failure supplies no matched quality result, training gain, coaching claim or
UI eligibility. No retry, source change or additional learned call was made.
