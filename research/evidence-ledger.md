# Evidence Ledger

Claim-level evidence is recorded with source owner, source date/version, access date, evidence class, exact supported claim, and caveat. Mutable popularity signals are omitted unless needed.

## E-015 — SportD supplies a value-grounded strategic-choice frontier
- **Fact status:** Verified primary paper snapshot; author-reported results not reproduced.
- **Claim:** SportD evaluates VLM choices of SHOOT or pass-to-teammate on 478 2022 FIFA World Cup on-ball decisions against a possession-value evaluator, reporting optimal-action accuracy and regret; its abstract reports 31.4% for the best VLM versus 38.9% for professional players.
- **Source:** Cekinmez et al., *SportD: Can VLMs Physically Strategize?*, arXiv `2607.14616v2`, https://arxiv.org/abs/2607.14616v2 and https://arxiv.org/html/2607.14616v2.
- **Accessed:** 2026-08-07. Local snapshots: `artifacts/sportd-consolidation-2026-08-07/arxiv-api.xml`, `paper.html`, `paper.txt`; verifier `verify_sportd.py` returned PASS.
- **Evidence class:** Primary arXiv API/HTML paper snapshot with SHA-256 anchors.
- **Caveat:** Paper declares CC BY-NC-SA 4.0, but this does not establish rights to broadcast media, annotations, or evaluator data. No SportD data/media/code/checkpoint was acquired or reproduced. The inspected paper does not verify answer-linked evidence intervals, soccer-field evidence scoring, confidence calibration, explicit abstention, or selective risk.
- **Project implication:** Optional secondary track only: model choice plus confidence/abstention and temporal/pitch evidence, scored by a frozen, provenance-recorded action-value evaluator. Preserve human-versus-value-model disagreement.
- **Version note:** Superseded for current citation by E-030 (`2607.14616v4`); retain this v2 entry as historical, hash-bound evidence.

## E-001 — SoccerNet-v2 scale and task scope
- **Fact status:** Verified primary research claim.
- **Claim:** SoccerNet-v2 reports around 300,000 annotations across 500 untrimmed broadcast soccer videos and defines/evaluates action spotting, camera-shot segmentation with boundary detection, and replay grounding.
- **Source:** Deliège, Adrien; Cioppa, Anthony; Giancola, Silvio; et al., *SoccerNet-v2: A Dataset and Benchmarks for Holistic Understanding of Broadcast Soccer Videos*.
- **Owner/authors:** Adrien Deliège, Anthony Cioppa, Silvio Giancola, Meisam J. Seikavandi, Jacob V. Dueholm, Kamal Nasrollahi, Bernard Ghanem, Thomas B. Moeslund, Marc Van Droogenbroeck.
- **Source date/version:** arXiv `2011.13367v3`, updated 2021-04-19.
- **URL:** https://arxiv.org/abs/2011.13367v3
- **Accessed:** 2026-08-06.
- **Evidence class:** Primary paper metadata/abstract from the versioned arXiv API record.
- **Exact support:** Abstract: “we release around 300k annotations within SoccerNet's 500 untrimmed broadcast soccer videos” and “include action spotting, camera shot segmentation with boundary detection, and ... replay grounding.”
- **Caveat:** These are author-reported corpus/task facts. They do not establish fine-grained question answering, answer-linked pitch/trajectory evidence, abstention evaluation, or unrestricted media access.

## E-002 — SoccerNet media access is gated while labels/features are separately documented
- **Fact status:** Verified official repository documentation.
- **Claim:** The official SoccerNet README documents direct download calls for labels and derived features, but states that SoccerNet videos require a password; challenge-video comments explicitly say the password comes from an NDA.
- **Source:** `SoccerNet/SoccerNet` official repository README.
- **Owner:** SoccerNet project; pinned README commit authored by Silvio Giancola.
- **Source date/version:** Commit `650aa54194f4a5e54a83a974dda899087b59f4b9`, 2025-01-27.
- **URL:** https://raw.githubusercontent.com/SoccerNet/SoccerNet/650aa54194f4a5e54a83a974dda899087b59f4b9/README.md
- **Accessed:** 2026-08-06.
- **Evidence class:** Primary official code/documentation, immutable commit.
- **Exact support:** README lines 81–91 list label/feature downloads; lines 93–97 say challenge videos “require password from NDA”; lines 113–119 say SoccerNet videos “require password” and assign a password before download.
- **Caveat:** The repository's MIT license applies to repository code and must not be inferred to license the broadcast media. This iteration did not request a password, submit a form, accept terms, or download labels, features, or video.

## Interpretation for PlayGround (research judgment, not a sourced fact)
SoccerNet-v2 is a relevant near-boundary predecessor and possible future annotation/feature source, but it does not by itself close PlayGround's proposed combination of fine-grained QA, answer-linked temporal and spatial evidence, confidence/calibration, and abstention. A broader novelty matrix is required before making a novelty claim.

## E-003 — SoccerNet-Caption provides timestamp-localized soccer captions, not verified QA evidence
- **Fact status:** Verified official project documentation.
- **Claim:** SoccerNet-Caption defines dense soccer video captioning as generating captions for soccer actions while localizing each caption with a timestamp; its official README reports 471 broadcast-game videos with captions and a separate 42-game challenge set.
- **Source:** `SoccerNet/sn-caption` official repository README.
- **Owner/authors:** SoccerNet project; cited paper authors Hassan Mkhallati, Anthony Cioppa, Silvio Giancola, Bernard Ghanem, and Marc Van Droogenbroeck.
- **Source date/version:** Commit `c05973d4f00853e208d54965f4d6fa47364b8d66`, committed 2024-04-12.
- **URL:** https://raw.githubusercontent.com/SoccerNet/sn-caption/c05973d4f00853e208d54965f4d6fa47364b8d66/README.md
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary official code/documentation, immutable commit.
- **Exact support:** README line 3 defines caption generation plus timestamp localization and reports 471 games and 42 challenge games; lines 112–121 document annotation/feature API calls and say video download requires filling an NDA to obtain a password.
- **Caveat:** Caption-to-time localization is a close temporal-grounding predecessor but is not question answering. The inspected source does not establish answer-linked spatial/trajectory evidence, calibrated confidence, or abstention. No data was downloaded and no form was submitted.

## E-004 — SoccerNet-MVFoul is multi-view foul classification with confidence, not evidence-grounded QA
- **Fact status:** Verified official project documentation.
- **Claim:** SoccerNet-MVFoul contains 3,901 foul actions, each with at least two live-action videos and at least one replay, annotated with ten referee-perspective foul properties; VARS predicts foul properties from multiple views and its interface displays confidence scores.
- **Source:** `SoccerNet/sn-mvfoul` official repository README.
- **Owner/authors:** SoccerNet project; cited paper authors Jan Held, Anthony Cioppa, Silvio Giancola, Abdullah Hamdi, Bernard Ghanem, and Marc Van Droogenbroeck.
- **Source date/version:** Commit `502fb44a76c254e332394f095d54abc830131a44`, committed 2025-01-09.
- **URL:** https://raw.githubusercontent.com/SoccerNet/sn-mvfoul/502fb44a76c254e332394f095d54abc830131a44/README.md
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary official code/documentation, immutable commit.
- **Exact support:** README lines 9–11 define the dataset, VARS, and confidence-bearing interface; lines 22–29 require an NDA/password; lines 34–43 give action counts, view composition, ten properties, and expert annotation; lines 46–50 describe multi-view feature aggregation and classification.
- **Caveat:** Multiple views are not the same as explicit pitch-region or trajectory evidence. Displayed prediction confidence is not evidence of calibration evaluation or abstention. No data was downloaded and no form was submitted.

