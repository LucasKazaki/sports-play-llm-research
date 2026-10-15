# V9: checked alternatives and conditional consequences

This is a **development-only software candidate** for the four already known
Chess.com practice positions. It has made no model or engine call and has not
passed the project's native function-level source review. The four plies come
from one game, so neither this check nor a future four-attempt trial is a fresh
holdout or a measure of Game Review parity.

V9 keeps v8's nine-field pre-move generator projection and source check. The
input is bound to PGN SHA-256
`684f9481f831b1605c3eb82d9bc33a1a0ca299ea3756e6a33a55f133cc997075`
and the exact ply/FEN/move pairs at 33, 46, 57 and 93. A packet carrying a
future board, PV, continuation, alternative score, review label or other
unknown nested field fails before projection. The same vocabulary is offered
on every case. No expected answer, Chess.com wording or sampled engine
alternative enters the prompt.

The model may abstain or return one exact typed JSON claim. It selects every
square, alternative and conditional move used in the text. The offline checker
replays the named moves, rejects false board facts and malformed JSON, then
renders short fixed sentences and a reusable cue. It never displays a free-form
causal story. Its new queen branch asks for a different legal non-queen move
that attacks the named knight. In this known position, a synthetic claim for
`17.Rc1` is verified: the rook attacks the c3 knight, but the queen on d1
remains attacked. A model-named `...Nxd1` is one legal reply that captures
the queen. This is a conditional example, **not** a ranking of `Qc2` and
`Rc1`; it also does not identify the best alternative. The checking capture,
rook-on-open-file choice and passed-pawn cases reuse v8's legal replay and
bounded wording, with fixed teaching cues. The rook case still cannot explain
why `Rac1` was inferior.

No ordering is emitted by v9. `comparison_admissibility` is an evaluator-side
guard only: a missing score, mate score or bounded score abstains; two
unqualified centipawn values are deferred until a separate, source-verified,
predeclared paired evaluator receipt exists. It computes no delta. In
particular the retained 10,000-node ply-57 pair contains an upper bound for
the alternative, so it cannot support a "why bad" contrast. Even a later
valid search-score ordering would be a finite engine observation, not proof
of Stockfish's strategic intent or a human teaching result.

## Retained local verification

The fail-first focused command
`.venv-soccernet\Scripts\python.exe -m pytest -q tests/test_chess_no_forward_teaching_v9.py`
exited 1 at collection with `ModuleNotFoundError: No module named
'chess_no_forward_teaching_v9'` before the source was added. After the
implementation, the same focused command passed **28/28** checks; the v8 and
v9 combined command passed **44/44**. The checks exercise true and false
queen alternatives, legal and illegal conditional replies, the three other
mechanisms, fixed cues, source/case mismatch, nested no-forward exclusions,
duplicate and nonfinite JSON values, deep nesting, abstention, and bound-aware
comparison deferral. They are synthetic software fixtures, not model-quality
observations.

A separate read-only local integration rebuilt all four packets from the
retained PGN, paired-review JSON and rendered page, requiring their exact
hashes and legal source replay. Four **synthetic** typed claims were accepted
against those source-bound packets, with zero new model and zero engine calls.
Packet SHA-256 values in ply order were:

| Ply | Packet SHA-256 | V9 nine-field projection SHA-256 |
| --- | --- | --- |
| 33 | `68a93644e372d4df7058fdae2866c6bc1ceee56e27b9240801842c2ca1bb0fae` | `7c70158228d817860ef5324720e4ab7463e4a39f9cb529af2b172111e3e12e49` |
| 46 | `2d377b2e0223a9fb9c4d01ba060c15078dc788aef233eb68fe52a861a5f735aa` | `0c97c3f4b518c11d70e24a74cd5d6ce7c138cfaf3ae6fee6997b7a8fe2769ef5` |
| 57 | `76d906526abaed37760bea838cec7671b9a093e607895f057f61c35cad767597` | `d40f62a8ef428f27920fd3a11d8e94b35b9da1ed1bfbc1fdcf7f5dfce2cd9628` |
| 93 | `3219c8c925997a9b02d4446f9ff04dd62a88a8bf6f815b43a141f4669b4c24eb` | `d043d1b5df046fe286227ca19549e4934c973d027760095084eda82296911b9d` |

The final source `scripts/chess_no_forward_teaching_v9.py` is 12,401 bytes,
SHA-256 `1ed2505f1fec9f51d056592113e236f06a48a341d4fe2a6f3674acaf72472ebc`.
The test `tests/test_chess_no_forward_teaching_v9.py` is 12,512 bytes,
SHA-256 `2bc87e3db1e9bade98368999e2afb0229435cd598f6c3479677babed65a78caf`.
The dependency v8 source was SHA-256
`679aa235d72eb1f3de4553e60c9c3e5ff87c28b0e81e2a6f2d3c2b638ffd03e6`
when this work began.

Next, route the exact v9 source, relevant tests and retained result through the
project's finite native function-level source review. Only after that passes
should a create-only four-case model trial be frozen and run, keeping every
attempt in its denominator. A separately verified evaluator may inspect only
the alternative the model actually named. Qualified chess judgment and the
game-disjoint commentary gate remain independent requirements.
