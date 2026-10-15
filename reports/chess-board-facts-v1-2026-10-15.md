# Immediate chess facts remain unreliable in the installed 27b model

The piece map improved some immediate move facts in a small development diagnostic, but neither input format was reliable. The run also failed before completing its 32 planned outcomes. All failures remain in the denominator.

| Input to the same fixed model | All eight facts correct | Strict completed responses | Moving piece correct | Capture flag correct | Captured piece correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| FEN and selected legal UCI move | 2/16 | 15/16 | 8/16 | 3/16 | 2/16 |
| Same input plus full pre-move square map | 5/16 | 15/16 | 14/16 | 7/16 | 7/16 |

Both formats were fully correct on two cases; the map alone was fully correct on three more. Neither was fully correct on the other eleven planned cases, including the interrupted pair. These are paired descriptive counts from sixteen convenience positions, with no significance or generalization claim.

## What was fixed before inference

The [frozen protocol](../experiments/chess-board-facts-v1/archive/board-fact-protocol-v1.json) specified sixteen new development games, eight output fields, one request per condition and case, alternating condition order, and strict failure-inclusive scoring. Selection used source order and a game-hash bucket in the retained 4 MiB CC0 Lichess puzzle prefix. An independent reconstruction excluded 21,688 prior games and 43,474 board keys across both source/setup roles, then matched every selected case and move. This does not establish independence from upstream model pretraining.

The selected legal move was a deterministic hash-indexed choice from sorted legal moves. It was not Stockfish's best move, a puzzle answer or a video observation. No model weights were updated. Both conditions used the installed alias `qwen3.8-27b-local-q2k:latest`; fresh backend metadata identifies family `qwen35`, 27.3B parameters and Q2_K quantization. The alias does not authenticate a model release.

The eight requested facts were moving piece, moving colour, capture status, captured piece, immediate check, castling, en passant and promotion piece. The optional map listed all 64 squares before the move, including empty squares. Generation received no labels, post-move positions, legal-move list, teacher values, puzzle annotations, video outputs or strategic explanations. Expected facts were stored separately and checked by predicate and board-transition routes, plus ten hand-specified fixtures.

The actual sixteen selected moves included three captures and one check, with no castling, en passant or promotion. The high counts for correctly reporting those absent special moves do not demonstrate competence on them. Both representations got the immediate-check field correct on 13/16 planned outcomes. There were no explicit `unknown` abstentions in the thirty completed responses.

## The interrupted attempt is retained

The original process made 31 generation requests. Thirty produced strict completed JSON responses. The 31st returned an incomplete envelope (`done=false`); the 32nd was never sent. At 06:45:10 UTC, Windows recorded virtual-memory exhaustion and the model server logged `std::bad_alloc` and exit 1. The caller then raised `MemoryError` while hashing the saved response body. The exact contribution of each resource consumer remains unresolved. No global memory or power settings were changed.

The original directory, source snapshots and progress file were preserved. A separate file-only recovery verified the thirty completed rows, classified the incomplete envelope as one backend failure, and retained the last row as not run. The incomplete call's elapsed time was unavailable and was not invented. The recovered raw evidence was sealed before separate evaluator access. No response was regenerated or repaired. The unload was confirmed, and the model was absent from the subsequent resident-model list.

The separate output audit checked fifty private seal bindings, reconstructed all 31 attempted prompts and requests, and independently recounted all 32 planned rows. Forty-four of those original bindings are distributed in the [evidence package](../experiments/chess-board-facts-v1/README.md). Six inventory/system-event artifacts remain private, with their hashes and omission reasons recorded.

## Software repair after the run

The exact executed runner and its 36-check test source are archived. The active repository copy is separately identified: imports and test discovery follow the repository layout, hashing uses 64 KiB blocks, and an outer failure handler stops later requests, unloads the model, then attempts to bind retained response bytes. It explicitly marks unavailable raw bytes and never retries generation.

Independent review found that an initial version of this repair could count a pre-call progress-save failure as an attempted request. A failing fake-client regression reproduced two actual calls versus three claimed attempts. The repaired wrapper records request preparation separately and marks an attempt immediately before invoking the client. All **39 focused fake-client/fixture checks pass**, including post-response allocation failure, raw-write failure and pre-call persistence failure. These are software checks; the revised wrapper was not used to regenerate this experiment, and it cannot guarantee recovery if memory or storage remains unavailable even after unload.

All sixteen panel games and both source/setup board roles are now spent development evidence. Future training, selection and independent evaluation must exclude them; rerunning the historical freeze procedure does not produce a new cohort.

The practical implication is to keep immediate board facts grounded in a rules implementation while investigating the local model's representation weaknesses. More large-model work needs a monitored memory preflight. These observations do not establish playing strength, faithful commentary, strategic understanding or sports transfer. Codex assistance is recorded; formal project promotion remains unmet.
