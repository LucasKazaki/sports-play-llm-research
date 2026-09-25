# SportsPlayLLMResearch

## Current authority — September 22, 18:28 UTC

Stay within chess until [the no-forward commentary capability gate](research/chess-commentary-capability-gate-v1.md) is independently satisfied. A generator must never receive engine PV tails, post-move FENs, future moves/features, solution/theme or answer labels, annotations or evaluator-only material. The legacy forward-assisted prototype is not a no-forward candidate. Internal implementation and review use registered local agents and the native executor; do not activate cloud roles merely for activity. Professional-commentator claims and board-game expansion remain gated. Earlier soccer/transfer and assisted-generation directions below are historical where they conflict with this authority.


## Current direction — continuous chess-first improvement

The September 18 user correction makes chess the immediate research starting
point. Follow [the current autonomous research program](research/chess-autonomous-research-program-2026-09-18.md)
and `GOAL_WORK.json`; historical soccer/football results below remain intact.

There is now real data: 24 game-derived CC0 Lichess puzzles, 122 legally replayed
plies and a source-bound 8/8/8 train/development/test split. Local Stockfish 19
matched the published solution on all eight development puzzles at both 10,000
and 100,000 nodes. The eight test cases remain unscored. This is a small
convenience-sample engine baseline, not evidence of explanation quality or sports
understanding. The board text is explicitly deterministic and no model was called.

Start with [the data/provenance README](data/open/chess/lichess-real-seed-v1/README.md),
[the current chess research program](research/chess-autonomous-research-program-2026-09-18.md),
and [the intake restoration and acceptance correction](research/chess-intake-restoration-2026-09-22.md).
The baseline HTML and audit bundle are generated local evidence under `artifacts/` and are not part of the portable Git mirror.
The installed chess library and engine remove the historical dependency HOLD.
Continuous work now means improving measured real-data failures, grounded
explanations and useful interfaces, with successor experiments retained after
each verified unit. Company Runtime is the sole scheduler.

Research and prototyping workspace for `PlayGround`: evidence-grounded VLM analysis of real soccer broadcasts, from short event windows toward a searchable full-match event memory.

## Portable repository and model inventory

See [the portable repository and model inventory](research/portable-repository-assets-2026-09-25.md) for the cross-computer checkout boundary, reproducible backbone acquisition, and the local checkpoints that remain held by data-rights or model-output review gates.

For a new Windows checkout, install Python 3.11 and run `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1`. Then run `powershell -ExecutionPolicy Bypass -File .\scripts\portable-doctor.ps1` and `powershell -ExecutionPolicy Bypass -File .\scripts\reproduce.ps1`. Private SoccerNet data and generated model packages remain local and require their documented access or rights gates.

## Current research status — 2026-08-31

The searchable interface and its provenance trail are operational, but both
current sports lanes remain **SYSTEMS GO / SEMANTIC NO-GO**: a retrieved report
is an untrusted research candidate, not a verified play, player, or tactical
assessment. The private soccer development corpus has been independently
audited as 9 game groups / 18 halves / 13.9222 hours (91/91 metadata checks).
A separate, openly licensed SoccerTrack v2 integrity intake has passed
direct-source, media/BAS hash, acquisition-only decode, split, and
label-isolation checks. Match `117092` is an official training split; first
half `128057` is an official held-out test split but remains sealed and
unscored; second official held-out match `132831` is absent. The public lane is
therefore not an evaluation cohort and has made zero model calls. Its BAS
annotations remain post-hoc only and never enter model-shaped artifacts.

The next evidence-gated soccer protocol is frozen before inference: 40 fresh
held-out windows, blinded independent proposals, and a VLM-authored evidence
audit. It has made zero new model calls while fresh-cohort, history-overlap, and
privacy gates remain incomplete. The local Agent Studio loop has completed
bounded `openai/gpt-oss-20b` work with server-owned receipts; it does not need a
generic hosted worker. See [the current research status](research/2026-08-30-loop-frontier-status.md)
for exact gates, source boundaries, and current Studio caveats.

## Dual-sport verified long-form demo — 2026-08-28

