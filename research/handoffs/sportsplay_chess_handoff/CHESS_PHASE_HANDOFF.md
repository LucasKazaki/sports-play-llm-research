# SportsPlay Chess Phase
## Implementation, evaluation, and presentation handoff

**Version:** 1.0. **Audience:** the project owner and every registered `sports-play-llm` agent. **Visibility:** internal only. **Status:** an implementation plan, not a claim that the chess system or its experiments already exist.

Use the SportsPlay Internal Research Hub for current decisions and verified progress. Use this handoff as the versioned technical protocol. Do not publish either document or link them from the Archit update. Source labels S01-S20 identify the primary references at the end. All dataset sizes, budgets, thresholds, paths, APIs, and task identifiers below are proposed project defaults unless explicitly described as an existing external capability.

## 1. Decision and intended outcome

Build chess as the first complete controlled phase of the broader sports-review project. Do not require a Connect Four implementation first. Preserve the soccer code, prior results, evaluation splits, and permission records; introduce a chess module or isolated worktree rather than replacing the project. Basketball, American football, and soccer remain possible later applications, not claims supported by this phase.

The application should import a completed chess game, reconstruct every position, identify review-worthy decisions, explain alternatives with inspectable evidence, answer questions about the game, and generate practice around supported mistakes. It should also process controlled board images and generated replay video in a separate condition, allowing the project to measure the cost of imperfect observations.

The central research question is: **How much do exact state, chess-analysis tools, and explicit claim checks improve the factuality and usefulness of local-model coaching, and what fails when the state must instead be recovered from images or replay?**

Chess engines and language-based chess commentary are established work. Engine-assisted commentary was studied by Lee and colleagues, and ACT-Eval studies atomic-claim checking and conceptual coverage. Do not claim that connecting an LLM to Stockfish, or checking sentences individually, is itself new. Candidate contributions are a reproducible local pipeline, controlled state-to-vision comparisons, uncertainty propagation, and a searchable review interface whose explanations link to exact positions and analysis. Confirm any novelty claim against the literature before writing it. [S14, S15]

### Final chess-phase deliverable

Deliver one local application, one reproducible evaluation package, and one evidence-backed report and presentation. The application must support exact-state review and a controlled visual/replay path. The evaluation must distinguish software health, state reconstruction, move-analysis agreement, explanation factuality, retrieval, and any human learning results.

Completing the research phase does not require every hypothesis to be positive. A failed visual condition or a weak LLM result is a valid research outcome when the implementation, test protocol, failures, and limitations are reported. However, do not call a component product-ready when its acceptance gate fails.

### Explicit exclusions

Do not build a chess engine, train a foundation model, or scrape a paid coaching corpus. Do not add live human-game assistance, automated moves on Chess.com, public deployment, physical-board camera support, speech synthesis, or real sports-footage ingestion to the required chess deliverable. These additions would obscure the core experiment. Formal participant recruitment, paid services, public release, and broader data permissions remain separate owner decisions.

## 2. Existing context and missing local evidence

The project materials reviewed in chat describe an early soccer-video-to-notes-to-search workflow and acknowledge incorrect soccer descriptions. They do not establish a validated coach. The earlier real-footage pilot was small and selected around known events; it cannot become a general soccer benchmark by being included in this report. SoccerMaster integration remains unverified in the current project narrative.

The chat cannot currently inspect the AI PC, current source checkout, active agent roster, database, or raw test receipts. Older Agent Studio handoffs described task-admission and workspace problems, but those must be checked locally rather than assumed current. An earlier exported restart note reported passing software checks; it was absent from the latest native read of the collaborator document. Do not use historical counts as fresh evidence.

C00 must establish the actual project root, repository and branch, commit, dirty files, active tasks, relevant model endpoints, available CPU/RAM/VRAM, and the owner-authorized execution recipes. Protect unrelated files. Do not assume a path from another project or create a second scheduler because the existing route is unfamiliar.

## 3. Internal document access and maintenance

### Two document audiences

The Internal Research Hub and this handoff are private working resources. The Archit update is a separate, conversational explanation of the direction. It must not become a mirror of internal agent logs, private links, test labels, participant information, or credentials.

All registered soccer-project agents need access to this plan, but they do not all need access to protected final-test answers. Use the project's actual registered agent identities. Logical roles below are job descriptions, not newly invented agent accounts.

### Bootstrap access contract

1. Resolve an already authorized Drive connection using the owner's identity. Verify that the hub and handoff can be read without changing their sharing. The current owner account is `kazakitao@gmail.com`; this is an access identity, not a credential to copy.
2. If the runtime has no suitable Drive read route, ingest the supplied bundle into the actual project workspace and expose a read-only shared context mirror to project agents. The local mirror is an explicitly versioned copy, not a new independent source of truth.
3. Register `sportsplay.research.hub` and `sportsplay.chess.handoff` in the existing context/resource registry. Record the canonical URLs, document revision, mirror hash, visibility, and refresh status. Use the supplied `project-context.json` as a proposed manifest, adapting its keys to the real runtime instead of assuming a ready-made API.
4. Enumerate all active agents attached to `sports-play-llm`. Each must read the resources and return an access receipt with its actual agent ID, document identities, version, content hash, and three task-relevant requirements. A failed read is not a successful enrollment.
5. Add the same read test to future agent enrollment. Access readiness requires receipts for the complete current roster or named, owner-visible exceptions.
6. Keep Google Docs restricted. Never use anyone-with-the-link sharing, a domain grant, guessed service-account addresses, exposed local ports, or copied browser cookies to make the access test pass.

### Editing and synchronization

Use one documentation coordinator as the normal writer. Workers submit append-only update proposals with task IDs and artifact references. The coordinator reads the live revision, reconciles changes, writes only supported updates, and refreshes the local mirror atomically. A changed instruction version invalidates stale task-start acknowledgments where the change affects scope or acceptance.

Source code and execution artifacts establish implementation state; a document summary cannot overrule them. Preserve proposed, reported, executed, and independently checked status distinctions. New evidence can justify an update; repeated agent discussion cannot. No evidence means no progress claim.

The chat-level maintenance task may review connected project evidence daily and update the hub when something material changes. It must not infer local progress, weaken frozen protocols, edit the Archit document, change permissions, or start local jobs. Local agents should update after accepted work and before a milestone review, not wait for the chat-level check.

## 4. What counts as ground truth

Do not use one undifferentiated label called ground truth. Store the reference type with every answer and metric.

**Rule truth.** Given a valid complete state and the declared rules, piece locations, side to move, legal actions, actual moves, check, and terminal conditions can be checked by a rules library. A valid-looking FEN alone does not prove reachability from a legal game history. Use replayed game histories where possible. [S03]

