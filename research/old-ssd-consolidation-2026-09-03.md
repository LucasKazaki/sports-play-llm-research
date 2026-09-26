# Old SSD consolidation receipt

## Outcome

The accessible source-only material from `D:\AI\projects\SportsPlayLLMResearch` was copied into the current project at `C:\AI\projects\SportsPlayLLMResearch` without overwriting newer or existing files.

- Source-only files copied: 11,427
- Source-only bytes copied: 748,671,938
- Copy policy: include subdirectories; skip junctions; do not replace existing, newer, or older destination files
- Post-copy dry run: 0 accessible source-only files and 0 accessible source-only bytes remain
- Existing project files overwritten: 0

Most of the recovered material was the local SoccerNet environment and Agent Studio history:

- `.venv-soccernet`: 10,157 files, about 570.1 MB
- `.agent`: 1,270 files, about 178.5 MB

## Protected source directories

Twenty-one directories on the old SSD deny read access to the current Windows account. Their current-project counterparts already exist, so permissions were left unchanged and no claim is made that their contents were byte-compared. This is the only remaining completeness caveat.

- `.agent/footballmaster-final-reproduction-20260827`
- `.agent/footballmaster-isolation-real-run`
- `.pytest_cache`
- `artifacts/footballmaster/pilot-v1`
- `artifacts/footballmaster/pilot-v1.backup-20260828T000900Z`
- `artifacts/footballmaster/pilot-v1.backup-20260828T001038Z`
- `artifacts/footballmaster/pilot-v1.backup-20260828T001431Z`
- `data/private/demo-soccernet-valid-qwen35-comparison-v1`
- `data/private/demo-soccernet-valid-qwen35-comparison-v1.backup-20260827T093605Z`
- `data/private/demo-soccernet-valid-qwen35-comparison-v1.backup-20260827T093843Z`
- `data/private/demo-soccernet-valid-qwen35-comparison-v1.backup-20260827T093956Z`
- `data/private/demo-soccernet-valid-recovery-v2`
- `data/private/demo-soccernet-valid-recovery-v2.backup-20260827T075634Z`
- `data/private/demo-soccernet-valid-recovery-v2.backup-20260827T081620Z`
- `data/private/demo-soccernet-valid-recovery-v2.backup-20260827T084910Z`
- `data/private/demo-soccernet-valid-recovery-v2.backup-20260827T091116Z`
- `data/private/demo-soccernet-valid-v1`
- `data/private/demo-soccernet-valid-v1.backup-20260827T073239Z`
- `data/private/demo-soccernet-valid-v1.backup-20260827T073515Z`
- `data/private/demo-soccernet-valid-v1.backup-20260827T085025Z`
- `data/private/demo-soccernet-valid-v1.backup-20260827T091116Z`

These protected paths are experiment outputs, caches, and private SoccerNet-derived material. No ACLs were weakened and no private footage was uploaded.

## Agent Studio project import

The legacy Agent Studio workspace was independently checked between the old SSD and the current Agent Studio repository: all 14 files and 56,309 bytes matched by path, size, and timestamp. A full hash-verified copy is preserved at:

`artifacts/agent-studio-soccer-research-complete-archive-2026-09-03`

This supplements the earlier six-file methodology import and preserves the full legacy workspace without creating a second scheduler or project authority.
