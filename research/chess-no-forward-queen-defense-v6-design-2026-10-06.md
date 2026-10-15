# A safer queen-capture lesson to test after v5

The [Chess.com practice replay](chesscom-queen-capture-defense-2026-10-06.md) found a useful distinction after the shared reply `20...Qxd4`. After `20.Qe4 Qxd4 21.Qxb7+`, White's bishop on f3 attacks b7; `...Kxb7` is illegal and Black's only legal reply is `...Kd7`. After `20.Qc3 Qxd4 21.Qxc7+`, no White piece defends c7 and Black's only legal reply is `...Kxc7`, taking the queen. Both branches can also trade queens and reach the same board. This is one conditional teaching example, not a proof that `Qc3` forces a queen loss or that Stockfish preferred `Qe4` for this reason.

## What the current checker misses

In `scripts/chess_no_forward_teaching_v5.py`, `evaluate` (lines 84–129) delegates its witness search and sentence to v4 (lines 111–117). In `scripts/chess_no_forward_teaching_v4.py`, `_candidate_witnesses` (lines 118–185) searches for an option available to the model's proposed alternative but unavailable from the selected move's destination. It can find `Qe4 Qxd4 Qxb7+` when the model proposes `Qe4`. `_teaching_text` (lines 188–200) then says that, after `Qc3` and the same reply, the queen cannot reach b7. The checker does not inspect the selected branch's similar `Qxc7+`, either destination's defenders, or Black's legal captures of the queen. The test in `tests/test_chess_no_forward_teaching_v5.py` (lines 94–113) asserts that *some* `Qxb7+` witness exists; it does not require that witness to be chosen or establish the safety comparison.

## Smallest bounded follow-up

Wait for the frozen v5 practice result. Keep the v5 generator's nine pre-move fields and exact proposal shape unchanged. Add a separately versioned **offline evaluator** and result schema, with its own source/dependency hashes; do not rewrite v5 receipts or feed any later fact into generation.

1. Starting from a model-proposed same-origin alternative, reuse v4's common legal reply and identical-SAN checks. After that reply, examine a capture with check by the moved piece in the alternative branch and a legal capture with check by the same kind of piece in the selected branch. Require the captured piece types to match. If several pairs meet the conditions below, abstain from the stronger comparison instead of choosing a convenient one.
2. On a copy of each board **after** the checking capture, record which of the mover's other pieces attack the queen's destination, with piece type and square. Enumerate all legal opponent replies and check whether the king can legally capture the queen on that square. Only say “only reply” when the entire legal-reply enumeration proves it.
3. For the stronger “the bishop keeps the king from taking the queen” wording, require a sole relevant defender and an additional evaluator-only counterfactual check: remove that defender on a copied board and verify that the king capture becomes legal. If this fails, report the attack and legal-reply facts separately without assigning cause, or use v4's generic conditional sentence. Do not call the defended queen generally safe; this checks only the immediate reply in one line.
4. Prefer a verified, unambiguous defense contrast over the first generic v4 witness. When the model proposes a different move, the common reply is absent, the pair is ambiguous, or any legality/defense condition fails, emit the generic legal illustration or evaluator abstention. Never substitute `Qe4` for the model's proposal.

For this game, the resulting sentence could say: “If Black replies `...Qxd4`, `Qe4` leaves `Qxb7+` available. The bishop on f3 protects b7, so Black cannot take that queen with `...Kxb7` in this position. After `Qc3 ...Qxd4`, the tempting `Qxc7+` has no White defender on c7, and `...Kxc7` takes the queen. This compares those two choices after one reply; it does not explain the engine score or the other replies.” Every clause must be backed by the recorded board/reply checks before using this wording.

## Adversarial checks before a practice claim

- The source FEN must yield the exact two legal three-ply lines, defender lists, full Black reply lists, and the bishop-removal sensitivity check. Also verify the common queen-trade board so the text cannot claim `Qe4` prevents `...Qxd4`.
- Captures of different piece types, a nonchecking capture, different SAN for the nominal common reply, or a reply missing in either branch must not produce the comparison.
- If both destinations are defended, both are undefended, another defender remains after removing the bishop, or a separate check makes the king capture illegal, the checker must not attribute the contrast to that bishop.
- An undefended destination without an adjacent king or without a legal king capture must not be described as an immediate queen loss. A checking capture without a unique legal reply must not be described as forced.
- A different model alternative, including the earlier `Qb3` proposal, must not acquire this example by evaluator substitution. The generator projection must still reject any reply, later move, post-move position, defender, engine line, or review label. Synthetic tests establish checker behavior only; the real practice response and all abstentions remain in their original denominator.

The saved finite-node Stockfish observations and one legal line do not measure why Stockfish scored the root moves differently, human teaching quality, or Chess.com parity. A later claim needs a fresh game-disjoint holdout and the project's independent commentary gate.
