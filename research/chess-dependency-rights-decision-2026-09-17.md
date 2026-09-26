# Chess dependency rights decision — 2026-09-17

**Superseded for local research on September 18:** the current user explicitly
authorizes local dependency setup and real public chess data. python-chess 1.10.0
and Stockfish 19 are now installed and have completed local engine work. The
historical HOLD below is not a current blocker. GPLv3 section 2 permits running
the program and private use; preserve notices and handle actual redistribution
obligations if a release is later proposed. See
`chess-autonomous-research-program-2026-09-18.md`. No creator-content, publication,
account-terms or paid-service authorization is inferred from this correction.

## Exact local observation

Company Runtime job e0dc4ea1-c850-422b-b821-67d90bc5e150 repaired the earlier
importer-sort failure and ran a local-only environment probe. The selected
.venv-soccernet Python has no chess or stockfish module, no Stockfish executable
on PATH, and no installed chess-related distribution. This is availability
evidence only, not chess competence or a license decision.

## Primary-source license receipt

- The [official python-chess repository](https://github.com/niklasf/python-chess)
  and [packaging metadata](https://github.com/niklasf/python-chess/blob/master/setup.py)
  identify python-chess as GPL-3.0-or-later.
- The [official Stockfish repository](https://github.com/official-stockfish/Stockfish)
  identifies Stockfish as GPL version 3 and notes separately sourced
  neural-network data.

These declarations do not authorize acquisition, installation, bundling,
distribution, or modification for this project.

## Decision: HOLD — user/compliance authority required

No package, binary, model, or data was downloaded or installed. Before use, the
user must either approve controlled internal GPL-v3-or-later dependency use
with a compliance review before any shared artifact, or provide an
already-approved local rules library and engine with version, SPDX, source URL,
checksum, and permitted-use record. Until then the demo remains evidence-only
and abstention-only; no legal replay, engine comparison, model generation,
training, or FIDE-level claim is allowed.
