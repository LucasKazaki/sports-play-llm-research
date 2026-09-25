# Archit next-meeting technical brief: SoccerMaster, stronger VLM baselines, and coach-search research

> **Soccer-track handoff preserved for provenance.** The current dual-sport presentation, measured FootballMaster-Pilot result, and live-demo instructions are consolidated in [`footballmaster-dual-sport-technical-report-2026-08-27.md`](footballmaster-dual-sport-technical-report-2026-08-27.md) and [`footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md`](footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md). The active UI is at `http://127.0.0.1:8771/`.

**Status:** canonical handoff for humans and Agent Studio  
**Prepared:** 2026-08-27 (America/New_York)  
**Audience:** Lucas, Archit, and any agent continuing the project  
**Primary internal evidence:** private 46:05 call transcript at `data/private/agent-context/archit-call-transcript-2026-08-27.txt`  
**Transcript SHA-256:** `96e50c38beacd2f8abb9f3f4c1667644532352d32255d9cfe50844cd0ce89cec`  
**Canonical Agent Studio project:** `sports-play-llm` (do not restart the retired duplicate `soccer-research`)

## One-minute summary

Archit gave three concrete next-meeting priorities, in this order:

1. **Most important: test a substantially stronger, current Gemini video model on the same kind of clips.** Six clips is the minimum; 10–15 is the desired small study. Freeze the detailed structured event-card prompt, preserve raw responses and failures, and compare against held-out SoccerNet labels. Do not treat commentary as ground truth.
2. **Try the newly shared SoccerMaster foundation model if it is technically feasible.** If local execution is not feasible, report the exact compute, dependency, model-contract, or rights blocker—not a vague failure.
3. **Prepare coach-discovery ideas.** Bring 4–5 useful clip categories and 4–5 retrieval interactions to coaches as hypotheses, then let their workflow decide whether the project should remain soccer-first, pivot to football, split into two projects, or become a multi-sport film-analysis system.

SoccerMaster is highly relevant but is **not** a drop-in conversational VLM. It is a soccer-specific vision encoder plus task heads for spatial perception, 24-way event classification, video–commentary alignment, and several downstream tasks. The most promising integration is to use SoccerMaster features, event scores, pitch registration, and tracks as structured evidence or reranking signals underneath the existing detailed VLM event-card/search layer. Training SoccerMaster from scratch is outside local scope: the paper reports 16 NVIDIA H800 GPUs for about nine days in float32. Released checkpoints make bounded inference/adaptation plausible, but the public implementation has a heavy multi-model dependency tree and the current paper explicitly omits ball detection/tracking.

The current project is a valid **systems demo and failure-analysis platform**, not a validated coach-search model. It can ingest real silent SoccerNet footage locally, ask a VLM for detailed event cards, index them, interpret a natural-language query with an LLM, rank cards deterministically, and seek to cited evidence timestamps. On the saved 30-second real clip, that plumbing works while the semantic report is wrong. The correct presentation boundary remains **SYSTEMS GO / SEMANTIC NO-GO** until stronger-model and broader evaluation evidence says otherwise.

## What Archit actually asked for

The call transcript labels Archit as “Them.” Some calendar phrases are ASR-corrupted, so this brief preserves priority and acceptance criteria without inventing an exact deadline.

### Priority 0 — stronger Gemini baseline

Archit repeatedly asks for the same real clips to be sent through current Gemini, either through an API/free tier or the GUI. At 43:37–43:45 he gives **six as a minimum and 10–15 as ideal**. At 45:02–45:08 he states that Gemini is the most important next item.

The experiment is complete only when it has:

- 6 clips minimum and a target of 10–15 rights-safe clips;
- one frozen event-card prompt and schema across all clips;
- exact model ID/version, input method, media settings, and date;
- clip ID and content hash, source/rights decision, duration, and sampling behavior;
- raw model response, parsed response, validation error, retry history, latency, and terminal failure;
- evaluation against held-out event labels that were never shown to the model;
- commentary/captions opened only after the visual result is sealed and reported as auxiliary evidence;
- a clip-level result table and an honest failure taxonomy;
- no accuracy or calibration claim from a convenience sample.

