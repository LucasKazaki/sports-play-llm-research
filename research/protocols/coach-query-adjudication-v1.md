# Coach-query retrieval adjudication protocol

**Internal draft; NOT_SENT, NOT_EXECUTED, unscored. SYSTEMS GO / SEMANTIC NO-GO.** These are proposed methods, not coach requirements, approvals, or results.

## Evidence context

The September 6 literal-search/local-video rehearsal passed 23 system checks. Historical exploratory corroboration was 3/166 mapped annotation labels and 3/54 predictions; 0/6 selected direct inspections were fully supported. These are neither mAP nor representative accuracy. Sources: `artifacts/demo-readiness-2026-09-06-v1/receipt.json` and `research/soccermaster-longform-technical-report-2026-08-27.md`, relative to the project root. The draft itself proves no evaluation occurred.

## Draft query categories

Hypothetical examples, not actual coach requests or observed events:

- Build-up: "Show a sequence of passes progressing out of defense."
- Pressing: "Show opponents closing down the player in possession."
- Transition: "Show the first actions after a possession loss."
- Set-piece: "Show a corner delivery and its immediate outcome."
- Individual off-ball movement: "Show a forward's run before receiving a pass."

## Separate grading dimensions

Score each dimension independently; never combine them into one score.

- Retrieval relevance: 0 = wrong event or no requested aspect visible; 1 = only some requested aspects visible or relevance ambiguous; 2 = all requested aspects visibly supported.
- Explanation faithfulness: 0 = a material contradiction or unsupported assertion; 1 = no such material error, but some claims remain visually ambiguous; 2 = every substantive claim is visibly supported and uncertainty is accurately stated. No explanation: N/A, never 0. An explicit abstention is recorded separately and is not a semantic success.
- Time localization: score the claimed event interval, not the returned clip's playback bounds. 0 = wrong event, wrong half, outside clip, or no temporal overlap; 1 = same event and positive overlap, but at least one endpoint differs by more than 2 seconds; 2 = same event and both endpoints within 2 seconds. No event-time claim: N/A, never 0. The 2-second tolerance is a proposal to validate in calibration and freeze before scoring, not a measured accuracy target.

For each query, define the visible event and onset/offset rule before scoring: first qualifying action to last qualifying action. Record half and clip-local seconds plus source-video offset; do not equate scoreboard time with video time without a documented mapping. For sustained patterns, predefine the required observation span. Occlusion, missing media, or an indeterminate reference interval: UNSCORABLE with reason, not N/A or an invented score. Retain uncertainty intervals and all exclusions.

## Blank per-reviewer worksheet

Use one row per query/result/reviewer. No observations have been entered.

| Query ID | Category | Exact query | Clip ID / half / offset | Claimed interval | Observed interval / uncertainty | Relevance | Faithfulness | Localization | Evidence / missing reason / abstention | Reviewer ID | Disagreement | Resolution |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | | |

## Proposed procedure and decisions

1. Confirm useful queries with a coach and permitted media use with the responsible rights owner. Name two independent reviewers and a separate adjudicator. No contact or data acquisition has occurred.
2. Separate calibration from a locked holdout before tuning or scoring. Group by match and deduplicate overlapping windows across splits. Freeze query IDs, source hashes, outputs, event rules and tolerance. Log any later amendment; do not retroactively tune the scored protocol.
3. Blind reviewers to model identity and each other's ratings. Retain both raw ratings; the adjudicator records disagreement, evidence and resolution separately, without overwriting them.
4. Pre-register total queries, returned results, dimension-specific scorable denominators, exclusions, N/A, UNSCORABLE and abstentions. Report each dimension's 0/1/2 distribution and failure cases; do not silently drop missing evidence or claim mAP.
5. Semantic readiness requires agreed coaching usefulness, permitted data, a frozen protocol and completed independent human scoring against predeclared acceptance criteria. None is established by this draft. Internal edits may continue. Any shareable candidate follows the repository's Luna review then Terra inspection/promotion sequence; external sharing still requires Lucas's authorization.
