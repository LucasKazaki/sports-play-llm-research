# No-forward input boundary — 22 September 2026, 20:29 UTC repair

## Implemented, tested and independently source-reviewed

scripts/chess_no_forward_packet.py is a new versioned input boundary; the historic prototype/chess_concept_model.py is unchanged and remains incompatible with the no-forward gate. The new module builds a selected real development move's pre-move FEN, source identity, deterministic transition facts, qualified typed engine observation and declared vocabulary. _shape rejects unknown fields. encode_no_forward_packet then compares canonical bytes with a fresh projection of the pinned source; modified allowed values also fail. dispatch_no_forward passes only those validated bytes to an injected generator. It makes no network/model call itself, returns raw callback output unchanged and propagates transport failure without retry or fallback.

Source SHA256 37f1f3cf9815d7b0d61f7358b72ced4cf230b1eab53420d4dbaa534b28413e22. Test SHA256 6eef7168b9c07db7bf7cbcc3429486ae76d4d4231ce5a4bf4e4bfe2e1557522b. Source/test code and original data hashes stayed frozen throughout verification. All 16 retained candidate inputs were checked in software tests. Fifty new tests include prohibited fields at six object depths, foreign/malformed/reference/hash/type tampering, rejection before dispatch, unchanged raw callback output, non-retry transport failure and CLI build/verify/no-overwrite. Synthetic score-shape probes are labelled software controls, not engine measurements.

## Native evidence and real inputs

Fail-first task 4c86ea97-ef73-4449-840a-5d2aae09262a reproduced the absent module. Its retained job is 47563c2a-4911-4781-a357-e9e6fb1f5d54. Before green execution, two synthetic bound spellings were corrected to the actual lower/upper enum; the original failed record was not rewritten.

Implementation task 0e757be8-e16c-4416-b683-558c9dee60cb; run 13219f43-068c-46cb-8b45-39e5a811a012; job b9015000-d2f8-4f14-b445-98cc838e91be; receipt 57a3a9ab2a17b439a16b2f0126c4f97cde5be9039e1153fe14bdd506a4473cfd. Result: 120 focused tests passed in 41.49 seconds, including 50 new tests and the existing 70 adapter/extended-claim checks.

Full verification task 4f81184f-d9a8-436a-bcd1-16150dafe1c6; run fae81381-6b25-4601-aaf5-3d275cb7a1f8; job e3243841-01f2-4360-bfef-5a15a5e6a026; receipt e7a46dc4194d2c979f97d63b8579c2516d87e3e7051c53313e70511b876cc6ed. All ten commands passed: frozen hash checks, retained evidence, eight real input packets, doctor, 25 reproductions, logs, full verification, explicitly synthetic smoke and reset preview. Full suite: 1375 passed, zero failed, one existing Windows symlink-permission skip. No reset was applied.

artifacts/chess-no-forward-input-v1/dev8-inputs/manifest.json, SHA256 b6458129c5e7b7f4ba0ebfe3c21f1ffd3dfeba5989691f48ec97461e52ff807e, binds eight canonical packet files: the first retained engine candidate from each of eight real development boards. It is a convenience selection, not a representative quality evaluation. Original CC0 Lichess source/projection/engine receipts and train/development/test partitions remain unchanged; original acquisition evidence is indexed in research/chess-extended-claims-2026-09-22.md. No new model or engine call, human annotation or heldout outcome scoring occurred. Historical test labels are not blind evidence.

## Independent review and protocol repair

Review 69901eca-a97d-4605-ba3a-085213ee12df, run f00b4381-fd49-42a8-b9ce-479b72927635, returned passed after reading only the focused test summary and listing files. Its required runtime read was real, but source/test inspection did not happen. It is NOT accepted software review.

The corrected native callback required the complete 20269-byte source/test/log bundle, SHA256 55273444b9666c9066c378d02787dc6c8e6cd2be01f5021ed4aa07cf75af3f2d, as its mandatory read. Review 0323eb3c-b0af-42d2-9fcf-05a705ab01ca, run ef933d01-671b-48c4-8351-91d30fb03e56, completed at 2026-09-22T20:47:49.709Z. Its complete read and concrete verdict were verified. See artifacts/chess-no-forward-input-v1/independent-review.json and source-review-bundle.txt. This is local source review, not formal Company goal acceptance, commentary quality or publication approval.

## Next concrete requirement; capability gate remains open

Implement a separately versioned local generation runner using dispatch_no_forward. Freeze at most eight permitted inputs and the existing local model identity/settings/seed before calls; preserve 131072 context and reasoning quality. Add meaningful fake-transport tests for before-call rejection, model identity mismatch and exact durable retention of raw responses, malformed output, abstentions, latency and failed/not-run requests before any live use. An injected callback test is not an integrated model runner. Returned raw text is not an accepted explanation. Output assertion validation, post-generation evaluation, the frozen extended-claim experiment, a new game-disjoint heldout and later independent qualified review remain open.

No PV tails, post-move FEN, future moves/features, solution/theme or answer labels, annotations or evaluator-only material may reach a generator. Full typed receipts are evaluator-side data only. Preserve original jobs/tasks/budgets and the single scheduler. Do not retry the earlier placeholder task or malformed experiment invocation. The original five agenda IDs and gate dependencies remain; no completion marker or accepted-progress credit was added.