**Exact endgame reference.** Use locally available Syzygy tables for covered positions and the supported rules. Preserve the raw five-valued WDL result, DTZ, side-to-move convention, halfmove clock, and coverage status. Castling rights and missing successor tables can make a query unsupported. Do not collapse cursed wins or blessed losses into unconditional wins/losses. DTZ is not distance to mate. A rule-aware adapter must distinguish the table's result from the game's actual claimable/automatic draw status. [S05]

**Engine reference.** Use a pinned Stockfish build for general positions. Store its analysis budget and configuration. Scores and proposed continuations are strong reference estimates, not a proof that every alternative was exhausted. Depth is not a guarantee of exhaustive search. Stockfish's WDL estimates are not a beginner's personal probability of winning. [S01, S02]

**Platform comparison.** Use Chess.com Analysis and Game Review on completed, authorized games as an external comparison and a usability reference. Its evaluations and move classifications can change with analysis settings or deeper review. Its explanations are not an infallible target, and engine overlap means agreement with local Stockfish is not fully independent corroboration. [S08, S09, S10]

**Human judgment.** Chess-competent reviewers assess whether an explanation captures the relevant idea and communicates it appropriately. Actual learning claims require a learner study. Reviewers can disagree; keep independent ratings, adjudication, and uncertainty rather than inventing consensus.

The system should expose labels such as `rule_verified`, `tablebase_supported`, `engine_supported`, `human_reviewed`, `uncertain`, and `unsupported`. These are provenance categories, not confidence percentages.

## 5. Reuse existing resources

### Required core

Use **Stockfish 19**, the stable release identified during this research, as the initial engine candidate. Download from the official project and record the exact binary, source tag, checksum, architecture, and network identity. A later version requires a new reference-analysis version, not a silent dependency update. Stockfish is a UCI engine, not a graphical interface. [S01]

Use **python-chess**, installed as the `chess` Python package, for state handling, PGN parsing, UCI communication, and tablebase access. Pin the exact resolved release and test it in the project's actual Python environment. It supplies these facilities already; agents should implement adapters and tests rather than reimplement chess legality. [S03, S04, S05, S06, S17]

Use **Syzygy** only for selected material classes needed by the benchmark. Begin with a small set of positions with at most five pieces including kings, and download the transitive table coverage required for their legal successors. Inventory coverage first. A full seven-piece download is not part of this project. [S05]

Use **Lichess database exports** for a reproducible, openly licensed starting corpus. The exports are CC0. Existing evaluation records have mixed depths and settings, so use them as discovery material and rerun the final selected positions with the pinned local reference. For puzzles, apply the first listed move to the supplied FEN before treating the next move as the solver's move. Preserve that distinction in importer tests. [S07]

### Chess.com use

Use manually supplied PGNs first, then the documented PubAPI for approved public completed-game archives when needed. It is read-only and is not a supported Game Review automation endpoint. Prefer serial requests, cache responses and headers, identify the client, and honor rate-limit responses. Download only the small corpus required by the frozen manifest. [S11]

Use a manually reviewed sample of 30 position-move pairs for Chess.com cross-checks. Record the platform, selected engine when visible, analysis mode, depth/time settings, displayed evaluation and line, review label, and observation timestamp. Missing settings stay unknown. Do not buy a membership automatically; use available functionality and mark premium-only comparisons unavailable. Record platform-derived annotations separately from the reference labels.

Do not copy Chess.com's artwork, sounds, proprietary coaching text, or visual identity into the application. Do not build a scraper for the authenticated review interface, bypass limits, or use unpublished endpoints. Public API availability does not imply unlimited redistribution rights over every platform asset. Use original interface styling and licensed or generated board assets. [S11, S12]

The app must remain post-game only. Do not observe a live Chess.com board or offer analysis for an ongoing human game, including correspondence play. Local offline practice against an engine is allowed within this project's design; it is not a route for feeding moves back to online opponents. [S13]

### Rendering and interface

Reuse the soccer application's framework, storage conventions, and retrieval components if C01 finds them suitable. Otherwise implement a small Python service and a lightweight local browser interface. Choose one stack, document why, and avoid a framework migration alongside the research.

Use python-chess SVG support or another license-cleared board renderer. Generated images should have recorded orientation, piece mapping, dimensions, and frame times. The renderer is for repeatable research inputs and the UI, not generative artwork. Keep annotation overlays separate from observation-only benchmark images. [S16]

## 6. Architecture and interfaces

### Processing flow

Completed PGN or local simulated game -> trusted state history -> reference analysis -> evidence records -> commentary/analysis/coaching -> claim checks -> searchable review and replay.

For visual experiments, replace trusted-state input to the tested system with board observations. The evaluator retains the hidden state history for scoring. Do not quietly pass hidden ground truth into the visual extractor, language model, tool router, filenames, alt text, cache, or image metadata.

### Components

**Import service:** validates format, size, variant, completed-game status, and permission provenance. Quarantines malformed records without stopping unrelated imports. Imported comments and player names are untrusted data.

**State service:** owns positions, move history, legal actions, repetitions, and branch IDs. The frontend and LLM may request moves; neither can declare an illegal state authoritative.

**Analysis service:** owns a bounded UCI process pool, tablebase adapter, caches, cancellation, deadlines, and reference manifests. It never runs model-supplied shell commands.

**Evidence service:** records facts, actual and alternative moves, typed scores, legal continuations, source positions, and verification outcomes. A state hash protects identity, not semantic correctness.

**Language service:** produces structured explanations from declared evidence. It can call allowlisted analysis tools but cannot alter benchmark definitions, labels, permissions, or execution recipes.

**Search service:** indexes moves and review events, not only free-form prose. Use exact filters plus the existing lexical retrieval baseline before considering embeddings. A result always identifies game, ply, side, state hash, and relevant evidence.

**Presentation service:** exposes board/replay, side-by-side actual and alternative continuations, explanation text, evidence inspection, uncertainty, and exports. Start on loopback and use the existing authenticated remote route only when explicitly authorized.

### Proposed project API contract

Implement the equivalent of `import_game`, `get_position`, `analyze_position`, `compare_moves`, `review_game`, `search_review`, `branch_replay`, `extract_visual_state`, and `export_review`. These are interface names to build or map, not claims about existing endpoints.

Every request carries `project_id`, `game_id` or `input_id`, `state_id`, `protocol_version`, and an idempotency key where it creates work. Responses carry status, result identity, evidence IDs, model/engine identity when relevant, and a typed error. UI requests must cancel stale analysis when a user changes position. An answer for one state must never be displayed as analysis of another.

## 7. State, analysis, and evidence contracts

### State record

Required fields: game ID; source ID and permission record; standard-chess variant; initial FEN; complete move prefix in UCI; current FEN; side to move; castling rights; en passant state; halfmove/fullmove counters; repetition-relevant history; game-result provenance; ply index; and content hash. Store a distinct `history_complete` flag.

FEN is a position format, not a complete record of repetition history. A screenshot does not reveal all rule-relevant information either. When history is unavailable, support only claims justified by the available information and mark draw-history conclusions uncertain. [S03, S04]

