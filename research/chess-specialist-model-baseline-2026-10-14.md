# Chess-specialist model baseline and integration plan

**Snapshot date:** 2026-10-14
**Repository status:** research and harness integrated; specialist candidates not yet executed
**Current release decision:** **NO-GO for claims of professional chess understanding**

## Decision

The production research route should be **chess-specialist first**, with the existing general-purpose model retained only as a control. This matches the project goal better than copying the GothamChess exhibitions: those videos are useful evidence that general language models can sometimes sustain coherent chess, but they do not establish calibrated strength, reliable board tracking, or faithful explanation.

Specialization is still a hypothesis to test, not an automatic pass. A model can be trained on chess and remain poor at one or more of the capabilities this project needs:

- a move-policy model can choose plausible moves but produce no useful language;
- a language model can recite chess vocabulary while losing track of the position;
- a model trained on synthetic engine rationales can emit convincing explanations that are not causally faithful;
- a human-move model can imitate players well without finding best moves;
- a legality mask can hide the model's raw board-state errors.

The preferred architecture hypothesis is therefore a verified hybrid: deterministic state handling and engine or specialist-policy evidence, followed by a chess-language generator operating under the existing no-forward-input boundary and an independent factuality verifier.

## What the recent GothamChess videos contribute

The source index is `research/gothamchess-ai-agent-discovery-2026-10-14.json`. It records the three recent videos inspected for this update:

1. `GPT-6, GPT-6.1, ORION 1 & KURO 4.7 FIGHT FOR THE TITLE!` (2026-10-14)
2. `GPT-6.1 IS PROBABLY THE BEST CHESS AI EVER` (2026-10-11)
3. `GPT-6.1 VS GPT-6 ASTRA: CHESS AI FIGHT FOR GLORY` (2026-10-07)

The useful baseline is qualitative:

- general-purpose frontier agents can produce stretches of legal, tactically relevant, and strategically coherent play;
- single exhibition games cannot separate memorized opening familiarity, board-state tracking, move selection, interface scaffolding, and editing effects;
- an illegal or rejected move path is enough to show that legality and interface compliance require explicit measurement;
- informal Elo estimates are not calibrated ratings;
- the videos do not test whether an explanation is supported by the actual board or by the process that selected the move.

The videos and transcripts are not committed. Existing project policy classifies GothamChess as discovery-only unless a compatible license or permission is recorded, and `.gitignore` excludes raw media. `scripts/collect_gothamchess_metadata.py` uses `yt-dlp` only in `--skip-download --dump-single-json` mode and writes normalized metadata under ignored `data/private/`.

## Current project model: what is known

The current declared local route is `loops-cpu-gpt-oss-20b` in `research/chess-local-route-131k-v1.json`. It is a general-purpose control, not a chess-specialized checkpoint.

The repository has strong infrastructure around it:

- a snapshot-bound local-route attestation;
- strict no-forward-input generation packets;
- output validation and counterfactual checks;
- a harder-cohort protocol;
- a commentary capability gate that separates factuality, evidence coverage, abstention, latency, and failure rate.

What the repository does **not** yet contain is a completed, held-out comparison proving that the current general model or any specialist model understands chess to the required standard. A route attestation proves which model was loaded; it does not prove chess competence. The correct present assessment is therefore **unestablished**, not “good” or “bad.”

## Candidate model stack

The machine-readable registry is `research/chess-specialist-model-registry-v1.json`.

| Candidate | Primary role | Why it is relevant | Main risk |
|---|---|---|---|
| Existing GPT-OSS 20B route | General control and language baseline | Quantifies the gain from specialization | No recorded chess-specific training |
| ROOK-CLF-9M | Small move-policy baseline | Cheap raw policy and legality comparison | Not a commentary model |
| ROOK-LM-124M | Chess move and reasoning-language candidate | Small, public, trained on chess and synthetic Stockfish reasoning | Synthetic rationales may be fluent but unfaithful |
| RookWorld-LM-124M | Policy plus chess world model | Directly tests state transition and long-horizon drift | World simulation quality is not commentary quality |
| ChessGPT | Joint policy-language research route | Closely matches the move-plus-language objective | Packaging, licensing, and reproducibility need review |
| Maia-3 5M | Human-move comparator | Measures human-likeness separately from engine optimality | Human prediction is not best-move analysis |

