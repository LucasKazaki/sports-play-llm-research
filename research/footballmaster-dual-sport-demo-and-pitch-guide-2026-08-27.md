# Dual-sport coach-search live demo and UMD pitch guide

**Prepared:** August 27, 2026  
**Target length:** 18 minutes, with a two-minute buffer  
**Audience:** Archit first; later a UMD coach/video/analytics workflow owner and media/compliance reviewer  
**Demo URL:** `http://127.0.0.1:8771/`  
**Technical reference:** [dual-sport technical report](footballmaster-dual-sport-technical-report-2026-08-27.md)  
**Goal:** demonstrate an honest, reproducible research scaffold and obtain a bounded workflow-design next step—not approval to deploy

## The one-sentence message

> “This is a local, evidence-first research scaffold: a coach asks in ordinary language, the system returns the exact source clip and a claim-origin ledger, and the demo makes both the soccer semantic failure and the football pilot's high-confidence failure visible.”

Do **not** call this a SoccerMaster replication, a football VLM, a whole-game understanding system, a coach-ready product, or a validated UMD workflow. No detailed football report was authored by a VLM. The soccer retrieval system works but its saved semantic report is wrong. The football classifier is trained, but only for touchdown versus not touchdown on nine weakly labeled clips; the three-clip test is a pipeline result, not a performance estimate. [Measured claim boundary](footballmaster-dual-sport-technical-report-2026-08-27.md#abstract)

## Preflight: five minutes before the meeting

Open PowerShell in `C:\AI\projects\SportsPlayLLMResearch`.

```powershell
# 1. Reverify the football media/split and immutable model package.
& .\.venv-soccernet\Scripts\python.exe .\data\public\footballmaster\verify_manifest.py
& .\.venv-soccernet\Scripts\python.exe .\prototype\footballmaster_pilot.py verify `
  --model-dir .\artifacts\footballmaster\pilot-v1

# 2. Start the local dual-sport server.
& .\.venv-soccernet\Scripts\python.exe .\prototype\multisport_search_demo_server.py `
  --host 127.0.0.1 --port 8771 --open-browser
```

Leave that PowerShell window open. In a second PowerShell window, check:

```powershell
Invoke-RestMethod http://127.0.0.1:8771/healthz
Invoke-RestMethod 'http://127.0.0.1:8771/api/status?sport=soccer'
Invoke-RestMethod 'http://127.0.0.1:8771/api/status?sport=football'
```

Expected facts from the current sealed artifacts:

- `/healthz` reports both `soccer` and `football` available.
- Soccer shows one 30-second window, three saved reports, and `SYSTEMS GO / SEMANTIC NO-GO`.
- Football shows nine clips/reports, a source-held-out test, a real fitted checkpoint, and `TRAINED PILOT / COACHING CLAIMS NO-GO`.
- The query-model badge is either **LOCAL MODEL ONLINE** or **FALLBACK READY**. Both are demo-safe because the literal fallback is visibly labeled.

Open these backup artifacts in advance:

- [football contact-sheet overview](../data/public/footballmaster/contact-sheets/overview.jpg)
- [whole-source split figure](../presentation/figures/FootballMaster-source-heldout-split-2026-08-27.png)
- [held-out metrics and confusion-matrix figure](../presentation/figures/FootballMaster-heldout-performance-2026-08-27.png)
- [football metrics](../artifacts/footballmaster/pilot-v1/metrics.json)
- [per-clip predictions](../artifacts/footballmaster/pilot-v1/predictions.jsonl)
- [model card](../artifacts/footballmaster/pilot-v1/model-card.json)
- [rights/source report](footballmaster-public-data-rights-and-split-2026-08-27.md)

If port 8771 is occupied, restart with `--port 8772` and use `http://127.0.0.1:8772/`. Do not bind to `0.0.0.0`; the server rejects non-loopback hosts by design. [Backend implementation](../prototype/multisport_search_demo_server.py)

## Screen map: know what to point at

1. **Sport switch:** changes ontology, index, evaluation panel, attribution, warnings, and default clip—not merely the color theme.
2. **Two status badges:** operational availability and claim status are separate.
3. **Search box:** sends only `{sport, query}`.
4. **Retrieval results:** stored reports ranked by validated deterministic code.
5. **Original video panel:** locally served, seekable evidence.
6. **Query LLM trace:** visible event filters, search terms, role terms, space/phase filters, source, model, and latency.
7. **Claim origin:** identifies learned probe fields, weak source metadata, deterministic processing, or saved VLM fields.
8. **Evaluation/audit panel:** soccer uses separately loaded held-out SoccerNet annotations; football uses the measured tiny-pilot result.
9. **Pipeline boundary:** names which component produced each claim.

## 18-minute technical walkthrough

### 0:00–1:30 — Open with the result and truth boundary

**Action:** Open `http://127.0.0.1:8771/?sport=soccer`. Keep the warning and both status badges on screen.

**Say:**

> “I built one local interface around two distinct experiments. The soccer side tests whether a VLM can turn real silent SoccerNet footage into searchable, evidence-linked event reports. The system path works, but the report is factually wrong, so it says systems-go and semantic-no-go. The football side is a newly trained visual pilot, but only for touchdown versus not-touchdown. It is not SoccerMaster-scale and it is not a football VLM. The point of this demo is that those boundaries are visible and testable.”

**If asked immediately for the headline number:**

> “Two of three source-held-out football clips were classified correctly versus one of three for the train-majority baseline, but the 95% Wilson interval is 20.8% to 93.9% and the model made a 94.9%-score mistake. That is pipeline evidence, not a generalization claim.”

### 1:30–3:30 — Explain where the language model is—and is not

**Action:** Point to the search box, query trace panel, and pipeline boundary.

**Say:**

> “There are two language-model roles, and they must not be conflated. In soccer, a VLM produced the saved event cards from video. At query time, a local language model sees only the coach's sentence plus a public sport ontology and emits a strict retrieval plan. It never sees video, audio, labels, predictions, or audit data. Ordinary code validates that plan, ranks already-saved records, and serves the allowlisted clip. In football there is no report VLM yet: the learned fields are only the binary probability and embedding; the fine tag is source metadata and the prose is deterministic.”

**Point to:** `QUERY LLM TRACE`, `CLAIM ORIGIN`, and the sport-specific pipeline list.

**Technical detail if useful:** the API is `POST /api/search` with `{sport, query}`; bad/absent query-model output becomes a clearly labeled literal fallback. The server is loopback-only, verifies the football package hashes, constrains media paths to the allowlisted roots, and supports byte ranges for seeking. [Backend contract](footballmaster-dual-sport-technical-report-2026-08-27.md#one-interface-exposes-two-ontologies-and-four-claim-origins)

### 3:30–7:00 — Soccer mode: demonstrate the failure, not just the retrieval

**Action 1:** Run this exact query:

```text
Show me shots involving the goalkeeper near the goal area
```

**Expected behavior:** the top result is the saved goalkeeper/shot report. The exact result count can depend on the query plan, so do not promise a count. Click **Play evidence**.

**Say:**

> “The query path works. The local query LLM made a visible soccer plan, deterministic code matched a saved VLM card, and the result seeks the real clip. But the card's self-score is not evidence that it is true.”

**Action 2:** Point to the result's `CLAIM ORIGIN` and uncertainty. Then click **See held-out audit**. Click the audit buttons around 14.5 and 15.0 seconds into the review clip.

**Say:**

> “The held-out annotations show a penalty and shot on target at 29:54, followed by a goal at 29:55. They are loaded only after inference and were never in the VLM or query prompt. The saved report instead claims a save/clearance and also invents build-up and corner sequences. So this is a successful systems demonstration and a failed semantic result.”

**Optional second query, if there is time:**

```text
Find set pieces and crosses from the corner
```

This retrieves the invented corner report. Use it to make the point that good search can faithfully retrieve a bad representation. The same-clip duration probe over 20, 30, and 60 seconds plus denser ten-second windows recovered 0/4 strict timestamp-aligned target events; that is a selected engineering study, not a benchmark or model ranking. [Soccer truth boundary](archit-next-meeting-soccermaster-brief-2026-08-27.md#current-project-state-and-truth-boundary)

### 7:00–9:00 — Switch sports and explain the trained football path

**Action:** Click **American football**. Wait for the nine-clip status and video to load. Point to `RIGHTS-AUDITED TRAINED PILOT` and the real CC-licensed video.

**Say:**

> “The switch changes the ontology, data package, media routes, evaluation, and attribution contract. These are nine real Wikimedia Commons clips from eight source groups, totaling 151.9 seconds. Every file is hash-bound and fully decoded; the FAU–UCF clips stay together in train, and test has three entirely separate source groups. Audio is excluded. Fine labels are weak Commons descriptions, not independent ground truth.”

Then give the model in one breath:

> “Eight uniform frames go through a frozen ONNX MobileNetV2 ImageNet classifier. I pool the 1,000 frame scores with mean, standard deviation, and endpoint difference, fit train-only standardization and a three-component PCA, then fit an eight-parameter two-class softmax head. The defined PCA-plus-head count is 9,008 parameters—9,000 unsupervised PCA coefficients and 8 supervised weights/biases. The backbone is not retrained.”

**Do not say:** “I trained a football foundation model.”  
**Do say:** “I trained a small football representation probe and verified its package.”

### 9:00–12:00 — Football mode: lead with the high-confidence miss

**Action:** Run this exact query:

```text
Find the Chiefs Buccaneers touchdown pass
```

The query is chosen so both the local LLM and the literal fallback rank the intended held-out clip first. Click **Play evidence** on the Chiefs–Buccaneers test result.

**Say:**

> “The source description weakly labels this as a touchdown pass. The learned probe predicts not-touchdown with a 0.9494 score, and that is wrong under the weak reference. Notice the card does not hide the contradiction: the source tag, learned prediction, deterministic prose, and playable source clip are separate.”

**Point to:** `CLAIM ORIGIN`, predicted label/probabilities, `split: test`, source attribution, and the absence of VLM evidence frames or participants.

**Say:**

> “This is why I call the score uncalibrated. The most useful output of a tiny pilot is often the failure that tells us what not to claim.”

**Action:** Scroll to the measured evaluation panel.

**Say:**

> “The complete test is 2/3 correct, balanced accuracy 0.75, macro F1 0.667, versus 1/3 and balanced accuracy 0.5 for the train-majority baseline. With three examples, the 95% accuracy interval is 0.208 to 0.939. There is no meaningful deployment estimate here.”

### 12:00–13:30 — Show a correct case without turning it into marketing

**Action:** Run:

```text
Find the SMU Louisville touchdown pass
```

**Expected behavior:** the held-out SMU–Louisville clip ranks first; the weak source label is touchdown and the probe predicts touchdown with a 0.9424 score.

**Say:**

> “This one is correct under the same weak-label protocol. It proves the inference/search/media path can produce and surface a correct case; it does not cancel the Chiefs miss or establish generalization.”

**Optional domain-shift query:**

```text
Show the Justin Bethel interception practice clip
```

This held-out negative is correctly predicted not-touchdown with a 0.9996 score, but it is minicamp practice rather than game footage. Use it only to explain why domain composition matters.

### 13:30–15:30 — Compare the research roles, not the headline accuracies

**Say:**

> “SoccerMaster's authors train a large soccer-specific encoder on millions of frames and multiple tasks. I have not reproduced that training or deployed its checkpoint here. My soccer experiment tests detailed VLM reporting and exposes a semantic failure. FootballMaster-Pilot is a much smaller binary visual baseline with real fitted parameters. Their metrics are not comparable. The shared scientific object is the evaluation scaffold: rights, source-held-out data, declared model inputs, structured evidence, retrieval, and human audit.”

Then connect to Dr. Lin:

> “The product direction follows Tica Lin's evidence-first sports systems: perception, explanation, and interaction should be separable. A fluent narrative should consume inspectable evidence; it should not become the evidence. The UI therefore externalizes the query plan and claim origin and keeps a correction/abstention path as a research requirement.”

Primary research: [SoccerMaster](https://haolinyang-hlyang.github.io/SoccerMaster/), [Sportify](https://arxiv.org/abs/2408.05123), [VIRD](https://arxiv.org/abs/2307.12539), and [Who's That Player?](https://vcg.seas.harvard.edu/publications/who-s-that-player).

### 15:30–17:00 — Translate it into two coach workflows

**Say:**

> “The UI can be shared; the evidence contracts cannot. Soccer is continuous and phase-based: possession, transitions, pitch regions, multi-event sequences, and replay/live state. Football is play-bounded and situation-based: down/distance, field and hash, personnel, formation, motion, snap-to-whistle structure, coverage evidence, and result. The current football model does not infer those fields. Those are the coach-defined targets for the next study.”

Give one candidate use case per sport:

- **Soccer:** “Show losses in the middle third where the nearest three players did not immediately counter-press and the opponent progressed.” Evidence versus interpretation must be distinct.
- **Football:** “Show third-and-medium plays from the left hash against 11 personnel with fast motion, grouped by visible coverage shell.” Counts must come from coach-validated tags and expose denominators.

These are hypotheses from established film/performance-analysis workflows, not evidence that a UMD coach wants this exact tool. [Coach use-case evidence and caveats](umd-coach-search-pilot-memo-2026-08-27.md)

### 17:00–18:00 — Make one bounded UMD ask

**Say:**

> “I am not asking for the archive or for sideline deployment. I am asking for a 45-minute workflow interview and permission to define a four-week, read-only post-game shadow pilot. We would need one workflow owner and one media/compliance approver, twelve coach-authored queries per sport, a small game-held-out set, and an explicit data-retention plan. The current system remains outside player-selection, discipline, medical, officiating, and live in-game decisions.”

Then stop. Let Archit react.

The UMD football staff page publicly identifies coaching-operations/analytics, football-technology, video, and analyst functions; soccer should designate its actual owner because the public pages do not name a sport-specific analytics/video role. This is an outreach clue, not proof of an internal workflow. Version 1 remains post-game because the NCAA's [football technology rule explanation](https://www.ncaa.org/media-center-technology-rules-approved-in-football/) excludes analytics/data access from the controlled in-game tablet context; compliance must recheck the [current rules](https://www.ncaa.org/championships/playing-rules/football-playing-rules/) before any live proposal. UMD sources: [football staff](https://umterps.com/sports/football/coaches/2026), [men's soccer](https://umterps.com/sports/mens-soccer/coaches), [women's soccer](https://umterps.com/sports/womens-soccer/coaches).

## Exact claims to use and claims to avoid

| Use this wording | Never use this wording |
|---|---|
| “A trained binary football probe on nine rights-audited clips” | “A trained FootballMaster foundation model” |
| “2/3 source-held-out clips in a descriptive pilot” | “67% football accuracy” without denominator/interval |
| “Weak source-description reference label” | “Ground-truth football annotation” |
| “Uncalibrated softmax score” | “94.9% confidence means 94.9% likely” |
| “Source metadata says touchdown pass; the probe predicts not-touchdown” | “The model detected a touchdown pass” when the fine tag came from metadata |
| “Detailed football prose is deterministic; no football VLM is attached” | “The football VLM wrote this report” |
| “Soccer retrieval works; current semantics fail held-out audit” | “The soccer system understands the play” |
| “SoccerMaster motivates a representation experiment” | “We replicated or trained SoccerMaster” |
| “Candidate coach workflow to validate” | “Coaches need this” or “UMD wants this” |
| “Post-game, read-only shadow pilot” | “Live sideline analytics” |
| “CC-licensed files with recorded conditions” | “Anything publicly viewable is safe to train on” |

## Backup plan if the live demo misbehaves

### Query LLM is offline or slow

Do not restart the presentation. The UI will show **FALLBACK READY** and label the trace `deterministic_literal_fallback`. Use these exact prompts because they also work as literal terms:

```text
Show me shots involving the goalkeeper near the goal area
Find the Chiefs Buccaneers touchdown pass
Find the SMU Louisville touchdown pass
Show the Justin Bethel interception practice clip
```

Say: “The query-model dependency is degraded, so the system preserved literal terms and labeled the fallback. The saved reports and video evidence are unchanged.” This is preferable to hiding a fallback.

### Browser UI loads but a search request fails

Use the API directly from a second PowerShell window:

```powershell
$body = @{
  sport = 'football'
  query = 'Find the Chiefs Buccaneers touchdown pass'
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8771/api/search `
  -ContentType 'application/json' `
  -Body $body | ConvertTo-Json -Depth 10
```

Point out `interpretation.source`, the strict `plan`, `results[].split`, `results[].attribution`, and `results[].clip_url`.

### Server does not start

1. Rerun the two verification commands from preflight and show their pass receipts.
2. Open the [contact sheet](../data/public/footballmaster/contact-sheets/overview.jpg) to prove the inputs are real football footage.
3. Show the [whole-source split figure](../presentation/figures/FootballMaster-source-heldout-split-2026-08-27.png), then the [held-out metrics/confusion-matrix figure](../presentation/figures/FootballMaster-heldout-performance-2026-08-27.png). Both are generated from the recorded artifacts and visibly carry the small-sample boundary.
4. Open [predictions.jsonl](../artifacts/footballmaster/pilot-v1/predictions.jsonl) and search for `chiefs-buccaneers-2024` to show the exact failure.
5. Open [metrics.json](../artifacts/footballmaster/pilot-v1/metrics.json) to show the denominator, baseline, interval, and confusion matrix.
6. Continue with the architecture and UMD-pilot discussion. Do not improvise performance numbers.

### Video playback fails

The result is still auditable through its local media path, SHA-256, source page, license, and timestamps. Use the contact sheet and source manifest, then state that playback is an interface failure rather than model evidence. Do not replace the clip with an unaudited web broadcast during the meeting.

### Soccer private review data is unavailable

Demonstrate football only, then show the saved soccer truth boundary in the [technical report](footballmaster-dual-sport-technical-report-2026-08-27.md#soccer-is-systems-go-and-semantic-no-go). Do not substitute unlicensed public footage or claim the soccer path was live-verified in that session.

## Anticipated PhD-level questions and concise answers

### 1. “Did you actually train anything?”

Yes. Four training clips fit 6,000 mean/scale statistics, 9,000 PCA coefficients, and an eight-parameter supervised softmax head. The model card defines 9,008 learned PCA/head parameters and 15,008 total persisted fitted values. The MobileNetV2 ImageNet backbone is frozen. [Model card](../artifacts/footballmaster/pilot-v1/model-card.json)

### 2. “Why call it FootballMaster if it is not SoccerMaster-scale?”

`FootballMaster-Pilot` names the research track and interface contract, not architectural equivalence. It is explicitly `soccer_master_replication=false` and prohibits “foundation model” and “generalizes to football games” claims. A more accurate technical description is “frozen-frame-descriptor touchdown probe.”

### 3. “Why MobileNetV2 1,000-class outputs instead of a video encoder or penultimate features?”

They provide a free, documented, hashable ONNX baseline that runs on CPU and exercises the full train/evaluate/checkpoint/search path. They are a deliberately weak representation, not the recommended endpoint. The next comparison should add a true temporal video representation under the identical data/split contract.

### 4. “How can PCA have 9,000 coefficients with four training examples?”

The pooled descriptor is 3,000-dimensional and the training matrix can supply only three nonzero centered components; 3 × 3,000 = 9,000 projection coefficients. That count does not imply sufficient data. It highlights the extreme sample-to-state mismatch and overfitting risk.

### 5. “Which parameters are supervised?”

Only the eight softmax weights/biases. PCA is train-fitted but unsupervised; mean/scale are fitted preprocessing statistics; MobileNetV2 is inherited and frozen.

### 6. “Does source-held-out testing solve leakage?”

No. It prevents the same recorded game/session from crossing splits, including the two FAU–UCF clips. It does not eliminate team, venue, camera, celebration, end-zone, or domain shortcuts, and eight source groups are far too few to estimate them.

### 7. “Could filenames or source descriptions give away touchdown?”

The visual descriptor receives decoded RGB frames only; audio and source text are not feature inputs. Source descriptions create weak labels and are retained as explicitly attributed search metadata. A rename-invariance test is still a required robustness check and is not claimed as completed.

### 8. “Is 2/3 meaningfully better than 1/3?”

No inferential claim is supported. The 95% Wilson interval for the model's accuracy is 0.208–0.939, and the baseline interval is 0.061–0.792. The result verifies mechanics and exposes a counterexample; it does not establish superiority.

### 9. “Why use balanced accuracy and macro F1?”

They give both classes equal influence. On the three test clips, negative recall is 1/1 and touchdown recall is 1/2, so balanced accuracy is `(1.0 + 0.5) / 2 = 0.75`. Each class F1 is 0.667, so macro F1 is 0.667.

### 10. “Is the softmax output calibrated?”

No. The source-labeled Chiefs touchdown is predicted not-touchdown with a 0.9494 score. With three test points, no calibration estimate is possible.

### 11. “Why are the train and validation metrics perfect?”

There are only four train and two validation clips, a high-capacity fitted projection relative to sample size, and epoch selection on those two validation points. Perfect values are a warning about fragility, not a result to advertise.

### 12. “Are the football event tags model outputs?”

No. `touchdown_pass`, `rushing_touchdown`, `kickoff_return`, `field_goal_attempt`, and `interception_practice` are Commons source-description metadata. The only learned target is binary `is_touchdown`.

### 13. “Who wrote the detailed football report?”

Deterministic template code projects the weak source tag and binary prediction into the shared display schema. `participants` and `evidence_frames` are empty, and `vlm_generated_fields` is empty. No football VLM authored the prose.

### 14. “Then what does the query LLM do?”

It translates the coach sentence into a strict sport-specific retrieval plan. It receives the query and ontology only. Deterministic code validates and ranks saved text; the query LLM does not classify the clip.

### 15. “Did you run SoccerMaster?”

No. The repository contains a feasibility and release audit, not a local SoccerMaster reproduction. The authors report a large multi-GPU soccer-specific training regime; checkpoint inference or frozen-feature extraction is the appropriate first local experiment after license and split-overlap checks. [SoccerMaster brief](archit-next-meeting-soccermaster-brief-2026-08-27.md)

### 16. “Why show a soccer system that is wrong?”

Because it demonstrates falsifiability and prevents UI quality from being confused with model quality. The held-out labels are isolated and reveal that the saved VLM event cards are not coach-ready.

### 17. “Can this search an entire match or game?”

Not yet. The architecture is window/index based, but this demo has one 30-second soccer window and nine short football clips. Full-game claims require long-video windowing, event-boundary evaluation, false positives per hour, source-held-out matches/games, and latency/storage measurements.

### 18. “Why not use commentator audio as truth?”

Commentary may reveal event labels and therefore leaks answers into visual evaluation; ASR also introduces its own errors. Future work should seal visual-only output first, then score commentary-only and late-fusion branches separately. Commentary can be a noisy post-hoc cross-check, not automatically ground truth. [Research framing](dr-tica-lin-and-soccer-vlm-research-2026-08-27.md)

### 19. “Are the videos legal to train on?”

The admitted clips have recorded CC BY/CC BY-SA file-page evidence and conditions, and local video-only research passes the project gate. That is not a blanket legal warranty. Third-party API upload is not authorized by the manifest, and weight publication remains held for institutional review of ShareAlike and other rights.

### 20. “Has a coach validated usefulness?”

No. All coach use cases and thresholds are hypotheses. The proposal is designed to measure top-five relevance, recall, evidence grounding, cutup time, unsupported claims, operational fit, and governance against the existing workflow.

### 21. “What is the strongest next experiment?”

Freeze coach-authored queries and a game-grouped adjudicated test, then compare direct video VLM reports, declared sport-specific representation evidence, and the frozen probe under the same clips and scoring contract. Evaluate answer/report correctness jointly with timestamps/regions and expert verification time.

### 22. “What result would make you stop?”

Stop or narrow the system if the augmented model cannot improve a preregistered evidence-linked metric or verification outcome at a fixed unsupported-event rate, if a critical query regresses, or if governance/workflow cost exceeds the measured benefit.

### 23. “Why not train fine-grained football concepts now?”

The current corpus has one or two examples for most fine tags and no labels for formation, coverage, routes, blocking, pressure, players, or boundaries. Fine-grained fitting would create an impressive-looking but scientifically undefined classifier.

### 24. “How is the local server secured?”

It binds only to loopback, validates request size and sport, verifies the football package hashes, allows media only from exact roots, rejects path escapes, and serves byte ranges with private/no-store headers. It is still a research prototype, not a complete multi-user security review.

### 25. “Why should UMD participate?”

Not to endorse the model. UMD coaches/video staff can define the vocabulary, evidence, failure cost, and baseline that public clips cannot provide. A small shadow study can quickly falsify whether the system saves time without lowering correctness.

## The proposed four-week UMD pilot in one slide

| Week | What happens | What is measured |
|---|---|---|
| 0 | Rights, data location, retention, current workflow, forbidden uses, owners | Approved scope and baseline |
| 1 | Coaches define 12 queries per sport and adjudicate a balanced reference set | Taxonomy, answerability, agreement, sealed game split |
| 2 | Read-only shadow retrieval; existing system remains source of record | Time, top-k results, abstentions, failures |
| 3 | Blind comparison of shuffled system and baseline cutups | Relevance, completeness, missed clips, reviewer agreement |
| 4 | Failure review and stop/revise/expand decision | Per-query evidence plus deletion/retention action |

Starting gates—subject to coach revision—are top-five relevance ≥80%, held-out recall ≥75%, evidence grounding ≥95%, median cutup-time reduction ≥40%, zero unsupported high-confidence statements, 100% pilot import/open/export, and zero governance incidents. Always show raw counts and game-grouped uncertainty. These are proposal gates, not current results. [Full pilot protocol](umd-coach-search-pilot-memo-2026-08-27.md#a-credible-four-week-shadow-pilot)

## Final bounded ask

Use this verbatim if the conversation goes well:

> “Would you help us schedule one 45-minute workflow session with a designated football video/analytics owner and one designated soccer workflow owner, plus whoever approves media use? We would bring a draft of twelve queries per sport and a read-only, post-game shadow protocol. We are not asking for unrestricted archive access, external upload, publication, or live deployment.”

The successful meeting outcome is a named next conversation and permission to refine the evaluation contract. It is **not** a coach endorsement, data transfer, pilot authorization, or publication decision.
