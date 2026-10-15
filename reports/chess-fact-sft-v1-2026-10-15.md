# Local chess fact training — 15 October 2026

The RTX 5080 completed adapter training and a sealed held-out comparison. The selected adapter returns the eight-field schema on all 256 held-out positions and gets all eight facts right on 242. It identifies all 17 captures, but misses every checking move (0/13) and the only rook promotion (0/1). These failures define the next research question more clearly than the 94.53% aggregate score.

The base model returns zero exact-schema-valid responses. Its zero all-eight score is assigned by the frozen strict rule; it does not demonstrate absence of factual content. The comparison mixes formatting/task conformance and factual accuracy. It cannot establish improved chess knowledge, strategic understanding, commentary quality or playing strength.

## Method and evidence

The pinned Qwen3-0.6B base has 596,049,920 unique frozen parameters. LoRA trains 5,046,272 parameters for 1,024 updates over 8,192 examples, with no repeated training example in the fixed permutation. Inputs contain the pre-move board, selected legal move and board-derived piece map. Eight rule-derived targets supervise immediate move facts. This complements earlier Stockfish move training; it does not distil video commentary or an identified frontier model.

The CC0 Lichess convenience-source cohort contains 8,192 training, 128 development and 256 held-out positions, separated by original game and filtered against the retained prior-game/board registry. Independent intake review verifies all 8,576 selected rows and the source selection trace. Upstream pretraining overlap is unknown. Development/held-out sets contain no castling or en-passant positives; the only held-out promotion is to a rook.

Development all-eight counts at steps 0/128/256/512/1024 are 0/111/115/118/118 out of 128. The fixed earliest-tie rule selects 512 before held-out generation. Both held-out raw batches are sealed before scoring; all seven development/held-out batches are verified before any audit truth join. All 1,152 planned responses complete, with no runtime error, truncation or missing outcome. The frozen base digest before/after training is identical.

The selected model gets moving piece, colour, capture flag and captured piece right on all 256 cases. Its check output is false on all 256: 243 correct negatives and 13 missed checks. Its promotion output is null on all 256: 255 correct negatives and one missed rook promotion. All 14 all-eight failures fall in those two rare-positive groups. Aggregate field accuracy would hide this collapse.

The supervised job takes 4,012.094 seconds including evaluation/final writes. Its 3,849 resource samples have a maximum interval of 1.078 seconds. Minimum available physical memory, commit headroom and free GPU memory are 9,553,625,088, 11,404,517,376 and 10,345,250,816 bytes. A retained training snapshot shows 98% GPU utilization at 62°C; it is not a sustained or peak claim. No resource cancellation or forced termination occurs.

## Engineering limits

Two earlier amended attempts remain preserved. The first stops on Windows process identity before model loading. The second completes 16 baseline-development responses before Windows denies replacement of a progress file, with zero optimizer updates. The exact lock holder was not captured. The third attempt repeats those baseline prompts under unchanged settings and never pools interrupted results. Repairs address actual interpreter ownership and bounded file replacement; model generation and optimizer work are never retried.

Focused launch/persistence verification records 83 passes and one deselection. The mandatory historical compatibility run separately records 9 failures, 5 passes and 89 errors from unavailable private fixtures. No full-suite pass or historical gate restoration is claimed. This practical engineering review is distinct from the repository's formal research-promotion gate.

The public package contains 137 exact-byte files and 19 private-artifact hashes: raw outputs, source snapshots, acquisition, cohort checks, failed-attempt records and completed review. Weights, optimizer state, source shard and copyrighted video media remain local. Publication checks authenticate all 184 bound inputs and membership of the cohort/three attempt directories before copying/deriving results. A publication helper ordering failure was preserved and narrowly corrected without changing experiment artifacts or making new model calls.

## Next bounded question

Can a separately frozen, game-disjoint diagnostic distinguish check detection from schema learning, and assess positive promotions, castling and en passant with explicit class support? These held-out observations are spent. A successor needs its own question, source/exclusion manifest, predeclared metrics and sealed generation; this cohort must not become an untouched selection set again. The adapter remains a candidate.

This is Codex-assisted research engineering. No human-only authorship, detector guarantee or supervisor approval is claimed. [Experiment](../experiments/chess-fact-sft-v1/README.md), [summary](../experiments/chess-fact-sft-v1/summary.json), [completed review](../experiments/chess-fact-sft-v1/evidence/independent-completed-review.json).
