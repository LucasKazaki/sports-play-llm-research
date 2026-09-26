# FootballMaster v2 public long-form dataset audit

Date: 2026-08-27  
Status: five-hour acquisition and integrity gate **PASS**; whole-game completeness claim **NO-GO**  
Dataset: `footballmaster-v2-public-games-2026-08-27`

## Answer first

The isolated FootballMaster v2 data lane now contains six authentic American-football game programs totaling **20,265.7455 seconds (5.6294 hours)** and **2,095,093,021 bytes (1.9512 GiB)**. All six preservation downloads were hash-checked against the primary Internet Archive metadata, assigned at whole-game grain to a 3/1/2 train/validation/test split, fully decoded through the video stream, and visually sampled across their duration.

The source metadata does not establish that any file is an uncut, every-play game recording. The correct claim is therefore “six long single-game programs,” not “six complete games.” A separately discovered 19-part DVIDS Doughboy Classic record is a promising near-complete-game supplement, but it is not part of this sealed receipt.

## Dataset and grain

| Split | Distinct games | Verified seconds | Hours |
|---|---:|---:|---:|
| Train | 3 | 9,886.8770 | 2.7464 |
| Validation | 1 | 3,939.9360 | 1.0944 |
| Test | 2 | 6,438.9325 | 1.7886 |
| **Total** | **6** | **20,265.7455** | **5.6294** |

The split key is `game_id`. Every future temporal window, clip, frame sample, or derivative from a game must inherit that game’s split. Berkeley appears in all games, so this is a **game-held-out** design, not a team-held-out design.

## Source and rights decision

Each asset comes from the [Berkeley Community Media collection](https://archive.org/details/berkeleycommunitymedia) on Internet Archive. The item metadata was supplied under the institutional uploader identifier `info@betv.org` and names [Creative Commons Attribution-ShareAlike 3.0](https://creativecommons.org/licenses/by-sa/3.0/). The acquisition tool fails closed unless the live title, collection, uploader, license, and selected H.264 derivative agree with the checked-in catalog.

Primary item pages:

- [Bishop O’Dowd vs. Berkeley varsity](https://archive.org/details/betv-16559varsityfootball-bishopodowd-vs-berkeley)
- [Castro Valley vs. Berkeley varsity](https://archive.org/details/betv-16556varsityfootball-castrovalley-vs-berkeley-11-8-13)
- [Berkeley vs. Pittsburg JV](https://archive.org/details/betv-16364bhs-jv-football---berkeley-vs-pittsburg)
- [Logan vs. Berkeley JV](https://archive.org/details/betv-16419bhs-jv-football---logan-vs-berkeley)
- [Encinal vs. Berkeley JV](https://archive.org/details/betv-16554jvfootball-enciminal-vs-berkeley-1028) — source title misspells Encinal as “Enciminal”
- [San Leandro vs. Berkeley](https://archive.org/details/betv-16546san-leandro-vs-berkeley-football)

Local research use is approved under the recorded license conditions. Redistribution must preserve attribution, the license link, change notices, and ShareAlike obligations. Public release of trained weights remains **HOLD** pending institutional review of ShareAlike, publicity, school-mark, and other non-copyright questions.

## Checks performed

1. Refreshed and byte-snapshotted the primary Internet Archive metadata for every item.
2. Required exact expected titles, institutional collection membership, institutional uploader, and CC BY-SA 3.0.
3. Selected exactly one hosted H.264 derivative per item and pinned its file name, byte count, duration, MD5, and SHA-1.
4. Downloaded with resumable `.part` files and HTTP Range support.
5. Recomputed remote MD5/SHA-1 and a local SHA-256 for every file.
6. Fully decoded each video stream with FFmpeg; audio was not mapped into the decode audit.
7. Compared container/frame duration against primary metadata within a two-second tolerance.
8. Recomputed the five-hour threshold and source-held-out split membership.
9. Sampled 12 frames at uniform interior points from every game (72 frames total). Direct inspection found real players, officials, field markings, formations, snaps, tackles, kicks, and sideline/game-break activity across all six files. No synthetic footage or soccer content was observed.

## Audio policy

Source audio is preserved. The primary research path is silent: audio cannot enter model input, features, training labels, evaluation labels, or ground truth. After silent visual predictions and their hashes are sealed, commentary/ASR may be compared in a **separate weak, unverified post-hoc audit**. That comparison is not a correctness oracle and cannot silently relabel the visual evaluation.

## Findings and analytical risks

| Finding | Evidence | Severity | Downstream risk |
|---|---|---|---|
| Five-hour coverage passes | 20,265.7455 verified seconds | Low | Adequate for a substantially larger engineering experiment, not a publication-scale benchmark |
| Test denominator is still small | Two distinct test games | High | Accuracy percentages will have very wide uncertainty and must be reported with counts and intervals |
| Team/domain diversity is narrow | Berkeley appears in all six games; all are high-school footage from one provider | High | Models may overfit venue, uniforms, camera position, or production style |
| Complete-game status is unproven | Source titles identify games but do not promise uncut every-play recordings | Medium | Whole-game recall and coverage claims are unsafe |
| No play annotations exist | Item metadata supplies game identity, not play boundaries or event labels | Critical for event training | Supervised event detection requires a separately audited annotation pipeline |
| ShareAlike and non-copyright questions remain | CC BY-SA 3.0 plus visible students/school marks | High for release, low for local research | Do not publish media-derived weights or redistribute a transformed dataset without review |

## Recommended next gates

1. Run shot-boundary/play segmentation without looking at test outcomes; annotate a train-only pilot with an explicit football ontology.
2. Have two annotators independently label at least a sample of play boundaries and event types; report agreement and adjudication.
3. Freeze all window IDs before modeling and prove that every derivative inherits its `game_id` split.
4. Add at least two new teams/providers to validation and test before making generalization claims.
5. Acquire and verify the 19-part DVIDS Doughboy Classic as a near-complete-game stress test, while preserving all 19 parts under one `game_id`.
6. Report event-level precision/recall, retrieval Recall@K, temporal evidence overlap, calibration/abstention, and failure counts—not only clip accuracy.

## Reproducibility evidence

- Catalog: `data/public/footballmaster-v2/catalog.json`
- Rights/provenance manifest: `data/public/footballmaster-v2/source-manifest.json`
- Full-decode receipt: `data/public/footballmaster-v2/verification-receipt.json`
- Visual sampling receipt: `data/public/footballmaster-v2/visual-inspection-receipt.json`
- Offline verifier: `data/public/footballmaster-v2/tools/verify_dataset.py`
- Manifest file SHA-256: `DA0E58D2EF1A0780A54DFA82D03C0A936F08C8DC61D24CB3A505FDC776713B68`
- Verification receipt file SHA-256: `B9E0AA080B40B10003FF6D4ABDF6E0F2BD872CB98931F56AADBA8E83DE3A66D2`

Offline verifier result: `PASS: 6 assets, 6 unique games, 20265.746s (5.6294h), 2095093021 bytes`.