No candidate is marked production-ready. Upstream metrics remain upstream claims until this repository reproduces them.

## Evaluation design

`research/chess-specialist-benchmark-plan-v1.json` turns the model-selection decision into a staged protocol.

### 1. Provenance and runtime

Record the immutable model revision or hash, license disposition, dependencies, quantization, hardware, context size, and route attestation. A model that cannot be reproduced or lawfully redistributed can still be studied locally, but it cannot silently become the project default.

### 2. Diagnostic chess understanding

Run ChessQA across FEN, ASCII-board, and piece-list representations. Report structural, motif, short-tactics, position-judgment, and semantic categories separately, plus protocol compliance. This detects models that score well only because one representation or task family suits their tokenizer.

### 3. Raw legality and board state

Measure raw illegal-move rate before any legality mask. Then measure legality-masked quality separately. Add exact FEN-transition accuracy, multi-ply drift, and complete-game rate. This prevents an interface layer from concealing the model's own state-tracking failures.

### 4. Move quality

Against a pinned Stockfish configuration, report top-1 agreement, top-3 coverage, average centipawn loss, blunder rate, and mate conversion. Use repeated, grouped positions and cluster-aware intervals. Do not infer Elo from a few games.

### 5. No-forward commentary

Retain the current capability gate. The generator receives the current position and allowed historical context, but no principal variation, answer move, post-move state, future features, puzzle solution, or hidden label. Verify every user-visible board claim independently.

### 6. Hybrid ablation

Compare:

- specialist model alone;
- specialist plus deterministic legal-state tooling;
- specialist plus engine evidence and factual verification;
- general control with the same tools.

This identifies whether gains come from chess-specific weights, tools, or both.

## Promotion rule

A chess-specialized model replaces the general control only when all of the following are true:

1. its exact weights and runtime are reproducible;
2. license review is resolved for the intended use;
3. it improves the relevant held-out capability under matched conditions;
4. raw legality and state tracking are reported rather than hidden by a mask;
5. it passes the existing no-forward commentary gate;
6. the result survives grouped or cluster-aware uncertainty analysis;
7. the improvement is large enough to justify any added latency or operational complexity.

Until those tests run, the strongest defensible conclusion is:

> Chess-trained models are better-targeted candidates than plain frontier models for this project, but the repository has not yet measured whether they are better at the complete task of legal play, board-state understanding, move quality, and faithful commentary.

## Immediate execution order

1. Run the registry validator and retain its report.
2. License-check and smoke-test ROOK-LM-124M and ROOK-CLF-9M.
3. Add Maia-3 as the human-move comparator.
4. Pin a ChessQA revision and build representation-matched local runners.
5. Run the existing general route as the fixed control.
6. Run the specialist candidates on development positions only.
7. Freeze thresholds and model revisions before opening the held-out test set.
8. Promote only the capability or route actually supported by the evidence.

## Source map

- GothamChess video metadata and derived observations: `research/gothamchess-ai-agent-discovery-2026-10-14.json`
- Candidate registry: `research/chess-specialist-model-registry-v1.json`
- Benchmark plan: `research/chess-specialist-benchmark-plan-v1.json`
- Registry validator: `scripts/chess_specialist_registry.py`
- Safe yt-dlp metadata collector: `scripts/collect_gothamchess_metadata.py`
- Existing capability gate: `research/chess-commentary-capability-gate-v1.md`
- Existing no-forward packet receipt: `research/chess-no-forward-input-2026-09-22.md`
