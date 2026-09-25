# From SoccerMaster research to FootballMaster-Pilot: a dual-sport, evidence-first video-search system

**Prepared:** August 27, 2026 (America/New_York)  
**Evidence snapshot:** Football package generation `3eb10b5935ca0649f5b6222e`, completed August 28, 2026 at 00:14 UTC  
**Audience:** Archit and other computer-vision, machine-learning, and sports-analytics reviewers  
**Decision supported:** whether the current prototype is ready for a technical demonstration and what evidence is required before asking UMD coaches to evaluate it  
**Evaluation unit:** one rights-audited video clip; whole source video/session is the split unit  
**Comparison basis:** FootballMaster-Pilot versus the deterministic train-majority baseline on three source-held-out clips  
**Status:** engineering/demo path verified; scientific performance and coaching-utility claims blocked

## Abstract

This project now provides one local interface over two deliberately different research paths. The **soccer path** converts a real 30-second SoccerNet review window into saved vision-language-model (VLM) event reports and lets a local language model translate a coach's query into a visible retrieval plan. The complete retrieval path works, but the saved soccer semantics are factually wrong against separately loaded held-out annotations; its honest status is **SYSTEMS GO / SEMANTIC NO-GO**. The **American-football path** trains a real but tiny visual classifier on nine Creative-Commons clips from eight source groups. It uses frozen ONNX MobileNetV2 ImageNet frame descriptors, fixed temporal pooling, train-only standardization/PCA, and an eight-parameter supervised softmax head for one binary target: `is_touchdown`. On three source-held-out test clips it classified 2/3 correctly versus 1/3 for the train-majority baseline, with a 95% Wilson accuracy interval of 0.208–0.939 and one 94.9%-score wrong prediction. These numbers verify the pipeline, not generalization.

The result is **not a SoccerMaster replication, not a football VLM, not coach validated, and not a whole-game understanding system**. No detailed football report was VLM-authored. The defensible contribution is a reproducible scaffold that makes model, metadata, deterministic retrieval, rights, and held-out evidence separable enough to evaluate honestly. The next decision should come from a small, post-game UMD shadow pilot with coach-authored questions and game-held-out adjudication—not from scaling the current point estimate. Local measurements are bound to the [metrics artifact](../artifacts/footballmaster/pilot-v1/metrics.json), [model card](../artifacts/footballmaster/pilot-v1/model-card.json), [run receipt](../artifacts/footballmaster/pilot-v1/run-receipt.json), and [predictions](../artifacts/footballmaster/pilot-v1/predictions.jsonl).

## Technical summary: the scaffold is real; the semantic claims remain narrow

- **Football training is real but intentionally minimal.** Four training clips fit a three-component PCA representation and a two-class linear head; two validation clips select the final epoch; three independent source groups form the test. The defined fitted PCA/head parameter count is 9,008, of which only 8 are supervised parameters. The inherited MobileNetV2 weights are frozen and were not trained here. [Model configuration](../artifacts/footballmaster/pilot-v1/model-config.json)
- **The only measured football task is touchdown versus not touchdown.** Fine tags such as `touchdown_pass`, `kickoff_return`, and `interception_practice` are weak source-description metadata, not classifier outputs. Player identity, formation, coverage, route, blocking, pressure, tackle, down/distance, and tactical intent are not inferred. [FootballMaster model report](footballmaster-pilot-model-2026-08-27.md)
- **The test result is descriptive, not decision-grade.** Accuracy is 0.667 (2/3) versus 0.333 (1/3) for the baseline, but the interval is extremely wide, labels are not independently adjudicated, and the model confidently misses a source-labeled Chiefs–Buccaneers touchdown pass. `performance_claim_allowed` is therefore `false`. [Metrics](../artifacts/footballmaster/pilot-v1/metrics.json)
- **The soccer result is a useful negative result.** The UI retrieves three saved VLM cards from one real 30-second SoccerNet clip, yet the report describes a save/clearance and invents set-piece/build-up sequences where held-out annotations show a penalty, shot on target, and goal. The labels are loaded only after inference for audit. [SoccerMaster/VLM research brief](archit-next-meeting-soccermaster-brief-2026-08-27.md)
- **The interface preserves attribution.** Soccer event semantics are VLM-authored; football's binary probability is learned; football fine labels come from source metadata; football prose and ranking are deterministic; the query LLM sees only the coach query and selected ontology. [Dual-sport backend](../prototype/multisport_search_demo_server.py)
- **The UMD value proposition is still a hypothesis.** The credible pitch is a post-game search assistant that returns evidence-linked cutups for human review, not an autonomous coach or live sideline analytics product. [UMD pilot memo](umd-coach-search-pilot-memo-2026-08-27.md)

## The research translation is not a SoccerMaster replication

