# Local model and SoccerMaster reasoning viability

## Purpose

Test whether the current local models can support the project in two distinct roles:

1. translate a coach's natural-language request into a constrained search plan; and
2. reason over sealed VLM and SoccerMaster-related evidence without inflating the scientific claim.

This is a local viability check, not a performance benchmark. It does not reproduce the official SoccerMaster checkpoint and it does not establish that the current VLM reports are factually reliable.

## Current local model availability

- LM Studio is live on loopback at `127.0.0.1:1234`.
- `openai/gpt-oss-20b` is installed and loaded for local text reasoning.
- The previously used Gemma and Qwen VLM checkpoints are represented in saved, hash-bound experiment artifacts, but their weights are not currently installed or loaded on this machine.
- No remote model or private media upload was used in this viability check.

## Existing visual-model evidence

- The sealed 50-window local Gemma run returned 50 valid responses, with 3 exact matches out of 50 and a 48% abstention rate. `performance_claim_allowed=false` and the detailed claims are not safe for coach search.
- The sealed long-form local run returned 96 valid responses over 96 windows and reported 361 events. Detailed-claim factuality and event accuracy were not measured before sealing.
- A selected six-window Qwen engineering probe completed all six requests and mapped 3/6 outputs to allowed labels, but it was post-hoc and used a different representation. It is not a controlled Gemma-versus-Qwen comparison.
- The local SoccerMaster-scale and long-form code is a pipeline scaffold around VLM outputs. It is not a reproduction of the official SoccerMaster checkpoint or paper metrics.

The current truth boundary remains: **SYSTEMS GO / SEMANTIC NO-GO**.

## Local GPT reasoning checks

### Coach-query planning

Five representative coach requests were sent to the loaded local `openai/gpt-oss-20b` model through the strict search-plan contract. All five returned schema-valid plans from the local model without falling back to rules. Median latency was 14.057 seconds.

Four plans were directly useful. One request about a cutback leading to a shot mentioned the shot in its explanation but omitted it from the actual search terms. This is promising interface evidence, but it is not a retrieval-accuracy result because the five queries were not preregistered or independently scored.

### Evidence-bound research reasoning

`prototype/reasoning_viability.py` sends only sealed aggregate evidence to the local model and checks its answer against frozen claim gates.

- First run: failed because one blocked claim was duplicated and `coach_ready` was omitted.
- Repair run: passed the original validator, but the prose changed the 96-window denominator into a “96-clip window.” This exposed a validator gap.
- The validator and test suite were strengthened to reject that unit substitution.
- Final run: preserved the correct `systems_only` verdict, all four blocked claims, and every structured metric, but wrote `None` instead of a supported 96-window finding. The strengthened validator rejected it.

The model therefore appears useful for constrained query planning, but it is not yet reliable as an autonomous scientific evidence summarizer. The deterministic gate is doing real work: it caught claim-list completeness, unit drift, and an unsupported empty summary.

## Verification

- Focused reasoning, search, hosted-video, SoccerMaster-scale, SoccerMaster-long-form, and evidence-gating tests: **74 passed**.
- All reasoning calls were loopback-only.
- Every evidence-reasoning request, raw response, parsed result, source hash, latency, and deterministic failure is preserved under:
  - `artifacts/local-reasoning-viability-v1/`
  - `artifacts/local-reasoning-viability-v1-repair/`
  - `artifacts/local-reasoning-viability-v2/`

## Research consequence

The viable near-term design is a hybrid:

- VLM or SoccerMaster-derived components produce explicitly attributed visual or structured evidence;
- a local or hosted GPT model turns that evidence into a query plan or candidate interpretation;
- deterministic validators preserve counts, units, provenance, claim gates, and abstention rules;
- a human-reviewed held-out set scores semantic accuracy and coach usefulness.

The next controlled reasoning experiment should freeze a small set of evidence packets and coach queries, then compare the local GPT model with GPT-5.6 Luna on the exact same JSON. Score schema validity, evidence copying, unit fidelity, unsupported claims, abstention, retrieval usefulness, and latency separately. A hosted comparison remains gated on credentials, zero-spend or explicit spend approval, and data rights; only derived non-sensitive JSON should leave the machine.

## Next executable work

1. Restore or install one local VLM checkpoint that fits the available hardware, then rerun frozen visual cases without changing the scoring contract.
2. Build the official SoccerMaster checkpoint/dependency/license preflight and keep its outputs separate from the current scaffold.
3. Freeze the cross-model reasoning cases and scoring rubric before any hosted GPT run.
4. Generate coach-facing prose deterministically from validated evidence fields until free-text model summaries pass the frozen faithfulness checks.
5. Continue the searchable event-card demo while keeping all current semantic claims visibly marked as unvalidated.
