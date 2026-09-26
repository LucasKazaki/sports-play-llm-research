# Soccer data expansion and evaluation plan

**Prepared:** 30 August 2026  
**Scope:** rights-aware next data step for SoccerMaster / PlayGround. This is a plan and local metadata audit, not an acquisition authorization, a license opinion, a new model result, or a performance claim.

## Answer first

The strongest immediate improvement is not an uncontrolled web scrape. It is to use the already authorized local SoccerNet corpus correctly, add its locally present SoccerNet-Echoes metadata only as a sealed post-hoc modality, and reserve genuinely new match groups for the next untouched test.

The current local corpus contains **9 complete SoccerNet game groups, 18 halves, 50,120 seconds (13.9222 hours), and 3.407 GB**. Four groups (6.1956 h) are current training groups and two (3.0619 h) are development groups. The existing two legacy test groups and one long-form frozen test group are valuable historical diagnostics, but they have already informed prior experiments and are not a fresh test for a new model/prompt selection.

Every current authorized game has local `whisper_v3` SoccerNet-Echoes coverage: **18 half files and 16,024 automatically generated ASR segments**. That supports a larger visual-only / text-only / late-fusion comparison without downloading any new media. It is not a substitute for human ground truth.

Audit artifacts:

- [authorized local corpus inventory](../artifacts/soccer-data-expansion-audit-2026-08-30/local-authorized-corpus-inventory.json)
- [metadata-only ASR overlay manifest](../artifacts/soccer-data-expansion-audit-2026-08-30/local-asr-overlay-manifest.json)
- [SoccerDB overlap audit](../artifacts/soccer-data-expansion-audit-2026-08-30/soccerdb-overlap-audit.json)

## Local data-quality findings

| Finding | Evidence | Risk | Decision |
|---|---|---|---|
| Authorized corpus is materially larger than the original clip pilot | 9 full game groups / 13.9222 h, hash-bound and private | None; it is already available but must remain local | **GO** for development on the existing training/development groups |
| Existing held-out groups are no longer new | 2 legacy test games and 1 long-form frozen test game were used in prior studies | Reusing them after model/prompt changes would overstate generalization | **NO-GO** as a newly untouched evaluation set |
| Current corpus has a single league-family concentration | All current core games come from the same league family | High domain-shift and shortcut risk | New cohort must span provider metadata strata where available |
| Rare labels are underrepresented | The existing training pool has only one penalty example; several classes are sparse | Any claim on rare events would be unstable | Use class-aware sampling and report class denominators; do not claim rare-event competence |
| Current official labels do not encode much of the requested coaching language | SoccerNet-v2 point labels cover 17 broadcast actions, not player identity, long-ball intent, tactical shape, or detailed outcome prose | A fluent report cannot be evaluated by the current labels alone | Add atomic human report/evidence annotations before coach claims |
| SoccerNet-Echoes is a weak, derived modality | 16,024 local ASR segments; its card warns of ASR error, repetition, and lack of human verification | Audio agreement can be mistaken for correctness | Use it post hoc or as a separately scored text-only branch only |
| SoccerDB cannot enrich this corpus as-is | Zero of the 18 authorized halves exactly matches the local public mapping | Incorrect cross-dataset join would silently mislabel video | **NO-GO** for current training/evaluation use |

The all-zero SoccerDB finding is important: its local CSVs are useful metadata, but its `seg_info.csv` must not be joined to these nine games. No SoccerDB video or labels were acquired in this audit.

## Candidate source groups

### 1. Existing authorized SoccerNet games + local SoccerNet-Echoes overlay — immediate GO

Why it is admissible:

