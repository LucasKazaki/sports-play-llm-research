# Legality-learning retry

The original v6 attempt stopped after 64 optimizer updates when Windows commit
headroom reached 7.60 GiB, below its frozen 8 GiB reserve. Physical memory had
9.55 GiB available and the GPU had 11.19 GiB free. It completed the starting
512-position development evaluation; no held-out or forecast call occurred.
The original source, protocol, loss log, resource samples and failed worker
receipt remain in their original paths.

This separately versioned run keeps the scientific experiment fixed: 65,536
training rows, batch 128, 4,096 updates, full-vocabulary cross entropy plus legal
probability mass, original v5 step-2048 start, and the same development-only
selection rule. It starts a fresh optimizer from the original checkpoint;
the 64 unsaved updates are spent work, not resumed weights.

The memory reserve changes to 6 GiB commit headroom, matching the completed
balanced-check experiment. Physical and GPU reserves remain 4 GiB and 256 MiB.
A forward pre-hook samples counters at most one second apart during training
and evaluation. The pre-hook changes no model input, logit or selection rule.
The shared GPU worker retains its lease until the owned child exits.

The new protocol binds the exact existing labels, their original protocol,
completion receipt and executed teacher-source manifest. No new engine label
is requested. Model outputs remain raw and unmasked at inference. The code
records per-update completed progress and all planned evaluation denominators,
including unknown interrupted requests and explicit identical-checkpoint reuse.

Forty-six CPU checks pass, including unchanged objective/selector source,
resource thresholds, sampling, full not-run/unknown ledgers, the original v6
gradient checks and v5 evaluation behavior. These tests establish software
behavior only.

The retry completed all 4,096 updates and 524,288 example presentations.
Development selected update 4,096 before held-out evaluation. The fresh
512-position test matched Stockfish on 369 positions, compared with 370 for the
starting checkpoint; raw legality fell from 512 to 511. On the separate
128-position forecast panel, exact one/two/three-ply prefixes changed from
85/54/43 to 86/55/43. All 128 references support three plies. Illegal stops fell
from four to three, while legal three-ply rollouts rose from 121 to 122.

These results are essentially flat and do not support a model promotion or
coaching claim. An independent file-only audit reconstructed every development
and held-out ranking from all 1,968 logits, verified all finite updates, exact
starting weights, development selection chronology and all 4,352 planned roots.
See the [summary](summary.json) and [evidence manifest](evidence-manifest.json).