Use separate keys for analysis identity and leakage grouping. Analysis identity includes rule-relevant history and configuration. Leakage grouping also detects near-duplicate positions and shared parent games. Do not use a shortened board hash as the sole key for both purposes.

### Analysis record

Record engine name/version, binary/network checksum, UCI options, node/time limits, requested root moves, returned depth, nodes, time, typed score, score perspective, principal variation, tablebase hits, and failure state. Store raw output alongside normalized records. A timeout is not a zero evaluation.

Starter reference configuration: one engine thread, 256 MiB hash, full strength, no pondering, no opening book, and a fresh or explicitly cleared engine state for independent cases. These are proposed reproducibility defaults, not optimal hardware settings. Stockfish analysis runs on CPU, leaving the GPU for language/vision inference. [S02]

Use a 2,000,000-node MultiPV discovery run to propose up to three alternatives, then evaluate each reported candidate and the actual move with separate 2,000,000-node root-restricted runs. Include any model-proposed alternative in the same fixed scoring procedure. Raise unstable or disputed cases to an 8,000,000-node adjudication budget. Freeze this policy on validation before final testing.

MultiPV is a candidate-discovery aid, not proof that all equally good moves have been listed. For acceptable-move metrics, evaluate any proposed legal move under the same reference policy, rather than rejecting it simply because it was outside the initial top three. [S18]

Normalize every comparison to the player who was to move before the actual move. Preserve the native score type: centipawn, mate, or tablebase. Never subtract a mate score from a centipawn score. Distinguish an engine-reported mating line from an independently exhaustive mate proof.

For finite centipawn comparisons, proposed near-equivalence tolerance is 25 cp. A 100 cp reference drop is a review-candidate heuristic, not a universal blunder definition or a Chess.com label. Preserve the raw signed difference. A negative difference beyond tolerance triggers reference adjudication, not silent clipping; small differences should be described as close. Verify that displayed 'cp' scores are ordinary finite evaluations, not encoded tablebase signals.

### Explanation record

Store question, audience setting, evidence IDs, game/ply/state identity, actual move, alternatives, explanation mode, factual assertions, teaching point, optional exercise, model identity, prompt hash, tool trace, timestamps, and verification results. Separate what happened, what the engine recommends, what the explanation infers, and what remains uncertain.

Each assertion includes exact text span, proposition type, entities/squares, time or branch scope, supporting evidence, checker identity, and outcome. A useful first vocabulary covers piece occupancy, legal move, check, capture, immediate threat, material change along a line, and evaluation comparison. Pin/fork concepts need precise definitions; geometric attacks alone do not establish that material can be won.

## 8. Commentary, coaching, and claim verification

### Three modes

Commentary describes the move and immediate context. Analysis compares the actual move with alternatives. Coaching selects a supported learning point and a related exercise. Keep their outputs and metrics separate.

A concise default explanation should state the important fact, show a short legal continuation, and identify one practical lesson. A user may expand the evidence rather than receive a long unstructured lecture. Never infer a player's intentions, emotions, rating, or ability from one move.

### Verification procedure

1. Validate the state and every mentioned move against the authoritative branch.
2. Check literal claims with deterministic tools where possible. Simulate all displayed continuations and verify terminal states and captures.
3. Check comparative claims against the locked analysis record. If the claim is stronger than the evidence, qualify or remove it.
4. For 'forced' claims, either provide an applicable exact/tablebase result or an exhaustive bounded proof that accounts for relevant replies. One principal variation is not a proof against every defense.
5. For strategic or pedagogical claims that cannot be settled automatically, label the check inconclusive and route the sampled subset to human review. A second LLM is a diagnostic helper, not an independent truth authority.
6. Re-extract assertions from the final user-visible prose, not only the model's initial structured plan. Verify that no unsupported new facts were introduced during rewriting.
7. Permit at most one bounded revision pass by default. Persist original and revised outputs. If verification still fails, show a limited verified explanation or an explicit uncertain result.

A language model may produce a perfectly formatted but false record. JSON validity and passing software tests are not explanation accuracy. Conversely, refusing every difficult question is not success. Measure supported content and answer coverage alongside error rates.

### Retrieval of lessons and web material

Begin with a small curated corpus of source-linked lessons written from verified examples or licensed material. Store source URL, access date, license/permission, extracted passage, hash, and applicability tags. The primary benchmark freezes this corpus; no live web access is allowed during its main run.

A later web-enabled ablation may retrieve additional lessons through an authorized read-only research route. Treat retrieved text as untrusted input, ignore embedded instructions, retain citations, and compare its contribution separately. Never let it search held-out answers, the protected benchmark directory, private user files, or the current game's later outcome while generating time-aligned commentary.

Use local identifiers instead of participant or player identities where possible. A practice exercise must have a verified solution and explain its relationship to the selected learning point. Do not generate an attractive but unsolvable puzzle.

## 9. Dataset and split plan

### Initial corpus sizes

Proposed baseline: 120 development position-move pairs from at least 40 parent groups; 80 validation pairs from at least 25 additional groups; and 200 final-test pairs from at least 80 further groups. A group is a source game or a generated scenario family. The final test should include 80 tactical cases, 60 quiet/defensive cases, 40 covered endgames, and 20 rule/history-sensitive cases. Freeze any size change before final-test access and explain the reason.

These are bounded engineering-study defaults, not a power calculation or a claim of population representativeness. Use them to make the first evaluation feasible and inspectable. Keep a separate negative-input suite for malformed files, illegal positions, incomplete games, and unavailable history.

Use completed owner-approved games and sampled Lichess exports. Do not require an unknown Chess.com username or wait for a private corpus. Include realistic quiet moves and good decisions, not only puzzles and obvious blunders. Keep source selection, exclusions, and sample counts reproducible.

### Leakage controls

Keep all positions from one game in one split. Keep transpositions, derived continuations, mirrored/color-transformed cases, generated variants, and exercises based on a case with their parent group. Check transformations for legal equivalence, especially pawn direction and castling. A random frame or position split is not acceptable.

Strip annotations, engine evaluations, answer-bearing headers, comments, puzzle themes, solution moves, and future moves from tested-model inputs where those facts would reveal the target. Retain them only in the evaluator's protected records. Image filenames, alt text, tool caches, prompts, and search indexes must not leak labels.

New legal rollouts and unfamiliar positions can reduce obvious memorization, but they do not prove absence of pretraining contamination. Document source exposure risk. ACT-Eval can be used as a separately reported external benchmark after its data and license are checked; never mix it silently into the custom held-out set. [S15]

### Protected evaluator

Only the benchmark curator/verifier receives final labels and hidden state sidecars. Builder agents see specifications, development data, and permitted validation feedback. Freeze the final manifest, evaluator code, prompt versions, model configurations, reference-analysis settings, and retrieval collection before opening final evaluation. Store hashes and access history.

