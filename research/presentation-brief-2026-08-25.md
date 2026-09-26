# PlayGround presentation brief — 2026-08-25

## Bottom line

PlayGround is ready to present as a rigorous **methods-and-progress research project**. It is not yet a completed benchmark result. The project has a clear, literature-grounded question, an explicit evidence-output contract, preregistered metrics, a reproducible local harness, a rights-documented open pilot clip, and concrete failure probes. It does **not** yet have an independently adjudicated multi-clip evaluation; therefore `realDataExperimentResults=null` and no model-performance, tool-benefit, coach-utility, or novelty claim is authorized.

## Research question

Can a tool-augmented video-language model answer fine-grained questions about 5–10 second soccer plays more faithfully than a direct video-language model while returning answer-linked temporal and pitch/trajectory evidence, calibrated confidence, and a defensible abstention when evidence is insufficient?

## What the primary literature establishes

### Soccer datasets already provide scale and geometry

- **SoccerNet-v2** reports 500 full-match broadcasts (764 hours) with 110,458 action annotations, 158,493 camera-change timestamps, and 32,932 replay shots: 301,883 annotations in total. The 158,493 camera timestamps are not comprehensive coverage of all 500 games: the paper reports 116,687 comprehensive timestamps for 200 games, while remaining timestamps delimit replays. Its tasks include action spotting, camera segmentation, and replay grounding; it is not a fine-grained QA benchmark with an answer-linked pitch-evidence contract. Source: https://arxiv.org/html/2011.13367
- **SoccerNet Game State Reconstruction** reports 200 clips of 30 seconds, 9.37 million pitch-line points, and more than 2.36 million athlete positions. The 2024 challenge's GS-HOTA scores ranged from 23.36 for the baseline to 63.81 for the top submission, showing that pitch-coordinate reconstruction is real and improving—but remains imperfect. Sources: https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Somers_SoccerNet_Game_State_Reconstruction_End-to-End_Athlete_Tracking_and_Identification_on_CVPRW_2024_paper.html and https://www.openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/papers/Golovkin_From_Broadcast_to_Minimap_Achieving_State-of-the-Art_SoccerNet_Game_State_Reconstruction_CVPRW_2025_paper.pdf

### Correct answers can still be weakly grounded

- **NExT-GQA** evaluates both question-answer accuracy and `Acc@GQA`, which requires a correct answer plus temporal grounding with intersection-over-prediction of at least 0.5. Reported QA / Acc@GQA values are: Human 93.3 / 82.1 (human study on 10% of the test set); FrozenBiLM post-hoc 69.1 / 15.8; FrozenBiLM NG+ 70.8 / 17.5; SeViLA* 68.1 / 16.6. The asterisk denotes SeViLA pretrained on video-language grounding data. This is strong evidence that answer accuracy alone can hide a large grounding gap, while the human point should not be presented as a directly matched full-test-set model row. Source: https://openaccess.thecvf.com/content/CVPR2024/html/Xiao_Can_I_Trust_Your_Answer_Visually_Grounded_Video_Question_Answering_CVPR_2024_paper.html

### Soccer decision reasoning is still difficult

- **SportD v4** reports 1,415 on-ball decisions from the 2022 men's and 2023 women's World Cups. The best tested VLM reaches 34.3% action accuracy, compared with 40.4% for real players. SportD is a valuable forward-looking action-choice benchmark, but it scores action value/regret rather than PlayGround's semantic answer plus evidence payload. Source: https://arxiv.org/html/2607.14616v4

## The remaining research hypothesis

The individual ingredients are not new: short sports QA, temporal answer grounding, image-plane grounding, pitch-coordinate reconstruction, trajectory representations, and tool-assisted soccer reasoning all have predecessors. The bounded literature review did not verify their following conjunction under one **target** evaluation contract:

1. fine-grained questions about 5–10 second soccer clips;
2. a semantic answer plus proposed supporting-versus-contradicting temporal evidence;
3. proposed pitch regions, player relations, or pitch-calibrated trajectories linked to that answer;
4. confidence, evidence-validity checks, and explicit insufficiency reasons;
5. a controlled direct-versus-tool comparison with selective-risk reporting.

This is a conditional working hypothesis, not a novelty guarantee.

## Proposed output and evaluation contract

The implemented `playground-output-v1` schema requires an answer, confidence, one unlabeled temporal interval, string-array spatial evidence, normalized trajectory points in broadcast-image coordinates, an abstention flag, and an abstention reason. The research target proposes a later schema version with supporting-versus-contradicting interval labels, player relations, pitch-calibrated regions/trajectories, and geometry/track validity receipts. Those extensions should not be described as implemented until the schema and annotation protocol are versioned and aligned.

The following are locally frozen, pre-eligible-data protocol choices. They are not empirically validated or optimized deployment thresholds:

- temporal IoU at least 0.50;
- pitch-region F1 at least 0.50;
- normalized trajectory ADE at most 0.10;
- operational confidence gate 0.50 for coverage of non-abstained predictions;
- five equal-width calibration bins;
- 1,000-replicate bootstrap grouped by `match_id`;
- independent second annotation and adjudication before any item is metric-eligible.