## E-005 — NExT-GQA directly overlaps answer-linked temporal grounding
- **Fact status:** Verified primary project/paper documentation.
- **Claim:** NExT-GQA studies visually grounded VideoQA by requiring models to answer questions and simultaneously ground the relevant video moments as visual evidence.
- **Source:** `doc-doc/NExT-GQA` project repository for *Can I Trust Your Answer? Visually Grounded Video Question Answering*.
- **Owner/authors:** Junbin Xiao, Angela Yao, Yicong Li, and Tat-Seng Chua.
- **Source date/version:** Repository commit `63772e0256ad9e34b83d6a108f1ba2041b924607`, committed 2024-07-01; README cites CVPR 2024 and arXiv `2309.01327`.
- **URL:** https://raw.githubusercontent.com/doc-doc/NExT-GQA/63772e0256ad9e34b83d6a108f1ba2041b924607/README.md
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author project repository, immutable commit.
- **Exact support:** README line 4 says models are forced to “answer questions and simultaneously ground the relevant video moments as visual evidences”; lines 34–39 identify the authors and CVPR 2024 publication.
- **Caveat:** The inspected source establishes answer-linked temporal evidence and therefore defeats any broad novelty claim for that component. It does not verify soccer-specific pitch/trajectory grounding, calibrated confidence, explicit abstention, or selective-risk evaluation.

## Updated interpretation for PlayGround (research judgment, not a sourced fact)
NExT-GQA makes temporal answer grounding a predecessor rather than a standalone PlayGround novelty. The defensible working hypothesis is the conjunction of short soccer-play QA, answer-linked temporal and pitch/trajectory evidence, explicit insufficiency/abstention, calibration/selective-risk scoring, and a tool-augmented versus direct-VLM comparison. See `research/novelty-matrix.md`.

## E-006 — One Wikimedia Commons soccer source is declared CC BY 2.0 and supports a 5–10 second interface clip
- **Fact status:** Verified platform source record and locally verified media identity.
- **Claim:** The Wikimedia Commons record for *Saša Viciknez scoring a goal* identifies Djuradj Vujcic as the creator, describes the upload as own work, labels it CC BY 2.0 with required attribution “video by Djuradj Vujcic,” and describes the depicted event as a penalty goal against the Caribbean Selects in July 2006. The 14.303492-second source supports an 8.008-second local derivative within PlayGround's frozen 5–10 second boundary.
- **Source:** Wikimedia Commons file page and MediaWiki imageinfo/extmetadata API record.
- **Owner/author:** Djuradj Vujcic (declared creator/uploader); Wikimedia Commons hosts the record.
- **Source date/version:** Media record timestamp `2015-03-04T06:19:22Z`; Commons page ID `38719680`; source-media SHA-1 `3587e8ff46d111397cf7004dff5169527b1e40df`.
- **URL:** https://commons.wikimedia.org/wiki/File:Sa%C5%A1a_Viciknez_scoring_a_goal.ogv
- **License URL:** https://creativecommons.org/licenses/by/2.0
- **Accessed:** 2026-08-07.
- **Evidence class:** First-party platform media metadata plus byte-level local verification; exact API response preserved at `artifacts/wikimedia-pilot-v1/commons-source-metadata.json` (SHA-256 `07ae9a8155b01e9b8a6a935d24e24ebdf87766be2f1af53c1a15bd371a0e4258`).
- **Exact support:** API fields report `Credit=Own work`, `Artist=Djuradj Vujcic`, `LicenseShortName=CC BY 2.0`, `Attribution=video by Djuradj Vujcic`, source duration `14.303492063492063`, and the penalty-goal description. Local SHA-1 exactly matches the API media SHA-1; the derived clip duration is `8.008000` seconds and SHA-256 is `25c872195a16dc57249b0f0e02fd2b04ff87f33ecb8d5c62c248acdb23cc5178`.
- **Caveat:** Commons exposes an uploader declaration, not an independently audited chain of title. One low-resolution convenience clip from one source/match group cannot support representativeness, model-performance, coach-domain, or benchmark claims. The loop has not authorized publication, public release, or hosted-model upload.

## E-007 — TVQA+ closes generic spatio-temporally grounded VideoQA novelty
- **Fact status:** Verified primary research and official project claim; reported metrics not reproduced.
- **Claim:** TVQA+ reports 29,383 multiple-choice QA pairs from 4,198 television clips, refined temporal spans, and 310,826 boxes over 148,468 sampled images. Boxes link people/objects to visual concepts in questions and correct answers. Its Answer-Span Accuracy counts a prediction as correct only when the answer is correct and the predicted temporal span overlaps ground truth at IoU at least 0.5.
- **Source:** Jie Lei, Licheng Yu, Tamara L. Berg, and Mohit Bansal, *TVQA+: Spatio-Temporal Grounding for Video Question Answering*; official `jayleicn/TVQAplus` repository.
- **Owner/authors:** Jie Lei, Licheng Yu, Tamara L. Berg, and Mohit Bansal.
- **Source date/version:** arXiv `1904.11574v2`, updated 2020-05-11; repository commit `d2dc7211732cfd31fe1a5416432003551b63f5df`, committed 2022-10-25.
- **URL:** https://arxiv.org/abs/1904.11574v2
- **Repository URL:** https://raw.githubusercontent.com/jayleicn/TVQAplus/d2dc7211732cfd31fe1a5416432003551b63f5df/README.md
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper plus official repository, both version-pinned; local paper/API/repository artifacts are hash-verified.
- **Exact support:** Paper text states 29,383 QA pairs/4,198 clips, 148,468 images/310,826 boxes, one frame sampled every two seconds within each refined span, and 2,527 box categories. The evaluation section defines ASA as joint answer/span correctness with temporal IoU >= 0.5. The arXiv abstract states that referenced people/objects are detected while relevant moments are retrieved. Verification receipt: `artifacts/tvqaplus-consolidation-2026-08-07/verification.json`.
- **Caveat:** This is television-domain multiple-choice QA, not soccer. Spatial evidence is sampled image-plane boxes, not field coordinates or trajectories. The paper's STAGE values are author-reported and were not reproduced; no dataset or checkpoints were acquired. Full-text inspection in the prior source review found no calibration, abstention, or selective-risk evaluation.

