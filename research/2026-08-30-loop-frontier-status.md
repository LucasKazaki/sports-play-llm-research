# SoccerMaster Frontier Status

**Updated:** 2026-08-31T03:34:00Z

## Executive research status

The project has a verified real-footage corpus, a legally public real-footage
extension in controlled intake, and a reliable technical search pipeline. It
does **not** yet have evidence for coach-ready semantic event search. Earlier
long-form VLM outputs remain sealed as systems results only; they must not be
presented as accurate detection of goals, offsides, fouls, or player-specific
actions.

## Evidence currently available

- Local, authorized soccer corpus: 9 opaque game groups, 18 halves,
  50,120 seconds (13.9222 hours), and 3.407 GB of private media.
- Read-only data-expansion audit: 91/91 checks passed. The audit is metadata
  only and deliberately excludes media, labels, transcripts, source identities,
  and credentials.
- Local SoccerNet-Echoes overlay: 18 matching ASR half-files and 16,024
  segments. It is a future separate text-only or late-fusion ablation, never
  visual-model ground truth or post-hoc repair.
- SoccerDB mapping audit: zero exact joins to the current authorized corpus;
  SoccerDB metadata is not admitted to current training or evaluation.
- Separate open-data intake: the [SoccerTrack v2 official repository](https://github.com/AtomScott/SoccerTrack-v2)
  was pinned at revision `6f5c47cd3a5c38b074c44e9c98dfba48daa230d3`; its
  dataset video and annotation license is CC BY 4.0. First halves from official
  **training** match `117092` and official **test** match `128057`, with their
  matching BAS JSON files, are admitted under `data/open/soccertrack-v2/`.
  `117092` is 6,687,957,167 bytes (SHA-256
  `9fabe074b0c6fc5812a602dd4119f3e6cb724e2f06b8a3a1eb9358b9734c036e`);
  held-out `128057` is 3,312,813,154 bytes (SHA-256
  `3bc95a7bb31baec68be8d737e7b99fa083c595ba856e879106223a26548cbf23`).
  Direct-source, media/BAS, acquisition-only decode, split, and label-isolation
  checks passed. `117092` is prohibited from any held-out result; `128057` is
  held out, sealed, and unscored. Official test `132831` is absent because the
  official delivery returned a quota/unavailable HTML response instead of
  media; that response and its unpaired BAS container are quarantined outside
  the intake root, and no substitute was used. This is a new public-data lane,
  not a model result or a replacement for the sealed private evaluation.

## Evaluation state

`soccermaster-evidence-gated-v1` is pre-registered and independently checked.
It uses 40 held-out windows, one atomic VLM claim per window, blinded second
proposal, VLM-authored temporal evidence audit, and post-seal label comparison.
Deterministic code only validates/gates VLM outputs; it never assigns a soccer
event type. The protocol has no inference transport and has made zero new model
calls.

The protocol remains **data-binding pending**: it requires at least two newly
acquired held-out game groups that are disjoint from every historic VLM input,
plus a full-frame privacy/overlay audit. Until those gates pass, no new quality
metric, improvement claim, coach-utility claim, player identity claim, or
full-match search-readiness claim is allowed.

## Acquisition status

The authorized official downloader was attempted for a frozen fresh test
selection. Authorization OCR passed without persisting the credential, but the
provider endpoint actively refused the connection before any file was written.
This is an acquisition/network gate, not a model result and not a credential
failure.

In parallel, the SoccerTrack v2 intake above uses an explicitly public,
CC BY 4.0 source. It is not a substitute for a fresh disjoint SoccerNet cohort:
the source, license, camera domain, annotations, split, and evaluation question
will be versioned separately. No rights-ambiguous broadcast or public-TV footage
has been substituted.

The completed public intake is integrity-admitted but **evaluation-ineligible**:
it now contains one development game and one sealed, unscored official held-out
game, while the second official held-out delivery is provider-quota-blocked.
The intake receipt reports development=1, heldout=1,
`blocked_missing_official_test_games`, and `evidence_gated_eligible=false`.
No video frames were sent to a model, and the label-free retrieval catalog
remains disabled. A schema observation is logged rather than repaired: 1,007
of 3,142 BAS `gameTime` strings in `117092` lack a canonical half prefix.

## Local Agent Studio status

The Sports project now uses the local `openai/gpt-oss-20b` route for director,
researcher, developer, and QA roles; it is not routed to a generic hosted
worker. A fresh v4 exact-path local workspace-write task settled after the
Studio contention repair: task `61f0f2e1-32fb-43a5-9657-6da5d164241a`, run
`75bcaed2-8a70-4c66-ab21-520c601c3c3a`, artifact SHA-256
`533669ae4d5ee4b769cd528c247dbd66a52563462043fb5fabadb84fc0433566`, and
server-owned workspace-mutation receipt
`03a3af7100a66c7e3b4b279c7abcda109e331511be128f623fced2b2ccf854f0`.
The run used local LM Studio / `openai/gpt-oss-20b`; it is an execution proof,
not a research-quality claim. See
`.agent/agent-studio-sports-loop-verified-local-execution-2026-08-31.md` and
`research/local-loop-soccertrack-intake-readiness-2026-08-31-v4.md`.

The narrow route remains scoped: no browser, terminal, media, network, or
generic hosted-worker authority is granted. The legacy full-history polling path
was replaced with compact control-center/project-office reads; a later repair
fenced Company Runtime ownership before SQLite opens, prevents the watchdog
from spawning against a TCP-bound live owner, and treats SQLite busy/locked
contention as a deferred resource condition. The repair passed independent
review and the reloaded Studio kept one watchdog, one server, and healthy
compact endpoints after the v4 task.

## Next safe actions

1. Preserve and independently re-verify the completed SoccerTrack v2 receipt;
   keep `117092` development-only and `128057` sealed/unscored. Keep the
   documented `132831` provider-quota block quarantined; retry only the
   official delivery when it becomes available. Do not call a VLM on the public
   lane until a separately reviewed study is defined.
2. Restore access to the official authorized source through a documented,
   rights-compliant route; acquire and validate at least two fresh held-out
   game groups without changing historic seals.
3. Materialize the applicable data binding, history-overlap lock, window
   manifest, and full-frame overlay audit before authorizing any local VLM call.
4. Run the evidence-gated diagnostic locally, seal predictions before labels,
   and report accepted versus withheld claims separately.
5. Keep the live UI labelled as a technical-search demonstrator while semantic
   readiness remains a no-go, and keep the Studio's compact control-center view
   on the live polling path.
