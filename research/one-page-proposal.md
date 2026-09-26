# One-Page Lab Proposal

## PlayGround: Evidence-Grounded Reasoning over Short Soccer Plays

### Motivation
Coaches need to retrieve and explain 5–10 second soccer plays using natural-language questions, not only event labels. A useful system must answer correctly, point to the decisive frames/regions/trajectories, know when evidence is insufficient, and operate quickly enough for halftime use.

### Research question
Do retrieval and structured soccer tools improve **grounded correctness** and calibration over a direct VLM on short plays?

### Hypotheses
- H1: direct VLMs can answer broad event questions but degrade on temporal order, identity, trajectory, and counterfactual questions.
- H2: retrieval improves event recognition but may not improve spatial evidence.
- H3: explicit tracking, pitch homography, and structured game state improve evidence correctness on spatial/trajectory questions.
- H4: abstention training/evaluation reduces confident unsupported answers.

### Pilot protocol
1. Obtain explicit lab authorization for a lawful video source.
2. Select 50 clips, 5–10 seconds each; define splits by match/source to prevent leakage.
3. Create 3–5 questions per clip across event, temporal order, entity, pitch/trajectory, and counterfactual types.
4. Annotate answer, decisive timestamps/frames, region or trajectory, difficulty, ambiguity, and unanswerable cases.
5. Compare: direct VLM; retrieval-augmented VLM; tool-augmented VLM; optional fine-tuning only after baselines.
6. Report answer accuracy/F1, temporal IoU/hit, spatial/trajectory agreement, evidence-conditioned correctness, ECE/Brier/selective risk, retrieval quality, latency, and compute.
7. Run distractor/evidence-swap tests to detect shortcut answers.

### Deliverables
- Data card and annotation guide for the authorized pilot.
- Versioned evaluation harness and per-example outputs.
- Controlled baseline/ablation table.
- Failure taxonomy and qualitative grounded examples.
- Paper draft separating reported prior-work claims, hypotheses, synthetic plumbing tests, and real-data results.

### Novelty boundary
SoccerLens already studies attribution grounding for soccer event classifiers. PlayGround is viable only if it focuses on answer-conditioned explicit evidence, short-play temporal/trajectory reasoning, calibrated abstention, and controlled direct-vs-retrieval-vs-tool comparisons. This remains a hypothesis until adjacent work is fully verified.

### Two-week gate
Proceed toward a paper only if the pilot has an authorized source, annotation agreement, a reproducible baseline, and at least one meaningful failure mode or tool benefit. Otherwise narrow the question or pivot before scaling.