## E-008 — SoccerBench and SoccerAgent close broad soccer multimodal QA and specialist-tool novelty
- **Fact status:** Verified primary research/project claims; reported accuracy not reproduced.
- **Claim:** SoccerBench is reported as around 10K multimodal multiple-choice QA pairs across 13 tasks, and SoccerAgent integrates 18 specialist tools. The paper evaluates answer accuracy by task and modality; one tool uses GroundingDINO image-plane boxes, but the inspected evaluation text does not establish externally scored answer-linked pitch coordinates/trajectories, calibration, abstention, or selective risk.
- **Source:** Jiayuan Rao, Zifeng Li, Haoning Wu, Ya Zhang, Yanfeng Wang, and Weidi Xie, *Multi-Agent System for Comprehensive Soccer Understanding*; official `jyrao/SoccerAgent` repository.
- **Owner/authors:** Jiayuan Rao, Zifeng Li, Haoning Wu, Ya Zhang, Yanfeng Wang, and Weidi Xie.
- **Source date/version:** arXiv `2505.03735v2`, updated 2025-09-02; repository main commit `763c254e5936767be491c84ff1252b20d355fa14`, committed 2025-10-31.
- **URL:** https://arxiv.org/abs/2505.03735v2
- **Repository URL:** https://github.com/jyrao/SoccerAgent/tree/763c254e5936767be491c84ff1252b20d355fa14
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper, official project page, and official repository snapshot; local artifacts are hash-verified.
- **Exact support:** The arXiv abstract and paper state around 10K text/image/video multiple-choice QA pairs across 13 tasks; the system section states 18 specialized tools (17 called open-source by the authors); the evaluation section states answer accuracy. Verification receipt: `artifacts/socceragent-consolidation-2026-08-07/verification.json`.
- **Caveat:** The paper reports 13 tasks while the pinned README reports 14; this may reflect a later challenge revision and must not be silently harmonized. The repository is inspectable and includes setup/run commands, but GitHub reports no repository license, so this ledger does not independently classify it as legally open source. Model accuracy was not reproduced, benchmark/media artifacts were not downloaded, and full-text term absence is weaker than an explicit author statement.

## E-009 — SoccerNet-GSR establishes pitch-coordinate game-state reconstruction, not answer-linked grounding
- **Fact status:** Verified primary research/project claims; baseline results not reproduced.
- **Claim:** SoccerNet-GSR formalizes game-state reconstruction as athlete positions and identities on a 2D top-view pitch. The authors report 200 fully annotated 30-second clips, more than 9.37 million pitch-line points, and more than 2.36 million athlete positions. Evaluation is limited to visible athletes; incorrectly calibrated frames may be discarded, and the ball is removed because the ground-plane approximation does not support precise airborne 3D localization. GS-HOTA evaluates pitch-coordinate localization and identity attributes; the official pinned README sets its localization tolerance parameter to 5 meters and requires matching identity attributes.
- **Source:** Vladimir Somers et al., *SoccerNet Game State Reconstruction: End-to-End Athlete Tracking and Identification on a Minimap*; official `SoccerNet/sn-gamestate` repository.
- **Owner/authors:** Vladimir Somers, Victor Joos, Anthony Cioppa, Silvio Giancola, Seyed Abolfazl Ghasemzadeh, Floriane Magera, Baptiste Standaert, Amir Mohammad Mansourian, Xin Zhou, Shohreh Kasaei, Bernard Ghanem, Alexandre Alahi, Marc Van Droogenbroeck, and Christophe De Vleeschouwer.
- **Source date/version:** arXiv `2404.11335v1`, submitted 2024-04-17; repository main commit `1c958345067218297d221e45e1a6405f975f83e0`, committed 2026-05-02.
- **URL:** https://arxiv.org/abs/2404.11335v1
- **Repository URL:** https://github.com/SoccerNet/sn-gamestate/tree/1c958345067218297d221e45e1a6405f975f83e0
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper plus official pinned repository; six source artifacts are hash-verified.
- **Exact support:** The paper defines 2D top-view positions/identities, reports the clip and annotation counts, defines the 105 by 68 meter centered pitch coordinate system, and documents visibility, calibration, and ball limitations. The official README defines 2D field positions and GS-HOTA's 5-meter tolerance/strict attribute match. Verification receipt: `artifacts/soccernet-gsr-consolidation-2026-08-07/verification.json`.
- **Caveat:** This closes novelty around pitch-coordinate reconstruction, but not QA or externally scored answer-linked pitch/trajectory evidence. Per-frame coordinates permit derived trajectories but are not answer-conditioned labels. GitHub reports GPL-3.0 for code; that does not establish video/dataset rights. No data, video, weights, tracker state, or reported metric was acquired or reproduced.

## E-010 — TrajSV uses field-coordinate trajectories for sports captioning, not answer-linked QA evidence
- **Fact status:** Verified primary author-paper claims; reported deployment and metrics not reproduced.
- **Claim:** TrajSV extracts player and ball trajectories from sports broadcast video by mapping image coordinates into a sports-field coordinate system, then uses learned trajectory-enhanced clip/video representations for retrieval, action spotting, and video captioning across soccer, basketball, and volleyball. Its DVC task temporally localizes a caption with start and end frames; the enumerated applications do not include question answering.
- **Source:** Zheng Wang, Shihao Xu, and Wei Shi, *TrajSV: A Trajectory-based Model for Sports Video Representations and Applications*.
- **Owner/authors:** Zheng Wang, Shihao Xu, and Wei Shi.
- **Source date/version:** arXiv `2508.11569v1`, submitted and last updated 2025-08-15.
- **URL:** https://arxiv.org/abs/2508.11569v1
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper, immutable arXiv version; local API, HTML, and extracted-text artifacts are hash-verified.
- **Exact support:** The preprocessing section states that player/ball image coordinates are mapped to a sports-field coordinate system using per-clip camera parameters. The abstract enumerates three sports and three downstream applications. The application section defines SDVC as commentary spotting plus sentence generation and DVC as caption localization with start/end frames. The experiment section reports SoccerNet comments as caption ground truth and uses centered `[-52.5,+52.5]` by `[-34,+34]` meter coordinate ranges. Verification receipt: `artifacts/trajsv-consolidation-2026-08-07/verification.json`.
- **Caveat:** Trajectories are model inputs/representations, not externally scored answer-linked evidence. The paper does not establish QA, confidence calibration, abstention, or selective-risk evaluation. Its stated deployed system and metrics are author-reported; no official implementation was verified, and a zero-result GitHub repository search is not proof that none exists. The paper applies soccer-sized coordinate ranges to non-soccer data. No video, dataset, annotation, model, or code archive was acquired.

