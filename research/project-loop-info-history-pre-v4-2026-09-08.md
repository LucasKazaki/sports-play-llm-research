# Soccer project loop information

Updated 2026-09-08 UTC (7 September locally). Company Runtime is the sole research scheduler. The current disposition is **SYSTEMS GO / SEMANTIC NO-GO**.

Current publication instruction: the loop is authorized to access and update the existing Archit Doc through the server-owned direct Google publisher, with zero model calls for routine status changes. The old Codex heartbeat remains PAUSED. Local Google OAuth setup is still required; do not report continuous publication before a direct read/write/readback receipt exists. See [publication protocol](archit-doc-sync.md). Only Live progress is automatic; new research prose retains the exact candidate, Luna and Terra gates. Native Doc receipts are publication evidence, not model improvement.

Current execution authority: the loop owns implementation throughout this project and registered worktrees, including creating/editing source, installing available dependencies, building, testing, debugging, media processing, inference, evaluation, training and long-running experiments. Use `sports-play-llm-project-executor`, `workflowId=project-execution`, `workflowVersion=1`, `actionScope=project_execution`, `requiresBrowser=false`, and actual `input.commands` argv arrays. There is no per-file allowlist or default elapsed-time cutoff for this lane. Older missing-broker statements are historical failures, not current instructions. Missing Python or a failed test is an engineering dependency to diagnose and fix.

The local developer reads source and retained logs and submits native command follow-ups. Include `input.resultTask={agentId:"sports-play-llm-developer",title:"Inspect result",readCommandIndices:[0],instructions:"specific acceptance check and next decision"}` so Company Runtime returns success or failure directly to a local inspector. Select the command indices containing the required acceptance output; the runtime binds their exact stdout paths, adds actual failure diagnostics, and requires those reads before completion. The default is the last command that actually ran. Inspect `.agent-runtime/jobs/<jobId>/receipt.json` additionally when useful, fix ordinary failures and submit a distinct corrected task. Do not replay retained jobs. Shared workspace/GPU ownership determines concurrency; use registered worktrees for disjoint parallel edits. Waiting native jobs consumes no model tokens. The runtime callback is part of the existing loop, not another scheduler.

Use the handoff's exact workspace-relative paths with `read_project_file`. Read the output containing the test count: a command count is not a test count. For a corrected native follow-up from an inspection, omit `recoveryFor`; its parent is the inspection task. Frozen `artifacts/footballmaster/pilot-v1` is explicitly readable in the native sandbox and stays immutable; create new experiment outputs elsewhere. The [live toolchain receipt](../artifacts/project-capability-20260908/live-toolchain-verification.json) verifies all seven commands exited zero, 407 project tests passed, all 14 logs matched, safe reset was preview-only, and all 11 frozen pilot files retained their hashes.

The native runner prepares each new Windows sandbox under a shared setup mutex,
then releases it before starting project work. This addresses the initial measured
permission race between fresh workspaces without serializing the experiments themselves.
The 120-second initialization deadline applies only to the no-op setup; ordinary
project commands retain their chosen duration, including unlimited execution.
Setup logs and command logs are distinct. A preparation failure is an execution
dependency to fix, never evidence that a project command ran.

Additional executor validation at 04:09 UTC found one intermittent frozen-evidence
read denial while project writes worked and frozen/outside writes remained denied.
The isolated recheck, four concurrent fresh rechecks and the complete 85-test
focused recheck passed. Preserve that failed observation; do not describe the
host permission race as eliminated. Inspect exact setup/command evidence and
correct the execution dependency without changing frozen evidence or replaying
a retained job. The [supplemental executor receipt](../artifacts/project-capability-20260908/prelaunch-executor-verification.json)
also covers 21 passing interpreter and callback regressions. Prelaunch callbacks
now retain the exact error and `projectCommandStarted=false`, with a mandatory
receipt read when both output logs are empty. Source validation and live activation
are recorded separately; this supplemental receipt does not claim a new experiment.

