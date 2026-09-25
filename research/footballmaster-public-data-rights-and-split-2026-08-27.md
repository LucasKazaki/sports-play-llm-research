# FootballMaster real-footage data: rights, quality, and source-held-out split

Accessed and audited 2026-08-27. Technical audience: the SportsPlayLLM research team and reviewers of the FootballMaster pilot.

## Technical summary

The project now has a **small, real, locally reproducible American-football video slice with explicit reuse evidence**: nine Wikimedia Commons-hosted clips, eight independent recorded-game/session groups, 21.94 MiB, and 151.893 seconds. Every downloaded 480p VP9 file has a unique SHA-256 and passes a complete FFmpeg decode-to-null. The split is 4 train / 2 validation / 3 test, and both values of the single supported learned target—`is_touchdown`—appear in every split.

This is enough to train and test a pipeline and to demonstrate source-held-out behavior. It is **not enough to claim a useful FootballMaster event recognizer or coach-grade performance**. Fine labels are Commons source-description weak labels with an agent contact-sheet plausibility check; none has been independently human-adjudicated. Formation, coverage, route, block, pressure, down/distance, yards after catch, and player-identity labels are absent.

Rights are deliberately fail-closed. All admitted file pages state CC BY or CC BY-SA licenses and permit copying and adaptation subject to their conditions. Local research training is approved; public model-weight release is held pending institutional/legal review of ShareAlike treatment, publicity/personality rights, trademarks, and any audio/music rights. Creative Commons' own AI-training guidance recommends a conservative approach to BY/SA compliance and specifically treats public sharing of a model trained on ShareAlike material as a question that may trigger ShareAlike obligations. [Creative Commons AI-training guidance](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)

## Nine clips pass provenance, integrity, and split checks

