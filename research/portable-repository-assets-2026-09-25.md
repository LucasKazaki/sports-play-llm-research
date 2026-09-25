# Portable repository and model inventory

**Inventory date:** 2026-09-25  
**Scope:** source, documentation, research, and model files in the local Sports Play LLM Research project. This records what a Git checkout can reproduce and why locally generated weights or data are not copied into the source tree.

## What a repository checkout contains

The project keeps first-party research, source, tests, and safe provenance records in Git, including the standalone first-party `footballmaster/` source package. On Windows with Python 3.11, run `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1`, then `scripts/portable-doctor.ps1` and `scripts/reproduce.ps1`. The Python lock file is `requirements-windows-py311.lock.txt`. The project’s GitHub mirror audit is `scripts/github_sync_audit.py`; it checks UTF-8 text candidates for recognized secret signatures and keeps runtime state, generated artifacts, private data, and raw media out of the mirror. `scripts/github_sync.ps1` uses that list as its only staging scope.

The mirror is not a snapshot of the workstation. A fresh checkout cannot contain the Studio runtime, virtual environment, licensed/private footage, generated run output, or a locally installed foundation model. Research claims and reproduction steps must state when one of those is required.

## Model files found locally

| Asset | Local state | Portability decision |
| --- | --- | --- |
| ONNX Model Zoo MobileNetV2-1.0-fp32 opset 12 | Two identical 13,964,571-byte local copies; SHA-256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5` | Third-party ImageNet backbone, not trained by this project. The upstream [MobileNet README at commit `4c46cd00`](https://github.com/onnx/models/blob/4c46cd00fbdb7cd30b6c1c17ab54f2e1f4f7b177/validated/vision/classification/mobilenet/README.md) identifies Apache-2.0. One binary copy is attached to the private [draft asset release](https://github.com/LucasKazaki/sports-play-llm-research/releases/tag/untagged-af5fdfd6c361b6df0984); its SHA-256 matches the upstream Git LFS object ID. The draft remains unpublished; the full upstream license is included at `third_party/ONNX-MODEL-ZOO-APACHE-2.0-LICENSE.txt` on the review branch. Reacquire and verify from the project root with `python -m footballmaster acquire-backbone --out artifacts/footballmaster/backbones/mobilenetv2-12.onnx --expected-sha256 c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`. |
| FootballMaster-Pilot-v1 fitted checkpoint | `footballmaster-pilot-v1.npz`, 111,336 bytes; SHA-256 `8af37f3030829be110e6e05fff2377f40b24a3aa61fdfb7a44cc453dc0b2b79c` | Locally trained research output. Its model card says local research only and requires a separate model-output rights review before publication. It is not included in the Git mirror pending that review. |
| SoccerMaster-Scale-v1 fitted checkpoint | `checkpoint.npz`, 52,971 bytes; SHA-256 `182ff4e8cc05e615cfdc9018074b07289457c4781dcfd6bc29599932e50fcacc` | Trained on the SoccerNet corpus covered by user-authorized NDA access. Its corpus receipt marks redistribution disallowed and raw media private. Do not copy the checkpoint, input data, or package outputs to GitHub. |
| FootballMaster weak visual probe | `weak-visual-probe.npz`, 37,085 bytes; SHA-256 `0cb4eacab5a4d387a2dd1f979c277220dac45bb0e8e266400f4116e4013cd64c` | Derived experiment artifact, not a distributable model package. Keep with local generated artifacts. |
| Local VLM used in a FootballMaster experiment | `google/gemma-4-e4b`, approximately 5,319,465,128 bytes in the local runtime record | Third-party model installed outside this project. The repository records the model identifier and experiment boundary; each machine must obtain weights through an authorized model-distribution channel and follow that model’s terms. |

The FootballMaster pilot is a tiny source-held-out binary touchdown probe; it does not support general football-understanding or coach-readiness claims. The SoccerMaster-Scale checkpoint is based on restricted SoccerNet footage. Neither is a general sports LLM checkpoint. No fine-tuned `.pt`, `.pth`, `.safetensors`, or `.gguf` model checkpoint for this project was found in either local project copy.

## Reproduce the shareable backbone dependency

The first-party FootballMaster package includes the acquisition and validation implementation in `footballmaster/pipeline.py`. From the repository root, run `scripts/bootstrap.ps1` to install the pinned project dependencies, then run:

```powershell
python -m footballmaster acquire-backbone --out artifacts/footballmaster/backbones/mobilenetv2-12.onnx --expected-sha256 c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5
```

This obtains the third-party backbone from the upstream ONNX Model Zoo and checks the expected SHA-256. The `.onnx` file remains excluded from Git source history; a verified copy is staged in the private draft asset release linked above. The draft release must be approved and published before it can serve as a normal cross-machine download source. Research using private SoccerNet media also requires a separately authorized local copy and cannot be reproduced from GitHub alone.