### Priority 1A — SoccerMaster feasibility and adapter experiment

At 44:04–44:22 Archit asks Lucas to try the recently released soccer foundation model. He explicitly says he has not tested it and does not know how practical it is. The required output is therefore a **feasibility decision with receipts**, not a promise that the entire pipeline will run.

The experiment is complete when:

- the paper, exact repository, checkpoint host, release state, and license evidence are recorded;
- the architecture, input contract, dependencies, compute requirements, and expected outputs are explained;
- the smallest useful checkpoint path is identified;
- a no-download inventory/dry run is performed first;
- if rights and compute gates pass, the same clips are tested without changing the evaluation definition;
- otherwise, the exact blocker and the smallest next executable step are documented;
- no reported paper metric is presented as locally reproduced.

### Priority 1B — coach-discovery packet

At 35:36–36:08 and 45:18–45:33 Archit asks for roughly 4–5 useful clip/retrieval ideas to take to coaches. These are research hypotheses, not claims about coach needs.

The packet should include:

- five candidate clip concepts;
- five interaction modes with sample queries;
- questions about the coach’s current workflow, pain points, evidence needs, and acceptable failure behavior;
- a decision rubric for soccer versus football versus multi-sport scope;
- a clear split between near-term text search and longer-term sketch/3D/spatial interaction.

### Technical corrections the next demo must make

- A **cryptographic hash** proves identity/integrity; it is not a semantic embedding and does not retrieve similar plays.
- **Commentary is not ground truth.** It may lag the visual event, discuss an earlier play, or contain unrelated context. It is auxiliary evidence only.
- The current search UI uses an LLM to convert a coach’s question into a strict search plan, then deterministic code ranks saved event-card text. Unless an embedding index is actually added and measured, do not call this “embedding retrieval.”
- SoccerNet event labels remain isolated from VLM prompts and are opened only for post-hoc evaluation.
- Current confidence values are model self-reports, not calibrated probabilities.

## Current project state and truth boundary

### What works today

1. Offline ingestion accepts real local video, plans overlapping windows, extracts physically silent frames, and binds every artifact to hashes.
2. The local VLM emits zero or more structured event cards containing descriptions, participants, coaching relevance, evidence timestamps, and uncertainty.
3. Strict validation rejects malformed or unsupported records before indexing.
4. A private SQLite full-text index stores VLM-produced cards.
5. A local query LLM turns natural language into a visible, validated query plan.
6. Deterministic ranking returns saved cards and the UI seeks the real clip to cited timestamps.
7. Held-out labels are loaded separately for a post-hoc audit panel.
8. The one-command UI is available through `START_COACH_SEARCH_UI.cmd` at `http://127.0.0.1:8770/`.

### What has been falsified or remains unproven

- On one real 30-second SoccerNet window, the full ingestion/search path completed, but the VLM’s descriptions contradicted held-out penalty/goal evidence.
- Matched 20-, 30-, and 60-second direct reports, and denser 10-second reports over the same minute, had 0/4 strict timestamp-aligned event recovery.
- The six-window real-footage comparison is a selected, one-match, post-hoc engineering study—not a benchmark.
- Qwen and Gemma used different image packaging, so their outcomes do not support a causal model ranking.
- No temporal/spatial grounding, coach utility, population accuracy, or calibration estimate has been established.
- No weights have been fine-tuned in this project.

### Current presentation-safe claim

> We have a reproducible, private, human-auditable pipeline for turning broadcast video into searchable VLM event records and returning evidence-linked clips. On the current local models, the plumbing works but the soccer semantics do not. The next research question is whether a stronger general video model, soccer-specific visual features, and explicit broadcast/pitch/player evidence reduce these errors under a frozen evaluation contract.

## SoccerMaster paper research

### Identity and release state

