# Soccer loop delivery recovery — 6 September 2026

Internal operational handoff, not a promoted research deliverable.

The canonical loop remains `sports-play-llm` in `C:/AI/projects/SportsPlayLLMResearch`. `soccer-research` was intentionally consolidated and archived on August 22; restarting it would duplicate authority. This recovery did not modify Studio runtime configuration, scheduling, or its database.

## Delivered and observed

- Started the existing dual-sport demo at `http://127.0.0.1:8771/` in foreground exec session `3198`. It remains a process in the current session, not a scheduled service. A hidden Start-Process attempt was automatically rejected; the normal foreground launch succeeded.
- Added `prototype/demo_readiness.py`. A real literal-search rehearsal passed all 23 checks: soccer availability, exact 96-window backend, both complete halves, explicit semantic NO-GO, blocked performance claims, label/audio exclusion, explicit query mode, valid result-to-media time bindings, two HTTP 206 media probes, and two saved query result sets.
- Browser search returned 12 candidates for “Show shots on goal.” Selecting the first **Play evidence** sought half 1 to the 30-minute span. Read-only browser inspection observed `currentTime=1809.745937`, `duration=2700.003`, `readyState=4`, `paused=false`, `398×224`, and `error=null`. The browser was closed after inspection; the server remains live.
- Corrected the launcher’s obsolete fixed query-model path by adding `-Model` and `-Endpoint` arguments. Defaults are `openai/gpt-oss-20b` and `http://127.0.0.1:1234/v1`; direct Python CLI defaults remain unchanged for backwards compatibility. Existing-session reuse reports the actual backend, query mode, and model and warns when literal mode is reused for a model request.
- Created `deliverables/archit-update-candidate-v2-2026-09-06.md` with exact evidence links and truthful systems/semantic scope. It still requires the repository’s sequential Luna review and Terra promotion gate.

## Loop-quality defect to prevent

`deliverables/archit-update-candidate-v1.md` contains placeholders, not completed evidence. `research/archit-coach-demo-evidence-reconciliation-candidate-v2.md` cites seven exact paths that are absent: `event_cards.json`, `search_queries.sql`, `logs/search.log`, `video_playback_demo.mp4`, `clip_categories.yaml`, `retrieval_interactions.json`, and `archit_update.md`. These old candidates are preserved for diagnosis and must not be promoted. A claim of file existence requires an existence/hash receipt. A progress timestamp, candidate filename, or model statement is not delivery evidence.

## Executable task contracts for the director

1. **Model-enabled demo rehearsal** — capabilities: project terminal, loopback HTTP, reserved local query-model lane, browser. Use the project virtualenv and an explicitly configured currently loaded text model; do not auto-download a model. In one owned demo session run `prototype/multisport_search_demo_server.py --host 127.0.0.1 --port 8772 --endpoint http://127.0.0.1:1234/v1 --model <verified-model-id>` and then `prototype/demo_readiness.py --url http://127.0.0.1:8772 --out artifacts/demo-local-model-rehearsal-v1 --require-local-model`. Acceptance requires all checks pass, actual `local_query_llm` interpretations without fallback, preserved raw request/response timings, and browser playback. Stop only that owned secondary demo when complete. Never mistake `/v1/models` listing for a successful inference.
2. **Official SoccerMaster radar refresh** — capabilities: first-party browser/source receipt, exact project file writer. Verify the official project, paper, code/checkpoint/license/input-contract surfaces against the last accepted packet. Write a versioned delta or observed-no-change receipt with time, exact URLs, source snippets, and hashes. No model/media/checkpoint download, license acceptance, or official-reproduction claim. This is independent of the query-model lane and should not wait behind it.
3. **Presentation candidate review** — capabilities: verified file receipts and reasoning-only GPT-5.6 Luna. Review candidate v2 against the hash-bound receipt packet, historic report, and exact existence results. Reject placeholders and unsupported file/path claims. Inspect the systems/semantic distinction, historic denominator units, literal-mode declaration, rights boundaries, and unrehearsed interactions. Resolve material defects in a new version, then have GPT-5.6 Terra inspect the exact candidate, verdict, and receipts before an exact promotion edit. Candidate writing and review must not run concurrently on the same version.

## Reproduce the completed local check

```powershell
.venv-soccernet/Scripts/python.exe prototype/demo_readiness.py --out artifacts/demo-readiness-next
.venv-soccernet/Scripts/python.exe -m pytest -q tests/test_demo_readiness.py
```

For an offline-model presentation rehearsal, start `scripts/start-coach-search-ui.ps1 -NoOpenBrowser -LiteralQueryFallback`. This avoids using a shared GPU and visibly labels the mode. For model mode, omit that switch and reserve the local-model lane first. No new VLM inference or semantic evaluation was performed in this recovery.