## E-011 — SoccerLens scores soccer event-class attribution against spatial and temporal cues, not answer-linked evidence
- **Fact status:** Verified primary research/project and annotation-artifact claims; reported model results not reproduced.
- **Claim:** SoccerLens evaluates soccer event-classification grounding by comparing target-class attribution maps with image-plane bounding boxes for primary, secondary, and common event cues. The paper defines Energy, Pointing, S-IoU, and T-IoU; its official code README documents the same four metrics and Chefer/Chefer-T evaluation. This directly precedes generic spatial/temporal grounding evaluation for soccer classifiers, but it is not QA and does not submit answer-conditioned pitch coordinates or trajectories.
- **Source:** Ismael Elsharkawi, Ahmed Sait, Silvio Giancola, Bernard Ghanem, Hossam Sharara, and Abdelrahman Eldesokey, *SoccerLens: Grounded Soccer Video Understanding Beyond Accuracy*; official `IsmaelElsharkawi/SoccerLensDataset` and `IsmaelElsharkawi/SoccerExplainability` repositories.
- **Owner/authors:** Ismael Elsharkawi, Ahmed Sait, Silvio Giancola, Bernard Ghanem, Hossam Sharara, and Abdelrahman Eldesokey.
- **Source date/version:** arXiv `2605.09598v2`, updated 2026-05-12; dataset commit `10441819af77193d88e187d785826a98872f42cd`; code commit `1a23c184fd42d4f0632afed973dd73a2db25d8e0`.
- **URL:** https://arxiv.org/abs/2605.09598v2
- **Repository URLs:** https://github.com/IsmaelElsharkawi/SoccerLensDataset/tree/10441819af77193d88e187d785826a98872f42cd and https://github.com/IsmaelElsharkawi/SoccerExplainability/tree/1a23c184fd42d4f0632afed973dd73a2db25d8e0
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper plus official dataset/code repositories and pinned public COCO annotations; ten artifacts are hash-verified.
- **Exact support:** The paper describes 200 30-second clips across 13 events, 1 fps sampling, 2,209 cue-bearing annotated frames, three cue tiers, three spatial attribution metrics, and temporal IoU. Direct inspection of the pinned COCO JSON found 2,711 unique image records and 5,189 raw annotation records: 4,687 valid boxes plus 502 explicit zero-box `no_roi` sentinels, reconciling the paper/README's 2,209 cue-bearing frames and 4,687 boxes. All 43 verification checks passed in `artifacts/soccerlens-consolidation-2026-08-07/verification.json`.
- **Caveat:** Four source discrepancies remain explicit: paper lineage says MatchTime while the dataset README says SoccerNet; paper/code describe event cues while the dataset README describes on-screen overlays and the COCO category names are `small label`, `large label`, and `visual cue`; the headline counts require excluding no-ROI sentinels; and GitHub's Apache-2.0 repository detection differs from the README's CC BY-NC 4.0 dataset declaration. The inspected sources do not establish QA, answer-linked evidence submission, pitch coordinates, trajectories, calibration, abstention, or selective risk. Code/results were not run because external media, checkpoints, GPU dependencies, and SLURM setup are required. No video, model, checkpoint, or gated data was downloaded and no license was accepted.

## E-012 — Physical-grounding benchmark outputs and scores answer-linked image-plane box trajectories
- **Fact status:** Verified immutable primary author paper; reported benchmark results not reproduced.
- **Claim:** *Grounding Video Reasoning in Physical Signals* requires one structured answer with `a_what`, `a_when`, and `a_where`. The spatial output is a normalized image-plane bounding box, and the paper scores text accuracy, temporal IoU, and spatial IoU against a shared grounded event record; its qualitative figure explicitly describes a ground-truth box trajectory. The benchmark reports 1,560 base clips from SSV2, YouCook2, HoloAssist, and Roundabout-TAU and evaluates original, shuffled, ablated, and frame-masked inputs.
- **Source:** Alibay Osmanli, Zixu Cheng, and Shaogang Gong, *Grounding Video Reasoning in Physical Signals*.
- **Owner/authors:** Alibay Osmanli, Zixu Cheng, and Shaogang Gong.
- **Source date/version:** arXiv `2604.21873v1`, submitted 2026-04-23.
- **URL:** https://arxiv.org/abs/2604.21873v1
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper, immutable arXiv version; API XML and arXiv HTML are locally hash-bound.
- **Exact support:** Sections 3.1 and 3.3 define the single three-field prediction and grounded component metrics; the `a_where` field is `x,y,w,h`; Figure 1 calls the reference sequence a ground-truth box trajectory; the abstract/introduction state 1,560 base clips and four perturbation conditions. All 20 metadata, integrity, task-contract, metric, and limitation checks passed in `artifacts/physical-grounding-consolidation-2026-08-07/verification.json`.
- **Caveat:** This is physical-video QA, not soccer. Its boxes are normalized image-plane coordinates, not calibrated sports-field coordinates, and the inspected task contract does not add confidence, explicit abstention, or selective-risk endpoints. The paper states that event descriptions, temporal spans, and spatial boxes are produced automatically rather than fully human-verified. Metrics and findings remain author-reported; no code repository was verified and no dataset, media, model, or checkpoint was acquired.

## E-013 — SVI-Bench establishes 10-second sports Action QA and tool-assisted corpus reasoning, not answer-linked field evidence
- **Fact status:** Verified primary author paper and official pinned repository; reported benchmark results not reproduced.
- **Claim:** SVI-Bench defines nine tasks over basketball, hockey, and soccer. T2 presents a 10-second clip, a question, and five candidate answers, with 31 question types including spatial relationships, and reports answer accuracy. T9 requires tool-assisted evidence gathering across clips, reports, and structured statistics. The separate T5 forecasting task reports calibration error, while T7 consumes time-aligned image-plane bounding-box trajectories and scores generated-video trajectory alignment; neither establishes answer-linked sports-field evidence or abstention for T2.
- **Source:** Yulu Pan, Han Yi, Seongsu Ha, Md Mohaiminul Islam, Benjamin Zhang, Lorenzo Torresani, and Gedas Bertasius, *SVI-Bench: A Dynamic Microworld for Strategic Video Intelligence*; official `Texaser/SVI-Bench` repository.
- **Owner/authors:** Yulu Pan, Han Yi, Seongsu Ha, Md Mohaiminul Islam, Benjamin Zhang, Lorenzo Torresani, and Gedas Bertasius.
- **Source date/version:** arXiv `2605.31529v2`, updated 2026-07-01; repository commit `35d60bd9c4c04dc80e05327bcfaf1e81a8540871`.
- **URL:** https://arxiv.org/abs/2605.31529v2
- **Repository URL:** https://github.com/Texaser/SVI-Bench/tree/35d60bd9c4c04dc80e05327bcfaf1e81a8540871
- **Accessed:** 2026-08-07.
- **Evidence class:** Primary author paper plus official pinned repository; API XML, immutable arXiv HTML, and README are locally hash-bound.
- **Exact support:** Paper sections 4.1.2, 4.2.2, 4.3.1, and 4.4.1 define T2, T5 calibration, T7 trajectory-conditioned generation, and T9 tool evidence. The pinned README enumerates all nine tasks and says dataset access is gated. All 22 metadata, task-contract, integrity, and repository-boundary checks passed in `artifacts/field-grounding-search-2026-08-07/verification.json`.
- **Caveat:** T2's short sports clips are direct scope precedent, but its output is an answer rather than a scored temporal/spatial evidence object. T5 calibration does not establish T2 or joint-grounded calibration. T7 boxes/trajectories are image-plane generation controls, not answer evidence or sports-field coordinates. Repository code is MIT; the README says data is governed separately and access requires agreeing to terms. No terms were accepted, no data/media/model/checkpoint was acquired, and no author metric was reproduced.