- **Paper:** *SoccerMaster: A Vision Foundation Model for Soccer Understanding*
- **Authors:** Haolin Yang, Jiayuan Rao, Haoning Wu, Weidi Xie
- **Venue:** CVPR 2026 Oral
- **arXiv:** 2512.11016, version 2 dated 2026-05-07
- **Project page:** <https://haolinyang-hlyang.github.io/SoccerMaster/>
- **Paper HTML:** <https://arxiv.org/html/2512.11016>
- **Official code:** <https://github.com/haolinyang-hlyang/SoccerMaster>
- **Released checkpoints:** <https://huggingface.co/xleprime/SoccerMaster>

The authors describe SoccerMaster as a unified soccer-specific **vision foundation model** trained by supervised multi-task pretraining. The aim is to place dense spatial perception and high-level soccer semantics in one visual representation rather than run unrelated expert models for every task.

### Architecture

- Hierarchical ViT initialized from `google/siglip2-large-patch16-512`.
- 16 spatial transformer blocks followed by 8 spatiotemporal blocks.
- Hidden dimension 1024.
- Uniformly sampled clips of 30 frames.
- Frames are processed at 512×512 with 16×16 patches.
- The backbone yields spatial features and semantic features.
- Task heads cover athlete detection/identification, pitch keypoints/lines, 24-class event classification, and video–commentary alignment.
- Downstream adapters cover commentary generation, camera calibration, and multi-object tracking.

This matters because the model is **an encoder plus task heads**, not an instruction-following language model that natively produces our rich JSON report. Its event head produces one of 24 SoccerReplay-1988 categories. Its alignment head maps video and commentary into a shared space. Rich coach reports still require a language layer, retrieval schema, or newly trained adapter.

There is also a release-level ontology mismatch to resolve before scoring: the paper repeatedly says 24 event classes, while the current public loader enumerates 23 literals. Those literals include offside and two foul types, but do not include long ball and do not include a null/background class. The semantic training/evaluation clips are centered on event or commentary timestamps; the paper does not report randomly sampled no-event windows. Consequently, 77.2% closed-set accuracy is not evidence of acceptable false positives per hour on a whole match.

### SoccerFactory data

The paper’s combined pretraining resource contains about **7.45 million frames across 248,300 segments**:

- 2.75M spatial-perception frames;
- 4.71M semantic-reasoning frames, sampled at 1 FPS;
- SoccerNet-GSR manual spatial data;
- 2.7M automatically curated SoccerFactory spatial frames;
- SoccerNet-v2 event-classification data;
- MatchTime and SoccerReplay-1988 event/alignment data.

Spatial samples use 30 consecutive 25-FPS frames (about 1.2 seconds); semantic samples use 30-second windows sampled at 1 FPS. SoccerMaster therefore receives 30 frames, not an entire game. Because its pretraining includes SoccerNet-v2, MatchTime, and SoccerReplay-1988, any local checkpoint evaluation must audit match IDs against the authors’ training splits. Otherwise, it cannot be called a clean held-out test. Video-only inference also does not mean the encoder has never learned from commentary: commentary alignment is one of its pretraining objectives.

The curation pipeline performs field registration, player/referee/goalkeeper detection, StrongSORT/ReID tracking, Qwen2.5-VL role and jersey recognition, SAM2 refinement, team assignment, and pitch-coordinate projection. It deliberately excludes replays, close-ups, alternative angles, and incompletely visible field views from its main-camera spatial training subset. That exclusion is directly relevant to this project’s replay/live-confusion failures.

The repository separately advertises a Soccer Factory release of 7,000 H.264 videos plus annotations: 2.4 GB of annotations and seven video archives totaling about 126.2 GB. **Do not download it automatically.** Dataset/video rights must be reviewed separately from model-code licensing.

### Training scale

The paper reports:

- 20 training epochs using AdamW;
- global batch size 16 for spatial tasks and 32 for semantic tasks;
- 16 NVIDIA H800 GPUs;
- about nine days of full-precision training.

Therefore:

- reproducing pretraining locally is a hard **no-go**;
- full pipeline reproduction is likely a multi-GPU engineering project;
- checkpoint inference or frozen-feature extraction is the appropriate first feasibility target;
- any claim that this project “trained SoccerMaster” would be false.