No final-test repair loop is allowed. A bug found after unsealing must be disclosed; reruns are labeled exploratory or use a genuinely new holdout. Preserve failed runs and original artifacts.

## 10. Controlled images and replay experiments

Generate observations from the same legal game histories used in the exact-state experiment. Start with 200 test positions under four predeclared conditions: clean familiar board, held-out piece/board appearance, changed orientation or moderate geometric/compression perturbation, and partial occlusion. This gives 800 observations, not 800 independent games.

Create 40 held-out replay clips from at least 20 parent groups, each with a known starting state and a short legal move sequence. Record frame timing, animation intervals, dropped-frame settings, orientation, and hidden state alignment. Parent groups remain disjoint from development and validation.

### Observation regimes

**Known-start replay:** supply the starting state and subsequent frames; hide the move list. The task is legal sequence recovery and uncertainty handling.

**Screenshot-only:** supply the board image and only the explicitly declared metadata. Score piece placement separately from complete-state inference. Do not infer castling or repetition history from pixels. If side to move is withheld, a full legal state may be ambiguous.

Keep a simple renderer-specific image parser or template-matching baseline alongside the VLM extractor. Do not ask a VLM to infer tactics before the state service validates its interpretation. If multiple legal states fit, retain alternatives or abstain; do not quietly snap to the engine's preferred position.

Evaluate perception-only outputs first, then end-to-end coaching from the recovered state. Also run the identical downstream pipeline with oracle state to isolate propagation of perception error. Hidden-state evaluation must be isolated from production tool routes and caches.

Do not claim physical-board or broadcast-video performance from generated 2D replays. Unknown appearance, occlusions, and frame gaps test controlled variation, not every real-world camera condition.

## 11. Experimental conditions and metrics

### Required comparison conditions

A0: rules, reference analysis, and fixed explanation templates, with no LLM.

A1: a local language model given exact state/history but no engine tools.

A2: the same language model given exact state/history and allowlisted engine tools.

A3: the same A2 system with the final-prose verification and bounded revision procedure.

V2 and V3: the corresponding tool-assisted and verified systems operating on recovered visual state instead of oracle state. Keep the extractor and images fixed between V2 and V3. Report the simple image-parser baseline separately.

Compare a second local model only after the primary ablation is frozen. Hold prompts, representation, allowed tools, evidence budget, retrieval source, and generation limits fixed where possible; document unavoidable differences. Temperature zero does not establish complete determinism. Repeated runs measure variation; they must not become best-of-N selection.

### Primary and secondary outcomes

**Primary:** final user-visible factual-assertion error rate, paired A3 versus A2, with answer coverage and supported-idea coverage reported alongside it. Count false and unsupported assertions separately as well as in a declared combined error measure.

**Rule and reference checks:** illegal recommendation rate; legal continuation rate; exact tablebase outcome preservation on the covered subset; and bounded-engine acceptable-move agreement on general positions. Do not label engine agreement mathematical correctness.

**Coverage:** answered-question rate; supported assertions per response; fraction of adjudicated required ideas included; incomplete or empty response rate; and abstention behavior on ambiguous inputs. An empty answer cannot receive a perfect factuality score by dividing zero errors by zero claims.

**Perception:** square-level accuracy, full piece-placement exact match, side-to-move accuracy when observable, legal-state validity, complete-state coverage, sequence exact match, and first divergence ply. Full-state claims require the metadata/history needed to establish them.

**Retrieval:** Recall@5 and reciprocal rank against a frozen set of relevant game-ply IDs for 60 held-out questions, including questions with no valid match. Score semantic correctness of the cited event separately from opening the right file.

**Usefulness and performance:** reviewer helpfulness and clarity, task completion time, p50/p95 end-to-end latency, timeouts, model/tool calls, tokens, CPU/RAM/VRAM peaks, and cache-cold versus cache-warm results. Distinguish precomputed review latency from fresh analysis latency.

### Analysis procedure

Use the game/scenario family as the statistical cluster, not each frame or sentence as an independent observation. Use paired comparisons on the same cases, with a proposed 2,000-resample cluster bootstrap for confidence intervals. Keep repeated model runs nested within their case. Predeclare one primary contrast; label the remaining comparisons exploratory or apply a declared multiple-comparison method.

Report both case-weighted and assertion-weighted factuality so verbose outputs cannot dominate without disclosure. Show effect sizes, denominators, confidence intervals, and missingness. Do not infer significance from overlapping or non-overlapping interval plots alone. Include all requested cases, serving failures, invalid outputs, and rejected answers in completion metrics.

Numerical results start as NOT RUN. No agent may generate plausible scores to complete a table or presentation.

## 12. Acceptance gates and failure policy

The following thresholds are proposed project acceptance criteria, not measured results or universal research standards. Calibrate feasibility on development/validation, then freeze them before final testing.

**G0, access and scope:** the actual workspace and project identity are verified; every registered project agent can read the private plan; protected soccer artifacts have a baseline manifest; no new public sharing exists.

**G1, chess core:** every required deterministic legality/history/import fixture passes. All displayed continuations replay legally. Any unsupported variant or incomplete-history condition has an explicit response.

**G2, references:** every benchmark case has a valid reference type or an explicit unsupported reason. Tablebase coverage and draw semantics pass targeted tests. General engine analyses have pinned identity and reproducible budgets. No missing score is silently filled.

**G3, demonstrator:** one completed game supports import, review, search, evidence inspection, alternative replay, and export without a language model. The same flow then works with the language model enabled. Cache and network failures cannot corrupt the saved game.

**G4, explanation quality:** target at most 5% combined false/unsupported assertions on adjudicable claims, with at least 80% answer coverage on answerable cases and at least 70% adjudicated idea coverage. Report intervals and judge agreement. A failed threshold is reported, not hidden by narrowing the denominator.

**G5, visual condition:** target at least 95% full piece-placement exact match on the clean held-out condition. Report degraded conditions separately without requiring an artificial success threshold. Ambiguous state must not produce confident unsupported history. End-to-end results must show the oracle-state comparison.

**G6, search and operation:** target Recall@5 of at least 0.90 on the frozen answerable retrieval set; all returned citations resolve to the correct saved game and ply. A local performance target is p95 at most 30 seconds for a bounded fresh review question and at most 2 seconds for a cached search, measured on the declared machine. Report unmet latency targets honestly.

**G7, research completion:** final manifests, raw outputs, deterministic tests, statistical analysis, negative cases, reproducibility instructions, source/license inventory, demo, report, and presentation are all present. Human-learning claims appear only when supported by the required study.

Engineering completion, research completion, and product readiness are different statuses. Do not convert a failed hypothesis into a fabricated success or keep revising the hidden test until it passes.

## 13. Human evaluation and Chess.com cross-check protocol

### Chess-competent review

