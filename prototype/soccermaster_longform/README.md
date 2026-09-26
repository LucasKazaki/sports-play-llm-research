# SoccerMaster long-form scale package

This soccer-only package freezes and runs a visual-only local VLM experiment over both complete halves of a newly acquired authorized SoccerNet test game. Raw media, frames, responses, labels, source names, and the complete index stay under `data/private/soccermaster-longform-v1`.

Protocol order:

1. `verify-source` hashes, probes, and fully decodes the two private halves without parsing annotations.
2. `prepare` freezes six label-free validation windows, 90 dense 60-second test windows, six 30/60/120-second test stress windows, prompt candidates, schema hashes, search queries, redaction, recovery strategies, and six direct spot checks.
3. `select-prompt` makes 12 local Gemma calls on validation footage only and selects by structural reliability and latency, never label correctness.
4. `run-test` locks the prompt and makes 96 visual-only test-window calls, builds a private report index, and runs the frozen queries.
5. `seal` hashes every visual input/output and pre-annotation retrieval result.
6. `evaluate` verifies the seal before opening SoccerNet-v2 annotations as a post-hoc evaluator.
7. `prepare-spotcheck`, human/agent adjudication, `verify`, `report`, and `package` complete the evidence bundle.

No stage sends audio, commentary, labels, source paths, filenames, team names, scores, game identity, or absolute match clock to the model. The top 16% of every frame is blacked out to remove the broadcast scoreboard/clock overlay. Prompt selection is not model fine-tuning. SoccerNet annotation matching is an evaluator, not an event detector. One game and sparse frames do not support deployment, generalization, detailed-prose factuality, or coach-utility claims.