### Author-reported results — not locally reproduced

The paper reports the following results under its own evaluation protocols:

| Task | SoccerMaster | Comparator cited in paper | Important qualifier |
|---|---:|---:|---|
| 24-way event classification accuracy | 77.2% | MatchVision 65.3% | Direct paper evaluation; not our detailed-report task |
| Video–commentary retrieval top-1 | 39.0% | MatchVision 4.0%; SigLIP2 3.4% | Top-1 within batches of 48, not corpus-scale coach retrieval |
| Athlete detection AP@50 / mAP | 91.5 / 49.5 | Task-dependent baselines | Paper dataset/protocol |
| MOT HOTA / MOTA / IDF1 | 59.1 / 81.6 / 74.6 | Tracking baselines | Downstream adapter and SoccerNet tracking protocol |
| Commentary BLEU@1 / BLEU@4 / CIDEr | 31.3 / 8.9 / 38.6 | MatchVision 30.9 / 8.7 / 35.7 | Text similarity is not factual event-card grounding |

These figures justify a feasibility experiment; they do not predict our detailed event-report quality and must never be merged with local results.

The comparisons also need careful wording. SoccerMaster is evaluated with its natively pretrained heads, while several baseline encoders are frozen and given common trained heads; this is a representation probe, not symmetric end-to-end fine-tuning. On MOT, SoccerMaster is strongest on some metrics but YOLOv8+PRTReID has higher HOTA and association accuracy. On commentary, SoccerMaster improves BLEU/CIDEr but trails MatchVision on METEOR and ROUGE-L. No human factuality or timestamp-support study is reported.

### Released checkpoint footprint

Public Hugging Face metadata inspected on 2026-08-27 reports these linked file sizes:

| File | Linked size | Likely use | Caveat |
|---|---:|---|---|
| `backbone.pt` | 1,435.25 MB | Soccer-specific visual encoder | Largest required core file |
| `yolo_v8x6_finetuned.pt` | 195.21 MB | Athlete detection for pipeline | Separate expert/pipeline dependency |
| `CaptionClassification.pt` | 100.89 MB | Semantic/event head | Inspect code contract before use |
| `KeypointsDetection.pt` | 33.54 MB | Pitch keypoint head | Spatial evidence candidate |
| `LinesDetection.pt` | 33.38 MB | Pitch line head | Spatial evidence candidate |
| `SoccerNetGSR_Detection.pt` | 6.05 MB | GSR detection head | Requires matching backbone/runtime |
| `VideoCaption.pt` | 0.0015 MB | Listed caption artifact | Suspiciously tiny; treat as placeholder until inspected |

The listed files total about 1.80 GB, excluding SigLIP2 and the many models required by the full tracking/recognition pipeline. The Hugging Face model card declares Apache-2.0 and identifies SigLIP2-L/16-512 as the base model. The GitHub repository root did not expose a `LICENSE` file during this audit, so **code license remains unclear** unless the authors add one. Model license, repository license, and source-video rights are separate questions.

Reproducibility is not turnkey. The released `inference_demo.py` constructs random dummy tensors and prints shapes rather than running a real video. The public model tree exposes the pretraining heads, but the downstream Q-Former/Llama commentary generator and MOTIP-style tracker described in the paper are not currently a complete one-command release. The README installs Transformers from unpinned GitHub main, marks pretraining-code refinement incomplete, and exposes no locked environment or core CI suite. The paper computes retrieval top-1 within candidate batches of 48, while the public test config/launcher does not reproduce that candidate pool without modification.

### Paper limitations that matter here

The authors explicitly report:

- jersey-number errors caused by occlusion, resolution, class imbalance, and the single-pass formulation;
- goalkeeper/player confusion;
- no ball detection or ball tracking in the current spatial-perception scope;
- future interest in audio commentary and player statistics.

For coach search, the absence of ball tracking is substantial. Queries such as “player X receives between the lines and plays a long ball” require the relationship among player identity, ball possession/trajectory, pitch location, and temporal event structure. SoccerMaster supplies several pieces, but not the complete answer.

