# One-shot CPU recovery v2

This is an operational recovery wrapper, pending independent source review and
explicit root dispatch. It has not constructed a corpus or run an engine. The
original intake, teacher and scientific protocol remain unchanged. The failed
first attempt stopped at the startup resource guard before source iteration;
its eight original evidence files are bound and preserved.

The changed context is the closed **failed** coach-held worker, its exited child
and the root's recorded free lease/two passing CPU observations. That failure is
not a held-quality result or model admission. This wrapper holds the existing
shared FileLock with zero wait as resource-context protection. It makes no GPU
query or learned call, and releases the lease after scientific work and cleanup.
Root defers other GPU dispatch until this driver has terminated.

The driver creates a sibling operational intent and phase ledger before importing
scientific modules or accessing the source corpus. It repeats two CPU samples at
least one second apart, requiring 8 GiB commit headroom and 4 GiB available physical
memory. A busy lease, live prior child, bad binding, failed sample, cancellation,
deadline or later error stops the sequence. There is no attempt loop, retry,
resource-floor change, source patch or adaptive cohort substitution.

Exactly one old intake must produce 512 TRAIN, 32 development and 512 reservoir
games. Only that complete intake permits the unchanged 3,168 teacher requests.
Only coherent complete teacher journals and read-only observations of the owned
Stockfish child and its exit permit the unchanged export. PID observation never
kills a process; observation failure requests cancellation only through this
attempt's `CANCEL` file. Absence of a sampled engine is not accepted as proof of
its lifecycle. No unrelated process is stopped.

Scientific guards retain 1,200 seconds for intake, 3,300 seconds for teachers and
the 13:00 UTC cutoff. They are cooperative guards. The wrapper also checks phase
elapsed time before permitting later work; it does not claim a hard OS deadline.
Writing only `<output>/CANCEL` requests cancellation after that owned directory
exists. Ctrl+C is retained as a failed operational phase. Hard process death
leaves its durable phase intent as active/unknown, never an invented completion.

`build_protocol.py` performs only source/metadata binding and freezes
`protocol.json` create-only. Its actual metadata check read the closed worker and
root context records, not held responses, references or quality. `run_cpu_once.py`
is the separate root-only dispatch entrypoint. Its root call, after review, uses:

```powershell
python experiments/chess-queen-coach-counterfactual-v1/recovery-v2/run_cpu_once.py `
  --protocol <absolute-protocol.json> --protocol-sha256 <exact-reviewed-hash>
```

The new private output is
`data/private/chess-queen-coach-counterfactual-recovery-v2`. Create-only sibling
files end in `-operational-intent.json`, `-operational-phases.jsonl`,
`-operational-admission.jsonl`, `-operational-engine-pids.jsonl` and
`-operational-closed.json`. Frozen operational sources and the prior failure
records are copied to `operational-sources/`; partial copy failure retains its
own manifest. Finalization also retains complete named teacher outcomes as
`operational-teacher-outcomes.json` once intake has supplied their identities.
Earlier failures record all 3,168 unstarted planned teacher slots without
inventing case IDs. All original scientific raw journals remain untouched.

The final output `operational-provenance.json` and sibling operational closed
record have identical values. A future trainer must require:

- `status == "completed"` and `owned_engine_exit_verified == true`;
- exact `scientific_protocol_sha256` and `operational_protocol_sha256`;
- `corpus_manifest_sha256` matching the actual exported `manifest.json`;
- exact closed-held-worker/source-snapshot/phase-ledger bindings and
  `resource_context_lease_released == true`.

Those fields are not a substitute for independent closed-corpus audit, a new
reviewed training/evaluation protocol or later explicit root GPU authorization.
The latest 11:15 UTC start rule still applies independently to each later GPU
phase. No source-data, corpus or current held-quality metric changes here.

The software receipt records 35 CPU tests with authored fake files/functions,
resource samples, process observations and clocks. These prove bounded software
behavior, not real intake, engine lifecycle, chess correctness or model quality.

`preexecution-draft-1/` preserves the exact previous unexecuted driver, operational
protocol, tests, receipt and full bundles. The amended driver also closes a
failed phase after an intent when a binding is malformed. PID observation or
logging failure still attempts this request's cancellation even if its error
journal cannot be written; any cancellation-write error is retained and export
remains blocked. These repairs change no scientific source or reserve.
