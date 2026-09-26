# Detailed long-clip VLM probe — 2026-08-27

## Bottom line

The local VLM can return a rich, searchable JSON report for 20-, 30-, and 60-second real SoccerNet clips, but **valid JSON is not valid soccer understanding**. On this one deliberately selected, post-hoc 60-second sequence, `google/gemma-4-e4b` returned fluent event narratives while missing every strict timestamp-aligned SoccerNet reference event. A dense six-window pass also missed all four reference events. The current model is therefore useful as a pipeline and failure-analysis demo, not yet as an autonomous coach-search index.

The safest whole-match design is a VLM-only sliding-window ingestion pipeline: analyze overlapping short windows, retain evidence frames and uncertainty, consolidate duplicates, and index the resulting reports. Windowing, validation, consolidation, and search are infrastructure; they do not replace the VLM with a hand-engineered play classifier.

## Private input and held-out reference

- Source: one NDA-authorized SoccerNet first half, kept under `data/private` and never sent off-device.
- Model input: silent video only, 398×224, 25 fps. No audio, transcript, labels, team knowledge, or source metadata entered any VLM prompt.
- Nested test clips all begin at 1,735 seconds in the source half and last 20, 30, or 60 seconds.
- The held-out SoccerNet labels file has SHA-256 `840f6b5b5db0cf99e8767e35cc5419b5ed32a735c9d4aaede27ad33cd98061b8`.
- Reference events relative to the nested clip start:
  - foul at 4.242 s;
  - yellow card at 19.160 s;
  - shot on target at 59.270 s;
  - goal at 59.800 s.
- These labels were inspected only after the visual outputs existed. SoccerNet does not densely annotate ordinary passes, carries, or duels, so unlabeled ordinary-action claims cannot be scored as false solely from this reference.

## Model and detailed output contract

- Endpoint: loopback-only `http://127.0.0.1:1240/v1`.
- Requested and reported model: `google/gemma-4-e4b`.
- Temperature: 0.
- Visual representation: six chronological 1280×720 contact-sheet images per request.
- Detailed schema: `playground-coach-search-report-v1`.
- Each event records: normalized event type, start/end time, team direction, actor description, identity basis, secondary player, field location, observed action, outcome, tactical context, coaching relevance, supporting frame times, confidence, and uncertainty. Each report also returns a clip summary, dominant phase, search keywords, a player-identification limit, and a coverage limit.
- The prompt forbids invented player names, asks for every supported retrieval-worthy event rather than one midpoint label, and explicitly distinguishes long balls, offsides, fouls, cards, shots, saves, and goals.
- Final probe-driver SHA-256: `5120d72741ba2217ce63ae510cc02ea2e088b962c53288b7d6711e4db6a8825c`.

## Direct progressively longer requests

| Duration | Frames / sheets | First-pass schema | Latency | Returned events | Strict reference alignment |
|---:|---:|---|---:|---|---|
| 20 s | 16 / 6 | valid | 14.749 s | 1: `progressive_pass` | 0/2; missed the foul and card |
| 30 s | 18 / 6 | valid | 9.779 s | 0 | 0/2; missed the foul and card |
| 60 s | 24 / 6 | valid | 28.315 s | 5: `shot_on_target`, `save`, `shot`, `tackle`, `progressive_pass` | 0/4 at the required time; missed foul/card and time-shifted the shot/goal narrative |

The 60-second answer looked plausible in isolation but described a shot/save/goal sequence around 39–50 seconds. The held-out shot and goal occur around 59.3–59.8 seconds. Full-size sheet inspection shows broadcast replays and camera cuts in the middle of the clip; the VLM treated replay imagery as if it were a correctly ordered live event. This is a concrete temporal-grounding failure, not just a label mismatch.

Selected private evidence directories:

- `data/private/long-clip-detailed-probe/run-20s-v2`
- `data/private/long-clip-detailed-probe/run-30s-v1`
- `data/private/long-clip-detailed-probe/run-60s-v1`

Every directory contains `input-manifest.json`, six hash-bound contact sheets, `request-metadata.json`, `raw-response.json`, `report.json`, and `receipt.json`.

## Dense six-window pass over the same 60 seconds

The same 60 seconds were divided into six non-overlapping 10-second clips. Each request received 12 sampled frames packed into six images. This increases temporal evidence density while keeping the number of image inputs fixed.

