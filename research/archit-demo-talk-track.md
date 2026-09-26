# Archit presentation and live-demo talk track

> **Historical soccer-only script.** For the current switchable Soccer/FootballMaster demo at `http://127.0.0.1:8771/`, use [`footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md`](footballmaster-dual-sport-demo-and-pitch-guide-2026-08-27.md). The material below is retained only as the earlier soccer presentation record.

**Target:** 14–16 minutes of slides, 3 minutes of live demos, then technical discussion  
**Audience:** PhD computer-science researcher  
**Primary demo URL:** `http://127.0.0.1:8770/`  
**One-click launcher:** `START_COACH_SEARCH_UI.cmd`  
**Rule:** the video VLM report is saved and hash-bound; the query LLM runs live. Never imply that the retrieved report is factually correct.

On this workstation, double-click `START_PRESENTATION.cmd` to use the verified no-install browser slideshow. Space or the arrow keys advance, `Home` returns to slide 1, and `F` enters full screen. The `.pptx` remains the canonical editable deck.

## The 20-second opening

Say this almost verbatim:

> I replaced the artificial soccer fixtures with real, authorized SoccerNet broadcasts linked to SoccerDB and upgraded the output from one label to a detailed, searchable event report. The local VLM now runs on 20-, 30-, and 60-second silent clips and a resumable backend can plan an entire half as overlapping windows, store evidence-linked event cards, and search them. The important result is a failure boundary: every selected long-window report was valid JSON, but none recovered the held-out reference events at the correct time. This is a pipeline and research demo—not an autonomous coaching system.

If there is time for only one methodological sentence, add:

> A fluent report and a working search index do not prove the report is true. The next study must score event discovery, timestamps, actor identity, evidence, and retrieval separately on untouched match groups.

## Four terms to know before speaking

- **ASR:** automatic speech recognition—software turning commentator audio into text. It is related evidence, not ground truth.
- **Seal:** save the visual result and its hash fingerprint before opening commentary, so later evidence cannot silently rewrite it.
- **Post hoc:** a choice made after earlier results were visible. It can debug a system but is not a fresh unbiased test.
- **Same-clip comparison:** both systems saw frames from the same six clip windows. This controls the footage, but it is not a clean model-only comparison because image grouping and other details changed.

## Slide-by-slide script

### Slide 1 — Frame the question and result

> The question is whether a local VLM can classify a real soccer event window from silent visual evidence. The strongest observed case-level result is three allowed-window matches out of six for Qwen, but the denominator is six selected windows from one match. I will show the real inputs, the exact backend, the failures, and the next falsifiable experiment.

Do not say “50% accuracy on soccer.” Say “3/6 allowed-window matches in this selected one-match case series.”

### Slide 2 — Explain what changed

> The old synthetic clips remain only as deterministic software fixtures. Every empirical result in this talk comes from authorized broadcast video. The current path adds byte-level provenance, physically silent VLM inputs, two local VLM runs, and a commentary probe that is opened only after vision is sealed.

### Slide 3 — Define the estimand precisely

> This is not SoccerNet action spotting. SoccerNet spotting takes an untrimmed match and retrieves event timestamps. Here, an official point label selects a ten-second window first; the model then returns one normalized label or abstains. The descriptive estimand is requested-set allowed-window accuracy: a prediction counts if it equals any mapped point label inside that window. The model also emits an interval and coarse regions, but we did not obtain human temporal or spatial evidence annotations, so grounding quality is unscored.

Call out three exclusions:

- no background or hard-negative windows;
- no full-match search or proposal generation;
- no population-level accuracy estimate from six clustered cases.

### Slide 4 — Establish data identity and split limits

> The bytes and point labels are SoccerNet. I call the clips SoccerDB-mapped because SoccerDB publishes a mapping from its video names to SoccerNet match names, and this project pins and hashes the exact mapping rows. Development is five windows from Barcelona–Roma; the six-window comparison set is Barcelona–BATE. The match IDs are disjoint, but both are Barcelona first halves from the same Champions League season, so team, competition, season, and broadcast domain are not held out.

> The footage remains local and non-redistributable. Public availability is not a license, which is why I did not scrape famous-match broadcasts from YouTube.

### Slide 5 — Walk through the backend

Use this exact sequence:

