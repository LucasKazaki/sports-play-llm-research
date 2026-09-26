# Archit research update and speaking notes — evidence-gated soccer video search

**Purpose:** a candid, technical update for the next research discussion. It separates what the project has demonstrated from what it has deliberately *not* claimed.

## The one-minute update

| Area | Verified state | Claim boundary |
| --- | --- | --- |
| Long-video system | The historical pipeline processed a complete match as 96 windows and produced 361 VLM-authored event reports. | This proves an end-to-end systems path, not soccer understanding. |
| Semantic reliability | Restricted post-seal checks corroborated 3/166 mapped annotations and 3/54 mapped predictions; a six-window visual review found 0 fully supported reports. | Coach-ready event retrieval, player-specific reports, and accuracy are currently a **no-go**. |
| Private data audit | 9 opaque game groups, 18 halves, 50,120 seconds (13.9222 h), and 3.407 GB were inventoried. The metadata-only audit passed 91/91 checks. | The audit confirms corpus bookkeeping, not labels, model quality, or rights to redistribute media. |
| Next evaluation | A frozen 40-window evidence-gated diagnostic is pre-registered, with zero new model calls. | It cannot run until fresh game-held-out media, privacy checks, and an overlap lock are present. |
| Open-data lane | A bounded [SoccerTrack v2](https://github.com/AtomScott/SoccerTrack-v2) CC BY 4.0 intake passed source, media/BAS hash, decoder, split, and label-isolation checks for development match `117092` and sealed held-out first half `128057`. | `128057` is unscored; official delivery of `132831` is provider-quota-blocked and was not substituted, so this is not an evaluation result or a substitute for the private fresh-test requirement. |

**Plain English:** the pipeline can make structured reports from long video, but the evidence says those reports are not dependable soccer facts yet. The work now is to make the next test capable of proving—or disproving—real improvement.

## What the historical run taught us

### Systems go; semantic no-go

The historical SoccerMaster-style long-form run established that the engineering stack can segment a full match, call a VLM, persist reports, and retrieve report text. Its outputs must remain sealed as **systems evidence only**. The low restricted corroboration and direct visual audit expose concrete failures: frame-as-event behavior, unsupported goal-like claims, invented continuity, and weak temporal grounding.

**Plain English:** “the app ran” is true; “the app correctly found offsides, fouls, or player actions” is not. Showing that distinction is the strongest and most scientifically honest result so far.

### Research framing

[SoccerMaster](https://haolinyang-hlyang.github.io/SoccerMaster/) motivates long-video soccer understanding. This project’s contribution is not a claim to reproduce its performance; it is an evidence-first evaluation path for open-ended VLM reports, where detailed prose creates more ways to hallucinate than a fixed action label does.

**Plain English:** rather than trusting a fluent paragraph because it sounds plausible, we force every proposed event to survive a separate visual-evidence check before it can enter search.

## Data status and split discipline

### Authorized private corpus

The local private corpus is represented only through opaque metadata: 9 game groups, 18 halves, 50,120 seconds / 13.9222 hours, and 3.407 GB. The read-only inventory and ASR/SoccerDB mapping audit passed 91/91 checks. It also found 18 local ASR half-files with 16,024 segments and **zero exact SoccerDB joins**. ASR is reserved for a later text-only or late-fusion ablation; it is not visual ground truth or a post-hoc repair mechanism.

**Plain English:** we know exactly what data is present and how it is partitioned, but we are not letting commentary or a separate database leak an answer into the visual test.

### Public SoccerTrack v2 intake

SoccerTrack v2 is a separately licensed public lane: the official repository specifies CC BY 4.0 for dataset video and annotations. A bounded intake under `data/open/soccertrack-v2/` now includes official **training** match `117092` (6,687,957,167 media bytes) and the first half of official **test** match `128057` (3,312,813,154 media bytes), each with matching BAS, direct-source provenance, a decoder check, official-split check, and label-isolation receipt. `117092` is integrity-admitted as development data; `128057` is held out, sealed, and unscored.

The adapter preserves the released source-game split rather than rebalancing locally:

- Train: `117092`, `117093`, `118575`, `118576`, `118577`, `128058`, `132877`
- Validation: `118578`
- Test: `128057`, `132831`

`117092` is development-only. `128057` remains held out, sealed, and unscored. The second official test match, `132831`, is not local because the official delivery returned a quota/unavailable HTML response rather than media; that rejected response and an unpaired BAS container are quarantined outside the intake root. No substitute source was used. The public lane is therefore still not an evaluation cohort and has no public-data result.

**Plain English:** the new video is lawful public data, but one development match plus one sealed test half is not a benchmark. We keep the held-out half separate from anything used to develop the system, and we do not score it until the full study gate is ready.

### Intake and adapter boundary

The SoccerTrack adapter is deliberately non-semantic. It accepts only files under the public-data root, validates provenance/hash/container linkage, emits opaque asset tokens, and keeps its retrieval catalog disabled. It has no video decoder, model transport, network client, event detector, or label-to-query path. An independent code-and-synthetic-fixture QA lane passed 22 focused tests, including tamper, path-containment, source-split, and annotation-leakage tests. The completed actual-data build/verify then passed for one media asset and one BAS container, with zero model/pixel/event calls. Neither check is a model evaluation.

**Plain English:** the adapter is a locked loading dock. It can check that the right boxes arrived without reading the answer sheet or deciding what happened on the field.

## Frozen next experiment: evidence-gated VLM diagnostic

The `soccermaster-evidence-gated-v1` protocol is frozen under SHA-256 `d0bf9809cb87491a088dc6abc85eef104c4950f773a2367d1de5239978fbc720`. It specifies 40 private, game-held-out 30-second windows: 4 goal, 8 offside, 8 foul, 8 corner-kick, and 12 background. Each uses 13 ordered, silent, scoreboard-redacted frames and a deterministic time jitter. Labels are used only to construct the private lock and for evaluation after predictions are sealed.

For each window the local VLM will produce: (1) one atomic proposal or abstention, (2) a blinded second proposal, and (3) a separate evidence audit that must cite a pre/anchor/post visual chain. Deterministic software can validate format, agreement, and audit gates; it must never label an event itself. Goal claims require direct VLM-stated evidence that the ball crossed the line or is visibly in the goal. Failed gates become abstentions, not fallback labels.

**Plain English:** each clip gets one carefully checked answer, not a pile of guesses. If the visual proof is missing, the correct system behavior is “I don’t know.”

This protocol has **zero inference calls**. Its hard preconditions are: at least two newly acquired held-out game groups disjoint from all historical VLM input, a hash-based history-overlap lock, full-frame privacy/overlay review, the private data binding, and an explicit local-model authorization receipt.

**Plain English:** there is no new score to announce yet. The experiment is ready on paper and in code, but intentionally blocked until its test set is truly new and blind.

## Agent Studio: local work loop, not a research-result generator

The Sports project’s director, researcher, developer, and QA roles now route to local LM Studio `openai/gpt-oss-20b`, with no generic hosted fallback. Two bounded local tasks have server-owned receipts: an exact-path browserless workspace read and an exact-path workspace-write handoff. The versioned local handoff’s checked SHA-256 is `667e452cc4e609e84774441ea8c1bb21ae5d89bb419d936b49449fb8df2db4da`.

The route is intentionally narrow: no browser, terminal, media, network, arbitrary file, or external-model authority. A legacy Studio full-history snapshot path can still delay health probes under load, so these receipts prove bounded local work occurred; they do **not** yet prove uninterrupted whole-Studio liveness.

**Plain English:** the local loop can take carefully limited project chores off the cloud-token path and leave an audit trail. It is not an unsupervised scientist, and it has not run new VLM experiments.

## 3–5 minute talk path

### 0:00–0:35 — Start with the honest headline

> “I separated pipeline execution from semantic validity. The long-video system ran, but the evidence says its soccer event reports are not reliable enough to present as coaching output. I froze that baseline rather than tuning against it.”

### 0:35–1:20 — Explain why the result is useful

> “The prior complete-match run gives us a systems baseline: 96 windows and 361 reports. But post-seal corroboration was only 3/166 annotations and 3/54 predictions, and visual review supported none of six sampled reports. That tells us the next contribution must be better measurement, not a stronger marketing claim.”

### 1:20–2:05 — Show the data discipline

> “The private corpus has 9 game groups, 18 halves, and 13.9222 hours, with a 91/91 metadata audit. It is no longer eligible as a fresh test pool. I also brought in SoccerTrack v2 through a completely separate CC BY 4.0 intake: one development half and one official held-out half, while preserving its released game-level split.”

### 2:05–3:05 — Walk through the next diagnostic

> “The frozen protocol uses 40 held-out windows. The VLM gets redacted silent frame sequences, makes two independent prompted proposals, then audits its own visual evidence. Code only enforces the contract; it never turns pixels into soccer labels. If the evidence is insufficient, the index records abstention.”

### 3:05–3:45 — Name the present blocker and proposed collaboration

> “I have not run the private protocol because I do not yet have two fresh private held-out game groups with the required overlap and privacy locks. The public SoccerTrack lane now has one development half and one sealed held-out half; the second official test delivery is quota-blocked, so I did not replace it with a weaker or rights-ambiguous source. It is not a shortcut around the private condition. I would value feedback on the event ontology, human-adjudication protocol, and what claim threshold would be convincing.”

### 3:45–4:20 — Close with practical engineering status

> “The demo remains a transparent technical-search demonstrator, not coach-ready software. I also routed routine, bounded project tasks through a local GPT-OSS worker with receipts, while keeping it out of media and evaluation authority.”

## Likely technical questions and direct answers

| Question | Honest answer |
| --- | --- |
| **Why call this a VLM experiment instead of action recognition?** | The target is structured, evidence-backed open-ended reporting/search over longer video. That makes grounding and abstention central; a fluent answer is not accepted as a label. |
| **Are Proposal A and Proposal B independent?** | No. They are separate prompted calls to the same local model, so they are procedural redundancy, not statistical independence. The report will state that limitation. |
| **What prevents label leakage?** | Game-level split locks, anonymous relative-time frame inputs, no audio/labels/source identity in the visual request, and post-seal-only evaluation. The adapter also blocks annotation-to-query flow. |
| **Why not use ASR/commentary to improve results?** | It is useful as a separately declared text-only/late-fusion ablation, but it cannot repair the primary visual condition after the fact. Otherwise commentary can reveal the event. |
| **What does SoccerTrack add?** | A lawful, real-footage public development lane with an official source-game split. It adds diversity and reproducibility, but its panoramic amateur-camera domain differs from broadcast/private SoccerNet data and it cannot yet establish generalization. |
| **Why is the second public test game missing?** | The official delivery returned a quota/unavailable page instead of video. We retained that failure evidence and quarantined the unpaired annotation, rather than bypassing the provider or substituting public-TV footage. |
| **Why no new result from the 40-window protocol?** | The held-out-data and privacy gates are intentional safeguards. Calling the model before those gates would compromise the experiment more than it would help progress. |
| **What would a valid positive result look like?** | A sealed, game-held-out run with raw and accepted counts, abstentions/gate reasons, temporal-error and restricted type/time corroboration, plus independently blinded human visual adjudication for any detailed claim. No target number is precommitted. |
| **Can a coach use the search UI now?** | Only as a transparent infrastructure demonstration. It must not be described as reliable event detection, player attribution, or training guidance. |
| **What did Agent Studio actually prove?** | That bounded local GPT-OSS work can be routed and receipt-checked without cloud fallback. It did not prove scientific validity, continuous uptime, or autonomous media analysis. |

## Next research actions, in order

1. Preserve and independently re-verify the completed SoccerTrack `117092` development and `128057` held-out provenance, byte/hash, and schema receipts; keep `128057` sealed and unscored. Revisit `132831` only if the official provider becomes available; retain the quota-block evidence and do not substitute footage.
2. Restore a rights-compliant path to at least two fresh private game groups, then lock their hashes against every historical VLM input.
3. Run the full-frame overlay/privacy audit and materialize the private binding/window manifest without exposing labels to the inference condition.
4. Obtain explicit local-model authorization, run the 40-window diagnostic once, seal raw outputs, then conduct post-seal evaluation and blinded visual adjudication.
5. Report failure modes, abstentions, and accepted versus withheld claims separately; only then decide whether to iterate on prompts, temporal sampling, model choice, or a declared ASR ablation.

**Plain English:** collect clean test footage first, run one honest experiment second, and only then spend time making the model better. That avoids training on the answer key.

## Supporting records

- Current frontier status: `C:\AI\projects\SportsPlayLLMResearch\research\2026-08-30-loop-frontier-status.md`
- Frozen protocol and claim boundary: `C:\AI\projects\SportsPlayLLMResearch\research\soccermaster-evidence-gated-v1-protocol-2026-08-30.md`
- Metadata-only private-corpus audit: `C:\AI\projects\SportsPlayLLMResearch\artifacts\soccer-data-expansion-audit-2026-08-30\README.md`
- Preflight/binding artifacts: `C:\AI\projects\SportsPlayLLMResearch\artifacts\soccermaster-evidence-gated-v1\`
- SoccerTrack intake contract: `C:\AI\projects\SportsPlayLLMResearch\research\soccertrack-v2-intake-adapter.md`
- Independent SoccerTrack boundary QA (22 focused tests): `C:\AI\projects\SportsPlayLLMResearch\.agent\soccertrack-intake-adapter-independent-qa-2026-08-31.md`
- Local Agent Studio execution receipt record: `C:\AI\projects\SportsPlayLLMResearch\.agent\agent-studio-sports-loop-verified-local-execution-2026-08-31.md`
- Versioned local-loop handoff: `C:\AI\projects\SportsPlayLLMResearch\research\local-loop-evidence-gated-handoff-2026-08-31-v2.md`
- Official SoccerTrack v2 source and data license: [repository](https://github.com/AtomScott/SoccerTrack-v2) and [CC BY 4.0 data license](https://github.com/AtomScott/SoccerTrack-v2/blob/main/LICENSE-DATA)

## One-sentence safe takeaway

> We have a verified long-video VLM research pipeline and a rigorously gated next experiment, but not yet evidence that the system reliably understands soccer events; the immediate contribution is making that distinction measurable on clean, held-out real footage.
