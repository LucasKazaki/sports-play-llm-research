# SoccerNet-GSR vs. PlayGround — pitch-state feasibility and novelty boundary

**Iteration:** 25  
**Accessed:** 2026-08-06  
**Working interpretation:** SoccerNet Game State Reconstruction (GSR) is a near-neighbor for reconstructing athlete identity and 2D pitch position from single-camera soccer broadcast video. It is coordinate-evidence infrastructure, not a question-answering, answer-provenance, confidence, or abstention benchmark.

## Status and primary sources

- **Paper:** Vladimir Somers et al., *SoccerNet Game State Reconstruction: End-to-End Athlete Tracking and Identification on a Minimap*, arXiv:2404.11335v1, submitted 2024-04-17; CVPRW 2024. https://arxiv.org/abs/2404.11335v1
- **Official repository:** SoccerNet, `SoccerNet/sn-gamestate`. https://github.com/SoccerNet/sn-gamestate
- **Classification:** **working-open-source (inspectability only)** for the code: the public repository provides installation, data/model download, baseline execution, and evaluation instructions. The project was not installed or run here, so this is not a reproducibility claim. The dataset is **authorization-gated for this lab** until Lucas/Archit approve a source and its terms are audited.
- **Mutable repository snapshot:** GitHub API checked 2026-08-06: public, unarchived, default branch `main`, code license reported as GPL-3.0, last push `2026-05-02T09:21:50Z`. Stars/forks are omitted from ranking because popularity is not evidence of suitability.

## Claim-level comparison

| Dimension | SoccerNet-GSR (primary-source fact) | PlayGround target | Boundary / design consequence |
|---|---|---|---|
| Task | Reconstruct athletes' pitch positions and identities from a single moving broadcast camera, visualized as a minimap. | Answer fine-grained questions about 5–10 s plays with answer-linked evidence and abstention. | GSR closes novelty of game-state/minimap reconstruction; it is a candidate tool or oracle, not the headline contribution. |
| Data unit | 200 fully annotated 30-second clips, split into train/validation/test/segregated challenge sets. | Rights-cleared 5–10 s question-bearing clips with grouped splits. | The duration and evaluation unit differ. Do not equate a GSR clip with an answerable short-play QA item. |
| Spatial representation | Per-frame 2D pitch positions for visible athletes, with role, team, jersey number, and track ID; the assumed pitch is 105 × 68 m and the coordinate system is centered on the pitch center. | Answer-linked pitch regions or trajectories submitted in normalized soccer coordinates. | This supplies a concrete coordinate precedent. PlayGround should define an explicit conversion/normalization contract and retain uncertainty when calibration is invalid. |
| Annotation scale | Authors report over 9.37M pitch-line points and over 2.36M athlete pitch positions. | Small pilot with evidence annotations tied to each answer. | Scale supports technical feasibility but not annotation rights or QA provenance. Values are author-reported and unreproduced. |
| Visibility and ball | Only athletes in the camera field of view are evaluated. Some frames with insufficient pitch lines are discarded; the ball is removed because airborne 3D localization is not supported. | Explicit insufficient-evidence labels and abstention reasons. | These limitations should become benchmark validity masks and abstention causes rather than silently dropped evidence. GSR does not solve ball trajectories. |
| Evaluation | GS-HOTA matches 2D pitch points and requires correct role/team/jersey attributes; repository documentation uses a 5 m localization tolerance parameter. Full baseline test GS-HOTA is author-reported as 22.26. | Region/trajectory agreement, answer correctness, joint grounding, calibration, and selective risk. | GS-HOTA is a useful upstream tool-quality metric but cannot substitute for answer-linked spatial evidence or joint-grounded QA risk. |
| Baseline architecture | Detection/tracking, pitch localization, camera calibration, re-identification, role/team classification, and jersey-number recognition; homography converts image boxes to 2D pitch positions. | Direct VLM vs retrieval vs structured-tool variants, including oracle and noisy-tool controls. | The modular baseline motivates component-level oracle/noise ablations. The paper reports calibration/pitch localization as major weaknesses. |
| QA / evidence provenance | No question answering or answer-conditioned evidence task is defined. | Every answer references temporal and spatial support. | GSR cannot close the proposed answer-provenance contribution. |
| Confidence / abstention | No QA confidence, calibration, abstention, risk-coverage, or selective-risk endpoint is defined. Invalid calibration frames may be discarded. | Mandatory confidence and explicit abstention, including tool-invalid conditions. | Treat calibration validity as an input to abstention; do not conflate dropping invalid frames with calibrated selective prediction. |

## Highest-value design decision

Add a **game-state validity mask** to the PlayGround protocol before any real pilot:

1. report whether image-to-pitch calibration is valid for every cited frame;
2. permit pitch evidence only when that validity is established;
3. expose `camera_out_of_view`, `insufficient_pitch_lines`, `airborne_ball_3d_unsupported`, and `identity_unresolved` as candidate insufficient-evidence reasons;
4. score answer-linked regions/trajectories separately from upstream GSR quality; and
5. include oracle-vs-predicted coordinates to measure error propagation.

This preserves the north-star. It narrows the claim from “we add soccer trajectories” to “we evaluate whether answer-linked pitch evidence remains valid and useful under known reconstruction failure modes, with calibrated abstention.”

## Evidence limitations

- All dataset counts and baseline metrics are author-reported; no model, dataset, video, weights, or tracking state was downloaded or executed.
- The paper uses per-frame tracked 2D positions; a trajectory can be derived over time, but the paper does not define an answer-linked trajectory annotation or QA metric.
- The code repository reports GPL-3.0 through the GitHub API, but that does not establish the license or permitted use of the videos/annotations. Dataset terms were not accepted or audited in this iteration.
- “Working-open-source” means implementation and runnable instructions were inspectable, not that this Windows workspace reproduced the stack.
- Repository metadata is mutable and preserved in the iteration receipt by hash.
