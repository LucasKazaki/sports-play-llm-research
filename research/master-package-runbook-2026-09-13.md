# SoccerMaster master package — local runbook, 13 September 2026

Internal implementation candidate. SYSTEMS GO / SEMANTIC NO-GO. This document does not authorize acquisition, inference uploads, spending, annotation, sharing or promotion.

## Reproduce through Company Runtime

Submit finite commands to sports-play-llm-project-executor, project-execution v1, actionScope project_execution, requiresBrowser false, with real argv arrays and timeoutMs 0. Use fresh output directories. Never replay a retained job or reuse an existing output directory under a new task identity. The native receipt and complete command logs are under .agent-runtime/jobs/<jobId>/.

1. Official checkpoint metadata preflight: python prototype/soccermaster_preflight.py --output artifacts/NEW_PREFLIGHT/preflight.json
2. Focused contracts: python -m pytest -q tests/test_soccermaster_preflight.py tests/test_hosted_video_benchmark.py tests/test_hosted_video_scoring.py
3. Synthetic six-clip end-to-end reproduction: python scripts/reproduce-hosted-video-scoring.py --private-out data/private/NEW_SYNTHETIC_RUN
4. Score a sealed run without media/model access: python prototype/hosted_video_scoring.py --run-dir data/private/SEALED_RUN --output data/private/NEW_SCORE/score.json
5. Convert frozen point labels offline: python prototype/hosted_video_label_conversion.py --annotations SOURCE_LABELS.json --config FROZEN_CONVERSION_CONFIG.json --private-out data/private/NEW_CONVERSION
6. Complete local checks and finite literal-mode demo: python scripts/verify-master-package.py --out artifacts/NEW_VERIFICATION

The preflight returns exit 0 when the inventory succeeds even if its status is BLOCKED. Read the status and blockers, not just the process exit. Synthetic reproduction generates silent color-screen videos and invented labels/reports, never soccer evidence.

## Frozen general-video contract

The existing coach-event-report.prompt.txt and coach-event-report.schema.json remain the model contract. A benchmark needs 6–15 actual clips; 10–15 is the target. research/fixtures/general-video-clip-intake-template-v1.json contains twelve unassigned intake slots and zero enrolled clips; it is not an executable manifest or evidence of rights.

Each hosted input clip retains source hash, actual silent stream probe, rights record, processor approval and held_out paths. For scoring, freeze held_out.labels_sha256 before inference. The label document has schema_version playground-hosted-video-labels-v1, clip_id, source_sha256, duration_s, time_unit seconds, annotation_origin synthetic_fixture or independent_annotation, and events with label_id, event_type, start_s, peak_s, end_s. Exact matching requires the same event type, interval IoU at least 0.5 and peak error at most 1 second; maximum-cardinality one-to-one matching prevents duplicate credit. The request receipt freezes this scoring definition.

prototype/hosted_video_label_conversion.py provides an explicit offline SoccerNet point-to-interval conversion. Supply the source annotation hash, matching match ID, half and duration, clip offset/duration/hash, exact ontology mapping and declared point-window/unit policy; inspect its --help and frozen config contract. It preserves source/mapping/policy hashes in a separate conversion receipt and fails on ambiguous grouping, duplicate or inconsistent timestamps and unmapped selected labels. The generated intervals are evaluation windows, not human-annotated event durations. Validate and freeze the actual policy and match grouping before real scoring. Legacy labels without the pre-inference hash remain explicitly ineligible.

Raw responses, parsed reports, errors, immutable attempt archives, primary seals and posthoc audit files stay private. Failed requests and abstentions remain in request denominators. Report event/time matching separately from unsupported details, identity, replay, field coordinates, retrieval relevance, calibration and coach usefulness. An empty event report requires explicit abstention under the current frozen schema; the harness does not yet represent a separately verified empty-background success.

## Official SoccerMaster path and smallest next step