- The project already records user-authorized SoccerNet NDA access for local, non-commercial research, with media kept below `data/private` and no redistribution.
- SoccerNet says the NDA controls copyrighted video redistribution, permits model training, permits source-attributed research/presentation screenshots or clips, and forbids commercial video use. [SoccerNet FAQ](https://www.soccer-net.org/faq)
- The SoccerNet-Echoes dataset card states CC BY 4.0 and describes timestamped automated commentary transcriptions. [SoccerNet-Echoes dataset card](https://huggingface.co/datasets/SoccerNet/SN-echoes)

What it adds:

- No new video duration, but 18 aligned ASR half files / 16,024 time-stamped text segments across every available game.
- A rigorous modality design: visual-only, text-only, and late-fusion variants can be separately frozen and scored.

Required evaluation rule:

1. Freeze visual reports and their timestamps first.
2. Freeze the ASR-only output separately.
3. Only then compare support / contradiction / uninformative relations.
4. Never alter a visual report after reading ASR, and never call ASR agreement ground truth.

This directly addresses the current project's commentary caveat instead of hiding it.

### 2. New, distinct official SoccerNet whole-game cohort — best next visual-data acquisition, approval required

Why it is technically strongest:

- SoccerNet's official catalog lists 500 + 50 broadcast videos at 25 fps and 720p or 224p, alongside labels, features, captions, tracking, and other task data. [SoccerNet data catalog](https://www.soccer-net.org/data)
- It is the closest distributional continuation of the existing local corpus and preserves match-grouped splits and private local inference.

Why this lane did not acquire it:

- This audit has not downloaded restricted video, reused credentials, or accepted additional terms. New media still requires the authorized operator to make the source-specific acquisition decision.

Recommended cohort sizes, estimated from the current corpus's observed average of 1.5469 h and 379 MB per game:

| New cohort | Approx. video duration | Approx. storage | Pre-frozen split | Interpretation |
|---|---:|---:|---|---|
| Minimum viable | 12 games | 18.6 h | 7 train / 2 dev / 3 untouched test | Feasibility study only |
| Recommended | 24 games | 37.1 h | 14 train / 5 dev / 5 untouched test | Still limited, but supports match-grouped uncertainty better |

The 24-game cohort should be selected by official split/league/season metadata before watching action content. No game, half, team, or source group may cross train, development, or test. Create an opaque pre-acquisition manifest, acquire to `data/private` only, fully decode and hash both halves, and open labels only according to a pre-registered evaluation stage.

### 3. SoccerNet-Caption — strongest label-aligned curriculum source, approval required

Why it is promising:

- The official SoccerNet-Caption repository defines the relevant task: timestamped natural-language descriptions of soccer actions. It reports 471 captioned broadcast-game videos and 42 separate challenge games, plus anonymized and identified comment variants and 2 fps features. [Official SoccerNet-Caption repository](https://github.com/SoccerNet/sn-caption)
- This is much closer to the requested detailed, searchable report than turning sparse action-point labels into invented prose.

Safe use plan:

- Treat it as a supervised caption/localization task, not proof of coach usefulness.
- Prefer anonymized captions for an initial language-style curriculum; store the exact source version, variant, and split.
- Keep caption-text training data, video input, validation, and untouched test groups separate. Do not tune on challenge data.
- Evaluate generated reports on timestamp localization, caption fidelity, and a new human factuality/evidence rubric separately.

Gate: confirm the exact current task release, download terms, caption variant, and local-only policy before acquiring annotations/features or video.

### 4. SoccerNet Ball Action Spotting — high-value action vocabulary for passes/high passes, approval required

Why it is promising:

- The official task has 7 fully annotated English Football League games and 2 challenge games, with 12 fine-grained ball-action classes: Pass, Drive, Header, High Pass, Out, Cross, Throw In, Shot, Ball Player Block, Player Successful Tackle, Free Kick, and Goal. [Official Ball Action Spotting task](https://www.soccer-net.org/tasks/ball-action-spotting)
- `High Pass` is a defensible, narrower proxy candidate for part of the user's “long ball” need. It is not the same as a coach-defined long ball, and the task has no offside/foul labels.

Safe use plan:

- Use 5/1/1 game-grouped training/dev/test rotation or complete out-of-fold evaluation across the seven labeled games; preserve the two challenge games untouched.
- Report per-class denominators and mAP@1 only for the official spotting task; do not convert the label into detailed prose truth.
- Use it to train or test a dedicated event-proposal module, not a hidden algorithm that overwrites the VLM's report.

### 5. SoccerNet Game State Reconstruction — evidence-only auxiliary evaluator, approval required

Why it is promising:

- The official development kit describes 200 annotated 30-second clips with player/referee/ball spatial information, role, team, and jersey-number targets. [Official SoccerNet-GSR repository](https://github.com/SoccerNet/sn-gamestate)
- It supports a separate test of spatial evidence rather than claiming that a text report's proposed player relation is grounded.

Boundary:

- Keep GSR as a declared auxiliary perception/evidence stage with its own metrics; never use its output as a hidden event-labeler.
- Do not expose player names or jersey numbers in reports unless the specific evidence task and evaluation establish them.

### 6. File-level Wikimedia Commons soccer video — rights-safe external-domain stress slice, conditional GO

One concrete candidate exists: [Ajax v Utrecht, December 2024](https://commons.wikimedia.org/wiki/File:Ajax_v_Utrecht_Dec_2024_edited.webm). Its file page records a 21:36, 3840×2160 fan-video excerpt, named author/source, and CC BY 3.0 license with an on-page license review. It is not a complete broadcast, has no gold event labels, and carries a visible-watermark warning. Therefore it is useful only as a **small external qualitative / abstention stress slice**, not as a training corpus or accuracy benchmark.

Wikimedia itself emphasizes that reuse must be verified file by file, with attribution/license compliance and consideration of privacy, personality, and other non-copyright restrictions. [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)

If later approved, the source record must retain the exact file-page revision, original URL, creator, license version, attribution string, SHA-256, watermarks/privacy review, and intended use. Do not treat an arbitrary YouTube URL as reusable because it is publicly viewable.

### Not admitted now

- **SoccerDB raw video:** the local public metadata has 492 mapping rows and 142,575 segment rows, but none map exactly to the present 9-game corpus. Its README says SoccerDB video needs a separate agreement path. It is not an immediate data expansion.
- **Commercial TV/social uploads:** public visibility is not permission. No famous-game broadcast source is admissible without an explicit compatible license or rights-owner permission.
- **Coach/Huddle/UMD footage:** this may be the most relevant eventual domain, but it needs written owner, privacy, retention, upload, and derivative-output authorization before any use.

## Recommended next protocol

### Phase 0 — run now, no new media

1. Lock the current 9-group inventory and ASR overlay with the accompanying verifier.
2. Restrict model/prompt development to the existing train + valid groups (6 groups / 9.2575 h).
3. Define a three-branch modality protocol: visual-only; text-only; late-fusion. All branches receive the same opaque windows and are evaluated separately.
4. Add a human-created atomic annotation rubric for a future untouched test: visible actor/role, action, outcome, live vs replay, interval, image/pitch evidence, report answerability, and coach-query relevance.

### Phase 1 — author-approved official expansion

1. Select 24 new whole-game source groups by provider metadata alone.
2. Freeze a 14/5/5 game-grouped split before media/labels are inspected.
3. Hash and full-decode every half; retain a source receipt and no public media paths.
4. Build matched positive, background, replay, and semantically close hard-negative windows within each split.
5. Require two independent annotations plus adjudication on all untouched-test atomic items.

### Phase 2 — model improvement that can be believed

1. Train/adapt only on development games; retain an untouched five-game test.
2. Compare (a) direct VLM, (b) VLM plus a declared evidence module, and (c) caption/event proposal baselines on identical held-out windows.
3. Report structural reliability, event correctness, evidence correctness, abstention/selective risk, retrieval precision@k, and human verification time separately.
4. Treat long-ball, press, tactical-shape, and player-specific claims as **new annotation tasks**. Do not infer them from a sparse label map.

## Handoff to the VLM-improvement lane

The local manifest authorizes this immediate experimental boundary:

- Development: opaque groups currently marked `train` (4) and `valid` (2).
- Historical diagnostics only: opaque groups currently marked `test` (2) and `longform_test_frozen` (1).
- Modality metadata: `whisper_v3`, 18 aligned files / 16,024 ASR segments; score it post hoc or as a separate branch only.
- New comparable held-out result: requires new group IDs not in this artifact.

## Sources and caveats

- [SoccerNet data catalog](https://www.soccer-net.org/data) — official task/data descriptions; it does not replace the applicable NDA for video.
- [SoccerNet FAQ](https://www.soccer-net.org/faq) — states video copyright, non-commercial research boundary, training/presentation guidance, and anti-redistribution purpose of the NDA.
- [SoccerNet-Echoes dataset card](https://huggingface.co/datasets/SoccerNet/SN-echoes) — CC BY 4.0 source record and explicit ASR/hallucination limitations.
- [SoccerNet-Caption](https://github.com/SoccerNet/sn-caption) — official dense-caption task and resource description.
- [SoccerNet Ball Action Spotting](https://www.soccer-net.org/tasks/ball-action-spotting) — official 7+2-game / 12-class task description.
- [SoccerNet-GSR](https://github.com/SoccerNet/sn-gamestate) — official spatial-evidence task description.
- [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en) and the [candidate file page](https://commons.wikimedia.org/wiki/File:Ajax_v_Utrecht_Dec_2024_edited.webm) — per-file licensing evidence, not blanket permission for arbitrary uploads.

This document does not give legal advice. New external acquisition, hosted processing, public release, or manual annotation requires the project owner and any applicable institutional/data-owner approval.