| Clip | Split | Whole-source group | Weak fine label | `is_touchdown` | License | Seconds |
|---|---|---|---|---:|---|---:|
| [Milton–Davis touchdown](https://commons.wikimedia.org/wiki/File:Milton_Touchdown_Pass_to_Davis.webm) | train | `fau-ucf-2018-09-21` | `touchdown_pass` | true | CC BY-SA 2.0 | 12.450 |
| [UCF–FAU kickoff](https://commons.wikimedia.org/wiki/File:UCF_Kickoff_(31018220288).webm) | train | `fau-ucf-2018-09-21` | `kickoff_return` | false | CC BY-SA 2.0 | 8.992 |
| [Devin Singletary touchdown](https://commons.wikimedia.org/wiki/File:Devin_Singletary_touchdown_(51394753691).webm) | train | `bills-bears-2021-preseason` | `rushing_touchdown` | true | CC BY 2.0 | 15.100 |
| [Field goal](https://commons.wikimedia.org/wiki/File:Field_Goal.ogv) | train | `field-goal-2011` | `field_goal_attempt` | false | CC BY-SA 3.0 | 4.060 |
| [Chiefs–Vikings touchdown](https://commons.wikimedia.org/wiki/File:Chiefs_at_Vikings_(53314593699).webm) | valid | `chiefs-vikings-2023` | `touchdown_pass` | true | CC BY-SA 2.0 | 19.667 |
| [Baker–Benedictine kickoff](https://commons.wikimedia.org/wiki/File:Kickoff_Baker_v_Benedictine_2014.webm) | valid | `baker-benedictine-2014` | `kickoff_return` | false | CC BY-SA 4.0 | 31.398 |
| [Chiefs–Buccaneers touchdown](https://commons.wikimedia.org/wiki/File:Buccaneers_at_Chiefs_(54133058812)-DeAndre_Hopkins_Touchdown.webm) | test | `chiefs-buccaneers-2024` | `touchdown_pass` | true | CC BY-SA 2.0 | 25.133 |
| [Justin Bethel minicamp interception](https://commons.wikimedia.org/wiki/File:Justin_Bethel_interception_from_minicamp_day_3.webm) | test | `falcons-minicamp-2018-06-14` | `interception_practice` | false | CC BY 3.0 | 13.805 |
| [SMU–Louisville touchdown](https://commons.wikimedia.org/wiki/File:Southern_Methodist_University_vs._Louisville_2025_touchdown_pass.webm) | test | `smu-louisville-2025` | `touchdown_pass` | true | CC BY-SA 4.0 | 21.288 |

The two UCF/FAU clips are from the same game and share one `source_id`; both remain in train. Every other asset has its own source group. No same-game or adjacent temporal windows cross train, validation, and test.

An exact lookup table is more informative than a chart for this nine-row audit: the decision depends on per-asset license and grouping, not on a distribution estimate. A chart would visually overstate the statistical weight of the corpus.

## What “rights-cleared” means—and what it does not mean

Wikimedia's reuse guidance says Commons material is generally reusable, but each file can impose different attribution, license-link, and ShareAlike requirements. It also distinguishes the uploader from the original creator, which is why the manifest preserves creator/source information rather than crediting Wikimedia. [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)

For this project, an asset is admitted only when all of the following are true:

1. The actual media is hosted on `upload.wikimedia.org` and has a canonical `commons.wikimedia.org/wiki/File:` description page.
2. The description page states CC BY or CC BY-SA, not merely “public,” “educational,” or “available.”
3. The license grants copying and adaptation; creator, license URL, immutable page revision, direct derivative URL, original hash, downloaded hash, and conditions are recorded.
4. The local example sets `rights_disposition=approved_for_local_research` and `training_allowed=true`.
5. Audio is excluded from model input. This avoids relying on commentary, music, or fight-song rights that were not separately audited.

This is permission-aware sourcing, not a warranty. Creative Commons explains that its licenses chiefly address copyright and do not necessarily clear third-party publicity, personality, privacy, trademark, or patent rights; licensors also provide material without a warranty that all embedded rights are cleared. [Creative Commons FAQ](https://creativecommons.org/faq/)

Practical disposition:

- **Local video-only research:** approved.
- **Showing short clips in an internal UMD research/coach demo:** technically feasible, but retain visible attribution and license access; confirm the meeting context before presentation.
- **Redistributing the corpus or derived clips:** allowed only with each license's attribution, link, change notice, and ShareAlike conditions.
- **Uploading to a third-party VLM/API:** not authorized by this manifest; approve processor terms and each asset's downstream use separately.
- **Publishing trained weights:** hold for UMD/institutional review, especially because seven of nine assets are ShareAlike.
- **Claiming team/player endorsement:** prohibited; none is implied.

## Data and metric definitions

- **Clip:** one downloaded Commons 480p VP9 derivative, used from timestamp 0 through its decoded duration.
- **Source group:** all clips from one recorded game or practice session. This is the split unit.
- **Weak fine label:** a coarse event named by the Commons file description, checked only for visual plausibility in six sampled frames.
- **Binary target:** `is_touchdown=true` for `touchdown_pass` or `rushing_touchdown`; false for `kickoff_return`, `field_goal_attempt`, or `interception_practice`.
- **Validation pass:** all required rights fields present, one-to-one agreement between source manifest and examples, file exists, byte count and SHA-256 match, full FFmpeg decode succeeds, hashes are unique, source groups occupy one split only, and both binary classes appear in each split.
- **Baseline for future evaluation:** report trivial majority-class accuracy (5/9 overall) and stratified/balanced metrics, but do not treat nine clips as an estimate of population performance.

## Verification method and result

The reproducible audit performs two independent media checks:

1. Sequential OpenCV decoding records dimensions, FPS, and observed frame duration while producing six-frame contact sheets.
2. FFmpeg decodes every video stream completely to a null sink; all nine return exit code 0.

The manifest verifier then recomputes every media SHA-256, matches it against both the manifest and media audit, enforces allowed license identifiers, enforces silent-video use, asserts that each `source_id` occurs in exactly one split, and verifies both target classes in train, validation, and test.

Result from `verify_manifest.py`:

| Check | Result |
|---|---|
| Manifest/example one-to-one agreement | pass |
| Nine media paths and byte counts | pass |
| Nine SHA-256 matches; nine unique hashes | pass |
| Nine full FFmpeg decodes | pass |
| Rights fields fail closed | pass |
| Eight source groups confined to one split | pass |
| Touchdown and non-touchdown in all three splits | pass |
| Audio disabled in all examples | pass |
| Weak-label truth boundary explicit | pass |

## The largest risk is scientific validity, not file integrity

### Critical: nine clips cannot establish coach-grade event recognition

Evidence: five touchdown positives and four heterogeneous negatives, with only one or two examples for most fine labels. A flexible classifier can memorize camera angle, venue, crowd reaction, end-zone geometry, or uniform color instead of learning the event.

Impact: any test accuracy is a **pipeline smoke result**, not a generalization claim. Fine-grained multi-class training is undefined because several classes have no independent train/validation/test support.

Remediation: acquire at least dozens of independent source groups per coarse class before model comparison, and hundreds per class before a coach-facing claim. Sample hard negatives from the same games and camera positions as positives.

### High: labels are weak and temporally coarse

Evidence: labels come from file descriptions; no two-person human adjudication exists. Whole clips include setup and celebration, and the field-goal file does not say whether the kick was made.

Impact: temporal grounding, made/missed outcome, player role, route, coverage, down/distance, and tactical explanations cannot be scored.

Remediation: use a two-reviewer annotation sheet with event start, snap, decisive moment, end, target outcome, visible evidence, uncertainty, and disagreement resolution. Keep source text hidden until after visual labeling to reduce confirmation bias.

### High: filenames and metadata leak the target

Evidence: downloaded filenames literally contain `touchdown`, `kickoff`, `field-goal`, or `interception`.

Impact: any pipeline that embeds paths, page descriptions, metadata, or contact-sheet captions can solve the benchmark without video understanding.

Remediation: the model must receive decoded video frames only, under opaque internal IDs. Add an automated test that renames media to random IDs and verifies identical predictions. Treat source descriptions as post-hoc weak labels, never prompt context.

### High: audio and music were not independently cleared

Evidence: the SMU clip description explicitly mentions the school fight song; other clips may contain stadium audio. CC page-level licensing may not prove every music or commentary layer is independently owned.

Impact: audio training, redistribution, or third-party processing could add copyright exposure and label leakage through crowd/commentary cues.

Remediation: strip or ignore audio for this pilot. Audit audio separately before any multimodal experiment.

### Medium: camera and domain distributions differ

Evidence: clips range from close sideline/end-zone spectator views to wide stadium views; one held-out negative is professional minicamp rather than a game. Repeated Chiefs footage appears in validation and test, although no Chiefs clip is in train.

Impact: results may reflect venue/team/camera shortcuts or practice-versus-game domain shift.

Remediation: report the minicamp item as a separate domain-shift case and add paired within-game positives/negatives across many independent games.

### Medium: creator and event-date metadata are incomplete

Evidence: two Flickr-derived Chiefs clips expose only account ID `187103922@N04` through Commons metadata, and some file `Date` fields may reflect upload/processing rather than kickoff date.

Impact: attribution remains possible through the account URL, but polished publication credits and chronological analyses are incomplete.

Remediation: preserve account URLs and immutable Commons revisions; do not infer event dates from filenames or page dates without a separate authoritative schedule source.

## Sources intentionally excluded

- **Publicly viewable commercial broadcasts:** rejected when no explicit reusable license exists. Public availability is not permission.
- **YouTube rips:** never used. The sole YouTube-origin item was downloaded from Commons only after the audited file page recorded its historical CC license review.
- **Amazon Nova football example:** rejected because Commons categorizes it as AI-generated; it fails the real-footage requirement.
- **FOX highlight compilations on Commons:** held because edited broadcasts can contain layered broadcast, music, graphic, or third-party rights; they were unnecessary for this pilot.
- **Princeton–Yale 1903 and UVA 1950s public-domain films:** held for a future historical domain-shift study because their visual distribution differs sharply from modern coach workflows.

## Recommended next steps

1. Use this slice only to verify the complete training, evaluation, reporting, and dual-sport GUI path.
2. Freeze and hash the mapping from fine labels to `is_touchdown`; do not derive it from filenames at runtime.
3. Run a filename-randomization leakage test and a mute-versus-audio ablation, with muted video as the only rights-approved primary result.
4. Have two reviewers human-label snap/event/end boundaries and adjudicate the nine clips before quoting any metric in a presentation.
5. Expand by independent source group, not by slicing more adjacent windows from these nine assets.
6. Keep public-weight release and third-party API upload gated until UMD review of ShareAlike and personality/trademark implications.

## Further questions

- Will FootballMaster stay a retrieval/reranking model, or will it make fine-grained tactical claims? The latter requires a much richer annotation ontology and all-22-like views.
- Can UMD Athletics provide institutionally authorized practice/game footage with coach-defined labels and a research-use agreement? That would be much more valuable than scaling random public clips.
- Which UMD football and soccer coach questions are visible in broadcast/sideline video alone, and which require tracking, playbook, roster, or scoreboard metadata?
- How will ShareAlike obligations be handled if weights, embeddings, or derived clip indexes are shared outside the lab?

## Reproducible artifacts

- Source and rights ledger: `data/public/footballmaster/source-manifest.json`
- Model-ready examples: `data/public/footballmaster/examples.jsonl`
- Media audit and hashes: `data/public/footballmaster/media-audit.json`
- Validation receipt: `data/public/footballmaster/verification-receipt.json`
- Attribution notice: `data/public/footballmaster/ATTRIBUTION.md`
- Contact-sheet overview: `data/public/footballmaster/contact-sheets/overview.jpg`
- Human-review protocol: `data/public/footballmaster/annotation-protocol.md`
- Audit scripts: `data/public/footballmaster/audit_media.py` and `data/public/footballmaster/verify_manifest.py`
