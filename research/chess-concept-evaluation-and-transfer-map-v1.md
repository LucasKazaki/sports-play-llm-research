# Chess Concept evaluation packet and chess-to-soccer/football transfer map v1

**Status:** Internal plan only — SYSTEMS GO / SEMANTIC NO-GO.

## Purpose and current evidence

This packet defines evidence needed before any chess-concept result is evaluated or discussed as transferable. The current prototype has loopback local-model interoperability on a labelled synthetic contract fixture and deterministic validation. Candidate references in that fixture are synthetic and are not engine receipts.

python-chess is present. Stockfish is absent, so engine-backed comparison is NOT_EVALUABLE. No commentary, audio, video, creator material, or external sports dataset is in scope.

## Evaluation record required for every example

| Field | Required state |
| --- | --- |
| Position identity | FEN plus source/provenance |
| Candidate move | legal-move validation result |
| Chess evidence | engine receipt, or explicitly absent |
| Explanation | model output separate from evidence |
| Confidence | value plus calibration status |
| Abstention | reason when evidence is insufficient |
| Reviewer decision | pass, fail, or not evaluable |

## Measures and gates

| Measure | Current state | Release gate |
| --- | --- | --- |
| Legal-move fidelity | NOT_RUN | every evaluated candidate is legal |
| Engine agreement | NOT_EVALUABLE | reproducible engine receipt required |
| Evidence attribution | NOT_RUN | all claims link to source |
| Confidence calibration | NOT_RUN | measured held-out records |
| Abstention behavior | partially guarded | unsupported claims abstain |
| Human concept quality | BLOCKED | blinded protocol and reviewers |

A response, synthetic candidate ID, or legal move alone does not satisfy engine agreement, concept quality, or calibration.

## Chess-to-soccer/football transfer map

| Chess construct | Careful football analogue | May transfer | Does not transfer |
| --- | --- | --- | --- |
| Space control | territorial access/passing lanes | spatial vocabulary | scoring or optimal action |
| Initiative | ability to force responses | sequence prompts | causal credit or possession value |
| Piece coordination | coordinated player roles | interaction language | player tracking or team tactics |
| King safety | goal-risk management | risk framing | objectives and event outcomes |
| Candidate variations | alternative action sequences | counterfactual structure | football forecasts |

## Semantic NO-GO

No chess evidence or explanation may be represented as proof of soccer or football understanding, prediction, coaching validity, player evaluation, or tactical truth. This map is vocabulary only. A football-facing claim needs sport-native, rights-cleared provenance and independent evaluation; chess engine receipts never substitute for it.

## Activation order

1. Obtain a legal-board fixture with stable provenance.
2. Add an engine receipt before measuring engine agreement.
3. Run held-out legal, attribution, confidence, and abstention checks.
4. Review explanations separately from engine evidence.
5. Consider sport-native transfer only after data, rights, and evaluation are independently approved.