The [supplemental activation readback](../artifacts/project-capability-20260908/supplemental-activation-verification.json)
now confirms the loaded runtime source and active soccer loop after the combined
2,276-test pass (zero failures, 13 skips), lint, type checks, build and smoke.
This activates the interpreter and diagnostic fixes while preserving retained jobs.

Live activation is verified in [the activation receipt](../artifacts/project-capability-20260908/activation-verification.json).
The combined Studio checks passed 2,252 tests with zero failures and 13 skips,
plus lint, type checks, build and smoke checks. Local Qwen run
`087138d9-7fb1-4e7f-812b-3775de7bc238` then used five local requests to read
the three required soccer logs and correctly report 407 tests, the project
interpreter and preview-only reset. A duplicate read was rejected and clipping
was disclosed; no command was replayed. [Actual readback evidence](../artifacts/project-capability-20260908/local-inspection-verification.json)
separates this accepted inspection from the retained failed receipt-only attempt.
This verifies the execution and inspection capability; sustained autonomous
model improvement and frontier parity remain to be demonstrated.

The subsequent autonomous event-classification proposal failed because it guessed
`sports_play_llm.evaluate_event_classification`; its successor then attempted to
install the guessed package. Both jobs are [rejected as experiment progress](../artifacts/project-capability-20260908/autonomous-command-grounding-rejected.json).
Before choosing a command, inspect the actual implementation, CLI and tests.
Use existing entry points such as `scripts/local-model-experiment-v1.py` when
appropriate; a missing proposed module needs a justified implementation task,
not an assumption that it is an installable dependency. Validate a concrete
development change and its result before advancing a model-quality claim.

A later grounded goal task passed 14 existing search tests and its local callback
read the actual output in four requests. The callback proposed the same command
again under another title; the runtime rejected it and created no duplicate job.
[Independent acceptance](../artifacts/project-capability-20260908/autonomous-test-readback-verification.json)
confirms autonomous test execution and required readback only. The original task
title claimed implementation, but no source change, human probe or model experiment
ran. Stronger local planner and context-budget work remains with the runtime repair
task; select routes by measured command validity and latency, not model size alone.

The shared CPU-only 20B planner trial was [rejected](../artifacts/project-capability-20260908/local-planner-trial-rejected.json):
183.6 seconds, four requests, two source-file reads and one listing, followed by
a nonconforming worker result and unsupported source claims. Its JSON syntax
was valid; its evidence/message structure failed the task contract. No route changed. This was
a benign software-planning trial, not soccer data or a matched model benchmark.
The owning runtime task is repairing source-context preservation before another
planning trial; a larger model is not evidence of more useful autonomous work.

The [second 20B trial](../artifacts/project-capability-20260908/local-planner-trial-v2-rejected.json)
also failed acceptance: 95.9 seconds and four requests produced a blocked result
with no native follow-up, incorrectly treating the read-only planner's lack of a
direct patch tool as lack of project execution authority. Its JSON parsed, but
the capability conclusion was wrong. The coordinator retained the existing GPU
routes and unloaded the temporary CPU instance. The next runtime revision passed
2,296 tests with zero failures and 13 skips; live activation is recorded separately.

Real data rights, credentials, external services, spending and scientific promotion retain their actual prerequisites. They do not block independent local software work or authorized development experiments. Project code must not read OAuth credentials or call Studio operator APIs. Benchmark the local specialist system on completed project tasks, hidden regression checks, error recovery, evidence fidelity, latency and total model calls; frontier-level capability and reasoning quality must be measured separately. No parity or doctoral-quality result is established by an execution receipt.

## Promoted proposed research contract

The exact reviewed contract is [loop-contract-review-copy-v2.md](../artifacts/soccer-loop-live-20260906/loop-contract-review-copy-v2.md), SHA-256 `ca49b04735f1bd47b2dd5f1927cde0ad58d377e38e3a8de999d1eec379c36720`. This is proposed governance and required future preregistration work; it establishes no performance, novelty, coach utility, doctoral quality, or processing rights.