## How SoccerMaster should fit this project

### Recommended hybrid architecture

```text
private broadcast video
        |
        +--> broadcast-state gate (live / replay / close-up / graphic)
        |
        +--> SoccerMaster backbone
        |      +--> event logits / semantic embedding
        |      +--> pitch lines + camera calibration
        |      +--> player boxes, roles, tracks, pitch coordinates
        |
        +--> detailed general VLM report over rights-safe visual input
        |
        +--> evidence fusion + strict schema validation
        |
        +--> event memory:
               text card + vector(s) + players + pitch + timestamps + provenance
        |
coach query --> query interpretation --> hybrid retrieval/reranking --> evidence clip
```

The next useful experiment is not to replace the detailed reporter with a 24-way label. It is to compare:

1. **Direct strong VLM** — video to detailed event card.
2. **Direct strong VLM + declared SoccerMaster evidence** — the same reporter receives only explicitly generated event/spatial evidence.
3. **SoccerMaster retrieval/reranking** — frozen soccer semantic embedding or event logits rerank candidate cards.
4. **Oracle broadcast-state gate** — human live/replay segmentation estimates whether broadcast grammar is the primary bottleneck before building a VLM gate.

### Smallest viable SoccerMaster experiment

Proceed in stages and stop when a gate fails:

1. Record machine GPU/VRAM, CUDA, Python, PyTorch, disk, and RAM.
2. Inspect repository imports/configs and checkpoint metadata without downloading large files.
3. Confirm a clear license path for the exact code and checkpoint files.
4. Audit local match IDs against the SoccerMaster/SoccerNet pretraining splits and label overlap status explicitly.
5. Build a 30-frame, 512×512 adapter from the existing real silent clips into the documented input tensor/sequence format.
6. If the machine can hold the ~1.44 GB backbone plus runtime memory, download only the backbone and smallest needed head from the official host; verify hashes.
7. Run one development clip and preserve raw tensors/logits/embedding dimensions, not just a label.
8. Run the frozen 6-clip comparison set only after one-clip verification.
9. Keep held-out SoccerNet labels outside the input path.
10. If execution is infeasible, produce a reproducible blocker receipt and do not install the full GSR/Qwen/SAM2 pipeline.

### Go/no-go rule

SoccerMaster advances from feasibility to a core dependency only if it adds a measurable capability under the same split and prompt contract, such as:

- higher event recall at fixed unsupported-event rate;
- lower replay-as-live error;
- better text retrieval of relevant clips at fixed candidate count;
- better temporal or pitch evidence precision;
- useful player/pitch features that the general VLM cannot provide;
- acceptable latency and memory on available hardware.

If it only emits a coarse event label with no measurable lift, keep it as a related-work baseline rather than adding infrastructure complexity.

## Current Gemini experiment protocol

### Model choice and video behavior

As of 2026-08-27, Google’s official model page lists `gemini-3.7-flash` as its most capable Flash model and its pricing page lists a free tier. The exact available endpoint can change, so the runner must enumerate/validate the model at execution time and record the returned model version. Google’s official video documentation says video is normally sampled at **1 FPS**, timestamps are inserted every second, and the API can analyze audio and visual streams together.

That default creates a real methodological risk for soccer: a pass, deflection, contact, or offside position can occur between sampled frames. The experiment should preserve the default condition for an honest product baseline, then optionally add a denser frame-sheet condition as a separate representation—not silently change inputs mid-comparison.

### Rights and privacy gate

No `GEMINI_API_KEY` or `GOOGLE_API_KEY` is currently present in the runtime environment. More importantly, Google’s free-tier pricing page states that submitted content may be used to improve its products. The private SoccerNet footage was obtained under non-redistribution/NDA terms and must remain local unless a rights holder explicitly confirms third-party model processing.

Therefore:

- **Do not upload private SoccerNet footage to Gemini.**
- Build the provider runner, frozen prompt, manifests, parser, evaluator, and resume logic locally.
- Run Gemini only on a 10–15-clip set whose license/terms explicitly permit the intended third-party processing, or after written rights clearance.
- Record whether audio was included. For the primary visual condition, use physically silent media.
- If no suitable rights-safe set or credential exists, report those exact gates; do not fake a Gemini result and do not substitute local model outputs.