1. A SoccerNet-v2 point timestamp selects an approximately ten-second window.
2. The clip builder writes two different media files: a VLM MP4 with zero audio streams and a local-review MP4 that retains commentary.
3. The visual runner chooses 12 uniform timestamps, decodes the corresponding frames, records indices and timestamps, and hashes the decoded pixels.
4. The frames are packaged into chronological image sheets and sent to a loopback-only local VLM with a frozen prompt and strict JSON schema.
5. The response, prompt, input hashes, model identity, timing, and runtime receipt are persisted before the mapped annotations are joined.
6. Deterministic fail-closed scoring keeps every requested clip in the denominator. Timeouts, malformed JSON, stale cache entries, and hash mismatches are failures—not silently dropped cases.
7. Only after the visual summary is hash-sealed may the text path open aligned SoccerNet-Echoes ASR. That output is compared with the already-saved visual label but cannot alter it.

Then say:

> No hand-engineered soccer algorithm determines the class. There is no ball-color rule, optical-flow decision tree, tracker event rule, or conventional classifier. Deterministic code handles media isolation, sampling, provenance, validation, and scoring; the VLM produces the semantic label.

### Slide 6 — Explain the model and representation confound

> Gemma receives twelve one-frame 1280-by-720 sheets. Qwen's first twelve-image request used 11,629 prompt tokens against an 8,192-token context and failed before inference, so the successful configuration packs the exact same twelve decoded frames into six two-frame 1280-by-360 sheets. Every sampled timestamp, frame index, ordinal, and decoded-frame hash matches across runs. Image grouping and geometry do not. Model and representation therefore change together.

> No weights were updated. The five-clip “train” directory is really development data used for prompt, schema, model, and runtime engineering. A proper fine-tuning claim would require an optimization procedure, checkpoint provenance, and a new untouched evaluation set.

### Slide 7 — Preserve the untouched Gemma result

> The only untouched first pass is Gemma primary v1: three of six requests completed, requested-set schema validity was three of six, allowed-window accuracy was one of six, and both single-label windows failed, so exact single-label accuracy was zero of two. Median latency among completed requests was 110.624 seconds. The three timeouts remain wrong in requested-set metrics.

> That result mixes model semantics with serving failure, but it is the honest end-to-end first pass. I preserve it instead of replacing it with a cleaner rerun.

### Slide 8 — Separate failure recovery from model performance

> I diagnosed the timeout path with a dedicated, hash-pinned `llama.cpp` server. The timeout pattern no longer reproduced: five of five development requests and six of six post-hoc comparison requests completed, and Gemma's comparison-set median fell to 9.306 seconds. Several runtime factors changed together, and the six clips had already been observed, so this supports a serving-recovery diagnosis—not a causal claim that isolation alone fixed the system and not a new performance estimate. Semantically, Gemma recovery matched zero of six allowed windows.

### Slide 9 — Present Qwen as a post-hoc engineering comparison

> Qwen completed six of six, matched an allowed mapped label in three of six, was exact on one of the two single-label windows, and had 9.9925-second median latency. Gemma recovery completed six of six but matched zero. Qwen was selected after the Gemma evidence and used different image grouping. I therefore do not rank the models or attach uncertainty intervals; I treat the difference as a reason to run a preregistered model-by-representation experiment on new match groups.

### Slide 10 — Use the per-clip table, not just the headline

Read the pattern rather than every row:

> The three Qwen matches are corner kick, goal, and yellow card. The errors are goal for a shot-off-target window, shot on target for a foul window, and penalty kick for a direct-free-kick window. All six outputs carry generated self-scores of 0.90 or 0.95, including all three errors, and Qwen never abstains. These are high-self-score errors. Six examples with no selective-coverage sweep do not support an expected-calibration-error or reliability claim.

Point out that the main metric is generous because any mapped point label within the ten seconds can count.

### Slide 11 — Describe commentary without calling it validation

> Audio never reaches the visual model. After the Qwen visual summary is sealed, Gemma sees only clip-relative SoccerNet-Echoes ASR segments and predicts a label under the same taxonomy. Deterministic code then asks whether the two saved labels are equal. The Qwen probe produced two supports and four contradictions.

> The seal makes commentary non-intervening, not independent. It describes the same event, shares the taxonomy, uses noisy automatic transcription, and can lag, anticipate, describe a replay, or hallucinate. “Supports” means label equality only; it is not a truth label.

### Slide 12 — Set up the qualitative case

> Clip five is the cleanest demonstration case. Qwen predicts `yellow_card`; the separately run ASR classifier also predicts `yellow_card`; and the mapped center point is `yellow_card`. That is useful convergence, but the displayed box and interval were generated by the model and were not adjudicated by a human. I will not call this validated grounding.

