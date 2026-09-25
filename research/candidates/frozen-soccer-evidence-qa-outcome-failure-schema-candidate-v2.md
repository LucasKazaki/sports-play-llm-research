# Frozen Soccer Evidence-QA Outcome and Failure Schema v2

## Frozen Queries
- The query 'What was the score at halftime?' is frozen and must be answered with the exact score from the official match report.
- The query 'Who scored the first goal?' is frozen and must be answered with the name of the player as recorded in the official match report.
- The query 'What was the weather like during the match?' is frozen and must be answered with the weather conditions as reported by the official match report.

## Answer-Level Provenance Requirements
- All answers must be explicitly sourced to the official match report or a publicly available, peer-reviewed source.
- If a source is not available, the answer must state 'Source unavailable' and provide a clear explanation of why the source could not be found.
- Answers must include a timestamp of when the source was accessed.

## Abstention and Failure Taxonomy
- **Abstention**: If the query is outside the scope of the match report or if the required information is not available in the official sources, the system must abstain from answering and state 'Abstention: Information not available in official sources.'
- **Failure**: If the system provides an answer that is factually incorrect or contradicts the official match report, the system must fail and state 'Failure: Answer contradicts official match report.'

## Explicit Metric-Ineligibility Gates
- No metrics such as 'most popular player' or 'best performance' are eligible for evaluation.
- Any metric that relies on subjective opinion or unverified data is ineligible.
- All metrics must be based on verifiable, objective data from official match reports or peer-reviewed sources.