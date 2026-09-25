# FootballMaster-Pilot v1: trained American-football representation probe

Status: **trained and source-held-out tested; systems artifact ready; scientific performance claim not allowed**  
Final package generation: `3eb10b5935ca0649f5b6222e`  
Run time: 6.766 seconds on CPU; no GPU, hosted API, or paid service used.

## Result first

FootballMaster-Pilot v1 is a real trained model, but it is intentionally much smaller than SoccerMaster. It learned one defensible binary target—whether a weakly labeled clip is a touchdown—from nine rights-audited real American-football clips. Entire source videos/sessions, not neighboring windows, define the train/validation/test split.

On the three source-held-out test clips, the pilot classified 2/3 correctly:

| Measure | FootballMaster-Pilot | Train-majority baseline |
|---|---:|---:|
| Accuracy | 0.667 (2/3) | 0.333 (1/3) |
| Balanced accuracy | 0.750 | 0.500 |
| Macro F1 | 0.667 | 0.250 |
| Accuracy Wilson 95% interval | 0.208–0.939 | 0.061–0.792 |

This is descriptive pilot evidence, not an estimate of deployment performance. The interval is extremely wide, labels come from source descriptions rather than independent football annotators, one test negative is minicamp practice footage, and the classifier made a high-confidence error. The package therefore sets `performance_claim_allowed` to `false`.

## What was actually trained

```text
real rights-approved clip (pixels only; audio excluded)
             |
       8 uniform frames
             |
frozen ONNX MobileNetV2 / ImageNet, 1,000 scores per frame
             |
fixed temporal pooling: mean + standard deviation + last-minus-first
             |
3,000-dimensional clip descriptor
             |
train-only standardization + 3-component PCA
             |
trained 2-class softmax linear head
             |
touchdown / not_touchdown + uncalibrated score
```

Parameter and state attribution:

| Component | Count | Origin | Updated here? |
|---|---:|---|---|
| MobileNetV2 ONNX file | 13,964,571 bytes | ONNX Model Zoo, ImageNet pretraining | No; frozen |
| Feature mean and scale | 6,000 statistics | Fitted on four training clips only | Fitted, not supervised parameters |
| PCA components | 9,000 coefficients | Fitted on four training clips only | Yes, unsupervised fitted representation |
| Softmax weights and bias | 8 parameters | Optimized from touchdown labels | Yes, supervised |
| Defined learned parameter total | 9,008 | PCA components + softmax parameters | Yes |
| Total persisted fitted numeric state | 15,008 | Statistics + PCA + head | Yes |

The [official ONNX MobileNet documentation](https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet) states that this model is an ImageNet 1,000-class image classifier, specifies RGB/224×224/ImageNet normalization, and licenses the model repository under Apache-2.0. Its inherited weights are not football-specific. This project uses the 1,000 output scores as frozen frame descriptors; it does not claim to have retrained the backbone.

## How this differs from SoccerMaster

SoccerMaster is a large soccer-specific spatial/semantic video encoder trained on millions of frames with many GPUs and several downstream heads. FootballMaster-Pilot is a CPU proof of the local data, representation, evaluation, checkpoint, and search plumbing:

- SoccerMaster-scale claim: **no**.
- New football foundation model: **no**.
- Actual fitted parameters: **yes**—train-only PCA plus an eight-parameter supervised head.
- Detailed football understanding: **no**—the evaluated model learns only `is_touchdown`.
- Fine tags such as `touchdown_pass`, `rushing_touchdown`, `kickoff_return`, `field_goal_attempt`, and `interception_practice`: **source-description metadata only**, not classifier outputs.
- Player identity, formation, coverage, route, blocking, pressure, tackle, down/distance, field zone, and temporal evidence: **not produced**.

The research value is the controlled comparison point. Future football VLM or sport-specific encoders can plug into the same rights gate, source split, event-report schema, and search UI without pretending that deterministic indexing or weak metadata are learned football reasoning.

## Data and split integrity

The dataset contains nine Wikimedia Commons derivatives (21.94 MiB, 151.89 seconds) from eight source groups. Every record has its source page, license evidence, access metadata, media hash, local-training disposition, redistribution conditions, and explicit `audio_in_model: false` flag.

| Split | Clips | Source groups | Not touchdown | Touchdown |
|---|---:|---:|---:|---:|
| Train | 4 | 3 | 2 | 2 |
| Validation | 2 | 2 | 1 | 1 |
| Test | 3 | 3 | 1 | 2 |

The Milton touchdown and UCF kickoff are from the same FAU–UCF game and stay together in training. No `source_id` appears in two splits. The independent data verifier passed one-to-one manifest binding, required fields, rights gates, path existence, unique/matching hashes, full FFmpeg decode, source isolation, class presence, visual-only input, and explicit weak-label status.

The manifest is a conservative research admission record, not legal advice. Although each clip has a public-domain or Creative Commons reuse basis, release of model weights remains on hold pending institutional review of ShareAlike, publicity, trademark, and jurisdiction-specific ML questions.

