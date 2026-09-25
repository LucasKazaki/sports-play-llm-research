# Reproduction and gated execution — v1, 13 September 2026

**SYSTEMS GO / SEMANTIC NO-GO.**

Internal, unpromoted runbook. Use the existing Company Runtime native executor `sports-play-llm-project-executor`, workflow `project-execution` v1, action scope `project_execution`, browser false. Submit executable/argument arrays, `timeoutMs:0`, and the exact project workspace. No second scheduler or retained-job replay. “NEW_*” below means a previously unused output directory for a distinct justified run.

## Locally executable checks

```text
.venv-soccernet/Scripts/python.exe -m pytest -q tests/test_evaluation_design_gate.py tests/test_hosted_video_benchmark.py tests/test_hosted_video_scoring.py tests/test_hosted_video_label_conversion.py tests/test_soccermaster_preflight.py
.venv-soccernet/Scripts/python.exe prototype/evaluation_design_gate.py --manifest research/fixtures/evaluation-design-unenrolled-v1.json --output artifacts/NEW_DESIGN_CHECK.json
.venv-soccernet/Scripts/python.exe prototype/soccermaster_preflight.py --output artifacts/NEW_PREFLIGHT.json
.venv-soccernet/Scripts/python.exe scripts/verify-master-package.py --out artifacts/NEW_VERIFICATION
```

The unenrolled design check deliberately exits 2/BLOCKED. The official preflight can exit 0/BLOCKED because inventory succeeded. Neither is inference authority. Full verification runs doctor, reproduce, verify, smoke-test, collect-logs and preview-only safe-reset, then a finite literal-mode demo. Read the JSON and complete logs. Zero exit is not scientific validity.

To exercise end-to-end fixture generation, use `scripts/reproduce-hosted-video-scoring.py --private-out data/private/NEW_SYNTHETIC_RUN`. Its color screens and invented responses remain fixtures. To rescore an existing sealed run without media/model access use `prototype/hosted_video_scoring.py --run-dir data/private/SEALED_RUN --output data/private/NEW_SCORE/score.json`. To convert approved frozen point labels use `prototype/hosted_video_label_conversion.py --annotations SOURCE_LABELS.json --config FROZEN_CONFIG.json --private-out data/private/NEW_CONVERSION`. Read the exact schema in that module; never infer a timing policy from test results.

## Design manifest contract

Create a separate private design manifest containing schema_version `playground-evaluation-design-v1`, evidence_kind `real_candidate`, clips, development_group_ids and evidence. Each clip has clip_id, group_id (original match including all derivatives), source_sha256 and split (development/validation/test). The test collection must contain 6–15 clips. Hash identities detect byte duplicates; renamed or recut content needs a human history/derivative map. This design manifest is NOT the hosted benchmark input manifest.

The six evidence roles are rights_scope, annotation_protocol, independent_review, adjudication_plan, history_overlap_audit and frozen_analysis_plan. Each points to an existing relative file with exact SHA-256. Paths resolve under the manifest directory. Missing/tampered files and cross-split groups fail. PASS_STRUCTURAL_ONLY does not authenticate documents, verify consent/independence, or authorize scientific claims. A reviewer still inspects actual content and scope. Empty/unassigned slots cannot pass.

## Gemini: executable next step after actual gates

First bind six or more actual clips in the hosted harness's existing manifest, with silent-input probes, exact source hashes, local rights and third-party processor scope. Bind independent label digests before inference. The user-established remote budget is zero spend: a paid path requires separate authorization, not a silent fallback. Record a currently verified model/version and input sampling behavior at execution time; the historical default is not a guarantee of current availability.

Run `prototype/hosted_video_benchmark.py --manifest ACTUAL_MANIFEST.json --private-out data/private/NEW_DRY_RUN --provider gemini --model EXACT_MODEL --dry-run` first. No real manifest, approved third-party clip set or credential is supplied here. The later real call uses the same reviewed contract and explicit `--execute-remote` only after processor/credential/budget evidence exists. Never open held-out labels before sealing primary output. Inspect `--help` and provider guard output before actual use. Do not infer authorization from a fabricated receipt.

## Official SoccerMaster: staged boundary

1. Bind approval already granted for local installation to the exact source/assets/compute scope; do not ask for that approval again. Separately resolve code/model/media terms and acquire only through an authorized broker or manually supplied bundle. The current public-wheel broker's 50 MiB scope cannot provision the large checkpoints or arbitrary GitHub source.
2. Inventory supplied source/config/backbone/event-head files and actual SHA-256, compare historical advertised identities, and inspect code/license. A repository revision is not a weight digest.
3. In a compatible isolated environment, verify imports only; record Python, CUDA, PyTorch, Transformers and platform. The public README's broader installation recipe is not a tested minimal Windows environment.
4. Read the pinned official callable and preprocessing. Confirm channel order, shape, dtype, temporal sampling and exact normalization from source; reconcile 23/24 output classes including background. The local thirty-frame adapter is a proposed boundary, not proof of official preprocessing parity.
5. On a permitted development clip only, implement/invoke transport and preserve raw embeddings/logits, model/source/config/input hashes, ordered ontology, finite-value/shape checks, cold/warm timing and measured peak VRAM/RAM. Stop on OOM; do not silently change representation or model.
6. Only then compare the same frozen test clips under an unchanged evaluation definition. Narrative claims, tracks, calibration and player identity need their own validated heads and evidence. A valid encoder output alone proves none of them.

Historical advertised backbone and event-head sizes are 1,435,246,749 and 100,892,440 bytes. Thirty RGB uint8 512×512 frames require 23,592,960 input bytes; FP32 requires 94,371,840 bytes before weights/activations. Two 8 GiB GPUs do not prove fit. Exact 15 inventory reasons remain in [audit preflight](../../artifacts/soccermaster-audit-20260913/preflight-independent-readback.json). No checkpoint, source bundle, dependency or license was acquired by this package.

## Evidence and release

Native inspection copies are under `.agent-runtime/jobs/JOB_ID/`; authority is the corresponding Company Runtime manifest/receipt and original log hashes. The package index binds exact bytes and lists historical mismatches rather than rewriting history. Source watch, native execution, structural fixtures, semantic labels and human studies are separate evidence classes.

Before promotion: independent Luna reviews the exact candidate and receipts; material defects are resolved in a versioned supplement; Terra inspects that verdict and dispatches exact promotion. Public release also needs author/license/privacy review and explicit external-release authority. The existing Google Doc schedule remains PAUSED. No change here enables uploads, contacts, credentials, paid APIs or external publication.

## Design-contract clarification after independent review

In the design manifest, source_sha256 identifies the exact model-input clip file bytes, after the declared extraction procedure; group_id identifies the original match and all its derivatives. Repeated input bytes in the test split fail, even under different clip/group IDs. Distinct encodes of the same moment still require the human derivative audit. Six clips can come from one test match only for descriptive feasibility, never six independent observations. Development/validation rows are optional in this feasibility checker; the future controlled study must supply the separately frozen development/validation design. One reviewed evidence packet may serve multiple roles if it explicitly addresses each role; hash equality alone proves neither adequacy nor independent authorship.
