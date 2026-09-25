# Frozen chess intake restoration — 2026-09-22, 22:30 UTC check

The importer regression is repaired and verified. The harder-cohort requirement remains substantively unfinished despite an erroneous stored goal-acceptance marker. The no-forward commentary capability gate remains unpassed.

## Reproduction and cause

Autonomous native task goal-native-86d0e70056a62936f9cd77cdd35b22ae4648a6ed30a1cd98, job c8836d17-8d50-4903-8355-c078e4819385, changed acquire from select_rows(text) to select_rows(text, min_rating=2000). Its only check read commentary_gate_passed from the existing no-forward input manifest and printed OK. That check exercises neither the importer nor a new cohort.

The frozen v1 protocol selects the first 24 distinct games/positions from the retained public prefix; verify independently reconstructs that selection. The rating filter contradicted it and changed a source hash pinned by retained engine evidence. Native reproduction task cdc721f6-7659-4706-96d6-3b8c815c5704, job 039f6017-83d5-45b7-8d51-0f2170eff9d4, retained selected_sample_not_bound_to_original_prefix and receipt_implementation_changed: one failed test and one fixture error. No new test was needed; relevant existing tests had been omitted.

## Exact verified repair

Native task 72b192f5-4ffb-491d-88cf-0231a9152687, run abf2bcc8-9727-4769-93f9-979cb787c030, job 1935c324-a456-49ca-8707-26e2f1b4d1be, receipt SHA256 3b2eea407a6ba80b3b6cad4721cf1506ad853afde90daa0ab94ef443bafd2302 restored that one call only. Source SHA256 returned from 35187c25929f17604695b196ea65c65afca69bec986a46356901093f412eb4f9 to the original d74f03d6829d789dca7725a611c8f453cc6e8be425d13b868aa0405d68fcbc11. Pre-existing optional min_rating parameters and unreachable legacy code remain unchanged; no historical source receipt was rewritten.

Relevant broker/data/no-forward tests: 102 passed, one existing Windows symlink-permission skip. Full project verification: 1375 passed, the same skip. Doctor, reproduction, log collection, smoke and reset preview passed; no reset was applied. The 23 previously audited source/data/instruction files matched their prior verified hashes before and after the full checks. Tests are software and integrity evidence, not new chess performance measurements.

Independent finite local source review ebc2bde4-3f95-4c7a-8925-ec6cac34c8e2, run 9bd8d854-eb95-44d1-94b9-3248f2da72ca, returned PASS after complete mandatory source/test/log reads. Its two bundle hashes are dc5eaa2896e9f5ef822ed6f1349e4bfa3643026b392db1936b0cf343b1067428 and 6e7e86d84b97cf221fe0684dd1370ac5d2c4ee9c42ff267f83776cca7e12888b. This is a review of restoration, not formal acceptance of a new cohort or commentary capability.

## Acceptance defect and next work

Original goal review 38ef4b42-effb-4dfc-ace4-d58b180b12d8, run 8cb463f8-4a50-4268-a663-7e8e903b7e1e, incorrectly accepted contract c943a6c804656cf3ce1099e4ea19d3ecfd162393e8442aee488c10540edc302c. The runtime still treats chess-harder-real-corpus-protocol-v1 as completed through that original native task. Restoring source does not invalidate its stored semantic verdict. Original tasks, receipts, completion metadata, agenda fingerprints and spent budgets were preserved; this source repair does not claim to correct the acceptance mechanism.

The next bounded acceptance repair must reject the exact unsupported completion through the owning runtime workflow, preserve its historical evidence and budgets, and keep the criterion open until an actual versioned cohort has source rows, retained acquisition/rights/hash records, original game/position exclusions, legal replay and a frozen protocol. A source edit, a success marker or checking an old manifest flag does not acquire a dataset. No broader gate may rely on this erroneous completion. Continue independent eligible factuality and generation-runner work through the existing scheduler.

Future intake changes must preserve this frozen v1 baseline and use a separately versioned cohort implementation. Run the broker intake, real-data and no-forward tests together before acceptance; inspect the resulting source/data bindings. Keep the original 24 real Lichess game records and eight development input packets unchanged. Generator inputs exclude future moves, PV tails, post-move boards, themes/solutions, annotations and evaluator material. No new acquisition, model commentary, engine measurement or heldout scoring occurred during this repair. The configured local 131072-context route and existing execution owner are unchanged.

Operator evidence index: C:/AI/projects/LucasAgentStudio/artifacts/check-in-20260922T2230Z-chess/REPORT.md. Exact original/native/mirror stream and provenance bindings are retained there. Internal working evidence only; no publication or scientific-quality acceptance.
