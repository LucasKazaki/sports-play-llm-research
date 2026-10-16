# Independent closed audit of coaching pilot train1 failure

Verdict: the failed attempt's retained evidence is internally coherent, with one important unknown microbatch. No trained-model performance result or accepted checkpoint follows.

The root confirmed terminal execution before this readback. The auditor checked only closed train1 and its frozen dependencies/development references; no model/tensor/engine library call and no held-reference content access occurred.

Exactly 160 finite backward-completion journal entries and 20 optimizer-completion entries match the first 160 cases of the declared seeded one-epoch order. Each optimizer mean loss matches its eight recorded micro losses. The final journal then contains **step 21, micro 0, `call_started` without completion**. That attempt remains unknown. The saved partial-accumulation value is zero, but the runtime's post-backward guard can fail before the trainer writes completion; zero therefore cannot establish that an additional backward did not occur. The planned 2,048 micros comprise 160 confirmed complete, one unknown and 1,887 never run. No 21st optimizer update is claimed.

The step-0 development condition has all 64 finite NLL outcomes and 4,180 supervised tokens, yielding independently recomputed token NLL 2.112202738717412. All eight fixed raw requests are retained: six EOS completions and two partial outputs. Their native metrics recompute exactly, with seven accepted legal/teacher-best choices overall; all eight whole-prose factuality measures remain unassessed. This is baseline development evidence, not a trained-vs-baseline gain.

The three future development conditions preserve all 24 raw requests and 192 NLL records as not-run. No heldout attempt, selection, final frozen-storage acceptance or saved post-training checkpoint exists. Only the initial step-0 adapter is saved. The 20-update in-memory weights were not retained and cannot be evaluated or reconstructed from the receipt.

All 623 resource samples match the durable journal. The final global commit headroom is 4,013,944,832 bytes, below the frozen 4 GiB floor. Physical/GPU free memory still exceeds its respective floors. The worker failed with exit 1 and recorded child exit before lease release. All 44 frozen software snapshots match originals and the reviewed plan; all 27 run/worker files remain byte-stable across the audit.

Run SHA-256: `9bd4a4c61007eb41e19da523d6965091476e9d6911a10d81219be463ee25092f`.
Worker SHA-256: `8701aba45612b14409db1629d6a195d43dbea55d71ffd7a33a611ea888c4be31`.

Auditor/result: `audit-coaching-train1-failure.py`, `coaching-train1-failed-result.json`. A versioned memory repair/qualification needs separate source/protocol review; this audit does not authorize a repeated attempt or lowered reserve.