### Slide 13 — Connect the project to Dr. Lin's research

> You specifically pointed me toward Dr. Tica Lin's work. The closest bridge is Sportify, but its result is not comparable to mine: Sportify detects actions and tactics from structured basketball data and gives that context to a text-only LLM for narratives and embedded visualizations. VIRD likewise derives poses and trajectories before experts drill from a match view to rallies, shots, and source video. My current run evaluates the upstream perception layer directly from genuine silent broadcast frames.

Then use the newest soccer result:

> *Who's That Player?* identifies referential, spatial, temporal, and metric ambiguity and externalizes the system's chosen interpretation. Inspectability improved, but users repaired only 38% of deliberately misaligned externalization trials. The lesson for PlayGround is two-part: expose the selected time window, evidence, and uncertainty, and also make correction cheap. Transparency alone is not a safety mechanism.

State the boundary explicitly:

> These are system, workflow, and interaction precedents—not visual-only VLM accuracy baselines. The architectural lesson is to separate perception, explanation, and presentation so each can be evaluated.

### Slide 14 — Position against the broader technical literature

Use four contrasts:

- SoccerNet action spotting is untrimmed temporal retrieval, so its mAP is not comparable to this selected-window accuracy.
- SoccerLens separates semantic classification from cue grounding and reports that grounding remains difficult; this pilot has not scored grounding at all.
- The CVPRW domain-adaptation study trains on roughly 20,000 soccer clips; this project is prompt-only inference with no weight updates.
- SoccerAgent/SoccerBench already covers broad multimodal soccer QA and tool routing; the open experiment is direct VLM versus declared soccer-state tools under the same clips and answer/evidence contract.

Then say:

> The interesting research direction is not merely whether a VLM can name a soccer action. It is whether answer, temporal evidence, spatial evidence, calibration, and abstention remain faithful under a controlled, rights-safe protocol.

### Slide 15 — Move from one label to a match memory

> The pilot classified one selected ten-second window. The target is to process a silent match once, save an evidence-linked card for every supported event, and let a coach search by player, action, location, outcome, or time. The VLM still supplies the soccer meaning; ordinary code only segments, validates, stores, and retrieves its reports.

### Slide 16 — Explain the detailed event contract

> Each event card records when, who, what, where, outcome, rule context, evidence, and uncertainty. “As detailed as possible” must mean maximally detailed subject to visible evidence. A hidden jersey number becomes unknown or an anonymous track—not a guessed player name. A visible referee decision can justify `called_offside`; geometrically verifying offside is a separate, much stronger claim.

### Slide 17 — Explain the whole-match architecture

> A full match should not go into one giant prompt. The target architecture would scan overlapping 30-to-60-second windows, zoom into candidates with denser 10-to-30-second windows, ask the VLM for zero or multiple event cards, merge duplicates, and index the saved reports. Commentary would stay in a sealed branch. What is implemented today is the resumable overlapping-window planner, detailed event-card contract, and private SQLite search index; dense refinement and duplicate merging are next. The full-half plan covers 2,700 seconds with 108 gap-free windows.

### Slide 18 — Present the negative long-window result cleanly

> The local model completed direct 20-, 30-, and 60-second real-footage requests in 14.749, 9.779, and 28.315 seconds. All produced schema-valid reports. Strict timestamp-aligned reference recovery was zero of two, zero of two, and zero of four. The sixty-second answer fluently misplaced replay and live action. Six denser ten-second requests also scored zero of four and took 204.157 seconds. So longer context fits, but semantic and temporal reliability is the blocker; shorter windows are still a hypothesis, not a demonstrated fix.

### Slide 19 — Run the 30-second coach-search demo

Follow the coach-query sequence in the next section. The saved video report is fixed, but the local query LLM runs live and the result card opens the real 30-second SoccerNet evidence window.

### Slide 20 — End with the searchable-coaching research program

> What I have today is genuine footage, a detailed VLM report contract, a working searchable index, a full-half window planner, and a measured failure boundary. Next, freeze coach-relevant event definitions and match-grouped annotations; evaluate discovery, field factuality, identity abstention, evidence grounding, and retrieval separately; then test whether a coach finds and verifies the right clip faster. Fine-tuning waits until this evaluation contract is stable.

Ask Archit:

> Would you make the next frozen milestone full-half discovery over a small event taxonomy, or field-level factual reporting and retrieval over fewer events first?