Recruit two independent chess-competent reviewers through the owner, not automated outreach. Record relevant expertise without inflating credentials. Pilot the rubric on development cases, then independently review a stratified subset of at least 60 final cases. Blind reviewers to condition labels where feasible and randomize presentation order. Preserve separate correctness, important-idea coverage, clarity, and usefulness ratings.

Resolve disagreements with a documented adjudication pass using the legal position and reference evidence. Report initial disagreement and agreement statistics. A machine checker that agrees with another checker using the same code is not an independent human audit.

### Learner pilot

Before collecting data intended as human-subject research, obtain the appropriate institutional determination or approval. UMD provides a Human Subject Research Determination process when the requirement is unclear. Do not self-declare an exemption or start recruitment on the strength of this plan. [S19]

A proposed exploratory pilot uses 12-20 consenting adult learners with recorded chess-experience bands. This is not a powered confirmatory study. Use matched, disjoint pre-test, instruction, and post-test positions; counterbalance condition order and concept assignment so a learner does not see the same solution twice. Compare template-based instruction with the verified explanation system on a small set of themes.

The primary learner measure is unassisted performance on new positions testing the same concept. Also measure explanation comprehension and task time. Keep satisfaction separate. No engine assistance during the test portion. A delayed retention session is optional and must be described as absent when not run.

Without approval or participants, complete the technical research package and label teaching benefit untested. Do not substitute an LLM learner and claim human improvement.

### Chess.com comparison details

Select 30 cases before inspecting platform results, stratified across tactics, quieter decisions, and covered endgames. Open the completed game or supplied position in Analysis, select the correct ply and side, and record the settings and visible result. For Game Review, preserve the platform's exact category as a platform observation, not the project's own severity label. [S08-S10]

Store a discrepancy record when local and platform results differ: state/history match, engine identities, budgets, line differences, and whether deeper local adjudication changes the conclusion. Unknown engine versions remain unknown. Do not count screenshots as an evaluation dataset or redistribute platform commentary without permission. The comparison can be incomplete without blocking local reference analysis.

## 14. Agent responsibilities and task graph

Map these logical roles onto existing registered agents: coordinator/integrator; chess/state engineer; data/reference curator; language/verification engineer; interface/vision engineer; independent evaluation/QA reviewer; documentation/presentation editor. One person or agent can cover multiple roles, but the builder must not be the sole approver of its own benchmark claim.

Use the existing Company Runtime and its supported task admission path. The task list below is a dependency graph to translate into that runtime, not an instruction to invent a parallel orchestration platform. Defaults begin NOT STARTED; a passed acceptance check and retained receipt are required to change a task to complete.

### C00. Verify workspace and shared document access

Owner: coordinator. Dependencies: none. Inspect project identity, active roster, permissions, worktree, and available recipes. Register the hub and handoff, synchronize the mirror, and collect each agent's read receipt. Preserve the soccer baseline manifest. Output `bootstrap.json`, access receipts, and a short discovery note. Accept only when all active project agents can read the plan or explicit exceptions are visible. A missing Drive route must not prevent work from the supplied private bundle.

### C01. Freeze scope and reuse plan

Owner: coordinator. Dependency: C00. Inspect existing retrieval, evidence-card, storage, interface, and model adapters. Choose reuse versus a small chess adapter for each component. Freeze standard chess, post-game-only behavior, required visual conditions, and final outputs. Output a module map and scoped architecture decision. Accept when there is one implementation path and no implicit dependency on a team contact, private footage, or a paid platform service.

### C02. Establish reproducible dependencies and resource limits

Owner: chess engineer. Dependency: C01. Pin Python packages, Stockfish binary/network, frontend tools, model configuration, and supported OS instructions. Measure a tiny engine/model canary on the actual host. Set bounded process concurrency, timeouts, and storage limits without changing unrelated PC settings. Output lockfiles and environment receipt. Accept when a clean environment can parse a game, run one UCI analysis, and save its identity.

### C03. Inventory sources, licenses, and permissions

Owner: data curator. Dependency: C01. Choose the small initial corpus, record origin/license and permitted uses, and separate platform-derived annotations from redistributable data. Review component and model licenses before packaging. Output source inventory and download manifest. Accept when every planned input and distributed component has a source and no unresolved permission is represented as granted.

### C04. Build state and PGN import/export

Owner: chess engineer. Dependency: C02. Implement validated standard-chess import, legal replay, move indexing, FEN/history preservation, branching, and annotated PGN export. Preserve or explicitly quarantine parser errors instead of importing a silent partial game. Output state module and deterministic tests. Accept round trips for castling, en passant, promotion, checks, terminal positions, and history-dependent draws, plus rejection of unsupported variants.

### C05. Construct development, validation, and test manifests

Owner: data curator. Dependencies: C03, C04. Sample completed games, quiet moves, tactical cases, rule/history cases, and generated endgames. Apply puzzle first-move semantics correctly. Group related positions and derivatives before splitting. Output manifests, exclusions, provenance, and duplicate audit. Accept only after no parent game, transposition family, or derived exercise crosses the declared split boundary.

### C06. Implement bounded UCI analysis and cache identity

Owner: chess engineer. Dependencies: C02, C04. Add process lifecycle, legal input checks, candidate/root-restricted analysis, cancellation, restart, and raw receipts. Include history and configuration in cache identity. Output service and error fixtures. Accept when stale-cache, opposite-side score, timeout, unavailable engine, and concurrent-request tests pass. No timeout may be presented as a draw or neutral evaluation.

### C07. Implement reference types and tablebase semantics

Owner: data curator with chess engineer. Dependencies: C05, C06. Build covered-endgame probing and engine-reference labeling, preserving raw WDL/DTZ and rule-aware outcomes. Inventory needed successor tables. Output reference records and coverage audit. Accept when uncovered positions, castling rights, halfmove limits, and cursed/blessed outcomes have correct explicit handling and no DTZ value is described as mate distance.

### C08. Implement evidence and result schemas

Owner: coordinator with language engineer. Dependencies: C04, C06, C07. Define versioned state, analysis, explanation, claim, retrieval, and result records. Validate referential integrity and hashes. Output schemas and example records. Accept when a changed game, move, engine configuration, or evidence file invalidates stale results rather than silently reusing them.

### C09. Implement deterministic factual checks

Owner: chess engineer. Dependency: C08. Add precise occupancy, move-legality, capture, check, material-change, line-validation, and reference-comparison tools. Separate attack geometry from tactical gain and unsupported strategic claims. Output checker tests, including deliberately false statements. Accept when known-false claims are rejected and inconclusive claims are not silently treated as true.

### C10. Build the non-LLM explanation baseline

Owner: language engineer. Dependencies: C08, C09. Produce short templates that describe the actual move, supported consequences, one alternative, and one justified practice idea. Output A0 baseline and sample reviews. Accept when the complete review pipeline runs with no model installed and every literal assertion traces to deterministic or reference evidence.

### C11. Build the exact-state LLM-only baseline