| Source interval | Selected run | Schema | Latency | Event count | Returned types | Reference assessment |
|---:|---|---|---:|---:|---|---|
| 0–10 s | `run-window-00-v1` | valid | 24.562 s | 0 | — | missed foul at 4.242 s |
| 10–20 s | `run-window-01-v1` | valid | 28.424 s | 5 | progressive pass, dribble, shot on target, recovery, set-piece setup | missed card at local 9.160 s |
| 20–30 s | `run-window-02-v1` | valid | 26.007 s | 4 | short pass, dribble, progressive pass, turnover | no dense ordinary-action reference available |
| 30–40 s | `run-window-03-v1` | valid | 42.783 s | 3 | dribble, progressive pass, shot | no dense ordinary-action reference available |
| 40–50 s | `run-window-04-v2` | valid | 51.737 s | 6 | set-piece setup, shot, save, clearance, dribble, progressive pass | no dense ordinary-action reference available |
| 50–60 s | `run-window-05-v2` | valid | 30.644 s | 5 | progressive pass, dribble, shot, clearance, turnover | missed timestamp-aligned shot-on-target and goal |

- Total sequential inference time: 204.157 seconds for 60 seconds of footage.
- Median per-window latency: 29.534 seconds.
- Measured processing cost: 3.403× video duration on this machine. A purely linear projection is roughly 5.1 hours for a 90-minute match; this is an engineering estimate, not a measured full-match result.
- Strict alignment with the four held-out target events: 0/4.

Selected private window evidence directories:

- `data/private/long-clip-detailed-probe/run-window-00-v1`
- `data/private/long-clip-detailed-probe/run-window-01-v1`
- `data/private/long-clip-detailed-probe/run-window-02-v1`
- `data/private/long-clip-detailed-probe/run-window-03-v1`
- `data/private/long-clip-detailed-probe/run-window-04-v2`
- `data/private/long-clip-detailed-probe/run-window-05-v2`

## Preserved failure evidence

Two failures were not hidden or repaired after the fact:

1. The first 20-second schema allowed too many generic `other` events. The model reached exactly 2,200 completion tokens (`finish_reason=length`) and emitted truncated JSON. Raw-response SHA-256: `768cf29ba2aa9bfdecb8a6107ad625c53cb631d3caf1f7a43fef48061e1f5bf8`. The retry removed generic filler, discretized confidence to 0–1, capped retrieval-worthy events, and raised the output budget within the measured context headroom.
2. The first 40–50-second window returned one event with `start_s > end_s`. The independent validator rejected it as `event_4_negative_interval`. The retry added an explicit ordering requirement; no model output was silently rewritten.

Failure directories:

- `data/private/long-clip-detailed-probe/run-20s-v1`
- `data/private/long-clip-detailed-probe/run-window-04-v1`

## What the experiment says about whole-game search

1. **Longer input technically fits; semantic reliability is the blocker.** Six packed images kept prompt usage between roughly 2.0K and 2.4K tokens, and all selected 20/30/60-second requests completed within the 8K context. The 60-second request did not fail from context length.
2. **Schema validity is necessary but far from sufficient.** All nine selected reports passed the project-side structural checks; none of the four reference events was strictly recovered at the correct time.
3. **Broadcast grammar needs explicit treatment.** Replays, close-ups, graphics, and live action are mixed. A future VLM report must label shot/replay boundaries or refuse to assign a live timestamp when broadcast order is ambiguous.
4. **Player-specific search is unresolved at 224p.** Some frames visibly contain a broadcast graphic and a jersey/name, but the VLM often returned `unspecified` or an appearance-only actor. Player names must be evidence-linked, never filled from team knowledge.
5. **The next honest experiment is a preregistered, independently annotated sliding-window evaluation.** Use overlapping 8–12-second windows, test a stronger/free VLM if available, consolidate duplicates, store evidence thumbnails and uncertainty, and measure event recall, temporal overlap, actor identity precision, unsupported-event rate, report consistency, and ingestion cost.

## Presentation-safe claim

> We upgraded the prototype from one-label classification to a detailed coach-search report and verified that 20-, 30-, and 60-second real clips run locally. The important result is a failure boundary: fluent structured reports can still be temporally wrong, especially across replays and camera cuts. Whole-game search should therefore ingest overlapping short windows, retain frame evidence and uncertainty, and remain human-auditable until event and player-level recall are independently measured.

This is a single-match, post-hoc systems probe. It is not an accuracy benchmark, a model ranking, a player-identification result, or evidence that the system is ready for coaching decisions.