PlayGround has one local interface for **Soccer** and **American football**. Double-click `START_DUAL_SPORT_DEMO.cmd` (or `START_COACH_SEARCH_UI.cmd`) and use the switch at `http://127.0.0.1:8771/`. Soccer mode now prefers the seal-verified SoccerMaster full-match package; Football mode prefers FootballMaster long-form v2. A local query LLM translates only the coach’s text into retrieval terms, deterministic BM25 ranks frozen VLM reports, and every result opens hash-checked local source footage with its claim boundary. If the verified SoccerMaster package cannot load, the server exposes the older soccer SQLite path only as an explicit `legacy_sqlite_fallback` rather than silently presenting it as the new result.

SoccerMaster’s frozen test covers both complete 45-minute halves with **90 contiguous 60-second dense windows** (45 per half, 60-second stride, eight ordered silent frames each) plus **six fixed 30/60/120-second stress windows** using 8/12/16 frames. All **96/96** test calls returned schema-valid reports on the first request, but that is a systems result, not evidence of correct soccer understanding. After the 1,874-file visual seal was closed, a restricted non-one-to-one ±6-second annotation corroboration matched only **3/166** mapped annotations and **3/54** mapped predictions; the six predeclared visual spot checks produced **0 supported, 2 partially supported, and 4 unsupported** judgments. The model produced no mapped offside or foul prediction against 3 and 19 corresponding annotations, and a sampled anonymization audit found readable team-name pixels outside the scoreboard mask. Soccer therefore remains **SYSTEMS GO / SEMANTIC NO-GO** and is not ready for autonomous coach use.

FootballMaster long-form v2 is football-only code, not a SoccerMaster port. Its source pool contains six real CC BY-SA long game programs totaling **20,265.7455 seconds (5.62937375 hours)**, split 3/1/2 by `game_id`. The frozen 69-window manifest totals **4,830 nominal window-seconds** but only **2,760 unique sampled seconds** after merging nested durations. The searchable test index covers **1,440 unique seconds** (2,520 nominal window-seconds) from two held-out source programs totaling 6,438.9325 seconds; it is not a dense entire-game index. A local `google/gemma-4-e4b` VLM receives eight ordered silent frames for deterministic 30/60/120-second windows. Audio, commentary, titles, filenames, team names, rosters, and labels are excluded. Prompt development used three games, locked label-free selection used one validation game, and the frozen test used 36 windows from two untouched games.

The systems path is reproducible, but the football semantics are **NO-GO**. The frozen test produced valid JSON for 35/36 windows, yet all 36 reports abstained; 27 simultaneously asserted events, and 126 `scoring` assignments across 21 windows lacked explicit scoring evidence. No human event labels exist, so event accuracy is not measured and `performance_claim_allowed=false`. The UI deliberately displays these failures. Its valid claim is that long-form silent VLM reports can be sealed, searched, and reviewed against real footage—not that the reported events are correct.

Current entry points:

- `START_DUAL_SPORT_DEMO.cmd` — one-click switchable Soccer/FootballMaster UI;
- `research/soccermaster-longform-technical-report-2026-08-27.md` — exact SoccerMaster protocol, timings, post-seal evaluation, direct visual spot checks, leakage audit, and safe claims;
- Local-only `artifacts/soccermaster-longform-v1/` — SoccerMaster protocol receipts, frozen queries, prediction seal, evaluation, spot checks, verification, and package receipt; the research report linked above records the portable method and safe claims;
- `prototype/soccer_longform_adapter.py` — soccer-only seal verifier, optional query-language expansion, deterministic BM25 retrieval, and private media binding;
- `research/footballmaster-longform-v2-technical-report-2026-08-28.md` — exact 144-call protocol, hashes, timings, held-out failures, post-seal ASR audit, demo choreography, and next experiment;
- Local-only `artifacts/footballmaster/longform-v2/` — prediction seal, raw responses/receipts, frozen index, query results, metrics, and verification;
- Local-only `artifacts/footballmaster/longform-v2-demo/` — desktop/mobile/search screenshots and demo/lifecycle receipts;
- `prototype/football_longform_adapter.py` — football-owned seal verifier, loopback query expansion, BM25 retrieval, and media binding;
- `prototype/multisport_search_demo_server.py` — loopback-only two-sport API, receipt validation, isolated ontologies, safe byte-range media serving, and per-field attribution;
- `data/public/footballmaster-v2/` — six verified programs, rights manifest, 3/1/2 split, and decode receipts;
- Local-only `artifacts/footballmaster/pilot-v1/` — legacy nine-window trained probe retained for fallback and historical comparison; its checkpoint remains held for a separate model-output rights review.

