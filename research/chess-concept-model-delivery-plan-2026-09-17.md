# Chess Concept Model: concrete local delivery plan — 2026-09-17

## Outcome and truth boundary

By noon America/New_York on September 18, the deliverable is a reviewable,
local **Chess Concept Model prototype** and its evidence packet. The prototype
must explain selected chess moves through cited board/engine evidence and say
when it cannot justify a concept. It is a feasibility demonstration, not a
claim that it plays chess at, explains chess as, or is certified by a FIDE-rated
player.

No one may claim "FIDE-level explanation" until a frozen, blind evaluation with
at least two named independent FIDE-rated reviewers (and an adjudication plan)
meets the predefined threshold below. The deadline cannot substitute for that
evidence.

## Deliverable contents

Create the following unpromoted internal candidate under a new
`chessconcept-v1` namespace. Do not alter frozen soccer/football artifacts.

| Path | Required content | Acceptance evidence |
| --- | --- | --- |
| `data/public/chessconcept/seed-manifest-v1.json` | At most 24 source positions from the license-cleared Lichess source. Store source URL, license, retrieval timestamp, FEN, PGN/UCI context, game/puzzle identifier, SHA-256, and a game-group split. | Manifest validator rejects missing license, duplicate FEN/transition bytes, same-game cross-split entries, or unpinned source fields. |
| `prototype/chess_concept_model.py` | Legal replay; deterministic evidence extraction; local-generator adapter; strict output schema and abstention gate. | Unit tests cover legal and illegal FEN/move paths, missing engine evidence, invalid citations, and false claim rejection. |
| `prototype/chess_concept_demo.py` | Loopback-only command/UI which renders the board state, move, concept cards, evidence references, alternatives, confidence, and abstention. | It works on the frozen seed subset and labels the explanation source/model/config; no network request or third-party commentary is required at runtime. |
| `prototype/chess_concept.schema.json` | Versioned contract below. | JSON-schema validation plus semantic-reference checks. |
| `tests/test_chess_concept_model.py` | Regression tests for all hard gates and non-template baselines. | Focused test receipt plus a full-suite receipt, with no frozen sports artifact changes. |
| `artifacts/chessconcept-v1/` | Immutable input manifest, model/config identifiers, engine version and limit, raw responses, validation results, checksums, demo screenshots/output, and run receipt. | Reproduction command and independent artifact verifier both pass. |

If an expected local engine or text model is absent, record that exact preflight
result and demonstrate the validated **evidence packet plus abstention path**.
Do not install a guessed package, download a model, or silently use a different
model. A deterministic text baseline may be shown only when labelled
`baseline_deterministic`, never as the Chess Concept Model.

## Frozen explanation contract

The generator receives a `PositionEvidenceV1` object, not raw web commentary.
It contains:

```text
source_id, license, game_id, ply, before_fen, after_fen, san, uci,
legal_replay_hash, engine_config, candidate_moves[], material_delta,
check/capture/castle flags, attacked_defended_relations[],
king_safety_features[], pawn_structure_features[], center_activity_features[],
piece_activity_features[], engine_pre_post_eval, multi_pv[], evidence_refs[]
```

It may return either `abstain` or `concept_explanation`:

```text
verdict, confidence, move_summary,
primary_concepts[{concept, claim, evidence_refs[], counterfactual_ref?, uncertainty}],
alternative_comparison[{move, relative_assessment, evidence_refs[]}],
teaching_takeaway, limitations
```

Allowed concepts for v1 are `king_safety`, `material`, `development`, `center`,
`piece_activity`, `pawn_structure`, `space`, `tactical_threat`, and
`endgame_transition`. Every `evidence_ref` must resolve to the frozen object;
the validator rejects uncited concepts, nonexistent alternatives, claims of a
capture/check contradicted by the legal transition, and a non-abstention when
engine or board evidence required by the chosen claim is absent. This prevents
unbounded prose but does not by itself prove that a chess concept is correct.

## Ordered implementation loop

### 1. Preflight and source binding (first bounded packet)

1. Inspect available local Python, chess-library, chess-engine, and local
   text-model endpoints without installing or starting a new service.
