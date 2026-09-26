# Chess, board-game, and sports-explanation research receipt — 2026-09-17

## Scope and decision

This is a bounded primary-source review for a new **Chess Concept Model**
track. Its purpose is to make chess the controlled, fully observable testbed
for the project's existing evidence-grounded sports research—not to claim that
chess proficiency transfers automatically to soccer or American football.

The immediate product is an auditable explanation system: it must replay a
legal position, name the concepts that matter, attach every claim to board and
engine evidence, and abstain where its evidence is insufficient. A centipawn
delta or a principal variation alone is not a human explanation.

## Primary research reviewed

| Source | What it establishes | Design consequence |
| --- | --- | --- |
| [Jhamtani et al., ACL 2018](https://aclanthology.org/P18-1154.pdf) | Move commentary contains distinct move description, quality, comparison, planning, context, and general-information functions; commentary needs state and move grounding. | Separate `what changed`, `why it matters`, `alternative`, and `teaching` fields. Do not treat generic advice as a grounded explanation. |
| [Zang et al., ACL 2019](https://aclanthology.org/P19-1597.pdf) | A chess-engine representation can ground commentary in boards, moves, options, and developments; the benchmark has five explanation categories. | Use a structured evidence layer between engine and generator, rather than ask a text model to reconstruct the position unaided. |
| [Feng et al., ChessGPT, 2023](https://arxiv.org/abs/2306.09200) and its [official code](https://github.com/waterhorse1/ChessGPT) | Combining game replay and language data is a plausible learning setup. The repository is Apache-2.0, but its named datasets retain their own source rights. | Reuse ideas and code only under their actual terms; verify each data source independently. A PGN-only policy model is not proof of explanatory understanding. |
| [Kim et al., NAACL 2025](https://aclanthology.org/2025.naacl-long.481.pdf) | Concept-guided chess commentary explicitly addresses the gap between fluent LLM prose and expert-model decision evidence; it also evaluates informativeness and linguistic quality. | Adopt a versioned concept ontology and ranked concept evidence. Use any LLM-based evaluator only as a secondary measure; human/expert assessment and deterministic claim checks remain required. |
| [Monroe & Chalmers, Chessformer, 2024](https://arxiv.org/abs/2409.12272) | Chess transformer performance depends strongly on a board-topology-aware position representation; attention maps can reveal some movement relations. | Keep the board as a first-class representation (FEN + legal replay + square relations), not merely notation in a text prompt. Attention is diagnostic evidence, not an explanation by itself. |
| [GameBench, 2024](https://arxiv.org/abs/2406.06613) | Across strategy games, LLM agents did not match human performance and prompt scaffolding was uneven. | Include legality, grounded reasoning, abstention, and human usefulness metrics. Do not infer strategic competence from fluent chain-of-thought. |
| [Rahimian, Flisar & Sumpter, 2025](https://journals.sagepub.com/doi/10.1177/22150218251353089) | Sports explanation can start from attributable predictive features, then render them as coaching language; the paper explicitly targets the practitioner communication gap. | For sport transfer, preserve feature-to-word attribution and never turn a model score into ungrounded coaching advice. |

This is a selected, current literature receipt—not a systematic review or a
novelty claim. It records the design implications that the local loop must test.

## Data and rights boundary

| Candidate source | Status | Allowed next use |
| --- | --- | --- |
| [Lichess open database](https://database.lichess.org/) | The provider states that its database exports are CC0; the puzzle feed includes FEN, UCI moves, ratings, and machine-generated themes, and the provider documents the format. | Approved discovery source for a small, hash-manifested local PGN/puzzle/evaluation sample. Keep source URL, retrieval time, license statement, checksum, and split assignment. |
| [Lichess broadcast PGNs](https://database.lichess.org/) | The provider states that broadcast games are CC BY-SA 4.0. | Use only if the attribution/share-alike obligations fit the exact internal or release artifact; record the decision before ingesting. |
| ChessGPT dataset references | The code license does not automatically grant rights to the datasets named by the project. | Metadata and source-license inspection only until every selected source is cleared. |
| Public forum commentary in the ACL 2018 lineage | The paper demonstrates value, but this receipt does not establish a redistributable or training license for its underlying crawled text. | Do not download, train on, or redistribute it until the dataset card/license is independently verified. |
| GothamChess or other creator commentary on public webpages/video platforms | Public visibility is not an ingestion license. YouTube's terms restrict automated access and copying unless the service, rights holder, or law permits it. | Discovery/linking only. Do not scrape videos, captions, transcripts, thumbnails, or comments. A creator's written permission or explicit applicable license is required before any training or persistent corpus use. |

The purpose of this boundary is to preserve the user's aim—learning the
concepts strong human commentators use—without laundering third-party
commentary into a training set. Lichess positions can support board and move
learning, but they do not create human explanatory labels.

## Transfer hypothesis and limit

Chess is useful because the state is discrete, rules are exact, turns are
clear, and counterfactual moves are inexpensive to inspect. Soccer and
American football are continuous, partially observed, multi-agent systems
where camera framing, occlusion, team context, and imperfect labels matter.

The intended transfer is therefore **an evidence and explanation architecture**,
not an unvalidated transfer of chess model weights or a claim of general sports
understanding:

| Chess field | Soccer / American-football analogue | Required change |
| --- | --- | --- |
| board state and legal move | timestamped player/ball or player/play state and feasible action | replace exact legality with calibrated observation/feasibility evidence |
| squares and attack/defense relations | pitch/gridiron zones, marking, passing lanes, pressure, blocking, leverage | attach time and spatial coordinates plus uncertainty |
| candidate moves and engine deltas | alternative actions/play calls and attributable value-model changes | preserve alternatives, but never call a counterfactual causal without a valid sports model and data scope |
| strategic concept | tactical pattern/role/formation concept | create sport-specific ontologies; never copy chess labels blindly |
| board replay proof | clip, event, tracking, and retrieval proof | require source-frame/time evidence and abstention for occlusion or insufficient view |

This aligns with PlayGround's current answer-plus-time/space-evidence contract.
The existing soccer and football systems remain **SYSTEMS GO / SEMANTIC NO-GO**;
this new board-game track does not change that status.

## Open research questions the plan must answer

1. Can a local model state a concept that is independently supported by a legal
   board transition and evidence packet, rather than reciting an engine line or
   a generic chess aphorism?
2. Does concept guidance improve blind expert ratings of factual grounding,
   causal explanation, and teaching value over a deterministic engine/PV
   baseline without reducing calibration?
3. Which parts of the architecture survive the transition from complete board
   state to sparse, uncertain sports observations?
4. Does an explanation help a player/coach choose a better next action in a
   controlled task, rather than merely sound plausible?