For UI or browser testing without using the query model, run `scripts/start-coach-search-ui.ps1 -LiteralQueryFallback`. The interface labels this mode; saved VLM reports and evidence remain identical. Normal presentation launch uses the live local query-model path.

Both current VLM report lanes are **SYSTEMS GO / SEMANTIC NO-GO**. The shared interface makes the distinction between working infrastructure and invalid sports semantics visible instead of flattening either result into a marketing claim.

## Searchable-match sprint — 2026-08-27

The project now has a VLM-only semantic path for detailed coaching reports rather than a single event label. `prototype/searchable_match_vlm.py` deterministically plans overlapping windows, samples and hashes silent frames, asks the local VLM for zero or multiple structured event cards, validates the evidence/identity contract, persists receipts under `data/private`, and indexes the VLM-produced text in a private SQLite full-text index. Windowing, validation, and retrieval never decide whether the play is a foul, offside, long ball, or other soccer event; all soccer-semantic fields come from the VLM.

A 2,700-second half plans as 108 gap-free 30-second windows at a 25-second stride. One authorized real 30-second SoccerNet window completed in 29.062 seconds and produced three indexed reports with detailed descriptions, participants, coaching relevance, two evidence timestamps, and uncertainty. The systems path works, but the report is semantically wrong: held-out labels show a penalty and goal, while Gemma described save/clearance and other confident events. The one-command search demo therefore prints an **UNADJUDICATED / hallucination warning** and must be presented as infrastructure plus a failure boundary—not as a correct coaching result.

The matched longer-window probe reinforces that boundary. Direct 20-, 30-, and 60-second requests all completed with schema-valid reports in 14.749, 9.779, and 28.315 seconds, but strict timestamp-aligned recovery was 0/2, 0/2, and 0/4. Six denser 10-second requests over the same minute also scored 0/4 and took 204.157 seconds. Fluent JSON is not soccer understanding; current evidence supports a human-auditable research pipeline, not autonomous coaching use.

Meeting-ready entry points:

- `presentation/PlayGround-Searchable-Full-Match-VLM-Archit-2026-08-27.pptx` — 20-slide technical deck with beginner-friendly speaker notes on every slide;
- `START_PRESENTATION.cmd` — no-install browser slideshow updated to the same 20 slides;
- `START_COACH_SEARCH_UI.cmd` — current one-click dual-sport browser UI at `http://127.0.0.1:8771/`; Soccer mode preserves this saved-report/audit demonstration while Football mode loads the trained pilot package;
- `START_SEARCH_DEMO.cmd` — double-click wrapper for the verified private search/failure demo;
- `powershell -ExecutionPolicy Bypass -File scripts/demo-searchable-coaching.ps1` — terminal form of the same demo;
- `START_LIVE_DEMO.cmd` — verified saved ten-second visual/audio demonstration at `http://127.0.0.1:8765/`;
- `research/archit-demo-talk-track.md` — slide narration, two live demos, PhD-level questions, and plain-English terminology;
- `research/long-clip-detailed-vlm-probe-2026-08-27.md` — exact 20/30/60-second and dense-window evidence, receipts, failures, and safe claim;
- `prototype/searchable_match_vlm.py` — full-half planner, strict VLM report contract, resumable indexer, and exact-token search;
- `prototype/search_demo_server.py` — original soccer-only implementation, now reused by `prototype/multisport_search_demo_server.py` for the sealed soccer context and query-model adapter;
- `tests/test_searchable_match_vlm.py` — planner, schema, privacy, identity, search, and resume tests.

The browser UI intentionally leads with **SYSTEMS GO / SEMANTIC NO-GO**. Its one saved 30-second report is unadjudicated and factually wrong against the held-out SoccerNet penalty/shot-on-target/goal annotations. Those annotations are loaded only for the post-hoc audit panel and are never included in either the visual-model input or the query-LLM prompt. Double-click `START_COACH_SEARCH_UI.cmd`, enter a coaching question, inspect the LLM's plan and latency, then use **Play evidence** or an evidence timestamp to seek the private local clip. The review derivative is silent H.264/MP4 and is never uploaded.

## Real-footage milestone — 2026-08-27