## What has actually been executed

- One 8.008-second, 426 × 240 Wikimedia Commons clip was admitted with CC BY 2.0 provenance and local hashes: “Saša Viciknez scoring a goal,” by Djuradj Vujcic. Source page: https://commons.wikimedia.org/wiki/File:Sa%C5%A1a_Viciknez_scoring_a_goal.ogv
- A local `zai-org/glm-4.6v-flash` smoke run produced schema-shaped JSON after an adapter repair. It verified interface plumbing, not answer correctness.
- A deliberately corrupted tool-evidence probe returned an abstention with empty evidence. Same-clip hard-negative and out-of-clip queries also exercised the contract. These are structural observations only.
- The cited 2026-08-21 real-clip packets recorded: smoke packet 27/27, corrupted-evidence packet 24/24, same-clip packet 43/43, and project suite 25 passed.
- Later 2026-08-22 stress probes exposed additional structural failures: a positive penalty probe answered `no` with malformed string-valued confidence/evidence, an abstention carried confidence 1.0, and four length-terminated outputs were not parseable. These failures remain unadjudicated and metric-ineligible, but they are part of the readiness record.

No item has completed independent second annotation, adjudication, and valid pitch calibration. The existing annotation interface and pilot manifest also disagree about whether annotation has started; historical artifacts are preserved, and the discrepancy is treated as a readiness issue rather than silently rewritten.

## Presentation-safe claims

- Prior work demonstrates that soccer event annotation and game-state reconstruction are feasible at scale.
- General video QA results show that answer correctness can substantially exceed joint answer-and-grounding performance.
- The project has a concrete, reproducible evaluation contract and a working local interface/harness.
- The decisive empirical question—whether tool augmentation improves jointly correct, calibrated, evidence-grounded soccer QA—remains unanswered.

## Claims that are not presentation-safe

- “PlayGround is novel” or “no prior work does this.”
- “The tool-augmented model is better.”
- Any accuracy, grounding, calibration, latency, utility, or generalization claim from the one unadjudicated clip.
- Any statement that pitch evidence has been validated; the current frame review records zero correspondences and no calibration artifact.
- Any implication that gated SoccerNet or other broadcast media has been cleared for use.

## Governed feasibility pilot

The next decision point is a preregistered pilot of at most 50 clips from at least 10 matches, with no more than five clips per match, 20% unanswerable controls, and double annotation of every primary item. At 50 independent clips, the worst-case 95% margin of error is about 13.9 percentage points; with five clips per match and an illustrative intra-match correlation of 0.30, it expands to about 20.6 points. The pilot is therefore a feasibility and failure-analysis study, not a precise leaderboard.

Exit criteria should require completed rights review, schema-valid double annotation, adjudication, calibration receipts, paired direct/tool runs on identical inputs, match-grouped uncertainty, and separate reporting of answer accuracy, temporal/spatial grounding, joint correctness, calibration, coverage, and selective risk.

## Presentation figure data

| Figure | Category | Value |
|---|---|---:|
| SoccerNet-v2 annotations | Actions | 110,458 |
| SoccerNet-v2 annotations | Camera changes | 158,493 |
| SoccerNet-v2 annotations | Replay shots | 32,932 |
| NExT-GQA | Human QA accuracy | 93.3 |
| NExT-GQA | Human Acc@GQA | 82.1 |
| NExT-GQA | FrozenBiLM post-hoc QA accuracy | 69.1 |
| NExT-GQA | FrozenBiLM post-hoc Acc@GQA | 15.8 |
| NExT-GQA | FrozenBiLM NG+ QA accuracy | 70.8 |
| NExT-GQA | FrozenBiLM NG+ Acc@GQA | 17.5 |
| NExT-GQA | SeViLA* QA accuracy | 68.1 |
| NExT-GQA | SeViLA* Acc@GQA | 16.6 |
| SoccerNet GSR Challenge 2024 | Baseline GS-HOTA | 23.36 |
| SoccerNet GSR Challenge 2024 | JAM GS-HOTA | 34.40 |
| SoccerNet GSR Challenge 2024 | UPCxMobius GS-HOTA | 43.15 |
| SoccerNet GSR Challenge 2024 | Constructor Tech GS-HOTA | 63.81 |
| SportD v4 | Best tested VLM action accuracy | 34.3 |
| SportD v4 | Real-player action accuracy | 40.4 |

## Web-image provenance for the presentation

- U.S.–Ghana match photo, U.S. Department of State, public domain: https://commons.wikimedia.org/wiki/File:U.S._Plays_Ghana_in_World_Cup_Match.jpg
- Stadium-installed match-analysis camera, MMAston, CC BY-SA 4.0: https://commons.wikimedia.org/wiki/File:Stadium_Installed_Match_Analysis_K2_Panoramic_Video_Camera_System.jpg
- Football pitch diagram, Chandler, public domain: https://commons.wikimedia.org/wiki/File:Football_pitch_metric_and_imperial.svg
- Pilot clip, Djuradj Vujcic, CC BY 2.0: https://commons.wikimedia.org/wiki/File:Sa%C5%A1a_Viciknez_scoring_a_goal.ogv

No AI-generated image is used or required.