prototype/soccermaster_preflight.py checks pinned source snapshot bytes, local machine/package metadata and caller-supplied asset hashes. It verifies separate scope-bound rights, license and computation records, while explicitly not authenticating an issuer. Its adapter hashes exactly thirty 512x512 RGB uint8 frames on a declared uniform plan. It does not decode/redact footage, normalize official tensors or invoke an official callable. Raw embeddings/logits require exact provenance and a verified ordered ontology; rich coach reports cannot be substituted for encoder output.

The current official source/checkpoint artifacts were not supplied and the selected environment lacks PyTorch and Transformers. Code/license review, media rights, model artifacts, verified callable/normalization and the 23-versus-24-class mapping remain open. There is no model acquisition or inference transport in this module. GPU peak memory and cold latency are unmeasured; two 8 GiB GPUs do not prove fit. Pretraining reproduction remains outside local scope.

The smallest next executable unit is an authorized, hash-pinned official source/config bundle and dependency import contract, followed by a one-clip bounded development call only when the retained rights/license/compute evidence permits it. Existing native public-wheel acquisition has a 50 MiB object limit; it does not authorize a GitHub/Hugging Face or checkpoint workaround. No restricted media or checkpoint should be downloaded to complete this package.

## Demo and coach decision

Use the versioned coach-discovery candidate for exactly five clip hypotheses, five interaction modes, workflow questions, scope rubric and five-minute script. Text search and evidence routes are implemented; example/sketch/conversational interactions remain partial or design concepts as labeled. Ask for a permissioned workflow/export and independently reviewed evidence before selecting soccer, football, a split demo or a multisport program.

The September 13 literal and local query-model rehearsals each passed 23 systems checks. Two query-model responses still expanded queries into unrelated event types. These passes demonstrate execution and evidence routing, not faithful query interpretation or correct soccer events. The long-form wrappers currently hard-code latency_ms=0; model latency was not measured and remains an audit repair. No new visual inference, training or independent human semantic annotation occurred.

## Promotion and audit

All new material remains internal and unpromoted. Review the exact candidate and hash index, obtain independent Luna review, resolve material defects, then have Terra inspect and dispatch the exact promotion. External sharing/publication and all other protected actions retain their existing authorization. The separately assigned auditor owns its report and subsequent accepted corrections after explicit file-ownership handoff.

## Historical official-source pins

The preflight config binds six historical snapshot/capture pairs under artifacts/research-loop-agenda-20260906/sources/. Their complete hashes and byte-count checks are in the preflight receipt. The recorded repository revision is 2e5619712d93f634b841aaf37231cd9fceb6b262; it is a source revision, not a checkpoint digest.

Primary surfaces: [official project](https://haolinyang-hlyang.github.io/SoccerMaster/), [paper](https://arxiv.org/abs/2512.11016), [repository](https://github.com/haolinyang-hlyang/SoccerMaster), [checkpoint host](https://huggingface.co/xleprime/SoccerMaster). September 13 project/paper source-watch identities are retained separately in runtime-observation.json; no new repository or checkpoint availability claim follows from those checks.

The pinned Hugging Face tree snapshot advertises:

| Artifact | Bytes | Upstream advertised SHA-256 |
| --- | ---: | --- |
| backbone.pt | 1,435,246,749 | d8a8932d844cc2756277ec485e36615b1196f1ad747240edb46b77e870fd9660 |
| CaptionClassification.pt | 100,892,440 | bee4abe25ae16861f757c69b643cfe859aed9ca2d45145ce12e39979d967d604 |
| VideoCaption.pt | 1,526 | 2031ec462b8b485a2e85254fd463c403d7d8aacd89567d100943bb092b808c3b |

These are upstream advertised file identities, not hashes of locally acquired weights. The smallest candidate is backbone plus event head; SigLIP configuration, official imports and the exact ontology still need verification. The tiny caption artifact is not evidence of an executable commentary model. The historical model card declares Apache-2.0, while repository-code and video rights were separately unresolved; public visibility is not acceptance or reuse authority.
