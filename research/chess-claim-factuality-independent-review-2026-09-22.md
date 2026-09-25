# Independent review — frozen chess claim experiment

**PASS for the finite internal software experiment, 22 September 2026.** This does not close the broader factuality goal or promote a shareable candidate. Review consisted of source/test inspection, development-only JSON accounting and file/native-log hash verification. The Company native executor performed all product execution. No reviewer product imports, model/engine calls or full-manifest/heldout-label inspection occurred.

## Accepted result and provenance

The versioned manifest froze 496 unique requests across the same eight real Lichess development positions and sixteen original candidate observations. Every request retains both its original candidate identity and submitted claim/reference, derivation and expected software-control disposition. All 496 executed; none failed or remained unrun. Independent JSON accounting confirms 256/256 supported board-field controls and 16/16 retained engine-observation controls accepted; 0/224 deliberately false, foreign-reference or unsupported controls accepted. The deliberately weak identity-only baseline accepted 192/224 negative probes. These are correlated software controls, not human labels or independent statistical samples.

- Manifest `artifacts/chess-claim-factuality-v1/dev8-claims-v1.json`: SHA256 `790d1a92672483f5aee39bee645621c9796c2c99a7a1ffcfbfdfd492b00e9c79`.
- Results `artifacts/chess-claim-factuality-v1/dev8-results-v1.json`: SHA256 `6903c0bdbc3e829df9a7b2c326704e6d28a3f11d63d78dc801d6925ecb2aed13`.
- Implementation `scripts/chess_claim_factuality_experiment.py`: SHA256 `0d0c0d2274ce9245372f03774e5699cb70620d035911ee498fffb95a33b57f45`.
- Primary test SHA256 `aaf56a2d1c6877456cacc5de654e55129c4fec2673499779eb4304c0aa7d59b9`; independent test SHA256 `0191d0f86f328c0042aa46c48378d4dc2d7f44645ea413906fa2344298a70175`.

Original v3 receipt `a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6`, typed packet `7743b9fac58695a99cee8f5918e0ca6225909c1750658fc60e34c57f42a9bd0c` and development projection `946754a1d52723786aaa4b63a60b5d499a9cc06470eac43a25601ea1da6e6316` remain unchanged. The manifest binds these, the adapter and experiment implementation. Actual source URLs/development partitions, canonical claim hashes, original/submitted references and complete denominators were independently checked. No new engine/model calls or heldout scoring support this result.

## Native verification and retained failures

Full task `ca09133f-d770-4ae4-bd4e-43d4bbe0325b`, run `0075ea3a-3ec9-46a8-bada-651fb9a0ea7f`, job `20aefb9f-540e-46d0-ac7d-34dbc57f9768`, server-owned receipt SHA256 `91f1469d557bdf0144329f76e176895d2ae80be9c69fce78c7e2070a925120a6`. All eleven commands succeeded. All eleven stdout/stderr pairs match original receipt hashes; before/after source hashes match current bytes. Native chronology proves manifest creation completed before measurement. Replay reproduced all 496 retained decisions with `complete=true`. Recorded aggregate per-claim validation time was 38.942409300 seconds, including repeated input validation; this is not a throughput or GPU benchmark.

Full verification: **1,281 tests passed, one skipped**. The skip is the existing Windows symlink privilege limitation in `tests/test_chess_broker_intake.py:133` (WinError 1314). Doctor, 25 reproduction cases, log collection, compilation, explicitly synthetic smoke and preview-only reset also passed; reset reported `applied=false` and `destructiveDelete=false`.

Red task `d7587079-20e0-468f-bbe3-f1081ba24da1` proved the missing module (receipt `fd1d7979e222605532084638fc3c52a23a69871f47c84f005711154a12f5553e`). Initial green task `130d755e-02ed-4d71-8276-79f9b72d7f88` failed duplicate foreign-probe IDs before measurement (receipt `0c9ac95a7be8e5fd934f259468343b1f928a238eef4c9bc652bf8ba3031d0417`). Correction retained original candidate identity rather than dropping requests. Task `2f0d88b5-1206-4496-8656-9f2a08db0486` passed **55 focused tests** (receipt `a4110393b2df592775f96c9bb7de8ecb7136b482c15accd3259a7b93bc6995a8`). All three earlier receipts/logs were independently hash-checked and remain historical evidence.

Tests cover manifest/result mutation, forged decisions with recomputed metrics, actual replay, pinned-source rejection, failed/not-run denominators, create-only output and size limits. Incomplete run/verify returns failure while preserving evidence. No unresolved material defect remains within this finite experiment's stated scope.

## Limits and remaining work

Expected board fields and replay share the existing legal-transition implementation. Success proves software consistency/control coverage, not independent chess-rule validation, trained explanation quality, teaching usefulness, general chess competence or sports transfer. Retained engine matches preserve typed scores and qualifications; they do not independently reproduce scores. The reference-only baseline is intentionally weak.

Keep `chess-real-claim-factuality-v1` open for structured square-occupation and explicit legal/illegal variation claims, with genuine negative controls and preserved source/version identities. The richer real-position interface also remains unmet. The typed adapter alone may retire from the active agenda after exact prior-agenda archival and truthful closure evidence; do not invent framework `completedBy` settlement or rewrite original task/budget history. The reviewed handoff script follows this scope, but its installation still requires native hash readback. Shareable output retains the separate Luna/Terra gate.

The [python-chess primary documentation](https://python-chess.readthedocs.io/en/latest/core.html#chess.Board.push) confirms that pushing a move alone does not establish legality. Preserve explicit board validity and legal-move checks in subsequent variation work. This source was checked during review; it is not a new empirical result or dependency-upgrade authority.

Detailed review accounting and exact native logs: `C:/AI/projects/LucasAgentStudio/artifacts/check-in-20260922T1438Z/chess-review/factuality-evidence.json` and `verify-factuality-receipts.mjs`.