Owner: language engineer. Dependencies: C04, C08. Give the chosen local model the same state representation and relevant history but no engine tools, future moves, or answer labels. Use fixed generation limits and record failures. Output A1 runner and prompt manifest. Accept when isolation tests show no hidden engine, retrieval, or reference cache access.

### C12. Build the tool-assisted explanation baseline

Owner: language engineer. Dependencies: C06, C08, C09, C11. Add allowlisted state/analysis tools with structured arguments and bounded calls. Require evidence-linked commentary, analysis, and coaching outputs. Output A2 runner. Accept when illegal tool requests fail clearly, requested evidence is retained, and every answer identifies the correct state and move.

### C13. Verify final prose and implement bounded repair

Owner: language engineer with independent QA. Dependencies: C09, C12. Extract assertions from final prose, run checks, allow one repair, and preserve original/revised outputs. Show partial verified answers or uncertainty when necessary. Output A3 runner and adversarial cases. Accept when rewriting cannot introduce unchecked claims or hide failed attempts from evaluation.

### C14. Add a source-linked lesson library

Owner: data curator with language engineer. Dependencies: C03, C10, C12. Create a small allowed lesson collection, attach source and evidence records, and link exercises to supported mistakes. Keep primary evaluation offline. Output corpus and retrieval tests. Accept when retrieved text cannot override system instructions and held-out solutions are inaccessible. Live web retrieval remains a separately labeled ablation.

### C15. Implement board and replay rendering

Owner: interface/vision engineer. Dependencies: C04, C08. Render saved games and alternative branches with stable coordinates, timestamps, and independently controlled overlays. Export short replay videos from legal histories. Output renderer, fixtures, and asset-license notes. Accept when frame/state alignment and board orientation round-trip correctly, and observation images contain no annotations that leak the intended answer.

### C16. Add searchable review events

Owner: interface engineer. Dependencies: C08, C10. Adapt existing lexical search and structured filters to game-ply event records. Handle paraphrases, negation, absence of a relevant event, and duplicate results. Output index and 60-question evaluation manifest. Accept when every result resolves to the exact saved state and no fabricated event is created to satisfy a query.

### C17. Assemble the review interface

Owner: interface engineer. Dependencies: C10, C12, C13, C15, C16. Implement import, timeline, board, actual/alternative replay, chat, evidence drawer, uncertainty, and export. Add local practice without online move submission. Output a usable local demo. Accept an end-to-end test from completed PGN import to a cited explanation and export, with keyboard access and stale-response cancellation.

### C18. Build static-image state recovery

Owner: vision engineer. Dependencies: C05, C15. Implement a simple image-parser baseline and a VLM extractor under identical observation conditions. Output recovered-state records with uncertainty, not unverified tactical prose. Accept clean held-out parsing tests, orientation checks, and explicit refusal to infer hidden history from a screenshot. Keep ground-truth sidecars evaluator-only.

### C19. Build temporal replay recovery

Owner: vision engineer. Dependencies: C04, C15, C18. Track legal state transitions from a known start across replay frames, using bounded hypotheses when frames are missing. Output move-sequence predictions and first-divergence logs. Accept dropped-frame, animation, occlusion, and ambiguous-transition tests without silently consulting the true move list.

### C20. Implement the evaluation runner

Owner: independent evaluator. Dependencies: C05, C07, C08, C10, C11, C12, C13, C16. Run identical cases through required conditions, retain all failures, validate references, and compute metrics with grouped uncertainty estimates. Output analysis scripts and NOT RUN result templates. Accept recomputation from raw receipts with no hand-entered performance numbers and no final-label access for builder agents.

### C21. Execute integration, reliability, and security tests

Owner: QA reviewer. Dependencies: C17, C18, C19, C20. Test malformed inputs, engine/model outages, stale IDs, cancellation, cache corruption, oversized PGNs, prompt injection, and path restrictions. Output a failure matrix and test receipts. Accept zero unresolved release-blocking data-integrity or unauthorized-access defects; performance weaknesses remain research results rather than hidden failures.

### C22. Validate, tune, and freeze the protocol

Owner: coordinator and evaluator. Dependencies: C14, C20, C21. Use development/validation only to settle budgets, prompts, thresholds, model choice, corpus, exclusions, and rubric. Freeze hashes and predeclare the primary contrast. Output signed-off protocol manifest. Accept when all required conditions can run, deviations are explained, and final data remains sealed.

### C23. Run the frozen held-out evaluation

Owner: independent evaluator. Dependency: C22. Run required exact-state and visual conditions on the protected test through the approved evaluator path. Preserve raw outputs, failures, and hardware telemetry. Output results and immutable run receipts. Accept completeness and reproducibility, not a predetermined favorable outcome. Do not admit model improvement tasks using these answers.

### C24. Complete the Chess.com comparison sample

Owner: data curator with owner-assisted browser review. Dependencies: C07, C22. Review the preselected 30 cases through supported platform functionality, record visible settings and discrepancies, and flag unavailable premium features. Output comparison records, not copied coaching content. Accept a documented sample or explicit access-limited subset; the local benchmark must remain reproducible without platform access.

### C25. Conduct independent review and optional learner pilot

Owner: evaluator with project owner. Dependencies: C17, C22, C23 for final-output review, and required institutional determination for participant work. Run the blinded review and approved learner protocol. Output anonymized ratings, consent/approval references stored privately, and analysis. Accept actual observations only. If people are unavailable, record NOT RUN and exclude claims of human learning or coach effectiveness.

### C26. Analyze errors, uncertainty, and ablations

Owner: evaluator. Dependencies: C23, C24; include C25 when available. Classify perception, history, reference, tool-use, language, citation, retrieval, and teaching failures. Compare A3/A2 and oracle/recovered-state conditions without cherry-picking. Output statistics, representative failures, and a claim-to-evidence map. Accept conclusions that match denominators, uncertainty, and reference types.

### C27. Package the application and reproduction bundle

Owner: coordinator with QA. Dependencies: C17, C21, C23. Create a clean-environment setup guide, lockfiles, minimal redistributable fixtures, source/license notices, saved demo, and one-command equivalents for tests and evaluation. No proprietary assets, secrets, or hidden participant identifiers. Accept installation and a smoke run by someone other than the primary builder.

### C28. Reconcile documents and agent mirrors

Owner: documentation coordinator. Dependencies: C00 and accepted work receipts as they arrive; final pass after C26. Update the private hub's actual progress, decisions, and blockers, then refresh mirrors and affected read acknowledgments. Preserve prior protocol versions. Accept revision-safe updates with evidence links and unchanged restricted sharing. Do not automatically edit the Archit update.

### C29. Write the final technical report

Owner: documentation editor with evaluator. Dependencies: C26, C27. Follow the report outline below, cite primary work, include actual results and negative outcomes, and distinguish measurements from proposals. Output editable source plus a reviewable export. Accept independent reconciliation of every quantitative claim to a result artifact, and no unsupported novelty, exactness, or human-benefit claim.

