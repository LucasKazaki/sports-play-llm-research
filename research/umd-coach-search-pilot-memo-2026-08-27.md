# A coach-first pilot for searchable soccer and American-football video

**Decision memo for the SportsPlayLLM / SoccerMaster–Football Master project**  
**Audience:** project team preparing a University of Maryland coaching demonstration  
**Evidence reviewed:** official UMD Athletics, NCAA, NFL, FIFA and U.S. Soccer pages; peer-reviewed/open-access sports-video research  
**Access date for all web sources:** August 27, 2026

## Executive Summary

- **Pitch a search assistant, not an autonomous coach.** The credible value proposition is: a coach asks a sport-specific question, the system returns a short ranked cutup with timestamps, structured evidence, uncertainty and the original video. The coach remains the adjudicator. This matches established coaching uses of film—cutups, opponent analysis, self-scout and practice-to-match teaching—without claiming that a vision-language model understands tactics at a coach's level.

- **Use one interface but two schemas.** Soccer is continuous and phase-based; American football is play-bounded and situation-based. SoccerMaster research can supply soccer-specific visual evidence, while a proposed “Football Master” encoder/report layer should represent personnel, formation, motion, situation and post-snap outcomes. A universal event label set would erase the information coaches actually need.

- **UMD football has the clearest operational entry point.** The official 2026 staff page names a Director of Coaching Operations & Analytics, offensive and defensive analysts, a Director of Football Technology, a Video Coordinator and an Assistant Video Coordinator. The current men's and women's soccer pages identify coaches and operations/support roles but no sport-dedicated video or analytics title. That is an outreach clue, not proof of either program's internal workflow.

- **Ask for a bounded, post-game shadow pilot.** Start with university-approved footage, no in-game deployment, no player-selection or medical decisions, local or university-approved processing, and a coach-authored evaluation set. Measure whether the tool finds useful clips faster than the current workflow. Do not ask first for unrestricted footage or permission to train on an entire archive.

## 1. Evidence boundary: what is known and what remains a hypothesis

### Sourced facts