## Three-minute live demo

### A. Coach query → local LLM plan → real footage (about two minutes)

The browser should already be open at `http://127.0.0.1:8770/`. If it is not, double-click `START_COACH_SEARCH_UI.cmd`. Use the default query:

> Show me shots involving the goalkeeper near the goal area

1. Start on the red warning banner and say: “The infrastructure works; the soccer semantics currently fail.”
2. Click **Search with local LLM**. During the roughly six-second wait, explain that the query LLM is not the video VLM. It translates the coach's words into a strict search plan; it does not rewatch the clip.
3. Point to **LOCAL LLM PLAN**, model identity, latency, event filters, search terms, and the transparent match-score evidence.
4. Click **Play evidence**. The player seeks to the event card's cited timestamp in the real 30-second SoccerNet clip.
5. Click **See held-out audit**. Show `Penalty`, `Shots on target`, and `Goal`, and say that these labels were never sent to either model call.

Say:

> There are two model calls. First, the video VLM previously wrote a detailed event card from silent frames. Second, a local language model now interprets my coaching query. Deterministic code only validates the plan and ranks the saved text. The search correctly retrieves what Gemma wrote, but Gemma's report is wrong: held-out SoccerNet labels show a penalty, shot on target, and goal, while the report says save and clearance. That is why the UI says systems go, semantic no-go.

Safe claim: the private, inspectable search pipeline works end to end. Unsafe claim: the current VLM understands the play correctly.

### B. Optional saved visual/audio comparison (only if Archit asks)

The browser should already be open at `http://127.0.0.1:8765/`.

1. Select the fifth clip tab.
2. Keep the commentary and mapped-label panels closed.
3. Play the entire ten-second **silent** VLM clip. If needed, focus the player and press Space.
4. Point to the fixed Qwen result: `yellow_card`, generated self-score `0.95`, and its model-proposed evidence fields.
5. Say: “This result was computed locally and saved before the demo. Playback gating is presentation choreography; the experimental protection is the persisted hash seal.”
6. Open the commentary version. Expand the timestamped transcript and show that its separately inferred label is also `yellow_card`, producing `supports`.
7. Reveal the mapped center label: `yellow_card`.
8. If Archit wants implementation evidence, open **Technical inspection** and show the model/config/prompt/runtime/media hashes.

Close the demo with:

> This is a successful case, not representative evidence. The same run also confidently confuses a shot off target with a goal and a foul with a shot on target, which is why the per-clip table and frozen denominators matter more than a cherry-picked clip.

## Backend deep dive for a technical discussion

### The two-model search path

1. `searchable_match_vlm.py` divides a match into overlapping windows, samples silent frames, and asks the video VLM for zero or more structured event cards.
2. Every card stores start/key/end times, participants or anonymous track IDs, team role, event and secondary actions, phase, field area, outcome, coaching relevance, evidence frames, and field-level uncertainty.
3. Validation is fail-closed. Bad JSON, unsafe paths, out-of-window evidence, and missing required fields are rejected. The cards and provenance go into a private SQLite full-text index.
4. At search time, `search_demo_server.py` sends only the user's sentence plus the retrieval ontology to the local query LLM. It requires a strict plan containing event filters, free-text terms, participant terms, phases, and field areas.
5. Ordinary deterministic code applies that plan to the saved VLM text and exposes every score contribution. It never infers foul, offside, long ball, or any other soccer meaning from pixels.
6. Held-out SoccerNet labels are loaded into a separate post-hoc audit panel. They are absent from both the video-VLM request and the query-LLM request, preventing answer leakage.

The full-half planner currently produces 108 gap-free 30-second windows at a 25-second stride for a 2,700-second half. Only one 30-second window has been fully inferred and indexed in the live UI; dense refinement and overlapping-window duplicate merging remain future work.

### Data and leakage boundaries

- Provider media, SoccerNet labels, Echoes ASR, the pinned SoccerDB mapping row, and all derivatives are SHA-256 bound.
- Labels select windows upstream, so this is an event-conditioned task. They are absent from the VLM request and joined only after prediction persistence.
- The current 30-second VLM input and its browser review derivative are both verified silent. The older optional ten-second comparison keeps a separate audio-bearing review file; that is a different demo path.
- The server is loopback-only. Requests cannot redirect or inherit environment proxies.
- Public summaries contain opaque clip IDs and normalized results, not transcripts, credentials, private absolute paths, or media.

### Earlier ten-second label-pilot contract

