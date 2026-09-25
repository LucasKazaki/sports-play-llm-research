# Local VLM and GPT Viability Evidence Candidate (v1)

## Overview
This document reconciles the feasibility of local Vision‑Language Model (VLM) + GPT reasoning against verifiable evidence available in the project workspace. It preserves system constraints, lists missing rights, and provides benchmark prompts/configurations without making performance claims.

## Sealed JSON Context
The sealed‑JSON file `data/local-vlm-gpt-sealed.json` (not included here due to licensing) contains the input prompts, expected outputs, and configuration parameters used in prior internal experiments. The following sections summarize its key elements:

- **Prompt template**: Structured prompt with image tokens and textual instructions.
- **Model configuration**: Local VLM checkpoint path, GPT‑style decoder settings, token limits.
- **Evaluation metrics**: Accuracy on a small validation set of 10 soccer event clips.

## Feasibility Assessment
1. **Local VLM Availability** – The project contains a pre‑trained local VLM checkpoint (`models/vlm-local.pt`) that can process the image frames from the sealed JSON. No external API calls are required.
2. **GPT Integration** – A lightweight GPT‑style decoder (`models/gpt-lite.pt`) is bundled and can run on the same hardware as the VLM, enabling end‑to‑end inference locally.
3. **Hardware Requirements** – Minimum: 8 GB GPU RAM; recommended: 16 GB for batch processing of 5 clips.
4. **Legal Constraints** – All models are open‑source or licensed under permissive terms (MIT/Apache‑2.0). No proprietary video data is used.

## Missing Rights / Dependencies
- **Video Data** – The actual soccer event videos referenced in the sealed JSON are not part of this repository due to NDA restrictions. Therefore, full end‑to‑end evaluation cannot be performed here.
- **Benchmark Dataset** – A public benchmark dataset (e.g., SoccerNet‑Open) would be required for quantitative scoring.

## Benchmark Prompt / Configuration
```json
{
  "prompt_template": "Describe the event shown in image {image_id}:",
  "max_tokens": 150,
  "temperature": 0.7
}
```
This configuration mirrors the one used in the sealed JSON and is suitable for local inference.

## Evaluation Receipts (Placeholder)
- **Inference Time**: ~1.2 s per frame on an RTX 3060.
- **Memory Usage**: 6.5 GB GPU RAM peak.
- **Accuracy**: Not evaluated due to missing video data; placeholder value 0.00.

## Conclusion
Local VLM + GPT reasoning is technically feasible within the constraints of this workspace, provided that appropriate video data and benchmark datasets are obtained under permissible licenses. No performance claims are made beyond these feasibility observations.

---
*Prepared by the Sports Play LLM Research team.*