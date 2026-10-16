# Queen coaching supervision corpus v1

The CPU corpus completed all 1,568 planned Stockfish teachers and exported
2,048 training records, 64 development records and 32 held-out inputs. There
were no failed, unknown or never-run teacher outcomes. These are supervision
and software results. No learned model or GPU call occurred in this intake.

The source is the retained, pinned 294,920,084-byte CC0 Lichess Parquet shard.
Frozen v5 source-order selection consumes only the first setup move. Source
solution tails and themes are unused. Original games and before/current board
roles exclude the prior registry, head groups and selected successors, all 96
Queen pool games and teacher successors, and four authored response boards and
their legal critical-line successors. Historical exclusions apply to candidate
root boards; future teachers can revisit older spent boards. New cross-split
root/PV or PV/PV board overlaps are rejected before export.

Protocol-v3 was frozen and independently reviewed before intake or engine
dispatch. Earlier unexecuted protocol candidates remain intact. Selection filled
1,024 TRAIN games, 32 development games and a 512-game held-out reservoir after
140,963 source rows. All 512 reservoir games remain reserved for future exclusion,
including the 496 not selected for the final held-out inputs.

Each game has two stable cases: free FEN-only input and FEN plus the teacher's
selected legal best move. Grouping and splits follow the original game. Targets
use native piece/square/capture/promotion descriptors, verified by the frozen
Queen parser and legal replay. The short ANALYSIS states only check/mate and
capture facts. BEST_MOVE, at most three CRITICAL_LINE plies and PROMISING_MOVES
are teacher-bound; EVALUATION is terminal mate/draw or Not assessed. No generic
strategic rationale is asserted. Selected-move agreement is assisted by its
supplied move and must be reported separately from free move choice.

After every planned teacher completed, the first source-order full three-ply
roots filled the fixed, mutually exclusive held-out quotas: 2 discovered/double
checks, 2 king movers, 2 pawn movers, 4 remaining checks, 4 quiet moves and 2
nonchecking captures. The first four full three-ply development games are fixed
for eight raw generation cases. No model output influenced either selection.

Private train/development target files and evaluator reference files are
separate. Held-out input records contain no response. Held-out references stay
private and may be inspected semantically only after completed prediction
ledgers. The public summary contains hashes, counts and scope, without private
source rows, PGNs, target text, weights, media or chat history.

Three CPU workers each used one pinned Stockfish19 process, one thread, 32 MiB
hash and 50,000 requested nodes per root. Search can overshoot its node target.
Each root has a 30-second owned deadline and shared owned CANCEL control.
Create-only attempts retain fsynced pre-call intents, incoming raw UCI lines and
completed outcomes. Interrupted active calls are distinguished from never-run
cases; attempts cannot be replayed. The setup-failure regression verifies that a
failure after reserving an attempt still closes every planned status. All raw
journals, failures and executed source snapshots remain in the private package.

The intake passed 21 CPU tests and an independent pre-execution source review.
The closed corpus also passed independent readiness audit of all source locations,
exclusions, legal teacher continuations, raw journal intents/outcomes, exports,
fixed held strata, development IDs and file seals. Held-reference content remained
unopened. The auditor observed zero teacher-successor revisits to older excluded
boards; the protocol itself guarantees historical novelty only for input roots.
A separately frozen training/evaluation plan is still required. This establishes
neither learning, playing strength, factual generated commentary nor tutoring
quality. Local exclusion checks cannot establish absence from publisher pretraining.