- Isolated GPT-5.6 Luna returned PASS in task `003beef9-4f93-4bb7-a40d-81245c421640`, run `0880bcf3-531f-4b87-a7f4-a1fd835ac578`, reasoning receipt `610cdaa04d3766cd63f84832aa845d70d10039e7d50f3751b81ed39a3e2dc890`.
- A later isolated GPT-5.6 Terra inspection in run `5e0379e7-a87e-406b-b6e1-9790235da24a` judged this proposed contract sound and dispatched the exact promotion edit. Both model gates used Codex CLI with zero tools.
- The local writer created [loop-contract-promotion-v2.json](loop-contract-promotion-v2.json), SHA-256 `127804315f6dcc929c8892071084907fd6876f3bdb201f149c9d189a30f250ad`, in task `ad34e26b-ddd2-49c1-9c30-21cb33a7707d`, run `3c45905a-d94e-4334-a1ad-54639ba6afb7`. Its workspace-mutation receipt is `2fd4bca0aaede321cd8ded0bd40e5a788629fbf9293da67015ca2778b0ce2c35`.

The expanded [research-loop-agenda-candidate-v1-2026-09-06.md](research-loop-agenda-candidate-v1-2026-09-06.md) remains an **unpromoted internal working draft**. Full text was not covered by the compact model gates. Its primary-source snapshots under `artifacts/research-loop-agenda-20260906/` are executor-captured provenance, not Company Runtime browser receipts or independently verified source truth.

## Current bounded priorities

The [model-improvement loop](model-improvement-loop-2026-09-07.md) and [college sports market research](college-sports-market-research-2026-09-07.md) are current internal operating notes. Their full text was not promoted by the compact Doc reviews.

1. Models and evaluation: use the [engineering receipt](../artifacts/college-sports-market-20260907/engineering-improvement-receipt.json) and [independent version-bound review](../artifacts/college-sports-market-20260907/query-guard-independent-review.json). The prototype query planner and its UI have 14 passing focused tests and 398 passing full-suite tests; this does not establish parity with the separate multisport planner or soccer accuracy. Next freeze development query cases, then outcome/failure rules and a controlled comparison on permitted, independently annotated inputs. Keep fixtures internal and unscored until their own review. Preregister scoring, eligibility, denominators, numeric criteria and matched budgets before untouched test access. Each task needs exact inputs, hashes, output, owner, budget and acceptance check. Run authorized development experiments through the native project executor and inspect its retained receipts.
2. Market and integration: verify an actual college soccer retrieval need and permissioned export/camera/clock feasibility before collecting partner data. College football has a separate ontology and incumbent baseline. Access, demand, account entitlements and team stacks remain unknown. The local worker delivered an internal [feasibility checklist](candidates/college-soccer-export-feasibility-checklist-v1-2026-09-07.md) from supplied source facts; it does not establish rights, run an experiment or freeze coach gold labels. Task `4f2430e2-6f40-4a5b-a7a5-6e10c4f75e37` completed at 00:30:45.668Z on 8 September in 58.545 seconds with one model round, one atomic create and no follow-ups. Full readback matched the literal packet except final newline; it remains internal and unreviewed. Actual status and receipt are in the [current operational receipt](../artifacts/college-sports-market-20260907/final-runtime-operational-receipt.json).
3. Sources: make the SoccerMaster encoder/head dependency preflight actionable from exact source facts. Distinguish repository revision from checkpoint hash, annotation-pipeline from encoder dependencies, and availability from rights or GPU fit. Check both official project and paper surfaces within 24 hours. Unchanged observations are activity. The live source policy uses a four-hour interval, giving the two-source catalog an eight-hour rotation within the 24-hour maximum. Prefer a new actionable dependency receipt over an identical source summary.

Keep the existing Gemini benchmark priority gated: at least six clips, ideally 10–15, only after third-party processing rights and zero-spend or approved-spend evidence. Frozen protocols and existing human gates remain in force.

## Execution and publication boundaries

