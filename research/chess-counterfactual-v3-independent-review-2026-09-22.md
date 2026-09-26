Independent internal review, 22 September 2026 UTC: **PASS for the bounded v3 chess evidence collector after correction.** No material defect remains in the reviewed scope. This disposition covers the implementation and the retained eight-development-position observation artifact; it is not scientific acceptance, an explanation-quality result, external promotion, or a substitute for the Luna → Terra shareable-candidate gate.

The reviewer did not author or change the chess product code. Review consisted of direct source/test inspection, reading the actual development-only artifact and projection, and reconciling current file bytes with three server-owned native receipts, all 30 command stdout/stderr pairs, and the 18-step native source-edit chain. Product tests and the Stockfish invocation ran only through Company Runtime. The reviewer did not import or execute product code, read the full dataset manifest or held-out labels, invoke a model/engine, or change product files.

The boolean-score defect is resolved: `typed_score_bound` validates the original relative `Score` and its integer scalar before perspective conversion. The retained regression covers `Cp(True)`, `Cp(False)`, `Mate(True)`, and `Mate(False)` in both same and opposite perspectives. The corrected native source chain also resolves the inaccurate staging-manifest “after” hashes: `chess-bound-stream-green-source-chain.json` is verified against each authoritative native edit log and ends at the installed collector hash. The original inaccurate staging record remains historical evidence and must not be used as the current source chain.

Validation observed:

| Check | Actual result |
| --- | --- |
| Focused helper/collector regressions after correction | 98 passed |
| Complete project verification | 1,226 passed; 1 skipped |
| Reproduction script | 25 passed |
| Doctor and log collection | Passed |
| Smoke | Passed; explicitly synthetic regression metrics |
| Safe reset | Preview only: `applied=false`, `destructiveDelete=false` |
| Real v3 Stockfish collection and separate receipt verification | 8 requested, 8 successful, 0 failed, 16 legal candidates |
| Score qualification | 12 unqualified (`exact`) observations, 2 lower bounds, 2 upper bounds |
| Score type | 15 centipawn observations and 1 mate observation |
| Chess collection model calls / held-out outcomes scored | 0 / 0 |

The skipped test is `tests/test_chess_broker_intake.py:133`: this host token cannot create its symlink fixture (`WinError 1314`). It remains a skipped host-permission control, not a passing assertion. Native command completion does not establish semantic quality of unrelated sports results; the smoke log itself labels its metrics synthetic.

The real artifact is `C:/AI/projects/SportsPlayLLMResearch/artifacts/chess-counterfactual-v1/dev8-node100k-v3.json`, SHA-256 `a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6`. Its development projection hash is `946754a1d52723786aaa4b63a60b5d499a9cc06470eac43a25601ea1da6e6316`; the projection contains exactly eight development items and omits solutions, themes, ratings, train items and test items. The declared source-manifest hash matches between the projection and receipt; the reviewer intentionally did not open the full manifest. The native source-integrity path supplied the underlying integrity/legal-replay checks.

All four implementation hashes in the real artifact match the current source:

| Source | SHA-256 |
| --- | --- |
| `scripts/chess_counterfactual_evidence.py` | `ee3a58965c700774a7a14ab3f77eb715b5ebfa33b28469e17b97b6b98456ea93` |
| `scripts/chess_score_bounds.py` | `6c7bc093547eeff142d8eea7e8ed3c0e265139e11db06f8e0858d2dc942ae85e` |
| `scripts/chess_dev_projection.py` | `1e3d09b05295b84ce808cf1068ce6181088c95cf8980b28a0abd4cb7e443a925` |
| `scripts/chess_real_data.py` | `d74f03d6829d789dca7725a611c8f453cc6e8be425d13b868aa0405d68fcbc11` |

The installed Stockfish binary also matches the artifact's `45bc8e4969147db9c2eb533810637994619bff0eacc81ccfd9854394901bcbd0` hash. The frozen settings remain one thread, 16 MB hash, two PV ranks and 100,000 requested nodes per position. Actual node overshoot is retained. Every result identity matches the same ordered development projection; no requested position has been removed from the denominator.

Source inspection and the native controls support these specific contracts: latest score, PV, depth, nodes, sequence and qualification originate from the same raw score-bearing event per rank; scoreless updates do not replace or supply fields; incomplete latest events are rejected; legal PV and transition facts are replayed; duplicate root moves and invalid evidence bindings are rejected; default v2 collection continues rejecting qualified scores; v3 explicitly records lower/upper qualification and engine-score ordering; perspective reversal flips bounds; centipawns and mate scores remain separate, including zero-mate direction. The real artifact's qualified scores have not been relabelled as exact values.

Native evidence identities:

| Work | Task / run / job | Receipt SHA-256 |
| --- | --- | --- |
| Collector installation | `afc6e65e-eb39-497b-ac4a-2aaa1f7eddd0` / `81c89bb3-b851-41e0-8467-42e1d74a1ef4` / `9616f72c-76ce-4b6f-aeee-a567dda3731f` | `b863a3f738de7a43071fff23be4cee4c0b3e63a64e23d2e81bc7840bedee9c37` |
| Boolean correction and regressions | `c59e571d-dd8c-4215-b958-f0d461fb57e3` / `abdf3882-fa49-40a4-ab9f-691ab62aba11` / `d307db58-6c84-4611-b167-764d7642eb13` | `a67cb6a7d170e6836eaefbdfaa268774528c55b06dfe917a78d57fa5b831b0c2` |
| Real Stockfish collection and required project checks | `eb3aaa88-699f-4f0e-89cb-c57c03f95232` / `3d58ac63-ecdf-4bed-83e2-3b306b5d48d9` / `4a35f153-8bf2-4c95-a304-e7f01cb80888` | `176f9b8a4f69d91299e408f2e0cd9d3051a50df32539d4c488c8b3ccdabfaa53` |

The complete independently reconciled evidence index is `C:/AI/projects/LucasAgentStudio/artifacts/systemic-productivity-20260921/chess-review/final-evidence.json`. It retains exact native receipt/log paths and hashes, per-position qualification summaries, binary/source/projection hashes, test outcomes and limitations.

Remaining limits are substantive: these eight positions are a tiny convenience sample; the engine scores have not been independently reproduced; `exact` means an unqualified engine observation, not mathematical ground truth; lower/upper bounds are in engine-score order, not centipawn intervals or statistical confidence; available setup history is retained but earlier game history is absent. Legal moves and coherent receipts do not prove explanation quality, teaching value, general chess competence, or sports transfer. Human/shareable acceptance is still separate.

The next useful requirement is a typed PositionEvidence/claim adapter on the same development-only inputs. Preserve exact/lower/upper qualification, cp/mate and zero-mate distinctions, perspective, and the complete requested/failed denominator. Add adversarial false-claim controls and abstention for unsupported comparisons before model-explanation evaluation. Any shareable candidate must still pass independent Luna review, material-defect resolution and later Terra director promotion; this internal review grants none of those external actions.