The presentation path now runs on **authorized, non-redistributable SoccerNet broadcast footage mapped to SoccerDB**, not on the old artificial clips. A bounded one-match development split (5 clips) and a match-disjoint one-match comparison set (6 clips) were cut into physically silent 10-second inputs, hash-bound to the public SoccerDB mapping, and evaluated locally. The implemented task is closed-set **event-window classification from sampled stills**, not full-match action spotting or temporal localization.

The untouched Gemma primary pass is preserved exactly: 3/6 requests completed, requested-set schema validity was 3/6, allowed-window accuracy was 1/6, and all three remaining requests timed out. A post-hoc **serving-recovery rerun on those same clips** used a directly owned, hash-pinned `llama.cpp` runtime: 6/6 completed with 9.306 s median latency, but allowed-window accuracy was 0/6. The runtime repair is a systems diagnostic, not an independent performance estimate.

After the Gemma results were known, a local `qwen/qwen3.5-9b` comparison completed 6/6 requests, matched an allowed mapped label in 3/6 windows, and was exact on 1/2 single-label windows, with 9.9925 s median latency. It used the same 72 decoded frames but six two-frame sheets instead of Gemma's twelve one-frame sheets after the twelve-image Qwen request exceeded the fixed context. Model selection was post hoc and the representation changed with it, so this is a hypothesis-generating engineering comparison—not a benchmark or causal model ranking.

Commentary was never provided to either visual model. After sealing each visual summary, a separate text-only consistency probe inspected SoccerNet-Echoes ASR. For the Qwen run it completed 6/6 with 2 label-equality supports and 4 contradictions; for canonical Gemma recovery it produced 2 supports, 2 contradictions, and 2 uninformative cases. The probe is non-intervening but not statistically independent: it describes the same broadcast event, uses a noisy transcript, and never changes the visual prediction.

Start with:

- `START_PRESENTATION.cmd` — no-install local browser slideshow; Space/arrows navigate and `F` enters full screen;
- `START_LIVE_DEMO.cmd` — double-click launcher for the verified loopback demo at `http://127.0.0.1:8765/`;
- `presentation/PlayGround-Real-Soccer-VLM-Archit-Research-Ready-2026-08-27.pptx` — final 16-slide technical deck with Dr. Tica Lin's work, adjacent soccer-VLM research, and a gated school-year program;
- `research/archit-demo-talk-track.md` — slide-by-slide script, live-demo choreography, and technical Q&A;
- `research/dr-tica-lin-and-soccer-vlm-research-2026-08-27.md` — claim-level primary-source synthesis and research roadmap;
- `research/soccernet-real-footage-pilot-2026-08-27.md` — canonical evidence report and claim boundaries;
- `research/phd-methodology-audit-2026-08-27.md` — adversarial methodological audit;
- `data/private/demo-soccernet-valid-qwen35-comparison-v1/index.html` — private loopback/offline live demo;
- Local-only `artifacts/soccernet-pilot-v1/` — frozen configs, runtime receipts, summaries, seals, and provenance bindings.

No model weights were fine-tuned. The development match was used for prompt/schema/runtime/model engineering; the Gemma primary pass alone is an untouched first pass. Gemma recovery and Qwen comparison are labeled post hoc throughout. With six selected windows from one match, no grounding adjudication, no negative windows, and a model-by-representation confound, the results support only case-level feasibility and failure analysis.

## Prior literature and prototype context (through 2026-08-25)

Before the real-footage milestone above, the 2026-08-09 TreeSoc, X-VARS / SoccerNet-XFoul, and SoccerChat branches were integrated as bounded near-neighbors. TreeSoc is verified soccer VQA with tool-derived internal field context and answer accuracy, not an established separately submitted answer-linked soccer-field-coordinate/trajectory scoring match; X-VARS is a semantic refereeing-VQA/explanation near-neighbor with the same field-evidence boundary; SoccerChat is short soccer-video QA/referee/action understanding without an established separately submitted answer-linked field payload or external field-payload scoring. See `research/evidence-ledger.md` E-017/E-018/E-019 and `research/decision-log.md` D-018/D-019/D-020; the immutable packets are under `artifacts/answer-conditioned-field-treesoc-branch-audit-2026-08-09/`, `artifacts/answer-conditioned-field-branch-audit-2026-08-09/`, and `artifacts/answer-conditioned-field-soccerchat-branch-audit-2026-08-09/`.