### Frozen event-card contract

Each clip may produce zero or more event cards. Required fields should include:

- `event_type` and `event_subtype`;
- `start_s`, `peak_s`, `end_s` relative to the clip;
- `phase_of_play` and `restart_context`;
- `team_side` only when visually supported;
- player references using visible identity evidence, otherwise anonymous role/jersey descriptions;
- ball action and inferred possession with separate confidence/visibility flags;
- origin/destination pitch regions and movement direction;
- ordered action sequence in plain language;
- tactical intent and coach relevance;
- visible evidence timestamps;
- explicit alternatives/uncertainties;
- `abstain` and `abstention_reason`.

The model must be told not to infer names from teams or commentary, not to promote replay footage to live match time, and not to output an event merely because a broadcast graphic or celebration is visible.

### Evaluation matrix

| Dimension | Metric or audit | Why it matters |
|---|---|---|
| Event semantics | label recall/precision at agreed mapping | Basic play understanding |
| Temporal evidence | timestamp tolerance and interval IoU | Search must land on the right moment |
| Unsupported detail | unsupported-claim rate | Rich reports can hallucinate more facts |
| Replay confusion | replay-as-live false-positive rate | Known broadcast failure |
| Abstention | coverage versus error/selective risk | Safe behavior under ambiguity |
| Schema | valid cards / attempted requests | Operational reliability |
| Retrieval | Recall@K, nDCG, hard-negative rank | Whole-match search objective |
| Identity | visible jersey/player evidence precision | Coach-specific search |
| Pitch/ball | evidence precision and missingness | Tactical usefulness |
| Systems | latency, bytes, token use, failures | Practical feasibility |

The small 10–15-clip phase is for failure discovery and protocol debugging. It is not large enough for a stable population accuracy estimate.

## Coach-discovery hypotheses

### Five candidate clip categories

1. **Possession progression and long balls** — who received, body orientation, pressure, origin/destination region, target, and outcome.
2. **Chance creation and box entries** — overload, cutback/cross/through ball, runner pattern, defender reaction, shot or breakdown.
3. **Defensive shape and transition** — press trigger, line break, recovery run, numerical advantage such as 2v1 or 3v2, and whether the team delayed/stopped the attack.
4. **Restarts and officiating events** — corners, free kicks, throw-ins, offside decisions, fouls/cards, setup, delivery, and second-ball outcome.
5. **Player-specific teaching moments** — first touch, scanning, positioning, decision, movement after passing, duel behavior, and repeated tendencies across clips.

### Five retrieval interactions

1. **Natural-language search:** “Show every time our left back received under pressure and played forward within three seconds.”
2. **Player/ball filter plus text:** choose a player or jersey candidate, then ask “long passes into the right half-space that reached a teammate.”
3. **Example-clip retrieval:** mark one clip and find tactically similar structures, with explicit reasons for similarity.
4. **Sketch/touch query:** draw a starting zone, arrow, and destination or outline a 2v1; retrieve matching pitch-coordinate trajectories.
5. **Audio or dictated query:** speak a coaching question, convert it to the same transparent query plan, and allow refinement by constraints rather than a single opaque answer.

### Questions for coaches

- What do you search for today, and what takes the longest?
- Is the unit of value a single event, a possession, a tactical pattern, or every action by a player?
- Which five play types would you want available tomorrow?
- Do you start from language, player/ball filters, a known example clip, a pitch sketch, or a timeline?
- What evidence must be shown before you trust a result?
- How wrong can retrieval be before it wastes more time than manual film review?
- Should near-misses and counterexamples be returned alongside matches?
- Do you need player names, jersey numbers, roles, or only positions?
- How should replays and commentator descriptions be displayed?
- Which output becomes actionable: a playlist, tagged clips, a report, a practice plan, or an export to existing film software?

### Post-interview scope decision

