# GothamChess opening illustrations — retained nine-call result

**All nine raw predictions were legal. Each fixed policy matched one of the three next displayed video moves.** Three short opening scenes do not establish move accuracy, chess strength, shared ideas, language understanding or parity with models shown in edited videos. There are zero accepted holdout positions.

## What was run

Three previously fixed policies received each current FEN independently: the v3 base 9m classifier, its development-selected step-512 checkpoint, and the original base ROOK-LM-124m. The trained move-only v4 LM was not a condition in this experiment. No training, checkpoint selection, prompt tuning or Stockfish search used these scenes.

The classifier used its reviewed native 77-character representation plus CLS and saved all 1,968 logits. Stable raw top-1 determined the action; legal-mask rankings were retained separately and did not replace it. The language policy received `P:` plus the FEN padded to 90 characters followed by `M:`, generated greedily for at most 16 tokens, and parsed only the first whitespace token after one optional initial `M:`. It did not search later text for a legal move or a `B:` answer.

Generation read the separate [FEN-only input](../experiments/gotham-illustrative-v1/fen-inputs.json), with no video, history, displayed answer, engine score, commentary or future board. All nine outcomes and source/model/runtime bindings were sealed before the evaluator read the source ledger. Each condition loaded once and attempted three calls. All completed, parsed and were raw-legal; no failure was dropped from the denominator.

| Condition | Accounted / planned | Parsed | Raw legal | Matches to displayed move |
| --- | ---: | ---: | ---: | ---: |
| Base classifier 9m | 3/3 | 3/3 | 3/3 | 1/3 |
| V3 selected classifier, step 512 | 3/3 | 3/3 | 3/3 | 1/3 |
| Base language policy 124m | 3/3 | 3/3 | 3/3 | 1/3 |

## Every scene

| Current source position | Next displayed observation, evaluator only | Base classifier | Selected classifier | Base LM |
| --- | --- | --- | --- | --- |
| [After `d4 Nf6 c4 e6 Nc3 Bb4`, 2:30](https://www.youtube.com/watch?v=sskvj1_ehx4&t=150s) | `e2e3`, at 2:35 | `c1d2` | `c1d2` | `d1c2` |
| [After `e4 c5 Nf3 d6 d4 cxd4`, 2:32](https://www.youtube.com/watch?v=ulLBRyVrI1Y&t=152s) | `f3d4`, at 2:33 | `f3d4` | `f3d4` | `f1c4` |
| [After `e4 e6 d4 d5`, 2:10](https://www.youtube.com/watch?v=PVVA-_wvKks&t=130s) | `b1c3`, at 2:25; variation status unresolved | `e4e5` | `e4e5` | `b1c3` |

The third video's following section explores and rewinds hypothetical branches, including `...Bb4` and `...Nf6`. Only the preceding four-ply history was retained. The displayed `Nc3` is an observation from the video, not an authenticated original-game mainline label. The first two histories were consistent across sampled intermediate boards, but human editorial/mainline review remains pending for all three.

Original game identities are unknown. The intake ledger reported no board-key overlap against the retained historical/v1/v2/v3 material (13,112 source games and 26,322 before/setup-after/historical keys); that limited screen does not certify whole-game exclusion, independence from every later dataset, or unknown upstream pretraining. These familiar openings are an intentionally small illustration rather than a challenge cohort. The video participants' exact model identity, prompt, compute, editing and interaction are not a controlled baseline.

## Evidence and review limits

The [candidate package](../experiments/gotham-illustrative-v1/README.md) contains exact FEN inputs, the evaluator-only [source ledger](../experiments/gotham-illustrative-v1/source-ledger.json), all [nine raw outputs](../experiments/gotham-illustrative-v1/evidence/raw-results.json), six logit arrays, [joined results](../experiments/gotham-illustrative-v1/summary.json), the original sixteen-binding seal and exact executed source snapshots. No creator video, frame, transcript, model weight or copied commentary is included. Media remain private; no creator-media training or redistribution right is inferred.

The executed runner hash is `f43f6beaed6ec8770b15967db0d14ab30827605cdcbe0a7aa55fa3034294c8a8`; the frozen plan hash is `bbe7f80c5729ff124e8d6aab038b3208e2b572ffc6c590a2f11ce419f70d9523`. The active repository utility has explicitly documented post-run test-path and future-plan CLI adaptations. It was not the source of the original nine calls. The archival plan still contains host-specific absolute paths and cannot be presented as a portable new-run recipe.

Thirty focused software checks pass: the original 27 fake-backend cases and three added CLI/portability guards. Two file/token audits independently reaccounted all nine outcomes, recomputed six complete logit rankings, decoded three retained continuations and reconstructed all nine native inputs. The packaging check made no new model, GPU or engine call and confirmed the original private artifacts were unchanged. Passing software checks and legal actions do not validate source mainlines or move quality.

No policy is promoted or ranked from these observations. Human source/mainline validation and original-game identity remain necessary before considering an accepted evaluation cohort. Commentary capability remains separately unpassed. This is Codex-assisted work prepared for review, not formal research acceptance.