[SoccerMaster](https://haolinyang-hlyang.github.io/SoccerMaster/) is a soccer-specific vision foundation model, not an instruction-following chat model or a natural-language search engine. Its [paper](https://arxiv.org/html/2512.11016) describes a SigLIP2-initialized hierarchical ViT with 16 spatial and 8 spatiotemporal blocks, 30-frame 512×512 inputs, task heads for spatial perception, a 24-way soccer event task, and video–commentary alignment. The authors report roughly 7.45 million frames across 248,300 segments and about nine days of full-precision training on 16 NVIDIA H800 GPUs. Their reported 77.2% closed-set event accuracy is under their own event-centered protocol; it is neither a local result nor evidence about false positives over a full match.

| Dimension | SoccerMaster, as reported by its authors | This project: FootballMaster-Pilot v1 | Consequence |
|---|---|---|---|
| Research object | Soccer-specific visual foundation encoder plus task heads | Small frozen-image-descriptor probe plus search scaffold | A research translation, not an architectural copy |
| Visual input | 30 frames at 512×512 | 8 uniformly sampled frames at 224×224 | Football pilot has much weaker temporal and spatial capacity |
| Pretraining | Multi-task soccer pretraining on millions of frames | Frozen ImageNet MobileNetV2 inherited weights; no football backbone pretraining | No football foundation-model claim |
| Learned semantic output | Author-reported 24-way soccer event head and alignment embedding | Binary `is_touchdown` softmax head only | Fine football semantics remain unmeasured |
| Local training scale | Not locally reproduced; reported 16 H800 GPUs for about nine days | 4 train clips; CPU run in 6.766 seconds | Metrics are not comparable |
| Detailed natural-language report | Not native to the released encoder/head | None from the football model | A future language/report adapter must be evaluated separately |
| Search product | Not validated by the paper | Local query planning plus deterministic search over persisted records | Product plumbing does not establish model understanding |

The safe statement is: **SoccerMaster motivates separating sport-specific visual representations from downstream language and retrieval, while FootballMaster-Pilot verifies a much smaller football data/training/evaluation interface.** Any claim that this repository trained, reproduced, or ported SoccerMaster would be false. The full comparison and release audit are preserved in the [SoccerMaster technical brief](archit-next-meeting-soccermaster-brief-2026-08-27.md).

## Evidence-first interaction follows Dr. Tica Lin's research direction

Dr. Tica Lin's sports systems motivate the product architecture without validating this model. [Sportify](https://arxiv.org/abs/2408.05123) combines action/tactic pipelines and structured game context with a text-only LLM and embedded basketball visualizations; the relevant design principle is to make structured evidence an input to explanation rather than treat fluent prose as evidence. [VIRD](https://arxiv.org/abs/2307.12539) connects summaries, rallies, shots, poses, trajectories, reconstructed views, and source video for expert inspection. [Who's That Player?](https://vcg.seas.harvard.edu/publications/who-s-that-player) shows that exposing a system's interpretation can improve inspectability, while also showing that visibility alone does not guarantee users repair a wrong interpretation.

Those works support three separable evaluation layers:

1. **Perception:** what can be recovered from video, and with what temporal/spatial evidence?
2. **Explanation and retrieval:** can a query map to the right stored evidence without changing the underlying claim?
3. **Human verification:** can an expert detect, correct, or reject an error faster and more reliably?

This framing also aligns with [SoccerNet-v2](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/html/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.html), which separates action spotting, camera segmentation, and replay grounding over long broadcasts; [NExT-GQA](https://openaccess.thecvf.com/content/CVPR2024/html/Xiao_Can_I_Trust_Your_Answer_Visually_Grounded_Video_Question_Answering_CVPR_2024_paper.html), which evaluates answers together with supporting moments; and a narrow [American-football formation study](https://openaccess.thecvf.com/content_cvpr_workshops_2013/W19/html/Atmosukarto_Automatic_Recognition_of_2013_CVPR_paper.html), which demonstrates that real-game formation/line-of-scrimmage automation is possible while not establishing a modern multimodal coach-search system. The research gap is therefore not “sports VideoQA is new”; it is whether sport-specific evidence improves detailed, falsifiable, evidence-linked retrieval under source-held-out evaluation.

## Nine real clips verify rights, integrity, and source isolation—not football understanding

The corpus contains nine Wikimedia Commons-hosted 480p VP9 clips from eight independent game/practice source groups: 21.94 MiB and 151.893 seconds total. Every clip has a canonical file page, creator/source record, CC BY or CC BY-SA license evidence, reuse conditions, immutable hash binding, and a full FFmpeg decode-to-null pass. The FAU–UCF touchdown and kickoff come from the same game and remain together in training. No `source_id` crosses splits. Audio is excluded from model input. [Rights and split audit](footballmaster-public-data-rights-and-split-2026-08-27.md)

| Split | Clips | Independent source groups | Not touchdown | Touchdown | Use |
|---|---:|---:|---:|---:|---|
| Train | 4 | 3 | 2 | 2 | Fit standardization, PCA, and head |
| Validation | 2 | 2 | 1 | 1 | Select epoch only; no taxonomy or feature changes |
| Test | 3 | 3 | 1 | 2 | One final source-held-out descriptive audit |
| **Total** | **9** | **8** | **4** | **5** | Pipeline feasibility only |

The figure below makes the split constraint visible: both binary classes appear in every split, while source groups—not frames—are the holdout unit. It is a data-integrity picture, not evidence that nine clips cover football's visual distribution.

![Whole-source held-out split: four train, two validation, and three test clips, with both binary classes in every split](../presentation/figures/FootballMaster-source-heldout-split-2026-08-27.png)

*Actual-data figure generated from `examples.jsonl` and the manifest verification receipt; 151.893 seconds total.*

The target is a frozen transform of source-supported weak tags: `touchdown_pass` and `rushing_touchdown` map to touchdown; `kickoff_return`, `field_goal_attempt`, and `interception_practice` map to not touchdown. These are **source-description weak labels**, checked for visual plausibility but not independently annotated ground truth. A filename containing “touchdown” is never a visual feature, although the source description is necessarily used to construct the weak training target. The separate search index retains those descriptions as visibly attributed metadata.

The rights decision is narrower than “publicly available.” [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia) requires attention to each file's creator, attribution, license link, and ShareAlike conditions. [Creative Commons' AI-training guidance](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/) recommends a conservative treatment of BY/SA obligations, and the [Creative Commons FAQ](https://creativecommons.org/faq/) explains that copyright licenses may not clear publicity, privacy, trademark, or other third-party rights. Local video-only research is admitted; third-party VLM upload is not authorized by this manifest; public release of trained weights remains on hold for institutional review. This is a technical rights gate, not legal advice.

## The trained model is a frozen visual baseline plus 9,008 fitted PCA/head parameters

```text
rights-approved clip pixels; audio excluded
        │
        ├── 8 uniform RGB frames, resized to 224×224
        │
        ├── frozen ONNX MobileNetV2 / ImageNet
        │      1,000 inherited class scores per frame
        │
        ├── fixed temporal pooling
        │      mean + standard deviation + (last − first)
        │      → 3,000-dimensional clip descriptor
        │
        ├── train-only mean/scale + PCA via SVD
        │      requested 16 components; 3 available with 4 train clips
        │
        └── trained two-class linear softmax head
               → touchdown / not_touchdown + uncalibrated score
```

The frozen backbone is the official [ONNX Model Zoo MobileNetV2](https://github.com/onnx/models/tree/main/validated/vision/classification/mobilenet), an Apache-2.0 ImageNet 1,000-class image classifier. This project uses its 1,000 output scores as inherited frame descriptors; it neither retrains the backbone nor claims those scores are football concepts. The [model configuration](../artifacts/footballmaster/pilot-v1/model-config.json) fixes 8 frames, ImageNet RGB normalization, mean/standard-deviation/endpoint-difference pooling, CPU execution, train-only preprocessing, inverse-frequency class weighting, 500 epochs, learning rate 0.05, L2 0.1, and zero-initialized softmax weights. The selected epoch is 500.

| Fitted or inherited state | Count | Label supervision? | Attribution |
|---|---:|---|---|
| Frozen MobileNetV2 file | 13,964,571 bytes | No | Inherited ImageNet weights; excluded from learned count |
| Training mean and scale | 6,000 statistics | No | Fitted on four training clips; excluded from parameter count |
| PCA projection | 3 × 3,000 = 9,000 coefficients | No | Train-fitted unsupervised representation |
| Softmax head | 3 × 2 weights + 2 biases = 8 parameters | **Yes** | Supervised by weak binary labels |
| **Defined learned PCA/head total** | **9,008 parameters** | 8 supervised | Model-card accounting |
| **Total persisted fitted numeric state** | **15,008 values** | 8 supervised | Mean/scale + PCA + head |

Calling all 9,008 parameters “supervised” would be wrong: 9,000 come from train-only PCA and 8 from label optimization. Calling the model untrained would also be wrong: the PCA and head are fitted and checkpointed. The exact boundary is encoded in the [model card](../artifacts/footballmaster/pilot-v1/model-card.json).

## The only measured football task beats the baseline on three clips, but uncertainty dominates

The test cohort is three clips from three source groups unseen during fitting or validation. The train-majority implementation predicts `not_touchdown`; because train is tied 2–2, that class is a deterministic tie choice rather than evidence of a dominant training class. The test numbers below were independently recomputed from the three rows in [predictions.jsonl](../artifacts/footballmaster/pilot-v1/predictions.jsonl) and match [metrics.json](../artifacts/footballmaster/pilot-v1/metrics.json).

| Measure | FootballMaster-Pilot | Train-majority baseline | Interpretation |
|---|---:|---:|---|
| Accuracy | 0.667 (2/3) | 0.333 (1/3) | One additional correct clip; too few for a population claim |
| Balanced accuracy | 0.750 | 0.500 | Average recall across the two classes |
| Macro F1 | 0.667 | 0.250 | Equal-weight average of both class F1 values |
| Accuracy 95% Wilson interval | 0.208–0.939 | 0.061–0.792 | Uncertainty spans weak through strong performance |

The chart pairs the three point metrics with the confusion matrix so the denominator cannot disappear. The model has one true negative, one true positive, and one false negative; the red footer carries the interval and performance-claim boundary that must accompany the bars.

![FootballMaster held-out descriptive metrics and two-class confusion matrix](../presentation/figures/FootballMaster-heldout-performance-2026-08-27.png)

*Actual-data figure generated from `metrics.json`; `n=3` source-held-out clips and no performance claim.*

Confusion matrix, rows = weak source label and columns = model prediction:

|  | Predicted not touchdown | Predicted touchdown |
|---|---:|---:|
| Actual not touchdown | 1 | 0 |
| Actual touchdown | 1 | 1 |

The point estimate is not a significance result and should not be compared directly with SoccerMaster's author-reported 24-way accuracy. Its value is diagnostic: the pipeline can train, checkpoint, verify, score an untouched source split, and expose a failure.

| Held-out clip | Weak source label | Probe output | Score for predicted class | Result |
|---|---|---|---:|---|
| Chiefs–Buccaneers 2024 | touchdown pass → touchdown | not touchdown | 0.9494 | **Wrong** |
| Falcons minicamp 2018 | interception practice → not touchdown | not touchdown | 0.9996 | Correct, but practice-domain negative |
| SMU–Louisville 2025 | touchdown pass → touchdown | touchdown | 0.9424 | Correct |

The Chiefs–Buccaneers error is the strongest finding. A wrong answer with a 0.9494 softmax score demonstrates that the score is not calibrated probability and that the model can be confidently wrong. The interface should foreground this counterexample rather than show only the successful SMU clip.

## Soccer is systems-go and semantic-no-go

The soccer mode contains one real, silent, 30-second SoccerNet review clip and three saved Gemma VLM event cards. The query LLM and retrieval code work: a natural-language query becomes a strict soccer plan; deterministic ranking returns cards; a result seeks the local clip to the stored timestamp. However, the VLM report contradicts separately loaded held-out annotations. The clip contains a visible penalty, shot on target, and goal around 14.5–15.0 seconds into the review window; the report instead describes a goalkeeper save/clearance and invents corner/build-up sequences. Matched 20-, 30-, and 60-second reports and denser ten-second reporting over the same minute recovered 0/4 strict timestamp-aligned target events. This is a selected one-match engineering study, not a benchmark. [Soccer research truth boundary](archit-next-meeting-soccermaster-brief-2026-08-27.md)

The separation matters:

- held-out SoccerNet labels are not sent to the visual reporter or query LLM;
- the UI loads them only in a post-hoc audit panel;
- saved soccer semantics are attributed to the VLM;
- query interpretation and deterministic ranking do not repair a wrong underlying report;
- no soccer weights were fine-tuned in this project.

The correct presentation statement is: **the retrieval and evidence plumbing works; the local soccer semantics do not yet support coaching use.**

## One interface exposes two ontologies and four claim origins

```text
coach query
   │
   ├── selected sport + public ontology only
   ▼
local query LLM ──invalid/offline──► labeled literal fallback
   │ strict validated plan
   ▼
deterministic ranker over one selected persisted index
   │
   ├── Soccer index
   │      saved VLM event cards + private real clip
   │      held-out annotations loaded only after search for audit
   │
   └── Football index
          learned binary probability/embedding
          + weak source tag
          + deterministic prose projection
          + rights-audited real clip
   ▼
result card: timestamps + source clip + uncertainty + claim-origin ledger
```

The [backend](../prototype/multisport_search_demo_server.py) binds only to loopback and defaults to `http://127.0.0.1:8771/`. The [UI](../prototype/search_demo_ui/app.js) keeps the sport in the URL, swaps the ontology and copy, shows the query trace, loads result-specific media, and surfaces evaluation and attribution instead of presenting all fields as model output.

| Contract | Request | Purpose |
|---|---|---|
| `GET /healthz` | none | Whether either sport package is locally available |
| `GET /api/sports` | none | Available sport names, ontologies, counts, and warnings |
| `GET /api/status?sport=soccer\|football` | selected sport | Model/package status, pipeline, evaluation, and claim boundary |
| `POST /api/search` | `{"sport":"football","query":"Find the Chiefs Buccaneers touchdown pass"}` | Query interpretation plus ranked saved events |
| `/media/soccer/...`, `/media/football/...` | allowlisted route, optional byte range | Local evidence playback with seeking |

The query LLM is a planner, not a video model. It receives only the coach's text and the selected sport's allowed event/phase/area values. It never receives video, audio, weak labels, held-out annotations, model probabilities, or audit results. The validated plan then drives deterministic ranking. If the local model is unavailable or returns invalid JSON, a visible literal keyword fallback is used; the UI does not silently relabel it as LLM output.

| UI field or behavior | Soccer origin | Football origin |
|---|---|---|
| Event description and evidence frames | Saved local VLM report | No VLM field; deterministic prose and empty evidence frames |
| Fine event type | Saved local VLM report | Commons source-description metadata |
| Touchdown probability/label | None | Learned PCA/softmax probe |
| Player identity | Role-only VLM text, often unsupported | Empty; not inferred |
| Query plan | Local query LLM or labeled literal fallback | Same, with football ontology |
| Ranking and time projection | Deterministic | Deterministic |
| Held-out/reference label | Separate post-hoc audit only | Evaluation artifact/source metadata, never sent to query LLM |

## Leakage and threat model: guarded paths and remaining failures

| Threat | Current control | Remaining gap |
|---|---|---|
| Same-game/source leakage | Whole `source_id` is confined to one split; both FAU–UCF clips stay in train | Eight source groups are too few to rule out venue/team/camera shortcuts |
| Filename/source-text leakage into visual model | Descriptor receives decoded RGB frames only; source text is not a visual feature | A filename-randomization invariance test is recommended but not yet recorded |
| Audio/commentary leakage | `audio_in_model=false`; model uses video frames only | Audio layers were not independently rights-audited; future commentary must remain a separately scored branch |
| Held-out-label leakage into search planner | Query LLM receives only query + ontology; soccer audit is post hoc | Search records intentionally contain attributed source metadata in football mode; that search demo must not be presented as learned fine-event recognition |
| Path traversal or arbitrary file serving | Package hashes are verified; media paths must remain under the exact allowlisted root; server is loopback-only | This is a local prototype, not a complete multi-user security review |
| Overconfidence | UI labels uncertainty and exposes source video; high-confidence miss is retained | Softmax scores are not calibrated; no abstention threshold is validated |
| Weak-label error | Label provenance and non-adjudicated status are explicit | Two independent football reviewers and event boundaries are still required |
| Domain shift | Test is source-held-out | One test negative is minicamp; views, leagues, venues, and eras are heterogeneous and unbalanced |
| Pretraining overlap | MobileNetV2 is documented as ImageNet-pretrained, not football-video-trained | Exact image-level pretraining overlap cannot be proven from the public model metadata |
| Rights and privacy | Per-file CC evidence, attribution, hashes, local use, no third-party upload | Weight sharing, ShareAlike, publicity, trademark, team-film, and student-athlete governance need institutional review |

## Coach value is a set of testable hypotheses, not a result

Official coaching-analysis material supports the *workflow categories*, not the prototype's usefulness. [FIFA's football language](https://www.fifatrainingcentre.com/en/game/performance-analysis/football-language-analysis/the-fifa-football-language.php) formalizes phases such as build-up, progression, pressing, blocks, and recovery; FIFA also documents [pairing training and match examples](https://www.fifatrainingcentre.com/en/environment/expert-knowledge/david-aznar-on-training-and-match-application.php). [U.S. Soccer](https://www.ussoccer.com/stories/2018/09/us-wnt-benefits-from-expanded-high-performance-department) describes performance analysis supporting in-game, opposition, and pre-game work. The NFL describes [All-22 and play isolation](https://operations.nfl.com/rules-officiating/officiating/performance-evaluation/) and [situation-specific digital cutups](https://www.nfl.com/news/when-it-comes-to-film-study-coaches-have-entered-the-digital-ag-09000d5d80c3eb01). None of those sources validates this model.

| Sport | Candidate coach searches | Evidence contract that would be required |
|---|---|---|
| Soccer | tactical sequences; transition/counter-press review; player receiving/body orientation; opponent/set-piece scouting; practice-to-match transfer | continuous clock, live/replay state, possession/phase, pitch region, player/unknown identity, action chain, outcome, evidence interval/region, view quality, uncertainty |
| American football | situation-specific cutups; opponent tendencies; position-room technique; self-scout/counter-tendency; practice/game and special-teams pairing | play boundaries, down/distance, field/hash, clock/score, personnel, formation, motion, concept/coverage evidence, assignment/result, view limitation, uncertainty |

The current football pilot cannot answer those rich questions. It proves that the package and UI can carry a future sport-specific report while accurately labeling what is learned today. The product hypothesis is that an evidence-first system could reduce recurring cutup effort while leaving adjudication with the coach. That must be tested against the current workflow.

## UMD should be approached through a bounded post-game workflow

The [2026 Maryland football staff page](https://umterps.com/sports/football/coaches/2026) publicly lists a Director of Coaching Operations & Analytics, offensive and defensive analysts, a Director of Football Technology, a Video Coordinator, and an Assistant Video Coordinator. Those roles suggest the right *functions* for evaluation; they do not reveal UMD's tools, taxonomies, permissions, workload, or interest. The [men's soccer](https://umterps.com/sports/mens-soccer/coaches) and [women's soccer](https://umterps.com/sports/womens-soccer/coaches) pages list coaching and operations/support roles but no publicly named sport-dedicated analytics/video role, so each program should designate its actual workflow owner.

Version 1 should remain post-game and post-practice. The NCAA's [football technology rule explanation](https://www.ncaa.org/media-center-technology-rules-approved-in-football/) describes controlled in-game video tablet use while excluding analytics/data access, and the [current rules hub](https://www.ncaa.org/championships/playing-rules/football-playing-rules/) is the authoritative place to recheck current rules. A separate [2026 FBS replay-feed experiment](https://www.ncaa.org/fbs-oversight-committee-introduces-proposal-to-modify-football-calendar/) does not authorize this system. Compliance review is required before any live use.

The appropriate ask is not access to the archive. It is a 45-minute workflow interview and permission to define—not yet run—a four-week, read-only shadow pilot with one workflow owner and one media/compliance approver per participating program.

## A four-week shadow pilot can falsify the coaching-value hypothesis

This is a proposal, not a commitment, interview result, or statistically powered protocol. The starting scope from the [UMD pilot memo](umd-coach-search-pilot-memo-2026-08-27.md) is one designated soccer program plus Maryland football; two approved games/matches and one approved practice per sport, or the smallest permitted equivalent; about 100 coach-adjudicated soccer moments and 150 football plays; and 12 coach-written queries per sport frozen before final evaluation. The existing video system remains the source of record.

| Week | Activity | Exit evidence |
|---|---|---|
| 0 | Confirm rights, data location, retention, roles, baseline task, and forbidden uses | Signed-off workflow/data map and named owners |
| 1 | Coaches define terms, 12 queries per sport, and a balanced reference set including ambiguous/negative cases | Frozen taxonomy, queries, and game-level split |
| 2 | Run read-only shadow ingestion/retrieval without changing the current process | Timing, outputs, abstentions, and failure log |
| 3 | Blindly judge shuffled prototype and baseline cutups | Per-query relevance/completeness and reviewer agreement |
| 4 | Review failures by query, view, event, and identity; decide stop/revise/expand | Decision record and retention/deletion action |

Proposed starting gates, subject to coach revision:

| Dimension | Measure | Starting gate |
|---|---|---:|
| Retrieval usefulness | Coach-rated relevant clips among top five, reported per query | ≥80% |
| Coverage | Recall on manually enumerated held-out events/plays | ≥75% |
| Evidence grounding | Displayed report fields traceable to clip or approved metadata | ≥95% |
| Workflow speed | Median cutup-build time versus current baseline | ≥40% reduction |
| Trust behavior | Unsupported high-confidence statements | 0 |
| Operational fit | Successful import/open/export on pilot set | 100% |
| Governance | Unauthorized transfer/access/retention events | 0 |

Raw numerators/denominators and game-clustered uncertainty must accompany every percentage. An aggregate cannot hide failure on a critical query.

## Limitations and robustness interpretation

1. **Sample size:** three test clips yield an accuracy interval of 0.208–0.939. This does not estimate deployment performance.
2. **Weak labels:** source descriptions are not independent football annotation; temporal boundaries and tactical fields are absent.
3. **Task narrowness:** touchdown/not-touchdown is far short of coach search and does not test player-specific or tactical reports.
4. **Representation:** ImageNet class scores sampled eight times cannot model continuous ball/player trajectories or reliable pre/post-snap structure.
5. **PCA-to-sample ratio:** 9,000 fitted coefficients come from only four training clips; perfect train/validation results are expected to be fragile and are not evidence of efficiency.
6. **Calibration:** the 94.9%-score mistake falsifies any calibrated-confidence interpretation.
7. **Domain balance:** one test negative is practice footage; camera, team, venue, league, and event distributions are not controlled.
8. **Search versus recognition:** football search can retrieve fine tags because the index stores attributed source metadata. That validates search plumbing, not model recognition of those tags.
9. **Soccer semantic failure:** one real clip and a selected duration study do not rank models or explain causality; they only falsify readiness of the current saved reports.
10. **No coach validation:** no UMD coach has been interviewed or asked to judge these outputs.
11. **No whole-game claim:** the infrastructure is window/index oriented, but the demonstrated corpus is one soccer window plus nine short football clips—not an indexed match or game.
12. **No football VLM:** detailed football prose is deterministic and no football event report was VLM-authored.

## The next experiment should test report evidence, not add another demo label

The next falsifiable experiment should freeze one coach-authored retrieval contract, then compare three declared conditions on the same source-held-out clips:

1. **Direct visual reporter:** video-only VLM → structured event/evidence card.
2. **Sport-specific evidence augmentation:** the same reporter plus declared SoccerMaster features for soccer or a football-adapted visual representation for football.
3. **Frozen-probe baseline:** the current MobileNetV2/PCA/head representation used only as a candidate or reranking signal.

Before any final test, use at least ten independent game groups per sport, cap adjacent clips per game, include at least 20% background/unanswerable or semantically close hard negatives, double-annotate answerability plus cue intervals/regions, and seal an untouched game-grouped test manifest. These design principles follow the [school-year research program](dr-tica-lin-and-soccer-vlm-research-2026-08-27.md). Score event/report correctness, temporal/spatial evidence, top-k retrieval, abstention/coverage-risk, and expert verification time separately. Keep commentary/audio out of the visual input; if later added, evaluate visual-only, commentary-only, and late-fusion branches separately so ASR does not become hidden ground truth.

**Advance criterion:** the augmented condition must improve a preregistered evidence-linked metric or verification outcome at a fixed unsupported-event rate, with source-grouped uncertainty and no critical-query regression. Otherwise, keep the added encoder as related work rather than a core dependency.

## Reproduction and verification

Run these commands from `C:\AI\projects\SportsPlayLLMResearch` in PowerShell. Use a new empty output directory for reproduction; do not overwrite the recorded generation.

```powershell
# Recheck rights, hashes, decode, split isolation, class presence, and audio exclusion.
& .\.venv-soccernet\Scripts\python.exe .\data\public\footballmaster\verify_manifest.py

# Acquire/verify the official frozen backbone if it is not already present.
& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py acquire-backbone `
  --expected-sha256 c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5

# Refit the complete pilot into a new directory.
& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py train `
  --out .\artifacts\footballmaster\pilot-v1-reproduction `
  --frames 8 --pca-components 16 --epochs 500 --learning-rate 0.05 --l2 0.1

# Verify immutable bindings and index/package consistency.
& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py verify `
  --model-dir .\artifacts\footballmaster\pilot-v1-reproduction

# Focused model and dual-sport API tests.
& .\.venv-soccernet\Scripts\python.exe -m pytest -q `
  .\tests\test_footballmaster_pilot.py `
  .\tests\test_multisport_search_demo_server.py

# Start the loopback-only dual-sport UI.
& .\.venv-soccernet\Scripts\python.exe .\prototype\multisport_search_demo_server.py `
  --host 127.0.0.1 --port 8771 --open-browser
```

With the server running:

```powershell
Invoke-RestMethod http://127.0.0.1:8771/healthz
Invoke-RestMethod 'http://127.0.0.1:8771/api/status?sport=soccer'
Invoke-RestMethod 'http://127.0.0.1:8771/api/status?sport=football'
```

The recorded run receipt reports no external services, no paid services, no GPU use, source-held-out test status `true`, and binding checks for checkpoint, configuration, model card, metrics, predictions, training log, feature receipts, search index, and index plan. [Run receipt](../artifacts/footballmaster/pilot-v1/run-receipt.json)

## File map

| Purpose | Artifact |
|---|---|
| Rights/source ledger | [`data/public/footballmaster/source-manifest.json`](../data/public/footballmaster/source-manifest.json) |
| Model-ready examples | [`data/public/footballmaster/examples.jsonl`](../data/public/footballmaster/examples.jsonl) |
| Visual audit | [`data/public/footballmaster/contact-sheets/overview.jpg`](../data/public/footballmaster/contact-sheets/overview.jpg) |
| Actual-data split figure | [`presentation/figures/FootballMaster-source-heldout-split-2026-08-27.png`](../presentation/figures/FootballMaster-source-heldout-split-2026-08-27.png) |
| Actual-data result figure | [`presentation/figures/FootballMaster-heldout-performance-2026-08-27.png`](../presentation/figures/FootballMaster-heldout-performance-2026-08-27.png) |
| Data verifier | [`data/public/footballmaster/verify_manifest.py`](../data/public/footballmaster/verify_manifest.py) |
| Training implementation | [`prototype/footballmaster_pilot.py`](../prototype/footballmaster_pilot.py) |
| Trained checkpoint | [`artifacts/footballmaster/pilot-v1/footballmaster-pilot-v1.npz`](../artifacts/footballmaster/pilot-v1/footballmaster-pilot-v1.npz) |
| Metrics/model truth | [`metrics.json`](../artifacts/footballmaster/pilot-v1/metrics.json), [`model-card.json`](../artifacts/footballmaster/pilot-v1/model-card.json), [`run-receipt.json`](../artifacts/footballmaster/pilot-v1/run-receipt.json) |
| Per-clip predictions | [`predictions.jsonl`](../artifacts/footballmaster/pilot-v1/predictions.jsonl) |
| Search database/contract | [`search-index.sqlite3`](../artifacts/footballmaster/pilot-v1/search-index.sqlite3), [`index-plan.json`](../artifacts/footballmaster/pilot-v1/index-plan.json) |
| Dual-sport backend | [`prototype/multisport_search_demo_server.py`](../prototype/multisport_search_demo_server.py) |
| Dual-sport UI | [`prototype/search_demo_ui/`](../prototype/search_demo_ui/) |
| Focused tests | [`tests/test_footballmaster_pilot.py`](../tests/test_footballmaster_pilot.py), [`tests/test_multisport_search_demo_server.py`](../tests/test_multisport_search_demo_server.py) |
| Coach/UMD evidence | [`umd-coach-search-pilot-memo-2026-08-27.md`](umd-coach-search-pilot-memo-2026-08-27.md) |
| Live-demo script | [`footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md`](footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md) |

## Glossary

| Term | Plain technical meaning in this project |
|---|---|
| **LLM** | A language model. Here it translates a coach query into a strict retrieval plan; it does not inspect video. |
| **VLM** | A vision-language model that consumes images/video and language. The soccer reporter is a VLM; FootballMaster-Pilot is **not**. |
| **ASR** | Automatic speech recognition: speech audio → text. ASR is not used in the current visual-only football result. |
| **Backbone** | The inherited feature extractor. MobileNetV2 is frozen here; SoccerMaster is a much larger soccer-specific encoder. |
| **Frozen** | Parameters are used without being updated during this training run. |
| **PCA** | Principal component analysis, a train-fitted linear projection used here to reduce 3,000 pooled features to 3 dimensions. It is unsupervised. |
| **Softmax head** | A small classifier that maps the three PCA values to two class scores. Only its 8 parameters are label-supervised. |
| **Weak label** | A label taken from a source description rather than independent human adjudication. |
| **Source-held-out** | Every clip from one recorded game/session stays in exactly one split. This reduces same-source leakage. |
| **Sealed test** | A test manifest that is frozen before model, prompt, threshold, or feature decisions and opened only for final evaluation. The current split is source-held-out, but the broader research program still needs a genuinely preregistered sealed benchmark. |
| **Post hoc** | Performed after model output. SoccerNet labels appear only in the later audit panel, never as model/query input. |
| **Same-clip comparison** | Two conditions receive the identical video interval so duration/content do not change along with the model. It controls one confound but does not create an independent benchmark. |
| **Balanced accuracy** | Mean recall across classes; useful when class counts differ. |
| **Macro F1** | Mean of per-class F1 scores, giving each class equal weight. |
| **Wilson interval** | A binomial proportion interval with better small-sample behavior than the simple normal approximation. Here its width makes the uncertainty obvious. |
| **Calibration** | Whether a 90% score is correct about 90% of the time. The pilot is not calibrated. |
| **Abstention** | Explicitly declining to answer when evidence is insufficient or risk is too high. |
| **FTS** | SQLite full-text search over saved report text; it retrieves records but does not infer events from pixels. |
| **Claim-origin ledger** | The UI's separation of learned output, weak source metadata, deterministic processing, optional VLM text, and held-out audit evidence. |

## Further questions

1. Which one soccer and one football workflow would UMD staff choose as the first low-risk, high-value retrieval task?
2. What view, roster, scoreboard, playbook, and tracking metadata can be used under university control, and which must remain unavailable to the model?
3. Which observations can two reviewers label reliably from broadcast/sideline video, and which require All-22, end-zone, or calibrated pitch views?
4. Should the next football model target play boundaries, formation/personnel/motion, or detailed report generation first?
5. Can a sport-specific representation improve evidence-linked retrieval over a direct VLM at a fixed unsupported-event rate?
6. Does exposing uncertainty and exact evidence reduce verification time without increasing missed errors?
7. What institutional position applies to ShareAlike training material, embeddings, checkpoints, and derived indexes?
8. What is the correct game-, opponent-, and season-level holdout design for a school-year study?