Score soccer, American football, two parallel systems, and a unified multi-sport system against:

- coach access and data access;
- clarity of high-value retrieval tasks;
- availability of reliable labels and rights-safe footage;
- need for ball/player tracking and field registration;
- model availability and compute;
- evaluation feasibility;
- integration cost with existing coaching tools.

Do not decide the sport scope solely from technical novelty before coach evidence.

## Prioritized work packages for Agent Studio

### WP0 — preserve context and truth boundaries

**Inputs:** this brief, private transcript, `README.md`, `research/final-verification-2026-08-27.md`, `research/long-clip-detailed-vlm-probe-2026-08-27.md`.  
**Output:** updated action plan, decision log, evidence ledger, run log, and loop state pointing back to this brief.  
**Acceptance:** no claim drift; no restricted media path or credential appears in public artifacts.

### WP1 — Gemini-ready benchmark harness

**Output:** provider-neutral runner plus a Gemini adapter, frozen schema/prompt, rights manifest, raw-output store, parser, resume logic, scoring script, and tests.  
**Acceptance:** dry-run and mock fixtures pass; remote execution refuses non-approved media; credentials are read only at runtime and never printed; 6 minimum/10–15 target protocol documented.  
**External gate:** actual Gemini inference requires a credential and clips approved for third-party processing. Zero spend only.

### WP2 — SoccerMaster feasibility packet

**Output:** official-source inventory, license matrix, checkpoint metadata, machine-resource audit, input adapter, and minimal dry-run/import test.  
**Acceptance:** exact blocker or verified one-clip output; no full dataset/full pipeline acquisition; no claim of reproduced paper results.

### WP3 — coach-discovery packet

**Output:** five clip concepts, five retrieval modes, sample queries, interview questions, and scope scorecard.  
**Acceptance:** every item labeled as a hypothesis awaiting coach validation.

### WP4 — broadcast-state gate experiment

**Output:** compare direct reporting with a human/oracle live-vs-replay gate on the known failure window before training a camera-state VLM.  
**Acceptance:** fixed reporter/model; macro F1 for gate labels, replay-as-live rate, event recovery, unsupported-event rate, abstention/coverage, latency; held-out labels isolated.  
**Decision:** implement a learned gate only if the oracle gate materially improves temporal correctness.

### WP5 — hybrid retrieval research

**Output:** an adapter interface for text-card scores, actual semantic vectors, SoccerMaster features/event logits, player/pitch state, and hard-negative evaluation.  
**Acceptance:** the UI labels deterministic token ranking versus embedding retrieval accurately; measurable Recall@K/nDCG on a match-disjoint, adjudicated set.

## Agent startup checklist

1. Read this file completely.
2. Read the private transcript completely; verify its SHA-256 against the header.
3. Read `AGENTS.md`, `README.md`, `research/final-verification-2026-08-27.md`, `research/long-clip-detailed-vlm-probe-2026-08-27.md`, and `research/rights-and-source-decision-packet.md`.
4. Treat `sports-play-llm` as the only Agent Studio project.
5. Preserve **SYSTEMS GO / SEMANTIC NO-GO**.
6. Never put SoccerNet labels, commentary, captions, or post-hoc audits into a visual-model prompt.
7. Never upload private SoccerNet video or accept a dataset/license automatically.
8. Never download the ~126 GB Soccer Factory video release as a feasibility shortcut.
9. Check credentials only by presence; never expose values.
10. Prefer bounded stages with persistent manifests, hashes, raw outputs, and resume behavior.
11. Run relevant focused tests, then the full suite, and request independent read-only verification for substantial changes.
12. Update the canonical research/state files and leave a clear next action or exact human-only gate.

### Useful entry points