Iteration 48 verified SportD as a distinct value-grounded strategic-choice frontier: closed soccer action selection evaluated with possession-value and regret, not answer-only QA (source verifier PASS; project suite 23 passed). It does not replace the working PlayGround target: fine-grained soccer-play QA with externally scored answer-linked **sports-field** coordinates/trajectories, evidence-validity-aware calibrated abstention, and controlled direct-versus-tool evaluation under one contract. Those pitch-calibrated and supporting-versus-contradicting evidence fields are proposed extensions beyond the narrower implemented v1 schema, which currently carries one unlabeled interval, string-array spatial evidence, and normalized broadcast-image trajectory points. SportD's paper license does not establish broadcast/data rights; no SportD data or media was acquired. This remains a literature-grounded hypothesis, not a novelty guarantee. The one Wikimedia pilot item remains ineligible pending independent review, calibration, a second annotator, and adjudication; no model-performance claim has been made.

## Earlier presentation audit — 2026-08-25

At that point, the project was ready only as a methods-and-progress study. The audited presentation brief in `research/presentation-brief-2026-08-25.md` reconciles the strongest primary-source comparisons, records current-version SportD figures, distinguishes published findings from local structural checks, and makes the then-remaining empirical milestone explicit. Its `realDataExperimentResults=null` status is historical and is superseded by the bounded 2026-08-27 SoccerNet feasibility result above; the new result is still not benchmark-eligible.

## Research question

Can a tool-augmented VLM produce more faithful fine-grained answers than a direct video-VLM while citing temporal and spatial evidence and abstaining when the available evidence is insufficient?

## Evidence policy

Facts, hypotheses, synthetic experiments, and real-data experiments must be labeled separately. Restricted data is not acquired without explicit approval. Claim-level sources and caveats are maintained in `research/evidence-ledger.md`.


## SoccerRAG bounded near-neighbor

Iteration 54 integrates SoccerRAG as a QA-accepted retrieval/database semantic-question-and-answer near-neighbor, not an answer-linked soccer-field evidence match. See E-020 and D-021; exact matches remain zero.

## Batch-2 citation-neighborhood update

Iteration 55 integrates QA-accepted SoccerMaster / Soccer Factory, MatchTime, and UniSoccer / SoccerReplay-1988 as selected bounded citation neighbors. Their immutable primary artifacts establish soccer semantic/model, commentary-temporal-alignment, and soccer-understanding/replay-adjacent components, respectively; none establishes the joint contract of a semantic soccer-play question and answer plus a separately submitted answer-linked pitch-coordinate/region/trajectory payload with external scoring. Preserve `BOUNDED_NEGATIVE_WITH_CITATION_NEIGHBORS`; this is not a global absence, novelty, rights, or acquisition determination.

## Iteration 56 — online frontier update and first local VLM execution

The 2026-08-21 living primary-source scan adds E-VQA / ST-Evidence, SportsTime / CoTR, TimeLens2, and GroundFormer as material predecessors and adds a same-clip question-invariance requirement. In parallel, a real loopback-only `zai-org/glm-4.6v-flash` direct/source-assisted smoke executed on the hash-bound 8.008-second CC BY 2.0 pilot, exposed and repaired the structured-output adapter contract, passed 27/27 packet checks, and left all 25 project tests passing. The run is interface evidence only: it does not authorize accuracy, grounding, calibration, latency, coach-utility, generalization, tool-benefit, or novelty claims. Next is an independently annotated multi-question same-clip and causal-corruption test with abstention.

## Iteration 57 — hard negatives, commentary alignment, and project consolidation

The online lane added a bounded coaching-document/fine-grained-retrieval scan plus NA-VMR, MVMR, and MCAD. It identifies Soccer-GMR-style null-set/multi-moment retrieval as the semantic baseline, commentary/timestamped event records as document-evidence inputs, and trajectory-aware reranking as an untested hypothesis. The local lane executed an intentionally corrupted-evidence probe and two same-clip hard-negative/null-query requests on the admitted pilot; fresh packet verification passed 24/24 and 43/43, and the project suite passed 25 tests. These are structural observations only—no model-performance or novelty claim is authorized, and `realDataExperimentResults` remains null.

The former Agent Studio `soccer-research` project is now consolidated here. Its useful synthetic annotation and fixed-prompt methodology fixtures are preserved byte-for-byte under local-only `artifacts/legacy-soccer-methodology-import-2026-08-22/`; both validators pass. The duplicate project can remain archived, with this workspace serving as the sole canonical soccer-research project.