### C30. Build the final presentation and demo

Owner: presentation editor with coordinator. Dependencies: C27, C29. Create the slide sequence and demo described below, using actual charts, legal replay examples, and an offline fallback. Output editable slides, speaker notes, demo script, and recording. Accept a rehearsal from a clean starting state, with one success, one failure, and uncertainty explained.

### C31. Conduct the chess-phase exit review

Owner: project owner and independent evaluator. Dependencies: C28, C29, C30. Mark each acceptance gate passed, failed, or not run. Decide whether to refine chess, conclude the experiment, or start a separately scoped soccer simulation. Output exit decision and transferable-module list. Accept a complete research record even when some performance targets fail, without relabeling it a validated sports coach.

## 15. Execution order, resource policy, and recovery

Start C00, then C01. After scope selection, dependency setup and source inventory can proceed in parallel. The minimum useful path is state -> analysis -> evidence -> deterministic checks -> template baseline -> replay/search -> interface. Only then add LLM and visual complexity. This gives the project a useful result even if local-model serving is unreliable.

Use a maximum of one active GPU inference worker initially and a small bounded CPU analysis pool. Reference evaluation should use single-threaded per-case settings for comparability. Measure throughput before increasing concurrency. Do not force GPU utilization for its own sake or change BIOS, drivers, sleep policies, or unrelated Agent Studio loops to satisfy a benchmark.

Default paid API spend is zero. Discover local models and record actual serving capabilities; do not assume a remembered model name still works. Pin weights, quantization, projector where relevant, context limit, prompt, image packing, runtime, and generation limits. CPU reference analysis can continue while a GPU lane is unavailable. Dataset and table downloads need explicit size estimates; pause before unexpectedly large downloads.

Use bounded retries only for transient infrastructure errors, with the number of attempts retained. A repeat after changing model, prompt, image grouping, or server is a different configuration. One failed task must not park every independent task. A blocked Chess.com check or human study does not block the deterministic pipeline, local evaluation, or documentation of the limitation.

Workers may propose patches and run authorized local tests in their scoped workspace. External publication, permission expansion, messages, purchases, data uploads, and public claims require the owner's explicit approval. Do not let the model rewrite its own acceptance criteria or erase a failed run.

## 16. Required test inventory

### Deterministic chess and import tests

Cover legal/illegal SAN and UCI, malformed/truncated PGNs, parser warnings, custom starting FEN, standard versus unsupported variants, castling through check, lost castling rights, en passant legality and expiry, underpromotion, promotion capture, pinned-piece movement, checkmate, stalemate, and supported draw conditions. Replay history must distinguish positions that look identical but have different repetition or halfmove status.

Use small hand-verified fixtures and cross-check selected move counts/terminal cases through an independent implementation or trusted reference. Testing a wrapper against itself is not enough. Record the limitations of automatic dead-position detection rather than claiming complete adjudication of all possible draw states.

### Engine and reference tests

Cover Black/White perspective, typed mate values, bound flags or incomplete results, root-restricted actual moves, near-ties, missing MultiPV candidates, tablebase coverage gaps, draw-rule edge cases, corrupt/missing engine files, process exit, restart, deadline, cancellation, and stale caches. Keep exact and approximate outcomes separate. A principal variation containing legal moves alone does not prove its strategic assertion.

### Explanation and retrieval tests

Inject wrong-square claims, impossible captures, invented pieces, false forced-mate statements, incorrect line summaries, unobserved intentions, future-information leakage, wrong game/ply citations, answer-bearing retrieved text, and unsupported advice. Verify the final prose after revision. Include no-mistake games, empty-search results, repeated questions, and questions about the opponent rather than the selected player.

### Visual and temporal tests

Test all declared orientations, clean and unseen piece styles, resolution/compression variation, animation frames, frame gaps, occlusion, multiple plausible transitions, and unknown side/history. Verify that missing information yields uncertainty instead of silent oracle correction. Separate image recognition from chess reasoning in result tables.

### Operational and access tests

Test project-path allowlists, traversal attempts, oversized input limits, hostile PGN comments, unauthorized network targets, disabled cloud fallback, concurrent document edits, stale mirrors, newly enrolled agents, and missing read receipts. Test recovery from an interrupted write using the existing project backup strategy on fixtures, not by risking live data.

## 17. Release contents and reproducibility requirements

The finished implementation should include: application source; dependency and engine manifests; model/prompt configuration; approved sample PGNs; data-selection and split manifests; versioned evidence schemas; deterministic tests; evaluation runner; raw model/tool receipts; result tables; statistical scripts; failure examples; source/license inventory; local setup/run instructions; a saved demonstration; and the final report and slides.

Expose reproducible command equivalents for environment diagnosis, unit tests, integration tests, sample review, fixture rendering, validation evaluation, protected final evaluation, and result/report generation. Command names such as `chess-phase doctor`, `review`, `render-fixtures`, and `evaluate` are proposed interfaces, not commands that exist in this bundle. Map them to the selected implementation and test the exact documented commands before release.

A clean-machine reproduction must verify checksums, install dependencies without hidden credentials, run the non-LLM sample, optionally connect the declared local model, and recompute summary metrics from saved outputs. Record expected artifacts and failure messages. Do not require the owner's whole Agent Studio database or private footage to reproduce the chess results.

Stockfish is GPLv3 and python-chess is GPLv3-or-later. Preserve notices and review the distribution obligations of the actual combined package before publishing. Keeping a private research workspace is not permission to remove licenses from redistributed components. Also inspect the selected model and board-asset licenses. Do not automatically choose an incompatible proprietary release license. [S17, S20]

## 18. Final report and presentation plan

### Technical report structure

1. Problem and scope: why a controlled chess phase is useful for the broader review project; what it does not establish about sports.
2. Related work: engine-assisted commentary, claim-level evaluation, existing platform analysis, and the precise candidate contribution.
3. System: state contract, reference policy, tools, evidence, verification, retrieval, interface, and visual-input path.
4. Data and method: provenance, grouping, split counts, leakage prevention, configurations, budgets, metrics, primary contrast, and human-review protocol.
5. Results: actual required-condition tables with denominators and confidence intervals; separate exact-state, visual, retrieval, reliability, and human observations.
6. Failure analysis: representative negative cases, uncertainty propagation, engine/platform disagreement, and non-adjudicable claims.
7. Discussion: what the evidence supports, what simpler baselines already solve, limitations, and the implications for a later soccer study.
8. Reproducibility and conclusion: artifact inventory, exact rerun instructions, final gate status, and justified next decision.

Put full prompts, schema details, settings, source inventory, test cases, and additional results in appendices. Every chart must be generated from saved result data, label its population and denominator, and distinguish real measurements from illustrative design figures. Do not use a performance chart containing invented placeholder values.

### Main presentation: 12 slides

**1. The question.** Show the user problem: useful game review requires more than fluent commentary. State the narrow chess research question. Do not open with a claim to replace coaches.

