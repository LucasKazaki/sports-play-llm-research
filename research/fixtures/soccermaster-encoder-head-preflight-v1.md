# INTERNAL DESIGN UNREVIEWED

## SoccerMaster Encoder and Head Dependency Preflight

### Overview
This document provides a preflight analysis of the SoccerMaster encoder and head dependencies, based on the official README (SHA256: 9924dafc723a6dd7899869c222922dcaadc3c790fa397d6f07d60cf2e9e7db67, captured 2026-09-07T04:11:45Z) and specified runtime requirements.

### Dependencies listed by the full README setup
- Python: 3.10.16
- PyTorch: 2.4.1, torchvision: 0.19.1, torchaudio: 2.4.1 (CUDA 12.1)
- setuptools: 78.1.1
- Editable installs: sn-gamestate, tracklab, sam2
- albumentations: 1.4.19
- Transformers: Git HEAD (unpinned)
- accelerate: 1.8.1
- qwen-vl-utils[decord]: 0.0.8
- flash-attn: included in the README installation commands; necessity for a minimal encoder/head import remains unresolved

### Asset Dependencies
| Asset | Type | Status | Notes |
|-------|------|--------|-------|
| SigLIP2 | Backbone | Unresolved | Requires import inspection |
| SoccerMaster checkpoints | Model | Unresolved | HF repository revision 0d94573662dbd678df22aa5c61ae77f474b939c9; this is not a checkpoint-file SHA256. Model-card metadata reports Apache-2.0; applicability requires separate review. |
| Calibration/ReID | Utility | Unresolved | Requires validation |
| YOLO | Detection | Unresolved | Role in encoder not specified |
| Legibility | Post-processing | Unresolved | Functionality not defined |
| Qwen2.5-VL72B/7B | Vision-Language | Unresolved | Assets listed but no defined role |

### Input Shape & Performance
- Input: 30 frames, 512x512 resolution
- Backbone size: 1.44GB (does not imply fits 8GB GPU)
- Warm/cold latency and peak GPU memory allocation not measured

### Critical Dependencies
- All assets are listed in the README but their exact role in encoder vs. head is not specified.
- No runnable entry point was established in this bounded source inspection; this is a preflight plan only.
- Zero-spend authorization and code, model and media permissions are separate checks. GitHub API `license: null` is a metadata observation, not a complete legal determination.

### Fail-Closed Conditions
- Missing scope/identity
- Incompatible pinned runtime
- Resource breach (e.g., GPU memory exceeding 8GB)

### Next Steps
- Conduct independent import inspection for all listed assets.
- Verify checkpoint hashes and media permissions.
- Measure warm/cold latency and peak GPU memory usage.
- Confirm role of each component in encoder vs. head.
- Pin an exact Transformers revision and all runtime versions before any authorized test. Record cold/warm latency and peak allocated/reserved GPU memory later; none has been measured here.
- If the measured encoder/head fails its approved resource budget, retain that failure and continue the viable baseline. Never silently substitute a scaffold and call it SoccerMaster.

*Source: https://raw.githubusercontent.com/haolinyang-hlyang/SoccerMaster/main/README.md (SHA256: 9924dafc723a6dd7899869c222922dcaadc3c790fa397d6f07d60cf2e9e7db67)*

Source snapshot: `artifacts/research-loop-agenda-20260906/sources/soccermaster-readme.txt` and its `.receipt.json`. These are executor-captured public-text snapshots, not Company Runtime browser receipts. No dependency installation, checkpoint download, media acquisition or model execution occurred.

> This document remains INTERNAL DESIGN UNREVIEWED and is not to be promoted without independent Luna QA and Terra director inspection.
