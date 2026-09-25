# Live Demo Adversarial Audit — 2026-08-27

## Decision

**GO for a controlled, loopback-only private presentation.** No P0, P1, or P2 issue remains open. This is not approval for public hosting or media redistribution. Final browser actions were performed by the coordinator because the audit worker's local launcher failed.

## Resolved findings

- Correctness copy now refers to mapped SoccerNet point-label timestamps and explicitly states that visibility was not independently adjudicated.
- Requested-set metrics are recomputed from bound per-clip records; aggregate or per-clip disagreement fails closed.
- Exact schema, provider, valid-split, model, prompt, config, manifest, frozen-runtime, provenance, private prediction, and commentary bindings are validated.
- NaN and Infinity are rejected. Confidence must be finite. Abstention, reason, and evidence fields must be coherent. Non-abstentions require an ordered in-range temporal interval and nonempty string spatial evidence.
- Safe clip IDs, post-resolution private-root confinement, byte hashes, HTML escaping, and VTT escaping are enforced. Rendering uses no `innerHTML` assignment.
- Visual media must declare zero audio streams; the review copy must declare at least one. Presenter clips must be 10.0 seconds. The native `ended` event unlocks commentary and the mapped label, which remain separate.
- The interface discloses that playback gating is presentation choreography, not access control.
- Each commentary copy has a hash-bound VTT and an escaped visible transcript derived from SoccerNet-Echoes evidence. Tabs and panels expose ARIA roles, Arrow/Home/End navigation, visible focus, live status, and a reduced-motion override.
- Output is fully written and hashed in a staging directory. Replacement creates a backup and restores it if promotion fails.

## Rebuilt artifacts

| Demo | Index SHA-256 | Receipt SHA-256 | Visual | Commentary |
|---|---|---|---:|---:|
| Qwen comparison | `de346f568c7d8cb7641f57c02351c8cedf299eee1200d37b82f2f0afdb132f4e` | `923e70692ce14a81b9b5aa32f0f4929c31b58277113ed1ea16f9c8214b4fb7ac` | 6 complete, 0 failed | 6 records |
| Gemma recovery v2 | `f0448eac0c23abf967d6bd90c52f57c0fee1bf28a15202848682268b1dd0ad49` | `942d627c83d6dbfe813523d6aed7a85854dfe30876451d188cdb08556be6435a` | 6 complete, 0 failed | 6 records |
| Gemma primary v1 | `0b2fa5fbfc5c2194b7040d8dbb1ad93ab29ef8cbf3615d8f7d2a37e7fc70183c` | `44591b492702593a6a9b718523493b0f62c1823ff22de1072e29038aa4a3cd47` | 3 complete, 3 failed | 2 records |

For all three builds, the receipt matches the index, all 18 media records re-hash correctly, all six VTT records match their source-evidence hashes, and the privacy/path/legacy-claim scan is clean.

## Result recomputation

- Qwen comparison: 6/6 schema-valid, 3/6 allowed-window correct, 1/2 exact on single-label windows.
- Gemma recovery: 6/6 schema-valid, 0/6 allowed-window correct, 0/2 exact.
- Gemma primary v1: 3/6 schema-valid, 1/6 allowed-window correct, 0/2 exact.

These are small-sample systems observations from six curated windows in one match, not benchmark or population estimates.

## Browser verification

The Qwen demo loaded over loopback HTTP. It exposed six accessible tabs. Keyboard playback of the full real clip fired the native end event and unlocked the commentary and mapped-label controls separately. The commentary panel played the review copy, the mapped-label panel opened separately, and the hash-bound transcript expanded to six timed ASR segments. Browser console logs were empty. The static CSP disables connections and all requested assets came from the loopback server.

## CSP and residual P3

The generated page uses:

`default-src 'self'; media-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`

The remaining P3 is the use of inline CSS and script under a corresponding CSP allowance. The artifact is an offline, generated, loopback-only page with no user-authored HTML injection path; this is acceptable for the controlled demo. Reduced-motion behavior is already implemented.

## Tests observed during the audit

- `python -m pytest tests/test_build_live_demo.py -q` — 38 passed.
- `python -m pytest tests/test_commentary_crosscheck.py -q` — 30 passed.
- Final fresh repository suite — 163 passed in 7.99 seconds.

The final independent re-audit also passed the 15-slide overflow/render check, inspected every current slide, found no package-level secret or private-path disclosure, reloaded the latest Qwen UI with no browser-console errors, and repeated clip 5's full silent-playback → commentary/ASR → mapped-label → technical-inspection sequence.

## Caveats for the presentation

Playback gating is not access control. Hashes are bindings, not signatures. Media remain private and non-redistributable. The sample is six windows from one match; Qwen was chosen post hoc; its image grouping differs from Gemma's; point-label visibility is unadjudicated; self-scores are uncalibrated; temporal and spatial grounding are unscored; and ASR is noisy same-event evidence rather than ground truth. Within these constraints, the page is suitable for the controlled live demo.