**2. Why chess first.** Compare known state with estimated state. Show a simple workflow distinction and explain why the soccer objective remains separate from the evidence obtained here.

**3. What we built and reused.** Show the actual application and architecture. Identify Stockfish, python-chess, tablebases, data sources, and the components written by the project. Distinguish existing tools from the contribution.

**4. Reference policy.** Explain rules, covered tablebases, bounded engine analysis, Chess.com comparison, and human review. Show one case where an engine estimate is not an exact proof.

**5. A review example.** Use one legally verified game position. Show actual move, alternative, short explanation, and the evidence drawer. Identify this as a demonstration rather than an aggregate result.

**6. Experimental design.** Present A0-A3 and visual conditions, split counts, grouping, and the protected holdout. Keep model and representation confounds visible.

**7. Explanation results.** Plot actual paired error and coverage results, with denominators and intervals. Explain the primary A3/A2 contrast and whether it met the predefined target.

**8. What vision changes.** Show oracle-state versus recovered-state performance and one first-divergence replay. Label synthetic 2D conditions clearly.

**9. Search and usefulness.** Show actual retrieval and latency results, plus independent review or learner findings only if run. Do not substitute satisfaction for learning.

**10. Failures and disagreements.** Include a confident wrong answer, an ambiguous input that should trigger abstention, or a platform/reference discrepancy. Explain what the system does and does not detect.

**11. Reproduction and limitations.** State hardware, cost boundaries, source/license availability, remaining gaps, and how another person can rerun the experiment.

**12. Decision and next step.** Mark the chess-phase gates honestly. Propose a narrow soccer-simulation experiment only when the evidence motivates it. Do not present chess outcomes as sports coaching validation.

Appendix slides should cover full configurations, detailed metric definitions, human-review rubric, ablations, license notes, and additional failures. Any unavailable result is explicitly NOT RUN, not an empty chart or a fabricated percentage.

### Demonstration script

Start from a saved completed game already included in the cleared release fixtures. Import it, move to a preselected decision, ask why the move deserves review, and open the referenced evidence. Play the actual continuation and the alternative separately. Search for a related missed threat and show the exact game/ply returned.

Then show a controlled degraded replay where the state extractor is uncertain. Demonstrate the uncertainty behavior or show a saved failure, rather than switching silently to true state. Finish by opening the exported annotated PGN and the result record behind one displayed metric.

Keep a local recording and saved outputs as a fallback if live model serving fails. Clearly say when the audience is seeing cached output. Rehearse from a clean initial state with no private tabs, hidden labels, account information, or unlicensed footage on screen.

## 19. Chess exit and soccer transfer

Transfer candidates are the event/evidence schema, state identity, search, replay, analysis-tool boundary, source-linked explanation, verification interface, uncertainty presentation, and evaluation discipline. Chess rules, Stockfish values, and tablebase guarantees do not transfer to soccer.

A later soccer-simulation phase should introduce one narrow decision task, known simulator state, policy-controlled alternatives, and a separately tested visual observation path. It needs its own outcome model and assumptions. Do not reuse a chess 'optimal move' label as if soccer decisions had the same exact reference.

Continue human discovery of the sports film-review workflow separately, through owner-approved contact. A board-game phase should reduce technical uncertainty, not become a reason to ignore what coaches actually need. Preserve the original soccer research record so the final story is a controlled progression, not a rewritten history.

## 20. Primary sources and use notes

[S01] Stockfish official release and download: [Stockfish 19 release](https://stockfishchess.org/blog/2026/stockfish-19/) and [official downloads](https://stockfishchess.org/download/). Establishes the current initial engine choice; freeze the actual installed artifact.

[S02] [Stockfish FAQ](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html). Evaluation interpretation, search depth limitations, CPU inference, and the distinction between engine evaluations and interface move annotations.

[S03] [python-chess core documentation](https://python-chess.readthedocs.io/en/latest/core.html). Board state, legal moves, game-history behavior, and rule-related APIs.

[S04] [python-chess PGN documentation](https://python-chess.readthedocs.io/en/latest/pgn.html). Parsing, game trees, annotations, and export; importer errors must be retained.

[S05] [python-chess Syzygy documentation](https://python-chess.readthedocs.io/en/latest/syzygy.html). Coverage, WDL/DTZ semantics, required tables, and probing limitations.

[S06] [python-chess engine communication](https://python-chess.readthedocs.io/en/latest/engine.html). UCI lifecycle, analysis limits, scores, principal variations, and root-move controls.

[S07] [Lichess open database](https://database.lichess.org/). CC0 game/evaluation/puzzle exports, schemas, mixed reference settings, and puzzle-move conventions.

[S08] [Chess.com Analysis board](https://support.chess.com/en/articles/8583825-how-do-i-use-the-analysis-board). Supported analysis workflow and loading completed games or positions.

[S09] [Chess.com Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work). Platform review functionality; not a ground-truth guarantee.

[S10] [Why Chess.com move classifications change](https://support.chess.com/en/articles/11845102-why-did-my-move-classification-change-in-game-review) and [Chess.com engine implementation](https://support.chess.com/en/articles/9462780-how-do-the-chess-engines-on-chess-com-work). Settings and engine differences must be recorded; platform agreement is not necessarily independent.

[S11] [Chess.com Published Data API](https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it). Read-only public data, cache behavior, rate limiting, and platform-asset boundaries.

[S12] [Chess.com User Agreement](https://www.chess.com/legal/user-agreement). Check current permitted use before collection or redistribution; this plan does not grant platform rights.

[S13] [Chess.com Fair Play Policy](https://www.chess.com/legal/fair-play). Keep engine/coaching assistance outside ongoing human games.

[S14] [Improving Chess Commentaries by Combining Language Models with Symbolic Reasoning Engines](https://arxiv.org/abs/2212.08195). Prior engine-assisted commentary research, not a claim created by this project.

[S15] [Hallucinations on the Board: Tool-Augmented Evaluation of LLM Chess Commentary](https://arxiv.org/abs/2608.04240). ACT-Eval prior work; check repository and license before adopting its benchmark.

[S16] [python-chess SVG rendering](https://python-chess.readthedocs.io/en/latest/svg.html). Deterministic board rendering facilities for the interface and controlled observations.

[S17] [python-chess repository and license](https://github.com/niklasf/python-chess). Package identity, implementation, and GPLv3-or-later terms.

[S18] [Stockfish useful data](https://official-stockfish.github.io/docs/stockfish-wiki/Useful-data.html). MultiPV/resource tradeoffs; the budgets in this handoff remain project-specific design choices.

[S19] [UMD Institutional Review Board](https://research.umd.edu/resources/irb). Human Subject Research Determination and review before the applicable participant research.

[S20] [Stockfish repository and license](https://github.com/official-stockfish/Stockfish). Source identity and distribution obligations for the exact binary used.