1. The [2026 Maryland football staff page](https://umterps.com/sports/football/coaches/2026) lists Michael Locksley as head coach; Carson Mitchell as Director of Coaching Operations & Analytics; offensive and defensive analysts; Chris Speeney as Director of Football Technology; Scott Hayward as Video Coordinator; and Garvey Biggers as Assistant Video Coordinator.
2. The [2026 Maryland men's soccer staff page](https://umterps.com/sports/mens-soccer/coaches) lists Sasho Cirovski as head coach, Brian Rowland and Steve Armas as associate head coaches, Michael Gould as assistant coach, Kerry Dziczkaniec in operations, and Shawn Flynn as sport supervisor.
3. The [2026 Maryland women's soccer staff page](https://umterps.com/sports/womens-soccer/coaches) lists Michael Marchiano as head coach; Alex Shinsky, Sara Butler and Morgan Ruhl as assistant coaches; and Shawn Flynn as sport supervisor.
4. Those public pages do **not** reveal UMD's internal video platform, tagging taxonomy, data-retention policy, review cadence, workload, pain points or model permissions. No claim about those items should be made before an interview.
5. The NFL describes All-22 as footage that compiles sideline and end-zone angles and can isolate plays, and its historical account of digital film study describes situation- and unit-specific cutups. These are general football-workflow examples, not evidence that UMD uses a particular vendor or exact process ([NFL Football Operations](https://operations.nfl.com/rules-officiating/officiating/performance-evaluation/); [NFL digital film-study account](https://www.nfl.com/news/when-it-comes-to-film-study-coaches-have-entered-the-digital-ag-09000d5d80c3eb01)).
6. FIFA's performance-analysis framework uses a standardized football language and enriched tracking data to describe phases such as build-up, progression, final third, counter-attack, high/mid/low blocks, pressing and recovery. FIFA also documents a coach pairing training footage with match footage to show whether a principle transferred to competition ([FIFA Football Language](https://www.fifatrainingcentre.com/en/game/performance-analysis/football-language-analysis/the-fifa-football-language.php); [David Aznar training/match example](https://www.fifatrainingcentre.com/en/environment/expert-knowledge/david-aznar-on-training-and-match-application.php)).
7. U.S. Soccer describes performance analysis as supporting in-game, opposition and pre-game analysis, and describes a senior national-team strategy analyst implementing opponent-analysis and game-model workflows ([U.S. Soccer high-performance department](https://www.ussoccer.com/stories/2018/09/us-wnt-benefits-from-expanded-high-performance-department); [B.J. Callaghan profile](https://www.ussoccer.com/stories/2023/05/five-things-to-know-about-usmnt-head-coach-bj-callaghan)).
8. SoccerNet-v2 formalizes action spotting as finding semantically meaningful moments in long, untrimmed broadcasts, but its 17-class action taxonomy is much narrower than the detailed, player-specific tactical reports requested here ([SoccerNet-v2 paper](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/html/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.html); [official task page](https://www.soccer-net.org/tasks/action-spotting)).
9. A peer-reviewed American-football formation study states that coaches manually tag formation frames and line of scrimmage and reports a real-game dataset of more than 800 play clips. Its reported results establish a narrow precedent for automation, not a modern coach-ready multimodal system ([CVPR Workshops paper](https://openaccess.thecvf.com/content_cvpr_workshops_2013/W19/html/Atmosukarto_Automatic_Recognition_of_2013_CVPR_paper.html)).
10. SoccerMaster presents a soccer-specific spatial/semantic video encoder with downstream task heads. It is relevant as an evidence representation, but its paper does not validate natural-language coach search or a UMD workflow ([official project](https://haolinyang-hlyang.github.io/SoccerMaster/); [paper](https://arxiv.org/html/2512.11016)).

### Product hypotheses to validate with coaches

- Natural-language search can reduce time spent building recurring cutups.
- Rich, evidence-linked reports can help coaches find examples that a fixed event taxonomy misses.
- Coaches will tolerate model uncertainty if every answer opens the source clip at the relevant moment.
- One user interface can serve both sports if the underlying ontologies, prompts, evaluation sets and filters remain sport-specific.
- A coach's corrections can become high-value labels, provided the correction workflow is faster than existing tagging.

These are hypotheses, not findings. The proposed pilot is designed to test them.

## 2. Who should evaluate a UMD pilot

Do not begin with a mass outreach or presume ownership. Ask Archit or the project sponsor for a warm introduction and let each program designate the workflow owner.

| Program | Current roles that make sense to include | Why they matter | Evidence status |
|---|---|---|---|
| Maryland football | Director of Coaching Operations & Analytics; Director of Football Technology; Video Coordinator; Assistant Video Coordinator; one offensive or defensive analyst; one coordinator/position coach | Together they cover workflow, video ingestion, technical fit, annotation and coaching relevance | Role titles are sourced from the official 2026 page; proposed responsibilities in the pilot are hypotheses |
| Maryland men's soccer | Head- or associate-head-coach-designated reviewer; operations; one assistant coach; sport supervisor only if cross-program coordination is useful | The current public page does not identify a dedicated soccer analyst/video owner, so the program should name the right person | Names/titles are sourced; ownership is unknown |
| Maryland women's soccer | Head-coach-designated reviewer; one assistant coach; sport supervisor only if cross-program coordination is useful | Same reason: discover the actual workflow before designing around it | Names/titles are sourced; ownership is unknown |
| Athletics governance | Compliance, IT/security and whoever owns media rights, added before any private footage is processed | Needed to approve data location, access, retention, model-provider terms and allowed uses | Proposed control, consistent with NCAA responsible-technology guidance |

The [NCAA's responsible performance-technology guidance](https://www.ncaa.org/media-center-performance-technology-guidance-approved-by-csmas/) says utility depends on user needs, warns of unintended health and mental-health impacts, and calls for a written plan covering education, data protection, technology decisions and continuous improvement. That supports treating coaches, video staff, student-athlete governance and compliance as design participants rather than merely end users.

## 3. Five high-value soccer use cases

Every item below is a **candidate use case**. A coach must validate the vocabulary, acceptable evidence and failure cost.

### 3.1 Tactical sequence retrieval

**Coach question:** “Show every time our left back received under pressure, played through the first line, and the possession entered the final third within ten seconds.”

The system should return a short sequence, not a single action label: players or unresolved identities, pitch region, team state, pressure, action chain, outcome, timestamp, view quality and uncertainty. FIFA's phase language provides a defensible starting vocabulary, but the UMD coaching staff's terms should win.

### 3.2 Transition and pressing review

**Coach question:** “Find losses in the middle third where the nearest three players failed to counter-press and the opponent progressed.”

This targets the few seconds between possession states, a coaching unit that ordinary goal/foul/offside labels cannot represent. Search results should distinguish visual evidence from interpretation—for example, “three nearby players visible” is evidence; “failed counter-press” is a coach-adjudicated tactical label.

### 3.3 Individual player development

**Coach question:** “Show the midfielder's body orientation and next action when receiving between lines on the half turn.”

The output can make recurring examples easier to review with a player. Identity must be grounded by roster/jersey evidence or shown as unknown; the model must not confidently invent a player name.

### 3.4 Opponent and set-piece scouting

**Coach question:** “How does the opponent defend second balls after long goal kicks?” or “Show near-post corner routines and the first action after the clearance.”

The useful result is a collection of comparable clips with context—score state, side, restart type, delivery zone, first contact, second-ball location and outcome—not a prose claim without evidence.

### 3.5 Practice-to-match transfer

**Coach question:** “Find match examples of the width principle trained on Tuesday.”

FIFA documents a coach placing training and match clips side by side to illustrate the same attacking-width principle. A searchable system could reduce the effort of assembling those pairs, but “same principle” should remain coach-verified.

## 4. Five high-value American-football use cases

### 4.1 Situation-specific play cutups

**Coach question:** “Show third-and-4-to-7 plays from the left hash against 11 personnel, with fast motion, grouped by coverage shell.”

This extends established digital cutup workflows. A result card should expose down, distance, quarter, game clock, field position, score state, field **hashmark**, personnel, formation, motion, visible shell, snap-to-whistle boundaries, result and uncertainty. “Hashmark” here is a field location, not a cryptographic file hash.

### 4.2 Opponent tendency discovery

**Coach question:** “When the offense motions the back out of 2x2 on third down, what concepts follow, and how often did the defense pressure?”

The system may group candidate plays and calculate counts only from coach-validated tags. It should not turn a small sample into a strategic certainty. Filters and denominators must remain visible.

### 4.3 Position-room technique and assignment review

**Coach question:** “Show every boundary corner rep against a reduced split, including leverage at the snap, route stem, separation point and outcome.”

The model's job is to retrieve and pre-structure evidence. Whether technique or assignment was correct is coach-owned unless an explicit playbook label is supplied under approved access controls.

### 4.4 Self-scout and counter-tendency review

**Coach question:** “Show our repeated formations on first-and-10 and whether motion or play family made them predictable.”

This is valuable only if the system can separate similar pre-snap pictures, expose its sample, and compare against a manually tagged baseline. A strong pitch is faster evidence collection, not secret-strategy generation.

### 4.5 Practice-to-game and special-teams teaching

**Coach question:** “Pair practice reps of the kickoff-fit rule with game reps where the return entered that lane.”

This mirrors the soccer practice-to-match use case but uses football-specific unit, lane, assignment and outcome fields. Special teams should be a first-class schema, not forced into offense/defense labels.

## 5. One product shell, two sport-specific evidence contracts

### Shared data and system needs

- Provenance and rights status for every video, plus whether it may be viewed, processed, retained and used for training.
- Stable game/practice ID, date, teams, source, camera/view, timestamps and file integrity digest.
- Roster and alias table with an explicit `unknown_player` path.
- Original clip plus the exact frames/time span used by the model.
- Coach-authored labels, corrections, reviewer identity/version and disagreement handling.
- Game-level—and when needed opponent/season-level—train, validation and test separation.
- Access control, audit log, retention/deletion rule and export restrictions.
- Evidence-linked model output: observation, interpretation, confidence/abstention and source timestamp must be different fields.
- Retrieval evaluation by query/use case, not one aggregate accuracy number.

### Soccer-specific fields

- Continuous match clock, half/period, stoppage and replay/broadcast-state handling.
- Possession/team state; in-possession, out-of-possession and transition phase.
- Pitch region, ball path, visible player locations, team shape and numerical relation such as 2v1 or 3v2.
- Restart/action vocabulary: kick-off, throw-in, corner, free kick, foul, offside, long pass/long ball, cross, shot and coach-defined subtypes.
- Pressure, line break, receiving context, action chain, terminal outcome and continuation window.
- Multiple events per window; a 20-second clip can contain recovery, progression, cross, clearance and second ball.

### American-football-specific fields

- Discrete play boundaries: pre-snap, snap, live action, whistle and post-play/replay.
- Down, distance, field position, field hashmark, quarter/game clock, score state and drive.
- Personnel, formation, strength, splits, motion/shift and eligible-player alignment.
- Offensive play family/concept, blocking/protection, route structure and ball-carrier/target.
- Defensive front, box count, shell/coverage evidence, pressure, rush count and disguise when supportable.
- Position/assignment/technique evidence, result, penalty and special-teams unit.
- Synchronized All-22/sideline and end-zone views when the institution controls them; broadcast-only footage should carry a view-limit warning.

### Model roles

- **SoccerMaster-derived component:** candidate soccer-specific visual representation and reranking/evidence layer. It should not be described as a validated natural-language search model until the project reproduces relevant results.
- **Football Master research prototype:** a sport-specific visual/report layer trained and evaluated on legally usable football clips and coach-approved labels. Initial targets should be play boundaries, formation/personnel/motion and evidence-rich retrieval—not every playbook concept at once.
- **Shared retrieval layer:** converts a query into sport-specific structured filters plus semantic retrieval, ranks clips, and returns evidence cards.
- **Shared language layer:** summarizes only retrieved evidence, preserves unknowns and cannot cite audio/commentary as visual ground truth.

## 6. Interview guide before building for UMD

### Current workflow

1. Who records, ingests, tags, quality-checks and distributes game and practice video?
2. What platform(s) and export formats are already part of the workflow?
3. Which cutups are rebuilt every week, by whom, and how long do they take?
4. Which five searches are easy today, and which five require manual rewatching?
5. What camera views exist for games and practices, and how are views synchronized?

### Vocabulary and evidence

6. What is the program's canonical taxonomy? Which terms differ by coach or position group?
7. What context must accompany a clip before it is usable in a meeting?
8. When two coaches disagree on a tag, how should that disagreement be recorded?
9. Which labels are objective observations, and which encode playbook/game-model interpretation?
10. When should the system abstain rather than return a best guess?

### Evaluation

11. What is the cost of a false positive versus a missed clip for each use case?
12. What top-k result set would a coach actually review: 3, 5, 10 or a full cutup?
13. What is the correct baseline: current platform search, manual rewatch, or analyst-built cutup?
14. Which held-out game(s) can be labeled without contaminating training?
15. What time saving or quality improvement would justify another month of work?

### Governance and adoption

16. Which footage may be processed locally, in a university cloud or by an external model provider?
17. May player identity be indexed? May model outputs be retained across seasons?
18. Who approves training use, derived annotations, exports and deletion?
19. Are there uses the program wants explicitly prohibited, such as medical inference, discipline or roster decisions?
20. Who is the weekly pilot owner, and what 30-minute review slot can be protected?

## 7. A credible four-week shadow pilot

This is a **proposal**, not a commitment or claim about UMD's current process.

### Scope

- One designated soccer program and Maryland football; expand to the second soccer program only after the workflow is stable.
- Two approved full games/matches and one approved practice per sport, or the smallest equivalent set the programs permit.
- Approximately 100 coach-adjudicated soccer moments and 150 football plays, sampled across common, rare and negative cases.
- Twelve coach-written natural-language queries per sport, frozen before final evaluation.
- Post-game and post-practice use only. No sideline/in-game analytics.
- Read-only shadow workflow: the existing video system remains the source of record.
- Local or explicitly university-approved processing. No model-provider upload unless rights, privacy and terms are approved in writing.
- No player-selection, discipline, injury, medical or officiating decisions.

### Week-by-week plan

1. **Week 0 — permission and workflow map:** confirm media rights, data location, retention, role access, current baseline task and forbidden uses; choose one workflow owner per sport.
2. **Week 1 — taxonomy and gold set:** coaches define the 12 queries and adjudicate a small, balanced reference set including no-event/ambiguous examples.
3. **Week 2 — shadow run:** run ingestion and retrieval without changing the coaching process; record time, results, abstentions and failures.
4. **Week 3 — blind comparison:** reviewers judge shuffled system and baseline cutups for relevance and completeness without knowing the source.
5. **Week 4 — decision review:** inspect failures by query, camera, event and identity; decide to stop, revise or expand. Delete or retain data according to the written plan.

### Proposed success scorecard

The coaches should revise these thresholds before the pilot.

| Dimension | Proposed measure | Starting gate |
|---|---|---|
| Retrieval usefulness | Coach-rated relevant clips among top five, reported per query | At least 80%, with no critical query hidden by an average |
| Coverage | Recall on a manually enumerated held-out event/play set | At least 75% for agreed initial categories |
| Evidence grounding | Displayed report fields traceable to the shown clip or approved metadata | At least 95%; player identity must abstain when unsupported |
| Workflow speed | Median time to build the same cutup versus current baseline | At least 40% reduction |
| Trust behavior | Unsupported high-confidence statements in the evaluated output | Zero; uncertain cases must be marked or omitted |
| Operational fit | Successful import/open/export in the existing review path | 100% for the pilot set |
| Governance | Unauthorized transfer, access or retention events | Zero |

Report confidence intervals or raw numerator/denominator alongside percentages because the pilot is small. Split by full game, not by random clips from the same game, to prevent visual and opponent leakage.

## 8. Twenty-minute live demonstration

### 0:00–2:00 — Lead with the coaching job

Say: “This does not call plays or grade athletes. It turns a coaching question into an evidence-linked cutup and shows what it could not verify.” Show the approved dataset manifest and the exact truth boundary.

### 2:00–7:00 — Soccer mode

1. Switch to **Soccer**.
2. Run one event query: “Show long balls that led to a second-ball contest in the attacking half.”
3. Run one tactical/player query: “Show receptions between lines under pressure followed by forward progression.”
4. Open the top result and point to timestamp, event chain, player/unknown identity, pitch context, evidence frames and uncertainty.
5. Correct one tag and show how that feedback is saved without silently rewriting past results.

### 7:00–12:00 — American-football mode

1. Switch to **Football**; show that the filters and report schema change.
2. Run: “Third-and-medium, 11 personnel, fast motion; group by visible coverage shell.”
3. Open a play and point to down/distance, hashmark, formation, motion, snap boundary, visible defensive evidence, result and view limitation.
4. Show synchronized views only if the demo data genuinely contains them.

### 12:00–15:00 — Demonstrate restraint

Use one intentionally ambiguous clip. The system should say that player identity, coverage or tactical intent is unresolved, then show why. This is more persuasive to technical and coaching audiences than hiding a failure.

### 15:00–18:00 — Compare with the baseline

Show the same frozen query completed through the current/manual baseline and the prototype. Compare elapsed time, top-five relevance and missed clips. Do not show a performance percentage that lacks a visible numerator, denominator and held-out set.

### 18:00–20:00 — Make one bounded ask

Ask for a 45-minute workflow interview and permission to define—not yet run—the four-week shadow pilot on a small approved set. Ask the program to name a workflow owner and a media/compliance approver. Do not ask for the whole archive in the room.

## 9. Adoption risks and controls

| Risk | Why it matters | Pilot control |
|---|---|---|
| Publicly viewable but unlicensed media | Viewability does not establish permission to copy, train or redistribute | Require a per-source rights record; use university-approved or explicitly licensed media only |
| Competitive secrecy | Practice/game film and playbook-linked labels are sensitive | Local/approved processing, least-privilege access, no public demo of private clips, explicit deletion/export policy |
| In-game rules | NCAA Rule 1-4-11-a permits specified in-game video on controlled tablets while excluding analytics/data access; a separate 2026 real-time replay-feed experiment is conference-optional | Keep v1 strictly post-game/practice; obtain compliance review before any live use ([current NCAA football-rules hub](https://www.ncaa.org/championships/playing-rules/football-playing-rules/); [NCAA explanation of the tablet rule](https://www.ncaa.org/media-center-technology-rules-approved-in-football/); [2026 FBS experimental replay rule](https://www.ncaa.org/fbs-oversight-committee-introduces-proposal-to-modify-football-calendar/)) |
| Camera/view insufficiency | Broadcast views can hide receivers, defensive shape, off-ball soccer runs or the ball | Carry a view-quality field; prefer coach-controlled wide/end-zone views; abstain when evidence leaves frame |
| Terminology mismatch | “Press,” “long ball,” “match quarters” or formation names can vary by staff | Let coaches define aliases and examples; version the taxonomy by program/season |
| Hallucinated player or tactical intent | A fluent wrong report damages trust and may affect athletes | Separate observation from interpretation; evidence links; unknown identity; calibration and abstention; human approval |
| Shortcut learning and leakage | Scoreboards, replay graphics, uniform/venue or same-game overlap can inflate evaluation | Game/opponent-aware splits, silent video tests, broadcast-state controls, adversarial examples and per-slice reporting |
| Workflow tax | A “smart” tool that creates extra tagging will be abandoned | Measure end-to-end task time; integrate with exports; make corrections faster than the current tag path |
| Player surveillance/mental-health impact | NCAA warns performance technology can have unintended health and mental-health effects | No medical, injury, personality, effort or roster inference; written data plan; stakeholder education and appeal/correction path |
| Model drift | Rosters, terminology, schemes and camera setup change | Version by season, monitor abstention/error slices, revalidate before expanding categories |

## 10. The UMD pitch

### One-sentence version

“We are building a local, evidence-first search layer for game and practice video: coaches ask in their own language, get the exact clips and structured context back, and remain in control of every label and decision.”

### Soccer version

“SoccerMaster gives us a research starting point for soccer-specific visual evidence. We want to test whether that evidence can help Maryland coaches retrieve phases, transitions, player actions and practice-to-match examples that fixed event tags miss.”

### American-football version

“Football Master is not a renamed soccer model. It uses football's own units—play boundary, situation, personnel, formation, motion, coverage evidence and result—to accelerate cutups and self-scout while preserving the original film.”

### What not to say

- Do not say the system “understands the whole game.”
- Do not call author-reported paper metrics locally reproduced.
- Do not claim public broadcast footage is automatically legal training data.
- Do not imply the tool replaces analysts, coaches or the existing video platform.
- Do not promise player identification when jersey/view evidence is weak.
- Do not present commentary, scoreboard graphics or play-by-play text as independent visual ground truth.
- Do not propose sideline deployment until compliance and the relevant conference/game rules are confirmed.

## 11. Further questions that determine whether to proceed

1. Which UMD program is willing to supply the first coach-authored query set and adjudicator time?
2. Can the existing system export timestamps, tags and synchronized views without violating vendor or conference terms?
3. Does the institution require all inference to remain on university-controlled hardware?
4. Which two use cases have enough value and low enough error cost for the first pilot?
5. What footage and derived annotations may be used for training, retained after the pilot or shown outside the team?
6. Can the project construct a true held-out evaluation by game/opponent/season before any adaptation?
7. Who owns correction of player identity, playbook terminology and disputed tactical labels?

## 12. Source inventory

All sources below were accessed August 27, 2026. Current-role claims should be rechecked immediately before any presentation because athletic staffs change.

### University of Maryland

- University of Maryland Athletics, [2026 Football Coaches](https://umterps.com/sports/football/coaches/2026).
- University of Maryland Athletics, [2026 Men's Soccer Coaches](https://umterps.com/sports/mens-soccer/coaches).
- University of Maryland Athletics, [2026 Women's Soccer Coaches](https://umterps.com/sports/womens-soccer/coaches).
- University of Maryland Athletics, [Staff Directory](https://umterps.com/staff-directory).

### Governing bodies and official coaching-analysis material

- FIFA Training Centre, [The FIFA Football Language](https://www.fifatrainingcentre.com/en/game/performance-analysis/football-language-analysis/the-fifa-football-language.php).
- FIFA Training Centre, [Phases of Play](https://www.fifatrainingcentre.com/en/fwc2022/efi-metrics/efi-metric--phases-of-play.php).
- FIFA Training Centre, [David Aznar on training and match application](https://www.fifatrainingcentre.com/en/environment/expert-knowledge/david-aznar-on-training-and-match-application.php).
- U.S. Soccer, [U.S. WNT Benefits from Expanded High Performance Department](https://www.ussoccer.com/stories/2018/09/us-wnt-benefits-from-expanded-high-performance-department).
- U.S. Soccer, [Five Things to Know About USMNT Head Coach B.J. Callaghan](https://www.ussoccer.com/stories/2023/05/five-things-to-know-about-usmnt-head-coach-bj-callaghan).
- NFL Football Operations, [How NFL officials use All-22 footage](https://operations.nfl.com/rules-officiating/officiating/performance-evaluation/).
- NFL, [When it comes to film study, coaches have entered the digital age](https://www.nfl.com/news/when-it-comes-to-film-study-coaches-have-entered-the-digital-ag-09000d5d80c3eb01).
- NCAA, [Current NCAA football playing-rules hub](https://www.ncaa.org/championships/playing-rules/football-playing-rules/).
- NCAA, [Technology rules approved in football](https://www.ncaa.org/media-center-technology-rules-approved-in-football/).
- NCAA, [2026 FBS instant-replay video-feed experimental rule](https://www.ncaa.org/fbs-oversight-committee-introduces-proposal-to-modify-football-calendar/).
- NCAA, [Performance technology guidance approved by CSMAS](https://www.ncaa.org/media-center-performance-technology-guidance-approved-by-csmas/).

### Sports-video research

- Deliège et al., [SoccerNet-v2: A Dataset and Benchmarks for Holistic Understanding of Broadcast Soccer Videos](https://openaccess.thecvf.com/content/CVPR2021W/CVSports/html/Deliege_SoccerNet-v2_A_Dataset_and_Benchmarks_for_Holistic_Understanding_of_Broadcast_CVPRW_2021_paper.html), CVPR Workshops 2021.
- SoccerNet, [Action Spotting task and taxonomy](https://www.soccer-net.org/tasks/action-spotting).
- Yang et al., [SoccerMaster official project](https://haolinyang-hlyang.github.io/SoccerMaster/) and [paper](https://arxiv.org/html/2512.11016), CVPR 2026.
- Atmosukarto et al., [Automatic Recognition of Offensive Team Formation in American Football Plays](https://openaccess.thecvf.com/content_cvpr_workshops_2013/W19/html/Atmosukarto_Automatic_Recognition_of_2013_CVPR_paper.html), CVPR Workshops 2013.

## Caveats and assumptions

- This memo does not report any interview with a UMD coach and does not claim access to UMD internal footage, tools or workflows.
- The named staff and roles come from public 2026 pages as of the access date; they may change.
- The pilot sizes and metric gates are starting proposals, not statistically powered performance claims.
- The memo makes no legal determination about footage, model-provider terms, student records, biometric data or intellectual property. UMD's authorized offices must decide those questions.
- Research feasibility does not equal coach usefulness. The pilot's primary outcome is workflow value under trustworthy evaluation, not a demo that produces plausible prose.
