# Goal queue wording repair — 6 October 2026

The overnight Sports goal queue had one invalid item. Its chess explanation task carried 4,160 instruction characters, while the Studio queue accepts at most 4,000. That meant the queue could not be admitted even though its other fields and dependencies passed inspection.

I shortened repeated evidence descriptions and the final holdout reminder without changing the work requested. The item now has 3,732 characters. It still requires the same source and receipt pins, a sealed-safe exclusion check, no-forward model inputs, and independent review before any quality or expansion claim. The other four items were left as they were.

- Before: `GOAL_WORK.json` SHA-256 `f51beaafeb340f684bd3c08baedb6c14bd8928ca875987bd888cb04e5f294c42`; target instruction SHA-256 `f6cc22105219ee68d009bafec623b73d3f3cb1612b623c4a036defcd906f97ac`.
- After: file SHA-256 `0ff9d7ea4cefeb0b931157db642943f6fd1208db8397115aed524eb6558f9fbc`; instruction SHA-256 `5613f9758c7d87ce5e85742d83e86f29a4e9b0269db5cb754d9f9da4ac0729c0`.
- Studio's `readGoalWorkAgenda` accepted the changed file with five items, five pending, and four currently dependency-eligible when evaluated with completion forced false. That is a schema and dependency check, not completion of any item.

The preexisting goal call ended in a retry state after an empty model completion. This wording repair was applied only after that call had released the model route and the Sports project was paused under its existing maintenance operation. The saved retry and its failure evidence remain available for later diagnosis; this edit does not claim to fix the empty completion.