## E-014 — CourtSI externally scores 3D court-coordinate answers
- **Fact status:** Verified primary paper; metrics not reproduced.
- **Claim:** CourtSI asks sports spatial questions whose numerical answers may be `(x,y,z)` court coordinates and scores localization with T-MRA.
- **Source:** *Stepping VLMs onto the Court*, arXiv `2603.09896v1`, https://arxiv.org/abs/2603.09896v1.
- **Exact support:** `courtsi.txt:430-440` and `:1221-1233`; verifier passed 18/18.
- **Caveat:** Badminton, tennis, and table tennis only; coordinate is the answer, not separate answer-linked evidence. No data rights or model result was verified.

## E-016 — Citation-neighborhood review finds no verified exact answer-conditioned field-evidence match
- **Fact status:** Verified primary-paper neighborhood review with independent QA provenance; not an exhaustive systematic review and not a novelty determination.
- **Claim:** The bounded citation neighborhood review found zero verified exact matches to the predicate: a soccer-play semantic question plus answer, a separately submitted answer-linked pitch-coordinate region or trajectory, and external scoring of that linked field payload. Verified near-neighbors were SoccerAgent/SoccerBench QA citing GSR, MSUE/SoccerNet VQA answer evaluation, SoccerNet-GSR localization-only field state, SoccerLens image-plane attribution, and SpatialScore coordinate-as-answer.
- **Source:** `artifacts/answer-conditioned-field-citation-neighborhood-2026-08-09/handoff.md` and `receipt.json`; independent QA v2 `artifacts/answer-conditioned-field-citation-neighborhood-qa-v2-2026-08-09/handoff.md` and `receipt.json`.
- **Exact support:** Source receipt reports `checks_passed=33`, `checks_total=33`, manifest `entries=14`, `verified_exact_matches=0`, and result `BOUNDED_NEGATIVE_WITH_CITATION_NEIGHBORS`. QA v2 independently records identical before/after SHA-256 maps for all 14 manifest entries, source receipt SHA-256 `a0bfdf2617c38bcffe5b5c76e29b226bb447ee2f460ff26e345dd57266909d43`, source verifier PASS 33/33, Python compilation exit 0, and 23 project tests passed.
- **Evidence anchors:** `socceragent.txt:28-35`; `msue.txt:9-24`; `gsr.txt:126-151`; `soccerlens.txt:190-239`; `spatialscore.txt:53-75`; `synloc.html:34` in the source packet.
- **Caveat:** This is a bounded selected-neighborhood result, not global absence, exhaustive review, author-metric reproduction, rights/licensing/legal determination, benchmark/model evaluation, or novelty authorization. No source or QA artifact was modified; no acquisition or restricted access occurred.
- **Project implication:** Preserve `BOUNDED_NEGATIVE_WITH_CITATION_NEIGHBORS`; the working hypothesis remains the conjunction of semantic soccer QA, separately scored answer-linked soccer-field evidence, evidence-validity-aware abstention/calibration, and controlled direct-versus-tool evaluation.

## E-017 — 2026-08-09 — X-VARS / SoccerNet-XFoul is a semantic refereeing-VQA near-neighbor, not an exact field-evidence match
- **Fact status:** Verified primary-paper snapshot; author-reported results and any data/media rights were not reproduced or acquired.
- **Claim:** X-VARS / SoccerNet-XFoul establishes soccer video-question-answer triplets with referee questions, semantic answers, detailed explanations, and multiple answers per action. The captured paper evaluates extracted foul/severity predictions from generated explanations, but the inspected evidence does not establish a separately submitted answer-linked pitch-coordinate region or trajectory with external scoring of that field payload. Therefore this bounded single-paper audit found zero exact matches to the PlayGround predicate while retaining X-VARS as a semantic-answer/explanation near-neighbor.
- **Source:** `artifacts/answer-conditioned-field-branch-audit-2026-08-09/xvars-api.xml:11-16`; `xvars.txt:541-622`; `xvars.txt:1828-1849`; immutable packet `handoff.md`, `receipt.json`, and `hashes.json` in the same directory.
- **Exact support:** The packet verifier returned exit 0 with `checks_passed=43`, `checks_total=43`, `manifest_hashes_matched=5/5`, and `snapshot_byte_identity=3/3`; Python compilation passed; the project suite returned `23 passed in 1.42s`.
- **Result class:** `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- **Caveat/consequence:** This is selected, single-paper evidence only—not global absence, systematic-review completion, independent source-group validation, author-metric reproduction, rights/licensing determination, benchmark/model evaluation, or novelty authorization. No dataset, media, code, model, or checkpoint was acquired.

## E-018 — 2026-08-09 — TreeSoc is a soccer-VQA/tool-evidence near-neighbor, not an exact field-evidence match
- **Fact status:** Verified primary-paper snapshot with independent QA provenance; author-reported results and any data/media rights were not reproduced or acquired.
- **Claim:** TreeSoc establishes soccer video question answering, tool-routed intermediate evidence, visual grounding/temporal localization, and SoccerBench TextQA/ImageQA/VideoQA accuracy. The captured paper does not establish a separately submitted answer-linked sports-field coordinate region or trajectory, nor external scoring of that linked field payload. This bounded single-paper audit therefore found zero exact matches to the PlayGround predicate while retaining TreeSoc as a soccer-VQA and internal-tool-evidence near-neighbor.
- **Source:** `artifacts/answer-conditioned-field-treesoc-branch-audit-2026-08-09/treesoc-api.xml:11-16`; `treesoc.html:342`, `:359`, `:465-477`, `:489`, `:894`, and `:909`; immutable packet `handoff.md`, `receipt.json`, and `hashes.json` in the same directory.
- **Exact support:** The source verifier exited 0 with `checks_passed=42`, `checks_total=42`, `manifest_hashes_matched=5/5`, and `snapshot_byte_identity=3/3`; Python compilation passed; the independent QA receipt records the same verifier result and 23 project tests passed. The current executable result is 42/42; earlier 43/43 task-history text is stale.
- **Result class:** `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- **Caveat/consequence:** This is selected, single-paper evidence only—not global absence, systematic-review completion, independent source-group validation, author-metric reproduction, rights/licensing determination, benchmark/model evaluation, or novelty authorization. No dataset, media, code, model, or checkpoint was acquired. The QA packet notes an unexpected generated `__pycache__` directory; it was preserved and not treated as a source-packet edit.

