# Official / licensed real-video data options for play search

**Scope.** This is a source-and-evaluation decision note for a VLM-only sports-play search project. It was researched on 2026-08-30; no media, credentials, or gated files were downloaded while preparing it. “Usable” means the media itself is released by the dataset owner under stated terms—not merely that a paper, feature file, or public video URL exists.

## Decision summary

| Priority | Source | What is actually available | Rights / access status | Appropriate role |
|---|---|---|---|---|
| 1 | [SoccerNet Action Spotting](https://www.soccer-net.org/tasks/action-spotting) + existing approved SoccerNet media | 500 broadcast games, with timestamped **Offside**, **Foul**, corner, free-kick, goal, and 12 additional event labels | Research-only broadcast video; video download requires the SoccerNet NDA. SoccerNet explicitly forbids commercial use and redistribution. | Primary long-form soccer retrieval benchmark; closest match to the requested queries. |
| 1 | [SoccerNet-Caption](https://github.com/SoccerNet/sn-caption) and [SoccerNet-Echoes](https://github.com/SoccerNet/sn-echoes) | Caption has 471 broadcast videos with timestamped textual commentaries; Echoes provides timestamped ASR/translation sidecars | Caption video remains NDA-gated. Echoes is an automatically generated transcript, not human ground truth. | Detailed-report evaluation and **sealed post-hoc** commentary audit; never give commentary to the VLM when judging the same clip. |
| 1 | [SoccerNet-MV Foul](https://github.com/SoccerNet/sn-mvfoul) | 3,901 foul actions, each with at least two live views plus a replay; 10 referee-oriented properties | NDA/password required; validate that the project’s permitted SoccerNet access covers this task before acquiring it. | Fine-grained foul report / severity study, separate from long-game search. It is clip-based, not a full-game corpus. |
| 2 | [SoccerTrack v2](https://github.com/AtomScott/SoccerTrack-v2) | 10 real, full-length panoramic 4K university matches; per-frame pitch coordinates, roles, teams, jersey-based IDs, and 12 ball-action labels | Dataset media and annotations are stated as [CC BY 4.0](https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA); the authors distribute through Hugging Face / Google Drive. Confirm current access and record the release revision before download. | Best open soccer complement for player-specific and tactical queries. Use as a cross-camera-domain held-out study, not as evidence that broadcast performance transfers. |
| 2 | [SportsTime](https://github.com/ustiniansy/SportsTime) | 1,575 videos across soccer and American football; 208 full games (~50 min each), 14,326 open-ended QA pairs, and 50,000+ timestamp/span evidence references | Videos, official video-level split, and annotations are CC BY-NC 4.0 but gated; access is manually reviewed for non-commercial research/education. | The strongest cross-sport, long-form VLM research candidate after access is granted. Use its official video-level split unchanged. |
| 2 | [AnyGroundBench](https://huggingface.co/datasets/rinost081/AnyGroundBench) | Newly captured amateur American-football videos with natural-language queries and dense spatio-temporal grounding annotations; 2.98 GB total benchmark | CC BY-NC-SA 4.0, directly hosted by the benchmark. | Small but lawful football VLM grounding benchmark for run/pass/punt/field-goal/kickoff-style queries; **not** a whole-game search corpus. |

## Sources that are useful, but not direct media sources

- [SoccerNet Ball / Team Ball Action Spotting](https://github.com/SoccerNet/sn-spotting) supplies dense 12-class ball-action labels (including pass, high pass, cross, free kick, and goal) over a small set of full games. It is useful for pass/high-pass localization, but “high pass” is not a validated synonym for “long ball.” Treat it as a separate task definition.
- [SoccerNet-v3](https://github.com/SoccerNet/SoccerNet-v3) supplies action/replay frames, pitch lines, player boxes, teams, and jersey numbers. It can evaluate identity/field grounding around annotated moments, but it is images—not a substitute for long video.
- [NFL Big Data Bowl](https://operations.nfl.com/programs-initiatives/innovation/big-data-bowl) provides official player-tracking data, not a video corpus. It can be a nonvisual sidecar or a future alignment study, but must not be described as VLM training footage or used to manufacture visual event labels.
- [NFL Player Contact Detection](https://www.kaggle.com/competitions/nfl-player-contact-detection/overview) is an NFL-hosted historical competition for contact detection from sensor and video data. It is a potential narrowly scoped contact study only after the current competition/data terms are accepted and archived; it is neither an open full-game corpus nor a general play-search benchmark.
- [SVHighlights](https://huggingface.co/datasets/idong1004/SVHighlights) releases non-commercial features/annotations and public source URLs, but expressly does **not** redistribute broadcasts and leaves video use to the original publisher’s terms. Do not fetch its URLs as a workaround for footage rights.
- [SoccerDB](https://github.com/newsdata/SoccerDB) is a useful historical research/code reference, but its public README does not establish a media license or an exact join to the project’s SoccerNet manifest. Do not treat it as an approved video source without a source-specific rights and identity review.
- [NFL Films](https://www.nflfilms.com/licensing/footage_licensing) states that use of NFL-controlled footage requires express written consent in a contract. NFL+ / All-22 access, public clips, and third-party broadcast uploads are therefore not a data-acquisition route for this project.
- [MUVY](https://doi.org/10.5281/zenodo.13883315) is promising real, multi-view user-generated soccer/American-football footage with frames and spatial annotations; its 2026 data paper says the source videos were Creative-Commons-licensed. The currently surfaced Zenodo v1 page does not state a dataset license and covers American football but not soccer. Treat the newer release as **pending per-file licence and provenance verification**, not as an approved download yet.

## Acquisition gates (apply before any download)

1. Record the source URL, dataset version/revision, media license or signed access condition, and allowed purpose in a private receipt. Do not copy credentials into logs, code, slides, or reports.
2. Freeze a **game-level** train/validation/test split before running a model. Never split windows from one game across development and test.
3. Hash the downloaded manifest and retain only opaque IDs in public artifacts. Do not redistribute private SoccerNet or gated SportsTime clips.
4. Confirm that the footage is real media and that the expected annotations join on the same game/clip IDs before a result is called an evaluation.
5. Keep sports separate: a soccer label/schema/prompt must not silently become an American-football one. Shared infrastructure may sample, cache, and score; sport semantics, taxonomies, and held-out splits remain separate.

## Recommended acquisition and evaluation sequence

### Soccer

1. **Recover the official SoccerNet route first.** It already covers requested offside and foul events at full-game scale; the [official data page](https://www.soccer-net.org/data) confirms broadcast video, labels, caption labels, tracking, and related task data are available through its package. Do not substitute unlicensed television uploads if that route is temporarily unavailable.
2. Add only the relevant annotation layers: Action Spotting for broad event retrieval, Caption/Echoes for report-language audit, and MV-Foul for incident detail. Put any commentary-derived field behind a post-hoc seal so the model cannot answer from commentary leakage.
3. Acquire SoccerTrack v2 as an **open-domain companion**, not a replacement. It supports reports such as “jersey X makes a high pass at time T” where its annotations actually support those fields. It does not validate offside or foul claims, and its panoramic amateur-camera domain differs from broadcast TV.
4. Evaluate a detailed VLM report as structured evidence: `sport`, `time span`, `event taxonomy term`, `visible actors / jersey only when grounded`, `visual evidence`, `uncertainty`, and `abstain reason`. Score (a) temporal retrieval against frozen labels, (b) field-level support, and (c) unsupported-detail rate. A label or ASR match alone is not evidence that every generated detail is true.

### American football

1. Start with **AnyGroundBench** for an inexpensive, legal, reproducible VLM grounding run. Its training subset may be used for adaptation; its test subset must remain untouched until the final run. Report temporal/spatial grounding metrics rather than claiming coach-ready whole-game search.
2. Submit a non-commercial research access request for **SportsTime**. If granted, use its official video-level split independently for soccer and football. Its time references enable evaluation of grounded multi-step reports, but do not feed test answers/evidence references into the evaluated model.
3. Do **not** claim an open, lawful, full-NFL-game corpus is available from this survey. A full-game American-football demo requires either SportsTime access, a separately licensed institutional/team corpus, or data collected with documented consent.

## Minimal professional experiment card

For every run, publish: source/revision and rights status; sport-specific split hash; the exact VLM and prompt; window/sample policy; no-call versus completed count; retrieval/localization metrics; blind field-level evidence audit; and a clearly labeled limitation. The right claim is “evidence-grounded research retrieval prototype” until a frozen, held-out evaluation supports more.

## References

- [SoccerNet data and rights FAQ](https://www.soccer-net.org/data), [SoccerNet Action Spotting task](https://www.soccer-net.org/tasks/action-spotting), and [SoccerNet FAQ](https://www.soccer-net.org/faq).
- [SoccerNet-Caption repository](https://github.com/SoccerNet/sn-caption), [SoccerNet-MV Foul repository](https://github.com/SoccerNet/sn-mvfoul), and [SoccerNet-Echoes repository](https://github.com/SoccerNet/sn-echoes).
- [SoccerTrack v2 repository](https://github.com/AtomScott/SoccerTrack-v2) and [dataset paper](https://arxiv.org/abs/2508.01802).
- [SportsTime repository](https://github.com/ustiniansy/SportsTime) and [gated dataset card](https://huggingface.co/datasets/Ustiniansy/SportsTime).
- [AnyGroundBench dataset card](https://huggingface.co/datasets/rinost081/AnyGroundBench) and [paper](https://arxiv.org/abs/2607.02269).
- [NFL Big Data Bowl](https://operations.nfl.com/programs-initiatives/innovation/big-data-bowl), [NFL contact-detection competition](https://www.kaggle.com/competitions/nfl-player-contact-detection/overview), and [NFL Films licensing terms](https://www.nflfilms.com/licensing/footage_licensing).
- [MUVY Zenodo record](https://doi.org/10.5281/zenodo.13883315) and [data paper](https://doi.org/10.1016/j.dib.2026.113003).