- Input: 12 uniform decoded frames from a ten-second clip.
- Taxonomy: the 17 normalized SoccerNet-v2 action types plus `background_or_other`; the separate abstention token is `insufficient_visual_evidence`.
- Output: one label, one generated self-score in `[0,1]`, one positive-duration temporal interval, nonempty coarse spatial evidence for non-abstentions, an empty trajectory in this pilot, and an explicit abstention reason when applicable.
- Validation rejects non-finite numbers, out-of-range scores, malformed intervals, inconsistent abstentions, wrong model identity, unsafe paths, stale cache entries, and mismatched hashes.
- Scoring is requested-set and fail-closed. Completed-only statistics are diagnostics, never the headline.

### Why this is VLM classification rather than an “algorithm”

The deterministic portion never maps pixels to a soccer label. It only:

1. isolates media modalities;
2. decodes/samples frames;
3. packages and hashes inputs;
4. enforces the response contract;
5. joins saved predictions to mapped annotations;
6. computes metrics and provenance receipts.

The only component producing the semantic class from pixels is the local multimodal language model. Conversely, this is not end-to-end video training: both models are frozen pretrained checkpoints used through prompted inference.

### Commentary computation

The visual-summary seal is written before any ASR file is opened. The text request contains only opaque segment IDs, relative times, text, duration, and midpoint. It excludes the visual answer, mapped label, match identity, file path, and audio. After the text output is persisted, deterministic equality yields `supports`, `contradicts`, or `uninformative`. This gives causal non-intervention, not statistical independence.

## Likely PhD-level questions

### “What exactly is the estimand?”

> A descriptive requested-set proportion over six selected windows: whether the emitted class equals any mapped SoccerNet point label falling inside the ten-second window. It is conditional on event-centered selection and this one match. There is no declared target population, so I do not interpret it as a population accuracy estimate.

### “Why use allowed-window labels rather than the center label?”

> SoccerNet-v2 annotations are timestamped points, not mutually exclusive intervals. A ten-second window can contain multiple points. Allowed-window scoring prevents an adjacent annotated event from being automatically treated as wrong. I separately report exact accuracy for the two windows containing a single mapped label. Neither metric proves visual answerability.

### “Why no confidence interval?”

> The six clips are clustered within one match and were deliberately selected around events. A clip-level binomial interval would assert an independence and sampling model that the design does not have. Match-level uncertainty is not estimable from one match.

### “Are those confidence values calibrated?”

> No. They are generated self-scores constrained to `[0,1]`. There is no calibration set, enough samples for reliability bins, or selective-risk curve. The defensible observation is simply that all three Qwen errors also received scores of at least 0.90.

### “Is the grounding valid?”

> Structurally valid, semantically unscored. The schema requires an interval and coarse region text, but no human annotated the actual supporting frames, boxes, pitch coordinates, or trajectories. I make no grounding-quality claim.

### “Why not native video?”

> Twelve deterministic frames make the payload inspectable and reproducible on an 8 GB consumer GPU, but introduce temporal aliasing. Native video, identical-sheet packaging, and sampling density should be explicit factors in the next experiment rather than silently changed implementation details.

### “Could the model exploit the scoreboard, replay graphics, or broadcast grammar?”

> Yes. The prompt withholds match identity and score context, but the pixels can contain overlays and production cues. A stronger study needs scoreboard masking, replay-logo perturbations, camera-shot controls, and semantically matched negatives to measure those shortcuts.

### “Does commentary validate the visual answer?”

> No. It is the same event through another noisy channel, not external truth. The seal prevents it from changing vision; it does not remove shared-event dependence. I would score commentary-only and late fusion as separate preregistered conditions.

### “Where is the training?”

> There is none at the weight level. “Train” is a legacy split name for five development clips used in prompt/runtime engineering. Before LoRA or other adaptation, the project needs more match groups, a frozen annotation protocol, and a genuinely untouched test set.

### “Why compare Qwen and Gemma if representation differs?”

> It is an engineering probe prompted by a context-limit failure, not a controlled model comparison. The exact decoded frames are matched, but grouping and geometry differ. The next design should cross model × packaging × sampling so the effects are identifiable.

### “Is this SoccerDB or SoccerNet?”

> The broadcast bytes and evaluation point labels are SoccerNet. SoccerDB contributes the public identity mapping that proves the selected SoccerNet halves occur in SoccerDB's published overlap. The precise phrase is “SoccerDB-mapped SoccerNet footage.”

### “What would make this publishable?”