## E-019 — 2026-08-09 — SoccerChat is a short soccer-VideoQA near-neighbor, not an exact field-evidence match
- **Fact status:** Verified primary-paper snapshot with independent QA v2 provenance; author-reported results and any data/media rights were not reproduced or acquired.
- **Claim:** SoccerChat establishes short soccer-video question-answer data and evaluates semantic soccer QA, referee decision making, event classification, and related response generation. The captured source does not establish a separately submitted answer-linked soccer-field coordinate/region/trajectory payload or external scoring of that linked field payload. This bounded single-paper audit therefore found zero exact matches to the PlayGround predicate while retaining SoccerChat as a semantic soccer-VideoQA near-neighbor.
- **Source:** `artifacts/answer-conditioned-field-soccerchat-branch-audit-2026-08-09/soccerchat-api.xml:11-16`; `soccerchat.txt:94-117`, `:1760-1821`, and `:2066-2092`; independent QA v2 `artifacts/answer-conditioned-field-soccerchat-branch-audit-qa-v2-2026-08-09/handoff.md`, `receipt.json`, and `hashes.json`; local verification context `artifacts/soccerchat-verification-2026-08-06/verification-summary.json:5-18` and `artifacts/soccerchat-verification-2026-08-06/verification-summary.json:79-88`.
- **Exact support:** Source verifier exit 0 with `checks_passed=39`, `checks_total=39`, manifest `5/5`, snapshot identity `3/3`, and exact match `0`; independent QA v2 recorded pre-integration exit 0 with `156/156` checks, read-only input count `24`, canonical baseline `8/8`, QA output manifest `3/3`, source manifest `5/5`, and source snapshot identity `3/3`. Local verification context records task facts and term counts at `artifacts/soccerchat-verification-2026-08-06/verification-summary.json:5-18` and `artifacts/soccerchat-verification-2026-08-06/verification-summary.json:79-88`; those term counts are contextual leads, not proof of field-payload absence. Post-integration QA and integration verification are recorded in `artifacts/soccerchat-canonical-integration-qa-2026-08-09/receipt.json` and `artifacts/soccerchat-canonical-integration-2026-08-09/receipt.json`; Python compilation passed and the project suite passed 23 tests.
- **Result class:** `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- **Caveat/consequence:** This is selected, single-paper evidence only—not global absence, systematic-review completion, independent source-group validation, author-metric reproduction, rights/licensing determination, benchmark/model evaluation, or novelty authorization. The rejected QA v1 packet is historical context only and is not accepted evidence. This integration changed the canonical files recorded in the integration manifest while the source and QA packets remained unchanged. SoccerNet video access is gated; no terms were accepted. The local verification context detected no repository license; that is not a rights determination. No dataset, media, code, model, or checkpoint was acquired.


## E-020 — 2026-08-09 — SoccerRAG is a retrieval/database QA near-neighbor, not an exact field-evidence match
- **Fact status:** QA-accepted single-paper/repository snapshot; author-reported results and rights were not reproduced or acquired.
- **Claim:** SoccerRAG supports natural-language soccer questions and semantic/database answers through retrieval over SoccerNet-derived metadata, commentary, captions, event annotations, and player information. It does not establish a separately submitted answer-linked soccer-field coordinate, region, or trajectory payload or external scoring of such a linked field payload. Exact matches: `0`.
- **Source:** `artifacts/answer-conditioned-field-soccerrag-branch-audit-2026-08-09/arxiv-2406.01273v2-api.xml:10-20`; `arxiv-2406.01273v2.txt:74-124`, `:342-370`, `:374-401`, `:824-897`, `:898-913`, `:960-968`, `:1201-1207`; `github-readme.md:35-63`, `:73-100`, `:103-126`; accepted QA packet receipt/verifier.
- **Result class:** `BOUNDED_NEGATIVE_WITH_NEAR_NEIGHBOR`.
- **Caveat:** Single candidate only; not global absence, systematic review, independent source-group validation, author-metric reproduction, rights determination, or novelty authorization. Timestamps, retrieved text, database results, captions, commentary, event annotations, and player metadata are not field evidence. MIT repository metadata does not establish SoccerNet/media rights. SQL/database rows, retrieved text, timestamps, commentary, captions, event annotations, player metadata, and future-video proposals are not answer-linked field evidence; subjective extractor validation and answer pass/fail scoring are not external linked-field-payload scoring. Local term counts are contextual search evidence only, not proof of payload or scoring absence. Author-reported results, including the twenty-question evaluation, were not reproduced. MIT metadata applies only to repository code; SoccerNet data, broadcast media, the paper, redistribution, and downstream rights remain unresolved.

## E-021 — 2026-08-10 — Batch-2 citation neighbors remain bounded negatives
- **Fact status:** QA-accepted selected primary-source packet; author-reported results, rights, and metrics were not reproduced.
- **Claim:** SoccerMaster / Soccer Factory, MatchTime, and UniSoccer / SoccerReplay-1988 are soccer-understanding, commentary/temporal-alignment, and replay-adjacent near-neighbors. None establishes all four required predicates: semantic soccer-play question, semantic answer, separately submitted answer-linked pitch-coordinate/region/trajectory payload, and external scoring of that linked field payload.
- **Source:** Immutable source packet `artifacts/answer-conditioned-field-citation-scout-batch2-2026-08-10/candidate-ledger.json` with hash-bound snapshots; accepted independent QA `artifacts/answer-conditioned-field-citation-scout-batch2-final-qa-2026-08-10/receipt.json`.
- **Exact support:** Source verifier `36/36`; independent QA `205/205`, protected inputs `24/24`, executable copied-packet mutations `6/6`, and project suite `23 passed`.
- **Result class:** `BOUNDED_NEGATIVE_WITH_CITATION_NEIGHBORS`; `exact_match_established=false`.
- **Caveat/consequence:** Selected three-candidate neighborhood only; not global absence, systematic review, novelty authorization, rights determination, acquisition authority, model execution, or independent source-group validation.

## E-022 — 2026-08-21 — Living frontier scan narrows the remaining research hypothesis
- **Fact status:** Source-grounded public primary-source scan; not systematic or exhaustive, not independently QA-reviewed, and not a novelty authorization. Author metrics, dataset rights, and model behavior were not reproduced.
- **Claim:** E-VQA / ST-Evidence establishes joint semantic answers, temporal spans, and tracked dense video evidence; SportsTime / CoTR establishes sports QA with stepwise timestamp evidence; TimeLens2 establishes question-form, multi-interval temporal grounding; and GroundFormer establishes same-clip question-invariance diagnostics. SoccerNet 2026, SVI-Bench, and SoccerLens were also refreshed. These sources make generic answer-plus-video evidence, sports temporal reasoning, multi-interval grounding, and question-conditioned grounding predecessor territory.
- **Source:** `experiments/2026-08-21-frontier-literature-delta.md` (SHA-256 `0f48f4acc21c04761a279f6fed59d0429ad5fb489160a55dfb3b0afe5123338f`) and the ten exact public URLs recorded there.
- **Project implication:** Retain only a conditional working hypothesis around fine-grained short soccer QA with separately submitted answer-linked pitch coordinates/regions/trajectories, evidence-validity-aware calibrated abstention, question-discriminative grounding, and controlled direct-versus-tool evaluation.
- **Caveat:** No exact-match, global-absence, legal-rights, or publication-novelty conclusion follows from this living scan. No data, video, checkpoint, model, terms acceptance, or external submission was used.

## E-023 — 2026-08-21 — Hash-bound local VLM execution verifies interface plumbing only
- **Fact status:** Verified loopback execution and protocol receipt; outputs are unadjudicated observations, not truth labels or performance evidence.
- **Claim:** `zai-org/glm-4.6v-flash` received three chronological contact sheets from the hash-bound 8.008-second CC BY 2.0 pilot in direct and source-assisted conditions. The run exposed and repaired an LM Studio structured-output compatibility defect by replacing unsupported `json_object` mode with an explicit JSON schema. The packet verifier passed 27/27 checks and the project suite passed 25 tests.
- **Source:** `experiments/2026-08-21-local-vlm-smoke.md` (SHA-256 `c9eabed7059d40252e7df28ab5402aba60d59806bf8d33e4eec80a23957a9909`); `artifacts/local-vlm-smoke-2026-08-21/receipt.json` (SHA-256 `9548dbcfdbf0daec8137fec92d29b940a0488c9e75cb9d047eb16c4a27573806`), `manifest.json` (`b231a5fff24047b73b89c76ecf60cc04d463bf8b6d88acfa645aa247794d891f`), and `verify_smoke.py` (`9a4942179a9c46f2b6d9699378126a0cbfa6582200083bf8f453bcfea8204c97`).
- **Observed failure boundary:** The direct output's narrow interval and trajectory are unverified. The tool condition largely repeated the supplied unadjudicated interval and pitch region, so it does not demonstrate independent visual verification or a tool benefit.
- **Caveat:** `performance_claim_allowed=false`. One unadjudicated, convenience-sampled clip under unequal failure-recovery conditions cannot support accuracy, grounding, calibration, latency, coach-utility, generalization, or direct-versus-tool comparison claims.

## E-024 — 2026-08-21 — Iteration-57 hard-negative retrieval and commentary-alignment primary-source delta
- **Fact status:** Verified public primary-source additions from immutable arXiv HTML/abstract endpoints and one official author repository; author metrics and rights were not reproduced or independently adjudicated.
- **Claim:** Negative-Aware Video Moment Retrieval (arXiv `2502.08544v2`) makes irrelevant-query rejection an explicit retrieval objective and separates in-domain from out-of-domain negatives. MVMR (arXiv `2309.16701v4`) evaluates retrieval against multiple distractor videos and names cross-directional hard-negative learning. MCAD (arXiv `2511.09448v1`) describes retrieving soccer commentary, player, and action cues for clip-level audio-description generation. These are three non-duplicate additions to the project’s hard-negative/commentary-alignment frontier; Soccer-GMR was detected as already recorded and excluded from the addition count.
- **Source:** `experiments/2026-08-21-iteration-057-hard-negative-commentary-frontier-delta.md`; primary URLs and exact discovery queries are recorded in that packet.
- **Exact support:** NA-VMR HTML HTTP 200, 271617 bytes, SHA-256 `8bb7c5c6d292bd27fd75b900583e283f622ddf7a6a7c671fafa65bf7118d648d`; MVMR HTML HTTP 200, 286157 bytes, SHA-256 `4da50a2dc0a93fafd2154378307d0aa7cc37606037ad4a4e1254b4b67384faaa`; MCAD HTML HTTP 200, 281461 bytes, SHA-256 `d331b130c6fd1c7ed2541802df8a7381c32cf2f52350a183cf133e9cbbe5abe7`.
- **Project implication:** Future retrieval QA should separate null/irrelevant-query rejection, semantically close distractor rejection, and commentary-span versus visual-moment agreement. These sources support protocol design only; they do not establish a soccer benchmark result, commentary ground truth, field-coordinate scoring, calibrated abstention, coach utility, novelty, or rights eligibility.
- **Caveat/consequence:** The delta is bounded and non-systematic. No data, media, model, checkpoint, restricted source, terms, license acceptance, external communication, or local experiment code was acquired or modified. `performance_claim_allowed=false`; `novelty_claim_allowed=false`; result class `BOUNDED_PRIMARY_SOURCE_DELTA_NO_EXECUTABLE_RESULT`.

## E-025 — 2026-08-21 — Intentionally corrupted tool-evidence probe is structural evidence only

- **Fact status:** Verified hash-bound local protocol execution; output remains unadjudicated and metric-ineligible.
- **Claim:** One loopback request to `zai-org/glm-4.6v-flash` supplied a visibly labeled, intentionally wrong `corner kick` tool payload with an incompatible interval and pitch region. The returned JSON abstained with confidence zero and empty temporal, spatial, and trajectory fields.
- **Source:** `experiments/2026-08-21-local-vlm-evidence-corruption.md`; receipt, manifest, raw request/response, and verifier under `artifacts/local-vlm-evidence-corruption-2026-08-21/`.
- **Exact support:** Fresh verifier PASS `24/24`; receipt SHA-256 `c7a06fde852f21664396149aea6a1c8188edb9d46773ce8b7dd3b60e60ba8b02`; `performance_claim_allowed=false`; `realDataExperimentResults=null`.
- **Caveat/consequence:** This one structural observation does not establish accuracy, causal resistance, grounding, calibration, abstention quality, latency, tool benefit, or model performance. The clip remains unadjudicated and ineligible for metrics.

## E-026 — 2026-08-21 — Same-clip hard-negative and out-of-clip null-query probe is structural evidence only

- **Fact status:** Verified hash-bound local protocol execution; outputs remain unadjudicated and metric-ineligible.
- **Claim:** Two loopback requests showed the same contact sheets with distinct questions. The hard-negative corner-kick output answered `no` with empty evidence; the explicitly out-of-clip next-minute query abstained with confidence zero. Both responses were parseable and contained the required fields.
- **Source:** `experiments/2026-08-21-iteration57-same-clip-null-query.md`; receipt, manifest, exact prompts, raw responses, and verifier under `artifacts/local-vlm-iteration57-same-clip-2026-08-21/`.
- **Exact support:** Fresh verifier PASS `43/43`; receipt SHA-256 `2e2511071afa28b086424e6ed3e3e67265d7704dcaae0b75c2c3793077309b15`; project suite `25 passed`; `realDataExperimentResults=null`.
- **Caveat/consequence:** These are model-output facts, not validated answers. They do not establish answer accuracy, question discrimination, temporal/spatial grounding, calibration, latency, tool benefit, coach utility, or model performance.

## E-027 — 2026-08-22 — Legacy soccer project contributes verified methodology fixtures only

- **Fact status:** Byte-identical local import with fresh validator passes.
- **Claim:** The retired `soccer-research` workspace contained one useful non-duplicative methodology unit: a two-clip synthetic annotation fixture with three records and a human-gated disagreement, plus a five-dimension fixed-prompt/faithfulness schema. It contained no real media or empirical result.
- **Source:** `artifacts/legacy-soccer-methodology-import-2026-08-22/manifest.json` and `handoff.md`.
- **Exact support:** Imported-file hashes match the source workspace; synthetic annotation validator PASS and fixed prompt packet validator PASS. The source workspace was preserved rather than deleted.
- **Caveat/consequence:** This is methodology and provenance evidence only. It does not establish real-data quality, model performance, data rights, publication approval, or novelty. Future changes should version the imported fixtures instead of rewriting their historical `projectId` values.

## E-028 — 2026-08-21 — Coaching-document QA and fine-grained soccer retrieval scan

- **Fact status:** Bounded public primary-source scan; author metrics, data rights, and reproducibility were not independently established.
- **Claim:** SoccerNet-Echoes, GOAL, SoccerNet Caption, and StreamSoccer provide speech/commentary, timestamped event text, and event-memory components; *Synthesizing the Expert* and ExpertAF provide coaching-QA/feedback analogues. Soccer-GMR directly precedes null-set, single-moment, and multi-moment soccer retrieval; TacticAI, TacticGen, and SoccerNet game-state work provide tactical geometry/trajectory infrastructure. No inspected source jointly established independent coaching documents, answer-to-source-video citations, season/player narrative joins, and evidence-aware abstention.
- **Source:** `experiments/2026-08-21-coaching-document-and-fine-grained-retrieval-scan.md`, SHA-256 `b354d20977430e840a24c1278d1b7f653a752620c0483ccc08d2ab7f68d33210`.
- **Project implication:** Use a provenance-rich document graph for Track A. For Track B, benchmark a semantic-only Soccer-GMR-style set retriever first, then test trajectory-aware reranking only on eligible data with homography, track-quality, and abstention gates.
- **Caveat/consequence:** The scan is bounded, not exhaustive. No data, media, model, checkpoint, restricted source, terms, external communication, author metric, rights decision, global-absence result, or novelty authorization was produced.

## E-029 — 2026-08-23 — Receipt-bound trajectory-grounding delta supplies protocol components, not a coach-QA result

- **Fact status:** Bounded public primary-source metadata review with hash-bound response receipts; source-reported results were not reproduced.
- **Claim:** PnLCalib (`arXiv:2404.08401v5`) records a broadcast-sports field-registration pipeline using a 3D soccer-field model, keypoints, detected field lines, and nonlinear refinement. U2Diffine (`arXiv:2605.10717v1`) records multi-agent trajectory completion with state-wise heteroscedastic uncertainty and per-generated-mode error-probability estimation, naming Soccer-U among its reported sports datasets. These are two complementary protocol precedents for retaining a geometry receipt and a trajectory-uncertainty field with future source-video spatial evidence.
- **Source:** `experiments/2026-08-23-iteration56-trajectory-grounding-receipt-delta.md`; immutable query/source/header receipts and manifest under `artifacts/iteration56-trajectory-grounding-delta-2026-08-23/`.
- **Exact support:** `verify_receipts.py` is the deterministic receipt verifier; it hashes three discovery responses, two source API records, and two HTTP-header receipts, then checks both canonical URLs against the corresponding source record. Expected result: `PASS: 7 receipt hashes and 2 canonical URLs verified`.
- **Project implication:** A future, separately approved local protocol may require `sourceVideoId`, frame/time interval, calibration receipt/version, coordinate convention, player/ball track points/IDs, geometry/track validity, and uncertainty before it treats a spatial claim as eligible; absent/failed fields can be an abstention gate.
- **Caveat/consequence:** This is a design hypothesis, not a claim of calibrated abstention, player/ball reconstruction, source-video citation, coach utility, model performance, novelty, or rights clearance. PnLCalib does not establish QA/tracks/abstention; U2Diffine does not establish video reconstruction, pitch calibration, QA, or coach utility. No data, media, checkpoint, code, restricted asset, terms acceptance, deployment, commit, or external action occurred.

## E-030 — 2026-08-25 — Current SportD version expands the decision benchmark but remains a distinct task

- **Fact status:** Verified current primary-paper version; author-reported figures were not independently reproduced, and no data, media, code, or checkpoint was acquired.
- **Claim:** SportD v4 reports a value-grounded strategic-choice benchmark with 1,415 on-ball decisions from the 2022 men's and 2023 women's World Cups. Its best tested VLM reaches 34.3% action accuracy, compared with 40.4% for real players in the paper's evaluation. The task evaluates forward-looking action selection using possession value and regret, rather than a semantic answer with separately submitted temporal and pitch/trajectory evidence.
- **Source:** Jasin Cekinmez et al., *SportD: How do VLMs physically strategize?*, arXiv `2607.14616v4`, revised 2026-08-14: https://arxiv.org/html/2607.14616v4
- **Accessed:** 2026-08-25.
- **Evidence class:** Primary versioned arXiv HTML; current-version author-reported results, not locally reproduced and not yet bound to a local receipt packet.
- **Project implication:** SportD is a strong soccer-reasoning frontier and should be cited in presentations, but it does not replace the proposed PlayGround answer-and-evidence contract.
- **Caveat/consequence:** v4 supersedes the smaller v2 snapshot previously summarized in the project. These are author-reported results, not local replications. Paper licensing does not establish rights to underlying match footage or benchmark redistribution, and the evidence does not authorize a novelty claim.

## E-031 — 2026-08-27 — FootballMaster-Pilot verifies a trained dual-sport pipeline, not football understanding

- **Fact status:** Locally executed and independently verified real-video pilot with immutable package/data receipts; statistically and semantically ineligible for a performance or coaching claim.
- **Claim:** Nine Creative Commons American-football clips from eight whole-source groups were hash-audited, fully decoded, split 4/2/3 by `source_id`, and used to fit train-only standardization/PCA plus a binary softmax head over frozen MobileNetV2 frame scores. The three-source test produced 2/3 correct, macro-F1 0.667, balanced accuracy 0.75, and confusion matrix `[[1,0],[1,1]]`, versus 1/3 for the train-majority baseline. The Wilson 95% accuracy interval is 0.208–0.939, and one source-labeled touchdown was predicted not-touchdown with a 0.9494 predicted-class score.
- **Source:** `data/public/footballmaster/verification-receipt.json`; `artifacts/footballmaster/pilot-v1/run-receipt.json`; `artifacts/footballmaster/pilot-v1/metrics.json`; `artifacts/footballmaster/pilot-v1/predictions.jsonl`; synthesis and citations in `research/footballmaster-dual-sport-technical-report-2026-08-27.md`.
- **Exact support:** Manifest verifier PASS for nine clips/eight source groups with no cross-split source overlap; package verifier PASS for all nine immutable bindings; clean retraining reproduced the same test metrics; complete repository suite PASS 220/220.
- **Result class:** `DESCRIPTIVE_REAL_VIDEO_PIPELINE_RESULT`; `performance_claim_allowed=false`.
- **Caveat/consequence:** Only `is_touchdown` is learned. Fine event labels are source-description weak metadata, football prose is deterministic, and no detailed report was VLM-authored. The sample has three test clips, one practice-domain negative, no independent label adjudication, no player/tactic/play-boundary target, no calibration, no whole-game evaluation, and no coach validation. This is not a SoccerMaster replication, foundation model, football VLM, comparative benchmark, or novelty authorization.
