# Final verification — 2026-08-27

## Verdict

**GO for the private, local Archit presentation and live demo.** No blocking defect remains. **NO-GO** for benchmark, population-generalization, calibrated-confidence, validated-grounding, causal model-ranking, trained-model, public-hosting, or media-redistribution claims.

## What is verified

- The empirical path uses authorized real SoccerNet broadcast clips linked to SoccerDB identities through SoccerDB's pinned public mapping. Synthetic clips remain software fixtures only.
- Both visual paths use physically silent MP4s. The VLM—not a hand-engineered soccer classifier—produces the semantic label; deterministic code handles sampling, hashing, validation, and scoring.
- Qwen and Gemma use the same 72 decoded-frame records across the six comparison clips. Qwen groups them into six two-frame sheets; Gemma uses twelve one-frame sheets, so the comparison is explicitly representation-confounded and post hoc.
- Commentary is opened only after the visual result is sealed. It is a non-intervening, same-event consistency probe—not independent ground truth—and cannot change a visual prediction.
- The final deck contains 16 slides and 16 `[Sources]` note blocks. Its six embedded images re-hash exactly to the five audited originals from the prior deck plus the official Harvard VCG *Who's That Player?* teaser. Those assets are SoccerNet frames, a local demo screenshot, cited Wikimedia photographs, or that official research-system image. No image was AI-generated; PanoCoach figures were deliberately excluded because its paper identifies the relevant conceptual illustrations as DALL-E-generated.
- A no-install local browser slideshow renders the same 16 verified 1600×900 slide images. Space/arrows and Home/End were smoke-tested in the browser; the viewer was left open on slide 1 with the live demo in a second ready tab.
- The Dr. Tica Lin section accurately distinguishes Sportify's structured-evidence/text-LLM pipeline, VIRD's expert drill-down, and *Who's That Player?*'s inspect-and-repair result from this pilot's upstream visual-perception test. The adjacent-work section explicitly states that broad soccer QA and tool routing are prior work and narrows the proposed contribution to a controlled direct-VLM-versus-declared-tools study with answer-linked evidence.
- The live site contains six Qwen clip records, six commentary records, 18 hash-matching media/caption records, and no external network dependency. All six visual MP4s have no audio; all six review MP4s have audio.

## Results that must be stated exactly

| Run | Completed | Schema-valid | Allowed-window matches | Single-label exact | Median latency |
|---|---:|---:|---:|---:|---:|
| Gemma primary v1, untouched first pass | 3/6 | 3/6 | 1/6 | 0/2 | 110.624 s among completions |
| Gemma serving recovery v2, post hoc | 6/6 | 6/6 | 0/6 | 0/2 | 9.306 s |
| Qwen3.5-9B engineering comparison, post hoc | 6/6 | 6/6 | 3/6 | 1/2 | 9.9925 s |

The Qwen visual self-scores were 0.90 or 0.95 on all six clips, including all three errors. That is a high-self-score error pattern, not a calibration estimate. Its sealed ASR consistency probe produced 2 label-equality supports, 4 contradictions, and 0 uninformative cases.

These are six event-centered windows selected from one match. There are no background windows, point-label visibility was not human-adjudicated, and temporal/spatial grounding was not scored. The results are a case-level feasibility and failure analysis, not an accuracy estimate for a target population.

## Final deterministic checks

- Repository compilation plus full suite: **163 passed in 7.51 s** in the final verification script; a separate direct run also passed 163/163.
- Focused live-demo suite: **38 passed**.
- Focused commentary suite: **30 passed**.
- Native project scripts: doctor PASS; reproduction 25/25; redacted log collection PASS; smoke PASS; safe-reset preview only, with no deletion or move applied.
- Gemma loopback runtime: all 9 ownership, process-image, PID/port, receipt, health, and single-model checks PASS.
- Presentation: template-plan check PASS; template-fidelity check PASS; official overflow test PASS; 16 nonzero 1600×900 native renders; slide-by-slide visual QA PASS; 16/16 notes contain `[Sources]`; six embedded images match their audited source bytes; package sensitive-pattern scan found zero matches.
- Demo: receipt/index match; 18/18 media/caption hashes match; physical audio isolation PASS; HTTP 200; expected post-hoc/different-packaging disclosure present.
- Browser: the slideshow navigated from slide 1 to slide 16 and back by keyboard, loaded the new Dr. Lin slide at 1600×900, and logged no errors/warnings. The live-demo page loaded clip 5 with the frozen `yellow_card` result, commentary transcript, mapped label, and technical-inspection surface; its console errors/warnings were empty.
- Privacy: deck-package scan found no password, credential, API key, private key, absolute path, or private-directory disclosure. No restricted media was moved into a public artifact.
- Independent final reviewer: **GO; no blockers remain.** The reviewer inspected every slide at full size, recomputed the Qwen/Gemma metrics, verified the literature claims from primary sources, matched the Harvard image hash, and confirmed the loopback demo health. One minor preserved-layout observation—slide 11's zero-value donut label sits near the ring edge—was readable and non-blocking.

## Delivery hashes

| Artifact | SHA-256 |
|---|---|
| Final PowerPoint | `e25a98b19ffcae5a69866c8f7e32858c71d10dc1dbfb0c0391094d9488fae99e` |
| No-install browser slideshow | `c4fc5e523244792187db4d077096cd3529722aaa086510328bfe7b93c9aeab2c` |
| Canonical technical report | `bee66444851c606634df24b4d03de9fb8d2bf27d73bd58129081c968d206e31d` |
| Archit talk track | `53e7765001abdd4f54d78757c6c04278d6bd8c35c2e1e9e9c5874169a7ec50c5` |
| Dr. Lin and adjacent-work synthesis | `ef0d55295b75aaa5674c9f3de706d00b1374f7c1771b925f1c1c05b2d061096d` |
| Methodology audit | `c8693a920ad8675353848c93413aa85d093c611d325cd43ca300a8db0eb0a181` |
| Qwen visual summary | `94f590c12958e04a0144a99695e9ba86b5f5daa54efdf5cbe2ba5c751cc3ef7d` |
| Independent Qwen recomputation | `9d3c5b0cef8f92f08f4350afdd8f1ce32754be0e5860c088f163d3c8f0437deb` |
| Real-data doctor | `3938bf32a7216f85c84995d3e0a2b3fcf5621732b5f49bebf1a8028d76edac7a` |
| Final demo index | `de346f568c7d8cb7641f57c02351c8cedf299eee1200d37b82f2f0afdb132f4e` |
| Final demo receipt | `923e70692ce14a81b9b5aa32f0f4929c31b58277113ed1ea16f9c8214b4fb7ac` |

Private SoccerNet media and its derivatives remain non-redistributable. The live demo is appropriate only for the controlled local research presentation.
