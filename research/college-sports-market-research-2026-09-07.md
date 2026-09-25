# College soccer technology: landscape and discovery plan

Internal research draft, 7 September 2026. Sources checked on that date; this is a bounded primary-source review, not a purchasing survey or a promoted deliverable. Source classifications and claim limits are recorded in [the source ledger](../artifacts/college-sports-market-20260907/source-ledger.json).

Start with a **read-only, post-game college soccer workflow study**. Existing products already cover substantial parts of capture, analysis and athlete monitoring. The promising question is whether an evidence-grounded assistant can help staff find and verify useful examples within their current workflow. An unmet need, willing partner, accessible data and institutional permission remain hypotheses. The supplied context establishes an inquiry about technology and observational access; it establishes no reply, introduction or permission. No private chat is reproduced here.

## What the sources establish

| Layer | Current primary-source evidence | Interpretation for this project |
| --- | --- | --- |
| Video capture and review | Hudl markets soccer cameras, video sharing, Sportscode, Replay and Insight. Its December 2023 Portland women's soccer story describes use of its suite. [Hudl soccer](https://www.hudl.com/sports/soccer), [Portland story](https://www.hudl.com/blog/portland-pilots-hudl-and-the-resurgence-of-a-soccer-power). | Capture, clips and dashboards are established product categories. The vendor's named customer example does not establish present contracts, prevalence or a complete team stack. |
| Event tagging and analysis | Assist links statistics to video. Its FAQ says analysts remain central for most sports; soccer Assist+ adds player and location detail. [Assist FAQ](https://www.hudl.com/products/assist/faq). | Compare with the team's actual tagged-video search and human analyst workflow. Do not describe all existing analysis as manual or all Assist as autonomous AI. |
| Portable capture and export | Veo Cam 3 requires an active subscription per camera for Editor access; downloads are offered above Starter. Upload/processing time depends on connection and recording length. [Veo](https://www.veo.com/product/veo-cam-3). | A team owning a camera does not establish an export entitlement or research-processing permission. Confirm its exact plan and one usable export before building an adapter. |
| Physical monitoring and data management | Catapult's June 23, 2026 Furman men's soccer story reports daily Vector Core/OpenField use for load, high-speed running and distance. UMD's athletics internship page lists VALD, Catapult GPS, Smartabase and Power BI. [Furman](https://www.catapult.com/blog/furman-university-mens-soccer-ncaa-division-i-catapult-vector-core), [UMD](https://umterps.com/sports/2024/9/17/internship-opportunities). | Furman is a vendor-authored adoption example, not causal evidence of fewer injuries or better results. UMD is an institutional department-level technology statement; current UMD soccer and Georgetown soccer configurations remain unverified. |

Hudl also markets Wyscout and Statsbomb for soccer scouting/data, and Titan/Signal for monitoring. These are product capabilities, not proof that any target team has the subscriptions. This crowded landscape argues for an integration experiment; it does not prove there is no remaining product opportunity. [Hudl soccer](https://www.hudl.com/sports/soccer).

## College versus high school and youth

Use college soccer as the initial discovery segment because it matches the existing project and potential local contacts. Include different staff/resource situations, men's and women's teams where access allows, and record division explicitly. Do not generalize from Division I or one university to all colleges.

For high school and youth, separately test who operates the camera, who prepares clips, who buys subscriptions, how often coaches review video, and how athlete/parent access is controlled. Lower staffing or budget, greater portability needs and different consent arrangements are discovery hypotheses, not measured segment facts. Hudl explicitly addresses club, high-school and college organizations; this establishes vendor segmentation, not relative adoption or willingness to pay. [Hudl soccer](https://www.hudl.com/sports/soccer).

Collect total workflow cost from participants: staff time, camera, subscriptions, analysis add-ons, storage and exports. Do not infer budgets from division labels, use vendor global customer counts as a soccer market size, or manufacture a TAM. A small convenience sample can guide a pilot but cannot estimate prevalence.

## American football: a separate comparison

Hudl IQ advertises collegiate recruiting, preparation and self-scouting, including formation/route/coverage/blitz classification and play finding. These are vendor claims about a different sport and ontology, with no performance reproduction here. [Hudl IQ](https://www.hudl.com/products/football-iq).

Football discovery should examine play-indexed cutups and situation-specific retrieval separately from soccer's continuous possessions and transitions. NCAA's 2026 Division II and Division III communications address permissive coach-to-player helmet communication and a 15-second cutoff. They do **not** establish permission for this project's live AI analysis. Keep any pilot post-game; a later live-use proposal needs a sport-, division- and competition-specific rules assessment. [Rules hub](https://www.ncaa.org/championships/playing-rules/football-playing-rules/), [DII memo](https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/2026PRMFB_D2CoachToPlayerTechnologyUpdateMemo.pdf), [DIII memo](https://ncaaorg.s3.amazonaws.com/championships/sports/football/rules/Feb2026PRMFB_DIII_Coach_to_Player_Communication.pdf).

## Concrete hypotheses and technical limits

1. **Retrieval utility:** natural-language requests may reduce the time needed to assemble verified teaching clips compared with existing filters and manual search. Observe real requests first, including repeated events, close distractors and cases with no match. Count incorrect inclusions, missed examples and final verification time.
2. **Grounding and abstention:** answer-linked timestamps and pitch evidence may improve reliable acceptance compared with fluent answers alone. A video crop may omit the relevant player or ball; unavailable evidence must cause abstention. GPS load is not itself a tactical explanation, and sensor/video correspondence needs validated identity and time alignment.
3. **Integration burden:** an assistant may be useful only if staff can export and reimport without substantial cleanup. Existing integration already exists: Catapult documents Sportscode XML imports into OpenField and period-start alignment. Do not sell basic synchronization as a new invention. Confirm versions, fields, clock resets and a reversible round trip. [Catapult support, updated October 8, 2024](https://support.catapultsports.com/hc/en-us/articles/360000516855-Hudl-SportsCode-Data-Import).

Test broadcast-to-training-camera transfer explicitly; do not assume a soccer representation handles a different viewpoint, resolution or event distribution. Report visibility/calibration failures separately from semantic mistakes. These are proposed engineering and measurement requirements, not observed failures of the named products.

## Access plan and decisions

Prepare a 45-minute interview and, if invited, one staff-led observation of a routine post-game review. Ask the coach, video analyst and performance/data owner about an actual recent task: input footage, tags, search steps, handoffs, corrections, destination and turnaround. Identify the account administrator and permitted export formats. UMD's published sport-science internship pathway is a potential institutional route, not guaranteed placement, soccer access or a substitute for research approval. [UMD opportunities](https://umterps.com/sports/2024/9/17/internship-opportunities).

Propose discovery in two college programs before a build decision, with high-school/youth conversations treated as a separate exploratory sample. This is a planning target, not a powered study. Record observations with participant agreement; screen sharing does not authorize copying footage or sending it to a model. Obtain explicit institutional/media-processing scope before data collection, plus the relevant human-participant review determination before a publishable study. Do not request health records or autonomous coaching authority.

**Go to a bounded pilot** only when staff demonstrate a recurring unresolved task, name a workflow owner, and authorize a usable sample/export and evaluation. Freeze the incumbent baseline, practical time benefit, acceptable error/coverage limits and resource budget with that partner. **Stop or narrow** if current tools already solve the task adequately, data cannot be used, or verification and integration costs erase the benefit. Observation and willingness to participate are not willingness to buy.

## Research and loop implications

Product demand and doctoral contribution require different evidence. SoccerMaster already studies a unified soccer visual representation; NExT-GQA already couples answers with temporal evidence. Neither their authors' claims nor a new chat interface establish this project's novelty. [SoccerMaster v2, May 7, 2026](https://arxiv.org/abs/2512.11016), [NExT-GQA](https://github.com/doc-doc/NExT-GQA).

A defensible candidate contribution remains a tested conjunction of question-specific soccer evidence, calibrated abstention and reduced expert verification burden. Require a broader nearest-work audit, frozen baselines/ablations, independent blinded annotation with adjudication, original-match/team-held-out evaluation, uncertainty clustered by source and participant, and all failure/abstention denominators. Choose sample size after development variance and a practical effect are specified; tiny pilots cannot certify generalization or PhD quality.

Give the loop three bounded outputs: a staff-verified workflow map, one authorized adapter feasibility receipt, and a preregistered comparison design. Version facts and hypotheses separately. Do not turn repeated vendor browsing into claimed adoption evidence; update when a relevant source changes or an observation closes a specific unknown. No contact, data acquisition, inference, Doc write or runtime mutation was performed for this draft.