## Per-test example audit

| Test source | Weak source label | Prediction | Score for predicted class | Result |
|---|---|---|---:|---|
| Chiefs–Buccaneers 2024 | touchdown pass | not touchdown | 0.949 | **wrong** |
| Falcons minicamp 2018 | interception practice | not touchdown | 0.9996 | correct, but practice-domain negative |
| SMU–Louisville 2025 | touchdown pass | touchdown | 0.942 | correct |

The Chiefs–Buccaneers miss is the most informative result. A wrong prediction at 0.949 shows that the softmax score is not calibrated and that four training clips cannot support trust. The UI should foreground this failure rather than showcase only the correct SMU result.

Confusion matrix, rows actual and columns predicted:

|  | Predicted not touchdown | Predicted touchdown |
|---|---:|---:|
| Actual not touchdown | 1 | 0 |
| Actual touchdown | 1 | 1 |

## Search/UI integration contract

The package includes a nine-window `search-index.sqlite3`, `index-plan.json`, and `run-receipt.json`. Each event record uses the shared renderer keys:

- `event_types`, `primary_action`, `phase_of_play`, `field_areas`, and `outcome`;
- `detailed_description`, `coaching_relevance`, `coaching_tags`, and `retrieval_keywords`;
- `uncertainty`, `participants`, and `evidence_frames`.

These keys do **not** imply a detailed VLM result. Each record declares:

- learned fields: binary prediction, two softmax scores, three-dimensional embedding;
- source metadata: fine event tag and reference target;
- deterministic fields: clip window, plain-language projection, SQLite/FTS indexing;
- VLM fields: none; `participants` and `evidence_frames` are empty.

This lets the dual-sport GUI render and search the pilot now while preserving a clean upgrade path: a future football VLM can add genuinely video-authored event cards, and the coarse probe can act as a candidate generator or reranking feature. Those conditions must be evaluated separately.

## Reproduction commands

From `C:\AI\projects\SportsPlayLLMResearch` in PowerShell:

```powershell
& .\.venv-soccernet\Scripts\python.exe .\data\public\footballmaster\verify_manifest.py

& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py acquire-backbone `
  --expected-sha256 c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5

& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py train `
  --out .\artifacts\footballmaster\pilot-v1-reproduction `
  --frames 8 --pca-components 16 --epochs 500 --learning-rate 0.05 --l2 0.1

& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py verify `
  --model-dir .\artifacts\footballmaster\pilot-v1-reproduction
```

Do not add `--replace` when independently reproducing; use a new output directory so a prior generation remains immutable.

## Final artifact map and immutable bindings

- Data source record: `data/public/footballmaster/source-manifest.json`
- Example manifest: `data/public/footballmaster/examples.jsonl`
- Independent data receipt: `data/public/footballmaster/verification-receipt.json`
- Implementation: `prototype/footballmaster_pilot.py`
- Focused tests: `tests/test_footballmaster_pilot.py`
- Backbone receipt: `artifacts/footballmaster/backbones/mobilenetv2-12.onnx.receipt.json`
- Trained package: `artifacts/footballmaster/pilot-v1/`
- Checkpoint: `footballmaster-pilot-v1.npz`
- Metrics and predictions: `metrics.json`, `predictions.jsonl`
- Training trace: `training-log.jsonl`
- Search package: `search-index.sqlite3`, `index-plan.json`
- Model/run truth boundary: `model-card.json`, `run-receipt.json`

Final generation `3eb10b5935ca0649f5b6222e` bindings:

- backbone SHA-256: `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`
- checkpoint SHA-256: `8af37f3030829be110e6e05fff2377f40b24a3aa61fdfb7a44cc453dc0b2b79c`
- examples SHA-256: `edba3a179de6315db7cda4265ab73c7a68067e8907376ac581625393642852e6`
- source manifest SHA-256: `0b6a40158455b96f357a74933748f457b0ef3d02d1ec174378169df9d7c98cf9`
- metrics SHA-256: `e390b40e519ce10aff3c2c7d20a14a95dd8ecd474beb5e735961b9e140ad2559`
- SQLite index SHA-256: `02fa5e0085c4fb8aabf34741a29146958465e42f40d769964010c762eb0c6b65`

## What a UMD coach could evaluate next

The current binary model is not the coach-facing product. It is the controlled lower layer for testing a larger workflow:

1. Ask a coach for five retrieval questions that matter in film study, without promising any event taxonomy.
2. Independently annotate whole source-held-out clips for visible evidence and “not answerable from this angle.”
3. Compare direct VLM reports, football-adapted representations, and the frozen-backbone probe as candidate/reranking conditions.
4. Measure event retrieval, evidence timestamps, abstention, and coach judgment—not only clip labels.
5. Keep audio/commentary post hoc so it can audit visual output without leaking answers into the primary model.

The responsible pitch is: “We have a reproducible dual-sport research and demo scaffold, a real small football checkpoint, and an explicit high-confidence failure. We want coaches to help define the questions and evidence needed before we scale data or claim utility.”
