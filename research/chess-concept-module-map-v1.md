# Chess Concept prototype — module map and scoped architecture decision

Generated from the verified local SportsPlay workspace by the Company Runtime native executor.

## Decision

Use one local, post-game-only, standard-chess review path built around the existing deterministic prototype. Keep exact board/state validation, evidence packaging, model-shaped explanation validation, and safe abstention as separate contracts. The prototype remains loopback-only and evidence-only; it is not a public deployment, a live-game assistant, a Chess.com replacement, or a claim of engine strength.

## Module map

| Concern | Existing module/contract | Decision |
|---|---|---|
| Demo/server boundary | `prototype/chess_concept_demo.py` | Reuse as the loopback preview entry point; preserve fail-closed readiness and safe abstention. |
| Concept model contract | `prototype/chess_concept_model.py` | Reuse as the model-facing normalization boundary; never treat generated explanation as exact truth. |
| Output schema | `prototype/chess_concept.schema.json` | Keep as the structured result contract. |
| Explanation schema | `prototype/chess_concept_explanation.schema.json` | Keep separate from exact state/evidence validation. |
| Manifest validation | `prototype/chess_concept_manifest_validator.py` | Reuse for provenance and manifest checks. |
| Schema validation | `prototype/chess_concept_schema_validator.py` | Reuse for deterministic structural checks. |
| Environment probe | `prototype/chess_environment_probe.py` | Reuse for local capability reporting; no external service or credential assumption. |
| Regression coverage | `tests/test_chess_*.py` | Require the focused suite before any later candidate review. |

## Frozen scope

- Standard chess only; reject unsupported variants.
- Completed-game/post-game analysis only.
- Evidence must remain distinct from generated explanation.
- Invalid or insufficient position evidence must abstain safely.
- Loopback-only preview; no public hosting or publication is authorized by this artifact.
- No private footage, paid platform, contact, commit, push, or release action.

## Source fingerprint

| Path | SHA-256 |
|---|---|
| `prototype/chess_concept_demo.py` | `4db92bef4ab2435752f2366950b3cdd98ad7daa7a8740ec795bfd3792ec553fb` |
| `prototype/chess_concept_model.py` | `42e74da78e79669c3a0499d645a183dc5cdc8d422ed60cf3ec8128174bd88b76` |
| `prototype/chess_concept.schema.json` | `e8e2a114a4bf67b047b4b4e2740e57b61888cbe047df70230cdcfbb04e9ad87c` |
| `prototype/chess_concept_explanation.schema.json` | `294cdf597a3fcf0b4777f9f9e387449258dd627dd6252b790ea49bcf8dce8aae` |
| `prototype/chess_concept_manifest_validator.py` | `0eb01eb2b19644f5a76c1ba776de0a318067ea73a30cb3dc935762cfd66796b1` |
| `prototype/chess_concept_schema_validator.py` | `3cb6f1b4da7e14a9cdc15ccd3bce40140652718765bf3be4b318518f0d57f78f` |
| `prototype/chess_environment_probe.py` | `4e9ce4ef6e99481b42b749a83afe64203f367429286d5f7d363741c300313d7c` |
| `tests/test_chess_concept_demo.py` | `5e8273dbf0e87e848084f299d01fec88ec46585efdf68ebe8bac8ee0a7c37d72` |
| `tests/test_chess_concept_model.py` | `b7c25029bf2ca4ea41f093e6a7673338927e6dbe5a4b8fb88ef0fd25e24ce122` |
| `tests/test_chess_environment_probe.py` | `baf8bb7bcd0f2eb079eda8e21e7ba8a448f531d495656036e6bcbc57a556d845` |
| `tests/test_chess_concept_schema_validator.py` | `3e1aced1a4e5ea3f08c3785ca75c5546fbc4afafd42e2b99a5d08a76bcd6cd94` |
| `tests/test_chess_concept_manifest_validator.py` | `27c094ba33394d07c42c6beb19525ef4ccc1ad0add9c91cb6d3f72365e8034b2` |

## Acceptance for this slice

The module map is accepted only with a zero-exit focused deterministic test run and a retained native receipt. This document is an internal architecture decision, not a shareable or release-approved deliverable.