Use the full native project executor for commands, edits, tests, benchmarks, media and model experiments. The exact-path writer remains a separate convenience for small file packets; its file-count restrictions do not govern native execution. The local developer has a real workspace-read surface. Hosted Luna/Terra reviewers retain their isolated evidence-review roles. Do not substitute model prose or synthetic examples for experiment output, or repeatedly inventory the workspace instead of changing and verifying the project.

Google Doc publication follows [archit-doc-sync.md](archit-doc-sync.md). The existing [Archit progress Doc](https://docs.google.com/document/d/1uUdenRhHnkKJQSQVH4ppDhSdTbrlLJafrAuiZMzKEjk/edit) contains the separately reviewed proposed plan and managed status. The publication-only heartbeat `soccer-progress-doc-sync` is now **PAUSED**, as confirmed during the 7 September model/market repair. Do not restart it or create a substitute schedule. Current explicit user-authorized Doc edits require their own review and readback. Historical native post-restart readback was verified at 2026-09-07T05:28:11.890Z for the runtime snapshot observed at 05:27:35.824Z; evidence is `artifacts/google-doc-sync-20260906/post-restart-verification.json`. This old snapshot is not current activity evidence.

Publication is limited to the user-authorized managed sections and cannot dispatch research, become a second scheduler or promote new scientific claims. Candidate creation, exact Luna review, defect correction, later Terra inspection and exact promotion precede scientific updates. The Doc research body and operational template have separate gates; this contract manifest does not certify future candidates or snapshots. The guarded publisher preserves collaborator edits and distinguishes runtime activity, structural delivery, retained backlog and scientific evidence.

Historical September 7 runtime repair (superseded by the execution authority above): the already-enabled project's supported objective update preserves queues and points to the two current operating notes. Its final 920-character contract forbids the stale evaluation-candidate path, generic create-or-correct tasks, inventories and invalid `recoveryFor` retries. Allow up to three disjoint lanes only when executable with admitted tools. New supplied content needs a fresh exact create-only target and full readback; verify an edit target exists. The objective is steering, not proof of enforcement: automatic director work still reused stale scope and generic local workers made unsupported completion claims. Exact failed tasks `4eee6fdb-8eab-449c-b6a9-51d14687d27b` and `ea18b799-e133-42ed-ac65-935ec5a770bb` remain blocked evidence, not completed recovery. Global `company.review` still depends on the unavailable `main` GPT-OSS route; no project-specific API fixes it without affecting other projects. Actual Terra/Luna gates and explicit bounded file packets work, but the full autonomous experiment loop is not functioning. Evidence: [runtime audit](../artifacts/college-sports-market-20260907/runtime-audit.md), [objective readback](../artifacts/college-sports-market-20260907/objective-narrow.validation.json) and the current operational receipt.

The exact compact market body passed Luna run `0d0a7b3a-06ee-4617-977c-5c806598e544` and later Terra run `07f6b300-210e-42a8-b8a2-0b69fa0a7630`; its review-copy SHA is `a02f17cf37defe8142c5cd38e2970d08558e1e0bb554cbbbd8df740b3ca020c5`. The exact model/engineering body passed Luna run `b6c8ad95-d981-4404-811a-35de4f40e454` and later Terra run `ba6d6562-a63c-4912-ab28-821766976329`; original SHA is `dc2ff9b4608ebd7a1623a04ac5913a822aed32e10d1103418a15ea55dd2cf0c7`. Both pairs used the requested models through isolated Codex CLI with zero tools and complete bounded candidate/fact exposure. These approve Doc prose only, not scientific results. [Market promotion receipt](../artifacts/college-sports-market-20260907/market-v4-doc-promotion-receipt.json) and [model promotion receipt](../artifacts/college-sports-market-20260907/model-v1-doc-promotion-receipt.json) preserve rejected versions, the model reviewer SHA transcription typo, actual identities/order and operator metadata corrections. The market metadata worker was rejected for zero observed mutations; its final manifest is explicitly operator-written. [Native Doc readback](../artifacts/college-sports-market-20260907/manual-doc-verification.json) verified both exact approved bodies, 24 citation links, two native dates and preserved content/styles outside the authorized range. Its operational snapshot was observed at 00:30:20.930Z, before the checklist completed; it is a dated observation, not live activity. The scheduler remains PAUSED.

Routing repair and gate evidence is retained in `artifacts/soccer-loop-live-20260906/`. Runtime task counts and file-creation receipts are operational evidence; neither measures research quality. Doctoral suitability remains a research outcome to earn through reproducible methods, sound comparisons, uncertainty, rights, human annotation and a broader novelty review.

## Repair handoff and open work

The exact reusable operational template v4 passed Luna in task `dd54c363-8eb8-46fb-ba76-8d233e5cd1c6` and final Terra inspection in run `6fa2428f-1f45-44c0-a2f6-ab6e6e2937ba`. Its reviewed copy is `artifacts/soccer-loop-live-20260906/archit-live-status-template-review-copy-v4.md`, SHA-256 `91783bb671bb29dfec0f32bc4e053c3b34918b5da0feeb84a33858ddd66fb2b5`. This approves template content only; native publication and future snapshots need their own guarded readback. The expanded agenda remains unpromoted.

Coach-query task `8b1c6847-8d3f-4789-a468-fbf9426c5de6` ran on the local writer and created a design fixture. Semantic readback rejected missing per-case bindings and incorrect absent-event wording. The original was preserved; an operator corrected the internal v1 draft and validated its structure. `artifacts/soccer-loop-live-20260906/coach-query-design-correction.receipt.json` records the exact defects and hashes.

After restart, literal v2 task `1a601fbd-ab3c-41f1-ad17-a000ab57615c` completed in run `e52ad2aa-9d4a-4d87-91f4-812399e0809f` with one local model request and one atomic create in 19.5 seconds. Its first output copied an escaped-quote encoding layer and was invalid JSON. The raw bytes were preserved; an operator removed only that encoding defect after exact comparison with the supplied complete object. [coach-query-design-cases-v2.json](fixtures/coach-query-design-cases-v2.json), SHA-256 `cb9d2394b6bf74c5e86d2f3599b74142a3fe00bb6779c1799b8faa10126be44b`, now matches the exact expected five cases with null media/gold bindings and all scientific-validation, execution and frozen flags false. It remains **internal, unreviewed and not frozen**; no experiment ran. The runtime receipt certifies the original bytes, while `artifacts/soccer-loop-live-20260906/coach-query-v2-literal.validation.json` separately certifies the encoding correction. Structural delivery alone did not catch this defect.

Obsolete interventions `d5587147-ded0-45bd-a396-31875013b074` (Sept4 internal write permission) and `273843e0-b0f3-4606-a8a1-16fe10e079df` (false empty-workspace assertion) were resolved through supported API with retained annotations and current exact-file evidence. They remained resolved after restart. Their old tasks were not certified done. The Sept4 durable interrupt remains open because the API offers no retirement without resuming old scope; it must not block current authorized lanes. Three original rights/adjudication interrupts remain open. A further interrupt `80bba42d-254a-4626-a338-307f67666f73` retains an unverified coach-boundary candidate whose worker claimed a nonexistent file and asked for promotion review; it was not resumed or promoted. Evidence: `artifacts/soccer-loop-live-20260906/obsolete-interventions-resolution.receipt.json` and the final operational receipt.

The supported graceful restart activated the four-hour soccer source policy. Readback confirmed one listener/runtime owner PID 27076, schema 8 compatible, runtime started, soccer desired/working and the director resolving to GPT-5.6 Terra through isolated Codex CLI. Two official sources imply an eight-hour catalog rotation, inside the 24-hour rule. All 21 project-registry tests and 14 focused active-wake/source-revalidation tests passed; the regression also preserves other projects' policies. One-line change evidence is `artifacts/soccer-loop-live-20260906/source-cadence-change.validation.json`; activation, actual task status and publication evidence are retained in `artifacts/soccer-loop-live-20260906/final-operational-receipt.json`. Local worker semantic defects still require independent readback; improved routing and bounded delivery do not establish research quality.