> A preregistered task; rights-safe match diversity; background and hard negatives; double annotation and adjudication of answerability plus evidence; matched model/representation conditions; match-grouped uncertainty; calibration and selective-risk analysis; and separately scored visual-only, commentary-only, and fusion baselines.

### “Why cite HCI work in an ML evaluation?”

> Dr. Lin's work defines downstream validity and the human evaluation target; it does not substitute for model-performance evidence. It tells us which interpretation and evidence should be inspectable, which user role must be named, and why correction behavior—not satisfaction alone—matters after the perception layer is technically valid.

### “What is new beyond Sportify or SoccerAgent?”

> Nothing is established as new by six clips. The candidate contribution is a controlled direct-VLM soccer study with externally adjudicated answer-linked evidence, selective abstention, match-grouped evaluation, and sealed modality comparisons, followed by explicit rather than hidden tool augmentations.

### “Are the model's intervals and regions explanations?”

> They are structured claims, not validated explanations. They become evidence only after people annotate and score the corresponding moments and regions and after same-clip questions show that the selected evidence changes with the question.

### “Why only 50 clips next?”

> Fifty is a feasibility and annotation-reliability pilot, not a powered benchmark. The goal is to stabilize answerability, evidence labels, hard negatives, and tooling across at least ten matches before spending effort on scale or weight updates. Match clustering still limits the effective sample size.

### “Will tracking or a classical algorithm determine the label?”

> No. The semantic label remains VLM-produced. Any game-state reconstruction, trajectory model, retrieval system, or tracker is a separately declared experimental condition whose incremental value is measured. Deterministic code continues to handle provenance, validation, and scoring—not play recognition.

### “What would the expert study measure?”

> Verification time, correction rate, missed-error rate, and final decision correctness, stratified by correct, incorrect, and abstained model outputs. Preference and satisfaction are secondary process measures, not the success criterion.

## Demo failure contingency

If the browser or server fails, do not rerun inference in front of Archit.

1. Reopen the coach-search UI with `START_COACH_SEARCH_UI.cmd` in the project root.
2. If playback still fails, use slide 19's verified screenshot and the terminal fallback `START_SEARCH_DEMO.cmd`.
3. Show the saved 30-second event-card receipt and the held-out mismatch described on slides 18–20.
4. State exactly which part is live: the query LLM and retrieval. The video VLM report is already persisted and hash-bound.
5. Never substitute synthetic footage, call the retrieved report correct, or imply that the video VLM was rerun live.

## Source cues

- SoccerNet rights/data/task: [FAQ](https://www.soccer-net.org/faq), [data catalog](https://www.soccer-net.org/data), [action spotting](https://www.soccer-net.org/tasks/action-spotting), [devkit](https://github.com/SoccerNet/sn-spotting)
- SoccerDB identity mapping: [paper](https://arxiv.org/html/1912.04465), [repository](https://github.com/newsdata/SoccerDB)
- Commentary: [SoccerNet-Echoes](https://arxiv.org/html/2405.07354), [commentary-only spotting](https://aclanthology.org/2025.ijcnlp-srw.6/)
- VLM context: [Gemma 4](https://ai.google.dev/gemma/docs/core/model_card_4), [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B), [soccer domain adaptation](https://openaccess.thecvf.com/content/CVPR2025W/CVSPORTS/html/Jiang_Domain_Adaptation_of_VLM_for_Soccer_Video_Understanding_CVPRW_2025_paper.html), [SoccerLens](https://arxiv.org/html/2605.09598)
- Dr. Tica Lin: [official profile and publications](https://ticalin.com/), [Sportify](https://arxiv.org/abs/2408.05123), [VIRD](https://arxiv.org/abs/2307.12539), [The Ball is in Our Court](https://arxiv.org/abs/2211.07832), [Who's That Player?](https://vcg.seas.harvard.edu/publications/who-s-that-player)
- Tool/evidence context: [SoccerAgent / SoccerBench](https://arxiv.org/abs/2505.03735), [NExT-GQA](https://openaccess.thecvf.com/content/CVPR2024/html/Xiao_Can_I_Trust_Your_Answer_Visually_Grounded_Video_Question_Answering_CVPR_2024_paper.html), [SoccerNet-GSR](https://openaccess.thecvf.com/content/CVPR2024W/CVsports/html/Somers_SoccerNet_Game_State_Reconstruction_End-to-End_Athlete_Tracking_and_Identification_on_CVPRW_2024_paper.html)