2. Create the source-decision record from
   `chess-board-game-sports-literature-and-rights-2026-09-17.md`.
3. Select a maximum 24-item CC0 Lichess seed. Hold out entire game IDs; do not
   use web/video commentary.
4. Hash every byte and freeze an eight-item development slice, eight-item
   validation slice, and eight-item demo-only slice.
5. Implement and run the manifest/legality validator before any model call.

**Stop condition:** missing rights record, no legal source binding, or no
available engine/model. Preserve the receipt and proceed only with the
evidence/abstention demo if it can be truthful.

### 2. Evidence extractor and fail-closed generator

1. Replay FEN/PGN with a chess rules library; reject any mismatch.
2. Run the detected local engine with one predeclared depth/nodes/time limit
   and MultiPV count. Save raw engine output separately from prose.
3. Extract narrow board facts and candidate-move comparisons. Assign stable
   IDs; never tell the generator that a feature proves a higher-level concept.
4. Query one exact discovered local language model using a fixed prompt,
   schema, maximum tokens, seed/temperature, and no internet tools.
5. Validate every output; invalid output becomes an abstention with a precise
   reason. Persist raw output and validation trace.

**Required baselines:** (a) raw engine/PV display, (b) labelled deterministic
feature template, and (c) concept-guided generator. Only the latter may be
called the prototype model.

### 3. Demonstration and anti-template checks

The local demonstration must make the following visible for each item:

- board before/after and the actual move;
- model/config/source identity and license;
- primary claim linked to highlighted evidence;
- one alternative where available;
- confidence and limitations; and
- a clear abstention state.

Run at least these deterministic checks before showing it:

1. legal replay agrees with FEN/PGN for all seed items;
2. corrupting a board/move reference fails validation;
3. removing necessary engine evidence forces abstention;
4. a tactical and a positional item do not emit identical concept/evidence
   structures; and
5. the demonstration never labels raw PV output as human explanation.

## Evaluation plan

### Tomorrow's honest readout

For the seed packet, report only: structural validity, legal-board fidelity,
source/rights completeness, valid-evidence-reference rate, abstention rate,
and whether output differs from the two labelled baselines. These are systems
and grounding checks, not chess-strength metrics.

### Required path to a FIDE-level claim

Freeze a separate, game-disjoint 80-position evaluation set balanced across
tactical and positional concepts. For every item, blind the source of three
explanations (raw-engine baseline, deterministic template, model). Two named
independent FIDE-rated reviewers score each on a 0–4 rubric for:

1. board/move factuality;
2. concept correctness and relevance;
3. causal/counterfactual explanation;
4. teaching usefulness for the intended player band; and
5. appropriate uncertainty.

Use a third adjudicator for material disagreements and report inter-rater
agreement, item-level errors, calibration/reliability, abstention selective
risk, and non-template diversity. Pre-register the threshold before model
evaluation: at least 90% legal/claim-reference validity; no material factual
error on more than 5% of non-abstentions; and a blind mean not more than 0.25
rubric points below the expert reference with a confidence interval that
excludes a worse margin. This threshold is deliberately provisional until the
reviewers and target player band are named.

## Chess-to-sports extension plan

Do not move chess weights directly into sports and call that understanding.
Transfer the contract and test design in three later gates:

1. **Board-game gate:** show that concept-grounded chess explanations beat
   labelled baselines in the blind evaluation above.
2. **Sports representation gate:** map the same record to timestamped
   soccer/football evidence: entities, regions, relations, candidate actions,
   counterfactual model evidence, source frames/tracks, confidence, and
   abstention. Create sport-specific ontology and relation extractors.
3. **Coach-usefulness gate:** on rights-cleared, held-out sport data, compare
   evidence-linked explanations with value-only/deterministic baselines using
   independent tactical annotations and a permissioned coach workflow. This
   remains blocked by the existing sports rights, annotation, calibration, and
   coach-validation gates.

The project may learn implementation lessons from chess (state encoding,
evidence pointers, explanation checking, counterfactual disclosure), but it
may not infer that chess success proves soccer or American-football skill.