- Search backend: `prototype/searchable_match_vlm.py`
- Search UI/server: `prototype/search_demo_server.py`
- One-click UI: `START_COACH_SEARCH_UI.cmd`
- Local search demo: `scripts/demo-searchable-coaching.ps1`
- Search tests: `tests/test_searchable_match_vlm.py`, `tests/test_search_demo_server.py`
- Real-footage protocol: `research/soccernet-real-footage-pilot-2026-08-27.md`
- Long-window failures: `research/long-clip-detailed-vlm-probe-2026-08-27.md`
- Method audit: `research/phd-methodology-audit-2026-08-27.md`
- Rights decisions: `research/rights-and-source-decision-packet.md`
- Presentation/talk track: `presentation/PlayGround-Searchable-Full-Match-VLM-Archit-2026-08-27.pptx`, `research/archit-demo-talk-track.md`

## Decisions already made

- Use real soccer broadcasts, not artificial soccer clips, for semantic claims.
- Keep restricted SoccerNet media local and non-redistributed.
- Use VLMs for soccer semantics; deterministic code may window, hash, validate, store, rank, and seek but must not secretly classify plays.
- Keep inference evidence separate from post-hoc labels and commentary.
- Treat current local-model results as failure analysis.
- Use the canonical `sports-play-llm` Agent Studio loop for the new work.
- Favor a hybrid future system: detailed language cards plus true visual/spatial/player/ball representations, provided each component earns its complexity experimentally.

## Open research questions

1. Does a current strong Gemini model materially reduce unsupported soccer claims on the frozen protocol?
2. Does its default 1 FPS video sampling miss decisive fast actions, and does a denser representation help?
3. Can SoccerMaster’s semantic features improve text-to-clip retrieval beyond event-card text?
4. Can SoccerMaster pitch/player features ground who/where without making identity claims from unreadable jerseys?
5. Is replay/live separation the largest temporal error source, or is the detailed reporter itself the bottleneck?
6. How should overlapping event cards be deduplicated into a single match timeline?
7. What is the shortest/longest useful window for each event family?
8. Which ball/possession tracker can fill SoccerMaster’s explicit ball-tracking gap?
9. What clip categories and interaction modes do coaches actually value?
10. What is the right evaluation unit: clip, event, possession, player action, tactical pattern, or coach task completion?

## Source ledger

### Primary public sources

- SoccerMaster official project page: <https://haolinyang-hlyang.github.io/SoccerMaster/>
- SoccerMaster arXiv record: <https://arxiv.org/abs/2512.11016>
- SoccerMaster full paper HTML: <https://arxiv.org/html/2512.11016>
- SoccerMaster official repository: <https://github.com/haolinyang-hlyang/SoccerMaster>
- Audited repository commit: <https://github.com/haolinyang-hlyang/SoccerMaster/commit/2e5619712d93f634b841aaf37231cd9fceb6b262>
- SoccerMaster checkpoint repository: <https://huggingface.co/xleprime/SoccerMaster>
- Google Gemini model catalog: <https://ai.google.dev/gemini-api/docs/models>
- Google Gemini video-understanding guide: <https://ai.google.dev/gemini-api/docs/video-understanding>
- Google Gemini API pricing/data-use disclosure: <https://ai.google.dev/gemini-api/docs/pricing>

### Internal evidence

- `data/private/agent-context/archit-call-transcript-2026-08-27.txt` — private full call transcript; do not publish.
- `research/final-verification-2026-08-27.md` — presentation/demo verification and exact local metrics.
- `research/long-clip-detailed-vlm-probe-2026-08-27.md` — detailed-report duration experiment and failure analysis.
- `research/soccernet-real-footage-pilot-2026-08-27.md` — canonical real-footage pilot.
- `research/phd-methodology-audit-2026-08-27.md` — methodological risks and claim bounds.

## Definition of “ready for the next meeting”

The project is ready when Lucas can show:

1. the existing live search UI, explicitly labeled systems-go/semantic-no-go;
2. a clean result table from a rights-safe stronger-Gemini run, or a runnable harness plus exact credential/rights blocker;
3. a SoccerMaster feasibility result or exact bounded blocker, with no training claim;
4. a diagram of the recommended hybrid architecture;
5. five coach clip hypotheses, five retrieval interactions, and interview questions;
6. a short prioritized research plan with experiments that can falsify the main ideas;
7. raw receipts and tests sufficient for Archit to inspect the backend rather than accept a polished demo on trust.
