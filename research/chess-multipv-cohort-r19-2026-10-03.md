# SLM-C02-R19-MULTIPV-COHORT-BINDING-v1

Current production collector blob: `7dccf3525049c60a72f0a2883709012d86d6adfb`.

Bug: the collector saves the latest score event for each MultiPV rank independently. If a complete depth-18 rank-1/rank-2 output is followed by only a newer depth-19 rank-1 score before stream completion, current selection can combine depths 19 and 18.

Required repair: group original streamed Stockfish score events into complete rank cohorts. For effective MultiPV N, accept only ranks 1..N in order at one reported root depth. Scoreless events may interleave. Keep nodes/time/seldepth per rank; they need not match. A newer incomplete cohort makes the position fail closed. Never fall back to an older complete cohort or mix generations.

Cloud reference: Python 3.13.5 (-S), fail-first exits 1 with current-selection depths [19,18]; 18 focused tests pass; py_compile exits 0. These are reference checks, not native engine evidence.

Native acceptance requires the current-source fail-first, one real raw Stockfish transcript validating the rank/depth grouping assumption, passing collector/streaming regressions, a bound cohort digest, unchanged historical v2/v3 receipt hashes, and genuine Company Runtime task/run/read/result receipts.

C00 and the N/N+1 consumption canary remain the first native coordination gate. Latest genuine local report remains BUG_REPORT 5816973293.
